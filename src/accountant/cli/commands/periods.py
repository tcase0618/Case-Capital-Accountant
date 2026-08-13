"""CLI commands for financial period inspection."""

from datetime import date

import click
from rich.console import Console
from rich.table import Table

from accountant.financial.period_resolver import FinancialPeriodResolver

console = Console()


@click.group()
def periods():
    """Inspect and resolve financial periods."""
    pass


@periods.command()
@click.argument("ticker")
@click.option("--concept", default=None, help="Concept code to filter by")
@click.option("--year", type=int, default=None, help="Fiscal year to filter by")
@click.option("--explain", is_flag=True, help="Show detailed period info")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def show(ticker: str, concept: str, year: int, explain: bool, output_json: bool):
    """Show resolved financial periods for a company."""
    console.print(f"[bold]Financial Periods: {ticker}[/bold]")
    console.print("(Database queries not yet implemented — showing resolver demo)")

    # Demo: show sample period resolutions
    resolver = FinancialPeriodResolver()

    periods_demo = [
        {
            "name": "Q1 2024",
            "start": date(2024, 1, 1),
            "end": date(2024, 3, 31),
            "fiscal_year": 2024,
            "fiscal_period": "FY1",
        },
        {
            "name": "6M YTD 2024",
            "start": date(2024, 1, 1),
            "end": date(2024, 6, 30),
            "fiscal_year": 2024,
            "fiscal_period": "FY2",
        },
        {
            "name": "FY 2024",
            "start": date(2024, 1, 1),
            "end": date(2024, 12, 31),
            "fiscal_year": 2024,
            "fiscal_period": "FY",
        },
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
            fiscal_year=p["fiscal_year"],
            fiscal_period=p["fiscal_period"],
            frame=None,
            form="10-Q" if "FY" in p["fiscal_period"] else "10-K",
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
        console.print("• TTM: Trailing twelve months (not yet implemented)")
        console.print("• UNKNOWN: Ambiguous or unusual durations")


@periods.command()
@click.argument("period_type")
@click.argument("start_date")
@click.argument("end_date")
@click.option("--explain", is_flag=True, help="Show why this classification was chosen")
def classify(period_type: str, start_date: str, end_date: str, explain: bool):
    """Classify a custom period by dates."""
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError:
        console.print("[red]Error: Invalid date format. Use YYYY-MM-DD.[/red]")
        return

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

        # Explain the classification
        if result.period_type == "INSTANT":
            console.print("• Balance sheet fact (single point in time)")
        elif result.period_type == "Q1":
            console.print("• Quarter 1 (88-95 day period)")
        elif result.period_type in ("Q2", "Q3", "Q4"):
            console.print(f"• {result.period_type} ({88}-95 day period)")
        elif result.period_type == "FY":
            console.print("• Full fiscal year (365-374 days, 52-53 weeks)")
        elif result.period_type == "YTD_Q2":
            console.print("• Year-to-date through Q2 (6 months, 181-188 days)")
        elif result.period_type == "YTD_Q3":
            console.print("• Year-to-date through Q3 (9 months, 273-283 days)")
        elif result.period_type == "UNKNOWN":
            console.print(f"• Ambiguous duration ({result.duration_days} days)")
            console.print("• Manual investigation recommended")


@periods.command()
@click.argument("fiscal_year", type=int)
@click.option("--fye", default="1231", help="Fiscal year end (MMDD format, default 1231)")
def derive_quarters(fiscal_year: int, fye: str):
    """Show fiscal calendar for a year given fiscal year end."""
    console.print(f"[bold]Fiscal Calendar FY{fiscal_year} (FYE {fye})[/bold]\n")

    # Parse FYE
    try:
        fye_month = int(fye[:2])
        _ = int(fye[2:])
    except (ValueError, IndexError):
        console.print("[red]Error: FYE must be MMDD format (e.g., 1231)[/red]")
        return

    # Determine start year based on FYE
    start_year = fiscal_year if fye_month == 12 else fiscal_year - 1

    table = Table(title=f"FY{fiscal_year} Calendar")
    table.add_column("Quarter", style="cyan")
    table.add_column("Start Date", style="green")
    table.add_column("End Date", style="green")
    table.add_column("Duration", style="yellow")

    # Q1, Q2, Q3 are simplified (calendar-based)
    # This is a demo; real calendars need more complex logic

    for q in range(1, 5):
        # Simplified calendar quarters
        if q == 1:
            q_start = date(start_year, 1, 1)
            q_end = date(start_year, 3, 31)
        elif q == 2:
            q_start = date(start_year, 4, 1)
            q_end = date(start_year, 6, 30)
        elif q == 3:
            q_start = date(start_year, 7, 1)
            q_end = date(start_year, 9, 30)
        else:  # Q4
            q_start = date(start_year, 10, 1)
            q_end = date(start_year, 12, 31)

        duration = (q_end - q_start).days + 1
        table.add_row(f"Q{q}", str(q_start), str(q_end), f"{duration} days")

    console.print(table)


__all__ = ["periods", "show", "classify", "derive_quarters"]
