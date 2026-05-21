from __future__ import annotations


def build_candidate_filter_calibration_page_html() -> str:
    return """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Candidate Filter Calibration</title>
  <style>
    :root { --bg:#f5f7fb; --card:#fff; --text:#111827; --muted:#64748b; --border:#e2e8f0; --green:#047857; --red:#b91c1c; --amber:#92400e; }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--text); font-family:Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    header { background:#0f172a; color:white; padding:28px 20px; }
    .inner, main { max-width:1280px; margin:0 auto; }
    h1 { margin:0 0 8px; font-size:30px; }
    header p { margin:0; color:#cbd5e1; max-width:980px; line-height:1.5; }
    nav { margin-top:16px; display:flex; gap:12px; flex-wrap:wrap; }
    nav a { border:1px solid rgba(255,255,255,.22); border-radius:8px; color:white; padding:9px 12px; text-decoration:none; font-weight:750; }
    main { padding:22px 20px 42px; }
    .toolbar, .card { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:16px; box-shadow:0 10px 24px rgba(15,23,42,.05); }
    .toolbar { display:grid; grid-template-columns:repeat(5, minmax(130px, 1fr)); gap:12px; align-items:end; }
    label { color:var(--muted); font-size:12px; font-weight:850; text-transform:uppercase; letter-spacing:.04em; }
    input { width:100%; margin-top:6px; border:1px solid var(--border); border-radius:8px; padding:10px; font:inherit; color:var(--text); background:white; }
    input[type="checkbox"] { width:auto; height:20px; }
    .button { background:#0f172a; border:1px solid #0f172a; border-radius:8px; color:white; height:40px; padding:0 14px; font-weight:850; cursor:pointer; }
    .status { margin:14px 0; color:var(--muted); }
    .summary { display:grid; grid-template-columns:repeat(6, minmax(0,1fr)); gap:12px; margin:16px 0; }
    .metric .label { color:var(--muted); font-size:12px; font-weight:850; text-transform:uppercase; }
    .metric .value { margin-top:6px; font-size:22px; font-weight:900; overflow-wrap:anywhere; }
    .grid { display:grid; grid-template-columns:1fr; gap:16px; }
    h2 { margin:0 0 12px; font-size:18px; }
    table { width:100%; border-collapse:collapse; font-size:13px; }
    th, td { padding:9px 8px; border-bottom:1px solid var(--border); text-align:right; white-space:nowrap; vertical-align:top; }
    th:first-child, td:first-child, th:last-child, td:last-child { text-align:left; }
    th { color:var(--muted); font-size:11px; text-transform:uppercase; }
    .table-wrap { overflow-x:auto; }
    .good { color:var(--green); font-weight:850; }
    .bad { color:var(--red); font-weight:850; }
    .warn { color:var(--amber); font-weight:850; }
    .muted { color:var(--muted); }
    ul { margin:8px 0 0 18px; padding:0; }
    @media (max-width:1100px) { .toolbar, .summary { grid-template-columns:1fr; } }
  </style>
</head>
<body>
  <header>
    <div class="inner">
      <h1>Candidate Filter Calibration</h1>
      <p>Проверяет, улучшают ли простые include/exclude filters результат после expectancy breakdown. Research layer, production logic не меняется.</p>
      <nav>
        <a href="/signals">← Сигналы</a>
        <a href="/signals/consumer/backtest-audit-page">Backtest audit</a>
        <a href="/signals/consumer/threshold-sweep-page">Threshold sweep</a>
        <a href="/signals/consumer/walk-forward-page">Walk-forward</a>
        <a href="/signals/consumer/adaptive-trade-calibration-page">Target/Stop calibration</a>
        <a href="/signals/consumer/expectancy-breakdown-page">Expectancy breakdown</a>
        <a href="/signals/data-coverage-page">Data coverage</a>
      </nav>
    </div>
  </header>
  <main>
    <section class="toolbar">
      <label>max_tickers<input id="maxTickers" type="number" value="80" min="1" max="300" /></label>
      <label>max_samples<input id="maxSamples" type="number" value="3000" min="100" max="50000" /></label>
      <label>horizon<input id="horizon" type="number" value="30" min="5" max="90" /></label>
      <label>target_pct<input id="targetPct" type="number" value="0.05" min="0.005" max="0.25" step="0.005" /></label>
      <label>stop_pct<input id="stopPct" type="number" value="0.03" min="0.005" max="0.20" step="0.005" /></label>
      <label>commission_bps<input id="commissionBps" type="number" value="10" min="0" max="100" /></label>
      <label>slippage_bps<input id="slippageBps" type="number" value="5" min="0" max="100" /></label>
      <label>min_bucket_samples<input id="minBucketSamples" type="number" value="20" min="1" max="1000" /></label>
      <label>max_filters<input id="maxFilters" type="number" value="80" min="5" max="300" /></label>
      <label>best adaptive policy<input id="useBestAdaptivePolicy" type="checkbox" checked /></label>
      <button class="button" onclick="loadReport()">Запустить filter calibration</button>
    </section>
    <div id="status" class="status">Загружаю отчёт...</div>
    <section id="summary" class="summary"></section>
    <section class="grid">
      <div class="card"><h2>Best filters</h2><div id="best"></div></div>
      <div class="card"><h2>Pockets used</h2><div id="pockets"></div></div>
      <div class="card"><h2>Warnings & limitations</h2><div id="notes"></div></div>
    </section>
  </main>
  <script>
    const esc = value => String(value ?? "—").replace(/[&<>"']/g, ch => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#039;" }[ch]));
    const fmt = (value, d = 2) => value === null || value === undefined || Number.isNaN(Number(value)) ? "—" : Number(value).toFixed(d);
    function q() {
      const params = new URLSearchParams();
      params.set("max_tickers", document.getElementById("maxTickers").value);
      params.set("max_samples", document.getElementById("maxSamples").value);
      params.set("horizon", document.getElementById("horizon").value);
      params.set("target_pct", document.getElementById("targetPct").value);
      params.set("stop_pct", document.getElementById("stopPct").value);
      params.set("commission_bps", document.getElementById("commissionBps").value);
      params.set("slippage_bps", document.getElementById("slippageBps").value);
      params.set("min_bucket_samples", document.getElementById("minBucketSamples").value);
      params.set("max_filters", document.getElementById("maxFilters").value);
      params.set("use_best_adaptive_policy", document.getElementById("useBestAdaptivePolicy").checked ? "true" : "false");
      return params;
    }
    function card(label, value, cls = "") {
      return `<div class="card metric"><div class="label">${esc(label)}</div><div class="value ${cls}">${esc(value)}</div></div>`;
    }
    function bestTable(rows) {
      if (!rows || !rows.length) return '<div class="muted">Нет фильтров.</div>';
      return `<div class="table-wrap"><table><thead><tr>
        <th>rank</th><th>filter</th><th>score</th><th>quality</th><th>kept</th><th>coverage</th><th>avg Δ</th><th>PF Δ</th><th>win Δ</th><th>stop Δ</th><th>avoided</th><th>missed</th><th>rules</th>
      </tr></thead><tbody>${rows.map(row => `<tr>
        <td>${row.rank}</td><td>${esc(row.filter_id)}<div class="muted">${esc(row.description)}</div></td><td>${fmt(row.score)}</td><td>${esc(row.quality_label)}</td><td>${row.kept_samples}</td><td>${fmt(row.coverage_after_filter_pct)}</td><td>${fmt(row.avg_trade_return_delta_pct)}</td><td>${fmt(row.profit_factor_delta, 3)}</td><td>${fmt(row.win_rate_delta_pct)}</td><td>${fmt(row.stop_hit_delta_pct)}</td><td>${row.avoided_losses}</td><td>${row.missed_wins}</td><td>${esc(JSON.stringify(row.rules || []))}</td>
      </tr>`).join("")}</tbody></table></div>`;
    }
    function pocketTable(title, rows) {
      return `<h2>${title}</h2>${(!rows || !rows.length) ? '<div class="muted">—</div>' : `<div class="table-wrap"><table><thead><tr><th>bucket</th><th>samples</th><th>avg</th><th>pf</th></tr></thead><tbody>${rows.slice(0, 10).map(row => `<tr><td>${esc(row.dimension)}=${esc(row.bucket)}</td><td>${row.samples}</td><td>${fmt(row.avg_trade_return_pct)}</td><td>${fmt(row.profit_factor, 3)}</td></tr>`).join("")}</tbody></table></div>`}`;
    }
    async function loadReport() {
      const status = document.getElementById("status");
      status.textContent = "Считаю filter calibration...";
      try {
        const response = await fetch(`/signals/consumer/candidate-filter-calibration?${q().toString()}`);
        const data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.detail || "request failed");
        const s = data.summary || {};
        const baseline = s.baseline_metrics || {};
        document.getElementById("summary").innerHTML = [
          card("samples", s.samples),
          card("baseline avg", fmt(baseline.avg_trade_return_pct), Number(baseline.avg_trade_return_pct || 0) >= 0 ? "good" : "bad"),
          card("baseline PF", fmt(baseline.profit_factor, 3)),
          card("best score", fmt(s.best_score), Number(s.best_score || 0) >= 25 ? "good" : "warn"),
          card("best filter", s.best_filter_id || "—"),
          card("recommendation", s.recommendation || "—")
        ].join("");
        document.getElementById("best").innerHTML = bestTable(data.best_filters || []);
        document.getElementById("pockets").innerHTML = pocketTable("Positive pockets used", data.positive_pockets_used || []) + pocketTable("Negative pockets used", data.negative_pockets_used || []);
        document.getElementById("notes").innerHTML = `<ul>${[...(s.warnings || []), ...(data.limitations || [])].map(item => `<li>${esc(item)}</li>`).join("") || "<li>—</li>"}</ul>`;
        status.textContent = `Готово: filters=${s.filters_tested || 0}, recommendation=${s.recommendation || "—"}.`;
      } catch (error) {
        status.textContent = `Ошибка: ${error.message}`;
      }
    }
    loadReport();
  </script>
</body>
</html>
"""
