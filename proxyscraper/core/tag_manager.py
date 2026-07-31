from __future__ import annotations

import json
import logging
from pathlib import Path

from .events import EventBus, EventType

logger = logging.getLogger(__name__)


class TagManager:
    def __init__(self, tag_file: str = "tags.json", event_bus: EventBus | None = None) -> None:
        self.tag_file = Path(tag_file)
        self.event_bus = event_bus
        self.tags: list[str] = self._load_tags()

    def _load_tags(self) -> list[str]:
        if not self.tag_file.exists():
            logger.info("Tag file %s not found, starting with empty tags", self.tag_file)
            return []
        try:
            with open(self.tag_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            tags = data.get("search_tags", [])
            logger.info("Loaded %d tags from %s", len(tags), self.tag_file)
            return tags
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to load tags from %s: %s", self.tag_file, e)
            return []

    def _save_tags(self) -> None:
        try:
            with open(self.tag_file, "w", encoding="utf-8") as f:
                json.dump({"search_tags": self.tags}, f, indent=2, ensure_ascii=False)
        except OSError as e:
            logger.error("Failed to save tags to %s: %s", self.tag_file, e)

    def add_tag(self, tag: str) -> bool:
        tag = tag.strip()
        if not tag or tag in self.tags:
            return False
        self.tags.append(tag)
        self._save_tags()
        if self.event_bus:
            self.event_bus.emit(EventType.TAG_ADDED, tag=tag)
        return True

    def remove_tag(self, tag: str) -> bool:
        if tag not in self.tags:
            return False
        self.tags.remove(tag)
        self._save_tags()
        if self.event_bus:
            self.event_bus.emit(EventType.TAG_REMOVED, tag=tag)
        return True

    def get_tags(self) -> list[str]:
        return list(self.tags)

    def set_tags(self, tags: list[str]) -> None:
        self.tags = list(tags)
        self._save_tags()
