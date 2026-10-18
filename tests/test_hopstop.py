"""Unit and property tests for HopStop's core guarantees:
1. Amortized O(1) SlidingWindow exactness against a naive O(W) list-scan oracle.
2. Receiver window eviction on append + idle-account TTL garbage collection.
3. Large corporate payroll (5,000 recurring employees > 2,048 LRU cap) zero false-novelty + dual-generation 64KB Bloom filter rotation.
4. Strict causal ordering (no future data leakage).
5. Exact TreeSHAP local accuracy (Σ φ_i + expected_log_odds == raw_margin to 1e-9 across 50 random vectors).
6. Exact TreeSHAP signed negative log-odds attributions on corporate payroll vs. positive on mule fan-out.
7. Verifiable 64-hex SHA-256 + HMAC-SHA256 audit hash chain from genesis (including ALLOW records).
8. Parametrized single-byte/field tamper detection across all 10 canonical payload & signature fields.
"""
from __future__ import annotations

import copy
import random
import pytest

from hopstop.data_generator import TransactionRecord
from hopstop.feature_engine import PayeeBloomFilter, SlidingWindow, StreamingFeatureEngine, hash_account_id
from hopstop.ibmz_runtime import SnapMLAcceleratedScorer
from hopstop.policy_engine import PolicyEngine


def test_sliding_window_o1_exactness() -> None:
    """Verifies SlidingWindow O(1) distinct_peers, sum_amount, and tx_count against a naive O(W) scan."""
    rng = random.Random(42)
    win = SlidingWindow()
    history = []
    peers = [f"PEER_{i}" for i in range(40)]

    t = 1000.0
    for _ in range(500):
        t += rng.uniform(0.5, 25.0)
        p = rng.choice(peers)
        amt = round(rng.uniform(10.0, 5000.0), 2)
        cutoff = t - 900.0

        win.evict(cutoff)
        win.push(t, p, amt)
        history.append((t, p, amt))

        active = [(ts, pr, a) for (ts, pr, a) in history if ts >= cutoff]
        expected_distinct = float(len({pr for _, pr, _ in active}))
        expected_sum = sum(a for _, _, a in active)
        expected_cnt = float(len(active))

        assert win.distinct_peers == expected_distinct
        assert abs(win.sum_amount - expected_sum) < 1e-6
        assert win.tx_count == expected_cnt


def test_receiver_eviction_and_idle_account_ttl() -> None:
    """Verifies that receive-only accounts evict expired items on append and idle accounts are swept."""
    engine = StreamingFeatureEngine(max_known_payees=64, idle_ttl_seconds=3600.0, gc_interval=100000)

    for i in range(10):
        tx = TransactionRecord(
            tx_id=i + 1,
            timestamp="2026/09/01 00:00:00",
            epoch_sec=1000.0 * (i + 1),
            from_bank=10,
            from_account=f"SENDER_{i}",
            to_bank=20,
            to_account="SINK_RECEIVE_ONLY",
            amount_received=500.0,
            receiving_currency="INR",
            amount_paid=500.0,
            payment_currency="INR",
            payment_format="ACH",
        )
        engine.extract_and_update(tx)

    sink_key = hash_account_id("SINK_RECEIVE_ONLY")
    assert engine.states[sink_key].in_15m.tx_count == 1.0
    assert engine.states[sink_key].in_1h.tx_count == 4.0

    evicted = engine.evict_idle_accounts(20000.0)
    assert evicted > 0 and len(engine.states) == 0


