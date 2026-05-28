from __future__ import annotations


def build_event_aware_walk_forward_page_html() -> str:
    return """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Event-Aware Walk-Forward</title>
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
    .summary { display:grid; grid-template-columns:repeat(6, minmax(0,1fr)); gap:12px; margin:16px 0; }
    .metric .label { color:var(--muted); font-size:12px; font-weight:850; text-transform:uppercase; }
    .metric .value { margin-top:6px; font-size:20px; font-weight:900; overflow-wrap:anywhere; }
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
    <h1>Event-Aware Walk-Forward</h1>
    <p>Leakage-safe validation: combos выбираются только на train window и проверяются на будущих test samples.</p>
    <nav>
      <a href="/signals">Сигналы</a>
      <a href="/signals/event-aware/research-page">Event-aware setups</a>
      <a href="/signals/event-aware/rule-search-page">Event rule search</a>
      <a href="/signals/event-aware/risk-overlay-page">Risk overlay</a>
      <a href="/signals/event-aware/risk-overlay-walk-forward-page">Risk overlay WF</a>
      <a href="/signals/event-aware/dual-side-page">Dual-side event risk</a>
      <a href="/signals/event-aware/rule-stability-page">Rule stability</a>
      <a href="/signals/setup-family/research-page">Setup families</a>
    </nav>
  </div></header>
  <main>
    <section class="toolbar">
      <label>max_tickers<input id="maxTickers" type="number" value="80" min="1" max="300" /></label>
      <label>max_samples<input id="maxSamples" type="number" value="3000" min="100" max="50000" /></label>
      <label>max_events<input id="maxEvents" type="number" value="10000" min="0" max="50000" /></label>
      <label>folds<input id="folds" type="number" value="4" min="2" max="8" /></label>
      <label>top_k<input id="topK" type="number" value="5" min="1" max="30" /></label>
      <label>lookback<input id="lookback" type="number" value="7" min="0" max="90" /></label>
      <label>decay<input id="decay" type="number" value="14" min="1" max="180" /></label>
      <label>min_signals<input id="minSignals" type="number" value="10" min="1" max="1000" /></label>
      <label>commission_bps<input id="commissionBps" type="number" value="10" min="0" max="100" /></label>
      <label>slippage_bps<input id="slippageBps" type="number" value="5" min="0" max="100" /></label>
      <button onclick="loadWF()">Run walk-forward</button>
    </section>
    <div id="status" class="status">Готово к запуску.</div>
    <section id="summary" class="summary"></section>
    <section class="grid">
      <div class="panel"><h2>Folds</h2><div id="foldTable"></div></div>
      <div class="panel"><h2>Selected combo frequency</h2><div id="comboTable"></div></div>
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
    async function loadWF() {
      status.textContent = "Считаю event-aware walk-forward...";
      const q = new URLSearchParams();
      q.set("max_tickers", maxTickers.value); q.set("max_samples", maxSamples.value); q.set("max_events", maxEvents.value);
      q.set("folds", folds.value); q.set("top_k_combos", topK.value); q.set("event_lookback_days", lookback.value); q.set("event_decay_days", decay.value);
      q.set("min_signals", minSignals.value); q.set("commission_bps", commissionBps.value); q.set("slippage_bps", slippageBps.value);
      const data = await getJson(`/signals/event-aware/walk-forward?${q}`);
      const s = data.summary || {};
      summary.innerHTML = [card("event samples", s.event_samples), card("folds", s.folds_completed), card("avg return", fmt(s.avg_test_selected_return_pct)), card("avg PF", fmt(s.avg_test_selected_profit_factor, 3)), card("positive folds", s.positive_folds), card("recommendation", s.recommendation)].join("");
      foldTable.innerHTML = table(data.folds || [], [["fold","fold"],["train", r => `${(r.train_period||{}).first_date}..${(r.train_period||{}).last_date}`],["test", r => `${(r.test_period||{}).first_date}..${(r.test_period||{}).last_date}`],["combos", r => (r.selected_combos||[]).length],["selected", r => (r.test_selected_metrics||{}).samples],["avg", r => fmt((r.test_selected_metrics||{}).avg_trade_return_pct)],["PF", r => fmt((r.test_selected_metrics||{}).profit_factor, 3)],["delta", r => fmt((r.delta_vs_baseline||{}).avg_trade_return_delta_pct)],["quality","quality_label"],["top ticker", r => fmt((r.concentration||{}).top_ticker_share_pct)]]);
      comboTable.innerHTML = table(data.selected_combo_frequency || [], [["combo","combo_key"],["folds","selected_folds"],["train score", r => fmt(r.avg_train_score)],["test avg", r => fmt(r.avg_test_return_pct)],["test PF", r => fmt(r.avg_test_profit_factor, 3)]]);
      notes.innerHTML = `<ul>${[...((s.warnings)||[]), ...((data.limitations)||[]), ...((data.folds||[]).flatMap(f => f.warnings || []))].map(x => `<li>${esc(x)}</li>`).join("")}</ul>`;
      status.textContent = `Готово: ${s.recommendation || "—"}.`;
    }
  </script>
</body>
</html>
"""
