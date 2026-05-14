from __future__ import annotations

from typing import Any


def build_ai_report_markdown(report: dict[str, Any]) -> str:
    sections = report.get("sections", {})

    lines = [
        f"# {report.get('title', 'AI Report российского рынка')}",
        "",
        f"**Дата:** {report.get('date') or '—'}",
        "",
        "> Это аналитическая сводка на основе рыночных и новостных данных, а не инвестиционная рекомендация.",
        "",
        "## 1. Рыночный фон",
        sections.get("market_context", "—"),
        "",
        "## 2. Главные события",
        sections.get("important_events", "—"),
        "",
        "## 3. Рыночные сигналы",
        sections.get("market_signals", "—"),
        "",
        "## 4. Портфель",
        sections.get("portfolio_context", "—"),
        "",
        "## 5. Риски",
        sections.get("risk_review", "—"),
        "",
        "## 6. Watchlist",
        sections.get("watchlist", "—"),
        "",
        "## 7. Вывод дня",
        sections.get("conclusion", "—"),
        "",
    ]

    return "\n".join(lines)
