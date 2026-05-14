def build_ai_report_history_page_html() -> str:
    return """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <title>История AI Report</title>
  <style>
    * { box-sizing: border-box; }

    body {
      margin: 0;
      font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f3f4f6;
      color: #111827;
    }

    header {
      background: #111827;
      color: #fff;
      padding: 42px 32px;
    }

    header h1 {
      margin: 0 0 18px 0;
      font-size: 32px;
    }

    header a {
      color: #93c5fd;
      text-decoration: none;
      font-weight: 700;
    }

    main {
      padding: 24px 32px 48px;
    }

    .card {
      background: #fff;
      border-radius: 16px;
      padding: 24px;
      margin-bottom: 20px;
      box-shadow: 0 12px 30px rgba(15, 23, 42, 0.06);
    }

    .muted {
      color: #64748b;
    }

    button,
    .button {
      border: 0;
      border-radius: 10px;
      padding: 10px 16px;
      font-weight: 700;
      background: #2563eb;
      color: #fff;
      cursor: pointer;
      margin-right: 8px;
      text-decoration: none;
      display: inline-block;
      font-size: 14px;
    }

    button:hover,
    .button:hover {
      background: #1d4ed8;
    }

    button.secondary,
    .button.secondary {
      background: #334155;
    }

    button.danger,
    .button.danger {
      background: #dc2626;
    }

    button.danger:hover,
    .button.danger:hover {
      background: #b91c1c;
    }

    button:disabled {
      opacity: 0.55;
      cursor: not-allowed;
    }

    input {
      border: 1px solid #cbd5e1;
      border-radius: 10px;
      padding: 10px 12px;
      font: inherit;
      width: 100px;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 16px;
    }

    th, td {
      text-align: left;
      border-bottom: 1px solid #e5e7eb;
      padding: 10px;
      vertical-align: middle;
    }

    th {
      color: #64748b;
      font-size: 14px;
    }

    td a {
      color: #2563eb;
      font-weight: 700;
      text-decoration: none;
    }

    .actions {
      display: flex;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
    }

    .danger-link {
      color: #dc2626 !important;
      font-weight: 700;
    }

    .status {
      margin-top: 14px;
      color: #64748b;
      font-weight: 700;
    }

    .cleanup-box {
      margin-top: 18px;
      padding: 16px;
      border-radius: 14px;
      background: #f8fafc;
      border-left: 4px solid #2563eb;
    }

    .cleanup-row {
      display: flex;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
      margin-top: 10px;
    }



    .filter-row {
      display: flex;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
      margin: 14px 0 8px;
    }

    .filter-button {
      background: #334155;
    }

    .filter-button.active {
      background: #2563eb;
    }

    .filter-count {
      margin-left: 4px;
      font-weight: 700;
      color: #64748b;
    }

    .favorite-button {
      border: 0;
      background: transparent;
      color: #f59e0b;
      font-size: 22px;
      padding: 0 6px 0 0;
      margin: 0;
      cursor: pointer;
      vertical-align: middle;
    }

    .favorite-button:hover {
      background: transparent;
      color: #d97706;
    }

    .note-input {
      min-width: 260px;
      width: 100%;
      max-width: 420px;
      margin-top: 6px;
    }

    .note-cell {
      min-width: 300px;
    }

    .small-button {
      padding: 7px 10px;
      border-radius: 8px;
      font-size: 12px;
      margin-top: 6px;
    }

    pre {
      background: #111827;
      color: #e5e7eb;
      padding: 18px;
      border-radius: 12px;
      overflow: auto;
      white-space: pre-wrap;
      line-height: 1.45;
    }
  </style>
</head>
<body>
  <header>
    <h1>История AI Report</h1>
    <nav>
      <a href="/dashboard">← Рынок</a> ·
      <a href="/ai/report/demo">AI Report</a> ·
      <a href="/ai/reports/trends">Динамика</a> ·
      <a href="/ai/report/compare/latest">Сравнить последние</a> ·
      <a href="/system/dashboard">Обновить данные + отчёт</a>
    </nav>
  </header>

  <main>
    <section class="card">
      <h2>Сохранение и обслуживание</h2>
      <p class="muted">Можно сохранить новый AI Report, обновить данные или очистить старые snapshot’ы.</p>

      <button id="saveButton" onclick="saveReport()">Сохранить новый отчёт</button>
      <button id="updateButton" onclick="updateAndReport()">Обновить данные + отчёт</button>
      <button onclick="loadReports()">Обновить список</button>
      <a class="button secondary" href="/ai/reports/trends">Динамика</a>
      <a class="button secondary" href="/ai/report/compare/latest">Сравнить последние</a>
      <a class="button secondary" href="/ai/reports/trends.csv">Скачать CSV</a>

      <div class="cleanup-box">
        <b>Очистка старых отчётов</b>
        <p class="muted">Оставить последние N отчётов, остальные удалить.</p>

        <div class="cleanup-row">
          <label>
            Оставить:
            <input id="cleanupKeep" type="number" min="0" max="1000" value="5" />
          </label>
          <button onclick="previewCleanup()">Предпросмотр очистки</button>
          <button class="danger" onclick="cleanupReports()">Очистить старые</button>
        </div>

        <div id="cleanupStatus" class="status">Очистка не запускалась.</div>
      </div>

      <div id="status" class="status">Готово.</div>
    </section>

    <section class="card">
      <h2>Сохранённые отчёты</h2>

      <div class="filter-row">
        <button id="filterAll" class="filter-button active" onclick="setReportFilter('all')">Все отчёты</button>
        <button id="filterFavorites" class="filter-button" onclick="setReportFilter('favorites')">Только избранные</button>
        <button id="filterNotes" class="filter-button" onclick="setReportFilter('notes')">Только с заметками</button>
        <span id="filterCount" class="filter-count">—</span>
      </div>

      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Дата отчёта</th>
            <th>Создан</th>
            <th>Название</th>
            <th>Избранное / заметка</th>
            <th>Действия</th>
          </tr>
        </thead>
        <tbody id="reports">
          <tr>
            <td colspan="6" class="muted">Загружаю...</td>
          </tr>
        </tbody>
      </table>
    </section>

    <section class="card">
      <h2>Просмотр</h2>
      <pre id="preview">Выберите отчёт.</pre>
    </section>
  </main>

  <script>
    let selectedReportId = null;
    let allReports = [];
    let currentReportFilter = "all";

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function setStatus(text) {
      document.getElementById("status").textContent = text;
    }

    function getCleanupKeep() {
      const keep = Number(document.getElementById("cleanupKeep").value);

      if (!Number.isFinite(keep) || keep < 0) {
        throw new Error("Введите корректное число отчётов для сохранения.");
      }

      return Math.floor(keep);
    }

    function setReportFilter(filter) {
      currentReportFilter = filter;
      loadReports().catch(error => {
        setStatus("Ошибка фильтра: " + error.message);
      });
    }

    function getReportsUrl() {
      if (currentReportFilter === "favorites") {
        return "/ai/reports?favorite=true";
      }

      if (currentReportFilter === "notes") {
        return "/ai/reports?with_note=true";
      }

      return "/ai/reports";
    }

    function updateFilterButtons() {
      const buttons = {
        all: document.getElementById("filterAll"),
        favorites: document.getElementById("filterFavorites"),
        notes: document.getElementById("filterNotes")
      };

      Object.keys(buttons).forEach(key => {
        if (!buttons[key]) return;

        if (key === currentReportFilter) {
          buttons[key].classList.add("active");
        } else {
          buttons[key].classList.remove("active");
        }
      });
    }

    function getFilteredReports() {
      return allReports;
    }

    function renderReports() {
      updateFilterButtons();

      const data = getFilteredReports();
      const tbody = document.getElementById("reports");
      const filterCount = document.getElementById("filterCount");

      if (filterCount) {
        filterCount.textContent = `Показано: ${data.length}`;
      }

      if (!allReports.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="muted">Пока нет сохранённых отчётов.</td></tr>';
        setStatus("Список пуст.");
        return;
      }

      if (!data.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="muted">По выбранному backend-фильтру отчётов нет.</td></tr>';
        setStatus("Backend-фильтр применён.");
        return;
      }

      tbody.innerHTML = data.map((row) => {
        const globalIndex = allReports.findIndex(item => item.id === row.id);
        const previous = globalIndex >= 0 ? allReports[globalIndex + 1] : null;

        const compareHtml = previous
          ? ` · <a href="/ai/report/compare?left_id=${row.id}&right_id=${previous.id}">Сравнить с предыдущим</a>`
          : "";

        return `
          <tr id="report-row-${row.id}">
            <td>${escapeHtml(row.id)}</td>
            <td>${escapeHtml(row.report_date || "—")}</td>
            <td>${escapeHtml(row.created_at || "—")}</td>
            <td>${escapeHtml(row.title || "—")}</td>
            <td class="note-cell">
              <button
                class="favorite-button"
                title="Переключить избранное"
                onclick="toggleFavorite(${row.id}, ${row.is_favorite ? "false" : "true"}); return false;"
              >${row.is_favorite ? "★" : "☆"}</button>
              <input
                class="note-input"
                id="note-${row.id}"
                value="${escapeHtml(row.note || "")}"
                placeholder="Заметка к отчёту"
              />
              <br>
              <button class="small-button secondary" onclick="saveNote(${row.id}); return false;">Сохранить заметку</button>
            </td>
            <td>
              <div class="actions">
                <a href="${escapeHtml(row.view_url || ("/ai/reports/" + row.id + "/view"))}">Открыть</a>
                <a href="${escapeHtml(row.markdown_url)}">Markdown</a>
                <a href="${escapeHtml(row.detail_url)}">JSON</a>
                ${compareHtml}
                <a class="danger-link" href="#" onclick="deleteReport(${row.id}); return false;">Удалить</a>
              </div>
            </td>
          </tr>
        `;
      }).join("");

      setStatus("Список обновлён.");
    }

    async function loadReports() {
      setStatus("Загружаю список...");

      const response = await fetch(getReportsUrl());
      if (!response.ok) {
        throw new Error("HTTP " + response.status + ": " + await response.text());
      }

      allReports = await response.json();
      renderReports();
    }

    async function viewReport(id) {
      selectedReportId = id;

      const response = await fetch(`/ai/reports/${id}`);
      if (!response.ok) {
        throw new Error("HTTP " + response.status + ": " + await response.text());
      }

      const data = await response.json();

      document.getElementById("preview").textContent =
        data.markdown || JSON.stringify(data, null, 2);
    }


    async function updateReportMeta(id, payload) {
      const response = await fetch(`/ai/reports/${id}/meta`, {
        method: "PATCH",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        throw new Error("HTTP " + response.status + ": " + await response.text());
      }

      return await response.json();
    }

    async function toggleFavorite(id, value) {
      setStatus("Обновляю избранное для отчёта #" + id + "...");

      try {
        await updateReportMeta(id, {is_favorite: value});
        await loadReports();
        setStatus(value ? "Отчёт #" + id + " добавлен в избранное." : "Отчёт #" + id + " убран из избранного.");
      } catch (error) {
        setStatus("Ошибка избранного: " + error.message);
      }
    }

    async function saveNote(id) {
      const input = document.getElementById("note-" + id);
      const note = input ? input.value : "";

      setStatus("Сохраняю заметку к отчёту #" + id + "...");

      try {
        await updateReportMeta(id, {note});
        await loadReports();
        setStatus("Заметка к отчёту #" + id + " сохранена.");
      } catch (error) {
        setStatus("Ошибка заметки: " + error.message);
      }
    }

    async function deleteReport(id) {
      const ok = confirm("Удалить отчёт #" + id + "?");
      if (!ok) return;

      setStatus("Удаляю отчёт #" + id + "...");

      const response = await fetch(`/ai/reports/${id}`, {
        method: "DELETE"
      });

      if (!response.ok) {
        setStatus("Ошибка удаления.");
        alert("Не удалось удалить отчёт: " + await response.text());
        return;
      }

      if (selectedReportId === id) {
        selectedReportId = null;
        document.getElementById("preview").textContent = "Отчёт удалён.";
      }

      await loadReports();
      setStatus("Отчёт #" + id + " удалён.");
    }

    async function saveReport() {
      const button = document.getElementById("saveButton");
      button.disabled = true;
      setStatus("Сохраняю отчёт...");

      try {
        const response = await fetch("/ai/report/save", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({})
        });

        if (!response.ok) {
          throw new Error("HTTP " + response.status + ": " + await response.text());
        }

        const data = await response.json();
        await loadReports();

        setStatus("Отчёт сохранён. ID: " + data.id);
      } catch (error) {
        setStatus("Ошибка сохранения: " + error.message);
      } finally {
        button.disabled = false;
      }
    }

    async function updateAndReport() {
      const button = document.getElementById("updateButton");
      button.disabled = true;
      setStatus("Обновляю данные и собираю отчёт...");

      try {
        const response = await fetch("/system/update-and-report", {
          method: "POST"
        });

        if (!response.ok) {
          throw new Error("HTTP " + response.status + ": " + await response.text());
        }

        const data = await response.json();
        await loadReports();

        if (data.report && data.report.id) {
          setStatus("Данные обновлены, отчёт сохранён. ID: " + data.report.id);
        } else {
          setStatus("Готово, но отчёт не найден в ответе.");
        }
      } catch (error) {
        setStatus("Ошибка обновления: " + error.message);
      } finally {
        button.disabled = false;
      }
    }

    async function previewCleanup() {
      try {
        const keep = getCleanupKeep();
        const response = await fetch(`/ai/reports/cleanup/preview?keep=${keep}`);

        if (!response.ok) {
          throw new Error("HTTP " + response.status + ": " + await response.text());
        }

        const data = await response.json();

        document.getElementById("cleanupStatus").textContent =
          `Всего: ${data.total_reports}. Останется: ${data.kept_count}. Будет удалено: ${data.delete_count}. ID к удалению: ${data.delete_ids.join(", ") || "нет"}.`;
      } catch (error) {
        document.getElementById("cleanupStatus").textContent =
          "Ошибка предпросмотра: " + error.message;
      }
    }

    async function cleanupReports() {
      try {
        const keep = getCleanupKeep();

        const previewResponse = await fetch(`/ai/reports/cleanup/preview?keep=${keep}`);
        if (!previewResponse.ok) {
          throw new Error("HTTP " + previewResponse.status + ": " + await previewResponse.text());
        }

        const preview = await previewResponse.json();

        if (!preview.delete_count) {
          document.getElementById("cleanupStatus").textContent = "Удалять нечего.";
          return;
        }

        const ok = confirm(
          `Удалить старые отчёты?\\n\\n` +
          `Останется: ${preview.kept_ids.join(", ") || "нет"}\\n` +
          `Будет удалено: ${preview.delete_ids.join(", ")}`
        );

        if (!ok) return;

        document.getElementById("cleanupStatus").textContent = "Удаляю старые отчёты...";

        const response = await fetch(`/ai/reports/cleanup?keep=${keep}`, {
          method: "DELETE"
        });

        if (!response.ok) {
          throw new Error("HTTP " + response.status + ": " + await response.text());
        }

        const data = await response.json();

        document.getElementById("cleanupStatus").textContent =
          data.message || `Удалено: ${data.deleted}.`;

        await loadReports();
      } catch (error) {
        document.getElementById("cleanupStatus").textContent =
          "Ошибка очистки: " + error.message;
      }
    }

    window.loadReports = loadReports;
    window.setReportFilter = setReportFilter;
    window.saveReport = saveReport;
    window.updateAndReport = updateAndReport;
    window.deleteReport = deleteReport;
    window.toggleFavorite = toggleFavorite;
    window.saveNote = saveNote;
    window.previewCleanup = previewCleanup;
    window.cleanupReports = cleanupReports;

    loadReports().catch(error => {
      setStatus("Ошибка загрузки: " + error.message);
    });
  </script>
</body>
</html>
"""
