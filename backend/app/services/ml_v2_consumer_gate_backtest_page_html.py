from __future__ import annotations


def build_ml_v2_consumer_gate_backtest_page_html() -> str:
    return """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Consumer ML v2 Gate Backtest</title>
  <style>
    :root { --bg:#f6f8fb; --card:#fff; --text:#111827; --muted:#64748b; --border:#dbe3ef; --green:#047857; --red:#b91c1c; --amber:#92400e; }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--text); font-family:Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    header { background:#102033; color:white; padding:28px 20px; }
    .inner, main { max-width:1320px; margin:0 auto; }
    h1 { margin:0 0 8px; font-size:30px; letter-spacing:0; }
    header p { margin:0; color:#cbd5e1; max-width:980px; line-height:1.5; }
    nav { margin-top:16px; display:flex; gap:10px; flex-wrap:wrap; }
    nav a { border:1px solid rgba(255,255,255,.24); border-radius:8px; color:white; padding:9px 12px; text-decoration:none; font-weight:750; }
    main { padding:22px 20px 42px; }
    .toolbar, .panel, .metric { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:16px; box-shadow:0 10px 22px rgba(15,23,42,.05); }
    .toolbar { display:grid; grid-template-columns:repeat(5, minmax(140px, 1fr)); gap:12px; align-items:end; }
    label { color:var(--muted); font-size:12px; font-weight:850; text-transform:uppercase; }
    input { width:100%; margin-top:6px; border:1px solid var(--border); border-radius:8px; padding:10px; font:inherit; color:var(--text); background:white; }
    .check { display:flex; gap:8px; align-items:center; text-transform:none; font-size:13px; color:var(--text); }
    .check input { width:auto; margin:0; }
    button { background:#102033; border:1px solid #102033; border-radius:8px; color:white; min-height:40px; padding:0 14px; font-weight:850; cursor:pointer; }
    .status { margin:14px 0; color:var(--muted); }
    .summary { display:grid; grid-template-columns:repeat(6, minmax(0,1fr)); gap:12px; margin:16px 0; }
    .metric .label { color:var(--muted); font-size:12px; font-weight:850; text-transform:uppercase; }
    .metric .value { margin-top:6px; font-size:21px; font-weight:900; overflow-wrap:anywhere; }
    .grid { display:grid; grid-template-columns:1fr; gap:16px; }
    h2 { margin:0 0 12px; font-size:18px; }
    table { width:100%; border-collapse:collapse; font-size:13px; }
    th, td { padding:9px 8px; border-bottom:1px solid var(--border); text-align:right; white-space:nowrap; vertical-align:top; }
    th:first-child, td:first-child, th:nth-child(2), td:nth-child(2), th:nth-child(3), td:nth-child(3) { text-align:left; }
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
      <h1>Consumer ML v2 Gate Backtest</h1>
      <p>Historical research backtest проверяет experimental ML v2 decision gate именно на proxy consumer-сигналах. Production default не меняется.</p>
      <nav>
        <a href="/signals">Сигналы</a>
        <a href="/signals/ml-v2/gate-walk-forward-page">ML v2 gate walk-forward</a>
        <a href="/signals/ml-v2/gate-impact-page">ML v2 gate impact</a>
        <a href="/signals/ml-v2/high-confidence-page">ML v2 high-confidence</a>
        <a href="/signals/consumer/backtest-audit-page">Backtest audit</a>
        <a href="/signals/consumer/adaptive-trade-calibration-page">Adaptive calibration</a>
      </nav>
    </div>
  </header>
  <main>
    <section class="toolbar">
      <label>max_tickers<input id="maxTickers" type="number" value="80" min="1" max="300" /></label>
      <label>max_samples<input id="maxSamples" type="number" value="3000" min="300" max="50000" /></label>
      <label>thresholds<input id="thresholds" value="0.50,0.55,0.60,0.65,0.70" /></label>
      <label>gate_modes<input id="gateModes" value="diagnostic_only,soft_downgrade,hard_gate" /></label>
      <label>commission_bps<input id="commissionBps" type="number" value="10" min="0" max="100" /></label>
      <label>slippage_bps<input id="slippageBps" type="number" value="5" min="0" max="100" /></label>
      <label>min_signals<input id="minSignals" type="number" value="50" min="10" max="5000" /></label>
      <label>folds<input id="folds" type="number" value="4" min="2" max="8" /></label>
      <label class="check"><input id="leakageSafe" type="checkbox" checked /> leakage-safe predictions</label>
      <button onclick="loadReport()">Запустить consumer ML v2 gate backtest</button>
    </section>
    <div id="status" class="status">Готово к запуску.</div>
    <section id="summary" class="summary"></section>
    <section class="grid">
      <div class="panel"><h2>Results</h2><div id="results"></div></div>
      <div class="panel"><h2>Changed examples</h2><div id="examples"></div></div>
      <div class="panel"><h2>Warnings & limitations</h2><div id="notes"></div></div>
    </section>
  </main>
  <script>
    const esc = value => String(value ?? "—").replace(/[&<>"']/g, ch => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#039;" }[ch]));
    const fmt = (value, d = 2) => value === null || value === undefined || Number.isNaN(Number(value)) ? "—" : Number(value).toFixed(d);
    function params() {
      const q = new URLSearchParams();
      q.set("max_tickers", document.getElementById("maxTickers").value);
      q.set("max_samples", document.getElementById("maxSamples").value);
      q.set("thresholds", document.getElementById("thresholds").value);
      q.set("gate_modes", document.getElementById("gateModes").value);
      q.set("commission_bps", document.getElementById("commissionBps").value);
      q.set("slippage_bps", document.getElementById("slippageBps").value);
      q.set("min_signals", document.getElementById("minSignals").value);
      q.set("folds", document.getElementById("folds").value);
      q.set("use_leakage_safe_predictions", document.getElementById("leakageSafe").checked ? "true" : "false");
      return q;
    }
    function card(label, value) {
      return `<div class="metric"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div></div>`;
    }
    function resultsTable(rows) {
      if (!rows || !rows.length) return '<div class="muted">Нет результатов.</div>';
      return `<div class="table-wrap"><table><thead><tr><th>mode</th><th>threshold</th><th>selected</th><th>coverage</th><th>selected avg</th><th>selected PF</th><th>avg delta</th><th>PF delta</th><th>stop delta</th><th>changed</th><th>avoided losses</th><th>missed wins</th><th>quality</th></tr></thead><tbody>${rows.map(row => `<tr><td>${esc(row.gate_mode)}</td><td>${fmt(row.threshold_pct, 1)}</td><td>${row.selected_active_trades ?? row.selected_samples ?? "—"}</td><td>${fmt(row.coverage_pct)}</td><td>${fmt(row.selected_avg_trade_return_pct)}</td><td>${fmt(row.selected_profit_factor, 3)}</td><td>${fmt(row.avg_trade_return_delta_pct)}</td><td>${fmt(row.profit_factor_delta, 3)}</td><td>${fmt(row.stop_hit_delta_pct)}</td><td>${row.changed_actions ?? 0}</td><td>${row.avoided_losses ?? 0}</td><td>${row.missed_wins ?? 0}</td><td>${esc(row.quality_label)}</td></tr>`).join("")}</tbody></table></div>`;
    }
    function examplesTable(rows) {
      if (!rows || !rows.length) return '<div class="muted">Нет изменённых historical actions.</div>';
      return `<div class="table-wrap"><table><thead><tr><th>ticker</th><th>date</th><th>original</th><th>final</th><th>ML v2</th><th>return</th><th>outcome</th></tr></thead><tbody>${rows.map(row => `<tr><td>${esc(row.ticker)}</td><td>${esc(row.date)}</td><td>${esc(row.original_action)}</td><td>${esc(row.final_action)}</td><td>${fmt(row.ml_v2_probability_pct)}</td><td>${fmt(row.trade_return_pct)}</td><td>${esc(row.outcome)}</td></tr>`).join("")}</tbody></table></div>`;
    }
    async function loadReport() {
      const status = document.getElementById("status");
      status.textContent = "Считаю historical consumer ML v2 gate backtest...";
      try {
        const response = await fetch(`/signals/consumer/ml-v2-gate-backtest?${params().toString()}`);
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "request failed");
        const s = data.summary || {};
        const base = s.baseline_metrics || {};
        document.getElementById("summary").innerHTML = [
          card("baseline PF", fmt(base.baseline_profit_factor, 3)),
          card("baseline avg return", fmt(base.baseline_avg_trade_return_pct)),
          card("best gate mode", s.best_gate_mode || "—"),
          card("best threshold", fmt(s.best_threshold_pct, 1)),
          card("best score", fmt(s.best_score)),
          card("recommendation", s.recommendation || "—")
        ].join("");
        document.getElementById("results").innerHTML = resultsTable(data.results || data.best_results || []);
        document.getElementById("examples").innerHTML = examplesTable(data.changed_examples || []);
        const notes = [...(s.warnings || []), ...(data.limitations || [])];
        document.getElementById("notes").innerHTML = `<ul>${notes.map(item => `<li>${esc(item)}</li>`).join("") || "<li>—</li>"}</ul>`;
        status.textContent = data.ok ? `Готово: ${s.recommendation || "—"}.` : `Нет оценки: ${data.error || "ok=false"}.`;
      } catch (error) {
        status.textContent = `Ошибка: ${error.message}`;
      }
    }
  </script>
</body>
</html>
"""
