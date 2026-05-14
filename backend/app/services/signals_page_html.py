from __future__ import annotations


def build_signals_page_html() -> str:
    return """<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <title>Сигналы · AI Аналитик рынка РФ</title>
  <style>
    * {
      box-sizing: border-box;
    }

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

    .muted {
      color: #64748b;
    }

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

    .button.secondary {
      background: #334155;
    }

    .button.active {
      background: #2563eb;
    }

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

    .good {
      color: #15803d;
      font-weight: 850;
    }

    .bad {
      color: #dc2626;
      font-weight: 850;
    }

    .badge {
      display: inline-block;
      padding: 5px 9px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 850;
      background: #e0f2fe;
      color: #075985;
    }

    .badge.buy {
      background: #dcfce7;
      color: #166534;
    }

    .badge.watch {
      background: #e0f2fe;
      color: #075985;
    }

    .badge.neutral {
      background: #f1f5f9;
      color: #334155;
    }

    .badge.risk {
      background: #fee2e2;
      color: #991b1b;
    }

    .reasons {
      margin: 0;
      padding-left: 18px;
      color: #475569;
    }

    .small {
      font-size: 13px;
    }

    @media (max-width: 900px) {
      .metrics {
        grid-template-columns: 1fr;
      }

      table {
        font-size: 13px;
      }
    }
  </style>
</head>
<body>
  <header>
    <h1>Сигналы рынка</h1>
    <nav>
      <a href="/dashboard">← Рынок</a> ·
      <a href="/signals/history">История сигналов</a> ·\n      <a href="/signals/models/compare">Model Lab</a> ·
      <a href="/signals/backtest">Backtest</a> ·
      <a href="/ai/report/demo">AI Report</a> ·
      <a href="/portfolio/construct/demo">Конструктор портфеля</a> ·
      <a href="/ai/reports/dashboard">История отчётов</a>
    </nav>
  </header>

  <main>
    <div id="activeModel" class="muted small" style="margin: 10px 0 0;">
      Активная модель: —
    </div>
<section class="card">
      <h2>Сводка</h2>
      <p class="muted" id="status">Загружаю сигналы...</p>

      <div class="metrics">
        <div class="metric">
          <div class="label">Всего</div>
          <div class="value" id="totalSignals">—</div>
        </div>
        <div class="metric">
          <div class="label">Кандидаты на покупку</div>
          <div class="value good" id="buySignals">—</div>
        </div>
        <div class="metric">
          <div class="label">Наблюдать</div>
          <div class="value" id="watchSignals">—</div>
        </div>
        <div class="metric">
          <div class="label">Риск снижения</div>
          <div class="value bad" id="riskSignals">—</div>
        </div>
      </div>

      <p style="margin-top:18px;">
        <label class="small muted" style="display:inline-flex; flex-direction:column; gap:6px; margin-right:10px; vertical-align:top;">
          Модель сигналов
          <select id="modelVersion" onchange="loadSignals()" style="height:40px; border:1px solid #d6dee8; border-radius:10px; padding:0 10px; min-width:260px;">
            <option value="tech_v1_sma_momentum">production · tech_v1_sma_momentum</option>
            <option value="tech_v2_rsi_atr">lab · tech_v2_rsi_atr</option>
            <option value="tech_v3_v1_atr_risk">lab · tech_v3_v1_atr_risk</option>
          </select>
        </label>
        <button id="filterAll" class="button active" onclick="setFilter('')">Все</button>
        <button id="filterBuy" class="button secondary" onclick="setFilter('buy_watch')">Кандидаты на покупку</button>
        <button id="filterWatch" class="button secondary" onclick="setFilter('hold_watch')">Нейтрально</button>
        <button id="filterRisk" class="button secondary" onclick="setFilter('risk_sell_watch')">Риск снижения</button>
        <button class="button secondary" onclick="loadSignals()">Обновить</button>
        <button class="button secondary" onclick="saveSignalSnapshot()">Сохранить snapshot</button>
        <a class="button secondary" href="/signals/history">История сигналов</a>
      </p>
    </section>

    <section class="card">
      <h2>Таблица сигналов</h2>

      <table>
        <thead>
          <tr>
            <th>Тикер</th>
            <th>Цена</th>
            <th>Изм.</th>
            <th>Сигнал</th>
            <th>Уверенность</th>
            <th>Риск</th>
            <th>Вход</th>
            <th>Цель</th>
            <th>Стоп</th>
            <th>Горизонт</th>
            <th>Факторы</th>
          </tr>
        </thead>
        <tbody id="signalsRows">
          <tr><td colspan="11">Загрузка...</td></tr>
        </tbody>
      </table>
    </section>
  </main>

  <script>
    let currentFilter = "";

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

    function signalBadgeClass(action) {
      if (action === "buy_watch") return "badge buy";
      if (action === "watch_buy") return "badge watch";
      if (action === "risk_sell_watch") return "badge risk";
      return "badge neutral";
    }

    function updateFilterButtons() {
      const map = {
        "": "filterAll",
        "buy_watch": "filterBuy",
        "hold_watch": "filterWatch",
        "risk_sell_watch": "filterRisk"
      };

      Object.entries(map).forEach(([filter, id]) => {
        const el = document.getElementById(id);
        if (!el) return;

        if (filter === currentFilter) {
          el.classList.add("active");
          el.classList.remove("secondary");
        } else {
          el.classList.remove("active");
          el.classList.add("secondary");
        }
      });
    }

    function getSignalsUrl() {
      const params = new URLSearchParams();
      const modelVersion = document.getElementById("modelVersion")?.value || "tech_v1_sma_momentum";
      params.set("model_version", modelVersion);
      params.set("limit", "100");
      params.set("candles_limit", "120");

      if (currentFilter) {
        params.set("action", currentFilter);
      }

      return "/signals/data?" + params.toString();
    }

    function setFilter(filter) {
      currentFilter = filter;
      loadSignals();
    }

    function renderSignals(data) {
      const summary = data.summary || {};
      const rows = data.rows || [];

      setText("totalSignals", summary.total);
      setText("buySignals", summary.buy_watch);
      setText("watchSignals", summary.watch_buy);
      setText("riskSignals", summary.risk_sell_watch);

      const tbody = document.getElementById("signalsRows");

      if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="11" class="muted">По выбранному фильтру сигналов нет.</td></tr>';
        return;
      }

      tbody.innerHTML = rows.map(row => {
        const signal = row.signal || {};
        const reasons = signal.reasons || [];

        return `
          <tr>
            <td>
              <a href="${escapeHtml(row.ticker_url)}">${escapeHtml(row.ticker)}</a>
              <div class="muted small">${escapeHtml(row.sector || "")}</div>
            </td>
            <td><b>${formatNumber(row.price)}</b></td>
            <td class="${valueClass(row.change_pct)}">${formatPct(row.change_pct)}</td>
            <td>
              <span class="${signalBadgeClass(signal.action)}">${escapeHtml(signal.label || signal.action || "—")}</span>
              <div class="muted small">${escapeHtml((row.technical || {}).trend || "")}</div>
            </td>
            <td><b>${signal.confidence_pct ? signal.confidence_pct + "%" : "—"}</b></td>
            <td>${escapeHtml(signal.risk_level || "—")}</td>
            <td>${formatNumber(signal.entry_price)}</td>
            <td>${formatNumber(signal.target_price)}</td>
            <td>${formatNumber(signal.stop_loss)}</td>
            <td>${escapeHtml(signal.horizon || "—")}</td>
            <td>
              <ul class="reasons">
                ${reasons.slice(0, 3).map(reason => `<li>${escapeHtml(reason)}</li>`).join("")}
              </ul>
            </td>
          </tr>
        `;
      }).join("");
    }

    async function loadSignals() {
      updateFilterButtons();
      setText("status", "Загружаю сигналы...");

      const response = await fetch(getSignalsUrl());

      if (!response.ok) {
        throw new Error("HTTP " + response.status + ": " + await response.text());
      }

      const data = await response.json();

      const activeModel = document.getElementById("activeModel");
      if (activeModel) {
        const model = data?.model_version || payload?.model_version || document.getElementById("modelVersion")?.value || "—";
        activeModel.textContent = `Активная модель: ${model}`;
      }
      renderSignals(data);

      const now = new Date().toLocaleTimeString("ru-RU");
      setText("status", "Сигналы обновлены: " + now + ".");
    }

    async function saveSignalSnapshot() {
      setText("status", "Сохраняю snapshot сигналов...");

      const response = await fetch("/signals/snapshot?limit=100&candles_limit=120", {
        method: "POST"
      });

      if (!response.ok) {
        throw new Error("HTTP " + response.status + ": " + await response.text());
      }

      const data = await response.json();
      setText("status", "Snapshot сохранён. Сигналов: " + data.saved_count + ".");
    }

    window.setFilter = setFilter;
    window.loadSignals = loadSignals;
    window.saveSignalSnapshot = saveSignalSnapshot;

    loadSignals().catch(error => {
      setText("status", "Ошибка загрузки: " + error.message);
    });
  </script>
</body>
</html>"""
