from __future__ import annotations

from app.services.ui_theme import render_page_shell


def build_signals_page_html() -> str:
    content = """
<div class="product-shell signals-product">
  <section class="product-hero">
    <div>
      <div class="action-row">
        <span class="status-badge tone-accent">Live Paper Validation Alpha</span>
        <span class="status-badge tone-info">MOEX equities</span>
        <span class="status-badge tone-warning">Paper tracking only</span>
      </div>
      <h2>Signals</h2>
      <p class="product-subtitle">MOEX equities watchlist with conservative event-risk overlay, clear risk labels and paper exposure diagnostics.</p>
    </div>
    <div class="action-row">
      <a class="button" href="/signals/live-paper-validation/page">Live Validation</a>
      <a class="button secondary" href="/signals/event-aware/conservative-overlay-quality-report-page">Quality</a>
      <a class="button secondary" href="/signals/research-hub-page">Research Hub</a>
    </div>
  </section>

  <section class="kpi-strip" id="statusStrip">
    <article class="metric-card"><div class="metric-label">Market data</div><div class="metric-value" id="marketStatus">Loading</div><div class="metric-hint" id="marketHint">Checking freshness</div></article>
    <article class="metric-card"><div class="metric-label">Live validation</div><div class="metric-value" id="officialStatus">Loading</div><div class="metric-hint" id="officialHint">Official snapshots</div></article>
    <article class="metric-card"><div class="metric-label">Quality</div><div class="metric-value" id="qualityStatus">Pending</div><div class="metric-hint" id="qualityHint">Official-only view</div></article>
    <article class="metric-card"><div class="metric-label">Paper mode</div><div class="metric-value">No real orders</div><div class="metric-hint">Production defaults unchanged</div></article>
  </section>

  <section class="product-card">
    <div class="product-card-header">
      <div>
        <h3 class="product-card-title">Watchlist filters</h3>
        <div class="product-card-subtitle">Keep the page clean; advanced diagnostics are collapsed inside each ticker.</div>
      </div>
      <div class="action-row">
        <button id="refreshButton" onclick="loadSignals()">Refresh</button>
        <button class="secondary" onclick="resetFilters()">Reset</button>
      </div>
    </div>
    <div class="filter-row">
      <label>Search <input id="searchInput" placeholder="SBER, GAZP, LKOH"></label>
      <label>Rows <select id="limitInput"><option value="20">20</option><option value="40" selected>40</option><option value="80">80</option></select></label>
      <label>Action <select id="actionFilter"><option value="">All</option><option value="positive">Buy / consider</option><option value="neutral">Watch</option><option value="negative">Avoid / risk</option></select></label>
      <label>Risk <select id="riskFilter"><option value="">All</option><option value="low">Low</option><option value="moderate">Moderate</option><option value="elevated">Elevated</option><option value="high">High</option><option value="extreme">Extreme</option></select></label>
      <label>Scenario <select id="scenarioInput"><option value="long" selected>Long candidates</option><option value="downside">Downside risk</option><option value="all">All</option></select></label>
      <label>Conservative overlay <select id="conservativeOverlayInput"><option value="false" selected>Off</option><option value="true">On</option></select></label>
      <label>Advanced <select id="advancedInput"><option value="false" selected>Hidden</option><option value="true">Show</option></select></label>
    </div>
  </section>

  <section class="kpi-strip">
    <article class="metric-card"><div class="metric-label">Shown</div><div class="metric-value" id="metricShown">—</div><div class="metric-hint">Filtered cards</div></article>
    <article class="metric-card"><div class="metric-label">Buy / consider</div><div class="metric-value" id="metricPositive">—</div><div class="metric-hint">Positive actions</div></article>
    <article class="metric-card"><div class="metric-label">Watch</div><div class="metric-value" id="metricNeutral">—</div><div class="metric-hint">Neutral actions</div></article>
    <article class="metric-card"><div class="metric-label">Avoid / risk</div><div class="metric-value" id="metricNegative">—</div><div class="metric-hint">Risk or veto</div></article>
  </section>

  <section class="signal-list" id="signalsList">
    <div class="empty-state"><h3>Loading signals</h3><p class="muted">Fetching consumer watchlist.</p></div>
  </section>

  <section class="disclaimer-bar">
    Conservative Event Overlay adjusts paper exposure diagnostics only. This interface is not investment advice and does not place trades.
  </section>
</div>
"""

    scripts = """
<script>
const state = { rows: [] };

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
function num(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}
function fmt(value, suffix = "", digits = 1) {
  const n = num(value);
  if (n === null) return "—";
  return n.toFixed(digits).replace(/\\.0+$/, "").replace(/(\\.\\d*?)0+$/, "$1") + suffix;
}
function firstArray(values) {
  for (const value of values) if (Array.isArray(value) && value.length) return value;
  return [];
}
function source(row) {
  return Object.assign({}, row.forecast || {}, row.signal || {}, row);
}
function actionTone(item) {
  const text = `${item.action} ${item.recommendation} ${item.decision_level}`.toLowerCase();
  if (text.includes("avoid") || text.includes("negative") || text.includes("risk") || text.includes("не покуп")) return "negative";
  if (text.includes("buy") || text.includes("consider") || text.includes("positive") || text.includes("покуп")) return "positive";
  return "neutral";
}
function riskTone(level) {
  const text = String(level || "").toLowerCase();
  if (text === "low") return "risk-low";
  if (text === "moderate") return "risk-moderate";
  if (text === "elevated") return "risk-elevated";
  if (text === "high") return "risk-high";
  if (text === "extreme") return "risk-extreme";
  return "neutral";
}
function normalize(row) {
  const s = source(row);
  const reasons = firstArray([
    s.event_risk_reasons,
    s.audit_top_strengths,
    s.audit_top_weaknesses,
    (s.signal_audit || {}).top_strengths,
    (s.signal_audit || {}).top_weaknesses,
  ]).slice(0, 3);
  return {
    raw: row,
    ticker: s.ticker || row.ticker || "—",
    name: s.name || s.company_name || row.name || "",
    action: s.consumer_action || s.action || s.recommendation || "watch",
    recommendation: s.recommendation || s.label || "Watch",
    decision_level: s.decision_level || "",
    probability: num(s.target_probability_pct ?? s.ml_probability_pct ?? s.rule_probability_pct),
    price: num(s.current_price ?? s.price),
    target: num(s.target_price),
    potential: num(s.potential_pct ?? s.expected_return_pct ?? s.target_potential_pct),
    risk: s.event_risk_level || s.risk_level || "unknown",
    eventScore: num(s.event_risk_score),
    multiplier: num(s.event_risk_position_multiplier ?? s.event_position_multiplier),
    baseSize: num(s.base_position_size_pct),
    adjustedSize: num(s.event_adjusted_position_size_pct),
    reasons,
    overlayEnabled: Boolean(s.conservative_event_overlay_enabled),
    overlayConfig: s.conservative_event_overlay_config_id || "",
    researchBasis: s.conservative_event_overlay_research_basis || s.event_risk_research_basis || "",
    audit: s.signal_audit || {},
    marketRegime: s.market_regime || {},
    detailUrl: `/ticker/${encodeURIComponent(s.ticker || row.ticker || "")}`,
  };
}
function statusBadge(label, tone) {
  return `<span class="status-badge tone-${esc(tone)}">${esc(label)}</span>`;
}
function mini(label, value) {
  return `<div class="mini-metric"><div class="mini-label">${esc(label)}</div><div class="mini-value">${esc(value)}</div></div>`;
}
function renderCard(item) {
  const tone = actionTone(item);
  const risk = item.risk || "unknown";
  const reasons = item.reasons.length
    ? item.reasons.map(r => `<div class="signal-reason">• ${esc(r)}</div>`).join("")
    : `<div class="signal-reason">• No concise reason available yet.</div>`;
  const size = item.baseSize !== null && item.adjustedSize !== null
    ? `${fmt(item.baseSize, "%")} → ${fmt(item.adjustedSize, "%")}`
    : (item.multiplier !== null ? `x${fmt(item.multiplier, "", 2)}` : "—");
  const multiplierText = item.overlayEnabled && item.multiplier !== null ? `x${fmt(item.multiplier, "", 2)}` : "Overlay off";
  const exposureText = item.overlayEnabled ? size : "Enable overlay";
  const advanced = advancedInput.value === "true"
    ? `<details class="advanced-panel" open><summary>Advanced diagnostics</summary><pre>${esc(JSON.stringify({
        overlay_config: item.overlayConfig,
        research_basis: item.researchBasis,
        audit: item.audit,
        market_regime: item.marketRegime
      }, null, 2))}</pre></details>`
    : `<details class="advanced-panel"><summary>Advanced diagnostics</summary><pre>${esc(JSON.stringify({
        overlay_config: item.overlayConfig,
        research_basis: item.researchBasis,
        audit: item.audit,
        market_regime: item.marketRegime
      }, null, 2))}</pre></details>`;
  return `<article class="signal-card">
    <div class="signal-main">
      <a class="ticker-symbol" href="${esc(item.detailUrl)}">${esc(item.ticker)}</a>
      <div class="ticker-name">${esc(item.name || "MOEX equity")}</div>
      <div class="action-row">${statusBadge(item.recommendation || item.action, tone)}${statusBadge(risk, riskTone(risk))}</div>
    </div>
    <div>
      <div class="signal-reasons">${reasons}</div>
      ${advanced}
    </div>
    <div class="signal-metrics">
      ${mini("Probability", fmt(item.probability, "%"))}
      ${mini("Target", item.target !== null ? fmt(item.target, " ₽", 2) : "—")}
      ${mini("Event multiplier", multiplierText)}
      ${mini("Paper exposure", exposureText)}
      <a class="button secondary" href="${esc(item.detailUrl)}">Details</a>
    </div>
  </article>`;
}
function applyFilters() {
  const query = searchInput.value.trim().toLowerCase();
  const action = actionFilter.value;
  const risk = riskFilter.value;
  let rows = state.rows;
  if (query) rows = rows.filter(item => `${item.ticker} ${item.name}`.toLowerCase().includes(query));
  if (action) rows = rows.filter(item => actionTone(item) === action);
  if (risk) rows = rows.filter(item => String(item.risk || "").toLowerCase() === risk);
  metricShown.textContent = rows.length;
  metricPositive.textContent = rows.filter(item => actionTone(item) === "positive").length;
  metricNeutral.textContent = rows.filter(item => actionTone(item) === "neutral").length;
  metricNegative.textContent = rows.filter(item => actionTone(item) === "negative").length;
  signalsList.innerHTML = rows.length
    ? rows.map(renderCard).join("")
    : `<div class="empty-state"><h3>No matching signals</h3><p class="muted">Try a wider filter or refresh local data.</p></div>`;
}
function consumerUrl() {
  const p = new URLSearchParams();
  p.set("limit", limitInput.value || "40");
  p.set("scenario", scenarioInput.value || "long");
  if (conservativeOverlayInput.value === "true") {
    p.set("use_conservative_event_overlay", "true");
    p.set("conservative_event_overlay_mode", "soft_adjust");
  }
  return `/signals/consumer.json?${p.toString()}`;
}
async function loadSignals() {
  refreshButton.classList.add("is-loading");
  signalsList.innerHTML = `<div class="empty-state"><h3>Loading signals</h3><p class="muted">Fetching consumer watchlist.</p></div>`;
  try {
    const res = await fetch(consumerUrl());
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.rows = (data.rows || data.signals || []).map(normalize);
    applyFilters();
  } catch (err) {
    signalsList.innerHTML = `<div class="empty-state"><h3>Could not load signals</h3><p class="muted">${esc(err.message || err)}</p></div>`;
  } finally {
    refreshButton.classList.remove("is-loading");
  }
}
async function loadStatus() {
  try {
    const [fresh, official, quality] = await Promise.all([
      fetch("/signals/daily-ops/market-data-freshness").then(r => r.json()),
      fetch("/signals/live-paper-validation/official-summary").then(r => r.json()),
      fetch("/signals/event-aware/conservative-overlay-quality-report?official_only=true").then(r => r.json()),
    ]);
    const fs = fresh.summary || {};
    marketStatus.textContent = fs.is_stale ? "Stale" : (fs.latest_candle_date ? "Fresh" : "No data");
    marketHint.textContent = fs.latest_candle_date ? `Latest candle ${fs.latest_candle_date}` : "Run market data refresh";
    const os = official.summary || {};
    officialStatus.textContent = os.has_official_snapshot ? `#${os.latest_official_snapshot_id}` : "Not started";
    officialHint.textContent = os.has_official_snapshot ? `Next evaluation ${os.next_evaluation_date || "—"}` : "Create official snapshot";
    const qs = quality.summary || {};
    qualityStatus.textContent = qs.quality_label || "Pending";
    qualityHint.textContent = `${qs.items_evaluated || 0} evaluated items`;
  } catch (err) {
    marketStatus.textContent = "Unavailable";
    officialStatus.textContent = "Unavailable";
  }
}
function resetFilters() {
  searchInput.value = "";
  actionFilter.value = "";
  riskFilter.value = "";
  scenarioInput.value = "long";
  conservativeOverlayInput.value = "false";
  advancedInput.value = "false";
  loadSignals();
}
[searchInput, actionFilter, riskFilter, advancedInput].forEach(el => el.addEventListener("input", applyFilters));
[limitInput, scenarioInput, conservativeOverlayInput].forEach(el => el.addEventListener("change", loadSignals));
searchInput.addEventListener("keydown", e => { if (e.key === "Enter") applyFilters(); });
loadStatus();
loadSignals();
</script>
"""
    return render_page_shell(
        title="Signals",
        subtitle="User-facing market signal dashboard. Advanced research is available in Research Hub.",
        active="signals",
        content=content,
        body_class="product-shell-body",
        extra_scripts=scripts,
    )
