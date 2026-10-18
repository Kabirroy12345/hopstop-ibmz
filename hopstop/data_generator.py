"""AMLworld transaction loader and synthetic multi-typology generator for HopStop.

Supports two input modes:
  1. Direct ingestion of public IBM AMLworld CSV files (`HI-Small_Trans.csv` /
     `LI-Small_Trans.csv`, Altman et al., NeurIPS 2023) via `load_amlworld_csv()`.
  2. Reproducible generation of time-ordered AMLworld-schema transactions
     (`generate_aml_dataset()`) modeling:
       - Normal retail, merchant, and benign corporate payroll batches (which create
         high fan-out patterns that trigger false positives in static velocity rules).
       - Multi-hop laundering chains across all 8 AMLSim/AMLworld typologies
         (Fan-Out, Fan-In, Gather-Scatter, Scatter-Gather, Simple-Cycle, Bipartite,
         Stack, Random-Walk), including delayed-hop (20-35 min) evasion chains.
"""
from __future__ import annotations

import csv
import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


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
    # Ground-truth evaluation fields (never exposed to feature engine or production PolicyDecision)
    is_laundering: int = 0
    chain_id: int = 0
    hop_number: int = 0
    typology: str = "Legitimate"


def _parse_timestamp_to_epoch(ts_str: str, base_dt: Optional[datetime] = None) -> Tuple[float, datetime]:
    """Parses IBM AMLworld timestamp (`YYYY/MM/DD HH:MM` or `YYYY/MM/DD HH:MM:SS`)."""
    ts_clean = ts_str.strip()
    for fmt in ("%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            dt = datetime.strptime(ts_clean, fmt)
            ref = base_dt or datetime(dt.year, dt.month, dt.day, 0, 0, 0)
            return (dt - ref).total_seconds(), ref
        except ValueError:
            continue
    return 0.0, base_dt or datetime(2026, 9, 1, 0, 0, 0)


def load_amlworld_csv(csv_path: Path, max_rows: Optional[int] = None) -> Tuple[List[TransactionRecord], Dict[str, Any]]:
    """Loads a public IBM AMLworld CSV file (`HI-Small_Trans.csv` / `LI-Small_Trans.csv`) or generated CSV.

    If explicit `Chain ID` / `Hop Number` columns are absent (as in raw Kaggle CSVs),
    connected illicit transfers within a 2-hour window are automatically grouped into
    temporal laundering chains so hop-level interdiction can be evaluated.
    """
    records: List[TransactionRecord] = []
    base_dt: Optional[datetime] = None
    accounts_seen = set()
    banks_seen = set()

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=1):
            if max_rows is not None and idx > max_rows:
                break
            ts_str = row.get("Timestamp", "2026/09/01 00:00:00")
            epoch_sec, base_dt = _parse_timestamp_to_epoch(ts_str, base_dt)
            from_bank = int(row.get("From Bank", 10) or 10)
            from_acct = str(row.get("Account", "")).strip()
            to_bank = int(row.get("To Bank", 10) or 10)
            to_acct = str(row.get("Account.1", "")).strip()
            amt_rec = float(row.get("Amount Received", 0.0) or 0.0)
            rec_curr = str(row.get("Receiving Currency", "USD")).strip()
            amt_paid = float(row.get("Amount Paid", amt_rec) or amt_rec)
            pay_curr = str(row.get("Payment Currency", rec_curr)).strip()
            fmt = str(row.get("Payment Format", "ACH")).strip()
            is_laund = int(float(row.get("Is Laundering", 0) or 0))
            chain_id = int(row.get("Chain ID", 0) or 0)
            hop_num = int(row.get("Hop Number", 0) or 0)
            typology = str(row.get("Typology", "Laundering" if is_laund else "Legitimate")).strip()

            accounts_seen.add(from_acct)
            accounts_seen.add(to_acct)
            banks_seen.add(from_bank)
            banks_seen.add(to_bank)

            records.append(
                TransactionRecord(
                    tx_id=idx,
                    timestamp=ts_str,
                    epoch_sec=epoch_sec,
                    from_bank=from_bank,
                    from_account=from_acct,
                    to_bank=to_bank,
                    to_account=to_acct,
                    amount_received=amt_rec,
                    receiving_currency=rec_curr,
                    amount_paid=amt_paid,
                    payment_currency=pay_curr,
                    payment_format=fmt,
                    is_laundering=is_laund,
                    chain_id=chain_id,
                    hop_number=hop_num,
                    typology=typology,
                )
            )

    records.sort(key=lambda r: (r.epoch_sec, r.tx_id))
    for i, r in enumerate(records, start=1):
        r.tx_id = i

    # If loading a raw Kaggle HI-Small file without Chain ID column, infer temporal chains
    if any(r.is_laundering == 1 and r.chain_id == 0 for r in records):
        next_chain_id = 1
        active_acct_chain: Dict[str, Tuple[int, int, float]] = {}
        for r in records:
            if r.is_laundering == 1 and r.chain_id == 0:
                prev = active_acct_chain.get(r.from_account)
                if prev is not None and (r.epoch_sec - prev[2]) <= 7200.0:
                    cid, prev_hop, _ = prev
                    r.chain_id = cid
                    r.hop_number = prev_hop + 1
                else:
                    cid = next_chain_id
                    next_chain_id += 1
                    r.chain_id = cid
                    r.hop_number = 1
                active_acct_chain[r.to_account] = (r.chain_id, r.hop_number, r.epoch_sec)

    n_laundering = sum(r.is_laundering for r in records)
    max_epoch = max((r.epoch_sec for r in records), default=86400.0)
    chains_set = {r.chain_id for r in records if r.chain_id > 0}
    stats = {
        "source": str(csv_path.name),
        "total_transactions": len(records),
        "laundering_transactions": n_laundering,
        "legitimate_transactions": len(records) - n_laundering,
        "laundering_ratio": round(n_laundering / max(1, len(records)), 5),
        "total_accounts": len(accounts_seen),
        "total_banks": len(banks_seen),
        "total_chains": len(chains_set),
        "days_spanned": max(1, int(math.ceil(max_epoch / 86400.0))),
    }
    return records, stats


