from __future__ import annotations

from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import PortfolioConstructSnapshot
from app.services.portfolio_construct_history import portfolio_construct_snapshot_to_dict


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _delta(new_value: Any, old_value: Any) -> float | None:
    new_number = _num(new_value)
    old_number = _num(old_value)

    if new_number is None or old_number is None:
        return None

    return round(new_number - old_number, 2)


def _round(value: Any, digits: int = 2) -> float | None:
    number = _num(value)

    if number is None:
        return None

    return round(number, digits)


def _positions_by_ticker(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}

    for row in snapshot.get("positions") or []:
        ticker = str(row.get("ticker") or "").upper().strip()

        if ticker:
            result[ticker] = row

    return result


def _get_snapshot_row(db: Session, snapshot_id: int) -> PortfolioConstructSnapshot | None:
    PortfolioConstructSnapshot.__table__.create(
        bind=db.get_bind(),
        checkfirst=True,
    )

    return db.get(PortfolioConstructSnapshot, snapshot_id)


def _latest_two_rows(db: Session) -> list[PortfolioConstructSnapshot]:
    PortfolioConstructSnapshot.__table__.create(
        bind=db.get_bind(),
        checkfirst=True,
    )

    return db.scalars(
        select(PortfolioConstructSnapshot)
        .order_by(desc(PortfolioConstructSnapshot.created_at), desc(PortfolioConstructSnapshot.id))
        .limit(2)
    ).all()


def compare_portfolio_construct_snapshots(
    db: Session,
    left_id: int | None = None,
    right_id: int | None = None,
) -> dict[str, Any]:
    if left_id is None and right_id is None:
        latest_rows = _latest_two_rows(db)

        if len(latest_rows) < 2:
            return {
                "ok": False,
                "error": "not_enough_snapshots",
                "message": "Нужно минимум два snapshot-а для сравнения.",
            }

        # left = более старый, right = более новый
        left_row = latest_rows[1]
        right_row = latest_rows[0]
    else:
        if left_id is None or right_id is None:
            return {
                "ok": False,
                "error": "both_ids_required",
                "message": "Для сравнения нужны left_id и right_id.",
            }

        left_row = _get_snapshot_row(db, left_id)
        right_row = _get_snapshot_row(db, right_id)

        if left_row is None or right_row is None:
            return {
                "ok": False,
                "error": "snapshot_not_found",
                "left_id": left_id,
                "right_id": right_id,
            }

    left = portfolio_construct_snapshot_to_dict(left_row)
    right = portfolio_construct_snapshot_to_dict(right_row)

    left_positions = _positions_by_ticker(left)
    right_positions = _positions_by_ticker(right)

    tickers = sorted(set(left_positions) | set(right_positions))

    rows: list[dict[str, Any]] = []

    for ticker in tickers:
        old = left_positions.get(ticker)
        new = right_positions.get(ticker)

        if old and new:
            status = "kept"
            status_label = "Осталась"
        elif new:
            status = "added"
            status_label = "Добавлена"
        else:
            status = "removed"
            status_label = "Удалена"

        old_value = old.get("value") if old else None
        new_value = new.get("value") if new else None
        old_weight = old.get("weight_pct") if old else None
        new_weight = new.get("weight_pct") if new else None

        rows.append(
            {
                "ticker": ticker,
                "name": (new or old or {}).get("name"),
                "status": status,
                "status_label": status_label,
                "old_action": old.get("action") if old else None,
                "new_action": new.get("action") if new else None,
                "old_label": old.get("label") if old else None,
                "new_label": new.get("label") if new else None,
                "old_quantity": old.get("quantity") if old else None,
                "new_quantity": new.get("quantity") if new else None,
                "delta_quantity": _delta(new.get("quantity") if new else None, old.get("quantity") if old else None),
                "old_value": old_value,
                "new_value": new_value,
                "delta_value": _delta(new_value, old_value),
                "old_weight_pct": old_weight,
                "new_weight_pct": new_weight,
                "delta_weight_pct": _delta(new_weight, old_weight),
                "old_score": old.get("score") if old else None,
                "new_score": new.get("score") if new else None,
                "delta_score": _delta(new.get("score") if new else None, old.get("score") if old else None),
                "old_target_upside_pct": old.get("target_upside_pct") if old else None,
                "new_target_upside_pct": new.get("target_upside_pct") if new else None,
                "old_stop_downside_pct": old.get("stop_downside_pct") if old else None,
                "new_stop_downside_pct": new.get("stop_downside_pct") if new else None,
                "ticker_url": (new or old or {}).get("ticker_url") or f"/tickers/{ticker}",
            }
        )

    left_summary = left.get("summary") or {}
    right_summary = right.get("summary") or {}

    compare_summary = {
        "added": sum(1 for row in rows if row["status"] == "added"),
        "removed": sum(1 for row in rows if row["status"] == "removed"),
        "kept": sum(1 for row in rows if row["status"] == "kept"),
        "total_compared": len(rows),
        "positions_count_delta": _delta(right_summary.get("positions_count"), left_summary.get("positions_count")),
        "invested_delta": _delta(right_summary.get("invested"), left_summary.get("invested")),
        "cash_delta": _delta(right_summary.get("cash"), left_summary.get("cash")),
        "cash_pct_delta": _delta(right_summary.get("cash_pct"), left_summary.get("cash_pct")),
        "risk_reward_delta": _delta(right_summary.get("risk_reward_ratio"), left_summary.get("risk_reward_ratio")),
        "old_risk_reward_ratio": _round(left_summary.get("risk_reward_ratio")),
        "new_risk_reward_ratio": _round(right_summary.get("risk_reward_ratio")),
        "old_risk_reward_label": left_summary.get("risk_reward_label"),
        "new_risk_reward_label": right_summary.get("risk_reward_label"),
    }

    return {
        "ok": True,
        "left": left,
        "right": right,
        "summary": compare_summary,
        "rows": rows,
    }


