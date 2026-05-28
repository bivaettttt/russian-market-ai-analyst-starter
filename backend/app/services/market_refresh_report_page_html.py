from __future__ import annotations


def build_market_refresh_report_page_html() -> str:
    return """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Market Refresh Report</title>
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
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { border-bottom: 1px solid #e5e7eb; padding: 8px; text-align: left; }
    th { color: #475467; font-size: 12px; }
    .controls { display: flex; gap: 10px; flex-wrap: wrap; align-items: end; }
    pre { white-space: pre-wrap; overflow: auto; background: #0b1220; color: #dbeafe; padding: 12px; border-radius: 8px; }
  </style>
</head>
<body>
  <header>
    <h1>Market Refresh Report</h1>
    <div class="nav">
      <a href="/signals/daily-ops/page">Daily Ops</a>
      <a href="/signals/data-coverage-page">Data coverage</a>
      <a href="/signals/event-aware/conservative-overlay-quality-report-page">Overlay quality</a>
      <a href="/signals">Signals</a>
    </div>
  </header>
  <main>
    <section class="panel">
      <div class="controls">
        <label>Max tickers <input id="maxTickers" type="number" min="1" max="1000" value="300"></label>
        <label>Stale days <input id="staleDays" type="number" min="1" max="30" value="3"></label>
        <button onclick="loadReport()">Refresh report</button>
        <button class="secondary" onclick="dryRunRefresh()">Dry-run refresh</button>
        <button onclick="runRefresh()">Run refresh</button>
        <a href="/signals/daily-ops/market-refresh-report.csv">CSV</a>
      </div>
    </section>
    <section class="panel"><h2>Summary</h2><div id="cards" class="grid"></div></section>
    <section class="panel">
      <h2>Tickers</h2>
      <table><thead><tr><th>Ticker</th><th>Latest candle</th><th>Days stale</th><th>Status</th></tr></thead><tbody id="rows"></tbody></table>
    </section>
    <section class="panel">
      <h2>Warnings</h2>
      <ul>
        <li>MOEX availability can affect refresh completeness.</li>
        <li>Refresh writes only to the local DB.</li>
        <li>No trading operations are created.</li>
        <li>No investment advice.</li>
      </ul>
      <pre id="output">Ready.</pre>
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
function params() {
  const p = new URLSearchParams();
  p.set("max_tickers", maxTickers.value || "300");
  p.set("stale_days", staleDays.value || "3");
  return p;
}
function render(data) {
  const s = data.summary || {};
  cards.innerHTML = [
    ["Latest candle", s.latest_candle_date],
    ["Status", s.market_data_stale ? "stale" : "fresh"],
    ["Fresh", s.fresh_tickers],
    ["Stale", s.stale_tickers],
    ["Missing", s.missing_candles_tickers],
    ["Action", s.recommended_action],
  ].map(x => card(x[0], x[1])).join("");
  const tf = data.ticker_freshness || {};
  const all = [...(tf.stale_tickers || []), ...(tf.fresh_tickers || []), ...(tf.missing_candles_tickers || []).map(t => ({ticker:t,status:"missing_candles"}))];
  rows.innerHTML = all.slice(0, 500).map(row => `<tr><td>${esc(row.ticker)}</td><td>${esc(row.latest_candle_date)}</td><td>${esc(row.days_stale)}</td><td>${esc(row.status)}</td></tr>`).join("") || `<tr><td colspan="4">No rows.</td></tr>`;
  output.textContent = JSON.stringify(data, null, 2);
}
async function loadReport() {
  try { render(await fetchJson(`/signals/daily-ops/market-refresh-report?${params().toString()}`)); } catch (err) { output.textContent = String(err); }
}
async function dryRunRefresh() {
  const p = new URLSearchParams();
  p.set("dry_run", "true");
  p.set("max_tickers", maxTickers.value || "300");
  p.set("days", "120");
  output.textContent = JSON.stringify(await fetchJson(`/signals/daily-ops/refresh-market-data?${p.toString()}`, {method:"POST"}), null, 2);
}
async function runRefresh() {
  const p = new URLSearchParams();
  p.set("max_tickers", maxTickers.value || "300");
  p.set("days", "120");
  output.textContent = JSON.stringify(await fetchJson(`/signals/daily-ops/refresh-market-data?${p.toString()}`, {method:"POST"}), null, 2);
  await loadReport();
}
loadReport();
</script>
</body>
</html>
"""
