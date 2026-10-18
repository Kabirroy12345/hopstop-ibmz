"""Unit and property tests for HopStop's core guarantees:
1. Amortized O(1) SlidingWindow exactness against a naive O(W) list-scan oracle.
2. Receiver window eviction on append + idle-account TTL garbage collection.
3. Large corporate payroll (5,000 recurring employees > 2,048 LRU cap) zero false-novelty via PayeeBloomFilter.
4. Strict causal ordering (no future data leakage).
5. Exact TreeSHAP local accuracy (Σ φ_i + base_score == raw_margin to 1e-9 across 50 random vectors).
6. Exact TreeSHAP signed negative log-odds attributions on corporate payroll vs. positive on mule fan-out.
7. Verifiable 64-hex SHA-256 + HMAC-SHA256 audit hash chain from genesis.
8. Single-byte tamper detection across payload, hash link, and HMAC signature.
"""
from __future__ import annotations

import copy
import random

from hopstop.data_generator import TransactionRecord
from hopstop.feature_engine import SlidingWindow, StreamingFeatureEngine
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

    # Send 10 credits spaced by 1000s to a receive-only account Sink_A
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

    # At t = 10,000s, SINK_RECEIVE_ONLY's 15m window (cutoff 9,100s) must only have 1 item (from t=10,000s)
    from hopstop.feature_engine import hash_account_id

    sink_key = hash_account_id("SINK_RECEIVE_ONLY")
    assert engine.states[sink_key].in_15m.tx_count == 1.0
    assert engine.states[sink_key].in_1h.tx_count == 4.0  # t = 7000, 8000, 9000, 10000

    # Sweep idle accounts at t = 20,000s (TTL = 3,600s -> cutoff = 16,400s)
    evicted = engine.evict_idle_accounts(20000.0)
    assert evicted == len(engine.states) + evicted and len(engine.states) == 0


def test_large_employer_payroll_5000_payees_bloom_filter() -> None:
    """Verifies that a corporate payroll account with 5,000 recurring employees (>2,048 LRU cap)
    retains evicted employees in its 64-kbit PayeeBloomFilter and gets zero false novelty."""
    engine = StreamingFeatureEngine(max_known_payees=2048, secret_key="test-payroll-key")

    # Cycle 1 (Month 1): Employer pays 5,000 distinct employees for the first time -> novelty == 1.0
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
        assert feats[8] == 1.0  # First-ever payment to this employee is novel

    # Verify exact LRU is capped at 2,048 while payee_bloom is allocated
    from hopstop.feature_engine import hash_account_id

    corp_key = hash_account_id("CORP_EMPLOYER_01", "test-payroll-key")
    assert len(engine.states[corp_key].known_payees) == 2048
    assert engine.states[corp_key].payee_bloom is not None

    # Cycle 2 (Month 2): Employer pays the earliest 1,000 employees (who were evicted from the 2,048 LRU!)
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
        assert feats[8] == 0.0, f"Evicted employee EMP_{i:05d} falsely flagged as novel!"


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
    """Verifies that PolicyEngine builds a valid 64-hex SHA-256 + HMAC-SHA256 chain from genesis."""
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


def test_audit_chain_single_byte_tamper_detection() -> None:
    """Verifies that flipping a single byte in risk_score, action, prev_audit_hash, or hmac_signature fails verify_chain()."""
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
        policy.evaluate(tx, 0.95, [{"feature": "fan_out_1h", "shap_log_odds": 1.1}], record_audit=True)

    # 1. Tamper risk_score
    t1 = copy.deepcopy(policy.audit_chain)
    t1[1].risk_score = 0.01
    ok1, _ = PolicyEngine.verify_chain(t1, audit_hmac_key="unit-test-hmac-secret")
    assert not ok1

    # 2. Tamper action
    t2 = copy.deepcopy(policy.audit_chain)
    t2[2].action = "ALLOW"
    ok2, _ = PolicyEngine.verify_chain(t2, audit_hmac_key="unit-test-hmac-secret")
    assert not ok2

    # 3. Flip 1 byte in hmac_signature
    t3 = copy.deepcopy(policy.audit_chain)
    sig = t3[0].hmac_signature
    flipped_char = "a" if sig[-1] != "a" else "b"
    t3[0].hmac_signature = sig[:-1] + flipped_char
    ok3, _ = PolicyEngine.verify_chain(t3, audit_hmac_key="unit-test-hmac-secret")
    assert not ok3

    # 4. Flip 1 byte in prev_audit_hash link
    t4 = copy.deepcopy(policy.audit_chain)
    ph = t4[2].prev_audit_hash
    t4[2].prev_audit_hash = ("f" if ph[0] != "f" else "0") + ph[1:]
    ok4, _ = PolicyEngine.verify_chain(t4, audit_hmac_key="unit-test-hmac-secret")
    assert not ok4
