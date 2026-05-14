def build_portfolio_demo_html() -> str:
    return """
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8" />
  <title>Портфель · AI Аналитик рынка РФ</title>
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
    header a {
      color: #93c5fd;
      text-decoration: none;
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
    .risk {
      background: #fff7ed;
      border-left: 4px solid #f97316;
    }
    .card h2 {
      margin-top: 0;
      font-size: 18px;
    }
    .big {
      font-size: 32px;
      font-weight: 800;
      margin: 8px 0;
    }
    .muted {
      color: #64748b;
      font-size: 14px;
    }
    .positive {
      color: #15803d;
      font-weight: 700;
    }
    .negative {
      color: #b91c1c;
      font-weight: 700;
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
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }
    th, td {
      text-align: left;
      padding: 10px 8px;
      border-bottom: 1px solid #e5e7eb;
    }
    th {
      color: #475569;
    }
    textarea {
      width: 100%;
      min-height: 160px;
      border: 1px solid #cbd5e1;
      border-radius: 12px;
      padding: 12px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 14px;
      box-sizing: border-box;
    }
    button {
      background: #2563eb;
      color: white;
      border: 0;
      border-radius: 10px;
      padding: 10px 14px;
      font-weight: 700;
      cursor: pointer;
      margin-top: 10px;
    }
    button:hover {
      background: #1d4ed8;
    }
  </style>
</head>
<body>
  <header>
    <h1>Портфельный анализ</h1>
    <p><a href="/dashboard">← Назад к рынку</a> · <a href="/portfolio/construct/demo">Конструктор портфеля</a></p>
  </header>

  <main>
    <section class="card">
      <h2>Демо-портфель</h2>
      <p class="muted">Можно изменить JSON и нажать “Пересчитать”.</p>
      <textarea id="portfolioInput">{
  "positions": [
    {"ticker": "SBER", "quantity": 10},
    {"ticker": "LKOH", "quantity": 1},
    {"ticker": "GAZP", "quantity": 50},
    {"ticker": "PLZL", "quantity": 1}
  ]
}</textarea>
      <br />
      <button onclick="loadPortfolio()">Пересчитать</button>
    </section>

    <section class="card">
      <h2>Краткий вывод</h2>
      <p id="summary">Загрузка...</p>
    </section>

    <section class="grid">
      <div class="card">
        <h2>Стоимость</h2>
        <div id="totalValue" class="big">—</div>
        <p id="dailyPnl" class="muted"></p>
      </div>

      <div class="card">
        <h2>Концентрация</h2>
        <p><span id="concentration" class="badge">—</span></p>
        <p id="maxPosition" class="muted"></p>
        <p id="maxSector" class="muted"></p>
      </div>

      <div class="card risk">
        <h2>Риски</h2>
        <ul id="riskNotes"></ul>
      </div>
    </section>

    <section class="card" id="portfolioEventsCard">
      <h2>События по портфелю</h2>
      <div id="portfolioEvents" class="muted">Загрузка событий...</div>
    </section>

    <section class="card">
      <h2>Позиции</h2>
      <table>
        <thead>
          <tr>
            <th>Тикер</th>
            <th>Сектор</th>
            <th>Кол-во</th>
            <th>Цена</th>
            <th>Стоимость</th>
            <th>Доля</th>
            <th>День</th>
          </tr>
        </thead>
        <tbody id="positions"></tbody>
      </table>
    </section>

    <section class="card">
      <h2>Сектора</h2>
      <table>
        <thead>
          <tr>
            <th>Сектор</th>
            <th>Стоимость</th>
            <th>Доля</th>
          </tr>
        </thead>
        <tbody id="sectors"></tbody>
      </table>
    </section>
  </main>

  <script>
    function rub(value) {
      if (value === null || value === undefined) return "—";
      return new Intl.NumberFormat("ru-RU", {
        maximumFractionDigits: 2
      }).format(value) + " руб.";
    }

    function pct(value) {
      if (value === null || value === undefined) return "—";
      return value + "%";
    }

    function pctClass(value) {
      return value >= 0 ? "positive" : "negative";
    }

    function li(text) {
      return `<li>${text}</li>`;
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

    function renderPortfolioEvent(group) {
      const events = group.events || [];

      return `
        <div style="border-left:4px solid #2563eb;padding:12px 14px;margin-bottom:12px;background:#f8fafc;border-radius:12px;">
          <h3>${escapeHtml(group.ticker)}</h3>
          ${events.map(event => {
            const source = event.url
              ? `<a href="${escapeHtml(event.url)}" target="_blank" rel="noreferrer" style="color:#2563eb;text-decoration:none;">Источник</a>`
              : "";

            return `
              <div style="margin-bottom:10px;">
                <strong>${escapeHtml(event.title || "Без заголовка")}</strong>
                <p class="muted">
                  важность: ${escapeHtml(event.importance)}
                  · тип: ${escapeHtml(event.event_type)}
                  · влияние: ${escapeHtml(event.impact)}
                  · ${source}
                </p>
                <p class="muted">${escapeHtml(event.reasoning || "")}</p>
              </div>
            `;
          }).join("")}
        </div>
      `;
    }

    async function loadPortfolio() {
      let payload;

      try {
        payload = JSON.parse(document.getElementById("portfolioInput").value);
      } catch (error) {
        document.getElementById("summary").textContent = "Ошибка JSON: " + error;
        return;
      }

      const response = await fetch("/portfolio/analyze", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
      });

      const data = await response.json();

      if (!data.ok) {
        document.getElementById("summary").textContent = data.error || "Ошибка анализа.";
        return;
      }

      document.getElementById("summary").textContent = data.summary;
      document.getElementById("totalValue").textContent = rub(data.total_value);

      const pnlClass = data.daily_pnl_abs >= 0 ? "positive" : "negative";
      document.getElementById("dailyPnl").innerHTML =
        `День: <span class="${pnlClass}">${rub(data.daily_pnl_abs)} / ${pct(data.daily_pnl_pct)}</span>`;

      document.getElementById("concentration").textContent = data.concentration.label;

      const maxPosition = data.concentration.max_position;
      document.getElementById("maxPosition").textContent = maxPosition
        ? `Крупнейшая позиция: ${maxPosition.ticker} — ${maxPosition.weight_pct}%`
        : "";

      const maxSector = data.concentration.max_sector;
      document.getElementById("maxSector").textContent = maxSector
        ? `Крупнейший сектор: ${maxSector.sector} — ${maxSector.weight_pct}%`
        : "";

      document.getElementById("riskNotes").innerHTML =
        (data.risk_notes || []).map(li).join("");

      document.getElementById("portfolioEvents").innerHTML =
        (data.related_events || []).length
          ? data.related_events.map(renderPortfolioEvent).join("")
          : "Связанных событий по бумагам портфеля не найдено.";

      document.getElementById("positions").innerHTML =
        (data.positions || []).map(item => `
          <tr>
            <td><strong><a href="/ticker/${item.ticker}" style="color:#2563eb;text-decoration:none;">${item.ticker}</a></strong></td>
            <td>${item.sector}</td>
            <td>${item.quantity}</td>
            <td>${item.last_close}</td>
            <td>${rub(item.current_value)}</td>
            <td>${item.weight_pct}%</td>
            <td class="${pctClass(item.daily_pnl_pct || 0)}">${pct(item.daily_pnl_pct)}</td>
          </tr>
        `).join("");

      document.getElementById("sectors").innerHTML =
        (data.sector_allocation || []).map(item => `
          <tr>
            <td><strong>${item.sector}</strong></td>
            <td>${rub(item.value)}</td>
            <td>${item.weight_pct}%</td>
          </tr>
        `).join("");
    }

    loadPortfolio();
  </script>
</body>
</html>
"""
