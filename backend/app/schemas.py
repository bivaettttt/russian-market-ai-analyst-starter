from datetime import date, datetime
from pydantic import BaseModel, Field


class CandleOut(BaseModel):
    ticker: str
    board: str
    trade_date: date
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: float | None = None
    value: float | None = None

    model_config = {"from_attributes": True}


class NewsAnalyzeRequest(BaseModel):
    text: str = Field(min_length=10)
    title: str | None = None
    source: str | None = "manual"
    url: str | None = None


class NewsAnalyzeResponse(BaseModel):
    title: str | None = None
    event_type: str
    importance: int
    impact: str
    affected_assets: list[str]
    affected_sectors: list[str]
    time_horizon: str
    confidence: float
    reasoning: str
    watch_next: list[str]
    stored_event_id: int | None = None


class MarketEventOut(BaseModel):
    id: int
    title: str | None
    text: str
    source: str | None
    importance: int | None
    impact: str | None
    affected_assets: str | None
    reasoning: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
