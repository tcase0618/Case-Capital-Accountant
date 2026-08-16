from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import uvicorn


def seed_local_demo_data() -> None:
    from sqlalchemy import select

    from accountant.db import create_db_engine, create_session_factory
    from accountant.db.models import Company, Filing, Security

    engine = create_db_engine(os.environ["DATABASE_URL"])
    session = create_session_factory(engine)()
    try:
        existing = session.execute(select(Company.id).limit(1)).scalar_one_or_none()
        if existing is not None:
            return

        demo_companies = [
            {
                "cik": "0000320193",
                "name": "Apple Inc.",
                "ticker": "AAPL",
                "exchange": "NASDAQ",
                "entity_type": "operating",
                "sic": "3571",
                "sic_description": "Electronic Computers",
                "fiscal_year_end": "0927",
                "state_of_incorporation": "CA",
                "filings": [
                    {
                        "accession_number": "0000320193-25-000001",
                        "form_type": "10-K",
                        "filing_date": date(2025, 11, 1),
                        "report_date": date(2025, 9, 27),
                        "primary_document": "aapl-20250927x10k.htm",
                        "source_url": "https://www.sec.gov/Archives/edgar/data/320193/demo-aapl-10k",
                        "is_xbrl": True,
                        "is_inline_xbrl": True,
                    }
                ],
            },
            {
                "cik": "0000789019",
                "name": "Microsoft Corporation",
                "ticker": "MSFT",
                "exchange": "NASDAQ",
                "entity_type": "operating",
                "sic": "7372",
                "sic_description": "Prepackaged Software",
                "fiscal_year_end": "0630",
                "state_of_incorporation": "WA",
                "filings": [
                    {
                        "accession_number": "0000789019-25-000001",
                        "form_type": "10-K",
                        "filing_date": date(2025, 7, 30),
                        "report_date": date(2025, 6, 30),
                        "primary_document": "msft-20250630x10k.htm",
                        "source_url": "https://www.sec.gov/Archives/edgar/data/789019/demo-msft-10k",
                        "is_xbrl": True,
                        "is_inline_xbrl": True,
                    }
                ],
            },
            {
                "cik": "0001652044",
                "name": "Alphabet Inc.",
                "ticker": "GOOGL",
                "exchange": "NASDAQ",
                "entity_type": "operating",
                "sic": "7370",
                "sic_description": "Services-Computer Programming, Data Processing, Etc.",
                "fiscal_year_end": "1231",
                "state_of_incorporation": "DE",
                "filings": [
                    {
                        "accession_number": "0001652044-25-000001",
                        "form_type": "10-K",
                        "filing_date": date(2025, 2, 5),
                        "report_date": date(2024, 12, 31),
                        "primary_document": "goog-20241231x10k.htm",
                        "source_url": "https://www.sec.gov/Archives/edgar/data/1652044/demo-googl-10k",
                        "is_xbrl": True,
                        "is_inline_xbrl": True,
                    }
                ],
            },
            {
                "cik": "0001018724",
                "name": "Amazon.com, Inc.",
                "ticker": "AMZN",
                "exchange": "NASDAQ",
                "entity_type": "operating",
                "sic": "5961",
                "sic_description": "Catalog and Mail-Order Houses",
                "fiscal_year_end": "1231",
                "state_of_incorporation": "DE",
                "filings": [
                    {
                        "accession_number": "0001018724-25-000001",
                        "form_type": "10-K",
                        "filing_date": date(2025, 2, 2),
                        "report_date": date(2024, 12, 31),
                        "primary_document": "amzn-20241231x10k.htm",
                        "source_url": "https://www.sec.gov/Archives/edgar/data/1018724/demo-amzn-10k",
                        "is_xbrl": True,
                        "is_inline_xbrl": True,
                    }
                ],
            },
            {
                "cik": "0001318605",
                "name": "Tesla, Inc.",
                "ticker": "TSLA",
                "exchange": "NASDAQ",
                "entity_type": "operating",
                "sic": "3711",
                "sic_description": "Motor Vehicles & Passenger Car Bodies",
                "fiscal_year_end": "1231",
                "state_of_incorporation": "DE",
                "filings": [
                    {
                        "accession_number": "0001318605-25-000001",
                        "form_type": "10-K",
                        "filing_date": date(2025, 1, 29),
                        "report_date": date(2024, 12, 31),
                        "primary_document": "tsla-20241231x10k.htm",
                        "source_url": "https://www.sec.gov/Archives/edgar/data/1318605/demo-tsla-10k",
                        "is_xbrl": True,
                        "is_inline_xbrl": True,
                    }
                ],
            },
        ]

        for item in demo_companies:
            company = Company(
                cik=item["cik"],
                name=item["name"],
                entity_type=item["entity_type"],
                sic=item["sic"],
                sic_description=item["sic_description"],
                fiscal_year_end=item["fiscal_year_end"],
                state_of_incorporation=item["state_of_incorporation"],
            )
            company.securities.append(
                Security(
                    ticker=item["ticker"],
                    exchange=item["exchange"],
                    security_type="common_stock",
                )
            )
            for filing_item in item["filings"]:
                company.filings.append(Filing(**filing_item))
            session.add(company)

        session.commit()
    finally:
        session.close()
        engine.dispose()


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    os.chdir(repo_root)
    data_dir = repo_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    sqlite_url = f"sqlite:///{(data_dir / 'accountant.db').resolve().as_posix()}"
    os.environ["DATABASE_URL"] = sqlite_url
    os.environ["ACCOUNTANT_ENV"] = "development"
    os.environ["DATA_DIR"] = str(data_dir)
    os.environ.setdefault("LOG_LEVEL", "INFO")

    from accountant.db import Base, create_db_engine
    from accountant.db.models import (  # noqa: F401
        BuyBoardCandidate,
        BuyBoardSnapshot,
        CalculationResult,
        CanonicalConcept,
        CanonicalFact,
        CanonicalMapping,
        Company,
        CompanyReport,
        Filing,
        FilingDocument,
        FinancialPeriod,
        RawFact,
        ResearchRecord,
        Security,
        StatementLine,
        StatementSnapshot,
    )

    engine = create_db_engine(os.environ["DATABASE_URL"])
    Base.metadata.create_all(bind=engine)
    engine.dispose()
    seed_local_demo_data()

    uvicorn.run(
        "accountant.api.app:app",
        app_dir=str(repo_root / "src"),
        host="127.0.0.1",
        port=8010,
        reload=False,
    )


if __name__ == "__main__":
    main()
