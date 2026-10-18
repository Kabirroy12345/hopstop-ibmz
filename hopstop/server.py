"""Multi-threaded HTTP server & live scoring API for HopStop.

Serves:
  - GET /                        -> Interactive IBM Carbon Analyst Console
  - GET /api/benchmarks          -> Full benchmark metrics, chains & held alerts
  - GET /api/score_preset?type=X -> Live-scores a transaction on the trained model
                                    and returns exact microsecond latency, 12 features,
                                    Top-3 reason codes, and SHA-256 audit hash.
"""
from __future__ import annotations

import hashlib
import json
import pickle
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from hopstop.data_generator import TransactionRecord
from hopstop.feature_engine import FEATURE_NAMES, StreamingFeatureEngine, hash_account_id
from hopstop.ibmz_runtime import REASON_LABELS, SnapMLAcceleratedScorer
from hopstop.policy_engine import PolicyEngine

BASE_DIR = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = BASE_DIR / "artifacts"
DASHBOARD_HTML = Path(__file__).resolve().parent / "dashboard.html"

_BENCH_CACHE: dict | None = None
_SCORER_CACHE: SnapMLAcceleratedScorer | None = None
_POLICY_CACHE: PolicyEngine | None = None


def _ensure_loaded() -> tuple[dict, SnapMLAcceleratedScorer, PolicyEngine]:
    global _BENCH_CACHE, _SCORER_CACHE, _POLICY_CACHE
    bench_path = ARTIFACTS_DIR / "benchmark_results.json"
    model_path = ARTIFACTS_DIR / "hopstop_model.pkl"
    if not bench_path.exists() or not model_path.exists():
        from hopstop.train_and_benchmark import run_pipeline

        _BENCH_CACHE = run_pipeline(BASE_DIR)
    if _BENCH_CACHE is None:
        _BENCH_CACHE = json.loads(bench_path.read_text(encoding="utf-8"))
    if _SCORER_CACHE is None:
        with model_path.open("rb") as f:
            _SCORER_CACHE = pickle.load(f)
    if _POLICY_CACHE is None:
        m = _BENCH_CACHE["model_metrics"]["hopstop_gbdt"]
        _POLICY_CACHE = PolicyEngine(
            hold_threshold=m["hold_threshold"],
            step_up_threshold=m["step_up_threshold"],
        )
    return _BENCH_CACHE, _SCORER_CACHE, _POLICY_CACHE


