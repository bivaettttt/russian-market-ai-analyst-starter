from __future__ import annotations

import json
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import PortfolioConstructSnapshot
from app.services.portfolio_constructor import construct_portfolio


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _json_load(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _snapshot_signature_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Stable payload used to detect duplicate portfolio constructor snapshots."""
    return {
        "budget": data.get("budget"),
        "risk_profile": data.get("risk_profile"),
        "horizon": data.get("horizon"),
        "quality_mode": data.get("quality_mode"),
        "model_version": data.get("model_version"),
        "positions": data.get("positions") or [],
        "excluded": data.get("excluded") or [],
        "summary": data.get("summary") or {},
    }


def _snapshot_signature(data: dict[str, Any]) -> str:
    return json.dumps(
        _snapshot_signature_payload(data),
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


def _get_latest_snapshot_row(db: Session) -> PortfolioConstructSnapshot | None:
    PortfolioConstructSnapshot.__table__.create(
        bind=db.get_bind(),
        checkfirst=True,
    )

    return db.scalars(
        select(PortfolioConstructSnapshot)
        .order_by(desc(PortfolioConstructSnapshot.created_at), desc(PortfolioConstructSnapshot.id))
        .limit(1)
    ).first()


def portfolio_construct_snapshot_to_dict(row: PortfolioConstructSnapshot) -> dict[str, Any]:
    summary = _json_load(row.summary_json, {})
    positions = _json_load(row.positions_json, [])
    excluded = _json_load(row.excluded_json, [])
    payload = _json_load(row.payload_json, {})
    result = _json_load(row.result_json, {})

    return {
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "budget": row.budget,
        "risk_profile": row.risk_profile,
        "horizon": row.horizon,
        "quality_mode": row.quality_mode,
        "model_version": row.model_version,
        "summary": summary,
        "positions": positions,
        "excluded": excluded,
        "payload": payload,
        "result": result,
        "positions_count": len(positions),
        "excluded_count": len(excluded),
        "detail_url": f"/portfolio/construct/snapshots/{row.id}",
    }


def create_portfolio_construct_snapshot(
    db: Session,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = dict(payload or {})

    data = construct_portfolio(
        db=db,
        budget=float(payload.get("budget") or 100000),
        risk_profile=payload.get("risk_profile") or "balanced",
        horizon=payload.get("horizon") or "medium",
        quality_mode=payload.get("quality_mode") or "normal",
        model_version=payload.get("model_version"),
        tickers=payload.get("tickers"),
    )

    summary = data.get("summary") or {}
    positions = data.get("positions") or []
    excluded = data.get("excluded") or []

    latest_row = _get_latest_snapshot_row(db)
    if latest_row is not None:
        latest_data = _json_load(latest_row.result_json, {})
        if _snapshot_signature(latest_data) == _snapshot_signature(data):
            return {
                "ok": True,
                "created": False,
                "duplicate": True,
                "snapshot": portfolio_construct_snapshot_to_dict(latest_row),
            }

    row = PortfolioConstructSnapshot(
        budget=data.get("budget"),
        risk_profile=data.get("risk_profile"),
        horizon=data.get("horizon"),
        quality_mode=data.get("quality_mode"),
        model_version=data.get("model_version"),
        positions_json=_json_dump(positions),
        excluded_json=_json_dump(excluded),
        summary_json=_json_dump(summary),
        payload_json=_json_dump(payload),
        result_json=_json_dump(data),
    )

    db.add(row)
    db.commit()
    db.refresh(row)

    return {
        "ok": True,
        "created": True,
        "duplicate": False,
        "snapshot": portfolio_construct_snapshot_to_dict(row),
    }


def list_portfolio_construct_snapshots(
    db: Session,
    limit: int = 50,
) -> dict[str, Any]:
    PortfolioConstructSnapshot.__table__.create(
        bind=db.get_bind(),
        checkfirst=True,
    )

    rows = db.scalars(
        select(PortfolioConstructSnapshot)
        .order_by(desc(PortfolioConstructSnapshot.created_at), desc(PortfolioConstructSnapshot.id))
        .limit(limit)
    ).all()

    return {
        "total": len(rows),
        "rows": [portfolio_construct_snapshot_to_dict(row) for row in rows],
    }


def get_portfolio_construct_snapshot(
    db: Session,
    snapshot_id: int,
) -> dict[str, Any]:
    PortfolioConstructSnapshot.__table__.create(
        bind=db.get_bind(),
        checkfirst=True,
    )

    row = db.get(PortfolioConstructSnapshot, snapshot_id)

    if row is None:
        return {
            "ok": False,
            "error": "snapshot_not_found",
            "id": snapshot_id,
        }

    return {
        "ok": True,
        "snapshot": portfolio_construct_snapshot_to_dict(row),
    }


def delete_portfolio_construct_snapshot(
    db: Session,
    snapshot_id: int,
) -> dict[str, Any]:
    PortfolioConstructSnapshot.__table__.create(
        bind=db.get_bind(),
        checkfirst=True,
    )

    row = db.get(PortfolioConstructSnapshot, snapshot_id)

    if row is None:
        return {
            "ok": False,
            "error": "snapshot_not_found",
            "id": snapshot_id,
        }

    db.delete(row)
    db.commit()

    return {
        "ok": True,
        "deleted_id": snapshot_id,
    }


def get_latest_portfolio_construct_snapshot(
    db: Session,
) -> dict[str, Any]:
    PortfolioConstructSnapshot.__table__.create(
        bind=db.get_bind(),
        checkfirst=True,
    )

    row = db.scalars(
        select(PortfolioConstructSnapshot)
        .order_by(desc(PortfolioConstructSnapshot.created_at), desc(PortfolioConstructSnapshot.id))
        .limit(1)
    ).first()

    if row is None:
        return {
            "ok": False,
            "error": "snapshot_not_found",
            "message": "Portfolio constructor snapshots not found.",
        }

    return {
        "ok": True,
        "snapshot": portfolio_construct_snapshot_to_dict(row),
    }


def portfolio_construct_snapshots_to_csv(data: dict[str, Any]) -> str:
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")

    writer.writerow([
        "id",
        "created_at",
        "budget",
        "risk_profile",
        "horizon",
        "quality_mode",
        "model_version",
        "positions_count",
        "invested",
        "cash",
        "cash_pct",
        "avg_confidence_pct",
        "portfolio_risk_level",
        "target_upside_rub",
        "target_upside_pct",
        "stop_downside_rub",
        "stop_downside_pct",
        "risk_reward_ratio",
        "risk_reward_label",
        "portfolio_conclusion",
    ])

    for row in data.get("rows") or []:
        summary = row.get("summary") or {}

        writer.writerow([
            row.get("id"),
            row.get("created_at"),
            row.get("budget"),
            row.get("risk_profile"),
            row.get("horizon"),
            row.get("quality_mode"),
            row.get("model_version"),
            summary.get("positions_count") or row.get("positions_count"),
            summary.get("invested"),
            summary.get("cash"),
            summary.get("cash_pct"),
            summary.get("avg_confidence_pct"),
            summary.get("portfolio_risk_level"),
            summary.get("target_upside_rub"),
            summary.get("target_upside_pct"),
            summary.get("stop_downside_rub"),
            summary.get("stop_downside_pct"),
            summary.get("risk_reward_ratio"),
            summary.get("risk_reward_label"),
            summary.get("portfolio_conclusion"),
        ])

    return output.getvalue()


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _average(values: list[float]) -> float | None:
    if not values:
        return None

    return round(sum(values) / len(values), 2)


def _snapshot_stats_brief(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None

    summary = row.get("summary") or {}

    return {
        "id": row.get("id"),
        "created_at": row.get("created_at"),
        "model_version": row.get("model_version"),
        "risk_profile": row.get("risk_profile"),
        "horizon": row.get("horizon"),
        "quality_mode": row.get("quality_mode"),
        "positions_count": summary.get("positions_count") or row.get("positions_count"),
        "cash_pct": summary.get("cash_pct"),
        "risk_reward_ratio": summary.get("risk_reward_ratio"),
        "risk_reward_label": summary.get("risk_reward_label"),
        "portfolio_conclusion": summary.get("portfolio_conclusion"),
        "view_url": f"/portfolio/construct/snapshots/{row.get('id')}/view",
        "json_url": row.get("detail_url"),
    }


def get_portfolio_construct_snapshot_stats(
    db: Session,
    limit: int = 500,
) -> dict[str, Any]:
    data = list_portfolio_construct_snapshots(
        db=db,
        limit=limit,
    )

    rows = data.get("rows") or []

    rr_rows = []
    cash_pct_values: list[float] = []
    positions_values: list[float] = []

    quality_counts: dict[str, int] = {}
    model_counts: dict[str, int] = {}

    for row in rows:
        summary = row.get("summary") or {}

        rr = _safe_float(summary.get("risk_reward_ratio"))
        cash_pct = _safe_float(summary.get("cash_pct"))
        positions_count = _safe_float(summary.get("positions_count") or row.get("positions_count"))

        if rr is not None:
            rr_rows.append((rr, row))

        if cash_pct is not None:
            cash_pct_values.append(cash_pct)

        if positions_count is not None:
            positions_values.append(positions_count)

        quality = str(row.get("quality_mode") or "unknown")
        model = str(row.get("model_version") or "unknown")

        quality_counts[quality] = quality_counts.get(quality, 0) + 1
        model_counts[model] = model_counts.get(model, 0) + 1

    best_row = max(rr_rows, key=lambda item: item[0])[1] if rr_rows else None
    weakest_row = min(rr_rows, key=lambda item: item[0])[1] if rr_rows else None

    return {
        "ok": True,
        "total": len(rows),
        "limit": limit,
        "latest": _snapshot_stats_brief(rows[0] if rows else None),
        "best_by_risk_reward": _snapshot_stats_brief(best_row),
        "weakest_by_risk_reward": _snapshot_stats_brief(weakest_row),
        "avg_risk_reward_ratio": _average([item[0] for item in rr_rows]),
        "avg_cash_pct": _average(cash_pct_values),
        "avg_positions_count": _average(positions_values),
        "quality_counts": quality_counts,
        "model_counts": model_counts,
    }

