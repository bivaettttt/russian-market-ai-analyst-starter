from __future__ import annotations

import html
import re
from typing import Any

from fastapi.responses import HTMLResponse


THEME_MARKER = "rm-ai-ui-theme-v1"


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


DESIGN_SYSTEM_CSS = f"""
/* {THEME_MARKER} */
:root {{
  color-scheme: dark light;
  --app-bg: #0b0f14;
  --app-bg-soft: #0f151d;
  --app-surface: rgba(17, 24, 34, 0.94);
  --app-surface-2: rgba(22, 32, 43, 0.96);
  --app-surface-3: #1b2735;
  --app-text: #edf2f7;
  --app-muted: #9aa7b7;
  --app-faint: #6f7f91;
  --app-border: rgba(255, 255, 255, 0.09);
  --app-border-strong: rgba(255, 255, 255, 0.16);
  --app-accent: #f4c542;
  --app-accent-2: #e4a11b;
  --app-blue: #38bdf8;
  --app-green: #34d399;
  --app-red: #fb7185;
  --app-amber: #fbbf24;
  --app-shadow: 0 22px 70px rgba(0, 0, 0, 0.30);
  --app-radius: 8px;
}}

@media (prefers-color-scheme: light) {{
  :root {{
    --app-bg: #f4f7fb;
    --app-bg-soft: #edf2f7;
    --app-surface: rgba(255, 255, 255, 0.96);
    --app-surface-2: #ffffff;
    --app-surface-3: #f8fafc;
    --app-text: #0f172a;
    --app-muted: #536174;
    --app-faint: #7b8797;
    --app-border: rgba(15, 23, 42, 0.09);
    --app-border-strong: rgba(15, 23, 42, 0.15);
    --app-shadow: 0 20px 55px rgba(15, 23, 42, 0.10);
  }}
}}

* {{ box-sizing: border-box; letter-spacing: 0 !important; }}
html {{ background: var(--app-bg); }}
body {{
  margin: 0;
  background:
    linear-gradient(180deg, rgba(244, 197, 66, 0.08), transparent 340px),
    var(--app-bg) !important;
  color: var(--app-text) !important;
  font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif !important;
  line-height: 1.5;
}}
body.app-enhanced {{ min-height: 100vh; }}
a {{ color: var(--app-blue); text-decoration: none; }}
a:hover {{ color: var(--app-accent); }}
:focus-visible {{ outline: 3px solid rgba(244, 197, 66, 0.55); outline-offset: 2px; }}

.app-topbar {{
  position: sticky;
  top: 0;
  z-index: 1000;
  border-bottom: 1px solid var(--app-border);
  background: rgba(11, 15, 20, 0.86);
  backdrop-filter: blur(18px);
}}
@media (prefers-color-scheme: light) {{
  .app-topbar {{ background: rgba(255, 255, 255, 0.88); }}
}}
.app-topbar-inner {{
  width: min(1320px, calc(100% - 32px));
  min-height: 68px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}}
.app-brand {{
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--app-text);
  min-width: 235px;
}}
.app-brand-mark {{
  width: 38px;
  height: 38px;
  border-radius: var(--app-radius);
  display: grid;
  place-items: center;
  color: #141006;
  background: linear-gradient(135deg, var(--app-accent), var(--app-accent-2));
  font-weight: 950;
  box-shadow: 0 10px 26px rgba(244, 197, 66, 0.24);
}}
.app-brand-title {{ font-weight: 950; font-size: 15px; line-height: 1.1; }}
.app-brand-subtitle {{ display: block; color: var(--app-muted); font-size: 12px; font-weight: 750; margin-top: 2px; }}
.app-nav {{
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}}
.app-nav a {{
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: 8px 11px;
  border: 1px solid transparent;
  border-radius: 999px;
  color: var(--app-muted);
  font-size: 13px;
  font-weight: 850;
}}
.app-nav a:hover, .app-nav a.active {{
  color: var(--app-text);
  border-color: var(--app-border-strong);
  background: rgba(244, 197, 66, 0.11);
}}

header:not(.app-topbar), .page-hero {{
  background: linear-gradient(135deg, #121a24, #172232) !important;
  color: var(--app-text) !important;
  border-bottom: 1px solid var(--app-border);
  box-shadow: none !important;
}}
header:not(.app-topbar) .inner, main, .wrap, .container {{
  width: min(1320px, calc(100% - 32px)) !important;
  max-width: 1320px !important;
}}
main, .wrap, .container {{ margin-left: auto !important; margin-right: auto !important; }}

h1, h2, h3 {{ color: inherit; line-height: 1.12; }}
h1 {{ font-size: clamp(30px, 4vw, 54px) !important; font-weight: 950 !important; }}
h2 {{ font-size: clamp(22px, 2vw, 30px) !important; font-weight: 900 !important; }}
h3 {{ font-size: 18px !important; font-weight: 900 !important; }}
p, li {{ color: inherit; }}

.panel, .section, .card, .metric, .stat-card, .hero-card, .toolbar, .result-card,
.snapshot-card, .command-panel, .empty-state, .warning-panel {{
  background: var(--app-surface) !important;
  border: 1px solid var(--app-border) !important;
  border-radius: var(--app-radius) !important;
  box-shadow: var(--app-shadow) !important;
  color: var(--app-text) !important;
}}
.panel, .section, .card, .metric, .stat-card, .command-panel, .empty-state, .warning-panel {{
  padding: 18px !important;
}}
.card:hover, .ticker-card:hover, .metric:hover {{
  border-color: var(--app-border-strong) !important;
}}
.label, .muted, .hint, small, .card .label, .metric .label {{
  color: var(--app-muted) !important;
}}
.value, .metric .value, .stat-value {{
  color: var(--app-text) !important;
  font-weight: 950 !important;
}}
.summary, .grid, .card-grid, .metrics-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 14px;
}}

button, .button, input[type="submit"], input[type="button"], a.button {{
  min-height: 40px;
  border: 1px solid rgba(244, 197, 66, 0.28) !important;
  border-radius: var(--app-radius) !important;
  background: linear-gradient(180deg, var(--app-accent), var(--app-accent-2)) !important;
  color: #181106 !important;
  font-weight: 900 !important;
  cursor: pointer;
  transition: transform 140ms ease, border-color 140ms ease, opacity 140ms ease;
}}
button:hover, .button:hover {{ transform: translateY(-1px); opacity: 0.95; }}
button.secondary, .button.secondary, button.ghost, .button.ghost {{
  background: var(--app-surface-3) !important;
  color: var(--app-text) !important;
  border-color: var(--app-border-strong) !important;
}}
button.is-loading, .button.is-loading {{ opacity: 0.65; pointer-events: none; }}
input, select, textarea {{
  background: var(--app-surface-2) !important;
  border: 1px solid var(--app-border-strong) !important;
  color: var(--app-text) !important;
  border-radius: var(--app-radius) !important;
}}
label {{ color: var(--app-muted) !important; font-weight: 850; }}

table, .data-table {{
  width: 100%;
  border-collapse: separate !important;
  border-spacing: 0 !important;
  overflow: hidden;
  border: 1px solid var(--app-border) !important;
  border-radius: var(--app-radius) !important;
  background: var(--app-surface) !important;
}}
thead, th {{
  background: var(--app-surface-3) !important;
  color: var(--app-muted) !important;
  text-transform: uppercase;
  font-size: 11px !important;
  font-weight: 900 !important;
}}
td, th {{
  padding: 11px 12px !important;
  border-bottom: 1px solid var(--app-border) !important;
  color: var(--app-text);
}}
tr:hover td {{ background: rgba(244, 197, 66, 0.05); }}
.table-wrap, .table-scroll {{ overflow-x: auto; }}

.status-badge, .badge, .pill, .diag-pill, .scenario-tab, .nav a {{
  border-radius: 999px !important;
}}
.status-badge {{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 9px;
  border: 1px solid var(--app-border);
  background: var(--app-surface-3);
  color: var(--app-muted);
  font-size: 12px;
  font-weight: 900;
}}
.tone-positive, .badge-positive, .positive, .risk-low {{ color: var(--app-green) !important; border-color: rgba(52, 211, 153, 0.30) !important; }}
.tone-negative, .badge-negative, .negative, .risk-high, .risk-extreme {{ color: var(--app-red) !important; border-color: rgba(251, 113, 133, 0.34) !important; }}
.tone-warning, .badge-warning, .warning, .risk-moderate, .risk-elevated {{ color: var(--app-amber) !important; border-color: rgba(251, 191, 36, 0.34) !important; }}
.tone-info, .badge-info, .info {{ color: var(--app-blue) !important; border-color: rgba(56, 189, 248, 0.34) !important; }}
.tone-accent, .badge-accent {{ color: var(--app-accent) !important; border-color: rgba(244, 197, 66, 0.38) !important; }}

.ticker-card, .signal-card {{
  background: var(--app-surface) !important;
  border: 1px solid var(--app-border) !important;
  border-radius: var(--app-radius) !important;
  box-shadow: var(--app-shadow) !important;
}}
.ticker-symbol, .ticker-title {{ color: var(--app-text) !important; font-weight: 950 !important; }}
.ticker-action {{ display: inline-flex; }}
details {{
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  padding: 12px;
  background: rgba(255, 255, 255, 0.03);
}}
summary {{ cursor: pointer; font-weight: 900; }}
pre, code {{
  background: #08111d !important;
  color: #d6e4f0 !important;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
}}
pre {{ padding: 14px !important; overflow-x: auto; }}

.app-footer-note {{
  width: min(1320px, calc(100% - 32px));
  margin: 28px auto;
  color: var(--app-muted);
  font-size: 12px;
  border-top: 1px solid var(--app-border);
  padding-top: 16px;
}}

@media (max-width: 760px) {{
  .app-topbar-inner {{ width: min(100% - 20px, 1320px); flex-direction: column; align-items: stretch; padding: 10px 0; }}
  .app-brand {{ min-width: 0; }}
  .app-nav {{ justify-content: flex-start; overflow-x: auto; flex-wrap: nowrap; padding-bottom: 4px; }}
  header:not(.app-topbar) .inner, main, .wrap, .container {{ width: min(100% - 20px, 1320px) !important; padding-left: 0 !important; padding-right: 0 !important; }}
  .summary, .grid, .card-grid, .metrics-grid {{ grid-template-columns: 1fr !important; }}
  .toolbar, .layout {{ grid-template-columns: 1fr !important; }}
  h1 {{ font-size: 32px !important; }}
}}
"""


