"""Verifies character counts for the Final Project Submission fields and packages the ZIP."""
from __future__ import annotations

import zipfile
from pathlib import Path

FIELDS = {
    "1_Challenge_Dropdown": "Real-Time AI for Critical Decisions",
    "2_What_is_the_Problem_you_are_trying_to_solve": (
        "When a cyber-fraud scam succeeds, stolen money is routed through money-mule "
        "accounts across multiple banks within minutes over instant payment rails "
        "(IMPS/UPI/ACH/Wire). Traditional bank AML transaction monitoring runs in hourly "
        "or overnight batches. By the time a batch alert fires—or a victim calls the 1930 "
        "Cybercrime Helpline and police issue a freeze request—the funds have already "
        "jumped 3 to 5 hops across dozens of accounts and been cashed out. Static velocity "
        "rules also suffer from high false-positive rates on legitimate corporate payroll "
        "fan-outs and merchant settlements, overwhelming fraud analysts while missing rapid "
        "multi-hop pass-through mule layering."
    ),
    "3_How_are_you_planning_to_solve_the_problem": (
        "HopStop embeds real-time money-mule graph scoring into the pre-settlement payment path:\n"
        "1. Stream & Causal O(1) Feature Engine (hopstop/feature_engine.py): Replays time-ordered "
        "IBM AMLworld transfers, hashes account IDs with salted SHA-256, and updates per-account "
        "15m/1h/24h deques (past events only) to extract 12 features: fan-in/out, 15m/1h "
        "pass-through ratio, time-since-last-credit, rapid drain flag, counterparty novelty, Welford "
        "amount Z-score, and rail risk.\n"
        "2. Snap ML / Tensor-Tree GBDT Scorer (hopstop/ibmz_runtime.py): Scores each transfer in "
        "0.04 ms (p50) / 0.20 ms (p99) using a 36-tree gradient-boosted ensemble (Snap ML "
        "tree_format=auto / compiled tensor-trees).\n"
        "3. Policy & Carbon Console (hopstop/policy_engine.py, server.py): Calibrates ALLOW / "
        "STEP_UP / HOLD thresholds to a 1% alert budget, outputs Top-3 reason codes and SHA-256 "
        "hash-chained audit logs, stopping 94.0% of test laundering chains by Hop 2 (PR-AUC 0.8317 "
        "vs 0.5306 rules baseline)."
    ),
    "4_How_does_your_solution_leverage_IBM_Z_LinuxONE": (
        "1. Co-Located In-Transaction Scoring: Core banking and payment switches run on IBM Z. "
        "Running HopStop on the same IBM Z / LinuxONE (s390x) platform eliminates the 5-30 ms "
        "network/TLS hop to external cloud AI servers and keeps sensitive transaction graphs on-platform.\n"
        "2. IBM Telum / Telum II NNPA & Snap ML: hopstop/ibmz_runtime.py probes s390x Facility 165 "
        "and libzdnn.so via zdnn_is_nnpa_installed() and configures IBM Snap ML with tree_format='auto' "
        "(targeting the Telum Integrated Accelerator for AI via tensor-trees, with automatic fallback "
        "to branch-minimized CPU tensor-trees when a guest VM does not expose physical NNPA), achieving "
        "0.202 ms p99 latency and 109,612 TPS (micro-batch=64).\n"
        "3. Pervasive Encryption & Secure Execution Readiness: Salted SHA-256 account hashing and "
        "hash-chained audit logs leverage CPACF hardware crypto on s390x, packaged in Dockerfile.s390x "
        "for LinuxONE and IBM Secure Execution (Facility 158) confidential guests."
    ),
    "5_What_value_does_your_solution_deliver": (
        "1. Fraud Operations Analysts: Receive a live sub-millisecond queue of HELD and STEP_UP "
        "transfers with Top-3 human-readable reason codes instead of next-day batch alerts.\n"
        "2. Cybercrime Investigators (1930 Helpline) & Victims: Because HopStop freezes 94.0% of "
        "test laundering chains by Hop 1 or Hop 2, stolen victim funds remain in the initial mule "
        "account ready to be frozen and recovered before Hop 3+ cash-out.\n"
        "3. Bank Risk Heads: Enforce a strict analyst alert budget (e.g., 1.0% alert rate) while "
        "achieving 53.3% laundering recall (+19.8% relative lift over static velocity rules at 44.5%) "
        "and 0.8317 PR-AUC (+56.7% lift over rules at 0.5306).\n"
        "4. AML Compliance Officers (FIU-IND): Get tamper-evident, time-stamped SHA-256 hash-chained "
        "audit records and feature attributions for Suspicious Transaction Reports.\n"
        "5. Retail Customers: Protected from scam losses while borderline transfers trigger frictionless "
        "STEP_UP verification instead of wrongful blanket account freezes."
    ),
    "6_Link_to_all_open_source_resources_used": (
        "1. Dataset: IBM Transactions for Anti Money Laundering (AML) (Altman et al., NeurIPS 2023, "
        "CDLA-Sharing-1.0) - https://www.kaggle.com/datasets/ealtman2019/ibm-transactions-for-anti-money-laundering-aml\n"
        "2. Paper & Generator Reference: IBM AMLworld / Multi-GNN - https://arxiv.org/abs/2306.16424 "
        "and https://github.com/IBM/Multi-GNN\n"
        "3. Optional Benchmark Reference: IBM TabFormer Synthetic Credit Card Dataset - "
        "https://github.com/IBM/TabFormer\n"
        "4. AI Toolkit for IBM Z and LinuxONE & Snap ML - https://github.com/IBM/ai-toolkit-for-ibm-z-and-linuxone "
        "and https://snapml.readthedocs.io/\n"
        "5. IBM Z Deep Neural Network Library (zDNN / NNPA) - https://github.com/IBM/zDNN\n"
        "6. Runtime: Python 3 Standard Library (http.server, ctypes, hashlib, collections, pickle) - "
        "https://docs.python.org/3/"
    ),
}


