from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from accountant.config import get_settings
from accountant.db import create_db_engine, session_scope
from accountant.db.models import Company, Security
from accountant.ingest.companyfacts import (
    ingest_company_facts_for_company,
    query_facts,
)
from accountant.ingest.filings import ingest_company_filings, latest_filing_for_ticker
from accountant.logging import configure_logging, get_logger
from accountant.sec import SecClient
from accountant.sec.companyfacts import CompanyFactsClient
from accountant.taxonomy import get_canonical_registry

app = typer.Typer(help="THE ACCOUNTANT — deterministic accounting research system.")
console = Console()


def _lookup_company_by_ticker(session, ticker: str) -> Company | None:
    return (
        session.query(Company)
        .join(Security, Security.company_id == Company.id)
        .filter(Security.ticker == ticker.upper())
        .first()
    )


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
    checks.append(
        (
            "Market Data Mode",
            settings.market_data_mode == "research_only",
            settings.market_data_mode,
        )
    )
    checks.append(
        (
            "IBKR Research Profile",
            settings.ibkr_enabled,
            f"{settings.ibkr_host}:{settings.ibkr_port} | client {settings.ibkr_client_id} | read_only={settings.ibkr_read_only}",
        )
    )

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


@app.command("taxonomy")
def taxonomy_list(category: str | None = typer.Option(None, help="Filter by category")) -> None:
    """List canonical accounting concepts."""
    try:
        registry = get_canonical_registry()

        if category:
            concepts = registry.list_concepts(category)
            title = f"Canonical Concepts — {category}"
        else:
            concepts = registry.list_concepts()
            title = f"Canonical Concepts ({registry.count()} total)"

        table = Table(title=title)
        table.add_column("Code", style="cyan")
        table.add_column("Label", style="green")
        table.add_column("Category", style="yellow")
        table.add_column("Unit Hint", style="magenta")

        for concept in sorted(concepts, key=lambda c: c.code):
            unit_str = concept.unit_hint or "—"
            table.add_row(concept.code, concept.label, concept.category, unit_str)

        console.print(table)

        if category is None:
            categories = registry.categories()
            console.print(f"\n[cyan]Categories:[/cyan] {', '.join(sorted(categories))}")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        log = get_logger(__name__)
        log.exception("taxonomy_list_failed", error=str(e))
        raise typer.Exit(1) from None


@app.command()
def explain(concept_code: str) -> None:
    """Explain a canonical concept."""
    try:
        registry = get_canonical_registry()
        concept = registry.get_concept(concept_code)

        if not concept:
            console.print(f"[red]Concept not found: {concept_code}[/red]")
            raise typer.Exit(1)

        console.print(f"[bold cyan]{concept.code}[/bold cyan]")
        console.print(f"[green]{concept.label}[/green]")
        console.print(f"\n[cyan]Description:[/cyan]\n{concept.description}")
        console.print(f"\n[cyan]Category:[/cyan] {concept.category}")
        if concept.unit_hint:
            console.print(f"[cyan]Unit Hint:[/cyan] {concept.unit_hint}")
        console.print(f"[cyan]Version:[/cyan] {concept.version}")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        log = get_logger(__name__)
        log.exception("explain_failed", concept=concept_code, error=str(e))
        raise typer.Exit(1) from None


@app.command()
def candidates(
    taxonomy: str,
    concept: str,
) -> None:
    """Find candidate canonical mappings for a raw concept.

    Example: candidates us-gaap Assets
    """
    log = get_logger(__name__)

    try:
        with session_scope() as session:
            from accountant.ingest.canonical_mapper import CanonicalMapper

            mapper = CanonicalMapper(session)
            mappings = mapper.find_candidates(taxonomy, concept)

            if not mappings:
                console.print(f"[yellow]No candidates found for {taxonomy}:{concept}[/yellow]")
                raise typer.Exit(0)

            table = Table(
                title=f"Candidates for {taxonomy}:{concept}",
            )
            table.add_column("Canonical", style="cyan")
            table.add_column("Priority", style="green")
            table.add_column("Confidence", style="yellow")
            table.add_column("Industry", style="magenta")

            for mapping in sorted(mappings, key=lambda m: (-m.get("priority", 0), m.get("confidence", ""))):
                industry_str = mapping.get("industry_applicability") or "—"
                table.add_row(
                    mapping.get("canonical_concept_code", "?"),
                    str(mapping.get("priority", "?")),
                    mapping.get("confidence", "?"),
                    industry_str,
                )

            console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        log.exception("candidates_failed", taxonomy=taxonomy, concept=concept, error=str(e))
        raise typer.Exit(1) from None


