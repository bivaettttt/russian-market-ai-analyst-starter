from __future__ import annotations

from app.services.ui_theme import render_page_shell


def build_event_overlay_paper_tracking_page_html() -> str:
    content = """
<div class="product-shell tracking-product">
  <section class="product-hero">
    <div>
      <div class="action-row"><span class="status-badge tone-info">Snapshot lifecycle</span><span class="status-badge tone-warning">Local DB only</span></div>
      <h2>Paper Tracking</h2>
      <p class="product-subtitle">Official, manual, test and legacy conservative-overlay paper snapshots with safe cleanup controls.</p>
    </div>
    <div class="action-row">
      <a class="button" href="/signals/live-paper-validation/page">Live Validation</a>
      <a class="button secondary" href="/signals/event-aware/conservative-overlay-quality-report-page">Quality</a>
      <a class="button secondary" href="/signals/event-aware/conservative-overlay-paper-snapshots.csv">CSV</a>
    </div>
  </section>

  <section class="product-card">
    <div class="filter-row">
      <button class="secondary" onclick="setView('official')">Official</button>
      <button class="secondary" onclick="setView('all')">All</button>
      <button class="secondary" onclick="setView('test')">Test</button>
      <button class="secondary" onclick="setView('legacy')">Legacy</button>
      <button class="secondary" onclick="setView('ready')">Ready</button>
      <button onclick="loadAll()">Refresh</button>
    </div>
  </section>

  <section class="kpi-strip" id="cards"></section>

  <section class="product-card">
    <div class="product-card-header"><h3 class="product-card-title">Snapshots</h3><div id="viewBadge"></div></div>
    <div class="table-wrap"><table class="data-table"><thead><tr><th>Snapshot</th><th>Type</th><th>Status</th><th>Exposure</th><th>Next evaluation</th><th>Actions</th></tr></thead><tbody id="snapshotRows"></tbody></table></div>
  </section>

  <section class="product-card">
    <h3 class="product-card-title">Cleanup</h3>
    <p class="product-card-subtitle">Dry-run first. Official snapshots are kept by default.</p>
    <div class="action-row">
      <button class="secondary" onclick="cleanup(true)">Dry-run legacy/test cleanup</button>
      <button onclick="cleanup(false)">Delete legacy/test candidates</button>
    </div>
    <pre id="cleanupOutput">No cleanup run yet.</pre>
  </section>

  <section class="product-card">
    <h3 class="product-card-title">Snapshot detail</h3>
    <div id="detailCards" class="kpi-strip"></div>
    <details class="advanced-panel"><summary>Items</summary><div class="table-wrap"><table class="data-table"><thead><tr><th>Ticker</th><th>Action</th><th>Size</th><th>Risk</th><th>Return</th><th>Delta</th></tr></thead><tbody id="detailRows"></tbody></table></div></details>
  </section>
</div>
"""
    scripts = """
<script>
let currentView="official";
function esc(value){return String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
function fmt(value,suffix="",digits=2){const n=Number(value);if(!Number.isFinite(n))return "—";return n.toFixed(digits).replace(/\\.0+$/,"").replace(/(\\.\\d*?)0+$/,"$1")+suffix;}
function badge(label,tone){return `<span class="status-badge tone-${tone}">${esc(label)}</span>`;}
function typeBadge(row){const type=row.snapshot_type||"manual";const tone=type==="official"?"positive":type==="legacy"?"negative":type==="test"?"warning":"info";let html=badge(type,tone);if(row.has_zero_exposure)html+=badge("zero exposure","negative");return html;}
function card(label,value,hint=""){return `<article class="metric-card"><div class="metric-label">${esc(label)}</div><div class="metric-value">${esc(value??"—")}</div><div class="metric-hint">${esc(hint)}</div></article>`;}
async function fetchJson(url,options){const r=await fetch(url,options||{});const t=await r.text();if(!r.ok)throw new Error(`HTTP ${r.status}: ${t}`);return JSON.parse(t);}
function params(){const p=new URLSearchParams();p.set("limit","80");if(currentView==="official"){p.set("official_only","true");}else if(currentView==="test"){p.set("include_legacy","false");}else if(currentView==="legacy"){p.set("include_test","false");}return p;}
function rowMatches(row){if(currentView==="test")return row.is_test;if(currentView==="legacy")return row.is_legacy||row.has_zero_exposure;if(currentView==="ready")return ["open","partially_evaluated"].includes(row.status)&&row.next_evaluation_date&&row.next_evaluation_date<=new Date().toISOString().slice(0,10);return true;}
function renderList(data){const rows=(data.rows||[]).filter(rowMatches);viewBadge.innerHTML=badge(`${currentView} view`,currentView==="official"?"positive":"info");snapshotRows.innerHTML=rows.map(row=>`<tr><td><strong>#${esc(row.id)} ${esc(row.name||"")}</strong><div class="muted">${esc(row.snapshot_date)}</div></td><td>${typeBadge(row)}<div class="muted">${esc(row.classification_reason||"")}</div></td><td>${esc(row.status)}</td><td>${fmt(row.baseline_total_exposure,"%")} → ${fmt(row.overlay_total_exposure,"%")}<div class="muted">x${fmt(row.avg_multiplier,"",3)}</div></td><td>${esc(row.next_evaluation_date||"—")}</td><td><button class="secondary" onclick="detail(${row.id})">Detail</button> <button class="secondary" onclick="evaluateOne(${row.id})">Evaluate</button></td></tr>`).join("")||`<tr><td colspan="6" class="muted">No snapshots for this view.</td></tr>`;}
function renderDash(data){const s=data.summary||{};cards.innerHTML=[card("Snapshots",s.total_snapshots??s.snapshots,"current filter"),card("Open",s.open_snapshots,"waiting"),card("Ready",s.ready_to_evaluate_snapshots,"evaluation due"),card("Evaluated",s.evaluated_snapshots,"completed"),card("Baseline PnL",fmt(s.baseline_total_pnl_pct??s.aggregate_baseline_pnl_pct,"%"),"paper"),card("Overlay PnL",fmt(s.overlay_total_pnl_pct??s.aggregate_overlay_pnl_pct,"%"),"paper"),card("Delta",fmt(s.overlay_delta_pnl_pct??s.aggregate_overlay_delta_pnl_pct,"%"),"overlay-baseline"),card("Avg multiplier",fmt(s.avg_multiplier,"",3),"sizing")].join("");}
async function loadAll(){const p=params();const [list,dash]=await Promise.all([fetchJson(`/signals/event-aware/conservative-overlay-paper-snapshots?${p}`),fetchJson(`/signals/event-aware/conservative-overlay-paper-dashboard?${p}`)]);renderList(list);renderDash(dash);}
function setView(view){currentView=view;loadAll();}
async function detail(id){const data=await fetchJson(`/signals/event-aware/conservative-overlay-paper-snapshots/${id}`);const s=data.summary||{};detailCards.innerHTML=[card("Snapshot",`#${id}`,data.name||""),card("Items",s.items||0,"saved rows"),card("Evaluated",s.evaluated_items||0,"with outcome"),card("Baseline PnL",fmt(s.baseline_realized_pnl_pct,"%"),"paper"),card("Overlay PnL",fmt(s.overlay_realized_pnl_pct,"%"),"paper"),card("Delta",fmt(s.overlay_delta_pnl_pct,"%"),"overlay-baseline")].join("");detailRows.innerHTML=(data.items||[]).slice(0,120).map(r=>`<tr><td>${esc(r.ticker)}</td><td>${esc(r.action)}</td><td>${fmt(r.base_position_size_pct,"%")} → ${fmt(r.overlay_position_size_pct,"%")}</td><td>${esc(r.event_risk_level||"—")}</td><td>${fmt(r.realized_return_pct,"%")}</td><td>${fmt(r.overlay_delta_pnl_pct,"%")}</td></tr>`).join("")||`<tr><td colspan="6" class="muted">No items.</td></tr>`;}
async function evaluateOne(id){cleanupOutput.textContent=JSON.stringify(await fetchJson(`/signals/event-aware/conservative-overlay-paper-snapshots/${id}/evaluate`,{method:"POST"}),null,2);await loadAll();await detail(id);}
async function cleanup(dryRun){if(!dryRun&&!confirm("Delete legacy/test snapshots? Official snapshots are kept."))return;const p=new URLSearchParams();p.set("dry_run",dryRun?"true":"false");p.set("delete_legacy_zero_exposure","true");p.set("delete_test_snapshots","true");p.set("keep_official","true");cleanupOutput.textContent=JSON.stringify(await fetchJson(`/signals/event-aware/conservative-overlay-paper-cleanup?${p}`,{method:"POST"}),null,2);await loadAll();}
loadAll();
</script>
"""
    return render_page_shell(
        title="Paper Tracking",
        subtitle="Snapshot lifecycle, official hygiene and safe cleanup.",
        active="tracking",
        content=content,
        body_class="product-shell-body",
        extra_scripts=scripts,
    )
