def build_ai_report_demo_html() -> str:
    return """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <title>AI Report · AI Аналитик рынка РФ</title>
  <style>
    :root {
      --bg: #f3f4f6;
      --card: #ffffff;
      --text: #111827;
      --muted: #64748b;
      --blue: #2563eb;
      --blue-soft: #eff6ff;
      --border: #e5e7eb;
      --dark: #111827;
      --green: #16803c;
      --red: #dc2626;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
    }

    header {
      background: #111827;
      color: white;
      padding: 28px 32px;
    }

    header h1 {
      margin: 0 0 10px;
      font-size: 30px;
    }

    header a {
      color: #93c5fd;
      text-decoration: none;
      font-weight: 600;
    }

    main {
      padding: 24px 32px 40px;
    }

    .card {
      background: var(--card);
      border-radius: 18px;
      padding: 24px;
      margin-bottom: 20px;
      box-shadow: 0 10px 25px rgba(15, 23, 42, 0.06);
    }

    h2 {
      margin: 0 0 16px;
      font-size: 24px;
    }

    h3 {
      margin: 0 0 12px;
      font-size: 18px;
    }

    .muted {
      color: var(--muted);
    }

    button {
      border: 0;
      border-radius: 10px;
      background: var(--blue);
      color: white;
      padding: 10px 16px;
      font-weight: 700;
      cursor: pointer;
      margin-right: 8px;
      margin-top: 10px;
    }

    button:hover {
      filter: brightness(0.95);
    }

    button.secondary {
      background: #334155;
    }

    button.danger {
      background: #dc2626;
    }

    button.small {
      padding: 7px 10px;
      margin: 0;
      font-size: 13px;
    }

    button:disabled {
      opacity: 0.55;
      cursor: wait;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 12px;
    }

    th, td {
      padding: 10px 8px;
      border-bottom: 1px solid var(--border);
      text-align: left;
      vertical-align: middle;
    }

    th {
      color: var(--muted);
      font-size: 14px;
    }

    input {
      width: 100%;
      border: 1px solid #cbd5e1;
      border-radius: 10px;
      padding: 10px 12px;
      font: inherit;
      background: white;
    }

    .ticker-input {
      font-weight: 800;
      text-transform: uppercase;
    }

    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
    }

    .actions button {
      margin: 0;
    }

    .status {
      margin-top: 14px;
      color: var(--muted);
      font-weight: 600;
    }

    .section {
      background: #f8fafc;
      border-left: 4px solid #3b82f6;
      border-radius: 12px;
      padding: 16px;
      margin: 12px 0;
    }

    .section p {
      white-space: pre-line;
      margin: 0;
      line-height: 1.45;
    }

    pre {
      background: #111827;
      color: white;
      padding: 18px;
      border-radius: 12px;
      overflow: auto;
      white-space: pre-wrap;
      line-height: 1.45;
    }

    .ok { color: var(--green); font-weight: 800; }
    .bad { color: var(--red); font-weight: 800; }

    .summary-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
      margin-top: 14px;
    }

    .mini-card {
      background: #f8fafc;
      border-radius: 14px;
      padding: 14px;
    }

    .mini-card .label {
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 6px;
    }

    .mini-card .value {
      font-size: 22px;
      font-weight: 900;
    }

    @media (max-width: 900px) {
      main { padding: 18px; }
      .summary-grid { grid-template-columns: 1fr; }
      table { font-size: 14px; }
    }
  </style>
</head>
<body>
  <header>
    <h1>AI Report</h1>
    <div>
      <a href="/dashboard">← Рынок</a> ·
      <a href="/events/dashboard">События</a> ·
      <a href="/portfolio/demo">Портфель</a> ·
      <a href="/portfolio/construct/demo">Конструктор портфеля</a> ·
      <a href="/ai/reports/dashboard">История отчётов</a>
    </div>
  </header>

  <main>
    <section class="card">
      <h2>Портфель для отчёта</h2>
      <p class="muted">Редактируйте позиции в таблице. JSON больше не нужен.</p>

      <table>
        <thead>
          <tr>
            <th style="width: 45%;">Тикер</th>
            <th style="width: 35%;">Количество</th>
            <th style="width: 20%;">Действие</th>
          </tr>
        </thead>
        <tbody id="positionsBody"></tbody>
      </table>

      <div class="actions">
        <button type="button" class="secondary" onclick="addPositionRow()">+ Добавить строку</button>
        <button type="button" onclick="savePortfolio()">Сохранить портфель</button>
        <button type="button" onclick="loadPortfolio()">Загрузить портфель</button>
        <button type="button" onclick="buildReport()">Собрать AI Report</button>
        <button type="button" onclick="saveReport()">Сохранить отчёт в историю</button>
        <button type="button" onclick="downloadMarkdown()">Скачать Markdown</button>
      </div>

      <div id="status" class="status">Готов к сборке отчёта.</div>
    </section>

    <section class="card" id="reportCard">
      <h2 id="reportTitle">Отчёт</h2>
      <p class="muted">Дата: <span id="reportDate">—</span></p>

      <div class="summary-grid">
        <div class="mini-card">
          <div class="label">Рынок</div>
          <div class="value" id="marketMood">—</div>
        </div>
        <div class="mini-card">
          <div class="label">Стоимость портфеля</div>
          <div class="value" id="portfolioValue">—</div>
        </div>
        <div class="mini-card">
          <div class="label">День</div>
          <div class="value" id="portfolioDay">—</div>
        </div>
      </div>

      <div class="section">
        <h3>1. Рыночный фон</h3>
        <p id="marketContext">—</p>
      </div>

      <div class="section">
        <h3>2. Главные события</h3>
        <p id="importantEvents">—</p>
      </div>

      <div class="section">
        <h3>3. Рыночные сигналы</h3>
        <p id="marketSignals">—</p>
      </div>

      <div class="section">
        <h3>4. Портфель</h3>
        <p id="portfolioContext">—</p>
      </div>

      <div class="section">
        <h3>5. Риски</h3>
        <p id="riskReview">—</p>
      </div>

      <div class="section">
        <h3>6. Watchlist</h3>
        <p id="watchlist">—</p>
      </div>

      <div class="section">
        <h3>7. Вывод дня</h3>
        <p id="conclusion">—</p>
      </div>

      <p class="muted" id="disclaimer">Это аналитическая сводка на основе рыночных и новостных данных, а не инвестиционная рекомендация.</p>
    </section>

    <section class="card">
      <h2>Полный текст</h2>
      <pre id="fullReport">—</pre>
    </section>
  </main>

  <script>
    let latestReportText = "";

    const DEFAULT_POSITIONS = [
      { ticker: "SBER", quantity: 10 },
      { ticker: "LKOH", quantity: 1 },
      { ticker: "GAZP", quantity: 50 },
      { ticker: "PLZL", quantity: 1 }
    ];

    function setStatus(message, isError = false) {
      const status = document.getElementById("status");
      status.textContent = message;
      status.className = isError ? "status bad" : "status";
    }

    function setText(id, value) {
      document.getElementById(id).textContent =
        value === null || value === undefined || value === "" ? "—" : value;
    }

    function formatRub(value) {
      if (value === null || value === undefined || Number.isNaN(Number(value))) {
        return "—";
      }

      return Number(value).toLocaleString("ru-RU", {
        maximumFractionDigits: 2
      }) + " руб.";
    }

    function formatPct(value) {
      if (value === null || value === undefined || Number.isNaN(Number(value))) {
        return "—";
      }

      return Number(value).toLocaleString("ru-RU", {
        maximumFractionDigits: 2
      }) + "%";
    }

    function normalizeTicker(value) {
      return String(value || "").trim().toUpperCase();
    }

    function addPositionRow(ticker = "", quantity = "") {
      const tbody = document.getElementById("positionsBody");
      const tr = document.createElement("tr");

      const tickerTd = document.createElement("td");
      const tickerInput = document.createElement("input");
      tickerInput.className = "ticker-input";
      tickerInput.placeholder = "SBER";
      tickerInput.value = normalizeTicker(ticker);
      tickerInput.addEventListener("input", function () {
        tickerInput.value = normalizeTicker(tickerInput.value);
      });
      tickerTd.appendChild(tickerInput);

      const quantityTd = document.createElement("td");
      const quantityInput = document.createElement("input");
      quantityInput.type = "number";
      quantityInput.min = "0";
      quantityInput.step = "any";
      quantityInput.placeholder = "10";
      quantityInput.value = quantity;
      quantityTd.appendChild(quantityInput);

      const actionTd = document.createElement("td");
      const removeButton = document.createElement("button");
      removeButton.type = "button";
      removeButton.className = "danger small";
      removeButton.textContent = "Удалить";
      removeButton.addEventListener("click", function () {
        tr.remove();

        if (document.querySelectorAll("#positionsBody tr").length === 0) {
          addPositionRow();
        }
      });
      actionTd.appendChild(removeButton);

      tr.appendChild(tickerTd);
      tr.appendChild(quantityTd);
      tr.appendChild(actionTd);

      tbody.appendChild(tr);
    }

    function renderPositions(positions) {
      const tbody = document.getElementById("positionsBody");
      tbody.innerHTML = "";

      const clean = Array.isArray(positions) && positions.length
        ? positions
        : DEFAULT_POSITIONS;

      clean.forEach(function (item) {
        addPositionRow(item.ticker, item.quantity);
      });
    }

    function getPositionsFromTable() {
      const rows = Array.from(document.querySelectorAll("#positionsBody tr"));
      const positions = [];

      rows.forEach(function (row) {
        const inputs = row.querySelectorAll("input");
        const ticker = normalizeTicker(inputs[0].value);
        const quantity = Number(inputs[1].value);

        if (!ticker && !inputs[1].value) {
          return;
        }

        if (!ticker) {
          throw new Error("У одной из строк не указан тикер.");
        }

        if (!Number.isFinite(quantity) || quantity <= 0) {
          throw new Error("Для " + ticker + " укажите количество больше нуля.");
        }

        positions.push({ ticker, quantity });
      });

      if (!positions.length) {
        throw new Error("Добавьте хотя бы одну позицию.");
      }

      return positions;
    }

    function getPortfolioPayload() {
      return {
        positions: getPositionsFromTable()
      };
    }

    async function loadPortfolio() {
      setStatus("Загружаю портфель...");

      const response = await fetch("/portfolio/positions");

      if (!response.ok) {
        throw new Error("HTTP " + response.status);
      }

      const data = await response.json();
      renderPositions(data.positions || []);

      setStatus("Портфель загружен.");
    }

    async function savePortfolio() {
      try {
        const payload = getPortfolioPayload();

        setStatus("Сохраняю портфель...");

        const response = await fetch("/portfolio/positions", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });

        if (!response.ok) {
          const errorText = await response.text();
          throw new Error("HTTP " + response.status + ": " + errorText);
        }

        const data = await response.json();
        renderPositions(data.positions || payload.positions);

        setStatus("Портфель сохранён.");
      } catch (error) {
        setStatus("Ошибка сохранения портфеля: " + error.message, true);
      }
    }

    function renderReport(data) {
      const sections = data.sections || {};
      const portfolio = data.portfolio || {};
      const market = data.market || {};

      setText("reportTitle", data.title || "AI Report российского рынка");
      setText("reportDate", data.date);
      setText("marketMood", market.market_mood);
      setText("portfolioValue", formatRub(portfolio.total_value));

      const dayText = portfolio.daily_pnl_abs !== undefined
        ? formatRub(portfolio.daily_pnl_abs) + " / " + formatPct(portfolio.daily_pnl_pct)
        : "—";
      setText("portfolioDay", dayText);

      setText("marketContext", sections.market_context);
      setText("importantEvents", sections.important_events);
      setText("marketSignals", sections.market_signals);
      setText("portfolioContext", sections.portfolio_context);
      setText("riskReview", sections.risk_review);
      setText("watchlist", sections.watchlist);
      setText("conclusion", sections.conclusion);
      setText("disclaimer", data.disclaimer);

      latestReportText = data.full_report || "";
      setText("fullReport", latestReportText);
    }

    async function buildReport() {
      console.log("AI Report button clicked");

      var status = document.getElementById("status");
      status.textContent = "Собираю отчёт...";

      try {
        var payload = getPortfolioPayload();

        var response = await fetch("/ai/report/build-and-save", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(payload)
        });

        if (!response.ok) {
          var errorText = await response.text();
          throw new Error("HTTP " + response.status + ": " + errorText);
        }

        var data = await response.json();

        renderReport(data);
        latestReportText = data.full_report || "";

        var saved = data.saved_report;
        if (saved && saved.id) {
          status.innerHTML =
            'Отчёт готов и сохранён в историю. ID: ' + saved.id +
            ' · <a href="' + saved.markdown_url + '">Markdown</a>' +
            ' · <a href="/ai/reports/dashboard">История</a>';
        } else {
          status.textContent = "Отчёт готов.";
        }
      } catch (error) {
        console.error(error);
        status.textContent = "Ошибка загрузки: " + error.message;
      }
    }

    async function downloadMarkdown() {
      try {
        let text = latestReportText;

        if (!text) {
          const payload = getPortfolioPayload();

          setStatus("Готовлю Markdown...");

          const response = await fetch("/ai/report/markdown", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
          });

          if (!response.ok) {
            const errorText = await response.text();
            throw new Error("HTTP " + response.status + ": " + errorText);
          }

          text = await response.text();
        }

        const blob = new Blob([text], {
          type: "text/markdown;charset=utf-8"
        });

        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");

        a.href = url;
        a.download = "ai_report.md";
        document.body.appendChild(a);
        a.click();
        a.remove();

        URL.revokeObjectURL(url);

        setStatus("Markdown скачан.");
      } catch (error) {
        setStatus("Ошибка скачивания Markdown: " + error.message, true);
      }
    }

    window.addPositionRow = addPositionRow;
    window.savePortfolio = savePortfolio;
    window.loadPortfolio = loadPortfolio;
    window.buildReport = buildReport;
    window.saveReport = saveReport;
    window.downloadMarkdown = downloadMarkdown;

    document.addEventListener("DOMContentLoaded", function () {
      renderPositions(DEFAULT_POSITIONS);

      loadPortfolio().catch(function (error) {
        console.error(error);
        setStatus("Не удалось загрузить сохранённый портфель. Использую demo-портфель.", true);
      });
    });
  </script>
</body>
</html>
"""
