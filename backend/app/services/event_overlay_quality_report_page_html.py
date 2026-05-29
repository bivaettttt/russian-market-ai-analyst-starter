from __future__ import annotations

from app.services.ui_theme import render_page_shell


def build_event_overlay_quality_report_page_html() -> str:
    content = """
<div class="product-shell quality-product">
  <section class="product-hero">
    <div>
      <div class="action-row">
        <span class="status-badge tone-positive">Official-only by default</span>
        <span class="status-badge tone-warning">Paper validation</span>
      </div>
      <h2>Conservative Overlay Quality</h2>
      <p class="product-subtitle">Baseline vs overlay paper outcomes for official live validation snapshots.</p>
    </div>
    <div class="action-row">
      <a class="button" href="/signals/live-paper-validation/page">Live Validation</a>
      <a class="button secondary" href="/signals/event-aware/conservative-overlay-paper-tracking-page">Tracking</a>
      <a class="button secondary" href="/signals/event-aware/conservative-overlay-quality-report.csv?official_only=true">CSV</a>
    </div>
  </section>

  <section class="product-card">
    <div class="filter-row">
      <label><input id="officialOnly" type="checkbox" checked> Official only</label>
      <label><input id="includeTest" type="checkbox"> Include test</label>
      <label><input id="includeLegacy" type="checkbox"> Include legacy</label>
      <button onclick="loadAll()">Apply</button>
      <button class="secondary" onclick="showAll()">Show all snapshots</button>
    </div>
  </section>

  <section class="kpi-strip" id="metricCards"></section>
  <section id="emptyState"></section>

  <section class="product-card">
    <div class="product-card-header"><h3 class="product-card-title">Risk contribution</h3><div id="viewBadge"></div></div>
    <div class="table-wrap"><table class="data-table"><thead><tr><th>Risk</th><th>Items</th><th>Baseline PnL</th><th>Overlay PnL</th><th>Delta</th><th>Avg multiplier</th><th>Win rate</th></tr></thead><tbody id="riskRows"></tbody></table></div>
  </section>

  <section class="product-card">
    <details class="advanced-panel"><summary>Advanced report tables</summary>
      <h3>Cumulative curve</h3>
      <div class="table-wrap"><table class="data-table"><thead><tr><th>Date</th><th>Snapshot</th><th>Baseline</th><th>Overlay</th><th>Delta</th></tr></thead><tbody id="curveRows"></tbody></table></div>
      <h3>Top contributors</h3>
      <div class="table-wrap"><table class="data-table"><tbody id="contributorRows"></tbody></table></div>
      <pre id="rawReport">Loading…</pre>
    </details>
  </section>

  <section class="disclaimer-bar">Legacy/test snapshots are excluded from the official view. This is paper validation only and not investment advice.</section>
</div>
"""
    scripts = """
<script>
function esc(value){return String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
function fmt(value,suffix="",digits=3){const n=Number(value);if(!Number.isFinite(n))return "—";return n.toFixed(digits).replace(/\\.0+$/,"").replace(/(\\.\\d*?)0+$/,"$1")+suffix;}
function card(label,value,hint=""){return `<article class="metric-card"><div class="metric-label">${esc(label)}</div><div class="metric-value">${esc(value??"—")}</div><div class="metric-hint">${esc(hint)}</div></article>`;}
function badge(label,tone){return `<span class="status-badge tone-${tone}">${esc(label)}</span>`;}
async function fetchJson(url){const r=await fetch(url);const t=await r.text();if(!r.ok)throw new Error(`HTTP ${r.status}: ${t}`);return JSON.parse(t);}
function params(){const p=new URLSearchParams();p.set("limit","30");p.set("official_only",officialOnly.checked?"true":"false");p.set("include_test",includeTest.checked?"true":"false");p.set("include_legacy",includeLegacy.checked?"true":"false");return p;}
function render(data, official){
 const s=data.summary||{};
 viewBadge.innerHTML=official?badge("Official validation view","positive"):badge("All local snapshots","warning");
 metricCards.innerHTML=[
  card("Snapshots",s.snapshots_total,`${s.snapshots_open||0} open`),
  card("Items",s.items_total,`${s.items_evaluated||0} evaluated`),
  card("Baseline PnL",fmt(s.baseline_total_pnl_pct,"%"),"paper account"),
  card("Overlay PnL",fmt(s.overlay_total_pnl_pct,"%"),"adjusted exposure"),
  card("Overlay delta",fmt(s.overlay_delta_pnl_pct,"%"),"overlay minus baseline"),
  card("Avg reduction",fmt(s.avg_exposure_reduction_pct,"%"),"exposure"),
  card("Avg multiplier",fmt(s.avg_multiplier,"",3),"risk sizing"),
  card("Quality",s.quality_label,"official-only"),
 ].join("");
 emptyState.innerHTML=(s.items_evaluated||0)>0?"":`<div class="empty-state"><h3>No evaluated outcomes yet</h3><p class="muted">The first official snapshot can be evaluated after its horizon date. Latest official date: ${esc(s.last_snapshot_date||"—")}.</p></div>`;
 riskRows.innerHTML=(data.by_risk_level||[]).map(r=>`<tr><td>${esc(r.risk_level)}</td><td>${esc(r.items)}</td><td>${fmt(r.baseline_pnl_pct,"%")}</td><td>${fmt(r.overlay_pnl_pct,"%")}</td><td>${fmt(r.delta_pnl_pct,"%")}</td><td>${fmt(r.avg_multiplier,"",3)}</td><td>${fmt(r.win_rate_pct,"%")}</td></tr>`).join("")||`<tr><td colspan="7" class="muted">No evaluated risk contribution yet.</td></tr>`;
 curveRows.innerHTML=(data.cumulative_curve||[]).map(r=>`<tr><td>${esc(r.snapshot_date)}</td><td>#${esc(r.snapshot_id)}</td><td>${fmt(r.baseline_cumulative_pnl_pct,"%")}</td><td>${fmt(r.overlay_cumulative_pnl_pct,"%")}</td><td>${fmt(r.delta_cumulative_pnl_pct,"%")}</td></tr>`).join("")||`<tr><td colspan="5" class="muted">No cumulative curve yet.</td></tr>`;
 const contrib=[...(data.top_positive_contributors||[]).slice(0,5),...(data.top_negative_contributors||[]).slice(0,5)];
 contributorRows.innerHTML=contrib.map(r=>`<tr><td>${esc(r.ticker)}</td><td>${fmt(r.overlay_delta_pnl_pct,"%")}</td><td>${esc(r.event_risk_level)}</td></tr>`).join("")||`<tr><td class="muted">No contributors yet.</td></tr>`;
 rawReport.textContent=JSON.stringify(data,null,2);
}
async function loadAll(){const p=params();render(await fetchJson(`/signals/event-aware/conservative-overlay-quality-report?${p}`),officialOnly.checked);}
function showAll(){officialOnly.checked=false;includeTest.checked=true;includeLegacy.checked=true;loadAll();}
loadAll();
</script>
"""
    return render_page_shell(
        title="Conservative Overlay Quality",
        subtitle="Official-only paper validation report.",
        active="quality",
        content=content,
        body_class="product-shell-body",
        extra_scripts=scripts,
    )
