import logging
from typing import Dict, Any, List, Optional, Type
from app.acquisition.framework.base_collector import BaseCollectorPlugin

logger = logging.getLogger("acquisition.framework.data_source_registry")


class DataSourceRegistry:
    """Central registry for discovering, registering, and retrieving data collector plugins."""

    _collectors: Dict[str, Type[BaseCollectorPlugin]] = {}

    @classmethod
    def register_collector(cls, collector_cls: Type[BaseCollectorPlugin]):
        temp_inst = collector_cls()
        name = temp_inst.source_name
        cls._collectors[name] = collector_cls
        logger.info("Registered Data Collector Plugin '%s' (Asset Type: %s)", name, temp_inst.asset_type)

    @classmethod
    def get_collector_class(cls, source_name: str) -> Optional[Type[BaseCollectorPlugin]]:
        return cls._collectors.get(source_name)

    @classmethod
    def list_collectors(cls) -> List[Dict[str, Any]]:
        results = []
        for name, collector_cls in cls._collectors.items():
            inst = collector_cls()
            results.append({
                "source_name": inst.source_name,
                "asset_type": inst.asset_type,
                "schema_fields": [field.name for field in inst.canonical_schema],
            })
        return results
