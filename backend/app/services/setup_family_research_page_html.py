from __future__ import annotations


def build_setup_family_research_page_html() -> str:
    return """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Setup Family Research</title>
  <style>
    :root { --bg:#f6f8fb; --card:#fff; --text:#111827; --muted:#64748b; --border:#dbe3ef; }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--text); font-family:Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    header { background:#102033; color:white; padding:28px 20px; }
    .inner, main { max-width:1320px; margin:0 auto; }
    h1 { margin:0 0 8px; font-size:30px; }
    header p { margin:0; color:#cbd5e1; max-width:980px; line-height:1.5; }
    nav { margin-top:16px; display:flex; gap:10px; flex-wrap:wrap; }
    nav a { border:1px solid rgba(255,255,255,.24); border-radius:8px; color:white; padding:9px 12px; text-decoration:none; font-weight:750; }
    main { padding:22px 20px 42px; }
    .toolbar, .panel, .metric { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:16px; box-shadow:0 10px 22px rgba(15,23,42,.05); }
    .toolbar { display:grid; grid-template-columns:repeat(5, minmax(140px, 1fr)); gap:12px; align-items:end; }
    label { color:var(--muted); font-size:12px; font-weight:850; text-transform:uppercase; }
    input, select { width:100%; margin-top:6px; border:1px solid var(--border); border-radius:8px; padding:10px; font:inherit; color:var(--text); background:white; }
    button { background:#102033; border:1px solid #102033; border-radius:8px; color:white; min-height:40px; padding:0 14px; font-weight:850; cursor:pointer; }
    .status { margin:14px 0; color:var(--muted); }
    .summary { display:grid; grid-template-columns:repeat(5, minmax(0,1fr)); gap:12px; margin:16px 0; }
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
  <header><div class="inner">
    <h1>Setup Family Research</h1>
    <p>Research layer для поиска long setup families с положительной expectancy. Production consumer logic не меняется.</p>
    <nav>
      <a href="/signals">Сигналы</a>
      <a href="/signals/ml-v3/consumer-candidate/page">ML v3 consumer candidates</a>
      <a href="/signals/event-aware/research-page">Event-aware setups</a>
      <a href="/signals/event-aware/walk-forward-page">Event-aware walk-forward</a>
      <a href="/signals/event-aware/rule-search-page">Event rule search</a>
      <a href="/signals/consumer/backtest-audit-page">Backtest audit</a>
      <a href="/signals/consumer/adaptive-trade-calibration-page">Adaptive calibration</a>
    </nav>
  </div></header>
  <main>
    <section class="toolbar">
      <label>max_tickers<input id="maxTickers" type="number" value="80" min="1" max="300" /></label>
      <label>max_samples<input id="maxSamples" type="number" value="3000" min="100" max="50000" /></label>
      <label>horizon<input id="horizon" type="number" value="30" min="5" max="90" /></label>
      <label>min_signals<input id="minSignals" type="number" value="30" min="5" max="5000" /></label>
      <label>max_setups<input id="maxSetups" type="number" value="100" min="10" max="1000" /></label>
      <label>commission_bps<input id="commissionBps" type="number" value="10" min="0" max="100" /></label>
      <label>slippage_bps<input id="slippageBps" type="number" value="5" min="0" max="100" /></label>
      <label>setup_family<select id="setupFamily"><option value="">all</option><option>breakout</option><option>pullback</option><option>mean_reversion</option><option>volatility_squeeze</option><option>trend_following</option></select></label>
      <label>max_configs<input id="maxConfigs" type="number" value="60" min="5" max="300" /></label>
      <button onclick="loadResearch()">Run research</button>
      <button onclick="loadSweep()">Run sweep</button>
    </section>
    <div id="status" class="status">Готово к запуску.</div>
    <section id="summary" class="summary"></section>
    <section class="grid">
      <div class="panel"><h2>By setup family</h2><div id="families"></div></div>
      <div class="panel"><h2>Parameter sweep</h2><div id="sweep"></div></div>
      <div class="panel"><h2>Examples</h2><div id="examples"></div></div>
      <div class="panel"><h2>Warnings & limitations</h2><div id="notes"></div></div>
    </section>
  </main>
  <script>
    const esc = value => String(value ?? "—").replace(/[&<>"']/g, ch => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#039;" }[ch]));
    const fmt = (value, d = 2) => value === null || value === undefined || Number.isNaN(Number(value)) ? "—" : Number(value).toFixed(d);
    function commonParams() {
      const q = new URLSearchParams();
      q.set("max_tickers", maxTickers.value);
      q.set("max_samples", maxSamples.value);
      q.set("horizon", horizon.value);
      q.set("min_signals", minSignals.value);
      q.set("commission_bps", commissionBps.value);
      q.set("slippage_bps", slippageBps.value);
      return q;
    }
    function card(label, value) { return `<div class="metric"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div></div>`; }
    function table(rows, cols) {
      if (!rows || !rows.length) return "—";
      return `<div class="table-wrap"><table><thead><tr>${cols.map(c => `<th>${esc(c[0])}</th>`).join("")}</tr></thead><tbody>${rows.map(r => `<tr>${cols.map(c => `<td>${esc(typeof c[1] === "function" ? c[1](r) : r[c[1]])}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
    }
    async function getJson(url) { const r = await fetch(url); const d = await r.json(); if (!r.ok) throw new Error(d.detail || "request failed"); return d; }
    async function loadResearch() {
      status.textContent = "Считаю setup family research...";
      const q = commonParams(); q.set("max_setups", maxSetups.value);
      const data = await getJson(`/signals/setup-family/research?${q}`);
      const s = data.summary || {};
      summary.innerHTML = [card("samples", s.samples), card("best setup", s.best_setup_family), card("quality", s.best_quality_label), card("recommendation", s.recommendation), card("old PF", fmt((s.old_consumer_baseline || {}).profit_factor, 3))].join("");
      families.innerHTML = table(data.by_setup_family || [], [["family","setup_family"],["samples","samples"],["avg", r => fmt(r.avg_trade_return_pct)],["PF", r => fmt(r.profit_factor, 3)],["win", r => fmt(r.win_rate_pct)],["stop", r => fmt(r.stop_hit_rate_pct)],["quality","quality_label"]]);
      examples.innerHTML = table((data.examples || {}).best_setup_examples || [], [["ticker","ticker"],["date","date"],["family","setup_family"],["return", r => fmt(r.trade_return_pct)],["outcome","outcome"],["score", r => fmt(r.setup_score)]]);
      notes.innerHTML = `<ul>${[...((s.warnings)||[]), ...((data.limitations)||[])].map(x => `<li>${esc(x)}</li>`).join("")}</ul>`;
      status.textContent = `Готово: ${s.recommendation || "—"}.`;
    }
    async function loadSweep() {
      status.textContent = "Считаю parameter sweep...";
      const q = commonParams(); q.set("max_configs", maxConfigs.value); if (setupFamily.value) q.set("setup_family", setupFamily.value);
      const data = await getJson(`/signals/setup-family/sweep?${q}`);
      sweep.innerHTML = table(data.best_configs || [], [["config","config_id"],["family","setup_family"],["samples","samples"],["avg", r => fmt(r.avg_trade_return_pct)],["PF", r => fmt(r.profit_factor, 3)],["win", r => fmt(r.win_rate_pct)],["stop", r => fmt(r.stop_hit_rate_pct)],["quality","quality_label"],["score", r => fmt(r.score)]]);
      status.textContent = "Sweep готов.";
    }
  </script>
</body>
</html>
"""
