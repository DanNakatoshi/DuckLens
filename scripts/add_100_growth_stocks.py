"""Add 100 high-growth stocks to the watchlist for 10-year backtesting."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# The 100 growth stocks by category
GROWTH_STOCKS = {
    # AI & Technology (20)
    "AI_CHIPS": ["AVGO", "QCOM", "MRVL", "ARM", "ASML", "AMAT", "LRCX", "KLAC"],
    "AI_SOFTWARE": ["MSFT", "META", "CRM", "NOW", "SNOW", "PLTR", "NET"],

    # Clean Energy & EVs (15)
    "EV_MAKERS": ["RIVN", "LCID", "NIO", "LI", "XPEV"],
    "CLEAN_ENERGY": ["ENPH", "SEDG", "RUN", "FSLR", "ALB", "SQM", "PLUG"],

    # Healthcare & Biotech (15)
    "PHARMA": ["LLY", "NVO", "JNJ", "ABBV", "GILD", "REGN", "VRTX", "MRNA", "BNTX"],
    "MEDICAL_DEVICES": ["ISRG", "EW", "SYK", "BSX", "MDT"],

    # Fintech & Payments (10)
    "PAYMENTS": ["V", "MA", "PYPL", "SQ", "ADYEN"],
    "FINTECH": ["HOOD", "SOFI", "AFRM", "NU"],

    # E-Commerce & Consumer (10)
    "ECOMMERCE": ["AMZN", "SHOP", "MELI", "SE"],
    "CONSUMER": ["NKE", "LULU", "SBUX", "MCD", "CMG"],

    # Industrial & Infrastructure (8)
    "INDUSTRIAL": ["CAT", "DE", "GE", "RTX", "LMT"],
    "LOGISTICS": ["FDX", "URI"],

    # Real Estate & REITs (5)
    "REITS": ["PLD", "AMT", "EQIX", "PSA"],

    # International Growth (7)
    "CHINA": ["JD", "PDD", "BIDU"],
    "INTERNATIONAL": ["TSM", "SAP"],

    # Gaming & Entertainment (5)
    "GAMING": ["RBLX", "U", "EA", "TTWO", "NFLX"],

    # Cybersecurity & Software (5)
    "CYBERSECURITY": ["CRWD", "PANW", "ZS", "DDOG", "MDB"],
}


def main():
    """Display the stock list and instructions."""

    # Flatten all stocks
    all_stocks = []
    for category_stocks in GROWTH_STOCKS.values():
        all_stocks.extend(category_stocks)

    print("=" * 80)
    print(f"100 HIGH-GROWTH STOCKS FOR 10-YEAR BACKTEST")
    print("=" * 80)
    print(f"\nTotal stocks to add: {len(all_stocks)}")
    print(f"\nBreakdown by category:")

    for category, stocks in GROWTH_STOCKS.items():
        print(f"  {category:<20} {len(stocks):>3} stocks: {', '.join(stocks[:5])}{'...' if len(stocks) > 5 else ''}")

    print("\n" + "=" * 80)
    print("STOCK LIST (alphabetical)")
    print("=" * 80)

    for i, stock in enumerate(sorted(all_stocks), 1):
        print(f"{i:3}. {stock:<8}", end="")
        if i % 6 == 0:
            print()
    print("\n")

    # Save to file for manual addition
    output_file = Path(__file__).parent.parent / "new_stocks_list.txt"
    with open(output_file, "w") as f:
        f.write("# 100 Growth Stocks to Add\n\n")
        for category, stocks in GROWTH_STOCKS.items():
            f.write(f"\n## {category} ({len(stocks)} stocks)\n")
            for stock in stocks:
                f.write(f"{stock}\n")

    print(f"Stock list saved to: {output_file}")
    print()

    # Instructions
    print("=" * 80)
    print("HOW TO ADD THESE STOCKS")
    print("=" * 80)
    print()
    print("OPTION 1: Add to tickers.py manually")
    print("  1. Open src/config/tickers.py")
    print("  2. Add stocks to TIER_2_STOCKS list with metadata")
    print("  3. Run: .\\tasks.ps1 fetch-10-years")
    print()
    print("OPTION 2: Use the generated list")
    print("  1. Open new_stocks_list.txt")
    print("  2. Copy stocks you want")
    print("  3. Add to tickers.py TIER_2_STOCKS")
    print()
    print("OPTION 3: I'll create the full tickers.py update for you")
    print("  Let me know and I'll generate the complete TickerMetadata entries")
    print()
    print("=" * 80)
    print("RECOMMENDED APPROACH")
    print("=" * 80)
    print()
    print("Start with TOP 20 highest-conviction stocks:")
    print()

    top_20 = [
        ("MSFT", "Microsoft - AI + Cloud leader"),
        ("AMZN", "Amazon - E-commerce + AWS"),
        ("META", "Meta - AI + social media"),
        ("AVGO", "Broadcom - Networking chips"),
        ("LLY", "Eli Lilly - Obesity drugs"),
        ("TSM", "TSMC - Chip manufacturing"),
        ("V", "Visa - Payment networks"),
        ("MA", "Mastercard - Payment networks"),
        ("ISRG", "Intuitive Surgical - Robotic surgery"),
        ("ASML", "ASML - Chip equipment"),
        ("CRWD", "CrowdStrike - Cybersecurity"),
        ("NOW", "ServiceNow - Enterprise AI"),
        ("ENPH", "Enphase - Solar energy"),
        ("NVO", "Novo Nordisk - Obesity drugs"),
        ("SHOP", "Shopify - E-commerce platform"),
        ("PLTR", "Palantir - AI analytics"),
        ("NET", "Cloudflare - Edge computing"),
        ("CRM", "Salesforce - Enterprise AI"),
        ("QCOM", "Qualcomm - Mobile AI chips"),
        ("MRVL", "Marvell - Data center chips"),
    ]

    for i, (symbol, description) in enumerate(top_20, 1):
        print(f"  {i:2}. {symbol:<6} - {description}")

    print()
    print("These 20 have:")
    print("  - Strong secular trends (AI, cloud, healthcare)")
    print("  - 10+ years of data available")
    print("  - Proven revenue growth")
    print("  - Market leadership")
    print()
    print("After backtesting these 20, expand to full 100 based on results.")
    print()


if __name__ == "__main__":
    main()
