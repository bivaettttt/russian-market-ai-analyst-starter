from app.services.ui_theme import (
    DESIGN_SYSTEM_CSS,
    THEME_MARKER,
    enhance_html_document,
    render_action_badge,
    render_metric_card,
    render_page_shell,
    render_risk_badge,
    render_signal_card,
    render_status_badge,
    truncate_text,
)


def test_design_system_css_contains_core_classes():
    assert THEME_MARKER in DESIGN_SYSTEM_CSS
    for class_name in [
        ".app-topbar",
        ".app-nav",
        ".metric",
        ".status-badge",
        ".ticker-card",
        ".signal-card",
        ".product-shell",
        ".table-wrap",
        ".line-clamp-2",
        ".overflow-safe",
        ".data-table",
        ".warning-panel",
    ]:
        assert class_name in DESIGN_SYSTEM_CSS


def test_page_shell_renders_nav_and_content():
    html = render_page_shell(
        title="Test Page",
        subtitle="Subtitle",
        active="signals",
        content="<section>Body</section>",
    )

    assert "<!doctype html>" in html
    assert "Russian Market AI Analyst" in html
    assert "Paper Validation Alpha" in html
    assert "Body" in html
    assert THEME_MARKER in html


def test_status_badge_and_metric_card_tones_are_rendered():
    assert "tone-positive" in render_status_badge("fresh", "positive")
    assert "tone-warning" in render_metric_card("Market", "stale", tone="warning")
    assert "tone-positive" in render_action_badge("consider_buy")
    assert "risk-elevated" in render_risk_badge("elevated")


def test_text_helpers_and_signal_card_are_overflow_safe():
    long_text = "x" * 400
    assert truncate_text(long_text, 20).endswith("…")
    card = render_signal_card(
        ticker="SBER",
        name=long_text,
        action="consider_buy",
        probability="62%",
        risk_level="elevated",
        multiplier="x0.80",
        exposure="1.0% → 0.8%",
        reasons=[long_text],
        detail_url="/ticker/SBER",
    )
    assert "signal-card" in card
    assert "line-clamp" in card


def test_enhance_html_document_injects_theme_once():
    raw = "<!doctype html><html><head><title>X</title></head><body><main>Y</main></body></html>"

    once = enhance_html_document(raw)
    twice = enhance_html_document(once)

    assert once == twice
    assert once.count(THEME_MARKER) == 1
    assert "app-topbar" in once
