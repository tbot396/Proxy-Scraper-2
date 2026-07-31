from __future__ import annotations

import csv
import json
import logging
from io import StringIO
from pathlib import Path

from proxyscraper.core.models import Proxy

logger = logging.getLogger(__name__)


class FileExporter:
    def export(self, proxies: list[Proxy], path: str, fmt: str = "txt") -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)

        if fmt == "txt":
            self._export_txt(proxies, path)
        elif fmt == "csv":
            self._export_csv(proxies, path)
        elif fmt == "json":
            self._export_json(proxies, path)
        else:
            raise ValueError(f"Unknown export format: {fmt}")

        logger.info("Exported %d proxies to %s (%s)", len(proxies), path, fmt)

    def to_string(self, proxies: list[Proxy], fmt: str = "txt") -> str:
        if fmt == "txt":
            return "\n".join(p.address for p in proxies)
        elif fmt == "csv":
            return self._csv_string(proxies)
        elif fmt == "json":
            return json.dumps(
                [self._proxy_dict(p) for p in proxies], indent=2, ensure_ascii=False
            )
        raise ValueError(f"Unknown export format: {fmt}")

    def _export_txt(self, proxies: list[Proxy], path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            for p in proxies:
                f.write(f"{p.address}\n")

    def _export_csv(self, proxies: list[Proxy], path: str) -> None:
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "ip", "port", "protocols", "anonymity", "latency_ms",
                "country", "city", "asn", "org", "tags",
            ])
            for p in proxies:
                writer.writerow([
                    p.ip, p.port, ",".join(p.protocols), p.anonymity or "",
                    p.latency_ms or "", p.country or "", p.city or "",
                    p.asn or "", p.org or "", ",".join(sorted(p.tags)),
                ])

    def _export_json(self, proxies: list[Proxy], path: str) -> None:
        data = [self._proxy_dict(p) for p in proxies]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _csv_string(self, proxies: list[Proxy]) -> str:
        buf = StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "ip", "port", "protocols", "anonymity", "latency_ms",
            "country", "city", "asn", "org", "tags",
        ])
        for p in proxies:
            writer.writerow([
                p.ip, p.port, ",".join(p.protocols), p.anonymity or "",
                p.latency_ms or "", p.country or "", p.city or "",
                p.asn or "", p.org or "", ",".join(sorted(p.tags)),
            ])
        return buf.getvalue()

    @staticmethod
    def _proxy_dict(p: Proxy) -> dict:
        return {
            "ip": p.ip,
            "port": p.port,
            "protocols": p.protocols,
            "anonymity": p.anonymity,
            "latency_ms": p.latency_ms,
            "country": p.country,
            "city": p.city,
            "asn": p.asn,
            "org": p.org,
            "tags": sorted(p.tags),
        }
