"""Policy Decision & Verifiable Cryptographic Audit Engine for HopStop.

Key engineering guarantees:
1. Strict Separation of Production Decisions vs. Ground-Truth Labels:
   `PolicyDecision` contains only production fields (pseudonymized account hashes,
   banks, amount, currency, risk score, action, model version, thresholds, TreeSHAP
   reason codes, full 64-hex SHA-256 chain hashes, and HMAC signature). Ground-truth
   evaluation labels (`is_laundering`, `chain_id`, `hop_number`, `typology`) never
   appear in production decision records.
2. Full-Length Verifiable SHA-256 Hash Chain + HMAC Authentication:
   - Stores full 64-character hex SHA-256 digests (`prev_audit_hash`, `audit_hash`).
   - Canonical payload includes `prev_audit_hash`, `tx_id`, `timestamp`,
     `from_account_hash`, `to_account_hash`, `amount`, `currency`, `risk_score`,
     `action`, `model_version`, `hold_threshold`, `step_up_threshold`, and
     canonical JSON of `reason_codes`.
   - Authenticates each block with `HMAC-SHA256` (`hmac_signature`) keyed via
     `HOPSTOP_AUDIT_HMAC_KEY`.
   - Provides `verify_chain()` to cryptographically verify any sequence of audit
     records from genesis (`"0" * 64`) and detect tampering.
3. Thread Safety & Append-Only Persistence:
   - Uses a `threading.Lock` around chain state transitions.
   - Supports optional append-only JSONL file persistence (`audit_log_path`).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from hopstop.data_generator import TransactionRecord
from hopstop.feature_engine import get_active_hmac_key, hash_account_id


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
    model_version: str
    hold_threshold: float
    step_up_threshold: float
    reason_codes: List[Dict[str, Any]]
    prev_audit_hash: str  # Full 64-hex SHA-256
    audit_hash: str       # Full 64-hex SHA-256
    hmac_signature: str   # Full 64-hex HMAC-SHA256

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PolicyEngine:
    """Applies validation-calibrated thresholds and maintains a thread-safe, verifiable audit log."""

    def __init__(
        self,
        hold_threshold: float = 0.80,
        step_up_threshold: float = 0.60,
        model_version: str = "hopstop-gbdt-v2.1",
        audit_log_path: Optional[Path] = None,
        audit_hmac_key: Optional[str] = None,
        log_allow_decisions: bool = False,
        max_memory_records: int = 5000,
    ) -> None:
        self.hold_threshold = round(float(hold_threshold), 6)
        self.step_up_threshold = round(float(step_up_threshold), 6)
        self.model_version = model_version
        self.audit_log_path = audit_log_path
        self.audit_hmac_key = (
            audit_hmac_key
            or os.environ.get("HOPSTOP_AUDIT_HMAC_KEY")
            or get_active_hmac_key()
        )
        self.log_allow_decisions = log_allow_decisions
        self.max_memory_records = max_memory_records
        self.last_audit_hash: str = "0" * 64
        self.audit_chain: List[PolicyDecision] = []
        self._lock = threading.Lock()

        if self.audit_log_path is not None:
            self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)

    def calibrate_thresholds(
        self,
        validation_scores: List[float],
        alert_budget_rate: float = 0.01,
        hold_share: float = 0.55,
    ) -> Tuple[float, float]:
        """Calibrates `hold_threshold` and `step_up_threshold` on validation-set scores."""
        if not validation_scores:
            return self.hold_threshold, self.step_up_threshold
        sorted_s = sorted(validation_scores, reverse=True)
        n = len(sorted_s)
        alert_k = max(1, min(n - 1, int(n * alert_budget_rate)))
        hold_k = max(1, min(alert_k, int(alert_k * hold_share)))
        self.step_up_threshold = round(sorted_s[alert_k], 6)
        self.hold_threshold = round(sorted_s[hold_k], 6)
        return self.hold_threshold, self.step_up_threshold

    @staticmethod
    def compute_canonical_payload(
        prev_hash: str,
        tx_id: int,
        timestamp: str,
        from_account_hash: str,
        to_account_hash: str,
        amount: float,
        currency: str,
        risk_score: float,
        action: str,
        model_version: str,
        hold_threshold: float,
        step_up_threshold: float,
        reason_codes: List[Dict[str, Any]],
    ) -> str:
        reasons_json = json.dumps(reason_codes, sort_keys=True, separators=(",", ":"))
        return (
            f"{prev_hash}|{tx_id}|{timestamp}|{from_account_hash}|{to_account_hash}|"
            f"{amount:.2f}|{currency}|{risk_score:.6f}|{action}|{model_version}|"
            f"{hold_threshold:.6f}|{step_up_threshold:.6f}|{reasons_json}"
        )

    @staticmethod
    def compute_audit_hashes(
        canonical_payload: str, hmac_key: str
    ) -> Tuple[str, str]:
        audit_hash = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
        sig = hmac.new(
            hmac_key.encode("utf-8"), audit_hash.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return audit_hash, sig

    def evaluate(
        self,
        tx: TransactionRecord,
        risk_score: float,
        reason_codes: List[Dict[str, Any]],
        record_audit: bool = True,
    ) -> PolicyDecision:
        rounded_score = round(float(risk_score), 6)
        if rounded_score >= self.hold_threshold:
            action = "HOLD"
        elif rounded_score >= self.step_up_threshold:
            action = "STEP_UP"
        else:
            action = "ALLOW"

        src_hash = hash_account_id(tx.from_account)
        dst_hash = hash_account_id(tx.to_account)
        active_reasons = reason_codes if (action != "ALLOW" or self.log_allow_decisions) else reason_codes

        should_chain = record_audit and (action in ("HOLD", "STEP_UP") or self.log_allow_decisions)

        with self._lock:
            prev_hash = self.last_audit_hash
            payload = self.compute_canonical_payload(
                prev_hash=prev_hash,
                tx_id=tx.tx_id,
                timestamp=tx.timestamp,
                from_account_hash=src_hash,
                to_account_hash=dst_hash,
                amount=float(tx.amount_paid),
                currency=tx.payment_currency,
                risk_score=rounded_score,
                action=action,
                model_version=self.model_version,
                hold_threshold=self.hold_threshold,
                step_up_threshold=self.step_up_threshold,
                reason_codes=active_reasons,
            )
            curr_hash, hmac_sig = self.compute_audit_hashes(payload, self.audit_hmac_key)

            decision = PolicyDecision(
                tx_id=tx.tx_id,
                timestamp=tx.timestamp,
                from_account_hash=src_hash,
                to_account_hash=dst_hash,
                from_bank=tx.from_bank,
                to_bank=tx.to_bank,
                amount=round(float(tx.amount_paid), 2),
                currency=tx.payment_currency,
                payment_format=tx.payment_format,
                risk_score=rounded_score,
                action=action,
                model_version=self.model_version,
                hold_threshold=self.hold_threshold,
                step_up_threshold=self.step_up_threshold,
                reason_codes=active_reasons,
                prev_audit_hash=prev_hash,
                audit_hash=curr_hash,
                hmac_signature=hmac_sig,
            )

            if should_chain:
                self.last_audit_hash = curr_hash
                if len(self.audit_chain) < self.max_memory_records:
                    self.audit_chain.append(decision)
                if self.audit_log_path is not None:
                    with self.audit_log_path.open("a", encoding="utf-8") as af:
                        af.write(json.dumps(decision.to_dict(), sort_keys=True) + "\n")

        return decision

    @classmethod
    def verify_chain(
        cls,
        records: List[PolicyDecision],
        audit_hmac_key: Optional[str] = None,
        genesis_hash: str = "0" * 64,
    ) -> Tuple[bool, str]:
        """Re-computes every SHA-256 link and HMAC-SHA256 signature from genesis to verify integrity."""
        key = audit_hmac_key or os.environ.get("HOPSTOP_AUDIT_HMAC_KEY") or get_active_hmac_key()
        expected_prev = genesis_hash

        for idx, rec in enumerate(records):
            if rec.prev_audit_hash != expected_prev:
                return (
                    False,
                    f"Chain link mismatch at index {idx} (tx_id={rec.tx_id}): "
                    f"expected prev_audit_hash={expected_prev}, got {rec.prev_audit_hash}",
                )
            payload = cls.compute_canonical_payload(
                prev_hash=rec.prev_audit_hash,
                tx_id=rec.tx_id,
                timestamp=rec.timestamp,
                from_account_hash=rec.from_account_hash,
                to_account_hash=rec.to_account_hash,
                amount=float(rec.amount),
                currency=rec.currency,
                risk_score=float(rec.risk_score),
                action=rec.action,
                model_version=rec.model_version,
                hold_threshold=float(rec.hold_threshold),
                step_up_threshold=float(rec.step_up_threshold),
                reason_codes=rec.reason_codes,
            )
            expected_hash, expected_sig = cls.compute_audit_hashes(payload, key)
            if not hmac.compare_digest(rec.audit_hash, expected_hash):
                return (
                    False,
                    f"Payload SHA-256 mismatch at index {idx} (tx_id={rec.tx_id}): "
                    f"expected {expected_hash}, got {rec.audit_hash}",
                )
            if not hmac.compare_digest(rec.hmac_signature, expected_sig):
                return (
                    False,
                    f"HMAC signature verification failed at index {idx} (tx_id={rec.tx_id})",
                )
            expected_prev = rec.audit_hash

        return True, f"Verified {len(records)} hash-chained audit records from genesis."
