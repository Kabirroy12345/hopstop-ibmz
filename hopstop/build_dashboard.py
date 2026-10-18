"""Builds hopstop/dashboard.html with embedded benchmark snapshot + live interactive simulator."""
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

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>HopStop | IBM Z & LinuxONE Real-Time Money-Mule Interdiction Console</title>
<style>
  :root {{
    --bg: #121619;
    --panel: #21272a;
    --panel-alt: #343a3f;
    --border: #4d5358;
    --text: #f4f4f4;
    --muted: #c1c7cd;
    --ibm-blue: #0f62fe;
    --ibm-cyan: #33b1ff;
    --green: #42be65;
    --amber: #f1c21b;
    --red: #fa4d56;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: "IBM Plex Sans", "Segoe UI", system-ui, sans-serif;
    font-size: 13px;
  }}
  header {{
    background: linear-gradient(90deg, #001141 0%, #001d6c 60%, #002d9c 100%);
    border-bottom: 2px solid var(--ibm-blue);
    padding: 12px 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
  }}
  .brand {{ display: flex; align-items: center; gap: 12px; }}
  .badge-z {{
    background: var(--ibm-blue);
    color: #fff;
    font-weight: 700;
    padding: 5px 10px;
    border-radius: 3px;
    font-size: 11px;
    letter-spacing: 0.6px;
    box-shadow: 0 0 10px rgba(15,98,254,0.6);
  }}
  .status-dot {{
    display: inline-block;
    width: 8px;
    height: 8px;
    background: var(--green);
    border-radius: 50%;
    margin-right: 5px;
    box-shadow: 0 0 8px var(--green);
  }}
  .title-main {{ font-size: 18px; font-weight: 700; }}
  .subtitle {{ font-size: 11.5px; color: #a6c8ff; margin-top: 2px; }}
  .controls {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
  button {{
    background: var(--ibm-blue);
    color: #fff;
    border: 1px solid transparent;
    padding: 7px 13px;
    border-radius: 3px;
    cursor: pointer;
    font-weight: 600;
    font-size: 12px;
    transition: all 0.15s;
  }}
  button.secondary {{ background: var(--panel-alt); border-color: var(--border); }}
  button.preset-btn {{ background: #002d9c; border-color: var(--ibm-cyan); }}
  button.preset-btn.active {{ background: var(--ibm-cyan); color: #001141; font-weight: 700; }}
  button:hover {{ filter: brightness(1.12); }}
  .kpi-row {{
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 10px;
    padding: 12px 20px;
  }}
  .kpi {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-top: 3px solid var(--ibm-blue);
    padding: 10px 12px;
    border-radius: 4px;
  }}
  .kpi .label {{ color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.4px; }}
  .kpi .val {{ font-size: 21px; font-weight: 700; margin: 4px 0 2px; color: #fff; }}
  .kpi .delta {{ font-size: 11px; color: var(--green); }}
  .sim-banner {{
    margin: 0 20px 12px;
    background: linear-gradient(135deg, #001d6c 0%, #161616 100%);
    border: 1.5px solid var(--ibm-cyan);
    border-radius: 5px;
    padding: 12px 16px;
  }}
  .sim-grid {{
    display: grid;
    grid-template-columns: 1.2fr 1fr;
    gap: 14px;
    margin-top: 10px;
  }}
  .grid-main {{
    display: grid;
    grid-template-columns: 1.38fr 1fr;
    gap: 12px;
    padding: 0 20px 20px;
  }}
  .card {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 12px 14px;
    margin-bottom: 12px;
  }}
  .card h3 {{
    margin: 0 0 8px;
    font-size: 12.5px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--ibm-cyan);
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  th, td {{
    padding: 6px 8px;
    border-bottom: 1px solid #343a3f;
    text-align: left;
  }}
  th {{ color: var(--muted); font-weight: 600; background: #161a1d; }}
  .pill {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 3px;
    font-weight: 700;
    font-size: 11px;
  }}
  .pill.HOLD {{ background: rgba(250,77,86,0.22); color: #ff8389; border: 1px solid var(--red); }}
  .pill.STEP_UP {{ background: rgba(241,194,27,0.2); color: #f1c21b; border: 1px solid var(--amber); }}
  .pill.ALLOW {{ background: rgba(66,190,101,0.2); color: #42be65; border: 1px solid var(--green); }}
  .pill.BLOCKED_UPSTREAM {{ background: rgba(66,190,101,0.22); color: #42be65; border: 1px solid var(--green); }}
  .reason-tag {{
    display: inline-block;
    background: #2b3238;
    border-left: 3px solid var(--ibm-cyan);
    padding: 2px 6px;
    margin: 2px 4px 2px 0;
    font-size: 10.5px;
    border-radius: 2px;
  }}
  .hop-box {{
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    padding: 10px;
    background: #161a1d;
    border-radius: 4px;
    margin-top: 6px;
  }}
  .node {{
    padding: 8px 11px;
    border-radius: 4px;
    border: 1.5px solid var(--ibm-blue);
    background: #001d6c;
    min-width: 140px;
  }}
  .node.held {{ border-color: var(--red); background: #3b0d11; }}
  .node.blocked {{ border-color: var(--green); background: #0b2e18; }}
  .arrow {{ font-size: 18px; color: var(--ibm-cyan); font-weight: bold; }}
  .bar-row {{ display: flex; align-items: center; gap: 8px; margin: 5px 0; font-size: 11.5px; }}
  .bar-name {{ width: 195px; color: var(--muted); }}
  .bar-track {{ flex: 1; background: #161a1d; height: 10px; border-radius: 2px; overflow: hidden; }}
  .bar-fill {{ background: linear-gradient(90deg, var(--ibm-blue), var(--ibm-cyan)); height: 100%; }}
  .mono {{ font-family: "IBM Plex Mono", Consolas, monospace; font-size: 11px; color: #a6c8ff; }}
</style>
</head>
<body>

<header>
  <div class="brand">
    <span class="badge-z">IBM Z / LinuxONE</span>
    <div>
      <div class="title-main"><span class="status-dot"></span>HopStop: Transaction-Time Money-Mule Interdiction Console</div>
      <div class="subtitle">Track 1: Real-Time AI for Critical Decisions &bull; Snap ML (tree_format=auto) &bull; Telum Integrated Accelerator for AI</div>
    </div>
  </div>
  <div class="controls">
    <button id="btnStream" onclick="stepStream()">+ Replay Next Stream Transfer</button>
    <button class="secondary" id="btnAuto" onclick="toggleAuto()">Auto-Stream: ON</button>
    <select id="chainSelect" onchange="renderChain(this.value)" style="background:#21272a;color:#fff;border:1px solid #4d5358;padding:6px 10px;border-radius:3px;"></select>
  </div>
</header>

<section class="kpi-row">
  <div class="kpi">
    <div class="label">End-to-End p99 Latency</div>
    <div class="val" id="kpiP99">0.202 ms</div>
    <div class="delta">50x faster than &lt;10 ms SLA (p50: 0.040 ms)</div>
  </div>
  <div class="kpi">
    <div class="label">PR-AUC (Unseen Days 8–10)</div>
    <div class="val" id="kpiPrauc">0.8317</div>
    <div class="delta">+56.7% lift vs Velocity Rules (0.5306)</div>
  </div>
  <div class="kpi">
    <div class="label">Recall @ 1.0% Alert Budget</div>
    <div class="val" id="kpiRecall">53.3%</div>
    <div class="delta">+19.8% lift over Rules Baseline (44.5%)</div>
  </div>
  <div class="kpi">
    <div class="label">Chains Stopped &le; Hop 2</div>
    <div class="val" id="kpiHop2">94.0%</div>
    <div class="delta">47/50 test chains frozen before Hop 3</div>
  </div>
  <div class="kpi">
    <div class="label">Sustained Throughput</div>
    <div class="val" id="kpiTps">109,612 TPS</div>
    <div class="delta">Micro-batch=64 | 20,366 TPS single-stream</div>
  </div>
  <div class="kpi">
    <div class="label">Audit &amp; Privacy Engine</div>
    <div class="val" style="font-size:16px;">CPACF + SHA-256</div>
    <div class="delta">Salted Account Hashes + Hash-Chained Log</div>
  </div>
</section>

<!-- INTERACTIVE LIVE SCORING SIMULATOR -->
<section class="sim-banner">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
    <div>
      <span style="color:var(--ibm-cyan);font-weight:700;text-transform:uppercase;font-size:12px;">Interactive Live Payment Scorer (Click Any Scenario to Test HopStop in Real Time):</span>
    </div>
    <div style="display:flex;gap:6px;flex-wrap:wrap;">
      <button class="preset-btn active" id="btn_fan_out_mule" onclick="runLivePreset('fan_out_mule')">1. Mule Hop-1 Fan-Out (INR 185K)</button>
      <button class="preset-btn" id="btn_gather_scatter_mule" onclick="runLivePreset('gather_scatter_mule')">2. Gather-Scatter Mule (INR 240K)</button>
      <button class="preset-btn" id="btn_step_up_borderline" onclick="runLivePreset('step_up_borderline')">3. Borderline Peer Transfer (STEP-UP)</button>
      <button class="preset-btn" id="btn_corporate_payroll" onclick="runLivePreset('corporate_payroll')">4. Legitimate Corporate Payroll (Rules False-Positive!)</button>
      <button class="preset-btn" id="btn_retail_normal" onclick="runLivePreset('retail_normal')">5. Normal Retail Payment (ALLOW)</button>
    </div>
  </div>
  <div class="sim-grid" id="liveSimResult"></div>
</section>

<div class="grid-main">
  <div>
    <div class="card">
      <h3>
        <span>Live Interdicted Transfer Queue (HOLD / STEP-UP with Top-3 Reason Codes)</span>
        <span class="mono" id="queueCounter">Streaming...</span>
      </h3>
      <table>
        <thead>
          <tr>
            <th>Tx ID</th>
            <th>Timestamp</th>
            <th>Sender &rarr; Receiver (SHA-256)</th>
            <th>Amount</th>
            <th>Typology / Hop</th>
            <th>Score</th>
            <th>Action</th>
            <th>Top-3 Reason Codes (Analyst Explainability)</th>
          </tr>
        </thead>
        <tbody id="alertTableBody"></tbody>
      </table>
    </div>

    <div class="card">
      <h3>
        <span>Multi-Hop Laundering Chain Interdiction Graph (First-Hop Freeze Proof)</span>
        <span class="mono" id="chainMeta"></span>
      </h3>
      <div id="chainGraphContainer"></div>
    </div>
  </div>

  <div>
    <div class="card">
      <h3><span>IBM Z / LinuxONE Hardware &amp; Runtime Telemetry</span></h3>
      <table>
        <tbody id="envTableBody"></tbody>
      </table>
    </div>

    <div class="card">
      <h3><span>Causal Graph-Velocity Feature Importances (Snap ML GBDT)</span></h3>
      <div id="featureBars"></div>
    </div>

    <div class="card">
      <h3><span>Tamper-Evident Hash-Chained Audit Log (FIU-IND / 1930 Helpline)</span></h3>
      <table>
        <thead>
          <tr>
            <th>Tx ID</th>
            <th>Action</th>
            <th>Prev Hash</th>
            <th>Current SHA-256 Audit Hash</th>
          </tr>
        </thead>
        <tbody id="auditTableBody"></tbody>
      </table>
    </div>
  </div>
</div>

<script>
let BENCH = {bench_json};
const EMBEDDED_SCENARIOS = {scenarios_json};
let streamCursor = 0;
let autoTimer = null;

async function initDashboard() {{
  try {{
    const res = await fetch('/api/benchmarks');
    if (res.ok) BENCH = await res.json();
  }} catch (e) {{
    // Standalone file:// mode uses embedded BENCH seamlessly
  }}

  document.getElementById('kpiP99').textContent = BENCH.latency_benchmark.batch_1_end_to_end_p99_ms + ' ms';
  document.getElementById('kpiPrauc').textContent = BENCH.model_metrics.hopstop_gbdt.pr_auc.toFixed(4);
  document.getElementById('kpiRecall').textContent = (BENCH.model_metrics.hopstop_gbdt.recall_at_1pct_alert_rate * 100).toFixed(1) + '%';
  document.getElementById('kpiHop2').textContent = BENCH.chain_interruption.hopstop_stopped_by_hop2_pct + '%';
  document.getElementById('kpiTps').textContent = BENCH.latency_benchmark.microbatch_64_scoring_tps.toLocaleString() + ' TPS';

  const env = BENCH.environment;
  const envRows = [
    ['Target Platform', 'IBM Z / LinuxONE (s390x Container Ready)'],
    ['Detected Host Arch', env.architecture + ' (' + env.os_platform + ')'],
    ['Telum NNPA Status', env.zdnn_status],
    ['Snap ML Mode', env.tree_format_mode],
    ['Crypto / Audit Engine', env.cpacf_crypto_mode],
    ['Chronological Split', `${{BENCH.dataset.train_transactions.toLocaleString()}} train (Days 1-7) / ${{BENCH.dataset.test_transactions.toLocaleString()}} test (Days 8-10)`]
  ];
  document.getElementById('envTableBody').innerHTML = envRows.map(r => `<tr><td style="color:#c1c7cd;">${{r[0]}}</td><td class="mono">${{r[1]}}</td></tr>`).join('');

  const maxW = Math.max(...BENCH.feature_importances.map(f => f.weight), 0.01);
  document.getElementById('featureBars').innerHTML = BENCH.feature_importances.slice(0, 8).map(f => `
    <div class="bar-row">
      <div class="bar-name">${{f.label}}</div>
      <div class="bar-track"><div class="bar-fill" style="width:${{(f.weight / maxW * 100).toFixed(0)}}%"></div></div>
      <div class="mono" style="width:45px;text-align:right;">${{(f.weight * 100).toFixed(1)}}%</div>
    </div>
  `).join('');

  const sel = document.getElementById('chainSelect');
  sel.innerHTML = BENCH.sample_interrupted_chains.map((c, idx) =>
    `<option value="${{idx}}">Chain #${{c.chain_id}} (${{c.typology}}) - Stopped at Hop ${{c.interrupted_at_hop}}</option>`
  ).join('');
  renderChain(0);
  runLivePreset('fan_out_mule');

  for (let i = 0; i < 6; i++) stepStream();
  autoTimer = setInterval(stepStream, 2200);
}}

async function runLivePreset(type) {{
  document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
  const activeBtn = document.getElementById('btn_' + type);
  if (activeBtn) activeBtn.classList.add('active');

  let data = EMBEDDED_SCENARIOS[type];
  try {{
    const res = await fetch('/api/score_preset?type=' + encodeURIComponent(type));
    if (res.ok) data = await res.json();
  }} catch (e) {{}}
  if (!data) return;

  const reasonsHtml = (data.reason_codes && data.reason_codes.length)
    ? data.reason_codes.map(r => `<span class="reason-tag"><b>${{r.label}}:</b> ${{r.value}} (impact ${{r.impact}})</span>`).join('')
    : '<span class="mono" style="color:#42be65;">No anomalous risk factors triggered (Clean Transfer)</span>';

  const rulesComp = data.rules_would_flag
    ? `<span style="color:#f1c21b;">Static Rules Score: ${{data.rules_baseline_score}} (Flagged)</span>`
    : `<span style="color:#c1c7cd;">Static Rules Score: ${{data.rules_baseline_score}} (Passed)</span>`;

  const topFeats = (data.feature_breakdown || []).slice(0, 6).map(f =>
    `<span class="mono" style="background:#161a1d;padding:2px 6px;border-radius:3px;border:1px solid #343a3f;">${{f.name}}: <b>${{f.value}}</b></span>`
  ).join(' ');

  document.getElementById('liveSimResult').innerHTML = `
    <div style="background:#161a1d;padding:10px 12px;border-radius:4px;border:1px solid #343a3f;">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <b style="font-size:13.5px;color:#fff;">${{data.title}}</b>
        <span class="pill ${{data.action}}" style="font-size:12.5px;padding:4px 10px;">DECISION: ${{data.action}}</span>
      </div>
      <div style="margin:6px 0;color:#c1c7cd;font-size:12px;">
        Sender: <span class="mono">${{data.from_account_hash}}</span> (Bank ${{data.from_bank}}) &rarr;
        Receiver: <span class="mono">${{data.to_account_hash}}</span> (Bank ${{data.to_bank}}) &bull;
        Amount: <b>${{data.currency}} ${{data.amount.toLocaleString()}} (${{data.payment_format}})</b>
      </div>
      <div style="margin-top:6px;"><b>Top-3 Reason Codes:</b> ${{reasonsHtml}}</div>
    </div>
    <div style="background:#161a1d;padding:10px 12px;border-radius:4px;border:1px solid #343a3f;display:flex;flex-direction:column;justify-content:space-between;">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <span><b>HopStop GBDT Score:</b> <span class="mono" style="font-size:15px;color:#33b1ff;font-weight:700;">${{data.risk_score}}</span></span>
        <span><b>Measured Latency:</b> <span class="mono" style="color:#42be65;font-weight:700;">${{data.latency_ms}} ms</span></span>
        ${{rulesComp}}
      </div>
      <div style="margin:6px 0;display:flex;flex-wrap:wrap;gap:4px;">${{topFeats}}</div>
      <div class="mono" style="font-size:10.5px;color:#8d8d8d;">
        Audit Chain: prev=${{data.prev_audit_hash}}... &rarr; sha256=${{data.audit_hash}}...
      </div>
    </div>
  `;
}}

function renderChain(idx) {{
  const c = BENCH.sample_interrupted_chains[idx];
  if (!c) return;
  document.getElementById('chainMeta').textContent = `Chain #${{c.chain_id}} | Typology: ${{c.typology}} | Interdicted at Hop ${{c.interrupted_at_hop}}`;
  const html = c.hops.map((h, i) => {{
    const cls = h.decision === 'BLOCKED_UPSTREAM' ? 'node blocked' : (h.decision === 'HOLD' || h.decision === 'STEP_UP' ? 'node held' : 'node');
    return `
      <div class="${{cls}}">
        <div style="font-weight:700;font-size:11px;">Hop ${{h.hop}}: ${{h.from_account}} &rarr; ${{h.to_account}}</div>
        <div style="font-size:11px;color:#c1c7cd;">Bank ${{h.from_bank}}&rarr;${{h.to_bank}} &bull; INR ${{h.amount.toLocaleString()}}</div>
        <div style="margin-top:4px;"><span class="pill ${{h.decision}}">${{h.decision}}</span> <span class="mono">Score: ${{h.risk_score}}</span></div>
      </div>
      ${{i < c.hops.length - 1 ? '<div class="arrow">&rarr;</div>' : ''}}
    `;
  }}).join('');
  document.getElementById('chainGraphContainer').innerHTML = `<div class="hop-box">${{html}}</div>`;
}}

function stepStream() {{
  if (!BENCH || !BENCH.sample_held_alerts.length) return;
  const alerts = BENCH.sample_held_alerts;
  const item = alerts[streamCursor % alerts.length];
  streamCursor++;
  document.getElementById('queueCounter').textContent = `Processed: ${{(15232 + streamCursor).toLocaleString()}} tx | Active Alert #${{streamCursor}}`;

  const tbody = document.getElementById('alertTableBody');
  const reasonsHtml = (item.reason_codes || []).map(r =>
    `<span class="reason-tag"><b>${{r.label}}:</b> ${{r.value}}</span>`
  ).join('');

  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td class="mono">#${{item.tx_id}}</td>
    <td>${{item.timestamp}}</td>
    <td class="mono">${{item.from_account_hash}}<br/>&rarr; ${{item.to_account_hash}}</td>
    <td><b>${{item.currency}} ${{item.amount.toLocaleString()}}</b><br/><span style="color:#a6c8ff;font-size:10.5px;">${{item.payment_format}}</span></td>
    <td>${{item.typology}}<br/><span class="mono">Hop ${{item.hop_number}}</span></td>
    <td class="mono" style="font-weight:700;color:#ff8389;">${{item.risk_score.toFixed(4)}}</td>
    <td><span class="pill ${{item.action}}">${{item.action}}</span></td>
    <td>${{reasonsHtml}}</td>
  `;
  tbody.insertBefore(tr, tbody.firstChild);
  while (tbody.children.length > 6) tbody.removeChild(tbody.lastChild);

  const auditBody = document.getElementById('auditTableBody');
  const atr = document.createElement('tr');
  atr.innerHTML = `
    <td class="mono">#${{item.tx_id}}</td>
    <td><span class="pill ${{item.action}}">${{item.action}}</span></td>
    <td class="mono">${{item.prev_audit_hash}}...</td>
    <td class="mono" style="color:#42be65;">${{item.audit_hash}}...</td>
  `;
  auditBody.insertBefore(atr, auditBody.firstChild);
  while (auditBody.children.length > 5) auditBody.removeChild(auditBody.lastChild);
}}

function toggleAuto() {{
  const btn = document.getElementById('btnAuto');
  if (autoTimer) {{
    clearInterval(autoTimer);
    autoTimer = null;
    btn.textContent = 'Auto-Stream: OFF';
  }} else {{
    autoTimer = setInterval(stepStream, 2200);
    btn.textContent = 'Auto-Stream: ON';
  }}
}}

window.addEventListener('DOMContentLoaded', initDashboard);
</script>
</body>
</html>
"""
    out = BASE_DIR / "hopstop" / "dashboard.html"
    out.write_text(html, encoding="utf-8")
    print(f"Built self-contained + live dashboard: {out} ({out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    build()
