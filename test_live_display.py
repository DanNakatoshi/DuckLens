"""Test the live display format."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from scripts.market_check import build_live_sections, MarketStatus
from src.data.storage.market_data_db import MarketDataDB
from src.models.enhanced_detector import EnhancedTrendDetector
from src.portfolio.portfolio_manager import PortfolioManager
from rich.console import Console

console = Console()

# Initialize
db = MarketDataDB()
detector = EnhancedTrendDetector(db=db, min_confidence=0.75, confirmation_days=1, long_only=True)
portfolio_manager = PortfolioManager()
portfolio = portfolio_manager.load_portfolio()
market_status = MarketStatus.get_status()

# Build and display live sections
live_content, signals = build_live_sections(db, market_status, detector, portfolio)
console.print(live_content)

db.close()
