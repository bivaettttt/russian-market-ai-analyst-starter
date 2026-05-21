from __future__ import annotations


def build_consumer_walk_forward_page_html() -> str:
    return """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Consumer Walk-Forward Validation</title>
  <style>
    :root {
      --bg: #f5f7fb;
      --card: #ffffff;
      --text: #111827;
      --muted: #64748b;
      --border: #e2e8f0;
      --green: #047857;
      --red: #b91c1c;
      --amber: #92400e;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    header { background: #0f172a; color: white; padding: 28px 20px; }
    .inner, main { max-width: 1240px; margin: 0 auto; }
    h1 { margin: 0 0 8px; font-size: 30px; }
    header p { margin: 0; color: #cbd5e1; max-width: 920px; line-height: 1.5; }
    nav { margin-top: 16px; display: flex; gap: 12px; flex-wrap: wrap; }
    nav a {
      border: 1px solid rgba(255,255,255,.22);
      border-radius: 8px;
      color: white;
      padding: 9px 12px;
      text-decoration: none;
      font-weight: 750;
    }
    main { padding: 22px 20px 40px; }
    .toolbar, .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px;
      box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
    }
    .toolbar {
      display: grid;
      grid-template-columns: repeat(4, minmax(130px, 1fr));
      gap: 12px;
      align-items: end;
    }
    label {
      color: var(--muted);
      font-size: 12px;
      font-weight: 850;
      text-transform: uppercase;
      letter-spacing: .04em;
    }
    input {
      width: 100%;
      margin-top: 6px;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px;
      font: inherit;
      color: var(--text);
      background: white;
    }
    .button {
      background: #0f172a;
      border: 1px solid #0f172a;
      border-radius: 8px;
      color: white;
      height: 40px;
      padding: 0 14px;
      font-weight: 850;
      cursor: pointer;
    }
    .status { margin: 14px 0; color: var(--muted); }
    .summary {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin: 16px 0;
    }
    .metric .label {
      color: var(--muted);
      font-size: 12px;
      font-weight: 850;
      text-transform: uppercase;
    }
    .metric .value {
      margin-top: 6px;
      font-size: 24px;
      font-weight: 900;
      overflow-wrap: anywhere;
    }
    .grid { display: grid; gap: 16px; }
    h2 { margin: 0 0 12px; font-size: 18px; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { padding: 9px 8px; border-bottom: 1px solid var(--border); text-align: right; white-space: nowrap; }
    th:first-child, td:first-child { text-align: left; }
    th { color: var(--muted); font-size: 11px; text-transform: uppercase; }
    .table-wrap { overflow-x: auto; }
    .positive { color: var(--green); font-weight: 850; }
    .negative { color: var(--red); font-weight: 850; }
    .warning { color: var(--amber); font-weight: 850; }
    .muted { color: var(--muted); }
    ul { margin: 8px 0 0 18px; padding: 0; }
    @media (max-width: 980px) {
      .toolbar, .summary { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <div class="inner">
      <h1>Consumer Walk-Forward Validation</h1>
      <p>Rolling train/test проверка threshold configs: выбираем параметры на train window и проверяем устойчивость на следующем test window.</p>
      <nav>
        <a href="/signals">← Сигналы</a>
        <a href="/signals/consumer/backtest-audit-page">Backtest audit</a>
        <a href="/signals/consumer/threshold-sweep-page">Threshold sweep</a>
        <a href="/signals/consumer/regime-historical-evaluation-page">Regime evaluation</a>
        <a href="/signals/consumer/regime-formula-calibration-page">Regime calibration</a>
        <a href="/signals/consumer/adaptive-trade-calibration-page">Target/Stop calibration</a>
        <a href="/signals/consumer/expectancy-breakdown-page">Expectancy breakdown</a>
      </nav>
    </div>
  </header>

  <main>
    <section class="toolbar">
      <label>max_tickers<input id="maxTickers" type="number" value="20" min="1" max="200" /></label>
      <label>max_samples<input id="maxSamples" type="number" value="600" min="200" max="30000" /></label>
      <label>max_configs<input id="maxConfigs" type="number" value="60" min="10" max="500" /></label>
      <label>folds<input id="folds" type="number" value="3" min="1" max="8" /></label>
      <label>train_ratio<input id="trainRatio" type="number" value="0.6" min="0.4" max="0.85" step="0.05" /></label>
      <label>min_train_samples<input id="minTrainSamples" type="number" value="80" min="50" max="5000" /></label>
      <label>min_test_samples<input id="minTestSamples" type="number" value="30" min="20" max="3000" /></label>
      <label>min_signals<input id="minSignals" type="number" value="10" min="1" max="1000" /></label>
      <label>Use market regime<input id="useMarketRegime" type="checkbox" /></label>
      <button class="button" onclick="loadWalkForward()">Запустить walk-forward</button>
      <label>horizons<input id="horizons" value="15,20,30" /></label>
      <label>target_pcts<input id="targetPcts" value="0.03,0.04,0.05,0.06" /></label>
      <label>stop_pcts<input id="stopPcts" value="0.02,0.03,0.04" /></label>
      <label>min_probabilities<input id="minProbabilities" value="45,50,55,60" /></label>
      <label>min_ml_probabilities<input id="minMlProbabilities" value="0,20,25,30,35" /></label>
      <label>min_rr_values<input id="minRrValues" value="0.8,1.0,1.2,1.5" /></label>
    </section>

    <div id="status" class="status">Готов к запуску.</div>
    <section id="summary" class="summary"></section>
    <section id="content" class="grid"></section>
  </main>

  <script>
    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }
    function fmt(value, digits = 2) {
      const n = Number(value);
      if (Number.isNaN(n)) return "—";
      return n.toLocaleString("ru-RU", { maximumFractionDigits: digits });
    }
    function pct(value) {
      return value === null || value === undefined ? "—" : `${fmt(value)}%`;
    }
    function param(id, key, q) {
      const value = document.getElementById(id).value.trim();
      if (value) q.set(key, value);
    }
    function query() {
      const q = new URLSearchParams();
      q.set("max_tickers", document.getElementById("maxTickers").value || "20");
      q.set("max_samples", document.getElementById("maxSamples").value || "600");
      q.set("max_configs", document.getElementById("maxConfigs").value || "60");
      q.set("folds", document.getElementById("folds").value || "3");
      q.set("train_ratio", document.getElementById("trainRatio").value || "0.6");
      q.set("min_train_samples", document.getElementById("minTrainSamples").value || "80");
      q.set("min_test_samples", document.getElementById("minTestSamples").value || "30");
      q.set("min_signals", document.getElementById("minSignals").value || "10");
      if (document.getElementById("useMarketRegime").checked) q.set("use_market_regime_filter", "true");
      param("horizons", "horizons", q);
      param("targetPcts", "target_pcts", q);
      param("stopPcts", "stop_pcts", q);
      param("minProbabilities", "min_probabilities", q);
      param("minMlProbabilities", "min_ml_probabilities", q);
      param("minRrValues", "min_rr_values", q);
      return q;
    }
    function metric(label, value, cls = "") {
      return `<div class="card metric"><div class="label">${escapeHtml(label)}</div><div class="value ${cls}">${escapeHtml(value)}</div></div>`;
    }
    function foldsTable(folds) {
      const values = Array.isArray(folds) ? folds : [];
      return `
        <section class="card">
          <h2>Folds</h2>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>fold</th><th>train</th><th>test</th><th>config</th><th>train score</th><th>test score</th><th>decay</th><th>target</th><th>stop</th><th>avg trade</th><th>win</th><th>PF</th><th>avg ret</th><th>stability</th>
                </tr>
              </thead>
              <tbody>
                ${values.length ? values.map(fold => {
                  const train = fold.train_period || {};
                  const test = fold.test_period || {};
                  const config = fold.selected_config || {};
                  const trainMetrics = fold.train_metrics || {};
                  const testMetrics = fold.test_metrics || {};
                  return `
                    <tr>
                      <td>${fmt(fold.fold, 0)}</td>
                      <td>${escapeHtml(train.first_date || "—")} → ${escapeHtml(train.last_date || "—")} (${fmt(train.samples, 0)})</td>
                      <td>${escapeHtml(test.first_date || "—")} → ${escapeHtml(test.last_date || "—")} (${fmt(test.samples, 0)})</td>
                      <td>${escapeHtml(config.config_id || "—")}</td>
                      <td>${fmt(trainMetrics.score)}</td>
                      <td class="${Number(testMetrics.score) >= 10 ? "positive" : Number(testMetrics.score) >= 0 ? "warning" : "negative"}">${fmt(testMetrics.score)}</td>
                      <td>${fmt(fold.score_decay)}</td>
                      <td>${pct(testMetrics.target_hit_rate_pct)}</td>
                      <td>${pct(testMetrics.stop_hit_rate_pct)}</td>
                      <td class="${Number(testMetrics.avg_trade_return_pct) >= 0 ? "positive" : "negative"}">${pct(testMetrics.avg_trade_return_pct)}</td>
                      <td>${pct(testMetrics.win_rate_pct)}</td>
                      <td>${fmt(testMetrics.profit_factor)}</td>
                      <td class="${Number(testMetrics.avg_forward_return_pct) >= 0 ? "positive" : "negative"}">${pct(testMetrics.avg_forward_return_pct)}</td>
                      <td>${escapeHtml(fold.stability_label || "—")}</td>
                    </tr>
                  `;
                }).join("") : "<tr><td colspan='14'>Нет fold данных.</td></tr>"}
              </tbody>
            </table>
          </div>
        </section>
      `;
    }
    function frequencyTable(freq) {
      const rows = Object.entries(freq || {});
      return `
        <section class="card">
          <h2>Config frequency</h2>
          <div class="table-wrap">
            <table>
              <thead><tr><th>config</th><th>folds</th></tr></thead>
              <tbody>${rows.length ? rows.map(([key, value]) => `<tr><td>${escapeHtml(key)}</td><td>${fmt(value, 0)}</td></tr>`).join("") : "<tr><td colspan='2'>—</td></tr>"}</tbody>
            </table>
          </div>
        </section>
      `;
    }
    async function loadWalkForward() {
      const status = document.getElementById("status");
      status.textContent = "Запускаю walk-forward validation...";
      document.getElementById("summary").innerHTML = "";
      document.getElementById("content").innerHTML = "";
      try {
        const response = await fetch(`/signals/consumer/walk-forward?${query().toString()}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}: ${await response.text()}`);
        const data = await response.json();
        const summary = data.summary || {};
        document.getElementById("summary").innerHTML = [
          metric("folds completed", fmt(summary.folds_completed, 0)),
          metric("avg train score", fmt(summary.avg_train_score)),
          metric("avg test score", fmt(summary.avg_test_score), Number(summary.avg_test_score) >= 10 ? "positive" : "warning"),
          metric("avg decay", fmt(summary.avg_score_decay)),
          metric("test target hit", pct(summary.avg_test_target_hit_rate_pct), "positive"),
          metric("test stop hit", pct(summary.avg_test_stop_hit_rate_pct), "negative"),
          metric("test avg return", pct(summary.avg_test_forward_return_pct), Number(summary.avg_test_forward_return_pct) >= 0 ? "positive" : "negative"),
          metric("recommendation", summary.recommendation || "—"),
        ].join("");
        document.getElementById("content").innerHTML = [
          foldsTable(data.folds || []),
          frequencyTable(data.config_frequency || {}),
          `<section class="card"><h2>Warnings</h2><ul>${(summary.warnings || []).map(item => `<li>${escapeHtml(item)}</li>`).join("") || "<li>—</li>"}</ul></section>`,
          `<section class="card"><h2>Limitations</h2><ul>${(data.limitations || []).map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul></section>`,
        ].join("");
        status.textContent = `Готово: mode=${data.mode || "—"}, folds=${summary.folds_completed || 0}.`;
      } catch (error) {
        status.textContent = `Ошибка walk-forward validation: ${error.message}`;
      }
    }
    loadWalkForward();
  </script>
</body>
</html>
"""
