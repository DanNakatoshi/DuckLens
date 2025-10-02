"""Ticker configuration with metadata for feature engineering."""

from dataclasses import dataclass
from typing import Literal


@dataclass
class TickerMetadata:
    """Metadata for a ticker symbol."""

    symbol: str
    name: str
    category: Literal[
        "market_index",
        "sector",
        "volatility",
        "inverse",
        "safe_haven",
        "credit",
        "crypto",
        "currency",
        "commodity",
        "international",
    ]
    sub_category: str
    weight: float  # Importance for prediction (0-1)
    inverse: bool = False  # True for inverse/short ETFs
    description: str = ""


# Tier 1: Essential tickers for market prediction
TIER_1_TICKERS = [
    # ========== MARKET INDICES (5) ==========
    TickerMetadata(
        symbol="SPY",
        name="S&P 500 ETF",
        category="market_index",
        sub_category="large_cap",
        weight=1.0,
        description="Primary market benchmark - 500 largest US companies",
    ),
    TickerMetadata(
        symbol="QQQ",
        name="NASDAQ 100 ETF",
        category="market_index",
        sub_category="tech_heavy",
        weight=0.95,
        description="Tech-heavy index - innovation & growth",
    ),
    TickerMetadata(
        symbol="DIA",
        name="Dow Jones ETF",
        category="market_index",
        sub_category="blue_chip",
        weight=0.8,
        description="30 blue-chip industrial companies",
    ),
    TickerMetadata(
        symbol="IWM",
        name="Russell 2000 ETF",
        category="market_index",
        sub_category="small_cap",
        weight=0.85,
        description="Small cap index - economic health indicator",
    ),
    TickerMetadata(
        symbol="VTI",
        name="Total Stock Market ETF",
        category="market_index",
        sub_category="total_market",
        weight=0.9,
        description="Entire US stock market coverage",
    ),
    # ========== SECTOR ETFS (11) ==========
    TickerMetadata(
        symbol="XLF",
        name="Financial Select Sector",
        category="sector",
        sub_category="financials",
        weight=0.85,
        description="Banks, insurance - credit cycle indicator",
    ),
    TickerMetadata(
        symbol="XLE",
        name="Energy Select Sector",
        category="sector",
        sub_category="energy",
        weight=0.8,
        description="Oil & gas - inflation & geopolitical indicator",
    ),
    TickerMetadata(
        symbol="XLK",
        name="Technology Select Sector",
        category="sector",
        sub_category="technology",
        weight=0.95,
        description="Tech companies - innovation & growth leader",
    ),
    TickerMetadata(
        symbol="XLV",
        name="Health Care Select Sector",
        category="sector",
        sub_category="healthcare",
        weight=0.75,
        description="Healthcare - defensive growth sector",
    ),
    TickerMetadata(
        symbol="XLI",
        name="Industrial Select Sector",
        category="sector",
        sub_category="industrials",
        weight=0.8,
        description="Manufacturing - economic activity indicator",
    ),
    TickerMetadata(
        symbol="XLP",
        name="Consumer Staples Select Sector",
        category="sector",
        sub_category="consumer_staples",
        weight=0.7,
        description="Essential goods - defensive sector",
    ),
    TickerMetadata(
        symbol="XLY",
        name="Consumer Discretionary Select Sector",
        category="sector",
        sub_category="consumer_discretionary",
        weight=0.85,
        description="Non-essential goods - consumer confidence indicator",
    ),
    TickerMetadata(
        symbol="XLU",
        name="Utilities Select Sector",
        category="sector",
        sub_category="utilities",
        weight=0.65,
        description="Utilities - defensive flight-to-safety sector",
    ),
    TickerMetadata(
        symbol="XLB",
        name="Materials Select Sector",
        category="sector",
        sub_category="materials",
        weight=0.75,
        description="Basic materials - economic growth indicator",
    ),
    TickerMetadata(
        symbol="XLRE",
        name="Real Estate Select Sector",
        category="sector",
        sub_category="real_estate",
        weight=0.7,
        description="Real estate - interest rate sensitive",
    ),
    TickerMetadata(
        symbol="XLC",
        name="Communication Services Select Sector",
        category="sector",
        sub_category="communication",
        weight=0.75,
        description="Telecom & media - tech-adjacent sector",
    ),
    # ========== VOLATILITY / FEAR (3) ==========
    TickerMetadata(
        symbol="VIX",
        name="CBOE Volatility Index",
        category="volatility",
        sub_category="fear_gauge",
        weight=1.0,
        description="THE fear gauge - VIX > 30 = high fear, < 15 = complacency",
    ),
    TickerMetadata(
        symbol="UVXY",
        name="2x VIX Short-Term Futures",
        category="volatility",
        sub_category="fear_leveraged",
        weight=0.85,
        description="Leveraged volatility - extreme fear indicator",
    ),
    TickerMetadata(
        symbol="SVXY",
        name="Short VIX ETF",
        category="volatility",
        sub_category="fear_inverse",
        weight=0.8,
        inverse=True,
        description="Inverse VIX - bets on low volatility",
    ),
    TickerMetadata(
        symbol="VXX",
        name="VIX Short-Term Futures ETN",
        category="volatility",
        sub_category="fear_tradeable",
        weight=0.9,
        description="Tradeable VIX - use for crash protection hedge",
    ),
    # ========== BEAR / INVERSE ETFS (2) ==========
    TickerMetadata(
        symbol="SQQQ",
        name="3x Inverse NASDAQ",
        category="inverse",
        sub_category="tech_bear",
        weight=0.85,
        inverse=True,
        description="3x short NASDAQ - bearish tech positioning",
    ),
    TickerMetadata(
        symbol="SH",
        name="Inverse S&P 500",
        category="inverse",
        sub_category="market_bear",
        weight=0.8,
        inverse=True,
        description="Short S&P 500 - bearish market positioning",
    ),
    # ========== SAFE HAVEN (3) ==========
    TickerMetadata(
        symbol="GLD",
        name="Gold ETF",
        category="safe_haven",
        sub_category="gold",
        weight=0.95,
        description="Gold - ultimate safe haven & inflation hedge",
    ),
    TickerMetadata(
        symbol="TLT",
        name="20+ Year Treasury Bonds",
        category="safe_haven",
        sub_category="bonds_long",
        weight=1.0,
        description="Long-term bonds - flight to safety & rate expectations",
    ),
    TickerMetadata(
        symbol="HYG",
        name="High Yield Corporate Bonds",
        category="credit",
        sub_category="junk_bonds",
        weight=1.0,
        description="Junk bonds - credit stress & recession predictor",
    ),
    # ========== CREDIT & INFLATION (2) ==========
    TickerMetadata(
        symbol="LQD",
        name="Investment Grade Corporate Bonds",
        category="credit",
        sub_category="investment_grade",
        weight=0.9,
        description="IG bonds - credit quality & risk premium",
    ),
    TickerMetadata(
        symbol="TIP",
        name="Treasury Inflation-Protected",
        category="safe_haven",
        sub_category="inflation_protected",
        weight=0.85,
        description="TIPS - inflation expectations",
    ),
    # ========== CRYPTO (2) ==========
    TickerMetadata(
        symbol="BITO",
        name="Bitcoin Strategy ETF",
        category="crypto",
        sub_category="bitcoin",
        weight=0.75,
        description="Bitcoin exposure - risk appetite & tech sentiment",
    ),
    TickerMetadata(
        symbol="COIN",
        name="Coinbase Stock",
        category="crypto",
        sub_category="crypto_exchange",
        weight=0.7,
        description="Crypto exchange - crypto market health proxy",
    ),
    # ========== CURRENCY (1) ==========
    TickerMetadata(
        symbol="UUP",
        name="US Dollar Index ETF",
        category="currency",
        sub_category="dollar_strength",
        weight=0.9,
        description="Dollar strength - impacts exports & global markets",
    ),
    # ========== COMMODITIES (1) ==========
    TickerMetadata(
        symbol="USO",
        name="US Oil Fund",
        category="commodity",
        sub_category="oil",
        weight=0.85,
        description="Oil prices - inflation & economic activity",
    ),
    # ========== INTERNATIONAL (2) ==========
    TickerMetadata(
        symbol="EFA",
        name="EAFE (Developed Markets ex-US)",
        category="international",
        sub_category="developed_markets",
        weight=0.75,
        description="Developed international markets - global risk",
    ),
    TickerMetadata(
        symbol="EEM",
        name="Emerging Markets",
        category="international",
        sub_category="emerging_markets",
        weight=0.8,
        description="Emerging markets - global growth & risk appetite",
    ),
]

