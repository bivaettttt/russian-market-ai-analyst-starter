from __future__ import annotations


def build_system_dashboard_html() -> str:
    return """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>Системное обновление · AI Аналитик рынка РФ</title>
  <style>
    body {
      margin: 0;
      font-family: Inter, Arial, sans-serif;
      background: #f3f4f6;
      color: #111827;
    }
    header {
      background: #111827;
      color: white;
      padding: 28px 32px;
    }
    header a {
      color: #93c5fd;
      text-decoration: none;
      font-weight: 600;
    }
    main {
      padding: 28px 32px;
    }
    .card {
      background: white;
      border-radius: 18px;
      padding: 22px;
      margin-bottom: 20px;
      box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
    }
    button, .button {
      border: 0;
      border-radius: 10px;
      background: #2563eb;
      color: white;
      padding: 12px 18px;
      font-weight: 700;
      cursor: pointer;
      text-decoration: none;
      display: inline-block;
      margin-right: 8px;
    }
    button:disabled {
      opacity: 0.6;
      cursor: wait;
    }
    .muted {
      color: #64748b;
    }
    .ok {
      color: #15803d;
      font-weight: 700;
    }
    .bad {
      color: #b91c1c;
      font-weight: 700;
    }

    summary {
      cursor: pointer;
      font-size: 18px;
      margin-bottom: 12px;
    }

    details[open] summary {
      margin-bottom: 16px;
    }

    pre {
      background: #111827;
      color: #e5e7eb;
      padding: 18px;
      border-radius: 14px;
      overflow: auto;
      white-space: pre-wrap;
      font-size: 13px;
      line-height: 1.45;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 14px;
    }
    th, td {
      text-align: left;
      padding: 10px;
      border-bottom: 1px solid #e5e7eb;
      vertical-align: top;
    }
    th {
      color: #64748b;
      font-size: 13px;
    }
  </style>
</head>
<body>
  <header>
    <h1>Системное обновление</h1>
    <div>
      <a href="/dashboard">← Рынок</a> ·
      <a href="/ai/report/demo">AI Report</a> ·
      <a href="/ai/reports/dashboard">История отчётов</a>
    </div>
  </header>

  <main>
    <section class="card">
      <h2>Обновить данные + собрать отчёт</h2>
      <p class="muted">
        Кнопка запускает MOEX ingest, RSS ingest, затем собирает и сохраняет новый AI Report.
      </p>

      <button id="runBtn" onclick="runUpdate()">Обновить данные + AI Report</button>
      <a class="button" href="/ai/reports/dashboard">Открыть историю</a>

      <p id="status" class="muted">Готово к запуску.</p>
    </section>

    <section class="card">
      <h2>Результат</h2>
      <div id="result">Пока запусков нет.</div>
    </section>

    <section class="card">
    <details>
      <summary><b>Технические детали</b></summary>
      <pre id="details">—</pre>
    </details>
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

    function renderSteps(steps) {
      if (!steps || !steps.length) {
        return "<p class='muted'>Шаги не вернулись.</p>";
      }

      return `
        <table>
          <thead>
            <tr>
              <th>Шаг</th>
              <th>Статус</th>
              <th>Кратко</th>
            </tr>
          </thead>
          <tbody>
            ${steps.map(step => {
              const ok = step.ok ? "ok" : "bad";
              let short = "";

              if (step.step === "moex_ingest") {
                short = `tickers_ok: ${step.tickers_ok ?? "—"} / ${step.tickers_total ?? "—"}`;
              } else if (step.step === "rss_ingest") {
                const data = step.data || {};
                short = `inserted: ${data.total_inserted ?? "—"}, duplicates: ${data.total_duplicates ?? "—"}`;
              } else {
                short = JSON.stringify(step);
              }

              return `
                <tr>
                  <td>${escapeHtml(step.step)}</td>
                  <td class="${ok}">${step.ok ? "OK" : "ERROR"}</td>
                  <td>${escapeHtml(short)}</td>
                </tr>
              `;
            }).join("")}
          </tbody>
        </table>
      `;
    }

    async function runUpdate() {
      const button = document.getElementById("runBtn");
      const status = document.getElementById("status");
      const result = document.getElementById("result");
      const details = document.getElementById("details");

      button.disabled = true;
      status.textContent = "Обновляю данные и собираю отчёт...";
      result.innerHTML = "Ждём ответ сервера...";
      details.textContent = "Запрос выполняется...";

      try {
        const response = await fetch("/system/update-and-report", {
          method: "POST"
        });

        const data = await response.json();

        if (!response.ok || !data.ok) {
          status.textContent = "Обновление завершилось с ошибкой.";
        } else {
          status.textContent = "Готово. Отчёт сохранён.";
        }

        const report = data.report || {};
        const reportHtml = report.id
          ? `
            <p><b>Новый отчёт:</b> ID ${escapeHtml(report.id)}</p>
            <p>
              <a href="${escapeHtml(report.detail_url)}">JSON</a> ·
              <a href="${escapeHtml(report.markdown_url)}">Markdown</a> ·
              <a href="/ai/reports/dashboard">История</a>
            </p>
          `
          : "<p class='muted'>Отчёт не вернулся в ответе.</p>";

        result.innerHTML = `
          <p>${escapeHtml(data.message || "Готово.")}</p>
          ${reportHtml}
          ${renderSteps(data.steps || [])}
        `;

        details.textContent = JSON.stringify(data, null, 2);
      } catch (error) {
        status.textContent = "Ошибка запроса: " + error.message;
        result.innerHTML = "<p class='bad'>Не удалось выполнить обновление.</p>";
        details.textContent = String(error);
      } finally {
        button.disabled = false;
      }
    }
  </script>
</body>
</html>
"""
