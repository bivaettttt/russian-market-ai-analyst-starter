from __future__ import annotations


def build_ml_model_report_page_html() -> str:
    return """<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>ML Model Report</title>
  <style>
    :root {
      --bg: #f6f7fb;
      --panel: #ffffff;
      --text: #111827;
      --muted: #667085;
      --border: rgba(15, 23, 42, 0.10);
      --accent: #2563eb;
      --good: #16a34a;
      --warn: #d97706;
      --bad: #dc2626;
      --shadow: 0 18px 45px rgba(15, 23, 42, 0.08);
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
      background:
        radial-gradient(circle at top left, rgba(37, 99, 235, 0.10), transparent 32%),
        var(--bg);
      color: var(--text);
    }

    header {
      padding: 28px 24px;
      background: rgba(255, 255, 255, 0.82);
      backdrop-filter: blur(16px);
      border-bottom: 1px solid var(--border);
      position: sticky;
      top: 0;
      z-index: 2;
    }

    .header-inner, main {
      max-width: 1240px;
      margin: 0 auto;
    }

    h1 {
      margin: 0;
      font-size: 30px;
      letter-spacing: -0.04em;
    }

    .subtitle {
      margin: 8px 0 0;
      color: var(--muted);
      line-height: 1.5;
      max-width: 880px;
    }

    nav {
      margin-top: 16px;
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }

    nav a, .button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 9px 14px;
      text-decoration: none;
      color: var(--text);
      background: #fff;
      font-weight: 800;
      font-size: 13px;
      cursor: pointer;
    }

    .button.primary {
      background: var(--accent);
      color: #fff;
      border-color: var(--accent);
    }

    main {
      padding: 24px;
    }

    .grid {
      display: grid;
      grid-template-columns: 1.15fr 0.85fr;
      gap: 18px;
    }

    .cards {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin-bottom: 18px;
    }

    .card, .panel {
      background: rgba(255, 255, 255, 0.92);
      border: 1px solid var(--border);
      border-radius: 24px;
      box-shadow: var(--shadow);
    }

    .card {
      padding: 18px;
      min-height: 118px;
    }

    .label {
      color: var(--muted);
      font-size: 12px;
      font-weight: 900;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }

    .value {
      margin-top: 10px;
      font-size: 28px;
      font-weight: 950;
      letter-spacing: -0.04em;
    }

    .hint {
      margin-top: 8px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }

    .panel {
      padding: 20px;
      margin-bottom: 18px;
    }

    .panel h2 {
      margin: 0 0 14px;
      font-size: 20px;
      letter-spacing: -0.03em;
    }

    .badge {
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 7px 11px;
      font-weight: 900;
      font-size: 12px;
      background: rgba(37, 99, 235, 0.10);
      color: var(--accent);
    }

    .badge.good { background: rgba(22, 163, 74, 0.10); color: var(--good); }
    .badge.warn { background: rgba(217, 119, 6, 0.12); color: var(--warn); }
    .badge.bad { background: rgba(220, 38, 38, 0.10); color: var(--bad); }

    table {
      width: 100%;
      border-collapse: collapse;
      overflow: hidden;
      border-radius: 18px;
      font-size: 13px;
    }

    th, td {
      padding: 12px 10px;
      text-align: left;
      border-bottom: 1px solid var(--border);
      vertical-align: top;
    }

    th {
      color: var(--muted);
      font-size: 11px;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      background: rgba(248, 250, 252, 0.9);
    }

    tr:last-child td { border-bottom: 0; }

    .bar-wrap {
      width: 100%;
      height: 8px;
      border-radius: 999px;
      background: rgba(15, 23, 42, 0.08);
      overflow: hidden;
      margin-top: 6px;
    }

    .bar {
      height: 100%;
      background: var(--accent);
      border-radius: inherit;
      min-width: 2px;
    }

    .recommendation {
      padding: 18px;
      border-radius: 20px;
      background: rgba(37, 99, 235, 0.08);
      border: 1px solid rgba(37, 99, 235, 0.16);
      line-height: 1.55;
    }

    .recommendation.warn {
      background: rgba(217, 119, 6, 0.10);
      border-color: rgba(217, 119, 6, 0.20);
    }

    .recommendation.good {
      background: rgba(22, 163, 74, 0.10);
      border-color: rgba(22, 163, 74, 0.20);
    }

    .recommendation.bad {
      background: rgba(220, 38, 38, 0.08);
      border-color: rgba(220, 38, 38, 0.18);
    }

    .mono {
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 12px;
    }

    .empty {
      padding: 22px;
      color: var(--muted);
      border: 1px dashed var(--border);
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.65);
    }

    @media (max-width: 980px) {
      .grid, .cards {
        grid-template-columns: 1fr;
      }

      header, main {
        padding-left: 16px;
        padding-right: 16px;
      }
    }
  </style>
</head>
<body>
  <header>
    <div class="header-inner">
      <h1>ML Model Report</h1>
      <p class="subtitle">
        Внутренний отчёт качества ML-модели: постановка цели, метрики, рабочие пороги,
        calibration buckets и feature importance. Используется для настройки сигналов, а не как торговая рекомендация.
      </p>
      <nav>
        <a href="/signals">← Сигналы</a>
        <a href="/signals/ml/status">ML status JSON</a>
        <a href="/signals/ml/report">ML report JSON</a>
        <button class="button primary" onclick="loadReport()">Обновить отчёт</button>
      </nav>
    </div>
  </header>

  <main>
    <div id="status" class="empty">Загружаю ML-отчёт...</div>

    <section class="cards" id="cards" style="display:none;">
      <div class="card">
        <div class="label">Model target</div>
        <div class="value" id="modelTarget">—</div>
        <div class="hint" id="modelTargetHint">—</div>
      </div>
      <div class="card">
        <div class="label">Calibrated AUC</div>
        <div class="value" id="modelAuc">—</div>
        <div class="hint">Качество ранжирования на evaluation-срезе</div>
      </div>
      <div class="card">
        <div class="label">Best lift</div>
        <div class="value" id="bestLift">—</div>
        <div class="hint" id="bestLiftHint">—</div>
      </div>
      <div class="card">
        <div class="label">Recommendation</div>
        <div class="value" id="recommendationLevel">—</div>
        <div class="hint" id="recommendationUsage">—</div>
      </div>
    </section>

    <div class="grid" id="contentGrid" style="display:none;">
      <div>
        <section class="panel">
          <h2>Рекомендация по использованию ML</h2>
          <div id="recommendationBox" class="recommendation"></div>
        </section>

        <section class="panel">
          <h2>Threshold report</h2>
          <div id="thresholdTable"></div>
        </section>

        <section class="panel">
          <h2>Calibration report</h2>
          <div id="calibrationTable"></div>
        </section>
      </div>

      <aside>
        <section class="panel">
          <h2>Модель</h2>
          <div id="modelDetails"></div>
        </section>

        <section class="panel">
          <h2>Feature importance</h2>
          <div id="featureImportance"></div>
        </section>
      </aside>
    </div>
  </main>

  <script>
    function fmtPct(value, digits = 2) {
      const num = Number(value);
      if (!Number.isFinite(num)) return "—";
      return `${num.toFixed(digits)}%`;
    }

    function fmtNum(value, digits = 4) {
      const num = Number(value);
      if (!Number.isFinite(num)) return "—";
      return num.toFixed(digits);
    }

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function badgeClass(level) {
      if (level === "useful_ranker") return "good";
      if (level === "limited") return "warn";
      if (level === "weak" || level === "not_trained") return "bad";
      return "";
    }

    function renderTable(rows, columns) {
      if (!rows || !rows.length) {
        return `<div class="empty">Нет данных.</div>`;
      }

      return `
        <table>
          <thead>
            <tr>${columns.map(col => `<th>${escapeHtml(col.label)}</th>`).join("")}</tr>
          </thead>
          <tbody>
            ${rows.map(row => `
              <tr>
                ${columns.map(col => `<td>${col.render ? col.render(row) : escapeHtml(row[col.key])}</td>`).join("")}
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;
    }

    function renderReport(data) {
      const status = document.getElementById("status");
      const cards = document.getElementById("cards");
      const grid = document.getElementById("contentGrid");

      status.style.display = "none";
      cards.style.display = "grid";
      grid.style.display = "grid";

      const model = data.model || {};
      const evaluation = data.evaluation || {};
      const metrics = evaluation.metrics || {};
      const testPeriod = evaluation.test_period || {};
      const best = data.best_threshold || {};
      const recommendation = data.recommendation || {};

      document.getElementById("modelTarget").textContent =
        `+${fmtPct(Number(model.target_pct || 0) * 100, 1)}`;
      document.getElementById("modelTargetHint").textContent =
        `stop -${fmtPct(Number(model.stop_pct || 0) * 100, 1)} · horizon ${model.horizon || "—"} дней`;

      document.getElementById("modelAuc").textContent = fmtNum(metrics.calibrated_auc, 4);
      document.getElementById("bestLift").textContent = fmtPct(best.lift_vs_base_pct, 2);
      document.getElementById("bestLiftHint").textContent =
        `threshold ${fmtPct(best.threshold_pct, 1)} · hit rate ${fmtPct(best.hit_rate_pct, 2)}`;

      document.getElementById("recommendationLevel").innerHTML =
        `<span class="badge ${badgeClass(recommendation.level)}">${escapeHtml(recommendation.level || "—")}</span>`;
      document.getElementById("recommendationUsage").textContent =
        recommendation.consumer_usage || "—";

      const recBox = document.getElementById("recommendationBox");
      recBox.className = `recommendation ${badgeClass(recommendation.level)}`;
      recBox.innerHTML = `
        <div><b>${escapeHtml(recommendation.title || "Нет рекомендации")}</b></div>
        <div style="margin-top:8px;">${escapeHtml(recommendation.summary || "")}</div>
        <div class="hint" style="margin-top:10px;">
          Base rate: ${fmtPct(recommendation.base_rate_pct, 2)} ·
          AUC: ${fmtNum(recommendation.calibrated_auc, 4)} ·
          Brier: ${fmtNum(recommendation.calibrated_brier, 4)}
        </div>
      `;

      document.getElementById("modelDetails").innerHTML = `
        <table>
          <tbody>
            <tr><th>Target</th><td>${fmtPct(Number(model.target_pct || 0) * 100, 2)}</td></tr>
            <tr><th>Stop</th><td>${fmtPct(Number(model.stop_pct || 0) * 100, 2)}</td></tr>
            <tr><th>Horizon</th><td>${escapeHtml(model.horizon || "—")} дней</td></tr>
            <tr><th>Feature set</th><td class="mono">${escapeHtml(model.feature_set || "—")}</td></tr>
            <tr><th>Feature count</th><td>${escapeHtml(model.feature_count || "—")}</td></tr>
            <tr><th>Trained at</th><td class="mono">${escapeHtml(model.trained_at || "—")}</td></tr>
            <tr><th>Test period</th><td>${escapeHtml(testPeriod.first_date || "—")} → ${escapeHtml(testPeriod.last_date || "—")}</td></tr>
            <tr><th>Positive rate</th><td>${fmtPct(testPeriod.positive_rate_pct, 2)}</td></tr>
          </tbody>
        </table>
      `;

      document.getElementById("thresholdTable").innerHTML = renderTable(
        evaluation.threshold_report || [],
        [
          { label: "Threshold", render: row => fmtPct(row.threshold_pct, 1) },
          { label: "Signals", render: row => escapeHtml(row.signals ?? "—") },
          { label: "Hit rate", render: row => fmtPct(row.hit_rate_pct, 2) },
          { label: "Avg probability", render: row => fmtPct(row.avg_probability_pct, 2) },
          { label: "Coverage", render: row => fmtPct(row.coverage_pct, 2) },
        ]
      );

      document.getElementById("calibrationTable").innerHTML = renderTable(
        evaluation.calibration_report || [],
        [
          { label: "Bucket", render: row => escapeHtml(row.bucket || "—") },
          { label: "Count", render: row => escapeHtml(row.count ?? "—") },
          { label: "Avg probability", render: row => fmtPct(row.avg_probability_pct, 2) },
          { label: "Hit rate", render: row => fmtPct(row.hit_rate_pct, 2) },
          { label: "Error", render: row => fmtPct(row.calibration_error_pct, 2) },
        ]
      );

      const features = (evaluation.feature_importance || []).slice(0, 15);
      document.getElementById("featureImportance").innerHTML = features.length
        ? features.map(item => {
            const value = Number(item.importance || 0);
            return `
              <div style="margin-bottom:13px;">
                <div style="display:flex;justify-content:space-between;gap:10px;">
                  <b class="mono">${escapeHtml(item.feature)}</b>
                  <span>${fmtNum(value, 4)}</span>
                </div>
                <div class="bar-wrap"><div class="bar" style="width:${Math.max(2, Math.min(100, value * 100))}%"></div></div>
              </div>
            `;
          }).join("")
        : `<div class="empty">Feature importance недоступен.</div>`;
    }

    async function loadReport() {
      const status = document.getElementById("status");
      status.style.display = "block";
      status.textContent = "Загружаю ML-отчёт...";

      try {
        const response = await fetch("/signals/ml/report?max_samples=12000");
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        renderReport(data);
      } catch (error) {
        status.style.display = "block";
        status.textContent = `Не удалось загрузить ML-отчёт: ${error.message}`;
      }
    }

    loadReport();
  </script>
</body>
</html>"""
