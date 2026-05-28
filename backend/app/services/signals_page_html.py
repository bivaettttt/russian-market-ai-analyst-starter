from __future__ import annotations


def build_signals_page_html() -> str:
    return """<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <title>Сигналы рынка</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root {
      --bg: #f5f7fb;
      --card: #ffffff;
      --text: #0f172a;
      --muted: #64748b;
      --border: #e2e8f0;
      --blue: #2563eb;
      --green: #16a34a;
      --green-bg: #dcfce7;
      --yellow: #ca8a04;
      --yellow-bg: #fef9c3;
      --red: #dc2626;
      --red-bg: #fee2e2;
      --neutral-bg: #f1f5f9;
      --shadow: 0 14px 40px rgba(15, 23, 42, 0.08);
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
    }

    header {
      padding: 26px 22px 18px;
      background: linear-gradient(135deg, #0f172a, #1e3a8a);
      color: white;
    }

    header .inner {
      max-width: 1180px;
      margin: 0 auto;
    }

    h1 {
      margin: 0 0 8px;
      font-size: 32px;
      letter-spacing: -0.04em;
    }

    header p {
      margin: 0;
      color: rgba(255,255,255,0.78);
      max-width: 860px;
      line-height: 1.55;
    }

    nav {
      margin-top: 16px;
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }

    nav a {
      color: white;
      text-decoration: none;
      border: 1px solid rgba(255,255,255,0.24);
      background: rgba(255,255,255,0.10);
      border-radius: 999px;
      padding: 8px 12px;
      font-weight: 700;
      font-size: 13px;
    }

    main {
      max-width: 1180px;
      margin: 0 auto;
      padding: 22px;
    }

    .toolbar {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 24px;
      box-shadow: var(--shadow);
      padding: 18px;
      display: grid;
      grid-template-columns: 1.4fr auto;
      gap: 16px;
      align-items: end;
    }

    .filters {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      align-items: end;
    }

    label {
      display: flex;
      flex-direction: column;
      gap: 6px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
    }

    input, select {
      height: 42px;
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 0 12px;
      min-width: 190px;
      background: white;
      color: var(--text);
      font-size: 14px;
    }

    .button {
      border: 0;
      border-radius: 12px;
      padding: 12px 16px;
      background: var(--blue);
      color: white;
      font-weight: 850;
      cursor: pointer;
      text-decoration: none;
      display: inline-flex;
      justify-content: center;
      align-items: center;
      min-height: 42px;
    }

    .button.secondary {
      background: #eef2ff;
      color: #1e40af;
    }

    .button.ghost {
      background: white;
      color: var(--text);
      border: 1px solid var(--border);
    }

    .button.active {
      background: #0f172a;
      color: white;
    }


    .scenario-tabs {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin: 18px 0 4px;
    }

    .scenario-tab {
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 10px 14px;
      background: white;
      color: var(--text);
      font-weight: 850;
      cursor: pointer;
      box-shadow: 0 8px 18px rgba(15, 23, 42, 0.04);
    }

    .scenario-tab.active {
      background: #0f172a;
      border-color: #0f172a;
      color: white;
    }

    .scenario-tab .count {
      margin-left: 6px;
      opacity: 0.75;
      font-weight: 750;
    }

    .diagnostics-row {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 12px;
    }

    .diag-pill {
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 6px 9px;
      background: #f8fafc;
      border: 1px solid var(--border);
      color: var(--muted);
      font-size: 12px;
      font-weight: 750;
    }

    .diag-pill.negative {
      background: #fef2f2;
      color: #991b1b;
      border-color: #fecaca;
    }

    .diag-pill.positive {
      background: #ecfdf5;
      color: #065f46;
      border-color: #bbf7d0;
    }

    .diag-pill.warning {
      background: #fffbeb;
      color: #92400e;
      border-color: #fde68a;
    }

    .scenario-note {
      margin: 10px 0 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }

    .summary {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin: 18px 0;
    }

    .metric {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 16px;
      box-shadow: 0 10px 26px rgba(15, 23, 42, 0.05);
    }

    .metric .label {
      color: var(--muted);
      font-size: 12px;
      font-weight: 850;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }

    .metric .value {
      margin-top: 8px;
      font-size: 28px;
      font-weight: 900;
      letter-spacing: -0.04em;
    }

    .status {
      margin: 12px 0 0;
      color: var(--muted);
      font-size: 14px;
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px;
      margin-top: 18px;
    }

    .signal-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 24px;
      box-shadow: var(--shadow);
      padding: 18px;
      display: flex;
      flex-direction: column;
      gap: 14px;
      min-height: 330px;
    }

    .card-top {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: flex-start;
    }

    .ticker {
      font-size: 24px;
      font-weight: 950;
      letter-spacing: -0.04em;
    }

    .name {
      color: var(--muted);
      font-size: 13px;
      margin-top: 4px;
      line-height: 1.35;
      min-height: 18px;
    }

    .badge {
      padding: 8px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 900;
      white-space: nowrap;
    }

    .badge.positive { background: var(--green-bg); color: #166534; }
    .badge.neutral { background: var(--neutral-bg); color: #334155; }
    .badge.negative { background: var(--red-bg); color: #991b1b; }
    .badge.unknown { background: var(--yellow-bg); color: #854d0e; }

    .probability {
      display: flex;
      align-items: baseline;
      gap: 8px;
    }

    .probability .number {
      font-size: 44px;
      line-height: 1;
      font-weight: 950;
      letter-spacing: -0.07em;
    }

    .probability .caption {
      color: var(--muted);
      font-weight: 800;
      font-size: 12px;
      line-height: 1.2;
    }

    .kv {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }

    .kv-item {
      background: #f8fafc;
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 12px;
    }

    .kv-item .k {
      color: var(--muted);
      font-size: 12px;
      font-weight: 850;
    }

    .kv-item .v {
      margin-top: 5px;
      font-weight: 950;
      font-size: 16px;
    }

    .decision {
      padding: 12px 14px;
      border-radius: 16px;
      line-height: 1.45;
      font-size: 14px;
      font-weight: 700;
    }

    .decision.positive { background: var(--green-bg); color: #14532d; }
    .decision.neutral { background: var(--neutral-bg); color: #334155; }
    .decision.negative { background: var(--red-bg); color: #7f1d1d; }
    .decision.unknown { background: var(--yellow-bg); color: #713f12; }

    .card-actions {
      margin-top: auto;
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }

    .details {
      display: none;
      border-top: 1px solid var(--border);
      padding-top: 12px;
      color: #334155;
      line-height: 1.5;
      font-size: 14px;
    }

    .details ul {
      margin: 8px 0 0 18px;
      padding: 0;
    }

    .details h4 {
      margin: 12px 0 4px;
    }

    .details .event-list {
      margin-top: 8px;
      display: grid;
      gap: 8px;
    }

    .details .event-item {
      border-left: 3px solid #cbd5e1;
      padding-left: 10px;
    }

    .details .layer-list {
      display: grid;
      gap: 8px;
      margin-top: 8px;
    }

    .details .layer-item {
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 8px 10px;
      background: #f8fafc;
    }

    .empty {
      background: var(--card);
      border: 1px dashed var(--border);
      border-radius: 24px;
      padding: 26px;
      text-align: center;
      color: var(--muted);
      grid-column: 1 / -1;
    }

    .small { font-size: 12px; }
    .muted { color: var(--muted); }

    @media (max-width: 980px) {
      .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .toolbar { grid-template-columns: 1fr; }
    }

    @media (max-width: 640px) {
      main { padding: 14px; }
      header { padding: 22px 14px; }
      h1 { font-size: 26px; }
      .grid { grid-template-columns: 1fr; }
      .summary { grid-template-columns: 1fr; }
      .filters { flex-direction: column; align-items: stretch; }
      input, select { width: 100%; min-width: 0; }
      .button { width: 100%; }
    }
  </style>
</head>
<body>
  <header>
    <div class="inner">
      <h1>Сигналы рынка</h1>
      <p>Пользовательская витрина сигналов: итоговая вероятность достижения цели, готовая рекомендация и объяснение. Модель, ML-фильтр и риск-блок работают внутри — без лишней сложности для пользователя.</p>
      <nav>
        <a href="/dashboard">← Рынок</a>
        <a href="/portfolio/construct/demo">Конструктор портфеля</a>
        <a href="/ai/report/demo">AI Report</a>
        <a href="/signals/consumer/backtest-audit-page">Backtest audit</a>
        <a href="/signals/consumer/threshold-sweep-page">Threshold sweep</a>
        <a href="/signals/consumer/walk-forward-page">Walk-forward</a>
        <a href="/signals/consumer/regime-historical-evaluation-page">Regime evaluation</a>
        <a href="/signals/consumer/regime-formula-calibration-page">Regime calibration</a>
        <a href="/signals/consumer/adaptive-trade-calibration-page">Target/Stop calibration</a>
        <a href="/signals/consumer/expectancy-breakdown-page">Expectancy breakdown</a>
        <a href="/signals/consumer/candidate-filter-calibration-page">Filter calibration</a>
        <a href="/signals/consumer/composite-rule-calibration-page">Composite rules</a>
        <a href="/signals/ml-v2/report-page">ML v2 research</a>
        <a href="/signals/ml-v2/high-confidence-page">ML v2 high-confidence</a>
        <a href="/signals/ml-v2/gate-impact-page">ML v2 gate impact</a>
        <a href="/signals/ml-v2/gate-walk-forward-page">ML v2 gate walk-forward</a>
        <a href="/signals/consumer/ml-v2-gate-backtest-page">Consumer ML v2 gate backtest</a>
        <a href="/signals/ml-v3/consumer-candidate/page">ML v3 consumer candidates</a>
        <a href="/signals/setup-family/research-page">Setup families</a>
        <a href="/signals/event-aware/research-page">Event-aware setups</a>
        <a href="/signals/event-aware/walk-forward-page">Event-aware walk-forward</a>
        <a href="/signals/event-aware/rule-search-page">Event rule search</a>
        <a href="/signals/event-aware/dual-side-page">Dual-side event risk</a>
        <a href="/signals/event-aware/rule-stability-page">Rule stability</a>
        <a href="/signals/event-aware/risk-overlay-page">Risk overlay</a>
        <a href="/signals/event-aware/risk-overlay-walk-forward-page">Risk overlay WF</a>
        <a href="/signals/event-aware/risk-overlay-conservative-page">Conservative overlay</a>
        <a href="/signals/event-aware/conservative-overlay-paper-page">Overlay paper</a>
        <a href="/signals/event-aware/conservative-overlay-paper-tracking-page">Overlay tracking</a>
        <a href="/signals/event-aware/conservative-overlay-quality-report-page">Overlay quality</a>
        <a href="/signals/data-coverage-page">Data coverage</a>
        <a href="/tickers/SBER">Пример тикера</a>
      </nav>
    </div>
  </header>

  <main>
    <section class="toolbar">
      <div class="filters">
        <label>
          Поиск тикера
          <input id="searchInput" placeholder="SBER, GAZP, LKOH..." />
        </label>

        <label>
          Фильтр
          <select id="decisionFilter">
            <option value="">Все решения</option>
            <option value="buy">Покупать / рассмотреть</option>
            <option value="watch">Наблюдать</option>
            <option value="avoid">Не покупать / риск</option>
          </select>
        </label>

        <label>
          Новости
          <select id="newsFilter">
            <option value="all">Все</option>
            <option value="with_events">Есть события</option>
            <option value="boost">Boost</option>
            <option value="penalty">Penalty</option>
            <option value="veto">Veto</option>
            <option value="info_only">Информационно</option>
            <option value="no_events">Без событий</option>
          </select>
        </label>

        <label>
          Сортировка
          <select id="sortBy">
            <option value="decision_probability">Сначала лучшие сигналы</option>
            <option value="probability_desc">Вероятность ↓</option>
            <option value="ticker_asc">Тикер A→Z</option>
          </select>
        </label>

        <label>
          Количество
          <select id="limitInput">
            <option value="30">30</option>
            <option value="60" selected>60</option>
            <option value="100">100</option>
          </select>
        </label>

        <label>
          ML v2 research gate
          <select id="mlV2GateInput">
            <option value="false" selected>Выключен</option>
            <option value="true">Включен</option>
          </select>
        </label>

        <label>
          ML v2 threshold, %
          <input id="mlV2ThresholdInput" type="number" min="0" max="100" step="1" value="55" />
        </label>

        <label>
          ML v2 gate mode
          <select id="mlV2ModeInput">
            <option value="diagnostic_only" selected>Diagnostic only</option>
            <option value="soft_downgrade">Soft downgrade</option>
            <option value="hard_gate">Hard gate</option>
          </select>
        </label>

        <label>
          Event risk overlay
          <select id="eventRiskOverlayInput">
            <option value="false" selected>Выключен</option>
            <option value="true">Включен</option>
          </select>
        </label>

        <label>
          Overlay mode
          <select id="eventRiskOverlayModeInput">
            <option value="diagnostic_only" selected>Diagnostic only</option>
            <option value="soft_adjust">Soft adjust</option>
            <option value="experimental_downgrade">Experimental downgrade</option>
          </select>
        </label>

        <label>
          Conservative Event Overlay
          <select id="conservativeEventOverlayInput">
            <option value="false" selected>Выключен</option>
            <option value="true">Включен</option>
          </select>
        </label>

        <label>
          Conservative mode
          <select id="conservativeEventOverlayModeInput">
            <option value="soft_adjust" selected>Soft adjust</option>
            <option value="diagnostic_only">Diagnostic only</option>
          </select>
        </label>
      </div>

      <div class="filters">
        <button class="button" onclick="loadSignals()">Обновить</button>
        <button class="button secondary" onclick="clearFilters()">Сбросить</button>
      </div>
    </section>


    <section class="scenario-tabs" aria-label="Сценарии сигналов">
      <button class="scenario-tab active" data-scenario="long" onclick="setScenario('long')">
        Long-кандидаты <span class="count" id="scenarioLongCount">—</span>
      </button>
      <button class="scenario-tab" data-scenario="downside" onclick="setScenario('downside')">
        Риск снижения <span class="count" id="scenarioDownsideCount">—</span>
      </button>
      <button class="scenario-tab" data-scenario="all" onclick="setScenario('all')">
        Все сигналы <span class="count" id="scenarioAllCount">—</span>
      </button>
    </section>
    <p class="scenario-note" id="scenarioNote">
      Показаны long-кандидаты и нейтральные наблюдения. Риск снижения вынесен отдельно, это не short-рекомендация.
    </p>

    <p id="status" class="status">Загружаю сигналы...</p>

    <section class="summary">
      <div class="metric">
        <div class="label">Всего показано</div>
        <div class="value" id="metricTotal">—</div>
      </div>
      <div class="metric">
        <div class="label">Покупка / рассмотреть</div>
        <div class="value" id="metricBuy">—</div>
      </div>
      <div class="metric">
        <div class="label">Наблюдать</div>
        <div class="value" id="metricWatch">—</div>
      </div>
      <div class="metric">
        <div class="label">Не покупать / риск</div>
        <div class="value" id="metricAvoid">—</div>
      </div>
      <div class="metric">
        <div class="label">Режим рынка</div>
        <div class="value" id="metricRegime">—</div>
        <div class="small muted" id="metricRegimeDetails">—</div>
      </div>
    </section>

    <section id="signalsGrid" class="grid"></section>
  </main>

  <script>
    let latestRows = [];
    let currentScenario = "long";

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

    function formatNumber(value, digits = 2) {
      const n = toNumber(value);
      if (n === null) return "—";
      return n.toLocaleString("ru-RU", {
        maximumFractionDigits: digits,
        minimumFractionDigits: digits === 0 ? 0 : 0
      });
    }

    function formatPct(value, digits = 1) {
      const n = toNumber(value);
      if (n === null) return "—";
      return `${formatNumber(n, digits)}%`;
    }

    function normalizeRow(row) {
      const forecast = row.forecast || {};
      const signal = row.signal || {};
      const source = Object.assign({}, forecast, signal, row);

      return {
        raw: row,
        ticker: source.ticker || row.ticker || "—",
        name: source.name || row.name || source.company_name || "",
        recommendation: source.recommendation || source.label || "Наблюдать",
        consumer_action: source.consumer_action || source.action || "",
        scenario_direction: source.scenario_direction || "neutral",
        source_signal_action: source.source_signal_action || "",
        source_signal_type: source.source_signal_type || "",
        source_target_price: toNumber(source.source_target_price),
        scenario_reason: source.scenario_reason || "",
        position_sizing: source.position_sizing || {},
        risk_reward_ratio: toNumber(source.risk_reward_ratio),
        news_adjustment_pct: toNumber(source.news_adjustment_pct),
        ticker_news_adjustment_pct: toNumber(source.ticker_news_adjustment_pct),
        global_event_adjustment_pct: toNumber(source.global_event_adjustment_pct),
        global_event_tags: Array.isArray(source.global_event_tags) ? source.global_event_tags : [],
        global_event_reason: source.global_event_reason || null,
        macro_regime_flags: Array.isArray(source.macro_regime_flags) ? source.macro_regime_flags : [],
        global_news_assessment: source.global_news_assessment || {},
        market_regime: source.market_regime || {},
        market_regime_adjustment_pct: toNumber(source.market_regime_adjustment_pct),
        market_regime_gate: source.market_regime_gate || "",
        market_regime_reason: source.market_regime_reason || "",
        market_regime_position_multiplier: toNumber(source.market_regime_position_multiplier),
        effective_min_rr: toNumber(source.effective_min_rr),
        effective_min_ml_probability: toNumber(source.effective_min_ml_probability),
        signal_audit: source.signal_audit || {},
        audit_overall_score: toNumber(source.audit_overall_score ?? (source.signal_audit || {}).overall_score),
        audit_confidence_level: source.audit_confidence_level || (source.signal_audit || {}).confidence_level || "",
        audit_blocked_by: Array.isArray(source.audit_blocked_by) ? source.audit_blocked_by : ((source.signal_audit || {}).blocked_by || []),
        audit_top_strengths: Array.isArray(source.audit_top_strengths) ? source.audit_top_strengths : ((source.signal_audit || {}).top_strengths || []),
        audit_top_weaknesses: Array.isArray(source.audit_top_weaknesses) ? source.audit_top_weaknesses : ((source.signal_audit || {}).top_weaknesses || []),
        news_assessment: source.news_assessment || {},
        news_risk_flags: source.news_risk_flags || [],
        decision: source.decision || "",
        decision_level: source.decision_level || "neutral",
        decision_reason: source.decision_reason || "",
        is_buy_candidate: Boolean(source.is_buy_candidate),
        target_probability_pct: toNumber(source.target_probability_pct),
        rule_probability_pct: toNumber(source.rule_probability_pct),
        ml_probability_pct: toNumber(source.ml_probability_pct),
        ml_adjustment_pct: toNumber(source.ml_adjustment_pct),
        ml_v2_probability_pct: toNumber(source.ml_v2_probability_pct),
        ml_v2_gate_threshold_pct: toNumber(source.ml_v2_gate_threshold_pct),
        ml_v2_gate_passed: source.ml_v2_gate_passed,
        ml_v2_gate_status: source.ml_v2_gate_status || "disabled",
        ml_v2_gate_reason: source.ml_v2_gate_reason || "",
        ml_v2_research_note: source.ml_v2_research_note || "",
        ml_v2_research_gate: source.ml_v2_research_gate || {},
        ml_v2_gate_mode: source.ml_v2_gate_mode || "diagnostic_only",
        ml_v2_gate_effect: source.ml_v2_gate_effect || source.ml_v2_research_gate_effect || "none_disabled",
        ml_v2_original_action: source.ml_v2_original_action || "",
        ml_v2_original_recommendation: source.ml_v2_original_recommendation || "",
        ml_v2_final_action_changed: Boolean(source.ml_v2_final_action_changed),
        ml_v2_gate_blocked_reason: source.ml_v2_gate_blocked_reason || "",
        ml_v2_gate_research_basis: source.ml_v2_gate_research_basis || "",
        ml_v2_research_gate_effect: source.ml_v2_research_gate_effect || "none",
        event_risk_overlay: source.event_risk_overlay || {},
        event_risk_score: toNumber(source.event_risk_score),
        event_risk_level: source.event_risk_level || "",
        event_risk_position_multiplier: toNumber(source.event_risk_position_multiplier),
        event_risk_min_probability_addon_pct: toNumber(source.event_risk_min_probability_addon_pct),
        event_risk_min_rr_multiplier: toNumber(source.event_risk_min_rr_multiplier),
        event_risk_effective_min_probability_pct: toNumber(source.event_risk_effective_min_probability_pct),
        event_risk_effective_min_rr: toNumber(source.event_risk_effective_min_rr),
        event_risk_matched_rule_ids: Array.isArray(source.event_risk_matched_rule_ids) ? source.event_risk_matched_rule_ids : [],
        event_risk_reasons: Array.isArray(source.event_risk_reasons) ? source.event_risk_reasons : [],
        event_risk_overlay_mode: source.event_risk_overlay_mode || "",
        event_risk_original_action: source.event_risk_original_action || "",
        event_risk_final_action_changed: Boolean(source.event_risk_final_action_changed),
        event_risk_action_effect: source.event_risk_action_effect || "",
        event_risk_research_basis: source.event_risk_research_basis || "",
        conservative_event_overlay_enabled: Boolean(source.conservative_event_overlay_enabled),
        conservative_event_overlay_config_id: source.conservative_event_overlay_config_id || "",
        conservative_event_overlay_mode: source.conservative_event_overlay_mode || "",
        conservative_event_overlay_research_basis: source.conservative_event_overlay_research_basis || "",
        base_position_size_pct: toNumber(source.base_position_size_pct),
        event_adjusted_position_size_pct: toNumber(source.event_adjusted_position_size_pct),
        event_position_multiplier: toNumber(source.event_position_multiplier),
        event_position_delta_pct: toNumber(source.event_position_delta_pct),
        target_price: toNumber(source.target_price),
        current_price: toNumber(source.current_price || source.price),
        potential_pct: toNumber(source.potential_pct || source.expected_return_pct || source.target_potential_pct),
        reliability_level: source.reliability_level || source.reliability || "—",
        risk_level: source.risk_level || "—",
        probability_source: source.probability_source || ""
      };
    }

    function decisionClass(level, action, recommendation) {
      const value = `${level || ""} ${action || ""} ${recommendation || ""}`.toLowerCase();

      // Важно: "Не покупать" содержит слово "покупать", поэтому negative проверяем первым.
      if (
        value.includes("не покуп") ||
        value.includes("avoid") ||
        value.includes("negative") ||
        value.includes("risk") ||
        value.includes("риск")
      ) return "negative";

      if (
        value.includes("рассмотреть") ||
        value.includes("покупать") ||
        value.includes("buy") ||
        value.includes("positive")
      ) return "positive";

      if (value.includes("unknown")) return "unknown";
      return "neutral";
    }

    function isAvoidSignal(item) {
      const action = String(item.consumer_action || "").toLowerCase();
      const recommendation = String(item.recommendation || "").toLowerCase().trim();
      const level = String(item.decision_level || "").toLowerCase();
      const decision = String(item.decision || "").toLowerCase();

      return (
        action.includes("avoid") ||
        level.includes("negative") ||
        recommendation.startsWith("не покупать") ||
        decision.includes("риск") ||
        decision.includes("слабый сигнал") ||
        decision.includes("ml-фильтр")
      );
    }

    function isPositiveSignal(item) {
      const action = String(item.consumer_action || "").toLowerCase();
      const recommendation = String(item.recommendation || "").toLowerCase().trim();
      const level = String(item.decision_level || "").toLowerCase();

      if (isAvoidSignal(item)) return false;

      return (
        Boolean(item.is_buy_candidate) ||
        action === "buy" ||
        action === "consider_buy" ||
        level.includes("positive") ||
        recommendation === "покупать" ||
        recommendation === "рассмотреть покупку"
      );
    }

    function isWatchSignal(item) {
      const action = String(item.consumer_action || "").toLowerCase();
      const recommendation = String(item.recommendation || "").toLowerCase().trim();
      const level = String(item.decision_level || "").toLowerCase();

      if (isPositiveSignal(item) || isAvoidSignal(item)) return false;

      return (
        action.includes("watch") ||
        recommendation.includes("наблюдать") ||
        level.includes("neutral")
      );
    }


    function scenarioLabel(value) {
      if (value === "downside") return "Риск снижения";
      if (value === "long") return "Long";
      if (value === "all") return "Все";
      return "Нейтральный";
    }

    function scenarioNote(value) {
      if (value === "downside") {
        return "Показаны инструменты, где базовая модель видит downside/risk-сценарий. Это не рекомендация открыть short.";
      }
      if (value === "all") {
        return "Показаны все сценарии: long-кандидаты, нейтральное наблюдение и риск снижения.";
      }
      return "Показаны long-кандидаты и нейтральные наблюдения. Риск снижения вынесен отдельно, это не short-рекомендация.";
    }

    function setScenario(value) {
      currentScenario = value || "long";

      document.querySelectorAll(".scenario-tab").forEach(button => {
        button.classList.toggle("active", button.dataset.scenario === currentScenario);
      });

      const note = document.getElementById("scenarioNote");
      if (note) note.textContent = scenarioNote(currentScenario);

      loadSignals();
    }

    function updateScenarioCounters(summary) {
      const counts = (summary && summary.scenario_counts) || {};
      const total = summary?.total ?? latestRows.length ?? 0;
      const active = summary?.scenario_filter || currentScenario;

      const longBox = document.getElementById("scenarioLongCount");
      const downsideBox = document.getElementById("scenarioDownsideCount");
      const allBox = document.getElementById("scenarioAllCount");

      if (active === "all") {
        if (longBox) longBox.textContent = `(${(counts.long ?? 0) + (counts.neutral ?? 0)})`;
        if (downsideBox) downsideBox.textContent = `(${counts.downside ?? 0})`;
        if (allBox) allBox.textContent = `(${total})`;
        return;
      }

      if (longBox) longBox.textContent = active === "long" ? `(${total})` : "—";
      if (downsideBox) downsideBox.textContent = active === "downside" ? `(${total})` : "—";
      if (allBox) allBox.textContent = active === "all" ? `(${total})` : "—";
    }

    function updateMarketRegimeSummary(summary) {
      const regime = (summary && summary.market_regime) || (latestRows[0] || {}).market_regime || {};
      const box = document.getElementById("metricRegime");
      const details = document.getElementById("metricRegimeDetails");
      if (!box || !details) return;

      if (!regime.regime) {
        box.textContent = "—";
        details.textContent = "нет данных";
        return;
      }

      box.textContent = regime.regime;
      details.textContent = `score ${regime.regime_score ?? "—"} · long ${regime.long_allowed === false ? "нет" : "да"} · pos x${regime.position_multiplier ?? "—"}`;
    }


    function newsBadgeClass(news) {
      const sentiment = (news && news.sentiment) || "none";

      if (sentiment === "positive") return "positive";
      if (sentiment === "negative") return "negative";
      if (sentiment === "mixed") return "warning";

      return "";
    }

    function newsBadgeText(item) {
      const news = item.news_assessment || {};
      const adjustment = item.ticker_news_adjustment_pct;

      if (!news.has_events) {
        return "Новости: нет событий";
      }

      const sentiment = news.sentiment || "neutral";
      const score = news.sentiment_score ?? 0;
      const adj = adjustment === null || Number.isNaN(adjustment)
        ? "0.0"
        : adjustment.toFixed(1);

      return `Новости: ${sentiment} ${adj > 0 ? "+" : ""}${adj} п.п. · score ${score}`;
    }

    function macroBadgeClass(item) {
      const adjustment = item.global_event_adjustment_pct;
      if (adjustment > 0) return "positive";
      if (adjustment < 0) return "negative";
      return "";
    }

    function macroBadgeText(item) {
      const adjustment = item.global_event_adjustment_pct;
      if (adjustment === null || Number.isNaN(adjustment)) return "Макро: —";

      const adjText = `${adjustment > 0 ? "+" : ""}${adjustment.toFixed(1)} п.п.`;
      const tags = Array.isArray(item.global_event_tags) ? item.global_event_tags.filter(Boolean).slice(0, 3) : [];
      return `Макро: ${adjText}${tags.length ? ` · ${tags.join(", ")}` : ""}`;
    }

    function regimeBadgeClass(item) {
      const regime = String((item.market_regime || {}).regime || "").toLowerCase();
      if (item.market_regime_gate === "blocked" || regime === "risk_off") return "negative";
      if (regime === "risk_on") return "positive";
      return "";
    }

    function regimeBadgeText(item) {
      const regime = (item.market_regime || {}).regime || "neutral";
      return `Режим: ${regime}`;
    }

    function auditBadgeClass(item) {
      const blocked = Array.isArray(item.audit_blocked_by) && item.audit_blocked_by.length > 0;
      const confidence = String(item.audit_confidence_level || "").toLowerCase();

      if (blocked) return "warning";
      if (confidence === "high") return "positive";
      if (confidence === "medium") return "warning";
      return "";
    }

    function auditBadgeText(item) {
      const score = item.audit_overall_score;
      const confidence = item.audit_confidence_level || "—";
      if (score === null || Number.isNaN(score)) return "Audit: —";
      return `Audit: ${Math.round(score)} / ${confidence}`;
    }

    function mlV2BadgeClass(item) {
      const effect = String(item.ml_v2_gate_effect || item.ml_v2_research_gate_effect || "").toLowerCase();
      if (effect === "hard_rejected") return "negative";
      if (effect === "soft_downgraded") return "warning";
      const status = String(item.ml_v2_gate_status || "disabled").toLowerCase();
      if (status === "passed") return "positive";
      if (status === "rejected") return "warning";
      if (status === "error") return "negative";
      return "";
    }

    function mlV2BadgeText(item) {
      const effect = String(item.ml_v2_gate_effect || item.ml_v2_research_gate_effect || "").toLowerCase();
      const status = String(item.ml_v2_gate_status || "disabled").toLowerCase();
      if (status === "disabled") return "ML v2: off";
      if (status === "not_available") return "ML v2: n/a";
      if (status === "error") return "ML v2: error";
      if (effect === "soft_downgraded") return "ML v2: downgraded";
      if (effect === "hard_rejected") return "ML v2: hard rejected";
      const probability = item.ml_v2_probability_pct;
      const probabilityText = probability === null || Number.isNaN(probability) ? "—" : `${probability.toFixed(1)}%`;
      return `ML v2: ${status} ${probabilityText}`;
    }

    function mlV2GateHtml(forecast, signal) {
      const gate = forecast.ml_v2_research_gate || signal.ml_v2_research_gate || {};
      const status = forecast.ml_v2_gate_status || signal.ml_v2_gate_status || gate.status || "disabled";
      const probability = forecast.ml_v2_probability_pct ?? signal.ml_v2_probability_pct ?? gate.probability_pct;
      const threshold = forecast.ml_v2_gate_threshold_pct ?? signal.ml_v2_gate_threshold_pct ?? gate.threshold_pct;
      const mode = forecast.ml_v2_gate_mode || signal.ml_v2_gate_mode || "diagnostic_only";
      const effect = forecast.ml_v2_gate_effect || signal.ml_v2_gate_effect || signal.ml_v2_research_gate_effect || "none_disabled";
      const originalAction = forecast.ml_v2_original_action || signal.ml_v2_original_action || forecast.source_signal_action || "—";
      const finalAction = forecast.action || signal.consumer_action || signal.action || "—";
      const changed = Boolean(forecast.ml_v2_final_action_changed || signal.ml_v2_final_action_changed);
      const blockedReason = forecast.ml_v2_gate_blocked_reason || signal.ml_v2_gate_blocked_reason || "";
      const researchBasis = forecast.ml_v2_gate_research_basis || signal.ml_v2_gate_research_basis || "";
      return `
        <h4>ML v2 research gate</h4>
        <p>${escapeHtml(forecast.ml_v2_gate_reason || signal.ml_v2_gate_reason || gate.reason || "ML v2 research gate выключен по умолчанию.")}</p>
        <p class="small muted">
          Status: ${escapeHtml(status)} ·
          Probability: ${formatPct(probability)} ·
          Threshold: ${formatPct(threshold)} ·
          Mode: ${escapeHtml(mode)} ·
          Effect: ${escapeHtml(effect)}
        </p>
        ${changed ? `<p class="small muted">Action: ${escapeHtml(originalAction)} → ${escapeHtml(finalAction)}</p>` : ""}
        ${blockedReason ? `<p class="small muted">${escapeHtml(blockedReason)}</p>` : ""}
        ${researchBasis ? `<p class="small muted">${escapeHtml(researchBasis)}</p>` : ""}
        <p class="small muted">${escapeHtml(forecast.ml_v2_research_note || signal.ml_v2_research_note || gate.research_note || "Diagnostic-only layer; production recommendation is unchanged.")}</p>
      `;
    }

    function eventRiskBadgeClass(item) {
      const level = String(item.event_risk_level || "").toLowerCase();
      if (level === "high" || level === "extreme") return "negative";
      if (level === "elevated" || level === "moderate") return "warning";
      if (level === "low") return "positive";
      return "";
    }

    function eventRiskBadgeText(item) {
      const level = String(item.event_risk_level || "").toLowerCase();
      if (!level) return "Event risk: off";
      const score = item.event_risk_score === null ? "—" : item.event_risk_score.toFixed(1);
      const mult = item.event_risk_position_multiplier === null ? "—" : `x${item.event_risk_position_multiplier}`;
      return `Event risk: ${level} ${score} · size ${mult}`;
    }

    function eventRiskOverlayHtml(forecast, signal) {
      const overlay = forecast.event_risk_overlay || signal.event_risk_overlay || {};
      const level = forecast.event_risk_level || signal.event_risk_level || overlay.risk_level || "";
      const score = forecast.event_risk_score ?? signal.event_risk_score ?? overlay.risk_score;
      const reasons = forecast.event_risk_reasons || signal.event_risk_reasons || overlay.risk_reasons || [];
      const rules = forecast.event_risk_matched_rule_ids || signal.event_risk_matched_rule_ids || overlay.matched_rule_ids || [];
      if (!level && !overlay.status) {
        return `
          <h4>Event Risk Overlay</h4>
          <p class="small muted">Overlay выключен по умолчанию; production action не меняется.</p>
        `;
      }
      return `
        <h4>${forecast.conservative_event_overlay_enabled || signal.conservative_event_overlay_enabled ? "Conservative Event Risk Overlay" : "Event Risk Overlay"}</h4>
        <p>${escapeHtml((reasons || [])[0] || "Research-only risk overlay calculates soft risk adjustments.")}</p>
        <p class="small muted">
          Config: ${escapeHtml(forecast.conservative_event_overlay_config_id || signal.conservative_event_overlay_config_id || overlay.config_id || "generic")} ·
          Score: ${escapeHtml(score ?? "—")} ·
          Level: ${escapeHtml(level || "—")} ·
          Size: x${escapeHtml(forecast.event_risk_position_multiplier ?? signal.event_risk_position_multiplier ?? overlay.position_multiplier ?? "—")} ·
          Base position: ${escapeHtml(forecast.base_position_size_pct ?? signal.base_position_size_pct ?? "—")} ·
          Adjusted position: ${escapeHtml(forecast.event_adjusted_position_size_pct ?? signal.event_adjusted_position_size_pct ?? "—")} ·
          Probability addon: ${escapeHtml(forecast.event_risk_min_probability_addon_pct ?? signal.event_risk_min_probability_addon_pct ?? overlay.min_probability_addon_pct ?? "—")} ·
          RR multiplier: ${escapeHtml(forecast.event_risk_min_rr_multiplier ?? signal.event_risk_min_rr_multiplier ?? overlay.min_rr_multiplier ?? "—")} ·
          Effect: ${escapeHtml(forecast.event_risk_action_effect || signal.event_risk_action_effect || "—")}
        </p>
        <p class="small muted">Rules: ${escapeHtml((rules || []).slice(0, 6).join(", ") || "—")}</p>
        <p class="small muted">Research/paper-trading only; production default is unchanged.</p>
        <p class="small muted">${escapeHtml(forecast.event_risk_research_basis || signal.event_risk_research_basis || overlay.research_basis || "Hard filter failed; overlay is diagnostic/soft unless explicitly enabled.")}</p>
      `;
    }


    function fmtPercent(value) {
      const number = toNumber(value);
      if (number === null || Number.isNaN(number)) return "—";
      return `${number.toFixed(2)}%`;
    }


    function decisionRank(item) {
      if (isPositiveSignal(item)) return 1;
      if (isWatchSignal(item)) return 2;
      if (isAvoidSignal(item)) return 3;
      return 4;
    }

    function filterRows(rows) {
      const filter = document.getElementById("decisionFilter").value;
      const query = document.getElementById("searchInput").value.trim().toUpperCase();

      return rows.filter(item => {
        if (query && !item.ticker.toUpperCase().includes(query) && !item.name.toUpperCase().includes(query)) {
          return false;
        }

        if (filter === "buy") {
          return isPositiveSignal(item);
        }

        if (filter === "watch") {
          return isWatchSignal(item);
        }

        if (filter === "avoid") {
          return isAvoidSignal(item);
        }

        return true;
      });
    }

    function sortRows(rows) {
      const sortBy = document.getElementById("sortBy").value;

      return [...rows].sort((a, b) => {
        if (sortBy === "probability_desc") {
          return (b.target_probability_pct ?? -1) - (a.target_probability_pct ?? -1);
        }

        if (sortBy === "ticker_asc") {
          return a.ticker.localeCompare(b.ticker);
        }

        const rankDelta = decisionRank(a) - decisionRank(b);
        if (rankDelta !== 0) return rankDelta;

        return (b.target_probability_pct ?? -1) - (a.target_probability_pct ?? -1);
      });
    }

    function listHtml(items) {
      const values = Array.isArray(items) ? items.filter(Boolean) : [];
      if (!values.length) return "<p class='muted'>Нет дополнительных факторов.</p>";
      return `<ul>${values.map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
    }

    function globalBackgroundHtml(assessment, fallbackForecast) {
      const global = assessment || {};
      if (!global.has_global_events) return "";

      const adjustment = toNumber(global.adjustment_pct ?? fallbackForecast.global_event_adjustment_pct);
      const tags = Array.isArray(global.tags) ? global.tags : [];
      const events = Array.isArray(global.events) ? global.events.slice(0, 3) : [];
      const reason = global.reason || fallbackForecast.global_event_reason || "Глобальный фон учтён в вероятности.";

      const eventHtml = events.length
        ? `<div class="event-list">${events.map(event => {
            const eventTags = Array.isArray(event.tags) ? event.tags.slice(0, 4).join(", ") : "—";
            const reasons = Array.isArray(event.reasons) ? event.reasons.slice(0, 3).join("; ") : "";
            const score = toNumber(event.score);
            return `
              <div class="event-item">
                <strong>${escapeHtml(event.title || "Глобальное событие")}</strong>
                <div class="small muted">
                  type: ${escapeHtml(event.event_type || "—")} ·
                  tags: ${escapeHtml(eventTags)} ·
                  score: ${score === null ? "—" : escapeHtml(score)}
                </div>
                ${reasons ? `<div class="small">${escapeHtml(reasons)}</div>` : ""}
              </div>
            `;
          }).join("")}</div>`
        : "<p class='muted'>Список событий не передан.</p>";

      return `
        <h4>Глобальный фон</h4>
        <p>${escapeHtml(reason)}</p>
        <p class="small muted">
          Макро-корректировка: ${adjustment === null ? "—" : `${adjustment > 0 ? "+" : ""}${adjustment.toFixed(1)} п.п.`} ·
          tags: ${escapeHtml(tags.length ? tags.join(", ") : "—")}
        </p>
        ${eventHtml}
      `;
    }

    function marketRegimeHtml(forecast) {
      const regime = forecast.market_regime || {};
      if (!regime.regime) return "";

      const reasons = Array.isArray(regime.reasons) ? regime.reasons : [];
      const adjustment = toNumber(forecast.market_regime_adjustment_pct);
      const multiplier = toNumber(forecast.market_regime_position_multiplier ?? regime.position_multiplier);
      const longAllowed = regime.long_allowed === false ? "нет" : "да";

      return `
        <h4>Режим рынка</h4>
        <p>${escapeHtml(forecast.market_regime_reason || `Режим рынка: ${regime.regime}`)}</p>
        <p class="small muted">
          adjustment: ${adjustment === null ? "—" : `${adjustment > 0 ? "+" : ""}${adjustment.toFixed(1)} п.п.`} ·
          long_allowed: ${escapeHtml(longAllowed)} ·
          position_multiplier: ${multiplier === null ? "—" : escapeHtml(multiplier)}
        </p>
        ${listHtml(reasons)}
      `;
    }

    function auditHtml(audit) {
      const data = audit || {};
      if (!Object.keys(data).length) return "";

      const layerLabels = {
        technical: "Technical",
        ml: "ML",
        risk: "Risk",
        ticker_news: "Новости",
        global_macro: "Макро",
        market_regime: "Режим рынка",
        scenario: "Scenario"
      };
      const layerScores = data.layer_scores || {};
      const layerHtml = Object.entries(layerLabels).map(([key, label]) => {
        const layer = layerScores[key] || {};
        const status = layer.status || "not_available";
        const score = layer.score ?? "—";
        const reason = layer.reason || "Данных по слою нет.";
        return `
          <div class="layer-item">
            <strong>${escapeHtml(label)}:</strong>
            ${escapeHtml(status)} · score ${escapeHtml(score)}
            <div class="small muted">${escapeHtml(reason)}</div>
          </div>
        `;
      }).join("");

      return `
        <h4>Аудит сигнала</h4>
        <p>${escapeHtml(data.human_explanation || "Audit недоступен для этого сигнала.")}</p>
        <p class="small muted">${escapeHtml(data.score_meaning || "Audit score — качество итогового решения, не вероятность роста.")}</p>
        <p class="small">${escapeHtml(data.risk_committee_note || "Risk layer не дал отдельного комментария.")}</p>
        <div class="small muted">
          Passed: ${escapeHtml((data.passed_layers || []).join(", ") || "—")} ·
          Warning: ${escapeHtml((data.warning_layers || []).join(", ") || "—")} ·
          Blocked: ${escapeHtml((data.blocked_by || []).join(", ") || "—")}
        </div>
        <h4>Сильные стороны</h4>
        ${listHtml(data.top_strengths)}
        <h4>Слабые места</h4>
        ${listHtml(data.top_weaknesses)}
        <h4>Что должно улучшиться</h4>
        ${listHtml(data.required_improvements)}
        <div class="layer-list">${layerHtml}</div>
      `;
    }

    async function toggleDetails(ticker) {
      const id = `details-${ticker}`;
      const box = document.getElementById(id);

      if (!box) return;

      if (box.dataset.loaded === "true") {
        box.style.display = box.style.display === "block" ? "none" : "block";
        return;
      }

      box.style.display = "block";
      box.innerHTML = "<p class='muted'>Загружаю объяснение...</p>";

      try {
        const detailParams = new URLSearchParams();
        const mlV2Gate = document.getElementById("mlV2GateInput");
        const mlV2Threshold = document.getElementById("mlV2ThresholdInput");
        const mlV2Mode = document.getElementById("mlV2ModeInput");
        if (mlV2Gate && mlV2Gate.value === "true") {
          detailParams.set("use_ml_v2_research_gate", "true");
          detailParams.set("ml_v2_gate_threshold_pct", mlV2Threshold?.value || "55");
          detailParams.set("ml_v2_gate_mode", mlV2Mode?.value || "diagnostic_only");
        }
        const eventRiskOverlay = document.getElementById("eventRiskOverlayInput");
        const eventRiskOverlayMode = document.getElementById("eventRiskOverlayModeInput");
        if (eventRiskOverlay && eventRiskOverlay.value === "true") {
          detailParams.set("use_event_risk_overlay", "true");
          detailParams.set("event_risk_overlay_mode", eventRiskOverlayMode?.value || "diagnostic_only");
        }
        const conservativeOverlay = document.getElementById("conservativeEventOverlayInput");
        const conservativeOverlayMode = document.getElementById("conservativeEventOverlayModeInput");
        if (conservativeOverlay && conservativeOverlay.value === "true") {
          detailParams.set("use_conservative_event_overlay", "true");
          detailParams.set("conservative_event_overlay_mode", conservativeOverlayMode?.value || "soft_adjust");
        }
        const detailQuery = detailParams.toString();
        const response = await fetch(`/signals/consumer/${encodeURIComponent(ticker)}.json${detailQuery ? `?${detailQuery}` : ""}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        const forecast = data.forecast || {};
        const signal = data.signal || {};
        const explanation = forecast.explanation || signal.explanation || {};
        const decisionReason = forecast.decision_reason || signal.decision_reason || "";
        const globalAssessment = forecast.global_news_assessment || signal.global_news_assessment || {};
        const signalAudit = forecast.signal_audit || signal.signal_audit || {};

        box.innerHTML = `
          <h4>Почему такой сигнал?</h4>
          <p>${escapeHtml(decisionReason || explanation.summary || "Система учитывает вероятность достижения цели, риск, техническую картину и ML-корректировку.")}</p>

          ${auditHtml(signalAudit)}

          <h4>Факторы</h4>
          ${listHtml(explanation.technical)}

          <h4>Новости и события</h4>
          ${listHtml(explanation.news)}

          ${globalBackgroundHtml(globalAssessment, forecast)}

          ${marketRegimeHtml(forecast)}

          ${mlV2GateHtml(forecast, signal)}

          ${eventRiskOverlayHtml(forecast, signal)}

          <h4>Риски</h4>
          ${listHtml(explanation.risks)}

          <p class="small muted">
            Rule: ${formatPct(forecast.rule_probability_pct || signal.rule_probability_pct)} ·
            ML: ${formatPct(forecast.ml_probability_pct || signal.ml_probability_pct)} ·
            ML v2: ${formatPct(forecast.ml_v2_probability_pct || signal.ml_v2_probability_pct)} ·
            Источник: ${escapeHtml(forecast.probability_source || signal.probability_source || "—")}
          </p>
        `;

        box.dataset.loaded = "true";
      } catch (error) {
        box.innerHTML = `<p class="muted">Не удалось загрузить объяснение: ${escapeHtml(error.message)}</p>`;
      }
    }

    function renderSignals() {
      const grid = document.getElementById("signalsGrid");
      const rows = sortRows(filterRows(latestRows));

      const buyCount = rows.filter(isPositiveSignal).length;
      const watchCount = rows.filter(isWatchSignal).length;
      const avoidCount = rows.filter(isAvoidSignal).length;

      document.getElementById("metricTotal").textContent = rows.length;
      document.getElementById("metricBuy").textContent = buyCount;
      document.getElementById("metricWatch").textContent = watchCount;
      document.getElementById("metricAvoid").textContent = avoidCount;

      if (!rows.length) {
        grid.innerHTML = `<div class="empty">По выбранным фильтрам сигналов нет.</div>`;
        return;
      }

      grid.innerHTML = rows.map(item => {
        const cls = decisionClass(item.decision_level, item.consumer_action, item.recommendation);
        const probability = item.target_probability_pct;
        const potential = item.potential_pct;
        const decisionText = item.decision || item.decision_reason || item.recommendation;
        const target = item.target_price;
        const current = item.current_price;
        const mlV2ActionChange = item.ml_v2_final_action_changed
          ? `<div class="small muted">ML v2: ${escapeHtml(item.ml_v2_original_action || "—")} → ${escapeHtml(item.consumer_action || item.action || "—")}</div>`
          : "";
        const eventRiskActionChange = item.event_risk_final_action_changed
          ? `<div class="small muted">Event risk: ${escapeHtml(item.event_risk_original_action || "—")} → ${escapeHtml(item.consumer_action || item.action || "—")}</div>`
          : "";

        return `
          <article class="signal-card">
            <div class="card-top">
              <div>
                <div class="ticker">${escapeHtml(item.ticker)}</div>
                <div class="name">${escapeHtml(item.name)}</div>
              </div>
              <span class="badge ${cls}">${escapeHtml(item.recommendation)}</span>
            </div>

            <div class="probability">
              <div class="number">${probability === null ? "—" : Math.round(probability)}</div>
              <div class="caption">вероятность<br>достижения цели, %</div>
            </div>

            <div class="kv">
              <div class="kv-item">
                <div class="k">Текущая цена</div>
                <div class="v">${formatNumber(current)}</div>
              </div>
              <div class="kv-item">
                <div class="k">Цель</div>
                <div class="v">${formatNumber(target)}</div>
              </div>
              <div class="kv-item">
                <div class="k">Потенциал</div>
                <div class="v">${formatPct(potential)}</div>
              </div>
              <div class="kv-item">
                <div class="k">Надёжность</div>
                <div class="v">${escapeHtml(item.reliability_level)}</div>
              </div>
            </div>

            <div class="decision ${cls}">
              ${escapeHtml(decisionText)}
              ${mlV2ActionChange}
              ${eventRiskActionChange}
            </div>

            <div class="diagnostics-row">
              <span class="diag-pill ${item.scenario_direction === "downside" ? "negative" : item.scenario_direction === "long" ? "positive" : ""}">
                ${escapeHtml(scenarioLabel(item.scenario_direction || "neutral"))}
              </span>
              <span class="diag-pill">Источник: ${escapeHtml(item.source_signal_action || "—")}</span>
              <span class="diag-pill">ML: ${fmtPercent(item.ml_probability_pct)}</span>
              <span class="diag-pill ${mlV2BadgeClass(item)}">${escapeHtml(mlV2BadgeText(item))}</span>
              <span class="diag-pill ${eventRiskBadgeClass(item)}">${escapeHtml(eventRiskBadgeText(item))}</span>
              ${item.conservative_event_overlay_enabled ? `<span class="diag-pill ${eventRiskBadgeClass(item)}">Event overlay: ${escapeHtml(item.event_risk_level || "—")} · x${escapeHtml(item.event_risk_position_multiplier ?? "—")}</span>` : ""}
              <span class="diag-pill ${newsBadgeClass(item.news_assessment || {})}">
                ${escapeHtml(newsBadgeText(item))}
              </span>
              <span class="diag-pill ${macroBadgeClass(item)}">
                ${escapeHtml(macroBadgeText(item))}
              </span>
              <span class="diag-pill ${regimeBadgeClass(item)}">
                ${escapeHtml(regimeBadgeText(item))}
              </span>
              <span class="diag-pill ${auditBadgeClass(item)}">
                ${escapeHtml(auditBadgeText(item))}
              </span>
              <span class="diag-pill">RR: ${item.risk_reward_ratio === null ? "—" : escapeHtml(item.risk_reward_ratio)}</span>
              <span class="diag-pill">Позиция: ${escapeHtml((item.position_sizing || {}).max_position_pct ?? 0)}%</span>
              ${item.conservative_event_overlay_enabled && item.base_position_size_pct !== null && item.event_adjusted_position_size_pct !== null ? `<span class="diag-pill">Size: ${escapeHtml(item.base_position_size_pct)}% → ${escapeHtml(item.event_adjusted_position_size_pct)}%</span>` : ""}
            </div>

            <div class="card-actions">
              <button class="button secondary" onclick="toggleDetails('${escapeHtml(item.ticker)}')">Почему?</button>
              <a class="button ghost" href="/tickers/${encodeURIComponent(item.ticker)}">Открыть тикер</a>
            </div>

            <div id="details-${escapeHtml(item.ticker)}" class="details"></div>
          </article>
        `;
      }).join("");
    }

    function getConsumerSignalsUrl() {
      const params = new URLSearchParams();
      params.set("limit", document.getElementById("limitInput").value || "60");
      params.set("scenario", currentScenario);

      const newsFilter = document.getElementById("newsFilter");
      if (newsFilter && newsFilter.value && newsFilter.value !== "all") {
        params.set("news", newsFilter.value);
      }

      const query = document.getElementById("searchInput").value.trim();
      if (query) {
        params.set("q", query);
      }

      const mlV2Gate = document.getElementById("mlV2GateInput");
      const mlV2Threshold = document.getElementById("mlV2ThresholdInput");
      const mlV2Mode = document.getElementById("mlV2ModeInput");
      if (mlV2Gate && mlV2Gate.value === "true") {
        params.set("use_ml_v2_research_gate", "true");
        params.set("ml_v2_gate_threshold_pct", mlV2Threshold?.value || "55");
        params.set("ml_v2_gate_mode", mlV2Mode?.value || "diagnostic_only");
      }

      const eventRiskOverlay = document.getElementById("eventRiskOverlayInput");
      const eventRiskOverlayMode = document.getElementById("eventRiskOverlayModeInput");
      if (eventRiskOverlay && eventRiskOverlay.value === "true") {
        params.set("use_event_risk_overlay", "true");
        params.set("event_risk_overlay_mode", eventRiskOverlayMode?.value || "diagnostic_only");
      }
      const conservativeOverlay = document.getElementById("conservativeEventOverlayInput");
      const conservativeOverlayMode = document.getElementById("conservativeEventOverlayModeInput");
      if (conservativeOverlay && conservativeOverlay.value === "true") {
        params.set("use_conservative_event_overlay", "true");
        params.set("conservative_event_overlay_mode", conservativeOverlayMode?.value || "soft_adjust");
      }

      return `/signals/consumer.json?${params.toString()}`;
    }

    async function loadSignals() {
      const status = document.getElementById("status");
      status.textContent = "Загружаю потребительские сигналы...";

      try {
        const response = await fetch(getConsumerSignalsUrl());
        if (!response.ok) throw new Error(`HTTP ${response.status}: ${await response.text()}`);

        const data = await response.json();
        updateScenarioCounters(data.summary || {});
        const rows = data.rows || data.signals || [];
        latestRows = rows.map(normalizeRow);
        updateMarketRegimeSummary(data.summary || {});

        renderSignals();

        const now = new Date().toLocaleTimeString("ru-RU");
        status.textContent = `Обновлено: ${now}. Показано ${latestRows.length} сигналов.`;
      } catch (error) {
        status.textContent = `Ошибка загрузки: ${error.message}`;
        document.getElementById("signalsGrid").innerHTML = `<div class="empty">Не удалось загрузить сигналы.</div>`;
      }
    }

    function clearFilters() {
      document.getElementById("searchInput").value = "";
      document.getElementById("decisionFilter").value = "";
      const newsFilter = document.getElementById("newsFilter");
      if (newsFilter) newsFilter.value = "all";
      document.getElementById("sortBy").value = "decision_probability";
      loadSignals();
    }

    document.getElementById("searchInput").addEventListener("keydown", event => {
      if (event.key === "Enter") loadSignals();
    });

    document.getElementById("decisionFilter").addEventListener("change", renderSignals);
    const newsFilter = document.getElementById("newsFilter");
    if (newsFilter) newsFilter.addEventListener("change", loadSignals);
    document.getElementById("sortBy").addEventListener("change", renderSignals);
    document.getElementById("limitInput").addEventListener("change", loadSignals);
    document.getElementById("mlV2GateInput").addEventListener("change", loadSignals);
    document.getElementById("mlV2ThresholdInput").addEventListener("change", loadSignals);
    document.getElementById("mlV2ModeInput").addEventListener("change", loadSignals);
    document.getElementById("eventRiskOverlayInput").addEventListener("change", loadSignals);
    document.getElementById("eventRiskOverlayModeInput").addEventListener("change", loadSignals);

    window.loadSignals = loadSignals;
    window.clearFilters = clearFilters;
    window.toggleDetails = toggleDetails;
    window.setScenario = setScenario;

    loadSignals();
  </script>
</body>
</html>"""
