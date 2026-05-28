from __future__ import annotations


def build_live_paper_validation_page_html() -> str:
    return """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Live Paper Validation Start</title>
  <style>
    body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f6f8fb; color: #17202a; }
    header { padding: 18px 24px; background: #101820; color: white; }
    main { max-width: 1180px; margin: 0 auto; padding: 20px; }
    a { color: #0f62fe; text-decoration: none; }
    .nav a { color: #dbeafe; margin-right: 14px; }
    .panel { background: white; border: 1px solid #dde3ea; border-radius: 8px; padding: 16px; margin: 14px 0; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; }
    .card { border: 1px solid #e1e7ef; border-radius: 8px; padding: 12px; background: #fbfcfe; }
    .label { color: #667085; font-size: 12px; }
    .value { font-size: 20px; font-weight: 700; margin-top: 4px; }
    button, input { font: inherit; padding: 8px 10px; border: 1px solid #cbd5e1; border-radius: 6px; background: white; }
    button { cursor: pointer; background: #0f62fe; color: white; border-color: #0f62fe; }
    button.secondary { background: white; color: #0f62fe; }
    .controls { display: flex; gap: 10px; flex-wrap: wrap; align-items: end; }
    pre { white-space: pre-wrap; overflow: auto; background: #0b1220; color: #dbeafe; padding: 12px; border-radius: 8px; }
  </style>
</head>
<body>
  <header>
    <h1>Live Paper Validation Start</h1>
    <div class="nav">
      <a href="/signals/daily-ops/page">Daily Ops</a>
      <a href="/signals/daily-ops/market-refresh-report-page">Market Refresh Report</a>
      <a href="/signals/event-aware/conservative-overlay-quality-report-page">Quality Report</a>
      <a href="/signals/event-aware/conservative-overlay-paper-tracking-page">Paper Tracking</a>
    </div>
  </header>
  <main>
    <section class="panel"><h2>Status</h2><div id="cards" class="grid"></div></section>
    <section class="panel">
      <h2>Official Start</h2>
      <div class="controls">
        <label>Name <input id="name" value="official-daily"></label>
        <label>Limit <input id="limit" type="number" min="1" max="500" value="100"></label>
        <label>Horizon <input id="horizon" type="number" min="1" max="120" value="20"></label>
        <label><input id="requireFresh" type="checkbox" checked> require fresh data</label>
        <button onclick="dryRun()">Dry run official start</button>
        <button onclick="start(true)">Start official validation</button>
        <button class="secondary" onclick="start(false)">Start without refresh</button>
        <button class="secondary" onclick="loadStatus()">Refresh</button>
      </div>
    </section>
    <section class="panel">
      <h2>Result</h2>
      <pre id="output">Ready.</pre>
    </section>
    <section class="panel">
      <h2>Caveats</h2>
      <ul>
        <li>Paper validation only.</li>
        <li>No real trades are created.</li>
        <li>Fresh market data is required by default for official snapshots.</li>
        <li>No investment advice.</li>
      </ul>
    </section>
  </main>
<script>
function esc(value) { return String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])); }
function card(label, value) { return `<div class="card"><div class="label">${esc(label)}</div><div class="value">${esc(value ?? "—")}</div></div>`; }
async function fetchJson(url, options) {
  const res = await fetch(url, options || {});
  const text = await res.text();
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${text}`);
  return JSON.parse(text);
}
function baseParams() {
  const p = new URLSearchParams();
  p.set("name", name.value || "official-daily");
  p.set("limit", limit.value || "100");
  p.set("horizon_days", horizon.value || "20");
  p.set("require_fresh_market_data", requireFresh.checked ? "true" : "false");
  return p;
}
function renderStatus(data) {
  const s = data.summary || {};
  cards.innerHTML = [
    ["Blocked", s.blocked],
    ["Reason", s.blocked_reason],
    ["Latest candle", s.latest_candle_date],
    ["Stale", s.market_data_stale],
    ["Snapshots", s.paper_snapshots_total],
    ["Quality", s.quality_label],
  ].map(x => card(x[0], x[1])).join("");
  output.textContent = JSON.stringify(data, null, 2);
}
async function loadStatus() {
  try { renderStatus(await fetchJson("/signals/live-paper-validation/status")); } catch (err) { output.textContent = String(err); }
}
async function dryRun() {
  const p = baseParams();
  p.set("dry_run", "true");
  p.set("refresh_market_data", "false");
  const data = await fetchJson(`/signals/live-paper-validation/start?${p.toString()}`, { method: "POST" });
  output.textContent = JSON.stringify(data, null, 2);
}
async function start(withRefresh) {
  const p = baseParams();
  p.set("refresh_market_data", withRefresh ? "true" : "false");
  const data = await fetchJson(`/signals/live-paper-validation/start?${p.toString()}`, { method: "POST" });
  output.textContent = JSON.stringify(data, null, 2);
  await loadStatus();
}
loadStatus();
</script>
</body>
</html>
"""