# Tier 2: Individual stocks for focused trading
TIER_2_STOCKS = [
    TickerMetadata(
        symbol="AAPL",
        name="Apple Inc.",
        category="sector",
        sub_category="technology",
        weight=1.0,
        description="Most liquid stock - tech mega cap, iPhone ecosystem",
    ),
    TickerMetadata(
        symbol="NVDA",
        name="NVIDIA Corporation",
        category="sector",
        sub_category="technology",
        weight=1.0,
        description="AI & GPU leader - high growth semiconductor",
    ),
    TickerMetadata(
        symbol="BABA",
        name="Alibaba Group",
        category="sector",
        sub_category="technology",
        weight=0.9,
        description="Chinese e-commerce giant - international exposure",
    ),
    TickerMetadata(
        symbol="INTC",
        name="Intel Corporation",
        category="sector",
        sub_category="technology",
        weight=0.85,
        description="Legacy semiconductor - value play in chips",
    ),
    TickerMetadata(
        symbol="IREN",
        name="Iris Energy",
        category="crypto",
        sub_category="crypto_mining",
        weight=0.75,
        description="Bitcoin mining - crypto exposure via equities",
    ),
    TickerMetadata(
        symbol="OPEN",
        name="Opendoor Technologies",
        category="sector",
        sub_category="real_estate",
        weight=0.7,
        description="Real estate tech - housing market proxy",
    ),
    TickerMetadata(
        symbol="UNH",
        name="UnitedHealth Group",
        category="sector",
        sub_category="healthcare",
        weight=0.95,
        description="Healthcare leader - defensive growth, strong trends",
    ),
    TickerMetadata(
        symbol="GOOGL",
        name="Alphabet Inc.",
        category="sector",
        sub_category="technology",
        weight=1.0,
        description="Google parent - search, cloud, AI leader",
    ),
    TickerMetadata(
        symbol="BE",
        name="Bloom Energy",
        category="sector",
        sub_category="energy",
        weight=0.7,
        description="Fuel cell technology - clean energy play",
    ),
    TickerMetadata(
        symbol="NEE",
        name="NextEra Energy",
        category="sector",
        sub_category="utilities",
        weight=0.85,
        description="Renewable energy utility - clean energy leader",
    ),
    TickerMetadata(
        symbol="WDC",
        name="Western Digital",
        category="sector",
        sub_category="technology",
        weight=0.75,
        description="Data storage - hard drives and SSDs",
    ),
    TickerMetadata(
        symbol="MU",
        name="Micron Technology",
        category="sector",
        sub_category="technology",
        weight=0.9,
        description="Memory chips - DRAM and NAND flash",
    ),
    TickerMetadata(
        symbol="AMD",
        name="Advanced Micro Devices",
        category="sector",
        sub_category="technology",
        weight=1.0,
        description="CPUs and GPUs - NVDA competitor",
    ),
    TickerMetadata(
        symbol="ENB",
        name="Enbridge Inc.",
        category="sector",
        sub_category="energy",
        weight=0.8,
        description="Canadian energy infrastructure - oil & gas pipelines",
    ),
    TickerMetadata(
        symbol="ELV",
        name="Elevance Health",
        category="sector",
        sub_category="healthcare",
        weight=0.9,
        description="Healthcare insurance - formerly Anthem",
    ),
    TickerMetadata(
        symbol="TSLA",
        name="Tesla Inc.",
        category="sector",
        sub_category="consumer_discretionary",
        weight=1.0,
        description="EV leader - high volatility growth stock",
    ),
    TickerMetadata(
        symbol="COP",
        name="ConocoPhillips",
        category="sector",
        sub_category="energy",
        weight=0.85,
        description="Oil & gas exploration - energy sector play",
    ),
    TickerMetadata(
        symbol="UPS",
        name="United Parcel Service",
        category="sector",
        sub_category="industrials",
        weight=0.8,
        description="Package delivery - logistics leader",
    ),
    TickerMetadata(
        symbol="BTC",
        name="Grayscale Bitcoin Trust",
        category="crypto",
        sub_category="bitcoin_trust",
        weight=0.8,
        description="Bitcoin exposure via trust (GBTC alternative)",
    ),
    TickerMetadata(
        symbol="ETH",
        name="Grayscale Ethereum Trust",
        category="crypto",
        sub_category="ethereum_trust",
        weight=0.75,
        description="Ethereum exposure via trust",
    ),
    TickerMetadata(
        symbol="CSIQ",
        name="Canadian Solar",
        category="sector",
        sub_category="energy",
        weight=0.7,
        description="Solar panel manufacturer - renewable energy",
    ),
    TickerMetadata(
        symbol="EPSM",
        name="Epsilon Energy",
        category="sector",
        sub_category="energy",
        weight=0.65,
        description="Small cap oil & gas - high risk",
    ),
    TickerMetadata(
        symbol="NEON",
        name="Neonode Inc.",
        category="sector",
        sub_category="technology",
        weight=0.6,
        description="Touch sensor technology - small cap tech",
    ),
    # ========== MEGA-CAP ADDITIONS - Safe Large Caps for Asset Protection ==========
    # Technology Giants (10 stocks)
    TickerMetadata(
        symbol="MSFT",
        name="Microsoft Corporation",
        category="sector",
        sub_category="technology",
        weight=1.0,
        description="Cloud (Azure) + AI (OpenAI/Copilot) + Office 365",
    ),
    TickerMetadata(
        symbol="AMZN",
        name="Amazon.com Inc.",
        category="sector",
        sub_category="technology",
        weight=1.0,
        description="AWS cloud leader + E-commerce dominance",
    ),
    TickerMetadata(
        symbol="META",
        name="Meta Platforms Inc.",
        category="sector",
        sub_category="communication",
        weight=0.95,
        description="Facebook/Instagram - 3.9B users, digital ads, AI",
    ),
    TickerMetadata(
        symbol="TSM",
        name="Taiwan Semiconductor",
        category="sector",
        sub_category="technology",
        weight=0.95,
        description="Chip manufacturing for NVDA, AAPL, AMD",
    ),
    TickerMetadata(
        symbol="AVGO",
        name="Broadcom Inc.",
        category="sector",
        sub_category="technology",
        weight=0.9,
        description="Networking chips, AI infrastructure",
    ),
    TickerMetadata(
        symbol="ORCL",
        name="Oracle Corporation",
        category="sector",
        sub_category="technology",
        weight=0.85,
        description="Cloud databases, AI cloud buildout",
    ),
    TickerMetadata(
        symbol="ADBE",
        name="Adobe Inc.",
        category="sector",
        sub_category="technology",
        weight=0.85,
        description="Creative Cloud, AI content creation",
    ),
    TickerMetadata(
        symbol="CRM",
        name="Salesforce Inc.",
        category="sector",
        sub_category="technology",
        weight=0.85,
        description="CRM software, enterprise AI",
    ),
    TickerMetadata(
        symbol="QCOM",
        name="Qualcomm Inc.",
        category="sector",
        sub_category="technology",
        weight=0.85,
        description="Mobile chips, 5G, automotive",
    ),
    TickerMetadata(
        symbol="CSCO",
        name="Cisco Systems Inc.",
        category="sector",
        sub_category="technology",
        weight=0.8,
        description="Networking, AI data center backbone",
    ),
    # Financials (8 stocks)
    TickerMetadata(
        symbol="JPM",
        name="JPMorgan Chase & Co.",
        category="sector",
        sub_category="financials",
        weight=1.0,
        description="Largest US bank, economic bellwether",
    ),
    TickerMetadata(
        symbol="V",
        name="Visa Inc.",
        category="sector",
        sub_category="financials",
        weight=0.95,
        description="Payment network, consumer spending indicator",
    ),
    TickerMetadata(
        symbol="MA",
        name="Mastercard Inc.",
        category="sector",
        sub_category="financials",
        weight=0.95,
        description="Payment network, global spending trends",
    ),
    TickerMetadata(
        symbol="BAC",
        name="Bank of America Corp.",
        category="sector",
        sub_category="financials",
        weight=0.9,
        description="Consumer banking, interest rate sensitive",
    ),
    TickerMetadata(
        symbol="WFC",
        name="Wells Fargo & Co.",
        category="sector",
        sub_category="financials",
        weight=0.85,
        description="Mortgage & consumer lending",
    ),
    TickerMetadata(
        symbol="MS",
        name="Morgan Stanley",
        category="sector",
        sub_category="financials",
        weight=0.85,
        description="Wealth management, investment banking",
    ),
    TickerMetadata(
        symbol="GS",
        name="Goldman Sachs Group",
        category="sector",
        sub_category="financials",
        weight=0.85,
        description="Investment banking, M&A indicator",
    ),
    TickerMetadata(
        symbol="BLK",
        name="BlackRock Inc.",
        category="sector",
        sub_category="financials",
        weight=0.9,
        description="Largest asset manager ($10T AUM)",
    ),
    # Healthcare (6 stocks)
    TickerMetadata(
        symbol="LLY",
        name="Eli Lilly & Co.",
        category="sector",
        sub_category="healthcare",
        weight=0.95,
        description="Obesity drugs mega-trend, diabetes leader",
    ),
    TickerMetadata(
        symbol="JNJ",
        name="Johnson & Johnson",
        category="sector",
        sub_category="healthcare",
        weight=0.9,
        description="Pharma + medical devices, dividend aristocrat",
    ),
    TickerMetadata(
        symbol="ABBV",
        name="AbbVie Inc.",
        category="sector",
        sub_category="healthcare",
        weight=0.85,
        description="Immunology drugs, stable cash flow",
    ),
    TickerMetadata(
        symbol="MRK",
        name="Merck & Co.",
        category="sector",
        sub_category="healthcare",
        weight=0.85,
        description="Cancer drugs (Keytruda), oncology growth",
    ),
    TickerMetadata(
        symbol="TMO",
        name="Thermo Fisher Scientific",
        category="sector",
        sub_category="healthcare",
        weight=0.85,
        description="Life sciences tools, biotech infrastructure",
    ),
    TickerMetadata(
        symbol="ABT",
        name="Abbott Laboratories",
        category="sector",
        sub_category="healthcare",
        weight=0.8,
        description="Medical devices, diagnostics",
    ),
    # Consumer Discretionary (5 stocks)
    TickerMetadata(
        symbol="HD",
        name="Home Depot Inc.",
        category="sector",
        sub_category="consumer_discretionary",
        weight=0.9,
        description="Home improvement, housing market proxy",
    ),
    TickerMetadata(
        symbol="MCD",
        name="McDonald's Corp.",
        category="sector",
        sub_category="consumer_discretionary",
        weight=0.85,
        description="Fast food leader, defensive consumer",
    ),
    TickerMetadata(
        symbol="NKE",
        name="Nike Inc.",
        category="sector",
        sub_category="consumer_discretionary",
        weight=0.8,
        description="Athletic apparel, brand power",
    ),
    TickerMetadata(
        symbol="SBUX",
        name="Starbucks Corp.",
        category="sector",
        sub_category="consumer_discretionary",
        weight=0.8,
        description="Coffee chain, consumer spending indicator",
    ),
    TickerMetadata(
        symbol="LOW",
        name="Lowe's Companies",
        category="sector",
        sub_category="consumer_discretionary",
        weight=0.8,
        description="Home improvement, housing trends",
    ),
    # Consumer Staples (4 stocks)
    TickerMetadata(
        symbol="WMT",
        name="Walmart Inc.",
        category="sector",
        sub_category="consumer_staples",
        weight=0.9,
        description="Discount retail, recession-proof",
    ),
    TickerMetadata(
        symbol="COST",
        name="Costco Wholesale",
        category="sector",
        sub_category="consumer_staples",
        weight=0.9,
        description="Membership warehouse, pricing power",
    ),
    TickerMetadata(
        symbol="PG",
        name="Procter & Gamble",
        category="sector",
        sub_category="consumer_staples",
        weight=0.85,
        description="Consumer staples giant, stable dividends",
    ),
    TickerMetadata(
        symbol="KO",
        name="Coca-Cola Co.",
        category="sector",
        sub_category="consumer_staples",
        weight=0.8,
        description="Beverages, dividend aristocrat",
    ),
    # Industrials (4 stocks)
    TickerMetadata(
        symbol="BA",
        name="Boeing Co.",
        category="sector",
        sub_category="industrials",
        weight=0.85,
        description="Aerospace, air travel recovery",
    ),
    TickerMetadata(
        symbol="CAT",
        name="Caterpillar Inc.",
        category="sector",
        sub_category="industrials",
        weight=0.85,
        description="Heavy machinery, infrastructure spending",
    ),
    TickerMetadata(
        symbol="RTX",
        name="RTX Corporation",
        category="sector",
        sub_category="industrials",
        weight=0.8,
        description="Aerospace & defense",
    ),
    TickerMetadata(
        symbol="GE",
        name="General Electric",
        category="sector",
        sub_category="industrials",
        weight=0.8,
        description="Aviation, power, renewables turnaround",
    ),
    # Communication Services (2 stocks)
    TickerMetadata(
        symbol="DIS",
        name="Walt Disney Co.",
        category="sector",
        sub_category="communication",
        weight=0.85,
        description="Entertainment, streaming, theme parks",
    ),
    TickerMetadata(
        symbol="NFLX",
        name="Netflix Inc.",
        category="sector",
        sub_category="communication",
        weight=0.85,
        description="Streaming leader, subscriber growth",
    ),
]

