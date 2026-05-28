from __future__ import annotations


def build_event_overlay_paper_snapshot_page_html() -> str:
    return """<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Conservative Overlay Paper Snapshot</title>
  <style>
    body { margin: 0; font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f6f7fb; color: #172033; }
    header { padding: 24px 32px; background: #111827; color: white; }
    main { padding: 24px 32px 48px; max-width: 1280px; margin: 0 auto; }
    nav a { color: #dbeafe; margin-right: 14px; font-size: 14px; }
    .panel { background: white; border: 1px solid #d8dee9; border-radius: 8px; padding: 16px; margin: 16px 0; }
    .controls { display: flex; flex-wrap: wrap; gap: 12px; align-items: end; }
    label { display: grid; gap: 4px; font-size: 13px; color: #475569; }
    input, select { padding: 8px 10px; border: 1px solid #cbd5e1; border-radius: 6px; min-width: 120px; }
    button { border: 0; border-radius: 6px; background: #2563eb; color: white; padding: 9px 14px; cursor: pointer; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
    .metric { border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; background: #fbfdff; }
    .metric .v { font-size: 24px; font-weight: 700; }
    .metric .k { color: #64748b; font-size: 12px; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { padding: 8px; border-bottom: 1px solid #e2e8f0; text-align: left; vertical-align: top; }
    th { color: #475569; background: #f8fafc; }
    .muted { color: #64748b; }
  </style>
</head>
<body>
  <header>
    <h1>Conservative Overlay Paper Snapshot</h1>
    <nav>
      <a href="/signals">Signals</a>
      <a href="/signals/event-aware/risk-overlay-conservative-page">Conservative overlay</a>
      <a href="/signals/event-aware/risk-overlay-page">Risk overlay</a>
      <a href="/signals/event-aware/conservative-overlay-paper-tracking-page">Overlay tracking</a>
    </nav>
  </header>
  <main>
    <section class="panel">
      <p class="muted">Read-only paper snapshot: compares baseline exposure vs conservative event overlay exposure. No trading actions are created.</p>
      <div class="controls">
        <label>limit <input id="limit" type="number" value="50" min="1" max="500"></label>
        <label>candles_limit <input id="candlesLimit" type="number" value="240" min="60" max="1000"></label>
        <label>mode
          <select id="mode">
            <option value="soft_adjust" selected>soft_adjust</option>
            <option value="diagnostic_only">diagnostic_only</option>
          </select>
        </label>
        <button onclick="run()">Load snapshot</button>
      </div>
    </section>
    <section class="panel"><h2>Summary</h2><div id="summary" class="grid"></div></section>
    <section class="panel"><h2>Top risk rows</h2><div id="rows"></div></section>
    <section class="panel"><h2>Caveat</h2><p class="muted">Research/paper trading only. No investment advice.</p></section>
  </main>
  <script>
    const fmt = v => v === null || v === undefined ? "—" : (typeof v === "number" ? v.toFixed(Math.abs(v) < 10 ? 2 : 1) : v);
    const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
    function table(rows, cols) {
      if (!rows || !rows.length) return "<p class='muted'>Нет данных.</p>";
      return `<table><thead><tr>${cols.map(c => `<th>${esc(c[0])}</th>`).join("")}</tr></thead><tbody>${rows.map(r => `<tr>${cols.map(c => `<td>${esc(fmt(c[2] ? c[2](r) : r[c[1]])))}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
    }
    async function run() {
      summary.innerHTML = "<p class='muted'>Loading...</p>";
      const p = new URLSearchParams();
      p.set("limit", limit.value);
      p.set("candles_limit", candlesLimit.value);
      p.set("conservative_event_overlay_mode", mode.value);
      const res = await fetch(`/signals/event-aware/conservative-overlay-paper-snapshot?${p.toString()}`);
      const data = await res.json();
      const s = data.summary || {};
      summary.innerHTML = [
        ["baseline exposure", s.baseline_total_exposure],
        ["overlay exposure", s.overlay_total_exposure],
        ["exposure reduction", s.exposure_reduction_pct],
        ["avg multiplier", s.avg_multiplier],
        ["elevated/high", s.elevated_or_higher_count],
        ["changed actions", s.changed_actions]
      ].map(x => `<div class="metric"><div class="v">${esc(fmt(x[1]))}</div><div class="k">${esc(x[0])}</div></div>`).join("");
      rows.innerHTML = table(data.top_risk_rows || [], [["ticker","ticker"],["action","action"],["base","base_position_size_pct"],["adjusted","event_adjusted_position_size_pct"],["mult","event_risk_multiplier"],["risk","event_risk_level"],["score","event_risk_score"],["reasons","top_reasons", r => (r.top_reasons || []).join("; ")]]);
    }
    run();
  </script>
</body>
</html>"""
