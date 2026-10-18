"""Automated unit and property test suite for HopStop.

Covers:
1. O(1) SlidingWindow exactness against brute-force window scans.
2. Strict causality (future events cannot alter past features) & receive-only eviction.
3. Exact path-dependent TreeSHAP additivity identity and signed attributions.
4. Full 64-hex SHA-256 + HMAC-SHA256 audit chain verification and tamper detection.
5. Production PolicyDecision isolation from ground-truth evaluation labels & JSON model serialization.
"""
from __future__ import annotations

import copy
import math
import tempfile
import unittest
from pathlib import Path

from hopstop.data_generator import TransactionRecord, generate_aml_dataset
from hopstop.feature_engine import (
    FEATURE_NAMES,
    SlidingWindow,
    StreamingFeatureEngine,
    hash_account_id,
)
from hopstop.ibmz_runtime import (
    LogisticRegressionBaseline,
    SnapMLAcceleratedScorer,
    VelocityRulesBaseline,
)
from hopstop.policy_engine import PolicyEngine


class TestHopStopSuite(unittest.TestCase):
    def test_sliding_window_o1_exactness(self) -> None:
        """Verifies O(1) SlidingWindow matches brute-force set/sum computation across evictions."""
        win = SlidingWindow()
        events = [
            (100.0, "PEER_A", 500.0),
            (250.0, "PEER_B", 1200.0),
            (400.0, "PEER_A", 300.0),
            (950.0, "PEER_C", 2000.0),
            (1200.0, "PEER_B", 800.0),
        ]
        active = []
        for ts, peer, amt in events:
            cutoff = ts - 600.0
            win.evict(cutoff)
            active = [(t, p, a) for (t, p, a) in active if t >= cutoff]

            win.push(ts, peer, amt)
            active.append((ts, peer, amt))

            expected_peers = float(len({p for _, p, _ in active}))
            expected_sum = sum(a for _, _, a in active)
            self.assertEqual(win.distinct_peers, expected_peers)
            self.assertAlmostEqual(win.sum_amount, expected_sum, places=6)
            self.assertEqual(win.tx_count, float(len(active)))

    def test_strict_causality_no_future_leakage(self) -> None:
        """Verifies that future transactions (t' > t) have zero effect on features extracted at time t."""
        stream_base = [
            TransactionRecord(
                tx_id=1,
                timestamp="2026/09/01 01:00:00",
                epoch_sec=3600.0,
                from_bank=10,
                from_account="ACC_VICTIM",
                to_bank=12,
                to_account="ACC_MULE",
                amount_received=100000.0,
                receiving_currency="INR",
                amount_paid=100000.0,
                payment_currency="INR",
                payment_format="Wire",
            ),
            TransactionRecord(
                tx_id=2,
                timestamp="2026/09/01 01:04:00",
                epoch_sec=3840.0,
                from_bank=12,
                from_account="ACC_MULE",
                to_bank=15,
                to_account="ACC_LAYER1",
                amount_received=95000.0,
                receiving_currency="INR",
                amount_paid=95000.0,
                payment_currency="INR",
                payment_format="Wire",
            ),
        ]
        future_events = [
            TransactionRecord(
                tx_id=3,
                timestamp="2026/09/01 01:10:00",
                epoch_sec=4200.0,
                from_bank=12,
                from_account="ACC_MULE",
                to_bank=19,
                to_account="ACC_LAYER2",
                amount_received=500000.0,
                receiving_currency="INR",
                amount_paid=500000.0,
                payment_currency="INR",
                payment_format="Wire",
            ),
        ]

        fe1 = StreamingFeatureEngine()
        feats_without_future = [fe1.extract_and_update(tx) for tx in stream_base]

        fe2 = StreamingFeatureEngine()
        feats_with_future = [fe2.extract_and_update(tx) for tx in (stream_base + future_events)]

        self.assertEqual(feats_without_future[0], feats_with_future[0])
        self.assertEqual(feats_without_future[1], feats_with_future[1])

        # Verify 15m pass-through ratio and rapid_turnover_flag on tx #2
        pt_15m_idx = FEATURE_NAMES.index("pass_through_ratio_15m")
        rapid_idx = FEATURE_NAMES.index("rapid_turnover_flag")
        self.assertAlmostEqual(feats_without_future[1][pt_15m_idx], 95000.0 / 100001.0, places=4)
        self.assertEqual(feats_without_future[1][rapid_idx], 1.0)

        # Verify engine state is keyed by HMAC digest, not raw account strings
        self.assertNotIn("ACC_MULE", fe1.states)
        self.assertIn(hash_account_id("ACC_MULE"), fe1.states)

    def test_treeshap_additivity_and_signed_attributions(self) -> None:
        """Verifies exact TreeSHAP additivity identity and negative SHAP values on benign payroll."""
        records, _ = generate_aml_dataset(n_normal=2500, n_chains=20, n_accounts=400, days=5, seed=7)
        fe = StreamingFeatureEngine()
        X = [fe.extract_and_update(r) for r in records]
        y = [r.is_laundering for r in records]

        scorer = SnapMLAcceleratedScorer(n_trees=16, learning_rate=0.18)
        scorer.fit(X, y, pos_weight=12.0)

        # Check exact Shapley additivity: sum(phi) + expected_log_odds == raw_margin(x)
        for sample_x in X[:25]:
            phi = scorer.explain_instance(sample_x)
            reconstructed = sum(phi) + scorer.expected_log_odds
            exact_margin = scorer.raw_margin(sample_x)
            self.assertAlmostEqual(reconstructed, exact_margin, places=9)

        # Check corporate payroll vector produces negative SHAP attributions and low risk score
        payroll_vec = [0.0, 5.0, 1.0, 5.0, 0.0, 0.0, 11.36, 0.0, 0.0, 0.25, 5.0, 0.75]
        mule_vec = [2.0, 5.0, 3.0, 6.0, 0.96, 0.95, 4.78, 1.0, 1.0, 4.2, 5.0, 1.0]

        payroll_score = scorer.score_one(payroll_vec)
        mule_score = scorer.score_one(mule_vec)
        self.assertLess(payroll_score, 0.25)
        self.assertGreater(mule_score, 0.80)
        self.assertGreaterEqual(VelocityRulesBaseline.score_one(payroll_vec), 0.45)

        payroll_reasons = scorer.top_reason_codes(payroll_vec, top_k=3)
        self.assertLess(payroll_reasons[0]["shap_log_odds"], 0.0)
        mule_reasons = scorer.top_reason_codes(mule_vec, top_k=3)
        self.assertGreater(mule_reasons[0]["shap_log_odds"], 0.0)

        # Check JSON model round-trip (no pickle)
        with tempfile.TemporaryDirectory() as tmp:
            json_path = Path(tmp) / "model.json"
            scorer.save_json(json_path)
            loaded = SnapMLAcceleratedScorer.load_json(json_path)
            self.assertAlmostEqual(scorer.score_one(mule_vec), loaded.score_one(mule_vec), places=12)

    def test_audit_hash_chain_verification_and_tamper_detection(self) -> None:
        """Verifies full 64-hex SHA-256 + HMAC audit chain and detects any field tampering."""
        policy = PolicyEngine(hold_threshold=0.85, step_up_threshold=0.65, log_allow_decisions=True)
        tx1 = TransactionRecord(
            tx_id=101,
            timestamp="2026/09/08 05:00:00",
            epoch_sec=1000.0,
            from_bank=10,
            from_account="ACC1001",
            to_bank=20,
            to_account="ACC2002",
            amount_received=185000.0,
            receiving_currency="INR",
            amount_paid=185000.0,
            payment_currency="INR",
            payment_format="Wire",
            is_laundering=1,
            chain_id=5,
            hop_number=1,
            typology="Fan-Out",
        )
        tx2 = copy.deepcopy(tx1)
        tx2.tx_id = 102
        tx2.amount_paid = 42000.0

        d1 = policy.evaluate(tx1, 0.994, [{"feature": "rapid_turnover_flag", "impact": "+2.1"}])
        d2 = policy.evaluate(tx2, 0.008, [{"feature": "pass_through_ratio_15m", "impact": "-1.8"}])

        # Ensure full 64-hex hashes and no ground-truth label fields leak into production decision
        self.assertEqual(len(d1.audit_hash), 64)
        self.assertEqual(len(d1.prev_audit_hash), 64)
        self.assertEqual(len(d1.hmac_signature), 64)
        d1_dict = d1.to_dict()
        self.assertNotIn("is_laundering", d1_dict)
        self.assertNotIn("chain_id", d1_dict)
        self.assertNotIn("hop_number", d1_dict)
        self.assertNotIn("typology", d1_dict)

        ok, msg = PolicyEngine.verify_chain(policy.audit_chain)
        self.assertTrue(ok, msg)

        # Tamper with amount in record 0 and verify detection
        tampered = copy.deepcopy(policy.audit_chain)
        tampered[0].amount = 185001.0
        ok_t, _ = PolicyEngine.verify_chain(tampered)
        self.assertFalse(ok_t)

        # Tamper with reason_codes in record 1 and verify detection
        tampered2 = copy.deepcopy(policy.audit_chain)
        tampered2[1].reason_codes = []
        ok_t2, _ = PolicyEngine.verify_chain(tampered2)
        self.assertFalse(ok_t2)


if __name__ == "__main__":
    unittest.main()
