from __future__ import annotations

from app.services.ui_theme import render_metric_card, render_page_shell, render_section


def _links(items: list[tuple[str, str, str]]) -> str:
    cards = []
    for title, href, note in items:
        cards.append(
            f'<a class="card" href="{href}">'
            f"<h3>{title}</h3>"
            f'<p class="muted">{note}</p>'
            "</a>"
        )
    return f'<div class="card-grid">{"".join(cards)}</div>'


def build_research_hub_page_html() -> str:
    validation = [
        ("Backtest Audit", "/signals/consumer/backtest-audit-page", "Consumer signal historical proxy audit."),
        ("Threshold Sweep", "/signals/consumer/threshold-sweep-page", "Candidate thresholds and sensitivity checks."),
        ("Walk-forward", "/signals/consumer/walk-forward-page", "Leakage-aware forward validation."),
        ("Expectancy", "/signals/consumer/expectancy-breakdown-page", "PnL and outcome decomposition."),
    ]
    regime = [
        ("Market Regime", "/signals/market-regime", "Current regime diagnostics."),
        ("Historical Regime", "/signals/consumer/regime-historical-evaluation-page", "Regime behavior over history."),
        ("Formula Calibration", "/signals/consumer/regime-formula-calibration-page", "Regime formula search."),
    ]
    ml = [
        ("ML v2 Report", "/signals/ml-v2/report-page", "Trade PnL research model."),
        ("ML v2 Gate Impact", "/signals/ml-v2/gate-impact-page", "Decision gate impact diagnostics."),
        ("ML v2 Walk-forward", "/signals/ml-v2/gate-walk-forward-page", "Leakage-safe ML v2 gate validation."),
        ("ML v3 Candidate", "/signals/ml-v3/consumer-candidate/page", "Consumer candidate research layer."),
    ]
    event = [
        ("Event-aware Research", "/signals/event-aware/research-page", "Event-aware setup diagnostics."),
        ("Rule Search", "/signals/event-aware/rule-search-page", "Generalized event-aware rule search."),
        ("Dual-side Risk", "/signals/event-aware/dual-side-page", "Avoid-long risk research."),
        ("Rule Stability", "/signals/event-aware/rule-stability-page", "Stability diagnostics by year/fold/regime."),
        ("Risk Overlay", "/signals/event-aware/risk-overlay-page", "Soft event risk overlay."),
        ("Conservative Calibration", "/signals/event-aware/risk-overlay-conservative-page", "Selected conservative overlay profile."),
    ]
    paper = [
        ("Daily Ops", "/signals/daily-ops/page", "Refresh, snapshot, evaluate, report."),
        ("Live Validation", "/signals/live-paper-validation/page", "Official paper validation start workflow."),
        ("Quality Report", "/signals/event-aware/conservative-overlay-quality-report-page", "Baseline vs overlay quality tracking."),
        ("Paper Tracking", "/signals/event-aware/conservative-overlay-paper-tracking-page", "Stored snapshots and lifecycle."),
        ("Market Refresh", "/signals/daily-ops/market-refresh-report-page", "Ticker freshness and refresh diagnostics."),
    ]
    overview = (
        '<div class="summary">'
        + render_metric_card("Stage", "Live Paper Validation Alpha", "Research and paper tracking only", "accent")
        + render_metric_card("Overlay", "Conservative Event Overlay", "Opt-in diagnostic exposure layer", "info")
        + render_metric_card("Production Defaults", "Unchanged", "No automatic trading behavior change", "positive")
        + render_metric_card("Caveat", "No investment advice", "No real orders are created", "warning")
        + "</div>"
    )
    content = (
        overview
        + render_section("Validation", _links(validation), "Core consumer signal validation pages.")
        + render_section("Market Regime", _links(regime), "Regime diagnostics and calibration.")
        + render_section("ML Research", _links(ml), "ML v2/v3 research surfaces.")
        + render_section("Event-aware Research", _links(event), "Event-aware setup, risk, and overlay research.")
        + render_section("Paper Validation", _links(paper), "Daily operations and conservative overlay paper lifecycle.")
    )
    return render_page_shell(
        title="Research Hub",
        subtitle="Navigation for validation, event-aware risk research and live paper tracking.",
        active="research",
        content=content,
    )
