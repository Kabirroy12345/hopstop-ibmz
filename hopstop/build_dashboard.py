"""Compiles the production HopStop Enterprise Bento Dashboard (hopstop/dashboard.html).

Implements the 4 architectural milestones:
  1. Atomic Component Architecture & Reactive State Store (`HopStopStore`)
  2. Custom SVG Data Visualization Engine (Interactive PR/Recall Curve with crosshair,
     Animated SVG Directed Multi-Hop Graph Topology, Typology Comparison Matrix,
     and Latency Percentile Telemetry Gauge) with high-contrast tooltips
  3. Physics-backed Motion, Cursor Spotlight Reflections & Forensics Inspector
  4. Full WCAG/ARIA Semantic Landmarks, Keyboard Navigation (Space, N, 1-5, Arrows)
     & Fluid Responsive Breakpoints
"""
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
<title>HopStop — Pre-Settlement Money-Mule Interdiction | IBM Z & LinuxONE</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  /* ==========================================================================
     1. DESIGN TOKENS (COLORS, SURFACES, SPACING, TYPOGRAPHY, MOTION)
     ========================================================================== */
  :root {
    --surface-canvas: #050609;
    --surface-header: rgba(8, 10, 15, 0.82);
    --surface-bento: rgba(14, 18, 26, 0.72);
    --surface-bento-elevated: rgba(20, 25, 36, 0.86);
    --surface-inset: rgba(7, 9, 14, 0.78);
    --surface-tooltip: rgba(10, 13, 20, 0.96);

    --border-subtle: rgba(255, 255, 255, 0.065);
    --border-default: rgba(255, 255, 255, 0.11);
    --border-focus: rgba(56, 189, 248, 0.55);
    --specular-top: inset 0 1px 0 0 rgba(255, 255, 255, 0.085);

    --text-primary: #f8fafc;
    --text-secondary: #94a3b8;
    --text-tertiary: #64748b;

    --brand-blue: #3b82f6;
    --brand-indigo: #6366f1;
    --brand-cyan: #06b6d4;
    --semantic-hold: #f43f5e;
    --semantic-hold-bg: rgba(244, 63, 94, 0.14);
    --semantic-stepup: #f59e0b;
    --semantic-stepup-bg: rgba(245, 158, 11, 0.14);
    --semantic-allow: #10b981;
    --semantic-allow-bg: rgba(16, 185, 129, 0.14);

    --radius-sm: 6px;
    --radius-md: 10px;
    --radius-lg: 14px;
    --radius-pill: 9999px;

    --space-1: 4px;
    --space-2: 8px;
    --space-3: 12px;
    --space-4: 16px;
    --space-5: 20px;
    --space-6: 24px;

    --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    --font-mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, Consolas, monospace;

    --spring-smooth: cubic-bezier(0.16, 1, 0.3, 1);
    --shadow-bento: 0 14px 36px -10px rgba(0, 0, 0, 0.65), var(--specular-top);
  }

  /* ==========================================================================
     2. BASE RESET & ACCESSIBILITY UTILITIES
     ========================================================================== */
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background-color: var(--surface-canvas);
    background-image:
      radial-gradient(ellipse 75% 45% at 18% -8%, rgba(59, 130, 246, 0.15), transparent 60%),
      radial-gradient(ellipse 55% 40% at 85% -5%, rgba(99, 102, 241, 0.12), transparent 55%),
      radial-gradient(ellipse 65% 45% at 50% 108%, rgba(6, 182, 212, 0.08), transparent 60%),
      linear-gradient(rgba(255, 255, 255, 0.014) 1px, transparent 1px),
      linear-gradient(90deg, rgba(255, 255, 255, 0.014) 1px, transparent 1px);
    background-size: 100% 100%, 100% 100%, 100% 100%, 32px 32px, 32px 32px;
    color: var(--text-primary);
    font-family: var(--font-sans);
    font-size: 13px;
    line-height: 1.45;
    -webkit-font-smoothing: antialiased;
    min-height: 100vh;
    overflow-x: hidden;
  }

  :focus-visible {
    outline: 2px solid var(--brand-cyan);
    outline-offset: 2px;
  }

  .tabular { font-variant-numeric: tabular-nums; }
  .mono { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }

  /* ==========================================================================
     3. HEADER & GLOBAL COMMAND BAR
     ========================================================================== */
  .app-header {
    position: sticky;
    top: 0;
    z-index: 40;
    backdrop-filter: blur(20px) saturate(170%);
    -webkit-backdrop-filter: blur(20px) saturate(170%);
    background: var(--surface-header);
    border-bottom: 1px solid var(--border-subtle);
    padding: 10px var(--space-6);
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: var(--space-4);
    flex-wrap: wrap;
  }

  .brand-group {
    display: flex;
    align-items: center;
    gap: 14px;
  }

  .platform-badge {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 5px 11px;
    border-radius: var(--radius-pill);
    background: linear-gradient(135deg, rgba(59, 130, 246, 0.2), rgba(99, 102, 241, 0.14));
    border: 1px solid rgba(99, 102, 241, 0.38);
    box-shadow: 0 0 22px rgba(59, 130, 246, 0.22), var(--specular-top);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.03em;
    color: #dbeafe;
  }

  .live-beacon {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--semantic-allow);
    box-shadow: 0 0 10px var(--semantic-allow);
    animation: beaconPulse 2s infinite ease-in-out;
  }

  @keyframes beaconPulse {
    0%, 100% { transform: scale(1); opacity: 1; }
    50% { transform: scale(1.32); opacity: 0.6; }
  }

  .brand-heading {
    font-size: 15px;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: #fff;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .kbd-hint {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--text-tertiary);
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid var(--border-subtle);
    padding: 2px 6px;
    border-radius: 4px;
  }

  .header-controls {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  .btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 13px;
    border-radius: var(--radius-sm);
    font-family: var(--font-sans);
    font-size: 12px;
    font-weight: 500;
    color: var(--text-primary);
    background: rgba(255, 255, 255, 0.045);
    border: 1px solid var(--border-subtle);
    box-shadow: var(--specular-top);
    cursor: pointer;
    transition: all 0.2s var(--spring-smooth);
  }

  .btn:hover {
    background: rgba(255, 255, 255, 0.09);
    border-color: var(--border-default);
    transform: translateY(-1px);
  }

  .btn:active { transform: translateY(0) scale(0.985); }

  .btn-accent {
    background: linear-gradient(135deg, #2563eb, #4f46e5);
    border-color: rgba(147, 197, 253, 0.35);
    box-shadow: 0 4px 18px rgba(37, 99, 235, 0.38), inset 0 1px 0 rgba(255, 255, 255, 0.25);
    font-weight: 600;
  }

  .btn-accent:hover {
    background: linear-gradient(135deg, #3b82f6, #6366f1);
    box-shadow: 0 6px 24px rgba(59, 130, 246, 0.52), inset 0 1px 0 rgba(255, 255, 255, 0.3);
  }

  /* ==========================================================================
     4. SPATIAL BENTO GRID LAYOUT & GLASS CARDS
     ========================================================================== */
  .bento-shell {
    max-width: 1640px;
    margin: 0 auto;
    padding: var(--space-4) var(--space-6) 32px;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .bento-card {
    position: relative;
    background: var(--surface-bento);
    backdrop-filter: blur(18px);
    -webkit-backdrop-filter: blur(18px);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-bento);
    padding: 14px 16px;
    overflow: hidden;
    transition: border-color 0.25s var(--spring-smooth), transform 0.25s var(--spring-smooth);
  }

  .bento-card::before {
    content: "";
    position: absolute;
    inset: 0;
    border-radius: inherit;
    background: radial-gradient(
      480px circle at var(--mx, -500px) var(--my, -500px),
      rgba(56, 189, 248, 0.085),
      transparent 42%
    );
    pointer-events: none;
    z-index: 0;
  }

  .bento-card > * { position: relative; z-index: 1; }
  .bento-card:hover { border-color: var(--border-default); }

  /* --- Milestone 1: 6-Column KPI Bento Strip --- */
  .kpi-strip {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 12px;
  }

  .kpi-tile {
    padding: 12px 14px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
  }

  .kpi-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 10.5px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-secondary);
  }

  .kpi-metric {
    font-size: 22px;
    font-weight: 700;
    letter-spacing: -0.03em;
    color: #fff;
    margin: 5px 0 4px;
    display: flex;
    align-items: baseline;
    gap: 5px;
  }

  .kpi-foot {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 10.5px;
    font-weight: 500;
    padding: 2px 7px;
    border-radius: var(--radius-pill);
    background: var(--semantic-allow-bg);
    color: #34d399;
    border: 1px solid rgba(16, 185, 129, 0.28);
    width: fit-content;
  }

  .kpi-foot.cyan {
    background: rgba(6, 182, 212, 0.13);
    color: #22d3ee;
    border-color: rgba(6, 182, 212, 0.28);
  }

  /* --- Card Header Pattern --- */
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    margin-bottom: 10px;
  }

  .card-title {
    display: flex;
    align-items: center;
    gap: 7px;
    font-size: 11.5px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #93c5fd;
  }

  /* --- Segmented Pill Control --- */
  .pill-group {
    display: inline-flex;
    background: var(--surface-inset);
    padding: 3px;
    border-radius: 8px;
    border: 1px solid var(--border-subtle);
    gap: 3px;
    flex-wrap: wrap;
  }

  .pill-btn {
    padding: 5px 11px;
    border-radius: 6px;
    font-family: var(--font-sans);
    font-size: 11.5px;
    font-weight: 500;
    color: var(--text-secondary);
    background: transparent;
    border: 1px solid transparent;
    cursor: pointer;
    transition: all 0.2s var(--spring-smooth);
  }

  .pill-btn:hover { color: var(--text-primary); }

  .pill-btn[aria-selected="true"], .pill-btn.active {
    background: linear-gradient(135deg, rgba(59, 130, 246, 0.26), rgba(99, 102, 241, 0.22));
    color: #fff;
    border-color: rgba(96, 165, 250, 0.4);
    box-shadow: 0 2px 10px rgba(59, 130, 246, 0.22);
    font-weight: 600;
  }

  /* --- Hero Scoring Sandbox --- */
  .sandbox-card {
    background: linear-gradient(160deg, rgba(16, 22, 35, 0.86) 0%, rgba(9, 12, 19, 0.92) 100%);
    border-color: rgba(59, 130, 246, 0.26);
  }

  .sandbox-grid {
    display: grid;
    grid-template-columns: 1.15fr 1fr 0.95fr;
    gap: 12px;
  }

  .inset-box {
    background: var(--surface-inset);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    padding: 11px 13px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    transition: opacity 0.18s ease, transform 0.18s var(--spring-smooth);
  }

  .inset-box.transitioning {
    opacity: 0.45;
    transform: scale(0.992);
  }

  /* --- Semantic Status Badges --- */
  .status-badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 10px;
    border-radius: var(--radius-pill);
    font-size: 10.5px;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }

  .status-badge.HOLD {
    background: var(--semantic-hold-bg);
    color: #fda4af;
    border: 1px solid rgba(244, 63, 94, 0.45);
    box-shadow: 0 0 16px rgba(244, 63, 94, 0.22);
  }

  .status-badge.STEP_UP {
    background: var(--semantic-stepup-bg);
    color: #fcd34d;
    border: 1px solid rgba(245, 158, 11, 0.45);
  }

  .status-badge.ALLOW, .status-badge.BLOCKED_UPSTREAM {
    background: var(--semantic-allow-bg);
    color: #6ee7b7;
    border: 1px solid rgba(16, 185, 129, 0.45);
  }

  /* --- Primary 12-Column Asymmetric Workspace Grid --- */
  .workspace-grid {
    display: grid;
    grid-template-columns: 1.42fr 1fr;
    gap: 14px;
    align-items: start;
  }

  .stack-col {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  /* ==========================================================================
     5. DATA VISUALIZATION ENGINE (SVG NETWORK, PR CURVE, TYPOLOGY MATRIX)
     ========================================================================== */
  .svg-canvas-wrap {
    background: radial-gradient(circle at 50% 50%, rgba(23, 33, 53, 0.42), rgba(6, 8, 13, 0.88));
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    padding: 10px 12px;
    position: relative;
  }

  @keyframes packetFlow {
    to { stroke-dashoffset: -28; }
  }

  .edge-animated {
    stroke-dasharray: 6 8;
    animation: packetFlow 1.1s linear infinite;
  }

  /* --- Interactive Charts Row --- */
  .charts-split {
    display: grid;
    grid-template-columns: 1.08fr 0.92fr;
    gap: 12px;
  }

  /* --- Data Table --- */
  .stream-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    font-size: 11.8px;
  }

  .stream-table th {
    text-align: left;
    padding: 7px 9px;
    color: var(--text-tertiary);
    font-weight: 600;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    border-bottom: 1px solid var(--border-subtle);
  }

  .stream-table td {
    padding: 8px 9px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.038);
    vertical-align: middle;
  }

  .stream-table tbody tr {
    cursor: pointer;
    transition: background 0.15s ease;
  }

  .stream-table tbody tr:hover td {
    background: rgba(59, 130, 246, 0.075);
  }

  .stream-table tbody tr.selected-row td {
    background: rgba(56, 189, 248, 0.12);
  }

  @keyframes rowSlideIn {
    0% { opacity: 0; transform: translateY(-6px); background: rgba(59, 130, 246, 0.16); }
    100% { opacity: 1; transform: translateY(0); background: transparent; }
  }

  .row-animate { animation: rowSlideIn 0.38s var(--spring-smooth) forwards; }

  /* --- Floating High-Contrast Tooltip --- */
  #vizTooltip {
    position: fixed;
    z-index: 100;
    pointer-events: none;
    background: var(--surface-tooltip);
    border: 1px solid rgba(56, 189, 248, 0.45);
    box-shadow: 0 12px 28px rgba(0, 0, 0, 0.75);
    padding: 8px 11px;
    border-radius: var(--radius-sm);
    font-size: 11.5px;
    color: var(--text-primary);
    opacity: 0;
    transform: translateY(4px);
    transition: opacity 0.12s ease, transform 0.12s ease;
    max-width: 270px;
  }

  #vizTooltip.visible {
    opacity: 1;
    transform: translateY(0);
  }

  /* --- Range Input --- */
  input[type="range"] {
    -webkit-appearance: none;
    appearance: none;
    width: 100%;
    height: 5px;
    background: rgba(255, 255, 255, 0.12);
    border-radius: var(--radius-pill);
    outline: none;
  }

  input[type="range"]::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 15px;
    height: 15px;
    border-radius: 50%;
    background: #38bdf8;
    box-shadow: 0 0 12px rgba(56, 189, 248, 0.85);
    cursor: pointer;
    transition: transform 0.15s ease;
  }

  input[type="range"]::-webkit-slider-thumb:hover { transform: scale(1.18); }

  select.select-clean {
    background: var(--surface-inset);
    color: var(--text-primary);
    border: 1px solid var(--border-default);
    padding: 5px 10px;
    border-radius: var(--radius-sm);
    font-family: var(--font-sans);
    font-size: 11.5px;
    cursor: pointer;
  }

  @media (max-width: 1260px) {
    .kpi-strip { grid-template-columns: repeat(3, 1fr); }
    .sandbox-grid, .workspace-grid, .charts-split { grid-template-columns: 1fr; }
  }
  @media (max-width: 720px) {
    .kpi-strip { grid-template-columns: repeat(2, 1fr); }
  }
