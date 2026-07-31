from __future__ import annotations

import tempfile
from pathlib import Path

from proxyscraper.core.config import FiltersConfig
from proxyscraper.core.models import Proxy
from proxyscraper.export.filters import ProxyFilter


class TestProxyFilter:
    def _make_filter(self, storage, **kwargs):
        config = FiltersConfig(**kwargs)
        return ProxyFilter(config, storage)

    def test_filter_no_criteria(self, storage, sample_proxies):
        storage.upsert_proxies(sample_proxies)
        pf = self._make_filter(storage)
        result = pf.filter()
        assert len(result) == 2  # only alive

    def test_filter_country_allow(self, storage, sample_proxies):
        storage.upsert_proxies(sample_proxies)
        pf = self._make_filter(storage, country={"mode": "allow", "list": ["DE"]})
        result = pf.filter()
        assert all(p.country == "DE" for p in result)

    def test_filter_country_block(self, storage, sample_proxies):
        storage.upsert_proxies(sample_proxies)
        pf = self._make_filter(storage, country={"mode": "block", "list": ["CN"]})
        result = pf.filter()
        assert all(p.country != "CN" for p in result)

    def test_filter_speed(self, storage, sample_proxies):
        storage.upsert_proxies(sample_proxies)
        pf = self._make_filter(storage, speed={"max_latency_ms": 200})
        result = pf.filter()
        assert all(p.latency_ms <= 200 for p in result if p.latency_ms)

    def test_is_blocked_by_ip(self, storage, tmp_path):
        blocklist = tmp_path / "block.txt"
        blocklist.write_text("1.2.3.4\n")

        pf = self._make_filter(storage, security={"blocklist_files": [str(blocklist)]})
        p = Proxy(ip="1.2.3.4", port=80)
        assert pf.is_blocked(p) is True

        p2 = Proxy(ip="5.6.7.8", port=80)
        assert pf.is_blocked(p2) is False

    def test_is_blocked_by_cidr(self, storage, tmp_path):
        blocklist = tmp_path / "block.txt"
        blocklist.write_text("10.0.0.0/8\n")

        pf = self._make_filter(storage, security={"blocklist_files": [str(blocklist)]})
        p = Proxy(ip="10.1.2.3", port=80)
        assert pf.is_blocked(p) is True

    def test_is_blocked_by_asn(self, storage):
        pf = self._make_filter(storage, security={"exclude_asns": ["12345"]})
        p = Proxy(ip="1.2.3.4", port=80, asn="12345")
        assert pf.is_blocked(p) is True

    def test_filter_by_tags(self, storage):
        proxies = [
            Proxy(ip="1.2.3.4", port=80, tags={"elite", "fast"}),
            Proxy(ip="5.6.7.8", port=80, tags={"slow"}),
        ]
        pf = self._make_filter(storage)

        result = pf.filter_by_tags(proxies, require_tags=["elite"])
        assert len(result) == 1

        result = pf.filter_by_tags(proxies, exclude_tags=["slow"])
        assert len(result) == 1
        assert result[0].ip == "1.2.3.4"
