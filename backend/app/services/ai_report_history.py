from __future__ import annotations

import json
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import AIReportSnapshot
from app.services.ai_report import DEFAULT_DEMO_PORTFOLIO, build_ai_report
from app.services.ai_report_export import build_ai_report_markdown


def save_ai_report_snapshot(
    db: Session,
    positions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if positions is None:
        positions = DEFAULT_DEMO_PORTFOLIO

    report = build_ai_report(
        db=db,
        positions=positions,
    )

    markdown = build_ai_report_markdown(report)

    snapshot = AIReportSnapshot(
        report_date=report.get("date"),
        title=report.get("title", "AI Report российского рынка"),
        portfolio_json=json.dumps({"positions": positions}, ensure_ascii=False),
        report_json=json.dumps(report, ensure_ascii=False),
        markdown=markdown,
    )

    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    return snapshot_to_summary(snapshot)


def list_ai_report_snapshots(
    db: Session,
    limit: int = 50,
    favorite: bool | None = None,
    with_note: bool = False,
) -> list[dict[str, Any]]:
    query = select(AIReportSnapshot)

    if favorite is not None:
        query = query.where(AIReportSnapshot.is_favorite.is_(bool(favorite)))

    if with_note:
        query = query.where(
            AIReportSnapshot.note.is_not(None),
            AIReportSnapshot.note != "",
        )

    rows = db.scalars(
        query
        .order_by(desc(AIReportSnapshot.created_at))
        .limit(limit)
    ).all()

    return [snapshot_to_summary(row) for row in rows]


def get_ai_report_snapshot(
    db: Session,
    report_id: int,
) -> dict[str, Any] | None:
    row = db.get(AIReportSnapshot, report_id)

    if row is None:
        return None

    return {
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "report_date": row.report_date,
        "title": row.title,
        "portfolio": safe_json(row.portfolio_json),
        "report": safe_json(row.report_json),
        "markdown": row.markdown,
    }


def get_ai_report_markdown(
    db: Session,
    report_id: int,
) -> str | None:
    row = db.get(AIReportSnapshot, report_id)

    if row is None:
        return None

    return row.markdown or ""


def snapshot_to_summary(row: AIReportSnapshot) -> dict[str, Any]:
    return {
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "report_date": row.report_date,
        "title": row.title,
        "markdown_url": f"/ai/reports/{row.id}.md",
        "detail_url": f"/ai/reports/{row.id}",
        "view_url": f"/ai/reports/{row.id}/view",
        "is_favorite": bool(getattr(row, "is_favorite", False)),
        "note": getattr(row, "note", "") or "",
    }


def safe_json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}

    try:
        return json.loads(value)
    except Exception:
        return {}


def delete_ai_report_snapshot(
    db,
    report_id: int,
) -> bool:
    row = db.get(AIReportSnapshot, report_id)

    if row is None:
        return False

    db.delete(row)
    db.commit()

    return True


def preview_ai_report_cleanup(
    db: Session,
    keep: int = 30,
) -> dict[str, Any]:
    from sqlalchemy import select

    keep = max(0, int(keep))

    ids = (
        db.execute(
            select(AIReportSnapshot.id)
            .order_by(AIReportSnapshot.id.desc())
        )
        .scalars()
        .all()
    )

    keep_ids = ids[:keep]
    delete_ids = ids[keep:]

    return {
        "ok": True,
        "keep": keep,
        "total_reports": len(ids),
        "kept_count": len(keep_ids),
        "delete_count": len(delete_ids),
        "kept_ids": keep_ids,
        "delete_ids": delete_ids,
    }


def cleanup_ai_report_snapshots(
    db: Session,
    keep: int = 30,
) -> dict[str, Any]:
    preview = preview_ai_report_cleanup(
        db=db,
        keep=keep,
    )

    delete_ids = preview["delete_ids"]

    if not delete_ids:
        return {
            **preview,
            "deleted": 0,
            "message": "Удалять нечего.",
        }

    (
        db.query(AIReportSnapshot)
        .filter(AIReportSnapshot.id.in_(delete_ids))
        .delete(synchronize_session=False)
    )
    db.commit()

    return {
        **preview,
        "deleted": len(delete_ids),
        "message": f"Удалено старых отчётов: {len(delete_ids)}.",
    }


def update_ai_report_snapshot_meta(
    db: Session,
    report_id: int,
    is_favorite: bool | None = None,
    note: str | None = None,
) -> dict[str, Any] | None:
    row = db.get(AIReportSnapshot, report_id)

    if row is None:
        return None

    if is_favorite is not None:
        row.is_favorite = bool(is_favorite)

    if note is not None:
        row.note = str(note).strip()

    db.commit()
    db.refresh(row)

    return snapshot_to_summary(row)
