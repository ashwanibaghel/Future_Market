import logging
from typing import Dict, Any, List, Optional, Type
from collections import defaultdict, deque
from app.research_os.perception.base_perception import BasePerceptionModule

logger = logging.getLogger("research_os.perception.registry")


class PerceptionRegistry:
    """
    Requirement 3 Perception Module Registry & Topological Dependency Resolver.
    Supports declaring module dependencies and executes perception modules in topological order.
    """

    _registry: Dict[str, Type[BasePerceptionModule]] = {}

    @classmethod
    def register_module(cls, module_cls: Type[BasePerceptionModule]):
        """Registers a perception module class."""
        temp_inst = module_cls()
        name = temp_inst.module_name
        cls._registry[name] = module_cls
        logger.info("Registered Perception Module '%s' (v%s, Dependencies: %s)", name, temp_inst.module_version, temp_inst.dependencies)

    @classmethod
    def get_module_class(cls, name: str) -> Optional[Type[BasePerceptionModule]]:
        """Retrieves a registered module class by name."""
        return cls._registry.get(name)

    @classmethod
    def list_modules(cls) -> List[Dict[str, Any]]:
        """Lists metadata of all registered perception modules."""
        results = []
        for name, module_cls in cls._registry.items():
            inst = module_cls()
            results.append({
                "module_name": inst.module_name,
                "module_version": inst.module_version,
                "required_features": inst.required_features,
                "dependencies": inst.dependencies,
            })
        return results

    @classmethod
    def resolve_topological_execution_order(cls, module_instances: List[BasePerceptionModule]) -> List[BasePerceptionModule]:
        """
        Requirement 3 Topological Dependency Resolver.
        Sorts perception module instances so that prerequisite dependency modules execute first.
        """
        inst_map = {inst.module_name: inst for inst in module_instances}
        in_degree = {inst.module_name: 0 for inst in module_instances}
        graph = defaultdict(list)

        for inst in module_instances:
            for dep in inst.dependencies:
                if dep in inst_map:
                    graph[dep].append(inst.module_name)
                    in_degree[inst.module_name] += 1
                else:
                    logger.warning("Perception Dependency Warning: Module '%s' depends on '%s', which is not registered.", inst.module_name, dep)

        # Kahn's Topological Sort Algorithm
        queue = deque([node for node, deg in in_degree.items() if deg == 0])
        sorted_names = []

        while queue:
            node = queue.popleft()
            sorted_names.append(node)
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(sorted_names) != len(module_instances):
            logger.error("Perception Dependency Cycle Detected! Falling back to registration order.")
            return module_instances

        return [inst_map[name] for name in sorted_names]
