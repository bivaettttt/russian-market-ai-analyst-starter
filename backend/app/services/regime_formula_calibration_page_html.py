from __future__ import annotations


def build_regime_formula_calibration_page_html() -> str:
    return """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Regime formula calibration</title>
  <style>
    :root { color-scheme: light; --bg:#f6f7f9; --panel:#fff; --text:#111827; --muted:#6b7280; --line:#d7dce3; --accent:#2563eb; --bad:#b91c1c; --good:#047857; --warn:#b45309; }
    * { box-sizing: border-box; }
    body { margin:0; background:var(--bg); color:var(--text); font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
    header { padding:18px 22px; border-bottom:1px solid var(--line); background:var(--panel); position:sticky; top:0; z-index:2; }
    h1 { margin:0 0 8px; font-size:22px; }
    nav { display:flex; gap:10px; flex-wrap:wrap; }
    nav a { color:var(--accent); text-decoration:none; font-weight:600; }
    main { padding:18px 22px 32px; max-width:1480px; margin:0 auto; }
    .controls, .cards, .panel { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:14px; margin-bottom:14px; }
    .controls { display:grid; grid-template-columns:repeat(5, minmax(130px, 1fr)); gap:10px; align-items:end; }
    label { display:grid; gap:4px; color:var(--muted); font-size:12px; font-weight:600; }
    input { width:100%; border:1px solid var(--line); border-radius:6px; padding:8px 9px; font:inherit; color:var(--text); background:#fff; }
    button { border:0; border-radius:6px; padding:9px 12px; background:var(--accent); color:white; font-weight:700; cursor:pointer; }
    button:disabled { opacity:.55; cursor:wait; }
    .cards { display:grid; grid-template-columns:repeat(7, minmax(130px, 1fr)); gap:10px; }
    .card { border:1px solid var(--line); border-radius:8px; padding:10px; min-height:76px; }
    .label { color:var(--muted); font-size:12px; font-weight:700; }
    .value { font-size:20px; font-weight:800; margin-top:6px; }
    .good { color:var(--good); } .bad { color:var(--bad); } .warn { color:var(--warn); }
    table { width:100%; border-collapse:collapse; }
    th, td { padding:8px 9px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }
    th { color:var(--muted); font-size:12px; position:sticky; top:83px; background:var(--panel); z-index:1; }
    code { white-space:pre-wrap; word-break:break-word; font-size:12px; }
    .muted { color:var(--muted); }
    .error { color:var(--bad); font-weight:700; }
    @media (max-width: 960px) { .controls, .cards { grid-template-columns:repeat(2, minmax(0, 1fr)); } th { position:static; } }
  </style>
</head>
<body>
  <header>
    <h1>Regime formula calibration</h1>
    <nav>
      <a href="/signals">Signals</a>
      <a href="/signals/consumer/backtest-audit-page">Backtest audit</a>
      <a href="/signals/consumer/threshold-sweep-page">Threshold sweep</a>
      <a href="/signals/consumer/walk-forward-page">Walk-forward</a>
      <a href="/signals/consumer/regime-historical-evaluation-page">Regime evaluation</a>
      <a href="/signals/consumer/adaptive-trade-calibration-page">Target/Stop calibration</a>
    </nav>
  </header>
  <main>
    <section class="controls">
      <label>max_tickers<input id="max_tickers" type="number" min="1" max="300" value="10"></label>
      <label>max_samples<input id="max_samples" type="number" min="100" max="30000" value="300"></label>
      <label>lookback<input id="lookback" type="number" min="20" max="250" value="60"></label>
      <label>horizon<input id="horizon" type="number" min="5" max="90" value="20"></label>
      <label>target_pct<input id="target_pct" type="number" min="0.005" max="0.25" step="0.005" value="0.05"></label>
      <label>stop_pct<input id="stop_pct" type="number" min="0.005" max="0.20" step="0.005" value="0.03"></label>
      <label>min_history<input id="min_history" type="number" min="30" max="250" value="80"></label>
      <label>max_configs<input id="max_configs" type="number" min="10" max="300" value="30"></label>
      <label>min_signals_after_filter<input id="min_signals_after_filter" type="number" min="1" max="1000" value="30"></label>
      <button id="run" type="button">Запустить calibration</button>
    </section>
    <section id="status" class="panel muted">Нажмите кнопку, чтобы запустить исследовательскую калибровку формулы режима.</section>
    <section id="summary" class="cards" style="display:none"></section>
    <section class="panel">
      <h2>Best configs</h2>
      <div id="best"></div>
    </section>
    <section class="panel">
      <h2>Limitations / warnings</h2>
      <div id="notes" class="muted"></div>
    </section>
  </main>
  <script>
    const ids = ["max_tickers","max_samples","lookback","horizon","target_pct","stop_pct","min_history","max_configs","min_signals_after_filter"];
    const el = (id) => document.getElementById(id);
    const fmt = (v) => v === null || v === undefined ? "—" : v;
    function query() {
      const params = new URLSearchParams();
      ids.forEach((id) => params.set(id, el(id).value));
      return params;
    }
    function card(label, value, cls="") {
      return `<div class="card"><div class="label">${label}</div><div class="value ${cls}">${fmt(value)}</div></div>`;
    }
    function renderTable(rows) {
      if (!rows || !rows.length) return '<div class="muted">Нет данных.</div>';
      return `<table><thead><tr>
        <th>#</th><th>score</th><th>quality</th><th>filtered</th><th>coverage</th><th>stop delta</th><th>target delta</th><th>return delta</th><th>avoided</th><th>missed</th><th>config</th><th>formula</th>
      </tr></thead><tbody>${rows.map((row) => `<tr>
        <td>${fmt(row.rank)}</td>
        <td>${fmt(row.score)}</td>
        <td>${fmt(row.quality_label)}</td>
        <td>${fmt(row.filtered_signals)}</td>
        <td>${fmt(row.coverage_after_filter_pct)}%</td>
        <td>${fmt(row.stop_hit_delta_pct)}</td>
        <td>${fmt(row.target_hit_delta_pct)}</td>
        <td>${fmt(row.avg_return_delta_pct)}</td>
        <td>${fmt(row.avoided_stop_hits)}</td>
        <td>${fmt(row.missed_target_hits)}</td>
        <td><code>${fmt(row.config_id)}</code></td>
        <td><code>${JSON.stringify(row.formula_config || {})}</code></td>
      </tr>`).join("")}</tbody></table>`;
    }
    async function run() {
      el("run").disabled = true;
      el("status").className = "panel muted";
      el("status").textContent = "Считаю calibration...";
      try {
        const response = await fetch(`/signals/consumer/regime-formula-calibration?${query().toString()}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        const summary = data.summary || {};
        const best = (data.best_configs || [])[0] || {};
        el("summary").style.display = "grid";
        el("summary").innerHTML = [
          card("configs_tested", summary.configs_tested),
          card("best_score", summary.best_score, (summary.best_score || 0) >= 0 ? "good" : "bad"),
          card("quality", summary.best_quality_label),
          card("recommendation", summary.recommendation),
          card("baseline stop", (summary.baseline_summary || {}).stop_hit_rate_pct),
          card("filtered stop", (summary.best_filtered_summary || {}).stop_hit_rate_pct),
          card("return delta", best.avg_return_delta_pct, (best.avg_return_delta_pct || 0) >= 0 ? "good" : "bad"),
        ].join("");
        el("best").innerHTML = renderTable(data.best_configs || []);
        const warnings = (summary.warnings || []).map((item) => `<div class="warn">${item}</div>`).join("");
        const limits = (data.limitations || []).map((item) => `<div>• ${item}</div>`).join("");
        el("notes").innerHTML = warnings + limits;
        el("status").textContent = `Готово: ${summary.configs_tested || 0} configs.`;
      } catch (err) {
        el("status").className = "panel error";
        el("status").textContent = `Ошибка: ${err.message || err}`;
      } finally {
        el("run").disabled = false;
      }
    }
    el("run").addEventListener("click", run);
  </script>
</body>
</html>
"""
