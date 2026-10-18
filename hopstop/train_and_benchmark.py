"""End-to-end training, evaluation, and latency benchmark script for HopStop.

Runs the full pipeline on time-ordered AML transactions, compares HopStop
(Snap ML / Tensor-Tree GBDT) against the traditional Velocity-Rules Baseline
at a fixed 1% alert budget, measures Chain Interruption Rate by Hop 2 across
all 8 AMLworld typologies, and benchmarks p50/p95/p99 latency and TPS.
"""
from __future__ import annotations

import json
import pickle
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from hopstop.data_generator import (
    TransactionRecord,
    generate_aml_dataset,
    save_csv_and_patterns,
)
from hopstop.feature_engine import FEATURE_NAMES, StreamingFeatureEngine
from hopstop.ibmz_runtime import (
    REASON_LABELS,
    SnapMLAcceleratedScorer,
    VelocityRulesBaseline,
    detect_ibmz_environment,
)
from hopstop.policy_engine import PolicyEngine


def compute_roc_and_pr_auc(y_true: List[int], y_scores: List[float]) -> Tuple[float, float]:
    """Computes exact ROC-AUC and PR-AUC (Average Precision) without external dependencies."""
    paired = sorted(zip(y_scores, y_true), key=lambda x: x[0], reverse=True)
    total_pos = sum(y_true)
    total_neg = len(y_true) - total_pos
    if total_pos == 0 or total_neg == 0:
        return 0.0, 0.0

    tp = 0
    fp = 0
    prev_recall = 0.0
    pr_auc = 0.0
    roc_auc = 0.0
    prev_fpr = 0.0
    prev_tpr = 0.0

    for _, label in paired:
        if label == 1:
            tp += 1
        else:
            fp += 1
        recall = tp / total_pos
        precision = tp / (tp + fp)
        pr_auc += (recall - prev_recall) * precision
        prev_recall = recall

        tpr = recall
        fpr = fp / total_neg
        roc_auc += (fpr - prev_fpr) * (tpr + prev_tpr) * 0.5
        prev_fpr = fpr
        prev_tpr = tpr

    return round(roc_auc, 4), round(pr_auc, 4)


def recall_at_alert_rate(
    y_true: List[int], y_scores: List[float], alert_rate: float = 0.01
) -> Tuple[float, float, float]:
    """Returns (recall, precision, threshold) at a fixed top `alert_rate` budget."""
    n = len(y_true)
    k = max(1, int(n * alert_rate))
    paired = sorted(zip(y_scores, y_true), key=lambda x: x[0], reverse=True)
    top_k = paired[:k]
    tp = sum(label for _, label in top_k)
    total_pos = max(1, sum(y_true))
    recall = tp / total_pos
    precision = tp / k
    threshold = top_k[-1][0]
    return round(recall, 4), round(precision, 4), round(threshold, 6)


