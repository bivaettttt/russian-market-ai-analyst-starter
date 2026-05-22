from __future__ import annotations


def build_adaptive_trade_calibration_page_html() -> str:
    return """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Adaptive target/stop calibration</title>
  <style>
    :root { --bg:#f6f7f9; --panel:#fff; --text:#111827; --muted:#6b7280; --line:#d7dce3; --accent:#2563eb; --bad:#b91c1c; --good:#047857; --warn:#b45309; }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--text); font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
    header { padding:18px 22px; background:var(--panel); border-bottom:1px solid var(--line); position:sticky; top:0; z-index:2; }
    h1 { margin:0 0 8px; font-size:22px; }
    nav { display:flex; flex-wrap:wrap; gap:10px; }
    nav a { color:var(--accent); text-decoration:none; font-weight:700; }
    main { max-width:1480px; margin:0 auto; padding:18px 22px 32px; }
    .controls, .cards, .panel { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:14px; margin-bottom:14px; }
    .controls { display:grid; grid-template-columns:repeat(6, minmax(130px, 1fr)); gap:10px; align-items:end; }
    label { display:grid; gap:4px; color:var(--muted); font-size:12px; font-weight:700; }
    input { width:100%; border:1px solid var(--line); border-radius:6px; padding:8px 9px; font:inherit; }
    button { border:0; border-radius:6px; padding:9px 12px; background:var(--accent); color:white; font-weight:800; cursor:pointer; }
    button:disabled { opacity:.55; cursor:wait; }
    .cards { display:grid; grid-template-columns:repeat(8, minmax(120px, 1fr)); gap:10px; }
    .card { border:1px solid var(--line); border-radius:8px; padding:10px; min-height:76px; }
    .label { color:var(--muted); font-size:12px; font-weight:800; }
    .value { margin-top:6px; font-size:19px; font-weight:850; }
    .good { color:var(--good); } .bad { color:var(--bad); } .warn { color:var(--warn); } .muted { color:var(--muted); }
    table { width:100%; border-collapse:collapse; }
    th, td { padding:8px 9px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }
    th { color:var(--muted); font-size:12px; position:sticky; top:83px; background:var(--panel); z-index:1; }
    code { white-space:pre-wrap; word-break:break-word; font-size:12px; }
    .error { color:var(--bad); font-weight:800; }
    @media (max-width: 960px) { .controls, .cards { grid-template-columns:repeat(2, minmax(0, 1fr)); } th { position:static; } }
  </style>
</head>
<body>
  <header>
    <h1>Adaptive Target / Stop / RR Calibration</h1>
    <nav>
      <a href="/signals">Signals</a>
      <a href="/signals/consumer/backtest-audit-page">Backtest audit</a>
      <a href="/signals/consumer/threshold-sweep-page">Threshold sweep</a>
      <a href="/signals/consumer/walk-forward-page">Walk-forward</a>
      <a href="/signals/consumer/regime-historical-evaluation-page">Regime evaluation</a>
      <a href="/signals/consumer/regime-formula-calibration-page">Regime calibration</a>
      <a href="/signals/consumer/expectancy-breakdown-page">Expectancy breakdown</a>
        <a href="/signals/consumer/candidate-filter-calibration-page">Filter calibration</a>
      <a href="/signals/consumer/composite-rule-calibration-page">Composite rules</a>
      <a href="/signals/ml-v2/high-confidence-page">ML v2 high-confidence</a>
      <a href="/signals/ml-v2/gate-impact-page">ML v2 gate impact</a>
      <a href="/signals/ml-v2/gate-walk-forward-page">ML v2 gate walk-forward</a>
      <a href="/signals/data-coverage-page">Data coverage</a>
    </nav>
  </header>
  <main>
    <section class="controls">
      <label>max_tickers<input id="max_tickers" type="number" min="1" max="300" value="10"></label>
      <label>max_samples<input id="max_samples" type="number" min="100" max="30000" value="300"></label>
      <label>max_policies<input id="max_policies" type="number" min="5" max="300" value="30"></label>
      <label>min_samples_per_policy<input id="min_samples_per_policy" type="number" min="1" max="1000" value="30"></label>
      <label>min_history<input id="min_history" type="number" min="30" max="250" value="80"></label>
      <label>commission_bps<input id="commission_bps" type="number" min="0" max="100" step="1" value="0"></label>
      <label>slippage_bps<input id="slippage_bps" type="number" min="0" max="100" step="1" value="0"></label>
      <button id="run" type="button">Запустить target/stop calibration</button>
    </section>
    <section id="status" class="panel muted">Запустите calibration, чтобы сравнить fixed, ATR и volatility-scaled policies.</section>
    <section id="summary" class="cards" style="display:none"></section>
    <section class="panel">
      <h2>Best policies</h2>
      <div id="best"></div>
    </section>
    <section class="panel">
      <h2>Limitations / warnings</h2>
      <div id="notes" class="muted"></div>
    </section>
  </main>
  <script>
    const ids = ["max_tickers","max_samples","max_policies","min_samples_per_policy","min_history","commission_bps","slippage_bps"];
    const el = (id) => document.getElementById(id);
    const fmt = (v) => v === null || v === undefined ? "—" : v;
    function params() {
      const q = new URLSearchParams();
      ids.forEach((id) => q.set(id, el(id).value));
      return q;
    }
    function card(label, value, cls="") {
      return `<div class="card"><div class="label">${label}</div><div class="value ${cls}">${fmt(value)}</div></div>`;
    }
    function renderTable(rows) {
      if (!rows || !rows.length) return '<div class="muted">Нет данных.</div>';
      return `<table><thead><tr>
        <th>#</th><th>policy</th><th>score</th><th>quality</th><th>samples</th><th>coverage</th><th>target hit</th><th>stop hit</th><th>avg trade</th><th>win rate</th><th>profit factor</th><th>payoff</th><th>avg forward</th><th>avg target</th><th>avg stop</th><th>avg RR</th><th>details</th>
      </tr></thead><tbody>${rows.map((row) => `<tr>
        <td>${fmt(row.rank)}</td>
        <td><code>${fmt(row.policy_id)}</code></td>
        <td>${fmt(row.score)}</td>
        <td>${fmt(row.quality_label)}</td>
        <td>${fmt(row.samples)}</td>
        <td>${fmt(row.coverage_pct)}%</td>
        <td>${fmt(row.target_hit_rate_pct)}%</td>
        <td>${fmt(row.stop_hit_rate_pct)}%</td>
        <td>${fmt(row.avg_trade_return_pct)}%</td>
        <td>${fmt(row.win_rate_pct)}%</td>
        <td>${fmt(row.profit_factor)}</td>
        <td>${fmt(row.payoff_ratio)}</td>
        <td>${fmt(row.avg_forward_return_pct)}%</td>
        <td>${fmt(row.avg_target_pct)}%</td>
        <td>${fmt(row.avg_stop_pct)}%</td>
        <td>${fmt(row.avg_rr)}</td>
        <td><code>${JSON.stringify(row.policy || {})}</code></td>
      </tr>`).join("")}</tbody></table>`;
    }
    async function run() {
      el("run").disabled = true;
      el("status").className = "panel muted";
      el("status").textContent = "Считаю target/stop calibration...";
      try {
        const response = await fetch(`/signals/consumer/adaptive-trade-calibration?${params().toString()}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        const summary = data.summary || {};
        const improvement = summary.improvement_vs_baseline || {};
        const baseline = summary.baseline_metrics || {};
        const best = summary.best_policy_metrics || {};
        el("summary").style.display = "grid";
        el("summary").innerHTML = [
          card("policies_tested", summary.policies_tested),
          card("best_score", summary.best_score, (summary.best_score || 0) >= 0 ? "good" : "bad"),
          card("best_policy", summary.best_policy_id),
          card("quality", summary.best_quality_label),
          card("recommendation", summary.recommendation),
          card("baseline stop", baseline.stop_hit_rate_pct),
          card("best stop", best.stop_hit_rate_pct),
          card("best trade", best.avg_trade_return_pct, (best.avg_trade_return_pct || 0) >= 0 ? "good" : "bad"),
          card("win rate", best.win_rate_pct),
          card("profit factor", best.profit_factor),
          card("trade delta", improvement.avg_trade_return_delta_pct, (improvement.avg_trade_return_delta_pct || 0) >= 0 ? "good" : "bad"),
        ].join("");
        el("best").innerHTML = renderTable(data.best_policies || []);
        const warnings = (summary.warnings || []).map((item) => `<div class="warn">${item}</div>`).join("");
        const limitations = (data.limitations || []).map((item) => `<div>• ${item}</div>`).join("");
        el("notes").innerHTML = warnings + limitations;
        el("status").innerHTML = `Готово: ${summary.policies_tested || 0} policies.`
          + (Number(summary.samples || 0) === 0 ? ' <a href="/signals/data-coverage-page">Проверить Data coverage</a>' : "");
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
