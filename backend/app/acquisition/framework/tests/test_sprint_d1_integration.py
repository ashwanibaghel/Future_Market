import os
import tempfile
import pyarrow as pa
import pyarrow.parquet as pq

from app.acquisition.framework.canonical_schema_registry import EQUITY_CANDLE_SCHEMA
from app.acquisition.framework.base_collector import BaseCollectorPlugin
from app.acquisition.framework.storage_registry import StorageRegistry
from app.acquisition.framework.backfill_framework import HistoricalBackfillFramework
from app.research_os.governance.dataset_registry import DatasetRegistry


class MockEquityCollector(BaseCollectorPlugin):
    @property
    def source_name(self) -> str:
        return "MOCK_EQUITY_COLLECTOR"

    @property
    def asset_type(self) -> str:
        return "EQUITIES"

    @property
    def canonical_schema(self) -> pa.Schema:
        return EQUITY_CANDLE_SCHEMA

    def fetch_historical_chunk(self, symbol: str, start_date: str, end_date: str) -> pa.Table:
        return pa.Table.from_arrays(
            [
                pa.array(["2021-03-01T09:15:00+05:30", "2021-03-01T09:16:00+05:30"], type=pa.string()),
                pa.array([1614570300, 1614570360], type=pa.int64()),
                pa.array([symbol.upper(), symbol.upper()], type=pa.string()),
                pa.array(["NSE", "NSE"], type=pa.string()),
                pa.array([2500.0, 2505.0], type=pa.float64()),
                pa.array([2510.0, 2515.0], type=pa.float64()),
                pa.array([2495.0, 2501.0], type=pa.float64()),
                pa.array([2505.0, 2512.0], type=pa.float64()),
                pa.array([10000, 12000], type=pa.int64()),
                pa.array([2504.0, 2509.0], type=pa.float64()),
                pa.array(["MOCK", "MOCK"], type=pa.string()),
            ],
            schema=EQUITY_CANDLE_SCHEMA,
        )


def test_sprint_d1_backfill_framework_integration():
    with tempfile.TemporaryDirectory() as tmpdir:
        lake_dir = os.path.join(tmpdir, "parquet_lake")
        archive_dir = os.path.join(tmpdir, "raw_archive")
        reg_dir = os.path.join(tmpdir, "dataset_registry")

        storage = StorageRegistry(base_lake_dir=lake_dir, raw_archive_dir=archive_dir)
        dataset_reg = DatasetRegistry()

        collector = MockEquityCollector()
        framework = HistoricalBackfillFramework(
            collector=collector,
            storage_registry=storage,
            dataset_registry=dataset_reg,
        )

        manifest = framework.run_backfill_chunk(
            exchange="NSE_EQ",
            symbol="RELIANCE",
            year="2021",
            month="03",
            start_date="2021-03-01",
            end_date="2021-03-31",
        )

        assert manifest is not None
        assert manifest.dataset_id == "CANONICAL-EQUITIES-RELIANCE-2021-03"
        assert manifest.row_count == 2

        # Verify Parquet Lake storage file creation
        partition_path = storage.get_canonical_partition_path("NSE_EQ", "RELIANCE", "2021", "03", "EQUITIES")
        assert os.path.exists(partition_path)

        pf = pq.ParquetFile(partition_path)
        table = pf.read()
        del pf
        assert table.num_rows == 2
        assert table.column("symbol")[0].as_py() == "RELIANCE"

        # Verify DatasetRegistry entry
        entries = dataset_reg.list_datasets(symbol="RELIANCE")
        assert len(entries) >= 1
        assert any(e["dataset_id"] == "CANONICAL-EQUITIES-RELIANCE-2021-03" for e in entries)


if __name__ == "__main__":
    test_sprint_d1_backfill_framework_integration()
    print("\nSPRINT D1 INTEGRATION TEST PASSED SUCCESSFULLY!")
