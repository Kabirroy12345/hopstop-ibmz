# HopStop: Transaction-Time Money-Mule Interdiction on IBM Z & LinuxONE

**Track:** Real-Time AI for Critical Decisions — **IBM Z Datathon 2026**  
**Author:** Kabir Roy (B.Tech CSE, VIT Bhopal)

---

## 1. Problem Statement
When a cyber-fraud scam succeeds, stolen funds are routed through **money-mule accounts** across banks within minutes using instant payment rails (IMPS/UPI/ACH/Wire). Traditional bank AML monitoring runs in hourly or overnight batches—by the time an alert fires, the money has already jumped 3 to 5 hops across multiple accounts, making freezing and victim recovery via the **1930 Cybercrime Helpline** or **FIU-IND** nearly impossible.

**HopStop** moves money-mule graph detection directly into the live payment settlement path on **IBM Z / LinuxONE**, scoring every outgoing transfer before it settles so suspicious payments are held while stolen money is still at **Hop 1 or Hop 2**.

---

## 2. Solution Architecture & IBM Z / LinuxONE Integration

```text
[Live Payment Stream (IBM AMLworld Schema)]
        │  (Timestamp-ordered replay / REST stream)
        ▼
[1. Causal O(1) Streaming Feature Engine (hopstop/feature_engine.py)]
   • Sliding 15m / 1h / 24h deques per account (past events only — zero label leakage)
   • 12 Graph-Velocity Features: fan-in/fan-out (1h, 24h), 15m/1h pass-through ratio,
     time-since-last-credit, rapid credit-to-debit drain flag, counterparty novelty,
     online Welford amount Z-score, outgoing velocity, payment rail risk.
   • Privacy-by-Design: salted SHA-256 account hashing (CPACF-assisted on s390x).
        │
        ▼
[2. IBM Snap ML / Tensor-Tree GBDT Scorer (hopstop/ibmz_runtime.py)]
   • Hardware probe: checks s390x Facility 165 & libzdnn `zdnn_is_nnpa_installed()`
   • Uses `tree_format='auto'` in `ibmz-accelerated-for-snapml` to target the on-chip
     IBM Telum / Telum II Integrated Accelerator for AI (NNPA), with automatic fallback
     to branch-minimized CPU tensor-trees.
        │
        ▼
[3. Alert-Budget Policy & Audit Engine (hopstop/policy_engine.py)]
   • Thresholds calibrated to bank analyst alert budget (1.0% alert rate):
     ALLOW | STEP_UP (OTP / cooling period) | HOLD (freeze transfer at Hop 1/2)
   • Top-3 Per-Transfer Reason Codes + Tamper-Evident SHA-256 Hash-Chained Audit Log.
        │
        ▼
[4. Live IBM Carbon Analyst Console (hopstop/server.py + dashboard.html)]
   • Real-time held queue, Multi-Hop Chain Interdiction Graph, and Latency Telemetry.
```

---

## 3. Measured Benchmark Results (Days 1–7 Train, Days 8–10 Test)

Evaluated on **50,880 time-ordered AMLworld-schema transactions** across **5,000 accounts**, **24 banks**, and **160 multi-hop laundering chains** spanning all 8 AMLSim/AMLworld typologies (`Fan-Out`, `Fan-In`, `Gather-Scatter`, `Scatter-Gather`, `Simple-Cycle`, `Bipartite`, `Stack`, `Random-Walk`) plus benign corporate payroll bursts:

| Metric | HopStop (Snap ML / Tensor-Tree GBDT) | Traditional Velocity-Rules Baseline | Improvement / Target |
| :--- | :---: | :---: | :---: |
| **PR-AUC (Minority Class)** | **0.8317** | 0.5306 | **+56.7% relative lift** |
| **ROC-AUC** | **0.9854** | 0.9035 | **+9.1% lift** |
| **Laundering Recall @ 1.0% Alert Rate** | **53.3%** | 44.5% | **+19.8% relative lift** |
| **Laundering Chains Stopped by Hop 2** | **94.0% (47/50)** | 86.0% (43/50) | **+8.0 pts more chains frozen early** |
| **End-to-End Decision Latency (`batch=1`)** | **p50: 0.040 ms / p99: 0.202 ms** | — | **50x faster than `< 10 ms` SLA** |
| **Sustained Throughput** | **20,366 TPS (stream) / 109,612 TPS (`batch=64`)** | — | High-volume core payment ready |

---

## 4. Quick Start (Runs Anywhere in < 10 Seconds)

### A. Run Training & Latency Benchmarks
```bash
python -m hopstop.train_and_benchmark
```
Generates `data/HI_Small_Sample_Trans.csv`, `data/HI_Small_Patterns.txt`, `artifacts/benchmark_results.json`, and `artifacts/hopstop_model.pkl`.

### B. Launch the Live Analyst Dashboard
```bash
python -m hopstop.server
```
Open **`http://127.0.0.1:8080`** in your browser to view the live streaming interdiction queue, multi-hop chain freeze graph, top-3 reason codes, and IBM Z / LinuxONE telemetry.

### C. Run on IBM Z / LinuxONE (`s390x` Container)
```bash
docker build -f Dockerfile.s390x -t hopstop-ibmz:latest .
docker run --rm -p 8080:8080 hopstop-ibmz:latest
```

---

## 5. Repository Structure
- `hopstop/data_generator.py` — Time-ordered AMLworld transaction & 8-typology chain generator
- `hopstop/feature_engine.py` — O(1) sliding-window causal graph-velocity feature engine + SHA-256 PII hashing
- `hopstop/ibmz_runtime.py` — `s390x` / `libzdnn` NNPA hardware detector, Snap ML / Tensor-Tree GBDT scorer, and Velocity-Rules baseline
- `hopstop/policy_engine.py` — Alert-budget threshold calibration (`ALLOW` / `STEP_UP` / `HOLD`) & hash-chained audit log
- `hopstop/train_and_benchmark.py` — End-to-end training, evaluation, and latency/throughput benchmark suite
- `hopstop/server.py` & `hopstop/dashboard.html` — Live IBM Carbon Analyst Console & REST API
- `Dockerfile.s390x` — Container definition for IBM Z / LinuxONE (`s390x`)
- `submission/` — Pitch Deck PDF, Architecture Flowchart PDF, and submission text
