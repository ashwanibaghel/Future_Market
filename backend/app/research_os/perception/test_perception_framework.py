from typing import Dict, Any, List
from app.research_os.perception.base_perception import BasePerceptionModule
from app.research_os.perception.perception_registry import PerceptionRegistry
from app.research_os.perception.perception_engine import PerceptionEngine


class DummyPatternModule(BasePerceptionModule):
    @property
    def module_name(self) -> str:
        return "dummy_pattern"

    @property
    def module_version(self) -> str:
        return "1.0.0"

    def process_snapshot(self, snapshot: Dict[str, Any], prior_perceptions: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "confidence": 0.92,
            "evidence": "Observed Put Floor Strike Clustering at 14500",
            "metadata": {"put_floor_strike": 14500.0},
        }


class DummyContextModule(BasePerceptionModule):
    @property
    def module_name(self) -> str:
        return "dummy_context"

    @property
    def module_version(self) -> str:
        return "1.0.0"

    @property
    def dependencies(self) -> List[str]:
        return ["dummy_pattern"]  # Depends on dummy_pattern!

    def process_snapshot(self, snapshot: Dict[str, Any], prior_perceptions: Dict[str, Any]) -> Dict[str, Any]:
        pattern_output = prior_perceptions.get("dummy_pattern", {})
        evidence = f"Synthesized context using pattern: {pattern_output.get('evidence', '')}"
        return {
            "confidence": 0.95,
            "evidence": evidence,
            "metadata": {"market_bias": "BULLISH_SUPPORTED"},
        }


class DummyFailingModule(BasePerceptionModule):
    @property
    def module_name(self) -> str:
        return "dummy_failing"

    @property
    def module_version(self) -> str:
        return "1.0.0"

    def process_snapshot(self, snapshot: Dict[str, Any], prior_perceptions: Dict[str, Any]) -> Dict[str, Any]:
        raise RuntimeError("Simulated Plugin Unexpected Failure!")


def test_perception_registry_and_topological_sort():
    PerceptionRegistry.register_module(DummyPatternModule)
    PerceptionRegistry.register_module(DummyContextModule)

    modules = [DummyContextModule(), DummyPatternModule()]  # Intentional reversed order
    sorted_mods = PerceptionRegistry.resolve_topological_execution_order(modules)

    assert len(sorted_mods) == 2
    # Prerequisite dummy_pattern must execute FIRST before dummy_context
    assert sorted_mods[0].module_name == "dummy_pattern"
    assert sorted_mods[1].module_name == "dummy_context"


def test_perception_engine_and_failure_isolation():
    engine = PerceptionEngine()
    engine.register_module(DummyPatternModule())
    engine.register_module(DummyFailingModule())  # Failing module!
    engine.register_module(DummyContextModule())

    snapshot = {
        "replay_timestamp": "2021-03-01T09:15:00+05:30",
        "timestamp_utc": 1614570300,
        "symbol": "NIFTY",
        "spot_price": 14500.0,
    }

    frame = engine.process_snapshot(snapshot)

    # Verify Frame metadata & provenance
    assert frame.symbol == "NIFTY"
    assert frame.perception_version == "P-v1.0.0"
    assert "dummy_pattern" in frame.executed_modules
    assert "dummy_context" in frame.executed_modules
    assert "dummy_failing" not in frame.executed_modules  # Failed module excluded from executed_modules

    # Verify Perception Explainability
    pattern_perc = frame.get_perception("dummy_pattern")
    assert pattern_perc is not None
    assert pattern_perc["confidence"] == 0.92
    assert "Observed Put Floor" in pattern_perc["evidence"]

    # Verify Plugin Failure Isolation Diagnostics (Requirement 7 & 8)
    diag = frame.diagnostics
    assert "dummy_failing" in diag["module_diagnostics"]
    failing_diag = diag["module_diagnostics"]["dummy_failing"]
    assert failing_diag["status"] == "FAILED"
    assert "Simulated Plugin Unexpected Failure!" in failing_diag["error_message"]


if __name__ == "__main__":
    test_perception_registry_and_topological_sort()
    test_perception_engine_and_failure_isolation()
    print("\nALL PERCEPTION FRAMEWORK UNIT TESTS PASSED SUCCESSFULLY!")
