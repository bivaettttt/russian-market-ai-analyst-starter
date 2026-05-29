from __future__ import annotations


def build_event_overlay_quality_report_page_html() -> str:
    return """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Conservative Overlay Quality Report</title>
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
    input, button { font: inherit; padding: 8px 10px; border: 1px solid #cbd5e1; border-radius: 6px; background: white; }
    button { cursor: pointer; background: #0f62fe; color: white; border-color: #0f62fe; }
    button.secondary { background: white; color: #0f62fe; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { border-bottom: 1px solid #e5e7eb; padding: 8px; text-align: left; vertical-align: top; }
    th { color: #475467; font-size: 12px; }
    .muted { color: #667085; }
    .badge { display: inline-flex; border-radius: 999px; padding: 5px 9px; font-size: 12px; font-weight: 800; background: #ecfdf5; color: #047857; border: 1px solid #bbf7d0; }
    .warning { background: #fffbeb; border: 1px solid #fde68a; color: #92400e; border-radius: 8px; padding: 10px 12px; margin-top: 10px; }
    .controls { display: flex; gap: 10px; flex-wrap: wrap; align-items: end; }
    .controls > div { min-width: 140px; }
    pre { white-space: pre-wrap; overflow: auto; background: #0b1220; color: #dbeafe; padding: 12px; border-radius: 8px; }
  </style>
</head>
<body>
  <header>
    <h1>Paper Validation Alpha · Conservative Event Overlay Quality Report</h1>
    <div class="nav">
      <a href="/signals">Signals</a>
      <a href="/signals/daily-ops/page">Daily Ops</a>
      <a href="/signals/event-aware/conservative-overlay-paper-tracking-page">Overlay tracking</a>
      <a href="/signals/event-aware/conservative-overlay-paper-page">Paper snapshot</a>
      <a href="/signals/event-aware/risk-overlay-conservative-page">Conservative calibration</a>
      <a href="/signals/event-aware/conservative-overlay-quality-report.csv?limit=30">Quality CSV</a>
    </div>
  </header>
  <main>
    <section class="panel">
      <h2>Actions</h2>
      <div class="controls">
        <div><label>Daily name</label><input id="dailyName" value="daily"></div>
        <div><label>Limit</label><input id="limit" type="number" min="1" max="500" value="100"></div>
        <div><label>Horizon days</label><input id="horizon" type="number" min="1" max="120" value="20"></div>
        <label><input id="officialOnly" type="checkbox" checked> Official only</label>
        <label><input id="includeTest" type="checkbox"> Include test</label>
        <label><input id="includeLegacy" type="checkbox"> Include legacy</label>
        <button onclick="runDaily()">Run Daily</button>
        <button onclick="evaluateReady()">Evaluate Ready</button>
        <button onclick="createSnapshot()">Create Snapshot</button>
        <button class="secondary" onclick="loadAll()">Refresh</button>
        <a href="/signals/event-aware/conservative-overlay-paper-dashboard.csv">Dashboard CSV</a>
        <a href="/signals/event-aware/conservative-overlay-paper-snapshots.csv?limit=100">Snapshots CSV</a>
      </div>
    </section>

    <section class="panel">
      <h2>Health</h2>
      <div><span class="badge" id="viewBadge">Official validation view</span></div>
      <div id="healthCards" class="grid"></div>
      <div id="officialNotice" class="warning" style="display:none;"></div>
    </section>

    <section class="panel">
      <h2>Main Metrics</h2>
      <div id="metricCards" class="grid"></div>
    </section>

    <section class="panel">
      <h2>Notification Summary</h2>
      <div id="notification" class="muted"></div>
    </section>

    <section class="panel">
      <h2>Cumulative Curve</h2>
      <table><thead><tr><th>Date</th><th>Snapshot</th><th>Baseline</th><th>Overlay</th><th>Delta</th></tr></thead><tbody id="curveRows"></tbody></table>
    </section>

    <section class="panel">
      <h2>By Risk Level</h2>
      <table><thead><tr><th>Risk</th><th>Items</th><th>Baseline</th><th>Overlay</th><th>Delta</th><th>Avg multiplier</th><th>Win rate</th></tr></thead><tbody id="riskRows"></tbody></table>
    </section>

    <section class="panel">
      <h2>Top Contributors</h2>
      <div class="grid">
        <div><h3>Positive</h3><table><tbody id="positiveRows"></tbody></table></div>
        <div><h3>Negative</h3><table><tbody id="negativeRows"></tbody></table></div>
      </div>
    </section>

    <section class="panel">
      <h2>Problem Tickers</h2>
      <table><thead><tr><th>Ticker</th><th>Items</th><th>Negative delta</th><th>Missed upside</th><th>Delta</th><th>Avg multiplier</th></tr></thead><tbody id="problemRows"></tbody></table>
    </section>

    <section class="panel">
      <h2>Limitations</h2>
      <ul>
        <li>Paper tracking only; no real trades are created.</li>
        <li>Evaluation requires future local candles.</li>
        <li>Close-to-close outcomes are validation proxies.</li>
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
function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
async function fetchJson(url, options) {
  const res = await fetch(url, options || {});
  const text = await res.text();
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${text}`);
  return JSON.parse(text);
}
function setStatus(value) { document.getElementById("status").textContent = value; }
function card(label, value) { return `<div class="card"><div class="label">${esc(label)}</div><div class="value">${esc(value ?? "—")}</div></div>`; }
function filterParams() {
  const p = new URLSearchParams();
  p.set("official_only", officialOnly.checked ? "true" : "false");
  p.set("include_test", includeTest.checked ? "true" : "false");
  p.set("include_legacy", includeLegacy.checked ? "true" : "false");
  return p;
}
function renderReport(data) {
  const s = data.summary || {};
  viewBadge.textContent = (s.filters || {}).official_only ? "Official validation view" : "All snapshots view";
  const warnings = data.warnings || [];
  officialNotice.style.display = warnings.length ? "block" : "none";
  officialNotice.textContent = warnings.includes("official_only_view")
    ? "Official-only report excludes test and legacy snapshots. Use filters to inspect all local paper data."
    : warnings.join(", ");
  const cards = [
    ["Snapshots", s.snapshots_total],
    ["Open", s.snapshots_open],
    ["Ready", s.snapshots_ready],
    ["Evaluated items", s.items_evaluated],
    ["Baseline PnL", fmt(s.baseline_total_pnl_pct, "%")],
    ["Overlay PnL", fmt(s.overlay_total_pnl_pct, "%")],
    ["Delta", fmt(s.overlay_delta_pnl_pct, "%")],
    ["Avg multiplier", fmt(s.avg_multiplier)],
    ["Quality", s.quality_label],
    ["Next action", s.recommended_action],
  ];
  metricCards.innerHTML = cards.map(x => card(x[0], x[1])).join("");
  curveRows.innerHTML = (data.cumulative_curve || []).map(row => `<tr>
    <td>${esc(row.snapshot_date)}</td><td>#${esc(row.snapshot_id)}</td>
    <td>${fmt(row.baseline_cumulative_pnl_pct, "%")}</td>
    <td>${fmt(row.overlay_cumulative_pnl_pct, "%")}</td>
    <td>${fmt(row.delta_cumulative_pnl_pct, "%")}</td>
  </tr>`).join("") || `<tr><td colspan="5" class="muted">No evaluated curve yet.</td></tr>`;
  riskRows.innerHTML = (data.by_risk_level || []).map(row => `<tr>
    <td>${esc(row.risk_level)}</td><td>${esc(row.items)}</td>
    <td>${fmt(row.baseline_pnl_pct, "%")}</td><td>${fmt(row.overlay_pnl_pct, "%")}</td>
    <td>${fmt(row.delta_pnl_pct, "%")}</td><td>${fmt(row.avg_multiplier)}</td><td>${fmt(row.win_rate_pct, "%")}</td>
  </tr>`).join("") || `<tr><td colspan="7" class="muted">No risk-level data.</td></tr>`;
  const contrib = row => `<tr><td>${esc(row.ticker)}</td><td>${fmt(row.overlay_delta_pnl_pct, "%")}</td><td>${fmt(row.realized_return_pct, "%")}</td><td>${esc(row.event_risk_level)}</td></tr>`;
  positiveRows.innerHTML = (data.top_positive_contributors || []).slice(0, 10).map(contrib).join("") || `<tr><td class="muted">No positive contributors yet.</td></tr>`;
  negativeRows.innerHTML = (data.top_negative_contributors || []).slice(0, 10).map(contrib).join("") || `<tr><td class="muted">No negative contributors yet.</td></tr>`;
  problemRows.innerHTML = (data.problem_tickers || []).map(row => `<tr>
    <td>${esc(row.ticker)}</td><td>${esc(row.items)}</td><td>${esc(row.negative_delta_count)}</td>
    <td>${esc(row.missed_upside_count)}</td><td>${fmt(row.delta_pnl_pct, "%")}</td><td>${fmt(row.avg_multiplier)}</td>
  </tr>`).join("") || `<tr><td colspan="6" class="muted">No problem tickers yet.</td></tr>`;
}
function renderHealth(data) {
  const s = data.summary || {};
  healthCards.innerHTML = [
    ["Last candle", s.last_market_candle_date],
    ["Stale", s.market_data_stale],
    ["Snapshots", s.total_snapshots],
    ["Ready", s.ready_snapshots],
    ["Events", s.event_count],
    ["Action", data.recommended_action],
  ].map(x => card(x[0], x[1])).join("");
}
async function loadAll() {
  try {
    const health = await fetchJson("/signals/event-aware/conservative-overlay-data-health");
    renderHealth(health);
    const params = filterParams();
    params.set("limit", "30");
    const report = await fetchJson(`/signals/event-aware/conservative-overlay-quality-report?${params.toString()}`);
    renderReport(report);
    const notificationParams = filterParams();
    notificationParams.set("limit", "30");
    const notificationData = await fetchJson(`/signals/event-aware/conservative-overlay-notification-summary?${notificationParams.toString()}`);
    notification.innerHTML = `<strong>${esc(notificationData.status)}</strong>: ${esc(notificationData.message)}<br>Next action: ${esc(notificationData.recommended_action)}`;
    setStatus("Loaded.");
  } catch (err) {
    setStatus(String(err));
  }
}
async function runDaily() {
  const p = new URLSearchParams();
  p.set("name", dailyName.value || "daily");
  p.set("limit", limit.value || "100");
  p.set("horizon_days", horizon.value || "20");
  p.set("evaluate_ready", "true");
  p.set("dedupe_same_day", "true");
  const data = await fetchJson(`/signals/event-aware/conservative-overlay-daily-run?${p.toString()}`, { method: "POST" });
  setStatus(JSON.stringify(data, null, 2));
  await loadAll();
}
async function evaluateReady() {
  const params = filterParams();
  params.set("limit", "50");
  const data = await fetchJson(`/signals/event-aware/conservative-overlay-paper-evaluate-ready?${params.toString()}`, { method: "POST" });
  setStatus(JSON.stringify(data, null, 2));
  await loadAll();
}
async function createSnapshot() {
  const p = new URLSearchParams();
  p.set("name", dailyName.value || "daily");
  p.set("limit", limit.value || "100");
  p.set("horizon_days", horizon.value || "20");
  p.set("dedupe_same_day", "true");
  const data = await fetchJson(`/signals/event-aware/conservative-overlay-paper-snapshots?${p.toString()}`, { method: "POST" });
  setStatus(JSON.stringify(data, null, 2));
  await loadAll();
}
loadAll();
</script>
</body>
</html>
"""