NAV_ITEMS = [
    ("Signals", "/signals", "signals"),
    ("Daily Ops", "/signals/daily-ops/page", "daily-ops"),
    ("Live Validation", "/signals/live-paper-validation/page", "live-validation"),
    ("Quality", "/signals/event-aware/conservative-overlay-quality-report-page", "quality"),
    ("Paper Tracking", "/signals/event-aware/conservative-overlay-paper-tracking-page", "tracking"),
    ("Market Data", "/signals/daily-ops/market-refresh-report-page", "market-data"),
    ("Research", "/signals/research-hub-page", "research"),
]


def render_nav(active: str | None = None) -> str:
    links = []
    for label, href, key in NAV_ITEMS:
        cls = ' class="active"' if active == key else ""
        links.append(f'<a{cls} href="{href}">{_esc(label)}</a>')
    return (
        '<header class="app-topbar">'
        '<div class="app-topbar-inner">'
        '<a class="app-brand" href="/signals" aria-label="Russian Market AI Analyst home">'
        '<span class="app-brand-mark">AI</span>'
        '<span><span class="app-brand-title">Russian Market AI Analyst</span>'
        '<span class="app-brand-subtitle">Paper Validation Alpha</span></span>'
        '</a>'
        f'<nav class="app-nav" aria-label="Primary navigation">{"".join(links)}</nav>'
        "</div></header>"
    )


