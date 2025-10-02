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


class PolygonAdditionalUnderlying(BaseModel):
    """Additional underlying or deliverable for an option contract."""

    amount: float = Field(..., description="Amount of the underlying")
    type: str = Field(..., description="Type of underlying (equity, currency, etc)")
    underlying: str = Field(..., description="Symbol or identifier of the underlying")


class PolygonOptionsContract(BaseModel):
    """Single options contract from Polygon.io."""

    additional_underlyings: list[PolygonAdditionalUnderlying] | None = Field(
        None, description="Additional underlyings or deliverables"
    )
    cfi: str | None = Field(None, description="6 letter CFI code (ISO 10962)")
    contract_type: Literal["call", "put", "other"] | None = Field(
        None, description="Type of contract"
    )
    correction: int | None = Field(None, description="Correction number for this contract")
    exercise_style: Literal["american", "european", "bermudan"] | None = Field(
        None, description="Exercise style of the contract"
    )
    expiration_date: str | None = Field(None, description="Expiration date (YYYY-MM-DD)")
    primary_exchange: str | None = Field(None, description="MIC code of primary exchange")
    shares_per_contract: float | None = Field(None, description="Number of shares per contract")
    strike_price: float | None = Field(None, description="Strike price")
    ticker: str | None = Field(None, description="Options contract ticker")
    underlying_ticker: str | None = Field(None, description="Underlying ticker symbol")


class PolygonOptionsContractsResponse(BaseModel):
    """Response from Polygon.io options contracts endpoint."""

    request_id: str | None = None
    results: list[PolygonOptionsContract] | None = None
    status: Literal["OK", "DELAYED", "ERROR", "NOT_FOUND"] | None = None
    next_url: str | None = Field(None, description="URL to fetch next page of results")


class PolygonShortInterest(BaseModel):
    """Short interest data from Polygon.io."""

    ticker: str | None = Field(None, description="Stock ticker symbol")
    settlement_date: str = Field(..., description="Settlement date (YYYY-MM-DD)")
    short_interest: int | None = Field(
        None, description="Total shares sold short but not yet covered"
    )
    avg_daily_volume: int | None = Field(None, description="Average daily trading volume")
    days_to_cover: float | None = Field(
        None, description="Estimated days to cover all short positions"
    )


class PolygonShortInterestResponse(BaseModel):
    """Response from Polygon.io short interest endpoint."""

    status: Literal["OK"] | None = None
    count: int | None = None
    request_id: str | None = None
    results: list[PolygonShortInterest] | None = None
    next_url: str | None = None


class PolygonShortVolume(BaseModel):
    """Daily short volume data from Polygon.io."""

    ticker: str | None = Field(None, description="Stock ticker symbol")
    date: str = Field(..., description="Trade activity date (YYYY-MM-DD)")
    short_volume: int | None = Field(None, description="Total shares sold short across all venues")
    total_volume: int | None = Field(None, description="Total reported volume across all venues")
    short_volume_ratio: float | None = Field(
        None, description="Percentage of total volume that was sold short"
    )
    exempt_volume: int | None = Field(None, description="Short volume exempt from regulation SHO")
    non_exempt_volume: int | None = Field(
        None, description="Short volume not exempt from regulation SHO"
    )
    # Exchange-specific volumes
    adf_short_volume: int | None = None
    adf_short_volume_exempt: int | None = None
    nasdaq_carteret_short_volume: int | None = None
    nasdaq_carteret_short_volume_exempt: int | None = None
    nasdaq_chicago_short_volume: int | None = None
    nasdaq_chicago_short_volume_exempt: int | None = None
    nyse_short_volume: int | None = None
    nyse_short_volume_exempt: int | None = None


class PolygonShortVolumeResponse(BaseModel):
    """Response from Polygon.io short volume endpoint."""

    status: Literal["OK"] | None = None
    count: int | None = None
    request_id: str | None = None
    results: list[PolygonShortVolume] | None = None
    next_url: str | None = None


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


# FRED (Federal Reserve Economic Data) Models
class FREDObservation(BaseModel):
    """Single observation from FRED API."""

    realtime_start: str
    realtime_end: str
    date: str
    value: str  # FRED returns "." for missing values


