from __future__ import annotations


def build_portfolio_construct_history_page_html() -> str:
    return """<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <title>История конструктора портфеля</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root {
      --bg: #f6f7fb;
      --card: #ffffff;
      --text: #111827;
      --muted: #6b7280;
      --border: #e5e7eb;
      --blue: #2563eb;
      --green: #15803d;
      --red: #b91c1c;
      --amber: #b45309;
      --shadow: 0 12px 30px rgba(15, 23, 42, 0.08);
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
    }

    .wrap {
      max-width: 1320px;
      margin: 0 auto;
      padding: 28px;
    }

    .top {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: flex-start;
      margin-bottom: 18px;
    }

    h1 {
      margin: 0 0 8px;
      font-size: 30px;
      letter-spacing: -0.03em;
    }

    h2 {
      margin: 0 0 14px;
      font-size: 20px;
    }

    a {
      color: var(--blue);
      text-decoration: none;
    }

    .muted {
      color: var(--muted);
    }

    .small {
      font-size: 13px;
    }

    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 20px;
      box-shadow: var(--shadow);
      padding: 20px;
      margin-bottom: 18px;
    }

    .nav {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      justify-content: flex-end;
    }

    .button {
      border: 0;
      border-radius: 12px;
      background: var(--blue);
      color: white;
      padding: 10px 14px;
      font-weight: 700;
      cursor: pointer;
      display: inline-block;
    }

    .button.secondary {
      background: #e5e7eb;
      color: #111827;
    }

    .controls {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: end;
    }

    .control {
      display: grid;
      gap: 6px;
    }

    input {
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 10px 12px;
      min-width: 120px;
      background: #fff;
      font-size: 14px;
    }

    .metrics {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 12px;
    }

    .metric {
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 14px;
      background: #fafafa;
    }

    .label {
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 6px;
    }

    .value {
      font-size: 22px;
      font-weight: 800;
      letter-spacing: -0.02em;
    }

    .good {
      color: var(--green);
    }

    .bad {
      color: var(--red);
    }

    .warn {
      color: var(--amber);
    }

    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }

    th, td {
      padding: 11px 10px;
      border-bottom: 1px solid var(--border);
      text-align: left;
      vertical-align: top;
    }

    th {
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      background: #fafafa;
      position: sticky;
      top: 0;
      z-index: 1;
    }

    .badge {
      display: inline-flex;
      border-radius: 999px;
      padding: 4px 9px;
      background: #eef2ff;
      color: #3730a3;
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }

    .badge.good {
      background: #dcfce7;
      color: #166534;
    }

    .badge.warn {
      background: #fef3c7;
      color: #92400e;
    }

    .badge.bad {
      background: #fee2e2;
      color: #991b1b;
    }

    .table-wrap {
      overflow-x: auto;
    }

    @media (max-width: 900px) {
      .top {
        display: block;
      }

      .nav {
        justify-content: flex-start;
        margin-top: 12px;
      }

      .metrics {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <div>
        <h1>История конструктора портфеля</h1>
        <div class="muted">
          Сохранённые snapshot-ы: состав портфеля, режим отбора, risk/reward и вывод на момент расчёта.
        </div>
      </div>

      <div class="nav">
        <a class="button secondary" href="/dashboard">Рынок</a>
        <a class="button secondary" href="/portfolio/construct/demo">Конструктор</a>
        <a class="button secondary" href="/portfolio/construct/compare">Сравнить последние</a>
        <a class="button secondary" href="/signals">Сигналы</a>
        <a class="button secondary" href="/signals/champion">Champion</a>
      </div>
    </div>

    <section class="card">
      <h2>Фильтр</h2>

      <div class="controls">
        <label class="control">
          <span class="small muted">Лимит</span>
          <input id="limit" type="number" min="1" max="500" value="50" />
        </label>

        <button class="button" onclick="loadSnapshots()">Обновить</button>
        <a id="jsonLink" class="button secondary" href="/portfolio/construct/snapshots?limit=50" target="_blank">JSON</a>
      </div>

      <p id="status" class="muted small" style="margin-bottom:0;">Готово.</p>
    </section>

    <section class="card">
      <h2>Сводка</h2>

      <div class="metrics">
        <div class="metric">
          <div class="label">Snapshot-ов</div>
          <div class="value" id="snapshotsTotal">—</div>
        </div>

        <div class="metric">
          <div class="label">Последний risk/reward</div>
          <div class="value" id="latestRiskReward">—</div>
        </div>

        <div class="metric">
          <div class="label">Последний кэш</div>
          <div class="value" id="latestCash">—</div>
        </div>

        <div class="metric">
          <div class="label">Позиций в последнем</div>
          <div class="value" id="latestPositions">—</div>
        </div>

        <div class="metric">
          <div class="label">Модель</div>
          <div class="value" id="latestModel">—</div>
        </div>
      </div>
    </section>

    <section class="card">
      <h2>Snapshot-ы</h2>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Дата</th>
              <th>Модель</th>
              <th>Профиль</th>
              <th>Горизонт</th>
              <th>Качество</th>
              <th>Позиций</th>
              <th>Кэш</th>
              <th>Risk/reward</th>
              <th>Вывод</th>
              <th>Ссылки</th>
            </tr>
          </thead>
          <tbody id="snapshotRows">
            <tr><td colspan="11" class="muted">Пока нет данных.</td></tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>

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

    function formatMoney(value) {
      if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
      return formatNumber(value, 2) + " ₽";
    }

    function formatPct(value) {
      if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
      return formatNumber(value, 2) + "%";
    }

    function setText(id, value) {
      document.getElementById(id).textContent =
        value === null || value === undefined || value === "" ? "—" : value;
    }

    function rrClass(value) {
      const n = Number(value);
      if (Number.isNaN(n)) return "";
      if (n < 0.8) return "bad";
      if (n < 1.2) return "warn";
      return "good";
    }

    function rrBadge(summary) {
      const ratio = summary.risk_reward_ratio;
      const label = summary.risk_reward_label || "нет данных";
      const cls = rrClass(ratio);

      if (ratio === null || ratio === undefined) {
        return `<span class="badge">${escapeHtml(label)}</span>`;
      }

      return `<span class="badge ${cls}">${formatNumber(ratio, 2)} · ${escapeHtml(label)}</span>`;
    }

    function render(data) {
      const rows = data.rows || [];
      const tbody = document.getElementById("snapshotRows");

      setText("snapshotsTotal", data.total ?? rows.length);

      if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="11" class="muted">Snapshot-ов пока нет.</td></tr>';
        setText("latestRiskReward", "—");
        setText("latestCash", "—");
        setText("latestPositions", "—");
        setText("latestModel", "—");
        return;
      }

      const latest = rows[0] || {};
      const latestSummary = latest.summary || {};

      setText(
        "latestRiskReward",
        latestSummary.risk_reward_ratio === null || latestSummary.risk_reward_ratio === undefined
          ? latestSummary.risk_reward_label
          : `${formatNumber(latestSummary.risk_reward_ratio, 2)} · ${latestSummary.risk_reward_label || ""}`
      );
      document.getElementById("latestRiskReward").className = "value " + rrClass(latestSummary.risk_reward_ratio);

      setText("latestCash", `${formatMoney(latestSummary.cash)} · ${formatPct(latestSummary.cash_pct)}`);
      setText("latestPositions", latestSummary.positions_count ?? latest.positions_count);
      setText("latestModel", latest.model_version);

      tbody.innerHTML = rows.map(row => {
        const summary = row.summary || {};
        const conclusion = summary.portfolio_conclusion || "—";

        return `
          <tr>
            <td><b>#${row.id}</b></td>
            <td>
              ${escapeHtml(row.created_at || "—")}
            </td>
            <td>${escapeHtml(row.model_version || "—")}</td>
            <td>${escapeHtml(row.risk_profile || "—")}</td>
            <td>${escapeHtml(row.horizon || "—")}</td>
            <td>${escapeHtml(row.quality_mode || "—")}</td>
            <td><b>${summary.positions_count ?? row.positions_count ?? "—"}</b></td>
            <td>
              <b>${formatMoney(summary.cash)}</b>
              <div class="muted small">${formatPct(summary.cash_pct)}</div>
            </td>
            <td>${rrBadge(summary)}</td>
            <td>
              <div style="max-width:420px;">${escapeHtml(conclusion)}</div>
            </td>
            <td>
              <a href="/portfolio/construct/snapshots/${row.id}/view">Открыть</a> ·
              <a href="${escapeHtml(row.detail_url)}" target="_blank">JSON</a>
            </td>
          </tr>
        `;
      }).join("");
    }

    async function loadSnapshots() {
      setText("status", "Загружаю snapshot-ы...");

      const limit = document.getElementById("limit").value || "50";
      const url = `/portfolio/construct/snapshots?limit=${encodeURIComponent(limit)}`;
      document.getElementById("jsonLink").href = url;

      const response = await fetch(url);

      if (!response.ok) {
        throw new Error("HTTP " + response.status + ": " + await response.text());
      }

      const data = await response.json();
      render(data);

      const now = new Date().toLocaleTimeString("ru-RU");
      setText("status", "Обновлено: " + now + ".");
    }

    window.loadSnapshots = loadSnapshots;

    loadSnapshots().catch(error => {
      setText("status", "Ошибка: " + error.message);
    });
  </script>
</body>
</html>"""
