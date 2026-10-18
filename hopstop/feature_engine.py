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

_DEFAULT_DEV_HMAC_KEY = "HOPSTOP_DEV_EPHEMERAL_KEY_OVERRIDE_IN_PROD"


def get_hmac_key_status() -> Dict[str, str]:
    """Reports whether HOPSTOP_HMAC_KEY is provisioned via environment/HSM."""
    env_key = os.environ.get("HOPSTOP_HMAC_KEY")
    if env_key:
        return {"mode": "HMAC-SHA256 (Environment/HSM key provisioned)", "key_source": "env:HOPSTOP_HMAC_KEY"}
    return {
        "mode": "HMAC-SHA256 (Development fallback key; set HOPSTOP_HMAC_KEY in production)",
        "key_source": "dev_fallback",
    }


def hash_account_id(raw_id: str, secret_key: Optional[str] = None) -> str:
    """Computes a 128-bit (32-hex) HMAC-SHA256 pseudonym (`ACCT_<32-hex>`) for an account ID."""
    if raw_id.startswith("ACCT_") and len(raw_id) >= 17:
        return raw_id
    key_str = secret_key or os.environ.get("HOPSTOP_HMAC_KEY") or _DEFAULT_DEV_HMAC_KEY
    digest = hmac.new(key_str.encode("utf-8"), raw_id.encode("utf-8"), hashlib.sha256).hexdigest()
    # 128-bit (32 hex chars) prevents birthday collisions up to >10^15 accounts
    return f"ACCT_{digest[:32].upper()}"


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

        # 9. Counterparty novelty: 1.0 if sender has not previously paid `dst_key`
        counterparty_novelty = 0.0 if dst_key in s_state.known_payees else 1.0

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
                s_state.known_payees.popitem(last=False)

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
