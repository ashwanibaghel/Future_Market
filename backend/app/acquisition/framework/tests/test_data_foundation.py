import pyarrow as pa
from app.acquisition.framework.provenance import DataProvenance
from app.acquisition.framework.dataset_manifest import DatasetManifest
from app.acquisition.framework.canonical_schema_registry import CanonicalSchemaRegistry, EQUITY_CANDLE_SCHEMA
from app.acquisition.framework.data_source_registry import DataSourceRegistry
from app.acquisition.framework.base_collector import BaseCollectorPlugin


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
                pa.array(["2021-03-01T09:15:00+05:30"], type=pa.string()),
                pa.array([1614570300], type=pa.int64()),
                pa.array([symbol.upper()], type=pa.string()),
                pa.array(["NSE"], type=pa.string()),
                pa.array([2500.0], type=pa.float64()),
                pa.array([2510.0], type=pa.float64()),
                pa.array([2495.0], type=pa.float64()),
                pa.array([2505.0], type=pa.float64()),
                pa.array([10000], type=pa.int64()),
                pa.array([2504.0], type=pa.float64()),
                pa.array(["MOCK"], type=pa.string()),
            ],
            schema=EQUITY_CANDLE_SCHEMA,
        )


def test_provenance_and_manifest():
    prov = DataProvenance.create("MOCK_PROVIDER", b"sample content", latency_ms=12.5)
    assert prov.provider == "MOCK_PROVIDER"
    assert len(prov.sha256_checksum) == 64

    manifest = DatasetManifest(
        dataset_id="DS-EQUITY-RELIANCE-2021-03",
        dataset_version="D-v1.0.0",
        schema_version="CS-v1.0.0",
        provider="MOCK_PROVIDER",
        symbols=["RELIANCE"],
        asset_type="EQUITIES",
        time_range={"start_date": "2021-03-01", "end_date": "2021-03-31"},
        row_count=100,
        checksum=prov.sha256_checksum,
    )
    assert manifest.dataset_id == "DS-EQUITY-RELIANCE-2021-03"
    assert manifest.asset_type == "EQUITIES"


def test_schema_and_collector_registry():
    schema = CanonicalSchemaRegistry.get_schema("EQUITIES")
    assert schema is not None
    assert "close" in [f.name for f in schema]

    DataSourceRegistry.register_collector(MockEquityCollector)
    collectors = DataSourceRegistry.list_collectors()
    assert len(collectors) >= 1
    assert collectors[0]["source_name"] == "MOCK_EQUITY_COLLECTOR"


if __name__ == "__main__":
    test_provenance_and_manifest()
    test_schema_and_collector_registry()
    print("\nALL DATA FOUNDATION UNIT TESTS PASSED SUCCESSFULLY!")
