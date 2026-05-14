from __future__ import annotations


def build_ai_report_trends_html() -> str:
    return """<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <title>Динамика AI Report</title>
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
      color: white;
      padding: 42px 32px;
    }

    header h1 {
      margin: 0 0 14px;
      font-size: 34px;
    }

    header a {
      color: #93c5fd;
      text-decoration: none;
      font-weight: 700;
    }

    main {
      padding: 28px 32px;
    }

    .card {
      background: white;
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
      grid-template-columns: repeat(3, minmax(180px, 1fr));
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
      font-weight: 700;
    }

    .metric .value {
      font-size: 24px;
      font-weight: 800;
      margin-top: 6px;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 14px;
    }

    th, td {
      padding: 11px 10px;
      border-bottom: 1px solid #e5e7eb;
      text-align: left;
      vertical-align: top;
    }

    th {
      color: #64748b;
      font-size: 13px;
    }

    a {
      color: #2563eb;
      font-weight: 700;
      text-decoration: none;
    }

    .good {
      color: #15803d;
      font-weight: 800;
    }

    .bad {
      color: #dc2626;
      font-weight: 800;
    }

    .chart-wrap {
      overflow-x: auto;
    }

    svg {
      width: 100%;
      min-width: 720px;
      height: 280px;
      background: #f8fafc;
      border-radius: 16px;
      margin-top: 14px;
    }

    .button-row {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-top: 14px;
    }

    .button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 38px;
      border-radius: 10px;
      padding: 10px 14px;
      background: #2563eb;
      color: #ffffff;
      text-decoration: none;
      font-weight: 800;
      border: 0;
      cursor: pointer;
    }

    .button.secondary {
      background: #334155;
    }
  </style>
</head>
<body>
  <header>
    <h1>Динамика AI Report</h1>
    <nav>
      <a href="/dashboard">← Рынок</a> ·
      <a href="/ai/reports/dashboard">История отчётов</a> ·
      <a href="/ai/report/compare/latest">Сравнить последние</a>
    </nav>
  </header>

  <main>
    <section class="card">
      <h2>Сводка</h2>
      <p class="muted" id="status">Загружаю историю...</p>

      <div class="metrics">
        <div class="metric">
          <div class="label">Последняя стоимость</div>
          <div class="value" id="lastValue">—</div>
        </div>
        <div class="metric">
          <div class="label">Изменение от первого отчёта</div>
          <div class="value" id="totalDelta">—</div>
        </div>
        <div class="metric">
          <div class="label">Последний дневной PnL</div>
          <div class="value" id="lastPnl">—</div>
        </div>
      </div>

      <div class="button-row">
        <a class="button" href="/system/dashboard">Обновить данные + отчёт</a>
        <a class="button secondary" href="/ai/report/demo">Редактор AI Report</a>
        <a class="button secondary" href="/ai/reports/trends.csv">Скачать CSV</a>
      </div>
    </section>

    <section class="card">
      <h2>График стоимости портфеля</h2>
      <div class="chart-wrap">
        <svg id="chart" viewBox="0 0 900 280" preserveAspectRatio="none"></svg>
      </div>
    </section>

    <section class="card">
      <h2>История метрик</h2>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Создан</th>
            <th>Рынок</th>
            <th>Стоимость</th>
            <th>Дневной PnL</th>
            <th>Действия</th>
          </tr>
        </thead>
        <tbody id="rows">
          <tr><td colspan="6">Загрузка...</td></tr>
        </tbody>
      </table>
    </section>
  </main>

  <script>
    function formatRub(value) {
      if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
      return Number(value).toLocaleString("ru-RU", {
        minimumFractionDigits: 1,
        maximumFractionDigits: 1
      }) + " руб.";
    }

    function formatPct(value) {
      if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
      return Number(value).toLocaleString("ru-RU", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      }) + "%";
    }

    function pnlClass(value) {
      const n = Number(value);
      if (Number.isNaN(n) || n === 0) return "";
      return n > 0 ? "good" : "bad";
    }

    function drawChart(items) {
      const svg = document.getElementById("chart");
      svg.innerHTML = "";

      const data = items
        .slice()
        .reverse()
        .filter(item => item.portfolio_value !== null && item.portfolio_value !== undefined);

      if (data.length < 2) {
        svg.innerHTML = '<text x="30" y="50" fill="#64748b">Недостаточно данных для графика</text>';
        return;
      }

      const width = 900;
      const height = 280;
      const pad = 36;

      const values = data.map(item => Number(item.portfolio_value));
      const min = Math.min(...values);
      const max = Math.max(...values);
      const range = max - min || 1;

      const points = data.map((item, index) => {
        const x = pad + index * ((width - pad * 2) / (data.length - 1));
        const y = height - pad - ((Number(item.portfolio_value) - min) / range) * (height - pad * 2);
        return {x, y, item};
      });

      const polyline = points.map(p => `${p.x},${p.y}`).join(" ");

      svg.innerHTML = `
        <line x1="${pad}" y1="${pad}" x2="${pad}" y2="${height - pad}" stroke="#cbd5e1" />
        <line x1="${pad}" y1="${height - pad}" x2="${width - pad}" y2="${height - pad}" stroke="#cbd5e1" />

        <text x="${pad}" y="22" fill="#64748b" font-size="12">${formatRub(max)}</text>
        <text x="${pad}" y="${height - 10}" fill="#64748b" font-size="12">${formatRub(min)}</text>

        <polyline points="${polyline}" fill="none" stroke="#2563eb" stroke-width="4" />

        ${points.map(p => `
          <circle cx="${p.x}" cy="${p.y}" r="5" fill="#2563eb">
            <title>ID ${p.item.id}: ${formatRub(p.item.portfolio_value)}</title>
          </circle>
        `).join("")}
      `;
    }

    async function loadTrends() {
      const response = await fetch("/ai/reports/trends.json?limit=100");
      if (!response.ok) {
        throw new Error("HTTP " + response.status);
      }

      const data = await response.json();

      if (!data.length) {
        document.getElementById("status").textContent = "Сохранённых отчётов пока нет.";
        document.getElementById("rows").innerHTML =
          "<tr><td colspan='6'>Пока нет данных.</td></tr>";
        return;
      }

      const latest = data[0];
      const oldest = data[data.length - 1];

      document.getElementById("status").textContent =
        "Отчётов в выборке: " + data.length;

      document.getElementById("lastValue").textContent =
        formatRub(latest.portfolio_value);

      const totalDelta =
        latest.portfolio_value !== null && oldest.portfolio_value !== null
          ? latest.portfolio_value - oldest.portfolio_value
          : null;

      document.getElementById("totalDelta").textContent = formatRub(totalDelta);
      document.getElementById("totalDelta").className =
        "value " + pnlClass(totalDelta);

      document.getElementById("lastPnl").textContent =
        formatRub(latest.daily_pnl_abs) + " / " + formatPct(latest.daily_pnl_pct);
      document.getElementById("lastPnl").className =
        "value " + pnlClass(latest.daily_pnl_abs);

      document.getElementById("rows").innerHTML = data.map(row => `
        <tr>
          <td>${row.id}</td>
          <td>${row.created_at || "—"}</td>
          <td>${row.market_mood || "—"}</td>
          <td>${formatRub(row.portfolio_value)}</td>
          <td class="${pnlClass(row.daily_pnl_abs)}">
            ${formatRub(row.daily_pnl_abs)} / ${formatPct(row.daily_pnl_pct)}
          </td>
          <td>
            <a href="${row.view_url}">Открыть</a> ·
            <a href="${row.markdown_url}">Markdown</a> ·
            <a href="${row.json_url}">JSON</a>
          </td>
        </tr>
      `).join("");

      drawChart(data);
    }

    loadTrends().catch(error => {
      console.error(error);
      document.getElementById("status").textContent =
        "Ошибка загрузки: " + error.message;
    });
  </script>
</body>
</html>
"""
