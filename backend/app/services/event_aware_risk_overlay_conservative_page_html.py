from __future__ import annotations


def build_event_aware_risk_overlay_conservative_page_html() -> str:
    return """<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Conservative Event Risk Overlay</title>
  <style>
    body { margin: 0; font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f6f7fb; color: #172033; }
    header { padding: 24px 32px; background: #111827; color: white; }
    main { padding: 24px 32px 48px; max-width: 1280px; margin: 0 auto; }
    nav a { color: #dbeafe; margin-right: 14px; font-size: 14px; }
    .panel { background: white; border: 1px solid #d8dee9; border-radius: 8px; padding: 16px; margin: 16px 0; }
    .controls { display: flex; flex-wrap: wrap; gap: 12px; align-items: end; }
    label { display: grid; gap: 4px; font-size: 13px; color: #475569; }
    input { padding: 8px 10px; border: 1px solid #cbd5e1; border-radius: 6px; min-width: 120px; }
    button { border: 0; border-radius: 6px; background: #2563eb; color: white; padding: 9px 14px; cursor: pointer; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
    .metric { border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; background: #fbfdff; }
    .metric .v { font-size: 24px; font-weight: 700; }
    .metric .k { color: #64748b; font-size: 12px; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { padding: 8px; border-bottom: 1px solid #e2e8f0; text-align: left; vertical-align: top; }
    th { color: #475569; background: #f8fafc; }
    .muted { color: #64748b; }
  </style>
</head>
<body>
  <header>
    <h1>Conservative Event Risk Overlay</h1>
    <nav>
      <a href="/signals">Signals</a>
      <a href="/signals/event-aware/risk-overlay-page">Risk overlay</a>
      <a href="/signals/event-aware/risk-overlay-walk-forward-page">Risk overlay WF</a>
      <a href="/signals/event-aware/rule-stability-page">Rule stability</a>
      <a href="/signals/event-aware/conservative-overlay-paper-tracking-page">Overlay tracking</a>
    </nav>
  </header>
  <main>
    <section class="panel">
      <p class="muted">Ищет более мягкий overlay: avg multiplier >= target, exposure reduction <= limit, при сохранении PF/stop-hit improvements.</p>
      <div class="controls">
        <label>max_tickers <input id="maxTickers" type="number" value="80" min="1" max="300"></label>
        <label>max_samples <input id="maxSamples" type="number" value="3000" min="100" max="50000"></label>
        <label>max_events <input id="maxEvents" type="number" value="10000" min="0" max="50000"></label>
        <label>folds <input id="folds" type="number" value="4" min="2" max="8"></label>
        <label>max_configs <input id="maxConfigs" type="number" value="100" min="5" max="300"></label>
        <label>min multiplier <input id="minMultiplier" type="number" value="0.5" min="0.1" max="1" step="0.05"></label>
        <label>max exposure reduction <input id="maxExposure" type="number" value="50" min="0" max="95"></label>
        <label>min PF folds <input id="minPfFolds" type="number" value="3" min="1" max="8"></label>
        <label>lookback <input id="lookback" type="number" value="7" min="0" max="90"></label>
        <label>decay <input id="decay" type="number" value="14" min="1" max="180"></label>
        <label>commission bps <input id="commission" type="number" value="10" min="0" max="100"></label>
        <label>slippage bps <input id="slippage" type="number" value="5" min="0" max="100"></label>
        <button onclick="run()">Run calibration</button>
      </div>
    </section>
    <section class="panel"><h2>Summary</h2><div id="summary" class="grid"></div></section>
    <section class="panel"><h2>Folds</h2><div id="foldTable"></div></section>
    <section class="panel"><h2>Config frequency</h2><div id="freqTable"></div></section>
    <section class="panel"><h2>Benchmark comparison</h2><div id="benchTable"></div></section>
    <section class="panel"><h2>Limitations / warnings</h2><ul id="limitations"><li>Run calibration to load limitations.</li></ul></section>
  </main>
  <script>
    const fmt = v => v === null || v === undefined ? "—" : (typeof v === "number" ? v.toFixed(Math.abs(v) < 10 ? 3 : 1) : v);
    const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
    function params() {
      const p = new URLSearchParams();
      p.set("max_tickers", maxTickers.value);
      p.set("max_samples", maxSamples.value);
      p.set("max_events", maxEvents.value);
      p.set("folds", folds.value);
      p.set("max_configs", maxConfigs.value);
      p.set("min_avg_position_multiplier", minMultiplier.value);
      p.set("max_exposure_reduction_pct", maxExposure.value);
      p.set("min_positive_pf_folds", minPfFolds.value);
      p.set("event_lookback_days", lookback.value);
      p.set("event_decay_days", decay.value);
      p.set("commission_bps", commission.value);
      p.set("slippage_bps", slippage.value);
      return p;
    }
    function table(rows, cols) {
      if (!rows || !rows.length) return "<p class='muted'>Нет данных.</p>";
      return `<table><thead><tr>${cols.map(c => `<th>${esc(c[0])}</th>`).join("")}</tr></thead><tbody>${rows.map(r => `<tr>${cols.map(c => `<td>${esc(fmt(c[2] ? c[2](r) : r[c[1]])))}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
    }
    async function run() {
      summary.innerHTML = "<p class='muted'>Loading...</p>";
      const res = await fetch(`/signals/event-aware/risk-overlay-conservative-calibration?${params().toString()}`);
      const data = await res.json();
      const s = data.summary || {};
      summary.innerHTML = [
        ["return delta", s.avg_weighted_return_delta_pct],
        ["PF delta", s.avg_weighted_profit_factor_delta],
        ["stop delta", s.avg_stop_hit_exposure_delta_pct],
        ["avg multiplier", s.avg_position_multiplier],
        ["exposure reduction", s.avg_exposure_reduction_pct],
        ["positive PF folds", s.positive_pf_delta_folds],
        ["recommendation", s.recommendation]
      ].map(x => `<div class="metric"><div class="v">${esc(fmt(x[1]))}</div><div class="k">${esc(x[0])}</div></div>`).join("");
      foldTable.innerHTML = table(data.folds || [], [
        ["fold","fold"],
        ["config","selected_config", r => (r.selected_config || {}).config_id],
        ["ret delta","test_metrics", r => (r.test_metrics || {}).weighted_return_delta_pct],
        ["PF delta","test_metrics", r => (r.test_metrics || {}).weighted_profit_factor_delta],
        ["stop delta","test_metrics", r => (r.test_metrics || {}).stop_hit_exposure_delta_pct],
        ["mult","test_metrics", r => (r.test_metrics || {}).avg_position_multiplier],
        ["exposure","test_metrics", r => (r.test_metrics || {}).exposure_reduction_pct],
        ["quality","test_metrics", r => (r.test_metrics || {}).quality_label]
      ]);
      freqTable.innerHTML = table(data.config_frequency || [], [["config","config_id"],["folds","selected_folds"],["train score","avg_train_conservative_score"],["test PF delta","avg_test_pf_delta"],["mult","avg_position_multiplier"]]);
      const bench = Object.entries(data.benchmark_comparison || {}).map(([k, v]) => ({name: k, ...(v || {})}));
      benchTable.innerHTML = table(bench, [["benchmark","name"],["ret delta","weighted_return_delta_pct"],["PF delta","weighted_profit_factor_delta"],["stop delta","stop_hit_exposure_delta_pct"],["mult","avg_position_multiplier"],["exposure","exposure_reduction_pct"],["score","conservative_score"]]);
      limitations.innerHTML = [...(data.warnings || []), ...(data.limitations || [])].map(x => `<li>${esc(x)}</li>`).join("");
    }
    run();
  </script>
</body>
</html>"""
