from __future__ import annotations

import asyncio
import logging
import os
import re
import time

from proxyscraper.core.config import ExportConfig, ExportSink
from proxyscraper.core.events import EventBus, EventType
from proxyscraper.core.models import Proxy
from proxyscraper.export.file_export import FileExporter
from proxyscraper.export.ftp_export import FTPExporter
from proxyscraper.export.http_export import HTTPExporter
from proxyscraper.export.mail_export import MailExporter

logger = logging.getLogger(__name__)

_TRIGGER_PATTERN = re.compile(
    r"^(\w+)\s*(>=|<=|>|<|==|!=)\s*(\d+)$"
)


def evaluate_trigger(trigger: str, proxies: list[Proxy]) -> bool:
    if not trigger:
        return True

    match = _TRIGGER_PATTERN.match(trigger.strip())
    if not match:
        logger.warning("Invalid trigger expression: %s", trigger)
        return True

    metric_name, operator, threshold_str = match.groups()
    threshold = int(threshold_str)

    value = _compute_metric(metric_name, proxies)

    ops = {
        ">=": lambda a, b: a >= b,
        "<=": lambda a, b: a <= b,
        ">": lambda a, b: a > b,
        "<": lambda a, b: a < b,
        "==": lambda a, b: a == b,
        "!=": lambda a, b: a != b,
    }
    result = ops[operator](value, threshold)
    logger.debug("Trigger '%s': %d %s %d = %s", trigger, value, operator, threshold, result)
    return result


def _compute_metric(name: str, proxies: list[Proxy]) -> int:
    if name == "total":
        return len(proxies)
    if name == "alive":
        return sum(1 for p in proxies if p.alive)

    # new_<tag> — count proxies with that tag
    if name.startswith("new_"):
        tag = name[4:]
        return sum(1 for p in proxies if tag in p.tags)

    # count_<tag>
    if name.startswith("count_"):
        tag = name[6:]
        return sum(1 for p in proxies if tag in p.tags)

    # Direct tag name match
    return sum(1 for p in proxies if name in p.tags)


class ExportManager:
    def __init__(
        self,
        config: ExportConfig,
        event_bus: EventBus | None = None,
    ) -> None:
        self.config = config
        self.event_bus = event_bus
        self._last_export: dict[int, float] = {}

    def export_all(self, proxies: list[Proxy]) -> None:
        for i, sink in enumerate(self.config.sinks):
            self._export_sink(sink, proxies, sink_index=i)

    def export_due(self, proxies: list[Proxy]) -> None:
        now = time.monotonic()
        for i, sink in enumerate(self.config.sinks):
            interval = sink.interval_seconds
            if interval <= 0:
                continue
            last = self._last_export.get(i, 0)
            if now - last >= interval:
                self._export_sink(sink, proxies, sink_index=i)

    def _export_sink(self, sink: ExportSink, proxies: list[Proxy], sink_index: int = 0) -> None:
        if sink.only_tags:
            req = set(sink.only_tags)
            proxies = [p for p in proxies if req & p.tags]

        if not evaluate_trigger(sink.trigger, proxies):
            logger.debug("Trigger not met for sink %d, skipping", sink_index)
            return

        try:
            if sink.type == "file":
                FileExporter().export(proxies, sink.path, sink.format)
            elif sink.type == "ftp":
                FTPExporter(
                    host=sink.host,
                    remote_path=sink.remote_path,
                ).export(proxies, sink.format or "txt")
            elif sink.type == "email":
                MailExporter(
                    smtp_host=sink.smtp_host,
                    smtp_port=sink.smtp_port,
                    smtp_user=sink.smtp_user,
                    smtp_pass=sink.smtp_pass,
                    to_addrs=sink.to,
                ).export(proxies, sink.format or "txt")
            elif sink.type == "http":
                auth = sink.auth_header
                # Expand env vars like ${SEO_TOKEN}
                auth = re.sub(
                    r"\$\{(\w+)\}",
                    lambda m: os.environ.get(m.group(1), m.group(0)),
                    auth,
                )
                exporter = HTTPExporter(
                    url=sink.url,
                    method=sink.method,
                    auth_header=auth,
                )
                asyncio.get_event_loop().run_until_complete(exporter.export(proxies))
            else:
                logger.warning("Unknown export sink type: %s", sink.type)
                return

            self._last_export[sink_index] = time.monotonic()

            if self.event_bus:
                self.event_bus.emit(
                    EventType.EXPORT_COMPLETE,
                    sink_type=sink.type, count=len(proxies),
                )
        except Exception as e:
            logger.error("Export failed for sink %s: %s", sink.type, e)
