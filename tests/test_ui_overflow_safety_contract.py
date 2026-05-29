from app.services.ui_theme import DESIGN_SYSTEM_CSS


def test_design_system_has_overflow_safety_rules():
    required = [
        "overflow-x: hidden",
        "overflow-wrap: anywhere",
        ".table-wrap",
        "max-width: 100%",
        ".line-clamp-1",
        ".line-clamp-2",
        ".overflow-safe",
        "minmax(0, 1fr)",
    ]

    for rule in required:
        assert rule in DESIGN_SYSTEM_CSS


def test_mobile_breakpoint_keeps_signal_cards_single_column():
    assert "@media (max-width: 760px)" in DESIGN_SYSTEM_CSS
    assert ".signal-card { grid-template-columns: 1fr;" in DESIGN_SYSTEM_CSS
