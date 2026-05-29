from __future__ import annotations

import html

from app.services.ui_theme import render_page_shell


def build_ticker_page_html(ticker: str) -> str:
    safe_ticker = html.escape((ticker or "").upper().strip() or "TICKER")
    content = f"""
<div class="product-shell ticker-product" data-ticker="{safe_ticker}">
  <section class="product-hero">
    <div>
      <div class="action-row">
        <a class="button secondary" href="/signals">Back to Signals</a>
        <span class="status-badge tone-warning">Paper validation only</span>
      </div>
      <h2 id="tickerTitle">{safe_ticker}</h2>
      <p class="product-subtitle" id="tickerSubtitle">Loading ticker signal, conservative overlay and risk context.</p>
    </div>
    <div class="action-row">
      <a class="button" id="jsonLink" href="/signals/consumer/{safe_ticker}.json?use_conservative_event_overlay=true">JSON</a>
      <a class="button secondary" href="/signals/live-paper-validation/page">Live Validation</a>
      <a class="button secondary" href="/signals/event-aware/conservative-overlay-quality-report-page">Quality</a>
    </div>
  </section>

  <section class="kpi-strip">
    <article class="metric-card"><div class="metric-label">Signal</div><div class="metric-value" id="signalValue">—</div><div class="metric-hint" id="signalHint">Current action</div></article>
    <article class="metric-card"><div class="metric-label">Probability</div><div class="metric-value" id="probabilityValue">—</div><div class="metric-hint">Target probability</div></article>
    <article class="metric-card"><div class="metric-label">Risk level</div><div class="metric-value" id="riskValue">—</div><div class="metric-hint" id="riskHint">Event-aware risk</div></article>
    <article class="metric-card"><div class="metric-label">Exposure</div><div class="metric-value" id="exposureValue">—</div><div class="metric-hint">Base → overlay</div></article>
    <article class="metric-card"><div class="metric-label">Event multiplier</div><div class="metric-value" id="multiplierValue">—</div><div class="metric-hint">Conservative overlay</div></article>
    <article class="metric-card"><div class="metric-label">Market regime</div><div class="metric-value" id="regimeValue">—</div><div class="metric-hint">Current filter context</div></article>
  </section>

  <section class="product-card">
    <div class="product-card-header">
      <div>
        <h3 class="product-card-title">Why this signal?</h3>
        <div class="product-card-subtitle">Concise explanation first; raw diagnostics are collapsed below.</div>
      </div>
      <div id="badges" class="action-row"></div>
    </div>
    <div id="reasonList" class="signal-reasons"></div>
  </section>

  <section class="product-card">
    <div class="product-card-header">
      <div>
        <h3 class="product-card-title">Conservative Event Overlay</h3>
        <div class="product-card-subtitle">Paper exposure adjustment only. No action downgrade and no real orders.</div>
      </div>
    </div>
    <div class="kpi-strip">
      <div class="mini-metric"><div class="mini-label">Base size</div><div class="mini-value" id="baseSize">—</div></div>
      <div class="mini-metric"><div class="mini-label">Adjusted size</div><div class="mini-value" id="adjustedSize">—</div></div>
      <div class="mini-metric"><div class="mini-label">Risk score</div><div class="mini-value" id="riskScore">—</div></div>
      <div class="mini-metric"><div class="mini-label">Action effect</div><div class="mini-value" id="actionEffect">—</div></div>
    </div>
  </section>

  <details class="advanced-panel">
    <summary>Advanced technical audit</summary>
    <pre id="rawDiagnostics">Loading…</pre>
  </details>

  <section class="disclaimer-bar">This page is a research and paper-validation interface. It is not investment advice and does not place trades.</section>
</div>
"""

    scripts = f"""
<script>
const ticker = "{safe_ticker}";
function esc(value) {{
  return String(value ?? "").replace(/[&<>"']/g, c => ({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}}[c]));
}}
function num(value) {{ const n = Number(value); return Number.isFinite(n) ? n : null; }}
function fmt(value, suffix = "", digits = 1) {{
  const n = num(value);
  if (n === null) return "—";
  return n.toFixed(digits).replace(/\\.0+$/, "").replace(/(\\.\\d*?)0+$/, "$1") + suffix;
}}
function badge(label, tone) {{ return `<span class="status-badge tone-${{tone}}">${{esc(label)}}</span>`; }}
function toneForRisk(value) {{
  const text = String(value || "").toLowerCase();
  if (text === "low") return "positive";
  if (text === "moderate" || text === "elevated") return "warning";
  if (text === "high" || text === "extreme") return "negative";
  return "neutral";
}}
function toneForAction(value) {{
  const text = String(value || "").toLowerCase();
  if (text.includes("avoid") || text.includes("risk") || text.includes("negative") || text.includes("не покуп")) return "negative";
  if (text.includes("buy") || text.includes("consider") || text.includes("positive") || text.includes("покуп")) return "positive";
  return "neutral";
}}
function source(payload) {{
  return Object.assign({{}}, payload.forecast || {{}}, payload.signal || {{}}, payload);
}}
async function loadTicker() {{
  try {{
    const res = await fetch(`/signals/consumer/${{encodeURIComponent(ticker)}}.json?use_conservative_event_overlay=true`);
    if (!res.ok) throw new Error(`HTTP ${{res.status}}`);
    const payload = await res.json();
    const s = source(payload);
    tickerTitle.textContent = s.ticker || ticker;
    tickerSubtitle.textContent = s.name || s.company_name || "MOEX equity";
    jsonLink.href = `/signals/consumer/${{encodeURIComponent(s.ticker || ticker)}}.json?use_conservative_event_overlay=true`;
    const action = s.recommendation || s.consumer_action || s.action || "Watch";
    const risk = s.event_risk_level || s.risk_level || "unknown";
    signalValue.textContent = action;
    signalHint.textContent = s.decision_reason || s.scenario_reason || "Consumer signal";
    probabilityValue.textContent = fmt(s.target_probability_pct ?? s.ml_probability_pct ?? s.rule_probability_pct, "%");
    riskValue.textContent = risk;
    riskHint.textContent = s.event_risk_score !== undefined ? `Score ${{fmt(s.event_risk_score, "", 1)}}` : "No event score";
    const base = num(s.base_position_size_pct);
    const adjusted = num(s.event_adjusted_position_size_pct);
    exposureValue.textContent = base !== null && adjusted !== null ? `${{fmt(base, "%")}} → ${{fmt(adjusted, "%")}}` : "—";
    multiplierValue.textContent = s.event_risk_position_multiplier !== undefined ? `x${{fmt(s.event_risk_position_multiplier, "", 2)}}` : "—";
    const regime = s.market_regime || {{}};
    regimeValue.textContent = regime.regime || regime.label || s.market_regime_gate || "—";
    badges.innerHTML = badge(action, toneForAction(action)) + badge(risk, toneForRisk(risk));
    const reasons = [
      ...(Array.isArray(s.event_risk_reasons) ? s.event_risk_reasons : []),
      ...(Array.isArray(s.audit_top_strengths) ? s.audit_top_strengths : []),
      ...(Array.isArray(s.audit_top_weaknesses) ? s.audit_top_weaknesses : []),
      ...((s.signal_audit || {{}}).top_strengths || []),
      ...((s.signal_audit || {{}}).top_weaknesses || []),
    ].filter(Boolean).slice(0, 6);
    reasonList.innerHTML = reasons.length
      ? reasons.map(item => `<div class="signal-reason">• ${{esc(item)}}</div>`).join("")
      : `<div class="signal-reason">• No concise explanation available for this ticker yet.</div>`;
    baseSize.textContent = base !== null ? fmt(base, "%") : "—";
    adjustedSize.textContent = adjusted !== null ? fmt(adjusted, "%") : "—";
    riskScore.textContent = fmt(s.event_risk_score, "", 1);
    actionEffect.textContent = s.event_risk_action_effect || "none";
    rawDiagnostics.textContent = JSON.stringify({{
      forecast: payload.forecast || payload,
      conservative_overlay: {{
        enabled: s.conservative_event_overlay_enabled,
        config_id: s.conservative_event_overlay_config_id,
        research_basis: s.conservative_event_overlay_research_basis,
      }},
      audit: s.signal_audit || null,
      market_regime: s.market_regime || null,
    }}, null, 2);
  }} catch (err) {{
    tickerSubtitle.textContent = "Ticker data is unavailable.";
    reasonList.innerHTML = `<div class="empty-state"><h3>No ticker data</h3><p class="muted">${{esc(err.message || err)}}</p></div>`;
    rawDiagnostics.textContent = String(err);
  }}
}}
loadTicker();
</script>
"""
    return render_page_shell(
        title=f"{safe_ticker} Detail",
        subtitle="Ticker signal, event overlay and paper exposure summary.",
        active="signals",
        content=content,
        body_class="product-shell-body",
        extra_scripts=scripts,
    )
