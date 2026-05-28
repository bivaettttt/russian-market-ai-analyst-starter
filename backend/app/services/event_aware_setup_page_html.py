from __future__ import annotations


def build_event_aware_setup_page_html() -> str:
    return """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Event-Aware Setup Research</title>
  <style>
    :root { --bg:#f7f8fb; --card:#fff; --text:#111827; --muted:#64748b; --border:#d8e1ee; --accent:#12324a; }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--text); font-family:Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    header { background:var(--accent); color:white; padding:28px 20px; }
    .inner, main { max-width:1360px; margin:0 auto; }
    h1 { margin:0 0 8px; font-size:30px; }
    header p { margin:0; color:#d5e1ee; max-width:1000px; line-height:1.5; }
    nav { margin-top:16px; display:flex; gap:10px; flex-wrap:wrap; }
    nav a { color:white; text-decoration:none; border:1px solid rgba(255,255,255,.24); border-radius:8px; padding:9px 12px; font-weight:800; }
    main { padding:22px 20px 42px; }
    .toolbar, .panel, .metric { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:16px; box-shadow:0 10px 22px rgba(15,23,42,.05); }
    .toolbar { display:grid; grid-template-columns:repeat(5, minmax(140px, 1fr)); gap:12px; align-items:end; }
    label { color:var(--muted); font-size:12px; font-weight:850; text-transform:uppercase; }
    input { width:100%; margin-top:6px; border:1px solid var(--border); border-radius:8px; padding:10px; font:inherit; color:var(--text); background:white; }
    button { background:var(--accent); border:1px solid var(--accent); border-radius:8px; color:white; min-height:40px; padding:0 14px; font-weight:850; cursor:pointer; }
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
    <h1>Event-Aware Setup Research</h1>
    <p>Research layer проверяет, появляется ли edge, когда technical setup подтверждается новостным, макро или геополитическим катализатором. Production consumer logic не меняется.</p>
    <nav>
      <a href="/signals">Сигналы</a>
      <a href="/signals/setup-family/research-page">Setup families</a>
      <a href="/signals/ml-v3/consumer-candidate/page">ML v3 consumer candidates</a>
      <a href="/signals/consumer/backtest-audit-page">Backtest audit</a>
      <a href="/signals/event-aware/walk-forward-page">Event-aware walk-forward</a>
      <a href="/signals/event-aware/rule-search-page">Event rule search</a>
      <a href="/signals/event-aware/risk-overlay-page">Risk overlay</a>
      <a href="/signals/event-aware/dual-side-page">Dual-side event risk</a>
      <a href="/signals/event-aware/rule-stability-page">Rule stability</a>
      <a href="/signals/events/bootstrap-status">Bootstrap status JSON</a>
    </nav>
  </div></header>
  <main>
    <section class="toolbar">
      <label>max_tickers<input id="maxTickers" type="number" value="80" min="1" max="300" /></label>
      <label>max_samples<input id="maxSamples" type="number" value="3000" min="100" max="50000" /></label>
      <label>max_events<input id="maxEvents" type="number" value="5000" min="0" max="50000" /></label>
      <label>lookback days<input id="lookback" type="number" value="7" min="0" max="90" /></label>
      <label>decay days<input id="decay" type="number" value="14" min="1" max="180" /></label>
      <label>min_signals<input id="minSignals" type="number" value="20" min="1" max="5000" /></label>
      <label>commission_bps<input id="commissionBps" type="number" value="10" min="0" max="100" /></label>
      <label>slippage_bps<input id="slippageBps" type="number" value="5" min="0" max="100" /></label>
      <label>max_configs<input id="maxConfigs" type="number" value="60" min="1" max="300" /></label>
      <button onclick="loadCoverage()">Event coverage</button>
      <button onclick="loadResearch()">Run research</button>
      <button onclick="loadSweep()">Run sweep</button>
    </section>
    <div id="status" class="status">Готово к запуску.</div>
    <section id="summary" class="summary"></section>
    <section class="grid">
      <div class="panel"><h2>Event coverage</h2><div id="coverage"></div></div>
      <div class="panel"><h2>By event family</h2><div id="byFamily"></div></div>
      <div class="panel"><h2>Setup + event combinations</h2><div id="combos"></div></div>
      <div class="panel"><h2>Parameter sweep</h2><div id="sweep"></div></div>
      <div class="panel"><h2>Examples</h2><div id="examples"></div></div>
      <div class="panel"><h2>Warnings & limitations</h2><div id="notes"></div></div>
    </section>
  </main>
  <script>
    const esc = value => String(value ?? "—").replace(/[&<>"']/g, ch => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#039;" }[ch]));
    const fmt = (value, d = 2) => value === null || value === undefined || Number.isNaN(Number(value)) ? "—" : Number(value).toFixed(d);
    const card = (label, value) => `<div class="metric"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div></div>`;
    function table(rows, cols) {
      if (!rows || !rows.length) return "—";
      return `<div class="table-wrap"><table><thead><tr>${cols.map(c => `<th>${esc(c[0])}</th>`).join("")}</tr></thead><tbody>${rows.map(r => `<tr>${cols.map(c => `<td>${esc(typeof c[1] === "function" ? c[1](r) : r[c[1]])}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
    }
    async function getJson(url) { const r = await fetch(url); const d = await r.json(); if (!r.ok) throw new Error(d.detail || "request failed"); return d; }
    function commonParams() {
      const q = new URLSearchParams();
      q.set("max_tickers", maxTickers.value);
      q.set("max_samples", maxSamples.value);
      q.set("max_events", maxEvents.value);
      q.set("min_signals", minSignals.value);
      q.set("commission_bps", commissionBps.value);
      q.set("slippage_bps", slippageBps.value);
      return q;
    }
    async function loadCoverage() {
      status.textContent = "Проверяю coverage событий...";
      const data = await getJson(`/signals/events/coverage?max_events=${encodeURIComponent(maxEvents.value)}`);
      const s = data.summary || {};
      coverage.innerHTML = table(Object.entries(s.by_event_family || {}).map(([family, count]) => ({family, count})), [["family","family"],["count","count"]]);
      summary.innerHTML = [card("events", s.total_events), card("with ticker", s.events_with_ticker), card("with date", s.events_with_date), card("date range", `${(s.date_range || {}).from || "—"} / ${(s.date_range || {}).to || "—"}`), card("warnings", (data.warnings || []).length)].join("");
      notes.innerHTML = `<ul>${(data.warnings || []).map(x => `<li>${esc(x)}</li>`).join("")}</ul>`;
      status.textContent = "Coverage готов.";
    }
    async function loadResearch() {
      status.textContent = "Считаю event-aware research...";
      const q = commonParams(); q.set("event_lookback_days", lookback.value); q.set("event_decay_days", decay.value);
      const data = await getJson(`/signals/event-aware/research?${q}`);
      const s = data.summary || {};
      summary.innerHTML = [card("event samples", s.event_samples), card("confirmed", s.setup_event_confirmed_samples), card("events used", s.events_used), card("best", s.best_group_key), card("recommendation", s.recommendation)].join("");
      byFamily.innerHTML = table(data.by_event_family || [], [["family","event_family"],["samples","samples"],["avg", r => fmt(r.avg_trade_return_pct)],["PF", r => fmt(r.profit_factor, 3)],["win", r => fmt(r.win_rate_pct)],["quality","quality_label"]]);
      combos.innerHTML = table(data.by_setup_event_combo || [], [["combo","group_key"],["samples","samples"],["avg", r => fmt(r.avg_trade_return_pct)],["PF", r => fmt(r.profit_factor, 3)],["win", r => fmt(r.win_rate_pct)],["stop", r => fmt(r.stop_hit_rate_pct)],["quality","quality_label"]]);
      examples.innerHTML = table((data.examples || {}).best_examples || [], [["ticker","ticker"],["date","date"],["setup","setup_family"],["event","event_family"],["dir","event_direction"],["score", r => fmt(r.event_score)],["return", r => fmt(r.trade_return_pct)],["outcome","outcome"]]);
      notes.innerHTML = `<ul>${[...((s.warnings)||[]), ...((data.limitations)||[])].map(x => `<li>${esc(x)}</li>`).join("")}</ul>`;
      status.textContent = `Готово: ${s.recommendation || "—"}.`;
    }
    async function loadSweep() {
      status.textContent = "Считаю event-aware sweep...";
      const q = commonParams(); q.set("max_configs", maxConfigs.value);
      const data = await getJson(`/signals/event-aware/sweep?${q}`);
      sweep.innerHTML = table(data.best_configs || [], [["config","config_id"],["samples","samples"],["avg", r => fmt(r.avg_trade_return_pct)],["PF", r => fmt(r.profit_factor, 3)],["win", r => fmt(r.win_rate_pct)],["stop", r => fmt(r.stop_hit_rate_pct)],["quality","quality_label"],["score", r => fmt(r.score)],["params", r => JSON.stringify(r.config || {})]]);
      status.textContent = "Sweep готов.";
    }
  </script>
</body>
</html>
"""