# Tier 3: Crypto (NOTE: BTC and ETH may not be available on Polygon as stock tickers)
# Use crypto proxies: BITO (Bitcoin ETF), COIN (Coinbase), MARA/RIOT (miners)
TIER_3_CRYPTO_PROXIES = [
    TickerMetadata(
        symbol="MARA",
        name="Marathon Digital",
        category="crypto",
        sub_category="crypto_mining",
        weight=0.8,
        description="Bitcoin mining - high beta crypto play",
    ),
    TickerMetadata(
        symbol="RIOT",
        name="Riot Platforms",
        category="crypto",
        sub_category="crypto_mining",
        weight=0.8,
        description="Bitcoin mining - crypto exposure",
    ),
]

# Create lookup dictionaries
ALL_TICKERS = TIER_1_TICKERS + TIER_2_STOCKS + TIER_3_CRYPTO_PROXIES
TICKER_SYMBOLS = [t.symbol for t in ALL_TICKERS]
TICKER_METADATA_MAP = {t.symbol: t for t in ALL_TICKERS}
STOCK_SYMBOLS = [t.symbol for t in TIER_2_STOCKS]
CRYPTO_PROXY_SYMBOLS = [t.symbol for t in TIER_3_CRYPTO_PROXIES]
TRADING_WATCHLIST = [t.symbol for t in TIER_2_STOCKS + TIER_3_CRYPTO_PROXIES]  # All tradeable stocks


