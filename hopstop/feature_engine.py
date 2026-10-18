"""Stateful, zero-leakage O(1) streaming feature engine for HopStop.

Key engineering guarantees:
1. True Amortized O(1) Sliding Windows (`SlidingWindow`):
   Each window maintains a FIFO deque alongside a reference-counted counterparty map
   (`cnt: Dict[str, int]`) and running currency sum (`total: float`). Both distinct
   counterparty degree (`len(w.cnt)`) and window volume (`w.total`) are read in O(1)
   time without rescanning the deque.
2. Strict Causal Ordering (Extract-Then-Update):
   Features for transaction `tx` at timestamp `t` are computed strictly from prior
   events before `tx` mutates sender or receiver state.
3. Bounded Memory (Receive-Only Eviction, Bounded Payee LRU, Idle Account TTL):
   - Receiver windows evict expired items on every incoming credit append.
   - `known_payees` per account is bounded by `max_known_payees` (LRU eviction).
   - Inactive accounts older than `idle_ttl_seconds` are periodically swept.
4. Keyed Pseudonymization (`HMAC-SHA256`):
   Account identifiers are pseudonymized via `HMAC-SHA256` using `HOPSTOP_HMAC_KEY`
   from the environment (or HSM-injected secret), producing 128-bit (32-hex-char)
   tokens (`ACCT_<32-hex>`) to prevent birthday-bound collisions at national scale.
   Internal engine state is keyed by these HMAC tokens so raw account IDs are not
   retained in feature state, logs, or outputs.
"""
from __future__ import annotations

import hashlib
import hmac
import math
import os
import secrets
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Tuple

from hopstop.data_generator import TransactionRecord


FEATURE_NAMES: List[str] = [
    "fan_in_1h",
    "fan_out_1h",
    "fan_in_24h",
    "fan_out_24h",
    "pass_through_ratio_15m",
    "pass_through_ratio_1h",
    "time_since_last_credit_log",
    "rapid_turnover_flag",
    "counterparty_novelty",
    "amount_zscore",
    "out_tx_velocity_1h",
    "payment_format_risk",
]

FORMAT_RISK_MAP: Dict[str, float] = {
    "Wire": 1.0,
    "ACH": 0.75,
    "Cash": 0.65,
    "Credit Card": 0.30,
    "Cheque": 0.20,
    "Reinvestment": 0.15,
}

# Never store a static secret key in source control: if HOPSTOP_HMAC_KEY is not injected
# via environment/HSM, generate a per-process 256-bit CSPRNG key via secrets.token_hex(32).
_PROCESS_EPHEMERAL_HMAC_KEY: str = secrets.token_hex(32)


def get_active_hmac_key(explicit_key: Optional[str] = None) -> str:
    """Returns explicit key, HOPSTOP_HMAC_KEY from environment/HSM, or 256-bit CSPRNG process key."""
    return explicit_key or os.environ.get("HOPSTOP_HMAC_KEY") or _PROCESS_EPHEMERAL_HMAC_KEY


def get_hmac_key_status() -> Dict[str, str]:
    """Reports whether HOPSTOP_HMAC_KEY is provisioned via environment/HSM or per-process CSPRNG."""
    env_key = os.environ.get("HOPSTOP_HMAC_KEY")
    if env_key:
        return {"mode": "HMAC-SHA256 (Environment/HSM key provisioned)", "key_source": "env:HOPSTOP_HMAC_KEY"}
    return {
        "mode": "HMAC-SHA256 (Per-process 256-bit CSPRNG ephemeral key; set HOPSTOP_HMAC_KEY for cross-restart persistence)",
        "key_source": "ephemeral_csprng_256bit",
    }


