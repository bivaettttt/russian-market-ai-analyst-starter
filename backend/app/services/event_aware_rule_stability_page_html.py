from __future__ import annotations


def build_event_aware_rule_stability_page_html() -> str:
    return """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Event Rule Stability</title>
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
    .metric .value { margin-top:6px; font-size:19px; font-weight:900; overflow-wrap:anywhere; }
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
    <h1>Event Rule Stability</h1>
    <p>Diagnostics for why static event risk rules do or do not transfer across years, regimes, buckets, tickers and event families.</p>
    <nav>
      <a href="/signals">Сигналы</a>
      <a href="/signals/event-aware/research-page">Event-aware setups</a>
      <a href="/signals/event-aware/walk-forward-page">Event-aware walk-forward</a>
      <a href="/signals/event-aware/rule-search-page">Event rule search</a>
      <a href="/signals/event-aware/risk-overlay-page">Risk overlay</a>
      <a href="/signals/event-aware/dual-side-page">Dual-side event risk</a>
    </nav>
  </div></header>
  <main>
    <section class="toolbar">
      <label>max_tickers<input id="maxTickers" type="number" value="80" min="1" max="300" /></label>
      <label>max_samples<input id="maxSamples" type="number" value="3000" min="100" max="50000" /></label>
      <label>max_events<input id="maxEvents" type="number" value="10000" min="0" max="50000" /></label>
      <label>max_rules<input id="maxRules" type="number" value="120" min="10" max="500" /></label>
      <label>lookback<input id="lookback" type="number" value="7" min="0" max="90" /></label>
      <label>decay<input id="decay" type="number" value="14" min="1" max="180" /></label>
      <label>min_signals<input id="minSignals" type="number" value="20" min="1" max="1000" /></label>
      <label>commission_bps<input id="commissionBps" type="number" value="10" min="0" max="100" /></label>
      <label>slippage_bps<input id="slippageBps" type="number" value="5" min="0" max="100" /></label>
      <button onclick="loadStability()">Run stability diagnostics</button>
    </section>
    <div id="status" class="status">Готово к запуску.</div>
    <section id="summary" class="summary"></section>
    <section class="grid">
      <div class="panel"><h2>Stable / moderate rules</h2><div id="rules"></div></div>
      <div class="panel"><h2>Failure analysis</h2><div id="failure"></div></div>
      <div class="panel"><h2>Rule detail</h2><div id="detail"></div></div>
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
    async function loadStability() {
      status.textContent = "Считаю event rule stability...";
      const q = new URLSearchParams();
      q.set("max_tickers", maxTickers.value); q.set("max_samples", maxSamples.value); q.set("max_events", maxEvents.value);
      q.set("max_rules", maxRules.value); q.set("event_lookback_days", lookback.value); q.set("event_decay_days", decay.value);
      q.set("min_signals", minSignals.value); q.set("commission_bps", commissionBps.value); q.set("slippage_bps", slippageBps.value);
      const data = await getJson(`/signals/event-aware/rule-stability?${q}`);
      const s = data.summary || {}; const f = data.failure_analysis || {};
      summary.innerHTML = [card("rules", s.rules_tested), card("stable", s.stable_rules), card("moderate", s.moderate_rules), card("best", s.best_stable_rule_id), card("failure", s.primary_failure_reason), card("recommendation", s.recommendation)].join("");
      const rows = [...(data.stable_rules || []), ...(data.moderate_rules || [])];
      rules.innerHTML = table(rows, [["rule","rule_id"],["family","rule_family"],["samples","samples"],["score", r => fmt(r.stability_score)],["year", r => fmt(r.year_stability_rate_pct)],["bucket", r => fmt(r.bucket_stability_rate_pct)],["avoid", r => fmt(r.avg_avoid_long_benefit_pct)],["missed", r => fmt(r.avg_missed_upside_pct)],["conc","concentration_label"],["use","recommended_use"]]);
      failure.innerHTML = `<p><b>${esc(f.primary_failure_reason)}</b></p><ul>${(f.findings || []).map(x => `<li>${esc(x)}</li>`).join("")}</ul><p>Next: ${esc(f.recommended_next_step)}</p>`;
      const first = rows[0] || {};
      detail.innerHTML = `<h3>${esc(first.rule_id)}</h3>` + table(first.by_year || [], [["year","year"],["samples","samples"],["avg", r => fmt(r.avg_long_trade_return_pct)],["stop", r => fmt(r.long_stop_hit_rate_pct)],["avoid", r => fmt(r.avoid_benefit)],["missed", r => fmt(r.missed_upside)],["score", r => fmt(r.score)],["quality","quality_label"]]) + table(first.by_market_regime || [], [["regime","market_regime"],["samples","samples"],["avg", r => fmt(r.avg_long_trade_return_pct)],["stop", r => fmt(r.long_stop_hit_rate_pct)],["quality","quality_label"]]);
      notes.innerHTML = `<ul>${[...((s.warnings)||[]), ...((data.limitations)||[])].map(x => `<li>${esc(x)}</li>`).join("")}</ul>`;
      status.textContent = `Готово: ${s.recommendation || "—"}.`;
    }
  </script>
</body>
</html>
"""
