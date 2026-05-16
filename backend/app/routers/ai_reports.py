from __future__ import annotations

from fastapi import APIRouter, Body as AIReportBody, Depends, Query
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.ai_report import build_ai_report
from app.services.ai_report_compare import build_ai_report_compare
from app.services.ai_report_compare_html import build_ai_report_compare_html
from app.services.ai_report_export import build_ai_report_markdown
from app.services.ai_report_history import (
    cleanup_ai_report_snapshots,
    delete_ai_report_snapshot,
    get_ai_report_markdown,
    get_ai_report_snapshot,
    list_ai_report_snapshots,
    preview_ai_report_cleanup,
    save_ai_report_snapshot,
    update_ai_report_snapshot_meta,
)
from app.services.ai_report_history_page_html import build_ai_report_history_page_html
from app.services.ai_report_page_html import build_ai_report_demo_html
from app.services.ai_report_saved_view_html import build_ai_report_saved_view_html
from app.services.ai_report_trends import build_ai_report_trends_csv, list_ai_report_trends
from app.services.ai_report_trends_html import build_ai_report_trends_html
from app.services.portfolio_store import get_portfolio_positions

router = APIRouter()


@router.post("/ai/report")
def ai_report(
    payload: dict = AIReportBody(default={}),
    db: Session = Depends(get_db),
):
    positions = payload.get("positions") or get_portfolio_positions(db)

    return build_ai_report(
        db=db,
        positions=positions,
    )


@router.get("/ai/report/demo", response_class=HTMLResponse)
def ai_report_demo_page():
    return build_ai_report_demo_html()


@router.post("/ai/report/markdown", response_class=PlainTextResponse)
def ai_report_markdown(
    payload: dict = AIReportBody(default={}),
    db: Session = Depends(get_db),
):
    positions = payload.get("positions") or get_portfolio_positions(db)

    report = build_ai_report(
        db=db,
        positions=positions,
    )

    return build_ai_report_markdown(report)


@router.get("/ai/report/demo.md")
def ai_report_demo_markdown(db: Session = Depends(get_db)):
    positions = [
        {"ticker": "SBER", "quantity": 10},
        {"ticker": "LKOH", "quantity": 1},
        {"ticker": "GAZP", "quantity": 50},
        {"ticker": "PLZL", "quantity": 1},
    ]

    report = build_ai_report(
        db=db,
        positions=positions,
    )

    markdown = build_ai_report_markdown(report)
    filename = f'ai_report_{report.get("date", "demo")}.md'

    return Response(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )


@router.post("/ai/report/build-and-save")
def ai_report_build_and_save(
    payload: dict = AIReportBody(default={}),
    db: Session = Depends(get_db),
):
    positions = payload.get("positions")

    report = build_ai_report(
        db=db,
        positions=positions,
    )

    saved = save_ai_report_snapshot(
        db=db,
        positions=positions,
    )

    report["saved_report"] = saved
    return report


@router.post("/ai/report/save")
def ai_report_save(
    payload: dict = AIReportBody(default={}),
    db: Session = Depends(get_db),
):
    positions = payload.get("positions") or get_portfolio_positions(db)

    return save_ai_report_snapshot(
        db=db,
        positions=positions,
    )


@router.get("/ai/reports/dashboard", response_class=HTMLResponse)
def ai_reports_dashboard_page():
    return build_ai_report_history_page_html()


@router.get("/ai/reports")
def ai_reports_list(
    limit: int = Query(50, ge=1, le=500),
    favorite: bool | None = Query(None),
    with_note: bool = Query(False),
    db: Session = Depends(get_db),
):
    return list_ai_report_snapshots(
        db=db,
        limit=limit,
        favorite=favorite,
        with_note=with_note,
    )


@router.get("/ai/reports/trends.csv")
def ai_report_trends_csv(
    limit: int = Query(500, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    csv_text = build_ai_report_trends_csv(
        db=db,
        limit=limit,
    )

    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="ai_report_trends.csv"'
        },
    )


