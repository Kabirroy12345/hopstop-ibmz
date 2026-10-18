"""Reproducible Linux (x86_64 / s390x, Python 3.11-3.12) benchmark for native `snapml.BoostingMachineClassifier(tree_format='auto')`.

Runs the exact same 3-way split, sample weighting, Day-7 validation calibration, tie-invariant AP/Recall@k,
and chain-interruption protocol as `hopstop/train_and_benchmark.py`.

Usage (on Linux / WSL 2 / s390x container with `snapml` installed):
    python3 -m hopstop.benchmark_snapml_linux
"""
from __future__ import annotations

import importlib.metadata
import json
import pathlib
import platform
import time
from typing import Dict, List, Tuple

import numpy as np  # type: ignore
import snapml  # type: ignore
from snapml import BoostingMachineClassifier  # type: ignore

from hopstop.data_generator import TransactionRecord, generate_aml_dataset
from hopstop.feature_engine import StreamingFeatureEngine
from hopstop.policy_engine import PolicyEngine
from hopstop.train_and_benchmark import (
    bayes_adjusted_precision,
    bootstrap_ci,
    compute_roc_and_pr_auc,
    recall_at_alert_rate,
)


def percentile(vals: List[float], q: float) -> float:
    s = sorted(vals)
    idx = min(len(s) - 1, max(0, int(len(s) * q / 100.0)))
    return s[idx]