def test_large_employer_payroll_5000_payees_bloom_filter() -> None:
    """Verifies that a corporate payroll account with 5,000 recurring employees (>2,048 LRU cap)
    retains evicted employees in its dual-generation 64KB PayeeBloomFilter (<0.1% FPR at 25k) and rotates cleanly."""
    engine = StreamingFeatureEngine(max_known_payees=2048, secret_key="test-payroll-key")

    for i in range(5000):
        tx = TransactionRecord(
            tx_id=i + 1,
            timestamp="2026/09/01 09:00:00",
            epoch_sec=10000.0 + i,
            from_bank=10,
            from_account="CORP_EMPLOYER_01",
            to_bank=10,
            to_account=f"EMP_{i:05d}",
            amount_received=42000.0,
            receiving_currency="INR",
            amount_paid=42000.0,
            payment_currency="INR",
            payment_format="ACH",
        )
        feats = engine.extract_and_update(tx)
        assert feats[8] == 1.0

    corp_key = hash_account_id("CORP_EMPLOYER_01", "test-payroll-key")
    assert len(engine.states[corp_key].known_payees) == 2048
    assert engine.states[corp_key].payee_bloom is not None

    # Paying the earliest 1,000 evicted employees in Month 2 must yield counterparty_novelty == 0.0
    for i in range(1000):
        tx = TransactionRecord(
            tx_id=6000 + i,
            timestamp="2026/09/15 09:00:00",
            epoch_sec=900000.0 + i,
            from_bank=10,
            from_account="CORP_EMPLOYER_01",
            to_bank=10,
            to_account=f"EMP_{i:05d}",
            amount_received=42000.0,
            receiving_currency="INR",
            amount_paid=42000.0,
            payment_currency="INR",
            payment_format="ACH",
        )
        feats = engine.extract_and_update(tx)
        assert feats[8] == 0.0

    # Also verify generation rotation ages out ancient generations while keeping recent generation
    bf = PayeeBloomFilter(max_generation_items=100, rotation_sec=3600.0)
    bf.add("ACCT_GEN1_ITEM", current_ts=1000.0)
    assert bf.contains("ACCT_GEN1_ITEM")
    bf.add("ACCT_GEN2_ITEM", current_ts=5000.0)  # Triggers rotation: GEN1 -> prev_bits, GEN2 -> active_bits
    assert bf.contains("ACCT_GEN1_ITEM") and bf.contains("ACCT_GEN2_ITEM")
    bf.add("ACCT_GEN3_ITEM", current_ts=9000.0)  # Triggers 2nd rotation: GEN1 aged out!
    assert not bf.contains("ACCT_GEN1_ITEM") and bf.contains("ACCT_GEN2_ITEM") and bf.contains("ACCT_GEN3_ITEM")


def test_strict_causality_no_future_leakage() -> None:
    """Verifies that features for transaction k are identical regardless of future transactions k+1..N."""
    base_txs = [
        TransactionRecord(
            tx_id=i,
            timestamp="2026/09/01 12:00:00",
            epoch_sec=10000.0 + i * 60.0,
            from_bank=10,
            from_account=f"ACC_{i % 4}",
            to_bank=12,
            to_account=f"ACC_{(i + 1) % 5}",
            amount_received=1500.0 * (i + 1),
            receiving_currency="INR",
            amount_paid=1500.0 * (i + 1),
            payment_currency="INR",
            payment_format="Wire" if i % 2 == 0 else "ACH",
        )
        for i in range(1, 15)
    ]

    eng_prefix = StreamingFeatureEngine(secret_key="causality-test-key")
    feats_prefix = [eng_prefix.extract_and_update(tx) for tx in base_txs[:8]]

    future_burst = [
        TransactionRecord(
            tx_id=100 + j,
            timestamp="2026/09/01 12:20:00",
            epoch_sec=20000.0 + j * 5.0,
            from_bank=10,
            from_account="ACC_1",
            to_bank=99,
            to_account=f"MULE_{j}",
            amount_received=950000.0,
            receiving_currency="INR",
            amount_paid=950000.0,
            payment_currency="INR",
            payment_format="Wire",
        )
        for j in range(20)
    ]
    eng_with_future = StreamingFeatureEngine(secret_key="causality-test-key")
    feats_with_future = [eng_with_future.extract_and_update(tx) for tx in (base_txs[:8] + future_burst)]

    assert feats_prefix == feats_with_future[:8]


def _build_trained_scorer() -> SnapMLAcceleratedScorer:
    rng = random.Random(7)
    X_train = []
    y_train = []
    for _ in range(240):
        is_mule = rng.random() < 0.25
        if is_mule:
            x = [2.0, 5.0, 3.0, 6.0, 0.95, 0.94, 4.5, 1.0, 1.0, 3.5, 5.0, 1.0]
            y_train.append(1)
        else:
            x = [0.0, 4.0, 1.0, 4.0, 0.0, 0.0, 11.2, 0.0, 0.0, 0.2, 4.0, 0.75]
            y_train.append(0)
        x = [max(0.0, v + rng.uniform(-0.05, 0.05)) for v in x]
        X_train.append(x)

    scorer = SnapMLAcceleratedScorer(n_trees=16, learning_rate=0.2)
    scorer.fit(X_train, y_train)
    return scorer


def test_treeshap_local_accuracy_additivity() -> None:
    """Verifies exact TreeSHAP local accuracy: sum(phi) + expected_log_odds == raw_margin(x) to 1e-9."""
    scorer = _build_trained_scorer()
    rng = random.Random(99)

    for _ in range(50):
        vec = [rng.uniform(0.0, 6.0) for _ in range(12)]
        phis = scorer.explain_instance(vec)
        assert abs((sum(phis) + scorer.expected_log_odds) - scorer.raw_margin(vec)) < 1e-9


