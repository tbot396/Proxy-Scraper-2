from __future__ import annotations

import ipaddress
import logging
from pathlib import Path

from proxyscraper.core.config import FiltersConfig
from proxyscraper.core.models import Proxy
from proxyscraper.core.storage import Storage

logger = logging.getLogger(__name__)


class ProxyFilter:
    def __init__(self, config: FiltersConfig, storage: Storage) -> None:
        self.config = config
        self.storage = storage
        self._blocklist: set[str] = set()
        self._blocklist_networks: list[ipaddress.IPv4Network] = []
        self._load_blocklists()

    def _load_blocklists(self) -> None:
        for path_str in self.config.security.blocklist_files:
            path = Path(path_str)
            if not path.exists():
                logger.warning("Blocklist file not found: %s", path)
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "/" in line:
                            try:
                                self._blocklist_networks.append(
                                    ipaddress.IPv4Network(line, strict=False)
                                )
                            except ValueError:
                                pass
                        else:
                            self._blocklist.add(line)
                logger.info("Loaded blocklist: %s", path)
            except OSError as e:
                logger.error("Failed to load blocklist %s: %s", path, e)

    def is_blocked(self, proxy: Proxy) -> bool:
        if proxy.ip in self._blocklist:
            return True

        try:
            addr = ipaddress.ip_address(proxy.ip)
            if any(addr in net for net in self._blocklist_networks):
                return True
        except ValueError:
            pass

        if proxy.asn and proxy.asn in self.config.security.exclude_asns:
            return True

        return False

    def matches_country(self, proxy: Proxy) -> bool:
        if not self.config.country.countries:
            return True
        if not proxy.country:
            return self.config.country.mode == "block"

        in_list = proxy.country in self.config.country.countries
        if self.config.country.mode == "allow":
            return in_list
        return not in_list

    def matches_speed(self, proxy: Proxy) -> bool:
        if proxy.latency_ms is None:
            return True
        return proxy.latency_ms <= self.config.speed.max_latency_ms

    def filter(self, proxies: list[Proxy] | None = None) -> list[Proxy]:
        if proxies is None:
            proxies = self.storage.get_proxies(alive_only=True)

        results = []
        for proxy in proxies:
            if self.is_blocked(proxy):
                continue
            if not self.matches_country(proxy):
                continue
            if not self.matches_speed(proxy):
                continue
            results.append(proxy)

        logger.info("Filtered %d -> %d proxies", len(proxies), len(results))
        return results

    def filter_by_tags(
        self,
        proxies: list[Proxy],
        require_tags: list[str] | None = None,
        exclude_tags: list[str] | None = None,
    ) -> list[Proxy]:
        results = proxies
        if require_tags:
            req = set(require_tags)
            results = [p for p in results if req <= p.tags]
        if exclude_tags:
            exc = set(exclude_tags)
            results = [p for p in results if not (exc & p.tags)]
        return results