def portfolio_construct_snapshot_compare_to_csv(data: dict[str, Any]) -> str:
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")

    left = data.get("left") or {}
    right = data.get("right") or {}
    summary = data.get("summary") or {}

    writer.writerow(["Portfolio snapshot compare"])
    writer.writerow(["left_id", left.get("id")])
    writer.writerow(["right_id", right.get("id")])
    writer.writerow(["left_created_at", left.get("created_at")])
    writer.writerow(["right_created_at", right.get("created_at")])
    writer.writerow(["added", summary.get("added")])
    writer.writerow(["removed", summary.get("removed")])
    writer.writerow(["kept", summary.get("kept")])
    writer.writerow(["cash_delta", summary.get("cash_delta")])
    writer.writerow(["risk_reward_delta", summary.get("risk_reward_delta")])
    writer.writerow([])

    writer.writerow([
        "ticker",
        "name",
        "status",
        "old_action",
        "new_action",
        "old_quantity",
        "new_quantity",
        "delta_quantity",
        "old_value",
        "new_value",
        "delta_value",
        "old_weight_pct",
        "new_weight_pct",
        "delta_weight_pct",
        "old_score",
        "new_score",
        "delta_score",
        "old_target_upside_pct",
        "new_target_upside_pct",
        "old_stop_downside_pct",
        "new_stop_downside_pct",
    ])

    for row in data.get("rows") or []:
        writer.writerow([
            row.get("ticker"),
            row.get("name"),
            row.get("status"),
            row.get("old_action"),
            row.get("new_action"),
            row.get("old_quantity"),
            row.get("new_quantity"),
            row.get("delta_quantity"),
            row.get("old_value"),
            row.get("new_value"),
            row.get("delta_value"),
            row.get("old_weight_pct"),
            row.get("new_weight_pct"),
            row.get("delta_weight_pct"),
            row.get("old_score"),
            row.get("new_score"),
            row.get("delta_score"),
            row.get("old_target_upside_pct"),
            row.get("new_target_upside_pct"),
            row.get("old_stop_downside_pct"),
            row.get("new_stop_downside_pct"),
        ])

    return output.getvalue()