def run_linux_snapml_benchmark() -> dict:
    records, _ = generate_aml_dataset(
        n_normal=50000,
        n_chains=160,
        n_accounts=5000,
        n_banks=24,
        days=10,
        seed=42,
    )
    fe = StreamingFeatureEngine()
    all_features = [fe.extract_and_update(r) for r in records]

    # Exact same 3-way chronological split as hopstop/train_and_benchmark.py
    max_epoch = max((r.epoch_sec for r in records), default=10 * 86400.0)
    train_end_epoch = 0.60 * max_epoch
    val_end_epoch = 0.70 * max_epoch

    X_train: List[List[float]] = []
    y_train: List[int] = []
    X_val: List[List[float]] = []
    y_val: List[int] = []
    X_test: List[List[float]] = []
    y_test: List[int] = []
    test_records: List[TransactionRecord] = []

    for r, feat in zip(records, all_features):
        if r.epoch_sec < train_end_epoch:
            X_train.append(feat)
            y_train.append(r.is_laundering)
        elif r.epoch_sec < val_end_epoch:
            X_val.append(feat)
            y_val.append(r.is_laundering)
        else:
            X_test.append(feat)
            y_test.append(r.is_laundering)
            test_records.append(r)

    pos_indices = [i for i, label in enumerate(y_train) if label == 1]
    neg_indices = [i for i, label in enumerate(y_train) if label == 0]
    step = max(1, len(neg_indices) // max(4000, len(pos_indices) * 8))
    train_idx = pos_indices + neg_indices[::step]

    pos_weight = 14.0
    X_sub = np.asarray([X_train[i] for i in train_idx], dtype=np.float32)
    y_sub = np.asarray([y_train[i] for i in train_idx], dtype=np.int32)
    w_sub = np.where(y_sub == 1, float(pos_weight), 1.0).astype(np.float32)

    X_val_np = np.asarray(X_val, dtype=np.float32)
    y_val_np = np.asarray(y_val, dtype=np.int32)
    X_test_np = np.asarray(X_test, dtype=np.float32)

    t_fit0 = time.perf_counter()
    clf = BoostingMachineClassifier(
        n_jobs=4,
        max_depth=2,
        num_round=36,
        learning_rate=0.18,
        early_stopping_rounds=10,
        random_state=42,
    )
    clf.fit(X_sub, y_sub, sample_weight=w_sub, X_val=X_val_np, y_val=y_val_np)
    clf.optimize_trees(tree_format="auto")
    fit_sec = round(time.perf_counter() - t_fit0, 4)

    val_probs = clf.predict_proba(X_val_np)[:, 1].tolist()
    probs = clf.predict_proba(X_test_np)[:, 1].tolist()

    # Calibrate thresholds on Day-7 Validation split using identical PolicyEngine protocol
    policy = PolicyEngine(model_version="snapml-1.17.2-tree-format-auto", log_allow_decisions=False)
    hold_thr, step_up_thr = policy.calibrate_thresholds(val_probs, alert_budget_rate=0.01, hold_share=0.55)
    realized_alerts = sum(1 for p in probs if round(p, 6) >= step_up_thr)
    realized_alert_rate = round(realized_alerts / max(1, len(probs)), 4)

    roc_auc, pr_auc = compute_roc_and_pr_auc(y_test, probs)
    rec_1, prec_1, _ = recall_at_alert_rate(y_test, probs, 0.01)
    rec_2, _, _ = recall_at_alert_rate(y_test, probs, 0.02)
    prevalence_rate = sum(y_test) / float(len(y_test))
    rec_prev, prec_prev, _ = recall_at_alert_rate(y_test, probs, prevalence_rate)
    snap_ci = bootstrap_ci(y_test, probs, n_boot=120, seed=42)

    n_test_total = len(y_test)
    n_test_pos = max(1, sum(y_test))
    n_test_neg = max(1, n_test_total - n_test_pos)
    k_1pct = max(1, int(n_test_total * 0.01))
    fp_1 = max(0.0, k_1pct - rec_1 * n_test_pos)
    fpr_1 = fp_1 / float(n_test_neg)
    prec_10bps = bayes_adjusted_precision(rec_1, fpr_1, 0.0010)
    prec_5bps = bayes_adjusted_precision(rec_1, fpr_1, 0.0005)

    # Chain interruption at exact 1.0% alert budget
    top1pct_ids = {
        tx_id
        for _, tx_id in sorted(
            zip(probs, [r.tx_id for r in test_records]), key=lambda x: x[0], reverse=True
        )[:k_1pct]
    }
    test_chains: Dict[int, List[Tuple[TransactionRecord, float]]] = {}
    for r, p in zip(test_records, probs):
        if r.chain_id > 0:
            test_chains.setdefault(r.chain_id, []).append((r, p))

    stopped_hop2 = 0
    fast_total = 0
    fast_stopped = 0
    evasion_total = 0
    evasion_stopped = 0
    for cid, items in sorted(test_chains.items()):
        is_delayed = (cid % 5 == 0)
        hit = any(r.hop_number <= 2 and r.tx_id in top1pct_ids for r, _ in items)
        if hit:
            stopped_hop2 += 1
        if is_delayed:
            evasion_total += 1
            if hit:
                evasion_stopped += 1
        else:
            fast_total += 1
            if hit:
                fast_stopped += 1

    single_lat_ms = []
    for i in range(min(3000, len(X_test))):
        arr1 = X_test_np[i : i + 1]
        ts0 = time.perf_counter_ns()
        _ = clf.predict_proba(arr1)
        single_lat_ms.append((time.perf_counter_ns() - ts0) / 1_000_000.0)

    batch_rows = X_test_np[:6400]
    tb0 = time.perf_counter_ns()
    for b in range(0, len(batch_rows), 64):
        _ = clf.predict_proba(batch_rows[b : b + 64])
    tb_sec = (time.perf_counter_ns() - tb0) / 1_000_000_000.0
    batch64_tps = int(round(len(batch_rows) / max(1e-9, tb_sec)))
    per_tx_in_batch64_us = round((tb_sec / len(batch_rows)) * 1_000_000.0, 3)

    try:
        snap_ver = importlib.metadata.version("snapml")
    except Exception:
        snap_ver = getattr(snapml, "__version__", "installed")

    return {
        "platform": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "python_version": platform.python_version(),
        "snapml_version": snap_ver,
        "active_backend": "snapml.BoostingMachineClassifier(tree_format='auto')",
        "protocol": "Identical 3-way split (Days 1-6 Train, Day 7 Val early-stopping & threshold calibration, Days 8-10 Unseen Test)",
        "fit_and_optimize_trees_sec": fit_sec,
        "test_pr_auc": round(pr_auc, 4),
        "test_pr_auc_95ci": list(snap_ci["pr_auc_95ci"]),
        "test_roc_auc": round(roc_auc, 4),
        "theoretical_max_recall_at_1pct": round(min(1.0, k_1pct / float(n_test_pos)), 4),
        "test_recall_at_1pct": round(rec_1, 4),
        "test_recall_1pct_95ci": list(snap_ci["recall_1pct_95ci"]),
        "test_precision_at_1pct": round(prec_1, 4),
        "test_precision_at_1pct_10bps_prior": prec_10bps,
        "test_precision_at_1pct_5bps_prior": prec_5bps,
        "test_recall_at_prevalence_budget_179bps": round(rec_prev, 4),
        "test_precision_at_prevalence_budget_179bps": round(prec_prev, 4),
        "test_recall_at_2pct": round(rec_2, 4),
        "val_calibrated_hold_threshold": hold_thr,
        "val_calibrated_step_up_threshold": step_up_thr,
        "realized_test_alert_rate": realized_alert_rate,
        "chains_stopped_by_hop2": stopped_hop2,
        "chains_stopped_by_hop2_pct": round(stopped_hop2 / max(1, len(test_chains)) * 100.0, 1),
        "fast_chains_stopped_by_hop2": fast_stopped,
        "fast_chains_total": fast_total,
        "fast_chains_stopped_pct": round(fast_stopped / max(1, fast_total) * 100.0, 1),
        "delayed_evasion_chains_stopped": evasion_stopped,
        "delayed_evasion_chains_total": evasion_total,
        "delayed_evasion_chains_stopped_pct": round(evasion_stopped / max(1, evasion_total) * 100.0, 1),
        "single_tx_predict_proba_p50_ms": round(percentile(single_lat_ms, 50), 4),
        "single_tx_predict_proba_p99_ms": round(percentile(single_lat_ms, 99), 4),
        "model_only_x86_cpu_batch_64_scoring_tps": batch64_tps,
        "model_only_x86_cpu_batch_64_per_tx_us": per_tx_in_batch64_us,
    }


if __name__ == "__main__":
    res = run_linux_snapml_benchmark()
    print(json.dumps(res, indent=2))
    bench_path = pathlib.Path(__file__).resolve().parent.parent / "artifacts" / "benchmark_results.json"
    if bench_path.exists():
        data = json.loads(bench_path.read_text(encoding="utf-8"))
        data["linux_snapml_verification"] = res
        bench_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
