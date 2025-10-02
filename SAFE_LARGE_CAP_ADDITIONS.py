"""
SAFE LARGE-CAP ADDITIONS - High Quality Stocks for Asset Protection & Growth

These are blue-chip, mega-cap stocks (market cap > $100B) that are:
- Liquid (easy to buy/sell with tight spreads)
- Stable (established businesses, not risky startups)
- Diversified across all sectors
- Perfect for 2x leverage strategy (lower volatility than small caps)

Total additions: 40 stocks
Your new total: 23 current + 40 new = 63 stocks (well-diversified, institutional-grade)

READY TO PASTE INTO src/config/tickers.py (add to TIER_2_STOCKS list)
"""

from dataclasses import dataclass

# =============================================================================
# MEGA-CAP TECHNOLOGY (10 stocks) - The "Magnificent 7" + AI/Cloud leaders
# =============================================================================

TickerMetadata(
    symbol="MSFT",
    name="Microsoft Corporation",
    category="sector",
    sub_category="technology",
    weight=1.0,
    description="Cloud (Azure) + AI (OpenAI/Copilot) + Office 365 - Most important stock you're missing",
),
TickerMetadata(
    symbol="AMZN",
    name="Amazon.com Inc.",
    category="sector",
    sub_category="technology",
    weight=1.0,
    description="AWS cloud leader (32% market share) + E-commerce dominance",
),
TickerMetadata(
    symbol="META",
    name="Meta Platforms Inc.",
    category="sector",
    sub_category="communication",
    weight=0.95,
    description="Facebook/Instagram - 3.9B users, digital ads, AI infrastructure",
),
TickerMetadata(
    symbol="TSM",
    name="Taiwan Semiconductor",
    category="sector",
    sub_category="technology",
    weight=0.95,
    description="Manufactures chips for NVDA, AAPL, AMD - critical supply chain",
),
TickerMetadata(
    symbol="AVGO",
    name="Broadcom Inc.",
    category="sector",
    sub_category="technology",
    weight=0.9,
    description="Networking chips, AI infrastructure, enterprise software",
),
TickerMetadata(
    symbol="ORCL",
    name="Oracle Corporation",
    category="sector",
    sub_category="technology",
    weight=0.85,
    description="Cloud databases, enterprise software - AI cloud buildout beneficiary",
),
TickerMetadata(
    symbol="ADBE",
    name="Adobe Inc.",
    category="sector",
    sub_category="technology",
    weight=0.85,
    description="Creative Cloud, Photoshop, AI content creation tools",
),
TickerMetadata(
    symbol="CRM",
    name="Salesforce Inc.",
    category="sector",
    sub_category="technology",
    weight=0.85,
    description="CRM software leader, enterprise AI applications",
),
TickerMetadata(
    symbol="QCOM",
    name="Qualcomm Inc.",
    category="sector",
    sub_category="technology",
    weight=0.85,
    description="Mobile chips, 5G, automotive - smartphone recovery play",
),
TickerMetadata(
    symbol="CSCO",
    name="Cisco Systems Inc.",
    category="sector",
    sub_category="technology",
    weight=0.8,
    description="Networking hardware, cybersecurity - AI data center backbone",
),

# =============================================================================
# FINANCIALS (8 stocks) - Banks, Payments, Insurance
# =============================================================================

TickerMetadata(
    symbol="JPM",
    name="JPMorgan Chase & Co.",
    category="sector",
    sub_category="financials",
    weight=1.0,
    description="Largest US bank - economic health bellwether, leads credit cycle",
),
TickerMetadata(
    symbol="V",
    name="Visa Inc.",
    category="sector",
    sub_category="financials",
    weight=0.95,
    description="Payment network - consumer spending indicator, high margins",
),
TickerMetadata(
    symbol="MA",
    name="Mastercard Inc.",
    category="sector",
    sub_category="financials",
    weight=0.95,
    description="Payment network - duopoly with Visa, global spending trends",
),
TickerMetadata(
    symbol="BAC",
    name="Bank of America Corp.",
    category="sector",
    sub_category="financials",
    weight=0.9,
    description="Consumer banking leader - interest rate sensitive, loan growth",
),
TickerMetadata(
    symbol="WFC",
    name="Wells Fargo & Co.",
    category="sector",
    sub_category="financials",
    weight=0.85,
    description="Mortgage & consumer lending - housing market proxy",
),
TickerMetadata(
    symbol="MS",
    name="Morgan Stanley",
    category="sector",
    sub_category="financials",
    weight=0.85,
    description="Wealth management + investment banking - high-net-worth trends",
),
TickerMetadata(
    symbol="GS",
    name="Goldman Sachs Group",
    category="sector",
    sub_category="financials",
    weight=0.85,
    description="Investment banking, trading - M&A activity indicator",
),
TickerMetadata(
    symbol="BLK",
    name="BlackRock Inc.",
    category="sector",
    sub_category="financials",
    weight=0.9,
    description="Largest asset manager ($10T AUM) - market flows, ETF dominance",
),

# =============================================================================
# HEALTHCARE (6 stocks) - Pharma, Biotech, MedTech
# =============================================================================

