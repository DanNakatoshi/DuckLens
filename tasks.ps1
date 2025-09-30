# DuckLens Development Tasks
# Run with: .\tasks.ps1 <command>

param(
    [Parameter(Position=0)]
    [ValidateSet("test", "lint", "format", "type-check", "all", "install")]
    [string]$Command = "all"
)

# Create alias for Poetry if needed
if (-not (Get-Command poetry -ErrorAction SilentlyContinue)) {
    Set-Alias -Name poetry -Value "$env:APPDATA\Python\Python311\Scripts\poetry.exe"
}

function Run-Tests {
    Write-Host "`n=== Running Tests ===" -ForegroundColor Cyan
    poetry run pytest tests/ -v --cov=src --cov-report=term-missing
}

function Run-Lint {
    Write-Host "`n=== Running Ruff Linter ===" -ForegroundColor Cyan
    poetry run ruff check src/ tests/
}

function Run-Format {
    Write-Host "`n=== Formatting Code with Black ===" -ForegroundColor Cyan
    poetry run black src/ tests/
}

function Run-TypeCheck {
    Write-Host "`n=== Type Checking with MyPy ===" -ForegroundColor Cyan
    poetry run mypy src/
}

function Run-Install {
    Write-Host "`n=== Installing Dependencies ===" -ForegroundColor Cyan
    poetry install --no-root
}

function Run-All {
    Run-Format
    Run-Lint
    Run-TypeCheck
    Run-Tests
}

switch ($Command) {
    "test" { Run-Tests }
    "lint" { Run-Lint }
    "format" { Run-Format }
    "type-check" { Run-TypeCheck }
    "install" { Run-Install }
    "all" { Run-All }
}

Write-Host "`nDone!" -ForegroundColor Green
