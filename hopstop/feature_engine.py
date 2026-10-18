"""Stateful, zero-leakage streaming feature engine for HopStop.

Computes 12 real-time graph-velocity and pass-through features per outgoing
transfer in O(1) amortized time using sliding deques over past events only.
"""
from __future__ import annotations

import hashlib
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Set, Tuple

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

FORMAT_RISK_MAP = {
    "Wire": 1.0,
    "ACH": 0.75,
    "Cash": 0.65,
    "Credit Card": 0.30,
    "Cheque": 0.20,
    "Reinvestment": 0.15,
}


def hash_account_id(raw_id: str, salt: str = "IBMZ_HOPSTOP_SALT_2026") -> str:
    """One-way SHA-256 hash of account identifier so no raw PII enters logs/models."""
    digest = hashlib.sha256(f"{salt}:{raw_id}".encode("utf-8")).hexdigest()
    return f"ACCT_{digest[:12].upper()}"


@dataclass
class AccountState:
    # Deques of (epoch_sec, counterparty_hash, amount)
    in_15m: Deque[Tuple[float, str, float]] = field(default_factory=deque)
    in_1h: Deque[Tuple[float, str, float]] = field(default_factory=deque)
    out_1h: Deque[Tuple[float, str, float]] = field(default_factory=deque)
    in_24h: Deque[Tuple[float, str, float]] = field(default_factory=deque)
    out_24h: Deque[Tuple[float, str, float]] = field(default_factory=deque)

    last_credit_sec: float = -1e9
    last_credit_amt: float = 0.0
    known_payees: Set[str] = field(default_factory=set)

    # Online Welford statistics for outgoing transaction amounts
    tx_count: int = 0
    mean_amt: float = 0.0
    m2_amt: float = 0.0


class StreamingFeatureEngine:
    """Maintains in-memory per-account state and extracts causal features before updating state."""

    def __init__(self) -> None:
        self.states: Dict[str, AccountState] = {}

    @staticmethod
    def _evict_old(q: Deque[Tuple[float, str, float]], cutoff: float) -> None:
        while q and q[0][0] < cutoff:
            q.popleft()

    def extract_and_update(self, tx: TransactionRecord) -> List[float]:
        """Extracts 12 causal features for `tx` using ONLY prior history, then updates sender & receiver states."""
        t = tx.epoch_sec
        src = tx.from_account
        dst = tx.to_account
        amt = float(tx.amount_paid)

        s_state = self.states.get(src)
        if s_state is None:
            s_state = AccountState()
            self.states[src] = s_state

        # Evict expired entries from sender sliding windows
        self._evict_old(s_state.in_15m, t - 900.0)
        self._evict_old(s_state.in_1h, t - 3600.0)
        self._evict_old(s_state.out_1h, t - 3600.0)
        self._evict_old(s_state.in_24h, t - 86400.0)
        self._evict_old(s_state.out_24h, t - 86400.0)

        # 1-4. Fan-in and fan-out degrees (unique counterparties in 1h and 24h)
        fan_in_1h = float(len({peer for _, peer, _ in s_state.in_1h}))
        fan_out_1h = float(len({peer for _, peer, _ in s_state.out_1h}))
        fan_in_24h = float(len({peer for _, peer, _ in s_state.in_24h}))
        fan_out_24h = float(len({peer for _, peer, _ in s_state.out_24h}))

        # 5-6. Pass-through ratios (money leaving vs money recently credited)
        in_sum_15m = sum(a for _, _, a in s_state.in_15m)
        in_sum_1h = sum(a for _, _, a in s_state.in_1h)
        out_sum_1h_prior = sum(a for _, _, a in s_state.out_1h)

        pass_through_15m = (
            min(5.0, (out_sum_1h_prior + amt) / (in_sum_15m + 1.0))
            if in_sum_15m > 0.0
            else 0.0
        )
        pass_through_1h = (
            min(5.0, (out_sum_1h_prior + amt) / (in_sum_1h + 1.0))
            if in_sum_1h > 0.0
            else 0.0
        )

        # 7. Time since last credit (log-scaled seconds)
        dt_credit = max(1.0, t - s_state.last_credit_sec) if s_state.last_credit_sec > 0 else 86400.0
        time_since_last_credit_log = math.log1p(min(dt_credit, 86400.0))

        # 8. Rapid turnover flag: recent credit within 15 min AND outgoing transfer drains >= 20% of recent credit
        rapid_turnover_flag = (
            1.0
            if (in_sum_15m > 5000.0 and (out_sum_1h_prior + amt) >= 0.22 * in_sum_15m)
            else 0.0
        )

        # 9. Counterparty novelty: 1.0 if sender has never paid `dst` before
        counterparty_novelty = 0.0 if dst in s_state.known_payees else 1.0

        # 10. Sender amount z-score
        if s_state.tx_count >= 2:
            var = max(1.0, s_state.m2_amt / (s_state.tx_count - 1))
            std = math.sqrt(var)
            amount_zscore = max(-3.0, min(10.0, (amt - s_state.mean_amt) / std))
        else:
            amount_zscore = math.log1p(amt) / 5.0

        # 11. Outgoing transaction count velocity in last 1 hour
        out_tx_velocity_1h = float(len(s_state.out_1h))

        # 12. Payment format risk weight
        payment_format_risk = FORMAT_RISK_MAP.get(tx.payment_format, 0.5)

        features = [
            fan_in_1h,
            fan_out_1h,
            fan_in_24h,
            fan_out_24h,
            pass_through_15m,
            pass_through_1h,
            time_since_last_credit_log,
            rapid_turnover_flag,
            counterparty_novelty,
            amount_zscore,
            out_tx_velocity_1h,
            payment_format_risk,
        ]

        # --- State Update (strictly AFTER feature extraction) ---
        s_state.out_1h.append((t, dst, amt))
        s_state.out_24h.append((t, dst, amt))
        s_state.known_payees.add(dst)
        s_state.tx_count += 1
        delta = amt - s_state.mean_amt
        s_state.mean_amt += delta / s_state.tx_count
        delta2 = amt - s_state.mean_amt
        s_state.m2_amt += delta * delta2

        r_state = self.states.get(dst)
        if r_state is None:
            r_state = AccountState()
            self.states[dst] = r_state
        r_state.in_15m.append((t, src, amt))
        r_state.in_1h.append((t, src, amt))
        r_state.in_24h.append((t, src, amt))
        r_state.last_credit_sec = t
        r_state.last_credit_amt = amt

        return features
