from __future__ import annotations


def build_signals_model_quality_page_html() -> str:
    return """<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <title>Signal Model Quality</title>
  <style>
    body {
      margin: 0;
      font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f3f4f6;
      color: #111827;
    }
    .wrap {
      max-width: 1180px;
      margin: 0 auto;
      padding: 28px;
    }
    .card {
      background: white;
      border: 1px solid #e5e7eb;
      border-radius: 18px;
      padding: 20px;
      box-shadow: 0 10px 26px rgba(15, 23, 42, 0.06);
      margin-bottom: 18px;
    }
    h1, h2 {
      margin-top: 0;
    }
    .muted {
      color: #6b7280;
    }
    .small {
      font-size: 13px;
    }
    .controls {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: end;
    }
    label {
      display: grid;
      gap: 6px;
    }
    input, select {
      border: 1px solid #d1d5db;
      border-radius: 10px;
      padding: 9px 10px;
      min-width: 160px;
    }
    .button {
      border: 0;
      border-radius: 10px;
      background: #2563eb;
      color: white;
      padding: 10px 14px;
      font-weight: 700;
      cursor: pointer;
      text-decoration: none;
      display: inline-block;
    }
    .button.secondary {
      background: #e5e7eb;
      color: #111827;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 12px;
    }
    .metric {
      background: #f9fafb;
      border: 1px solid #e5e7eb;
      border-radius: 14px;
      padding: 14px;
    }
    .metric .label {
      color: #6b7280;
      font-size: 12px;
    }
    .metric .value {
      font-size: 22px;
      font-weight: 800;
      margin-top: 4px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }
    th, td {
      border-bottom: 1px solid #e5e7eb;
      padding: 10px;
      text-align: left;
      vertical-align: top;
    }
    th {
      background: #f9fafb;
      color: #374151;
      font-size: 12px;
      text-transform: uppercase;
    }
    .badge {
      display: inline-block;
      padding: 4px 8px;
      border-radius: 999px;
      background: #eef2ff;
      color: #3730a3;
      font-size: 12px;
      font-weight: 700;
    }
    .good {
      background: #dcfce7;
      color: #166534;
    }
    .warn {
      background: #fef3c7;
      color: #92400e;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <section class="card">
      <p class="small muted">
        <a href="/dashboard">← Рынок</a> ·
        <a href="/signals">Сигналы</a> ·
        <a href="/signals/models/compare">Model Lab</a> ·
        <a href="/signals/champion">Champion</a>
      </p>

      <h1>Signal Model Quality</h1>
      <p class="muted">
        Сравнение моделей по текущим live-сигналам: confidence, quality_score, risk/reward и заблокированные buy-сценарии.
      </p>

      <div class="controls">
        <label>
          <span class="small muted">Модели</span>
          <input id="modelVersions" style="min-width:460px;" value="tech_v1_sma_momentum,tech_v2_rsi_atr,tech_v3_v1_atr_risk,tech_v4_quality_rr" />
        </label>

        <label>
          <span class="small muted">Limit</span>
          <input id="limit" type="number" min="1" max="500" value="100" />
        </label>

        <label>
          <span class="small muted">Candles</span>
          <input id="candlesLimit" type="number" min="20" max="1000" value="120" />
        </label>

        <button class="button" onclick="loadQuality()">Обновить</button>
        <a id="jsonLink" class="button secondary" href="/signals/models/quality.json" target="_blank">JSON</a>
      </div>

      <p id="status" class="small muted">Готово.</p>
    </section>

    <section class="card">
      <h2>Итоги</h2>
      <div class="grid">
        <div class="metric">
          <div class="label">Лучший avg RR</div>
          <div class="value" id="bestRR">—</div>
        </div>
        <div class="metric">
          <div class="label">Лучший avg confidence</div>
          <div class="value" id="bestConfidence">—</div>
        </div>
        <div class="metric">
          <div class="label">Самая строгая</div>
          <div class="value" id="strictest">—</div>
        </div>
      </div>
    </section>

    <section class="card">
      <h2>Модели</h2>
      <div style="overflow:auto;">
        <table>
          <thead>
            <tr>
              <th>Модель</th>
              <th>Всего</th>
              <th>Buy</th>
              <th>Hold</th>
              <th>Risk</th>
              <th>Avg confidence</th>
              <th>Avg quality</th>
              <th>RR coverage</th>
              <th>Avg RR</th>
              <th>Blocked buy</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody id="qualityTable">
            <tr><td colspan="11" class="muted">Загрузка...</td></tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>

  <script>
    function setText(id, value) {
      const el = document.getElementById(id);
      if (!el) return;
      el.textContent = value === null || value === undefined || value === "" ? "—" : value;
    }

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function formatNumber(value, digits = 2) {
      const n = Number(value);
      if (Number.isNaN(n)) return "—";
      return n.toLocaleString("ru-RU", {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits
      });
    }

    function formatPct(value) {
      const n = Number(value);
      if (Number.isNaN(n)) return "—";
      return formatNumber(n, 2) + "%";
    }

    function badge(value, kind = "") {
      return `<span class="badge ${kind}">${escapeHtml(value)}</span>`;
    }

    function actionsHtml(actions) {
      return Object.entries(actions || {})
        .map(([key, value]) => `${escapeHtml(key)}: <b>${escapeHtml(value)}</b>`)
        .join("<br>");
    }

    function buildParams() {
      const params = new URLSearchParams();
      params.set("model_versions", document.getElementById("modelVersions").value);
      params.set("limit", document.getElementById("limit").value || "100");
      params.set("candles_limit", document.getElementById("candlesLimit").value || "120");
      return params;
    }

    async function loadQuality() {
      setText("status", "Загружаю quality report...");

      const params = buildParams();
      const url = `/signals/models/quality.json?${params.toString()}`;

      document.getElementById("jsonLink").href = url;

      const response = await fetch(url);
      if (!response.ok) {
        throw new Error("HTTP " + response.status + ": " + await response.text());
      }

      const data = await response.json();

      const bestRR = data.best_by_avg_risk_reward;
      const bestConfidence = data.best_by_avg_confidence;
      const strictest = data.strictest_by_blocked_buy_count;

      setText("bestRR", bestRR ? `${bestRR.model_version} · ${formatNumber(bestRR.avg_risk_reward_ratio, 2)}` : "—");
      setText("bestConfidence", bestConfidence ? `${bestConfidence.model_version} · ${formatPct(bestConfidence.avg_confidence_pct)}` : "—");
      setText("strictest", strictest ? `${strictest.model_version} · ${strictest.blocked_buy_count}` : "—");

      const rows = data.models || [];
      const tbody = document.getElementById("qualityTable");

      if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="11" class="muted">Нет данных.</td></tr>';
        return;
      }

      tbody.innerHTML = rows.map(row => `
        <tr>
          <td><b>${escapeHtml(row.model_version)}</b></td>
          <td>${escapeHtml(row.total)}</td>
          <td>${badge(row.buy_like_count, row.buy_like_count ? "good" : "")}</td>
          <td>${escapeHtml(row.hold_count)}</td>
          <td>${escapeHtml(row.risk_count)}</td>
          <td>${formatPct(row.avg_confidence_pct)}</td>
          <td>${formatNumber(row.avg_quality_score, 2)}</td>
          <td>${formatPct(row.risk_reward_coverage_pct)}<br><span class="small muted">${escapeHtml(row.risk_reward_count)} сигналов</span></td>
          <td>${formatNumber(row.avg_risk_reward_ratio, 2)}</td>
          <td>${badge(row.blocked_buy_count, row.blocked_buy_count ? "warn" : "")}<br><span class="small muted">${formatPct(row.blocked_buy_pct)}</span></td>
          <td class="small">${actionsHtml(row.actions)}</td>
        </tr>
      `).join("");

      const now = new Date().toLocaleTimeString("ru-RU");
      setText("status", "Обновлено: " + now + ".");
    }

    window.loadQuality = loadQuality;

    loadQuality().catch(error => {
      setText("status", "Ошибка: " + error.message);
    });
  </script>
</body>
</html>"""
