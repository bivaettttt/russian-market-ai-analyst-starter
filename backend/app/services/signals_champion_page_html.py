from __future__ import annotations


def build_signal_champion_page_html() -> str:
    return """<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <title>Champion Model · Russian Market AI Analyst</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root {
      --bg: #f4f7fb;
      --card: #ffffff;
      --text: #172033;
      --muted: #6b7280;
      --border: #dbe3ef;
      --good: #057a55;
      --bad: #c2410c;
      --warn: #a16207;
      --blue: #2563eb;
      --shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
    }

    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
    }

    .wrap {
      max-width: 1240px;
      margin: 0 auto;
      padding: 28px;
    }

    .top {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 18px;
      margin-bottom: 18px;
    }

    h1 {
      margin: 0 0 8px;
      font-size: 32px;
      letter-spacing: -0.03em;
    }

    h2 {
      margin: 0 0 16px;
      font-size: 20px;
    }

    .muted {
      color: var(--muted);
    }

    .small {
      font-size: 12px;
    }

    .nav {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }

    .button {
      border: 0;
      border-radius: 12px;
      padding: 10px 14px;
      background: var(--blue);
      color: white;
      text-decoration: none;
      font-weight: 700;
      cursor: pointer;
      display: inline-block;
    }

    .button.secondary {
      background: white;
      color: var(--text);
      border: 1px solid var(--border);
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
      margin-bottom: 14px;
    }

    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 18px;
      box-shadow: var(--shadow);
      margin-bottom: 14px;
    }

    .metric {
      background: #f8fafc;
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 14px;
    }

    .label {
      font-size: 12px;
      color: var(--muted);
      margin-bottom: 6px;
    }

    .value {
      font-size: 26px;
      font-weight: 800;
      letter-spacing: -0.03em;
    }

    .good { color: var(--good); }
    .bad { color: var(--bad); }
    .warn { color: var(--warn); }

    .badge {
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 5px 9px;
      font-size: 12px;
      font-weight: 800;
      background: #eef2ff;
      color: #3730a3;
      white-space: nowrap;
    }

    .badge.production {
      background: #dcfce7;
      color: #166534;
    }

    .badge.lab {
      background: #fef3c7;
      color: #92400e;
    }

    .badge.ok {
      background: #dcfce7;
      color: #166534;
    }

    .badge.warn {
      background: #ffedd5;
      color: #9a3412;
    }

    input, select {
      height: 40px;
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 0 10px;
      min-width: 160px;
      background: white;
      color: var(--text);
    }

    .controls {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      align-items: end;
    }

    .control {
      display: inline-flex;
      flex-direction: column;
      gap: 6px;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      overflow: hidden;
    }

    th, td {
      padding: 12px 10px;
      border-bottom: 1px solid var(--border);
      text-align: left;
      vertical-align: top;
      font-size: 14px;
    }

    th {
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      background: #f8fafc;
    }

    tr:last-child td {
      border-bottom: 0;
    }

    .desc {
      max-width: 520px;
      line-height: 1.45;
    }

    @media (max-width: 900px) {
      .top {
        flex-direction: column;
      }

      .nav {
        justify-content: flex-start;
      }

      .grid {
        grid-template-columns: 1fr;
      }

      table {
        display: block;
        overflow-x: auto;
      }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <div>
        <h1>Champion Model</h1>
        <div class="muted">Production-модель, лабораторные версии и сравнение по backtest.</div>
      </div>

      <div class="nav">
        <a class="button secondary" href="/signals">Сигналы</a>
        <a class="button secondary" href="/signals/history">История</a>
        <a class="button secondary" href="/signals/evaluation">Оценка</a>
        <a class="button secondary" href="/signals/backtest">Backtest</a>
        <a class="button secondary" href="/signals/models/compare">Model Lab</a>
        <a class="button secondary" href="/signals/models/quality">Quality</a>
        <a class="button secondary" href="/portfolio/construct/demo">Конструктор портфеля</a>
      </div>
    </div>

    <section class="grid">
      <div class="metric">
        <div class="label">Production model</div>
        <div class="value" id="productionModel">—</div>
        <div class="muted small" id="productionKind">—</div>
      </div>

      <div class="metric">
        <div class="label">Winner по текущему compare</div>
        <div class="value" id="winnerModel">—</div>
        <div class="muted small" id="winnerScore">Score: —</div>
      </div>

      <div class="metric">
        <div class="label">Статус champion</div>
        <div class="value" id="championStatus">—</div>
        <div class="muted small" id="championHint">—</div>
      </div>
    </section>

    <section class="card">
      <h2>Параметры сравнения</h2>

      <div class="controls">
        <label class="control">
          <span class="small muted">Тикеры</span>
          <input id="tickers" value="SBER,GAZP,LKOH,PLZL,MOEX,VTBR" style="min-width:360px;" />
        </label>

        <label class="control">
          <span class="small muted">Limit</span>
          <input id="limit" type="number" min="1" max="2000" value="50" />
        </label>

        <label class="control">
          <span class="small muted">Future limit</span>
          <input id="futureLimit" type="number" min="1" max="120" value="20" />
        </label>

        <label class="control">
          <span class="small muted">Max points / ticker</span>
          <input id="maxPoints" type="number" min="1" max="300" value="10" />
        </label>

        <button class="button" onclick="loadChampion()">Обновить</button>
        <a id="compareJsonLink" class="button secondary" href="/signals/models/compare.json">Compare JSON</a>
        <a id="modelsJsonLink" class="button secondary" href="/signals/models">Models JSON</a>
      </div>

      <p class="muted small" id="status" style="margin-bottom:0;">Готово.</p>
    </section>

    <section class="card">
      <h2>Доступные модели</h2>

      <table>
        <thead>
          <tr>
            <th>Модель</th>
            <th>Статус</th>
            <th>Тип</th>
            <th>Описание</th>
          </tr>
        </thead>
        <tbody id="modelsRows">
          <tr><td colspan="4" class="muted">Загрузка...</td></tr>
        </tbody>
      </table>
    </section>

    <section class="card">
      <h2>Результаты compare</h2>

      <table>
        <thead>
          <tr>
            <th>Rank</th>
            <th>Модель</th>
            <th>Score</th>
            <th>Accuracy</th>
            <th>Avg strategy</th>
            <th>Actionable</th>
            <th>Всего</th>
            <th>Сигналы</th>
          </tr>
        </thead>
        <tbody id="compareRows">
          <tr><td colspan="8" class="muted">Загрузка...</td></tr>
        </tbody>
      </table>
    </section>
  </div>

  <script>
    let latestWinnerModelVersion = null;
    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function formatPct(value) {
      if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";

      return Number(value).toLocaleString("ru-RU", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      }) + "%";
    }

    function formatNumber(value, digits = 2) {
      if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";

      return Number(value).toLocaleString("ru-RU", {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits
      });
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

    function renderModels(data) {
      const rows = data.models || [];

      document.getElementById("modelsRows").innerHTML = rows.map(row => `
        <tr>
          <td>
            <b>${escapeHtml(row.model_version)}</b>
            ${row.is_production ? '<div class="muted small">current production</div>' : ''}
          </td>
          <td><span class="badge ${row.status === "production" ? "production" : "lab"}">${escapeHtml(row.status)}</span></td>
          <td>${escapeHtml(row.kind || "—")}</td>
          <td class="desc">${escapeHtml(row.description || "—")}</td>
        </tr>
      `).join("");

      const production = data.production_model || {};
      setText("productionModel", production.model_version);
      setText("productionKind", `${production.status || "—"} · ${production.kind || "—"}`);
    }

    function renderCompare(data, productionModel) {
      const rows = data.rows || [];
      const winner = data.winner || {};
      const winnerSummary = winner.summary || {};

      setText("winnerModel", winner.model_version);
      setText("winnerScore", `Score: ${formatNumber(winner.score)}`);

      const isProductionWinner = winner.model_version && winner.model_version === productionModel;

      const championStatus = document.getElementById("championStatus");
      const championHint = document.getElementById("championHint");

      if (!winner.model_version) {
        championStatus.textContent = "Нет данных";
        championStatus.className = "value warn";
        championHint.textContent = "Недостаточно строк для compare.";
      } else if (isProductionWinner) {
        championStatus.textContent = "OK";
        championStatus.className = "value good";
        championHint.textContent = "Production совпадает с winner по выбранному backtest.";
      } else {
        championStatus.textContent = "Review";
        championStatus.className = "value warn";
        championHint.textContent = `Winner сейчас ${winner.model_version}, но production — ${productionModel}.`;
      }

      document.getElementById("compareRows").innerHTML = rows.map((row, index) => {
        const summary = row.summary || {};
        const isWinner = row.model_version === winner.model_version;
        const isProduction = row.model_version === productionModel;

        return `
          <tr>
            <td>${index + 1}</td>
            <td>
              <b>${escapeHtml(row.model_version)}</b>
              <div>
                ${isWinner ? '<span class="badge ok">winner</span>' : ''}
                ${isProduction ? '<span class="badge production">production</span>' : ''}
              </div>
            </td>
            <td><b>${formatNumber(row.score)}</b></td>
            <td>${formatPct(summary.accuracy_pct)}</td>
            <td class="${valueClass(summary.avg_strategy_result_pct)}">${formatPct(summary.avg_strategy_result_pct)}</td>
            <td>${summary.actionable_count ?? "—"}</td>
            <td>${summary.total ?? "—"}</td>
            <td>
              <div class="small muted">buy: ${summary.buy_watch ?? 0}</div>
              <div class="small muted">hold: ${summary.hold_watch ?? 0}</div>
              <div class="small muted">risk: ${summary.risk_sell_watch ?? 0}</div>
            </td>
          </tr>
        `;
      }).join("");

      if (!rows.length) {
        document.getElementById("compareRows").innerHTML = '<tr><td colspan="8" class="muted">Нет данных compare.</td></tr>';
      }
    }

    function buildCompareParams() {
      const params = new URLSearchParams();

      params.set("tickers", document.getElementById("tickers").value || "SBER,GAZP,LKOH,PLZL");
      params.set("limit", document.getElementById("limit").value || "50");
      params.set("future_limit", document.getElementById("futureLimit").value || "20");
      params.set("max_points_per_ticker", document.getElementById("maxPoints").value || "10");

      return params;
    }

    async function loadChampion() {
      setText("status", "Загружаю champion dashboard...");

      const modelsResponse = await fetch("/signals/models");

      if (!modelsResponse.ok) {
        throw new Error("Models HTTP " + modelsResponse.status + ": " + await modelsResponse.text());
      }

      const modelsData = await modelsResponse.json();
      renderModels(modelsData);

      const productionModel = (modelsData.production_model || {}).model_version;
      const params = buildCompareParams();
      const compareUrl = `/signals/models/compare.json?${params.toString()}`;

      document.getElementById("compareJsonLink").href = compareUrl;

      const compareResponse = await fetch(compareUrl);

      if (!compareResponse.ok) {
        throw new Error("Compare HTTP " + compareResponse.status + ": " + await compareResponse.text());
      }

      const compareData = await compareResponse.json();
      latestWinnerModelVersion = (compareData.winner || {}).model_version || null;
      renderCompare(compareData, productionModel);

      const now = new Date().toLocaleTimeString("ru-RU");
      setText("status", "Обновлено: " + now + ".");
    }

    async function promoteWinner() {
      if (!latestWinnerModelVersion) {
        setText("status", "Нет winner-модели для promotion.");
        return;
      }

      const confirmed = confirm(`Сделать ${latestWinnerModelVersion} production-моделью?`);
      if (!confirmed) return;

      setText("status", "Переключаю production на " + latestWinnerModelVersion + "...");

      const response = await fetch(
        `/signals/models/production?model_version=${encodeURIComponent(latestWinnerModelVersion)}`,
        { method: "POST" }
      );

      if (!response.ok) {
        throw new Error("Promote HTTP " + response.status + ": " + await response.text());
      }

      await loadChampion();
      setText("status", "Production переключена на " + latestWinnerModelVersion + ".");
    }

    window.loadChampion = loadChampion;
    window.promoteWinner = promoteWinner;

    loadChampion().catch(error => {
      setText("status", "Ошибка: " + error.message);
    });
  </script>
</body>
</html>"""