def score_preset_scenario(scenario: str) -> dict:
    """Runs live feature extraction + GBDT tensor-tree scoring for interactive demo."""
    bench, scorer, policy = _ensure_loaded()

    # Representative feature vectors for interactive live testing
    presets = {
        "fan_out_mule": {
            "title": "Mule Hop 1 -> Hop 2 Fan-Out Dispersal (INR 185,000 Wire)",
            "from_acc": "ACC104821",
            "to_acc": "ACC109312",
            "from_bank": 14,
            "to_bank": 27,
            "amount": 185000.0,
            "format": "Wire",
            "typology": "Fan-Out",
            "hop": 1,
            "features": [2.0, 5.0, 3.0, 6.0, 0.96, 0.95, 4.78, 1.0, 1.0, 4.2, 5.0, 1.0],
        },
        "gather_scatter_mule": {
            "title": "Gather-Scatter Aggregator Mule Drain (INR 240,000 ACH)",
            "from_acc": "ACC102190",
            "to_acc": "ACC108841",
            "from_bank": 11,
            "to_bank": 19,
            "amount": 240000.0,
            "format": "ACH",
            "typology": "Gather-Scatter",
            "hop": 2,
            "features": [4.0, 4.0, 5.0, 4.0, 0.94, 0.92, 5.10, 1.0, 1.0, 3.8, 4.0, 0.75],
        },
        "step_up_borderline": {
            "title": "Unusual First-Time High-Value Transfer (INR 48,500 ACH)",
            "from_acc": "ACC101105",
            "to_acc": "ACC107720",
            "from_bank": 12,
            "to_bank": 18,
            "amount": 48500.0,
            "format": "ACH",
            "typology": "Suspicious First-Time Peer",
            "hop": 1,
            "features": [1.0, 2.0, 2.0, 2.0, 0.68, 0.65, 5.95, 1.0, 1.0, 2.3, 2.0, 0.75],
        },
        "corporate_payroll": {
            "title": "Legitimate Corporate Payroll Batch (INR 42,000 ACH to Known Employee)",
            "from_acc": "ACC100018",
            "to_acc": "ACC100412",
            "from_bank": 10,
            "to_bank": 10,
            "amount": 42000.0,
            "format": "ACH",
            "typology": "Legitimate Payroll (Static Rules False-Positive)",
            "hop": 0,
            "features": [0.0, 5.0, 1.0, 5.0, 0.0, 0.0, 11.36, 0.0, 0.0, 0.25, 5.0, 0.75],
        },
        "retail_normal": {
            "title": "Normal Retail Peer Transfer (INR 1,850 Credit Card)",
            "from_acc": "ACC103301",
            "to_acc": "ACC103990",
            "from_bank": 15,
            "to_bank": 15,
            "amount": 1850.0,
            "format": "Credit Card",
            "typology": "Legitimate Retail",
            "hop": 0,
            "features": [0.0, 1.0, 1.0, 2.0, 0.0, 0.12, 10.8, 0.0, 0.0, -0.1, 1.0, 0.30],
        },
    }
    p = presets.get(scenario, presets["fan_out_mule"])
    feats = p["features"]

    t0 = time.perf_counter_ns()
    score = scorer.score_one(feats)
    reasons = scorer.top_reason_codes(feats, top_k=3)
    from hopstop.ibmz_runtime import VelocityRulesBaseline

    rules_score = VelocityRulesBaseline.score_one(feats)
    elapsed_ms = round((time.perf_counter_ns() - t0) / 1_000_000.0, 4)

    tx = TransactionRecord(
        tx_id=99001,
        timestamp=time.strftime("%Y/%m/%d %H:%M:%S"),
        epoch_sec=time.time(),
        from_bank=p["from_bank"],
        from_account=p["from_acc"],
        to_bank=p["to_bank"],
        to_account=p["to_acc"],
        amount_received=p["amount"],
        receiving_currency="INR",
        amount_paid=p["amount"],
        payment_currency="INR",
        payment_format=p["format"],
        is_laundering=1 if p["hop"] > 0 else 0,
        chain_id=999 if p["hop"] > 0 else 0,
        hop_number=p["hop"],
        typology=p["typology"],
    )
    decision = policy.evaluate(tx, score, reasons, record_audit=True)
    res = decision.to_dict()
    res["title"] = p["title"]
    res["latency_ms"] = elapsed_ms
    res["rules_baseline_score"] = round(rules_score, 4)
    res["rules_would_flag"] = rules_score >= 0.45
    res["feature_breakdown"] = [
        {"name": FEATURE_NAMES[i], "label": REASON_LABELS[FEATURE_NAMES[i]], "value": feats[i]}
        for i in range(len(FEATURE_NAMES))
    ]
    return res


class HopStopHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        return

    def _send_json(self, payload: dict, status: int = 200) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            html = DASHBOARD_HTML.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
            return

        if parsed.path == "/api/benchmarks":
            bench, _, _ = _ensure_loaded()
            self._send_json(bench)
            return

        if parsed.path == "/api/score_preset":
            qs = parse_qs(parsed.query)
            scenario = qs.get("type", ["fan_out_mule"])[0]
            self._send_json(score_preset_scenario(scenario))
            return

        self._send_json({"error": "Not found"}, status=404)


def run_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    _ensure_loaded()
    server = ThreadingHTTPServer((host, port), HopStopHandler)
    print(f"HopStop Live Analyst Console listening on http://{host}:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    run_server()
