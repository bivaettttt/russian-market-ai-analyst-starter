from __future__ import annotations


def build_signals_page_html() -> str:
    return """<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <title>Сигналы · AI Аналитик рынка РФ</title>
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f3f4f6;
      color: #111827;
    }
    header {
      background: linear-gradient(135deg, #0f172a, #111827);
      color: #fff;
      padding: 42px 32px;
    }
    header h1 { margin: 0 0 10px; font-size: 34px; }
    header p { margin: 0; color: #cbd5e1; max-width: 880px; line-height: 1.55; }
    header a { color: #93c5fd; text-decoration: none; font-weight: 800; }
    main { padding: 28px 32px; max-width: 1480px; margin: 0 auto; }
    .card {
      background: #fff;
      border: 1px solid #e5e7eb;
      border-radius: 22px;
      padding: 24px;
      margin-bottom: 22px;
      box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
    }
    .muted { color: #64748b; }
    .small { font-size: 13px; }
    .metrics {
      display: grid;
      grid-template-columns: repeat(4, minmax(160px, 1fr));
      gap: 14px;
      margin-top: 16px;
    }
    .metric {
      background: #f8fafc;
      border: 1px solid #e5e7eb;
      border-radius: 16px;
      padding: 16px;
    }
    .metric .label { color: #64748b; font-size: 13px; font-weight: 800; }
    .metric .value { font-size: 28px; font-weight: 950; margin-top: 6px; }
    .controls { display: flex; flex-wrap: wrap; gap: 10px; align-items: end; margin-top: 18px; }
    .control { display: inline-flex; flex-direction: column; gap: 6px; }
    input, select {
      height: 40px;
      border: 1px solid #d6dee8;
      border-radius: 12px;
      padding: 0 10px;
      background: #fff;
      min-width: 150px;
    }
    .button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 40px;
      border-radius: 12px;
      padding: 10px 14px;
      background: #2563eb;
      color: #fff;
      text-decoration: none;
      font-weight: 850;
      border: 0;
      cursor: pointer;
      margin: 0;
    }
    .button.secondary { background: #334155; }
    .button.light { background: #e5e7eb; color: #111827; }
    .button.active { background: #2563eb; }
    .pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border-radius: 999px;
      padding: 6px 10px;
      font-weight: 850;
      font-size: 13px;
      background: #eef2ff;
      color: #3730a3;
      white-space: nowrap;
    }
    .pill.positive { background: #dcfce7; color: #166534; }
    .pill.neutral { background: #f1f5f9; color: #334155; }
    .pill.negative { background: #fee2e2; color: #991b1b; }
    .probability {
      font-size: 28px;
      font-weight: 950;
      letter-spacing: -0.04em;
    }
    .probability.positive { color: #15803d; }
    .probability.neutral { color: #334155; }
    .probability.negative { color: #dc2626; }
    table { width: 100%; border-collapse: collapse; margin-top: 14px; }
    th, td { text-align: left; border-bottom: 1px solid #e5e7eb; padding: 13px 10px; vertical-align: top; }
    th { color: #64748b; font-size: 13px; background: #f8fafc; }
    a { color: #2563eb; font-weight: 850; text-decoration: none; }
    .good { color: #15803d; font-weight: 850; }
    .bad { color: #dc2626; font-weight: 850; }
    .explain-row td { background: #f8fafc; border-bottom: 1px solid #dbe3ef; }
    .explanation {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 14px;
    }
    .explanation-box {
      background: #fff;
      border: 1px solid #e5e7eb;
      border-radius: 14px;
      padding: 14px;
    }
    .explanation-box h4 { margin: 0 0 8px; }
    .explanation-box ul { margin: 0; padding-left: 18px; color: #475569; }
    .disclaimer { color: #64748b; font-size: 13px; line-height: 1.5; }
    @media (max-width: 1000px) {
      .metrics, .explanation { grid-template-columns: 1fr; }
      main { padding: 18px; }
      table { font-size: 13px; }
    }
  </style>
</head>
<body>
  <header>
    <h1>Сигналы по акциям</h1>
    <p>
      Готовая витрина прогнозов без выбора модели. Главное число — вероятность достижения цели в указанном горизонте.
      Нажмите «Почему?» у любого сигнала, чтобы увидеть простое объяснение: техника, новости и риски.
    </p>
    <p style="margin-top:14px;"><a href="/dashboard">← Рынок</a> · <a href="/portfolio/construct/demo">Конструктор портфеля</a> · <a href="/ai/report/demo">AI Report</a></p>
  </header>

  <main>
    <section class="card">
      <h2>Обзор сигналов</h2>
      <p class="muted" id="status">Загружаю сигналы...</p>
      <div class="metrics">
        <div class="metric"><div class="label">Всего</div><div class="value" id="totalSignals">—</div></div>
        <div class="metric"><div class="label">Покупка / интерес</div><div class="value good" id="positiveSignals">—</div></div>
        <div class="metric"><div class="label">Наблюдать</div><div class="value" id="watchSignals">—</div></div>
        <div class="metric"><div class="label">Средняя вероятность</div><div class="value" id="avgProbability">—</div></div>
      </div>
      <div class="controls">
        <button id="filterAll" class="button active" onclick="setFilter('')">Все</button>
        <button id="filterPositive" class="button light" onclick="setFilter('positive')">Покупка / интерес</button>
        <button id="filterWatch" class="button light" onclick="setFilter('hold_watch')">Наблюдать</button>
        <button id="filterRisk" class="button light" onclick="setFilter('risk_sell_watch')">Высокий риск</button>
        <label class="control small muted">Поиск тикера
          <input id="tickerSearch" type="search" placeholder="SBER, Газпром, Лукойл" onkeydown="handleSearchKey(event)" />
        </label>
        <label class="control small muted">Мин. вероятность
          <input id="minProbability" type="number" min="0" max="100" step="1" placeholder="например 60" onchange="loadSignals()" />
        </label>
        <label class="control small muted">Сортировка
          <select id="sortBy" onchange="renderCurrentSignals()">
            <option value="probability_desc">Вероятность ↓</option>
            <option value="potential_desc">Потенциал ↓</option>
            <option value="ticker_asc">Тикер A→Z</option>
          </select>
        </label>
        <button class="button secondary" onclick="loadSignals()">Обновить</button>
      </div>
    </section>

    <section class="card">
      <h2>Список сигналов</h2>
      <table>
        <thead>
          <tr>
            <th>Бумага</th>
            <th>Цена</th>
            <th>Прогноз</th>
            <th>Вероятность цели</th>
            <th>Цель / диапазон</th>
            <th>Потенциал</th>
            <th>Горизонт</th>
            <th></th>
          </tr>
        </thead>
        <tbody id="signalsRows">
          <tr><td colspan="8" class="muted">Загрузка...</td></tr>
        </tbody>
      </table>
      <p class="disclaimer">
        Вероятность — модельная оценка достижения указанной цели, а не гарантия результата и не индивидуальная инвестиционная рекомендация.
      </p>
    </section>
  </main>

  <script>
    let currentFilter = "";
    let currentRows = [];

    function setText(id, value) {
      document.getElementById(id).textContent = value === null || value === undefined || value === "" ? "—" : value;
    }
    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }
    function formatNumber(value, digits = 2) {
      const n = Number(value);
      if (Number.isNaN(n)) return "—";
      return n.toLocaleString("ru-RU", { minimumFractionDigits: digits, maximumFractionDigits: digits });
    }
    function formatRub(value) {
      const n = Number(value);
      if (Number.isNaN(n)) return "—";
      return formatNumber(n, 2) + " ₽";
    }
    function formatPct(value, digits = 2) {
      const n = Number(value);
      if (Number.isNaN(n)) return "—";
      return formatNumber(n, digits) + "%";
    }
    function toneClass(tone) {
      if (tone === "positive") return "positive";
      if (tone === "negative") return "negative";
      return "neutral";
    }
    function probabilityClass(row) {
      const probability = Number(row.target_probability_pct);
      if (row.recommendation_tone === "negative") return "negative";
      if (!Number.isNaN(probability) && probability >= 65) return "positive";
      return "neutral";
    }
    function updateFilterButtons() {
      const buttons = {
        filterAll: currentFilter === "",
        filterPositive: currentFilter === "positive",
        filterWatch: currentFilter === "hold_watch",
        filterRisk: currentFilter === "risk_sell_watch"
      };
      Object.entries(buttons).forEach(([id, active]) => {
        const el = document.getElementById(id);
        if (!el) return;
        el.className = active ? "button active" : "button light";
      });
    }
    function setFilter(filter) {
      currentFilter = filter;
      loadSignals();
    }
    function handleSearchKey(event) {
      if (event.key === "Enter") {
        loadSignals();
      }
    }
    function getApiAction() {
      if (currentFilter === "positive") return "";
      return currentFilter;
    }
    function buildUrl() {
      const params = new URLSearchParams();
      params.set("limit", "100");
      const action = getApiAction();
      if (action) params.set("action", action);
      const minProbability = document.getElementById("minProbability")?.value;
      if (minProbability) params.set("min_probability", minProbability);
      const search = document.getElementById("tickerSearch")?.value?.trim();
      if (search) params.set("q", search);
      return "/signals/consumer.json?" + params.toString();
    }
    function filteredRows() {
      let rows = [...currentRows];
      if (currentFilter === "positive") {
        rows = rows.filter(row => ["buy_watch", "watch_buy"].includes(row.action));
      }
      const sortBy = document.getElementById("sortBy")?.value || "probability_desc";
      rows.sort((a, b) => {
        if (sortBy === "ticker_asc") return String(a.ticker || "").localeCompare(String(b.ticker || ""));
        if (sortBy === "potential_desc") return Number(b.potential_pct || -999) - Number(a.potential_pct || -999);
        return Number(b.target_probability_pct || -999) - Number(a.target_probability_pct || -999);
      });
      return rows;
    }
    function explanationList(items) {
      return (items || []).map(item => `<li>${escapeHtml(item)}</li>`).join("") || "<li>Факторы не выделены.</li>";
    }
    function explanationHtml(row) {
      const explanation = row.explanation || {};
      return `
        <tr class="explain-row" id="explain-${escapeHtml(row.ticker)}" style="display:none;">
          <td colspan="8">
            <p><b>${escapeHtml(explanation.summary || "Почему появился этот прогноз")}</b></p>
            <div class="explanation">
              <div class="explanation-box"><h4>Техническая картина</h4><ul>${explanationList(explanation.technical)}</ul></div>
              <div class="explanation-box"><h4>Новости и события</h4><ul>${explanationList(explanation.news)}</ul></div>
              <div class="explanation-box"><h4>Риски</h4><ul>${explanationList(explanation.risks)}</ul></div>
            </div>
          </td>
        </tr>`;
    }
    function toggleExplanation(ticker) {
      const el = document.getElementById("explain-" + ticker);
      if (!el) return;
      el.style.display = el.style.display === "none" ? "table-row" : "none";
    }
    function renderCurrentSignals() {
      const rows = filteredRows();
      const tbody = document.getElementById("signalsRows");
      if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="8" class="muted">Под выбранные фильтры сигналов нет.</td></tr>';
        return;
      }
      tbody.innerHTML = rows.map(row => {
        const range = row.forecast_range || {};
        const rangeText = range.low && range.high ? `${formatRub(range.low)} — ${formatRub(range.high)}` : "—";
        const tone = toneClass(row.recommendation_tone);
        const probClass = probabilityClass(row);
        return `
          <tr>
            <td><a href="${escapeHtml(row.ticker_url)}">${escapeHtml(row.ticker)}</a><div class="muted small">${escapeHtml(row.name || "")}</div></td>
            <td><b>${formatRub(row.price)}</b><div class="muted small">${escapeHtml(row.trade_date || "")}</div></td>
            <td><span class="pill ${tone}">${escapeHtml(row.recommendation)}</span></td>
            <td><div class="probability ${probClass}">${formatPct(row.target_probability_pct, 0)}</div><div class="muted small">достижения цели</div></td>
            <td><b>${formatRub(row.target_price)}</b><div class="muted small">${rangeText}</div></td>
            <td class="${Number(row.potential_pct) >= 0 ? 'good' : 'bad'}"><b>${formatPct(row.potential_pct)}</b><div class="muted small">${formatRub(row.potential_abs)}</div></td>
            <td>
              ${escapeHtml(row.horizon || "—")}
              <div class="muted small">риск: ${escapeHtml(row.risk_level || "—")}</div>
              <div class="muted small">надёжность: ${escapeHtml(row.reliability_level || "—")}</div>
            </td>
            <td><button class="button light" onclick="toggleExplanation('${escapeHtml(row.ticker)}')">Почему?</button></td>
          </tr>
          ${explanationHtml(row)}
        `;
      }).join("");
    }
    async function loadSignals() {
      updateFilterButtons();
      setText("status", "Загружаю потребительские сигналы...");
      const response = await fetch(buildUrl());
      if (!response.ok) throw new Error("HTTP " + response.status + ": " + await response.text());
      const data = await response.json();
      currentRows = data.rows || [];
      const summary = data.summary || {};
      setText("totalSignals", summary.total);
      setText("positiveSignals", summary.positive);
      setText("watchSignals", summary.watch);
      setText("avgProbability", formatPct(summary.avg_probability_pct, 1));
      renderCurrentSignals();
      const now = new Date().toLocaleTimeString("ru-RU");
      const query = data.query ? ` Поиск: ${data.query}.` : "";
      setText("status", `Готово. Показано сигналов: ${currentRows.length}.${query} Обновлено: ${now}.`);
    }
    window.setFilter = setFilter;
    window.handleSearchKey = handleSearchKey;
    window.loadSignals = loadSignals;
    window.renderCurrentSignals = renderCurrentSignals;
    window.toggleExplanation = toggleExplanation;
    loadSignals().catch(error => setText("status", "Ошибка загрузки: " + error.message));
  </script>
</body>
</html>"""
