from __future__ import annotations

from proxyscraper.core.models import Proxy, TagRule
from proxyscraper.testing.tagging import TagEngine


class TestTagEngine:
    def test_default_protocol_tags(self):
        engine = TagEngine()
        p = Proxy(ip="1.2.3.4", port=80, protocols=["http", "socks5"])
        tags = engine.apply_tags(p)
        assert "http" in tags
        assert "socks5" in tags
        assert "socks4" not in tags

    def test_anonymity_tags(self):
        engine = TagEngine()
        p = Proxy(ip="1.2.3.4", port=80, anonymity="elite")
        tags = engine.apply_tags(p)
        assert "elite" in tags
        assert "anonymous" not in tags

    def test_speed_tags(self):
        engine = TagEngine()

        fast = Proxy(ip="1.2.3.4", port=80, latency_ms=500)
        tags = engine.apply_tags(fast)
        assert "fast" in tags
        assert "medium" in tags

        slow = Proxy(ip="5.6.7.8", port=80, latency_ms=5000)
        tags = engine.apply_tags(slow)
        assert "slow" in tags
        assert "fast" not in tags

    def test_country_tags(self):
        engine = TagEngine()
        p = Proxy(ip="1.2.3.4", port=80, country="DE")
        tags = engine.apply_tags(p)
        assert "country:DE" in tags

    def test_target_check_tags(self):
        engine = TagEngine()
        p = Proxy(ip="1.2.3.4", port=80, target_checks={"google": "passed", "bing": "failed"})
        tags = engine.apply_tags(p)
        assert "google-passed" in tags
        assert "bing-passed" not in tags

    def test_custom_rule(self):
        rule = TagRule(name="german_fast", field="country", operator="==", value="DE", tag="de-fast")
        engine = TagEngine(custom_rules=[rule])
        p = Proxy(ip="1.2.3.4", port=80, country="DE")
        tags = engine.apply_tags(p)
        assert "de-fast" in tags

    def test_apply_tags_batch(self):
        engine = TagEngine()
        proxies = [
            Proxy(ip="1.2.3.4", port=80, protocols=["http"], country="US"),
            Proxy(ip="5.6.7.8", port=80, protocols=["socks5"], country="DE"),
        ]
        engine.apply_tags_batch(proxies)
        assert "http" in proxies[0].tags
        assert "country:US" in proxies[0].tags
        assert "socks5" in proxies[1].tags
        assert "country:DE" in proxies[1].tags

    def test_add_remove_rule(self):
        engine = TagEngine()
        initial_count = len(engine.rules)

        rule = TagRule(name="custom", field="port", operator="==", value=8080, tag="port8080")
        engine.add_rule(rule)
        assert len(engine.rules) == initial_count + 1

        assert engine.remove_rule("custom") is True
        assert len(engine.rules) == initial_count

        assert engine.remove_rule("nonexistent") is False
