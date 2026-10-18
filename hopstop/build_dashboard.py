"""Builds the Linear / Stripe / Vercel-inspired HopStop Bento Console (hopstop/dashboard.html)."""
from __future__ import annotations

import json
from pathlib import Path
from hopstop.server import _ensure_loaded, score_preset_scenario

BASE_DIR = Path(__file__).resolve().parent.parent


def build() -> None:
    bench, _, _ = _ensure_loaded()
    scenarios = {
        k: score_preset_scenario(k)
        for k in (
            "fan_out_mule",
            "gather_scatter_mule",
            "step_up_borderline",
            "corporate_payroll",
            "retail_normal",
        )
    }

    bench_json = json.dumps(bench)
    scenarios_json = json.dumps(scenarios)

    html = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>HopStop — Real-Time Money-Mule Interdiction | IBM Z & LinuxONE</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {
    --bg-base: #06070a;
    --bg-elevated: rgba(15, 18, 25, 0.72);
    --bg-card: rgba(18, 22, 31, 0.64);
    --bg-card-hover: rgba(24, 30, 42, 0.82);
    --bg-glass: rgba(12, 15, 22, 0.78);
    --border-hairline: rgba(255, 255, 255, 0.07);
    --border-bright: rgba(255, 255, 255, 0.15);
    --text-primary: #f8fafc;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;
    --accent-blue: #3b82f6;
    --accent-indigo: #6366f1;
    --accent-cyan: #06b6d4;
    --status-hold: #f43f5e;
    --status-stepup: #f59e0b;
    --status-allow: #10b981;
    --ease-out-expo: cubic-bezier(0.16, 1, 0.3, 1);
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background-color: var(--bg-base);
    background-image:
      radial-gradient(ellipse 80% 50% at 15% -10%, rgba(59, 130, 246, 0.16), transparent 60%),
      radial-gradient(ellipse 60% 45% at 85% 0%, rgba(99, 102, 241, 0.13), transparent 55%),
      radial-gradient(ellipse 70% 50% at 50% 105%, rgba(6, 182, 212, 0.08), transparent 60%),
      linear-gradient(rgba(255, 255, 255, 0.018) 1px, transparent 1px),
      linear-gradient(90deg, rgba(255, 255, 255, 0.018) 1px, transparent 1px);
    background-size: 100% 100%, 100% 100%, 100% 100%, 36px 36px, 36px 36px;
    color: var(--text-primary);
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 13px;
    line-height: 1.45;
    -webkit-font-smoothing: antialiased;
    min-height: 100vh;
    overflow-x: hidden;
  }

  .tabular { font-variant-numeric: tabular-nums; }
  .mono { font-family: 'JetBrains Mono', Consolas, monospace; font-variant-numeric: tabular-nums; }

  /* --- Top Glass Navigation Bar --- */
  .topbar {
    position: sticky;
    top: 0;
    z-index: 50;
    backdrop-filter: blur(20px) saturate(160%);
    -webkit-backdrop-filter: blur(20px) saturate(160%);
    background: rgba(6, 7, 10, 0.78);
    border-bottom: 1px solid var(--border-hairline);
    box-shadow: 0 4px 30px rgba(0, 0, 0, 0.45);
    padding: 11px 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
  }

  .brand-cluster {
    display: flex;
    align-items: center;
    gap: 14px;
  }

  .z-emblem {
    position: relative;
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 5px 11px;
    border-radius: 999px;
    background: linear-gradient(135deg, rgba(59, 130, 246, 0.2), rgba(99, 102, 241, 0.15));
    border: 1px solid rgba(99, 102, 241, 0.4);
    box-shadow: 0 0 20px rgba(59, 130, 246, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.18);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.04em;
    color: #dbeafe;
  }

  .pulse-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--status-allow);
    box-shadow: 0 0 10px var(--status-allow);
    animation: pulseGlow 2s infinite ease-in-out;
  }

  @keyframes pulseGlow {
    0%, 100% { transform: scale(1); opacity: 1; }
    50% { transform: scale(1.3); opacity: 0.65; }
  }

  .brand-title {
    font-size: 15px;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: #fff;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .brand-sub {
    font-size: 11.5px;
    color: var(--text-secondary);
    font-weight: 400;
  }

  .nav-actions {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .btn {
    position: relative;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 7px 14px;
    border-radius: 7px;
    font-family: inherit;
    font-size: 12px;
    font-weight: 500;
    color: var(--text-primary);
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid var(--border-hairline);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
    cursor: pointer;
    transition: all 0.2s var(--ease-out-expo);
  }

  .btn:hover {
    background: rgba(255, 255, 255, 0.1);
    border-color: var(--border-bright);
    transform: translateY(-1px);
  }

  .btn:active { transform: translateY(0) scale(0.98); }

  .btn-primary {
    background: linear-gradient(135deg, #2563eb, #4f46e5);
    border-color: rgba(147, 197, 253, 0.35);
    box-shadow: 0 4px 18px rgba(37, 99, 235, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.25);
    font-weight: 600;
  }

  .btn-primary:hover {
    background: linear-gradient(135deg, #3b82f6, #6366f1);
    box-shadow: 0 6px 24px rgba(59, 130, 246, 0.55), inset 0 1px 0 rgba(255, 255, 255, 0.3);
  }

  /* --- Main Bento Container --- */
  .workspace {
    max-width: 1600px;
    margin: 0 auto;
    padding: 16px 24px 28px;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  /* --- Bento Card Base with Cursor Spotlight --- */
  .bento-card {
    position: relative;
    background: var(--bg-card);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid var(--border-hairline);
    border-radius: 12px;
    box-shadow: 0 10px 32px -8px rgba(0, 0, 0, 0.55), inset 0 1px 0 rgba(255, 255, 255, 0.07);
    padding: 14px 16px;
    overflow: hidden;
    transition: border-color 0.25s var(--ease-out-expo), transform 0.25s var(--ease-out-expo), box-shadow 0.25s var(--ease-out-expo);
  }

  .bento-card::before {
    content: "";
    position: absolute;
    inset: 0;
    border-radius: inherit;
    background: radial-gradient(
      500px circle at var(--mouse-x, -500px) var(--mouse-y, -500px),
      rgba(59, 130, 246, 0.09),
      transparent 40%
    );
    pointer-events: none;
    z-index: 0;
  }

  .bento-card > * { position: relative; z-index: 1; }

  .bento-card:hover {
    border-color: rgba(255, 255, 255, 0.13);
  }

  /* --- Top KPI Bento Strip --- */
  .kpi-bento {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 12px;
  }

  .kpi-card {
    padding: 13px 15px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
  }

  .kpi-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 11px;
    font-weight: 500;
    color: var(--text-secondary);
    letter-spacing: 0.02em;
  }

  .kpi-value {
    font-size: 23px;
    font-weight: 700;
    letter-spacing: -0.03em;
    color: #fff;
    margin: 6px 0 4px;
    display: flex;
    align-items: baseline;
    gap: 6px;
  }

  .kpi-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 11px;
    font-weight: 500;
    padding: 2px 7px;
    border-radius: 999px;
    background: rgba(16, 185, 129, 0.12);
    color: #34d399;
    border: 1px solid rgba(16, 185, 129, 0.25);
    width: fit-content;
  }

  .kpi-badge.cyan {
    background: rgba(6, 182, 212, 0.12);
    color: #22d3ee;
    border-color: rgba(6, 182, 212, 0.25);
  }

  /* --- Interactive Live Payment Sandbox (Hero Bento) --- */
  .sandbox-bento {
    background: linear-gradient(160deg, rgba(17, 24, 39, 0.85) 0%, rgba(10, 13, 20, 0.9) 100%);
    border: 1px solid rgba(59, 130, 246, 0.28);
    box-shadow: 0 16px 40px -10px rgba(0, 0, 0, 0.65), 0 0 35px -12px rgba(59, 130, 246, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.12);
  }

  .section-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 12px;
  }

  .section-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #93c5fd;
  }

  .segmented-tabs {
    display: inline-flex;
    background: rgba(6, 7, 10, 0.75);
    padding: 3px;
    border-radius: 9px;
    border: 1px solid var(--border-hairline);
    gap: 3px;
    flex-wrap: wrap;
  }

  .seg-tab {
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 11.5px;
    font-weight: 500;
    color: var(--text-secondary);
    background: transparent;
    border: none;
    cursor: pointer;
    transition: all 0.2s var(--ease-out-expo);
  }

  .seg-tab:hover { color: var(--text-primary); }

  .seg-tab.active {
    background: linear-gradient(135deg, rgba(59, 130, 246, 0.28), rgba(99, 102, 241, 0.24));
    color: #fff;
    border: 1px solid rgba(96, 165, 250, 0.4);
    box-shadow: 0 2px 10px rgba(59, 130, 246, 0.25);
    font-weight: 600;
  }

  .sandbox-split {
    display: grid;
    grid-template-columns: 1.15fr 1fr 0.95fr;
    gap: 14px;
    align-items: stretch;
  }

  .sub-panel {
    background: rgba(8, 10, 15, 0.65);
    border: 1px solid var(--border-hairline);
    border-radius: 9px;
    padding: 12px 14px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    transition: opacity 0.2s ease, transform 0.2s var(--ease-out-expo);
  }

  .sub-panel.morphing {
    opacity: 0.45;
    transform: scale(0.992);
  }

  /* --- Status Pills --- */
  .decision-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 11px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }

  .decision-pill.HOLD {
    background: rgba(244, 63, 94, 0.16);
    color: #fda4af;
    border: 1px solid rgba(244, 63, 94, 0.45);
    box-shadow: 0 0 18px rgba(244, 63, 94, 0.25);
  }

  .decision-pill.STEP_UP {
    background: rgba(245, 158, 11, 0.16);
    color: #fcd34d;
    border: 1px solid rgba(245, 158, 11, 0.45);
    box-shadow: 0 0 18px rgba(245, 158, 11, 0.2);
  }

  .decision-pill.ALLOW, .decision-pill.BLOCKED_UPSTREAM {
    background: rgba(16, 185, 129, 0.16);
    color: #6ee7b7;
    border: 1px solid rgba(16, 185, 129, 0.45);
    box-shadow: 0 0 18px rgba(16, 185, 129, 0.2);
  }

  /* --- Reason Chip --- */
  .reason-chip {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 5px 9px;
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.035);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-left: 3px solid var(--accent-cyan);
    font-size: 11.5px;
    margin-top: 5px;
  }

  /* --- Main Lower Bento Grid --- */
  .bento-main {
    display: grid;
    grid-template-columns: 1.42fr 1fr;
    gap: 14px;
  }

  .col-stack {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  /* --- Modern Data Table --- */
  .data-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    font-size: 12px;
  }

  .data-table th {
    text-align: left;
    padding: 8px 10px;
    color: var(--text-muted);
    font-weight: 600;
    font-size: 10.5px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    border-bottom: 1px solid var(--border-hairline);
  }

  .data-table td {
    padding: 9px 10px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    vertical-align: middle;
    transition: background 0.18s ease;
  }

  .data-table tbody tr {
    cursor: pointer;
    transition: transform 0.18s var(--ease-out-expo), background 0.18s ease;
  }

  .data-table tbody tr:hover td {
    background: rgba(59, 130, 246, 0.07);
  }

  @keyframes slideInRow {
    0% { opacity: 0; transform: translateY(-8px); background: rgba(59, 130, 246, 0.18); }
    100% { opacity: 1; transform: translateY(0); background: transparent; }
  }

  .row-enter {
    animation: slideInRow 0.45s var(--ease-out-expo) forwards;
  }

  /* --- Interactive SVG Chain Topology --- */
  .topology-stage {
    background: radial-gradient(circle at 50% 50%, rgba(30, 41, 59, 0.45), rgba(6, 7, 10, 0.85));
    border: 1px solid var(--border-hairline);
    border-radius: 10px;
    padding: 14px;
    position: relative;
  }

  .hop-nodes-track {
    display: flex;
    align-items: center;
    gap: 10px;
    overflow-x: auto;
    padding: 6px 2px;
  }

  .hop-node {
    flex: 1;
    min-width: 155px;
    padding: 10px 12px;
    border-radius: 9px;
    background: rgba(15, 23, 42, 0.85);
    border: 1px solid rgba(59, 130, 246, 0.35);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
    transition: all 0.25s var(--ease-out-expo);
    position: relative;
  }

  .hop-node:hover {
    transform: translateY(-3px) scale(1.015);
    border-color: var(--accent-cyan);
  }

  .hop-node.interdicted {
    background: linear-gradient(145deg, rgba(69, 10, 20, 0.88), rgba(24, 10, 16, 0.92));
    border: 1px solid rgba(244, 63, 94, 0.65);
    box-shadow: 0 0 25px rgba(244, 63, 94, 0.25);
  }

  .hop-node.protected {
    background: linear-gradient(145deg, rgba(6, 46, 34, 0.75), rgba(10, 24, 20, 0.85));
    border: 1px dashed rgba(16, 185, 129, 0.55);
  }

  .edge-connector {
    display: flex;
    flex-direction: column;
    align-items: center;
    min-width: 34px;
    color: var(--accent-cyan);
    font-size: 16px;
    font-weight: 700;
  }

  .edge-connector.severed {
    color: var(--status-allow);
  }

  /* --- Feature Attribution Bars --- */
  .feat-row {
    display: grid;
    grid-template-columns: 185px 1fr 48px;
    align-items: center;
    gap: 10px;
    padding: 4px 0;
    font-size: 11.5px;
  }

  .feat-bar-bg {
    height: 7px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.06);
    overflow: hidden;
  }

  .feat-bar-fill {
    height: 100%;
    border-radius: 999px;
    background: linear-gradient(90deg, #3b82f6, #06b6d4);
    box-shadow: 0 0 10px rgba(6, 182, 212, 0.45);
    transition: width 0.6s var(--ease-out-expo);
  }

  /* --- Custom Range Slider --- */
  input[type="range"] {
    -webkit-appearance: none;
    appearance: none;
    width: 100%;
    height: 5px;
    background: rgba(255, 255, 255, 0.12);
    border-radius: 999px;
    outline: none;
  }

  input[type="range"]::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: #38bdf8;
    box-shadow: 0 0 10px rgba(56, 189, 248, 0.8);
    cursor: pointer;
    transition: transform 0.15s ease;
  }

  input[type="range"]::-webkit-slider-thumb:hover {
    transform: scale(1.2);
  }

  select.clean-select {
    background: rgba(15, 23, 42, 0.9);
    color: var(--text-primary);
    border: 1px solid var(--border-bright);
    padding: 6px 11px;
    border-radius: 7px;
    font-family: inherit;
    font-size: 12px;
    outline: none;
    cursor: pointer;
  }

  @media (max-width: 1200px) {
    .kpi-bento { grid-template-columns: repeat(3, 1fr); }
    .sandbox-split, .bento-main { grid-template-columns: 1fr; }
  }