class FREDSeriesResponse(BaseModel):
    """Response from FRED API series observations endpoint."""

    realtime_start: str
    realtime_end: str
    observation_start: str
    observation_end: str
    units: str
    output_type: int
    file_type: str
    order_by: str
    sort_order: str
    count: int
    offset: int
    limit: int
    observations: list[FREDObservation]


class EconomicIndicator(BaseModel):
    """Normalized economic indicator data model."""

    series_id: str = Field(..., description="FRED series ID (e.g., 'FEDFUNDS', 'CPIAUCSL')")
    indicator_name: str = Field(..., description="Human-readable indicator name")
    date: datetime
    value: Decimal | None = Field(None, description="Indicator value (None if missing)")
    units: str | None = Field(None, description="Units of measurement")

    @classmethod
    def from_fred_observation(
        cls,
        series_id: str,
        indicator_name: str,
        obs: FREDObservation,
        units: str | None = None,
    ) -> "EconomicIndicator":
        """Convert FRED observation to EconomicIndicator."""
        # FRED uses "." for missing values
        value = None if obs.value == "." else Decimal(obs.value)

        return cls(
            series_id=series_id,
            indicator_name=indicator_name,
            date=datetime.strptime(obs.date, "%Y-%m-%d"),
            value=value,
            units=units,
        )


class EconomicCalendarEvent(BaseModel):
    """Economic calendar event (CPI release, FOMC meeting, NFP, etc.)."""

    event_id: str = Field(..., description="Unique event ID")
    event_type: Literal[
        "CPI",
        "PPI",
        "NFP",
        "FOMC",
        "GDP",
        "PCE",
        "RETAIL_SALES",
        "JOBLESS_CLAIMS",
        "HOUSING_STARTS",
        "ISM_MANUFACTURING",
        "ISM_SERVICES",
        "CONSUMER_SENTIMENT",
    ] = Field(..., description="Type of economic event")
    event_name: str = Field(..., description="Human-readable event name")
    release_date: datetime = Field(..., description="Date/time of event or data release")
    actual_value: Decimal | None = Field(None, description="Actual value reported")
    forecast_value: Decimal | None = Field(None, description="Consensus forecast")
    previous_value: Decimal | None = Field(None, description="Previous period value")
    surprise: Decimal | None = Field(None, description="Surprise factor (actual - forecast)")
    impact: Literal["high", "medium", "low"] = Field(..., description="Market impact level")
    description: str | None = Field(None, description="Event description")

    @classmethod
    def from_fred_data(
        cls,
        event_type: str,
        event_name: str,
        release_date: datetime,
        actual_value: Decimal | None = None,
        impact: str = "high",
    ) -> "EconomicCalendarEvent":
        """Create calendar event from FRED data."""
        event_id = f"{event_type}_{release_date.strftime('%Y%m%d')}"
        return cls(
            event_id=event_id,
            event_type=event_type,
            event_name=event_name,
            release_date=release_date,
            actual_value=actual_value,
            forecast_value=None,
            previous_value=None,
            surprise=None,
            impact=impact,
            description=None,
        )


# Options Flow Models
class OptionsChainContract(BaseModel):
    """Single options contract from chain snapshot."""

    ticker: str = Field(..., description="Contract ticker (e.g., O:SPY251219C00650000)")
    underlying_ticker: str = Field(..., description="Underlying asset ticker")
    strike_price: Decimal = Field(..., description="Strike price")
    expiration_date: datetime = Field(..., description="Contract expiration date")
    contract_type: Literal["call", "put"] = Field(..., description="Call or Put")

    # Pricing & Volume
    last_price: Decimal | None = Field(None, description="Last trade price")
    volume: int | None = Field(None, description="Daily volume")
    open_interest: int | None = Field(None, description="Open interest")

    # Greeks
    delta: Decimal | None = Field(None, description="Delta")
    gamma: Decimal | None = Field(None, description="Gamma")
    theta: Decimal | None = Field(None, description="Theta")
    vega: Decimal | None = Field(None, description="Vega")

    # Volatility & Quotes
    implied_volatility: Decimal | None = Field(None, description="Implied volatility")
    bid: Decimal | None = Field(None, description="Bid price")
    ask: Decimal | None = Field(None, description="Ask price")
    bid_size: int | None = Field(None, description="Bid size")
    ask_size: int | None = Field(None, description="Ask size")

    # Metadata
    break_even_price: Decimal | None = Field(None, description="Break even price")
    snapshot_time: datetime = Field(..., description="Time of snapshot")


