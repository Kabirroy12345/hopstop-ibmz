"""Synthetic AML transaction generator matching the IBM AMLworld (HI-Small) schema.

Follows the exact column format of the Kaggle dataset
'IBM Transactions for Anti Money Laundering (AML)' (Altman et al., NeurIPS 2023)
and models both:
  1. Normal retail, merchant, and corporate payroll transactions (which create
     benign fan-in/fan-out patterns that fool naive static velocity rules), and
  2. Explicit multi-hop laundering chains across the 8 AMLSim/AMLworld typologies
     (Fan-Out, Fan-In, Gather-Scatter, Scatter-Gather, Simple-Cycle, Bipartite,
     Stack, Random-Walk) so we can measure Chain Interruption Rate by Hop 1/2.
"""
from __future__ import annotations

import csv
import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple


PAYMENT_FORMATS = ["ACH", "Wire", "Cheque", "Credit Card", "Reinvestment", "Cash"]
CURRENCIES = ["INR", "USD", "EUR"]
TYPOLOGIES = [
    "Fan-Out",
    "Fan-In",
    "Gather-Scatter",
    "Scatter-Gather",
    "Simple-Cycle",
    "Bipartite",
    "Stack",
    "Random-Walk",
]


@dataclass
class TransactionRecord:
    tx_id: int
    timestamp: str
    epoch_sec: float
    from_bank: int
    from_account: str
    to_bank: int
    to_account: str
    amount_received: float
    receiving_currency: str
    amount_paid: float
    payment_currency: str
    payment_format: str
    is_laundering: int
    chain_id: int  # 0 for normal, >0 for laundering chain
    hop_number: int  # 0 for normal, 1..K for hop position in laundering chain
    typology: str  # 'Legitimate' or one of TYPOLOGIES


