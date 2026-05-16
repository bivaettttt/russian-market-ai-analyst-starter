from __future__ import annotations
from fastapi import Response

import json
from datetime import date

from fastapi.responses import HTMLResponse
from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db import Base, engine, get_db
from app.models import Candle, Instrument, MarketEvent
from app.schemas import CandleOut, MarketEventOut, NewsAnalyzeRequest, NewsAnalyzeResponse
from app.services.event_classifier import EventClassifier
from app.services.moex_client import MoexClient
from app.services.market_radar import build_market_radar
from app.services.market_briefing import build_market_briefing
from app.services.market_signals import build_market_signals
from app.services.market_daily_report import build_market_daily_report
from app.services.dashboard_html import build_dashboard_html
from app.services.ticker_analysis import build_ticker_analysis
from app.services.signal_model_registry import PRODUCTION_SIGNAL_MODEL_VERSION

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Russian Market AI Analyst",
    description="Local-first AI analyst for Russian stock market data and events.",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/instruments")
def list_instruments(db: Session = Depends(get_db)):
    rows = db.scalars(select(Instrument).order_by(Instrument.ticker)).all()
    return rows


@app.post("/ingest/moex/securities")
async def ingest_moex_securities(board: str = "TQBR", db: Session = Depends(get_db)):
    client = MoexClient()
    securities = await client.get_board_securities(board=board)
    inserted = 0
    updated = 0

    for item in securities:
        ticker = item.get("ticker")
        if not ticker:
            continue

        try:
            lot_size = int(float(item.get("lot_size") or 1))
        except (TypeError, ValueError):
            lot_size = 1

        if lot_size <= 0:
            lot_size = 1

        instrument = db.scalar(select(Instrument).where(Instrument.ticker == ticker))
        if instrument:
            instrument.name = item.get("name") or item.get("short_name")
            instrument.board = board
            instrument.lot_size = lot_size
            updated += 1
        else:
            db.add(
                Instrument(
                    ticker=ticker,
                    name=item.get("name") or item.get("short_name"),
                    board=board,
                    lot_size=lot_size,
                )
            )
            inserted += 1
    db.commit()
    return {"board": board, "fetched": len(securities), "inserted": inserted, "updated": updated}


@app.post("/ingest/moex/{ticker}")
async def ingest_moex_candles(
    ticker: str,
    from_date: date = Query(..., description="YYYY-MM-DD"),
    to_date: date = Query(..., description="YYYY-MM-DD"),
    board: str = "TQBR",
    db: Session = Depends(get_db),
):
    client = MoexClient()
    rows = await client.get_daily_candles(ticker=ticker, from_date=from_date, to_date=to_date, board=board)
    saved = 0

    for row in rows:
        candle = Candle(
            ticker=row["ticker"],
            board=row["board"],
            trade_date=date.fromisoformat(row["trade_date"]),
            open=row.get("open"),
            high=row.get("high"),
            low=row.get("low"),
            close=row.get("close"),
            volume=row.get("volume"),
            value=row.get("value"),
        )
        existing = db.scalar(
            select(Candle).where(
                Candle.ticker == candle.ticker,
                Candle.board == candle.board,
                Candle.trade_date == candle.trade_date,
            )
        )
        if existing:
            existing.open = candle.open
            existing.high = candle.high
            existing.low = candle.low
            existing.close = candle.close
            existing.volume = candle.volume
            existing.value = candle.value
        else:
            db.add(candle)
        saved += 1

    db.commit()
    return {"ticker": ticker.upper(), "board": board, "rows_fetched": len(rows), "rows_saved": saved}