def get_tickers_by_category(
    category: str,
) -> list[TickerMetadata]:
    """Get all tickers in a category."""
    return [t for t in ALL_TICKERS if t.category == category]


def get_tickers_by_weight(min_weight: float = 0.0) -> list[TickerMetadata]:
    """Get tickers with weight >= min_weight."""
    return [t for t in ALL_TICKERS if t.weight >= min_weight]


def get_high_importance_tickers() -> list[str]:
    """Get symbols of high importance tickers (weight >= 0.9)."""
    return [t.symbol for t in ALL_TICKERS if t.weight >= 0.9]


def get_inverse_tickers() -> list[str]:
    """Get inverse/short ETF symbols."""
    return [t.symbol for t in ALL_TICKERS if t.inverse]


def print_ticker_summary():
    """Print summary of ticker configuration."""
    from collections import Counter

    print("\n" + "=" * 70)
    print("TICKER CONFIGURATION SUMMARY")
    print("=" * 70)

    print(f"\nTotal Tickers: {len(ALL_TICKERS)}")
    print(f"  - ETFs (Tier 1): {len(TIER_1_TICKERS)}")
    print(f"  - Stocks (Tier 2): {len(TIER_2_STOCKS)}")

    # By category
    categories = Counter(t.category for t in ALL_TICKERS)
    print("\nBy Category:")
    for cat, count in categories.most_common():
        print(f"  {cat:20s}: {count:2d} tickers")

    # Stocks
    if TIER_2_STOCKS:
        print(f"\nIndividual Stocks: {len(TIER_2_STOCKS)} tickers")
        print(f"  {', '.join([t.symbol for t in TIER_2_STOCKS])}")

    # High importance
    high_imp = get_high_importance_tickers()
    print(f"\nHigh Importance (≥0.9): {len(high_imp)} tickers")
    print(f"  {', '.join(high_imp)}")

    # Inverse tickers
    inverse = get_inverse_tickers()
    print(f"\nInverse/Short ETFs: {len(inverse)} tickers")
    print(f"  {', '.join(inverse)}")

    print("\n" + "=" * 70 + "\n")


# Feature engineering helpers for CatBoost
def get_category_features() -> dict[str, list[str]]:
    """Get ticker symbols grouped by category for feature engineering."""
    from collections import defaultdict

    features = defaultdict(list)
    for ticker in ALL_TICKERS:
        features[ticker.category].append(ticker.symbol)
    return dict(features)


def get_weight_map() -> dict[str, float]:
    """Get ticker symbol to weight mapping."""
    return {t.symbol: t.weight for t in ALL_TICKERS}


if __name__ == "__main__":
    print_ticker_summary()