class OptionsFlowDaily(BaseModel):
    """Daily aggregated options flow metrics for a ticker."""

    ticker: str = Field(..., description="Underlying ticker symbol")
    date: datetime = Field(..., description="Date of flow data")

    # Volume metrics
    total_call_volume: int = Field(..., description="Total call volume")
    total_put_volume: int = Field(..., description="Total put volume")
    put_call_ratio: Decimal = Field(..., description="Put/Call volume ratio")

    # Open Interest
    total_call_oi: int = Field(..., description="Total call open interest")
    total_put_oi: int = Field(..., description="Total put open interest")
    call_oi_change: int = Field(0, description="Call OI change from previous day")
    put_oi_change: int = Field(0, description="Put OI change from previous day")

    # Volatility
    avg_call_iv: Decimal | None = Field(None, description="Average call IV")
    avg_put_iv: Decimal | None = Field(None, description="Average put IV")
    iv_rank: Decimal | None = Field(None, description="IV rank (0-100)")

    # Greeks (net exposure)
    net_delta: Decimal | None = Field(None, description="Net delta exposure")
    net_gamma: Decimal | None = Field(None, description="Net gamma exposure")
    net_theta: Decimal | None = Field(None, description="Net theta exposure")
    net_vega: Decimal | None = Field(None, description="Net vega exposure")

    # Unusual Activity
    unusual_call_contracts: int = Field(0, description="Calls with unusual volume")
    unusual_put_contracts: int = Field(0, description="Puts with unusual volume")

    # Smart Money Indicators
    call_volume_at_ask: int = Field(0, description="Call volume executed at ask (bullish)")
    put_volume_at_ask: int = Field(0, description="Put volume executed at ask (bearish)")

    # Max Pain
    max_pain_price: Decimal | None = Field(
        None, description="Price where most options expire worthless"
    )


class OptionsFlowIndicators(BaseModel):
    """Derived options flow indicators for ML feature engineering."""

    ticker: str
    date: datetime

    # Sentiment Indicators (CatBoost features)
    put_call_ratio: Decimal = Field(..., description="P/C ratio: >1 bearish, <1 bullish")
    put_call_ratio_ma5: Decimal | None = Field(None, description="5-day MA of P/C ratio")
    put_call_ratio_percentile: Decimal | None = Field(
        None, description="P/C ratio percentile (0-100)"
    )

    # Smart Money Flow
    smart_money_index: Decimal | None = Field(
        None, description="(Call@Ask - Put@Ask) / Total Volume"
    )
    oi_momentum: Decimal | None = Field(
        None, description="(Today OI - Yesterday OI) / Yesterday OI"
    )
    unusual_activity_score: Decimal = Field(0, description="Count of unusual volume contracts")

    # Volatility Features
    iv_rank: Decimal | None = Field(None, description="IV rank vs 52-week range")
    iv_skew: Decimal | None = Field(None, description="Put IV - Call IV (fear gauge)")

    # Directional Bias
    delta_weighted_volume: Decimal | None = Field(
        None, description="Sum(delta * volume) - directional exposure"
    )
    gamma_exposure: Decimal | None = Field(None, description="Total gamma risk")

    # Support/Resistance
    max_pain_distance: Decimal | None = Field(
        None, description="(Current Price - Max Pain) / Current Price"
    )
    high_oi_call_strike: Decimal | None = Field(None, description="Call strike with highest OI")
    high_oi_put_strike: Decimal | None = Field(None, description="Put strike with highest OI")

    # Time-based features
    days_to_nearest_expiry: int | None = Field(None, description="Days to nearest contract expiry")

    # Trend signals for CatBoost
    flow_signal: Literal["BULLISH", "BEARISH", "NEUTRAL"] = Field(
        ..., description="Overall options flow signal"
    )
