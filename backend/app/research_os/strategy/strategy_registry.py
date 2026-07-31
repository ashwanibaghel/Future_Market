import logging
from typing import Dict, Any, List, Optional, Type
from app.research_os.strategy.base_strategy import BaseStrategyPlugin

logger = logging.getLogger("research_os.strategy.registry")


class StrategyRegistry:
    """
    Deliverable 2 Strategy Registry & Validator.
    Handles discovery, registration, instantiation, and pre-execution compatibility checks.
    """

    _registry: Dict[str, Type[BaseStrategyPlugin]] = {}

    @classmethod
    def register_strategy(cls, strategy_cls: Type[BaseStrategyPlugin]):
        """Registers a strategy class into the global registry."""
        temp_inst = strategy_cls()
        manifest = temp_inst.manifest
        key = f"{manifest.strategy_name}:{manifest.strategy_version}"
        cls._registry[key] = strategy_cls
        logger.info("Registered Strategy Plugin '%s' (v%s)", manifest.strategy_name, manifest.strategy_version)

    @classmethod
    def get_strategy_class(cls, name: str, version: str) -> Optional[Type[BaseStrategyPlugin]]:
        """Retrieves a registered strategy class by name and version."""
        key = f"{name}:{version}"
        return cls._registry.get(key)

    @classmethod
    def list_strategies(cls) -> List[Dict[str, Any]]:
        """Lists metadata of all registered strategies."""
        results = []
        for key, strategy_cls in cls._registry.items():
            inst = strategy_cls()
            results.append(inst.manifest.to_dict())
        return results

    @classmethod
    def validate_strategy_compatibility(cls, strategy: BaseStrategyPlugin, available_features: List[str], feature_version: str) -> bool:
        """
        Requirement 3 Pre-Execution Strategy Validation.
        Validates required features and minimum feature version string before replay starts.
        """
        manifest = strategy.manifest

        # Check feature version string
        if feature_version < manifest.minimum_feature_version:
            raise ValueError(
                f"Strategy Validation Error: Strategy '{manifest.strategy_name}' requires feature_version >= "
                f"'{manifest.minimum_feature_version}', but current dataset is '{feature_version}'."
            )

        # Check required features
        for req_f in manifest.required_features:
            if req_f not in available_features:
                raise ValueError(
                    f"Strategy Validation Error: Strategy '{manifest.strategy_name}' requires feature column '{req_f}', "
                    f"which is missing in available dataset features: {available_features}."
                )

        return True
