from __future__ import annotations


def build_portfolio_constructor_page_html() -> str:
    return """<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <title>Конструктор портфеля · Russian Market AI Analyst</title>
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

    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 18px;
      box-shadow: var(--shadow);
      margin-bottom: 14px;
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 14px;
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

    .badge.buy {
      background: #dcfce7;
      color: #166534;
    }

    .badge.risk {
      background: #ffedd5;
      color: #9a3412;
    }

    .notes {
      margin: 0;
      padding-left: 18px;
      line-height: 1.5;
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
        <h1>Конструктор портфеля</h1>
        <div class="muted">MVP: бюджет, риск-профиль, горизонт и текущие сигналы.</div>
      </div>

      <div class="nav">
        <a class="button secondary" href="/dashboard">Рынок</a>
        <a class="button secondary" href="/signals">Сигналы</a>
        <a class="button secondary" href="/signals/champion">Champion</a>
        <a class="button secondary" href="/portfolio/demo">Портфель</a>
      </div>
    </div>

    <section class="card">
      <h2>Параметры</h2>

      <div class="controls">
        <label class="control">
          <span class="small muted">Бюджет, ₽</span>
          <input id="budget" type="number" min="1000" value="100000" />
        </label>

        <label class="control">
          <span class="small muted">Профиль риска</span>
          <select id="riskProfile">
            <option value="conservative">Консервативный</option>
            <option value="balanced" selected>Сбалансированный</option>
            <option value="aggressive">Агрессивный</option>
          </select>
        </label>

        <label class="control">
          <span class="small muted">Горизонт</span>
          <select id="horizon">
            <option value="short">Краткосрочный</option>
            <option value="medium" selected>Среднесрочный</option>
            <option value="long">Долгосрочный</option>
          </select>
        </label>

        <label class="control">
          <span class="small muted">Качество отбора</span>
          <select id="qualityMode">
            <option value="loose">Мягкий</option>
            <option value="normal" selected>Обычный</option>
            <option value="strict">Строгий</option>
          </select>
        </label>

        <label class="control">
          <span class="small muted">Модель сигналов</span>
          <select id="modelVersion">
            <option value="">Текущая production</option>
            <option value="tech_v1_sma_momentum">tech_v1_sma_momentum</option>
            <option value="tech_v2_rsi_atr">tech_v2_rsi_atr</option>
            <option value="tech_v3_v1_atr_risk">tech_v3_v1_atr_risk</option>
          </select>
        </label>

        <label class="control">
          <span class="small muted">Тикеры, необязательно</span>
          <input id="tickers" placeholder="SBER,GAZP,LKOH" style="min-width:260px;" />
        </label>

        <button class="button" onclick="constructPortfolio()">Собрать портфель</button>
        <button class="button secondary" onclick="downloadPortfolioCsv()">Скачать CSV</button>
      </div>

      <p class="muted small" id="status" style="margin-bottom:0;">Готово.</p>
    </section>

    <section class="grid">
      <div class="metric">
        <div class="label">Модель</div>
        <div class="value" id="model">—</div>
      </div>

      <div class="metric">
        <div class="label">Инвестировано</div>
        <div class="value" id="invested">—</div>
      </div>

      <div class="metric">
        <div class="label">Кэш</div>
        <div class="value" id="cash">—</div>
      </div>

      <div class="metric">
        <div class="label">Риск портфеля</div>
        <div class="value" id="risk">—</div>
      </div>

      <div class="metric">
        <div class="label">Risk/reward</div>
        <div class="value" id="riskReward">—</div>
      </div>
    </section>

    <section class="card">
      <h2>Вывод</h2>
      <p id="portfolioConclusion" class="muted">Портфель ещё не собран.</p>
    </section>

    <section class="card">
      <h2>Позиции</h2>

      <table>
        <thead>
          <tr>
            <th>Тикер</th>
            <th>Цена</th>
            <th>Лот</th>
            <th>Лоты</th>
            <th>Кол-во</th>
            <th>Сумма</th>
            <th>Доля</th>
            <th>Сигнал</th>
            <th>Уверенность</th>
            <th>Цель</th>
            <th>Потенциал</th>
            <th>Стоп</th>
            <th>Риск</th>
            <th>Причины</th>
          </tr>
        </thead>
        <tbody id="positionsRows">
          <tr><td colspan="14" class="muted">Портфель ещё не собран.</td></tr>
        </tbody>
      </table>
    </section>

    <section class="card">
      <h2>Исключённые тикеры</h2>

      <table>
        <thead>
          <tr>
            <th>Тикер</th>
            <th>Сигнал</th>
            <th>Цена</th>
            <th>Score</th>
            <th>Причина</th>
          </tr>
        </thead>
        <tbody id="excludedRows">
          <tr><td colspan="5" class="muted">Пока нет данных.</td></tr>
        </tbody>
      </table>
    </section>

    <section class="card">
      <h2>Комментарии</h2>
      <ul class="notes" id="notes">
        <li class="muted">После расчёта здесь появятся ограничения и пояснения.</li>
      </ul>
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

    function signalBadgeClass(action) {
      if (action === "buy_watch") return "badge buy";
      if (action === "risk_sell_watch") return "badge risk";
      return "badge";
    }

    function render(data) {
      if (!data.ok) {
        setText("status", "Ошибка: " + (data.error || "неизвестная ошибка"));
        return;
      }

      const summary = data.summary || {};
      const positions = data.positions || [];

      setText("model", `${data.model_version} · ${data.quality_mode_title || data.quality_mode || "normal"}`);
      setText("invested", formatMoney(summary.invested));
      setText("cash", `${formatMoney(summary.cash)} · ${formatPct(summary.cash_pct)}`);
      setText("risk", summary.portfolio_risk_level);

      const rr = summary.risk_reward_ratio;
      const rrLabel = summary.risk_reward_label || "нет данных";
      setText("riskReward", rr === null || rr === undefined ? rrLabel : `${formatNumber(rr, 2)} · ${rrLabel}`);

      const conclusion = document.getElementById("portfolioConclusion");
      if (conclusion) {
        conclusion.textContent = summary.portfolio_conclusion || "Портфель собран.";
        conclusion.className = "muted";
      }

      const tbody = document.getElementById("positionsRows");

      if (!positions.length) {
        tbody.innerHTML = '<tr><td colspan="14" class="muted">Нет подходящих позиций по текущим условиям.</td></tr>';
      } else {
        tbody.innerHTML = positions.map(row => `
          <tr>
            <td><a href="${escapeHtml(row.ticker_url || "#")}"><b>${escapeHtml(row.ticker)}</b></a></td>
            <td>${formatMoney(row.price)}</td>
            <td>${row.lot_size || 1}</td>
            <td><b>${row.lots || "—"}</b></td>
            <td><b>${row.quantity}</b></td>
            <td><b>${formatMoney(row.value)}</b></td>
            <td>${formatPct(row.weight_pct)}</td>
            <td>
              <span class="${signalBadgeClass(row.action)}">${escapeHtml(row.label || row.action || "—")}</span>
              <div class="muted small">${escapeHtml(row.trend || "")}</div>
            </td>
            <td>${formatPct(row.confidence_pct)}</td>
            <td>${formatMoney(row.target_price)}</td>
            <td>
              <b>${formatPct(row.target_upside_pct)}</b>
              <div class="muted small">${formatMoney(row.target_upside_rub)}</div>
            </td>
            <td>${formatMoney(row.stop_loss)}</td>
            <td>
              <b>${formatPct(row.stop_downside_pct)}</b>
              <div class="muted small">${formatMoney(row.stop_downside_rub)}</div>
            </td>
            <td>
              ${(row.reasons || []).map(reason => `<div class="small muted">• ${escapeHtml(reason)}</div>`).join("")}
            </td>
          </tr>
        `).join("");
      }

      const excluded = data.excluded || [];
      const excludedTbody = document.getElementById("excludedRows");

      if (excludedTbody) {
        if (!excluded.length) {
          excludedTbody.innerHTML = '<tr><td colspan="5" class="muted">Нет исключённых тикеров.</td></tr>';
        } else {
          excludedTbody.innerHTML = excluded.map(row => `
            <tr>
              <td><a href="${escapeHtml(row.ticker_url || "#")}"><b>${escapeHtml(row.ticker || "—")}</b></a></td>
              <td>
                <span class="${signalBadgeClass(row.action)}">${escapeHtml(row.label || row.action || "—")}</span>
              </td>
              <td>${formatMoney(row.price)}</td>
              <td>${row.score === null || row.score === undefined ? "—" : formatNumber(row.score, 2)}</td>
              <td>${escapeHtml(row.reason || "—")}</td>
            </tr>
          `).join("");
        }
      }

      const notes = data.notes || [];
      document.getElementById("notes").innerHTML = notes.map(note => `
        <li class="muted">${escapeHtml(note)}</li>
      `).join("");
    }

    function getPortfolioPayload() {
      return {
        budget: Number(document.getElementById("budget").value || 0),
        risk_profile: document.getElementById("riskProfile").value,
        horizon: document.getElementById("horizon").value,
        quality_mode: document.getElementById("qualityMode").value,
        model_version: document.getElementById("modelVersion").value || null,
        tickers: document.getElementById("tickers").value || null
      };
    }

    async function constructPortfolio() {
      setText("status", "Собираю портфель...");

      const payload = getPortfolioPayload();

      const response = await fetch("/portfolio/construct", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        throw new Error("HTTP " + response.status + ": " + await response.text());
      }

      const data = await response.json();
      render(data);

      const now = new Date().toLocaleTimeString("ru-RU");
      setText("status", "Портфель собран: " + now + ".");
    }


    async function downloadPortfolioCsv() {
      setText("status", "Готовлю CSV...");

      const response = await fetch("/portfolio/construct.csv", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(getPortfolioPayload())
      });

      if (!response.ok) {
        throw new Error("CSV HTTP " + response.status + ": " + await response.text());
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);

      const link = document.createElement("a");
      link.href = url;
      link.download = "portfolio_construct.csv";
      document.body.appendChild(link);
      link.click();
      link.remove();

      URL.revokeObjectURL(url);

      const now = new Date().toLocaleTimeString("ru-RU");
      setText("status", "CSV сформирован: " + now + ".");
    }

    window.constructPortfolio = constructPortfolio;
    window.downloadPortfolioCsv = downloadPortfolioCsv;

    constructPortfolio().catch(error => {
      setText("status", "Ошибка: " + error.message);
    });
  </script>
</body>
</html>"""
