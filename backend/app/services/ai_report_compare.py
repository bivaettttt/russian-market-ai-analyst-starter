from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models import AIReportSnapshot


def _safe_json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}

    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _pick(item: dict[str, Any] | None, *keys: str) -> Any:
    if not item:
        return None

    for key in keys:
        value = item.get(key)
        if value is not None:
            return value

    return None


def _delta(new: Any, old: Any) -> float | None:
    new_num = _num(new)
    old_num = _num(old)

    if new_num is None or old_num is None:
        return None

    return round(new_num - old_num, 4)


def _positions_map(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    portfolio = report.get("portfolio") or {}
    positions = portfolio.get("positions") or []

    result: dict[str, dict[str, Any]] = {}

    for item in positions:
        ticker = item.get("ticker")
        if ticker:
            result[str(ticker)] = item

    return result


def build_ai_report_compare(
    db: Session,
    left_id: int,
    right_id: int,
) -> dict[str, Any] | None:
    """
    left_id — старый отчёт.
    right_id — новый отчёт.
    """
    left_row = db.get(AIReportSnapshot, left_id)
    right_row = db.get(AIReportSnapshot, right_id)

    if left_row is None or right_row is None:
        return None

    left_report = _safe_json(left_row.report_json)
    right_report = _safe_json(right_row.report_json)

    left_portfolio = left_report.get("portfolio") or {}
    right_portfolio = right_report.get("portfolio") or {}

    left_market = left_report.get("market") or {}
    right_market = right_report.get("market") or {}

    left_positions = _positions_map(left_report)
    right_positions = _positions_map(right_report)

    tickers = sorted(set(left_positions) | set(right_positions))

    position_changes: list[dict[str, Any]] = []

    for ticker in tickers:
        old = left_positions.get(ticker)
        new = right_positions.get(ticker)

        if old and not new:
            status = "removed"
        elif new and not old:
            status = "added"
        else:
            status = "changed"

        old_value = _pick(
            old,
            "value",
            "value_rub",
            "current_value",
            "previous_value",
            "market_value",
            "market_value_rub",
            "position_value",
            "position_value_rub",
            "total_value",
        )
        new_value = _pick(
            new,
            "value",
            "value_rub",
            "current_value",
            "previous_value",
            "market_value",
            "market_value_rub",
            "position_value",
            "position_value_rub",
            "total_value",
        )

        old_weight = _pick(old, "weight_pct", "weight", "portfolio_weight_pct")
        new_weight = _pick(new, "weight_pct", "weight", "portfolio_weight_pct")

        old_day = _pick(
            old,
            "daily_change_pct",
            "day_change_pct",
            "change_pct",
            "daily_pnl_pct",
            "pnl_pct",
        )
        new_day = _pick(
            new,
            "daily_change_pct",
            "day_change_pct",
            "change_pct",
            "daily_pnl_pct",
            "pnl_pct",
        )

        position_changes.append(
            {
                "ticker": ticker,
                "status": status,
                "old_value": old_value,
                "new_value": new_value,
                "value_delta": _delta(new_value, old_value),
                "old_weight_pct": old_weight,
                "new_weight_pct": new_weight,
                "weight_delta": _delta(new_weight, old_weight),
                "old_daily_change_pct": old_day,
                "new_daily_change_pct": new_day,
            }
        )

    return {
        "left": {
            "id": left_row.id,
            "created_at": left_row.created_at.isoformat() if left_row.created_at else None,
            "report_date": left_row.report_date,
            "title": left_row.title,
            "view_url": f"/ai/reports/{left_row.id}/view",
            "markdown_url": f"/ai/reports/{left_row.id}.md",
        },
        "right": {
            "id": right_row.id,
            "created_at": right_row.created_at.isoformat() if right_row.created_at else None,
            "report_date": right_row.report_date,
            "title": right_row.title,
            "view_url": f"/ai/reports/{right_row.id}/view",
            "markdown_url": f"/ai/reports/{right_row.id}.md",
        },
        "summary": {
            "market_mood_old": left_market.get("market_mood"),
            "market_mood_new": right_market.get("market_mood"),
            "portfolio_value_old": left_portfolio.get("total_value"),
            "portfolio_value_new": right_portfolio.get("total_value"),
            "portfolio_value_delta": _delta(
                right_portfolio.get("total_value"),
                left_portfolio.get("total_value"),
            ),
            "daily_pnl_abs_old": left_portfolio.get("daily_pnl_abs"),
            "daily_pnl_abs_new": right_portfolio.get("daily_pnl_abs"),
            "daily_pnl_abs_delta": _delta(
                right_portfolio.get("daily_pnl_abs"),
                left_portfolio.get("daily_pnl_abs"),
            ),
            "daily_pnl_pct_old": left_portfolio.get("daily_pnl_pct"),
            "daily_pnl_pct_new": right_portfolio.get("daily_pnl_pct"),
            "daily_pnl_pct_delta": _delta(
                right_portfolio.get("daily_pnl_pct"),
                left_portfolio.get("daily_pnl_pct"),
            ),
        },
        "positions": position_changes,
    }
