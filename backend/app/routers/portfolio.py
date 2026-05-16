from __future__ import annotations

from fastapi import APIRouter, Body as PortfolioConstructBody, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from app.db import get_db

router = APIRouter()

# --- Portfolio constructor ---

from app.services.portfolio_constructor import construct_portfolio
from app.services.portfolio_constructor_page_html import build_portfolio_constructor_page_html


@router.post("/portfolio/construct")
def portfolio_construct(
    payload: dict = PortfolioConstructBody(default={}),
    db: Session = Depends(get_db),
):
    return construct_portfolio(
        db=db,
        budget=float(payload.get("budget") or 100000),
        risk_profile=payload.get("risk_profile") or "balanced",
        horizon=payload.get("horizon") or "medium",
        quality_mode=payload.get("quality_mode") or "normal",
        model_version=payload.get("model_version"),
        tickers=payload.get("tickers"),
    )




@router.post("/portfolio/construct.csv")
def portfolio_construct_csv(
    payload: dict = PortfolioConstructBody(default={}),
    db: Session = Depends(get_db),
):
    import csv
    import io

    data = construct_portfolio(
        db=db,
        budget=float(payload.get("budget") or 100000),
        risk_profile=payload.get("risk_profile") or "balanced",
        horizon=payload.get("horizon") or "medium",
        quality_mode=payload.get("quality_mode") or "normal",
        model_version=payload.get("model_version"),
        tickers=payload.get("tickers"),
    )

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "row_type",
        "ticker",
        "name",
        "sector",
        "action",
        "label",
        "reason",
        "price",
        "lot_size",
        "lots",
        "quantity",
        "value",
        "weight_pct",
        "score",
        "confidence_pct",
        "risk_level",
        "entry_price",
        "target_price",
        "stop_loss",
        "target_upside_pct",
        "target_upside_rub",
        "stop_downside_pct",
        "stop_downside_rub",
        "trend",
        "return_5d_pct",
        "volatility_20d_pct",
        "volume_ratio",
    ])

    for row in data.get("positions", []):
        writer.writerow([
            "position",
            row.get("ticker"),
            row.get("name"),
            row.get("sector"),
            row.get("action"),
            row.get("label"),
            "",
            row.get("price"),
            row.get("lot_size"),
            row.get("lots"),
            row.get("quantity"),
            row.get("value"),
            row.get("weight_pct"),
            row.get("score"),
            row.get("confidence_pct"),
            row.get("risk_level"),
            row.get("entry_price"),
            row.get("target_price"),
            row.get("stop_loss"),
            row.get("target_upside_pct"),
            row.get("target_upside_rub"),
            row.get("stop_downside_pct"),
            row.get("stop_downside_rub"),
            row.get("trend"),
            row.get("return_5d_pct"),
            row.get("volatility_20d_pct"),
            row.get("volume_ratio"),
        ])

    for row in data.get("excluded", []):
        writer.writerow([
            "excluded",
            row.get("ticker"),
            row.get("name"),
            "",
            row.get("action"),
            row.get("label"),
            row.get("reason"),
            row.get("price"),
            row.get("lot_size"),
            "",
            "",
            "",
            "",
            row.get("score"),
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ])

    summary = data.get("summary") or {}
    filename = (
        "portfolio_construct_"
        f"{data.get('risk_profile', 'risk')}_"
        f"{data.get('horizon', 'horizon')}_"
        f"{data.get('quality_mode', 'quality')}.csv"
    )

    # Добавляем summary в конец отдельным блоком, чтобы CSV оставался читаемым.
    writer.writerow([])
    writer.writerow(["summary_key", "summary_value"])
    for key in [
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
        "buy_positions",
        "hold_positions",
        "risk_signals_in_market",
    ]:
        writer.writerow([key, summary.get(key)])

    content = "\ufeff" + output.getvalue()

    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )



# --- Portfolio constructor snapshots ---

from app.services.portfolio_construct_history import (
    create_portfolio_construct_snapshot,
    delete_portfolio_construct_snapshot,
    get_latest_portfolio_construct_snapshot,
    get_portfolio_construct_snapshot,
    get_portfolio_construct_snapshot_stats,
    list_portfolio_construct_snapshots,
    portfolio_construct_snapshots_to_csv,
)


@router.post("/portfolio/construct/snapshot")
def portfolio_construct_snapshot_create(
    payload: dict = PortfolioConstructBody(default={}),
    db: Session = Depends(get_db),
):
    return create_portfolio_construct_snapshot(
        db=db,
        payload=payload,
    )


