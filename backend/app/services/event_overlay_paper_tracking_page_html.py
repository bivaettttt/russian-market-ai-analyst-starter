from __future__ import annotations


def build_event_overlay_paper_tracking_page_html() -> str:
    return """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Conservative Overlay Paper Tracking</title>
  <style>
    body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #17202a; background: #f6f8fb; }
    header { padding: 18px 24px; background: #101820; color: white; }
    main { max-width: 1180px; margin: 0 auto; padding: 20px; }
    a { color: #0f62fe; text-decoration: none; }
    .nav a { color: #dbeafe; margin-right: 14px; }
    .panel { background: white; border: 1px solid #dde3ea; border-radius: 8px; padding: 16px; margin: 14px 0; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; }
    .card { border: 1px solid #e1e7ef; border-radius: 8px; padding: 12px; background: #fbfcfe; }
    .label { color: #667085; font-size: 12px; }
    .value { font-size: 20px; font-weight: 700; margin-top: 4px; }
    label { display: block; font-size: 12px; color: #475467; margin-bottom: 4px; }
    input, select, button { font: inherit; padding: 8px 10px; border: 1px solid #cbd5e1; border-radius: 6px; background: white; }
    button { cursor: pointer; background: #0f62fe; color: white; border-color: #0f62fe; }
    button.secondary { background: white; color: #0f62fe; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { border-bottom: 1px solid #e5e7eb; padding: 8px; text-align: left; vertical-align: top; }
    th { color: #475467; font-size: 12px; }
    .muted { color: #667085; }
    .danger { color: #b42318; }
    .ok { color: #027a48; }
    .controls { display: flex; gap: 10px; flex-wrap: wrap; align-items: end; }
    .controls > div { min-width: 140px; }
    pre { white-space: pre-wrap; overflow: auto; background: #0b1220; color: #dbeafe; padding: 12px; border-radius: 8px; }
  </style>
</head>
<body>
  <header>
    <h1>Conservative Overlay Paper Tracking</h1>
    <div class="nav">
      <a href="/signals">Signals</a>
      <a href="/signals/daily-ops/page">Daily Ops</a>
      <a href="/signals/event-aware/conservative-overlay-paper-page">Paper snapshot</a>
      <a href="/signals/event-aware/conservative-overlay-quality-report-page">Quality report</a>
      <a href="/signals/event-aware/risk-overlay-conservative-page">Conservative calibration</a>
      <a href="/signals/event-aware/risk-overlay-page">Risk overlay</a>
    </div>
  </header>
  <main>
    <section class="panel">
      <h2>Create Snapshot</h2>
      <div class="controls">
        <div><label>Name</label><input id="name" value="paper-tracking"></div>
        <div><label>Limit</label><input id="limit" type="number" min="1" max="500" value="100"></div>
        <div><label>Candles</label><input id="candles" type="number" min="60" max="1000" value="240"></div>
        <div><label>Horizon days</label><input id="horizon" type="number" min="1" max="120" value="20"></div>
        <div><label>Mode</label><select id="mode"><option>soft_adjust</option><option>diagnostic_only</option></select></div>
        <button onclick="createSnapshot()">Create Snapshot</button>
        <button class="secondary" onclick="loadAll()">Refresh</button>
      </div>
      <p class="muted">Writes only to local paper-tracking tables. No real trades and no production default changes.</p>
    </section>

    <section class="panel">
      <h2>Lifecycle Status</h2>
      <div id="lifecycleCards" class="grid"></div>
      <div class="controls" style="margin-top:12px;">
        <button onclick="evaluateReady()">Evaluate Ready Snapshots</button>
        <button class="secondary" onclick="loadAll()">Refresh Dashboard</button>
        <a href="/signals/event-aware/conservative-overlay-paper-snapshots.csv?limit=100">Snapshots CSV</a>
        <a href="/signals/event-aware/conservative-overlay-paper-dashboard.csv">Dashboard CSV</a>
        <a href="/signals/event-aware/conservative-overlay-quality-report.csv?limit=30">Quality CSV</a>
      </div>
    </section>

    <section class="panel">
      <h2>Dashboard</h2>
      <div id="cards" class="grid"></div>
    </section>

    <section class="panel">
      <h2>Cumulative Curve</h2>
      <table>
        <thead><tr><th>Date</th><th>Snapshot</th><th>Baseline</th><th>Overlay</th><th>Delta</th></tr></thead>
        <tbody id="curveRows"></tbody>
      </table>
    </section>

    <section class="panel">
      <h2>By Risk Level</h2>
      <table>
        <thead><tr><th>Risk</th><th>Items</th><th>Evaluated</th><th>Baseline</th><th>Overlay</th><th>Delta</th><th>Avg multiplier</th></tr></thead>
        <tbody id="riskRows"></tbody>
      </table>
    </section>

    <section class="panel">
      <h2>Snapshots</h2>
      <table>
        <thead><tr><th>ID</th><th>Date</th><th>Status</th><th>Exposure</th><th>Multiplier</th><th>Evaluation</th><th>Actions</th></tr></thead>
        <tbody id="snapshotRows"></tbody>
      </table>
    </section>

    <section class="panel">
      <h2>Detail</h2>
      <div id="detailSummary" class="muted">Select a snapshot.</div>
      <table>
        <thead><tr><th>Ticker</th><th>Action</th><th>Size</th><th>Risk</th><th>Return</th><th>Baseline PnL</th><th>Overlay PnL</th><th>Delta</th></tr></thead>
        <tbody id="detailRows"></tbody>
      </table>
    </section>

    <section class="panel">
      <h2>Warnings</h2>
      <ul>
        <li>Research/paper trading only.</li>
        <li>No real trading operations are created.</li>
        <li>Evaluation uses local candles and close-to-close proxy logic.</li>
        <li>No investment advice.</li>
      </ul>
      <pre id="status">Ready.</pre>
    </section>
  </main>
<script>
function fmt(value, suffix = "") {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return Number(value).toFixed(3).replace(/\\.000$/, "") + suffix;
}
function setStatus(value) { document.getElementById("status").textContent = value; }
async function fetchJson(url, options) {
  const res = await fetch(url, options || {});
  const text = await res.text();
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${text}`);
  return JSON.parse(text);
}
function renderDashboard(data) {
  const s = data.summary || {};
  const cards = [
    ["Snapshots", s.total_snapshots ?? s.snapshots],
    ["Open", s.open_snapshots],
    ["Ready", s.ready_to_evaluate_snapshots],
    ["Evaluated", s.evaluated_snapshots],
    ["Baseline PnL", fmt(s.baseline_total_pnl_pct ?? s.aggregate_baseline_pnl_pct, "%")],
    ["Overlay PnL", fmt(s.overlay_total_pnl_pct ?? s.aggregate_overlay_pnl_pct, "%")],
    ["Delta", fmt(s.overlay_delta_pnl_pct ?? s.aggregate_overlay_delta_pnl_pct, "%")],
    ["Avg multiplier", fmt(s.avg_multiplier)],
    ["Recommendation", s.recommendation || "—"],
  ];
  document.getElementById("cards").innerHTML = cards.map(([label, value]) => `<div class="card"><div class="label">${label}</div><div class="value">${value ?? "—"}</div></div>`).join("");
  document.getElementById("curveRows").innerHTML = (data.cumulative_curve || []).map(row => `<tr>
    <td>${row.date || "—"}</td><td>#${row.snapshot_id}</td>
    <td>${fmt(row.cumulative_baseline_pnl, "%")}</td>
    <td>${fmt(row.cumulative_overlay_pnl, "%")}</td>
    <td>${fmt(row.cumulative_delta, "%")}</td>
  </tr>`).join("") || `<tr><td colspan="5" class="muted">No evaluated curve yet.</td></tr>`;
  const risk = data.by_risk_level || {};
  document.getElementById("riskRows").innerHTML = Object.keys(risk).sort().map(level => {
    const row = risk[level] || {};
    return `<tr><td>${level}</td><td>${row.items || 0}</td><td>${row.evaluated_items || 0}</td>
      <td>${fmt(row.baseline_realized_pnl_pct, "%")}</td>
      <td>${fmt(row.overlay_realized_pnl_pct, "%")}</td>
      <td>${fmt(row.overlay_delta_pnl_pct, "%")}</td>
      <td>${fmt(row.avg_multiplier)}</td></tr>`;
  }).join("") || `<tr><td colspan="7" class="muted">No risk breakdown yet.</td></tr>`;
}
function renderLifecycle(data) {
  const s = data.summary || {};
  const cards = [
    ["Total", s.total_snapshots],
    ["Open", s.open_snapshots],
    ["Ready", s.ready_to_evaluate_snapshots],
    ["Evaluated", s.evaluated_snapshots],
    ["Last date", s.last_snapshot_date || "—"],
    ["Next action", s.recommended_action || "—"],
  ];
  document.getElementById("lifecycleCards").innerHTML = cards.map(([label, value]) => `<div class="card"><div class="label">${label}</div><div class="value">${value ?? "—"}</div></div>`).join("");
}
function renderSnapshots(data) {
  const rows = data.rows || [];
  const today = new Date().toISOString().slice(0, 10);
  document.getElementById("snapshotRows").innerHTML = rows.map(row => {
    const ev = (row.summary || {}).evaluation || {};
    const ready = ["open", "partially_evaluated"].includes(row.status) && row.snapshot_date && row.horizon_days && row.snapshot_date <= today;
    return `<tr>
      <td>#${row.id}</td>
      <td>${row.snapshot_date || "—"}</td>
      <td>${ready ? "ready" : (row.status || "—")}</td>
      <td>${fmt(row.baseline_total_exposure, "%")} → ${fmt(row.overlay_total_exposure, "%")}</td>
      <td>${fmt(row.avg_multiplier)}</td>
      <td>Δ ${fmt(ev.overlay_delta_pnl_pct, "%")}</td>
      <td>
        <button class="secondary" onclick="loadDetail(${row.id})">Detail</button>
        <button onclick="evaluateSnapshot(${row.id})">Evaluate</button>
        <button class="secondary" onclick="deleteSnapshot(${row.id})">Delete</button>
        <a href="/signals/event-aware/conservative-overlay-paper-snapshots/${row.id}.csv">CSV</a>
      </td>
    </tr>`;
  }).join("") || `<tr><td colspan="7" class="muted">No snapshots yet.</td></tr>`;
}
function renderDetail(data) {
  const summary = data.summary || {};
  document.getElementById("detailSummary").textContent =
    `Items ${summary.items || 0}, evaluated ${summary.evaluated_items || 0}, baseline ${fmt(summary.baseline_realized_pnl_pct, "%")}, overlay ${fmt(summary.overlay_realized_pnl_pct, "%")}, delta ${fmt(summary.overlay_delta_pnl_pct, "%")}`;
  document.getElementById("detailRows").innerHTML = (data.items || []).slice(0, 100).map(row => `<tr>
    <td>${row.ticker}</td>
    <td>${row.action || "—"}</td>
    <td>${fmt(row.base_position_size_pct, "%")} → ${fmt(row.overlay_position_size_pct, "%")}</td>
    <td>${row.event_risk_level || "—"} · ${fmt(row.event_risk_score)}</td>
    <td>${fmt(row.realized_return_pct, "%")}</td>
    <td>${fmt(row.baseline_realized_pnl_pct, "%")}</td>
    <td>${fmt(row.overlay_realized_pnl_pct, "%")}</td>
    <td>${fmt(row.overlay_delta_pnl_pct, "%")}</td>
  </tr>`).join("") || `<tr><td colspan="8" class="muted">No rows.</td></tr>`;
}
async function loadAll() {
  try {
    const lifecycle = await fetchJson("/signals/event-aware/conservative-overlay-paper-lifecycle-status");
    renderLifecycle(lifecycle);
    const dash = await fetchJson("/signals/event-aware/conservative-overlay-paper-dashboard?limit=20");
    renderDashboard(dash);
    const list = await fetchJson("/signals/event-aware/conservative-overlay-paper-snapshots?limit=50");
    renderSnapshots(list);
    setStatus("Loaded.");
  } catch (err) {
    setStatus(String(err));
  }
}
async function evaluateReady() {
  try {
    const data = await fetchJson("/signals/event-aware/conservative-overlay-paper-evaluate-ready?limit=50", { method: "POST" });
    setStatus(JSON.stringify(data, null, 2));
    await loadAll();
  } catch (err) {
    setStatus(String(err));
  }
}
async function createSnapshot() {
  try {
    const p = new URLSearchParams();
    p.set("name", document.getElementById("name").value || "paper-tracking");
    p.set("limit", document.getElementById("limit").value || "100");
    p.set("candles_limit", document.getElementById("candles").value || "240");
    p.set("horizon_days", document.getElementById("horizon").value || "20");
    p.set("overlay_mode", document.getElementById("mode").value || "soft_adjust");
    const data = await fetchJson(`/signals/event-aware/conservative-overlay-paper-snapshots?${p.toString()}`, { method: "POST" });
    setStatus(JSON.stringify(data, null, 2));
    await loadAll();
    if (data.snapshot_id) await loadDetail(data.snapshot_id);
  } catch (err) {
    setStatus(String(err));
  }
}
async function deleteSnapshot(id) {
  if (!confirm(`Delete paper snapshot #${id}?`)) return;
  try {
    const data = await fetchJson(`/signals/event-aware/conservative-overlay-paper-snapshots/${id}`, { method: "DELETE" });
    setStatus(JSON.stringify(data, null, 2));
    await loadAll();
  } catch (err) {
    setStatus(String(err));
  }
}
async function loadDetail(id) {
  try {
    const data = await fetchJson(`/signals/event-aware/conservative-overlay-paper-snapshots/${id}`);
    renderDetail(data);
    setStatus(`Loaded snapshot #${id}.`);
  } catch (err) {
    setStatus(String(err));
  }
}
async function evaluateSnapshot(id) {
  try {
    const data = await fetchJson(`/signals/event-aware/conservative-overlay-paper-snapshots/${id}/evaluate`, { method: "POST" });
    setStatus(JSON.stringify(data.summary || data, null, 2));
    await loadAll();
    await loadDetail(id);
  } catch (err) {
    setStatus(String(err));
  }
}
loadAll();
</script>
</body>
</html>
"""