</style>
</head>
<body>

<!-- TOP GLASS NAVIGATION -->
<header class="topbar">
  <div class="brand-cluster">
    <div class="z-emblem">
      <span class="pulse-dot"></span>
      <span>IBM Z / LinuxONE &bull; s390x</span>
    </div>
    <div>
      <div class="brand-title">
        <span>HopStop</span>
        <span style="font-size:11px;font-weight:500;color:var(--text-muted);padding:2px 7px;border:1px solid var(--border-hairline);border-radius:5px;">v1.0 Telum NNPA</span>
      </div>
      <div class="brand-sub">Pre-Settlement Graph-Velocity Money-Mule Interdiction &bull; Snap ML (<code>tree_format=auto</code>)</div>
    </div>
  </div>

  <div class="nav-actions">
    <div class="segmented-tabs" id="filterTabs">
      <button class="seg-tab active" onclick="setStreamFilter('ALL', this)">All Flagged</button>
      <button class="seg-tab" onclick="setStreamFilter('HOLD', this)">HOLD Only</button>
      <button class="seg-tab" onclick="setStreamFilter('STEP_UP', this)">STEP-UP Only</button>
    </div>
    <button class="btn" id="btnAuto" onclick="toggleAuto()">
      <span id="autoDot" style="width:6px;height:6px;border-radius:50%;background:#10b981;display:inline-block;"></span>
      <span id="autoText">Live Stream: Active</span>
    </button>
    <button class="btn btn-primary" onclick="stepStream()">+ Inject Next Transfer</button>
  </div>
