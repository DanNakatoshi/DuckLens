###
###
###
1. Morning Check (Before 9:30 AM)
.\tasks.ps1 morning

2. Intraday Monitor (At 3 PM)
.\tasks.ps1 intraday

3. After-Hours Update (After 4 PM)
.\tasks.ps1 update-daily

.\tasks.ps1 check-data
 
# Daily update (after market close)
.\tasks.ps1 update-daily
# - Fetches latest data
# - Shows watchlist BUY/SELL signals
# - Reviews your portfolio with recommendations
# - Asks to update portfolio interactively

# Portfolio review only
.\tasks.ps1 portfolio

# Database stats with all tables
.\tasks.ps1 db-stats

# Analyze trade history
.\tasks.ps1 analyze-trades

# Watchlist signals
.\tasks.ps1 watchlist
###
###
###







# Calculate all indicators and store in DB
.\tasks.ps1 calc-indicators

# Show indicators with trading signals for SPY
.\tasks.ps1 show-indicators

# Run indicator tests
.\tasks.ps1 test-indicators

###

# Fetch 5 years of historical data (run once)
.\tasks.ps1 fetch-historical

4. New PowerShell Commands
# List all 23 available economic indicators
.\tasks.ps1 list-economic

# Fetch 5 years of economic data (backfill)
.\tasks.ps1 fetch-economic

# Run FRED collector tests
.\tasks.ps1 test-fred

# Build economic calendar from FRED data
.\tasks.ps1 build-calendar

# Daily updates (now includes economic data automatically)
.\tasks.ps1 update-daily

# View database statistics
.\tasks.ps1 db-stats


### TRY
# List all 23 available indicators
.\tasks.ps1 list-economic

# Fetch 5 years of all economic data (backfill)
.\tasks.ps1 fetch-economic

# Run tests
.\tasks.ps1 test-fred



🚀 Quick Start: OPTIONS
# Daily update with signals + portfolio + interactive updates
.\tasks.ps1 update-daily

# Portfolio review only
.\tasks.ps1 portfolio

# See all database tables
.\tasks.ps1 db-stats

# Analyze trade history
.\tasks.ps1 analyze-trades

####

python scripts/add_ticker.py COP
python scripts/add_ticker.py UPS  
python scripts/add_ticker.py CSIQ
python scripts/add_ticker.py EPSM
python scripts/add_ticker.py NEON
python scripts/add_ticker.py VXX 

####