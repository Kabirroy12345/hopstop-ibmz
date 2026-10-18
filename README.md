# HopStop — Real-Time Pre-Settlement Money-Mule Interdiction on IBM Z & LinuxONE

<div align="center">

[![Platform](https://img.shields.io/badge/Target_Platform-IBM_Z_%26_LinuxONE_(s390x)-0f62fe?style=for-the-badge&logo=ibm&logoColor=white)](https://www.ibm.com/z)
[![Measured Scorer](https://img.shields.io/badge/Measured_Scorer-Portable_Python_Depth--2_GBDT_%2B_Exact_TreeSHAP-4f46e5?style=for-the-badge)](#3-measured-benchmark-results-3-way-chronological-split)
[![s390x Integration](https://img.shields.io/badge/s390x_Runtime_Path-Snap_ML_(tree__format%3Dauto)_%7C_CPACF-06b6d4?style=for-the-badge)](#2-end-to-end-architecture--ibm-z--linuxone-integration)
[![p99 Latency](https://img.shields.io/badge/E2E_p99_Latency-0.19_ms_(p50%3A_0.06_ms)-10b981?style=for-the-badge)](#component-level-latency--throughput-telemetry)
[![PR-AUC](https://img.shields.io/badge/Test_PR--AUC-0.8122_(%2B81.1%25_vs_Rules)-f59e0b?style=for-the-badge)](#3-measured-benchmark-results-3-way-chronological-split)
[![Tests](https://img.shields.io/badge/Pytest_Suite-8_%2F_8_Passing-10b981?style=for-the-badge)](tests/test_hopstop.py)
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

| IBM Z / LinuxONE Capability | Implementation in HopStop | Active Backend & Portability Disclosure |
| :--- | :--- | :--- |
| **Portable JSON Tensor-Tree Engine (`portable_python_depth2_gbdt`)** | Always fits and exports a portable JSON depth-2 tree ensemble ([`artifacts/hopstop_model.json`](artifacts/hopstop_model.json), avoiding insecure `.pkl` files) with exact path-dependent TreeSHAP. | **Used for all headline benchmark numbers in this repository** (measured on `Intel64 Family 6 Model 154, AMD64, Windows 11, Python 3.13.9`, where `snapml` has no PyPI wheel). [`benchmark_results.json`](artifacts/benchmark_results.json) explicitly logs `active_backend` and host hardware. |
| **Facility 165 (`nnpa` — Telum / Telum II AI Accelerator) & `snapml`** | [`detect_ibmz_environment()`](hopstop/ibmz_runtime.py) inspects `/proc/cpuinfo` (`facility 165`) and probes `libzdnn.so` (`zdnn_is_nnpa_installed()`) via `ctypes`. | When deployed on Linux (`x86_64` or `s390x`, Python 3.11–3.12 via [`Dockerfile.s390x`](Dockerfile.s390x)) with `snapml` installed, [`SnapMLAcceleratedScorer.fit()`](hopstop/ibmz_runtime.py) fits `snapml.BoostingMachineClassifier` and invokes `optimize_trees(tree_format='auto')`. |
| **Facility 17 / 76 / 77 / 146 (`msa` — CPACF Crypto)** | [`hash_account_id()`](hopstop/feature_engine.py) pseudonymizes account IDs via `HMAC-SHA256` into 128-bit (`ACCT_<32-hex>`) tokens; [`PolicyEngine`](hopstop/policy_engine.py) maintains a full 64-hex SHA-256 + HMAC-SHA256 audit chain. | Keyed via `HOPSTOP_HMAC_KEY` / `HOPSTOP_AUDIT_HMAC_KEY` from the environment or HSM; if unset, generates a per-process **256-bit CSPRNG ephemeral key** (`secrets.token_hex(32)`) so no static secret key is ever stored in the repository. |
| **Facility 158 (`prot_virt` — IBM Secure Execution)** | Probed via `/proc/cpuinfo` (`facility 158`) and `/sys/firmware/uv` for confidential LinuxONE guest enclave deployment ([`Dockerfile.s390x`](Dockerfile.s390x)). | Protects in-memory sliding-window state and HMAC keys inside an Ultravisor-isolated LinuxONE container. |

---

## 3. Measured Benchmark Results (Single-Run 3-Way Chronological Split)

All metrics below come from a single deterministic run of [`hopstop/train_and_benchmark.py`](hopstop/train_and_benchmark.py) saved in [`artifacts/benchmark_results.json`](artifacts/benchmark_results.json). To prevent both **temporal feature leakage** and **test-set threshold calibration leakage**, the 10-day (`50,880`-transaction) stream is partitioned into three strictly disjoint chronological splits:

1. **Train Split (Days 1–6):** `30,616` transactions (`494` laundering transfers) — used to fit `SnapMLAcceleratedScorer` (36 depth-2 trees) and `LogisticRegressionBaseline` (L2-regularized linear model on the exact same 12 features).
2. **Validation Split (Day 7):** `5,032` transactions (`114` laundering transfers) — used **exclusively** to calibrate `step_up_threshold` (`0.9873`) and `hold_threshold` (`0.9931`) for a target **1.0% analyst alert budget**.
3. **Unseen Test Split (Days 8–10):** `15,232` transactions (`272` laundering transfers across `50` chains, including `12` delayed-hop evasion chains that wait `22.5 minutes` between Hop 1 and Hop 2). Applying the frozen Day-7 thresholds yields a **realized test alert rate of `0.83%`** (`127` hash-chained alert records verified from genesis out of `15,232` test transfers).

### Model Comparison on Unseen Test Split (Days 8–10, `15,232` Transactions)

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

**Backend & Hardware Disclosure:** Measured over `3,000` sequential single-transfer (`batch=1`) evaluations and `6,400` micro-batch (`batch=64`) evaluations using **`active_backend = portable_python_depth2_gbdt`** on local CPU (`Intel64 Family 6 Model 154, AMD64, Windows 11, Python 3.13.9`):

| Pipeline Stage (`batch=1` Sequential Stream) | Median (`p50`) | `p95` | `p99` | SLA Target |
| :--- | :---: | :---: | :---: | :---: |
| **1. Amortized $O(1)$ Feature Extraction (`StreamingFeatureEngine`)** | `0.0256 ms` | — | — | — |
| **2. Depth-2 GBDT Scoring + Exact TreeSHAP (`SnapMLAcceleratedScorer`)** | `0.0059 ms` | — | — | — |
| **3. Policy Evaluation + Full 64-Hex SHA-256 & HMAC Audit (`PolicyEngine`)** | `0.0270 ms` | — | — | — |
| **Total End-to-End Decision Latency (`batch=1`)** | **`0.0589 ms`** | **`0.1145 ms`** | **`0.1881 ms`** | **`< 10.0 ms` (53x faster)** |

- **Sustained Single-Worker Stream Throughput (`batch=1`):** `14,858 TPS` (including HMAC-SHA256 pseudonymization, feature extraction, scoring, TreeSHAP, and policy evaluation)
- **Micro-Batch Scoring Throughput (`batch=64`):** `174,828 TPS`

---

## 4. Exact Path-Dependent TreeSHAP & Payroll vs. Mule Differentiation

Unlike heuristic z-score attributions, [`Depth2Tree.shap_contributions()`](hopstop/ibmz_runtime.py) implements **exact path-dependent TreeSHAP** for binary depth-2 trees using the empirical node routing probabilities $(w_L, w_{LL|L}, w_{RL|R})$ recorded during training. For every transaction $x$, the 12 feature attributions $\phi_j(x)$ satisfy the exact Shapley local-accuracy identity (verified across 50 random vectors to $10^{-9}$ in [`tests/test_hopstop.py`](tests/test_hopstop.py)):

$$\sum_{j=1}^{12} \phi_j(x) + \mathbb{E}[f(X)] = \text{raw\_margin}(x)$$

### A. Real Unseen Test-Split (`Days 8–10`) Transactions (from [`artifacts/benchmark_results.json`](artifacts/benchmark_results.json))

These two transactions are extracted directly from the causal `Days 8–10` test stream (`real_test_case_examples` in [`benchmark_results.json`](artifacts/benchmark_results.json)):

| Signal / Output | Unseen Test Mule (`tx_id=35893`, `INR 49,848.99 Wire`, Scatter-Gather) | Unseen Test Corporate Batch (`tx_id=35895`, `INR 33,622.83 ACH`, Legitimate) |
| :--- | :--- | :--- |
| **`fan_out_1h` / `fan_out_24h`** | `0.0` / `3.0` | `4.0` / `5.0` *(high fan-out triggers static velocity rules!)* |
| **`pass_through_ratio_15m`** | **`0.96`** *(96% of 15m inflow drained within `244s`)* | **`0.00`** *(funded from reserve balance, zero 15m inflow)* |
| **`counterparty_novelty`** | **`1.0`** *(first-time recipient account)* | **`0.0`** *(known recurring employee/vendor account)* |
| **Static Velocity-Rules Baseline** | `0.63` → **FLAGGED** | `0.60` → **FLAGGED (False Positive — Freezes Batch)** |
| **HopStop GBDT Score & Action** | **`0.9931` → `HOLD`** | **`0.0159` → `ALLOW`** |
| **Exact TreeSHAP Top Attributions** | `amount_zscore (+1.924)`, `time_since_last_credit_log (+1.635)`, `payment_format_risk (+1.503)` | `counterparty_novelty (-1.552)`, `amount_zscore (-0.390)`, `time_since_last_credit_log (-0.314)` |

### B. Hand-Specified Illustrative Sandbox Presets (`/api/score_preset` in [`hopstop/server.py`](hopstop/server.py))

In addition to the real test-split cases above (`/api/score_preset?type=real_test_mule_hold` and `/api/score_preset?type=real_test_payroll_allow`), the interactive console includes 5 hand-specified illustrative sandbox scenarios (`scenario_source = "hand_specified_sandbox_illustration"`):

| Preset Key | Illustrative Scenario | Static Rules Score | HopStop Score & Action | Top Exact TreeSHAP Log-Odds Attributions |
| :--- | :--- | :---: | :---: | :--- |
| `fan_out_mule` | Mule Hop-1 Fan-Out (`INR 185,000 Wire`) | `0.99` (FLAGGED) | **`0.9938` → `HOLD`** | `amount_zscore (+1.828)`, `time_since_last_credit_log (+1.635)`, `payment_format_risk (+1.333)` |
| `gather_scatter_mule` | Gather-Scatter Drain (`INR 240,000 ACH`) | `0.99` (FLAGGED) | **`0.9938` → `HOLD`** | `amount_zscore (+1.828)`, `time_since_last_credit_log (+1.635)`, `payment_format_risk (+1.365)` |
| `step_up_borderline` | First-Time High-Value Transfer (`INR 48,500 ACH`) | `0.63` (FLAGGED) | **`0.9930` → `STEP_UP`** | `time_since_last_credit_log (+1.635)`, `amount_zscore (+1.568)`, `payment_format_risk (+1.428)` |
| `corporate_payroll` | Corporate Payroll (`INR 42,000 ACH`, `fan_out=5`) | `0.60` (**False Positive**) | **`0.0183` → `ALLOW`** | `counterparty_novelty (-1.552)`, `time_since_last_credit_log (-0.314)`, `amount_zscore (-0.249)` |
| `retail_normal` | Normal Retail Transfer (`INR 1,850 Credit Card`) | `0.00` (ALLOW) | **`0.0034` → `ALLOW`** | `payment_format_risk (-1.474)`, `counterparty_novelty (-0.918)`, `amount_zscore (-0.251)` |

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
| 9 | `counterparty_novelty` | LRU + 8 KB Bloom (`O(1)`) | `0.0` if recipient is in sender's bounded LRU `known_payees` (`max=2048`) **or** overflow 64-kbit `PayeeBloomFilter`, else `1.0` |
| 10 | `amount_zscore` | Online Welford (`O(1)`) | Clipped sender Z-score $(\text{amt} - \mu) / \sigma$ using Welford running variance |
| 11 | `out_tx_velocity_1h` | 1h (`O(1)`) | `len(out_1h.q)` — total outgoing transactions in the last 3,600s |
| 12 | `payment_format_risk` | Instant (`O(1)`) | Rail risk weight (`Wire=1.0`, `ACH=0.75`, `Cash=0.65`, `Credit Card=0.30`, `Cheque=0.20`) |

### Memory Safety, Large-Payroll Bloom Filter & Verifiable Audit Chain
- **Large-Employer Payroll Safety (`PayeeBloomFilter`):** Normal accounts track up to `2,048` recurring payees in an exact LRU `OrderedDict`. When a large employer exceeds `2,048` payees, evicted payees are registered in a lazy-allocated **65,536-bit (8 KB) 3-hash `PayeeBloomFilter`**, preventing false novelty (`counterparty_novelty = 0.0`) on 5,000+ employee payrolls while keeping memory strictly bounded.
- **Receive-Only Eviction & Idle Account TTL:** Receiver windows (`in_15m`, `in_1h`, `in_24h`) evict expired entries on every credit arrival so receive-only accounts never grow unbounded, and `evict_idle_accounts()` sweeps inactive accounts after `idle_ttl_seconds`.
- **Full 64-Hex SHA-256 + HMAC-SHA256 Audit Chain:** Every `PolicyDecision` stores full 64-character `prev_audit_hash`, `audit_hash`, and `hmac_signature` computed over the canonical payload (including `model_version`, `hold_threshold`, `step_up_threshold`, and JSON-serialized `reason_codes`), protected by `threading.Lock()` and verifiable from genesis (`"0"*64`) via `PolicyEngine.verify_chain()`.

---

## 6. Quick Start & Automated Tests (`8 / 8` Passing)

### A. Run the Automated Pytest Suite
```bash
python -m pytest -v
```
Runs [`tests/test_hopstop.py`](tests/test_hopstop.py) (`8 passed`):
1. `test_sliding_window_o1_exactness` — exact agreement between $O(1)$ `SlidingWindow` and naive $O(W)$ window scans.
2. `test_receiver_eviction_and_idle_account_ttl` — receive-only accounts evict on append and `evict_idle_accounts()` frees stale state.
3. `test_large_employer_payroll_5000_payees_bloom_filter` — a corporate employer paying 5,000 recurring employees (`> 2,048` LRU cap) gets zero false novelty (`counterparty_novelty == 0.0`) via `PayeeBloomFilter`.
4. `test_strict_causality_no_future_leakage` — future transactions have zero effect on past features.
5. `test_treeshap_local_accuracy_additivity` — exact TreeSHAP local accuracy ($\sum \phi_j + \mathbb{E}[f(X)] = \text{raw\_margin}(x)$ to $10^{-9}$) across 50 random vectors.
6. `test_treeshap_signed_negative_attributions_on_payroll` — signed negative TreeSHAP log-odds on corporate payroll vs. positive on mule fan-out.
7. `test_audit_hash_chain_verification` — full 64-hex SHA-256 + HMAC-SHA256 verification from genesis and zero ground-truth leakage in `PolicyDecision`.
8. `test_audit_chain_single_byte_tamper_detection` — flipping a single byte in `risk_score`, `action`, `prev_audit_hash`, or `hmac_signature` makes `PolicyEngine.verify_chain()` fail.

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
├── .github/workflows/ci.yml  # GitHub Actions CI running 8 unit tests & benchmark verification
├── hopstop/
│   ├── __init__.py           # Package metadata
│   ├── data_generator.py     # Public IBM AMLworld CSV loader + 8-typology & delayed-evasion generator
│   ├── feature_engine.py     # Amortized O(1) SlidingWindow, LRU + 8KB PayeeBloomFilter & CSPRNG/Env HMAC
│   ├── ibmz_runtime.py       # s390x facility probe, Snap ML wrapper, exact TreeSHAP & LogReg/Rules baselines
│   ├── policy_engine.py      # Validation threshold calibration & verifiable 64-hex SHA-256 + HMAC audit chain
│   ├── train_and_benchmark.py# 3-way split training, 95% bootstrap CIs, evasion test & latency profiler
│   ├── server.py             # Multi-threaded REST API (/api/benchmarks, /api/score_preset, /api/verify_audit)
│   └── dashboard.html        # Interactive Analyst Console (live API + standalone offline support)
├── tests/
│   └── test_hopstop.py       # 8 unit & property tests (O(1) windows, 5k-payee Bloom, causality, TreeSHAP, tamper)
├── artifacts/
│   ├── benchmark_results.json# Single-run 3-way split metrics, real test examples, 95% CIs & latencies
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