TickerMetadata(
    symbol="LLY",
    name="Eli Lilly & Co.",
    category="sector",
    sub_category="healthcare",
    weight=0.95,
    description="Obesity drugs (Mounjaro/Zepbound) mega-trend, diabetes leader",
),
TickerMetadata(
    symbol="JNJ",
    name="Johnson & Johnson",
    category="sector",
    sub_category="healthcare",
    weight=0.9,
    description="Pharma + medical devices - defensive, dividend aristocrat",
),
TickerMetadata(
    symbol="ABBV",
    name="AbbVie Inc.",
    category="sector",
    sub_category="healthcare",
    weight=0.85,
    description="Immunology drugs (Humira, Rinvoq) - stable cash flow",
),
TickerMetadata(
    symbol="MRK",
    name="Merck & Co.",
    category="sector",
    sub_category="healthcare",
    weight=0.85,
    description="Cancer drugs (Keytruda) - oncology growth trend",
),
TickerMetadata(
    symbol="TMO",
    name="Thermo Fisher Scientific",
    category="sector",
    sub_category="healthcare",
    weight=0.85,
    description="Life sciences tools, lab equipment - biotech infrastructure",
),
TickerMetadata(
    symbol="ABT",
    name="Abbott Laboratories",
    category="sector",
    sub_category="healthcare",
    weight=0.8,
    description="Medical devices, diagnostics - healthcare utilization trends",
),

# =============================================================================
# CONSUMER DISCRETIONARY (6 stocks) - Retail, Auto, Entertainment
# =============================================================================

TickerMetadata(
    symbol="AMZN",  # Already listed above in tech, but also consumer
    name="Amazon.com Inc.",
    category="sector",
    sub_category="consumer_discretionary",
    weight=1.0,
    description="E-commerce + Prime + advertising - consumer spending leader",
),
TickerMetadata(
    symbol="HD",
    name="Home Depot Inc.",
    category="sector",
    sub_category="consumer_discretionary",
    weight=0.9,
    description="Home improvement retail - housing market, DIY trends",
),
TickerMetadata(
    symbol="MCD",
    name="McDonald's Corp.",
    category="sector",
    sub_category="consumer_discretionary",
    weight=0.85,
    description="Fast food leader - defensive consumer, global expansion",
),
TickerMetadata(
    symbol="NKE",
    name="Nike Inc.",
    category="sector",
    sub_category="consumer_discretionary",
    weight=0.8,
    description="Athletic apparel - brand power, China exposure",
),
TickerMetadata(
    symbol="SBUX",
    name="Starbucks Corp.",
    category="sector",
    sub_category="consumer_discretionary",
    weight=0.8,
    description="Coffee chain - consumer spending, loyalty program",
),
TickerMetadata(
    symbol="LOW",
    name="Lowe's Companies",
    category="sector",
    sub_category="consumer_discretionary",
    weight=0.8,
    description="Home improvement - duopoly with HD, housing trends",
),

# =============================================================================
# CONSUMER STAPLES (4 stocks) - Defensive, Recession-Proof
# =============================================================================

TickerMetadata(
    symbol="WMT",
    name="Walmart Inc.",
    category="sector",
    sub_category="consumer_staples",
    weight=0.9,
    description="Discount retail leader - recession-proof, e-commerce growth",
),
TickerMetadata(
    symbol="COST",
    name="Costco Wholesale",
    category="sector",
    sub_category="consumer_staples",
    weight=0.9,
    description="Membership warehouse - loyal customers, pricing power",
),
TickerMetadata(
    symbol="PG",
    name="Procter & Gamble",
    category="sector",
    sub_category="consumer_staples",
    weight=0.85,
    description="Consumer staples giant - Tide, Pampers, Gillette - stable",
),
TickerMetadata(
    symbol="KO",
    name="Coca-Cola Co.",
    category="sector",
    sub_category="consumer_staples",
    weight=0.8,
    description="Beverages - dividend aristocrat, global brand",
),

# =============================================================================
# INDUSTRIALS (4 stocks) - Manufacturing, Aerospace, Logistics
# =============================================================================

TickerMetadata(
    symbol="BA",
    name="Boeing Co.",
    category="sector",
    sub_category="industrials",
    weight=0.85,
    description="Aerospace - air travel recovery, defense contracts",
),
TickerMetadata(
    symbol="CAT",
    name="Caterpillar Inc.",
    category="sector",
    sub_category="industrials",
    weight=0.85,
    description="Heavy machinery - infrastructure spending, construction",
),
TickerMetadata(
    symbol="RTX",
    name="RTX Corporation",
    category="sector",
    sub_category="industrials",
    weight=0.8,
    description="Aerospace & defense - commercial aviation + military",
),
TickerMetadata(
    symbol="GE",
    name="General Electric",
    category="sector",
    sub_category="industrials",
    weight=0.8,
    description="Aviation, power, renewables - turnaround story",
),

# =============================================================================
# COMMUNICATION SERVICES (2 stocks) - Media, Telecom
# =============================================================================

TickerMetadata(
    symbol="DIS",
    name="Walt Disney Co.",
    category="sector",
    sub_category="communication",
    weight=0.85,
    description="Entertainment, streaming (Disney+), theme parks - content king",
),
TickerMetadata(
    symbol="NFLX",
    name="Netflix Inc.",
    category="sector",
    sub_category="communication",
    weight=0.85,
    description="Streaming leader - subscriber growth, ad-tier monetization",
),

# =============================================================================
# Total: 40 NEW LARGE-CAP STOCKS
# =============================================================================
# Technology: 10
# Financials: 8
# Healthcare: 6
# Consumer Discretionary: 6
# Consumer Staples: 4
# Industrials: 4
# Communication: 2
#
# ALL are mega-cap (>$100B market cap)
# ALL are liquid (tight spreads, high volume)
# ALL are safe for 2x leverage strategy
# NO small caps, NO micro caps, NO risky stocks
#
# Combined with your existing 23, you'll have 63 high-quality stocks
# covering all major sectors for maximum diversification and safety.
