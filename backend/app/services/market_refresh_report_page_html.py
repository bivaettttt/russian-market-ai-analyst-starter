from __future__ import annotations

from app.services.ui_theme import render_page_shell


def build_market_refresh_report_page_html() -> str:
    content = """
<div class="product-shell market-refresh-product">
  <section class="product-hero">
    <div>
      <div class="action-row"><span class="status-badge tone-info">MOEX local candles</span><span class="status-badge tone-warning">Refresh diagnostics</span></div>
      <h2>Market Data</h2>
      <p class="product-subtitle">Freshness, stale tickers and safe refresh commands for local MOEX candle data.</p>
    </div>
    <div class="action-row">
      <a class="button" href="/signals/daily-ops/page">Daily Ops</a>
      <a class="button secondary" href="/signals/data-coverage-page">Data Coverage</a>
      <a class="button secondary" href="/signals">Signals</a>
    </div>
  </section>

  <section class="product-card">
    <div class="filter-row">
      <label>Max tickers <input id="maxTickers" type="number" min="1" max="1000" value="300"></label>
      <label>Stale days <input id="staleDays" type="number" min="1" max="30" value="3"></label>
      <button onclick="loadReport()">Refresh report</button>
      <button class="secondary" onclick="dryRunRefresh()">Dry-run refresh</button>
      <a class="button secondary" href="/signals/daily-ops/market-refresh-report.csv">CSV</a>
    </div>
  </section>

  <section class="kpi-strip" id="cards"></section>

  <section class="product-card">
    <h3 class="product-card-title">Ticker freshness</h3>
    <div class="table-wrap"><table class="data-table"><thead><tr><th>Ticker</th><th>Latest candle</th><th>Days stale</th><th>Status</th></tr></thead><tbody id="rows"></tbody></table></div>
  </section>

  <section class="product-card">
    <h3 class="product-card-title">Recommended command</h3>
    <pre><code>cd backend
python3 -m app.tasks.market_daily_ops refresh --skip-universe-refresh --max-tickers 150 --days 120 --request-timeout 10 --max-retries 1</code></pre>
    <details class="advanced-panel"><summary>Raw diagnostics</summary><pre id="output">Ready.</pre></details>
  </section>
  <section class="disclaimer-bar">Refresh writes local market data only. MOEX availability can affect completeness. No investment advice.</section>
</div>
"""
    scripts = """
<script>
function esc(v){return String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
function card(l,v,h=""){return `<article class="metric-card"><div class="metric-label">${esc(l)}</div><div class="metric-value">${esc(v??"—")}</div><div class="metric-hint">${esc(h)}</div></article>`;}
async function fetchJson(url,opt){const r=await fetch(url,opt||{});const t=await r.text();if(!r.ok)throw new Error(`HTTP ${r.status}: ${t}`);return JSON.parse(t);}
function params(){const p=new URLSearchParams();p.set("max_tickers",maxTickers.value||"300");p.set("stale_days",staleDays.value||"3");return p;}
function render(data){const s=data.summary||{};cards.innerHTML=[card("Latest candle",s.latest_candle_date,"local DB"),card("Status",s.market_data_stale?"Stale":"Fresh",s.recommended_action),card("Fresh tickers",s.fresh_tickers,"checked"),card("Stale tickers",s.stale_tickers,"need update"),card("Missing candles",s.missing_candles_tickers,"bootstrap needed")].join("");const tf=data.ticker_freshness||{};const all=[...(tf.stale_tickers||[]),...(tf.fresh_tickers||[]),...(tf.missing_candles_tickers||[]).map(t=>({ticker:t,status:"missing_candles"}))];rows.innerHTML=all.slice(0,500).map(r=>`<tr><td>${esc(r.ticker)}</td><td>${esc(r.latest_candle_date||"—")}</td><td>${esc(r.days_stale??"—")}</td><td>${esc(r.status||"fresh")}</td></tr>`).join("")||`<tr><td colspan="4" class="muted">No ticker rows.</td></tr>`;output.textContent=JSON.stringify(data,null,2);}
async function loadReport(){render(await fetchJson(`/signals/daily-ops/market-refresh-report?${params()}`));}
async function dryRunRefresh(){const p=new URLSearchParams();p.set("dry_run","true");p.set("max_tickers",maxTickers.value||"300");p.set("days","120");output.textContent=JSON.stringify(await fetchJson(`/signals/daily-ops/refresh-market-data?${p}`,{method:"POST"}),null,2);}
loadReport();
</script>
"""
    return render_page_shell(
        title="Market Data",
        subtitle="MOEX candle freshness and refresh diagnostics.",
        active="market-data",
        content=content,
        body_class="product-shell-body",
        extra_scripts=scripts,
    )
