# HopStop — Real-Time Pre-Settlement Money-Mule Interdiction on IBM Z & LinuxONE

<div align="center">

[![Platform](https://img.shields.io/badge/Target_Platform-IBM_Z_%26_LinuxONE_(s390x)-0f62fe?style=for-the-badge&logo=ibm&logoColor=white)](https://www.ibm.com/z)
[![Measured Scorers](https://img.shields.io/badge/Verified_Backends-Portable_JSON_GBDT_%2B_Snap_ML_1.17.2_(tree__format%3Dauto)-4f46e5?style=for-the-badge)](#3-measured-benchmark-results-single-run-3-way-chronological-split)
[![Chains Stopped](https://img.shields.io/badge/Chains_Stopped_%E2%89%A4_Hop_2-84.0%25_(42%2F50_Overall)_%7C_50.0%25_Delayed_Evasion-f43f5e?style=for-the-badge)](#3-measured-benchmark-results-single-run-3-way-chronological-split)
[![Latency](https://img.shields.io/badge/GBDT_Scoring_p50-0.0073_ms_(E2E_p50%3A_0.072_ms)-10b981?style=for-the-badge)](#component-level-latency--throughput-telemetry)
[![PR-AUC](https://img.shields.io/badge/Test_PR--AUC-0.8122_(JSON_GBDT)_%7C_0.8430_(Snap_ML_1.17.2)-f59e0b?style=for-the-badge)](#3-measured-benchmark-results-single-run-3-way-chronological-split)
[![Tests](https://img.shields.io/badge/Pytest_Suite-18_%2F_18_Passing-10b981?style=for-the-badge)](tests/test_hopstop.py)
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

**HopStop** addresses these challenges by co-locating **amortized $O(1)$ streaming graph-velocity feature extraction**, **depth-2 GBDT / Snap ML scoring with on-alert exact path-dependent TreeSHAP**, and **verifiable HMAC-SHA256 hash-chained audit logging** on **IBM Z / LinuxONE (`s390x`)**, scoring outgoing transfers **before settlement** so suspicious chains are frozen at **Hop 1 or Hop 2**.

---

## 2. End-to-End Architecture & IBM Z / LinuxONE Integration

<div align="center">
  <img src="submission/HopStop_System_Architecture.svg" alt="HopStop Overall System Architecture on IBM Z & LinuxONE" width="100%" />
  <br/>
  <sub><b>Figure 1:</b> HopStop Pre-Settlement Inference & Cryptographic Audit Pipeline. <a href="submission/HopStop_Architecture_Diagram.pdf">Download Architecture PDF</a> • <a href="submission/HopStop_System_Architecture.png">View High-Res PNG</a> • <a href="submission/HopStop_System_Architecture.svg">View Vector SVG</a></sub>
</div>

### Hardware & Runtime Mapping (`hopstop/ibmz_runtime.py`)

| IBM Z / LinuxONE Capability | Implementation in HopStop | Active Backend & Operational Disclosure |
| :--- | :--- | :--- |
| **Portable JSON Tensor-Tree Engine (`portable_python_depth2_gbdt`)** | Always fits and exports a portable JSON depth-2 tree ensemble ([`artifacts/hopstop_model.json`](artifacts/hopstop_model.json), avoiding insecure `.pkl` files) with exact path-dependent TreeSHAP. | Used for the cross-platform Windows/macOS/Linux default benchmark (`Intel64 Family 6 Model 154, AMD64, Windows 11, Python 3.13.9`, where `snapml` has no Windows wheel). |
| **Snap ML C++ / Telum Runtime (`snapml.BoostingMachineClassifier(tree_format='auto')`)** | [`SnapMLAcceleratedScorer.fit()`](hopstop/ibmz_runtime.py) fits `snapml.BoostingMachineClassifier` and invokes `optimize_trees(tree_format='auto')`, while [`detect_ibmz_environment()`](hopstop/ibmz_runtime.py) probes `/proc/cpuinfo` (`facility 165`) and `libzdnn.so`. | **Verified on Linux (`Linux 6.6.87.2-microsoft-standard-WSL2 x86_64`, `Python 3.12.3`, `snapml 1.17.2`)** via [`hopstop/benchmark_snapml_linux.py`](hopstop/benchmark_snapml_linux.py) and logged under `linux_snapml_verification` in [`artifacts/benchmark_results.json`](artifacts/benchmark_results.json). On `s390x` ([`Dockerfile.s390x`](Dockerfile.s390x)), `tree_format='auto'` selects the z16/Telum accelerator format when available and compressed CPU trees otherwise. |
| **Facility 17 / 76 / 77 / 146 (`msa` — CPACF Crypto) & Key Lifecycle** | [`hash_account_id()`](hopstop/feature_engine.py) pseudonymizes account IDs via `HMAC-SHA256` into 128-bit (`ACCT_<32-hex>`) tokens; [`PolicyEngine`](hopstop/policy_engine.py) chains all decisions (`ALLOW`, `STEP_UP`, `HOLD`) with 64-hex SHA-256 + HMAC-SHA256. | **Key Lifecycle Disclosure:** If `HOPSTOP_HMAC_KEY` / `HOPSTOP_AUDIT_HMAC_KEY` are not set, HopStop generates a **per-process 256-bit CSPRNG ephemeral key** (`secrets.token_hex(32)`). This is a safe public-repo default (zero secrets in Git), but **restarting without env keys rotates account pseudonyms and invalidates prior audit HMAC signatures**. Production IBM Z deployments must inject persistent keys from an HSM / PKCS#11 EP11 store via environment variables. |
| **Facility 158 (`prot_virt` — IBM Secure Execution)** | Probed via `/proc/cpuinfo` (`facility 158`) and `/sys/firmware/uv` for confidential LinuxONE guest enclave deployment ([`Dockerfile.s390x`](Dockerfile.s390x)). | Protects in-memory sliding-window state and HMAC keys inside an Ultravisor-isolated LinuxONE container. |

---

## 3. Measured Benchmark Results (Single-Run 3-Way Chronological Split)

All metrics below come from [`hopstop/train_and_benchmark.py`](hopstop/train_and_benchmark.py) and [`hopstop/benchmark_snapml_linux.py`](hopstop/benchmark_snapml_linux.py), saved in [`artifacts/benchmark_results.json`](artifacts/benchmark_results.json). To prevent both **temporal feature leakage** and **test-set threshold calibration leakage**, the 10-day (`50,880`-transaction) stream is partitioned into three strictly disjoint chronological splits:

1. **Train Split (Days 1–6):** `30,616` transactions (`494` laundering transfers) — used to fit the depth-2 GBDT and `LogisticRegressionBaseline` (L2-regularized linear model on the exact same 12 features).
2. **Validation Split (Day 7):** `5,032` transactions (`114` laundering transfers) — used **exclusively** to calibrate `step_up_threshold` (`0.9873`) and `hold_threshold` (`0.9931`) for a target **1.0% analyst alert budget**.
3. **Unseen Test Split (Days 8–10):** `15,232` transactions (`272` laundering transfers across `50` chains: `38` fast chains with `<15m` hop turnover and `12` delayed-hop evasion chains that wait `22.5 minutes` between Hop 1 and Hop 2). Applying the frozen Day-7 thresholds yields a **realized test alert rate of `0.83%`** (`127` flagged alerts, `58` pre-settlement `HOLD`s), with **all `15,232` test decisions (`ALLOW`, `STEP_UP`, `HOLD`)** cryptographically verified from genesis in the SHA-256 + HMAC audit chain.

### Model Comparison on Unseen Test Split (Days 8–10, `15,232` Transactions)

| Metric | HopStop Portable JSON GBDT (Windows Py 3.13) | Native `snapml 1.17.2` `tree_format='auto'` (WSL 2 Linux Py 3.12) | Logistic Regression (Same 12 Features) | Static Velocity-Rules Baseline |
| :--- | :---: | :---: | :---: | :---: |
| **Test PR-AUC (95% Bootstrap CI)** | **`0.8122`** `[0.7941, 0.8708]` | **`0.8430`** | `0.8059` `[0.7688, 0.8523]` | `0.4484` `[0.4912, 0.6109]` |
| **Test ROC-AUC** | **`0.9837`** | **`0.9846`** | `0.9804` | `0.9148` |
| **Recall @ 1.0% Alert Budget** | **`53.68%`** `[51.5%, 55.2%]` | **`55.51%`** | `52.57%` `[51.1%, 55.2%]` | `35.66%` `[30.9%, 40.8%]` |
| **Precision @ 1.0% Alert Budget** | **`96.05%`** | **`99.34%`** | `94.08%` | `63.82%` |
| **Recall @ 2.0% Alert Budget** | **`77.94%`** | — | `78.68%` | `48.90%` |
| **Overall Chains Stopped $\le$ Hop 2 (All 50 Chains)** | **`84.0%` (`42 / 50`)** | — | `90.0%` (`45 / 50`) | `66.0%` (`33 / 50`) |
| **Fast Chains Stopped $\le$ Hop 2 (`<15m` wait, $n=38$)** | **`94.7%` (`36 / 38`)** | — | `94.7%` (`36 / 38`) | `84.2%` (`32 / 38`) |
| **Delayed Evasion Chains Stopped (`22.5m` wait, $n=12$)** | **`50.0%` (`6 / 12`)** *(95% Wilson CI: `[25.4%, 74.6%]`)* | — | `75.0%` (`9 / 12`) | `8.3%` (`1 / 12`) |

### Engineering Analysis: What Drives Accuracy vs. Why GBDT + Snap ML on IBM Z

1. **The 12 Causal $O(1)$ Features Drive the Accuracy Jump (`0.4484` $\to$ `~0.81–0.84`):**
   A paired bootstrap difference test (`400` resamples in [`benchmark_results.json`](artifacts/benchmark_results.json)) confirms that moving from Static Velocity Rules to the 12 causal graph-velocity features produces a massive, statistically significant gain (`gbdt_minus_rules`: $\Delta\text{PR-AUC} = +0.2797$, 95% CI `[+0.2383, +0.3267]`; $\Delta\text{Recall@1\%}$ 95% CI `[+14.34%, +23.90%]`). By contrast, on the exact same 12 features, **Depth-2 GBDT (`0.8122`) and Logistic Regression (`0.8059`) are nearly tied** (`gbdt_minus_logreg`: $\Delta\text{PR-AUC} = +0.0224$, 95% CI `[+0.0038, +0.0410]`; $\Delta\text{Recall@1\%}$ 95% CI `[-0.37%, +2.94%]`, which spans zero).
2. **Why Depth-2 GBDT + Snap ML on IBM Z:**
   Since the 12 streaming features do the heavy lifting on accuracy, the architectural case for **Depth-2 GBDT + Snap ML on IBM Z** rests on **sub-millisecond on-platform co-location (`7.3 µs` pure-Python / `8.7 µs` single-tx Snap ML / `0.192 µs/tx` in `batch=64` via Snap ML C++)**, **non-linear interaction splits** (e.g., high `fan_out_1h` is benign when `pass_through_ratio_15m == 0.0` and `counterparty_novelty == 0.0`), and **exact path-dependent TreeSHAP reason codes** for regulatory lien packets.
3. **Evasion Analysis (`84.0%` Overall vs. `50.0%` on Delayed `22.5m` Chains):**
   HopStop stops **`84.0%` (`42 / 50`)** of all unseen test laundering chains by Hop 2 (`94.7%`, `36 / 38` on fast `<15m` chains). When adversaries intentionally wait **`22.5 minutes`** between Hop 1 and Hop 2 to age out the `15m` sliding window (`delayed_evasion_22m_chains`), HopStop's interception rate drops to **`50.0%` (`6 / 12`, 95% Wilson CI `[25.4%, 74.6%]`)**, compared to **`8.3%` (`1 / 12`)** for Static Rules. While the `1h` fallback (`pass_through_ratio_1h` and `rapid_turnover_flag = 0.5`) catches half of the delayed chains, the 15-minute window remains the primary vulnerability against patient mules. Adding **longer-horizon (`6h` and `24h`) exponentially decayed pass-through ratios** is the highest-leverage next improvement.

---

### Component-Level Latency & Throughput Telemetry

#### A. Portable Python Depth-2 GBDT (`Windows 11, AMD64, Python 3.13.9`, `3,000` sequential `batch=1` evaluations)

TreeSHAP explanations (`top_reason_codes`) are computed **only on flagged `HOLD` / `STEP_UP` transfers** (`0.83%` of traffic) plus interactive analyst queries, keeping normal `ALLOW` transfers (`99.17%` of traffic) on the ultra-fast `score_one` path:

| Pipeline Stage (`batch=1` Sequential Stream) | Execution Frequency | Median (`p50`) | `p95` | `p99` | SLA Target |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **1. Amortized $O(1)$ Feature Extraction (`StreamingFeatureEngine`)** | `100%` of transfers | `0.0315 ms` (`31.5 µs`) | — | — | — |
| **2a. Depth-2 GBDT Scoring Only (`SnapMLAcceleratedScorer.score_one`)** | `100%` of transfers | **`0.0073 ms` (`7.3 µs`)** | — | — | — |
| **2b. Exact Path-Dependent TreeSHAP (`top_reason_codes`, on-alert only)** | `0.83%` (flagged alerts) | **`0.1124 ms` (`112.4 µs`)** | — | `0.2587 ms` | — |
| **3. Policy Evaluation + Full 64-Hex SHA-256 & HMAC Audit (`PolicyEngine`)** | `100%` of transfers | `0.0319 ms` (`31.9 µs`) | — | — | — |
| **Total End-to-End Decision Latency (`batch=1`, amortized across stream)** | `100%` of transfers | **`0.0717 ms` (`71.7 µs`)** | **`0.1830 ms`** | **`0.3174 ms`** | **`< 10.0 ms` (31x faster)** |

- **Sustained Single-Worker Stream Throughput (`batch=1`, Portable Python):** `8,223 TPS` (with all `15,232` decisions hash-chained & HMAC-signed)
- **Micro-Batch Scoring Throughput (`batch=64`, Portable Python):** `147,938 TPS`

#### B. Native `snapml 1.17.2` Verification (`WSL 2 Ubuntu Linux 6.6.87.2 x86_64, Python 3.12.3`)

Reproducible via `python3 -m hopstop.benchmark_snapml_linux` (`linux_snapml_verification` in [`artifacts/benchmark_results.json`](artifacts/benchmark_results.json)):

| Runtime Backend | Host OS & Python | Fit + `optimize_trees(tree_format='auto')` | `batch=1` Scoring `p50` / `p99` | `batch=64` Scoring Throughput |
| :--- | :--- | :---: | :---: | :---: |
| **`snapml.BoostingMachineClassifier(tree_format='auto')` (`1.17.2`)** | `Linux 6.6.87.2-WSL2 (x86_64)`, `Python 3.12.3` | **`0.0178 s` (`17.8 ms`)** | **`0.0087 ms` / `0.0362 ms`** | **`5,201,772 TPS` (`0.192 µs/tx`)** |
| **`portable_python_depth2_gbdt` (JSON fallback)** | `Windows 11 (AMD64)`, `Python 3.13.9` | `4.596 s` | `0.0073 ms` / — | `147,938 TPS` (`6.76 µs/tx`) |

---

## 4. Exact Path-Dependent TreeSHAP & Unseen Test-Split Case Studies

[`Depth2Tree.shap_contributions()`](hopstop/ibmz_runtime.py) implements **exact path-dependent TreeSHAP** for binary depth-2 trees using the empirical node routing probabilities $(w_L, w_{LL|L}, w_{RL|R})$ recorded during training. For every transaction $x$, the 12 feature attributions $\phi_j(x)$ satisfy the exact Shapley local-accuracy identity (verified across 50 random vectors to $10^{-9}$ in [`tests/test_hopstop.py`](tests/test_hopstop.py)):

$$\sum_{j=1}^{12} \phi_j(x) + \mathbb{E}[f(X)] = \text{raw\_margin}(x)$$

### A. Deterministic Unseen Test-Split (`Days 8–10`) Case Studies — Wins & False Negative

To avoid cherry-picking, [`hopstop/train_and_benchmark.py`](hopstop/train_and_benchmark.py) selects four real unseen test transactions (`real_test_case_examples` in [`artifacts/benchmark_results.json`](artifacts/benchmark_results.json)) using a **deterministic chronological scan of the `Days 8–10` test split**:
1. **First Interior `HOLD`** (`risk_score > hold_threshold = 0.993063`): **`tx_id=35896`** (`score = 0.9938`).
2. **First Boundary `HOLD`** (`risk_score == hold_threshold = 0.993063`): **`tx_id=35893`** (`score = 0.9931`, where `amount_zscore = 10.0` hits the clipping ceiling).
3. **First Benign Corporate Batch `ALLOW`** (`fan_out_1h >= 3`, `pass_through_15m == 0`, `rules_score >= 0.45`): **`tx_id=35895`** (`score = 0.0159`).
4. **First Missed Laundering Transfer (False Negative, `is_laundering == 1` and `action == ALLOW`)**: **`tx_id=35747`** (`score = 0.9870 < step_up_threshold = 0.9873`).

| Signal / Output | 1. Interior Mule `HOLD` (`tx_id=35896`, Hop 3 Wire) | 2. Boundary Mule `HOLD` (`tx_id=35893`, Hop 3 Wire) | 3. Benign Corporate Batch (`tx_id=35895`, Legit ACH) | 4. Missed Mule **False Negative** (`tx_id=35747`, Hop 2 ACH) |
| :--- | :--- | :--- | :--- | :--- |
| **`fan_in_1h` / `fan_out_1h`** | `1.0` / `0.0` (`fan_in_24h=3.0`) | `1.0` / `0.0` (`fan_out_24h=3.0`) | `0.0` / **`4.0`** *(triggers static rules!)* | `3.0` / `1.0` (`fan_in_24h=4.0`) |
| **`pass_through_ratio_15m`** | **`0.96`** (`260s` after credit) | **`0.96`** (`244s` after credit) | **`0.00`** *(reserve-funded payroll)* | **`0.64`** *(just below `0.65` rapid-turnover cutoff!)* |
| **`rapid_turnover_flag`** | **`1.0`** | **`1.0`** | **`0.0`** | **`0.0`** *(missed `0.65` cutoff by `0.01`)* |
| **`counterparty_novelty`** | **`1.0`** *(new recipient)* | **`1.0`** *(new recipient)* | **`0.0`** *(known recurring payee)* | **`1.0`** *(new recipient)* |
| **`amount_zscore`** | `10.00` (clipped ceiling) | `10.00` (clipped ceiling) | `0.65` | `2.26` |
| **Static Rules Baseline** | `0.63` → **FLAGGED** | `0.63` → **FLAGGED** | `0.60` → **FLAGGED (False Positive)** | `0.40` → **MISSED (`ALLOW`)** |
| **HopStop Score & Action** | **`0.9938` → `HOLD`** | **`0.9931` → `HOLD`** | **`0.0159` → `ALLOW`** | **`0.9870` → `ALLOW` (False Negative)** |
| **Why It Succeeded / Failed (Exact TreeSHAP)** | `amount_zscore (+1.860)`, `time_since_credit (+1.635)`, `format_risk (+1.503)` | `amount_zscore (+1.924)`, `time_since_credit (+1.635)`, `format_risk (+1.503)` | `counterparty_novelty (-1.552)`, `amount_zscore (-0.390)`, `time_since_credit (-0.314)` | Partial dispersal (`64%` of inflow over `ACH` with moderate `zscore=2.26`) missed `rapid_turnover_flag` (`0.65`) and fell `0.0003` short of `STEP_UP` (`0.9873`). |

### B. Hand-Specified Illustrative Sandbox Presets (`/api/score_preset` in [`hopstop/server.py`](hopstop/server.py))

In addition to querying all 4 real unseen test-split transactions via `/api/score_preset?type=real_test_mule_hold`, `real_test_mule_hold_boundary`, `real_test_payroll_allow`, and `real_test_missed_mule_false_negative`, the interactive console includes 5 hand-specified illustrative sandbox scenarios (`scenario_source = "hand_specified_sandbox_illustration"`):

| Preset Key | Illustrative Scenario | Static Rules Score | HopStop Score & Action | Top Exact TreeSHAP Log-Odds Attributions |
| :--- | :--- | :---: | :---: | :--- |
| `fan_out_mule` | Mule Hop-1 Fan-Out (`INR 185,000 Wire`) | `0.99` (FLAGGED) | **`0.9938` → `HOLD`** | `amount_zscore (+1.828)`, `time_since_last_credit_log (+1.635)`, `payment_format_risk (+1.333)` |
| `gather_scatter_mule` | Gather-Scatter Drain (`INR 240,000 ACH`) | `0.99` (FLAGGED) | **`0.9938` → `HOLD`** | `amount_zscore (+1.828)`, `time_since_last_credit_log (+1.635)`, `payment_format_risk (+1.365)` |
| `step_up_borderline` | First-Time High-Value Transfer (`INR 48,500 ACH`) | `0.63` (FLAGGED) | **`0.9930` → `STEP_UP`** | `time_since_last_credit_log (+1.635)`, `amount_zscore (+1.568)`, `payment_format_risk (+1.428)` |
| `corporate_payroll` | Corporate Payroll (`INR 42,000 ACH`, `fan_out=5`) | `0.60` (**False Positive**) | **`0.0183` → `ALLOW`** | `counterparty_novelty (-1.552)`, `time_since_last_credit_log (-0.314)`, `amount_zscore (-0.249)` |
| `retail_normal` | Normal Retail Transfer (`INR 1,850 Credit Card`) | `0.00` (ALLOW) | **`0.0034` → `ALLOW`** | `payment_format_risk (-1.474)`, `counterparty_novelty (-0.918)`, `amount_zscore (-0.251)` |

---

## 5. Amortized $O(1)$ Feature Engine, Rotating 64 KB Bloom Filter & Full Audit Chain

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
| 9 | `counterparty_novelty` | LRU + 64 KB Rotating Bloom (`O(1)`) | `0.0` if recipient is in sender's exact LRU `known_payees` (`max=2,048`) **or** dual-generation `PayeeBloomFilter`, else `1.0` |
| 10 | `amount_zscore` | Online Welford (`O(1)`) | Clipped sender Z-score $(\text{amt} - \mu) / \sigma \in [-3, 10]$ using Welford running variance |
| 11 | `out_tx_velocity_1h` | 1h (`O(1)`) | `len(out_1h.q)` — total outgoing transactions in the last 3,600s |
| 12 | `payment_format_risk` | Instant (`O(1)`) | Rail risk weight (`Wire=1.0`, `ACH=0.75`, `Cash=0.65`, `Credit Card=0.30`, `Cheque=0.20`) |

### B. Dual-Generation Rotating 64 KB Bloom Filter Capacity & False-Positive Rate (`PayeeBloomFilter`)

A naive small Bloom filter saturates over time and never ages out old payees. [`PayeeBloomFilter`](hopstop/feature_engine.py) uses a **lazy-allocated Dual-Generation Rotating 64 KB (`524,288` bits total = two `262,144`-bit / 32 KB generations, $k=4$ independent SHA-256 probes)** design:

$$\text{FPR}(n) = \left(1 - e^{-kn/m}\right)^k, \quad m = 262{,}144\text{ bits per generation},\; k = 4$$

- **Up to `2,048` recurring payees (99.9% of retail/SME accounts):** Tracked in the exact LRU `OrderedDict` with **`0.0%` FPR** and zero Bloom allocation overhead.
- **At $n = 10,000$ evicted payees (`12,048` total payees):** $\text{FPR} = (1 - e^{-40000/262144})^4 = \mathbf{0.0029\%}$ (`2.9e-5`).
- **At $n = 25,000$ evicted payees (`27,048` total payees — automatic rotation threshold):** $\text{FPR} = (1 - e^{-100000/262144})^4 = \mathbf{0.091\%}$ (`< 0.1%`).
- **Automatic Generation Aging (`rotate_generation()`):** Whenever `active_count >= 25,000` evicted payees or `30 days` (`2,592,000s`) elapse, `active_bits` demotes to `prev_bits` and a fresh zeroed `active_bits` buffer starts. Queries check `active_bits OR prev_bits`, guaranteeing that recent recurring payees are never forgotten while stale one-off payees age out without saturating the bitset.

### C. Full `15,232`-Decision SHA-256 + HMAC-SHA256 Audit Chain (`hopstop/policy_engine.py`)

When `PolicyEngine(log_allow_decisions=True)` is active (used in both `train_and_benchmark.py` and `server.py`), **every decision (`ALLOW`, `STEP_UP`, and `HOLD` — all `15,232` unseen test transfers)** is committed into the hash chain (`H_n = SHA256(H_{n-1} || canonical_payload)`, signed with `HMAC_SHA256(key, H_n)`). Consequently, **deleting even a single `ALLOW` record breaks `prev_audit_hash` continuity** on the following record and fails `PolicyEngine.verify_chain()` (verified in `test_audit_chain_single_byte_tamper_detection[delete_allow_record]`).

---

## 6. Quick Start & Automated Tests (`18 / 18` Passing)

### A. Run the Automated Pytest Suite (`18 passed`)
```bash
python -m pytest -v
```
Runs [`tests/test_hopstop.py`](tests/test_hopstop.py) (`18 passed` across 8 test functions, including `@pytest.mark.parametrize` over **all 11 canonical audit tamper & record-deletion modes**):
- `test_sliding_window_o1_exactness` — exact agreement between $O(1)$ `SlidingWindow` and naive $O(W)$ scans.
- `test_receiver_eviction_and_idle_account_ttl` — receive-only accounts evict on append and `evict_idle_accounts()` frees stale state.
- `test_large_employer_payroll_5000_payees_and_bloom_rotation` — verifies zero false novelty on 5,000 recurring employees, verifies $\text{FPR} < 0.02\%$ at 10,000 evicted payees, and verifies dual-generation aging (`rotate_generation()`).
- `test_strict_causality_no_future_leakage` — future transactions have zero effect on past features.
- `test_treeshap_local_accuracy_additivity` — exact TreeSHAP local accuracy ($\sum \phi_j + \mathbb{E}[f(X)] = \text{raw\_margin}(x)$ to $10^{-9}$) across 50 random vectors.
- `test_treeshap_signed_negative_attributions_on_payroll` — signed negative TreeSHAP log-odds on corporate payroll vs. positive on mule fan-out.
- `test_audit_hash_chain_verification` — full 64-hex SHA-256 + HMAC-SHA256 verification from genesis (`"0"*64`) across `ALLOW`, `STEP_UP`, and `HOLD`.
- `test_audit_chain_single_byte_tamper_detection[...]` (**11 parametrized cases**) — verifies that modifying any canonical field (`risk_score`, `action`, `reason_codes`, `model_version`, `hold_threshold`, `step_up_threshold`, `amount`, `from_account_hash`, `prev_audit_hash`, `hmac_signature`) or deleting an `ALLOW` record (`delete_allow_record`) fails `PolicyEngine.verify_chain()`.

### B. Run Training, Validation Calibration & Benchmarks
```bash
# Cross-platform full benchmark (writes artifacts/benchmark_results.json & artifacts/hopstop_model.json):
python -m hopstop.train_and_benchmark

# Optional: on Linux / WSL 2 / s390x with snapml installed, append native snapml 1.17.2 telemetry:
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
├── .github/workflows/ci.yml      # GitHub Actions CI running 18 pytest cases & benchmark verification
├── hopstop/
│   ├── __init__.py               # Package metadata
│   ├── data_generator.py         # Public IBM AMLworld CSV loader + 8-typology & delayed-evasion generator
│   ├── feature_engine.py         # Amortized O(1) SlidingWindow, LRU + 64KB Rotating PayeeBloomFilter & HMAC
│   ├── ibmz_runtime.py           # s390x facility probe, Snap ML wrapper, exact TreeSHAP & LogReg/Rules baselines
│   ├── policy_engine.py          # Validation threshold calibration & full 15,232-tx SHA-256 + HMAC audit chain
│   ├── train_and_benchmark.py    # 3-way split training, paired bootstrap CIs, evasion test & latency profiler
│   ├── benchmark_snapml_linux.py # Reproducible Linux / s390x benchmark for snapml.BoostingMachineClassifier
│   ├── server.py                 # Multi-threaded REST API (/api/benchmarks, /api/score_preset, /api/verify_audit)
│   └── dashboard.html            # Interactive Analyst Console (live API + standalone offline support)
├── tests/
│   └── test_hopstop.py           # 18 unit & parametrized tamper tests (O(1) windows, 64KB Bloom, TreeSHAP, audit)
├── artifacts/
│   ├── benchmark_results.json    # Single-run 3-way split metrics, paired bootstrap CIs, 4 real test cases & Snap ML
│   └── hopstop_model.json        # Safe, portable JSON serialized depth-2 GBDT ensemble (no pickle)
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