@app.get("/candles/{ticker}", response_model=list[CandleOut])
def get_candles(
    ticker: str,
    limit: int = Query(100, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(Candle)
        .where(Candle.ticker == ticker.upper())
        .order_by(desc(Candle.trade_date))
        .limit(limit)
    ).all()
    return list(reversed(rows))


@app.post("/analyze/news", response_model=NewsAnalyzeResponse)
async def analyze_news(payload: NewsAnalyzeRequest, db: Session = Depends(get_db)):
    analysis = await EventClassifier().analyze(payload.text, title=payload.title)

    event = MarketEvent(
        title=payload.title,
        text=payload.text,
        source=payload.source,
        url=payload.url,
        importance=analysis.importance,
        impact=analysis.impact,
        affected_assets=",".join(analysis.affected_assets),
        reasoning=analysis.reasoning,
        raw_analysis=analysis.model_dump_json(ensure_ascii=False),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    analysis.stored_event_id = event.id
    return analysis


@app.get("/events", response_model=list[MarketEventOut])
def list_events(limit: int = Query(50, ge=1, le=500), db: Session = Depends(get_db)):
    return db.scalars(select(MarketEvent).order_by(desc(MarketEvent.created_at)).limit(limit)).all()

@app.get("/market/radar")
def market_radar(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    return build_market_radar(db=db, limit=limit)


@app.get("/market/briefing")
def market_briefing(
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    return build_market_briefing(db=db, limit=limit)


@app.get("/market/signals")
def market_signals(
    price_threshold_pct: float = Query(2.0, ge=0.1, le=20.0),
    volume_spike_ratio: float = Query(2.0, ge=1.1, le=20.0),
    min_value_rub: float = Query(10_000_000, ge=0),
    db: Session = Depends(get_db),
):
    return build_market_signals(
        db=db,
        price_threshold_pct=price_threshold_pct,
        volume_spike_ratio=volume_spike_ratio,
        min_value_rub=min_value_rub,
    )


@app.get("/market/daily-report")
def market_daily_report(
    limit: int = Query(5, ge=1, le=20),
    price_threshold_pct: float = Query(1.5, ge=0.1, le=20.0),
    volume_spike_ratio: float = Query(2.0, ge=1.1, le=20.0),
    min_value_rub: float = Query(10_000_000, ge=0),
    db: Session = Depends(get_db),
):
    return build_market_daily_report(
        db=db,
        limit=limit,
        price_threshold_pct=price_threshold_pct,
        volume_spike_ratio=volume_spike_ratio,
        min_value_rub=min_value_rub,
    )



@app.get("/briefing/demo")
def demo_briefing(tickers: str = "SBER,GAZP,LKOH,MOEX", db: Session = Depends(get_db)):
    requested = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    events = db.scalars(select(MarketEvent).order_by(desc(MarketEvent.created_at)).limit(20)).all()

    latest_prices: dict[str, float | None] = {}
    for ticker in requested:
        candle = db.scalar(
            select(Candle).where(Candle.ticker == ticker).order_by(desc(Candle.trade_date)).limit(1)
        )
        latest_prices[ticker] = candle.close if candle else None

    top_events = [
        {
            "title": event.title,
            "importance": event.importance,
            "impact": event.impact,
            "affected_assets": event.affected_assets,
            "reasoning": event.reasoning,
        }
        for event in events[:5]
    ]

    return {
        "market": "MOEX / Russian equities",
        "tracked_tickers": requested,
        "latest_prices": latest_prices,
        "top_events": top_events,
        "note": "Demo briefing. Full version should add real-time market breadth, OFZ yields, FX, dividends, and source citations.",
    }

from fastapi.responses import HTMLResponse as DashboardHTMLResponse
from app.services.dashboard_html import build_dashboard_html as build_dashboard_page


@app.get("/dashboard", response_class=DashboardHTMLResponse)
def dashboard_page():
    return build_dashboard_page()



@app.get("/ticker/{ticker}/analysis")
def ticker_analysis(
    ticker: str,
    db: Session = Depends(get_db),
):
    return build_ticker_analysis(db=db, ticker=ticker)

from fastapi.responses import HTMLResponse as TickerHTMLResponse
from app.services.ticker_page_html import build_ticker_page_html


@app.get("/ticker/{ticker}", response_class=TickerHTMLResponse)
def ticker_page(ticker: str):
    return build_ticker_page_html(ticker)


@app.get("/ticker/{ticker}/history")
def ticker_history(
    ticker: str,
    limit: int = Query(120, ge=2, le=500),
    db: Session = Depends(get_db),
):
    ticker = ticker.upper().strip()

    candles = db.scalars(
        select(Candle)
        .where(Candle.ticker == ticker)
        .order_by(desc(Candle.trade_date))
        .limit(limit)
    ).all()

    rows = list(reversed(candles))

    return {
        "ticker": ticker,
        "rows": [
            {
                "date": item.trade_date.isoformat(),
                "open": item.open,
                "high": item.high,
                "low": item.low,
                "close": item.close,
                "volume": item.volume,
                "value": item.value,
            }
            for item in rows
        ],
    }

from fastapi import Body as PortfolioBody
from app.services.portfolio_analysis import analyze_portfolio


@app.post("/portfolio/analyze")
def portfolio_analyze(
    payload: dict = PortfolioBody(...),
    db: Session = Depends(get_db),
):
    return analyze_portfolio(
        db=db,
        positions=payload.get("positions", []),
    )

from fastapi.responses import HTMLResponse as PortfolioHTMLResponse
from app.services.portfolio_page_html import build_portfolio_demo_html


@app.get("/portfolio/demo", response_class=PortfolioHTMLResponse)
def portfolio_demo_page():
    return build_portfolio_demo_html()

from fastapi import Body as RSSBody
from app.services.rss_ingestor import (
    build_events_radar,
    ingest_default_rss_sources,
    ingest_rss_feed,
)


@app.post("/ingest/rss")
async def ingest_rss(
    payload: dict = RSSBody(...),
    db: Session = Depends(get_db),
):
    return await ingest_rss_feed(
        db=db,
        url=payload["url"],
        source=payload.get("source", "rss"),
        limit=int(payload.get("limit", 20)),
    )


@app.post("/ingest/rss/defaults")
async def ingest_rss_defaults(
    limit_per_source: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    return await ingest_default_rss_sources(
        db=db,
        limit_per_source=limit_per_source,
    )


@app.get("/events/radar")
def events_radar(
    limit: int = Query(30, ge=1, le=100),
    min_importance: int = Query(1, ge=1, le=10),
    ticker: str | None = None,
    db: Session = Depends(get_db),
):
    return build_events_radar(
        db=db,
        limit=limit,
        min_importance=min_importance,
        ticker=ticker,
    )

from fastapi.responses import HTMLResponse as EventsHTMLResponse
from app.services.events_dashboard_html import build_events_dashboard_html


@app.get("/events/dashboard", response_class=EventsHTMLResponse)
def events_dashboard_page():
    return build_events_dashboard_html()

from fastapi import Body as AIReportBody
from fastapi.responses import HTMLResponse as AIReportHTMLResponse
from app.services.ai_report import build_ai_report
from app.services.portfolio_store import get_portfolio_positions, save_portfolio_positions
from app.services.ai_report_page_html import build_ai_report_demo_html



# --- Portfolio storage API ---

@app.get("/portfolio/positions")
def portfolio_positions_get(
    db: Session = Depends(get_db),
):
    return {
        "positions": get_portfolio_positions(db),
    }


@app.post("/portfolio/positions")
def portfolio_positions_save(
    payload: dict = AIReportBody(default={}),
    db: Session = Depends(get_db),
):
    positions = payload.get("positions") or []
    saved = save_portfolio_positions(
        db=db,
        positions=positions,
    )

    return {
        "ok": True,
        "positions": saved,
    }


@app.post("/ai/report")
def ai_report(
    payload: dict = AIReportBody(default={}),
    db: Session = Depends(get_db),
):
    positions = payload.get("positions") or get_portfolio_positions(db)

    return build_ai_report(
        db=db,
        positions=positions,
    )


@app.get("/ai/report/demo", response_class=AIReportHTMLResponse)
def ai_report_demo_page():
    return build_ai_report_demo_html()

from fastapi.responses import PlainTextResponse as AIReportPlainTextResponse
from app.services.ai_report_export import build_ai_report_markdown


@app.post("/ai/report/markdown", response_class=AIReportPlainTextResponse)
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


@app.get("/ai/report/demo.md")
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

@app.post("/ai/report/build-and-save")
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


@app.post("/ai/report/save")
def ai_report_save(
    payload: dict = AIReportBody(default={}),
    db: Session = Depends(get_db),
):
    positions = payload.get("positions") or get_portfolio_positions(db)

    return save_ai_report_snapshot(
        db=db,
        positions=positions,
    )


from app.services.ai_report_trends_html import build_ai_report_trends_html
from app.services.ai_report_history_page_html import build_ai_report_history_page_html
@app.get("/ai/reports/dashboard", response_class=AIReportHTMLResponse)
def ai_reports_dashboard_page():
    return build_ai_report_history_page_html()


from app.services.ai_report_history import list_ai_report_snapshots, save_ai_report_snapshot
@app.get("/ai/reports")
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


@app.get("/ai/reports/trends.csv")
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


@app.get("/ai/reports/trends.json")
def ai_report_trends_json(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return list_ai_report_trends(
        db=db,
        limit=limit,
    )


@app.get("/ai/reports/trends", response_class=AIReportHTMLResponse)
def ai_report_trends_page():
    return build_ai_report_trends_html()


from app.services.ai_report_history import update_ai_report_snapshot_meta


@app.patch("/ai/reports/{report_id}/meta")
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


@app.get("/ai/reports/{report_id}.md")
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





from app.services.ai_report_history import preview_ai_report_cleanup, cleanup_ai_report_snapshots

@app.get("/ai/reports/cleanup/preview")
def ai_reports_cleanup_preview(
    keep: int = Query(30, ge=0, le=1000),
    db: Session = Depends(get_db),
):
    return preview_ai_report_cleanup(
        db=db,
        keep=keep,
    )


@app.delete("/ai/reports/cleanup")
def ai_reports_cleanup(
    keep: int = Query(30, ge=0, le=1000),
    db: Session = Depends(get_db),
):
    return cleanup_ai_report_snapshots(
        db=db,
        keep=keep,
    )


@app.delete("/ai/reports/{report_id}")
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


@app.get("/ai/reports/{report_id}")
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


# --- System one-click update ---

from app.services.system_update import run_system_update_and_report


@app.post("/system/update-and-report")
def system_update_and_report(
    db: Session = Depends(get_db),
):
    return run_system_update_and_report(db=db)
from fastapi.responses import HTMLResponse as SystemDashboardHTMLResponse
from app.services.system_dashboard_html import build_system_dashboard_html


@app.get("/system/dashboard", response_class=SystemDashboardHTMLResponse)
def system_dashboard_page():
    return build_system_dashboard_html()


# --- AI Report saved HTML view ---

from app.services.ai_report_saved_view_html import build_ai_report_saved_view_html


@app.get("/ai/reports/{report_id}/view", response_class=AIReportHTMLResponse)
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


# --- AI Report compare ---

from app.services.ai_report_compare import build_ai_report_compare
from app.services.ai_report_compare_html import build_ai_report_compare_html


@app.get("/ai/report/compare")
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



from fastapi.responses import RedirectResponse as AIReportRedirectResponse


@app.get("/ai/report/compare/latest")
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

    return AIReportRedirectResponse(
        url=f"/ai/report/compare?left_id={new_report['id']}&right_id={old_report['id']}",
        status_code=302,
    )


@app.get("/ai/report/compare.json")
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


# --- Ticker pages and live-ish data ---

from app.services.ticker_data import get_ticker_snapshot
from app.services.ticker_page_html import build_ticker_page_html


@app.get("/tickers/{ticker}/data")
def ticker_data_api(
    ticker: str,
    limit: int = Query(240, ge=10, le=1000),
    db: Session = Depends(get_db),
):
    return get_ticker_snapshot(
        db=db,
        ticker=ticker,
        limit=limit,
    )


@app.get("/tickers/{ticker}", response_class=AIReportHTMLResponse)
def ticker_page(
    ticker: str,
):
    return build_ticker_page_html(ticker)

# --- Signals router ---

from app.routers.signals import router as signals_router

app.include_router(signals_router)

# --- Portfolio router ---

from app.routers.portfolio import router as portfolio_router

app.include_router(portfolio_router)