def hash_account_id(raw_id: str, secret_key: Optional[str] = None) -> str:
    """Computes a 128-bit (32-hex) HMAC-SHA256 pseudonym (`ACCT_<32-hex>`) for an account ID."""
    if raw_id.startswith("ACCT_") and len(raw_id) >= 37:
        return raw_id
    key_str = get_active_hmac_key(secret_key)
    digest = hmac.new(key_str.encode("utf-8"), raw_id.encode("utf-8"), hashlib.sha256).hexdigest()
    # 128-bit (32 hex chars) prevents birthday collisions up to >10^15 accounts
    return f"ACCT_{digest[:32].upper()}"


class PayeeBloomFilter:
    """Dual-generation rotating Bloom filter (`64 KB = 524,288 bits` per generation, `128 KB` total across both generations, `k=4` probes).

    Exact Capacity, Single- vs. Dual-Generation FPR & Dormant-Payee Horizon:
    - Each generation allocates `65,536 bytes = 524,288 bits` (`64 KB`) with `k=4` independent 19-bit probes (`0 .. 524,287`).
      When `prev_bits` is also active after rotation, total memory is `128 KB` (`1,048,576 bits` across the two generations).
    - Single-generation formula (`m = 524,288 bits`, `k = 4`):
        `FPR_1(n) = (1 - exp(-4 * n / 524288)) ** 4`
        * `n = 10,000` evicted payees: `0.00291%` (`2.91e-5`)
        * `n = 25,000` evicted payees (rotation limit): `0.0910%` (`9.10e-4`)
      (Note: if sized at half-width `m = 262,144 bits = 32 KB/gen` (`64 KB` total), `FPR_1(10,000) = 0.0401%`,
       `FPR_1(25,000) = 1.012%`, and dual-generation pre-rotation `FPR_2(25,000, 25,000) = 2.014%`.)
    - Dual-generation combined formula (`contains` queries `active_bits OR prev_bits`):
        `FPR_2(n_act, n_prev) = 1 - (1 - FPR_1(n_act)) * (1 - FPR_1(n_prev))`
        * At `n_act = 10,000, n_prev = 25,000` (`m = 524,288/gen`): `0.0939%`
        * Worst-case just before rotation (`n_act = 25,000, n_prev = 25,000`, `m = 524,288/gen`): `0.1819%` (`< 0.2%`)
    - Dormant-Payee Horizon (`> 60 days`):
      Because at most two 30-day (`2,592,000s`) / `25,000`-item generations (`active_bits` and `prev_bits`) are retained,
      a recurring payee who is both evicted from the `2,048`-entry LRU and dormant across two full rotations (`> 60 days`,
      such as a quarterly or annual vendor) ages out of both generations and is scored as novel (`counterparty_novelty = 1.0`)
      on their next transfer.
    """

    __slots__ = ("active_bits", "prev_bits", "active_count", "prev_count", "max_generation_items", "last_rotation_ts", "rotation_sec")

    BITS_PER_GEN = 524288  # 64 KB per generation (128 KB total when prev_bits is allocated)
    NUM_PROBES = 4

    def __init__(self, max_generation_items: int = 25000, rotation_sec: float = 2592000.0) -> None:
        self.active_bits = bytearray(65536)  # 524,288 bits = 64 KB per generation
        self.prev_bits: Optional[bytearray] = None
        self.active_count: int = 0
        self.prev_count: int = 0
        self.max_generation_items: int = max_generation_items
        self.last_rotation_ts: float = 0.0
        self.rotation_sec: float = rotation_sec

    @staticmethod
    def single_generation_fpr(n_items: int, m_bits: int = 524288, k: int = 4) -> float:
        """Exact theoretical false-positive probability `(1 - exp(-k * n / m)) ** k` for a single generation."""
        if n_items <= 0:
            return 0.0
        return (1.0 - math.exp((-k * n_items) / float(m_bits))) ** k

    @classmethod
    def dual_generation_fpr(cls, n_active: int, n_prev: int = 0, m_bits: int = 524288, k: int = 4) -> float:
        """Exact combined false-positive probability when querying both `active_bits` and `prev_bits`."""
        p_act = cls.single_generation_fpr(n_active, m_bits=m_bits, k=k)
        p_prv = cls.single_generation_fpr(n_prev, m_bits=m_bits, k=k)
        return 1.0 - (1.0 - p_act) * (1.0 - p_prv)

    @staticmethod
    def _probes(acct_token: str) -> Tuple[int, int, int, int]:
        # Derive 4 independent 19-bit bit-indices (0 .. 524,287) from 20 hex chars of HMAC token
        hex_part = (
            acct_token[5:25]
            if acct_token.startswith("ACCT_") and len(acct_token) >= 25
            else hashlib.sha256(acct_token.encode("utf-8")).hexdigest()[:20]
        )
        h1 = int(hex_part[0:5], 16) & 0x7FFFF
        h2 = int(hex_part[5:10], 16) & 0x7FFFF
        h3 = int(hex_part[10:15], 16) & 0x7FFFF
        h4 = int(hex_part[15:20], 16) & 0x7FFFF
        return h1, h2, h3, h4

    def _rotate(self, current_ts: float) -> None:
        self.prev_bits = self.active_bits
        self.prev_count = self.active_count
        self.active_bits = bytearray(65536)
        self.active_count = 0
        self.last_rotation_ts = current_ts

    def add(self, acct_token: str, current_ts: float = 0.0) -> None:
        if self.last_rotation_ts == 0.0 and current_ts > 0.0:
            self.last_rotation_ts = current_ts
        if self.active_count >= self.max_generation_items or (
            current_ts > 0.0 and self.last_rotation_ts > 0.0 and (current_ts - self.last_rotation_ts) >= self.rotation_sec
        ):
            self._rotate(current_ts)
        for idx in self._probes(acct_token):
            self.active_bits[idx >> 3] |= 1 << (idx & 7)
        self.active_count += 1

    def contains(self, acct_token: str) -> bool:
        probes = self._probes(acct_token)
        if all(self.active_bits[idx >> 3] & (1 << (idx & 7)) for idx in probes):
            return True
        if self.prev_bits is not None:
            return all(self.prev_bits[idx >> 3] & (1 << (idx & 7)) for idx in probes)
        return False


