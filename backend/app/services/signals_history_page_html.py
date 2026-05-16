from __future__ import annotations


def build_signals_history_page_html() -> str:
    return """<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <title>История сигналов · AI Аналитик рынка РФ</title>
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
    }

    .badge.buy { background: #dcfce7; color: #166534; }
    .badge.watch { background: #e0f2fe; color: #075985; }
    .badge.risk { background: #fee2e2; color: #991b1b; }

    @media (max-width: 900px) {
      .metrics { grid-template-columns: 1fr; }
      table { font-size: 13px; }
    }
  </style>
</head>
<body>
  <header>
    <h1>История сигналов</h1>
    <nav>
      <a href="/dashboard">← Рынок</a> ·
      <a href="/signals">Сигналы</a> ·
      <a href="/signals/evaluation">Оценка сигналов</a> ·
      <a href="/signals/backtest">Backtest</a> ·
      <a href="/ai/report/demo">AI Report</a>
    </nav>
  </header>

  <main>
    <section class="card">
      <h2>Сводка</h2>
      <p class="muted" id="status">Загружаю историю...</p>

      <div class="metrics">
        <div class="metric">
          <div class="label">Всего snapshot-сигналов</div>
          <div class="value" id="totalSignals">—</div>
        </div>
        <div class="metric">
          <div class="label">Кандидаты на покупку</div>
          <div class="value good" id="buySignals">—</div>
        </div>
        <div class="metric">
          <div class="label">Нейтрально</div>
          <div class="value" id="neutralSignals">—</div>
        </div>
        <div class="metric">
          <div class="label">Риск снижения</div>
          <div class="value bad" id="riskSignals">—</div>
        </div>
      </div>

      <p style="margin-top:18px;">
        <label class="small muted" style="display:inline-flex; flex-direction:column; gap:6px; margin-right:10px; vertical-align:top;">
          Модель сигналов
          <select id="modelVersion" onchange="loadHistory()" style="height:40px; border:1px solid #d6dee8; border-radius:10px; padding:0 10px; min-width:260px;">
            <option value="">Все модели</option>
            <option value="tech_v1_sma_momentum">production · tech_v1_sma_momentum</option>
            <option value="tech_v2_rsi_atr">lab · tech_v2_rsi_atr</option>
            <option value="tech_v3_v1_atr_risk">lab · tech_v3_v1_atr_risk</option>
            <option value="tech_v4_quality_rr">lab · tech_v4_quality_rr</option>
          </select>
        </label>
        <button class="button" onclick="saveSnapshot()">Сохранить текущие сигналы</button>
        <button class="button secondary" onclick="loadHistory()">Обновить историю</button>
        <a id="jsonLink" class="button secondary" href="/signals/history.json">JSON</a>
        <a class="button secondary" href="/signals/evaluation">Оценка сигналов</a>
        <a class="button secondary" href="/signals/backtest">Backtest</a>
      </p>
    </section>

    <section class="card">
      <h2>Сохранённые сигналы</h2>

      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Создан</th>
            <th>Тикер</th>
            <th>Модель</th>
            <th>Цена</th>
            <th>Изм.</th>
            <th>Сигнал</th>
            <th>Уверенность</th>
            <th>Риск</th>
            <th>Вход</th>
            <th>Цель</th>
            <th>Стоп</th>
            <th>Горизонт</th>
          </tr>
        </thead>
        <tbody id="historyRows">
          <tr><td colspan="12">Загрузка...</td></tr>
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

    function signalBadgeClass(action) {
      if (action === "buy_watch") return "badge buy";
      if (action === "risk_sell_watch") return "badge risk";
      if (action === "watch_buy") return "badge watch";
      return "badge";
    }

    function renderHistory(data) {
      const summary = data.summary || {};
      const rows = data.rows || [];

      setText("totalSignals", summary.total);
      setText("buySignals", summary.buy_watch);
      setText("neutralSignals", summary.hold_watch);
      setText("riskSignals", summary.risk_sell_watch);

      const tbody = document.getElementById("historyRows");

      if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="13" class="muted">История сигналов пока пустая.</td></tr>';
        return;
      }

      tbody.innerHTML = rows.map(row => `
        <tr>
          <td>${row.id}</td>
          <td>${escapeHtml(row.created_at || "—")}</td>
          <td><a href="${escapeHtml(row.ticker_url)}">${escapeHtml(row.ticker)}</a></td>
          <td class="muted small">${escapeHtml(row.model_version || "—")}</td>
          <td><b>${formatNumber(row.price)}</b></td>
          <td class="${valueClass(row.change_pct)}">${formatPct(row.change_pct)}</td>
          <td><span class="${signalBadgeClass(row.action)}">${escapeHtml(row.label || row.action)}</span></td>
          <td><b>${row.confidence_pct ? row.confidence_pct + "%" : "—"}</b></td>
          <td>${escapeHtml(row.risk_level || "—")}</td>
          <td>${formatNumber(row.entry_price)}</td>
          <td>${formatNumber(row.target_price)}</td>
          <td>${formatNumber(row.stop_loss)}</td>
          <td>${escapeHtml(row.horizon || "—")}</td>
        </tr>
      `).join("");
    }

    async function loadHistory() {
      setText("status", "Загружаю историю...");

      const modelVersion = document.getElementById("modelVersion")?.value || "";
      const params = new URLSearchParams();
      params.set("limit", "200");

      if (modelVersion) {
        params.set("model_version", modelVersion);
      }

      const jsonLink = document.getElementById("jsonLink");
      if (jsonLink) {
        jsonLink.href = `/signals/history.json?${params.toString()}`;
      }

      const response = await fetch(`/signals/history.json?${params.toString()}`);

      if (!response.ok) {
        throw new Error("HTTP " + response.status + ": " + await response.text());
      }

      const data = await response.json();
      renderHistory(data);

      const now = new Date().toLocaleTimeString("ru-RU");
      setText("status", "История обновлена: " + now + ".");
    }

    async function saveSnapshot() {
      setText("status", "Сохраняю текущие сигналы...");

      const modelVersion = document.getElementById("modelVersion")?.value || "";
      const params = new URLSearchParams();
      params.set("limit", "100");
      params.set("candles_limit", "120");

      if (modelVersion) {
        params.set("model_version", modelVersion);
      }

      const response = await fetch(`/signals/snapshot?${params.toString()}`, {
        method: "POST"
      });

      if (!response.ok) {
        throw new Error("HTTP " + response.status + ": " + await response.text());
      }

      const data = await response.json();
      setText("status", "Сохранено сигналов: " + data.saved_count + ".");
      await loadHistory();
    }

    window.loadHistory = loadHistory;
    window.saveSnapshot = saveSnapshot;

    loadHistory().catch(error => {
      setText("status", "Ошибка загрузки: " + error.message);
    });
  </script>
</body>
</html>"""
