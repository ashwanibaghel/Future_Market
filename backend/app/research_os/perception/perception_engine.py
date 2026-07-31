import time
import logging
from typing import Dict, Any, List, Optional
from app.research_os.perception.perception_version import DEFAULT_PERCEPTION_VERSION
from app.research_os.perception.base_perception import BasePerceptionModule
from app.research_os.perception.perception_frame import PerceptionFrame
from app.research_os.perception.perception_diagnostics import PerceptionDiagnostics, ModuleDiagnostic
from app.research_os.perception.perception_registry import PerceptionRegistry
from app.research_os.strategy.strategy_context import StrategyContext

logger = logging.getLogger("research_os.perception.engine")


class PerceptionEngine:
    """
    Perception Engine Orchestrator.
    Accepts snapshot events from Replay Engine, executes registered perception modules
    in topological dependency order with plugin error boundaries, constructs explainable
    PerceptionFrames, and binds them to StrategyContext.
    """

    def __init__(self, modules: Optional[List[BasePerceptionModule]] = None):
        self.modules: List[BasePerceptionModule] = modules or []
        self.perception_version = DEFAULT_PERCEPTION_VERSION
        self._sorted_modules: List[BasePerceptionModule] = []
        self._re_resolve_modules()

    def register_module(self, module: BasePerceptionModule):
        """Registers and initializes an active perception module instance."""
        module.initialize()
        self.modules.append(module)
        self._re_resolve_modules()

    def _re_resolve_modules(self):
        """Requirement 3: Resolves topological dependency execution order."""
        if self.modules:
            self._sorted_modules = PerceptionRegistry.resolve_topological_execution_order(self.modules)

    def process_snapshot(
        self,
        snapshot: Dict[str, Any],
        session_id: str = "SESS-PERCEPTION",
        feature_version: str = "F-v1.0.0",
        replay_version: str = "R-v1.0.0",
    ) -> PerceptionFrame:
        """
        Main Perception Pipeline execution tick.
        Runs all active modules with error boundaries and generates an explainable PerceptionFrame.
        """
        ts = str(snapshot.get("replay_timestamp", snapshot.get("timestamp", "")))
        ts_utc = int(snapshot.get("timestamp_utc", 0))
        symbol = str(snapshot.get("symbol", "NIFTY")).upper()

        perceptions: Dict[str, Any] = {}
        diagnostics = PerceptionDiagnostics()
        executed_modules: List[str] = []

        # Execute topologically sorted perception modules
        for mod in self._sorted_modules:
            mod_name = mod.module_name
            t0 = time.monotonic()

            # Check missing feature requirements
            missing = [f for f in mod.required_features if f not in snapshot]
            warnings = []
            if missing:
                warnings.append(f"Missing required features: {missing}")

            # Requirement 7: Plugin Failure Isolation Boundary
            try:
                out = mod.process_snapshot(snapshot, perceptions)
                t1 = time.monotonic()
                dur_ms = (t1 - t0) * 1000.0

                # Requirement 1 & 2: Verify explainability fields (Observation Only)
                conf = float(out.get("confidence", 1.0))
                evidence = str(out.get("evidence", "No evidence string provided."))
                meta = out.get("metadata", {})

                perceptions[mod_name] = {
                    "module_name": mod_name,
                    "module_version": mod.module_version,
                    "confidence": conf,
                    "evidence": evidence,
                    "metadata": meta,
                }
                executed_modules.append(mod_name)

                # Requirement 8: Record Success Diagnostic
                diagnostics.add_diagnostic(ModuleDiagnostic(
                    module_name=mod_name,
                    execution_time_ms=dur_ms,
                    status="SUCCESS",
                    warnings=warnings,
                    missing_features=missing,
                ))

            except Exception as exc:
                t1 = time.monotonic()
                dur_ms = (t1 - t0) * 1000.0
                err_msg = str(exc)
                logger.error("Requirement 7 Plugin Failure Isolated: Perception Module '%s' failed: %s", mod_name, err_msg)

                # Requirement 8: Record Failure Diagnostic without crashing replay
                diagnostics.add_diagnostic(ModuleDiagnostic(
                    module_name=mod_name,
                    execution_time_ms=dur_ms,
                    status="FAILED",
                    warnings=warnings,
                    missing_features=missing,
                    error_message=err_msg,
                ))

        frame_id = f"PERC-{symbol}-{ts_utc}"

        frame = PerceptionFrame(
            frame_id=frame_id,
            timestamp=ts,
            timestamp_utc=ts_utc,
            symbol=symbol,
            perception_version=self.perception_version,
            feature_version=feature_version,
            replay_version=replay_version,
            executed_modules=executed_modules,
            perceptions=perceptions,
            diagnostics=diagnostics.to_dict(),
        )
        return frame

    def enrich_strategy_context(self, context: StrategyContext, frame: PerceptionFrame):
        """Binds synthesized PerceptionFrame to StrategyContext."""
        context.snapshot["perception_frame"] = frame.to_dict()