@app.command()
def normalize(
    ticker: str,
    form: str | None = typer.Option(None, help="Filter by form type"),
    mapping_version: int = typer.Option(1, help="Mapping rules version"),
) -> None:
    """Normalize raw XBRL facts to canonical facts for a company.

    Validates filings, maps all facts to canonical concepts, and stores canonical facts
    with full lineage. Idempotent: repeated runs produce consistent state.

    Example: normalize AAPL --form 10-K
    """
    log = get_logger(__name__)

    try:
        from accountant.ingest.canonical_ingestion import CanonicalFactIngestion
        from accountant.xbrl.arelle_adapter import ArelleFacade

        with session_scope() as session:
            # Find company
            company = _lookup_company_by_ticker(session, ticker)
            if not company:
                console.print(f"[red]Company not found: {ticker}[/red]")
                raise typer.Exit(1)

            # Get filings to normalize
            from sqlalchemy import select

            from accountant.db.models import Filing

            stmt = select(Filing).where(Filing.company_id == company.id)
            if form:
                stmt = stmt.where(Filing.form_type == form)
            filings = session.execute(stmt).scalars().all()

            if not filings:
                console.print(f"[yellow]No filings found for {ticker}[/yellow]")
                raise typer.Exit(0)

            # Initialize Arelle and ingestion
            try:
                arelle = ArelleFacade()
            except RuntimeError:
                arelle = None
                console.print("[yellow]Arelle not available; validations will be skipped[/yellow]")

            ingestion = CanonicalFactIngestion(session, arelle)

            # Normalize each filing
            console.print(f"\n[cyan]Normalizing {len(filings)} filing(s) for {ticker}...[/cyan]\n")
            total_stats = {
                "examined": 0,
                "inserted": 0,
                "existing": 0,
                "mapped": 0,
                "low_confidence": 0,
                "conflicts": 0,
                "unmapped": 0,
                "custom_tags": 0,
            }

            for filing in filings:
                result = ingestion.ingest_filing(
                    filing,
                    company,
                    mapping_version=mapping_version,
                )

                total_stats["examined"] += result.raw_facts_examined
                total_stats["inserted"] += result.canonical_facts_inserted
                total_stats["existing"] += result.canonical_facts_existing
                total_stats["mapped"] += result.facts_mapped
                total_stats["low_confidence"] += result.facts_low_confidence
                total_stats["conflicts"] += result.facts_conflicts
                total_stats["unmapped"] += result.facts_unmapped
                total_stats["custom_tags"] += result.facts_custom_tags

                status_icon = "[green]✓[/green]" if not result.errors else "[yellow]⚠[/yellow]"
                console.print(
                    f"{status_icon} {filing.form_type} ({filing.filing_date}) — "
                    f"{result.raw_facts_examined} facts → {result.canonical_facts_inserted} canonical"
                )
                if result.errors:
                    for err in result.errors[:3]:
                        console.print(f"  [yellow]{err}[/yellow]")

            # Summary
            console.print(f"\n[bold cyan]Summary for {ticker}[/bold cyan]")
            summary_table = Table()
            summary_table.add_column("Metric", style="cyan")
            summary_table.add_column("Count", style="green")

            summary_table.add_row("Raw facts examined", str(total_stats["examined"]))
            summary_table.add_row("Canonical facts inserted", str(total_stats["inserted"]))
            summary_table.add_row("Canonical facts existing", str(total_stats["existing"]))
            summary_table.add_row("Mapped (HIGH confidence)", str(total_stats["mapped"]))
            summary_table.add_row("Low confidence", str(total_stats["low_confidence"]))
            summary_table.add_row("Conflicts", str(total_stats["conflicts"]))
            summary_table.add_row("Unmapped", str(total_stats["unmapped"]))
            summary_table.add_row("Custom tags", str(total_stats["custom_tags"]))

            console.print(summary_table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        log.exception("normalize_failed", ticker=ticker, error=str(e))
        raise typer.Exit(1) from None


@app.command()
def periods_show(ticker: str, explain: bool = False) -> None:
    """Show resolved financial periods for a company."""
    from datetime import date

    from accountant.financial.period_resolver import FinancialPeriodResolver

    console.print(f"[bold]Financial Periods: {ticker}[/bold]")
    console.print("(Database queries not yet implemented — showing resolver demo)\n")

    resolver = FinancialPeriodResolver()

    periods_demo = [
        {"name": "Q1 2024", "start": date(2024, 1, 1), "end": date(2024, 3, 31)},
        {"name": "Q2 2024", "start": date(2024, 4, 1), "end": date(2024, 6, 30)},
        {"name": "6M YTD 2024", "start": date(2024, 1, 1), "end": date(2024, 6, 30)},
        {"name": "9M YTD 2024", "start": date(2024, 1, 1), "end": date(2024, 9, 30)},
        {"name": "FY 2024", "start": date(2024, 1, 1), "end": date(2024, 12, 31)},
    ]

    table = Table(title="Resolved Periods")
    table.add_column("Period", style="cyan")
    table.add_column("Start", style="green")
    table.add_column("End", style="green")
    table.add_column("Type", style="yellow")
    table.add_column("Q", style="magenta")
    table.add_column("Confidence", style="blue")

    for p in periods_demo:
        resolved = resolver.resolve_period(
            company_cik="0000789019",
            instant_date=None,
            start_date=p["start"],
            end_date=p["end"],
            fiscal_year=p["start"].year if p["start"].year == p["end"].year else None,
            fiscal_period=None,
            frame=None,
            form="10-Q",
            decimals=-6,
        )

        table.add_row(
            p["name"],
            str(p["start"]),
            str(p["end"]),
            resolved.period_type,
            str(resolved.fiscal_quarter) if resolved.fiscal_quarter else "-",
            resolved.confidence,
        )

    console.print(table)

    if explain:
        console.print("\n[bold]Period Classification Rules:[/bold]")
        console.print("• INSTANT: Balance sheet facts (single point in time)")
        console.print("• Q1-Q4: 88-95 day quarters")
        console.print("• FY: 365-374 day periods (52-53 weeks)")
        console.print("• YTD_Q2: 181-188 day half-year periods")
        console.print("• YTD_Q3: 273-283 day nine-month periods")
        console.print("• UNKNOWN: Ambiguous or unusual durations")


@app.command("periods-classify")
def periods_classify(
    start_date: str = typer.Argument(..., help="Start date (YYYY-MM-DD)"),
    end_date: str = typer.Argument(..., help="End date (YYYY-MM-DD)"),
    explain: bool = typer.Option(False, help="Show classification rationale"),
) -> None:
    """Classify a period by date range."""
    from datetime import date

    from accountant.financial.period_resolver import FinancialPeriodResolver

    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError:
        console.print("[red]Error: Invalid date format. Use YYYY-MM-DD.[/red]")
        raise typer.Exit(1) from None

    resolver = FinancialPeriodResolver()
    result = resolver.resolve_period(
        company_cik="0000789019",
        instant_date=None,
        start_date=start,
        end_date=end,
        fiscal_year=None,
        fiscal_period=None,
        frame=None,
        form=None,
        decimals=None,
    )

    console.print("\n[bold]Period Classification:[/bold]")
    console.print(f"Start Date:     {start}")
    console.print(f"End Date:       {end}")
    console.print(f"Duration:       {result.duration_days} days")
    console.print(f"Period Type:    [bold]{result.period_type}[/bold]")
    console.print(f"Is YTD:         {result.is_ytd}")
    console.print(f"Confidence:     {result.confidence}")

    if result.fiscal_quarter:
        console.print(f"Fiscal Quarter: Q{result.fiscal_quarter}")

    if result.warnings:
        console.print(f"[yellow]Warnings:[/yellow] {', '.join(result.warnings)}")

    if explain:
        console.print("\n[bold]Explanation:[/bold]")
        if result.period_type == "FY":
            console.print("• Full fiscal year (365-374 days, 52-53 weeks)")
        elif result.period_type.startswith("Q"):
            console.print(f"• {result.period_type} (88-95 day quarter)")
        elif result.period_type == "YTD_Q2":
            console.print("• Year-to-date through Q2 (181-188 days)")
        elif result.period_type == "YTD_Q3":
            console.print("• Year-to-date through Q3 (273-283 days)")
        else:
            console.print("• Ambiguous or unusual duration")
            console.print("• Manual investigation recommended")


@app.command("canonical-facts")
def canonical_facts(
    ticker: str,
    concept: str | None = typer.Option(None, help="Filter by canonical concept code"),
    form: str | None = typer.Option(None, help="Filter by form type"),
    explain: bool = typer.Option(False, help="Show mapping lineage and confidence"),
    limit: int = typer.Option(100, help="Maximum results"),
) -> None:
    """Query canonical facts with optional lineage explanation.

    Example: canonical-facts AAPL --concept CC_REVENUE
    Example: canonical-facts AAPL --explain --limit 10
    """
    log = get_logger(__name__)

    try:
        from accountant.db.models import CanonicalConcept, RawFact
        from accountant.ingest.canonical_ingestion import query_canonical_facts

        with session_scope() as session:
            # Find company
            company = _lookup_company_by_ticker(session, ticker)
            if not company:
                console.print(f"[red]Company not found: {ticker}[/red]")
                raise typer.Exit(1)

            # Query canonical facts
            canonical_facts_list = query_canonical_facts(
                session,
                company_id=str(company.id),
                concept_code=concept,
                form=form,
                limit=limit,
            )

            if not canonical_facts_list:
                console.print(f"[yellow]No canonical facts found for {ticker}[/yellow]")
                raise typer.Exit(0)

            # Display results
            title = f"Canonical Facts for {ticker}"
            if concept:
                title += f" ({concept})"
            table = Table(title=title)
            table.add_column("Concept", style="cyan")
            table.add_column("Value", style="green")
            table.add_column("Unit", style="magenta")
            table.add_column("Confidence", style="yellow")
            table.add_column("Version", style="blue")

            for fact in canonical_facts_list:
                # Get concept code
                canonical_concept = session.query(CanonicalConcept).filter(
                    CanonicalConcept.id == fact.canonical_concept_id
                ).first()
                concept_code = canonical_concept.code if canonical_concept else "?"

                # Format value
                value_str = str(fact.value_numeric) if fact.value_numeric else fact.value or ""

                table.add_row(
                    concept_code,
                    value_str[:30],
                    fact.unit or "—",
                    fact.mapping_confidence or "?",
                    str(fact.mapping_version),
                )

                # Add lineage if explained
                if explain:
                    raw_fact = session.query(RawFact).filter(
                        RawFact.id == fact.raw_fact_id
                    ).first()
                    if raw_fact:
                        console.print(
                            f"  [dim]← {raw_fact.taxonomy}:{raw_fact.concept} "
                            f"(raw_fact_id: {fact.raw_fact_id})[/dim]"
                        )
                    if fact.mapping_rule:
                        console.print(f"  [dim]  rule: {fact.mapping_rule}[/dim]")

            console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        log.exception("canonical_facts_failed", ticker=ticker, error=str(e))
        raise typer.Exit(1) from None


@app.command()
def metrics(category: str | None = typer.Option(None, help="Filter by category")) -> None:
    """List all available financial metrics.

    Example: metrics
    Example: metrics --category ROIC
    """
    try:
        from accountant.calculations import get_calculation_registry

        registry = get_calculation_registry()

        if category:
            calcs = registry.list_by_category(category)
            title = f"Metrics — {category}"
        else:
            calcs = registry.list_all()
            title = f"Available Metrics ({registry.count()} total)"

        table = Table(title=title)
        table.add_column("ID", style="cyan")
        table.add_column("Label", style="green")
        table.add_column("Category", style="yellow")
        table.add_column("Formula", style="magenta")
        table.add_column("Unit", style="blue")

        for calc in sorted(calcs, key=lambda c: c.calculation_id):
            table.add_row(
                calc.calculation_id,
                calc.label,
                calc.category,
                calc.formula_text[:30],
                calc.unit,
            )

        console.print(table)

        if category is None:
            # Show available categories
            all_calcs = registry.list_all()
            categories = set(c.category for c in all_calcs)
            console.print(f"\n[cyan]Categories:[/cyan] {', '.join(sorted(categories))}")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        log = get_logger(__name__)
        log.exception("metrics_list_failed", error=str(e))
        raise typer.Exit(1) from None


@app.command()
def metric(
    ticker: str,
    metric_id: str,
    fiscal_year: int = typer.Option(..., help="Fiscal year"),
    fiscal_quarter: int | None = typer.Option(None, help="Fiscal quarter (Q1-Q4, or None for FY)"),
    explain: bool = typer.Option(False, help="Show formula and inputs"),
) -> None:
    """Calculate a financial metric for a company.

    Example: metric AAPL GROSS_MARGIN --fiscal-year 2024 --explain
    Example: metric AAPL ROIC --fiscal-year 2024 --fiscal-quarter 4
    """
    log = get_logger(__name__)

    try:
        from accountant.calculations import (
            get_calculation_registry,
        )

        # Get registry and lookup metric
        registry = get_calculation_registry()
        calc_def = registry.get(metric_id)

        if not calc_def:
            console.print(f"[red]Metric not found: {metric_id}[/red]")
            raise typer.Exit(1)

        # Demo output (full implementation requires DB statements)
        console.print(f"[bold cyan]{calc_def.label}[/bold cyan]")
        console.print(f"[cyan]Formula:[/cyan] {calc_def.formula_text}")
        console.print(f"[cyan]Unit:[/cyan] {calc_def.unit}")

        if explain:
            console.print("\n[cyan]Description:[/cyan]")
            console.print(calc_def.description or "No description available")
            console.print("\n[cyan]Inputs:[/cyan]")
            for inp in calc_def.inputs:
                console.print(f"  • {inp}")
            console.print(f"\n[cyan]Formula Version:[/cyan] {calc_def.formula_version}")

        console.print("\n[yellow]Note: Live calculation requires full statement reconstruction from database[/yellow]")
        console.print("[yellow]Current scope: Framework and metric definitions complete[/yellow]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        log.exception("metric_calculation_failed", ticker=ticker, metric_id=metric_id, error=str(e))
        raise typer.Exit(1) from None


@app.command("owner-earnings")
def owner_earnings(
    ticker: str,
    fiscal_year: int = typer.Option(..., help="Fiscal year"),
    fiscal_quarter: int | None = typer.Option(None, help="Fiscal quarter"),
    method: str = typer.Option(
        "all",
        help="Calculation method: conservative, maintenance, cfo, or all",
    ),
    years: int | None = typer.Option(None, help="Historical years to show"),
    explain: bool = typer.Option(False, help="Show formula and inputs"),
) -> None:
    """Calculate Owner Earnings for a company.

    Example: owner-earnings AAPL --fiscal-year 2024
    Example: owner-earnings AAPL --fiscal-year 2024 --method maintenance --explain
    Example: owner-earnings AAPL --fiscal-year 2024 --years 10
    """
    log = get_logger(__name__)

    try:
        console.print("[bold cyan]Owner Earnings Analysis[/bold cyan]")
        console.print(f"[cyan]Company:[/cyan] {ticker.upper()}")
        console.print(f"[cyan]Fiscal Year:[/cyan] {fiscal_year}")
        if fiscal_quarter:
            console.print(f"[cyan]Fiscal Quarter:[/cyan] Q{fiscal_quarter}")

        console.print("\n[yellow]Note: Full implementation requires statement data from database[/yellow]")
        console.print("[yellow]Current scope: Framework and calculation methods defined[/yellow]")
        console.print("\n[cyan]Available Models:[/cyan]")
        console.print("  • CONSERVATIVE: Uses full CAPEX (most conservative)")
        console.print("  • MAINTENANCE: Uses estimated maintenance CAPEX (realistic)")
        console.print("  • CFO: Uses operating cash flow (direct)")

        if explain:
            console.print("\n[cyan]Conservative Formula:[/cyan]")
            console.print("  OE = NI + noncash_charges - total_CAPEX - WC_investment - adjustments")
            console.print("\n[cyan]Maintenance CAPEX Formula:[/cyan]")
            console.print("  OE = NI + noncash_charges - maintenance_CAPEX - WC_investment - adjustments")
            console.print("\n[cyan]CFO Formula:[/cyan]")
            console.print("  OE = CFO - maintenance_CAPEX - adjustments")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        log.exception("owner_earnings_failed", ticker=ticker, error=str(e))
        raise typer.Exit(1) from None


@app.command("bear-case")
def bear_case(
    ticker: str,
    fcf_current: float = typer.Option(None, help="Current FCF ($ millions)"),
    revenue_prior: float = typer.Option(None, help="Prior year revenue ($ millions)"),
    revenue_current: float = typer.Option(None, help="Current year revenue ($ millions)"),
    net_leverage: float = typer.Option(2.0, help="Net leverage ratio"),
    fcf_coverage: float = typer.Option(2.0, help="FCF coverage ratio"),
    customer_concentration: float = typer.Option(0.30, help="Top customer concentration (0-1)"),
    pe_current: float = typer.Option(None, help="Current P/E multiple"),
    pe_historical: float = typer.Option(None, help="Historical P/E multiple"),
    json_output: bool = typer.Option(False, help="Output as JSON"),
) -> None:
    """Bear case analysis: thesis breakers and downside scenarios.

    Example: bear-case MSFT --fcf-current 50 --net-leverage 1.5 --customer-concentration 0.25
    """
    log = get_logger(__name__)

    try:
        from accountant.valuation import BearCaseEngine

        revenue_trend = []
        if revenue_prior and revenue_current:
            revenue_trend = [revenue_prior, revenue_current]

        result = BearCaseEngine.calculate_bear_case(
            company_id=ticker,
            fiscal_year=2024,
            as_of_date="2024-12-31",
            fcf_current=fcf_current or 0.0,
            revenue_trend=revenue_trend,
            net_leverage_x=net_leverage,
            fcf_coverage_x=fcf_coverage,
            customer_concentration_pct=customer_concentration,
            current_pe_multiple=pe_current,
            historical_pe_multiple=pe_historical,
        )

        if json_output:
            import json

            console.print(
                json.dumps(
                    {
                        "company": ticker,
                        "thesis_breaker_count": len(result.thesis_breaker_flags),
                        "bear_score": result.bear_case_risk_score,
                        "bear_price": result.bear_case_implied_price,
                        "downside_pct": result.downside_pct,
                    },
                    default=str,
                )
            )
        else:
            table = Table(title=f"Bear Case Analysis: {ticker.upper()}")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")

            table.add_row(
                "Thesis Breakers",
                f"[red]{len(result.thesis_breaker_flags)}[/red]"
                if result.thesis_breaker_flags
                else "[green]0[/green]",
            )
            table.add_row("Risk Score", f"{result.bear_case_risk_score:.1f}/100")
            table.add_row(
                "Implied Price",
                f"${result.bear_case_implied_price:.2f}"
                if result.bear_case_implied_price
                else "N/A",
            )
            table.add_row("Downside", f"{result.downside_pct:.1f}%" if result.downside_pct else "N/A")

            console.print(table)

            if result.thesis_breaker_flags:
                console.print("\n[red][bold]Thesis Breakers:[/bold][/red]")
                for breaker in result.thesis_breaker_flags:
                    console.print(f"  • {breaker.breaker.value}: {breaker.description}")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        log.exception("bear_case_failed", ticker=ticker, error=str(e))
        raise typer.Exit(1) from None


@app.command("capital-structure")
def capital_structure(
    ticker: str,
    cash: float = typer.Option(None, help="Current cash ($ millions)"),
    debt: float = typer.Option(None, help="Current debt ($ millions)"),
    equity_cap: float = typer.Option(None, help="Market cap ($ millions)"),
    fcf: float = typer.Option(None, help="Free cash flow ($ millions)"),
    net_income: float = typer.Option(None, help="Net income ($ millions)"),
    json_output: bool = typer.Option(False, help="Output as JSON"),
) -> None:
    """Capital structure analysis: excess cash, leverage, buyback opportunities.

    Example: capital-structure AAPL --cash 50000 --debt 10000 --equity-cap 3000000
    """
    log = get_logger(__name__)

    try:
        from accountant.valuation import CapitalStructureEngine

        result = CapitalStructureEngine.calculate_capital_structure(
            company_id=ticker,
            fiscal_year=2024,
            as_of_date="2024-12-31",
            total_cash_usd=cash or 0.0,
            total_debt_usd=debt or 0.0,
            market_cap_usd=equity_cap or 0.0,
            fcf_available_usd=fcf or 0.0,
            net_income_usd=net_income or 0.0,
            shares_outstanding=100.0,
            stock_price=100.0,
            intrinsic_value_estimate=100.0,
            sector="TECHNOLOGY",
        )

        if json_output:
            import json

            console.print(
                json.dumps(
                    {
                        "company": ticker,
                        "excess_cash": result.excess_cash_analysis.excess_cash_usd
                        if result.excess_cash_analysis
                        else 0,
                        "can_borrow": result.can_borrow_more,
                        "structure_type": result.structure_type.value,
                    },
                    default=str,
                )
            )
        else:
            table = Table(title=f"Capital Structure: {ticker.upper()}")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")

            if result.excess_cash_analysis:
                table.add_row(
                    "Excess Cash",
                    f"${result.excess_cash_analysis.excess_cash_usd:.0f}M"
                    if result.excess_cash_analysis.excess_cash_usd > 0
                    else "None",
                )
            table.add_row(
                "Borrowing Capacity",
                "Yes" if result.can_borrow_more else "No",
            )
            table.add_row("Structure Type", result.structure_type.value)

            console.print(table)

            if result.top_priorities:
                console.print("\n[cyan][bold]Top Priorities:[/bold][/cyan]")
                for priority in result.top_priorities[:3]:
                    console.print(f"  • {priority}")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        log.exception("capital_structure_failed", ticker=ticker, error=str(e))
        raise typer.Exit(1) from None


@app.command("special-situations")
def special_situations(
    ticker: str,
    situation_type: str = typer.Option("M_AND_A_ACQUISITION", help="Situation type (M_AND_A_ACQUISITION, TENDER_OFFER, SPIN_OFF, etc.)"),
    current_price: float = typer.Option(100.0, help="Current stock price"),
    base_case_price: float = typer.Option(100.0, help="Base case valuation per share"),
    probability: float = typer.Option(50.0, help="Event probability (0-100)"),
    json_output: bool = typer.Option(False, help="Output as JSON"),
) -> None:
    """Special situations analysis: M&A, spin-offs, restructurings.

    Example: special-situations MSFT --situation-type M_AND_A_ACQUISITION --probability 60
    Example: special-situations SNAP --situation-type TENDER_OFFER --current-price 12.50
    """
    log = get_logger(__name__)

    try:
        from accountant.valuation import SpecialSituationsEngine, SpecialSituationType

        result = SpecialSituationsEngine.calculate_special_situations(
            company_id=ticker,
            fiscal_year=2024,
            as_of_date="2024-12-31",
            situation_type=SpecialSituationType(situation_type),
            current_stock_price=current_price,
            base_case_price=base_case_price,
            event_probability_pct=probability,
        )

        if json_output:
            import json

            console.print(
                json.dumps(
                    {
                        "company": ticker,
                        "situation": result.situation_type.value,
                        "probability": result.probability_pct,
                        "expected_value": result.expected_value_price,
                        "mispricing": result.mispricing_opportunity,
                        "action": result.action,
                    },
                    default=str,
                )
            )
        else:
            table = Table(title=f"Special Situations: {ticker.upper()}")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("Situation Type", result.situation_type.value)
            table.add_row("Probability", f"{result.probability_pct:.0f}%")
            table.add_row(
                "Expected Value",
                f"${result.expected_value_price:.2f}"
                if result.expected_value_price
                else "N/A",
            )
            table.add_row("Current Price", f"${current_price:.2f}")
            table.add_row("Mispricing", result.mispricing_opportunity)
            table.add_row("Action", f"[bold]{result.action}[/bold]")

            console.print(table)

            if result.deal_risks:
                console.print("\n[yellow][bold]Key Risks:[/bold][/yellow]")
                for risk in result.deal_risks[:3]:
                    console.print(f"  • {risk}")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        log.exception("special_situations_failed", ticker=ticker, error=str(e))
        raise typer.Exit(1) from None


@app.command("maintenance-capex")
def maintenance_capex(
    ticker: str,
    fiscal_year: int = typer.Option(..., help="Fiscal year"),
    fiscal_quarter: int | None = typer.Option(None, help="Fiscal quarter"),
    method: str = typer.Option(
        "all",
        help="Estimation method: da_anchor, historical_ratio, growth_separation, range, or all",
    ),
    explain: bool = typer.Option(False, help="Show methodology and ranges"),
) -> None:
    """Estimate Maintenance CAPEX for a company.

    Example: maintenance-capex AAPL --fiscal-year 2024
    Example: maintenance-capex AAPL --fiscal-year 2024 --method da_anchor --explain
    """
    log = get_logger(__name__)

    try:
        console.print("[bold cyan]Maintenance CAPEX Estimation[/bold cyan]")
        console.print(f"[cyan]Company:[/cyan] {ticker.upper()}")
        console.print(f"[cyan]Fiscal Year:[/cyan] {fiscal_year}")
        if fiscal_quarter:
            console.print(f"[cyan]Fiscal Quarter:[/cyan] Q{fiscal_quarter}")

        console.print("\n[yellow]Note: Full implementation requires financial statement data from database[/yellow]")
        console.print("[yellow]Current scope: Estimation framework and methods defined[/yellow]")
        console.print("\n[cyan]Available Methods:[/cyan]")
        console.print("  • DA_ANCHOR: Maintenance CAPEX ≈ D&A × multiple")
        console.print("  • HISTORICAL_RATIO: Uses CAPEX/PPE relationship")
        console.print("  • GROWTH_SEPARATION: Separates growth vs maintenance CAPEX from Δ PPE")
        console.print("  • HISTORICAL_RANGE: Multi-year normalized range approach")

        if explain:
            console.print("\n[cyan]Why Multiple Methods?[/cyan]")
            console.print("  • Different companies have different capital patterns")
            console.print("  • Over-reliance on single method can produce outliers")
            console.print("  • Multiple methods provide confidence range (low/base/high)")
            console.print("\n[cyan]Output:[/cyan]")
            console.print("  • Low estimate (conservative)")
            console.print("  • Base estimate (most likely)")
            console.print("  • High estimate (aggressive)")
            console.print("  • Method-specific metadata and assumptions")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        log.exception("maintenance_capex_failed", ticker=ticker, error=str(e))
        raise typer.Exit(1) from None


@app.command()
def valuation(
    ticker: str,
    method: str = typer.Option("dcf", help="Valuation method: dcf, multiples, nav, sotp"),
    fcf_growth: float = typer.Option(0.05, help="Annual FCF growth rate (0.05 = 5%)"),
    terminal_growth: float = typer.Option(0.025, help="Terminal growth rate (0.025 = 2.5%)"),
    discount_rate: float = typer.Option(None, help="Discount rate / WACC (0.10 = 10%)"),
    shares_outstanding: float = typer.Option(None, help="Shares outstanding (millions)"),
    current_price: float = typer.Option(None, help="Current market price per share"),
    years: int = typer.Option(10, help="Forecast horizon (years)"),
    json_output: bool = typer.Option(False, help="Output as JSON"),
) -> None:
    """
    Valuation analysis: DCF, multiples, NAV, SOTP with scenarios.

    Examples:
      accountant valuation MSFT --method dcf --discount-rate 0.08
      accountant valuation AAPL --method multiples --shares-outstanding 15000
    """
    log = get_logger(__name__)

    try:
        from accountant.valuation import ValuationEngine

        # Simple DCF for demo
        if method.lower() == "dcf":
            fcf_projections = [100.0 * ((1.0 + fcf_growth) ** i) for i in range(1, years + 1)]
            dr = discount_rate or 0.10

            dcf = ValuationEngine.calculate_dcf(
                company_id=ticker,
                fiscal_year=2024,
                as_of_date="2024-12-31",
                fcf_projections=fcf_projections,
                terminal_growth=terminal_growth,
                discount_rate=dr,
                forecast_horizon=years,
                shares_outstanding=shares_outstanding or 100.0,
                reference_price=current_price,
            )

            if json_output:
                import json

                console.print(
                    json.dumps(
                        {
                            "method": "DCF",
                            "base_price": dcf.base_price_per_share,
                            "bear_price": dcf.bear_price_per_share,
                            "bull_price": dcf.bull_price_per_share,
                            "terminal_growth": dcf.terminal_growth_rate,
                            "discount_rate": dr,
                        },
                        default=str,
                    )
                )
            else:
                table = Table(title=f"DCF Valuation: {ticker}")
                table.add_column("Metric", style="cyan")
                table.add_column("Value", style="green")
                table.add_row("Bear Case", f"${dcf.bear_price_per_share:.2f}" if dcf.bear_price_per_share else "N/A")
                table.add_row("Base Case", f"${dcf.base_price_per_share:.2f}" if dcf.base_price_per_share else "N/A")
                table.add_row("Bull Case", f"${dcf.bull_price_per_share:.2f}" if dcf.bull_price_per_share else "N/A")
                table.add_row("Terminal Growth", f"{dcf.terminal_growth_rate*100:.1f}%")
                table.add_row("Discount Rate", f"{dr*100:.1f}%")
                if dcf.margin_of_safety_pct:
                    table.add_row("Margin of Safety", f"{dcf.margin_of_safety_pct:.1f}%")
                console.print(table)
        else:
            console.print(f"[yellow]Method '{method}' not yet implemented[/yellow]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        log.exception("valuation_failed", ticker=ticker, error=str(e))
        raise typer.Exit(1) from None


@app.command()
def reverse_dcf(
    ticker: str,
    current_price: float = typer.Option(100.0, help="Current market price per share"),
    shares_outstanding: float = typer.Option(100.0, help="Shares outstanding (millions)"),
    fcf_per_share: float = typer.Option(5.0, help="Current FCF per share"),
    solve_for: str = typer.Option("terminal_growth", help="Solve for: terminal_growth or discount_rate"),
    terminal_growth: float = typer.Option(0.025, help="Terminal growth (if solving for discount rate)"),
    discount_rate: float = typer.Option(0.10, help="Discount rate (if solving for terminal growth)"),
) -> None:
    """
    Reverse DCF: given market price, solve for implied assumptions.

    Examples:
      accountant reverse-dcf MSFT --current-price 350 --fcf-per-share 12
    """
    log = get_logger(__name__)

    try:
        from accountant.valuation import ReverseDCFEngine, SolveVariable

        solve_var = (
            SolveVariable.TERMINAL_GROWTH_RATE
            if solve_for.lower() == "terminal_growth"
            else SolveVariable.DISCOUNT_RATE
        )

        result = ReverseDCFEngine.calculate_reverse_dcf(
            company_id=ticker,
            fiscal_year=2024,
            as_of_date="2024-12-31",
            market_price_per_share=current_price,
            shares_outstanding=shares_outstanding,
            current_fcf_per_share=fcf_per_share,
            solve_variable=solve_var,
            discount_rate=discount_rate if solve_var == SolveVariable.TERMINAL_GROWTH_RATE else None,
            terminal_growth=terminal_growth if solve_var == SolveVariable.DISCOUNT_RATE else None,
        )

        table = Table(title=f"Reverse DCF Analysis: {ticker}")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Market Cap", f"${result.market_cap_usd:,.0f}M" if result.market_cap_usd else "N/A")
        table.add_row("Market Price", f"${current_price:.2f}")
        if result.market_implied_assumption:
            var_name = result.market_implied_assumption.variable.value
            var_value = result.market_implied_assumption.market_implied_value
            pct = f"{var_value*100:.2f}%" if var_value else "N/A"
            table.add_row(f"Implied {var_name}", pct)
            table.add_row("Reasonable?", "Yes" if result.market_implied_assumption.reasonable else "No")
            table.add_row("Assessment", result.market_implied_assumption.reasonableness_note)
        console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        log.exception("reverse_dcf_failed", ticker=ticker, error=str(e))
        raise typer.Exit(1) from None


@app.command()
def credit(
    ticker: str,
    gross_debt: float = typer.Option(1000.0, help="Gross debt (millions)"),
    cash: float = typer.Option(100.0, help="Cash and equivalents (millions)"),
    ebitda: float = typer.Option(500.0, help="EBITDA (millions)"),
    fcf: float = typer.Option(300.0, help="Free cash flow (millions)"),
    interest_expense: float = typer.Option(50.0, help="Annual interest expense (millions)"),
) -> None:
    """
    Credit risk analysis: leverage, coverage, maturity, and credit score.

    Examples:
      accountant credit MSFT --gross-debt 60000 --ebitda 90000
    """
    log = get_logger(__name__)

    try:
        from accountant.valuation import CreditRiskEngine

        result = CreditRiskEngine.calculate_credit_risk(
            company_id=ticker,
            fiscal_year=2024,
            as_of_date="2024-12-31",
            gross_debt_usd=gross_debt,
            cash_and_equivalents_usd=cash,
            ebitda_usd=ebitda,
            fcf_usd=fcf,
            owner_earnings_usd=fcf * 1.1,  # Rough estimate
            operating_cf_usd=fcf * 1.05,
            interest_expense_usd=interest_expense,
            debt_service_annual_usd=interest_expense * 1.5,
            due_within_1_year_usd=gross_debt * 0.2,
            due_within_1_3_years_usd=gross_debt * 0.3,
            due_within_3_5_years_usd=gross_debt * 0.25,
            due_after_5_years_usd=gross_debt * 0.25,
        )

        table = Table(title=f"Credit Risk Analysis: {ticker}")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        if result.leverage_metrics.net_leverage_x:
            table.add_row("Net Leverage", f"{result.leverage_metrics.net_leverage_x:.2f}x")
        if result.coverage_metrics.interest_coverage_x:
            table.add_row("Interest Coverage", f"{result.coverage_metrics.interest_coverage_x:.2f}x")
        table.add_row("Credit Quality", result.credit_quality_score.quality_classification.value if result.credit_quality_score.quality_classification else "N/A")
        table.add_row("Credit Score", f"{result.credit_quality_score.total_score:.0f}/100" if result.credit_quality_score.total_score else "N/A")

        if result.key_risks:
            table.add_row("Key Risks", ", ".join(result.key_risks[:2]))
        if result.key_strengths:
            table.add_row("Key Strengths", ", ".join(result.key_strengths[:2]))

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        log.exception("credit_failed", ticker=ticker, error=str(e))
        raise typer.Exit(1) from None


@app.command("research-record")
def research_record(
    ticker: str,
    date: str = typer.Option(..., help="Query date (YYYY-MM-DD)"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """
    Display research classification record for a company at a point in time.

    Shows the classification, metrics, and confidence for a company
    based on data available at the specified date.

    Examples:
      accountant research-record MSFT --date 2024-02-15
      accountant research-record MSFT --date 2024-02-15 --json
    """
    log = get_logger(__name__)

    try:
        from accountant.db.models import ResearchRecord
        from accountant.sec import SecClient
        from sqlalchemy import and_, select

        sec_client = SecClient()

        with session_scope() as session:
            # Resolve ticker to company_id
            resolution = sec_client.resolve_ticker(ticker)
            company = session.query(Company).filter(Company.cik == resolution.cik).first()

            if not company:
                console.print(f"[yellow]Company not found for ticker {ticker}[/yellow]")
                console.print("[yellow]Run 'ingest TICKER' first[/yellow]")
                raise typer.Exit(1) from None

            # Query research record
            stmt = select(ResearchRecord).where(
                and_(
                    ResearchRecord.company_id == company.id,
                    ResearchRecord.as_of_date == date,
                )
            )
            record = session.scalars(stmt).first()

            if not record:
                console.print(f"[yellow]No research record found for {ticker} on {date}[/yellow]")
                raise typer.Exit(1) from None

            if json_output:
                import json

                output = {
                    "ticker": ticker,
                    "date": record.as_of_date,
                    "classification": record.classification,
                    "confidence": record.classification_confidence,
                    "metrics": {
                        "accounting_quality": record.accounting_quality_score,
                        "owner_earnings_yield_pct": record.owner_earnings_yield_pct,
                        "owner_earnings_growth_pct": record.owner_earnings_growth_pct,
                        "roic_pct": record.roic_pct,
                        "capital_allocation_score": record.capital_allocation_score,
                        "credit_quality_score": record.credit_quality_score,
                        "forensic_risk_score": record.forensic_risk_score,
                    },
                    "valuation": {
                        "low": record.valuation_range_low,
                        "high": record.valuation_range_high,
                        "current_price": record.current_price,
                        "margin_of_safety_pct": record.margin_of_safety_pct,
                    },
                    "rules_triggered": record.rules_triggered or [],
                    "rules_failed": record.rules_failed or [],
                    "warnings": record.warnings or [],
                }
                console.print(json.dumps(output, indent=2))
            else:
                # Human-readable output
                console.print(f"\n[bold cyan]Research Classification Record[/bold cyan]")
                console.print(f"[cyan]Company:[/cyan] {company.name} ({ticker})")
                console.print(f"[cyan]As of:[/cyan] {record.as_of_date}")

                # Classification
                console.print(f"\n[bold]Classification:[/bold]")
                console.print(f"  [cyan]Status:[/cyan] {record.classification}")
                if record.classification_confidence:
                    console.print(f"  [cyan]Confidence:[/cyan] {record.classification_confidence:.0%}")

                # Key metrics
                console.print(f"\n[bold]Key Metrics:[/bold]")
                if record.accounting_quality_score is not None:
                    console.print(
                        f"  [cyan]Accounting Quality:[/cyan] {record.accounting_quality_score:.1f}/10"
                    )
                if record.owner_earnings_yield_pct is not None:
                    console.print(
                        f"  [cyan]Owner Earnings Yield:[/cyan] {record.owner_earnings_yield_pct:.2f}%"
                    )
                if record.roic_pct is not None:
                    console.print(f"  [cyan]ROIC:[/cyan] {record.roic_pct:.2f}%")
                if record.capital_allocation_score is not None:
                    console.print(
                        f"  [cyan]Capital Allocation:[/cyan] {record.capital_allocation_score:.1f}/10"
                    )

                # Valuation
                console.print(f"\n[bold]Valuation:[/bold]")
                if record.valuation_range_low and record.valuation_range_high:
                    console.print(
                        f"  [cyan]Range:[/cyan] ${record.valuation_range_low:.2f} - ${record.valuation_range_high:.2f}"
                    )
                if record.current_price:
                    console.print(f"  [cyan]Current Price:[/cyan] ${record.current_price:.2f}")
                if record.margin_of_safety_pct:
                    console.print(f"  [cyan]Margin of Safety:[/cyan] {record.margin_of_safety_pct:.1f}%")

                # Rules
                if record.rules_triggered:
                    console.print(f"\n[bold green]Rules Triggered ({len(record.rules_triggered)}):[/bold green]")
                    for rule in record.rules_triggered:
                        console.print(f"  [green]✓ {rule}[/green]")

                if record.rules_failed:
                    console.print(f"\n[bold red]Rules Failed ({len(record.rules_failed)}):[/bold red]")
                    for rule in record.rules_failed:
                        console.print(f"  [red]✗ {rule}[/red]")

                # Warnings
                if record.warnings:
                    console.print(f"\n[bold yellow]Warnings:[/bold yellow]")
                    for warning in record.warnings:
                        console.print(f"  [yellow]• {warning}[/yellow]")

                if record.classification_notes:
                    console.print(f"\n[bold]Notes:[/bold]")
                    console.print(f"[cyan]{record.classification_notes}[/cyan]")

        sec_client.close()

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        log.exception("research_record_failed", ticker=ticker, date=date, error=str(e))
        raise typer.Exit(1) from None


@app.command("research-history")
def research_history(
    ticker: str,
    start: str = typer.Option(..., help="Start date (YYYY-MM-DD)"),
    end: str = typer.Option(..., help="End date (YYYY-MM-DD)"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """
    Display research classification history over a date range.

    Shows how classification, metrics, and confidence changed over time,
    useful for analyzing research evolution and decision changes.

    Examples:
      accountant research-history MSFT --start 2023-01-01 --end 2024-12-31
      accountant research-history MSFT --start 2023-01-01 --end 2024-12-31 --json
    """
    log = get_logger(__name__)

    try:
        from accountant.db.models import ResearchRecord
        from accountant.sec import SecClient
        from sqlalchemy import and_, select

        sec_client = SecClient()

        with session_scope() as session:
            # Resolve ticker to company_id
            resolution = sec_client.resolve_ticker(ticker)
            company = session.query(Company).filter(Company.cik == resolution.cik).first()

            if not company:
                console.print(f"[yellow]Company not found for ticker {ticker}[/yellow]")
                console.print("[yellow]Run 'ingest TICKER' first[/yellow]")
                raise typer.Exit(1) from None

            # Query research records in date range
            stmt = (
                select(ResearchRecord)
                .where(
                    and_(
                        ResearchRecord.company_id == company.id,
                        ResearchRecord.as_of_date >= start,
                        ResearchRecord.as_of_date <= end,
                    )
                )
                .order_by(ResearchRecord.as_of_date)
            )
            records = session.scalars(stmt).all()

            if not records:
                console.print(
                    f"[yellow]No research records found for {ticker} between {start} and {end}[/yellow]"
                )
                raise typer.Exit(0)

            if json_output:
                import json

                output = {
                    "ticker": ticker,
                    "start": start,
                    "end": end,
                    "records": [
                        {
                            "date": r.as_of_date,
                            "classification": r.classification,
                            "confidence": r.classification_confidence,
                            "accounting_quality": r.accounting_quality_score,
                            "roic_pct": r.roic_pct,
                            "owner_earnings_yield_pct": r.owner_earnings_yield_pct,
                            "rules_triggered_count": len(r.rules_triggered or []),
                            "rules_failed_count": len(r.rules_failed or []),
                        }
                        for r in records
                    ],
                }
                console.print(json.dumps(output, indent=2))
            else:
                # Human-readable output
                console.print(f"\n[bold cyan]Research Classification History[/bold cyan]")
                console.print(f"[cyan]Company:[/cyan] {company.name} ({ticker})")
                console.print(f"[cyan]Period:[/cyan] {start} to {end}")
                console.print(f"[cyan]Records:[/cyan] {len(records)}")

                # Timeline table
                table = Table(title=f"Classification Timeline: {ticker}")
                table.add_column("Date", style="cyan")
                table.add_column("Classification", style="magenta")
                table.add_column("Confidence", style="yellow")
                table.add_column("ROIC %", style="blue")
                table.add_column("Accounting Qual.", style="green")
                table.add_column("Rules ✓/✗", style="white")

                for record in records:
                    confidence_str = (
                        f"{record.classification_confidence:.0%}"
                        if record.classification_confidence
                        else "—"
                    )
                    roic_str = f"{record.roic_pct:.1f}%" if record.roic_pct is not None else "—"
                    quality_str = (
                        f"{record.accounting_quality_score:.1f}"
                        if record.accounting_quality_score is not None
                        else "—"
                    )
                    rules_str = f"{len(record.rules_triggered or [])}/{len(record.rules_failed or [])}"

                    table.add_row(
                        record.as_of_date,
                        record.classification,
                        confidence_str,
                        roic_str,
                        quality_str,
                        rules_str,
                    )

                console.print(table)

                # Summary statistics
                classifications = [r.classification for r in records]
                unique_classifications = set(classifications)
                console.print(f"\n[bold]Summary:[/bold]")
                console.print(f"  [cyan]Unique classifications:[/cyan] {len(unique_classifications)}")
                console.print(f"  [cyan]Most recent:[/cyan] {records[-1].classification}")
                if len(records) > 1 and records[-1].classification != records[0].classification:
                    console.print(f"  [cyan]Changed from:[/cyan] {records[0].classification} → {records[-1].classification}")

        sec_client.close()

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        log.exception(
            "research_history_failed", ticker=ticker, start=start, end=end, error=str(e)
        )
        raise typer.Exit(1) from None


@app.command("time-machine")
def time_machine(
    ticker: str,
    date: str = typer.Option(..., help="Query date (YYYY-MM-DD)"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    explain: bool = typer.Option(False, "--explain", help="Show detailed explanation"),
) -> None:
    """
    Explore historical financial data as of a point in time.

    Shows what statements, metrics, and facts were available at a specific date,
    preventing future-data leakage and restatement contamination.

    Examples:
      accountant time-machine MSFT --date 2024-02-15
      accountant time-machine MSFT --date 2024-02-15 --explain
      accountant time-machine MSFT --date 2024-02-15 --json
    """
    log = get_logger(__name__)

    try:
        from accountant.analysis.point_in_time_engine import PointInTimeResolver
        from accountant.sec import SecClient

        sec_client = SecClient()

        with session_scope() as session:
            # Resolve ticker to company_id
            resolution = sec_client.resolve_ticker(ticker)
            company = session.query(Company).filter(Company.cik == resolution.cik).first()

            if not company:
                console.print(f"[yellow]Company not found for ticker {ticker}[/yellow]")
                console.print("[yellow]Run 'ingest TICKER' first[/yellow]")
                raise typer.Exit(1) from None

            # Get historical snapshot at point in time
            snapshot = PointInTimeResolver.get_historical_snapshot(
                session=session,
                company_id=str(company.id),
                as_of_date=date,
            )

            if json_output:
                import json

                # Convert to JSON-serializable format
                output = {
                    "company_id": snapshot.company_id,
                    "as_of_date": snapshot.as_of_date,
                    "as_of_timestamp": snapshot.as_of_timestamp,
                    "available_annual_filings": len(snapshot.available_annual_filings),
                    "available_quarterly_filings": len(snapshot.available_quarterly_filings),
                    "available_amendments": len(snapshot.available_amendments),
                    "raw_fact_coverage_pct": round(snapshot.raw_fact_coverage_pct, 1),
                    "statement_completeness_score": round(snapshot.statement_completeness_score, 1),
                    "accounting_metrics_available": snapshot.accounting_metrics_available,
                    "warnings": snapshot.warnings,
                }
                console.print(json.dumps(output, indent=2))
            else:
                # Human-readable output
                console.print(f"\n[bold cyan]Point-in-Time Snapshot[/bold cyan]")
                console.print(f"[cyan]Company:[/cyan] {company.name} ({company.cik})")
                console.print(f"[cyan]As of:[/cyan] {snapshot.as_of_date}")

                # Filings available
                console.print(f"\n[bold]Filings Available:[/bold]")
                console.print(f"  [cyan]Annual (10-K):[/cyan] {len(snapshot.available_annual_filings)}")
                console.print(
                    f"  [cyan]Quarterly (10-Q):[/cyan] {len(snapshot.available_quarterly_filings)}"
                )
                console.print(f"  [cyan]Amendments:[/cyan] {len(snapshot.available_amendments)}")

                # Data quality
                console.print(f"\n[bold]Data Quality:[/bold]")
                console.print(
                    f"  [cyan]Raw fact coverage:[/cyan] {snapshot.raw_fact_coverage_pct:.0f}%"
                )
                console.print(
                    f"  [cyan]Statement completeness:[/cyan] {snapshot.statement_completeness_score:.0f}%"
                )
                console.print(
                    f"  [cyan]Accounting metrics available:[/cyan] {'Yes' if snapshot.accounting_metrics_available else 'No'}"
                )

                # Warnings
                if snapshot.warnings:
                    console.print(f"\n[bold yellow]Warnings:[/bold yellow]")
                    for warning in snapshot.warnings:
                        console.print(f"  [yellow]• {warning}[/yellow]")

                # Detailed explanation
                if explain:
                    console.print(f"\n[bold green]Detailed Analysis:[/bold green]")
                    console.print(f"[green]{snapshot.coverage_notes}[/green]")

                    if snapshot.available_annual_filings:
                        console.print(f"\n[bold]Latest 10-K:[/bold]")
                        latest_10k = snapshot.available_annual_filings[-1]
                        console.print(f"  [cyan]Fiscal End:[/cyan] {latest_10k.fiscal_end_date}")
                        console.print(f"  [cyan]Accepted:[/cyan] {latest_10k.accepted_timestamp}")
                        console.print(f"  [cyan]Is Restated:[/cyan] {'Yes' if latest_10k.is_restated else 'No'}")

        sec_client.close()

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        log.exception("time_machine_failed", ticker=ticker, date=date, error=str(e))
        raise typer.Exit(1) from None


if __name__ == "__main__":
    app()