def render_status_badge(label: str, tone: str = "neutral") -> str:
    return f'<span class="status-badge tone-{_esc(tone)}">{_esc(label)}</span>'


def snapshot_badge_tone(snapshot_type: str | None) -> str:
    return {
        "official": "accent",
        "test": "warning",
        "manual": "info",
        "legacy": "negative",
    }.get(str(snapshot_type or "").lower(), "neutral")


def render_snapshot_badges(snapshot: dict[str, Any]) -> str:
    badges = [
        render_status_badge(str(snapshot.get("snapshot_type") or "manual").title(), snapshot_badge_tone(snapshot.get("snapshot_type")))
    ]
    if snapshot.get("is_official"):
        badges.append(render_status_badge("Official", "positive"))
    if snapshot.get("is_test"):
        badges.append(render_status_badge("Test", "warning"))
    if snapshot.get("is_legacy"):
        badges.append(render_status_badge("Legacy", "negative"))
    if snapshot.get("has_zero_exposure"):
        badges.append(render_status_badge("Zero exposure", "negative"))
    return '<span class="snapshot-badges">' + "".join(badges) + "</span>"


def render_metric_card(label: str, value: Any, hint: str | None = None, tone: str = "neutral") -> str:
    hint_html = f'<div class="hint">{_esc(hint)}</div>' if hint else ""
    return (
        f'<article class="metric tone-{_esc(tone)}">'
        f'<div class="label">{_esc(label)}</div>'
        f'<div class="value">{_esc(value if value is not None else "—")}</div>'
        f"{hint_html}</article>"
    )


