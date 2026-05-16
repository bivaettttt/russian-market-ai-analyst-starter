from __future__ import annotations


def build_signals_backtest_page_html() -> str:
    return """<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <title>Backtest сигналов · AI Аналитик рынка РФ</title>
  <style>
    * { box-sizing: border-box; }

    body {
      margin: 0;
      font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #eef0f3;
      color: #111827;
    }

    header {
      background: #111827;
      color: #fff;
      padding: 42px 32px;
    }

    header h1 {
      margin: 0 0 12px;
      font-size: 34px;
    }

    header a {
      color: #93c5fd;
      text-decoration: none;
      font-weight: 800;
    }

    main {
      padding: 28px 32px;
    }

    .card {
      background: #fff;
      border-radius: 18px;
      padding: 24px;
      margin-bottom: 22px;
      box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
    }

    .muted { color: #64748b; }

    .metrics {
      display: grid;
      grid-template-columns: repeat(4, minmax(160px, 1fr));
      gap: 14px;
      margin-top: 16px;
    }

    .metric {
      background: #f8fafc;
      border-radius: 14px;
      padding: 14px;
    }

    .metric .label {
      color: #64748b;
      font-size: 13px;
      font-weight: 800;
    }

    .metric .value {
      font-size: 26px;
      font-weight: 900;
      margin-top: 6px;
    }

    .controls {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: end;
      margin-top: 18px;
    }

    label {
      display: block;
      color: #64748b;
      font-size: 13px;
      font-weight: 800;
      margin-bottom: 6px;
    }

    input, select {
      min-height: 38px;
      border: 1px solid #cbd5e1;
      border-radius: 10px;
      padding: 8px 10px;
      font: inherit;
      min-width: 140px;
    }

    .button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 38px;
      border-radius: 10px;
      padding: 10px 14px;
      background: #2563eb;
      color: #fff;
      text-decoration: none;
      font-weight: 850;
      border: 0;
      cursor: pointer;
      margin: 0 8px 8px 0;
    }

    .button.secondary { background: #334155; }

    table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 14px;
    }

    th, td {
      text-align: left;
      border-bottom: 1px solid #e5e7eb;
      padding: 10px;
      vertical-align: top;
    }

    th {
      color: #64748b;
      font-size: 13px;
    }

    a {
      color: #2563eb;
      font-weight: 800;
      text-decoration: none;
    }

    .good { color: #15803d; font-weight: 850; }
    .bad { color: #dc2626; font-weight: 850; }

    .badge {
      display: inline-block;
      padding: 5px 9px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 850;
      background: #f1f5f9;
      color: #334155;
      white-space: nowrap;
    }

    .badge.success { background: #dcfce7; color: #166534; }
    .badge.failed { background: #fee2e2; color: #991b1b; }
    .badge.open { background: #e0f2fe; color: #075985; }
    .badge.pending { background: #fef3c7; color: #92400e; }

    .small { font-size: 13px; }

    .split-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 18px;
      margin-top: 12px;
    }

    @media (max-width: 1100px) {
      .split-grid { grid-template-columns: 1fr; }
    }

    @media (max-width: 900px) {
      .metrics { grid-template-columns: 1fr; }
      table { font-size: 13px; }
    }
  </style>
</head>
<body>
  <header>
    <h1>Backtest сигналов</h1>
    <nav>
      <a href="/dashboard">← Рынок</a> ·
      <a href="/signals">Сигналы</a> ·
      <a href="/signals/history">История сигналов</a> ·
      <a href="/signals/evaluation">Оценка snapshot</a> ·\n      <a href="/signals/models/compare">Model Lab</a>
    </nav>
  </header>

  <main>
    <section class="card">
      <h2>Ретроспективная проверка</h2>
      <p class="muted" id="status">Загружаю backtest...</p>

      <div class="controls">
        <div>
          <label>Тикеры через запятую</label>
          <input id="tickers" value="SBER,GAZP,LKOH,PLZL,VTBR,MOEX" />
        </div>

        <div>
          <label>Тип сигнала</label>
          <select id="action">
            <option value="">Все</option>
            <option value="buy_watch">Кандидаты на покупку</option>
            <option value="risk_sell_watch">Риск снижения</option>
            <option value="hold_watch">Нейтральные</option>
          </select>
        </div>

        <div>
          <label>Версия модели</label>
          <select id="modelVersion">
            <option value="tech_v1_sma_momentum">tech_v1_sma_momentum</option>
            <option value="tech_v2_rsi_atr">tech_v2_rsi_atr</option>
            <option value="tech_v3_v1_atr_risk">tech_v3_v1_atr_risk</option>
            <option value="tech_v4_quality_rr">tech_v4_quality_rr</option>
          </select>
        </div>

        <div>
          <label>Будущих свечей</label>
          <input id="futureLimit" type="number" value="20" min="1" max="120" />
        </div>

        <div>
          <label>Точек на тикер</label>
          <input id="pointsPerTicker" type="number" value="25" min="1" max="200" />
        </div>

        <button class="button" onclick="loadBacktest()">Запустить backtest</button>
        <a class="button secondary" id="jsonLink" href="/signals/backtest.json">JSON</a>
        <a class="button secondary" id="csvLink" href="/signals/backtest.csv">Скачать CSV</a>
      </div>

      <div class="metrics">
        <div class="metric">
          <div class="label">Всего</div>
          <div class="value" id="total">—</div>
        </div>
        <div class="metric">
          <div class="label">Успешно</div>
          <div class="value good" id="success">—</div>
        </div>
        <div class="metric">
          <div class="label">Провалено</div>
          <div class="value bad" id="failed">—</div>
        </div>
        <div class="metric">
          <div class="label">Точность</div>
          <div class="value" id="accuracy">—</div>
        </div>
      </div>

      <div class="metrics">
        <div class="metric">
          <div class="label">Средний результат стратегии</div>
          <div class="value" id="avgResult">—</div>
        </div>
        <div class="metric">
          <div class="label">Покупка</div>
          <div class="value good" id="buyCount">—</div>
        </div>
        <div class="metric">
          <div class="label">Риск снижения</div>
          <div class="value bad" id="riskCount">—</div>
        </div>
        <div class="metric">
          <div class="label">Нейтрально</div>
          <div class="value" id="neutralCount">—</div>
        </div>
      </div>
    </section>

    <section class="card">
      <h2>Качество по группам</h2>

      <div class="split-grid">
        <div>
          <h3>По типу сигнала</h3>
          <table>
            <thead>
              <tr>
                <th>Тип</th>
                <th>Всего</th>
                <th>Успешно</th>
                <th>Провалено</th>
                <th>Точность</th>
                <th>Средний рез.</th>
              </tr>
            </thead>
            <tbody id="actionRows">
              <tr><td colspan="6">Загрузка...</td></tr>
            </tbody>
          </table>
        </div>

        <div>
          <h3>По тикерам</h3>
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
              <tr><td colspan="6">Загрузка...</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <section class="card">
      <h2>Сделки / сценарии</h2>

      <table>
        <thead>
          <tr>
            <th>Дата</th>
            <th>Тикер</th>
            <th>Сигнал</th>
            <th>Цена</th>
            <th>Вход</th>
            <th>Цель</th>
            <th>Стоп</th>
            <th>Статус</th>
            <th>Результат</th>
            <th>Дата результата</th>
            <th>Комментарий</th>
          </tr>
        </thead>
        <tbody id="rows">
          <tr><td colspan="11">Загрузка...</td></tr>
        </tbody>
      </table>
    </section>
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

    function formatNumber(value, digits = 2) {
      if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";

      return Number(value).toLocaleString("ru-RU", {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits
      });
    }

    function formatPct(value) {
      if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";

      return Number(value).toLocaleString("ru-RU", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      }) + "%";
    }

    function valueClass(value) {
      const n = Number(value);

      if (Number.isNaN(n) || n === 0) return "";

      return n > 0 ? "good" : "bad";
    }

    function setText(id, value) {
      document.getElementById(id).textContent =
        value === null || value === undefined || value === "" ? "—" : value;
    }

    function badgeClass(status) {
      if (status === "success") return "badge success";
      if (status === "failed") return "badge failed";
      if (status === "open") return "badge open";
      if (status === "pending" || status === "not_triggered") return "badge pending";
      return "badge";
    }

    function renderGroupRows(items, key) {
      if (!items || !items.length) {
        return '<tr><td colspan="6" class="muted">Нет данных.</td></tr>';
      }

      return items.map(item => {
        const label = item[key] || "—";
        const avg = item.avg_strategy_result_pct;

        return `
          <tr>
            <td><b>${escapeHtml(label)}</b></td>
            <td>${escapeHtml(item.total ?? "—")}</td>
            <td class="good">${escapeHtml(item.success ?? "—")}</td>
            <td class="bad">${escapeHtml(item.failed ?? "—")}</td>
            <td>${item.accuracy_pct === null || item.accuracy_pct === undefined ? "—" : escapeHtml(item.accuracy_pct + "%")}</td>
            <td class="${valueClass(avg)}">${formatPct(avg)}</td>
          </tr>
        `;
      }).join("");
    }

    function buildUrl() {
      const tickers = document.getElementById("tickers").value.trim();
      const action = document.getElementById("action").value;
      const modelVersion = document.getElementById("modelVersion").value;
      const futureLimit = document.getElementById("futureLimit").value;
      const pointsPerTicker = document.getElementById("pointsPerTicker").value;

      const params = new URLSearchParams();
      params.set("limit", "500");
      params.set("min_history", "60");
      params.set("future_limit", futureLimit || "20");
      params.set("max_points_per_ticker", pointsPerTicker || "25");

      if (tickers) params.set("tickers", tickers);
      if (action) params.set("action", action);
      params.set("model_version", modelVersion || "tech_v1_sma_momentum");

      return "/signals/backtest.json?" + params.toString();
    }

    function buildCsvUrl() {
      return buildUrl().replace("/signals/backtest.json?", "/signals/backtest.csv?");
    }

    function render(data) {
      const summary = data.summary || {};
      const rows = data.rows || [];

      setText("total", summary.total);
      setText("success", summary.success);
      setText("failed", summary.failed);
      setText("accuracy", summary.accuracy_pct === null || summary.accuracy_pct === undefined ? "—" : summary.accuracy_pct + "%");
      setText("avgResult", summary.avg_strategy_result_pct === null || summary.avg_strategy_result_pct === undefined ? "—" : summary.avg_strategy_result_pct + "%");
      setText("buyCount", summary.buy_watch);
      setText("riskCount", summary.risk_sell_watch);
      setText("neutralCount", summary.hold_watch);

      const actionRows = document.getElementById("actionRows");
      const tickerRows = document.getElementById("tickerRows");

      if (actionRows) {
        actionRows.innerHTML = renderGroupRows(data.by_action || [], "action");
      }

      if (tickerRows) {
        tickerRows.innerHTML = renderGroupRows(data.by_ticker || [], "ticker");
      }

      const tbody = document.getElementById("rows");

      if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="11" class="muted">Нет данных для backtest.</td></tr>';
        return;
      }

      tbody.innerHTML = rows.map(row => {
        const evaluation = row.evaluation || {};

        return `
          <tr>
            <td>${escapeHtml(row.trade_date || "—")}</td>
            <td><a href="${escapeHtml(row.ticker_url)}">${escapeHtml(row.ticker)}</a></td>
            <td>
              <b>${escapeHtml(row.label || row.action)}</b>
              <div class="muted small">${escapeHtml(row.action || "")}</div>
            </td>
            <td><b>${formatNumber(row.price)}</b></td>
            <td>${formatNumber(row.entry_price)}</td>
            <td>${formatNumber(row.target_price)}</td>
            <td>${formatNumber(row.stop_loss)}</td>
            <td><span class="${badgeClass(evaluation.status)}">${escapeHtml(evaluation.label || evaluation.status)}</span></td>
            <td>
              <div class="${valueClass(row.strategy_result_pct)}"><b>${formatPct(row.strategy_result_pct)}</b></div>
              <div class="muted small">raw: ${formatPct(evaluation.result_pct)}</div>
            </td>
            <td>${escapeHtml(evaluation.result_date || "—")}</td>
            <td>${escapeHtml(evaluation.details || "—")}</td>
          </tr>
        `;
      }).join("");
    }

    async function loadBacktest() {
      setText("status", "Запускаю backtest...");

      const url = buildUrl();
      document.getElementById("jsonLink").href = url;
      document.getElementById("csvLink").href = buildCsvUrl();

      const response = await fetch(url);

      if (!response.ok) {
        throw new Error("HTTP " + response.status + ": " + await response.text());
      }

      const data = await response.json();
      render(data);

      const now = new Date().toLocaleTimeString("ru-RU");
      setText("status", "Backtest обновлён: " + now + ".");
    }

    window.loadBacktest = loadBacktest;

    loadBacktest().catch(error => {
      setText("status", "Ошибка: " + error.message);
    });
  </script>
</body>
</html>"""
