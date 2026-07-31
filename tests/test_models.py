from __future__ import annotations

import json
from datetime import datetime

from proxyscraper.core.models import (
    AnonymityLevel,
    Proxy,
    ProxyProtocol,
    RotationStrategy,
    Source,
    TagRule,
    TestResult,
)


class TestProxy:
    def test_address(self):
        p = Proxy(ip="1.2.3.4", port=8080)
        assert p.address == "1.2.3.4:8080"

    def test_defaults(self):
        p = Proxy(ip="1.2.3.4", port=80)
        assert p.protocols == []
        assert p.anonymity is None
        assert p.latency_ms is None
        assert p.tags == set()
        assert p.alive is False
        assert p.target_checks == {}

    def test_to_row_from_row_roundtrip(self):
        p = Proxy(
            ip="1.2.3.4",
            port=8080,
            source_url="http://example.com",
            protocols=["http", "socks5"],
            anonymity="elite",
            latency_ms=150,
            country="DE",
            city="Berlin",
            asn="12345",
            org="Example ISP",
            tags={"fast", "elite"},
            first_seen=datetime(2026, 1, 1),
            last_checked=datetime(2026, 1, 2),
            alive=True,
            target_checks={"google": "passed"},
        )
        row = p.to_row()
        assert len(row) == 15

        restored = Proxy.from_row(row)
        assert restored.ip == p.ip
        assert restored.port == p.port
        assert restored.protocols == p.protocols
        assert restored.anonymity == p.anonymity
        assert restored.latency_ms == p.latency_ms
        assert restored.country == p.country
        assert restored.tags == p.tags
        assert restored.alive == p.alive
        assert restored.target_checks == p.target_checks

    def test_to_row_none_values(self):
        p = Proxy(ip="1.2.3.4", port=80)
        row = p.to_row()
        restored = Proxy.from_row(row)
        assert restored.anonymity is None
        assert restored.latency_ms is None
        assert restored.last_checked is None


class TestSource:
    def test_to_row_from_row_roundtrip(self):
        s = Source(url="http://example.com", last_crawled=datetime(2026, 1, 1), proxy_count=42, enabled=True)
        row = s.to_row()
        restored = Source.from_row(row)
        assert restored.url == s.url
        assert restored.proxy_count == 42
        assert restored.enabled is True

    def test_defaults(self):
        s = Source(url="http://example.com")
        assert s.last_crawled is None
        assert s.proxy_count == 0
        assert s.enabled is True


class TestTagRule:
    def test_matches_equality(self):
        rule = TagRule(name="test", field="country", operator="==", value="DE", tag="german")
        p = Proxy(ip="1.2.3.4", port=80, country="DE")
        assert rule.matches(p) is True

        p2 = Proxy(ip="1.2.3.4", port=80, country="US")
        assert rule.matches(p2) is False

    def test_matches_less_than(self):
        rule = TagRule(name="fast", field="latency_ms", operator="<", value=1000, tag="fast")
        p = Proxy(ip="1.2.3.4", port=80, latency_ms=500)
        assert rule.matches(p) is True

        p2 = Proxy(ip="1.2.3.4", port=80, latency_ms=1500)
        assert rule.matches(p2) is False

    def test_matches_contains(self):
        rule = TagRule(name="has_http", field="protocols", operator="contains", value="http", tag="http")
        p = Proxy(ip="1.2.3.4", port=80, protocols=["http", "socks5"])
        assert rule.matches(p) is True

        p2 = Proxy(ip="1.2.3.4", port=80, protocols=["socks5"])
        assert rule.matches(p2) is False

    def test_matches_none_field(self):
        rule = TagRule(name="test", field="country", operator="==", value="DE", tag="de")
        p = Proxy(ip="1.2.3.4", port=80)
        assert rule.matches(p) is False

    def test_matches_invalid_operator(self):
        rule = TagRule(name="test", field="port", operator="??", value=80, tag="bad")
        p = Proxy(ip="1.2.3.4", port=80)
        assert rule.matches(p) is False


class TestEnums:
    def test_proxy_protocol_values(self):
        assert ProxyProtocol.HTTP.value == "http"
        assert ProxyProtocol.SOCKS5.value == "socks5"

    def test_anonymity_level_values(self):
        assert AnonymityLevel.ELITE.value == "elite"
        assert AnonymityLevel.TRANSPARENT.value == "transparent"

    def test_rotation_strategy_values(self):
        assert RotationStrategy.PER_REQUEST.value == "per_request"
        assert RotationStrategy.STICKY.value == "sticky"
