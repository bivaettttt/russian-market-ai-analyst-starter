from __future__ import annotations


def build_expectancy_breakdown_page_html() -> str:
    return """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Expectancy Breakdown</title>
  <style>
    :root { --bg:#f5f7fb; --card:#fff; --text:#111827; --muted:#64748b; --border:#e2e8f0; --green:#047857; --red:#b91c1c; --amber:#92400e; }
    * { box-sizing: border-box; }
    body { margin:0; background:var(--bg); color:var(--text); font-family:Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    header { background:#0f172a; color:white; padding:28px 20px; }
    .inner, main { max-width:1280px; margin:0 auto; }
    h1 { margin:0 0 8px; font-size:30px; }
    header p { margin:0; color:#cbd5e1; max-width:920px; line-height:1.5; }
    nav { margin-top:16px; display:flex; gap:12px; flex-wrap:wrap; }
    nav a { border:1px solid rgba(255,255,255,.22); border-radius:8px; color:white; padding:9px 12px; text-decoration:none; font-weight:750; }
    main { padding:22px 20px 42px; }
    .toolbar, .card { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:16px; box-shadow:0 10px 24px rgba(15,23,42,.05); }
    .toolbar { display:grid; grid-template-columns:repeat(4, minmax(130px, 1fr)); gap:12px; align-items:end; }
    label { color:var(--muted); font-size:12px; font-weight:850; text-transform:uppercase; letter-spacing:.04em; }
    input { width:100%; margin-top:6px; border:1px solid var(--border); border-radius:8px; padding:10px; font:inherit; color:var(--text); background:white; }
    .button { background:#0f172a; border:1px solid #0f172a; border-radius:8px; color:white; height:40px; padding:0 14px; font-weight:850; cursor:pointer; }
    .status { margin:14px 0; color:var(--muted); }
    .summary { display:grid; grid-template-columns:repeat(6, minmax(0, 1fr)); gap:12px; margin:16px 0; }
    .metric .label { color:var(--muted); font-size:12px; font-weight:850; text-transform:uppercase; }
    .metric .value { margin-top:6px; font-size:24px; font-weight:900; overflow-wrap:anywhere; }
    .grid { display:grid; gap:16px; }
    h2 { margin:0 0 12px; font-size:18px; }
    h3 { margin:18px 0 10px; font-size:16px; }
    table { width:100%; border-collapse:collapse; font-size:13px; }
    th, td { padding:9px 8px; border-bottom:1px solid var(--border); text-align:right; white-space:nowrap; vertical-align:top; }
    th:first-child, td:first-child, th:last-child, td:last-child { text-align:left; }
    th { color:var(--muted); font-size:11px; text-transform:uppercase; }
    .table-wrap { overflow-x:auto; }
    .positive { color:var(--green); font-weight:850; }
    .negative { color:var(--red); font-weight:850; }
    .unstable { color:var(--amber); font-weight:850; }
    .neutral, .muted { color:var(--muted); }
    .sections { display:grid; grid-template-columns:repeat(2, minmax(0,1fr)); gap:16px; margin-bottom:16px; }
    @media (max-width:980px) { .toolbar, .summary, .sections { grid-template-columns:1fr; } }
  </style>
</head>
<body>
  <header>
    <div class="inner">
      <h1>Expectancy Breakdown</h1>
      <p>Диагностика trade PnL по сегментам: positive/negative pockets, candidate filters и candidate boosts. Research layer, production thresholds не меняются.</p>
      <nav>
        <a href="/signals">← Сигналы</a>
        <a href="/signals/consumer/backtest-audit-page">Backtest audit</a>
        <a href="/signals/consumer/threshold-sweep-page">Threshold sweep</a>
        <a href="/signals/consumer/walk-forward-page">Walk-forward</a>
        <a href="/signals/consumer/regime-historical-evaluation-page">Regime evaluation</a>
        <a href="/signals/consumer/regime-formula-calibration-page">Regime calibration</a>
        <a href="/signals/consumer/adaptive-trade-calibration-page">Target/Stop calibration</a>
        <a href="/signals/data-coverage-page">Data coverage</a>
      </nav>
    </div>
  </header>
  <main>
    <section class="toolbar">
      <label>max_tickers<input id="maxTickers" type="number" value="40" min="1" max="300" /></label>
      <label>max_samples<input id="maxSamples" type="number" value="800" min="100" max="50000" /></label>
      <label>horizon<input id="horizon" type="number" value="20" min="5" max="90" /></label>
      <label>target_pct<input id="targetPct" type="number" value="0.05" min="0.005" max="0.25" step="0.005" /></label>
      <label>stop_pct<input id="stopPct" type="number" value="0.03" min="0.005" max="0.20" step="0.005" /></label>
      <label>commission_bps<input id="commissionBps" type="number" value="0" min="0" max="100" step="1" /></label>
      <label>slippage_bps<input id="slippageBps" type="number" value="0" min="0" max="100" step="1" /></label>
      <label>min_bucket_samples<input id="minBucketSamples" type="number" value="20" min="1" max="1000" /></label>
      <button class="button" onclick="loadReport()">Запустить expectancy breakdown</button>
    </section>
    <div id="status" class="status">Загружаю отчёт...</div>
    <section id="summary" class="summary"></section>
    <section class="sections">
      <div class="card"><h2>Positive pockets</h2><div id="positive"></div></div>
      <div class="card"><h2>Negative pockets</h2><div id="negative"></div></div>
      <div class="card"><h2>Candidate filters</h2><div id="filters"></div></div>
      <div class="card"><h2>Candidate boosts</h2><div id="boosts"></div></div>
    </section>
    <section class="card">
      <h2>Breakdown by dimension</h2>
      <div id="dimensions"></div>
    </section>
  </main>
  <script>
    const fmt = (v, d = 2) => v === null || v === undefined || Number.isNaN(Number(v)) ? "—" : Number(v).toFixed(d);
    const esc = value => String(value ?? "—").replace(/[&<>"']/g, ch => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#039;" }[ch]));
    function params() {
      const q = new URLSearchParams();
      q.set("max_tickers", document.getElementById("maxTickers").value);
      q.set("max_samples", document.getElementById("maxSamples").value);
      q.set("horizon", document.getElementById("horizon").value);
      q.set("target_pct", document.getElementById("targetPct").value);
      q.set("stop_pct", document.getElementById("stopPct").value);
      q.set("commission_bps", document.getElementById("commissionBps").value);
      q.set("slippage_bps", document.getElementById("slippageBps").value);
      q.set("min_bucket_samples", document.getElementById("minBucketSamples").value);
      return q;
    }
    function rowClass(row) {
      return row.quality_label === "positive" ? "positive" : row.quality_label === "negative" ? "negative" : row.quality_label === "unstable" ? "unstable" : "neutral";
    }
    function pocketTable(rows) {
      if (!rows || !rows.length) return '<div class="muted">Нет устойчивых bucket.</div>';
      return `<div class="table-wrap"><table><thead><tr><th>bucket</th><th>samples</th><th>avg</th><th>pf</th><th>win</th><th>quality</th></tr></thead><tbody>${rows.slice(0, 12).map(row => `
        <tr><td>${esc(row.dimension)}=${esc(row.bucket)}</td><td>${row.samples}</td><td class="${rowClass(row)}">${fmt(row.avg_trade_return_pct)}</td><td>${fmt(row.profit_factor, 3)}</td><td>${fmt(row.win_rate_pct)}</td><td class="${rowClass(row)}">${esc(row.quality_label)}</td></tr>
      `).join("")}</tbody></table></div>`;
    }
    function recommendationTable(rows) {
      if (!rows || !rows.length) return '<div class="muted">Нет рекомендаций с достаточной выборкой.</div>';
      return `<div class="table-wrap"><table><thead><tr><th>rule</th><th>samples</th><th>avg</th><th>pf</th></tr></thead><tbody>${rows.slice(0, 12).map(row => `
        <tr><td>${esc(row.rule)}</td><td>${row.samples}</td><td>${fmt(row.avg_trade_return_pct)}</td><td>${fmt(row.profit_factor, 3)}</td></tr>
      `).join("")}</tbody></table></div>`;
    }
    function dimensionTable(name, rows) {
      const sorted = [...(rows || [])].sort((a, b) => (Number(b.avg_trade_return_pct ?? -999) - Number(a.avg_trade_return_pct ?? -999)));
      const visible = sorted.length > 16 ? [...sorted.slice(0, 8), ...sorted.slice(-8)] : sorted;
      return `<h3>${esc(name)}</h3><div class="table-wrap"><table><thead><tr>
        <th>bucket</th><th>samples</th><th>coverage</th><th>avg</th><th>win</th><th>pf</th><th>stop_hit</th><th>quality</th><th>diagnostic</th>
      </tr></thead><tbody>${visible.map(row => `
        <tr><td>${esc(row.bucket)}</td><td>${row.samples}</td><td>${fmt(row.coverage_pct)}</td><td class="${rowClass(row)}">${fmt(row.avg_trade_return_pct)}</td><td>${fmt(row.win_rate_pct)}</td><td>${fmt(row.profit_factor, 3)}</td><td>${fmt(row.stop_hit_rate_pct)}</td><td class="${rowClass(row)}">${esc(row.quality_label)}</td><td>${esc(row.diagnostic)}</td></tr>
      `).join("")}</tbody></table></div>`;
    }
    async function loadReport() {
      const status = document.getElementById("status");
      status.textContent = "Считаю expectancy breakdown...";
      try {
        const response = await fetch(`/signals/consumer/expectancy-breakdown?${params().toString()}`);
        const data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.detail || "request failed");
        const s = data.summary || {};
        document.getElementById("summary").innerHTML = [
          ["samples", s.samples], ["avg trade", fmt(s.avg_trade_return_pct)], ["win rate", fmt(s.win_rate_pct)],
          ["profit factor", fmt(s.profit_factor, 3)], ["expectancy", fmt(s.expectancy_pct)], ["stop hit", fmt(s.stop_hit_rate_pct)]
        ].map(([label, value]) => `<div class="card metric"><div class="label">${label}</div><div class="value">${value}</div></div>`).join("");
        document.getElementById("positive").innerHTML = pocketTable(data.positive_pockets || []);
        document.getElementById("negative").innerHTML = pocketTable(data.negative_pockets || []);
        document.getElementById("filters").innerHTML = recommendationTable(data.candidate_filters || []);
        document.getElementById("boosts").innerHTML = recommendationTable(data.candidate_boosts || []);
        document.getElementById("dimensions").innerHTML = Object.entries(data.dimensions || {}).map(([name, rows]) => dimensionTable(name, rows)).join("");
        status.innerHTML = `Готово: ${s.samples || 0} samples, ${s.tickers_used || 0} tickers.`
          + (Number(s.samples || 0) === 0 ? ' <a href="/signals/data-coverage-page">Проверить Data coverage</a>' : "");
      } catch (error) {
        status.textContent = `Ошибка: ${error.message}`;
      }
    }
    loadReport();
  </script>
</body>
</html>
"""
