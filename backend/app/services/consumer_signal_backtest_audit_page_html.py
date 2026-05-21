from __future__ import annotations


def build_consumer_signal_backtest_audit_page_html() -> str:
    return """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Consumer Signal Backtest Audit</title>
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

    header {
      background: #0f172a;
      color: white;
      padding: 28px 20px;
    }

    .inner, main {
      max-width: 1220px;
      margin: 0 auto;
    }

    h1 { margin: 0 0 8px; font-size: 30px; }
    p { line-height: 1.5; }
    header p { margin: 0; color: #cbd5e1; max-width: 900px; }
    nav { margin-top: 16px; display: flex; gap: 12px; flex-wrap: wrap; }
    nav a, .button {
      border: 1px solid rgba(255,255,255,.22);
      border-radius: 8px;
      color: white;
      padding: 9px 12px;
      text-decoration: none;
      font-weight: 750;
      cursor: pointer;
      background: transparent;
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
      grid-template-columns: repeat(6, minmax(120px, 1fr));
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
      border-color: #0f172a;
      height: 40px;
    }

    .status { margin: 14px 0; color: var(--muted); }
    .summary {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
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
      font-size: 26px;
      font-weight: 900;
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
      margin-top: 16px;
    }

    h2 { margin: 0 0 12px; font-size: 18px; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { padding: 9px 8px; border-bottom: 1px solid var(--border); text-align: right; }
    th:first-child, td:first-child { text-align: left; }
    th { color: var(--muted); font-size: 11px; text-transform: uppercase; }
    .positive { color: var(--green); font-weight: 850; }
    .negative { color: var(--red); font-weight: 850; }
    .muted { color: var(--muted); }
    .examples { display: grid; gap: 8px; }
    .example {
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px;
      background: #f8fafc;
      font-size: 13px;
    }

    .full { grid-column: 1 / -1; }
    ul { margin: 8px 0 0 18px; padding: 0; }

    @media (max-width: 920px) {
      .toolbar, .summary, .grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <div class="inner">
      <h1>Consumer Signal Backtest Audit</h1>
      <p>Исторический proxy-аудит consumer decision model: actions, blockers, audit confidence и forward outcomes по дневным свечам.</p>
      <nav>
        <a href="/signals">← Сигналы</a>
        <a href="/signals/consumer/threshold-sweep-page">Threshold sweep</a>
        <a href="/signals/consumer/walk-forward-page">Walk-forward</a>
        <a href="/signals/consumer/regime-historical-evaluation-page">Regime evaluation</a>
        <a href="/signals/consumer/regime-formula-calibration-page">Regime calibration</a>
        <a href="/signals/consumer.json?limit=50&scenario=all">Consumer JSON</a>
      </nav>
    </div>
  </header>

  <main>
    <section class="toolbar">
      <label>max_tickers<input id="maxTickers" type="number" value="40" min="1" max="300" /></label>
      <label>max_samples<input id="maxSamples" type="number" value="800" min="50" max="20000" /></label>
      <label>horizon<input id="horizon" type="number" value="20" min="5" max="90" /></label>
      <label>target_pct<input id="targetPct" type="number" value="0.05" min="0.005" max="0.25" step="0.005" /></label>
      <label>stop_pct<input id="stopPct" type="number" value="0.03" min="0.005" max="0.20" step="0.005" /></label>
      <label>Use market regime<input id="useMarketRegime" type="checkbox" /></label>
      <button class="button" onclick="loadReport()">Обновить отчёт</button>
    </section>

    <div id="status" class="status">Загружаю отчёт...</div>
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

    function params() {
      const q = new URLSearchParams();
      q.set("max_tickers", document.getElementById("maxTickers").value || "40");
      q.set("max_samples", document.getElementById("maxSamples").value || "800");
      q.set("horizon", document.getElementById("horizon").value || "20");
      q.set("target_pct", document.getElementById("targetPct").value || "0.05");
      q.set("stop_pct", document.getElementById("stopPct").value || "0.03");
      if (document.getElementById("useMarketRegime").checked) q.set("use_market_regime_filter", "true");
      return q;
    }

    function metric(label, value, cls = "") {
      return `<div class="card metric"><div class="label">${escapeHtml(label)}</div><div class="value ${cls}">${escapeHtml(value)}</div></div>`;
    }

    function table(title, data) {
      const rows = Object.entries(data || {});
      if (!rows.length) return `<section class="card"><h2>${escapeHtml(title)}</h2><p class="muted">Нет данных.</p></section>`;

      return `
        <section class="card">
          <h2>${escapeHtml(title)}</h2>
          <table>
            <thead>
              <tr>
                <th>bucket</th><th>samples</th><th>target</th><th>stop</th><th>timeout</th><th>avg ret</th><th>MFE</th><th>MAE</th>
              </tr>
            </thead>
            <tbody>
              ${rows.map(([key, value]) => `
                <tr>
                  <td>${escapeHtml(key)}</td>
                  <td>${fmt(value.samples, 0)}</td>
                  <td>${pct(value.target_hit_rate_pct)}</td>
                  <td>${pct(value.stop_hit_rate_pct)}</td>
                  <td>${pct(value.timeout_rate_pct)}</td>
                  <td class="${Number(value.avg_forward_return_pct) >= 0 ? "positive" : "negative"}">${pct(value.avg_forward_return_pct)}</td>
                  <td>${pct(value.avg_mfe_pct)}</td>
                  <td>${pct(value.avg_mae_pct)}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </section>
      `;
    }

    function examples(title, items) {
      const values = Array.isArray(items) ? items : [];
      return `
        <section class="card">
          <h2>${escapeHtml(title)}</h2>
          <div class="examples">
            ${values.length ? values.map(item => `
              <div class="example">
                <strong>${escapeHtml(item.ticker)} · ${escapeHtml(item.date)}</strong>
                <div class="muted">${escapeHtml(item.action)} · ${escapeHtml(item.outcome)} · blocked: ${escapeHtml((item.blocked_by || []).join(", ") || "—")}</div>
                <div>prob ${fmt(item.probability_pct, 0)} · audit ${fmt(item.audit_score, 0)} · ret ${pct(item.forward_return_pct)} · MFE ${pct(item.mfe_pct)} · MAE ${pct(item.mae_pct)}</div>
              </div>
            `).join("") : "<p class='muted'>Нет примеров.</p>"}
          </div>
        </section>
      `;
    }

    async function loadReport() {
      const status = document.getElementById("status");
      status.textContent = "Загружаю backtest audit...";
      document.getElementById("summary").innerHTML = "";
      document.getElementById("content").innerHTML = "";

      try {
        const response = await fetch(`/signals/consumer/backtest-audit?${params().toString()}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}: ${await response.text()}`);
        const data = await response.json();
        const summary = data.summary || {};

        document.getElementById("summary").innerHTML = [
          metric("samples", fmt(summary.samples, 0)),
          metric("target hit", pct(summary.target_hit_rate_pct), "positive"),
          metric("stop hit", pct(summary.stop_hit_rate_pct), "negative"),
          metric("avg forward return", pct(summary.avg_forward_return_pct), Number(summary.avg_forward_return_pct) >= 0 ? "positive" : "negative"),
          metric("tickers used", fmt(summary.tickers_used, 0)),
        ].join("");

        document.getElementById("content").innerHTML = [
          table("By action", data.by_action),
          table("By blocker", data.by_blocker),
          table("By audit confidence", data.by_audit_confidence),
          table("By layer support", data.by_layer_support),
          examples("Top positive examples", data.top_positive_examples),
          examples("Top negative examples", data.top_negative_examples),
          examples("Worst false positives", data.worst_false_positives),
          examples("Near-miss examples", data.near_miss_examples),
          `<section class="card full"><h2>Limitations</h2><p>${escapeHtml(data.note || "")}</p><ul>${(data.limitations || []).map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul></section>`,
        ].join("");

        status.textContent = `Готово: mode=${data.mode || "—"}, samples=${summary.samples || 0}.`;
      } catch (error) {
        status.textContent = `Ошибка загрузки отчёта: ${error.message}`;
      }
    }

    loadReport();
  </script>
</body>
</html>
"""
