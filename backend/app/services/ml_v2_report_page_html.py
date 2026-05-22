from __future__ import annotations


def build_ml_v2_report_page_html() -> str:
    return """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>ML v2 Trade PnL Research</title>
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
    .summary { display:grid; grid-template-columns:repeat(6, minmax(0,1fr)); gap:12px; margin:16px 0; }
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
      <h1>ML v2 Trade PnL Research</h1>
      <p>Оценивает ML v2 labels для positive PnL, target hit, avoid stop и good trade. Research layer, production ML v1 не заменяется.</p>
      <nav>
        <a href="/signals">← Сигналы</a>
        <a href="/signals/ml/report-page">ML v1 report</a>
        <a href="/signals/consumer/adaptive-trade-calibration-page">Target/Stop calibration</a>
        <a href="/signals/consumer/composite-rule-calibration-page">Composite rules</a>
        <a href="/signals/data-coverage-page">Data coverage</a>
      </nav>
    </div>
  </header>
  <main>
    <section class="toolbar">
      <label>max_tickers<input id="maxTickers" type="number" value="80" min="1" max="300" /></label>
      <label>max_samples<input id="maxSamples" type="number" value="3000" min="100" max="50000" /></label>
      <label>horizon<input id="horizon" type="number" value="30" min="5" max="90" /></label>
      <label>label<select id="label"><option value="positive_trade_return">positive_trade_return</option><option value="target_hit">target_hit</option><option value="avoid_stop">avoid_stop</option><option value="good_trade">good_trade</option></select></label>
      <label>policy_id<input id="policyId" value="atr_t1_5_s1_6_h30_rr0_8" /></label>
      <label>commission_bps<input id="commissionBps" type="number" value="10" min="0" max="100" /></label>
      <label>slippage_bps<input id="slippageBps" type="number" value="5" min="0" max="100" /></label>
      <button class="button" onclick="loadReport()">Оценить ML v2</button>
    </section>
    <div id="status" class="status">Готово к запуску.</div>
    <section id="summary" class="summary"></section>
    <section class="grid">
      <div class="card"><h2>Threshold report</h2><div id="thresholds"></div></div>
      <div class="card"><h2>Feature importance</h2><div id="features"></div></div>
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
      q.set("horizon", document.getElementById("horizon").value);
      q.set("label", document.getElementById("label").value);
      q.set("policy_id", document.getElementById("policyId").value);
      q.set("commission_bps", document.getElementById("commissionBps").value);
      q.set("slippage_bps", document.getElementById("slippageBps").value);
      return q;
    }
    function card(label, value, cls = "") {
      return `<div class="card metric"><div class="label">${esc(label)}</div><div class="value ${cls}">${esc(value)}</div></div>`;
    }
    function thresholdTable(rows) {
      if (!rows || !rows.length) return '<div class="muted">—</div>';
      return `<div class="table-wrap"><table><thead><tr><th>threshold</th><th>signals</th><th>coverage</th><th>avg prob</th><th>hit</th><th>avg trade</th><th>PF</th><th>win</th><th>stop</th></tr></thead><tbody>${rows.map(row => `<tr><td>${fmt(row.threshold_pct, 1)}</td><td>${row.signals}</td><td>${fmt(row.coverage_pct)}</td><td>${fmt(row.avg_probability_pct)}</td><td>${fmt(row.hit_rate_pct)}</td><td>${fmt(row.avg_trade_return_pct)}</td><td>${fmt(row.profit_factor, 3)}</td><td>${fmt(row.win_rate_pct)}</td><td>${fmt(row.stop_hit_rate_pct)}</td></tr>`).join("")}</tbody></table></div>`;
    }
    function featureTable(rows) {
      if (!rows || !rows.length) return '<div class="muted">No feature importance available for this model.</div>';
      return `<div class="table-wrap"><table><thead><tr><th>feature</th><th>importance</th></tr></thead><tbody>${rows.slice(0, 20).map(row => `<tr><td>${esc(row.feature)}</td><td>${fmt(row.importance, 6)}</td></tr>`).join("")}</tbody></table></div>`;
    }
    async function loadReport() {
      const status = document.getElementById("status");
      status.textContent = "Считаю ML v2 evaluation...";
      try {
        const response = await fetch(`/signals/ml-v2/evaluation?${params().toString()}`);
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "request failed");
        if (!data.ok) {
          status.textContent = `Нет оценки: ${data.message || "ok=false"}`;
          document.getElementById("notes").innerHTML = `<ul>${(data.warnings || []).map(item => `<li>${esc(item)}</li>`).join("") || "<li>—</li>"}</ul>`;
          return;
        }
        const m = data.metrics || {};
        const ds = data.dataset_summary || {};
        document.getElementById("summary").innerHTML = [
          card("samples", ds.samples),
          card("label", data.label),
          card("auc", fmt(m.auc, 4)),
          card("brier", fmt(m.brier, 4)),
          card("baseline positive", fmt(m.baseline_positive_rate_pct)),
          card("test avg trade", fmt(m.test_avg_trade_return_pct), Number(m.test_avg_trade_return_pct || 0) >= 0 ? "good" : "bad")
        ].join("");
        document.getElementById("thresholds").innerHTML = thresholdTable(data.threshold_report || []);
        document.getElementById("features").innerHTML = featureTable(data.feature_importance || []);
        document.getElementById("notes").innerHTML = `<ul>${[...(data.warnings || []), ...(data.limitations || [])].map(item => `<li>${esc(item)}</li>`).join("") || "<li>—</li>"}</ul>`;
        status.textContent = `Готово: test samples=${(data.test_period || {}).samples || 0}.`;
      } catch (error) {
        status.textContent = `Ошибка: ${error.message}`;
      }
    }
  </script>
</body>
</html>
"""