class SlidingWindow:
    """Amortized O(1) time-window tracker for distinct counterparties, transaction count, and volume."""

    __slots__ = ("q", "cnt", "total")

    def __init__(self) -> None:
        self.q: Deque[Tuple[float, str, float]] = deque()
        self.cnt: Dict[str, int] = {}
        self.total: float = 0.0

    def push(self, ts: float, peer: str, amt: float) -> None:
        """Appends a new event in O(1) time."""
        self.q.append((ts, peer, amt))
        self.cnt[peer] = self.cnt.get(peer, 0) + 1
        self.total += amt

    def evict(self, cutoff: float) -> None:
        """Evicts events strictly older than `cutoff` (`event_ts < cutoff`) in amortized O(1) time."""
        while self.q and self.q[0][0] < cutoff:
            _, peer, amt = self.q.popleft()
            rem = self.cnt.get(peer, 0) - 1
            if rem <= 0:
                self.cnt.pop(peer, None)
            else:
                self.cnt[peer] = rem
            self.total -= amt
        if not self.q:
            self.total = 0.0
        elif self.total < 0.0:
            self.total = 0.0

    @property
    def distinct_peers(self) -> float:
        """O(1) distinct counterparty count in the active window."""
        return float(len(self.cnt))

    @property
    def sum_amount(self) -> float:
        """O(1) total transaction amount in the active window."""
        return self.total

    @property
    def tx_count(self) -> float:
        """O(1) transaction count in the active window."""
        return float(len(self.q))


