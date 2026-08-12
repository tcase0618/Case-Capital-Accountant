from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from accountant.config import get_settings
from accountant.db import create_db_engine, session_scope
from accountant.db.models import Company
from accountant.ingest.companyfacts import (
    ingest_company_facts_for_company,
    query_facts,
)
from accountant.ingest.filings import ingest_company_filings, latest_filing_for_ticker
from accountant.logging import configure_logging, get_logger
from accountant.sec import SecClient
from accountant.sec.companyfacts import CompanyFactsClient

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


@app.command("ingest-companyfacts")
def ingest_companyfacts(ticker: str) -> None:
    """Ingest CompanyFacts (XBRL facts) for a company by ticker."""
    log = get_logger(__name__)
    settings = get_settings()

    if not settings.sec_user_agent.strip():
        console.print("[red]SEC_USER_AGENT is not configured[/red]")
        raise typer.Exit(1) from None

    try:
        sec_client = SecClient()
        companyfacts_client = CompanyFactsClient(settings, sec_client=sec_client)

        with session_scope() as session:
            # Resolve ticker to find company
            resolution = sec_client.resolve_ticker(ticker)
            company = session.query(Company).filter(Company.cik == resolution.cik).first()

            if not company:
                console.print(f"[yellow]Company not found for ticker {ticker}[/yellow]")
                console.print("[yellow]Run 'ingest TICKER' first to fetch company data[/yellow]")
                raise typer.Exit(1) from None

            result = ingest_company_facts_for_company(
                session, company, companyfacts_client, sec_client
            )

            console.print(f"[cyan]Ingested for:[/cyan] {result.ticker} ({result.cik})")
            console.print(f"[cyan]Company:[/cyan] {result.company_name}")
            console.print(f"[cyan]Concepts processed:[/cyan] {result.concepts_processed}")
            console.print(f"[cyan]Facts inserted:[/cyan] {result.facts_inserted}")
            console.print(f"[cyan]Facts skipped:[/cyan] {result.facts_skipped}")
            if result.errors:
                console.print(f"[yellow]Errors: {len(result.errors)}[/yellow]")
                for err in result.errors[:5]:
                    console.print(f"  [yellow]{err}[/yellow]")

            session.commit()

        sec_client.close()

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        log.exception("ingest_companyfacts_failed", ticker=ticker, error=str(e))
        raise typer.Exit(1) from None


@app.command()
def facts(
    ticker: str,
    concept: str | None = typer.Option(None, help="Filter by concept"),
    taxonomy: str | None = typer.Option(None, help="Filter by taxonomy"),
    form: str | None = typer.Option(None, help="Filter by form type"),
    limit: int = typer.Option(50, help="Maximum results"),
) -> None:
    """Query raw XBRL facts for a company."""
    log = get_logger(__name__)

    try:
        sec_client = SecClient()

        with session_scope() as session:
            # Resolve ticker
            try:
                resolution = sec_client.resolve_ticker(ticker)
            except Exception:
                console.print(f"[red]Ticker not found: {ticker}[/red]")
                raise typer.Exit(1) from None

            # Find company
            company = session.query(Company).filter(Company.cik == resolution.cik).first()
            if not company:
                console.print(f"[yellow]Company not found for ticker {ticker}[/yellow]")
                raise typer.Exit(1) from None

            # Query facts
            facts_list = query_facts(
                session,
                company_id=str(company.id),
                concept=concept,
                taxonomy=taxonomy,
                form=form,
                limit=limit,
            )

            if not facts_list:
                console.print(f"[yellow]No facts found for {ticker}[/yellow]")
                raise typer.Exit(0)

            # Display results
            table = Table(title=f"Facts for {ticker} ({company.cik})")
            table.add_column("Concept", style="cyan")
            table.add_column("Taxonomy", style="magenta")
            table.add_column("Form", style="blue")
            table.add_column("Period", style="yellow")
            table.add_column("Value", style="green")
            table.add_column("Unit", style="white")

            for fact in facts_list:
                period_str = ""
                if fact.instant_date:
                    period_str = str(fact.instant_date)
                elif fact.period_end:
                    period_str = str(fact.period_end)

                value_str = str(fact.value_numeric) if fact.value_numeric else fact.value_text or ""
                table.add_row(
                    fact.concept,
                    fact.taxonomy or "",
                    fact.form or "",
                    period_str,
                    value_str[:40],
                    fact.unit or "",
                )

            console.print(table)

        sec_client.close()

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        log.exception("facts_lookup_failed", ticker=ticker, error=str(e))
        raise typer.Exit(1) from None


@app.command()
def companyconcept(
    ticker: str,
    taxonomy: str,
    concept: str,
) -> None:
    """Retrieve historical data for a single concept."""
    log = get_logger(__name__)

    try:
        sec_client = SecClient()
        companyfacts_client = CompanyFactsClient(settings=get_settings(), sec_client=sec_client)

        with session_scope() as session:
            # Resolve ticker
            resolution = sec_client.resolve_ticker(ticker)
            company = session.query(Company).filter(Company.cik == resolution.cik).first()

            if not company:
                console.print(f"[yellow]Company not found for ticker {ticker}[/yellow]")
                raise typer.Exit(1) from None

            # Get concept data
            concept_data = companyfacts_client.get_company_concept(
                company.cik, taxonomy, concept
            )

            # Display metadata
            console.print(f"[cyan]Concept:[/cyan] {concept}")
            console.print(f"[cyan]Taxonomy:[/cyan] {taxonomy}")
            console.print(f"[cyan]Company:[/cyan] {company.name} ({ticker})")

            # Display concept metadata
            unit_data = concept_data.get("units", {})
            if unit_data:
                console.print(f"[cyan]Units:[/cyan] {', '.join(unit_data.keys())}")

            # Display values
            for unit, values in unit_data.items():
                if not values:
                    continue

                console.print(f"\n[bold]Unit: {unit}[/bold]")
                table = Table()
                table.add_column("Value", style="green")
                table.add_column("Form", style="blue")
                table.add_column("Filed", style="yellow")
                table.add_column("Period", style="cyan")

                for value in sorted(values, key=lambda x: x.get("filed", ""), reverse=True)[:20]:
                    val_str = str(value.get("val", ""))[:20]
                    form_str = value.get("form", "")
                    filed_str = value.get("filed", "")
                    period_str = value.get("end", "") or value.get("instant", "") or ""
                    table.add_row(val_str, form_str, filed_str, period_str)

                console.print(table)

        sec_client.close()

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        log.exception("companyconcept_failed", ticker=ticker, error=str(e))
        raise typer.Exit(1) from None


if __name__ == "__main__":
    app()
