"""Reproducible Linux (x86_64 / s390x, Python 3.11-3.12) benchmark for native `snapml.BoostingMachineClassifier(tree_format='auto')`.

Usage (on Linux / WSL 2 / s390x container with `snapml` installed):
    python3 -m hopstop.benchmark_snapml_linux
"""
from __future__ import annotations

import importlib.metadata
import json
import pathlib
import platform
import time

import numpy as np  # type: ignore
import snapml  # type: ignore
from snapml import BoostingMachineClassifier  # type: ignore

from hopstop.data_generator import generate_aml_dataset
from hopstop.feature_engine import StreamingFeatureEngine
from hopstop.train_and_benchmark import (
    compute_roc_and_pr_auc,
    recall_at_alert_rate,
)


def percentile(vals: list[float], q: float) -> float:
    s = sorted(vals)
    idx = min(len(s) - 1, max(0, int(len(s) * q / 100.0)))
    return s[idx]


def run_linux_snapml_benchmark() -> dict:
    txs, _ = generate_aml_dataset(seed=42)
    fe = StreamingFeatureEngine(max_known_payees=2048)

    X_train, y_train = [], []
    X_val, y_val = [], []
    X_test, y_test = [], []

    t0 = txs[0].epoch_sec
    train_end = t0 + 6 * 86400
    val_end = t0 + 7 * 86400

    for tx in txs:
        row = fe.extract_and_update(tx)
        if tx.epoch_sec < train_end:
            X_train.append(row)
            y_train.append(tx.is_laundering)
        elif tx.epoch_sec < val_end:
            X_val.append(row)
            y_val.append(tx.is_laundering)
        else:
            X_test.append(row)
            y_test.append(tx.is_laundering)

    pos_indices = [i for i, label in enumerate(y_train) if label == 1]
    neg_indices = [i for i, label in enumerate(y_train) if label == 0]
    step = max(1, len(neg_indices) // max(4000, len(pos_indices) * 8))
    train_idx = pos_indices + neg_indices[::step]

    X_sub = np.asarray([X_train[i] for i in train_idx], dtype=np.float32)
    y_sub = np.asarray([y_train[i] for i in train_idx], dtype=np.int32)

    t_fit0 = time.perf_counter()
    clf = BoostingMachineClassifier(
        n_jobs=4,
        max_depth=2,
        num_round=36,
        learning_rate=0.18,
        random_state=42,
    )
    clf.fit(X_sub, y_sub)
    clf.optimize_trees(tree_format="auto")
    fit_sec = round(time.perf_counter() - t_fit0, 4)

    X_test_np = np.asarray(X_test, dtype=np.float32)
    probs = clf.predict_proba(X_test_np)[:, 1].tolist()

    roc_auc, pr_auc = compute_roc_and_pr_auc(y_test, probs)
    rec_1, prec_1, _ = recall_at_alert_rate(y_test, probs, 0.01)

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
        "fit_and_optimize_trees_sec": fit_sec,
        "test_pr_auc": round(pr_auc, 4),
        "test_roc_auc": round(roc_auc, 4),
        "test_recall_at_1pct": round(rec_1, 4),
        "test_precision_at_1pct": round(prec_1, 4),
        "single_tx_predict_proba_p50_ms": round(percentile(single_lat_ms, 50), 4),
        "single_tx_predict_proba_p99_ms": round(percentile(single_lat_ms, 99), 4),
        "batch_64_scoring_tps": batch64_tps,
        "batch_64_per_tx_us": per_tx_in_batch64_us,
    }


if __name__ == "__main__":
    res = run_linux_snapml_benchmark()
    print(json.dumps(res, indent=2))
    bench_path = pathlib.Path(__file__).resolve().parent.parent / "artifacts" / "benchmark_results.json"
    if bench_path.exists():
        data = json.loads(bench_path.read_text(encoding="utf-8"))
        data["linux_snapml_verification"] = res
        bench_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
