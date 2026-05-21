from __future__ import annotations


def build_regime_historical_evaluation_page_html() -> str:
    return """<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Regime Historical Evaluation</title>
  <style>
    :root { --bg:#f6f7fb; --card:#fff; --text:#172033; --muted:#667085; --line:#e5e7eb; --good:#15803d; --bad:#b91c1c; --warn:#b45309; }
    body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; background:var(--bg); color:var(--text); }
    header { background:#111827; color:#fff; padding:24px; }
    header .inner, main { max-width:1180px; margin:0 auto; }
    h1 { margin:0 0 8px; font-size:28px; }
    h2 { margin:0 0 14px; font-size:18px; }
    p { color:var(--muted); }
    header p { color:#cbd5e1; }
    nav { display:flex; gap:10px; flex-wrap:wrap; margin-top:16px; }
    nav a { color:#fff; text-decoration:none; border:1px solid rgba(255,255,255,.25); padding:8px 10px; border-radius:8px; }
    main { padding:22px; }
    .toolbar, .summary, .grid { display:grid; gap:12px; }
    .toolbar { grid-template-columns:repeat(4,minmax(0,1fr)); align-items:end; margin-bottom:16px; }
    .summary { grid-template-columns:repeat(5,minmax(0,1fr)); margin:16px 0; }
    .grid { grid-template-columns:1fr; }
    label { font-size:12px; color:var(--muted); display:grid; gap:5px; }
    input { padding:9px 10px; border:1px solid var(--line); border-radius:8px; font:inherit; }
    button { padding:10px 14px; border:0; border-radius:8px; background:#2563eb; color:#fff; font-weight:700; cursor:pointer; }
    .card { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:16px; box-shadow:0 1px 2px rgba(15,23,42,.04); }
    .metric .label { font-size:12px; color:var(--muted); text-transform:uppercase; }
    .metric .value { font-size:24px; font-weight:800; margin-top:6px; }
    .status { color:var(--muted); margin:12px 0; }
    table { width:100%; border-collapse:collapse; font-size:13px; }
    th, td { text-align:left; padding:9px; border-bottom:1px solid var(--line); vertical-align:top; }
    th { color:var(--muted); font-size:12px; text-transform:uppercase; }
    .table-wrap { overflow:auto; }
    .good { color:var(--good); } .bad { color:var(--bad); } .warn { color:var(--warn); }
    @media (max-width:900px) { .toolbar, .summary { grid-template-columns:1fr 1fr; } }
    @media (max-width:560px) { .toolbar, .summary { grid-template-columns:1fr; } }
  </style>
</head>
<body>
  <header>
    <div class="inner">
      <h1>Regime Historical Evaluation</h1>
      <p>Proxy historical validation: считает market regime на каждую дату и сравнивает качество long-сигналов до/после regime filter.</p>
      <nav>
        <a href="/signals">← Сигналы</a>
        <a href="/signals/consumer/backtest-audit-page">Backtest audit</a>
        <a href="/signals/consumer/threshold-sweep-page">Threshold sweep</a>
        <a href="/signals/consumer/walk-forward-page">Walk-forward</a>
        <a href="/signals/consumer/regime-formula-calibration-page">Regime calibration</a>
        <a href="/signals/consumer/adaptive-trade-calibration-page">Target/Stop calibration</a>
        <a href="/signals/consumer/expectancy-breakdown-page">Expectancy breakdown</a>
      </nav>
    </div>
  </header>
  <main>
    <section class="toolbar">
      <label>max_tickers<input id="maxTickers" type="number" value="20" min="5" max="300" /></label>
      <label>max_samples<input id="maxSamples" type="number" value="500" min="100" max="30000" /></label>
      <label>horizon<input id="horizon" type="number" value="20" min="5" max="90" /></label>
      <label>target_pct<input id="targetPct" type="number" value="0.05" min="0.005" max="0.25" step="0.005" /></label>
      <label>stop_pct<input id="stopPct" type="number" value="0.03" min="0.005" max="0.20" step="0.005" /></label>
      <label>lookback<input id="lookback" type="number" value="60" min="20" max="250" /></label>
      <label>min_tickers<input id="minTickers" type="number" value="20" min="5" max="200" /></label>
      <button onclick="loadEvaluation()">Запустить regime evaluation</button>
    </section>
    <div id="status" class="status">Готов к запуску.</div>
    <section id="summary" class="summary"></section>
    <section id="content" class="grid"></section>
  </main>
  <script>
    const escapeHtml = value => String(value ?? "").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;");
    const fmt = (value, digits = 2) => {
      const n = Number(value);
      if (Number.isNaN(n)) return "—";
      return n.toLocaleString("ru-RU", { maximumFractionDigits: digits });
    };
    const pct = value => value === null || value === undefined ? "—" : `${fmt(value)}%`;
    const metric = (label, value, cls = "") => `<div class="card metric"><div class="label">${escapeHtml(label)}</div><div class="value ${cls}">${escapeHtml(value)}</div></div>`;
    function query() {
      const q = new URLSearchParams();
      q.set("max_tickers", document.getElementById("maxTickers").value || "20");
      q.set("max_samples", document.getElementById("maxSamples").value || "500");
      q.set("horizon", document.getElementById("horizon").value || "20");
      q.set("target_pct", document.getElementById("targetPct").value || "0.05");
      q.set("stop_pct", document.getElementById("stopPct").value || "0.03");
      q.set("lookback", document.getElementById("lookback").value || "60");
      q.set("min_tickers", document.getElementById("minTickers").value || "20");
      return q;
    }
    function regimeTable(byRegime) {
      const rows = Object.entries(byRegime || {});
      return `<section class="card"><h2>By Market Regime</h2><div class="table-wrap"><table><thead><tr>
        <th>regime</th><th>samples</th><th>target hit</th><th>stop hit</th><th>timeout</th><th>avg trade</th><th>win</th><th>PF</th><th>avg return</th><th>avg regime score</th><th>long allowed</th>
      </tr></thead><tbody>${rows.map(([key, row]) => `<tr>
        <td>${escapeHtml(key)}</td><td>${fmt(row.samples,0)}</td><td>${pct(row.target_hit_rate_pct)}</td><td>${pct(row.stop_hit_rate_pct)}</td>
        <td>${pct(row.timeout_rate_pct)}</td><td>${pct(row.avg_trade_return_pct)}</td><td>${pct(row.win_rate_pct)}</td><td>${fmt(row.profit_factor)}</td><td>${pct(row.avg_forward_return_pct)}</td><td>${fmt(row.avg_regime_score)}</td><td>${pct(row.long_allowed_rate_pct)}</td>
      </tr>`).join("")}</tbody></table></div></section>`;
    }
    function comparisonTable(comparison) {
      const baseline = comparison?.baseline || {};
      const filtered = comparison?.with_regime_filter || {};
      const delta = comparison?.delta || {};
      return `<section class="card"><h2>Regime Filter Comparison</h2><div class="table-wrap"><table><thead><tr>
        <th>case</th><th>signals</th><th>target hit</th><th>stop hit</th><th>avg trade</th><th>win</th><th>PF</th><th>avg return</th>
      </tr></thead><tbody>
        <tr><td>baseline</td><td>${fmt(baseline.signals,0)}</td><td>${pct(baseline.target_hit_rate_pct)}</td><td>${pct(baseline.stop_hit_rate_pct)}</td><td>${pct(baseline.avg_trade_return_pct)}</td><td>${pct(baseline.win_rate_pct)}</td><td>${fmt(baseline.profit_factor)}</td><td>${pct(baseline.avg_forward_return_pct)}</td></tr>
        <tr><td>with filter</td><td>${fmt(filtered.signals,0)}</td><td>${pct(filtered.target_hit_rate_pct)}</td><td>${pct(filtered.stop_hit_rate_pct)}</td><td>${pct(filtered.avg_trade_return_pct)}</td><td>${pct(filtered.win_rate_pct)}</td><td>${fmt(filtered.profit_factor)}</td><td>${pct(filtered.avg_forward_return_pct)}</td></tr>
        <tr><td>delta</td><td>${fmt(delta.signals,0)}</td><td>${pct(delta.target_hit_rate_pct)}</td><td>${pct(delta.stop_hit_rate_pct)}</td><td>${pct(delta.avg_trade_return_delta_pct)}</td><td>${pct(delta.win_rate_delta_pct)}</td><td>${fmt(delta.profit_factor_delta)}</td><td>${pct(delta.avg_forward_return_pct)}</td></tr>
      </tbody></table></div><p>${escapeHtml(comparison?.interpretation || "")}</p></section>`;
    }
    function examplesBlock(examples) {
      const groups = Object.entries(examples || {});
      return `<section class="card"><h2>Examples</h2>${groups.map(([key, values]) => `
        <h3>${escapeHtml(key)}</h3>
        <div class="table-wrap"><table><thead><tr><th>ticker</th><th>date</th><th>regime</th><th>outcome</th><th>return</th></tr></thead><tbody>
          ${(values || []).slice(0,8).map(row => `<tr><td>${escapeHtml(row.ticker)}</td><td>${escapeHtml(row.date)}</td><td>${escapeHtml(row.market_regime_name)}</td><td>${escapeHtml(row.outcome)}</td><td>${pct(row.forward_return_pct)}</td></tr>`).join("") || `<tr><td colspan="5">Нет примеров</td></tr>`}
        </tbody></table></div>`).join("")}</section>`;
    }
    async function loadEvaluation() {
      const status = document.getElementById("status");
      status.textContent = "Считаю historical regime evaluation...";
      try {
        const response = await fetch(`/signals/consumer/regime-historical-evaluation?${query().toString()}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}: ${await response.text()}`);
        const data = await response.json();
        const summary = data.summary || {};
        document.getElementById("summary").innerHTML = [
          metric("samples", fmt(summary.samples,0)),
          metric("best regime", summary.best_regime || "—", "good"),
          metric("worst regime", summary.worst_regime || "—", "bad"),
          metric("risk_off stop", pct(summary.risk_off_stop_hit_rate_pct), "bad"),
          metric("risk_on target", pct(summary.risk_on_target_hit_rate_pct), "good"),
        ].join("");
        document.getElementById("content").innerHTML = [
          regimeTable(data.by_market_regime),
          comparisonTable(data.regime_filter_comparison),
          examplesBlock(data.examples),
          `<section class="card"><h2>Limitations</h2><ul>${(data.limitations || []).map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul></section>`
        ].join("");
        status.innerHTML = "Готово."
          + (Number(summary.samples || 0) === 0 ? ' <a href="/signals/data-coverage-page">Проверить Data coverage</a>' : "");
      } catch (error) {
        status.textContent = `Ошибка: ${error.message}`;
      }
    }
    window.loadEvaluation = loadEvaluation;
    loadEvaluation();
  </script>
</body>
</html>"""
