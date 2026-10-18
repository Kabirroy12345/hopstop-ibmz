"""Policy Decision & Tamper-Evident Audit Engine for HopStop.

1. Calibrates decision thresholds (`HOLD` and `STEP_UP`) against a bank's
   fixed analyst alert budget (default 1.0% of transaction volume).
2. Produces structured real-time decisions (`ALLOW`, `STEP_UP`, `HOLD`)
   with Top-3 reason codes and hash-chained audit records for FIU-IND / 1930
   cybercrime compliance.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from typing import Any, Dict, List

from hopstop.data_generator import TransactionRecord
from hopstop.feature_engine import hash_account_id


@dataclass
class PolicyDecision:
    tx_id: int
    timestamp: str
    from_account_hash: str
    to_account_hash: str
    from_bank: int
    to_bank: int
    amount: float
    currency: str
    payment_format: str
    risk_score: float
    action: str  # ALLOW | STEP_UP | HOLD
    reason_codes: List[Dict[str, Any]]
    chain_id: int
    hop_number: int
    typology: str
    prev_audit_hash: str
    audit_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PolicyEngine:
    """Applies alert-budget-calibrated thresholds and maintains a hash-chained audit log."""

    def __init__(self, hold_threshold: float = 0.80, step_up_threshold: float = 0.60) -> None:
        self.hold_threshold = hold_threshold
        self.step_up_threshold = step_up_threshold
        self.last_audit_hash = "0" * 64
        self.audit_chain: List[PolicyDecision] = []

    def calibrate_thresholds(
        self, scores: List[float], alert_budget_rate: float = 0.01, hold_share: float = 0.55
    ) -> Tuple[float, float]:
        """Sets step_up and hold thresholds to match the exact analyst alert budget rate."""
        if not scores:
            return self.hold_threshold, self.step_up_threshold
        sorted_s = sorted(scores, reverse=True)
        n = len(sorted_s)
        alert_k = max(1, min(n - 1, int(n * alert_budget_rate)))
        hold_k = max(1, min(alert_k, int(alert_k * hold_share)))
        self.step_up_threshold = round(sorted_s[alert_k], 6)
        self.hold_threshold = round(sorted_s[hold_k], 6)
        return self.hold_threshold, self.step_up_threshold

    def evaluate(
        self,
        tx: TransactionRecord,
        risk_score: float,
        reason_codes: List[Dict[str, Any]],
        record_audit: bool = True,
    ) -> PolicyDecision:
        if risk_score >= self.hold_threshold:
            action = "HOLD"
        elif risk_score >= self.step_up_threshold:
            action = "STEP_UP"
        else:
            action = "ALLOW"

        src_hash = hash_account_id(tx.from_account)
        dst_hash = hash_account_id(tx.to_account)

        prev_hash = self.last_audit_hash
        if action in ("HOLD", "STEP_UP") and record_audit:
            payload = (
                f"{prev_hash}|{tx.tx_id}|{tx.timestamp}|{src_hash}|{dst_hash}|"
                f"{tx.amount_paid:.2f}|{risk_score:.6f}|{action}"
            )
            curr_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            self.last_audit_hash = curr_hash
        else:
            curr_hash = prev_hash

        decision = PolicyDecision(
            tx_id=tx.tx_id,
            timestamp=tx.timestamp,
            from_account_hash=src_hash,
            to_account_hash=dst_hash,
            from_bank=tx.from_bank,
            to_bank=tx.to_bank,
            amount=tx.amount_paid,
            currency=tx.payment_currency,
            payment_format=tx.payment_format,
            risk_score=round(risk_score, 4),
            action=action,
            reason_codes=reason_codes if action != "ALLOW" else [],
            chain_id=tx.chain_id,
            hop_number=tx.hop_number,
            typology=tx.typology,
            prev_audit_hash=prev_hash[:16],
            audit_hash=curr_hash[:16],
        )
        if action in ("HOLD", "STEP_UP") and record_audit and len(self.audit_chain) < 500:
            self.audit_chain.append(decision)
        return decision
