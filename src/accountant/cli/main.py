from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from accountant.config import get_settings
from accountant.db import create_db_engine, session_scope
from accountant.ingest.filings import ingest_company_filings, latest_filing_for_ticker
from accountant.logging import configure_logging, get_logger
from accountant.sec import SecClient

app = typer.Typer(help="THE ACCOUNTANT — deterministic accounting research system.")
console = Console()


@app.callback()
def setup_logging() -> None:
    """Configure logging before any command runs."""
    settings = get_settings()
    configure_logging(level=settings.log_level)


@app.command()
def doctor() -> None:
    """Check configuration, database, DuckDB, directories, and Python environment."""
    log = get_logger(__name__)
    settings = get_settings()

    checks = []

    # SEC User-Agent
    sec_ua_ok = bool(settings.sec_user_agent.strip())
    checks.append(("SEC User-Agent", sec_ua_ok, settings.sec_user_agent[:50] if sec_ua_ok else "MISSING"))

    # Database
    try:
        engine = create_db_engine()
        with engine.connect() as conn:
            result = conn.execute("SELECT 1")
            result.fetchone()
        checks.append(("PostgreSQL/SQLite", True, settings.database_url.split("://")[0]))
        engine.dispose()
    except Exception as e:
        checks.append(("PostgreSQL/SQLite", False, str(e)[:80]))
        log.warning("doctor.database_failed", error=str(e))

    # DuckDB
    try:
        from accountant.storage import connect_duckdb, duckdb_available

        if duckdb_available():
            db = connect_duckdb()
            db.sql("SELECT 1")
            checks.append(("DuckDB", True, str(settings.duckdb_path)))
        else:
            checks.append(("DuckDB", False, "not installed"))
    except Exception as e:
        checks.append(("DuckDB", False, str(e)[:80]))
        log.warning("doctor.duckdb_failed", error=str(e))

    # Required directories
    all_dirs_ok = True
    missing_dirs = []
    for d in settings.required_directories():
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            missing_dirs.append(str(d))
        all_dirs_ok = all_dirs_ok and d.exists()
    checks.append(
        ("Required directories", all_dirs_ok, f"{len(settings.required_directories())} directories")
    )

    # Python environment
    try:
        import accountant

        checks.append(("Python package", True, accountant.__version__))
    except Exception as e:
        checks.append(("Python package", False, str(e)))
        log.warning("doctor.package_failed", error=str(e))

    # Print results
    table = Table(title="THE ACCOUNTANT System Check")
    table.add_column("Check", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Details", style="magenta")

    for check_name, ok, details in checks:
        status = "✓ OK" if ok else "✗ FAIL"
        status_style = "green" if ok else "red"
        table.add_row(check_name, f"[{status_style}]{status}[/{status_style}]", details)

    console.print(table)

    all_ok = all(ok for _, ok, _ in checks)
    if all_ok:
        console.print("[green]✓ All checks passed[/green]")
        raise typer.Exit(0)
    else:
        console.print("[red]✗ Some checks failed[/red]")
        raise typer.Exit(1)


@app.command()
def company(ticker: str) -> None:
    """Look up company info by ticker."""
    log = get_logger(__name__)
    settings = get_settings()

    if not settings.sec_user_agent.strip():
        console.print("[red]SEC_USER_AGENT is not configured[/red]")
        raise typer.Exit(1)

    try:
        client = SecClient()
        resolution = client.resolve_ticker(ticker)
        console.print(f"[cyan]Ticker:[/cyan] {resolution.ticker}")
        console.print(f"[cyan]CIK:[/cyan] {resolution.cik}")
        console.print(f"[cyan]Name:[/cyan] {resolution.name}")
        client.close()
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        log.exception("company_lookup_failed", ticker=ticker, error=str(e))
        raise typer.Exit(1) from None


@app.command()
def ingest(
    ticker: str,
    include_historical: bool = typer.Option(True, help="Include historical filing shards"),
) -> None:
    """Ingest SEC filings for a company by ticker."""
    log = get_logger(__name__)
    settings = get_settings()

    if not settings.sec_user_agent.strip():
        console.print("[red]SEC_USER_AGENT is not configured[/red]")
        raise typer.Exit(1)

    try:
        client = SecClient()
        with session_scope() as session:
            result = ingest_company_filings(
                session,
                client,
                ticker,
                include_historical_files=include_historical,
            )
            console.print(f"[cyan]Ingested for:[/cyan] {result.ticker} ({result.cik})")
            console.print(f"[cyan]Company:[/cyan] {result.company_name}")
            console.print(f"[cyan]Inserted:[/cyan] {result.inserted} filings")
            console.print(f"[cyan]Skipped:[/cyan] {result.skipped} (duplicate/invalid)")
            console.print(f"[cyan]Documents:[/cyan] {result.documents_inserted}")
        client.close()
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        log.exception("ingest_failed", ticker=ticker, error=str(e))
        raise typer.Exit(1) from None


@app.command()
def filing(ticker: str) -> None:
    """Get the latest filing for a ticker."""
    log = get_logger(__name__)

    try:
        with session_scope() as session:
            latest = latest_filing_for_ticker(session, ticker)
            if latest is None:
                console.print(f"[yellow]No filings found for {ticker}[/yellow]")
                raise typer.Exit(1)

            console.print(f"[cyan]Latest filing for:[/cyan] {ticker}")
            console.print(f"[cyan]Accession:[/cyan] {latest.accession_number}")
            console.print(f"[cyan]Form:[/cyan] {latest.form_type}")
            console.print(f"[cyan]Filing Date:[/cyan] {latest.filing_date}")
            console.print(f"[cyan]Report Date:[/cyan] {latest.report_date}")
            if latest.source_url:
                console.print(f"[cyan]URL:[/cyan] {latest.source_url}")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        log.exception("filing_lookup_failed", ticker=ticker, error=str(e))
        raise typer.Exit(1) from None


if __name__ == "__main__":
    app()