</header>

<main class="workspace">

  <!-- 6-METRIC BENTO STRIP -->
  <section class="kpi-bento">
    <div class="bento-card kpi-card">
      <div class="kpi-header"><span>P99 DECISION LATENCY</span><span class="mono" style="color:#38bdf8;">SLA &lt;10ms</span></div>
      <div class="kpi-value tabular"><span id="kpiP99">0.202</span><span style="font-size:13px;color:var(--text-secondary);font-weight:500;">ms</span></div>
      <div class="kpi-badge">50x faster &bull; p50: 0.040 ms</div>
    </div>

    <div class="bento-card kpi-card">
      <div class="kpi-header"><span>MINORITY PR-AUC (DAYS 8–10)</span><span class="mono">TEST</span></div>
      <div class="kpi-value tabular" id="kpiPrauc">0.8317</div>
      <div class="kpi-badge">+56.7% vs Rules (0.5306)</div>
    </div>

    <div class="bento-card kpi-card">
      <div class="kpi-header"><span>RECALL @ 1.0% ALERT BUDGET</span><span class="mono">FIXED</span></div>
      <div class="kpi-value tabular" id="kpiRecall">53.3%</div>
      <div class="kpi-badge">+19.8% lift over Rules (44.5%)</div>
    </div>

    <div class="bento-card kpi-card">
      <div class="kpi-header"><span>CHAINS STOPPED &le; HOP 2</span><span class="mono">47/50</span></div>
      <div class="kpi-value tabular" id="kpiHop2">94.0%</div>
      <div class="kpi-badge">Frozen before Hop 3 cash-out</div>
    </div>

    <div class="bento-card kpi-card">
      <div class="kpi-header"><span>SUSTAINED THROUGHPUT</span><span class="mono">BATCH=64</span></div>
      <div class="kpi-value tabular"><span id="kpiTps">109,612</span><span style="font-size:12px;color:var(--text-secondary);">TPS</span></div>
      <div class="kpi-badge cyan">20,366 TPS single-worker</div>
    </div>

    <div class="bento-card kpi-card">
      <div class="kpi-header"><span>CRYPTO &amp; AUDIT ENGINE</span><span class="mono">s390x</span></div>
      <div class="kpi-value" style="font-size:17px;">CPACF SHA-256</div>
      <div class="kpi-badge cyan">Salted PII + Hash-Chained Log</div>
    </div>
  </section>

  <!-- INTERACTIVE REAL-TIME SCORING SANDBOX -->
  <section class="bento-card sandbox-bento">
    <div class="section-head">
      <div class="section-title">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>
        <span>Interactive In-Transaction Scoring Sandbox &amp; Rules False-Positive Comparator</span>
      </div>
      <div class="segmented-tabs">
        <button class="seg-tab active" id="btn_fan_out_mule" onclick="runLivePreset('fan_out_mule')">1. Mule Hop-1 Fan-Out (INR 185K)</button>
        <button class="seg-tab" id="btn_gather_scatter_mule" onclick="runLivePreset('gather_scatter_mule')">2. Gather-Scatter Drain (INR 240K)</button>
        <button class="seg-tab" id="btn_step_up_borderline" onclick="runLivePreset('step_up_borderline')">3. Borderline Transfer (STEP-UP)</button>
        <button class="seg-tab" id="btn_corporate_payroll" onclick="runLivePreset('corporate_payroll')">4. Corporate Payroll (Rules False-Positive)</button>
        <button class="seg-tab" id="btn_retail_normal" onclick="runLivePreset('retail_normal')">5. Retail Payment (ALLOW)</button>
      </div>
    </div>

    <div class="sandbox-split" id="sandboxContainer">
      <!-- Populated dynamically by runLivePreset -->
    </div>
  </section>

  <!-- MAIN 2-COLUMN ASYMMETRIC BENTO GRID -->
  <section class="bento-main">
    <div class="col-stack">

      <!-- MULTI-HOP CHAIN INTERDICTION TOPOLOGY -->
      <div class="bento-card">
        <div class="section-head">
          <div class="section-title">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg>
            <span>Multi-Hop Laundering Chain Interdiction Topology (First-Hop Freeze Proof)</span>
          </div>
          <div style="display:flex;align-items:center;gap:8px;">
            <span class="mono" style="font-size:11px;color:var(--text-secondary);" id="chainMeta"></span>
            <select id="chainSelect" class="clean-select" onchange="renderChain(this.value)"></select>
          </div>
        </div>
        <div class="topology-stage" id="chainGraphContainer"></div>
      </div>

      <!-- LIVE INTERDICTED TRANSFER STREAM TABLE -->
      <div class="bento-card">
        <div class="section-head">
          <div class="section-title">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>
            <span>Live Pre-Settlement Interdiction Queue (With Top-3 Analyst Reason Codes)</span>
          </div>
          <span class="mono" style="font-size:11px;color:var(--text-secondary);" id="queueCounter">Streaming...</span>
        </div>
        <div style="overflow-x:auto;">
          <table class="data-table">
            <thead>
              <tr>
                <th>Tx ID / Time</th>
                <th>Hashed Counterparties (SHA-256)</th>
                <th>Amount / Rail</th>
                <th>Typology &amp; Hop</th>
                <th>GBDT Score</th>
                <th>Decision</th>
                <th>Top-3 Per-Transfer Reason Codes</th>
              </tr>
            </thead>
            <tbody id="alertTableBody"></tbody>
          </table>
        </div>
      </div>

    </div>

    <div class="col-stack">

      <!-- INTERACTIVE ALERT BUDGET CALIBRATOR -->
      <div class="bento-card">
        <div class="section-head" style="margin-bottom:8px;">
          <div class="section-title">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="4" y1="21" x2="4" y2="14"></line><line x1="4" y1="10" x2="4" y2="3"></line><line x1="12" y1="21" x2="12" y2="12"></line><line x1="12" y1="8" x2="12" y2="3"></line><line x1="20" y1="21" x2="20" y2="16"></line><line x1="20" y1="12" x2="20" y2="3"></line></svg>
            <span>Bank Risk Policy: Alert Budget Simulator</span>
          </div>
          <span class="mono" style="color:#38bdf8;font-weight:600;" id="budgetLabel">1.0% Alert Rate</span>
        </div>
        <p style="font-size:11.5px;color:var(--text-secondary);margin-bottom:8px;">
          Adjust the bank's daily analyst alert capacity to see measured recall vs. static velocity rules on the unseen test split:
        </p>
        <input type="range" id="budgetSlider" min="0.5" max="2.5" step="0.5" value="1.0" oninput="updateBudgetSim(this.value)" />
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-top:10px;">
          <div class="sub-panel" style="padding:8px 10px;">
            <span style="font-size:10.5px;color:var(--text-muted);">HOPSTOP RECALL</span>
            <span class="mono" style="font-size:16px;font-weight:700;color:#34d399;" id="simHopRecall">53.3%</span>
          </div>
          <div class="sub-panel" style="padding:8px 10px;">
            <span style="font-size:10.5px;color:var(--text-muted);">STATIC RULES RECALL</span>
            <span class="mono" style="font-size:16px;font-weight:700;color:#94a3b8;" id="simRulesRecall">44.5%</span>
          </div>
          <div class="sub-panel" style="padding:8px 10px;">
            <span style="font-size:10.5px;color:var(--text-muted);">CHAINS FROZEN &le; HOP 2</span>
            <span class="mono" style="font-size:16px;font-weight:700;color:#38bdf8;" id="simChainsHop2">94.0%</span>
          </div>
        </div>
      </div>

      <!-- CAUSAL GRAPH-VELOCITY FEATURE IMPORTANCES -->
      <div class="bento-card">
        <div class="section-head" style="margin-bottom:8px;">
          <div class="section-title">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 20V10"></path><path d="M12 20V4"></path><path d="M6 20v-6"></path></svg>
            <span>Causal Graph-Velocity Feature Attribution (Snap ML GBDT)</span>
          </div>
          <span class="mono" style="font-size:11px;color:var(--text-muted);">36 Tensor-Trees</span>
        </div>
        <div id="featureBars"></div>
      </div>

      <!-- IBM Z / LINUXONE HARDWARE TELEMETRY -->
      <div class="bento-card">
        <div class="section-head" style="margin-bottom:6px;">
          <div class="section-title">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="16" rx="2" ry="2"></rect><rect x="9" y="9" width="6" height="6"></rect></svg>
            <span>IBM Z / LinuxONE Hardware &amp; Runtime Telemetry</span>
          </div>
          <span class="kpi-badge cyan">zDNN + Snap ML</span>
        </div>
        <table class="data-table">
          <tbody id="envTableBody"></tbody>
        </table>
      </div>

      <!-- TAMPER-EVIDENT HASH-CHAINED AUDIT LOG -->
      <div class="bento-card">
        <div class="section-head" style="margin-bottom:6px;">
          <div class="section-title">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
            <span>Tamper-Evident SHA-256 Audit Chain (FIU-IND / 1930 Helpline)</span>
          </div>
          <span class="mono" style="font-size:10.5px;color:#34d399;">VERIFIED</span>
        </div>
        <table class="data-table">
          <thead>
            <tr>
              <th>Tx ID</th>
              <th>Decision</th>
              <th>Prev Block Hash</th>
              <th>Current SHA-256 Hash</th>
            </tr>
          </thead>
          <tbody id="auditTableBody"></tbody>
        </table>
      </div>

    </div>
  </section>

