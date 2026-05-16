from __future__ import annotations


def build_signals_model_compare_page_html() -> str:
    return """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>Сравнение моделей сигналов</title>
  <style>
    :root {
      --bg: #eef1f5;
      --card: #ffffff;
      --text: #111827;
      --muted: #64748b;
      --blue: #2563eb;
      --dark: #111827;
      --green: #07883d;
      --red: #dc2626;
      --line: #e5e7eb;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background: var(--bg);
    }

    header {
      background: #111827;
      color: white;
      padding: 44px 32px;
    }

    header h1 {
      margin: 0 0 12px;
      font-size: 34px;
    }

    header a {
      color: #93c5fd;
      font-weight: 700;
      text-decoration: none;
    }

    main {
      padding: 28px 32px 60px;
    }

    .card {
      background: var(--card);
      border-radius: 18px;
      padding: 24px;
      margin-bottom: 24px;
      box-shadow: 0 8px 30px rgba(15, 23, 42, 0.06);
    }

    h2 {
      margin: 0 0 18px;
      font-size: 24px;
    }

    label {
      display: block;
      font-size: 13px;
      font-weight: 800;
      color: var(--muted);
      margin-bottom: 6px;
    }

    input, select {
      height: 38px;
      border: 1px solid #cbd5e1;
      border-radius: 8px;
      padding: 0 10px;
      font-size: 15px;
      background: white;
      min-width: 150px;
    }

    .form {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: end;
      margin-bottom: 18px;
    }

    .button {
      border: 0;
      border-radius: 9px;
      background: var(--blue);
      color: white;
      font-weight: 800;
      padding: 11px 16px;
      cursor: pointer;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      height: 40px;
    }

    .button.secondary {
      background: #334155;
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }

    .metric {
      background: #f8fafc;
      border-radius: 14px;
      padding: 14px;
    }

    .metric .label {
      color: var(--muted);
      font-size: 13px;
      font-weight: 800;
    }

    .metric .value {
      margin-top: 4px;
      font-size: 26px;
      font-weight: 900;
    }

    .green { color: var(--green); }
    .red { color: var(--red); }
    .muted { color: var(--muted); }

    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 15px;
    }

    th {
      text-align: left;
      color: var(--muted);
      font-size: 13px;
      padding: 10px;
      border-bottom: 1px solid var(--line);
    }

    td {
      padding: 12px 10px;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
    }

    .pill {
      display: inline-block;
      border-radius: 999px;
      padding: 4px 10px;
      background: #e0f2fe;
      color: #075985;
      font-size: 13px;
      font-weight: 800;
    }

    .winner {
      background: #dcfce7;
      color: #166534;
    }

    .small {
      font-size: 12px;
    }

    @media (max-width: 1000px) {
      .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      table { font-size: 13px; }
    }
  </style>
</head>
<body>
  <header>
    <h1>Сравнение моделей сигналов</h1>
    <nav>
      <a href="/dashboard">← Рынок</a> ·
      <a href="/signals">Сигналы</a> ·
      <a href="/signals/backtest">Backtest</a> ·
      <a href="/signals/history">История сигналов</a>
    </nav>
  </header>

  <main>
    <section class="card">
      <h2>Model Lab</h2>

      <div class="form">
        <div>
          <label>Тикеры через запятую</label>
          <input id="tickers" value="SBER,GAZP,LKOH,PLZL,MOEX,VTBR">
        </div>

        <div>
          <label>Модели через запятую</label>
          <input id="models" style="min-width: 340px" value="tech_v1_sma_momentum,tech_v2_rsi_atr,tech_v3_v1_atr_risk,tech_v4_quality_rr">
        </div>

        <div>
          <label>Тип сигнала</label>
          <select id="action">
            <option value="">Все</option>
            <option value="buy_watch">Покупка</option>
            <option value="risk_sell_watch">Риск снижения</option>
            <option value="hold_watch">Нейтральные</option>
          </select>
        </div>

        <div>
          <label>Будущих свечей</label>
          <input id="futureLimit" type="number" value="20">
        </div>

        <div>
          <label>Точек на тикер</label>
          <input id="maxPoints" type="number" value="25">
        </div>

        <button class="button" onclick="loadCompare()">Сравнить модели</button>
        <a id="jsonLink" class="button secondary" href="/signals/models/compare.json" target="_blank">JSON</a>\n        <a id="csvLink" class="button secondary" href="/signals/models/compare.csv">Скачать CSV</a>
      </div>

      <div class="grid">
        <div class="metric">
          <div class="label">Лучшая модель</div>
          <div id="winnerModel" class="value">—</div>
        </div>
        <div class="metric">
          <div class="label">Score</div>
          <div id="winnerScore" class="value">—</div>
        </div>
        <div class="metric">
          <div class="label">Точность</div>
          <div id="winnerAccuracy" class="value">—</div>
        </div>
        <div class="metric">
          <div class="label">Средний результат стратегии</div>
          <div id="winnerAvg" class="value">—</div>
        </div>
      </div>
    </section>

    <section class="card">
      <h2>Сводка по моделям</h2>
      <table>
        <thead>
          <tr>
            <th>Модель</th>
            <th>Score</th>
            <th>Всего</th>
            <th>Actionable</th>
            <th>Покупка</th>
            <th>Риск снижения</th>
            <th>Успешно</th>
            <th>Провалено</th>
            <th>Точность</th>
            <th>Средний рез. стратегии</th>
          </tr>
        </thead>
        <tbody id="modelRows">
          <tr><td colspan="10" class="muted">Загрузка...</td></tr>
        </tbody>
      </table>
    </section>

    <section class="card">
      <h2>Качество по тикерам лучшей модели</h2>
      <table>
        <thead>
          <tr>
            <th>Тикер</th>
            <th>Всего</th>
            <th>Успешно</th>
            <th>Провалено</th>
            <th>Точность</th>
            <th>Средний рез.</th>
          </tr>
        </thead>
        <tbody id="tickerRows">
          <tr><td colspan="6" class="muted">Загрузка...</td></tr>
        </tbody>
      </table>
    </section>
  </main>

  <script>
    function formatPct(value) {
      if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
      return `${Number(value).toFixed(2)}%`;
    }

    function valueClass(value) {
      if (value === null || value === undefined || Number.isNaN(Number(value))) return "";
      return Number(value) >= 0 ? "green" : "red";
    }

    function esc(value) {
      return String(value ?? "").replace(/[&<>"']/g, function(ch) {
        return ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#039;"
        })[ch];
      });
    }

    function buildParams() {
      const params = new URLSearchParams();

      const tickers = document.getElementById("tickers").value.trim();
      const models = document.getElementById("models").value.trim();
      const action = document.getElementById("action").value;
      const futureLimit = document.getElementById("futureLimit").value;
      const maxPoints = document.getElementById("maxPoints").value;

      if (tickers) params.set("tickers", tickers);
      if (models) params.set("model_versions", models);
      if (action) params.set("action", action);
      params.set("future_limit", futureLimit || "20");
      params.set("max_points_per_ticker", maxPoints || "25");
      params.set("limit", "150");

      return params;
    }

    function renderModelRows(rows) {
      if (!rows || !rows.length) {
        return '<tr><td colspan="10" class="muted">Нет данных.</td></tr>';
      }

      return rows.map((row, index) => {
        const s = row.summary || {};
        const winnerPill = index === 0 ? ' <span class="pill winner">winner</span>' : '';

        return `
          <tr>
            <td><b>${esc(row.model_version)}</b>${winnerPill}</td>
            <td><b>${esc(row.score)}</b></td>
            <td>${esc(s.total)}</td>
            <td>${esc(s.actionable_count)}</td>
            <td class="green"><b>${esc(s.buy_watch)}</b></td>
            <td class="red"><b>${esc(s.risk_sell_watch)}</b></td>
            <td class="green"><b>${esc(s.success)}</b></td>
            <td class="red"><b>${esc(s.failed)}</b></td>
            <td>${formatPct(s.accuracy_pct)}</td>
            <td class="${valueClass(s.avg_strategy_result_pct)}"><b>${formatPct(s.avg_strategy_result_pct)}</b></td>
          </tr>
        `;
      }).join("");
    }

    function renderTickerRows(rows) {
      if (!rows || !rows.length) {
        return '<tr><td colspan="6" class="muted">Нет данных.</td></tr>';
      }

      return rows.map(row => `
        <tr>
          <td><b>${esc(row.ticker)}</b></td>
          <td>${esc(row.total)}</td>
          <td class="green"><b>${esc(row.success)}</b></td>
          <td class="red"><b>${esc(row.failed)}</b></td>
          <td>${formatPct(row.accuracy_pct)}</td>
          <td class="${valueClass(row.avg_strategy_result_pct)}"><b>${formatPct(row.avg_strategy_result_pct)}</b></td>
        </tr>
      `).join("");
    }

    async function loadCompare() {
      const params = buildParams();
      const url = `/signals/models/compare.json?${params.toString()}`;
      const csvUrl = `/signals/models/compare.csv?${params.toString()}`;

      document.getElementById("jsonLink").href = url;
      document.getElementById("csvLink").href = csvUrl;

      const response = await fetch(url);
      const data = await response.json();

      const winner = data.winner || {};
      const winnerSummary = winner.summary || {};

      document.getElementById("winnerModel").textContent = winner.model_version || "—";
      document.getElementById("winnerScore").textContent = winner.score ?? "—";
      document.getElementById("winnerAccuracy").textContent = formatPct(winnerSummary.accuracy_pct);
      document.getElementById("winnerAvg").textContent = formatPct(winnerSummary.avg_strategy_result_pct);
      document.getElementById("winnerAvg").className = "value " + valueClass(winnerSummary.avg_strategy_result_pct);

      document.getElementById("modelRows").innerHTML = renderModelRows(data.rows || []);
      document.getElementById("tickerRows").innerHTML = renderTickerRows((winner || {}).by_ticker || []);
    }

    loadCompare();
  </script>
</body>
</html>
"""
