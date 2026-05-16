from __future__ import annotations


def build_ticker_page_html(ticker: str) -> str:
    ticker = ticker.upper().strip()

    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <title>{ticker} · Тикер</title>
  <style>
    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #eef0f3;
      color: #111827;
    }}

    header {{
      background: #111827;
      color: #fff;
      padding: 42px 32px;
    }}

    header h1 {{
      margin: 0 0 12px;
      font-size: 34px;
    }}

    header a {{
      color: #93c5fd;
      text-decoration: none;
      font-weight: 700;
    }}

    main {{
      padding: 28px 32px;
    }}

    .card {{
      background: #fff;
      border-radius: 18px;
      padding: 24px;
      margin-bottom: 22px;
      box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
    }}

    .muted {{
      color: #64748b;
    }}

    .metrics {{
      display: grid;
      grid-template-columns: repeat(4, minmax(160px, 1fr));
      gap: 14px;
      margin-top: 16px;
    }}

    .metric {{
      background: #f8fafc;
      border-radius: 14px;
      padding: 14px;
    }}

    .metric .label {{
      color: #64748b;
      font-size: 13px;
      font-weight: 700;
    }}

    .metric .value {{
      font-size: 24px;
      font-weight: 850;
      margin-top: 6px;
    }}

    .good {{
      color: #15803d;
      font-weight: 800;
    }}

    .bad {{
      color: #dc2626;
      font-weight: 800;
    }}

    .grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 22px;
    }}

    svg {{
      width: 100%;
      height: 320px;
      background: #f8fafc;
      border-radius: 16px;
      margin-top: 14px;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 14px;
    }}

    th, td {{
      text-align: left;
      border-bottom: 1px solid #e5e7eb;
      padding: 10px;
      vertical-align: top;
    }}

    th {{
      color: #64748b;
      font-size: 13px;
    }}

    .button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 38px;
      border-radius: 10px;
      padding: 10px 14px;
      background: #2563eb;
      color: #fff;
      text-decoration: none;
      font-weight: 800;
      border: 0;
      cursor: pointer;
      margin-right: 8px;
    }}

    .button.secondary {{
      background: #334155;
    }}

    .forecast-card {{
      border: 1px solid #dbeafe;
      background: linear-gradient(135deg, #ffffff, #f8fbff);
    }}

    .forecast-grid {{
      display: grid;
      grid-template-columns: 1.3fr 1fr 1fr 1fr;
      gap: 14px;
      margin-top: 16px;
    }}

    .forecast-pill {{
      display: inline-flex;
      border-radius: 999px;
      padding: 6px 10px;
      font-size: 13px;
      font-weight: 850;
      background: #eef2ff;
      color: #3730a3;
    }}

    .forecast-pill.positive {{ background: #dcfce7; color: #166534; }}
    .forecast-pill.neutral {{ background: #f1f5f9; color: #334155; }}
    .forecast-pill.negative {{ background: #fee2e2; color: #991b1b; }}

    .forecast-value {{
      font-size: 30px;
      font-weight: 950;
      margin-top: 6px;
      letter-spacing: -0.04em;
    }}

    .forecast-explanation {{
      display: none;
      margin-top: 16px;
      border-top: 1px solid #e5e7eb;
      padding-top: 16px;
    }}

    .explanation-grid {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 14px;
    }}

    .explanation-box {{
      background: #f8fafc;
      border: 1px solid #e5e7eb;
      border-radius: 14px;
      padding: 14px;
    }}

    .explanation-box h4 {{ margin: 0 0 8px; }}
    .explanation-box ul {{ margin: 0; padding-left: 18px; color: #475569; }}

    @media (max-width: 900px) {{
      .metrics,
      .grid,
      .forecast-grid,
      .explanation-grid {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <h1 id="pageTitle">{ticker}</h1>
    <nav>
      <a href="/dashboard">← Рынок</a> ·
      <a href="/ai/report/demo">AI Report</a> ·
      <a href="/ai/reports/dashboard">История отчётов</a>
    </nav>
  </header>

  <main>
    <section class="card">
      <h2>Сводка по тикеру</h2>
      <p class="muted" id="status">Загружаю данные...</p>

      <div class="metrics">
        <div class="metric">
          <div class="label">Цена</div>
          <div class="value" id="lastPrice">—</div>
        </div>
        <div class="metric">
          <div class="label">Изменение</div>
          <div class="value" id="change">—</div>
        </div>
        <div class="metric">
          <div class="label">Оборот</div>
          <div class="value" id="turnover">—</div>
        </div>
        <div class="metric">
          <div class="label">Последняя дата</div>
          <div class="value" id="tradeDate">—</div>
        </div>
      </div>

      <p style="margin-top:18px;">
        <button class="button" onclick="loadTicker()">Обновить</button>
        <a class="button secondary" href="/tickers/{ticker}/data">JSON</a>
      </p>
    </section>

    <section class="card forecast-card">
      <h2>Сводный прогноз</h2>
      <p class="muted" id="forecastSubtitle">Прогноз строится автоматически по цене, объёму, технической картине и доступным событиям.</p>

      <div class="forecast-grid">
        <div class="metric">
          <div class="label">Рекомендация</div>
          <div class="forecast-value"><span id="forecastRecommendation" class="forecast-pill neutral">—</span></div>
        </div>
        <div class="metric">
          <div class="label">Вероятность достижения цели</div>
          <div class="forecast-value" id="forecastProbability">—</div>
        </div>
        <div class="metric">
          <div class="label">Прогнозная цена</div>
          <div class="forecast-value" id="forecastPrice">—</div>
        </div>
        <div class="metric">
          <div class="label">Диапазон</div>
          <div class="forecast-value" id="forecastRange">—</div>
        </div>
      </div>

      <div class="metrics">
        <div class="metric">
          <div class="label">Потенциал</div>
          <div class="value" id="forecastPotential">—</div>
        </div>
        <div class="metric">
          <div class="label">Целевая цена</div>
          <div class="value" id="forecastTarget">—</div>
        </div>
        <div class="metric">
          <div class="label">Горизонт</div>
          <div class="value" id="forecastHorizon">—</div>
        </div>
        <div class="metric">
          <div class="label">Уровень пересмотра</div>
          <div class="value" id="forecastStop">—</div>
        </div>
      </div>

      <p style="margin-top:18px;">
        <button class="button" onclick="toggleForecastExplanation()">Почему такой прогноз?</button>
      </p>

      <div id="forecastExplanation" class="forecast-explanation">
        <p class="muted" id="forecastExplanationSummary">—</p>
        <div class="explanation-grid">
          <div class="explanation-box"><h4>Техническая картина</h4><ul id="forecastTechnical"><li>—</li></ul></div>
          <div class="explanation-box"><h4>Новости и события</h4><ul id="forecastNews"><li>—</li></ul></div>
          <div class="explanation-box"><h4>Риски</h4><ul id="forecastRisks"><li>—</li></ul></div>
        </div>
      </div>
    </section>


    <section class="card">
      <h2>Что влияет на прогноз</h2>

      <div class="metrics">
        <div class="metric">
          <div class="label">Тренд</div>
          <div class="value" id="technicalTrend">—</div>
        </div>
        <div class="metric">
          <div class="label">SMA 20</div>
          <div class="value" id="sma20">—</div>
        </div>
        <div class="metric">
          <div class="label">SMA 50</div>
          <div class="value" id="sma50">—</div>
        </div>
        <div class="metric">
          <div class="label">Волатильность 20 свечей</div>
          <div class="value" id="volatility20d">—</div>
        </div>
      </div>

      <div class="metrics">
        <div class="metric">
          <div class="label">Доходность 1 свеча</div>
          <div class="value" id="return1d">—</div>
        </div>
        <div class="metric">
          <div class="label">Доходность 5 свечей</div>
          <div class="value" id="return5d">—</div>
        </div>
        <div class="metric">
          <div class="label">Доходность 20 свечей</div>
          <div class="value" id="return20d">—</div>
        </div>
        <div class="metric">
          <div class="label">Объём / средний объём</div>
          <div class="value" id="volumeRatio">—</div>
        </div>
      </div>

      <p class="muted" id="technicalSummary" style="margin-top:18px;">—</p>
    </section>


    <section class="card">
      <h2>Технические детали сценария</h2>

      <div class="metrics">
        <div class="metric">
          <div class="label">Сценарий</div>
          <div class="value" id="signalAction">—</div>
        </div>
        <div class="metric">
          <div class="label">Уверенность</div>
          <div class="value" id="signalConfidence">—</div>
        </div>
        <div class="metric">
          <div class="label">Риск</div>
          <div class="value" id="signalRisk">—</div>
        </div>
        <div class="metric">
          <div class="label">Горизонт</div>
          <div class="value" id="signalHorizon">—</div>
        </div>
      </div>

      <div class="metrics">
        <div class="metric">
          <div class="label">Цена входа / условие</div>
          <div class="value" id="signalEntry">—</div>
        </div>
        <div class="metric">
          <div class="label">Цель</div>
          <div class="value" id="signalTarget">—</div>
        </div>
        <div class="metric">
          <div class="label">Стоп / отмена сценария</div>
          <div class="value" id="signalStop">—</div>
        </div>
        <div class="metric">
          <div class="label">Последний диапазон</div>
          <div class="value" id="signalRange">—</div>
        </div>
      </div>

      <p class="muted" id="signalSummary" style="margin-top:18px;">—</p>

      <h3>Факторы сигнала</h3>
      <ul id="signalReasons">
        <li>—</li>
      </ul>

      <p class="muted" id="signalDisclaimer">—</p>
    </section>

    <section class="grid">
      <div class="card">
        <h2>Цена</h2>
        <svg id="priceChart" viewBox="0 0 900 320" preserveAspectRatio="none"></svg>
      </div>

      <div class="card">
        <h2>Объём</h2>
        <svg id="volumeChart" viewBox="0 0 900 320" preserveAspectRatio="none"></svg>
      </div>
    </section>

    <section class="card">
      <h2>Последние свечи</h2>
      <table>
        <thead>
          <tr>
            <th>Дата</th>
            <th>Open</th>
            <th>High</th>
            <th>Low</th>
            <th>Close</th>
            <th>Изм.</th>
            <th>Объём</th>
            <th>Оборот</th>
          </tr>
        </thead>
        <tbody id="candlesRows">
          <tr><td colspan="8">Загрузка...</td></tr>
        </tbody>
      </table>
    </section>
  </main>

  <script>
    const ticker = "{ticker}";
    let refreshTimer = null;

    function formatNumber(value, digits = 2) {{
      if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";

      return Number(value).toLocaleString("ru-RU", {{
        minimumFractionDigits: digits,
        maximumFractionDigits: digits
      }});
    }}

    function formatRub(value) {{
      if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";

      return Number(value).toLocaleString("ru-RU", {{
        minimumFractionDigits: 1,
        maximumFractionDigits: 1
      }}) + " руб.";
    }}

    function formatPct(value) {{
      if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";

      return Number(value).toLocaleString("ru-RU", {{
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      }}) + "%";
    }}

    function valueClass(value) {{
      const n = Number(value);

      if (Number.isNaN(n) || n === 0) return "";

      return n > 0 ? "good" : "bad";
    }}

    function setText(id, value) {{
      document.getElementById(id).textContent =
        value === null || value === undefined || value === "" ? "—" : value;
    }}

    function drawLineChart(svgId, rows, field, labelFormatter) {{
      const svg = document.getElementById(svgId);
      svg.innerHTML = "";

      const data = rows
        .filter(row => row[field] !== null && row[field] !== undefined && !Number.isNaN(Number(row[field])))
        .slice(-120);

      if (data.length < 2) {{
        svg.innerHTML = '<text x="30" y="50" fill="#64748b">Недостаточно данных</text>';
        return;
      }}

      const width = 900;
      const height = 320;
      const pad = 42;

      const values = data.map(row => Number(row[field]));
      const min = Math.min(...values);
      const max = Math.max(...values);
      const range = max - min || 1;

      const points = data.map((row, index) => {{
        const x = pad + index * ((width - pad * 2) / (data.length - 1));
        const y = height - pad - ((Number(row[field]) - min) / range) * (height - pad * 2);

        return {{x, y, row}};
      }});

      const polyline = points.map(p => `${{p.x}},${{p.y}}`).join(" ");

      svg.innerHTML = `
        <line x1="${{pad}}" y1="${{pad}}" x2="${{pad}}" y2="${{height - pad}}" stroke="#cbd5e1" />
        <line x1="${{pad}}" y1="${{height - pad}}" x2="${{width - pad}}" y2="${{height - pad}}" stroke="#cbd5e1" />

        <text x="${{pad}}" y="24" fill="#64748b" font-size="13">${{labelFormatter(max)}}</text>
        <text x="${{pad}}" y="${{height - 10}}" fill="#64748b" font-size="13">${{labelFormatter(min)}}</text>

        <polyline points="${{polyline}}" fill="none" stroke="#2563eb" stroke-width="4" />

        ${{points.map(p => `
          <circle cx="${{p.x}}" cy="${{p.y}}" r="4" fill="#2563eb">
            <title>${{p.row.trade_date}}: ${{labelFormatter(p.row[field])}}</title>
          </circle>
        `).join("")}}
      `;
    }}

    function renderCandles(candles) {{
      const recent = candles.slice(-20).reverse();

      document.getElementById("candlesRows").innerHTML = recent.map(row => `
        <tr>
          <td>${{row.trade_date || "—"}}</td>
          <td>${{formatNumber(row.open)}}</td>
          <td>${{formatNumber(row.high)}}</td>
          <td>${{formatNumber(row.low)}}</td>
          <td><b>${{formatNumber(row.close)}}</b></td>
          <td class="${{valueClass(row.change_pct)}}">${{formatPct(row.change_pct)}}</td>
          <td>${{formatNumber(row.volume, 0)}}</td>
          <td>${{formatRub(row.value_rub)}}</td>
        </tr>
      `).join("");
    }}


    function escapeHtml(value) {{
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }}

    function forecastToneClass(tone) {{
      if (tone === "positive") return "positive";
      if (tone === "negative") return "negative";
      return "neutral";
    }}

    function listHtml(items) {{
      return (items || []).map(item => `<li>${{escapeHtml(item)}}</li>`).join("") || "<li>Факторы не выделены.</li>";
    }}

    function toggleForecastExplanation() {{
      const box = document.getElementById("forecastExplanation");
      if (!box) return;
      box.style.display = box.style.display === "block" ? "none" : "block";
    }}

    function renderForecast(data) {{
      const forecast = (data || {{}}).forecast || {{}};
      const explanation = forecast.explanation || {{}};
      const range = forecast.forecast_range || {{}};
      const rec = document.getElementById("forecastRecommendation");

      if (rec) {{
        rec.textContent = forecast.recommendation || "—";
        rec.className = "forecast-pill " + forecastToneClass(forecast.recommendation_tone);
      }}

      setText("forecastProbability", forecast.target_probability_pct ? formatPct(forecast.target_probability_pct) : "—");
      setText("forecastPrice", formatRub(forecast.forecast_price));
      setText("forecastRange", range.low && range.high ? `${{formatRub(range.low)}} — ${{formatRub(range.high)}}` : "—");
      setText("forecastPotential", `${{formatRub(forecast.potential_abs)}} / ${{formatPct(forecast.potential_pct)}}`);
      setText("forecastTarget", formatRub(forecast.target_price));
      setText("forecastHorizon", forecast.horizon);
      setText("forecastStop", formatRub(forecast.stop_loss));
      setText("forecastExplanationSummary", explanation.summary);
      document.getElementById("forecastTechnical").innerHTML = listHtml(explanation.technical);
      document.getElementById("forecastNews").innerHTML = listHtml(explanation.news);
      document.getElementById("forecastRisks").innerHTML = listHtml(explanation.risks);
    }}

    async function loadForecast() {{
      const response = await fetch(`/signals/consumer/${{ticker}}.json?candles_limit=240`);
      if (!response.ok) {{
        throw new Error("Forecast HTTP " + response.status + ": " + await response.text());
      }}
      const data = await response.json();
      renderForecast(data);
    }}

    function renderTicker(data) {{
      const latest = data.latest || {{}};
      const instrument = data.instrument || {{}};
      const technical = data.technical || {{}};
      const signal = data.signal || {{}};
      const candles = data.candles || [];

      document.title = `${{data.ticker}} · ${{instrument.name || data.ticker}}`;
      setText("pageTitle", `${{data.ticker}} · ${{instrument.name || data.ticker}}`);

      setText("lastPrice", formatNumber(latest.close));
      setText("turnover", formatRub(latest.value_rub));
      setText("tradeDate", latest.trade_date);

      setText("technicalTrend", technical.trend);
      setText("sma20", formatNumber(technical.sma_20));
      setText("sma50", formatNumber(technical.sma_50));
      setText("volatility20d", formatPct(technical.volatility_20d_pct));
      setText("return1d", formatPct(technical.return_1d_pct));
      setText("return5d", formatPct(technical.return_5d_pct));
      setText("return20d", formatPct(technical.return_20d_pct));
      setText("volumeRatio", technical.volume_ratio ? technical.volume_ratio + "x" : "—");
      setText("technicalSummary", technical.summary);

      setText("signalAction", signal.label || signal.action);
      setText("signalConfidence", signal.confidence_pct ? signal.confidence_pct + "%" : "—");
      setText("signalRisk", signal.risk_level);
      setText("signalHorizon", signal.horizon);
      setText("signalEntry", signal.entry_price ? formatNumber(signal.entry_price) : "—");
      setText("signalTarget", signal.target_price ? formatNumber(signal.target_price) : "—");
      setText("signalStop", signal.stop_loss ? formatNumber(signal.stop_loss) : "—");

      const rangeText = signal.recent_low && signal.recent_high
        ? formatNumber(signal.recent_low) + "—" + formatNumber(signal.recent_high)
        : "—";
      setText("signalRange", rangeText);

      setText("signalSummary", signal.summary);
      setText("signalDisclaimer", signal.disclaimer);

      const reasons = signal.reasons || [];
      document.getElementById("signalReasons").innerHTML = reasons.length
        ? reasons.map(reason => `<li>${{reason}}</li>`).join("")
        : "<li>Нет факторов.</li>";

      const changeText = `${{formatNumber(latest.change_abs)}} / ${{formatPct(latest.change_pct)}}`;
      const changeEl = document.getElementById("change");
      changeEl.textContent = changeText;
      changeEl.className = "value " + valueClass(latest.change_pct);

      drawLineChart("priceChart", candles, "close", value => formatNumber(value));
      drawLineChart("volumeChart", candles, "volume", value => formatNumber(value, 0));

      renderCandles(candles);

      const now = new Date().toLocaleTimeString("ru-RU");
      setText(
        "status",
        `Свечей: ${{data.candles_count}}. Автообновление каждые ${{data.auto_refresh_seconds}} сек. Последнее обновление: ${{now}}.`
      );
    }}

    async function loadTicker() {{
      const response = await fetch(`/tickers/${{ticker}}/data?limit=240`);

      if (!response.ok) {{
        throw new Error("HTTP " + response.status + ": " + await response.text());
      }}

      const data = await response.json();
      renderTicker(data);
      loadForecast().catch(error => {{
        setText("forecastSubtitle", "Не удалось загрузить прогноз: " + error.message);
      }});
    }}

    function startAutoRefresh() {{
      if (refreshTimer) {{
        clearInterval(refreshTimer);
      }}

      refreshTimer = setInterval(() => {{
        loadTicker().catch(error => {{
          setText("status", "Ошибка автообновления: " + error.message);
        }});
      }}, 60 * 1000);
    }}

    window.loadTicker = loadTicker;
    window.toggleForecastExplanation = toggleForecastExplanation;

    loadTicker()
      .then(startAutoRefresh)
      .catch(error => {{
        setText("status", "Ошибка загрузки: " + error.message);
      }});
  </script>
</body>
</html>"""