@router.get("/ai/reports/trends.json")
def ai_report_trends_json(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return list_ai_report_trends(
        db=db,
        limit=limit,
    )


@router.get("/ai/reports/trends", response_class=HTMLResponse)
def ai_report_trends_page():
    return build_ai_report_trends_html()


@router.patch("/ai/reports/{report_id}/meta")
def ai_report_update_meta(
    report_id: int,
    payload: dict = AIReportBody(default={}),
    db: Session = Depends(get_db),
):
    report = update_ai_report_snapshot_meta(
        db=db,
        report_id=report_id,
        is_favorite=payload.get("is_favorite"),
        note=payload.get("note"),
    )

    if report is None:
        return Response(
            content='{"error":"Report not found"}',
            status_code=404,
            media_type="application/json",
        )

    return report


@router.get("/ai/reports/{report_id}.md")
def ai_report_saved_markdown(
    report_id: int,
    db: Session = Depends(get_db),
):
    markdown = get_ai_report_markdown(
        db=db,
        report_id=report_id,
    )

    if markdown is None:
        return Response(
            content="Report not found",
            status_code=404,
            media_type="text/plain; charset=utf-8",
        )

    return Response(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="ai_report_{report_id}.md"'
        },
    )


@router.get("/ai/reports/cleanup/preview")
def ai_reports_cleanup_preview(
    keep: int = Query(30, ge=0, le=1000),
    db: Session = Depends(get_db),
):
    return preview_ai_report_cleanup(
        db=db,
        keep=keep,
    )


@router.delete("/ai/reports/cleanup")
def ai_reports_cleanup(
    keep: int = Query(30, ge=0, le=1000),
    db: Session = Depends(get_db),
):
    return cleanup_ai_report_snapshots(
        db=db,
        keep=keep,
    )


@router.delete("/ai/reports/{report_id}")
def ai_report_saved_delete(
    report_id: int,
    db: Session = Depends(get_db),
):
    ok = delete_ai_report_snapshot(
        db=db,
        report_id=report_id,
    )

    if not ok:
        return Response(
            content='{"error":"Report not found"}',
            status_code=404,
            media_type="application/json",
        )

    return {"ok": True, "deleted_id": report_id}


@router.get("/ai/reports/{report_id}")
def ai_report_saved_detail(
    report_id: int,
    db: Session = Depends(get_db),
):
    report = get_ai_report_snapshot(
        db=db,
        report_id=report_id,
    )

    if report is None:
        return Response(
            content='{"error":"Report not found"}',
            status_code=404,
            media_type="application/json",
        )

    return report


@router.get("/ai/reports/{report_id}/view", response_class=HTMLResponse)
def ai_report_saved_view(
    report_id: int,
    db: Session = Depends(get_db),
):
    report = get_ai_report_snapshot(
        db=db,
        report_id=report_id,
    )

    if report is None:
        return Response(
            content="Report not found",
            status_code=404,
            media_type="text/plain; charset=utf-8",
        )

    return build_ai_report_saved_view_html(report)


@router.get("/ai/report/compare")
def ai_report_compare_page(
    left_id: int = Query(...),
    right_id: int = Query(...),
    db: Session = Depends(get_db),
):
    comparison = build_ai_report_compare(
        db=db,
        left_id=left_id,
        right_id=right_id,
    )

    if comparison is None:
        return Response(
            content="Report not found",
            status_code=404,
            media_type="text/plain; charset=utf-8",
        )

    return Response(
        content=build_ai_report_compare_html(comparison),
        media_type="text/html; charset=utf-8",
    )


@router.get("/ai/report/compare/latest")
def ai_report_compare_latest(
    db: Session = Depends(get_db),
):
    reports = list_ai_report_snapshots(
        db=db,
        limit=2,
    )

    if len(reports) < 2:
        return Response(
            content="Need at least two saved reports to compare",
            status_code=400,
            media_type="text/plain; charset=utf-8",
        )

    new_report = reports[0]
    old_report = reports[1]

    return RedirectResponse(
        url=f"/ai/report/compare?left_id={new_report['id']}&right_id={old_report['id']}",
        status_code=302,
    )


@router.get("/ai/report/compare.json")
def ai_report_compare_json(
    left_id: int = Query(...),
    right_id: int = Query(...),
    db: Session = Depends(get_db),
):
    comparison = build_ai_report_compare(
        db=db,
        left_id=left_id,
        right_id=right_id,
    )

    if comparison is None:
        return Response(
            content='{"error":"Report not found"}',
            status_code=404,
            media_type="application/json",
        )

    return comparison