def test_treeshap_signed_negative_attributions_on_payroll() -> None:
    """Verifies that corporate payroll receives negative TreeSHAP log-odds while mule fan-out receives positive."""
    scorer = _build_trained_scorer()
    payroll_vec = [0.0, 5.0, 1.0, 5.0, 0.0, 0.0, 11.36, 0.0, 0.0, 0.25, 5.0, 0.75]
    mule_vec = [2.0, 5.0, 3.0, 6.0, 0.96, 0.95, 4.78, 1.0, 1.0, 4.2, 5.0, 1.0]

    phis_payroll = scorer.explain_instance(payroll_vec)
    phis_mule = scorer.explain_instance(mule_vec)

    assert sum(phis_payroll) < 0.0
    assert any(p < 0.0 for p in phis_payroll)
    assert sum(phis_mule) > 0.0


def test_audit_hash_chain_verification() -> None:
    """Verifies that PolicyEngine builds a valid 64-hex SHA-256 + HMAC-SHA256 chain from genesis covering ALLOWs."""
    policy = PolicyEngine(
        hold_threshold=0.85,
        step_up_threshold=0.60,
        audit_hmac_key="unit-test-hmac-secret",
        log_allow_decisions=True,
    )
    for i in range(6):
        tx = TransactionRecord(
            tx_id=500 + i,
            timestamp="2026/09/08 10:00:00",
            epoch_sec=1725789600.0 + i,
            from_bank=10,
            from_account=f"SRC_{i}",
            to_bank=20,
            to_account=f"DST_{i}",
            amount_received=25000.0,
            receiving_currency="INR",
            amount_paid=25000.0,
            payment_currency="INR",
            payment_format="Wire",
        )
        reasons = [{"feature": "pass_through_ratio_15m", "shap_log_odds": 1.42}]
        dec = policy.evaluate(tx, 0.92 if i % 2 == 0 else 0.12, reasons, record_audit=True)
        assert len(dec.audit_hash) == 64
        assert len(dec.prev_audit_hash) == 64
        assert len(dec.hmac_signature) == 64
        assert "is_laundering" not in dec.to_dict()

    ok, msg = PolicyEngine.verify_chain(policy.audit_chain, audit_hmac_key="unit-test-hmac-secret")
    assert ok, msg


@pytest.mark.parametrize(
    "tamper_field",
    [
        "risk_score",
        "action",
        "reason_codes",
        "model_version",
        "hold_threshold",
        "step_up_threshold",
        "amount",
        "from_account_hash",
        "prev_audit_hash",
        "hmac_signature",
        "delete_allow_record",
    ],
)
def test_audit_chain_single_byte_tamper_detection(tamper_field: str) -> None:
    """Parametrized test verifying that tampering with ANY canonical payload field or deleting an ALLOW record fails verify_chain()."""
    policy = PolicyEngine(
        hold_threshold=0.85,
        step_up_threshold=0.60,
        audit_hmac_key="unit-test-hmac-secret",
        log_allow_decisions=True,
    )
    for i in range(4):
        tx = TransactionRecord(
            tx_id=800 + i,
            timestamp="2026/09/08 11:00:00",
            epoch_sec=1725793200.0 + i,
            from_bank=14,
            from_account=f"A_{i}",
            to_bank=27,
            to_account=f"B_{i}",
            amount_received=50000.0,
            receiving_currency="INR",
            amount_paid=50000.0,
            payment_currency="INR",
            payment_format="Wire",
        )
        score = 0.05 if i == 1 else 0.95  # index 1 is an ALLOW record
        policy.evaluate(tx, score, [{"feature": "fan_out_1h", "shap_log_odds": 1.1}], record_audit=True)

    chain = copy.deepcopy(policy.audit_chain)
    rec = chain[1]

    if tamper_field == "risk_score":
        rec.risk_score = 0.01
    elif tamper_field == "action":
        rec.action = "HOLD"
    elif tamper_field == "reason_codes":
        rec.reason_codes = [{"feature": "tampered", "shap_log_odds": 0.0}]
    elif tamper_field == "model_version":
        rec.model_version = "hopstop-gbdt-v9.9"
    elif tamper_field == "hold_threshold":
        rec.hold_threshold = 0.99
    elif tamper_field == "step_up_threshold":
        rec.step_up_threshold = 0.50
    elif tamper_field == "amount":
        rec.amount = 49999.99
    elif tamper_field == "from_account_hash":
        rec.from_account_hash = "ACCT_" + "0" * 32
    elif tamper_field == "prev_audit_hash":
        ph = rec.prev_audit_hash
        rec.prev_audit_hash = ("f" if ph[0] != "f" else "0") + ph[1:]
    elif tamper_field == "hmac_signature":
        sig = rec.hmac_signature
        rec.hmac_signature = sig[:-1] + ("a" if sig[-1] != "a" else "b")
    elif tamper_field == "delete_allow_record":
        del chain[1]  # Deleting the ALLOW record breaks the hash link at chain[2]!

    ok, _ = PolicyEngine.verify_chain(chain, audit_hmac_key="unit-test-hmac-secret")
    assert not ok, f"Tampering with {tamper_field} was not detected!"
