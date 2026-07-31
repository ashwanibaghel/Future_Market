from dataclasses import dataclass, field
from typing import Dict, Any, List


@dataclass
class ModuleDiagnostic:
    """Diagnostic telemetry for a single perception module execution."""
    module_name: str
    execution_time_ms: float
    status: str  # SUCCESS, FAILED, SKIPPED
    warnings: List[str] = field(default_factory=list)
    missing_features: List[str] = field(default_factory=list)
    error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_name": self.module_name,
            "execution_time_ms": round(self.execution_time_ms, 3),
            "status": self.status,
            "warnings": self.warnings,
            "missing_features": self.missing_features,
            "error_message": self.error_message,
        }


@dataclass
class PerceptionDiagnostics:
    """
    Requirement 8 Perception Diagnostics Container.
    Tracks module-level performance, failure isolation logs, and missing feature warnings.
    """
    total_execution_time_ms: float = 0.0
    module_diagnostics: Dict[str, ModuleDiagnostic] = field(default_factory=dict)

    def add_diagnostic(self, diag: ModuleDiagnostic):
        self.module_diagnostics[diag.module_name] = diag
        self.total_execution_time_ms += diag.execution_time_ms

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_execution_time_ms": round(self.total_execution_time_ms, 3),
            "module_diagnostics": {k: v.to_dict() for k, v in self.module_diagnostics.items()},
        }
