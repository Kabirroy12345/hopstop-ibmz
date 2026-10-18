# HopStop — Real-Time Pre-Settlement Money-Mule Interdiction on IBM Z & LinuxONE

<div align="center">

[![Platform](https://img.shields.io/badge/Target_Platform-IBM_Z_%26_LinuxONE_(s390x)-0f62fe?style=for-the-badge&logo=ibm&logoColor=white)](https://www.ibm.com/z)
[![Verified Scorers](https://img.shields.io/badge/Verified_x86__64_Backends-Portable_JSON_GBDT_%2B_Snap_ML_1.17.2_(WSL2_Linux)-4f46e5?style=for-the-badge)](#3-measured-benchmark-results-unified-3-way-chronological-protocol)
[![Chains Stopped](https://img.shields.io/badge/Chains_Stopped_%E2%89%A4_Hop_2-84.0%25_(42%2F50_Overall)_%7C_50.0%25_Delayed_Evasion-f43f5e?style=for-the-badge)](#3-measured-benchmark-results-unified-3-way-chronological-protocol)
[![PR-AUC](https://img.shields.io/badge/Test_PR--AUC-0.8100_(Portable_GBDT)_%7C_0.8340_(Snap_ML_1.17.2)-f59e0b?style=for-the-badge)](#3-measured-benchmark-results-unified-3-way-chronological-protocol)
[![Tests](https://img.shields.io/badge/Pytest_Suite-22_%2F_22_Passing-10b981?style=for-the-badge)](tests/test_hopstop.py)
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

**HopStop** addresses these challenges by co-locating **amortized $O(1)$ streaming graph-velocity feature extraction**, **Day-7 calibrated depth-2 GBDT / Snap ML scoring with on-alert exact path-dependent TreeSHAP**, and **verifiable HMAC-SHA256 hash-chained audit logging** on **IBM Z / LinuxONE (`s390x`)**, scoring outgoing transfers **before settlement** so suspicious chains are frozen at **Hop 1 or Hop 2**.

---

## 2. End-to-End Architecture & IBM Z / LinuxONE Integration

<div align="center">
  <img src="submission/HopStop_System_Architecture.svg" alt="HopStop Overall System Architecture on IBM Z & LinuxONE" width="100%" />
  <br/>
  <sub><b>Figure 1:</b> HopStop Pre-Settlement Inference & Cryptographic Audit Pipeline. <a href="submission/HopStop_Architecture_Diagram.pdf">Download Architecture PDF</a> • <a href="submission/HopStop_System_Architecture.png">View High-Res PNG</a> • <a href="submission/HopStop_System_Architecture.svg">View Vector SVG</a></sub>
</div>

### Hardware & Runtime Mapping (`hopstop/ibmz_runtime.py`)

| Capability | Implementation in HopStop | Measured Backend & Operational Disclosure |
| :--- | :--- | :--- |
| **Portable JSON Tensor-Tree Engine (`portable_python_depth2_gbdt`)** | Always fits, calibrates (Day-7 PAVA isotonic + prior-shift), and exports a portable JSON depth-2 tree ensemble ([`artifacts/hopstop_model.json`](artifacts/hopstop_model.json), avoiding insecure `.pkl` files) with exact path-dependent TreeSHAP. | Executed on `Windows 11 (Intel64 Family 6 Model 154, AMD64, Python 3.13.9)` where `snapml` has no Windows wheel. Produces the baseline metrics in [`artifacts/benchmark_results.json`](artifacts/benchmark_results.json). |
| **Native Snap ML C++ Runtime (`snapml.BoostingMachineClassifier(tree_format='auto')`)** | [`SnapMLAcceleratedScorer.fit()`](hopstop/ibmz_runtime.py) and [`hopstop/benchmark_snapml_linux.py`](hopstop/benchmark_snapml_linux.py) train `snapml.BoostingMachineClassifier` and invoke `optimize_trees(tree_format='auto')`, while [`detect_ibmz_environment()`](hopstop/ibmz_runtime.py) probes `/proc/cpuinfo` (`facility 165`) and `libzdnn.so`. | **Measured on `WSL 2 Ubuntu Linux 6.6.87.2 (x86_64, Python 3.12.3, snapml 1.17.2)`** under the exact same 3-way split protocol (`linux_snapml_verification` in [`artifacts/benchmark_results.json`](artifacts/benchmark_results.json)). *Hardware Disclosure:* All numbers in this repo were measured on `x86_64` CPU; on an actual `s390x` IBM z16 / LinuxONE host ([`Dockerfile.s390x`](Dockerfile.s390x)), `tree_format='auto'` targets the z16 accelerator format when Facility 165 (`nnpa`) is exposed and compressed CPU trees otherwise. |
| **Facility 17 / 76 / 77 / 146 (`msa` — CPACF Crypto) & Key Lifecycle** | [`hash_account_id()`](hopstop/feature_engine.py) pseudonymizes account IDs via `HMAC-SHA256` into 128-bit (`ACCT_<32-hex>`) tokens; [`PolicyEngine`](hopstop/policy_engine.py) chains all decisions (`ALLOW`, `STEP_UP`, `HOLD`) with 64-hex SHA-256 + HMAC-SHA256. | **Key Lifecycle Disclosure:** If `HOPSTOP_HMAC_KEY` / `HOPSTOP_AUDIT_HMAC_KEY` are not set, HopStop generates a **per-process 256-bit CSPRNG ephemeral key** (`secrets.token_hex(32)`). This is a safe public-repo default (zero secrets in Git), but **restarting without env keys rotates account pseudonyms and invalidates prior audit HMAC signatures**. Production deployments must inject persistent keys from an HSM / PKCS#11 EP11 store via environment variables. |
| **Facility 158 (`prot_virt` — IBM Secure Execution)** | Probed via `/proc/cpuinfo` (`facility 158`) and `/sys/firmware/uv` for confidential LinuxONE guest enclave deployment ([`Dockerfile.s390x`](Dockerfile.s390x)). | Protects in-memory sliding-window state and HMAC keys inside an Ultravisor-isolated LinuxONE container. |

---

## 3. Measured Benchmark Results (Unified 3-Way Chronological Protocol)

All metrics below are generated in a single reproducible pipeline ([`hopstop/train_and_benchmark.py`](hopstop/train_and_benchmark.py) + [`hopstop/benchmark_snapml_linux.py`](hopstop/benchmark_snapml_linux.py)) and stored in [`artifacts/benchmark_results.json`](artifacts/benchmark_results.json). Both the **Portable JSON Depth-2 GBDT** and **Native `snapml 1.17.2`** are evaluated under the **exact same 3-way chronological split and calibration protocol**:

1. **Train Split (Days 1–6, $\le 0.60 \times T_{\max}$):** `30,616` transactions (`494` laundering transfers) — used to fit all models with positive class weight `14.0`.
2. **Validation Split (Day 7, $0.60 \times T_{\max} < t \le 0.70 \times T_{\max}$):** `5,032` transactions (`114` laundering transfers) — used **exclusively** for:
   - **Early-stopping tree selection** (`best_n` prefix maximizing Day-7 PR-AUC),
   - **PAVA Isotonic + Prior-Shift Probability Calibration** (`calibrate_on_validation`), and
   - **Operating threshold calibration** (`step_up_threshold` at the `99.0th` validation percentile for a **1.0% analyst alert budget**, and `hold_threshold` at the `99.5th` validation percentile for a **0.5% pre-settlement freeze budget**).
3. **Unseen Test Split (Days 8–10, $> 0.70 \times T_{\max}$):** `15,232` transactions (`272` laundering transfers, **`1.7857%` positive prevalence**, across `50` chains: `38` fast chains with `<15m` hop turnover and `12` delayed-hop evasion chains that wait `22.5 minutes` between Hop 1 and Hop 2).

> **Dataset Disclosure:** By default, the pipeline runs on the built-in deterministic 50,880-transaction IBM AMLworld-schema generator ([`hopstop/data_generator.py`](hopstop/data_generator.py)) so the repository runs out-of-the-box in CI without a 475 MB download. To run the exact same causal feature engine and 3-way split on the public Kaggle **IBM Transactions for Anti-Money Laundering (`HI-Small_Trans.csv`)** dataset, pass `--csv /path/to/HI-Small_Trans.csv --max-rows 200000` to `python -m hopstop.train_and_benchmark`.

### A. Unified Model Comparison on Unseen Test Split (`Days 8–10`, `15,232` Tx, `272` Laundering)

*Note on Recall Ceiling:* Because the unseen test set has **`272` laundering transfers (`1.79%` prevalence)**, a **1.0% alert budget allows at most `152` alerts (`1% of 15,232`)**, which mathematically caps maximum possible Recall@1% at **`152 / 272 = 55.88%`**. We therefore report both Recall@1% (alongside % of the `55.88%` ceiling), Recall at the **prevalence-matched `1.79%` budget (`272` alerts, where the ceiling is `100.0%`)**, and **Bayes-adjusted precision at realistic production base rates (`10 bps = 0.10%` and `5 bps = 0.05%`)**.

| Metric (Identical 3-Way Protocol & Tie-Invariant Evaluation) | HopStop Portable JSON GBDT (`Py 3.13`, Calibrated) | Native `snapml 1.17.2` `tree_format='auto'` (`WSL 2 Linux Py 3.12`) | Logistic Regression (Same 12 Features) | Static Velocity-Rules Baseline |
| :--- | :---: | :---: | :---: | :---: |
| **Test PR-AUC (95% Stratified Bootstrap CI)** | **`0.8100`** `[0.7720, 0.8513]` | **`0.8340`** `[0.7933, 0.8696]` | `0.8059` `[0.7685, 0.8521]` | `0.4471` `[0.3903, 0.5098]` |
| **Test ROC-AUC** | **`0.9833`** | **`0.9837`** | `0.9804` | `0.8957` |
| **Recall @ 1.0% Alert Budget (`152` alerts; Max Ceiling = `55.88%`)** | **`53.75%`** (`96.2%` of ceiling) `[51.56%, 55.15%]` | **`54.78%`** (`98.0%` of ceiling) `[52.57%, 55.51%]` | `52.57%` (`94.1%` of ceiling) `[50.74%, 54.78%]` | `35.66%` (`63.8%` of ceiling) `[31.10%, 41.18%]` |
| **Precision @ 1.0% Budget (Test `1.79%` Base Rate)** | **`96.18%`** | **`98.03%`** | `94.08%` | `63.82%` |
| **Bayes Precision @ 1.0% Budget (`10 bps = 0.10%` Realistic Prior)** | **`58.12%`** | **`73.23%`** | `46.63%` | `8.85%` |
| **Bayes Precision @ 1.0% Budget (`5 bps = 0.05%` Realistic Prior)** | **`40.95%`** | **`57.76%`** | `30.39%` | `4.63%` |
| **Recall & Precision @ Prevalence Budget (`1.79%` = `272` alerts; Ceiling = `100%`)** | **`74.02%`** | **`80.15%`** | `76.97%` | `48.90%` |
| **Recall @ 2.0% Alert Budget (`304` alerts; Ceiling = `100%`)** | **`78.29%`** | **`80.83%`** | `78.68%` | `48.90%` |
| **Day-7 Calibrated Thresholds (`HOLD` / `STEP_UP`)** | `0.9390` / `0.8797` *(calibrated prob)* | `0.9952` / `0.9905` *(raw Snap ML prob)* | `0.8998` / `0.8404` | `0.6300` / `0.4500` |
| **Realized Unseen Test Alert Rate** | `0.83%` (`127` alerts, `58` `HOLD`s) | `0.68%` | `0.84%` | `1.54%` |
| **Overall Chains Stopped $\le$ Hop 2 (All `50` Test Chains)** | **`84.0%` (`42 / 50`)** | **`84.0%` (`42 / 50`)** | `90.0%` (`45 / 50`) | `66.0%` (`33 / 50`) |
| **Fast Chains Stopped $\le$ Hop 2 (`<15m` wait, $n=38$)** | **`94.7%` (`36 / 38`)** | **`100.0%` (`38 / 38`)** | `94.7%` (`36 / 38`) | `84.2%` (`32 / 38`) |
| **Delayed Evasion Chains Stopped (`22.5m` wait, $n=12$)** | **`50.0%` (`6 / 12`)** *(Wilson CI `[25.4%, 74.6%]`)* | **`33.3%` (`4 / 12`)** | `75.0%` (`9 / 12`) | `8.3%` (`1 / 12`) |

### B. Alert-Budget Scaling Curve & Realistic Base-Rate Precision (`alert_budget_curve` in `benchmark_results.json`)

For any alert budget $B$ (`alerts_count` $= A$) on $P = 272$ positives (`test_prevalence` $\pi_{\text{test}} = 272 / 15,232 = 1.7857\%$), maximum possible recall is bounded by $\text{Ceiling}(B) = \min(1.0, A / P)$ (enforced in `test_alert_budget_recall_ceiling_and_dashboard_sync`). To evaluate precision under realistic banking base rates $\pi_{\text{real}} \in \{10\text{ bps} (0.10\%), 5\text{ bps} (0.05\%)\}$, we compute Bayes prior-adjusted precision from test TPR and FPR:

$$\text{Precision}(\pi_{\text{real}}) = \frac{\text{TPR} \cdot \pi_{\text{real}}}{\text{TPR} \cdot \pi_{\text{real}} + \text{FPR} \cdot (1 - \pi_{\text{real}})}$$

| Alert Budget ($B$) | Allowed Alerts ($A$) | Mathematical Recall Ceiling ($\min(1, A/272)$) | HopStop GBDT Recall (% of Ceiling) | LogReg Recall | Static Rules Recall | HopStop Test Precision (`1.79%` Prior) | HopStop Precision @ `10 bps` (`0.10%` Prior) | HopStop Precision @ `5 bps` (`0.05%` Prior) | Chains Stopped $\le$ Hop 2 |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`0.50%`** | `76` | **`27.94%`** | **`27.94%`** (**`100.0%`**) | `27.94%` | `21.55%` | `100.00%` | **`99.92%`** | **`99.85%`** | `46.0%` (`23/50`) |
| **`1.00%`** | `152` | **`55.88%`** | **`53.75%`** (**`96.2%`**) | `52.57%` | `35.66%` | `96.18%` | **`58.12%`** *(Snap ML: `73.23%`)* | **`40.95%`** *(Snap ML: `57.76%`)* | `84.0%` (`42/50`) |
| **`1.50%`** | `228` | **`83.82%`** | **`66.93%`** (`79.8%`) | `70.96%` | `48.90%` | `79.84%` | `17.91%` | `9.83%` | `100.0%` (`50/50`) |
| **`1.79%` (Prevalence)** | `272` | **`100.00%`** | **`74.02%`** (`74.0%`) | `76.97%` | `48.90%` | `74.02%` | `13.56%` | `7.27%` | `100.0%` (`50/50`) |
| **`2.00%`** | `304` | **`100.00%`** | **`78.29%`** (`78.3%`) | `78.68%` | `48.90%` | `70.05%` | `11.41%` | `6.05%` | `100.0%` (`50/50`) |
| **`2.50%`** | `380` | **`100.00%`** | **`82.71%`** (`82.7%`) | `81.99%` | `56.03%` | `59.20%` | `7.40%` | `3.84%` | `100.0%` (`50/50`) |

### C. Tie-Invariant Paired Bootstrap Comparisons & Engineering Takeaways

> **Why Tie-Invariant Grouping Matters for Discrete Tree/Rule Scores:** In stratified bootstrap resampling (`idx_sample = s_pos + s_neg`), positive indices precede negative indices. A naive `sorted(zip(y_scores, y_true), key=lambda x: x[0], reverse=True)` uses Python's stable Timsort, which breaks tied scores by placing `y=1` first—biasing bootstrap PR-AUC upward on discrete-score models (`VelocityRulesBaseline` and `Depth2Tree`). Grouping by distinct score thresholds in [`compute_roc_and_pr_auc()`](hopstop/train_and_benchmark.py) and [`recall_at_alert_rate()`](hopstop/train_and_benchmark.py) makes all metrics **100% order-invariant and tie-invariant** (verified in `test_tie_invariance_and_paired_bootstrap_delta_consistency`), so bootstrap mean differences align with point estimate differences:

| Paired Comparison (`400` Stratified Transaction Resamples, $n=15,232$) | Point $\Delta\text{PR-AUC}$ | Bootstrap Mean $\Delta\text{PR-AUC}$ (95% CI) | Point $\Delta\text{Recall@1\%}$ | Bootstrap Mean $\Delta\text{Recall@1\%}$ (95% CI) | Statistical Conclusion |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **HopStop GBDT minus Static Rules (`gbdt_minus_rules`)** | **`+0.3629`** (`0.8100 - 0.4471`) | **`+0.3604`** `[+0.3081, +0.4064]` | **`+18.09%`** (`53.75% - 35.66%`) | **`+17.78%`** `[+12.87%, +22.98%]` | **Highly significant gain** driven by the 12 causal $O(1)$ graph-velocity features. |
| **HopStop GBDT minus Logistic Regression (`gbdt_minus_logreg`)** | **`+0.0041`** (`0.8100 - 0.8059`) | **`+0.0018`** `[-0.0158, +0.0213]` | **`+1.18%`** (`53.75% - 52.57%`) | **`+0.72%`** `[-0.74%, +2.94%]` | **Statistically tied** on PR-AUC and Recall@1% (95% CIs span zero). |

1. **The 12 Causal $O(1)$ Features Do the Heavy Lifting on Accuracy:** Moving from static rules to the 12 streaming features lifts PR-AUC by **`+0.3629`** (`0.4471` $\to$ `0.8100` portable GBDT / `0.8059` LogReg / `0.8340` native Snap ML). While portable GBDT and LogReg are tied on overall PR-AUC, tree ensembles (`0.9618` / `0.9803` test precision; **`58.12%` / `73.23%` precision at `10 bps` prior**) achieve sharper top-tail concentration at the `1.0%` alert budget than linear scoring (`46.63%` at `10 bps` prior), and support **exact path-dependent TreeSHAP** and **high-throughput C++ batching (`6.25M TPS` at `batch=64`)**.
2. **Evasion Analysis (`84.0%` Overall vs. `50.0%` on Delayed `22.5m` Chains):** Overall, HopStop stops **`84.0%` (`42 / 50`)** of test chains by Hop 2 (`94.7%`, `36 / 38` on fast `<15m` chains; `100.0%`, `38 / 38` with native Snap ML). When adversaries delay **`22.5 minutes`** between Hop 1 and Hop 2 (`delayed_evasion_22m_chains`, $n=12$) to age out the `15m` pass-through window, interception drops to **`50.0%` (`6 / 12`, 95% Wilson CI `[25.4%, 74.6%]`)** for Portable GBDT and `33.3%` (`4 / 12`) for Snap ML (vs. `8.3%`, `1 / 12` for Static Rules). Adding **longer-horizon (`6h` and `24h`) exponentially decayed pass-through ratios** is the highest-leverage next enhancement.

---

### D. Component-Level Latency & Single-Row vs. Batch Throughput Disclosure

#### 1. Portable Python Depth-2 GBDT (`Windows 11, AMD64, Python 3.13.9`, `3,000` sequential `batch=1` evaluations)

Exact path-dependent TreeSHAP (`top_reason_codes`) runs **only on flagged `HOLD` / `STEP_UP` transfers** (`0.83%` of traffic) plus analyst console queries, keeping `99.17%` of routine `ALLOW` traffic on the fast scoring path:

| Pipeline Stage (`batch=1` Sequential Stream) | Execution Frequency | Median (`p50`) | `p95` | `p99` | SLA Target |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **1. Amortized $O(1)$ Feature Extraction (`StreamingFeatureEngine`)** | `100%` of transfers | `0.0616 ms` (`61.6 µs`) | — | — | — |
| **2a. Calibrated Depth-2 GBDT Scoring Only (`score_one`)** | `100%` of transfers | **`0.0134 ms` (`13.4 µs`)** | — | — | — |
| **2b. Exact Path-Dependent TreeSHAP (`top_reason_codes`, on-alert only)** | `0.83%` (flagged alerts) | **`0.1816 ms` (`181.6 µs`)** | — | `0.2465 ms` | — |
| **3. Policy Evaluation + Full 64-Hex SHA-256 & HMAC Audit (`PolicyEngine`)** | `100%` of transfers | `0.0727 ms` (`72.7 µs`) | — | — | — |
| **Total End-to-End Decision Latency (`batch=1`, amortized across stream)** | `100%` of transfers | **`0.1509 ms` (`150.9 µs`)** | **`0.2033 ms`** | **`0.3946 ms`** | **`< 10.0 ms` (25x faster)** |

#### 2. Native `snapml 1.17.2` vs. Portable Python (`batch=1` vs. Model-Only `batch=64` on `x86_64` CPU)

| Runtime Backend | Host Environment | Fit + `optimize_trees` | Single-Row `batch=1` Scoring `p50` / `p99` | `batch=64` Throughput & Scope Disclosure |
| :--- | :--- | :---: | :---: | :--- |
| **`snapml.BoostingMachineClassifier(tree_format='auto')` (`1.17.2`)** | `WSL 2 Linux 6.6.87.2 (x86_64)`, `Python 3.12.3` | **`0.0311 s` (`31.1 ms`)** | **`0.0082 ms` (`8.2 µs`)** / `0.0512 ms` | **`6,245,645 TPS` (`0.160 µs/tx`)** — **Model-only `predict_proba` batch scoring on `x86_64` CPU** (excludes feature extraction & SHA-256 audit). |
| **`portable_python_depth2_gbdt` (JSON fallback)** | `Windows 11 (AMD64)`, `Python 3.13.9` | `6.431 s` | **`0.0134 ms` (`13.4 µs`)** *(uncalibrated: `0.0073 ms`)* | **`92,660 TPS`** (`batch=64` model-only) / **`6,090 TPS`** (full single-worker end-to-end stream with feature extraction + 15,232 SHA-256/HMAC audit records). |

> **Single-Row (`batch=1`) vs. Micro-Batch (`batch=64`) Engineering Note:** On a single 12-feature transaction (`batch=1`), calling `snapml`'s C++ `predict_proba` across the Python / NumPy / C++ boundary takes **`8.2 µs` (`0.0082 ms`)**, which is slightly slower than raw pure-Python tree traversal (`7.3 µs`) and comparable to calibrated Python scoring (`13.4 µs`). Snap ML's C++ vectorization advantage only materializes when scoring **micro-batches (`batch=64`: `0.160 µs/tx`, `6.25M TPS` model-only)** or during model training (`0.031 s` vs. `6.43 s`).

---

## 4. Calibrated Probabilities, Validation Percentiles & Unseen Test-Split Case Studies

Because training uses `pos_weight=14.0` to emphasize rare laundering chains, raw sigmoid outputs cluster near `0.98–0.99` in the upper tail. [`SnapMLAcceleratedScorer.calibrate_on_validation()`](hopstop/ibmz_runtime.py) fits a **Day-7 PAVA Isotonic Regression + Prior-Shift Calibrator** and stores the **Day-7 validation score distribution (`5,032` transfers)** inside [`artifacts/hopstop_model.json`](artifacts/hopstop_model.json). Every scored transaction reports:
- **`hopstop_score`**: Day-7 calibrated empirical laundering probability (`HOLD >= 0.9390`, `STEP_UP >= 0.8797`),
- **`hopstop_val_percentile`**: Exact empirical percentile rank on the Day-7 validation set (`HOLD >= P99.50`, `STEP_UP >= P99.00`), and
- **Exact Path-Dependent TreeSHAP (`reason_codes`)**: Satisfying $\sum_{j=1}^{12} \phi_j(x) + \mathbb{E}[f(X)] = \text{raw\_margin}(x)$ to $10^{-9}$.

### A. Deterministic Unseen Test-Split (`Days 8–10`) Case Studies — Wins & False Negative

[`hopstop/train_and_benchmark.py`](hopstop/train_and_benchmark.py) selects four unseen test transactions (`real_test_case_examples` in [`artifacts/benchmark_results.json`](artifacts/benchmark_results.json)) via a **deterministic chronological scan of `Days 8–10`**:
1. **First Interior `HOLD`** (`risk_score > hold_threshold = 0.939048`): **`tx_id=35896`** (`score = 0.9431`, **`Val P99.95`**).
2. **First Boundary `HOLD`** (`risk_score == hold_threshold = 0.939048`): **`tx_id=35893`** (`score = 0.9390`, **`Val P99.50`**).
3. **First Benign Corporate Batch `ALLOW`** (`fan_out_1h >= 3`, `pass_through_15m == 0`, `rules_score >= 0.45`): **`tx_id=35895`** (`score = 0.000059`, **`Val P43.72`**).
4. **First Missed Laundering Transfer (False Negative, `is_laundering == 1` and `action == ALLOW`)**: **`tx_id=35747`** (`score = 0.8773`, **`Val P98.99`** — just `0.01` percentile points below the `P99.00` `STEP_UP` cutoff `0.8797`).

| Signal / Output | 1. Interior Mule `HOLD` (`tx_id=35896`, Hop 3 Wire) | 2. Boundary Mule `HOLD` (`tx_id=35893`, Hop 3 Wire) | 3. Benign Corporate Batch (`tx_id=35895`, Legit ACH) | 4. Missed Mule **False Negative** (`tx_id=35747`, Hop 2 ACH) |
| :--- | :--- | :--- | :--- | :--- |
| **`fan_in_1h` / `fan_out_1h`** | `1.0` / `0.0` (`fan_in_24h=3.0`) | `1.0` / `0.0` (`fan_out_24h=3.0`) | `0.0` / **`4.0`** *(triggers static rules!)* | `3.0` / `1.0` (`fan_in_24h=4.0`) |
| **`pass_through_ratio_15m`** | **`0.96`** (`260s` after credit) | **`0.96`** (`244s` after credit) | **`0.00`** *(reserve-funded payroll)* | **`0.64`** *(just below `0.65` rapid-turnover cutoff!)* |
| **`rapid_turnover_flag`** | **`1.0`** | **`1.0`** | **`0.0`** | **`0.0`** *(missed `0.65` cutoff by `0.01`)* |
| **`counterparty_novelty`** | **`1.0`** *(new recipient)* | **`1.0`** *(new recipient)* | **`0.0`** *(known recurring payee)* | **`1.0`** *(new recipient)* |
| **`amount_zscore`** | `10.00` (clipped ceiling) | `10.00` (clipped ceiling) | `0.65` | `2.26` |
| **Static Rules Baseline** | `0.63` → **FLAGGED** | `0.63` → **FLAGGED** | `0.60` → **FLAGGED (False Positive)** | `0.40` → **MISSED (`ALLOW`)** |
| **Calibrated Score & Val Percentile** | **`0.9431` (`Val P99.95`) → `HOLD`** *(raw: `0.9938`)* | **`0.9390` (`Val P99.50`) → `HOLD`** *(raw: `0.9931`)* | **`0.000059` (`Val P43.72`) → `ALLOW`** *(raw: `0.0159`)* | **`0.8773` (`Val P98.99`) → `ALLOW`** *(raw: `0.9870`)* |
| **Exact TreeSHAP Explanation** | `amount_zscore (+1.860)`, `time_since_credit (+1.635)`, `format_risk (+1.503)` | `amount_zscore (+1.924)`, `time_since_credit (+1.635)`, `format_risk (+1.503)` | `counterparty_novelty (-1.552)`, `amount_zscore (-0.390)`, `time_since_credit (-0.314)` | Ranked at **`P98.99`** on Day 7 (`+1.635` post-credit dispersal, `+1.613` z-score, `+1.563` ACH risk), falling **`0.01` percentile points** short of the strict `1.0%` alert budget (`P99.00`, `0.8797`). |

### B. Hand-Specified Illustrative Sandbox Presets (`/api/score_preset` in [`hopstop/server.py`](hopstop/server.py))

Alongside the 4 real unseen test-split transactions (`/api/score_preset?type=real_test_mule_hold`, etc.), the live console provides 5 hand-specified illustrative sandbox scenarios (`scenario_source = "hand_specified_sandbox_illustration"`):

| Preset Key | Illustrative Scenario | Static Rules Score | Calibrated Score (`Val Percentile`) & Action | Top Exact TreeSHAP Log-Odds Attributions |
| :--- | :--- | :---: | :---: | :--- |
| `fan_out_mule` | Mule Hop-1 Fan-Out (`INR 185,000 Wire`) | `0.99` (FLAGGED) | **`0.9431` (`Val P99.95`) → `HOLD`** | `amount_zscore (+1.828)`, `time_since_last_credit_log (+1.635)`, `payment_format_risk (+1.333)` |
| `gather_scatter_mule` | Gather-Scatter Drain (`INR 240,000 ACH`) | `0.99` (FLAGGED) | **`0.9431` (`Val P99.95`) → `HOLD`** | `amount_zscore (+1.828)`, `time_since_last_credit_log (+1.635)`, `payment_format_risk (+1.365)` |
| `step_up_borderline` | First-Time High-Value Transfer (`INR 48,500 ACH`) | `0.63` (FLAGGED) | **`0.9167` (`Val P99.40`) → `STEP_UP`** | `time_since_last_credit_log (+1.635)`, `amount_zscore (+1.568)`, `payment_format_risk (+1.428)` |
| `corporate_payroll` | Corporate Payroll (`INR 42,000 ACH`, `fan_out=5`) | `0.60` (**False Positive**) | **`0.000059` (`Val P44.20`) → `ALLOW`** | `counterparty_novelty (-1.552)`, `time_since_last_credit_log (-0.314)`, `amount_zscore (-0.249)` |
| `retail_normal` | Normal Retail Transfer (`INR 1,850 Credit Card`) | `0.00` (ALLOW) | **`0.000059` (`Val P12.60`) → `ALLOW`** | `payment_format_risk (-1.474)`, `counterparty_novelty (-0.918)`, `amount_zscore (-0.251)` |

---

## 5. Amortized $O(1)$ Feature Engine, Rotating Bloom Filter Math & Full Audit Chain

### A. The 12 Causal $O(1)$ Streaming Features (`hopstop/feature_engine.py`)

Each per-account time window is managed by [`SlidingWindow`](hopstop/feature_engine.py), which pairs a FIFO `deque` with a reference-counted counterparty map (`cnt: Dict[str, int]`) and running total (`total: float`). Both `distinct_peers` (`len(w.cnt)`) and `sum_amount` (`w.total`) execute in **$O(1)$ time**:

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
| 9 | `counterparty_novelty` | LRU + Rotating Bloom (`O(1)`) | `0.0` if recipient is in sender's exact LRU `known_payees` (`max=2,048`) **or** dual-generation `PayeeBloomFilter`, else `1.0` |
| 10 | `amount_zscore` | Online Welford (`O(1)`) | Clipped sender Z-score $(\text{amt} - \mu) / \sigma \in [-3, 10]$ using Welford running variance |
| 11 | `out_tx_velocity_1h` | 1h (`O(1)`) | `len(out_1h.q)` — total outgoing transactions in the last 3,600s |
| 12 | `payment_format_risk` | Instant (`O(1)`) | Rail risk weight (`Wire=1.0`, `ACH=0.75`, `Cash=0.65`, `Credit Card=0.30`, `Cheque=0.20`) |

### B. Exact Single- & Dual-Generation Bloom Filter FPR Math & Dormancy Horizon (`PayeeBloomFilter`)

[`PayeeBloomFilter`](hopstop/feature_engine.py) is lazily allocated only when a hub account exceeds `2,048` recurring payees (`99.9%` of accounts use `0 bytes` of Bloom memory and have `0.0%` exact-LRU FPR). It maintains two generations (`active_bits` and `prev_bits`) with $k = 4$ SHA-256 probes. Because `contains()` queries **both** generations (`active_bits OR prev_bits`), the single-generation and combined dual-generation false-positive rates are:

$$\text{FPR}_1(n, m) = \left(1 - e^{-kn/m}\right)^k, \qquad \text{FPR}_{\text{dual}}(n_{\text{act}}, n_{\text{prev}}, m) = 1 - \bigl(1 - \text{FPR}_1(n_{\text{act}}, m)\bigr)\bigl(1 - \text{FPR}_1(n_{\text{prev}}, m)\bigr)$$

Both configurations below are verified in [`PayeeBloomFilter.single_generation_fpr()`](hopstop/feature_engine.py), [`PayeeBloomFilter.dual_generation_fpr()`](hopstop/feature_engine.py), and `test_bloom_filter_exact_fpr_math_and_60day_dormancy`:

| Filter Allocation (`k = 4` probes) | Bits per Generation ($m$) | Single-Gen FPR @ $n=10\text{k}$ Evicted | Dual-Gen FPR @ $(10\text{k}, 10\text{k})$ | Single-Gen FPR @ $n=25\text{k}$ (Rotation Cap) | Dual-Gen Peak FPR @ $(25\text{k}, 25\text{k})$ Just Before Rotation |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Default Production (`64 KB/gen` = `128 KB total` across 2 gens)** | `524,288` bits (`65,536 B/gen`) | **`0.00291%`** (`2.91e-5`) | **`0.00582%`** | **`0.0910%`** (`9.10e-4`) | **`0.1819%`** (`< 0.2%`) |
| **Compact Option (`32 KB/gen` = `64 KB total` across 2 gens)** | `262,144` bits (`32,768 B/gen`) | **`0.0401%`** (`4.01e-4`) | **`0.0802%`** | **`1.012%`** (`1.01e-2`) | **`2.014%`** (`~2.0%`) |

- **Automatic Rotation (`rotate_generation()`):** Triggered whenever `active_count >= 25,000` evicted payees or `30 days` (`2,592,000s`) elapse (`active_bits` demotes to `prev_bits` and a zeroed `active_bits` starts).
- **Dormant Payee Horizon (`> 60 Days` Limitation):** Any recurring counterparty that is evicted from the `2,048`-entry exact LRU **and remains completely dormant across two consecutive 30-day Bloom rotations (`> 60 days` total, e.g., an annual or quarterly vendor)** will age out of both `active_bits` and `prev_bits` and be scored as a novel counterparty (`counterparty_novelty = 1.0`) on its next transfer. Quarterly/annual vendor whitelists should therefore be persisted in the database or given a longer rotation period.

### C. Full `15,232`-Decision SHA-256 + HMAC-SHA256 Audit Chain (`hopstop/policy_engine.py`)

When `PolicyEngine(log_allow_decisions=True)` is active (default in `train_and_benchmark.py` and `server.py`), **every decision (`ALLOW`, `STEP_UP`, and `HOLD` — all `15,232` unseen test transfers)** is committed into the hash chain (`H_n = SHA256(H_{n-1} || canonical_payload)`, signed with `HMAC_SHA256(key, H_n)`). Deleting even a single `ALLOW` record breaks `prev_audit_hash` continuity on the following record and fails `PolicyEngine.verify_chain()` (`test_audit_chain_single_byte_tamper_detection[delete_allow_record]`).

---

## 6. Quick Start & Automated Tests (`22 / 22` Passing)

### A. Run the Automated Pytest Suite (`22 passed`)
```bash
python -m pytest -v
```
Runs [`tests/test_hopstop.py`](tests/test_hopstop.py) (`22 passed` across 12 test functions, including `@pytest.mark.parametrize` over **all 11 canonical audit tamper & record-deletion modes**):
- `test_sliding_window_o1_exactness` — exact agreement between $O(1)$ `SlidingWindow` and naive $O(W)$ scans.
- `test_receiver_eviction_and_idle_account_ttl` — receive-only accounts evict on append and `evict_idle_accounts()` frees stale state.
- `test_large_employer_payroll_5000_payees_bloom_filter` — verifies zero false novelty on 5,000 recurring employees and verifies dual-generation aging.
- `test_bloom_filter_exact_fpr_math_and_60day_dormancy` — verifies exact single-gen and dual-gen FPR formulas for both `64 KB/gen` (`524,288` bits) and `32 KB/gen` (`262,144` bits), plus the `> 60-day` two-rotation dormancy horizon.
- `test_strict_causality_no_future_leakage` — future transactions have zero effect on past features.
- `test_treeshap_local_accuracy_additivity` — exact TreeSHAP local accuracy ($\sum \phi_j + \mathbb{E}[f(X)] = \text{raw\_margin}(x)$ to $10^{-9}$) across 50 random vectors.
- `test_treeshap_signed_negative_attributions_on_payroll` — signed negative TreeSHAP log-odds on corporate payroll vs. positive on mule fan-out.
- `test_tie_invariance_and_paired_bootstrap_delta_consistency` — verifies that `compute_roc_and_pr_auc` and `recall_at_alert_rate` are 100% invariant to `[y=1 first]` vs. `[y=0 first]` tie ordering and that `point_delta_pr_auc` matches `benchmark_results.json`.
- `test_alert_budget_recall_ceiling_and_dashboard_sync` — asserts `recall <= alerts / positives` across all budgets in `alert_budget_curve` and verifies that `dashboard.html` contains no impossible recall figures.
- `test_day7_isotonic_calibration_and_percentile_rank` — verifies Day-7 PAVA isotonic + prior-shift calibration and validation percentile ranks on `hopstop_model.json`.
- `test_audit_hash_chain_verification` & `test_audit_chain_single_byte_tamper_detection[...]` (**11 parametrized cases**) — verifies tamper detection across all canonical fields and `ALLOW` record deletion.

### B. Run Training, Validation Calibration & Benchmarks
```bash
# 1. Cross-platform full benchmark (writes artifacts/benchmark_results.json & artifacts/hopstop_model.json):
python -m hopstop.train_and_benchmark

# 2. Optional: run on a public IBM AMLworld HI-Small_Trans.csv file:
python -m hopstop.train_and_benchmark --csv /path/to/HI-Small_Trans.csv --max-rows 200000

# 3. Optional: on Linux / WSL 2 / s390x with snapml installed, append native snapml 1.17.2 telemetry:
python3 -m hopstop.benchmark_snapml_linux
```

### C. Launch the Live Analyst Console (`http://127.0.0.1:8080`)
```bash
python -m hopstop.server
```

---

## 7. Repository Structure

```text
hopstop-ibmz/
├── .github/workflows/ci.yml      # GitHub Actions CI running 22 pytest cases & benchmark verification
├── hopstop/
│   ├── __init__.py               # Package metadata
│   ├── data_generator.py         # Public IBM AMLworld CSV loader + 8-typology & delayed-evasion generator
│   ├── feature_engine.py         # Amortized O(1) SlidingWindow, LRU + 128KB Dual-Gen PayeeBloomFilter & HMAC
│   ├── ibmz_runtime.py           # s390x probe, Snap ML wrapper, Day-7 Isotonic Calibrator, TreeSHAP & Baselines
│   ├── policy_engine.py          # Validation threshold calibration & full 15,232-tx SHA-256 + HMAC audit chain
│   ├── train_and_benchmark.py    # Tie-invariant 3-way split benchmark, Bayes precision & alert-budget curve
│   ├── benchmark_snapml_linux.py # Unified-protocol Linux / s390x benchmark for snapml.BoostingMachineClassifier
│   ├── server.py                 # Multi-threaded REST API (/api/benchmarks, /api/score_preset, /api/verify_audit)
│   └── dashboard.html            # Interactive Analyst Console (synced with alert_budget_curve & calibrated scores)
├── tests/
│   └── test_hopstop.py           # 22 unit & parametrized tests (O(1) windows, Bloom FPR, tie-invariance, calibration, audit)
├── artifacts/
│   ├── benchmark_results.json    # Single-run 3-way split metrics, alert_budget_curve, 4 real test cases & Snap ML
│   └── hopstop_model.json        # Safe, portable JSON serialized depth-2 GBDT ensemble + Day-7 calibrator (no pickle)
├── submission/
│   ├── HopStop_PitchDeck_KabirRoy.pdf       # 6-Slide Jury Pitch Deck PDF
│   ├── HopStop_Architecture_Diagram.pdf     # 1-Page Landscape System Architecture Diagram PDF
│   └── HopStop_System_Architecture.svg      # Vector System Architecture Diagram
├── Dockerfile.s390x              # Container definition for IBM Z / LinuxONE (icr.io/ibmz/python:3.11)
├── run_hopstop.sh                # POSIX launcher script (Linux / macOS / s390x)
├── Start_HopStop_Dashboard.bat   # Windows launcher script
├── requirements.txt              # Pinned optional & s390x dependencies
├── LICENSE                       # Apache-2.0 License
└── README.md                     # Technical documentation
```
