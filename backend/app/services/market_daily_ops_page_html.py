from __future__ import annotations

from app.services.ui_theme import render_page_shell


def build_market_daily_ops_page_html() -> str:
    content = """
<div class="product-shell daily-ops-product">
  <section class="product-hero">
    <div>
      <div class="action-row"><span class="status-badge tone-info">Operational workflow</span><span class="status-badge tone-warning">Local writes only</span></div>
      <h2>Market Daily Ops</h2>
      <p class="product-subtitle">Daily checklist: refresh MOEX candles, create official paper snapshot, evaluate ready snapshots, review quality.</p>
    </div>
    <div class="action-row">
      <a class="button" href="/signals/live-paper-validation/page">Live Validation</a>
      <a class="button secondary" href="/signals/daily-ops/market-refresh-report-page">Market Data</a>
      <a class="button secondary" href="/signals/event-aware/conservative-overlay-quality-report-page">Quality</a>
    </div>
  </section>

  <section class="kpi-strip" id="cards"></section>

  <section class="product-card">
    <h3 class="product-card-title">Daily checklist</h3>
    <div class="progress-steps">
      <div class="progress-step"><span class="status-badge tone-info">1</span><strong>Refresh market data</strong><span class="muted">Update local MOEX candles.</span></div>
      <div class="progress-step"><span class="status-badge tone-info">2</span><strong>Start official snapshot</strong><span class="muted">Dedupe same-day official paper view.</span></div>
      <div class="progress-step"><span class="status-badge tone-info">3</span><strong>Evaluate ready</strong><span class="muted">Use future local candles after horizon.</span></div>
      <div class="progress-step"><span class="status-badge tone-info">4</span><strong>Review quality</strong><span class="muted">Official-only baseline vs overlay.</span></div>
    </div>
  </section>

  <section class="product-card">
    <div class="filter-row">
      <label>Name <input id="name" value="daily"></label>
      <label>Limit <input id="limit" type="number" value="100" min="1" max="500"></label>
      <label>Horizon <input id="horizon" type="number" value="20" min="1" max="120"></label>
      <label>Refresh tickers <input id="refreshTickers" type="number" value="150" min="1" max="500"></label>
      <label>Refresh days <input id="refreshDays" type="number" value="120" min="10" max="1000"></label>
      <button onclick="dryRun()">Dry run</button>
      <button onclick="runDaily(true)">Run daily ops</button>
      <button class="secondary" onclick="runDaily(false)">Run without refresh</button>
      <button class="secondary" onclick="evaluateReady()">Evaluate ready</button>
      <button class="secondary" onclick="loadStatus()">Refresh status</button>
    </div>
  </section>

  <section class="product-card">
    <h3 class="product-card-title">Terminal command</h3>
    <pre><code>cd backend
python3 -m app.tasks.market_daily_ops run --name daily --limit 100 --horizon-days 20 --refresh-max-tickers 150 --refresh-days 120</code></pre>
    <details class="advanced-panel"><summary>Latest raw result</summary><pre id="output">Ready.</pre></details>
  </section>
  <section class="disclaimer-bar">Daily Ops is for local paper validation. It does not place trades and is not investment advice.</section>
</div>
"""
    scripts = """
<script>
function esc(v){return String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
function card(l,v,h=""){return `<article class="metric-card"><div class="metric-label">${esc(l)}</div><div class="metric-value">${esc(v??"—")}</div><div class="metric-hint">${esc(h)}</div></article>`;}
async function fetchJson(url,opt){const r=await fetch(url,opt||{});const t=await r.text();if(!r.ok)throw new Error(`HTTP ${r.status}: ${t}`);return JSON.parse(t);}
function params(){const p=new URLSearchParams();p.set("name",name.value||"daily");p.set("limit",limit.value||"100");p.set("horizon_days",horizon.value||"20");p.set("refresh_max_tickers",refreshTickers.value||"150");p.set("refresh_days",refreshDays.value||"120");return p;}
function renderStatus(data){const s=data.summary||{};cards.innerHTML=[card("Market data",s.market_data_stale?"Stale":"Fresh",s.latest_candle_date||"local candles"),card("Paper snapshots",s.paper_snapshots_total,"stored"),card("Ready",s.ready_to_evaluate,"due for evaluation"),card("Quality",s.quality_label,"official quality"),card("Next action",s.recommended_action,"operational guidance")].join("");output.textContent=JSON.stringify(data,null,2);}
async function loadStatus(){try{renderStatus(await fetchJson("/signals/daily-ops/status"));}catch(e){output.textContent=String(e);}}
async function dryRun(){const p=params();p.set("dry_run","true");p.set("refresh_market_data","false");renderStatus(await fetchJson(`/signals/daily-ops/run?${p}`,{method:"POST"}));}
async function runDaily(withRefresh){const p=params();p.set("refresh_market_data",withRefresh?"true":"false");renderStatus(await fetchJson(`/signals/daily-ops/run?${p}`,{method:"POST"}));}
async function evaluateReady(){output.textContent=JSON.stringify(await fetchJson("/signals/event-aware/conservative-overlay-paper-evaluate-ready?official_only=true&include_test=false&include_legacy=false&limit=50",{method:"POST"}),null,2);await loadStatus();}
loadStatus();
</script>
"""
    return render_page_shell(
        title="Market Daily Ops",
        subtitle="Operational command center for live paper validation.",
        active="daily-ops",
        content=content,
        body_class="product-shell-body",
        extra_scripts=scripts,
    )