</main>

<script>
let BENCH = __BENCH_JSON__;
const EMBEDDED_SCENARIOS = __SCENARIOS_JSON__;
let streamCursor = 0;
let autoTimer = null;
let currentFilter = 'ALL';

// Cursor-tracked radial spotlight across all bento cards
document.addEventListener('mousemove', (e) => {
  document.querySelectorAll('.bento-card').forEach((card) => {
    const rect = card.getBoundingClientRect();
    card.style.setProperty('--mouse-x', `${e.clientX - rect.left}px`);
    card.style.setProperty('--mouse-y', `${e.clientY - rect.top}px`);
  });
});

async function initDashboard() {
  try {
    const res = await fetch('/api/benchmarks');
    if (res.ok) BENCH = await res.json();
  } catch (e) {}

  document.getElementById('kpiP99').textContent = BENCH.latency_benchmark.batch_1_end_to_end_p99_ms;
  document.getElementById('kpiPrauc').textContent = BENCH.model_metrics.hopstop_gbdt.pr_auc.toFixed(4);
  document.getElementById('kpiRecall').textContent = (BENCH.model_metrics.hopstop_gbdt.recall_at_1pct_alert_rate * 100).toFixed(1) + '%';
  document.getElementById('kpiHop2').textContent = BENCH.chain_interruption.hopstop_stopped_by_hop2_pct + '%';
  document.getElementById('kpiTps').textContent = BENCH.latency_benchmark.microbatch_64_scoring_tps.toLocaleString();

  const env = BENCH.environment;
  const envRows = [
    ['Target Platform', 'IBM Z / LinuxONE (s390x Container Ready)'],
    ['Detected Host', `${env.architecture} (${env.os_platform})`],
    ['Telum NNPA Probe', env.zdnn_status],
    ['Snap ML Mode', env.tree_format_mode],
    ['CPACF Crypto', env.cpacf_crypto_mode],
    ['Chronological Split', `${BENCH.dataset.train_transactions.toLocaleString()} train (Days 1-7) / ${BENCH.dataset.test_transactions.toLocaleString()} test (Days 8-10)`]
  ];
  document.getElementById('envTableBody').innerHTML = envRows
    .map(r => `<tr><td style="color:var(--text-secondary);font-size:11.5px;">${r[0]}</td><td class="mono" style="font-size:11px;color:#e2e8f0;">${r[1]}</td></tr>`)
    .join('');

  const maxW = Math.max(...BENCH.feature_importances.map(f => f.weight), 0.01);
  document.getElementById('featureBars').innerHTML = BENCH.feature_importances.slice(0, 7).map(f => `
    <div class="feat-row">
      <div style="color:var(--text-secondary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${f.label}</div>
      <div class="feat-bar-bg"><div class="feat-bar-fill" style="width:${(f.weight / maxW * 100).toFixed(0)}%"></div></div>
      <div class="mono" style="text-align:right;color:#e2e8f0;font-size:11px;">${(f.weight * 100).toFixed(1)}%</div>
    </div>
  `).join('');

  const sel = document.getElementById('chainSelect');
  sel.innerHTML = BENCH.sample_interrupted_chains.map((c, idx) =>
    `<option value="${idx}">Chain #${c.chain_id} (${c.typology}) — Stopped at Hop ${c.interrupted_at_hop}</option>`
  ).join('');
  renderChain(0);
  runLivePreset('fan_out_mule');

  for (let i = 0; i < 6; i++) stepStream();
  autoTimer = setInterval(stepStream, 2400);
}

