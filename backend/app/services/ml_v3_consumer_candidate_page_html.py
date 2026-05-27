from __future__ import annotations


def build_ml_v3_consumer_candidate_page_html() -> str:
    return """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>ML v3 Consumer Candidates</title>
  <style>
    :root { --bg:#f6f8fb; --card:#fff; --text:#111827; --muted:#64748b; --border:#dbe3ef; }
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
    input, select { width:100%; margin-top:6px; border:1px solid var(--border); border-radius:8px; padding:10px; font:inherit; color:var(--text); background:white; }
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
    th:first-child, td:first-child, th:nth-child(2), td:nth-child(2) { text-align:left; }
    th { color:var(--muted); font-size:11px; text-transform:uppercase; }
    .table-wrap { overflow-x:auto; }
    ul { margin:8px 0 0 18px; padding:0; }
    @media (max-width:1100px) { .toolbar, .summary { grid-template-columns:1fr; } }
  </style>
</head>
<body>
  <header>
    <div class="inner">
      <h1>ML v3 Consumer Candidates</h1>
      <p>Research-модель обучается только на historical consumer long-candidates и проверяется leakage-safe walk-forward.</p>
      <nav>
        <a href="/signals">Сигналы</a>
        <a href="/signals/consumer/ml-v2-gate-backtest-page">ML v2 consumer gate backtest</a>
        <a href="/signals/ml-v2/gate-walk-forward-page">ML v2 gate walk-forward</a>
        <a href="/signals/ml-v2/report-page">ML v2 report</a>
        <a href="/signals/setup-family/research-page">Setup families</a>
      </nav>
    </div>
  </header>
  <main>
    <section class="toolbar">
      <label>max_tickers<input id="maxTickers" type="number" value="80" min="1" max="300" /></label>
      <label>max_samples<input id="maxSamples" type="number" value="3000" min="100" max="50000" /></label>
      <label>folds<input id="folds" type="number" value="4" min="2" max="8" /></label>
      <label>label<select id="label"><option>positive_trade_return</option><option>good_trade</option><option>avoid_loss</option><option>target_hit</option><option>avoid_stop</option></select></label>
      <label>thresholds<input id="thresholds" value="0.40,0.45,0.50,0.55,0.60,0.65,0.70" /></label>
      <label>gate_modes<input id="gateModes" value="diagnostic_only,soft_downgrade,hard_gate" /></label>
      <label>commission_bps<input id="commissionBps" type="number" value="10" min="0" max="100" /></label>
      <label>slippage_bps<input id="slippageBps" type="number" value="5" min="0" max="100" /></label>
      <label class="check"><input id="includeWatch" type="checkbox" /> include watch candidates</label>
      <button onclick="loadAll()">Запустить ML v3 research</button>
    </section>
    <div id="status" class="status">Готово к запуску.</div>
    <section id="summary" class="summary"></section>
    <section class="grid">
      <div class="panel"><h2>Evaluation threshold report</h2><div id="eval"></div></div>
      <div class="panel"><h2>Walk-forward best results</h2><div id="wf"></div></div>
      <div class="panel"><h2>Folds</h2><div id="foldsTable"></div></div>
      <div class="panel"><h2>Feature importance</h2><div id="features"></div></div>
      <div class="panel"><h2>Warnings & limitations</h2><div id="notes"></div></div>
    </section>
  </main>
  <script>
    const esc = value => String(value ?? "—").replace(/[&<>"']/g, ch => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#039;" }[ch]));
    const fmt = (value, d = 2) => value === null || value === undefined || Number.isNaN(Number(value)) ? "—" : Number(value).toFixed(d);
    function params(base = true) {
      const q = new URLSearchParams();
      q.set("max_tickers", document.getElementById("maxTickers").value);
      q.set("max_samples", document.getElementById("maxSamples").value);
      q.set("commission_bps", document.getElementById("commissionBps").value);
      q.set("slippage_bps", document.getElementById("slippageBps").value);
      q.set("include_watch_candidates", document.getElementById("includeWatch").checked ? "true" : "false");
      if (!base) {
        q.set("label", document.getElementById("label").value);
        q.set("folds", document.getElementById("folds").value);
        q.set("thresholds", document.getElementById("thresholds").value);
        q.set("gate_modes", document.getElementById("gateModes").value);
      }
      return q;
    }
    function card(label, value) { return `<div class="metric"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div></div>`; }
    function table(rows, cols) {
      if (!rows || !rows.length) return "—";
      return `<div class="table-wrap"><table><thead><tr>${cols.map(c => `<th>${esc(c[0])}</th>`).join("")}</tr></thead><tbody>${rows.map(r => `<tr>${cols.map(c => `<td>${esc(typeof c[1] === "function" ? c[1](r) : r[c[1]])}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
    }
    async function getJson(url) {
      const response = await fetch(url);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "request failed");
      return data;
    }
    async function loadAll() {
      const status = document.getElementById("status");
      status.textContent = "Считаю ML v3 consumer candidate research...";
      try {
        const ds = await getJson(`/signals/ml-v3/consumer-candidate/dataset-summary?${params(true)}`);
        const ev = await getJson(`/signals/ml-v3/consumer-candidate/evaluation?${params(false)}`);
        const wf = await getJson(`/signals/ml-v3/consumer-candidate/walk-forward?${params(false)}&min_train_samples=300&min_test_samples=100&min_signals=30`);
        const s = ds.summary || {};
        const m = ev.metrics || {};
        const ws = wf.summary || {};
        document.getElementById("summary").innerHTML = [
          card("samples", s.samples ?? "—"),
          card("PF", fmt(s.profit_factor, 3)),
          card("avg return", fmt(s.avg_trade_return_pct)),
          card("AUC", fmt(m.auc, 3)),
          card("best gate", `${ws.best_gate_mode || "—"} ${fmt(ws.best_threshold_pct, 1)}`),
          card("recommendation", ws.recommendation || "—")
        ].join("");
        document.getElementById("eval").innerHTML = table(ev.threshold_report || [], [["threshold","threshold_pct"],["signals","signals"],["coverage", r => fmt(r.coverage_pct)],["avg", r => fmt(r.avg_trade_return_pct)],["PF", r => fmt(r.profit_factor, 3)],["win", r => fmt(r.win_rate_pct)],["stop", r => fmt(r.stop_hit_rate_pct)],["quality","quality_label"]]);
        document.getElementById("wf").innerHTML = table(wf.best_results || [], [["mode","gate_mode"],["threshold","threshold_pct"],["signals","total_selected_samples"],["coverage", r => fmt(r.avg_coverage_pct)],["avg", r => fmt(r.avg_selected_trade_return_pct)],["PF", r => fmt(r.avg_selected_profit_factor, 3)],["pos folds","positive_folds"],["quality","quality_label"],["score", r => fmt(r.score)]]);
        document.getElementById("foldsTable").innerHTML = table(wf.folds || [], [["fold","fold"],["train", r => (r.train_period || {}).samples],["test", r => (r.test_period || {}).samples],["auc", r => fmt(r.auc, 3)],["brier", r => fmt(r.brier, 3)]]);
        document.getElementById("features").innerHTML = table(ev.feature_importance || [], [["feature","feature"],["importance", r => fmt(r.importance, 6)]]);
        const notes = [...(ds.warnings || []), ...(ev.warnings || []), ...(wf.summary?.warnings || []), ...(wf.limitations || [])];
        document.getElementById("notes").innerHTML = `<ul>${notes.map(item => `<li>${esc(item)}</li>`).join("") || "<li>—</li>"}</ul>`;
        status.textContent = `Готово: ${ws.recommendation || "—"}.`;
      } catch (error) {
        status.textContent = `Ошибка: ${error.message}`;
      }
    }
  </script>
</body>
</html>
"""
