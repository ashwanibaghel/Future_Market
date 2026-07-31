import logging
from typing import Dict, Any, List, Optional
from app.acquisition.framework.base_collector import BaseCollectorPlugin

logger = logging.getLogger("acquisition.framework.live")


class LiveCollectionFramework:
    """Generic Live Streaming Collection Framework Coordinator."""

    def __init__(self, collector: BaseCollectorPlugin):
        self.collector = collector

    def start_live_collection(self):
        """Starts live collection loop for stream ticks."""
        logger.info("Started live collection framework for collector '%s'", self.collector.source_name)
        for tick in self.collector.stream_live_tick():
            if tick:
                logger.debug("Live tick received: %s", tick)
