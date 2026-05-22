from __future__ import annotations


def build_data_coverage_page_html() -> str:
    return """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Data Coverage Diagnostics</title>
  <style>
    :root { --bg:#f5f7fb; --card:#fff; --text:#111827; --muted:#64748b; --border:#e2e8f0; --green:#047857; --red:#b91c1c; --amber:#92400e; }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--text); font-family:Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    header { background:#0f172a; color:white; padding:28px 20px; }
    .inner, main { max-width:1280px; margin:0 auto; }
    h1 { margin:0 0 8px; font-size:30px; }
    header p { margin:0; color:#cbd5e1; max-width:920px; line-height:1.5; }
    nav { margin-top:16px; display:flex; gap:12px; flex-wrap:wrap; }
    nav a { border:1px solid rgba(255,255,255,.22); border-radius:8px; color:white; padding:9px 12px; text-decoration:none; font-weight:750; }
    main { padding:22px 20px 42px; }
    .toolbar, .card { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:16px; box-shadow:0 10px 24px rgba(15,23,42,.05); }
    .toolbar { display:grid; grid-template-columns:repeat(6, minmax(130px, 1fr)); gap:12px; align-items:end; }
    label { color:var(--muted); font-size:12px; font-weight:850; text-transform:uppercase; letter-spacing:.04em; }
    input { width:100%; margin-top:6px; border:1px solid var(--border); border-radius:8px; padding:10px; font:inherit; color:var(--text); background:white; }
    input[type="checkbox"] { width:auto; height:20px; }
    .button { background:#0f172a; border:1px solid #0f172a; border-radius:8px; color:white; height:40px; padding:0 14px; font-weight:850; cursor:pointer; }
    .status { margin:14px 0; color:var(--muted); }
    .summary { display:grid; grid-template-columns:repeat(7, minmax(0, 1fr)); gap:12px; margin:16px 0; }
    .metric .label { color:var(--muted); font-size:12px; font-weight:850; text-transform:uppercase; }
    .metric .value { margin-top:6px; font-size:22px; font-weight:900; overflow-wrap:anywhere; }
    .grid { display:grid; grid-template-columns:repeat(2, minmax(0,1fr)); gap:16px; }
    h2 { margin:0 0 12px; font-size:18px; }
    table { width:100%; border-collapse:collapse; font-size:13px; }
    th, td { padding:9px 8px; border-bottom:1px solid var(--border); text-align:right; white-space:nowrap; vertical-align:top; }
    th:first-child, td:first-child { text-align:left; }
    th { color:var(--muted); font-size:11px; text-transform:uppercase; }
    .table-wrap { overflow-x:auto; }
    .good { color:var(--green); font-weight:850; }
    .bad { color:var(--red); font-weight:850; }
    .warn { color:var(--amber); font-weight:850; }
    .muted { color:var(--muted); }
    ul { margin:8px 0 0 18px; padding:0; }
    @media (max-width:1100px) { .toolbar, .summary, .grid { grid-template-columns:1fr; } }
  </style>
</head>
<body>
  <header>
    <div class="inner">
      <h1>Data Coverage Diagnostics</h1>
      <p>Проверка покрытия инструментов и свечей для backtest, adaptive calibration и expectancy breakdown.</p>
      <nav>
        <a href="/signals">← Сигналы</a>
        <a href="/signals/consumer/backtest-audit-page">Backtest audit</a>
        <a href="/signals/consumer/adaptive-trade-calibration-page">Target/Stop calibration</a>
        <a href="/signals/consumer/expectancy-breakdown-page">Expectancy breakdown</a>
        <a href="/signals/consumer/candidate-filter-calibration-page">Filter calibration</a>
        <a href="/signals/consumer/composite-rule-calibration-page">Composite rules</a>
      </nav>
    </div>
  </header>
  <main>
    <section class="toolbar">
      <label>max_tickers<input id="maxTickers" type="number" value="500" min="1" max="5000" /></label>
      <label>min_history<input id="minHistory" type="number" value="80" min="10" max="500" /></label>
      <label>horizon<input id="horizon" type="number" value="20" min="1" max="250" /></label>
      <label>candles_limit<input id="candlesLimit" type="number" value="1000" min="50" max="5000" /></label>
      <label>include_examples<input id="includeExamples" type="checkbox" checked /></label>
      <button class="button" onclick="loadReport()">Проверить покрытие данных</button>
    </section>
    <div id="status" class="status">Загружаю диагностику...</div>
    <section id="summary" class="summary"></section>
    <section class="grid">
      <div class="card"><h2>Skip reasons</h2><div id="skipReasons"></div></div>
      <div class="card"><h2>By asset type</h2><div id="assetTypes"></div></div>
      <div class="card"><h2>Top usable tickers</h2><div id="usable"></div></div>
      <div class="card"><h2>Top skipped tickers</h2><div id="skipped"></div></div>
      <div class="card"><h2>Recommendations</h2><div id="recommendations"></div></div>
      <div class="card"><h2>Warnings</h2><div id="warnings"></div></div>
    </section>
  </main>
  <script>
    const esc = value => String(value ?? "—").replace(/[&<>"']/g, ch => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#039;" }[ch]));
    const fmt = value => value === null || value === undefined ? "—" : String(value);
    function query() {
      const q = new URLSearchParams();
      q.set("max_tickers", document.getElementById("maxTickers").value);
      q.set("min_history", document.getElementById("minHistory").value);
      q.set("horizon", document.getElementById("horizon").value);
      q.set("candles_limit", document.getElementById("candlesLimit").value);
      q.set("include_examples", document.getElementById("includeExamples").checked ? "true" : "false");
      return q;
    }
    function metric(label, value, cls = "") {
      return `<div class="card metric"><div class="label">${esc(label)}</div><div class="value ${cls}">${esc(fmt(value))}</div></div>`;
    }
    function kvTable(obj) {
      const entries = Object.entries(obj || {});
      if (!entries.length) return '<div class="muted">Нет данных.</div>';
      return `<div class="table-wrap"><table><thead><tr><th>bucket</th><th>value</th></tr></thead><tbody>${entries.map(([key, value]) => `<tr><td>${esc(key)}</td><td>${esc(value)}</td></tr>`).join("")}</tbody></table></div>`;
    }
    function assetTable(obj) {
      const entries = Object.entries(obj || {});
      if (!entries.length) return '<div class="muted">Нет данных.</div>';
      return `<div class="table-wrap"><table><thead><tr><th>asset_type</th><th>instruments</th><th>candidates</th><th>usable</th></tr></thead><tbody>${entries.map(([key, row]) => `<tr><td>${esc(key)}</td><td>${esc(row.instruments)}</td><td>${esc(row.candidate_tickers)}</td><td>${esc(row.usable_tickers)}</td></tr>`).join("")}</tbody></table></div>`;
    }
    function usableTable(rows) {
      if (!rows || !rows.length) return '<div class="muted">Нет usable tickers.</div>';
      return `<div class="table-wrap"><table><thead><tr><th>ticker</th><th>candles</th><th>possible</th><th>first</th><th>last</th></tr></thead><tbody>${rows.slice(0, 20).map(row => `<tr><td>${esc(row.ticker)}</td><td>${esc(row.valid_ohlc_count)}</td><td>${esc(row.possible_samples)}</td><td>${esc(row.first_date)}</td><td>${esc(row.last_date)}</td></tr>`).join("")}</tbody></table></div>`;
    }
    function skippedTable(rows) {
      if (!rows || !rows.length) return '<div class="muted">Нет skipped tickers.</div>';
      return `<div class="table-wrap"><table><thead><tr><th>ticker</th><th>reason</th><th>candles</th><th>missing close</th><th>missing high/low</th></tr></thead><tbody>${rows.slice(0, 30).map(row => `<tr><td>${esc(row.ticker)}</td><td class="warn">${esc(row.skip_reason)}</td><td>${esc(row.valid_ohlc_count)}</td><td>${esc(row.missing_close_count)}</td><td>${esc(row.missing_high_low_count)}</td></tr>`).join("")}</tbody></table></div>`;
    }
    function list(items) {
      return `<ul>${(items || []).map(item => `<li>${esc(item)}</li>`).join("") || "<li>—</li>"}</ul>`;
    }
    async function loadReport() {
      const status = document.getElementById("status");
      status.textContent = "Считаю coverage...";
      try {
        const response = await fetch(`/signals/data-coverage?${query().toString()}`);
        const data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.detail || "request failed");
        const s = data.summary || {};
        const levelClass = s.coverage_level === "good" ? "good" : s.coverage_level === "empty" ? "bad" : "warn";
        document.getElementById("summary").innerHTML = [
          metric("total instruments", s.total_instruments),
          metric("eligible instruments", s.signal_eligible_count),
          metric("tickers with candles", s.tickers_with_candles),
          metric("usable tickers", s.usable_tickers, Number(s.usable_tickers || 0) > 0 ? "good" : "bad"),
          metric("possible samples", s.total_possible_samples, Number(s.total_possible_samples || 0) > 0 ? "good" : "bad"),
          metric("coverage level", s.coverage_level, levelClass),
          metric("main blocker", s.main_blocker, s.main_blocker === "none" ? "good" : "warn")
        ].join("");
        document.getElementById("skipReasons").innerHTML = kvTable(data.skip_reasons || {});
        document.getElementById("assetTypes").innerHTML = assetTable(data.by_asset_type || {});
        document.getElementById("usable").innerHTML = usableTable(data.top_usable_tickers || []);
        document.getElementById("skipped").innerHTML = skippedTable(data.top_skipped_tickers || []);
        document.getElementById("recommendations").innerHTML = list(data.recommendations || []);
        document.getElementById("warnings").innerHTML = list(data.warnings || []);
        status.textContent = `Готово: coverage=${s.coverage_level || "—"}, samples=${s.total_possible_samples || 0}.`;
      } catch (error) {
        status.textContent = `Ошибка: ${error.message}`;
      }
    }
    loadReport();
  </script>
</body>
</html>
"""
