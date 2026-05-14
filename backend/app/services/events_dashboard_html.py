def build_events_dashboard_html() -> str:
    return """
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8" />
  <title>События · AI Аналитик рынка РФ</title>
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
    .event {
      border-left: 4px solid #2563eb;
      margin-bottom: 14px;
    }
    .event.high {
      border-left-color: #dc2626;
    }
    .event.medium {
      border-left-color: #f97316;
    }
    .muted {
      color: #64748b;
      font-size: 14px;
    }
    .badge {
      display: inline-block;
      padding: 5px 9px;
      border-radius: 999px;
      background: #e0f2fe;
      color: #075985;
      font-size: 13px;
      font-weight: 700;
      margin-right: 6px;
      margin-bottom: 6px;
    }
    .badge.impact-positive {
      background: #dcfce7;
      color: #166534;
    }
    .badge.impact-negative {
      background: #fee2e2;
      color: #991b1b;
    }
    .badge.impact-mixed {
      background: #fef3c7;
      color: #92400e;
    }
    button {
      background: #2563eb;
      color: white;
      border: 0;
      border-radius: 10px;
      padding: 10px 14px;
      font-weight: 700;
      cursor: pointer;
      margin-right: 8px;
    }
    button:hover {
      background: #1d4ed8;
    }
    input, select {
      border: 1px solid #cbd5e1;
      border-radius: 10px;
      padding: 10px 12px;
      font-size: 14px;
      margin-right: 8px;
    }
    a.source {
      color: #2563eb;
      text-decoration: none;
      font-weight: 600;
    }
    ul {
      margin-top: 8px;
    }
  </style>
</head>
<body>
  <header>
    <h1>Радар событий</h1>
    <p>
      <a href="/dashboard">← Назад к рынку</a>
      · <a href="/portfolio/demo">Портфель</a>
    </p>
  </header>

  <main>
    <section class="card">
      <h2>Управление</h2>
      <p class="muted">Загрузка RSS ЦБ и фильтр событий по важности/тикеру.</p>

      <button onclick="ingestRSS()">Загрузить RSS ЦБ</button>
      <button onclick="loadEvents()">Обновить радар</button>

      <br /><br />

      <label class="muted">Мин. важность:</label>
      <select id="minImportance">
        <option value="1">1+</option>
        <option value="5" selected>5+</option>
        <option value="7">7+</option>
        <option value="8">8+</option>
        <option value="9">9+</option>
      </select>

      <label class="muted">Тикер:</label>
      <input id="tickerFilter" placeholder="SBER, GAZP..." />

      <button onclick="loadEvents()">Применить</button>

      <p id="status" class="muted"></p>
    </section>

    <section class="card">
      <h2>Краткая сводка</h2>
      <p id="summary">Загрузка...</p>
    </section>

    <section class="grid">
      <div class="card">
        <h2>Типы событий</h2>
        <div id="byType"></div>
      </div>

      <div class="card">
        <h2>Влияние</h2>
        <div id="byImpact"></div>
      </div>

      <div class="card">
        <h2>Активы</h2>
        <div id="byAsset"></div>
      </div>
    </section>

    <section class="card">
      <h2>Главные события</h2>
      <div id="events"></div>
    </section>
  </main>

  <script>
    function escapeHtml(value) {
      if (value === null || value === undefined) return "";
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function badge(text, cls = "") {
      return `<span class="badge ${cls}">${escapeHtml(text)}</span>`;
    }

    function renderAggregation(obj) {
      if (!obj || Object.keys(obj).length === 0) {
        return '<p class="muted">Нет данных</p>';
      }

      return Object.entries(obj)
        .map(([key, value]) => badge(`${key}: ${value}`))
        .join("");
    }

    function importanceClass(value) {
      if (value >= 8) return "high";
      if (value >= 6) return "medium";
      return "";
    }

    function impactClass(value) {
      if (value === "positive") return "impact-positive";
      if (value === "negative") return "impact-negative";
      if (value === "mixed") return "impact-mixed";
      return "";
    }

    function renderEvent(event) {
      const title = event.title || "Без заголовка";
      const assets = (event.affected_assets || []).map(x => badge(x)).join("");
      const sectors = (event.affected_sectors || []).map(x => badge(x)).join("");
      const watch = (event.watch_next || []).map(x => `<li>${escapeHtml(x)}</li>`).join("");

      const sourceLink = event.url
        ? `<a class="source" href="${escapeHtml(event.url)}" target="_blank" rel="noreferrer">Источник</a>`
        : "";

      return `
        <div class="card event ${importanceClass(event.importance)}">
          <h3>${escapeHtml(title)}</h3>
          <p class="muted">
            ${escapeHtml(event.source || "")}
            · важность: ${escapeHtml(event.importance)}
            · тип: ${escapeHtml(event.event_type)}
            · ${sourceLink}
          </p>

          <p>
            ${badge(event.impact || "unknown", impactClass(event.impact))}
            ${badge(event.time_horizon || "без горизонта")}
            ${badge("confidence: " + (event.confidence ?? "—"))}
          </p>

          <p><strong>Активы:</strong> ${assets || '<span class="muted">не определены</span>'}</p>
          <p><strong>Секторы:</strong> ${sectors || '<span class="muted">не определены</span>'}</p>

          <p class="muted">${escapeHtml(event.reasoning || "")}</p>

          ${watch ? `<p><strong>Что отслеживать:</strong></p><ul>${watch}</ul>` : ""}
        </div>
      `;
    }

    async function ingestRSS() {
      document.getElementById("status").textContent = "Загружаю RSS ЦБ...";
      const response = await fetch("/ingest/rss/defaults?limit_per_source=10", {
        method: "POST"
      });
      const data = await response.json();

      document.getElementById("status").textContent =
        `RSS загружен. Новых событий: ${data.total_inserted}, дублей: ${data.total_duplicates}.`;

      await loadEvents();
    }

    async function loadEvents() {
      const minImportance = document.getElementById("minImportance").value;
      const ticker = document.getElementById("tickerFilter").value.trim();

      const params = new URLSearchParams({
        limit: "30",
        min_importance: minImportance
      });

      if (ticker) {
        params.set("ticker", ticker);
      }

      const response = await fetch(`/events/radar?${params.toString()}`);
      const data = await response.json();

      document.getElementById("summary").textContent = data.summary || "Нет сводки.";
      document.getElementById("byType").innerHTML = renderAggregation(data.by_event_type);
      document.getElementById("byImpact").innerHTML = renderAggregation(data.by_impact);
      document.getElementById("byAsset").innerHTML = renderAggregation(data.by_asset);

      document.getElementById("events").innerHTML =
        (data.top_events || []).map(renderEvent).join("") ||
        '<p class="muted">Событий не найдено.</p>';
    }

    loadEvents().catch(error => {
      document.getElementById("summary").textContent = "Ошибка загрузки: " + error;
    });
  </script>
</body>
</html>
"""