def main() -> None:
    base_dir = Path(__file__).resolve().parent.parent
    sub_dir = base_dir / "submission"
    out_txt = sub_dir / "final_project_submission_fields.txt"

    lines = []
    print("=== Final Project Submission Field Character Counts ===")
    for key, val in FIELDS.items():
        c = len(val)
        w = len(val.split())
        status = "OK (<= 1024)" if c <= 1024 else "OVER LIMIT!"
        print(f"{key:48s}: {c:4d} chars | {w:3d} words -> {status}")
        lines.append(f"=== {key} [{c} chars / {w} words] ===\n{val}\n")

    out_txt.write_text("\n".join(lines), encoding="utf-8")

    # Package clean project ZIP for upload/sharing
    zip_path = sub_dir / "HopStop_Project_KabirRoy.zip"
    include_paths = [
        base_dir / "README.md",
        base_dir / "LICENSE",
        base_dir / "requirements.txt",
        base_dir / "Dockerfile.s390x",
        base_dir / "run_hopstop.sh",
        base_dir / "Start_HopStop_Dashboard.bat",
        base_dir / ".github" / "workflows" / "ci.yml",
        base_dir / "hopstop" / "__init__.py",
        base_dir / "hopstop" / "data_generator.py",
        base_dir / "hopstop" / "feature_engine.py",
        base_dir / "hopstop" / "ibmz_runtime.py",
        base_dir / "hopstop" / "policy_engine.py",
        base_dir / "hopstop" / "train_and_benchmark.py",
        base_dir / "hopstop" / "server.py",
        base_dir / "hopstop" / "dashboard.html",
        base_dir / "tests" / "test_hopstop.py",
        base_dir / "artifacts" / "benchmark_results.json",
        base_dir / "artifacts" / "hopstop_model.json",
        sub_dir / "HopStop_PitchDeck_KabirRoy.pdf",
        sub_dir / "HopStop_Outline_KabirRoy.pdf",
        sub_dir / "HopStop_Architecture_Diagram.pdf",
        sub_dir / "HopStop_System_Architecture.svg",
    ]
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in include_paths:
            if p.exists():
                zf.write(p, p.relative_to(base_dir))
    print(f"Created project archive: {zip_path} ({zip_path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
