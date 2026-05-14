from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AIReportSnapshot


def _safe_json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}

    try:
        data = json.loads(value)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def list_ai_report_trends(
    db: Session,
    limit: int = 100,
) -> list[dict[str, Any]]:
    rows = (
        db.execute(
            select(AIReportSnapshot)
            .order_by(AIReportSnapshot.id.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )

    result: list[dict[str, Any]] = []

    for row in rows:
        report = _safe_json(row.report_json)
        portfolio = report.get("portfolio") or {}
        market = report.get("market") or {}

        result.append(
            {
                "id": row.id,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "report_date": row.report_date,
                "title": row.title,
                "market_mood": market.get("market_mood"),
                "portfolio_value": _num(portfolio.get("total_value")),
                "daily_pnl_abs": _num(portfolio.get("daily_pnl_abs")),
                "daily_pnl_pct": _num(portfolio.get("daily_pnl_pct")),
                "view_url": f"/ai/reports/{row.id}/view",
                "markdown_url": f"/ai/reports/{row.id}.md",
                "json_url": f"/ai/reports/{row.id}",
            }
        )

    return result


def build_ai_report_trends_csv(
    db: Session,
    limit: int = 500,
) -> str:
    import csv
    import io

    rows = list_ai_report_trends(
        db=db,
        limit=limit,
    )

    output = io.StringIO()

    # BOM нужен, чтобы Excel/Numbers нормально открывали UTF-8 с русским текстом
    output.write("\ufeff")

    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "created_at",
            "report_date",
            "market_mood",
            "portfolio_value",
            "daily_pnl_abs",
            "daily_pnl_pct",
            "view_url",
            "markdown_url",
            "json_url",
        ]
    )

    for row in rows:
        writer.writerow(
            [
                row.get("id"),
                row.get("created_at"),
                row.get("report_date"),
                row.get("market_mood"),
                row.get("portfolio_value"),
                row.get("daily_pnl_abs"),
                row.get("daily_pnl_pct"),
                row.get("view_url"),
                row.get("markdown_url"),
                row.get("json_url"),
            ]
        )

    return output.getvalue()
