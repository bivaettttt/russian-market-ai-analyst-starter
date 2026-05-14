def build_dashboard_html() -> str:
    return """
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8" />
  <title>AI Аналитик рынка РФ</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 0;
      background: #f4f6f8;
      color: #17212b;
    }
    header {
      background: #111827;
      color: white;
      padding: 24px 32px;
    }
    header h1 {
      margin: 0 0 8px 0;
      font-size: 28px;
    }
    header p {
      margin: 0;
      color: #cbd5e1;
    }
    main {
      padding: 24px 32px;
      display: grid;
      gap: 20px;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 16px;
    }
    .card {
      background: white;
      border-radius: 16px;
      padding: 20px;
      box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
    }
    .card h2 {
      margin-top: 0;
      font-size: 18px;
    }
    .badge {
      display: inline-block;
      padding: 6px 10px;
      border-radius: 999px;
      background: #e0f2fe;
      color: #075985;
      font-size: 13px;
      font-weight: 600;
    }
    .risk {
      background: #fff7ed;
      border-left: 4px solid #f97316;
    }
    .signal {
      border-left: 4px solid #2563eb;
    }
    .muted {
      color: #64748b;
      font-size: 14px;
    }
    ul {
      padding-left: 20px;
    }
    li {
      margin-bottom: 8px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }
    th, td {
      text-align: left;
      padding: 8px;
      border-bottom: 1px solid #e5e7eb;
    }
    th {
      color: #475569;
    }
    .positive {
      color: #15803d;
      font-weight: 600;
    }
    .negative {
      color: #b91c1c;
      font-weight: 600;
    }
  
    .quick-actions-row {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      align-items: center;
      margin-top: 12px;
    }}

    .button-link {{
      display: inline-block;
      background: #2563eb;
      color: white;
      text-decoration: none;
      border-radius: 10px;
      padding: 10px 14px;
      font-weight: 700;
      font-size: 14px;
    }}

    .button-link.secondary {{
      background: #334155;
    }}

    .quick-status {{
      margin-top: 14px;
      font-weight: 700;
    }}

    .quick-result {{
      margin-top: 12px;
      padding: 12px;
      border-radius: 12px;
      background: #f8fafc;
      border-left: 4px solid #2563eb;
    }}

    .quick-result a {{
      font-weight: 700;
    }}

  
    .quick-actions-row {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      align-items: center;
      margin-top: 12px;
    }

    .quick-actions-row button,
    .button-link {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 38px;
      border: 0;
      border-radius: 10px;
      padding: 10px 14px;
      background: #2563eb;
      color: #ffffff;
      text-decoration: none;
      font-weight: 700;
      font-size: 14px;
      cursor: pointer;
      line-height: 1;
    }

    .quick-actions-row button:hover,
    .button-link:hover {
      background: #1d4ed8;
      color: #ffffff;
      text-decoration: none;
    }

    .button-link.secondary {
      background: #334155;
    }

    .button-link.secondary:hover {
      background: #1e293b;
    }

    .quick-status {
      margin-top: 14px;
      font-weight: 700;
    }

    .quick-result {
      margin-top: 12px;
      padding: 12px;
      border-radius: 12px;
      background: #f8fafc;
      border-left: 4px solid #2563eb;
    }

    .quick-result a {
      font-weight: 700;
    }

  </style>
</head>
<body>
  <header>
    <h1>AI Аналитик российского рынка</h1>
    <p>
  MOEX Market Radar · Briefing · Signals · Daily Report ·
  <a href="/ai/report/demo" style="color:#93c5fd;text-decoration:none;">AI Report →</a> ·
  <a href="/signals" style="color:#93c5fd;text-decoration:none;">Сигналы →</a> ·
  <a href="/signals/champion" style="color:#93c5fd;text-decoration:none;">Champion →</a> ·
  <a href="/portfolio/construct/demo" style="color:#93c5fd;text-decoration:none;">Конструктор портфеля →</a> ·
  <a href="/portfolio/demo" style="color:#93c5fd;text-decoration:none;">Портфель →</a> ·
  <a href="/events/dashboard" style="color:#93c5fd;text-decoration:none;">События →</a> ·
  <a href="/system/dashboard" style="color:#93c5fd;text-decoration:none;">Обновить данные + отчёт →</a>
</p>
  </header>

  <main>

  <section class="card">
    <h2>Быстрые действия</h2>
    <p class="muted">Запустите полный цикл: обновить MOEX/RSS, собрать AI Report, сохранить его и сразу перейти к результатам.</p>

    <div class="quick-actions-row">
      <button type="button" onclick="runDashboardUpdate()">Обновить данные + новый AI Report</button>
      <a class="button-link" href="/ai/report/compare/latest">Сравнить последние отчёты</a>
      <a class="button-link secondary" href="/ai/reports/dashboard">История отчётов</a>\n      <a class="button-link secondary" href="/ai/reports/trends">Динамика</a>
      <a class="button-link secondary" href="/ai/report/demo">Редактор AI Report</a>
      <a class="button-link secondary" href="/portfolio/construct/demo">Конструктор портфеля</a>
    </div>

    <div id="dashboard-update-status" class="muted quick-status">Готово к запуску.</div>
    <div id="dashboard-update-result"></div>
  </section>

    <section class="card">
      <h2>Ежедневный отчёт</h2>
      <div id="meta" class="muted">Загрузка...</div>
      <p id="summary"></p>
    </section>

    <section class="grid">
      <div class="card">
        <h2>Состояние рынка</h2>
        <p><span id="mood" class="badge">—</span></p>
        <p id="breadth" class="muted"></p>
      </div>

      <div class="card">
        <h2>Watchlist</h2>
        <ul id="watchlist"></ul>
      </div>

      <div class="card risk">
        <h2>Риски</h2>
        <ul id="risks"></ul>
      </div>
    </section>

    <section class="grid">
      <div class="card">
        <h2>Лидеры роста</h2>
        <table>
          <thead>
            <tr><th>Тикер</th><th>Изм.</th><th>Цена</th></tr>
          </thead>
          <tbody id="gainers"></tbody>
        </table>
      </div>

      <div class="card">
        <h2>Лидеры снижения</h2>
        <table>
          <thead>
            <tr><th>Тикер</th><th>Изм.</th><th>Цена</th></tr>
          </thead>
          <tbody id="losers"></tbody>
        </table>
      </div>
    </section>

    <section class="card" id="importantEventsCard">
      <h2>Важные события</h2>
      <div id="importantEvents" class="muted">Загрузка событий...</div>
      <p class="muted"><a href="/events/dashboard" style="color:#2563eb;text-decoration:none;">Открыть радар событий →</a></p>
    </section>

    <section class="card">
      <h2>Сигналы</h2>
      <div id="signals"></div>
    </section>
  
  <section class="card">
    <h2>Последний AI Report</h2>
    <div id="latest-ai-report">
      <p class="muted">Загружаю последний отчёт...</p>
    </div>
  </section>

</main>

  <script>
    function pctClass(value) {
      return value >= 0 ? "positive" : "negative";
    }

    function row(item) {
      return `
        <tr>
          <td><strong><a href="/ticker/${item.ticker}" style="color:#2563eb;text-decoration:none;">${item.ticker}</a></strong></td>
          <td class="${pctClass(item.change_pct)}">${item.change_pct}%</td>
          <td>${item.close}</td>
        </tr>
      `;
    }

    function li(text) {
      return `<li>${text}</li>`;
    }

    function tickerLink(ticker) {
      const safeTicker = String(ticker || "").trim().toUpperCase();
      if (!safeTicker) return "—";
      return `<a href="/tickers/${safeTicker}">${safeTicker}</a>`;
    }

    function escapeHtml(value) {
      if (value === null || value === undefined) return "";
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function renderImportantEvent(event) {
      const title = event.title || "Без заголовка";
      const source = event.url
        ? `<a href="${escapeHtml(event.url)}" target="_blank" rel="noreferrer" style="color:#2563eb;text-decoration:none;">Источник</a>`
        : "";

      return `
        <div style="border-left:4px solid #2563eb;padding:12px 14px;margin-bottom:10px;background:#f8fafc;border-radius:12px;">
          <strong>${escapeHtml(title)}</strong>
          <p class="muted">
            важность: ${escapeHtml(event.importance)}
            · тип: ${escapeHtml(event.event_type)}
            · влияние: ${escapeHtml(event.impact)}
            · ${source}
          </p>
          <p class="muted">${escapeHtml(event.reasoning || "")}</p>
        </div>
      `;
    }

    async function loadImportantEvents() {
      const response = await fetch("/events/radar?limit=5&min_importance=7");
      const data = await response.json();

      const events = data.top_events || [];

      document.getElementById("importantEvents").innerHTML =
        events.length
          ? events.map(renderImportantEvent).join("")
          : "Важных событий не найдено.";
    }

    async function loadReport() {
      const response = await fetch("/market/daily-report");
      const data = await response.json();

      document.getElementById("meta").textContent =
        `${data.market} · ${data.date}`;

      document.getElementById("summary").textContent =
        data.executive_summary || "Нет сводки.";

      document.getElementById("mood").textContent =
        data.market_mood || "нет данных";

      const b = data.briefing?.breadth || {};
      document.getElementById("breadth").textContent =
        `Растут: ${b.up ?? 0}, снижаются: ${b.down ?? 0}, без изменений: ${b.flat ?? 0}`;

      document.getElementById("watchlist").innerHTML =
        (data.watchlist || []).map(x => li(`<strong>${x.ticker}</strong>: ${x.reason}`)).join("");

      document.getElementById("risks").innerHTML =
        (data.risk_notes || []).map(li).join("");

      document.getElementById("gainers").innerHTML =
        (data.briefing?.top_gainers || []).map(row).join("");

      document.getElementById("losers").innerHTML =
        (data.briefing?.top_losers || []).map(row).join("");

      document.getElementById("signals").innerHTML =
        (data.signals?.signals || []).map(s => `
          <div class="card signal" style="margin-bottom: 12px;">
            <strong>${s.title}</strong>
            <p class="muted">${s.description}</p>
          </div>
        `).join("");
    }

    loadReport().then(loadImportantEvents).catch(error => {
      document.getElementById("summary").textContent = "Ошибка загрузки отчёта: " + error;
    });
  
    async function loadLatestAIReport() {
      const box = document.getElementById("latest-ai-report");
      if (!box) return;

      try {
        const response = await fetch("/ai/reports");
        const reports = await response.json();

        if (!Array.isArray(reports) || reports.length === 0) {
          box.innerHTML = "<p class='muted'>Сохранённых AI Report пока нет.</p>";
          return;
        }

        const latest = reports[0];

        box.innerHTML = `
          <p><b>Последний отчёт:</b> ${latest.report_date || "—"}</p>
          <p class="muted">Создан: ${latest.created_at || "—"}</p>
          <p>
            <a href="${latest.detail_url}">JSON</a> ·
            <a href="${latest.markdown_url}">Markdown</a> ·
            <a href="/ai/reports/dashboard">История отчётов</a> ·
            <a href="/system/dashboard">Обновить данные + отчёт</a>
          </p>
        `;
      } catch (error) {
        box.innerHTML = "<p class='bad'>Ошибка загрузки последнего отчёта.</p>";
      }
    }

    loadLatestAIReport();
  </script>
</body>
</html>
"""
