"""ACC-LOW-016: densities are not coverage; estimates cannot grade trust."""

from types import SimpleNamespace
from unittest.mock import Mock

from accountant.db.models import (
    CanonicalConcept,
    CanonicalFact,
    Company,
    CompanyBottleneckSnapshot,
    CompanyReport,
)
from accountant.research import source_integrity as module


def seed_company(session, index, *, report=False, bottleneck=False):
    company = Company(cik=f"{index:010d}", name=f"Fixture {index}")
    session.add(company)
    session.flush()
    fields = {"company_id": company.id, "ticker": f"T{index}", "company_name": company.name}
    if report:
        session.add(CompanyReport(**fields, as_of_date="2026-11-09", stance="WATCH"))
    if bottleneck:
        session.add(CompanyBottleneckSnapshot(**fields))
    session.commit()


def test_bottleneck_coverage_counts_only_reported_companies(test_session):
    seed_company(test_session, 1, report=True)
    seed_company(test_session, 2, bottleneck=True)
    coverage = module.build_source_integrity_snapshot(test_session)["coverage"]
    assert coverage["report_coverage_pct"] == 50
    assert coverage["bottleneck_coverage_pct"] == 0


def test_density_is_named_as_ratio_not_percentage(test_session, monkeypatch):
    seed_company(test_session, 1, report=True, bottleneck=True)
    original = module._exact_scalar
    monkeypatch.setattr(module, "_exact_scalar", lambda session, sql: 2 if "statement_snapshots" in sql else original(session, sql))
    coverage = module.build_source_integrity_snapshot(test_session)["coverage"]
    assert coverage.get("statement_to_report_pct") is None
    assert coverage["statements_per_report"] == 2
    assert coverage.get("canonical_to_raw_pct") is None
    assert all(value is None or 0 <= value <= 100 for key, value in coverage.items() if key.endswith("_pct"))


def test_inverted_postgres_estimates_do_not_change_grade(test_session, monkeypatch):
    seed_company(test_session, 1, report=True, bottleneck=True)
    monkeypatch.setattr(module, "_days_since", lambda _: 0)
    estimates = {"raw_facts": 10000, "canonical_facts": 1, "filings": 100}

    class PostgreSQLSession:
        def get_bind(self):
            return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

        def execute(self, statement, params=None):
            if "pg_class" in str(statement):
                return Mock(scalar=lambda: estimates[params["table_name"]])
            return test_session.execute(statement, params or {})

    first = module.build_source_integrity_snapshot(PostgreSQLSession())
    estimates.update(raw_facts=1, canonical_facts=10000)
    second = module.build_source_integrity_snapshot(PostgreSQLSession())
    assert first["source_grade"] == second["source_grade"]
    assert first["coverage"].get("canonical_to_raw_pct") is None
    assert second["coverage"].get("canonical_to_raw_pct") is None
    estimates.update(raw_facts=0, canonical_facts=0)
    assert module.build_source_integrity_snapshot(PostgreSQLSession())["source_grade"] == first["source_grade"]


def test_exact_lineage_is_one_cohort_even_with_archived_raw_facts(test_session):
    seed_company(test_session, 1, report=True, bottleneck=True)
    company = test_session.query(Company).one()
    concept = CanonicalConcept(code="FIXTURE", label="Fixture")
    test_session.add(concept)
    test_session.flush()
    for source_hash in ("a" * 64, "a" * 64, None):
        test_session.add(CanonicalFact(company_id=company.id, canonical_concept_id=concept.id,
                                       source_fact_hash=source_hash, raw_fact_archived=source_hash is not None))
    test_session.commit()
    coverage = module.build_source_integrity_snapshot(test_session)["coverage"]
    assert coverage["canonical_facts_exact"] == 3
    assert coverage["canonical_facts_with_lineage"] == 2
    assert coverage["canonical_lineage_coverage_pct"] == 66.67
    assert coverage["mapping_coverage_pct"] is None
    assert coverage["mapping_coverage_status"] == "NOT_MEASURED"
    assert coverage["canonical_to_raw_ratio_estimate"] is None


def test_empty_cohorts_are_not_complete_or_infinite(test_session):
    result = module.build_source_integrity_snapshot(test_session)
    assert result["source_grade"] == "FAILED"
    assert result["coverage"]["statements_per_report"] is None
    assert result["coverage"]["canonical_lineage_coverage_pct"] is None
    assert result["coverage"]["report_coverage_pct"] == 0