@router.get("/portfolio/construct/snapshots")
def portfolio_construct_snapshots_list(
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return list_portfolio_construct_snapshots(
        db=db,
        limit=limit,
    )




@router.delete("/portfolio/construct/snapshots/{snapshot_id}")
def portfolio_construct_snapshot_delete(
    snapshot_id: int,
    db: Session = Depends(get_db),
):
    result = delete_portfolio_construct_snapshot(
        db=db,
        snapshot_id=snapshot_id,
    )

    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result)

    return result





@router.get("/portfolio/construct/snapshots.csv")
def portfolio_construct_snapshots_csv(
    limit: int = Query(500, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    from fastapi.responses import Response

    data = list_portfolio_construct_snapshots(
        db=db,
        limit=limit,
    )

    csv_text = portfolio_construct_snapshots_to_csv(data)

    return Response(
        content="\ufeff" + csv_text,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="portfolio_snapshots.csv"',
        },
    )



@router.get("/portfolio/construct/snapshots/stats")
def portfolio_construct_snapshots_stats(
    limit: int = Query(500, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    return get_portfolio_construct_snapshot_stats(
        db=db,
        limit=limit,
    )

@router.get("/portfolio/construct/snapshots/latest")
def portfolio_construct_snapshot_latest(
    db: Session = Depends(get_db),
):
    return get_latest_portfolio_construct_snapshot(db=db)

@router.get("/portfolio/construct/snapshots/{snapshot_id}")
def portfolio_construct_snapshot_detail(
    snapshot_id: int,
    db: Session = Depends(get_db),
):
    result = get_portfolio_construct_snapshot(
        db=db,
        snapshot_id=snapshot_id,
    )

    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result)

    return result



# --- Portfolio constructor history page ---

from app.services.portfolio_construct_history_page_html import build_portfolio_construct_history_page_html




from app.services.portfolio_construct_snapshot_detail_page_html import (
    build_portfolio_construct_snapshot_detail_page_html,
)


@router.get("/portfolio/construct/snapshots/{snapshot_id}/view", response_class=HTMLResponse)
def portfolio_construct_snapshot_view_page(
    snapshot_id: int,
    db: Session = Depends(get_db),
):
    result = get_portfolio_construct_snapshot(
        db=db,
        snapshot_id=snapshot_id,
    )

    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result)

    return build_portfolio_construct_snapshot_detail_page_html(
        result.get("snapshot") or {},
    )



# --- Portfolio constructor snapshot compare ---

from app.services.portfolio_construct_snapshot_compare import compare_portfolio_construct_snapshots, portfolio_construct_snapshot_compare_to_csv
from app.services.portfolio_construct_snapshot_compare_page_html import (
    build_portfolio_construct_snapshot_compare_page_html,
)




@router.get("/portfolio/construct/compare.csv")
def portfolio_construct_compare_csv(
    left_id: int | None = Query(None),
    right_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    from fastapi.responses import Response

    result = compare_portfolio_construct_snapshots(
        db=db,
        left_id=left_id,
        right_id=right_id,
    )

    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result)

    csv_text = portfolio_construct_snapshot_compare_to_csv(result)
    left = result.get("left") or {}
    right = result.get("right") or {}
    filename = f"portfolio_compare_{left.get('id', 'left')}_{right.get('id', 'right')}.csv"

    return Response(
        content="\ufeff" + csv_text,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )

@router.get("/portfolio/construct/compare.json")
def portfolio_construct_compare_json(
    left_id: int | None = Query(None),
    right_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    result = compare_portfolio_construct_snapshots(
        db=db,
        left_id=left_id,
        right_id=right_id,
    )

    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result)

    return result


@router.get("/portfolio/construct/compare", response_class=HTMLResponse)
def portfolio_construct_compare_page(
    left_id: int | None = Query(None),
    right_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    result = compare_portfolio_construct_snapshots(
        db=db,
        left_id=left_id,
        right_id=right_id,
    )

    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result)

    return build_portfolio_construct_snapshot_compare_page_html(result)

@router.get("/portfolio/construct/history", response_class=HTMLResponse)
def portfolio_construct_history_page():
    return build_portfolio_construct_history_page_html()

@router.get("/portfolio/construct/demo", response_class=HTMLResponse)
def portfolio_construct_demo_page():
    return build_portfolio_constructor_page_html()
