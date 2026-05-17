from __future__ import annotations

import html


def build_ticker_page_html(ticker: str) -> str:
    safe_ticker = html.escape((ticker or "").upper().strip())

    page = """<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <title>__TICKER__ — прогноз</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root {
      --bg: #f4f6fb;
      --surface: #ffffff;
      --surface-2: #f8fafc;
      --text: #101828;
      --muted: #667085;
      --border: #e4e7ec;
      --accent: #3157ff;
      --accent-2: #14213d;
      --accent-soft: rgba(49, 87, 255, 0.10);
      --good: #039855;
      --good-bg: #ecfdf3;
      --bad: #d92d20;
      --bad-bg: #fef3f2;
      --warn: #dc6803;
      --warn-bg: #fffaeb;
      --shadow: 0 20px 50px rgba(16, 24, 40, 0.08);
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      color: var(--text);
      background:
        radial-gradient(circle at 15% 0%, rgba(49, 87, 255, 0.08), transparent 28%),
        radial-gradient(circle at 90% 8%, rgba(20, 33, 61, 0.08), transparent 24%),
        var(--bg);
      font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
    }

    a { color: inherit; text-decoration: none; }

    .topbar {
      height: 72px;
      background: rgba(255, 255, 255, 0.84);
      border-bottom: 1px solid var(--border);
      backdrop-filter: blur(14px);
      position: sticky;
      top: 0;
      z-index: 50;
    }

    .topbar-inner {
      width: min(1200px, calc(100% - 32px));
      height: 100%;
      margin: 0 auto;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 24px;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 18px;
      font-weight: 950;
      letter-spacing: -0.03em;
    }

    .brand-mark {
      width: 36px;
      height: 36px;
      border-radius: 12px;
      display: grid;
      place-items: center;
      color: white;
      background: linear-gradient(135deg, var(--accent), var(--accent-2));
      box-shadow: 0 10px 24px rgba(49, 87, 255, 0.22);
      font-weight: 950;
    }

    .nav {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .nav a {
      padding: 10px 14px;
      border-radius: 999px;
      color: var(--muted);
      font-weight: 800;
      font-size: 14px;
    }

    .nav a.active {
      color: var(--accent);
      background: var(--accent-soft);
    }

    .wrap {
      width: min(1200px, calc(100% - 32px));
      margin: 0 auto;
      padding: 26px 0 64px;
    }

    .layout {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 330px;
      gap: 28px;
      align-items: start;
    }

    .main-col { min-width: 0; }

    .side-col {
      position: sticky;
      top: 96px;
    }

    .hero-card {
      position: relative;
      overflow: hidden;
      min-height: 210px;
      border-radius: 30px;
      padding: 30px;
      color: white;
      background:
        radial-gradient(circle at 85% 28%, rgba(255,255,255,0.28), transparent 16%),
        linear-gradient(135deg, var(--accent), var(--accent-2));
      box-shadow: var(--shadow);
    }

    .hero-card::after {
      content: "";
      position: absolute;
      width: 280px;
      height: 280px;
      border-radius: 50%;
      right: -90px;
      bottom: -140px;
      background: rgba(255,255,255,0.12);
    }

    .hero-content {
      position: relative;
      z-index: 2;
      display: flex;
      justify-content: space-between;
      gap: 24px;
    }

    .ticker-title {
      font-size: 34px;
      line-height: 1.04;
      max-width: 680px;
      font-weight: 950;
      letter-spacing: -0.06em;
    }

    .ticker-code {
      opacity: 0.72;
      font-size: 15px;
      font-weight: 850;
      margin-left: 8px;
      letter-spacing: 0;
      white-space: nowrap;
    }

    .hero-meta {
      display: grid;
      grid-template-columns: repeat(3, minmax(120px, 1fr));
      gap: 18px;
      margin-top: 36px;
      max-width: 680px;
    }

    .hero-meta .label {
      opacity: 0.72;
      font-size: 13px;
      margin-bottom: 8px;
      font-weight: 750;
    }

    .hero-meta .value {
      font-size: 21px;
      font-weight: 950;
      letter-spacing: -0.03em;
    }

    .logo-token {
      flex: 0 0 auto;
      width: 106px;
      height: 106px;
      border-radius: 28px;
      display: grid;
      place-items: center;
      background: rgba(255,255,255,0.92);
      color: var(--accent);
      font-weight: 950;
      font-size: 22px;
      letter-spacing: -0.04em;
      box-shadow: 0 20px 38px rgba(0,0,0,0.14);
    }

    .subnav {
      display: flex;
      gap: 10px;
      margin: 16px 0 0;
      flex-wrap: wrap;
    }

    .subnav button {
      border: 1px solid var(--border);
      background: white;
      color: var(--muted);
      border-radius: 999px;
      padding: 10px 14px;
      font-weight: 850;
      cursor: pointer;
    }

    .subnav button.active {
      color: var(--accent);
      border-color: rgba(49, 87, 255, 0.28);
      background: var(--accent-soft);
    }

    .panel {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 28px;
      box-shadow: 0 12px 38px rgba(16, 24, 40, 0.06);
      padding: 24px;
      margin-top: 18px;
    }

    .chart-toolbar {
      display: flex;
      justify-content: space-between;
      gap: 14px;
      flex-wrap: wrap;
      margin-bottom: 16px;
    }

    .periods, .chart-actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }

    .chip {
      border: 1px solid var(--border);
      background: white;
      color: var(--muted);
      border-radius: 12px;
      min-height: 38px;
      padding: 0 13px;
      font-weight: 850;
      cursor: pointer;
    }

    .chip.active {
      color: var(--accent);
      border-color: rgba(49, 87, 255, 0.35);
      background: var(--accent-soft);
    }

    .chart-box {
      position: relative;
      height: 360px;
      border-radius: 22px;
      background:
        linear-gradient(to bottom, rgba(148, 163, 184, 0.10), transparent),
        #fff;
      border: 1px solid var(--border);
      overflow: hidden;
    }

    .chart-container {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
    }

    .chart-tooltip {
      position: absolute;
      display: none;
      z-index: 5;
      min-width: 190px;
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 10px 12px;
      background: rgba(255, 255, 255, 0.96);
      box-shadow: 0 12px 30px rgba(16, 24, 40, 0.14);
      color: var(--text);
      font-size: 12px;
      line-height: 1.45;
      pointer-events: none;
      backdrop-filter: blur(10px);
    }

    .chart-tooltip b {
      display: block;
      font-size: 13px;
      margin-bottom: 5px;
    }

    .chart-empty {
      position: absolute;
      inset: 0;
      display: none;
      align-items: center;
      justify-content: center;
      text-align: center;
      color: var(--muted);
      padding: 24px;
      font-weight: 800;
    }

    .price-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 28px;
      padding: 24px;
      box-shadow: var(--shadow);
    }

    .price-caption {
      color: var(--muted);
      font-size: 13px;
      font-weight: 800;
      margin-bottom: 10px;
    }

    .side-price {
      font-size: 34px;
      font-weight: 950;
      letter-spacing: -0.06em;
      margin-bottom: 10px;
    }

    .side-change {
      font-size: 15px;
      font-weight: 900;
      margin-bottom: 22px;
    }

    .cta {
      width: 100%;
      min-height: 48px;
      border: 0;
      border-radius: 16px;
      background: linear-gradient(135deg, var(--accent), var(--accent-2));
      color: white;
      font-weight: 950;
      cursor: pointer;
      box-shadow: 0 14px 28px rgba(49, 87, 255, 0.22);
    }

    .watchlist {
      width: 100%;
      min-height: 44px;
      margin-top: 10px;
      border: 1px solid var(--border);
      border-radius: 16px;
      background: white;
      color: var(--text);
      font-weight: 900;
      cursor: pointer;
    }

    .section {
      margin-top: 26px;
    }

    .section h2 {
      margin: 0 0 14px;
      font-size: 25px;
      letter-spacing: -0.04em;
    }

    .about {
      color: #344054;
      line-height: 1.66;
      font-size: 16px;
    }

    .forecast-grid {
      display: grid;
      grid-template-columns: 1.1fr 0.9fr 1fr 1fr;
      gap: 12px;
      align-items: stretch;
    }

    .forecast-cell {
      background: var(--surface-2);
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 16px;
    }

    .forecast-cell .label {
      color: var(--muted);
      font-size: 13px;
      font-weight: 850;
      margin-bottom: 8px;
    }

    .forecast-cell .value {
      font-size: 22px;
      font-weight: 950;
      letter-spacing: -0.04em;
    }

    .rec-pill {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 42px;
      padding: 10px 14px;
      border-radius: 999px;
      font-weight: 950;
      background: var(--accent-soft);
      color: var(--accent);
    }

    .rec-pill.negative {
      background: var(--bad-bg);
      color: #991b1b;
    }

    .rec-pill.positive {
      background: var(--good-bg);
      color: #027a48;
    }

    .rec-pill.neutral {
      background: #eef2ff;
      color: #3538cd;
    }

    .buttons {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-top: 14px;
    }

    .btn {
      min-height: 42px;
      padding: 0 16px;
      border-radius: 14px;
      border: 1px solid var(--border);
      background: white;
      color: var(--text);
      font-weight: 900;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }

    .btn.primary {
      background: var(--accent-soft);
      border-color: rgba(49, 87, 255, 0.22);
      color: var(--accent);
    }

    .explanation {
      display: none;
      margin-top: 14px;
      padding: 18px;
      border: 1px solid var(--border);
      border-radius: 20px;
      background: #fff;
      color: #344054;
      line-height: 1.55;
    }

    .explanation h3 {
      margin: 14px 0 8px;
      font-size: 16px;
    }

    .explanation ul {
      margin: 8px 0 0 20px;
      padding: 0;
    }

    .stats-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
    }

    .stat-row {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      border-bottom: 1px solid var(--border);
      padding: 15px 0;
      color: var(--muted);
    }

    .stat-row b {
      color: var(--text);
    }

    .notice {
      display: none;
      margin-bottom: 14px;
      border-radius: 18px;
      padding: 14px 16px;
      background: var(--warn-bg);
      color: #93370d;
      font-weight: 800;
      line-height: 1.45;
    }

    .positive { color: var(--good); }
    .negative { color: var(--bad); }
    .muted { color: var(--muted); }

    @media (max-width: 1020px) {
      .layout { grid-template-columns: 1fr; }
      .side-col { position: static; order: -1; }
      .forecast-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .hero-meta { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }

    @media (max-width: 640px) {
      .topbar { height: auto; padding: 12px 0; position: static; }
      .topbar-inner { flex-direction: column; align-items: flex-start; }
      .nav { width: 100%; overflow-x: auto; }
      .wrap { width: calc(100% - 20px); padding-top: 14px; }
      .hero-card { border-radius: 22px; padding: 22px; }
      .hero-content { display: block; }
      .ticker-title { font-size: 27px; }
      .logo-token { display: none; }
      .hero-meta { grid-template-columns: 1fr; gap: 14px; }
      .forecast-grid { grid-template-columns: 1fr; }
      .stats-grid { grid-template-columns: 1fr; }
      .chart-box { height: 280px; }
    }
  
    .cta:disabled {
      cursor: not-allowed;
      opacity: 0.55;
      filter: grayscale(0.35);
    }

    .ticker-unavailable-note {
      border: 1px solid rgba(245, 158, 11, 0.22);
      background: rgba(255, 251, 235, 0.9);
      color: #92400e;
      border-radius: 18px;
      padding: 16px 18px;
      font-weight: 800;
      line-height: 1.45;
    }
  </style>
  <script src="https://unpkg.com/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js"></script>
</head>
<body>
  <header class="topbar">
    <div class="topbar-inner">
      <a class="brand" href="/signals">
        <span class="brand-mark">AI</span>
        <span>AI Аналитик рынка</span>
      </a>
      <nav class="nav">
        <a href="/dashboard">Обзор</a>
        <a href="/signals" class="active">Сигналы</a>
        <a href="/portfolio/construct/demo">Портфель</a>
        <a href="/ai/report/demo">AI Report</a>
      </nav>
    </div>
  </header>

  <main class="wrap">
    <div class="layout">
      <section class="main-col">
        <section class="hero-card">
          <div class="hero-content">
            <div>
              <div class="ticker-title">
                <span id="instrumentName">__TICKER__</span>
                <span class="ticker-code" id="tickerCode">__TICKER__</span>
              </div>

              <div class="hero-meta">
                <div>
                  <div class="label">Вероятность цели</div>
                  <div class="value" id="heroProbability">—</div>
                </div>
                <div>
                  <div class="label">Рекомендация</div>
                  <div class="value" id="heroRecommendation">—</div>
                </div>
                <div>
                  <div class="label">Сектор</div>
                  <div class="value" id="heroSector">—</div>
                </div>
              </div>
            </div>

            <div class="logo-token" id="logoToken">__TICKER__</div>
          </div>
        </section>

        <div class="subnav">
          <button class="active" onclick="scrollToBlock('overview')">Обзор</button>
          <button onclick="scrollToBlock('forecast')">Прогноз</button>
          <button onclick="scrollToBlock('stats')">Показатели</button>
          <button onclick="openForecastExplanation()">Почему?</button>
        </div>

        <section class="panel">
          <div class="chart-toolbar">
            <div class="periods">
              <button class="chip" data-period="1D" onclick="setChartPeriod('1D', this)">1Д</button>
              <button class="chip" data-period="1W" onclick="setChartPeriod('1W', this)">1Н</button>
              <button class="chip" data-period="1M" onclick="setChartPeriod('1M', this)">1М</button>
              <button class="chip" data-period="3M" onclick="setChartPeriod('3M', this)">3М</button>
              <button class="chip" data-period="6M" onclick="setChartPeriod('6M', this)">6М</button>
              <button class="chip active" data-period="1Y" onclick="setChartPeriod('1Y', this)">1Г</button>
              <button class="chip" data-period="ALL" onclick="setChartPeriod('ALL', this)">Всё</button>
            </div>
            <div class="chart-actions">
              <button class="chip active" data-chart="line" onclick="setChartType('line', this)">Линия</button>
              <button class="chip" data-chart="candles" onclick="setChartType('candles', this)">Свечи</button>
            </div>
          </div>

          <div class="chart-box">
            <div id="chartContainer" class="chart-container"></div>
            <div id="chartTooltip" class="chart-tooltip"></div>
            <div id="chartEmpty" class="chart-empty">Недостаточно исторических данных для графика</div>
          </div>
        </section>

        <section id="overview" class="section panel">
          <h2 id="aboutTitle">О компании</h2>
          <div class="about" id="aboutText">Загружаю данные...</div>
        </section>

        <section id="forecast" class="section panel">
          <h2>Сводный прогноз</h2>
          <div id="forecastNotice" class="notice"></div>

          <div class="forecast-grid">
            <div class="forecast-cell">
              <div class="label">Прогнозная цена</div>
              <div class="value" id="forecastPrice">—</div>
            </div>
            <div class="forecast-cell">
              <div class="label">Потенциал</div>
              <div class="value" id="forecastPotential">—</div>
            </div>
            <div class="forecast-cell">
              <div class="label">Диапазон</div>
              <div class="value" id="forecastRange">—</div>
            </div>
            <div class="forecast-cell">
              <div class="label">Рекомендация</div>
              <div id="forecastRecommendation" class="rec-pill neutral">—</div>
            </div>
          </div>

          <div class="buttons">
            <button class="btn primary" onclick="toggleForecastExplanation()">Почему такой прогноз?</button>
            <a class="btn" href="/signals">Все сигналы</a>
          </div>

          <div id="forecastExplanation" class="explanation"></div>
        </section>

        <section id="stats" class="section panel">
          <h2>Показатели инструмента</h2>
          <div class="stats-grid">
            <div>
              <div class="stat-row"><span>Цена открытия</span><b id="statOpen">—</b></div>
              <div class="stat-row"><span>Цена закрытия</span><b id="statClose">—</b></div>
              <div class="stat-row"><span>Дневной диапазон</span><b id="statDayRange">—</b></div>
            </div>
            <div>
              <div class="stat-row"><span>Изменение за день</span><b id="statDayChange">—</b></div>
              <div class="stat-row"><span>Изменение за 20 дней</span><b id="stat20Change">—</b></div>
              <div class="stat-row"><span>Горизонт прогноза</span><b id="statHorizon">—</b></div>
            </div>
          </div>
        </section>
      </section>

      <aside class="side-col">
        <section class="price-card">
          <div class="price-caption" id="priceDate">Цена инструмента</div>
          <div class="side-price" id="sidePrice">—</div>
          <div class="side-change" id="sideChange">—</div>
          <button id="portfolioCta" class="cta" onclick="window.location.href='/portfolio/construct/demo'">Добавить в портфель</button>
          <button class="watchlist" onclick="window.location.href='/signals'">Вернуться к сигналам</button>
        </section>
      </aside>
    </div>
  </main>

  <script>
    const TICKER = "__TICKER__";
    let latestPayload = null;
    let allCandles = [];
    let chartPeriod = "1Y";
    let chartType = "line";

    const BRAND_ACCENTS = {
      SBER: ["#159947", "#0b5d35"],
      GAZP: ["#1b75bb", "#0b3d91"],
      LKOH: ["#d71920", "#7f1d1d"],
      ROSN: ["#111827", "#f59e0b"],
      TATN: ["#0f766e", "#064e3b"],
      YNDX: ["#fc3f1d", "#111827"],
      VKCO: ["#2688eb", "#1554b8"],
      OZON: ["#005bff", "#001a72"],
      TCSG: ["#111827", "#facc15"],
      VTBR: ["#0072ce", "#003b75"],
      MOEX: ["#e30613", "#7f1d1d"],
      NVTK: ["#005aaa", "#003a70"],
      GMKN: ["#008c95", "#00545a"],
      PLZL: ["#c99700", "#7c5f00"],
      ALRS: ["#00a3e0", "#005f83"],
      AFLT: ["#0033a0", "#d52b1e"],
      MGNT: ["#e30613", "#b91c1c"],
      FIVE: ["#e0001b", "#8b0011"],
      CHMF: ["#1d4ed8", "#0f172a"],
      NLMK: ["#1e40af", "#0f172a"],
      PHOR: ["#00a651", "#005f2f"],
      RUAL: ["#64748b", "#334155"],
      PAZA: ["#2563eb", "#1e293b"]
    };

    function hashAccent(ticker) {
      let hash = 0;
      for (const char of ticker) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
      const hue = hash % 360;
      return [`hsl(${hue}, 70%, 44%)`, `hsl(${(hue + 26) % 360}, 72%, 26%)`];
    }

    function applyAccent(ticker) {
      const pair = BRAND_ACCENTS[ticker] || hashAccent(ticker);
      document.documentElement.style.setProperty("--accent", pair[0]);
      document.documentElement.style.setProperty("--accent-2", pair[1]);
      document.documentElement.style.setProperty("--accent-soft", `${pair[0]}18`);
    }

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function toNumber(value) {
      const n = Number(value);
      return Number.isNaN(n) ? null : n;
    }

    function setText(id, value) {
      const element = document.getElementById(id);
      if (!element) return;
      element.textContent = value === null || value === undefined || value === "" ? "—" : value;
    }

    function formatNumber(value, digits = 2) {
      const n = toNumber(value);
      if (n === null) return "—";
      return n.toLocaleString("ru-RU", {
        maximumFractionDigits: digits,
        minimumFractionDigits: digits === 0 ? 0 : 0
      });
    }

    function formatRub(value) {
      const n = toNumber(value);
      if (n === null) return "—";
      return `${formatNumber(n)} ₽`;
    }

    function formatPct(value, digits = 1) {
      const n = toNumber(value);
      if (n === null) return "—";
      const sign = n > 0 ? "+" : "";
      return `${sign}${formatNumber(n, digits)}%`;
    }

    function classBySign(value) {
      const n = toNumber(value);
      if (n === null) return "";
      return n >= 0 ? "positive" : "negative";
    }

    function recommendationClass(value, level) {
      const text = `${value || ""} ${level || ""}`.toLowerCase();
      if (text.includes("не покуп") || text.includes("negative") || text.includes("risk") || text.includes("риск")) return "negative";
      if (text.includes("покуп") || text.includes("рассмотреть") || text.includes("positive")) return "positive";
      return "neutral";
    }

    function extractForecast(payload) {
      return payload.forecast || payload.signal || {};
    }

    function extractLatest(payload) {
      const forecast = extractForecast(payload);
      return payload.latest || forecast.latest || forecast || {};
    }

    function findCandleArrays(obj, result = []) {
      if (!obj || typeof obj !== "object") return result;

      if (Array.isArray(obj)) {
        const looksLikeCandles = obj.some(item => {
          if (!item || typeof item !== "object") return false;
          return (
            item.close !== undefined ||
            item.CLOSE !== undefined ||
            item.price !== undefined ||
            item.trade_date !== undefined ||
            item.TRADEDATE !== undefined
          );
        });

        if (looksLikeCandles) result.push(obj);

        for (const item of obj.slice(0, 5)) {
          findCandleArrays(item, result);
        }

        return result;
      }

      for (const value of Object.values(obj)) {
        findCandleArrays(value, result);
      }

      return result;
    }

    function normalizeCandle(item) {
      const close = toNumber(item.close ?? item.CLOSE ?? item.price ?? item.last ?? item.value);
      const open = toNumber(item.open ?? item.OPEN ?? close);
      const high = toNumber(item.high ?? item.HIGH ?? close);
      const low = toNumber(item.low ?? item.LOW ?? close);
      const date = item.trade_date ?? item.TRADEDATE ?? item.date ?? item.begin ?? item.time ?? "";

      if (close === null) return null;

      return { open, high, low, close, date };
    }

    function extractCandlesFromPayloads(...payloads) {
      const arrays = [];

      for (const payload of payloads) {
        findCandleArrays(payload, arrays);
      }

      const best = arrays
        .map(array => array.map(normalizeCandle).filter(Boolean))
        .filter(array => array.length)
        .sort((a, b) => b.length - a.length)[0];

      return best || [];
    }

    function getVisibleCandles() {
      return allCandles;
    }

    async function setChartPeriod(period, button) {
      chartPeriod = period;

      document.querySelectorAll("[data-period]").forEach(item => item.classList.remove("active"));
      if (button) button.classList.add("active");

      await loadChartData();
    }

    function setChartType(type, button) {
      chartType = type;

      document.querySelectorAll("[data-chart]").forEach(item => item.classList.remove("active"));
      if (button) button.classList.add("active");

      drawChart();
    }

    function scrollToBlock(id) {
      const block = document.getElementById(id);
      if (block) block.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    function listHtml(items) {
      const values = Array.isArray(items) ? items.filter(Boolean) : [];
      if (!values.length) return "<p class='muted'>Нет дополнительных факторов.</p>";
      return `<ul>${values.map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
    }

    function renderUnavailable(payload) {
      const message = payload.message || payload.reason || "Для инструмента пока недостаточно данных.";
      const notice = document.getElementById("forecastNotice");
      notice.style.display = "block";
      notice.textContent = message;

      setText("forecastPrice", "—");
      setText("forecastPotential", "—");
      setText("forecastRange", "—");
      setText("forecastRecommendation", "Недостаточно данных");
      setText("heroProbability", "—");
    }

    function payloadReason(payload) {
      return String(
        (payload && (payload.reason || payload.error || payload.status)) ||
        ""
      ).trim();
    }

    function setPortfolioCtaEnabled(enabled, label) {
      const button = document.getElementById("portfolioCta");

      if (!button) return;

      button.disabled = !enabled;
      button.textContent = label || (enabled ? "Добавить в портфель" : "Недоступно");

      if (enabled) {
        button.onclick = () => {
          window.location.href = "/portfolio/construct/demo";
        };
      } else {
        button.onclick = event => {
          event.preventDefault();
          return false;
        };
      }
    }

    function renderUnavailableTicker(payload) {
      latestPayload = payload;

      const ticker = String(
        (payload && (payload.ticker || payload.requested_ticker)) ||
        TICKER ||
        ""
      ).toUpperCase();

      const message =
        (payload && payload.message) ||
        "Инструмент не найден в локальном справочнике MOEX. Обновите universe или проверьте тикер.";

      document.title = `${ticker} — инструмент недоступен`;

      setText("heroName", ticker);
      setText("heroTicker", ticker);
      setText("logoTicker", ticker);
      setText("heroProbability", "—");
      setText("heroRecommendation", "Недоступно");
      setText("heroSector", "—");

      setText("priceDate", "Цена инструмента");
      setText("sidePrice", "—");
      setText("sideChange", "—");

      setText("companyTitle", `О компании ${ticker}`);
      setText(
        "companyDescription",
        `${ticker} (${ticker}) — инструмент не найден в локальном справочнике MOEX. Для анализа нужно обновить справочник инструментов и исторические свечи.`
      );

      setText("forecastPrice", "—");
      setText("forecastPotential", "—");
      setText("forecastRange", "—");
      setText("forecastRecommendation", "Недоступно");

      setText("statOpen", "—");
      setText("statClose", "—");
      setText("statDayRange", "—");
      setText("statDayChange", "—");
      setText("stat20Change", "—");
      setText("statHorizon", "—");

      setPortfolioCtaEnabled(false, "Недоступно");

      const notice = document.getElementById("forecastNotice");
      if (notice) {
        notice.style.display = "block";
        notice.textContent = message;
      }

      const chartEmpty = document.getElementById("chartEmpty");
      if (chartEmpty) {
        chartEmpty.style.display = "flex";
        chartEmpty.textContent = "Нет исторических рыночных данных для построения графика";
      }

      if (typeof destroyInteractiveChart === "function") {
        destroyInteractiveChart();
      }
    }


    function renderTicker(payload, snapshot) {
      latestPayload = payload;

      if (payload && payload.ok === false && payloadReason(payload) === "instrument_not_found") {
        renderUnavailableTicker(payload);
        return;
      }

      setPortfolioCtaEnabled(true, "Добавить в портфель");

      const forecast = extractForecast(payload);
      const latest = extractLatest(payload);
      const instrument = payload.instrument || forecast.instrument || snapshot.instrument || {};
      const ticker = forecast.ticker || payload.ticker || TICKER;
      const name = forecast.name || instrument.name || ticker;

      const price = toNumber(forecast.price || forecast.current_price || latest.close || latest.price);
      const target = toNumber(forecast.forecast_price || forecast.target_price);
      const probability = toNumber(forecast.target_probability_pct);
      const potential = toNumber(forecast.potential_pct);
      const range = forecast.forecast_range || {};
      const recommendation = forecast.recommendation || "Наблюдать";
      const decisionLevel = forecast.decision_level || "neutral";

      setText("instrumentName", name);
      setText("tickerCode", ticker);
      setText("logoToken", ticker.slice(0, 5));
      setText("heroProbability", probability === null ? "—" : `${Math.round(probability)}%`);
      setText("heroRecommendation", recommendation);
      setText("heroSector", instrument.sector || forecast.sector || "—");

      setText("priceDate", latest.trade_date ? `Цена инструмента ${latest.trade_date}` : "Цена инструмента");
      setText("sidePrice", formatRub(price));

      const change = toNumber(forecast.change_pct || latest.change_pct);
      const sideChange = document.getElementById("sideChange");
      sideChange.textContent = formatPct(change);
      sideChange.className = `side-change ${classBySign(change)}`;

      setText("aboutTitle", `О компании ${name}`);
      setText(
        "aboutText",
        instrument.description ||
        forecast.description ||
        `${name} (${ticker}) — инструмент Московской биржи. Прогноз строится автоматически по рыночным данным, технической картине, исторической проверке достижения цели, ML-фильтру и риск-блоку.`
      );

      const notice = document.getElementById("forecastNotice");
      if (!payload.ok) {
        notice.style.display = "block";
        notice.textContent = payload.message || payload.reason || "Прогноз ограничен из-за недостатка данных.";
      } else {
        notice.style.display = "none";
        notice.textContent = "";
      }

      setText("forecastPrice", formatRub(target));
      setText("forecastPotential", formatPct(potential));
      setText("forecastRange", `${formatNumber(range.low)} — ${formatNumber(range.high)}`);

      const rec = document.getElementById("forecastRecommendation");
      rec.textContent = recommendation;
      rec.className = `rec-pill ${recommendationClass(recommendation, decisionLevel)}`;

      setText("statOpen", formatRub(latest.open || forecast.open));
      setText("statClose", formatRub(latest.close || price));

      const low = toNumber(latest.low || forecast.low);
      const high = toNumber(latest.high || forecast.high);
      setText("statDayRange", low !== null && high !== null ? `${formatRub(low)} – ${formatRub(high)}` : "—");

      setText("statDayChange", formatPct(change));
      setText("stat20Change", formatPct(forecast.return_20d_pct || (forecast.technical || {}).return_20d_pct));
      setText("statHorizon", forecast.horizon || "1–4 недели");

      allCandles = extractCandlesFromPayloads(snapshot, payload);

      if (!allCandles.length && price !== null) {
        allCandles = [{ open: price, high: price, low: price, close: price, date: latest.trade_date || "" }];
      }

      drawChart();
    }

    function toggleForecastExplanation() {
      const box = document.getElementById("forecastExplanation");

      if (box.style.display === "block") {
        box.style.display = "none";
        return;
      }

      const payload = latestPayload || {};
      const forecast = extractForecast(payload);
      const explanation = forecast.explanation || {};
      const decisionReason = forecast.decision_reason || explanation.summary || "";

      box.innerHTML = `
        <p>${escapeHtml(decisionReason || "Система учитывает вероятность достижения цели, риск, техническую картину, историческую проверку и ML-корректировку.")}</p>

        <h3>Технические и модельные факторы</h3>
        ${listHtml(explanation.technical)}

        <h3>Новости и события</h3>
        ${listHtml(explanation.news)}

        <h3>Риски</h3>
        ${listHtml(explanation.risks)}

        <p class="muted">
          Rule: ${formatPct(forecast.rule_probability_pct)} ·
          ML: ${formatPct(forecast.ml_probability_pct)} ·
          Итог: ${formatPct(forecast.target_probability_pct)} ·
          Источник: ${escapeHtml(forecast.probability_source || "—")}
        </p>
      `;

      box.style.display = "block";
    }

    async function fetchJson(url) {
      const response = await fetch(url);
      if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
      return response.json();
    }



    let tvChart = null;
    let tvSeries = null;
    let tvResizeObserver = null;

    function parsedChartTime(value) {
      const raw = String(value || "").trim();

      if (!raw) return null;

      const normalized = raw.replace(" ", "T");
      const datePart = normalized.slice(0, 10);

      const looksLikeDate =
        datePart.length === 10 &&
        datePart[4] === "-" &&
        datePart[7] === "-";

      if (looksLikeDate) {
        const year = Number(datePart.slice(0, 4));
        const month = Number(datePart.slice(5, 7));
        const day = Number(datePart.slice(8, 10));

        if (
          Number.isFinite(year) &&
          Number.isFinite(month) &&
          Number.isFinite(day) &&
          year > 1900 &&
          month >= 1 &&
          month <= 12 &&
          day >= 1 &&
          day <= 31
        ) {
          return {
            time: { year, month, day },
            key: datePart,
            sort: Date.UTC(year, month - 1, day),
          };
        }
      }

      const parsed = Date.parse(normalized);

      if (Number.isNaN(parsed)) {
        return null;
      }

      const unix = Math.floor(parsed / 1000);

      return {
        time: unix,
        key: String(unix),
        sort: parsed,
      };
    }

    function normalizeChartRows(rows) {
      const byTime = new Map();

      for (const row of rows) {
        if (!row || row._key === null || row._key === undefined) {
          continue;
        }

        byTime.set(String(row._key), row);
      }

      return Array
        .from(byTime.values())
        .sort((a, b) => a._sort - b._sort)
        .map(({ _key, _sort, ...clean }) => clean);
    }

    function buildInteractiveLineData(candles) {
      const rows = candles
        .map(item => {
          const parsed = parsedChartTime(item.date || item.time || item.begin || item.end || item.trade_date);
          const value = toNumber(item.close ?? item.price ?? item.last ?? item.value);

          if (!parsed || value === null) {
            return null;
          }

          return {
            time: parsed.time,
            value,
            _key: parsed.key,
            _sort: parsed.sort,
          };
        })
        .filter(Boolean);

      return normalizeChartRows(rows);
    }

    function buildInteractiveCandleData(candles) {
      const rows = candles
        .map(item => {
          const parsed = parsedChartTime(item.date || item.time || item.begin || item.end || item.trade_date);
          const close = toNumber(item.close ?? item.price ?? item.last ?? item.value);

          if (!parsed || close === null) {
            return null;
          }

          const open = toNumber(item.open ?? close);
          const high = toNumber(item.high ?? close);
          const low = toNumber(item.low ?? close);

          return {
            time: parsed.time,
            open: open === null ? close : open,
            high: high === null ? close : high,
            low: low === null ? close : low,
            close,
            _key: parsed.key,
            _sort: parsed.sort,
          };
        })
        .filter(Boolean);

      return normalizeChartRows(rows);
    }

    function destroyInteractiveChart() {
      if (tvResizeObserver) {
        tvResizeObserver.disconnect();
        tvResizeObserver = null;
      }

      if (tvChart) {
        tvChart.remove();
        tvChart = null;
        tvSeries = null;
      }
    }

    function addCompatibleLineSeries(chartInstance, options) {
      if (typeof chartInstance.addLineSeries === "function") {
        return chartInstance.addLineSeries(options);
      }

      if (window.LightweightCharts && window.LightweightCharts.LineSeries && typeof chartInstance.addSeries === "function") {
        return chartInstance.addSeries(window.LightweightCharts.LineSeries, options);
      }

      // fallback для старого кода, если LineSeries недоступен
      if (typeof chartInstance.addAreaSeries === "function") {
        return chartInstance.addAreaSeries({
          ...options,
          topColor: "rgba(37, 99, 235, 0.12)",
          bottomColor: "rgba(37, 99, 235, 0.02)",
        });
      }

      if (window.LightweightCharts && window.LightweightCharts.AreaSeries && typeof chartInstance.addSeries === "function") {
        return chartInstance.addSeries(window.LightweightCharts.AreaSeries, {
          ...options,
          topColor: "rgba(37, 99, 235, 0.12)",
          bottomColor: "rgba(37, 99, 235, 0.02)",
        });
      }

      throw new Error("Line series API недоступен в текущей версии lightweight-charts");
    }


    function addCompatibleAreaSeries(chartInstance, options) {
      if (typeof chartInstance.addAreaSeries === "function") {
        return chartInstance.addAreaSeries(options);
      }

      if (window.LightweightCharts && window.LightweightCharts.AreaSeries && typeof chartInstance.addSeries === "function") {
        return chartInstance.addSeries(window.LightweightCharts.AreaSeries, options);
      }

      throw new Error("Area series API недоступен в текущей версии lightweight-charts");
    }

    function addCompatibleCandlestickSeries(chartInstance, options) {
      if (typeof chartInstance.addCandlestickSeries === "function") {
        return chartInstance.addCandlestickSeries(options);
      }

      if (window.LightweightCharts && window.LightweightCharts.CandlestickSeries && typeof chartInstance.addSeries === "function") {
        return chartInstance.addSeries(window.LightweightCharts.CandlestickSeries, options);
      }

      throw new Error("Candlestick series API недоступен в текущей версии lightweight-charts");
    }

    function normalizeChartColor(value, fallback = "#2563eb") {
      const raw = String(value || "").trim();

      if (!raw) {
        return fallback;
      }

      if (/^#[0-9a-f]{3,8}$/i.test(raw) || /^rgba?\(/i.test(raw)) {
        return raw;
      }

      const probe = document.createElement("span");
      probe.style.color = fallback;
      probe.style.color = raw;
      probe.style.display = "none";

      document.body.appendChild(probe);
      const computed = getComputedStyle(probe).color;
      probe.remove();

      if (!computed || computed === "rgba(0, 0, 0, 0)") {
        return fallback;
      }

      return computed;
    }

    function chartColorWithAlpha(value, alpha, fallback = "#2563eb") {
      const color = normalizeChartColor(value, fallback);
      const match = color.match(/^rgba?\(([^)]+)\)$/i);

      if (!match) {
        return color;
      }

      const parts = match[1].split(",").map(item => Number.parseFloat(item.trim()));
      const [r, g, b] = parts;

      if (![r, g, b].every(Number.isFinite)) {
        return fallback;
      }

      return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    }


    function createInteractiveChartInstance() {
      const container = document.getElementById("chartContainer");

      if (!container || !window.LightweightCharts) {
        return null;
      }

      const styles = getComputedStyle(document.documentElement);
      const rawAccent = styles.getPropertyValue("--accent").trim() || "#2563eb";
      const accent = normalizeChartColor(rawAccent, "#2563eb");

      destroyInteractiveChart();

      tvChart = LightweightCharts.createChart(container, {
        width: container.clientWidth,
        height: container.clientHeight,
        layout: {
          background: { color: "transparent" },
          textColor: "#667085",
          fontSize: 12,
          fontFamily: "Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Arial, sans-serif",
        },
        grid: {
          vertLines: { color: "rgba(148, 163, 184, 0.12)" },
          horzLines: { color: "rgba(148, 163, 184, 0.18)" },
        },
        crosshair: {
          mode: LightweightCharts.CrosshairMode.Normal,
        },
        rightPriceScale: {
          borderVisible: false,
          scaleMargins: {
            top: 0.12,
            bottom: 0.14,
          },
        },
        timeScale: {
          borderVisible: false,
          timeVisible: chartPeriod === "1D" || chartPeriod === "1W",
          secondsVisible: false,
          rightOffset: 8,
          barSpacing: chartType === "candles" ? 7 : 6,
        },
        handleScroll: {
          mouseWheel: true,
          pressedMouseMove: true,
          horzTouchDrag: true,
          vertTouchDrag: false,
        },
        handleScale: {
          axisPressedMouseMove: true,
          mouseWheel: true,
          pinch: true,
        },
        localization: {
          priceFormatter: price => Number(price).toLocaleString("ru-RU", {
            maximumFractionDigits: 2,
          }),
        },
      });

      if (chartType === "candles") {
        tvSeries = addCompatibleCandlestickSeries(tvChart, {
          upColor: "#12b76a",
          downColor: "#f04438",
          borderUpColor: "#12b76a",
          borderDownColor: "#f04438",
          wickUpColor: "#12b76a",
          wickDownColor: "#f04438",
          priceLineVisible: true,
        });
      } else {
        tvSeries = addCompatibleLineSeries(tvChart, {
          color: accent,
          lineColor: accent,
          lineWidth: 3,
          priceLineVisible: true,
          lastValueVisible: true,
          crosshairMarkerVisible: true,
        });
      }

      tvResizeObserver = new ResizeObserver(entries => {
        const entry = entries[0];

        if (!entry || !tvChart) return;

        tvChart.applyOptions({
          width: Math.floor(entry.contentRect.width),
          height: Math.floor(entry.contentRect.height),
        });
      });

      tvResizeObserver.observe(container);

      return tvChart;
    }

    function drawChart() {
      const empty = document.getElementById("chartEmpty");
      const container = document.getElementById("chartContainer");

      if (!container) {
        return;
      }

      if (!window.LightweightCharts) {
        empty.style.display = "flex";
        empty.textContent = "Не загрузилась библиотека интерактивного графика.";
        return;
      }

      const candles = getVisibleCandles();

      if (!candles.length || candles.length < 2) {
        destroyInteractiveChart();
        empty.style.display = "flex";
        empty.textContent = "Недостаточно исторических данных для графика";
        return;
      }

      const lineData = buildInteractiveLineData(candles);
      const candleData = buildInteractiveCandleData(candles);
      const data = chartType === "candles" ? candleData : lineData;

      window.__tickerChartDebug = {
        ticker: TICKER,
        chartType,
        chartPeriod,
        rawCandlesCount: candles.length,
        lineDataCount: lineData.length,
        candleDataCount: candleData.length,
        firstRaw: candles[0],
        lastRaw: candles[candles.length - 1],
        firstLine: lineData[0],
        lastLine: lineData[lineData.length - 1],
        firstCandle: candleData[0],
        lastCandle: candleData[candleData.length - 1],
      };

      console.log("ticker chart debug", window.__tickerChartDebug);

      if (!data.length || data.length < 2) {
        destroyInteractiveChart();
        empty.style.display = "flex";
        empty.textContent = "Недостаточно корректных свечей для графика";
        return;
      }

      empty.style.display = "none";

      createInteractiveChartInstance();

      tvSeries.setData(data);
      tvChart.timeScale().fitContent();
    }


    async function loadChartData() {
      const empty = document.getElementById("chartEmpty");
      empty.style.display = "flex";
      empty.textContent = "Загружаю график...";

      try {
        const chartPayload = await fetchJson(
          `/tickers/${encodeURIComponent(TICKER)}/chart.json?period=${encodeURIComponent(chartPeriod)}&limit=1500`
        );

        allCandles = (chartPayload.candles || []).map(normalizeCandle).filter(Boolean);

        if (!allCandles.length) {
          empty.textContent = "Недостаточно исторических данных для графика";
        }

        drawChart();
      } catch (error) {
        allCandles = [];
        destroyInteractiveChart();
        empty.style.display = "flex";
        empty.textContent = `Не удалось загрузить график: ${error.message}`;
      }
    }


    function openForecastExplanation() {
      scrollToBlock("forecast");

      setTimeout(() => {
        const box = document.getElementById("forecastExplanation");

        if (!box) {
          return;
        }

        if (box.style.display !== "block") {
          toggleForecastExplanation();
        }
      }, 260);
    }


    async function loadTicker() {
      applyAccent(TICKER);

      let payload = {};
      let snapshot = {};

      try {
        payload = await fetchJson(`/signals/consumer/${encodeURIComponent(TICKER)}.json`);
      } catch (error) {
        payload = {
          ok: false,
          ticker: TICKER,
          message: `Не удалось загрузить прогноз: ${error.message}`
        };
      }

      try {
        snapshot = await fetchJson(`/tickers/${encodeURIComponent(TICKER)}/data?limit=1000`);
      } catch (_) {
        snapshot = {};
      }

      renderTicker(payload, snapshot);
      await loadChartData();
    }

    window.toggleForecastExplanation = toggleForecastExplanation;
    window.openForecastExplanation = openForecastExplanation;
    window.setChartPeriod = setChartPeriod;
    window.setChartType = setChartType;
    window.scrollToBlock = scrollToBlock;

    loadTicker();
  </script>
</body>
</html>"""

    return page.replace("__TICKER__", safe_ticker)
