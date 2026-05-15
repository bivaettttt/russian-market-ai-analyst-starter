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

# --- Market signals dashboard ---

from app.services.signals_data import list_market_signals
from app.services.signals_page_html import build_signals_page_html


@app.get("/signals/data")
def market_signals_data_api(
    limit: int = Query(100, ge=1, le=500),
    candles_limit: int = Query(120, ge=20, le=1000),
    action: str | None = Query(None),
    model_version: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return list_market_signals(
        db=db,
        limit=limit,
        candles_limit=candles_limit,
        action=action,
        model_version=model_version,
    )


@app.get("/signals", response_class=AIReportHTMLResponse)
def market_signals_page():
    return build_signals_page_html()




# --- Signal snapshots history ---

from app.services.signals_history import create_signal_snapshots, list_signal_snapshots
from app.services.signals_history_page_html import build_signals_history_page_html


@app.post("/signals/snapshot")
def market_signals_snapshot_create(
    limit: int = Query(100, ge=1, le=500),
    candles_limit: int = Query(120, ge=20, le=1000),
    action: str | None = Query(None),
    model_version: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return create_signal_snapshots(
        db=db,
        limit=limit,
        candles_limit=candles_limit,
        action=action,
        model_version=model_version,
    )


@app.get("/signals/history.json")
def market_signals_history_json(
    limit: int = Query(100, ge=1, le=1000),
    ticker: str | None = Query(None),
    action: str | None = Query(None),
    model_version: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return list_signal_snapshots(
        db=db,
        limit=limit,
        ticker=ticker,
        action=action,
        model_version=model_version,
    )


@app.get("/signals/history", response_class=AIReportHTMLResponse)
def market_signals_history_page():
    return build_signals_history_page_html()




# --- Signal evaluation ---

from app.services.signals_evaluation import list_signal_evaluations
from app.services.signals_evaluation_page_html import build_signals_evaluation_page_html


@app.get("/signals/evaluation.json")
def market_signals_evaluation_json(
    limit: int = Query(100, ge=1, le=1000),
    ticker: str | None = Query(None),
    action: str | None = Query(None),
    model_version: str | None = Query(None),
    future_limit: int = Query(60, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return list_signal_evaluations(
        db=db,
        limit=limit,
        ticker=ticker,
        action=action,
        model_version=model_version,
        future_limit=future_limit,
    )


@app.get("/signals/evaluation", response_class=AIReportHTMLResponse)
def market_signals_evaluation_page():
    return build_signals_evaluation_page_html()




# --- Signal backtest ---

from app.services.signals_backtest import run_signals_backtest
from app.services.signals_backtest_page_html import build_signals_backtest_page_html


@app.get("/signals/backtest.json")
def market_signals_backtest_json(
    tickers: str | None = Query(None),
    limit: int = Query(300, ge=1, le=2000),
    min_history: int = Query(60, ge=20, le=500),
    future_limit: int = Query(20, ge=1, le=250),
    max_points_per_ticker: int = Query(25, ge=1, le=500),
    action: str | None = Query(None),
    model_version: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return run_signals_backtest(
        db=db,
        tickers=tickers,
        limit=limit,
        min_history=min_history,
        future_limit=future_limit,
        max_points_per_ticker=max_points_per_ticker,
        action=action,
        model_version=model_version,
    )



@app.get("/signals/backtest.csv")
def market_signals_backtest_csv(
    tickers: str = Query("SBER,GAZP,LKOH,PLZL"),
    limit: int = Query(150, ge=1, le=2000),
    min_history: int = Query(60, ge=20, le=300),
    future_limit: int = Query(20, ge=1, le=120),
    max_points_per_ticker: int = Query(25, ge=1, le=300),
    action: str | None = Query(None),
    model_version: str | None = Query(None),
    db: Session = Depends(get_db),
):
    import csv
    import io

    data = run_signals_backtest(
        db=db,
        tickers=tickers,
        limit=limit,
        min_history=min_history,
        future_limit=future_limit,
        max_points_per_ticker=max_points_per_ticker,
        action=action,
        model_version=model_version,
    )

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "id",
        "trade_date",
        "ticker",
            "model_version",
        "price",
        "change_pct",
        "action",
        "label",
        "confidence_pct",
        "risk_level",
        "entry_price",
        "target_price",
        "stop_loss",
        "horizon",
        "evaluation_status",
        "evaluation_label",
        "result_pct",
        "strategy_result_pct",
        "result_date",
        "details",
    ])

    for row in data.get("rows", []):
        evaluation = row.get("evaluation") or {}
        writer.writerow([
            row.get("id"),
            row.get("trade_date"),
            row.get("ticker"),
                row.get("model_version"),
            row.get("price"),
            row.get("change_pct"),
            row.get("action"),
            row.get("label"),
            row.get("confidence_pct"),
            row.get("risk_level"),
            row.get("entry_price"),
            row.get("target_price"),
            row.get("stop_loss"),
            row.get("horizon"),
            evaluation.get("status"),
            evaluation.get("label"),
            evaluation.get("result_pct"),
            row.get("strategy_result_pct"),
            evaluation.get("result_date"),
            evaluation.get("details"),
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="signals_backtest.csv"'
        },
    )


from app.services.signals_model_compare import compare_signal_models
from app.services.signals_model_compare_page_html import build_signals_model_compare_page_html

@app.get("/signals/backtest", response_class=AIReportHTMLResponse)
def market_signals_backtest_page():
    return build_signals_backtest_page_html()




@app.get("/signals/models/compare.csv")
def market_signals_models_compare_csv(
    tickers: str = Query("SBER,GAZP,LKOH,PLZL,MOEX,VTBR"),
    model_versions: str | None = Query(None),
    limit: int = Query(150, ge=1, le=2000),
    min_history: int = Query(60, ge=20, le=300),
    future_limit: int = Query(20, ge=1, le=120),
    max_points_per_ticker: int = Query(25, ge=1, le=300),
    action: str | None = Query(None),
    db: Session = Depends(get_db),
):
    import csv
    import io

    data = compare_signal_models(
        db=db,
        tickers=tickers,
        model_versions=model_versions,
        limit=limit,
        min_history=min_history,
        future_limit=future_limit,
        max_points_per_ticker=max_points_per_ticker,
        action=action,
    )

    winner = data.get("winner") or {}
    winner_model = winner.get("model_version")

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "rank",
        "is_winner",
        "model_version",
        "score",
        "total",
        "actionable_count",
        "buy_watch",
        "hold_watch",
        "risk_sell_watch",
        "success",
        "failed",
        "open",
        "neutral",
        "accuracy_pct",
        "avg_result_pct",
        "avg_strategy_result_pct",
    ])

    for index, row in enumerate(data.get("rows") or [], start=1):
        summary = row.get("summary") or {}

        writer.writerow([
            index,
            row.get("model_version") == winner_model,
            row.get("model_version"),
            row.get("score"),
            summary.get("total"),
            summary.get("actionable_count"),
            summary.get("buy_watch"),
            summary.get("hold_watch"),
            summary.get("risk_sell_watch"),
            summary.get("success"),
            summary.get("failed"),
            summary.get("open"),
            summary.get("neutral"),
            summary.get("accuracy_pct"),
            summary.get("avg_result_pct"),
            summary.get("avg_strategy_result_pct"),
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="signals_model_compare.csv"'
        },
    )


@app.get("/signals/models/compare.json")
def market_signals_models_compare_json(
    tickers: str = Query("SBER,GAZP,LKOH,PLZL,MOEX,VTBR"),
    model_versions: str | None = Query(None),
    limit: int = Query(150, ge=1, le=2000),
    min_history: int = Query(60, ge=20, le=300),
    future_limit: int = Query(20, ge=1, le=120),
    max_points_per_ticker: int = Query(25, ge=1, le=300),
    action: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return compare_signal_models(
        db=db,
        tickers=tickers,
        model_versions=model_versions,
        limit=limit,
        min_history=min_history,
        future_limit=future_limit,
        max_points_per_ticker=max_points_per_ticker,
        action=action,
    )


@app.get("/signals/models/compare", response_class=AIReportHTMLResponse)
def market_signals_models_compare_page():
    return build_signals_model_compare_page_html()

# --- Signal model registry ---

from app.services.signal_model_registry import (
    PRODUCTION_SIGNAL_MODEL_VERSION,
    get_production_signal_model_version,
    get_signal_model_info,
    list_signal_models,
    set_production_signal_model_version,
)


@app.get("/signals/models")
def market_signal_models():
    return {
        "production_model": get_signal_model_info(get_production_signal_model_version()),
        "models": list_signal_models(),
    }


@app.post("/signals/models/production")
def market_signal_models_set_production(
    model_version: str = Query(...),
):
    production_model = set_production_signal_model_version(model_version)

    return {
        "ok": True,
        "production_model": production_model,
        "models": list_signal_models(),
    }

# --- Signal champion dashboard ---

from app.services.signals_champion_page_html import build_signal_champion_page_html


@app.get("/signals/champion", response_class=HTMLResponse)
def market_signals_champion_page():
    return build_signal_champion_page_html()

# --- Portfolio constructor ---

from fastapi import Body as PortfolioConstructBody
from app.services.portfolio_constructor import construct_portfolio
from app.services.portfolio_constructor_page_html import build_portfolio_constructor_page_html


@app.post("/portfolio/construct")
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




@app.post("/portfolio/construct.csv")
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
    list_portfolio_construct_snapshots,
)


@app.post("/portfolio/construct/snapshot")
def portfolio_construct_snapshot_create(
    payload: dict = PortfolioConstructBody(default={}),
    db: Session = Depends(get_db),
):
    return create_portfolio_construct_snapshot(
        db=db,
        payload=payload,
    )


@app.get("/portfolio/construct/snapshots")
def portfolio_construct_snapshots_list(
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return list_portfolio_construct_snapshots(
        db=db,
        limit=limit,
    )




@app.delete("/portfolio/construct/snapshots/{snapshot_id}")
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



@app.get("/portfolio/construct/snapshots/latest")
def portfolio_construct_snapshot_latest(
    db: Session = Depends(get_db),
):
    return get_latest_portfolio_construct_snapshot(db=db)

@app.get("/portfolio/construct/snapshots/{snapshot_id}")
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


@app.get("/portfolio/construct/snapshots/{snapshot_id}/view", response_class=HTMLResponse)
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




@app.get("/portfolio/construct/compare.csv")
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

@app.get("/portfolio/construct/compare.json")
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


@app.get("/portfolio/construct/compare", response_class=HTMLResponse)
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

@app.get("/portfolio/construct/history", response_class=HTMLResponse)
def portfolio_construct_history_page():
    return build_portfolio_construct_history_page_html()

@app.get("/portfolio/construct/demo", response_class=HTMLResponse)
def portfolio_construct_demo_page():
    return build_portfolio_constructor_page_html()
