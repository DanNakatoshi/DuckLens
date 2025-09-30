from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator
from pydantic_core.core_schema import ValidationInfo


# Polygon.io API Response Models
class PolygonTicker(BaseModel):
    """Polygon.io ticker information."""

    ticker: str
    name: str
    market: Literal["stocks", "crypto", "fx", "otc", "indices"]
    locale: Literal["us", "global"]
    primary_exchange: str | None = None
    type: str | None = None
    active: bool | None = None
    currency_name: str | None = None
    currency_symbol: str | None = None
    base_currency_name: str | None = None
    base_currency_symbol: str | None = None
    cik: str | None = None
    composite_figi: str | None = None
    share_class_figi: str | None = None
    last_updated_utc: str | None = None
    delisted_utc: str | None = None


class PolygonTickersResponse(BaseModel):
    """Response from Polygon.io tickers endpoint."""

    status: Literal["OK", "DELAYED", "ERROR", "NOT_FOUND"]
    count: int | None = None
    request_id: str | None = None
    next_url: str | None = None
    results: list[PolygonTicker] | None = None


class PolygonAggregateBar(BaseModel):
    """Single aggregate bar from Polygon.io."""

    v: int = Field(..., description="Trading volume")
    vw: Decimal | None = Field(None, description="Volume weighted average price")
    o: Decimal = Field(..., description="Open price")
    c: Decimal = Field(..., description="Close price")
    h: Decimal = Field(..., description="High price")
    l: Decimal = Field(..., description="Low price")  # noqa: E741
    t: int = Field(..., description="Timestamp (Unix ms)")
    n: int | None = Field(None, description="Number of transactions")


class PolygonAggregatesResponse(BaseModel):
    """Response from Polygon.io aggregates endpoint."""

    ticker: str
    status: Literal["OK", "DELAYED", "ERROR", "NOT_FOUND"]
    adjusted: bool
    queryCount: int | None = None
    resultsCount: int | None = None
    request_id: str | None = None
    results: list[PolygonAggregateBar] | None = None


# Internal Domain Models
class StockPrice(BaseModel):
    """Normalized stock price data model."""

    symbol: str = Field(..., min_length=1, max_length=10)
    timestamp: datetime
    open: Decimal = Field(..., gt=0)
    high: Decimal = Field(..., gt=0)
    low: Decimal = Field(..., gt=0)
    close: Decimal = Field(..., gt=0)
    volume: int = Field(..., ge=0)

    @field_validator("high")
    @classmethod
    def validate_high(cls, v: Decimal, info: ValidationInfo) -> Decimal:
        if "low" in info.data and v < info.data["low"]:
            raise ValueError("high must be >= low")
        return v

    @classmethod
    def from_polygon_bar(cls, symbol: str, bar: PolygonAggregateBar) -> "StockPrice":
        """Convert Polygon.io aggregate bar to StockPrice."""
        return cls(
            symbol=symbol,
            timestamp=datetime.fromtimestamp(bar.t / 1000),  # Convert ms to seconds
            open=bar.o,
            high=bar.h,
            low=bar.l,
            close=bar.c,
            volume=bar.v,
        )


class SentimentData(BaseModel):
    """Social media sentiment data."""

    symbol: str
    source: Literal["reddit", "twitter"]
    sentiment_score: float = Field(..., ge=-1.0, le=1.0)
    text: str
    timestamp: datetime
    author: str | None = None


class PredictionRequest(BaseModel):
    """Request model for stock prediction."""

    symbol: str
    horizon: Literal["1d", "5d", "1m"] = "1d"
    include_sentiment: bool = True


class PredictionResponse(BaseModel):
    """Response model for stock prediction."""

    symbol: str
    predicted_price: Decimal
    confidence: float = Field(..., ge=0.0, le=1.0)
    timestamp: datetime
    model_version: str
    horizon: str
