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
      --bg: #ffffff;
      --page: #f7f8fb;
      --text: #202124;
      --muted: #70757a;
      --border: #e5e7eb;
      --soft: #f3f4f6;
      --green: #0a9f38;
      --green-bg: #e7f7ed;
      --red: #d93025;
      --red-bg: #fde8e7;
      --yellow: #ffd429;
      --blue: #0b57d0;
      --shadow: 0 12px 32px rgba(15, 23, 42, 0.08);
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      color: var(--text);
      background: var(--bg);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
    }

    a { color: var(--blue); text-decoration: none; }

    .topbar {
      height: 64px;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: center;
      background: white;
      position: sticky;
      top: 0;
      z-index: 20;
    }

    .topbar-inner {
      width: min(1180px, calc(100% - 32px));
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 18px;
      font-weight: 950;
    }

    .brand-icon {
      width: 32px;
      height: 32px;
      border-radius: 10px;
      background: var(--yellow);
      color: #111827;
      display: grid;
      place-items: center;
      font-weight: 950;
    }

    .nav {
      display: flex;
      gap: 22px;
      color: var(--muted);
      font-size: 14px;
      font-weight: 650;
    }

    .nav a {
      color: var(--muted);
    }

    .nav a.active {
      color: var(--text);
      border-bottom: 2px solid #111827;
      padding-bottom: 20px;
    }

    .wrap {
      width: min(1180px, calc(100% - 32px));
      margin: 0 auto;
      padding: 28px 0 56px;
    }

    .layout {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 320px;
      gap: 44px;
      align-items: start;
    }

    .main-col {
      min-width: 0;
    }

    .side-col {
      position: sticky;
      top: 92px;
    }

    .instrument-card {
      background: linear-gradient(135deg, #18a300, #0f7d00);
      color: white;
      border-radius: 24px;
      min-height: 168px;
      padding: 26px 28px;
      display: flex;
      justify-content: space-between;
      gap: 24px;
      overflow: hidden;
    }

    .instrument-title {
      font-size: 30px;
      line-height: 1.05;
      font-weight: 950;
      letter-spacing: -0.05em;
      display: flex;
      align-items: baseline;
      gap: 8px;
    }

    .ticker-code {
      font-size: 14px;
      font-weight: 700;
      opacity: 0.72;
      letter-spacing: 0;
    }

    .instrument-meta {
      display: flex;
      gap: 48px;
      margin-top: 54px;
    }

    .meta-label {
      font-size: 13px;
      opacity: 0.76;
      margin-bottom: 8px;
    }

    .meta-value {
      font-size: 19px;
      font-weight: 900;
    }

    .logo-circle {
      width: 92px;
      height: 92px;
      border-radius: 50%;
      background: rgba(255,255,255,0.9);
      color: var(--green);
      display: grid;
      place-items: center;
      font-size: 20px;
      font-weight: 950;
      margin-top: 18px;
    }

    .tabs {
      display: flex;
      gap: 26px;
      border-bottom: 1px solid var(--border);
      margin-top: 18px;
      color: var(--muted);
      font-size: 14px;
    }

    .tab {
      padding: 0 0 14px;
      cursor: default;
    }

    .tab.active {
      color: var(--text);
      border-bottom: 2px solid var(--yellow);
    }

    .chart-card {
      margin-top: 40px;
    }

    .periods {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-bottom: 24px;
    }

    .periods button {
      border: 1px solid var(--border);
      background: white;
      border-radius: 9px;
      min-width: 44px;
      height: 34px;
      cursor: default;
      color: #3c4043;
    }

    .periods button.active {
      border-color: #fbbc04;
      box-shadow: inset 0 0 0 1px #fbbc04;
    }

    .chart-box {
      height: 290px;
      border-bottom: 1px solid #d9dce1;
      position: relative;
      overflow: hidden;
    }

    .chart-svg {
      width: 100%;
      height: 100%;
      display: block;
    }

    .chart-price-line {
      position: absolute;
      left: 0;
      right: 0;
      top: 48%;
      border-top: 1px dotted #111827;
      pointer-events: none;
    }

    .price-tag {
      position: absolute;
      right: 0;
      top: calc(48% - 12px);
      background: #111827;
      color: white;
      padding: 4px 7px;
      font-size: 12px;
      font-weight: 800;
      border-radius: 2px;
    }

    .price-card {
      border: 1px solid var(--border);
      border-radius: 24px;
      padding: 28px 22px;
      text-align: center;
      background: white;
    }

    .price-card .caption {
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 12px;
    }

    .price-card .price {
      font-size: 30px;
      font-weight: 950;
      letter-spacing: -0.04em;
      margin-bottom: 24px;
    }

    .open-account {
      width: 100%;
      border: 0;
      background: var(--yellow);
      border-radius: 12px;
      min-height: 54px;
      font-weight: 850;
      cursor: default;
      font-size: 15px;
    }

    .login-text {
      margin-top: 20px;
      font-size: 14px;
      line-height: 1.5;
      color: #3c4043;
    }

    .section {
      margin-top: 54px;
    }

    .section h2 {
      font-size: 24px;
      letter-spacing: -0.03em;
      margin: 0 0 22px;
    }

    .about {
      font-size: 16px;
      line-height: 1.65;
      color: #3c4043;
      max-width: 760px;
    }

    .company-meta {
      display: flex;
      gap: 70px;
      margin-top: 28px;
      color: #3c4043;
    }

    .forecast-card {
      background: var(--soft);
      border-radius: 24px;
      padding: 24px 30px;
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 22px;
      align-items: center;
    }

    .forecast-item .label {
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 8px;
    }

    .forecast-item .value {
      font-size: 19px;
      font-weight: 950;
      letter-spacing: -0.02em;
    }

    .forecast-item .value.big {
      font-size: 24px;
    }

    .forecast-item .value.positive { color: var(--green); }
    .forecast-item .value.negative { color: var(--red); }

    .recommendation-pill {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 42px;
      padding: 10px 16px;
      border-radius: 999px;
      font-weight: 950;
      background: var(--green-bg);
      color: #047857;
    }

    .recommendation-pill.negative {
      background: var(--red-bg);
      color: #991b1b;
    }

    .recommendation-pill.neutral {
      background: #eef2ff;
      color: #1e40af;
    }

    .forecast-actions {
      margin-top: 16px;
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }

    .btn {
      border: 1px solid var(--border);
      background: white;
      color: var(--text);
      border-radius: 12px;
      min-height: 42px;
      padding: 0 16px;
      font-weight: 850;
      cursor: pointer;
    }

    .btn.primary {
      background: #eef2ff;
      color: #1e40af;
      border-color: #dbeafe;
    }

    .explanation {
      display: none;
      margin-top: 16px;
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 18px;
      background: white;
      line-height: 1.55;
      color: #3c4043;
    }

    .explanation h3 {
      margin: 14px 0 8px;
      font-size: 16px;
    }

    .explanation ul {
      margin: 8px 0 0 20px;
      padding: 0;
    }

    .stats-card {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 44px;
      margin-top: 20px;
    }

    .stats-table {
      border-collapse: collapse;
      width: 100%;
    }

    .stats-table td {
      border-bottom: 1px solid var(--border);
      padding: 17px 0;
      font-size: 15px;
    }

    .stats-table td:first-child {
      color: var(--muted);
    }

    .stats-table td:last-child {
      text-align: right;
      font-weight: 700;
    }

    .positive { color: var(--green); }
    .negative { color: var(--red); }
    .muted { color: var(--muted); }

    .notice {
      display: none;
      margin-top: 16px;
      border-radius: 16px;
      padding: 14px 16px;
      background: #fff7ed;
      color: #9a3412;
      font-weight: 700;
      line-height: 1.45;
    }

    @media (max-width: 980px) {
      .layout {
        grid-template-columns: 1fr;
      }

      .side-col {
        position: static;
        order: -1;
      }

      .forecast-card {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .stats-card {
        grid-template-columns: 1fr;
        gap: 10px;
      }
    }

    @media (max-width: 640px) {
      .topbar { position: static; height: auto; padding: 12px 0; }
      .nav { display: none; }
      .wrap { width: calc(100% - 20px); padding-top: 14px; }
      .instrument-card { border-radius: 18px; padding: 22px; }
      .instrument-title { font-size: 25px; }
      .instrument-meta { margin-top: 34px; gap: 24px; flex-direction: column; }
      .logo-circle { display: none; }
      .forecast-card { grid-template-columns: 1fr; }
      .chart-box { height: 230px; }
    }
  </style>
</head>
<body>
  <header class="topbar">
    <div class="topbar-inner">
      <div class="brand">
        <div class="brand-icon">AI</div>
        <span>AI Аналитик рынка</span>
      </div>
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
        <div class="instrument-card">
          <div>
            <div class="instrument-title">
              <span id="instrumentName">__TICKER__</span>
              <span class="ticker-code" id="tickerCode">__TICKER__</span>
            </div>

            <div class="instrument-meta">
              <div>
                <div class="meta-label">Вероятность цели</div>
                <div class="meta-value" id="heroProbability">—</div>
              </div>
              <div>
                <div class="meta-label">Сектор</div>
                <div class="meta-value" id="heroSector">—</div>
              </div>
            </div>
          </div>

          <div class="logo-circle" id="logoCircle">__TICKER__</div>
        </div>

        <div class="tabs">
          <div class="tab active">Обзор</div>
          <div class="tab">Прогноз</div>
          <div class="tab">Дивиденды</div>
          <div class="tab">Новости</div>
          <div class="tab">Идеи</div>
        </div>

        <section class="chart-card">
          <div class="periods">
            <button>М5</button>
            <button>М15</button>
            <button>М30</button>
            <button>Ч1</button>
            <button>Ч4</button>
            <button>Д</button>
            <button>Н</button>
            <button class="active">Мес</button>
          </div>

          <div class="chart-box">
            <div class="chart-price-line"></div>
            <div class="price-tag" id="chartPriceTag">—</div>
            <svg id="chartSvg" class="chart-svg" viewBox="0 0 760 290" preserveAspectRatio="none"></svg>
          </div>
        </section>

        <section class="section">
          <h2 id="aboutTitle">О компании</h2>
          <div class="about" id="aboutText">
            Загружаю описание инструмента и рыночные данные...
          </div>
          <div class="company-meta">
            <div>
              <div class="muted">Страна эмитента</div>
              <div style="margin-top:10px;">🇷🇺 Россия</div>
            </div>
            <div>
              <div class="muted">Биржа торгов</div>
              <div style="margin-top:10px;">Московская биржа</div>
            </div>
          </div>
        </section>

        <section class="section">
          <h2>Сводный прогноз</h2>

          <div id="forecastNotice" class="notice"></div>

          <div class="forecast-card">
            <div class="forecast-item">
              <div class="label">Прогнозная цена</div>
              <div class="value big" id="forecastPrice">—</div>
            </div>
            <div class="forecast-item">
              <div class="label">Потенциал</div>
              <div class="value" id="forecastPotential">—</div>
            </div>
            <div class="forecast-item">
              <div class="label">Диапазон</div>
              <div class="value" id="forecastRange">—</div>
            </div>
            <div class="forecast-item">
              <div class="label">Рекомендация</div>
              <div id="forecastRecommendation" class="recommendation-pill neutral">—</div>
            </div>
          </div>

          <div class="forecast-actions">
            <button class="btn primary" onclick="toggleForecastExplanation()">Почему такой прогноз?</button>
            <a class="btn" href="/signals">Все сигналы</a>
          </div>

          <div id="forecastExplanation" class="explanation"></div>
        </section>

        <section class="section">
          <h2>Показатели акции</h2>
          <div class="stats-card">
            <table class="stats-table">
              <tbody>
                <tr><td>Цена открытия</td><td id="statOpen">—</td></tr>
                <tr><td>Цена закрытия</td><td id="statClose">—</td></tr>
                <tr><td>Дневной диапазон</td><td id="statDayRange">—</td></tr>
              </tbody>
            </table>
            <table class="stats-table">
              <tbody>
                <tr><td>Изменение за день</td><td id="statDayChange">—</td></tr>
                <tr><td>Изменение за 20 дней</td><td id="stat20Change">—</td></tr>
                <tr><td>Горизонт прогноза</td><td id="statHorizon">—</td></tr>
              </tbody>
            </table>
          </div>
        </section>
      </section>

      <aside class="side-col">
        <div class="price-card">
          <div class="caption" id="priceDate">Цена инструмента</div>
          <div class="price" id="sidePrice">—</div>
          <button class="open-account">Открыть счёт</button>
          <div class="login-text">
            Если у вас уже есть счёт,<br>
            <a href="#">войдите в личный кабинет</a>
          </div>
        </div>
      </aside>
    </div>
  </main>

  <script>
    const TICKER = "__TICKER__";
    let latestPayload = null;

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

    function recommendationClass(value, level) {
      const text = `${value || ""} ${level || ""}`.toLowerCase();
      if (text.includes("не покуп") || text.includes("negative") || text.includes("risk") || text.includes("риск")) return "negative";
      if (text.includes("покуп") || text.includes("рассмотреть") || text.includes("positive")) return "";
      return "neutral";
    }

    function extractForecast(payload) {
      return payload.forecast || payload.signal || {};
    }

    function extractLatest(payload) {
      const forecast = extractForecast(payload);
      return payload.latest || forecast.latest || forecast || {};
    }

    function extractCandles(payload) {
      return payload.candles || payload.history || payload.rows || [];
    }

    function listHtml(items) {
      const values = Array.isArray(items) ? items.filter(Boolean) : [];
      if (!values.length) return "<p class='muted'>Нет дополнительных факторов.</p>";
      return `<ul>${values.map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
    }

    function drawChart(candles, currentPrice) {
      const svg = document.getElementById("chartSvg");
      const width = 760;
      const height = 290;
      const pad = 16;

      const points = candles
        .map(item => ({
          close: toNumber(item.close || item.price || item.value),
          date: item.trade_date || item.date
        }))
        .filter(item => item.close !== null)
        .slice(-180);

      if (!points.length && currentPrice !== null) {
        points.push({ close: currentPrice, date: "" });
      }

      if (points.length < 2) {
        svg.innerHTML = `<text x="20" y="145" fill="#70757a">Недостаточно данных для графика</text>`;
        return;
      }

      const values = points.map(item => item.close);
      const min = Math.min(...values);
      const max = Math.max(...values);
      const span = max - min || 1;

      const coords = points.map((item, index) => {
        const x = pad + index * ((width - pad * 2) / Math.max(1, points.length - 1));
        const y = height - pad - ((item.close - min) / span) * (height - pad * 2);
        return [x, y];
      });

      const d = coords.map((point, index) => `${index === 0 ? "M" : "L"} ${point[0].toFixed(2)} ${point[1].toFixed(2)}`).join(" ");

      const last = coords[coords.length - 1];
      const area = `${d} L ${last[0]} ${height - pad} L ${coords[0][0]} ${height - pad} Z`;

      svg.innerHTML = `
        <path d="${area}" fill="#f1f3f4"></path>
        <path d="${d}" fill="none" stroke="#111827" stroke-width="2.4" vector-effect="non-scaling-stroke"></path>
        <circle cx="${last[0]}" cy="${last[1]}" r="3.5" fill="#111827"></circle>
        <text x="12" y="${height - 8}" fill="#70757a" font-size="12">${escapeHtml(points[0].date || "")}</text>
        <text x="${width - 96}" y="${height - 8}" fill="#70757a" font-size="12">${escapeHtml(points[points.length - 1].date || "")}</text>
      `;
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

    function renderForecast(payload) {
      latestPayload = payload;

      if (!payload.ok) {
        renderUnavailable(payload);
      }

      const forecast = extractForecast(payload);
      const latest = extractLatest(payload);
      const instrument = payload.instrument || forecast.instrument || {};

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
      setText("logoCircle", ticker.slice(0, 5));
      setText("heroProbability", probability === null ? "—" : `${Math.round(probability)}%`);
      setText("heroSector", instrument.sector || forecast.sector || "—");

      setText("priceDate", latest.trade_date ? `Цена инструмента ${latest.trade_date}` : "Цена инструмента");
      setText("sidePrice", formatRub(price));
      setText("chartPriceTag", formatNumber(price));

      setText("aboutTitle", `О компании ${name}`);
      setText(
        "aboutText",
        instrument.description ||
        forecast.description ||
        `${name} (${ticker}) — инструмент Московской биржи. Прогноз на странице строится автоматически по рыночным данным, технической картине, исторической проверке достижения цели, ML-фильтру и риск-блоку.`
      );

      setText("forecastPrice", formatRub(target));
      setText("forecastPotential", formatPct(potential));
      setText("forecastRange", `${formatNumber(range.low)} — ${formatNumber(range.high)}`);

      const rec = document.getElementById("forecastRecommendation");
      rec.textContent = recommendation;
      rec.className = `recommendation-pill ${recommendationClass(recommendation, decisionLevel)}`;

      setText("statOpen", formatRub(latest.open || forecast.open));
      setText("statClose", formatRub(latest.close || price));

      const low = toNumber(latest.low || forecast.low);
      const high = toNumber(latest.high || forecast.high);
      setText("statDayRange", low !== null && high !== null ? `${formatRub(low)} – ${formatRub(high)}` : "—");

      setText("statDayChange", formatPct(forecast.change_pct || latest.change_pct));
      setText("stat20Change", formatPct(forecast.return_20d_pct || (forecast.technical || {}).return_20d_pct));
      setText("statHorizon", forecast.horizon || "1–4 недели");

      drawChart(extractCandles(payload), price);
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

        <h3>Ключевые факторы</h3>
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

    async function loadTicker() {
      try {
        const response = await fetch(`/signals/consumer/${encodeURIComponent(TICKER)}.json`);
        if (!response.ok) throw new Error(`HTTP ${response.status}: ${await response.text()}`);

        const payload = await response.json();

        let snapshot = {};
        try {
          const snapshotResponse = await fetch(`/tickers/${encodeURIComponent(TICKER)}/snapshot?limit=240`);
          if (snapshotResponse.ok) {
            snapshot = await snapshotResponse.json();
          }
        } catch (_) {}

        renderForecast(Object.assign({}, snapshot, payload, {
          candles: snapshot.candles || snapshot.rows || payload.candles || []
        }));
      } catch (error) {
        renderUnavailable({
          ok: false,
          message: `Не удалось загрузить прогноз: ${error.message}`
        });
      }
    }

    window.toggleForecastExplanation = toggleForecastExplanation;

    loadTicker();
  </script>
</body>
</html>"""

    return page.replace("__TICKER__", safe_ticker)