@dataclass
class AccountState:
    in_15m: SlidingWindow = field(default_factory=SlidingWindow)
    out_15m: SlidingWindow = field(default_factory=SlidingWindow)
    in_1h: SlidingWindow = field(default_factory=SlidingWindow)
    out_1h: SlidingWindow = field(default_factory=SlidingWindow)
    in_24h: SlidingWindow = field(default_factory=SlidingWindow)
    out_24h: SlidingWindow = field(default_factory=SlidingWindow)

    last_credit_sec: float = -1e9
    last_credit_amt: float = 0.0
    last_seen_sec: float = -1e9
    known_payees: OrderedDict[str, None] = field(default_factory=OrderedDict)
    payee_bloom: Optional[PayeeBloomFilter] = None

    # Online Welford statistics for outgoing transaction amounts
    tx_count: int = 0
    mean_amt: float = 0.0
    m2_amt: float = 0.0


class StreamingFeatureEngine:
    """Maintains bounded per-account sliding state and extracts 12 causal O(1) features."""

    def __init__(
        self,
        max_known_payees: int = 2048,
        idle_ttl_seconds: float = 172800.0,
        gc_interval: int = 10000,
        secret_key: Optional[str] = None,
    ) -> None:
        self.states: Dict[str, AccountState] = {}
        self.max_known_payees = max_known_payees
        self.idle_ttl_seconds = idle_ttl_seconds
        self.gc_interval = gc_interval
        self.secret_key = secret_key
        self._processed_count = 0

    def evict_idle_accounts(self, current_ts: float) -> int:
        """Evicts accounts that have had neither inbound nor outbound activity within `idle_ttl_seconds`."""
        cutoff = current_ts - self.idle_ttl_seconds
        stale_keys = [k for k, st in self.states.items() if st.last_seen_sec < cutoff]
        for k in stale_keys:
            del self.states[k]
        return len(stale_keys)

    def extract_and_update(self, tx: TransactionRecord) -> List[float]:
        """Extracts 12 causal features for `tx` using ONLY prior history, then updates sender & receiver states."""
        t = float(tx.epoch_sec)
        src_key = hash_account_id(tx.from_account, self.secret_key)
        dst_key = hash_account_id(tx.to_account, self.secret_key)
        amt = float(tx.amount_paid)

        s_state = self.states.get(src_key)
        if s_state is None:
            s_state = AccountState()
            self.states[src_key] = s_state

        # 0. Evict expired entries from sender sliding windows in amortized O(1)
        s_state.in_15m.evict(t - 900.0)
        s_state.out_15m.evict(t - 900.0)
        s_state.in_1h.evict(t - 3600.0)
        s_state.out_1h.evict(t - 3600.0)
        s_state.in_24h.evict(t - 86400.0)
        s_state.out_24h.evict(t - 86400.0)

        # 1-4. Fan-in and fan-out degrees in O(1) via reference-counted dict length
        fan_in_1h = s_state.in_1h.distinct_peers
        fan_out_1h = s_state.out_1h.distinct_peers
        fan_in_24h = s_state.in_24h.distinct_peers
        fan_out_24h = s_state.out_24h.distinct_peers

        # 5-6. Pass-through ratios: 15m outflow / 15m inflow and 1h outflow / 1h inflow
        in_sum_15m = s_state.in_15m.sum_amount
        out_sum_15m_prior = s_state.out_15m.sum_amount
        in_sum_1h = s_state.in_1h.sum_amount
        out_sum_1h_prior = s_state.out_1h.sum_amount

        pass_through_ratio_15m = (
            min(5.0, (out_sum_15m_prior + amt) / (in_sum_15m + 1.0))
            if in_sum_15m > 0.0
            else 0.0
        )
        pass_through_ratio_1h = (
            min(5.0, (out_sum_1h_prior + amt) / (in_sum_1h + 1.0))
            if in_sum_1h > 0.0
            else 0.0
        )

        # 7. Time since last credit (log-scaled seconds)
        dt_credit = max(1.0, t - s_state.last_credit_sec) if s_state.last_credit_sec > 0 else 86400.0
        time_since_last_credit_log = math.log1p(min(dt_credit, 86400.0))

        # 8. Rapid turnover flag:
        #    1.0 if credit within 15m (<=900s), inflow >= 5000, and >=65% 15m pass-through;
        #    0.5 if credit within 15m-60m (<=3600s), inflow >= 5000, and >=65% 1h pass-through (catches 20m delay evasion);
        #    0.0 otherwise.
        if dt_credit <= 900.0 and in_sum_15m >= 5000.0 and pass_through_ratio_15m >= 0.65:
            rapid_turnover_flag = 1.0
        elif dt_credit <= 3600.0 and in_sum_1h >= 5000.0 and pass_through_ratio_1h >= 0.65:
            rapid_turnover_flag = 0.5
        else:
            rapid_turnover_flag = 0.0

        # 9. Counterparty novelty: 0.0 if recipient is in exact LRU or overflow 64-kbit Bloom filter
        is_known_payee = (dst_key in s_state.known_payees) or (
            s_state.payee_bloom is not None and s_state.payee_bloom.contains(dst_key)
        )
        counterparty_novelty = 0.0 if is_known_payee else 1.0

        # 10. Sender amount z-score (online Welford mean/variance)
        if s_state.tx_count >= 2:
            var = max(1.0, s_state.m2_amt / (s_state.tx_count - 1))
            std = math.sqrt(var)
            amount_zscore = max(-3.0, min(10.0, (amt - s_state.mean_amt) / std))
        else:
            amount_zscore = math.log1p(amt) / 5.0

        # 11. Outgoing transaction count velocity in last 1 hour (O(1))
        out_tx_velocity_1h = s_state.out_1h.tx_count

        # 12. Payment format risk weight
        payment_format_risk = FORMAT_RISK_MAP.get(tx.payment_format, 0.5)

        features = [
            fan_in_1h,
            fan_out_1h,
            fan_in_24h,
            fan_out_24h,
            pass_through_ratio_15m,
            pass_through_ratio_1h,
            time_since_last_credit_log,
            rapid_turnover_flag,
            counterparty_novelty,
            amount_zscore,
            out_tx_velocity_1h,
            payment_format_risk,
        ]

        # --- State Update (strictly AFTER feature extraction) ---
        s_state.out_15m.push(t, dst_key, amt)
        s_state.out_1h.push(t, dst_key, amt)
        s_state.out_24h.push(t, dst_key, amt)
        s_state.last_seen_sec = t

        if dst_key in s_state.known_payees:
            s_state.known_payees.move_to_end(dst_key)
        else:
            s_state.known_payees[dst_key] = None
            if len(s_state.known_payees) > self.max_known_payees:
                evicted_payee, _ = s_state.known_payees.popitem(last=False)
                if s_state.payee_bloom is None:
                    s_state.payee_bloom = PayeeBloomFilter()
                s_state.payee_bloom.add(evicted_payee, t)

        s_state.tx_count += 1
        delta = amt - s_state.mean_amt
        s_state.mean_amt += delta / s_state.tx_count
        delta2 = amt - s_state.mean_amt
        s_state.m2_amt += delta * delta2

        r_state = self.states.get(dst_key)
        if r_state is None:
            r_state = AccountState()
            self.states[dst_key] = r_state

        # Evict expired entries on receiver windows BEFORE appending so receive-only accounts stay bounded
        r_state.in_15m.evict(t - 900.0)
        r_state.in_1h.evict(t - 3600.0)
        r_state.in_24h.evict(t - 86400.0)

        r_state.in_15m.push(t, src_key, amt)
        r_state.in_1h.push(t, src_key, amt)
        r_state.in_24h.push(t, src_key, amt)
        r_state.last_credit_sec = t
        r_state.last_credit_amt = amt
        r_state.last_seen_sec = t

        self._processed_count += 1
        if self.gc_interval > 0 and (self._processed_count % self.gc_interval == 0):
            self.evict_idle_accounts(t)

        return features