def render_section(title: str, content: str, subtitle: str | None = None, tone: str = "neutral") -> str:
    subtitle_html = f'<p class="muted">{_esc(subtitle)}</p>' if subtitle else ""
    return f'<section class="section tone-{_esc(tone)}"><h2>{_esc(title)}</h2>{subtitle_html}{content}</section>'


def render_empty_state(title: str = "No data yet", message: str | None = None) -> str:
    message_html = f'<p class="muted">{_esc(message)}</p>' if message else ""
    return f'<div class="empty-state"><h3>{_esc(title)}</h3>{message_html}</div>'


def render_warning_panel(title: str, message: str, tone: str = "warning") -> str:
    return f'<div class="warning-panel tone-{_esc(tone)}"><strong>{_esc(title)}</strong><p>{_esc(message)}</p></div>'


def render_action_bar(actions: list[tuple[str, str, str | None]]) -> str:
    links = [
        f'<a class="button {(_esc(kind) if kind else "secondary")}" href="{_esc(href)}">{_esc(label)}</a>'
        for label, href, kind in actions
    ]
    return f'<div class="action-bar">{"".join(links)}</div>'


def render_table(headers: list[str], rows: list[list[Any]]) -> str:
    head = "".join(f"<th>{_esc(item)}</th>" for item in headers)
    body = "".join("<tr>" + "".join(f"<td>{_esc(cell)}</td>" for cell in row) + "</tr>" for row in rows)
    return f'<div class="table-wrap"><table class="data-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def render_page_header(title: str, subtitle: str | None = None, badges: list[str] | None = None) -> str:
    subtitle_html = f'<p>{_esc(subtitle)}</p>' if subtitle else ""
    badges_html = f'<div class="diagnostics-row">{"".join(badges or [])}</div>' if badges else ""
    return f'<header class="page-hero"><div class="inner"><h1>{_esc(title)}</h1>{subtitle_html}{badges_html}</div></header>'


def render_footer_note() -> str:
    return (
        '<footer class="app-footer-note">'
        "Paper tracking only. No real orders. No investment advice. Production defaults are unchanged."
        "</footer>"
    )


def render_page_shell(
    *,
    title: str,
    subtitle: str | None = None,
    active: str | None = None,
    content: str,
    body_class: str = "",
    extra_head: str = "",
    extra_scripts: str = "",
) -> str:
    return (
        "<!doctype html><html lang=\"ru\"><head>"
        '<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{_esc(title)}</title><style>{DESIGN_SYSTEM_CSS}</style>{extra_head}</head>"
        f'<body class="app-enhanced {_esc(body_class)}">'
        f"{render_nav(active)}"
        f"{render_page_header(title, subtitle)}"
        f"<main>{content}</main>{render_footer_note()}{extra_scripts}</body></html>"
    )


def enhance_html_document(raw_html: str | bytes, *, active: str | None = None) -> str:
    text = raw_html.decode("utf-8", errors="replace") if isinstance(raw_html, bytes) else str(raw_html)
    if THEME_MARKER in text:
        return text
    css = f"<style>{DESIGN_SYSTEM_CSS}</style>"
    if "</head>" in text:
        text = text.replace("</head>", f"{css}</head>", 1)
    else:
        text = f"{css}{text}"
    nav = render_nav(active)
    body_match = re.search(r"<body([^>]*)>", text, flags=re.IGNORECASE)
    if body_match:
        attrs = body_match.group(1) or ""
        if "class=" in attrs:
            attrs = re.sub(r'class=(["\'])(.*?)\1', lambda m: f'class={m.group(1)}app-enhanced {m.group(2)}{m.group(1)}', attrs, count=1)
        else:
            attrs = f'{attrs} class="app-enhanced"'
        text = text[: body_match.start()] + f"<body{attrs}>{nav}" + text[body_match.end() :]
    else:
        text = f"{nav}{text}"
    if "</body>" in text:
        text = text.replace("</body>", f"{render_footer_note()}</body>", 1)
    return text


class ThemedHTMLResponse(HTMLResponse):
    def render(self, content: Any) -> bytes:
        if content is None:
            content = ""
        if isinstance(content, (str, bytes)):
            content = enhance_html_document(content)
        return super().render(content)