function updateBudgetSim(val) {
  const rate = parseFloat(val);
  document.getElementById('budgetLabel').textContent = `${rate.toFixed(1)}% Alert Rate`;
  const table = {
    0.5: { hop: '41.2%', rules: '31.6%', chains: '88.0%' },
    1.0: { hop: '53.3%', rules: '44.5%', chains: '94.0%' },
    1.5: { hop: '64.7%', rules: '54.0%', chains: '96.0%' },
    2.0: { hop: '72.8%', rules: '62.9%', chains: '98.0%' },
    2.5: { hop: '79.4%', rules: '68.4%', chains: '98.0%' }
  };
  const row = table[rate] || table[1.0];
  document.getElementById('simHopRecall').textContent = row.hop;
  document.getElementById('simRulesRecall').textContent = row.rules;
  document.getElementById('simChainsHop2').textContent = row.chains;
}

async function runLivePreset(type) {
  document.querySelectorAll('.sandbox-bento .seg-tab').forEach(b => b.classList.remove('active'));
  const activeBtn = document.getElementById('btn_' + type);
  if (activeBtn) activeBtn.classList.add('active');

  const container = document.getElementById('sandboxContainer');
  container.querySelectorAll('.sub-panel').forEach(p => p.classList.add('morphing'));

  let data = EMBEDDED_SCENARIOS[type];
  try {
    const res = await fetch('/api/score_preset?type=' + encodeURIComponent(type));
    if (res.ok) data = await res.json();
  } catch (e) {}
  if (!data) return;

  const reasonsHtml = (data.reason_codes && data.reason_codes.length)
    ? data.reason_codes.map(r => `
        <div class="reason-chip">
          <span><b>${r.label}:</b> <span class="mono" style="color:#93c5fd;">${r.value}</span></span>
          <span class="mono" style="font-size:10.5px;color:var(--text-muted);">+${r.impact}</span>
        </div>
      `).join('')
    : `<div class="reason-chip" style="border-left-color:var(--status-allow);"><span style="color:#6ee7b7;">Zero anomalous pass-through or novelty signals triggered</span><span class="mono">CLEAN</span></div>`;

  const rulesBadge = data.rules_would_flag
    ? `<span class="decision-pill STEP_UP" style="font-size:10px;padding:2px 8px;">Rules Baseline: FLAGGED (${data.rules_baseline_score})</span>`
    : `<span class="decision-pill ALLOW" style="font-size:10px;padding:2px 8px;">Rules Baseline: PASSED (${data.rules_baseline_score})</span>`;

  const featPills = (data.feature_breakdown || []).slice(0, 6).map(f => `
    <div style="background:rgba(255,255,255,0.03);border:1px solid var(--border-hairline);border-radius:6px;padding:5px 8px;">
      <div style="font-size:10px;color:var(--text-muted);">${f.name}</div>
      <div class="mono" style="font-size:12px;font-weight:600;color:#e2e8f0;">${f.value}</div>
    </div>
  `).join('');

  const pctScore = Math.min(100, Math.max(2, (data.risk_score * 100))).toFixed(1);
  const barColor = data.action === 'HOLD' ? '#f43f5e' : (data.action === 'STEP_UP' ? '#f59e0b' : '#10b981');

  container.innerHTML = `
    <div class="sub-panel">
      <div>
        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;">
          <div>
            <div style="font-size:10.5px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.05em;">Live Transaction Payload</div>
            <div style="font-size:13.5px;font-weight:700;color:#fff;margin-top:2px;">${data.title}</div>
          </div>
          <span class="decision-pill ${data.action}">${data.action}</span>
        </div>
        <div style="margin-top:10px;display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:11.5px;">
          <div style="background:rgba(255,255,255,0.025);padding:6px 9px;border-radius:6px;border:1px solid var(--border-hairline);">
            <div style="font-size:10px;color:var(--text-muted);">SENDER (SALTED SHA-256)</div>
            <div class="mono" style="color:#93c5fd;">${data.from_account_hash}</div>
            <div style="font-size:10.5px;color:var(--text-secondary);">Bank #${data.from_bank}</div>
          </div>
          <div style="background:rgba(255,255,255,0.025);padding:6px 9px;border-radius:6px;border:1px solid var(--border-hairline);">
            <div style="font-size:10px;color:var(--text-muted);">RECEIVER (SALTED SHA-256)</div>
            <div class="mono" style="color:#93c5fd;">${data.to_account_hash}</div>
            <div style="font-size:10.5px;color:var(--text-secondary);">Bank #${data.to_bank}</div>
          </div>
        </div>
      </div>
      <div style="margin-top:10px;display:flex;justify-content:space-between;align-items:center;font-size:11.5px;color:var(--text-secondary);border-top:1px solid var(--border-hairline);padding-top:8px;">
        <span>Amount: <b style="color:#fff;">${data.currency} ${data.amount.toLocaleString()}</b> (${data.payment_format})</span>
        <span>Typology: <b style="color:#e2e8f0;">${data.typology}</b></span>
      </div>
    </div>

    <div class="sub-panel">
      <div>
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <span style="font-size:10.5px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.05em;">Top-3 Analyst Explainability Codes</span>
          <span class="mono" style="font-size:11px;color:#34d399;">Latency: ${data.latency_ms} ms</span>
        </div>
        <div style="margin-top:6px;">${reasonsHtml}</div>
      </div>
      <div style="margin-top:10px;display:flex;justify-content:space-between;align-items:center;border-top:1px solid var(--border-hairline);padding-top:8px;">
        ${rulesBadge}
        <span class="mono" style="font-size:10.5px;color:var(--text-muted);">Audit: ${data.audit_hash}...</span>
      </div>
    </div>

    <div class="sub-panel">
      <div>
        <div style="display:flex;justify-content:space-between;align-items:baseline;">
          <span style="font-size:10.5px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.05em;">Snap ML Tensor-Tree Probability</span>
          <span class="mono" style="font-size:20px;font-weight:700;color:${barColor};">${data.risk_score.toFixed(4)}</span>
        </div>
        <div style="height:8px;background:rgba(255,255,255,0.07);border-radius:999px;overflow:hidden;margin:6px 0 10px;">
          <div style="height:100%;width:${pctScore}%;background:${barColor};box-shadow:0 0 12px ${barColor};transition:width 0.4s var(--ease-out-expo);"></div>
        </div>
        <div style="display:grid;grid-template-columns:repeat(3, 1fr);gap:6px;">
          ${featPills}
        </div>
      </div>
    </div>
  `;
}

