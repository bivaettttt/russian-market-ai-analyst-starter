from __future__ import annotations


def build_ml_v2_gate_walk_forward_page_html() -> str:
    return """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>ML v2 Gate Walk-forward</title>
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
    th:first-child, td:first-child, th:nth-child(2), td:nth-child(2) { text-align:left; }
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
      <h1>ML v2 Gate Walk-forward</h1>
      <p>Leakage-safe проверка ML v2 gate: каждый fold обучает модель только на train-period и оценивает gate на будущем test-period.</p>
      <nav>
        <a href="/signals">← Сигналы</a>
        <a href="/signals/ml-v2/report-page">ML v2 report</a>
        <a href="/signals/ml-v2/high-confidence-page">ML v2 high-confidence</a>
        <a href="/signals/ml-v2/gate-impact-page">ML v2 gate impact</a>
        <a href="/signals/consumer/adaptive-trade-calibration-page">Target/Stop calibration</a>
        <a href="/signals/consumer/expectancy-breakdown-page">Expectancy breakdown</a>
      </nav>
    </div>
  </header>
  <main>
    <section class="toolbar">
      <label>max_tickers<input id="maxTickers" type="number" value="80" min="1" max="300" /></label>
      <label>max_samples<input id="maxSamples" type="number" value="3000" min="300" max="50000" /></label>
      <label>folds<input id="folds" type="number" value="4" min="2" max="8" /></label>
      <label>train_ratio<input id="trainRatio" type="number" value="0.6" min="0.4" max="0.85" step="0.05" /></label>
      <label>thresholds<input id="thresholds" value="0.50,0.55,0.60,0.65,0.70" /></label>
      <label>gate_modes<input id="gateModes" value="diagnostic_only,soft_downgrade,hard_gate" /></label>
      <label>commission_bps<input id="commissionBps" type="number" value="10" min="0" max="100" /></label>
      <label>slippage_bps<input id="slippageBps" type="number" value="5" min="0" max="100" /></label>
      <label>min_signals<input id="minSignals" type="number" value="50" min="10" max="5000" /></label>
      <button class="button" onclick="loadReport()">Запустить leakage-safe gate walk-forward</button>
    </section>
    <div id="status" class="status">Готово к запуску.</div>
    <section id="summary" class="summary"></section>
    <section class="grid">
      <div class="card"><h2>Best results</h2><div id="results"></div></div>
      <div class="card"><h2>Folds</h2><div id="foldsTable"></div></div>
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
      q.set("folds", document.getElementById("folds").value);
      q.set("train_ratio", document.getElementById("trainRatio").value);
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
      return `<div class="table-wrap"><table><thead><tr><th>mode</th><th>threshold</th><th>signals</th><th>coverage</th><th>avg return</th><th>PF</th><th>win</th><th>stop</th><th>positive folds</th><th>score</th><th>quality</th></tr></thead><tbody>${rows.map(row => `<tr><td>${esc(row.gate_mode)}</td><td>${fmt(row.threshold_pct, 1)}</td><td>${row.total_selected_samples}</td><td>${fmt(row.avg_coverage_pct)}</td><td>${fmt(row.avg_selected_trade_return_pct)}</td><td>${fmt(row.avg_selected_profit_factor, 3)}</td><td>${fmt(row.avg_selected_win_rate_pct)}</td><td>${fmt(row.avg_selected_stop_hit_rate_pct)}</td><td>${row.positive_folds}</td><td>${fmt(row.score)}</td><td>${esc(row.quality_label)}</td></tr>`).join("")}</tbody></table></div>`;
    }
    function foldsTable(rows) {
      if (!rows || !rows.length) return '<div class="muted">—</div>';
      return `<div class="table-wrap"><table><thead><tr><th>fold</th><th>train</th><th>test</th><th>AUC</th><th>Brier</th><th>baseline PF</th><th>best fold</th><th>warnings</th></tr></thead><tbody>${rows.map(row => { const best = row.best_fold_result || {}; return `<tr><td>${row.fold}</td><td>${esc((row.train_period || {}).first_date)} → ${esc((row.train_period || {}).last_date)}<div class="muted">${(row.train_period || {}).samples || 0} samples</div></td><td>${esc((row.test_period || {}).first_date)} → ${esc((row.test_period || {}).last_date)}<div class="muted">${(row.test_period || {}).samples || 0} samples</div></td><td>${fmt(row.auc, 4)}</td><td>${fmt(row.brier, 4)}</td><td>${fmt((row.baseline_metrics || {}).profit_factor, 3)}</td><td>${esc(best.gate_mode || "—")} ${fmt(best.threshold_pct, 1)} PF ${fmt(best.selected_profit_factor, 3)}</td><td>${esc((row.warnings || []).join("; "))}</td></tr>` }).join("")}</tbody></table></div>`;
    }
    async function loadReport() {
      const status = document.getElementById("status");
      status.textContent = "Считаю leakage-safe walk-forward...";
      try {
        const response = await fetch(`/signals/ml-v2/gate-walk-forward?${params().toString()}`);
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "request failed");
        const s = data.summary || {};
        document.getElementById("summary").innerHTML = [
          card("samples", s.samples),
          card("folds", s.folds_completed),
          card("best mode", s.best_gate_mode || "—"),
          card("best threshold", fmt(s.best_threshold_pct, 1)),
          card("best score", fmt(s.best_score)),
          card("quality", s.best_quality_label || "—"),
          card("recommendation", s.recommendation || "—")
        ].join("");
        document.getElementById("results").innerHTML = resultTable(data.best_results || []);
        document.getElementById("foldsTable").innerHTML = foldsTable(data.folds || []);
        document.getElementById("notes").innerHTML = `<ul>${[...((s.warnings || [])), ...((data.limitations || []))].map(item => `<li>${esc(item)}</li>`).join("") || "<li>—</li>"}</ul>`;
        status.textContent = `Готово: folds=${s.folds_completed || 0}, recommendation=${s.recommendation || "—"}.`;
      } catch (error) {
        status.textContent = `Ошибка: ${error.message}`;
      }
    }
  </script>
</body>
</html>
"""
