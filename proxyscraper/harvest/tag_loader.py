from __future__ import annotations

import logging

from proxyscraper.core.tag_manager import TagManager

logger = logging.getLogger(__name__)


class TagLoader:
    def __init__(self, tag_manager: TagManager) -> None:
        self.tag_manager = tag_manager

    def get_search_queries(self, base_queries: list[str] | None = None) -> list[str]:
        tags = self.tag_manager.get_tags()
        queries = list(base_queries or [])
        for tag in tags:
            if tag not in queries:
                queries.append(tag)
        logger.debug("Prepared %d search queries (%d from tags)", len(queries), len(tags))
        return queries