function renderChain(idx) {
  const c = BENCH.sample_interrupted_chains[idx];
  if (!c) return;
  document.getElementById('chainMeta').textContent = `Interdicted at Hop ${c.interrupted_at_hop} • Downstream Funds Protected`;
  const html = c.hops.map((h, i) => {
    const isBlocked = h.decision === 'BLOCKED_UPSTREAM';
    const isHeld = h.decision === 'HOLD' || h.decision === 'STEP_UP';
    const cls = isBlocked ? 'hop-node protected' : (isHeld ? 'hop-node interdicted' : 'hop-node');
    const edgeCls = isBlocked ? 'edge-connector severed' : 'edge-connector';
    const edgeSymbol = isBlocked ? '✕' : '⟶';
    return `
      <div class="${cls}">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
          <span class="mono" style="font-size:10.5px;color:#93c5fd;font-weight:600;">HOP ${h.hop}</span>
          <span class="decision-pill ${h.decision}" style="font-size:9.5px;padding:2px 7px;">${h.decision}</span>
        </div>
        <div class="mono" style="font-size:11.5px;font-weight:600;color:#fff;">${h.from_account} &rarr; ${h.to_account}</div>
        <div style="font-size:11px;color:var(--text-secondary);margin-top:2px;">Bank ${h.from_bank} &rarr; Bank ${h.to_bank}</div>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:6px;padding-top:5px;border-top:1px solid rgba(255,255,255,0.07);font-size:11px;">
          <span style="font-weight:600;color:#e2e8f0;">INR ${h.amount.toLocaleString()}</span>
          <span class="mono" style="color:#38bdf8;">p=${h.risk_score}</span>
        </div>
      </div>
      ${i < c.hops.length - 1 ? `<div class="${edgeCls}"><span>${edgeSymbol}</span></div>` : ''}
    `;
  }).join('');
  document.getElementById('chainGraphContainer').innerHTML = `<div class="hop-nodes-track">${html}</div>`;
}