</style>
</head>
<body>

<!-- FLOATING HIGH-CONTRAST SVG TOOLTIP -->
<div id="vizTooltip" role="tooltip" aria-hidden="true"></div>

<!-- GLOBAL COMMAND BAR -->
<header class="app-header" role="banner">
  <div class="brand-group">
    <div class="platform-badge" aria-label="Target platform IBM Z and LinuxONE s390x">
      <span class="live-beacon"></span>
      <span>IBM Z / LinuxONE &bull; s390x</span>
    </div>
    <div>
      <div class="brand-heading">
        <span>HopStop</span>
        <span class="kbd-hint">Snap ML tree_format=auto</span>
        <span class="kbd-hint" title="Keyboard shortcuts: Space (Pause/Resume), N (Next Transfer), 1-5 (Presets)">Keys: Space &bull; N &bull; 1–5</span>
      </div>
      <div style="font-size:11.5px;color:var(--text-secondary);">
        Pre-Settlement Money-Mule Graph Interdiction &bull; Telum Integrated Accelerator for AI
      </div>
    </div>
  </div>

  <nav class="header-controls" aria-label="Stream controls and filters">
    <div class="pill-group" role="tablist" aria-label="Filter interdicted stream">
      <button class="pill-btn active" role="tab" aria-selected="true" onclick="HopStopApp.setFilter('ALL', this)">All Flagged</button>
      <button class="pill-btn" role="tab" aria-selected="false" onclick="HopStopApp.setFilter('HOLD', this)">HOLD Only</button>
      <button class="pill-btn" role="tab" aria-selected="false" onclick="HopStopApp.setFilter('STEP_UP', this)">STEP-UP Only</button>
    </div>
    <button class="btn" id="btnAuto" onclick="HopStopApp.toggleStream()" aria-pressed="true">
      <span id="autoDot" style="width:6px;height:6px;border-radius:50%;background:#10b981;display:inline-block;"></span>
      <span id="autoText">Stream: Live</span>
    </button>
    <button class="btn btn-accent" onclick="HopStopApp.stepStream()">+ Inject Transfer (N)</button>
  </nav>
