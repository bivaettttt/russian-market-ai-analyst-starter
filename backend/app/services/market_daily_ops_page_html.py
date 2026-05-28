from __future__ import annotations


def build_market_daily_ops_page_html() -> str:
    return """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Market Daily Ops</title>
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
    label { display: block; font-size: 12px; color: #475467; margin-bottom: 4px; }
    input, button { font: inherit; padding: 8px 10px; border: 1px solid #cbd5e1; border-radius: 6px; background: white; }
    button { cursor: pointer; background: #0f62fe; color: white; border-color: #0f62fe; }
    button.secondary { background: white; color: #0f62fe; }
    .controls { display: flex; gap: 10px; flex-wrap: wrap; align-items: end; }
    .controls > div { min-width: 130px; }
    pre { white-space: pre-wrap; overflow: auto; background: #0b1220; color: #dbeafe; padding: 12px; border-radius: 8px; }
  </style>
</head>
<body>
  <header>
    <h1>Market Daily Ops · Paper Validation Alpha</h1>
    <div class="nav">
      <a href="/signals">Signals</a>
      <a href="/signals/event-aware/conservative-overlay-quality-report-page">Overlay quality</a>
      <a href="/signals/event-aware/conservative-overlay-paper-tracking-page">Overlay tracking</a>
      <a href="/signals/data-coverage-page">Data coverage</a>
      <a href="/signals/market-regime">Market regime</a>
      <a href="/signals/daily-ops/status">Status JSON</a>
      <a href="/signals/daily-ops/market-data-freshness">Freshness JSON</a>
    </div>
  </header>
  <main>
    <section class="panel">
      <h2>Status</h2>
      <div id="cards" class="grid"></div>
    </section>

    <section class="panel">
      <h2>Actions</h2>
      <div class="controls">
        <div><label>Name</label><input id="name" value="daily"></div>
        <div><label>Limit</label><input id="limit" type="number" value="100" min="1" max="500"></div>
        <div><label>Horizon</label><input id="horizon" type="number" value="20" min="1" max="120"></div>
        <div><label>Refresh tickers</label><input id="refreshTickers" type="number" value="150" min="1" max="500"></div>
        <div><label>Refresh days</label><input id="refreshDays" type="number" value="120" min="10" max="1000"></div>
        <button onclick="dryRun()">Dry run</button>
        <button onclick="runDaily(true)">Run daily ops</button>
        <button onclick="refreshMarket()">Refresh market data</button>
        <button class="secondary" onclick="runDaily(false)">Run without refresh</button>
        <button class="secondary" onclick="evaluateReady()">Evaluate ready</button>
        <button class="secondary" onclick="loadStatus()">Refresh status</button>
      </div>
    </section>

    <section class="panel">
      <h2>Latest Run Result</h2>
      <div id="runCards" class="grid"></div>
      <pre id="output">Ready.</pre>
    </section>

    <section class="panel">
      <h2>Caveats</h2>
      <ul>
        <li>Paper tracking only; no real trades are created.</li>
        <li>Market data refresh writes only local MOEX candles/instruments.</li>
        <li>Dry-run does not create snapshots or evaluate ready snapshots.</li>
        <li>No investment advice.</li>
      </ul>
    </section>
  </main>
<script>
function fmt(value) {
  if (value === null || value === undefined) return "—";
  return String(value);
}
function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
function card(label, value) { return `<div class="card"><div class="label">${esc(label)}</div><div class="value">${esc(fmt(value))}</div></div>`; }
async function fetchJson(url, options) {
  const res = await fetch(url, options || {});
  const text = await res.text();
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${text}`);
  return JSON.parse(text);
}
function params() {
  const p = new URLSearchParams();
  p.set("name", name.value || "daily");
  p.set("limit", limit.value || "100");
  p.set("horizon_days", horizon.value || "20");
  p.set("refresh_max_tickers", refreshTickers.value || "150");
  p.set("refresh_days", refreshDays.value || "120");
  return p;
}
function renderRun(data) {
  const s = data.summary || {};
  runCards.innerHTML = [
    ["Refresh", s.market_refresh_status],
    ["Latest candle", s.latest_candle_date],
    ["Stale", s.market_data_stale],
    ["Snapshot", s.created_snapshot ? `created #${s.snapshot_id}` : (s.duplicate_snapshot ? `duplicate #${s.snapshot_id}` : "none")],
    ["Evaluated", s.evaluated_snapshots],
    ["Items", s.evaluated_items],
    ["Quality", s.quality_label],
    ["Next", s.recommended_action],
  ].map(x => card(x[0], x[1])).join("");
  output.textContent = JSON.stringify(data, null, 2);
}
async function loadStatus() {
  try {
    const data = await fetchJson("/signals/daily-ops/status");
    const s = data.summary || {};
    cards.innerHTML = [
      ["Latest candle", s.latest_candle_date],
      ["Freshness", s.market_data_stale ? "stale" : "fresh"],
      ["Paper snapshots", s.paper_snapshots_total],
      ["Ready", s.ready_to_evaluate],
      ["Quality", s.quality_label],
      ["Next", s.recommended_action],
    ].map(x => card(x[0], x[1])).join("");
    output.textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    output.textContent = String(err);
  }
}
async function dryRun() {
  const p = params();
  p.set("dry_run", "true");
  p.set("refresh_market_data", "false");
  const data = await fetchJson(`/signals/daily-ops/run?${p.toString()}`, { method: "POST" });
  renderRun(data);
}
async function runDaily(withRefresh) {
  const p = params();
  p.set("refresh_market_data", withRefresh ? "true" : "false");
  const data = await fetchJson(`/signals/daily-ops/run?${p.toString()}`, { method: "POST" });
  renderRun(data);
  await loadStatus();
}
async function refreshMarket() {
  const p = new URLSearchParams();
  p.set("max_tickers", refreshTickers.value || "150");
  p.set("days", refreshDays.value || "120");
  const data = await fetchJson(`/signals/daily-ops/refresh-market-data?${p.toString()}`, { method: "POST" });
  renderRun({ summary: { market_refresh_status: data.recommendation, latest_candle_date: (data.after?.summary || {}).latest_candle_date, market_data_stale: (data.after?.summary || {}).is_stale }, steps: { market_refresh: data }, warnings: data.warnings || [] });
  await loadStatus();
}
async function evaluateReady() {
  const data = await fetchJson("/signals/event-aware/conservative-overlay-paper-evaluate-ready?limit=50", { method: "POST" });
  output.textContent = JSON.stringify(data, null, 2);
  await loadStatus();
}
loadStatus();
</script>
</body>
</html>
"""
