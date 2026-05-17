from __future__ import annotations


def build_signals_page_html() -> str:
    return """<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <title>Сигналы рынка</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root {
      --bg: #f5f7fb;
      --card: #ffffff;
      --text: #0f172a;
      --muted: #64748b;
      --border: #e2e8f0;
      --blue: #2563eb;
      --green: #16a34a;
      --green-bg: #dcfce7;
      --yellow: #ca8a04;
      --yellow-bg: #fef9c3;
      --red: #dc2626;
      --red-bg: #fee2e2;
      --neutral-bg: #f1f5f9;
      --shadow: 0 14px 40px rgba(15, 23, 42, 0.08);
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
    }

    header {
      padding: 26px 22px 18px;
      background: linear-gradient(135deg, #0f172a, #1e3a8a);
      color: white;
    }

    header .inner {
      max-width: 1180px;
      margin: 0 auto;
    }

    h1 {
      margin: 0 0 8px;
      font-size: 32px;
      letter-spacing: -0.04em;
    }

    header p {
      margin: 0;
      color: rgba(255,255,255,0.78);
      max-width: 860px;
      line-height: 1.55;
    }

    nav {
      margin-top: 16px;
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }

    nav a {
      color: white;
      text-decoration: none;
      border: 1px solid rgba(255,255,255,0.24);
      background: rgba(255,255,255,0.10);
      border-radius: 999px;
      padding: 8px 12px;
      font-weight: 700;
      font-size: 13px;
    }

    main {
      max-width: 1180px;
      margin: 0 auto;
      padding: 22px;
    }

    .toolbar {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 24px;
      box-shadow: var(--shadow);
      padding: 18px;
      display: grid;
      grid-template-columns: 1.4fr auto;
      gap: 16px;
      align-items: end;
    }

    .filters {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      align-items: end;
    }

    label {
      display: flex;
      flex-direction: column;
      gap: 6px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
    }

    input, select {
      height: 42px;
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 0 12px;
      min-width: 190px;
      background: white;
      color: var(--text);
      font-size: 14px;
    }

    .button {
      border: 0;
      border-radius: 12px;
      padding: 12px 16px;
      background: var(--blue);
      color: white;
      font-weight: 850;
      cursor: pointer;
      text-decoration: none;
      display: inline-flex;
      justify-content: center;
      align-items: center;
      min-height: 42px;
    }

    .button.secondary {
      background: #eef2ff;
      color: #1e40af;
    }

    .button.ghost {
      background: white;
      color: var(--text);
      border: 1px solid var(--border);
    }

    .button.active {
      background: #0f172a;
      color: white;
    }

    .summary {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin: 18px 0;
    }

    .metric {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 16px;
      box-shadow: 0 10px 26px rgba(15, 23, 42, 0.05);
    }

    .metric .label {
      color: var(--muted);
      font-size: 12px;
      font-weight: 850;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }

    .metric .value {
      margin-top: 8px;
      font-size: 28px;
      font-weight: 900;
      letter-spacing: -0.04em;
    }

    .status {
      margin: 12px 0 0;
      color: var(--muted);
      font-size: 14px;
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px;
      margin-top: 18px;
    }

    .signal-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 24px;
      box-shadow: var(--shadow);
      padding: 18px;
      display: flex;
      flex-direction: column;
      gap: 14px;
      min-height: 330px;
    }

    .card-top {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: flex-start;
    }

    .ticker {
      font-size: 24px;
      font-weight: 950;
      letter-spacing: -0.04em;
    }

    .name {
      color: var(--muted);
      font-size: 13px;
      margin-top: 4px;
      line-height: 1.35;
      min-height: 18px;
    }

    .badge {
      padding: 8px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 900;
      white-space: nowrap;
    }

    .badge.positive { background: var(--green-bg); color: #166534; }
    .badge.neutral { background: var(--neutral-bg); color: #334155; }
    .badge.negative { background: var(--red-bg); color: #991b1b; }
    .badge.unknown { background: var(--yellow-bg); color: #854d0e; }

    .probability {
      display: flex;
      align-items: baseline;
      gap: 8px;
    }

    .probability .number {
      font-size: 44px;
      line-height: 1;
      font-weight: 950;
      letter-spacing: -0.07em;
    }

    .probability .caption {
      color: var(--muted);
      font-weight: 800;
      font-size: 12px;
      line-height: 1.2;
    }

    .kv {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }

    .kv-item {
      background: #f8fafc;
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 12px;
    }

    .kv-item .k {
      color: var(--muted);
      font-size: 12px;
      font-weight: 850;
    }

    .kv-item .v {
      margin-top: 5px;
      font-weight: 950;
      font-size: 16px;
    }

    .decision {
      padding: 12px 14px;
      border-radius: 16px;
      line-height: 1.45;
      font-size: 14px;
      font-weight: 700;
    }

    .decision.positive { background: var(--green-bg); color: #14532d; }
    .decision.neutral { background: var(--neutral-bg); color: #334155; }
    .decision.negative { background: var(--red-bg); color: #7f1d1d; }
    .decision.unknown { background: var(--yellow-bg); color: #713f12; }

    .card-actions {
      margin-top: auto;
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }

    .details {
      display: none;
      border-top: 1px solid var(--border);
      padding-top: 12px;
      color: #334155;
      line-height: 1.5;
      font-size: 14px;
    }

    .details ul {
      margin: 8px 0 0 18px;
      padding: 0;
    }

    .details h4 {
      margin: 12px 0 4px;
    }

    .empty {
      background: var(--card);
      border: 1px dashed var(--border);
      border-radius: 24px;
      padding: 26px;
      text-align: center;
      color: var(--muted);
      grid-column: 1 / -1;
    }

    .small { font-size: 12px; }
    .muted { color: var(--muted); }

    @media (max-width: 980px) {
      .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .toolbar { grid-template-columns: 1fr; }
    }

    @media (max-width: 640px) {
      main { padding: 14px; }
      header { padding: 22px 14px; }
      h1 { font-size: 26px; }
      .grid { grid-template-columns: 1fr; }
      .summary { grid-template-columns: 1fr; }
      .filters { flex-direction: column; align-items: stretch; }
      input, select { width: 100%; min-width: 0; }
      .button { width: 100%; }
    }
  </style>
</head>
<body>
  <header>
    <div class="inner">
      <h1>Сигналы рынка</h1>
      <p>Пользовательская витрина сигналов: итоговая вероятность достижения цели, готовая рекомендация и объяснение. Модель, ML-фильтр и риск-блок работают внутри — без лишней сложности для пользователя.</p>
      <nav>
        <a href="/dashboard">← Рынок</a>
        <a href="/portfolio/construct/demo">Конструктор портфеля</a>
        <a href="/ai/report/demo">AI Report</a>
        <a href="/tickers/SBER">Пример тикера</a>
      </nav>
    </div>
  </header>

  <main>
    <section class="toolbar">
      <div class="filters">
        <label>
          Поиск тикера
          <input id="searchInput" placeholder="SBER, GAZP, LKOH..." />
        </label>

        <label>
          Фильтр
          <select id="decisionFilter">
            <option value="">Все решения</option>
            <option value="buy">Покупать / рассмотреть</option>
            <option value="watch">Наблюдать</option>
            <option value="avoid">Не покупать / риск</option>
          </select>
        </label>

        <label>
          Сортировка
          <select id="sortBy">
            <option value="decision_probability">Сначала лучшие сигналы</option>
            <option value="probability_desc">Вероятность ↓</option>
            <option value="ticker_asc">Тикер A→Z</option>
          </select>
        </label>

        <label>
          Количество
          <select id="limitInput">
            <option value="30">30</option>
            <option value="60" selected>60</option>
            <option value="100">100</option>
          </select>
        </label>
      </div>

      <div class="filters">
        <button class="button" onclick="loadSignals()">Обновить</button>
        <button class="button secondary" onclick="clearFilters()">Сбросить</button>
      </div>
    </section>

    <p id="status" class="status">Загружаю сигналы...</p>

    <section class="summary">
      <div class="metric">
        <div class="label">Всего показано</div>
        <div class="value" id="metricTotal">—</div>
      </div>
      <div class="metric">
        <div class="label">Покупка / рассмотреть</div>
        <div class="value" id="metricBuy">—</div>
      </div>
      <div class="metric">
        <div class="label">Наблюдать</div>
        <div class="value" id="metricWatch">—</div>
      </div>
      <div class="metric">
        <div class="label">Не покупать / риск</div>
        <div class="value" id="metricAvoid">—</div>
      </div>
    </section>

    <section id="signalsGrid" class="grid"></section>
  </main>

  <script>
    let latestRows = [];

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function toNumber(value) {
      const n = Number(value);
      return Number.isNaN(n) ? null : n;
    }

    function formatNumber(value, digits = 2) {
      const n = toNumber(value);
      if (n === null) return "—";
      return n.toLocaleString("ru-RU", {
        maximumFractionDigits: digits,
        minimumFractionDigits: digits === 0 ? 0 : 0
      });
    }

    function formatPct(value, digits = 1) {
      const n = toNumber(value);
      if (n === null) return "—";
      return `${formatNumber(n, digits)}%`;
    }

    function normalizeRow(row) {
      const forecast = row.forecast || {};
      const signal = row.signal || {};
      const source = Object.assign({}, forecast, signal, row);

      return {
        raw: row,
        ticker: source.ticker || row.ticker || "—",
        name: source.name || row.name || source.company_name || "",
        recommendation: source.recommendation || source.label || "Наблюдать",
        consumer_action: source.consumer_action || source.action || "",
        decision: source.decision || "",
        decision_level: source.decision_level || "neutral",
        decision_reason: source.decision_reason || "",
        is_buy_candidate: Boolean(source.is_buy_candidate),
        target_probability_pct: toNumber(source.target_probability_pct),
        rule_probability_pct: toNumber(source.rule_probability_pct),
        ml_probability_pct: toNumber(source.ml_probability_pct),
        ml_adjustment_pct: toNumber(source.ml_adjustment_pct),
        target_price: toNumber(source.target_price),
        current_price: toNumber(source.current_price || source.price),
        potential_pct: toNumber(source.potential_pct || source.expected_return_pct || source.target_potential_pct),
        reliability_level: source.reliability_level || source.reliability || "—",
        risk_level: source.risk_level || "—",
        probability_source: source.probability_source || ""
      };
    }

    function decisionClass(level, action, recommendation) {
      const value = `${level || ""} ${action || ""} ${recommendation || ""}`.toLowerCase();

      if (value.includes("buy") || value.includes("positive") || value.includes("покуп")) return "positive";
      if (value.includes("avoid") || value.includes("negative") || value.includes("risk") || value.includes("не покуп")) return "negative";
      if (value.includes("unknown")) return "unknown";
      return "neutral";
    }

    function decisionRank(item) {
      if (item.is_buy_candidate) return 1;
      if ((item.consumer_action || "").includes("watch")) return 2;
      if ((item.consumer_action || "").includes("avoid")) return 3;
      return 4;
    }

    function filterRows(rows) {
      const filter = document.getElementById("decisionFilter").value;
      const query = document.getElementById("searchInput").value.trim().toUpperCase();

      return rows.filter(item => {
        if (query && !item.ticker.toUpperCase().includes(query) && !item.name.toUpperCase().includes(query)) {
          return false;
        }

        const action = String(item.consumer_action || "").toLowerCase();
        const rec = String(item.recommendation || "").toLowerCase();

        if (filter === "buy") {
          return item.is_buy_candidate || action.includes("buy") || rec.includes("покупать") || rec.includes("рассмотреть");
        }

        if (filter === "watch") {
          return action.includes("watch") || rec.includes("наблюдать");
        }

        if (filter === "avoid") {
          return action.includes("avoid") || rec.includes("не покупать") || rec.includes("риск");
        }

        return true;
      });
    }

    function sortRows(rows) {
      const sortBy = document.getElementById("sortBy").value;

      return [...rows].sort((a, b) => {
        if (sortBy === "probability_desc") {
          return (b.target_probability_pct ?? -1) - (a.target_probability_pct ?? -1);
        }

        if (sortBy === "ticker_asc") {
          return a.ticker.localeCompare(b.ticker);
        }

        const rankDelta = decisionRank(a) - decisionRank(b);
        if (rankDelta !== 0) return rankDelta;

        return (b.target_probability_pct ?? -1) - (a.target_probability_pct ?? -1);
      });
    }

    function listHtml(items) {
      const values = Array.isArray(items) ? items.filter(Boolean) : [];
      if (!values.length) return "<p class='muted'>Нет дополнительных факторов.</p>";
      return `<ul>${values.map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
    }

    async function toggleDetails(ticker) {
      const id = `details-${ticker}`;
      const box = document.getElementById(id);

      if (!box) return;

      if (box.dataset.loaded === "true") {
        box.style.display = box.style.display === "block" ? "none" : "block";
        return;
      }

      box.style.display = "block";
      box.innerHTML = "<p class='muted'>Загружаю объяснение...</p>";

      try {
        const response = await fetch(`/signals/consumer/${encodeURIComponent(ticker)}.json`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        const forecast = data.forecast || {};
        const signal = data.signal || {};
        const explanation = forecast.explanation || signal.explanation || {};
        const decisionReason = forecast.decision_reason || signal.decision_reason || "";

        box.innerHTML = `
          <h4>Почему такой сигнал?</h4>
          <p>${escapeHtml(decisionReason || explanation.summary || "Система учитывает вероятность достижения цели, риск, техническую картину и ML-корректировку.")}</p>

          <h4>Факторы</h4>
          ${listHtml(explanation.technical)}

          <h4>Новости и события</h4>
          ${listHtml(explanation.news)}

          <h4>Риски</h4>
          ${listHtml(explanation.risks)}

          <p class="small muted">
            Rule: ${formatPct(forecast.rule_probability_pct || signal.rule_probability_pct)} ·
            ML: ${formatPct(forecast.ml_probability_pct || signal.ml_probability_pct)} ·
            Источник: ${escapeHtml(forecast.probability_source || signal.probability_source || "—")}
          </p>
        `;

        box.dataset.loaded = "true";
      } catch (error) {
        box.innerHTML = `<p class="muted">Не удалось загрузить объяснение: ${escapeHtml(error.message)}</p>`;
      }
    }

    function renderSignals() {
      const grid = document.getElementById("signalsGrid");
      const rows = sortRows(filterRows(latestRows));

      const buyCount = rows.filter(item => item.is_buy_candidate).length;
      const watchCount = rows.filter(item => String(item.consumer_action || "").includes("watch") || item.recommendation === "Наблюдать").length;
      const avoidCount = rows.filter(item => String(item.consumer_action || "").includes("avoid") || item.recommendation === "Не покупать").length;

      document.getElementById("metricTotal").textContent = rows.length;
      document.getElementById("metricBuy").textContent = buyCount;
      document.getElementById("metricWatch").textContent = watchCount;
      document.getElementById("metricAvoid").textContent = avoidCount;

      if (!rows.length) {
        grid.innerHTML = `<div class="empty">По выбранным фильтрам сигналов нет.</div>`;
        return;
      }

      grid.innerHTML = rows.map(item => {
        const cls = decisionClass(item.decision_level, item.consumer_action, item.recommendation);
        const probability = item.target_probability_pct;
        const potential = item.potential_pct;
        const decisionText = item.decision || item.decision_reason || item.recommendation;
        const target = item.target_price;
        const current = item.current_price;

        return `
          <article class="signal-card">
            <div class="card-top">
              <div>
                <div class="ticker">${escapeHtml(item.ticker)}</div>
                <div class="name">${escapeHtml(item.name)}</div>
              </div>
              <span class="badge ${cls}">${escapeHtml(item.recommendation)}</span>
            </div>

            <div class="probability">
              <div class="number">${probability === null ? "—" : Math.round(probability)}</div>
              <div class="caption">вероятность<br>достижения цели, %</div>
            </div>

            <div class="kv">
              <div class="kv-item">
                <div class="k">Текущая цена</div>
                <div class="v">${formatNumber(current)}</div>
              </div>
              <div class="kv-item">
                <div class="k">Цель</div>
                <div class="v">${formatNumber(target)}</div>
              </div>
              <div class="kv-item">
                <div class="k">Потенциал</div>
                <div class="v">${formatPct(potential)}</div>
              </div>
              <div class="kv-item">
                <div class="k">Надёжность</div>
                <div class="v">${escapeHtml(item.reliability_level)}</div>
              </div>
            </div>

            <div class="decision ${cls}">
              ${escapeHtml(decisionText)}
            </div>

            <div class="card-actions">
              <button class="button secondary" onclick="toggleDetails('${escapeHtml(item.ticker)}')">Почему?</button>
              <a class="button ghost" href="/tickers/${encodeURIComponent(item.ticker)}">Открыть тикер</a>
            </div>

            <div id="details-${escapeHtml(item.ticker)}" class="details"></div>
          </article>
        `;
      }).join("");
    }

    function getConsumerSignalsUrl() {
      const params = new URLSearchParams();
      params.set("limit", document.getElementById("limitInput").value || "60");

      const query = document.getElementById("searchInput").value.trim();
      if (query) {
        params.set("q", query);
      }

      return `/signals/consumer.json?${params.toString()}`;
    }

    async function loadSignals() {
      const status = document.getElementById("status");
      status.textContent = "Загружаю потребительские сигналы...";

      try {
        const response = await fetch(getConsumerSignalsUrl());
        if (!response.ok) throw new Error(`HTTP ${response.status}: ${await response.text()}`);

        const data = await response.json();
        const rows = data.rows || data.signals || [];
        latestRows = rows.map(normalizeRow);

        renderSignals();

        const now = new Date().toLocaleTimeString("ru-RU");
        status.textContent = `Обновлено: ${now}. Показано ${latestRows.length} сигналов.`;
      } catch (error) {
        status.textContent = `Ошибка загрузки: ${error.message}`;
        document.getElementById("signalsGrid").innerHTML = `<div class="empty">Не удалось загрузить сигналы.</div>`;
      }
    }

    function clearFilters() {
      document.getElementById("searchInput").value = "";
      document.getElementById("decisionFilter").value = "";
      document.getElementById("sortBy").value = "decision_probability";
      loadSignals();
    }

    document.getElementById("searchInput").addEventListener("keydown", event => {
      if (event.key === "Enter") loadSignals();
    });

    document.getElementById("decisionFilter").addEventListener("change", renderSignals);
    document.getElementById("sortBy").addEventListener("change", renderSignals);
    document.getElementById("limitInput").addEventListener("change", loadSignals);

    window.loadSignals = loadSignals;
    window.clearFilters = clearFilters;
    window.toggleDetails = toggleDetails;

    loadSignals();
  </script>
</body>
</html>"""
