from __future__ import annotations


def build_ml_v2_gate_impact_page_html() -> str:
    return """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>ML v2 Gate Impact Evaluation</title>
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
    .toolbar { display:grid; grid-template-columns:repeat(4, minmax(150px, 1fr)); gap:12px; align-items:end; }
    label { color:var(--muted); font-size:12px; font-weight:850; text-transform:uppercase; letter-spacing:.04em; }
    input, select { width:100%; margin-top:6px; border:1px solid var(--border); border-radius:8px; padding:10px; font:inherit; color:var(--text); background:white; }
    .button { background:#0f172a; border:1px solid #0f172a; border-radius:8px; color:white; height:40px; padding:0 14px; font-weight:850; cursor:pointer; }
    .status { margin:14px 0; color:var(--muted); }
    .summary { display:grid; grid-template-columns:repeat(7, minmax(0,1fr)); gap:12px; margin:16px 0; }
    .metric .label { color:var(--muted); font-size:12px; font-weight:850; text-transform:uppercase; }
    .metric .value { margin-top:6px; font-size:22px; font-weight:900; overflow-wrap:anywhere; }
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
    code { background:#f1f5f9; border:1px solid var(--border); border-radius:6px; padding:2px 5px; }
    ul { margin:8px 0 0 18px; padding:0; }
    @media (max-width:1100px) { .toolbar, .summary { grid-template-columns:1fr; } }
  </style>
</head>
<body>
  <header>
    <div class="inner">
      <h1>ML v2 Gate Impact Evaluation</h1>
      <p>Artifact-based research simulation сравнивает diagnostic-only, soft downgrade и hard gate режимы. Production consumer logic не меняется.</p>
      <nav>
        <a href="/signals">← Сигналы</a>
        <a href="/signals/ml-v2/report-page">ML v2 report</a>
        <a href="/signals/ml-v2/high-confidence-page">ML v2 high-confidence</a>
        <a href="/signals/consumer/adaptive-trade-calibration-page">Target/Stop calibration</a>
        <a href="/signals/consumer/expectancy-breakdown-page">Expectancy breakdown</a>
        <a href="/signals/data-coverage-page">Data coverage</a>
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
      <label>min_signals<input id="minSignals" type="number" value="30" min="10" max="5000" /></label>
      <button class="button" onclick="loadReport()">Оценить ML v2 gate impact</button>
    </section>
    <div id="status" class="status">Готово к запуску.</div>
    <section id="summary" class="summary"></section>
    <section class="grid">
      <div class="card"><h2>Best results</h2><div id="results"></div></div>
      <div class="card"><h2>Diagnostic buckets</h2><div id="diagnostics"></div></div>
      <div class="card"><h2>Warnings & limitations</h2><div id="notes"></div></div>
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
      return q;
    }
    function card(label, value, cls = "") {
      return `<div class="card metric"><div class="label">${esc(label)}</div><div class="value ${cls}">${esc(value)}</div></div>`;
    }
    function resultTable(rows) {
      if (!rows || !rows.length) return '<div class="muted">—</div>';
      return `<div class="table-wrap"><table><thead><tr><th>rank</th><th>mode</th><th>threshold</th><th>selected</th><th>coverage</th><th>avg trade</th><th>PF</th><th>avg delta</th><th>PF delta</th><th>win delta</th><th>stop delta</th><th>avoided</th><th>missed</th><th>score</th><th>quality</th></tr></thead><tbody>${rows.map(row => `<tr><td>${row.rank}</td><td>${esc(row.gate_mode)}</td><td>${fmt(row.threshold_pct, 1)}</td><td>${row.selected_samples}</td><td>${fmt(row.coverage_pct)}</td><td>${fmt(row.selected_avg_trade_return_pct)}</td><td>${fmt(row.selected_profit_factor, 3)}</td><td>${fmt(row.avg_trade_return_delta_pct)}</td><td>${fmt(row.profit_factor_delta, 3)}</td><td>${fmt(row.win_rate_delta_pct)}</td><td>${fmt(row.stop_hit_delta_pct)}</td><td>${row.avoided_losses}</td><td>${row.missed_wins}</td><td>${fmt(row.score)}</td><td>${esc(row.quality_label)}</td></tr>`).join("")}</tbody></table></div>`;
    }
    function diagnosticTable(rows) {
      if (!rows || !rows.length) return '<div class="muted">—</div>';
      return `<div class="table-wrap"><table><thead><tr><th>threshold</th><th>passed</th><th>rejected</th><th>passed avg</th><th>rejected avg</th><th>passed PF</th><th>rejected PF</th><th>passed stop</th><th>rejected stop</th></tr></thead><tbody>${rows.map(row => `<tr><td>${fmt(row.threshold_pct, 1)}</td><td>${row.passed_samples}</td><td>${row.rejected_samples}</td><td>${fmt(row.passed_avg_trade_return_pct)}</td><td>${fmt(row.rejected_avg_trade_return_pct)}</td><td>${fmt(row.passed_profit_factor, 3)}</td><td>${fmt(row.rejected_profit_factor, 3)}</td><td>${fmt(row.passed_stop_hit_rate_pct)}</td><td>${fmt(row.rejected_stop_hit_rate_pct)}</td></tr>`).join("")}</tbody></table></div>`;
    }
    async function loadReport() {
      const status = document.getElementById("status");
      status.textContent = "Считаю ML v2 gate impact...";
      try {
        const response = await fetch(`/signals/ml-v2/gate-impact?${params().toString()}`);
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "request failed");
        const s = data.summary || {};
        const base = s.baseline_metrics || {};
        document.getElementById("summary").innerHTML = [
          card("samples", s.samples ?? "—"),
          card("baseline avg", fmt(base.avg_trade_return_pct)),
          card("baseline PF", fmt(base.profit_factor, 3)),
          card("best mode", s.best_mode || "—"),
          card("best threshold", fmt(s.best_threshold_pct, 1)),
          card("best score", fmt(s.best_score)),
          card("recommendation", s.recommendation || data.recommendation || "—")
        ].join("");
        document.getElementById("results").innerHTML = resultTable(data.best_results || []);
        document.getElementById("diagnostics").innerHTML = diagnosticTable(data.diagnostic_buckets || []);
        const missing = data.error === "ml_v2_artifact_not_available";
        const train = missing ? ['Run: <code>cd backend && python3 -m app.tasks.train_ml_v2 --label positive_trade_return --max-tickers 120 --max-samples 10000 --horizon 30</code>'] : [];
        document.getElementById("notes").innerHTML = `<ul>${[...train, ...((s.warnings || [])), ...((data.limitations || []))].map(item => `<li>${item}</li>`).join("") || "<li>—</li>"}</ul>`;
        status.textContent = data.ok ? `Готово: recommendation=${s.recommendation || "—"}.` : `Нет оценки: ${data.error || "ok=false"}.`;
      } catch (error) {
        status.textContent = `Ошибка: ${error.message}`;
      }
    }
  </script>
</body>
</html>
"""