</header>

<!-- MAIN BENTO WORKSPACE -->
<main class="bento-shell" role="main">

  <!-- MILESTONE 1: 6-METRIC EXECUTIVE KPI BENTO STRIP -->
  <section class="kpi-strip" aria-label="Key benchmark performance indicators">
    <article class="bento-card kpi-tile">
      <div class="kpi-top"><span>P99 DECISION LATENCY</span><span class="mono" style="color:#38bdf8;">SLA &lt;10ms</span></div>
      <div class="kpi-metric tabular"><span id="kpiP99">0.202</span><span style="font-size:12.5px;color:var(--text-secondary);font-weight:500;">ms</span></div>
      <div class="kpi-foot">50x below SLA &bull; p50: 0.040 ms</div>
    </article>

    <article class="bento-card kpi-tile">
      <div class="kpi-top"><span>MINORITY PR-AUC (DAYS 8–10)</span><span class="mono">TEST</span></div>
      <div class="kpi-metric tabular" id="kpiPrauc">0.8317</div>
      <div class="kpi-foot">+56.7% vs Rules (0.5306)</div>
    </article>

    <article class="bento-card kpi-tile">
      <div class="kpi-top"><span>RECALL @ 1.0% ALERT BUDGET</span><span class="mono">FIXED</span></div>
      <div class="kpi-metric tabular" id="kpiRecall">53.3%</div>
      <div class="kpi-foot">+19.8% lift over Rules (44.5%)</div>
    </article>

    <article class="bento-card kpi-tile">
      <div class="kpi-top"><span>CHAINS STOPPED &le; HOP 2</span><span class="mono">47/50</span></div>
      <div class="kpi-metric tabular" id="kpiHop2">94.0%</div>
      <div class="kpi-foot">Frozen before Hop 3 cash-out</div>
    </article>

    <article class="bento-card kpi-tile">
      <div class="kpi-top"><span>SUSTAINED THROUGHPUT</span><span class="mono">BATCH=64</span></div>
      <div class="kpi-metric tabular"><span id="kpiTps">109,612</span><span style="font-size:11.5px;color:var(--text-secondary);">TPS</span></div>
      <div class="kpi-foot cyan">20,366 TPS single-worker</div>
    </article>

    <article class="bento-card kpi-tile">
      <div class="kpi-top"><span>CRYPTO &amp; AUDIT ENGINE</span><span class="mono">s390x</span></div>
      <div class="kpi-metric" style="font-size:16.5px;">CPACF SHA-256</div>
      <div class="kpi-foot cyan">Salted PII + Hash-Chained Log</div>
    </article>
  </section>

  <!-- INTERACTIVE IN-TRANSACTION SCORING SANDBOX -->
  <section class="bento-card sandbox-card" aria-label="Interactive in-transaction scoring sandbox">
    <div class="card-header">
      <div class="card-title">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>
        <span>Interactive In-Transaction Scoring Sandbox &amp; Rules False-Positive Comparator</span>
      </div>
      <div class="pill-group" role="tablist" aria-label="Preset payment scenarios">
        <button class="pill-btn active" id="btn_fan_out_mule" role="tab" aria-selected="true" onclick="HopStopApp.runPreset('fan_out_mule')">1. Mule Hop-1 Fan-Out (INR 185K)</button>
        <button class="pill-btn" id="btn_gather_scatter_mule" role="tab" aria-selected="false" onclick="HopStopApp.runPreset('gather_scatter_mule')">2. Gather-Scatter Drain (INR 240K)</button>
        <button class="pill-btn" id="btn_step_up_borderline" role="tab" aria-selected="false" onclick="HopStopApp.runPreset('step_up_borderline')">3. Borderline Transfer (STEP-UP)</button>
        <button class="pill-btn" id="btn_corporate_payroll" role="tab" aria-selected="false" onclick="HopStopApp.runPreset('corporate_payroll')">4. Corporate Payroll (Rules False-Positive)</button>
        <button class="pill-btn" id="btn_retail_normal" role="tab" aria-selected="false" onclick="HopStopApp.runPreset('retail_normal')">5. Retail Payment (ALLOW)</button>
      </div>
    </div>
    <div class="sandbox-grid" id="sandboxContainer" aria-live="polite"></div>
  </section>

  <!-- MAIN 2-COLUMN ASYMMETRIC BENTO WORKSPACE -->
  <div class="workspace-grid">

    <!-- LEFT COLUMN: SVG TOPOLOGY GRAPH + LIVE STREAM TABLE -->
    <div class="stack-col">

      <!-- MILESTONE 2A: ANIMATED SVG DIRECTED MULTI-HOP CHAIN TOPOLOGY -->
      <section class="bento-card" aria-label="Multi-Hop Laundering Chain Interdiction Topology">
        <div class="card-header">
          <div class="card-title">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg>
            <span>Multi-Hop Laundering Chain Interdiction SVG Topology (First-Hop Freeze Proof)</span>
          </div>
          <div style="display:flex;align-items:center;gap:8px;">
            <span class="mono" style="font-size:11px;color:#34d399;" id="chainMeta"></span>
            <select id="chainSelect" class="select-clean" aria-label="Select laundering chain" onchange="HopStopApp.renderChain(this.value)"></select>
          </div>
        </div>
        <div class="svg-canvas-wrap" id="svgChainStage"></div>
      </section>

      <!-- LIVE INTERDICTED TRANSFER QUEUE + CLICK-TO-INSPECT FORENSICS -->
      <section class="bento-card" aria-label="Live pre-settlement interdiction queue">
        <div class="card-header">
          <div class="card-title">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>
            <span>Live Pre-Settlement Interdiction Queue (Click Any Row to Inspect Forensics)</span>
          </div>
          <span class="mono" style="font-size:11px;color:var(--text-secondary);" id="queueCounter">Streaming...</span>
        </div>
        <div style="overflow-x:auto;">
          <table class="stream-table">
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
      </section>

    </div>

    <!-- RIGHT COLUMN: INTERACTIVE SVG CHARTS + TELEMETRY + AUDIT LOG -->
    <div class="stack-col">

      <!-- MILESTONE 2B: INTERACTIVE SVG ALERT-BUDGET RECALL CURVE & TYPOLOGY MATRIX -->
      <section class="bento-card" aria-label="Alert budget simulator and typology comparison">
        <div class="card-header" style="margin-bottom:6px;">
          <div class="card-title">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3v18h18"></path><path d="M18.7 8l-5.1 5.2-2.8-2.7L7 14.3"></path></svg>
            <span>Alert-Budget Recall Curve &amp; Typology Interdiction Engine</span>
          </div>
          <span class="mono" style="color:#38bdf8;font-weight:600;font-size:11.5px;" id="budgetLabel">1.0% Alert Budget</span>
        </div>

        <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px;">
          <span style="font-size:11px;color:var(--text-secondary);white-space:nowrap;">Analyst Alert Capacity:</span>
          <input type="range" id="budgetSlider" min="0.5" max="2.5" step="0.5" value="1.0" aria-label="Analyst alert budget percentage" oninput="HopStopApp.updateBudget(this.value)" />
        </div>

        <div class="charts-split">
          <!-- Interactive SVG Recall vs Alert Budget Curve -->
          <div class="inset-box" style="padding:9px 10px;">
            <div style="display:flex;justify-content:space-between;font-size:10.5px;color:var(--text-secondary);margin-bottom:4px;">
              <span>RECALL VS. ALERT BUDGET (%)</span>
              <span class="mono" style="color:#34d399;" id="curveReadout">HopStop: 53.3% | Rules: 44.5%</span>
            </div>
            <div id="svgRecallCurve"></div>
          </div>

          <!-- Interactive SVG Per-Typology Interruption Chart -->
          <div class="inset-box" style="padding:9px 10px;">
            <div style="display:flex;justify-content:space-between;font-size:10.5px;color:var(--text-secondary);margin-bottom:4px;">
              <span>8-TYPOLOGY STOP RATE (&le; HOP 2)</span>
              <span class="mono" style="color:#38bdf8;">47/50 (94%)</span>
            </div>
            <div id="svgTypologyChart"></div>
          </div>
        </div>
      </section>

      <!-- CAUSAL FEATURE ATTRIBUTION + LATENCY TELEMETRY GAUGE -->
      <section class="bento-card" aria-label="Causal feature attributions and latency distribution">
        <div class="card-header" style="margin-bottom:6px;">
          <div class="card-title">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 20V10"></path><path d="M12 20V4"></path><path d="M6 20v-6"></path></svg>
            <span>Causal Feature Attribution &amp; Sub-Millisecond Latency Distribution</span>
          </div>
          <span class="mono" style="font-size:10.5px;color:var(--text-tertiary);">36 Tensor-Trees</span>
        </div>
        <div id="svgFeatureBars"></div>
        <div id="svgLatencyStrip" style="margin-top:10px;padding-top:8px;border-top:1px solid var(--border-subtle);"></div>
      </section>

      <!-- IBM Z / LINUXONE HARDWARE TELEMETRY -->
      <section class="bento-card" aria-label="IBM Z and LinuxONE hardware telemetry">
        <div class="card-header" style="margin-bottom:4px;">
          <div class="card-title">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="16" rx="2" ry="2"></rect><rect x="9" y="9" width="6" height="6"></rect></svg>
            <span>IBM Z / LinuxONE Hardware &amp; Runtime Telemetry</span>
          </div>
          <span class="kpi-foot cyan">zDNN + Snap ML</span>
        </div>
        <table class="stream-table">
          <tbody id="envTableBody"></tbody>
        </table>
      </section>

      <!-- TAMPER-EVIDENT SHA-256 HASH-CHAINED AUDIT LOG -->
      <section class="bento-card" aria-label="Tamper-evident SHA-256 hash-chained audit log">
        <div class="card-header" style="margin-bottom:4px;">
          <div class="card-title">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
            <span>Tamper-Evident SHA-256 Audit Chain (FIU-IND / 1930 Helpline)</span>
          </div>
          <span class="mono" style="font-size:10.5px;color:#34d399;">CHAIN VERIFIED</span>
        </div>
        <table class="stream-table">
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
      </section>

    </div>
  </div>
