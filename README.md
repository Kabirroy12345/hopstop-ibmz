# HopStop — Real-Time Pre-Settlement Money-Mule Interdiction on IBM Z & LinuxONE

<div align="center">

[![Platform](https://img.shields.io/badge/IBM_Z_%26_LinuxONE-s390x_Ready-0f62fe?style=for-the-badge&logo=ibm&logoColor=white)](https://www.ibm.com/z)
[![AI Engine](https://img.shields.io/badge/IBM_Snap_ML-tree__format%3Dauto_%2B_JSON_Trees-4f46e5?style=for-the-badge)](https://www.ibm.com/docs/en/snap-ml)
[![Hardware Acceleration](https://img.shields.io/badge/s390x_Facilities-165_NNPA_%7C_MSA_CPACF_%7C_158_SecExec-06b6d4?style=for-the-badge)](https://research.ibm.com/blog/telum-ii-processor)
[![p99 Latency](https://img.shields.io/badge/p99_Latency-0.50_ms_(p50%3A_0.13_ms)-10b981?style=for-the-badge)](#3-measured-benchmark-results-3-way-chronological-split)
[![PR-AUC](https://img.shields.io/badge/Test_PR--AUC-0.8122_(%2B81.1%25_vs_Rules)-f59e0b?style=for-the-badge)](#3-measured-benchmark-results-3-way-chronological-split)
[![Tests](https://img.shields.io/badge/Unit_%26_Causality_Tests-Passing-10b981?style=for-the-badge)](tests/test_hopstop.py)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue?style=for-the-badge)](LICENSE)

**IBM Z Datathon 2026 — Track 1: Real-Time AI for Critical Decisions**  
**Author:** Kabir Roy (B.Tech CSE, VIT Bhopal) • **Pitch Deck:** [`submission/HopStop_PitchDeck_KabirRoy.pdf`](submission/HopStop_PitchDeck_KabirRoy.pdf) • **Architecture PDF:** [`submission/HopStop_Architecture_Diagram.pdf`](submission/HopStop_Architecture_Diagram.pdf)

</div>

---

## 1. Executive Summary & Problem Statement

When an Authorized Push Payment (APP) scam, phishing attack, or cyber-extortion succeeds, stolen funds are routed through **money-mule accounts** across banks within minutes over instant payment rails (**UPI / IMPS / ACH / Wire**).

1. **Why Batch AML Fails:** Traditional bank AML and graph analytics run in **hourly or overnight batches**. By the time an alert is generated, stolen funds have already dispersed across **3 to 5 hops**, making lien-marking and recovery via India's **1930 National Cybercrime Helpline** or **FIU-IND** nearly impossible.
2. **Why Static Velocity Rules Fail:** Simple velocity thresholds (e.g., *"flag if `fan_out_1h >= 3`"*) suffer from a severe precision-recall trade-off: they either **miss multi-hop gather-scatter and delayed-turnover mules** or **falsely flag legitimate corporate payroll and vendor batches**.
3. **Why Off-Platform Cloud AI Adds Risk & Latency:** Sending core banking payment payloads out to external cloud microservices adds **15–50 ms of network round-trip latency** and expands the compliance boundary for sensitive payment graphs.

**HopStop** addresses these challenges by co-locating **amortized $O(1)$ streaming graph-velocity feature extraction**, **depth-2 GBDT scoring with exact path-dependent TreeSHAP**, and **verifiable HMAC-SHA256 hash-chained audit logging** on **IBM Z / LinuxONE (`s390x`)**, scoring outgoing transfers **before settlement** so suspicious chains can be held at **Hop 1 or Hop 2**.

---

## 2. End-to-End Architecture & IBM Z / LinuxONE Integration

<div align="center">
  <img src="submission/HopStop_System_Architecture.svg" alt="HopStop Overall System Architecture on IBM Z & LinuxONE" width="100%" />
  <br/>
  <sub><b>Figure 1:</b> HopStop Pre-Settlement Inference & Cryptographic Audit Pipeline. <a href="submission/HopStop_Architecture_Diagram.pdf">Download Architecture PDF</a> • <a href="submission/HopStop_System_Architecture.png">View High-Res PNG</a> • <a href="submission/HopStop_System_Architecture.svg">View Vector SVG</a></sub>
</div>

### Hardware & Runtime Mapping (`hopstop/ibmz_runtime.py`)

| IBM Z / LinuxONE Capability | Implementation in HopStop | Verification & Portability Behavior |
| :--- | :--- | :--- |
| **Facility 165 (`nnpa` — Telum / Telum II AI Accelerator)** | [`detect_ibmz_environment()`](hopstop/ibmz_runtime.py) inspects `/proc/cpuinfo` (`facility 165`) and probes `libzdnn.so` (`zdnn_is_nnpa_installed()`) via `ctypes`. | When `snapml` is installed on the target host, [`SnapMLAcceleratedScorer.fit()`](hopstop/ibmz_runtime.py) fits `snapml.BoostingMachineClassifier` and invokes `optimize_trees(tree_format='auto')`. |
| **Portable JSON Tensor-Tree Engine (`hopstop_model.json`)** | Because binary Snap ML models are not portable between `x86_64` and `s390x`, HopStop also trains and exports a portable JSON depth-2 tree ensemble ([`artifacts/hopstop_model.json`](artifacts/hopstop_model.json), avoiding insecure `.pkl` files). | [`benchmark_results.json`](artifacts/benchmark_results.json) explicitly logs `active_backend` (`snapml.BoostingMachineClassifier(tree_format='auto')` vs. `portable_python_depth2_gbdt`) and the exact host hardware. |
| **Facility 17 / 76 / 77 / 146 (`msa` — CPACF Crypto)** | [`hash_account_id()`](hopstop/feature_engine.py) pseudonymizes account identifiers via `HMAC-SHA256` keyed from `HOPSTOP_HMAC_KEY` into 128-bit (`ACCT_<32-hex>`) tokens; [`PolicyEngine`](hopstop/policy_engine.py) maintains a full 64-hex SHA-256 + HMAC-SHA256 audit chain. | Internal feature state (`StreamingFeatureEngine.states`), decision records, and audit logs are keyed strictly by 128-bit HMAC pseudonyms so raw account IDs never enter model state or logs. |
| **Facility 158 (`prot_virt` — IBM Secure Execution)** | Probed via `/proc/cpuinfo` (`facility 158`) and `/sys/firmware/uv` for confidential LinuxONE guest enclave deployment ([`Dockerfile.s390x`](Dockerfile.s390x)). | Protects in-memory sliding-window state and HMAC keys inside an Ultravisor-isolated LinuxONE container. |

---

## 3. Measured Benchmark Results (3-Way Chronological Split)

To prevent both **temporal feature leakage** and **test-set threshold calibration leakage**, [`hopstop/train_and_benchmark.py`](hopstop/train_and_benchmark.py) partitions the 10-day (`50,880`-transaction) stream into three strictly disjoint chronological splits:

1. **Train Split (Days 1–6):** `30,616` transactions (`494` laundering transfers) — used to fit `SnapMLAcceleratedScorer` (36 depth-2 trees) and `LogisticRegressionBaseline` (L2-regularized linear model on the exact same 12 features).
2. **Validation Split (Day 7):** `5,032` transactions (`114` laundering transfers) — used **exclusively** to calibrate `step_up_threshold` (`0.9873`) and `hold_threshold` (`0.9931`) for a target **1.0% analyst alert budget**.
3. **Unseen Test Split (Days 8–10):** `15,232` transactions (`272` laundering transfers across `50` chains, including `12` delayed-hop evasion chains that wait `22.5 minutes` between Hop 1 and Hop 2). Applying the frozen Day-7 thresholds yields a **realized test alert rate of `0.83%`** (`127` flagged transfers out of `15,232`).

### Model Comparison on Unseen Test Split (Days 8–10)

| Metric | HopStop GBDT (Depth-2 Trees) | Logistic Regression (Same 12 Features) | Static Velocity-Rules Baseline | Notes / Lift |
| :--- | :---: | :---: | :---: | :--- |
| **Test PR-AUC (95% Bootstrap CI)** | **`0.8122`** `[0.7941, 0.8708]` | `0.8059` `[0.7617, 0.8501]` | `0.4484` `[0.3827, 0.5177]` | **+81.1% PR-AUC lift** over Static Rules |
| **Test ROC-AUC** | **`0.9806`** | `0.9824` | `0.8749` | **+12.1% lift** over Static Rules |
| **Recall @ 1.0% Alert Budget** | **`53.68%`** `[49.6%, 61.0%]` | `52.57%` `[47.1%, 57.7%]` | `35.66%` `[30.5%, 41.2%]` | **+50.5% relative recall lift** over Rules |
| **Precision @ 1.0% Alert Budget** | **`96.05%`** | `94.08%` | `63.82%` | **+32.2 pts higher precision** than Rules |
| **Recall @ 2.0% Alert Budget** | **`83.46%`** | `83.09%` | `58.09%` | Captures >83% of all illicit transfers at 2% cap |
| **Chains Stopped ≤ Hop 2 (All 50 Test Chains)** | **`84.0%` (`42 / 50`)** | `90.0%` (`45 / 50`) | `66.0%` (`33 / 50`) | **+18.0 pts more chains stopped** than Rules |
| **Fast Chains Stopped ≤ Hop 2 (`<15m` turnover)** | **`94.7%` (`36 / 38`)** | `94.7%` (`36 / 38`) | `84.2%` (`32 / 38`) | Stops 36 of 38 fast dispersal chains by Hop 2 |
| **Delayed Evasion Chains Stopped (`22.5m` wait)** | **`50.0%` (`6 / 12`)** | `75.0%` (`9 / 12`) | `8.3%` (`1 / 12`) | **6x more delayed evasion chains caught** than Rules |

> **Ingesting External IBM AMLworld CSVs:** In addition to the built-in generator, you can run the full benchmark directly on public Kaggle IBM AMLworld files (`HI-Small_Trans.csv` or `LI-Small_Trans.csv`) via:
> ```bash
> python -m hopstop.train_and_benchmark --csv-path /path/to/HI-Small_Trans.csv
> ```

### Component-Level Latency & Throughput Telemetry

Measured over `3,000` sequential single-transfer (`batch=1`) evaluations and `6,400` micro-batch (`batch=64`) evaluations using the `portable_python_depth2_gbdt` backend on local CPU (`AMD64, Windows 11, Python 3.13`):

| Pipeline Stage (`batch=1` Sequential Stream) | Median (`p50`) | `p95` | `p99` | SLA Target |
| :--- | :---: | :---: | :---: | :---: |
| **1. Amortized $O(1)$ Feature Extraction (`StreamingFeatureEngine`)** | `0.0551 ms` | — | — | — |
| **2. Depth-2 GBDT Scoring + Exact TreeSHAP (`SnapMLAcceleratedScorer`)** | `0.0111 ms` | — | — | — |
| **3. Policy Evaluation + Full 64-Hex SHA-256 & HMAC Audit (`PolicyEngine`)** | `0.0668 ms` | — | — | — |
| **Total End-to-End Decision Latency (`batch=1`)** | **`0.1341 ms`** | **`0.2442 ms`** | **`0.4999 ms`** | **`< 10.0 ms` (20x faster)** |

- **Sustained Single-Worker Stream Throughput (`batch=1`):** `6,349 TPS` (including HMAC-SHA256 pseudonymization, feature extraction, scoring, TreeSHAP, and policy evaluation)
- **Micro-Batch Scoring Throughput (`batch=64`):** `86,869 TPS`

---

## 4. Exact Path-Dependent TreeSHAP & Payroll vs. Mule Differentiation

Unlike heuristic z-score attributions, [`Depth2Tree.shap_contributions()`](hopstop/ibmz_runtime.py) implements **exact path-dependent TreeSHAP** for binary depth-2 trees using the empirical node routing probabilities $(w_L, w_{LL|L}, w_{RL|R})$ recorded during training. For every transaction $x$, the 12 feature attributions $\phi_j(x)$ satisfy the exact Shapley additivity identity (verified to $10^{-9}$ in [`tests/test_hopstop.py`](tests/test_hopstop.py)):

$$\sum_{j=1}^{12} \phi_j(x) + \mathbb{E}[f(X)] = \text{raw\_margin}(x)$$

Because TreeSHAP is signed, it explains **both** why a money-mule fan-out is frozen (`HOLD`) and why a high-fan-out corporate payroll batch is safely cleared (`ALLOW`):

| Signal / Output | Scenario 1: Money-Mule Hop-1 Fan-Out (`INR 185,000`) | Scenario 4: Legitimate Corporate Payroll (`INR 42,000`) |
| :--- | :--- | :--- |
| **`fan_out_1h`** | `5.0` distinct payees | `5.0` distinct payees *(triggers static velocity rules!)* |
| **`pass_through_ratio_15m`** | **`0.96`** *(15m outflow / 15m inflow)* | **`0.00`** *(funded from reserve balance, zero 15m inflow)* |
| **`counterparty_novelty`** | **`1.0`** *(unseen recipient account)* | **`0.0`** *(known recurring employee account)* |
| **Static Velocity-Rules Baseline** | `0.99` → **FLAGGED** | `0.60` → **FLAGGED (False Positive — Freezes Payroll)** |
| **HopStop GBDT Score & Action** | **`0.9938` → `HOLD`** | **`0.0183` → `ALLOW`** |
| **Exact TreeSHAP Top Attributions** | `amount_zscore (+1.828)`, `time_since_last_credit_log (+1.635)`, `payment_format_risk (+1.333)` | `counterparty_novelty (-1.552)`, `time_since_last_credit_log (-0.314)`, `amount_zscore (-0.249)` |

---

## 5. Amortized $O(1)$ Feature Engine & Memory Bounds (`hopstop/feature_engine.py`)

Each per-account time window is managed by [`SlidingWindow`](hopstop/feature_engine.py), which pairs a FIFO `deque` with a reference-counted counterparty map (`cnt: Dict[str, int]`) and running total (`total: float`). Both `distinct_peers` (`len(w.cnt)`) and `sum_amount` (`w.total`) execute in **$O(1)$ time** without rescanning the deque:

| # | Feature Name | Window / Complexity | Exact Formula & Behavioral Signal |
| :-: | :--- | :---: | :--- |
| 1 | `fan_in_1h` | 1h (`O(1)` amortized) | `len(in_1h.cnt)` — distinct inbound senders in the past 3,600s |
| 2 | `fan_out_1h` | 1h (`O(1)` amortized) | `len(out_1h.cnt)` — distinct outbound payees in the past 3,600s |
| 3 | `fan_in_24h` | 24h (`O(1)` amortized) | `len(in_24h.cnt)` — distinct inbound senders in the past 86,400s |
| 4 | `fan_out_24h` | 24h (`O(1)` amortized) | `len(out_24h.cnt)` — distinct outbound payees in the past 86,400s |
| 5 | `pass_through_ratio_15m` | 15m / 15m (`O(1)`) | $\min(5.0, (\text{out\_15m} + \text{amt}) / (\text{in\_15m} + 1))$ when $\text{in\_15m} > 0$ else $0.0$ |
| 6 | `pass_through_ratio_1h` | 1h / 1h (`O(1)`) | $\min(5.0, (\text{out\_1h} + \text{amt}) / (\text{in\_1h} + 1))$ when $\text{in\_1h} > 0$ else $0.0$ |
| 7 | `time_since_last_credit_log` | Instant (`O(1)`) | $\log(1 + \min(86400, \max(1, t - t_{\text{last\_credit}})))$ |
| 8 | `rapid_turnover_flag` | Tiered 15m / 1h (`O(1)`) | `1.0` if $\Delta t_{\text{credit}} \le 900\text{s}, \text{in\_15m} \ge 5000, \text{pt\_15m} \ge 0.65$; `0.5` if $\Delta t_{\text{credit}} \le 3600\text{s}, \text{in\_1h} \ge 5000, \text{pt\_1h} \ge 0.65$; else `0.0` |
| 9 | `counterparty_novelty` | Bounded LRU (`O(1)`) | `0.0` if recipient is in sender's bounded LRU `known_payees` (`max=2048`), else `1.0` |
| 10 | `amount_zscore` | Online Welford (`O(1)`) | Clipped sender Z-score $(\text{amt} - \mu) / \sigma$ using Welford running variance |
| 11 | `out_tx_velocity_1h` | 1h (`O(1)`) | `len(out_1h.q)` — total outgoing transactions in the last 3,600s |
| 12 | `payment_format_risk` | Instant (`O(1)`) | Rail risk weight (`Wire=1.0`, `ACH=0.75`, `Cash=0.65`, `Credit Card=0.30`, `Cheque=0.20`) |

### Memory Safety & Verifiable Audit Chain (`hopstop/policy_engine.py`)
- **Receive-Only Eviction & Idle Account TTL:** Receiver windows (`in_15m`, `in_1h`, `in_24h`) evict expired entries on every credit arrival so receive-only accounts never grow unbounded, and `evict_idle_accounts()` garbage-collects inactive accounts after `idle_ttl_seconds`.
- **Full 64-Hex SHA-256 + HMAC-SHA256 Audit Chain:** Every `PolicyDecision` stores full 64-character `prev_audit_hash`, `audit_hash`, and `hmac_signature` computed over the canonical payload (including `model_version`, `hold_threshold`, `step_up_threshold`, and JSON-serialized `reason_codes`), protected by a `threading.Lock()` and verifiable from genesis (`"0"*64`) via `PolicyEngine.verify_chain()`.

---

## 6. Quick Start & Automated Tests

### A. Run the Automated Unit & Causality Test Suite
```bash
python -m unittest discover -s tests -p "test_*.py" -v
```
Runs [`tests/test_hopstop.py`](tests/test_hopstop.py) verifying:
1. `test_sliding_window_o1_exactness` — exact agreement between `SlidingWindow` and brute-force window scans.
2. `test_strict_causality_no_future_leakage` — future transactions have zero effect on past features, and state is keyed by HMAC pseudonyms.
3. `test_treeshap_additivity_and_signed_attributions` — exact Shapley additivity ($\sum \phi_j + \mathbb{E}[f(X)] = f(x)$) to $10^{-9}$, negative SHAP values on benign corporate payroll, and JSON model round-trip.
4. `test_audit_hash_chain_verification_and_tamper_detection` — full 64-hex SHA-256 + HMAC chain verification, tamper detection, and zero ground-truth label leakage in `PolicyDecision`.

### B. Run Training, Validation Calibration & Benchmarks
```bash
python -m hopstop.train_and_benchmark
```

### C. Launch the Live Analyst Console (`http://127.0.0.1:8080`)
```bash
# Cross-platform Python command (or ./run_hopstop.sh on Linux/macOS, Start_HopStop_Dashboard.bat on Windows):
python -m hopstop.server
```

---

## 7. Repository Structure

```text
hopstop-ibmz/
├── .github/workflows/ci.yml  # GitHub Actions CI running unit tests & benchmark verification
├── hopstop/
│   ├── __init__.py           # Package metadata
│   ├── data_generator.py     # Public IBM AMLworld CSV loader + 8-typology & delayed-evasion generator
│   ├── feature_engine.py     # Amortized O(1) SlidingWindow engine, bounded LRU state & HMAC-SHA256
│   ├── ibmz_runtime.py       # s390x facility probe, Snap ML wrapper, exact TreeSHAP & LogReg/Rules baselines
│   ├── policy_engine.py      # Validation threshold calibration & verifiable 64-hex SHA-256 + HMAC audit chain
│   ├── train_and_benchmark.py# 3-way split training, 95% bootstrap CIs, evasion test & latency profiler
│   ├── server.py             # Multi-threaded REST API (/api/benchmarks, /api/score_preset, /api/verify_audit)
│   └── dashboard.html        # Interactive Analyst Console (live API + standalone offline support)
├── tests/
│   └── test_hopstop.py       # Unit & property tests (O(1) windows, causality, TreeSHAP additivity, audit chain)
├── artifacts/
│   ├── benchmark_results.json# Verified 3-way split metrics, 95% CIs, component latencies & audit verification
│   └── hopstop_model.json    # Safe, portable JSON serialized depth-2 GBDT ensemble (no pickle)
├── submission/
│   ├── HopStop_PitchDeck_KabirRoy.pdf       # 6-Slide Jury Pitch Deck PDF
│   ├── HopStop_Architecture_Diagram.pdf     # 1-Page Landscape System Architecture Diagram PDF
│   └── HopStop_System_Architecture.svg      # Vector System Architecture Diagram
├── Dockerfile.s390x          # Container definition for IBM Z / LinuxONE (icr.io/ibmz/python:3.11)
├── run_hopstop.sh            # POSIX launcher script (Linux / macOS / s390x)
├── Start_HopStop_Dashboard.bat # Windows launcher script
├── requirements.txt          # Pinned optional & s390x dependencies
├── LICENSE                   # Apache-2.0 License
└── README.md                 # Technical documentation
```
