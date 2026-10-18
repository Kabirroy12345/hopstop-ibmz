"""Character/word counter for the IBM Z Datathon abstract fields.

Holds the draft (v1) and final (v2) text for each form field, prints counts,
and writes the final fields to final_fields.txt for copy-paste.
"""
from pathlib import Path

LIMITS = {
    "problem": ("chars", 200),
    "solution": ("words", 199),  # "under 200 words"
    "audience": ("chars", 1024),
    "datasets": ("chars", 1024),
    "comments": ("chars", 1024),
}

V1 = {
    "problem": (
        "Banks detect money-mule accounts too late, so cyber-fraud victims lose "
        "their savings as stolen money moves through many accounts before anyone acts."
    ),
    "solution": (
        "HopStop is a real-time AI system that detects money-mule transactions on IBM Z. "
        "It streams transactions, builds graph features for each account, and uses a "
        "gradient-boosted model running on the Telum AI accelerator to score each payment "
        "in under 1 ms. Suspicious payments are blocked instantly. Because the data never "
        "leaves IBM Z and is protected by pervasive encryption and confidential computing, "
        "the solution is secure by design. We expect to reach over 95% recall on laundering "
        "transactions and cut fraud losses for banks significantly, while keeping false "
        "positives low. The system includes a dashboard for analysts and can scale to "
        "billions of transactions per day on IBM Z."
    ),
}

V2 = {
    "problem": (
        "Mule accounts pass cyber-fraud money onward within minutes, but bank AML checks "
        "often run hours later. Victims lose savings, and every extra hop makes recovery harder."
    ),
    "solution": (
        "HopStop scores every outgoing transfer for money-mule behaviour before it settles, "
        "so a bank can pause the payment while stolen money is still one hop from the victim.\n\n"
        "How it works: IBM's synthetic AML transactions are replayed in time order as a "
        "payment stream. A stateful feature engine updates each account's "
        "rolling fan-in and fan-out, pass-through ratio (money out vs. money in within minutes), "
        "time since last credit and counterparty novelty, using only past events. A "
        "gradient-boosted tree model, loaded into IBM Snap ML, scores the transfer. On "
        "z16/z17-class LinuxONE, Snap ML can run tree inference on the Telum on-chip "
        "Integrated Accelerator for AI; we will benchmark it against CPU-only. A policy layer "
        "returns allow, step-up verification or hold, with its top three reason codes.\n\n"
        "Why IBM Z: where core payments already run on Z, scoring on the same platform keeps "
        "transaction data off external AI servers and removes a network hop from the decision "
        "path.\n\n"
        "Targets (measured, not assumed): p99 decision latency under 10 ms; higher laundering "
        "recall than a velocity-rules baseline at the same 1% alert rate; share of laundering "
        "chains stopped by the second hop."
    ),
    "audience": (
        "1. Fraud operations analysts at banks and payment providers: get a live queue of held "
        "or step-up payments with reason codes, instead of next-day alerts.\n"
        "2. AML compliance officers: get explainable, time-stamped evidence to support "
        "suspicious transaction reports to FIU-IND.\n"
        "3. Core banking and payments platform teams on IBM Z or LinuxONE: get a scoring "
        "service whose latency is measured on the platform against the payment time budget.\n"
        "4. Police cyber cells and cybercrime investigators: when a victim calls the 1930 "
        "helpline, money held at the first hop is still there to freeze.\n"
        "5. Bank risk heads: set the alert rate to match analyst capacity and see the recall "
        "trade-off before go-live.\n"
        "6. Retail customers, especially new digital-payment users: fewer completed scams, and "
        "step-up checks instead of blanket account freezes."
    ),
    "datasets": (
        "1. IBM Transactions for Anti Money Laundering (AML), Kaggle (ealtman2019), "
        "CDLA-Sharing-1.0, from IBM's AMLworld generator (Altman et al., NeurIPS 2023). "
        "Main set HI-Small: ~5M transactions, ~515K accounts, 10 days, ~1 laundering "
        "transaction per 981. Fields: timestamp, from/to bank and account, amounts, currencies, "
        "payment format; label Is Laundering. A patterns file groups part of the laundering "
        "into typologies (fan-in, fan-out, cycle, scatter-gather and more), used to measure how "
        "early chains are cut. LI-Small tests a lower illicit ratio.\n"
        "2. Optional: IBM TabFormer synthetic card data (~24M transactions, 2,000 users, GitHub "
        "IBM/TabFormer) to check generalisation.\n"
        "Imbalance: time-based split, class weighting, threshold set by alert budget; report "
        "PR-AUC and recall at 1% alerts, not accuracy.\n"
        "Privacy: fully synthetic, no real PII; account IDs hashed; data and model stay "
        "on the LinuxONE instance.\n"
        "IBM Z fit: replayed in timestamp order as a payment stream, mirroring in-transaction "
        "scoring."
    ),
    "comments": (
        "This builds on my fraud-pattern analysis work with the MP Police Cybercrime & Data "
        "Analysis Division; I want to stop mule chains at the first hop instead of tracing "
        "them afterwards. Question: will the event LinuxONE instances expose the Integrated "
        "Accelerator for AI (NNPA), so we can report accelerator vs CPU-only latency?"
    ),
}


def count(text: str) -> tuple[int, int]:
    return len(text), len(text.split())


def report(name: str, fields: dict) -> None:
    print(f"===== {name} =====")
    for key, text in fields.items():
        chars, words = count(text)
        unit, limit = LIMITS[key]
        value = chars if unit == "chars" else words
        status = "OK" if value <= limit else "OVER"
        print(f"{key:9s} chars={chars:5d} words={words:4d}  limit={limit} {unit} -> {status}")


if __name__ == "__main__":
    report("V1 draft", V1)
    report("V2 final", V2)
    out = Path(__file__).with_name("final_fields.txt")
    titles = {
        "problem": "2. PROBLEM STATEMENT",
        "solution": "3. PROPOSED SOLUTION",
        "audience": "4. AUDIENCE",
        "datasets": "5. DATASETS",
        "comments": "6. OPTIONAL COMMENTS",
    }
    parts = ["1. CHALLENGE: Real-Time AI for Critical Decisions\n"]
    for key, text in V2.items():
        chars, words = count(text)
        parts.append(f"{titles[key]}  [{chars} chars / {words} words]\n{text}\n")
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"wrote {out}")