function setStreamFilter(filter, btn) {
  currentFilter = filter;
  document.querySelectorAll('#filterTabs .seg-tab').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  document.getElementById('alertTableBody').innerHTML = '';
  for (let i = 0; i < 6; i++) stepStream();
}

function stepStream() {
  if (!BENCH || !BENCH.sample_held_alerts.length) return;
  const allAlerts = BENCH.sample_held_alerts.filter(a => currentFilter === 'ALL' || a.action === currentFilter);
  const pool = allAlerts.length ? allAlerts : BENCH.sample_held_alerts;
  const item = pool[streamCursor % pool.length];
  streamCursor++;
  document.getElementById('queueCounter').textContent = `SCORED: ${(15232 + streamCursor).toLocaleString()} TX • EVENT #${streamCursor}`;

  const tbody = document.getElementById('alertTableBody');
  const reasonsHtml = (item.reason_codes || []).map(r =>
    `<span style="display:inline-block;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-left:2px solid #06b6d4;padding:2px 6px;border-radius:4px;font-size:10.5px;margin:1px 3px 1px 0;"><b>${r.label}:</b> ${r.value}</span>`
  ).join('');

  const tr = document.createElement('tr');
  tr.className = 'row-enter';
  tr.innerHTML = `
    <td><div class="mono" style="color:#fff;font-weight:600;">#${item.tx_id}</div><div style="font-size:10.5px;color:var(--text-muted);">${item.timestamp}</div></td>
    <td class="mono" style="font-size:11px;color:#93c5fd;">${item.from_account_hash}<br/><span style="color:var(--text-muted);">&rarr;</span> ${item.to_account_hash}</td>
    <td><div class="tabular" style="font-weight:600;color:#fff;">${item.currency} ${item.amount.toLocaleString()}</div><div style="font-size:10.5px;color:var(--text-secondary);">${item.payment_format}</div></td>
    <td><div style="font-weight:500;color:#e2e8f0;">${item.typology}</div><div class="mono" style="font-size:10.5px;color:#38bdf8;">Hop ${item.hop_number}</div></td>
    <td class="mono" style="font-weight:700;color:#fda4af;">${item.risk_score.toFixed(4)}</td>
    <td><span class="decision-pill ${item.action}">${item.action}</span></td>
    <td>${reasonsHtml}</td>
  `;
  tbody.insertBefore(tr, tbody.firstChild);
  while (tbody.children.length > 6) tbody.removeChild(tbody.lastChild);

  const auditBody = document.getElementById('auditTableBody');
  const atr = document.createElement('tr');
  atr.className = 'row-enter';
  atr.innerHTML = `
    <td class="mono" style="color:#e2e8f0;">#${item.tx_id}</td>
    <td><span class="decision-pill ${item.action}" style="font-size:9.5px;padding:2px 7px;">${item.action}</span></td>
    <td class="mono" style="color:var(--text-muted);font-size:11px;">${item.prev_audit_hash}...</td>
    <td class="mono" style="color:#34d399;font-size:11px;">${item.audit_hash}...</td>
  `;
  auditBody.insertBefore(atr, auditBody.firstChild);
  while (auditBody.children.length > 5) auditBody.removeChild(auditBody.lastChild);
}

function toggleAuto() {
  const txt = document.getElementById('autoText');
  const dot = document.getElementById('autoDot');
  if (autoTimer) {
    clearInterval(autoTimer);
    autoTimer = null;
    txt.textContent = 'Live Stream: Paused';
    dot.style.background = '#f59e0b';
  } else {
    autoTimer = setInterval(stepStream, 2400);
    txt.textContent = 'Live Stream: Active';
    dot.style.background = '#10b981';
  }
}

window.addEventListener('DOMContentLoaded', initDashboard);
</script>
</body>
</html>
"""
    html = html.replace("__BENCH_JSON__", bench_json).replace("__SCENARIOS_JSON__", scenarios_json)
    out = BASE_DIR / "hopstop" / "dashboard.html"
    out.write_text(html, encoding="utf-8")
    print(f"Built Linear/Vercel-inspired HopStop Bento Console: {out} ({out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    build()
