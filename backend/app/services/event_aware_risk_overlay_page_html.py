from __future__ import annotations


def build_event_aware_risk_overlay_page_html() -> str:
    return """<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Event-Aware Risk Overlay</title>
  <style>
    body { margin: 0; font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f6f7fb; color: #172033; }
    header { padding: 24px 32px; background: #111827; color: white; }
    main { padding: 24px 32px 48px; max-width: 1280px; margin: 0 auto; }
    nav a { color: #dbeafe; margin-right: 14px; font-size: 14px; }
    .panel { background: white; border: 1px solid #d8dee9; border-radius: 8px; padding: 16px; margin: 16px 0; }
    .controls { display: flex; flex-wrap: wrap; gap: 12px; align-items: end; }
    label { display: grid; gap: 4px; font-size: 13px; color: #475569; }
    input, select { padding: 8px 10px; border: 1px solid #cbd5e1; border-radius: 6px; min-width: 120px; }
    button { border: 0; border-radius: 6px; background: #2563eb; color: white; padding: 9px 14px; cursor: pointer; }
    button.secondary { background: #475569; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
    .metric { border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; background: #fbfdff; }
    .metric .v { font-size: 24px; font-weight: 700; }
    .metric .k { color: #64748b; font-size: 12px; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { padding: 8px; border-bottom: 1px solid #e2e8f0; text-align: left; vertical-align: top; }
    th { color: #475569; background: #f8fafc; }
    .muted { color: #64748b; }
    .warning { color: #b45309; }
    .bad { color: #b91c1c; }
    .good { color: #047857; }
  </style>
</head>
<body>
  <header>
    <h1>Event-Aware Risk Overlay v1</h1>
    <nav>
      <a href="/signals">Signals</a>
      <a href="/signals/event-aware/rule-stability-page">Rule stability</a>
      <a href="/signals/event-aware/dual-side-page">Dual-side risk</a>
      <a href="/signals/event-aware/research-page">Event-aware research</a>
      <a href="/signals/event-aware/risk-overlay-walk-forward-page">Risk overlay WF</a>
      <a href="/signals/event-aware/risk-overlay-conservative-page">Conservative overlay</a>
    </nav>
  </header>
  <main>
    <section class="panel">
      <p class="muted">Overlay не блокирует сделки по умолчанию: он рассчитывает event risk score, снижает диагностический размер позиции и повышает требования к probability/RR.</p>
      <div class="controls">
        <label>max_tickers <input id="maxTickers" type="number" value="80" min="1" max="300"></label>
        <label>max_samples <input id="maxSamples" type="number" value="3000" min="100" max="50000"></label>
        <label>max_events <input id="maxEvents" type="number" value="10000" min="0" max="50000"></label>
        <label>overlay_mode
          <select id="overlayMode">
            <option value="soft_adjust" selected>soft_adjust</option>
            <option value="diagnostic_only">diagnostic_only</option>
            <option value="experimental_downgrade">experimental_downgrade</option>
          </select>
        </label>
        <label>lookback <input id="lookback" type="number" value="7" min="0" max="90"></label>
        <label>decay <input id="decay" type="number" value="14" min="1" max="180"></label>
        <label>commission bps <input id="commission" type="number" value="10" min="0" max="100"></label>
        <label>slippage bps <input id="slippage" type="number" value="5" min="0" max="100"></label>
        <button onclick="runBacktest()">Run backtest</button>
        <button class="secondary" onclick="runCompare()">Current compare</button>
      </div>
    </section>
    <section class="panel">
      <h2>Backtest summary</h2>
      <div id="summary" class="grid"></div>
      <h3>By overlay mode</h3>
      <div id="modes"></div>
      <h3>By risk level</h3>
      <div id="levels"></div>
    </section>
    <section class="panel">
      <h2>Current snapshot compare</h2>
      <div id="compare"></div>
    </section>
    <section class="panel">
      <h2>Limitations</h2>
      <ul id="limitations"><li>Run a backtest to load limitations.</li></ul>
    </section>
  </main>
  <script>
    const fmt = v => v === null || v === undefined ? "—" : (typeof v === "number" ? v.toFixed(Math.abs(v) < 10 ? 2 : 1) : v);
    const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
    function params() {
      const p = new URLSearchParams();
      p.set("max_tickers", maxTickers.value);
      p.set("max_samples", maxSamples.value);
      p.set("max_events", maxEvents.value);
      p.set("event_lookback_days", lookback.value);
      p.set("event_decay_days", decay.value);
      p.set("commission_bps", commission.value);
      p.set("slippage_bps", slippage.value);
      p.set("overlay_modes", overlayMode.value);
      return p;
    }
    function table(rows, cols) {
      if (!rows || !rows.length) return "<p class='muted'>Нет данных.</p>";
      return `<table><thead><tr>${cols.map(c => `<th>${esc(c[0])}</th>`).join("")}</tr></thead><tbody>${rows.map(r => `<tr>${cols.map(c => `<td>${esc(fmt(r[c[1]]))}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
    }
    async function runBacktest() {
      summary.innerHTML = "<p class='muted'>Loading...</p>";
      const res = await fetch(`/signals/event-aware/risk-overlay-backtest?${params().toString()}`);
      const data = await res.json();
      const s = data.summary || {};
      summary.innerHTML = [
        ["samples", s.samples],
        ["baseline avg", s.baseline_avg_trade_return_pct],
        ["overlay avg", s.overlay_weighted_avg_return_pct],
        ["baseline PF", s.baseline_profit_factor],
        ["overlay PF", s.overlay_weighted_profit_factor],
        ["exposure reduction", s.exposure_reduction_pct],
        ["recommendation", s.recommendation]
      ].map(x => `<div class="metric"><div class="v">${esc(fmt(x[1]))}</div><div class="k">${esc(x[0])}</div></div>`).join("");
      modes.innerHTML = table(data.by_overlay_mode || [], [["mode","overlay_mode"],["samples","samples"],["base avg","baseline_avg_trade_return_pct"],["overlay avg","overlay_weighted_avg_return_pct"],["base PF","baseline_profit_factor"],["overlay PF","overlay_weighted_profit_factor"],["exposure red.","exposure_reduction_pct"],["delta","risk_adjusted_return_delta_pct"]]);
      levels.innerHTML = table(data.by_risk_level || [], [["risk","risk_level"],["samples","samples"],["avg","avg_trade_return_pct"],["PF","profit_factor"],["stop","stop_hit_rate_pct"],["mult","avg_position_multiplier"]]);
      limitations.innerHTML = (data.limitations || []).map(x => `<li>${esc(x)}</li>`).join("");
    }
    async function runCompare() {
      compare.innerHTML = "<p class='muted'>Loading...</p>";
      const res = await fetch(`/signals/consumer/event-risk-overlay-compare?limit=50&event_risk_overlay_mode=${encodeURIComponent(overlayMode.value)}`);
      const data = await res.json();
      compare.innerHTML = `<pre>${esc(JSON.stringify(data.summary || {}, null, 2))}</pre>` + table(data.risk_rows || [], [["ticker","ticker"],["action","action"],["risk","risk_level"],["score","risk_score"],["mult","position_multiplier"],["addon","probability_addon_pct"]]);
    }
    runBacktest();
  </script>
</body>
</html>"""
