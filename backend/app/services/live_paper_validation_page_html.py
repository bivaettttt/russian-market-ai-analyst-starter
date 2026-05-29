from __future__ import annotations

from app.services.ui_theme import render_page_shell


def build_live_paper_validation_page_html() -> str:
    content = """
<div class="product-shell live-validation-product">
  <section class="product-hero">
    <div>
      <div class="action-row">
        <span class="status-badge tone-accent">Official paper validation</span>
        <span class="status-badge tone-warning">No real orders</span>
      </div>
      <h2>Live Validation</h2>
      <p class="product-subtitle">Official snapshot cockpit for conservative event-overlay paper validation.</p>
    </div>
    <div class="action-row">
      <a class="button" href="/signals/event-aware/conservative-overlay-quality-report-page">Quality Report</a>
      <a class="button secondary" href="/signals/event-aware/conservative-overlay-paper-tracking-page">Tracking</a>
    </div>
  </section>

  <section class="kpi-strip" id="statusCards"></section>

  <section class="product-card">
    <div class="product-card-header">
      <div>
        <h3 class="product-card-title">Latest official snapshot</h3>
        <div class="product-card-subtitle">Test and legacy snapshots are not shown as primary validation data.</div>
      </div>
      <div id="officialBadges" class="action-row"></div>
    </div>
    <div class="kpi-strip" id="officialCards"></div>
    <div class="risk-distribution" id="riskDistribution"></div>
  </section>

  <section class="product-card">
    <div class="product-card-header">
      <div>
        <h3 class="product-card-title">Actions</h3>
        <div class="product-card-subtitle">Dry-run first, then start official validation only with fresh local market data.</div>
      </div>
    </div>
    <div class="filter-row">
      <label>Name <input id="name" value="official-daily"></label>
      <label>Limit <input id="limit" type="number" min="1" max="500" value="100"></label>
      <label>Horizon <input id="horizon" type="number" min="1" max="120" value="20"></label>
      <label><input id="requireFresh" type="checkbox" checked> require fresh data</label>
      <button onclick="dryRun()">Dry run</button>
      <button onclick="start(true)">Start official</button>
      <button class="secondary" onclick="start(false)">Start without refresh</button>
      <button class="secondary" onclick="evaluateOfficialReady()">Evaluate ready</button>
      <button class="secondary" onclick="loadStatus()">Refresh</button>
    </div>
  </section>

  <section class="product-card">
    <h3 class="product-card-title">Validation timeline</h3>
    <div class="progress-steps" id="timeline"></div>
  </section>

  <section class="product-card">
    <h3 class="product-card-title">Terminal routine</h3>
    <pre><code>cd backend
python3 -m app.tasks.market_daily_ops refresh --skip-universe-refresh --max-tickers 150 --days 120
python3 -m app.tasks.live_paper_validation start --name official-daily --limit 100 --horizon-days 20</code></pre>
    <details class="advanced-panel"><summary>Raw last result</summary><pre id="output">Ready.</pre></details>
  </section>

  <section class="disclaimer-bar">Paper validation only. No real trades, no investment advice, production defaults unchanged.</section>
</div>
"""
    scripts = """
<script>
function esc(value){return String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
function fmt(value, suffix="", digits=2){const n=Number(value);if(!Number.isFinite(n))return "—";return n.toFixed(digits).replace(/\\.0+$/,"").replace(/(\\.\\d*?)0+$/,"$1")+suffix;}
function card(label,value,hint=""){return `<article class="metric-card"><div class="metric-label">${esc(label)}</div><div class="metric-value">${esc(value??"—")}</div><div class="metric-hint">${esc(hint)}</div></article>`;}
function badge(label,tone){return `<span class="status-badge tone-${tone}">${esc(label)}</span>`;}
async function fetchJson(url,options){const r=await fetch(url,options||{});const t=await r.text();if(!r.ok)throw new Error(`HTTP ${r.status}: ${t}`);return JSON.parse(t);}
function baseParams(){const p=new URLSearchParams();p.set("name",name.value||"official-daily");p.set("limit",limit.value||"100");p.set("horizon_days",horizon.value||"20");p.set("require_fresh_market_data",requireFresh.checked?"true":"false");return p;}
function renderTimeline(summary){
  const has=!!summary.has_official_snapshot;
  const ready=(summary.ready_official_snapshots||0)>0;
  timeline.innerHTML=[
    ["Snapshot created",has?`Latest #${summary.latest_official_snapshot_id}`:"Start official validation",has?"completed":"waiting"],
    ["Waiting horizon",summary.next_evaluation_date?`Next evaluation ${summary.next_evaluation_date}`:"No official horizon yet",ready?"completed":(has?"waiting":"pending")],
    ["Ready to evaluate",ready?`${summary.ready_official_snapshots} ready`:"No official snapshots ready",ready?"ready":"pending"],
    ["Quality review",summary.official_evaluated_items?`${summary.official_evaluated_items} evaluated items`:"Insufficient evaluated data","pending"],
  ].map(([title,text,status])=>`<div class="progress-step">${badge(status,status==="completed"?"positive":status==="ready"?"warning":"neutral")}<strong>${esc(title)}</strong><span class="muted">${esc(text)}</span></div>`).join("");
}
function renderStatus(data){
  const s=data.summary||{}; const official=data.official_summary||{}; const os=official.summary||{}; const snap=official.latest_official_snapshot||{}; const qs=(official.quality_official||{}).summary||{};
  statusCards.innerHTML=[
    card("Status",s.blocked?"Blocked":(os.has_official_snapshot?"Active":"Not started"),s.blocked_reason||"Official paper validation"),
    card("Market data",s.market_data_stale?"Stale":"Fresh",s.latest_candle_date||"local candles"),
    card("Latest official",os.latest_official_snapshot_id?`#${os.latest_official_snapshot_id}`:"—",os.latest_official_snapshot_date||"none"),
    card("Next evaluation",os.next_evaluation_date||"—",`${os.days_until_next_evaluation??"—"} days`),
    card("Quality",qs.quality_label||"insufficient_data",`${qs.items_evaluated||0} evaluated items`),
  ].join("");
  officialBadges.innerHTML=os.has_official_snapshot?badge("Official","positive")+badge(s.market_data_stale?"Market stale":"Market fresh",s.market_data_stale?"negative":"positive"):badge("Not started","warning");
  officialCards.innerHTML=[
    card("Snapshot",os.latest_official_snapshot_id?`#${os.latest_official_snapshot_id}`:"—",snap.name||""),
    card("Rows",(snap.summary||{}).rows??snap.limit??"—","signals saved"),
    card("Baseline exposure",fmt(snap.baseline_total_exposure,"%"),"paper notional"),
    card("Overlay exposure",fmt(snap.overlay_total_exposure,"%"),"adjusted notional"),
    card("Exposure reduction",fmt(snap.exposure_reduction_pct,"%"),"conservative overlay"),
    card("Avg multiplier",fmt(snap.avg_multiplier,"",3),"risk sizing"),
  ].join("");
  const counts=snap.risk_level_counts||{};
  riskDistribution.innerHTML=Object.keys(counts).length?Object.entries(counts).map(([k,v])=>badge(`${k}: ${v}`,k==="low"?"positive":k==="moderate"||k==="elevated"?"warning":"negative")).join(""):`<span class="muted">No risk distribution yet.</span>`;
  renderTimeline(os);
  output.textContent=JSON.stringify(data,null,2);
}
async function loadStatus(){try{renderStatus(await fetchJson("/signals/live-paper-validation/status"));}catch(err){output.textContent=String(err);}}
async function dryRun(){const p=baseParams();p.set("dry_run","true");p.set("refresh_market_data","false");output.textContent=JSON.stringify(await fetchJson(`/signals/live-paper-validation/start?${p}`,{method:"POST"}),null,2);}
async function start(withRefresh){const p=baseParams();p.set("refresh_market_data",withRefresh?"true":"false");output.textContent=JSON.stringify(await fetchJson(`/signals/live-paper-validation/start?${p}`,{method:"POST"}),null,2);await loadStatus();}
async function evaluateOfficialReady(){output.textContent=JSON.stringify(await fetchJson("/signals/event-aware/conservative-overlay-paper-evaluate-ready?official_only=true&include_test=false&include_legacy=false&limit=50",{method:"POST"}),null,2);await loadStatus();}
loadStatus();
</script>
"""
    return render_page_shell(
        title="Live Paper Validation",
        subtitle="Official conservative overlay paper-validation cockpit.",
        active="live-validation",
        content=content,
        body_class="product-shell-body",
        extra_scripts=scripts,
    )