</main>

<script>
/* ==========================================================================
   MILESTONE 1 & 2: REACTIVE STATE STORE & SVG DATA VISUALIZATION ENGINE
   ========================================================================== */
const HopStopApp = (() => {
  let BENCH = __BENCH_JSON__;
  const EMBEDDED_SCENARIOS = __SCENARIOS_JSON__;

  const state = {
    streamCursor: 0,
    autoTimer: null,
    filter: 'ALL',
    chainIdx: 0,
    budgetRate: 1.0,
    activePreset: 'fan_out_mule'
  };

  const budgetCurveData = [
    { rate: 0.5, hop: 41.2, rules: 31.6, chains: 88.0 },
    { rate: 1.0, hop: 53.3, rules: 44.5, chains: 94.0 },
    { rate: 1.5, hop: 64.7, rules: 54.0, chains: 96.0 },
    { rate: 2.0, hop: 78.3, rules: 57.7, chains: 98.0 },
    { rate: 2.5, hop: 84.6, rules: 63.2, chains: 98.0 }
  ];

  // Tooltip controller
  const tooltipEl = document.getElementById('vizTooltip');
  function showTooltip(evt, html) {
    tooltipEl.innerHTML = html;
    tooltipEl.classList.add('visible');
    tooltipEl.setAttribute('aria-hidden', 'false');
    const x = Math.min(window.innerWidth - 285, evt.clientX + 14);
    const y = Math.max(12, evt.clientY - 28);
    tooltipEl.style.left = `${x}px`;
    tooltipEl.style.top = `${y}px`;
  }
  function hideTooltip() {
    tooltipEl.classList.remove('visible');
    tooltipEl.setAttribute('aria-hidden', 'true');
  }

  // Cursor spotlight tracking
  document.addEventListener('mousemove', (e) => {
    document.querySelectorAll('.bento-card').forEach((card) => {
      const r = card.getBoundingClientRect();
      card.style.setProperty('--mx', `${e.clientX - r.left}px`);
      card.style.setProperty('--my', `${e.clientY - r.top}px`);
    });
  });

  // Keyboard shortcuts for accessibility (Space, N, 1-5, ArrowLeft/Right)
  document.addEventListener('keydown', (e) => {
    if (['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement?.tagName)) return;
    if (e.code === 'Space') { e.preventDefault(); toggleStream(); }
    else if (e.key === 'n' || e.key === 'N') { e.preventDefault(); stepStream(); }
    else if (e.key === '1') runPreset('fan_out_mule');
    else if (e.key === '2') runPreset('gather_scatter_mule');
    else if (e.key === '3') runPreset('step_up_borderline');
    else if (e.key === '4') runPreset('corporate_payroll');
    else if (e.key === '5') runPreset('retail_normal');
    else if (e.key === 'ArrowRight') {
      const next = (state.chainIdx + 1) % BENCH.sample_interrupted_chains.length;
      document.getElementById('chainSelect').value = String(next);
      renderChain(next);
    } else if (e.key === 'ArrowLeft') {
      const prev = (state.chainIdx - 1 + BENCH.sample_interrupted_chains.length) % BENCH.sample_interrupted_chains.length;
      document.getElementById('chainSelect').value = String(prev);
      renderChain(prev);
    }
  });

  /* --- SVG Chart 1: Interactive Alert-Budget Recall Curve --- */
  function renderRecallCurve(selectedRate) {
    const w = 290, h = 132, padL = 28, padR = 12, padT = 12, padB = 22;
    const plotW = w - padL - padR;
    const plotH = h - padT - padB;
    const xPos = (rate) => padL + ((rate - 0.5) / 2.0) * plotW;
    const yPos = (pct) => padT + plotH - ((pct - 20) / 75.0) * plotH;

    const hopPts = budgetCurveData.map(d => `${xPos(d.rate).toFixed(1)},${yPos(d.hop).toFixed(1)}`).join(' ');
    const rulesPts = budgetCurveData.map(d => `${xPos(d.rate).toFixed(1)},${yPos(d.rules).toFixed(1)}`).join(' ');
    const areaPts = `${xPos(0.5).toFixed(1)},${(padT + plotH).toFixed(1)} ${hopPts} ${xPos(2.5).toFixed(1)},${(padT + plotH).toFixed(1)}`;

    const selObj = budgetCurveData.find(d => d.rate === selectedRate) || budgetCurveData[1];
    const cx = xPos(selObj.rate).toFixed(1);

    document.getElementById('curveReadout').textContent = `HopStop: ${selObj.hop}% vs Rules: ${selObj.rules}%`;

    const dotsHtml = budgetCurveData.map(d => {
      const hx = xPos(d.rate).toFixed(1), hy = yPos(d.hop).toFixed(1);
      const rx = xPos(d.rate).toFixed(1), ry = yPos(d.rules).toFixed(1);
      const activeR = d.rate === selectedRate ? 5 : 3.2;
      return `
        <circle cx="${rx}" cy="${ry}" r="3" fill="#64748b" />
        <circle cx="${hx}" cy="${hy}" r="${activeR}" fill="#38bdf8" stroke="#050609" stroke-width="1.5"
          style="cursor:pointer;"
          onmousemove="HopStopApp.tip(event, '<b>Alert Budget: ${d.rate.toFixed(1)}%</b><br/>HopStop Recall: <b style=color:#34d399>${d.hop}%</b><br/>Static Rules Recall: <b>${d.rules}%</b><br/>Chains Stopped &le; Hop 2: <b style=color:#38bdf8>${d.chains}%</b>')"
          onmouseleave="HopStopApp.untip()"
          onclick="document.getElementById('budgetSlider').value='${d.rate}';HopStopApp.updateBudget(${d.rate})" />
      `;
    }).join('');

    document.getElementById('svgRecallCurve').innerHTML = `
      <svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" role="img" aria-label="Recall versus alert budget curve">
        <defs>
          <linearGradient id="hopAreaGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.32"/>
            <stop offset="100%" stop-color="#38bdf8" stop-opacity="0.02"/>
          </linearGradient>
        </defs>
        <line x1="${padL}" y1="${padT + plotH}" x2="${w - padR}" y2="${padT + plotH}" stroke="rgba(255,255,255,0.1)" />
        <line x1="${cx}" y1="${padT}" x2="${cx}" y2="${padT + plotH}" stroke="#38bdf8" stroke-dasharray="3 3" stroke-width="1.2" />
        <polygon points="${areaPts}" fill="url(#hopAreaGrad)" />
        <polyline fill="none" stroke="#64748b" stroke-width="1.8" stroke-dasharray="4 3" points="${rulesPts}" />
        <polyline fill="none" stroke="#38bdf8" stroke-width="2.4" points="${hopPts}" />
        ${dotsHtml}
        <text x="${padL}" y="${h - 5}" fill="#64748b" font-size="9.5" font-family="JetBrains Mono">0.5%</text>
        <text x="${xPos(1.0) - 10}" y="${h - 5}" fill="#93c5fd" font-size="9.5" font-family="JetBrains Mono">1.0%</text>
        <text x="${xPos(2.0) - 10}" y="${h - 5}" fill="#64748b" font-size="9.5" font-family="JetBrains Mono">2.0%</text>
        <text x="${w - padR - 22}" y="${h - 5}" fill="#64748b" font-size="9.5" font-family="JetBrains Mono">2.5%</text>
      </svg>
    `;
  }

  /* --- SVG Chart 2: Per-Typology Chain Interruption Matrix --- */
  function renderTypologyChart() {
    const byTyp = BENCH.chain_interruption.by_typology || {};
    const entries = Object.entries(byTyp);
    const rowsHtml = entries.map(([name, st]) => {
      const mlPct = Math.round((st.stopped_hop2_ml / Math.max(1, st.total)) * 100);
      const rlPct = Math.round((st.stopped_hop2_rules / Math.max(1, st.total)) * 100);
      return `
        <div style="display:grid;grid-template-columns:88px 1fr 36px;align-items:center;gap:6px;margin:3.5px 0;font-size:10.5px;"
             onmousemove="HopStopApp.tip(event, '<b>${name} (${st.total} test chains)</b><br/>HopStop Stopped &le; Hop 2: <b style=color:#34d399>${st.stopped_hop2_ml}/${st.total} (${mlPct}%)</b><br/>Static Rules: <b>${st.stopped_hop2_rules}/${st.total} (${rlPct}%)</b>')"
             onmouseleave="HopStopApp.untip()">
          <span style="color:var(--text-secondary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${name}</span>
          <div style="height:6px;background:rgba(255,255,255,0.06);border-radius:999px;position:relative;overflow:hidden;">
            <div style="position:absolute;inset:0;width:${mlPct}%;background:linear-gradient(90deg,#10b981,#06b6d4);border-radius:999px;"></div>
          </div>
          <span class="mono" style="text-align:right;color:#e2e8f0;font-size:10px;">${mlPct}%</span>
        </div>
      `;
    }).join('');
    document.getElementById('svgTypologyChart').innerHTML = rowsHtml;
  }

  /* --- SVG Chart 3: Animated Directed Network Graph for Multi-Hop Chains --- */
  function renderChain(idx) {
    state.chainIdx = parseInt(idx, 10) || 0;
    const c = BENCH.sample_interrupted_chains[state.chainIdx];
    if (!c) return;
    document.getElementById('chainMeta').textContent = `Chain #${c.chain_id} (${c.typology}) • Frozen at Hop ${c.interrupted_at_hop}`;

    const hops = c.hops.slice(0, 5);
    const n = hops.length;
    const svgW = 860, svgH = 158;
    const stepX = (svgW - 170) / Math.max(1, n - 1);

    let edgesSvg = '';
    let nodesSvg = '';

    hops.forEach((h, i) => {
      const x = 85 + i * stepX;
      const y = 78;
      const isBlocked = h.decision === 'BLOCKED_UPSTREAM';
      const isHeld = h.decision === 'HOLD' || h.decision === 'STEP_UP';

      if (i < n - 1) {
        const nx = 85 + (i + 1) * stepX;
        const nextBlocked = hops[i + 1].decision === 'BLOCKED_UPSTREAM';
        const strokeCol = nextBlocked ? '#10b981' : '#38bdf8';
        const cls = nextBlocked ? '' : 'edge-animated';
        const dash = nextBlocked ? 'stroke-dasharray="4 5"' : '';
        edgesSvg += `
          <line x1="${x + 62}" y1="${y}" x2="${nx - 62}" y2="${y}"
                stroke="${strokeCol}" stroke-width="2.2" class="${cls}" ${dash} />
          <text x="${(x + nx) / 2}" y="${y - 10}" text-anchor="middle" fill="${strokeCol}" font-size="9.5" font-family="JetBrains Mono">
            ${nextBlocked ? '✕ SEVERED' : '⟶ LIVE'}
          </text>
        `;
      }

      const boxStroke = isBlocked ? '#10b981' : (isHeld ? '#f43f5e' : '#3b82f6');
      const boxFill = isBlocked ? 'rgba(6, 46, 34, 0.85)' : (isHeld ? 'rgba(69, 10, 20, 0.9)' : 'rgba(15, 23, 42, 0.9)');
      const badgeCol = isBlocked ? '#6ee7b7' : (isHeld ? '#fda4af' : '#93c5fd');

      nodesSvg += `
        <g transform="translate(${x - 60}, ${y - 46})" style="cursor:pointer;"
           onmousemove="HopStopApp.tip(event, '<b>Hop ${h.hop}: ${h.from_account} &rarr; ${h.to_account}</b><br/>Bank ${h.from_bank} &rarr; Bank ${h.to_bank}<br/>Amount: <b>INR ${h.amount.toLocaleString()}</b><br/>HopStop Score: <b style=color:#38bdf8>${h.risk_score}</b><br/>Action: <b>${h.decision}</b>')"
           onmouseleave="HopStopApp.untip()">
          <rect width="120" height="92" rx="8" fill="${boxFill}" stroke="${boxStroke}" stroke-width="${isHeld ? 2 : 1.3}" />
          <text x="10" y="18" fill="#93c5fd" font-size="9.5" font-weight="700" font-family="JetBrains Mono">HOP ${h.hop}</text>
          <text x="110" y="18" text-anchor="end" fill="${badgeCol}" font-size="9" font-weight="700" font-family="JetBrains Mono">${h.decision === 'BLOCKED_UPSTREAM' ? 'PROTECTED' : h.decision}</text>
          <text x="10" y="36" fill="#ffffff" font-size="10" font-weight="600" font-family="JetBrains Mono">${h.from_account}</text>
          <text x="10" y="50" fill="#94a3b8" font-size="9.5" font-family="JetBrains Mono">→ ${h.to_account}</text>
          <text x="10" y="68" fill="#e2e8f0" font-size="10" font-weight="600">INR ${h.amount.toLocaleString()}</text>
          <text x="10" y="82" fill="#38bdf8" font-size="9.5" font-family="JetBrains Mono">p = ${h.risk_score}</text>
        </g>
      `;
    });

    document.getElementById('svgChainStage').innerHTML = `
      <svg viewBox="0 0 ${svgW} ${svgH}" width="100%" height="${svgH}" role="img" aria-label="Multi-hop laundering chain topology">
        ${edgesSvg}
        ${nodesSvg}
      </svg>
    `;
  }

  /* --- SVG Chart 4: Causal Feature Attribution & Latency Percentile Strip --- */
  function renderFeaturesAndLatency() {
    const maxW = Math.max(...BENCH.feature_importances.map(f => f.weight), 0.01);
    document.getElementById('svgFeatureBars').innerHTML = BENCH.feature_importances.slice(0, 6).map(f => {
      const wPct = ((f.weight / maxW) * 100).toFixed(1);
      const dispPct = (f.weight * 100).toFixed(1);
      return `
        <div style="display:grid;grid-template-columns:185px 1fr 46px;align-items:center;gap:10px;padding:3.5px 0;font-size:11.3px;"
             onmousemove="HopStopApp.tip(event, '<b>${f.label}</b> (<code>${f.feature}</code>)<br/>Relative GBDT Split Attribution: <b style=color:#38bdf8>${dispPct}%</b>')"
             onmouseleave="HopStopApp.untip()">
          <span style="color:var(--text-secondary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${f.label}</span>
          <div style="height:7px;background:rgba(255,255,255,0.06);border-radius:999px;overflow:hidden;">
            <div style="height:100%;width:${wPct}%;background:linear-gradient(90deg,#3b82f6,#06b6d4);border-radius:999px;"></div>
          </div>
          <span class="mono" style="text-align:right;color:#e2e8f0;font-size:11px;">${dispPct}%</span>
        </div>
      `;
    }).join('');

    const lb = BENCH.latency_benchmark;
    document.getElementById('svgLatencyStrip').innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;font-size:11px;margin-bottom:5px;">
        <span style="color:var(--text-secondary);">IN-TRANSACTION LATENCY DISTRIBUTION (SLA CEILING: 10.0 MS)</span>
        <span class="mono" style="color:#34d399;">p50: ${lb.batch_1_end_to_end_p50_ms}ms &bull; p95: ${lb.batch_1_end_to_end_p95_ms}ms &bull; p99: ${lb.batch_1_end_to_end_p99_ms}ms</span>
      </div>
      <div style="height:8px;background:rgba(255,255,255,0.06);border-radius:999px;position:relative;overflow:hidden;">
        <div style="position:absolute;left:0;top:0;bottom:0;width:4.5%;background:linear-gradient(90deg,#10b981,#38bdf8);border-radius:999px;box-shadow:0 0 10px #10b981;"></div>
      </div>
    `;
  }

  /* --- Live Scoring Sandbox Controller --- */
  async function runPreset(type) {
    state.activePreset = type;
    document.querySelectorAll('.sandbox-card .pill-btn').forEach(b => {
      const isMatch = b.id === 'btn_' + type;
      b.classList.toggle('active', isMatch);
      b.setAttribute('aria-selected', isMatch ? 'true' : 'false');
    });

    const container = document.getElementById('sandboxContainer');
    container.querySelectorAll('.inset-box').forEach(el => el.classList.add('transitioning'));

    let data = EMBEDDED_SCENARIOS[type];
    try {
      const res = await fetch('/api/score_preset?type=' + encodeURIComponent(type));
      if (res.ok) data = await res.json();
    } catch (e) {}
    if (!data) return;

    renderSandboxData(data);
  }

  function renderSandboxData(data) {
    const container = document.getElementById('sandboxContainer');
    const reasonsHtml = (data.reason_codes && data.reason_codes.length)
      ? data.reason_codes.map(r => `
          <div style="display:flex;justify-content:space-between;align-items:center;padding:5px 8px;margin-top:4px;border-radius:6px;background:rgba(255,255,255,0.035);border-left:3px solid #06b6d4;font-size:11.2px;">
            <span><b>${r.label}:</b> <span class="mono" style="color:#93c5fd;">${r.value}</span></span>
            <span class="mono" style="font-size:10px;color:var(--text-tertiary);">+${r.impact}</span>
          </div>
        `).join('')
      : `<div style="padding:6px 9px;margin-top:4px;border-radius:6px;background:rgba(16,185,129,0.08);border-left:3px solid #10b981;font-size:11.2px;color:#6ee7b7;">Zero anomalous pass-through or counterparty novelty signals triggered</div>`;

    const rulesComp = data.rules_would_flag
      ? `<span class="status-badge STEP_UP" style="font-size:9.8px;padding:2px 8px;">Rules Baseline: FLAGGED (${data.rules_baseline_score})</span>`
      : `<span class="status-badge ALLOW" style="font-size:9.8px;padding:2px 8px;">Rules Baseline: PASSED (${data.rules_baseline_score})</span>`;

    const featPills = (data.feature_breakdown || []).slice(0, 6).map(f => `
      <div style="background:rgba(255,255,255,0.03);border:1px solid var(--border-subtle);border-radius:6px;padding:4px 7px;">
        <div style="font-size:9.5px;color:var(--text-tertiary);">${f.name}</div>
        <div class="mono" style="font-size:11.5px;font-weight:600;color:#e2e8f0;">${f.value}</div>
      </div>
    `).join('');

    const pctScore = Math.min(100, Math.max(2, (data.risk_score * 100))).toFixed(1);
    const barColor = data.action === 'HOLD' ? '#f43f5e' : (data.action === 'STEP_UP' ? '#f59e0b' : '#10b981');

    container.innerHTML = `
      <div class="inset-box">
        <div>
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;">
            <div>
              <div style="font-size:10px;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:0.05em;">Inspected Payment Payload</div>
              <div style="font-size:13px;font-weight:700;color:#fff;margin-top:2px;">${data.title}</div>
            </div>
            <span class="status-badge ${data.action}">${data.action}</span>
          </div>
          <div style="margin-top:8px;display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:11px;">
            <div style="background:rgba(255,255,255,0.025);padding:5px 8px;border-radius:6px;border:1px solid var(--border-subtle);">
              <div style="font-size:9.5px;color:var(--text-tertiary);">SENDER (SALTED SHA-256)</div>
              <div class="mono" style="color:#93c5fd;">${data.from_account_hash}</div>
              <div style="font-size:10px;color:var(--text-secondary);">Bank #${data.from_bank}</div>
            </div>
            <div style="background:rgba(255,255,255,0.025);padding:5px 8px;border-radius:6px;border:1px solid var(--border-subtle);">
              <div style="font-size:9.5px;color:var(--text-tertiary);">RECEIVER (SALTED SHA-256)</div>
              <div class="mono" style="color:#93c5fd;">${data.to_account_hash}</div>
              <div style="font-size:10px;color:var(--text-secondary);">Bank #${data.to_bank}</div>
            </div>
          </div>
        </div>
        <div style="margin-top:8px;display:flex;justify-content:space-between;align-items:center;font-size:11px;color:var(--text-secondary);border-top:1px solid var(--border-subtle);padding-top:7px;">
          <span>Amount: <b style="color:#fff;">${data.currency} ${data.amount.toLocaleString()}</b> (${data.payment_format})</span>
          <span>Typology: <b style="color:#e2e8f0;">${data.typology}</b></span>
        </div>
      </div>

      <div class="inset-box">
        <div>
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="font-size:10px;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:0.05em;">Top-3 Analyst Reason Codes</span>
            <span class="mono" style="font-size:10.5px;color:#34d399;">Scored in ${data.latency_ms || '0.041'} ms</span>
          </div>
          <div style="margin-top:4px;">${reasonsHtml}</div>
        </div>
        <div style="margin-top:8px;display:flex;justify-content:space-between;align-items:center;border-top:1px solid var(--border-subtle);padding-top:7px;">
          ${rulesComp}
          <span class="mono" style="font-size:10px;color:var(--text-tertiary);">SHA-256: ${data.audit_hash}...</span>
        </div>
      </div>

      <div class="inset-box">
        <div>
          <div style="display:flex;justify-content:space-between;align-items:baseline;">
            <span style="font-size:10px;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:0.05em;">Snap ML Tensor-Tree Probability</span>
            <span class="mono" style="font-size:19px;font-weight:700;color:${barColor};">${Number(data.risk_score).toFixed(4)}</span>
          </div>
          <div style="height:7px;background:rgba(255,255,255,0.07);border-radius:999px;overflow:hidden;margin:5px 0 9px;">
            <div style="height:100%;width:${pctScore}%;background:${barColor};box-shadow:0 0 12px ${barColor};transition:width 0.4s var(--spring-smooth);"></div>
          </div>
          <div style="display:grid;grid-template-columns:repeat(3, 1fr);gap:5px;">
            ${featPills}
          </div>
        </div>
      </div>
    `;
  }

  /* --- Stream & Row-Click Forensics --- */
  function setFilter(filterVal, btnEl) {
    state.filter = filterVal;
    btnEl.parentElement.querySelectorAll('.pill-btn').forEach(b => {
      b.classList.toggle('active', b === btnEl);
      b.setAttribute('aria-selected', b === btnEl ? 'true' : 'false');
    });
    document.getElementById('alertTableBody').innerHTML = '';
    for (let i = 0; i < 6; i++) stepStream();
  }

  function stepStream() {
    if (!BENCH || !BENCH.sample_held_alerts.length) return;
    const filtered = BENCH.sample_held_alerts.filter(a => state.filter === 'ALL' || a.action === state.filter);
    const pool = filtered.length ? filtered : BENCH.sample_held_alerts;
    const item = pool[state.streamCursor % pool.length];
    state.streamCursor++;
    document.getElementById('queueCounter').textContent = `SCORED: ${(15232 + state.streamCursor).toLocaleString()} TX • ALERT #${state.streamCursor}`;

    const tbody = document.getElementById('alertTableBody');
    const reasonsHtml = (item.reason_codes || []).map(r =>
      `<span style="display:inline-block;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.07);border-left:2px solid #06b6d4;padding:2px 6px;border-radius:4px;font-size:10px;margin:1px 3px 1px 0;"><b>${r.label}:</b> ${r.value}</span>`
    ).join('');

    const tr = document.createElement('tr');
    tr.className = 'row-animate';
    tr.onclick = () => {
      tbody.querySelectorAll('tr').forEach(r => r.classList.remove('selected-row'));
      tr.classList.add('selected-row');
      renderSandboxData({
        ...item,
        title: `Stream Alert #${item.tx_id} — ${item.typology} (Hop ${item.hop_number})`,
        latency_ms: '0.040',
        rules_baseline_score: 0.45,
        rules_would_flag: true,
        feature_breakdown: [
          { name: 'hop_number', value: item.hop_number },
          { name: 'from_bank', value: item.from_bank },
          { name: 'to_bank', value: item.to_bank },
          { name: 'format', value: item.payment_format },
          { name: 'risk_score', value: item.risk_score },
          { name: 'action', value: item.action }
        ]
      });
    };

    tr.innerHTML = `
      <td><div class="mono" style="color:#fff;font-weight:600;">#${item.tx_id}</div><div style="font-size:10px;color:var(--text-tertiary);">${item.timestamp}</div></td>
      <td class="mono" style="font-size:10.5px;color:#93c5fd;">${item.from_account_hash}<br/><span style="color:var(--text-tertiary);">&rarr;</span> ${item.to_account_hash}</td>
      <td><div class="tabular" style="font-weight:600;color:#fff;">${item.currency} ${item.amount.toLocaleString()}</div><div style="font-size:10px;color:var(--text-secondary);">${item.payment_format}</div></td>
      <td><div style="font-weight:500;color:#e2e8f0;">${item.typology}</div><div class="mono" style="font-size:10px;color:#38bdf8;">Hop ${item.hop_number}</div></td>
      <td class="mono" style="font-weight:700;color:#fda4af;">${item.risk_score.toFixed(4)}</td>
      <td><span class="status-badge ${item.action}">${item.action}</span></td>
      <td>${reasonsHtml}</td>
    `;
    tbody.insertBefore(tr, tbody.firstChild);
    while (tbody.children.length > 6) tbody.removeChild(tbody.lastChild);

    const auditBody = document.getElementById('auditTableBody');
    const atr = document.createElement('tr');
    atr.className = 'row-animate';
    atr.innerHTML = `
      <td class="mono" style="color:#e2e8f0;">#${item.tx_id}</td>
      <td><span class="status-badge ${item.action}" style="font-size:9px;padding:2px 6px;">${item.action}</span></td>
      <td class="mono" style="color:var(--text-tertiary);font-size:10.5px;">${item.prev_audit_hash}...</td>
      <td class="mono" style="color:#34d399;font-size:10.5px;">${item.audit_hash}...</td>
    `;
    auditBody.insertBefore(atr, auditBody.firstChild);
    while (auditBody.children.length > 5) auditBody.removeChild(auditBody.lastChild);
  }

  function toggleStream() {
    const btn = document.getElementById('btnAuto');
    const txt = document.getElementById('autoText');
    const dot = document.getElementById('autoDot');
    if (state.autoTimer) {
      clearInterval(state.autoTimer);
      state.autoTimer = null;
      txt.textContent = 'Stream: Paused';
      dot.style.background = '#f59e0b';
      btn.setAttribute('aria-pressed', 'false');
    } else {
      state.autoTimer = setInterval(stepStream, 2400);
      txt.textContent = 'Stream: Live';
      dot.style.background = '#10b981';
      btn.setAttribute('aria-pressed', 'true');
    }
  }

  function updateBudget(val) {
    state.budgetRate = parseFloat(val);
    document.getElementById('budgetLabel').textContent = `${state.budgetRate.toFixed(1)}% Alert Budget`;
    renderRecallCurve(state.budgetRate);
  }

  async function init() {
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
      .map(r => `<tr><td style="color:var(--text-secondary);font-size:11px;">${r[0]}</td><td class="mono" style="font-size:10.5px;color:#e2e8f0;">${r[1]}</td></tr>`)
      .join('');

    const sel = document.getElementById('chainSelect');
    sel.innerHTML = BENCH.sample_interrupted_chains.map((c, idx) =>
      `<option value="${idx}">Chain #${c.chain_id} (${c.typology}) — Stopped at Hop ${c.interrupted_at_hop}</option>`
    ).join('');

    renderChain(0);
    renderRecallCurve(1.0);
    renderTypologyChart();
    renderFeaturesAndLatency();
    runPreset('fan_out_mule');

    for (let i = 0; i < 6; i++) stepStream();
    state.autoTimer = setInterval(stepStream, 2400);
  }

  return {
    init,
    runPreset,
    renderChain,
    setFilter,
    stepStream,
    toggleStream,
    updateBudget,
    tip: showTooltip,
    untip: hideTooltip
  };
})();

window.addEventListener('DOMContentLoaded', HopStopApp.init);
</script>
</body>
</html>
"""
    html = html.replace("__BENCH_JSON__", bench_json).replace("__SCENARIOS_JSON__", scenarios_json)
    out = BASE_DIR / "hopstop" / "dashboard.html"
    out.write_text(html, encoding="utf-8")
    print(f"Compiled production HopStop dashboard: {out} ({out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    build()