def generate_aml_dataset(
    n_normal: int = 50000,
    n_chains: int = 160,
    n_accounts: int = 5000,
    n_banks: int = 24,
    days: int = 10,
    seed: int = 42,
) -> Tuple[List[TransactionRecord], Dict[str, Any]]:
    """Generates a time-ordered AMLworld-schema transaction stream with ground-truth chains."""
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

    # 1a. Baseline retail & commercial transactions
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

    # 1b. Benign corporate payroll / vendor batches (high fan-out to recurring employees, zero 15m pass-through)
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

    # 2. Multi-hop laundering chains across all 8 typologies
    # Every 5th chain is a "delayed-hop evasion" chain (waiting 22.5 minutes between Hop 1 and Hop 2 across all typologies)
    mule_pool = rng.sample(accounts[250:], k=min(900, len(accounts) // 4))
    for chain_idx in range(1, n_chains + 1):
        typology = TYPOLOGIES[(chain_idx - 1) % len(TYPOLOGIES)]
        is_delayed_evasion = (chain_idx % 5 == 0)
        delay_offset = 1350 if is_delayed_evasion else 0  # +22.5 min delay for evasion chains

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
                hops.append((primary_mule, m, split_amt, delay_offset + 90 + idx * 75, 2))
                hops.append(
                    (
                        m,
                        cashout_mules[idx % len(cashout_mules)],
                        round(split_amt * 0.95, 2),
                        delay_offset + 380 + idx * 95,
                        3,
                    )
                )

        elif typology == "Gather-Scatter":
            part_amt = round(base_chain_amt / 3.0, 2)
            for idx in range(3):
                hops.append((layer_mules[idx], primary_mule, part_amt, idx * 80, 1))
            out_amt = round((part_amt * 3 * 0.96) / 3.0, 2)
            for idx, cm in enumerate(cashout_mules):
                hops.append((primary_mule, cm, out_amt, delay_offset + 260 + idx * 65, 2))

        elif typology == "Scatter-Gather":
            hops.append((victim_or_placement, primary_mule, base_chain_amt, 0, 1))
            part = round(base_chain_amt * 0.97 / 3.0, 2)
            for idx in range(3):
                inter = layer_mules[idx]
                hops.append((primary_mule, inter, part, delay_offset + 110 + idx * 55, 2))
                hops.append(
                    (inter, cashout_mules[0], round(part * 0.96, 2), delay_offset + 340 + idx * 70, 3)
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
                step_delay = (delay_offset if h_i >= 1 else 0) + h_i * 140
                hops.append(
                    (cycle[h_i], cycle[h_i + 1], round(cur_amt, 2), step_delay, h_i + 1)
                )
                cur_amt *= 0.97

        elif typology == "Fan-In":
            part = round(base_chain_amt / 4.0, 2)
            for idx, m in enumerate(layer_mules):
                hops.append((m, primary_mule, part, idx * 70, 1))
            hops.append(
                (primary_mule, cashout_mules[0], round(base_chain_amt * 0.96, 2), delay_offset + 320, 2)
            )
            hops.append(
                (
                    cashout_mules[0],
                    cashout_mules[1],
                    round(base_chain_amt * 0.93, 2),
                    delay_offset + 580,
                    3,
                )
            )

        else:  # Bipartite, Stack, Random-Walk
            hops.append((victim_or_placement, primary_mule, base_chain_amt, 0, 1))
            hops.append(
                (primary_mule, layer_mules[0], round(base_chain_amt * 0.97, 2), delay_offset + 120, 2)
            )
            hops.append(
                (
                    layer_mules[0],
                    layer_mules[1],
                    round(base_chain_amt * 0.94, 2),
                    delay_offset + 270,
                    3,
                )
            )
            hops.append(
                (
                    layer_mules[1],
                    cashout_mules[0],
                    round(base_chain_amt * 0.91, 2),
                    delay_offset + 450,
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
        "source": "synthetic_amlworld_8_typologies",
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
    """Writes transactions in IBM HI-Small CSV format plus a ground-truth patterns file."""
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