def generate_aml_dataset(
    n_normal: int = 50000,
    n_chains: int = 160,
    n_accounts: int = 5000,
    n_banks: int = 24,
    days: int = 10,
    seed: int = 42,
) -> Tuple[List[TransactionRecord], Dict[str, Any]]:
    """Generates a realistic time-ordered AML transaction dataset with ground-truth chains."""
    rng = random.Random(seed)
    base_time = datetime(2026, 9, 1, 0, 0, 0)
    total_seconds = days * 86400

    accounts = [f"ACC{100000 + i:06d}" for i in range(n_accounts)]
    account_bank = {acc: rng.randint(10, 10 + n_banks - 1) for acc in accounts}
    account_base_amt = {acc: math.exp(rng.uniform(6.2, 9.6)) for acc in accounts}
    regular_peers = {
        acc: rng.sample(accounts, k=min(10, len(accounts))) for acc in accounts
    }

    records: List[TransactionRecord] = []

    # 1a. Generate baseline retail & commercial transactions
    n_benign_bursts = 320
    n_retail = n_normal - (n_benign_bursts * 5)
    for _ in range(n_retail):
        day = rng.randint(0, days - 1)
        hour_float = rng.gauss(14.0, 4.5) % 24.0
        sec_offset = int(day * 86400 + hour_float * 3600 + rng.uniform(0, 60))
        sec_offset = max(0, min(total_seconds - 1, sec_offset))
        ts = base_time + timedelta(seconds=sec_offset)

        sender = rng.choice(accounts)
        if rng.random() < 0.78:
            receiver = rng.choice(regular_peers[sender])
        else:
            receiver = rng.choice(accounts)
        if receiver == sender:
            receiver = accounts[(accounts.index(sender) + 1) % len(accounts)]

        base_amt = account_base_amt[sender]
        amt = round(max(50.0, rng.lognormvariate(math.log(base_amt), 0.50)), 2)
        fmt = rng.choices(
            ["ACH", "Wire", "Credit Card", "Cheque", "Reinvestment"],
            weights=[0.40, 0.18, 0.27, 0.10, 0.05],
        )[0]

        records.append(
            TransactionRecord(
                tx_id=0,
                timestamp=ts.strftime("%Y/%m/%d %H:%M:%S"),
                epoch_sec=float(sec_offset),
                from_bank=account_bank[sender],
                from_account=sender,
                to_bank=account_bank[receiver],
                to_account=receiver,
                amount_received=amt,
                receiving_currency="INR",
                amount_paid=amt,
                payment_currency="INR",
                payment_format=fmt,
                is_laundering=0,
                chain_id=0,
                hop_number=0,
                typology="Legitimate",
            )
        )

    # 1b. Inject benign corporate payroll / merchant settlement bursts
    # (High fan-out or fan-in, but from established accounts to known employees/suppliers
    # or without rapid 1:1 pass-through drain — these fool static velocity rules!)
    corp_accounts = accounts[:250]
    for _ in range(n_benign_bursts):
        corp = rng.choice(corp_accounts)
        burst_start = int(rng.uniform(3600, total_seconds - 3600))
        employees = regular_peers[corp][:5]
        for idx, emp in enumerate(employees):
            sec = burst_start + idx * 45
            ts = base_time + timedelta(seconds=sec)
            amt = round(rng.uniform(18000.0, 65000.0), 2)
            records.append(
                TransactionRecord(
                    tx_id=0,
                    timestamp=ts.strftime("%Y/%m/%d %H:%M:%S"),
                    epoch_sec=float(sec),
                    from_bank=account_bank[corp],
                    from_account=corp,
                    to_bank=account_bank[emp],
                    to_account=emp,
                    amount_received=amt,
                    receiving_currency="INR",
                    amount_paid=amt,
                    payment_currency="INR",
                    payment_format=rng.choice(["ACH", "Cheque", "Reinvestment"]),
                    is_laundering=0,
                    chain_id=0,
                    hop_number=0,
                    typology="Legitimate",
                )
            )

    # 2. Inject explicit multi-hop laundering chains across all 8 typologies
    mule_pool = rng.sample(accounts[250:], k=min(900, len(accounts) // 4))
    for chain_idx in range(1, n_chains + 1):
        typology = TYPOLOGIES[(chain_idx - 1) % len(TYPOLOGIES)]
        chain_start_sec = int(rng.uniform(1800, total_seconds - 7200))
        base_chain_amt = round(rng.uniform(35000.0, 320000.0), 2)

        chain_nodes = rng.sample(mule_pool, k=10)
        victim_or_placement = chain_nodes[0]
        primary_mule = chain_nodes[1]
        layer_mules = chain_nodes[2:6]
        cashout_mules = chain_nodes[6:9]

        hops: List[Tuple[str, str, float, int, int]] = []

        if typology == "Fan-Out":
            hops.append((victim_or_placement, primary_mule, base_chain_amt, 0, 1))
            split_amt = round(base_chain_amt * 0.96 / len(layer_mules), 2)
            for idx, m in enumerate(layer_mules):
                hops.append((primary_mule, m, split_amt, 90 + idx * 75, 2))
                hops.append(
                    (
                        m,
                        cashout_mules[idx % len(cashout_mules)],
                        round(split_amt * 0.95, 2),
                        380 + idx * 95,
                        3,
                    )
                )

        elif typology == "Gather-Scatter":
            part_amt = round(base_chain_amt / 3.0, 2)
            for idx in range(3):
                hops.append((layer_mules[idx], primary_mule, part_amt, idx * 80, 1))
            out_amt = round((part_amt * 3 * 0.96) / 3.0, 2)
            for idx, cm in enumerate(cashout_mules):
                hops.append((primary_mule, cm, out_amt, 260 + idx * 65, 2))

        elif typology == "Scatter-Gather":
            hops.append((victim_or_placement, primary_mule, base_chain_amt, 0, 1))
            part = round(base_chain_amt * 0.97 / 3.0, 2)
            for idx in range(3):
                inter = layer_mules[idx]
                hops.append((primary_mule, inter, part, 110 + idx * 55, 2))
                hops.append(
                    (inter, cashout_mules[0], round(part * 0.96, 2), 340 + idx * 70, 3)
                )

        elif typology == "Simple-Cycle":
            cycle = [
                primary_mule,
                layer_mules[0],
                layer_mules[1],
                layer_mules[2],
                primary_mule,
            ]
            cur_amt = base_chain_amt
            for h_i in range(len(cycle) - 1):
                hops.append(
                    (cycle[h_i], cycle[h_i + 1], round(cur_amt, 2), h_i * 140, h_i + 1)
                )
                cur_amt *= 0.97

        elif typology == "Fan-In":
            part = round(base_chain_amt / 4.0, 2)
            for idx, m in enumerate(layer_mules):
                hops.append((m, primary_mule, part, idx * 70, 1))
            hops.append(
                (primary_mule, cashout_mules[0], round(base_chain_amt * 0.96, 2), 320, 2)
            )
            hops.append(
                (
                    cashout_mules[0],
                    cashout_mules[1],
                    round(base_chain_amt * 0.93, 2),
                    580,
                    3,
                )
            )

        else:  # Bipartite, Stack, Random-Walk
            hops.append((victim_or_placement, primary_mule, base_chain_amt, 0, 1))
            hops.append(
                (primary_mule, layer_mules[0], round(base_chain_amt * 0.97, 2), 120, 2)
            )
            hops.append(
                (
                    layer_mules[0],
                    layer_mules[1],
                    round(base_chain_amt * 0.94, 2),
                    270,
                    3,
                )
            )
            hops.append(
                (
                    layer_mules[1],
                    cashout_mules[0],
                    round(base_chain_amt * 0.91, 2),
                    450,
                    4,
                )
            )

        for src, dst, amt, delta_s, hop_num in hops:
            sec = min(total_seconds - 1, chain_start_sec + delta_s)
            ts = base_time + timedelta(seconds=sec)
            fmt = rng.choices(["ACH", "Wire"], weights=[0.60, 0.40])[0]
            records.append(
                TransactionRecord(
                    tx_id=0,
                    timestamp=ts.strftime("%Y/%m/%d %H:%M:%S"),
                    epoch_sec=float(sec),
                    from_bank=account_bank[src],
                    from_account=src,
                    to_bank=account_bank[dst],
                    to_account=dst,
                    amount_received=amt,
                    receiving_currency="INR",
                    amount_paid=amt,
                    payment_currency="INR",
                    payment_format=fmt,
                    is_laundering=1,
                    chain_id=chain_idx,
                    hop_number=hop_num,
                    typology=typology,
                )
            )

    records.sort(key=lambda r: r.epoch_sec)
    for idx, rec in enumerate(records, start=1):
        rec.tx_id = idx

    n_laundering = sum(r.is_laundering for r in records)
    stats = {
        "total_transactions": len(records),
        "laundering_transactions": n_laundering,
        "legitimate_transactions": len(records) - n_laundering,
        "laundering_ratio": round(n_laundering / len(records), 5),
        "total_accounts": n_accounts,
        "total_banks": n_banks,
        "total_chains": n_chains,
        "days_spanned": days,
    }
    return records, stats


def save_csv_and_patterns(
    records: List[TransactionRecord], csv_path: Path, patterns_path: Path
) -> None:
    """Writes transactions in IBM HI-Small CSV format plus a patterns file."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Timestamp",
                "From Bank",
                "Account",
                "To Bank",
                "Account.1",
                "Amount Received",
                "Receiving Currency",
                "Amount Paid",
                "Payment Currency",
                "Payment Format",
                "Is Laundering",
                "Chain ID",
                "Hop Number",
                "Typology",
            ]
        )
        for r in records:
            writer.writerow(
                [
                    r.timestamp,
                    r.from_bank,
                    r.from_account,
                    r.to_bank,
                    r.to_account,
                    f"{r.amount_received:.2f}",
                    r.receiving_currency,
                    f"{r.amount_paid:.2f}",
                    r.payment_currency,
                    r.payment_format,
                    r.is_laundering,
                    r.chain_id,
                    r.hop_number,
                    r.typology,
                ]
            )

    chains: Dict[int, List[TransactionRecord]] = {}
    for r in records:
        if r.chain_id > 0:
            chains.setdefault(r.chain_id, []).append(r)

    with patterns_path.open("w", encoding="utf-8") as pf:
        for cid, txs in sorted(chains.items()):
            typ = txs[0].typology.upper()
            pf.write(f"BEGIN LAUNDERING ATTEMPT - {typ} (Chain #{cid})\n")
            for t in txs:
                pf.write(
                    f"{t.timestamp},{t.from_bank},{t.from_account},"
                    f"{t.to_bank},{t.to_account},{t.amount_paid:.2f},"
                    f"{t.payment_currency},{t.payment_format},{t.is_laundering},Hop={t.hop_number}\n"
                )
            pf.write(f"END LAUNDERING ATTEMPT - {typ}\n\n")