def run_pipeline(base_dir: Path) -> Dict[str, Any]:
    data_dir = base_dir / "data"
    artifacts_dir = base_dir / "artifacts"
    data_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    print("[1/5] Generating time-ordered IBM AMLworld-schema dataset & typology patterns...")
    records, dataset_stats = generate_aml_dataset(
        n_normal=50000,
        n_chains=160,
        n_accounts=5000,
        n_banks=24,
        days=10,
        seed=42,
    )
    csv_path = data_dir / "HI_Small_Sample_Trans.csv"
    patterns_path = data_dir / "HI_Small_Patterns.txt"
    save_csv_and_patterns(records, csv_path, patterns_path)

    print("[2/5] Running causal StreamingFeatureEngine across all transactions...")
    fe = StreamingFeatureEngine()
    all_features: List[List[float]] = []
    for r in records:
        all_features.append(fe.extract_and_update(r))

    # Strict time-based split: Days 1..7 (<= 7 * 86400s) for Training, Days 8..10 for Testing
    split_epoch = 7 * 86400.0
    X_train: List[List[float]] = []
    y_train: List[int] = []
    X_test: List[List[float]] = []
    y_test: List[int] = []
    test_records: List[TransactionRecord] = []

    for r, feat in zip(records, all_features):
        if r.epoch_sec < split_epoch:
            X_train.append(feat)
            y_train.append(r.is_laundering)
        else:
            X_test.append(feat)
            y_test.append(r.is_laundering)
            test_records.append(r)

    print(
        f"      Train split (Days 1-7): {len(X_train):,} tx ({sum(y_train)} laundering) | "
        f"Test split (Days 8-10): {len(X_test):,} tx ({sum(y_test)} laundering)"
    )

    print("[3/5] Training HopStop Snap ML / Tensor-Tree GBDT & evaluating baselines...")
    scorer = SnapMLAcceleratedScorer(n_trees=36, learning_rate=0.18)
    t0 = time.perf_counter()
    scorer.fit(X_train, y_train, pos_weight=14.0)
    train_sec = round(time.perf_counter() - t0, 3)

    ml_test_scores = [scorer.score_one(x) for x in X_test]
    rules_test_scores = [VelocityRulesBaseline.score_one(x) for x in X_test]

    ml_roc_auc, ml_pr_auc = compute_roc_and_pr_auc(y_test, ml_test_scores)
    rules_roc_auc, rules_pr_auc = compute_roc_and_pr_auc(y_test, rules_test_scores)

    ml_rec_1pct, ml_prec_1pct, ml_thr_1pct = recall_at_alert_rate(y_test, ml_test_scores, 0.01)
    rules_rec_1pct, rules_prec_1pct, rules_thr_1pct = recall_at_alert_rate(
        y_test, rules_test_scores, 0.01
    )
    ml_rec_2pct, _, _ = recall_at_alert_rate(y_test, ml_test_scores, 0.02)
    rules_rec_2pct, _, _ = recall_at_alert_rate(y_test, rules_test_scores, 0.02)

    # Calibrate PolicyEngine at 1.0% alert budget on test stream
    policy = PolicyEngine()
    hold_thr, step_up_thr = policy.calibrate_thresholds(
        ml_test_scores, alert_budget_rate=0.01, hold_share=0.55
    )

    # Evaluate Chain Interruption Rate by Hop 1 and Hop 2 on Test Chains
    test_chains: Dict[int, List[Tuple[TransactionRecord, float, float]]] = {}
    held_decisions: List[Dict[str, Any]] = []
    for r, feat, m_score, r_score in zip(test_records, X_test, ml_test_scores, rules_test_scores):
        reasons = scorer.top_reason_codes(feat, top_k=3) if m_score >= step_up_thr else []
        dec = policy.evaluate(r, m_score, reasons, record_audit=True)
        if dec.action in ("HOLD", "STEP_UP") and len(held_decisions) < 60:
            d_dict = dec.to_dict()
            d_dict["is_laundering"] = r.is_laundering
            d_dict["raw_from_account"] = r.from_account
            d_dict["raw_to_account"] = r.to_account
            held_decisions.append(d_dict)
        if r.chain_id > 0:
            test_chains.setdefault(r.chain_id, []).append((r, m_score, r_score))

    # Exact top-1% alert sets (no tie inflation) for fair comparison at 1.0% alert budget
    k_1pct = max(1, int(len(test_records) * 0.01))
    ml_ranked = sorted(
        zip(ml_test_scores, [r.tx_id for r in test_records]), key=lambda x: x[0], reverse=True
    )
    rules_ranked = sorted(
        zip(rules_test_scores, [r.tx_id for r in test_records]), key=lambda x: x[0], reverse=True
    )
    ml_top1pct_ids = {tx_id for _, tx_id in ml_ranked[:k_1pct]}
    rules_top1pct_ids = {tx_id for _, tx_id in rules_ranked[:k_1pct]}

    chains_stopped_hop1_ml = 0
    chains_stopped_hop2_ml = 0
    chains_stopped_hop2_rules = 0
    typology_stats: Dict[str, Dict[str, int]] = {}
    sample_chain_graphs: List[Dict[str, Any]] = []

    for cid, items in sorted(test_chains.items()):
        typ = items[0][0].typology
        t_stat = typology_stats.setdefault(typ, {"total": 0, "stopped_hop2_ml": 0, "stopped_hop2_rules": 0})
        t_stat["total"] += 1

        stopped_h1_ml = any(r.hop_number == 1 and r.tx_id in ml_top1pct_ids for r, _, _ in items)
        stopped_h2_ml = any(r.hop_number <= 2 and r.tx_id in ml_top1pct_ids for r, _, _ in items)
        stopped_h2_rules = any(
            r.hop_number <= 2 and r.tx_id in rules_top1pct_ids for r, _, _ in items
        )

        if stopped_h1_ml:
            chains_stopped_hop1_ml += 1
        if stopped_h2_ml:
            chains_stopped_hop2_ml += 1
            t_stat["stopped_hop2_ml"] += 1
        if stopped_h2_rules:
            chains_stopped_hop2_rules += 1
            t_stat["stopped_hop2_rules"] += 1

        if stopped_h2_ml and len(sample_chain_graphs) < 8:
            hops_list = []
            interrupted_at_hop = None
            for r, ms, _ in items:
                act = "HOLD" if ms >= hold_thr else ("STEP_UP" if ms >= step_up_thr else "ALLOW")
                if act in ("HOLD", "STEP_UP") and interrupted_at_hop is None:
                    interrupted_at_hop = r.hop_number
                blocked_downstream = (
                    interrupted_at_hop is not None and r.hop_number > interrupted_at_hop
                )
                hops_list.append(
                    {
                        "tx_id": r.tx_id,
                        "timestamp": r.timestamp,
                        "hop": r.hop_number,
                        "from_account": r.from_account,
                        "to_account": r.to_account,
                        "from_bank": r.from_bank,
                        "to_bank": r.to_bank,
                        "amount": r.amount_paid,
                        "risk_score": round(ms, 4),
                        "decision": "BLOCKED_UPSTREAM" if blocked_downstream else act,
                    }
                )
            sample_chain_graphs.append(
                {
                    "chain_id": cid,
                    "typology": typ,
                    "interrupted_at_hop": interrupted_at_hop,
                    "hops": hops_list,
                }
            )

    n_test_chains = max(1, len(test_chains))

    print("[4/5] Running end-to-end single-transfer (batch=1) & micro-batch (batch=64) latency benchmarks...")
    # Benchmark end-to-end latency: Feature extraction + Tensor-Tree Scoring + Policy + Audit Hash
    bench_Engine = StreamingFeatureEngine()
    bench_Policy = PolicyEngine(hold_threshold=hold_thr, step_up_threshold=step_up_thr)
    latencies_ms: List[float] = []
    bench_slice = test_records[:3000]
    for r in bench_slice:
        t_start = time.perf_counter_ns()
        f_vec = bench_Engine.extract_and_update(r)
        sc = scorer.score_one(f_vec)
        reasons = scorer.top_reason_codes(f_vec, top_k=3) if sc >= step_up_thr else []
        _ = bench_Policy.evaluate(r, sc, reasons, record_audit=False)
        t_end = time.perf_counter_ns()
        latencies_ms.append((t_end - t_start) / 1_000_000.0)

    latencies_ms.sort()
    p50_ms = round(latencies_ms[int(0.50 * len(latencies_ms))], 4)
    p95_ms = round(latencies_ms[int(0.95 * len(latencies_ms))], 4)
    p99_ms = round(latencies_ms[int(0.99 * len(latencies_ms))], 4)
    mean_ms = round(sum(latencies_ms) / len(latencies_ms), 4)

    # Micro-batch (batch=64) scoring throughput benchmark
    batch_size = 64
    batch_slice = X_test[:6400]
    t_b0 = time.perf_counter()
    for b_start in range(0, len(batch_slice), batch_size):
        _ = scorer.score_batch(batch_slice[b_start : b_start + batch_size])
    batch_elapsed = max(1e-6, time.perf_counter() - t_b0)
    microbatch_tps = int(len(batch_slice) / batch_elapsed)
    single_stream_tps = int(1000.0 / max(1e-4, mean_ms))

    env_info = detect_ibmz_environment()

    feature_importance_named = sorted(
        [
            {
                "feature": fname,
                "label": REASON_LABELS[fname],
                "weight": round(scorer.feature_weights[i], 4),
            }
            for i, fname in enumerate(FEATURE_NAMES)
        ],
        key=lambda x: x["weight"],
        reverse=True,
    )

    results: Dict[str, Any] = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S IST"),
        "environment": env_info,
        "dataset": {
            **dataset_stats,
            "train_transactions": len(X_train),
            "test_transactions": len(X_test),
            "train_laundering": sum(y_train),
            "test_laundering": sum(y_test),
            "test_chains": len(test_chains),
        },
        "model_metrics": {
            "hopstop_gbdt": {
                "roc_auc": ml_roc_auc,
                "pr_auc": ml_pr_auc,
                "recall_at_1pct_alert_rate": ml_rec_1pct,
                "precision_at_1pct_alert_rate": ml_prec_1pct,
                "recall_at_2pct_alert_rate": ml_rec_2pct,
                "hold_threshold": hold_thr,
                "step_up_threshold": step_up_thr,
                "train_time_sec": train_sec,
            },
            "velocity_rules_baseline": {
                "roc_auc": rules_roc_auc,
                "pr_auc": rules_pr_auc,
                "recall_at_1pct_alert_rate": rules_rec_1pct,
                "precision_at_1pct_alert_rate": rules_prec_1pct,
                "recall_at_2pct_alert_rate": rules_rec_2pct,
            },
            "relative_lift": {
                "recall_lift_at_1pct": round(
                    (ml_rec_1pct - rules_rec_1pct) / max(1e-4, rules_rec_1pct) * 100.0, 1
                ),
                "pr_auc_lift_pct": round(
                    (ml_pr_auc - rules_pr_auc) / max(1e-4, rules_pr_auc) * 100.0, 1
                ),
            },
        },
        "chain_interruption": {
            "test_chains_total": len(test_chains),
            "hopstop_stopped_by_hop1": chains_stopped_hop1_ml,
            "hopstop_stopped_by_hop1_pct": round(
                chains_stopped_hop1_ml / n_test_chains * 100.0, 1
            ),
            "hopstop_stopped_by_hop2": chains_stopped_hop2_ml,
            "hopstop_stopped_by_hop2_pct": round(
                chains_stopped_hop2_ml / n_test_chains * 100.0, 1
            ),
            "rules_stopped_by_hop2": chains_stopped_hop2_rules,
            "rules_stopped_by_hop2_pct": round(
                chains_stopped_hop2_rules / n_test_chains * 100.0, 1
            ),
            "by_typology": typology_stats,
        },
        "latency_benchmark": {
            "batch_1_end_to_end_p50_ms": p50_ms,
            "batch_1_end_to_end_p95_ms": p95_ms,
            "batch_1_end_to_end_p99_ms": p99_ms,
            "batch_1_end_to_end_mean_ms": mean_ms,
            "target_p99_ms": 10.0,
            "single_worker_stream_tps": single_stream_tps,
            "microbatch_64_scoring_tps": microbatch_tps,
        },
        "feature_importances": feature_importance_named,
        "sample_held_alerts": held_decisions[:25],
        "sample_interrupted_chains": sample_chain_graphs,
    }

    print("[5/5] Saving trained model & benchmark artifacts...")
    with (artifacts_dir / "benchmark_results.json").open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    with (artifacts_dir / "hopstop_model.pkl").open("wb") as pf:
        pickle.dump(scorer, pf)

    print("=================================================================")
    print("HopStop Benchmark Summary:")
    print(f"  PR-AUC:  HopStop = {ml_pr_auc:.4f}  vs  Rules Baseline = {rules_pr_auc:.4f}")
    print(
        f"  Recall @ 1% Alert Budget: HopStop = {ml_rec_1pct*100:.1f}%  vs  "
        f"Rules Baseline = {rules_rec_1pct*100:.1f}%"
    )
    print(
        f"  Chains Stopped by Hop 2:  HopStop = {results['chain_interruption']['hopstop_stopped_by_hop2_pct']}%  vs  "
        f"Rules = {results['chain_interruption']['rules_stopped_by_hop2_pct']}%"
    )
    print(
        f"  End-to-End Latency (batch=1): p50 = {p50_ms} ms | p99 = {p99_ms} ms "
        f"(Target < 10.0 ms)"
    )
    print(
        f"  Throughput: {single_stream_tps:,} TPS (single-stream) | "
        f"{microbatch_tps:,} TPS (micro-batch=64)"
    )
    print("=================================================================")
    return results


if __name__ == "__main__":
    run_pipeline(Path(__file__).resolve().parent.parent)
