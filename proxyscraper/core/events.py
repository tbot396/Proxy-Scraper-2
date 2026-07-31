from __future__ import annotations

import enum
import logging
import threading
from collections import defaultdict
from typing import Any, Callable

logger = logging.getLogger(__name__)


class EventType(enum.Enum):
    PROXY_FOUND = "proxy_found"
    PROXY_TESTED = "proxy_tested"
    PROXY_DEAD = "proxy_dead"
    SCAN_PROGRESS = "scan_progress"
    SCAN_COMPLETE = "scan_complete"
    HARVEST_PROGRESS = "harvest_progress"
    HARVEST_COMPLETE = "harvest_complete"
    TEST_PROGRESS = "test_progress"
    TEST_COMPLETE = "test_complete"
    EXPORT_COMPLETE = "export_complete"
    SERVER_STARTED = "server_started"
    SERVER_STOPPED = "server_stopped"
    SERVER_CONNECTION = "server_connection"
    SERVER_ROTATION = "server_rotation"
    TAG_ADDED = "tag_added"
    TAG_REMOVED = "tag_removed"
    SEARCH_ENGINE_CHANGED = "search_engine_changed"
    CONFIG_UPDATED = "config_updated"
    ERROR = "error"
    LOG = "log"


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[EventType, list[Callable[..., Any]]] = defaultdict(list)
        self._lock = threading.Lock()

    def subscribe(self, event_type: EventType, callback: Callable[..., Any]) -> None:
        with self._lock:
            self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: EventType, callback: Callable[..., Any]) -> None:
        with self._lock:
            try:
                self._subscribers[event_type].remove(callback)
            except ValueError:
                pass

    def emit(self, event_type: EventType, **data: Any) -> None:
        with self._lock:
            callbacks = list(self._subscribers[event_type])
        for cb in callbacks:
            try:
                cb(**data)
            except Exception:
                logger.exception("Event handler error for %s", event_type.value)

    def clear(self) -> None:
        with self._lock:
            self._subscribers.clear()
