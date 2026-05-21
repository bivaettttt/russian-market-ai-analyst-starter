from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from app.db import get_db

AIReportHTMLResponse = HTMLResponse

router = APIRouter()


# --- ML probability engine ---

from app.services.ml_probability_engine import get_ml_probability_status
from app.services.ml_probability_evaluation import evaluate_ml_probability_model
from app.services.ml_model_report import build_ml_model_report
from app.services.ml_model_report_page_html import build_ml_model_report_page_html


@router.get("/signals/ml/status")
def market_signals_ml_status():
    return get_ml_probability_status()


@router.get("/signals/ml/evaluation")
def market_signals_ml_evaluation(
    thresholds: str = Query("0.30,0.35,0.40,0.45,0.50,0.55,0.60"),
    max_samples: int | None = Query(None, ge=1000, le=100000),
    db: Session = Depends(get_db),
):
    threshold_values = [
        float(item.strip())
        for item in thresholds.split(",")
        if item.strip()
    ]

    return evaluate_ml_probability_model(
        db=db,
        thresholds=threshold_values,
        max_samples=max_samples,
    )




@router.get("/signals/ml/report")
def market_signals_ml_report(
    thresholds: str = Query("0.25,0.30,0.35,0.40,0.45,0.50"),
    max_samples: int | None = Query(12000, ge=1000, le=100000),
    min_signals: int = Query(30, ge=1, le=10000),
    db: Session = Depends(get_db),
):
    threshold_values = [
        float(item.strip())
        for item in thresholds.split(",")
        if item.strip()
    ]

    return build_ml_model_report(
        db=db,
        thresholds=threshold_values,
        max_samples=max_samples,
        min_signals=min_signals,
    )




@router.get("/signals/ml/report-page", response_class=AIReportHTMLResponse)
def market_signals_ml_report_page():
    return build_ml_model_report_page_html()


# --- Market signals dashboard ---

from app.services.signals_data import list_market_signals
from app.services.consumer_signals import build_consumer_signal_for_ticker, list_consumer_signals
from app.services.consumer_signal_backtest_audit import build_consumer_signal_backtest_audit
from app.services.consumer_signal_backtest_audit_page_html import build_consumer_signal_backtest_audit_page_html
from app.services.signals_page_html import build_signals_page_html




@router.get("/signals/consumer.json")
def consumer_signals_data_api(
    limit: int = Query(100, ge=1, le=500),
    candles_limit: int = Query(240, ge=20, le=1000),
    action: str | None = Query(None),
    min_probability: float | None = Query(None, ge=0, le=100),
    q: str | None = Query(None),
    scenario: str = Query("all", description="all, long, downside или neutral"),
    news: str = Query("all", description="all, with_events, no_events, boost, penalty, veto или info_only"),
    db: Session = Depends(get_db),
):
    return list_consumer_signals(
        db=db,
        limit=limit,
        action=action,
        min_probability=min_probability,
        candles_limit=candles_limit,
        q=q,
        scenario=scenario,
        news=news,
    )


@router.get("/signals/consumer/backtest-audit")
def consumer_signal_backtest_audit_api(
    max_tickers: int = Query(80, ge=1, le=300),
    max_samples: int = Query(2000, ge=50, le=20000),
    horizon: int = Query(20, ge=5, le=90),
    target_pct: float = Query(0.05, ge=0.005, le=0.25),
    stop_pct: float = Query(0.03, ge=0.005, le=0.20),
    min_history: int = Query(80, ge=30, le=250),
    db: Session = Depends(get_db),
):
    return build_consumer_signal_backtest_audit(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        horizon=horizon,
        target_pct=target_pct,
        stop_pct=stop_pct,
        min_history=min_history,
    )


@router.get("/signals/consumer/backtest-audit-page", response_class=AIReportHTMLResponse)
def consumer_signal_backtest_audit_page():
    return build_consumer_signal_backtest_audit_page_html()


@router.get("/signals/consumer/{ticker}.json")
def consumer_signal_ticker_api(
    ticker: str,
    candles_limit: int = Query(240, ge=20, le=1000),
    db: Session = Depends(get_db),
):
    return build_consumer_signal_for_ticker(
        db=db,
        ticker=ticker,
        candles_limit=candles_limit,
    )


@router.get("/signals/data")
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


@router.get("/signals", response_class=AIReportHTMLResponse)
def market_signals_page():
    return build_signals_page_html()




# --- Signal snapshots history ---

from app.services.signals_history import create_signal_snapshots, list_signal_snapshots
from app.services.signals_history_page_html import build_signals_history_page_html


@router.post("/signals/snapshot")
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


@router.get("/signals/history.json")
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


@router.get("/signals/history", response_class=AIReportHTMLResponse)
def market_signals_history_page():
    return build_signals_history_page_html()




# --- Signal evaluation ---

from app.services.signals_evaluation import list_signal_evaluations
from app.services.signals_evaluation_page_html import build_signals_evaluation_page_html


@router.get("/signals/evaluation.json")
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


@router.get("/signals/evaluation", response_class=AIReportHTMLResponse)
def market_signals_evaluation_page():
    return build_signals_evaluation_page_html()




# --- Signal backtest ---

from app.services.signals_backtest import run_signals_backtest
from app.services.signals_backtest_page_html import build_signals_backtest_page_html


@router.get("/signals/backtest.json")
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



@router.get("/signals/backtest.csv")
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

@router.get("/signals/backtest", response_class=AIReportHTMLResponse)
def market_signals_backtest_page():
    return build_signals_backtest_page_html()




@router.get("/signals/models/compare.csv")
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


@router.get("/signals/models/compare.json")
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


@router.get("/signals/models/compare", response_class=AIReportHTMLResponse)
def market_signals_models_compare_page():
    return build_signals_model_compare_page_html()



# --- Signal model quality ---

from app.services.signals_model_quality import build_signal_model_quality_report
from app.services.signals_model_quality_page_html import build_signals_model_quality_page_html


@router.get("/signals/models/quality.json")
def market_signals_models_quality_json(
    model_versions: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    candles_limit: int = Query(120, ge=20, le=1000),
    action: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return build_signal_model_quality_report(
        db=db,
        model_versions=model_versions,
        limit=limit,
        candles_limit=candles_limit,
        action=action,
    )


@router.get("/signals/models/quality", response_class=HTMLResponse)
def market_signals_models_quality_page():
    return build_signals_model_quality_page_html()


# --- Signal model registry ---

from app.services.signal_model_registry import (
    PRODUCTION_SIGNAL_MODEL_VERSION,
    get_production_signal_model_version,
    get_signal_model_info,
    list_signal_models,
    set_production_signal_model_version,
)


@router.get("/signals/models")
def market_signal_models():
    return {
        "production_model": get_signal_model_info(get_production_signal_model_version()),
        "models": list_signal_models(),
    }


@router.post("/signals/models/production")
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


@router.get("/signals/champion", response_class=HTMLResponse)
def market_signals_champion_page():
    return build_signal_champion_page_html()
