"""Export research data to multiple formats (JSON, CSV, Parquet, DuckDB)."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from accountant.research.classification_engine import FundamentalResearchRecord


class ExportFormat:
    """Supported export formats."""

    JSON = "json"
    CSV = "csv"
    PARQUET = "parquet"
    DUCKDB = "duckdb"


class ResearchExporter:
    """Export research records to multiple formats."""

    @staticmethod
    def export_record_to_json(
        record: FundamentalResearchRecord,
        output_path: str | Path,
    ) -> Path:
        """
        Export single research record to JSON.

        Args:
            record: FundamentalResearchRecord to export
            output_path: Path to write JSON file

        Returns:
            Path to created file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert frozen dataclass to dict
        record_dict = asdict(record)

        # Serialize with custom JSON encoder
        with open(output_path, "w") as f:
            json.dump(record_dict, f, indent=2, default=str)

        return output_path

    @staticmethod
    def export_records_to_json(
        records: list[FundamentalResearchRecord],
        output_path: str | Path,
    ) -> Path:
        """
        Export multiple research records to JSON array.

        Args:
            records: List of FundamentalResearchRecord objects
            output_path: Path to write JSON file

        Returns:
            Path to created file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        records_list = [asdict(r) for r in records]

        with open(output_path, "w") as f:
            json.dump(records_list, f, indent=2, default=str)

        return output_path

    @staticmethod
    def export_records_to_csv(
        records: list[FundamentalResearchRecord],
        output_path: str | Path,
    ) -> Path:
        """
        Export research records to CSV.

        Args:
            records: List of FundamentalResearchRecord objects
            output_path: Path to write CSV file

        Returns:
            Path to created file
        """
        try:
            import csv
        except ImportError:
            raise ImportError("csv module required for CSV export")

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if not records:
            # Write empty CSV with headers
            with open(output_path, "w", newline="") as f:
                f.write("")
            return output_path

        # Get all field names from first record
        fieldnames = list(asdict(records[0]).keys())

        # Write CSV
        with open(output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for record in records:
                writer.writerow(asdict(record))

        return output_path

    @staticmethod
    def export_records_to_parquet(
        records: list[FundamentalResearchRecord],
        output_path: str | Path,
    ) -> Path:
        """
        Export research records to Parquet format.

        Args:
            records: List of FundamentalResearchRecord objects
            output_path: Path to write Parquet file

        Returns:
            Path to created file
        """
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError:
            raise ImportError("pyarrow required for Parquet export")

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if not records:
            # Create empty table with schema
            schema = pa.schema([("company_id", pa.string()), ("as_of_date", pa.string())])
            table = pa.table({}, schema=schema)
            pq.write_table(table, output_path)
            return output_path

        # Convert records to dict format
        records_data: dict[str, list[Any]] = {}
        for record in records:
            record_dict = asdict(record)
            for key, value in record_dict.items():
                if key not in records_data:
                    records_data[key] = []
                records_data[key].append(value)

        # Create PyArrow table
        table = pa.table(records_data)

        # Write Parquet
        pq.write_table(table, output_path)

        return output_path

    @staticmethod
    def export_records_to_duckdb(
        records: list[FundamentalResearchRecord],
        output_path: str | Path,
        table_name: str = "research_records",
    ) -> Path:
        """
        Export research records to DuckDB format.

        Creates a DuckDB database file with research records in a table.

        Args:
            records: List of FundamentalResearchRecord objects
            output_path: Path to write DuckDB file (.duckdb)
            table_name: Name of table to create

        Returns:
            Path to created DuckDB file
        """
        try:
            import duckdb
        except ImportError:
            raise ImportError("duckdb required for DuckDB export")

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Connect to DuckDB database
        conn = duckdb.connect(str(output_path))

        try:
            if not records:
                # Create empty table with schema
                conn.execute(
                    f"""
                    CREATE TABLE {table_name} (
                        company_id VARCHAR,
                        as_of_date VARCHAR
                    )
                    """
                )
            else:
                # Convert records to dict list
                records_data = [asdict(r) for r in records]

                # Create table from records
                from_df = conn.from_df(records_data)
                from_df.create_view(table_name, replace=True)
                conn.execute(
                    f"CREATE TABLE {table_name} AS SELECT * FROM {table_name}_view"
                )
                conn.execute(f"DROP VIEW {table_name}_view")

            conn.commit()
        finally:
            conn.close()

        return output_path

    @staticmethod
    def export_snapshot_summary(
        records: list[FundamentalResearchRecord],
        output_format: str = ExportFormat.JSON,
    ) -> str:
        """
        Generate summary statistics for research records.

        Args:
            records: List of FundamentalResearchRecord objects
            output_format: Export format (json or csv)

        Returns:
            Formatted summary string
        """
        if not records:
            return "{}" if output_format == ExportFormat.JSON else ""

        summary = {
            "total_records": len(records),
            "date_range": {
                "earliest": min(r.as_of_date for r in records),
                "latest": max(r.as_of_date for r in records),
            },
            "classifications": {},
            "metrics": {
                "avg_roic_pct": None,
                "avg_owner_earnings_yield": None,
                "avg_accounting_quality": None,
            },
        }

        # Count classifications
        for record in records:
            cls = record.classification
            summary["classifications"][cls] = summary["classifications"].get(cls, 0) + 1

        # Calculate average metrics
        roic_values = [r.roic_pct for r in records if r.roic_pct is not None]
        if roic_values:
            summary["metrics"]["avg_roic_pct"] = sum(roic_values) / len(roic_values)

        oe_yield_values = [r.owner_earnings_yield_pct for r in records
                          if r.owner_earnings_yield_pct is not None]
        if oe_yield_values:
            summary["metrics"]["avg_owner_earnings_yield"] = (
                sum(oe_yield_values) / len(oe_yield_values)
            )

        quality_values = [r.accounting_quality_score for r in records
                         if r.accounting_quality_score is not None]
        if quality_values:
            summary["metrics"]["avg_accounting_quality"] = (
                sum(quality_values) / len(quality_values)
            )

        if output_format == ExportFormat.JSON:
            return json.dumps(summary, indent=2, default=str)
        else:
            # CSV format
            lines = []
            lines.append("Metric,Value")
            lines.append(f"Total Records,{summary['total_records']}")
            lines.append(f"Earliest Date,{summary['date_range']['earliest']}")
            lines.append(f"Latest Date,{summary['date_range']['latest']}")
            for cls, count in summary["classifications"].items():
                lines.append(f"Classification: {cls},{count}")
            if summary["metrics"]["avg_roic_pct"]:
                lines.append(f"Avg ROIC %,{summary['metrics']['avg_roic_pct']:.2f}")
            if summary["metrics"]["avg_owner_earnings_yield"]:
                lines.append(
                    f"Avg OE Yield %,{summary['metrics']['avg_owner_earnings_yield']:.2f}"
                )
            if summary["metrics"]["avg_accounting_quality"]:
                lines.append(
                    f"Avg Accounting Quality,{summary['metrics']['avg_accounting_quality']:.1f}"
                )
            return "\n".join(lines)
