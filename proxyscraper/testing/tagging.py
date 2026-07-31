from __future__ import annotations

import logging

from proxyscraper.core.models import Proxy, TagRule

logger = logging.getLogger(__name__)

DEFAULT_RULES: list[TagRule] = [
    TagRule(name="proto_http", field="protocols", operator="contains", value="http", tag="http"),
    TagRule(name="proto_https", field="protocols", operator="contains", value="https", tag="https"),
    TagRule(name="proto_socks4", field="protocols", operator="contains", value="socks4", tag="socks4"),
    TagRule(name="proto_socks5", field="protocols", operator="contains", value="socks5", tag="socks5"),
    TagRule(name="anon_transparent", field="anonymity", operator="==", value="transparent", tag="transparent"),
    TagRule(name="anon_anonymous", field="anonymity", operator="==", value="anonymous", tag="anonymous"),
    TagRule(name="anon_elite", field="anonymity", operator="==", value="elite", tag="elite"),
    TagRule(name="speed_fast", field="latency_ms", operator="<", value=1000, tag="fast"),
    TagRule(name="speed_medium", field="latency_ms", operator="<=", value=3000, tag="medium"),
    TagRule(name="speed_slow", field="latency_ms", operator=">", value=3000, tag="slow"),
]


class TagEngine:
    def __init__(self, custom_rules: list[TagRule] | None = None) -> None:
        self.rules = list(DEFAULT_RULES)
        if custom_rules:
            self.rules.extend(custom_rules)

    def apply_tags(self, proxy: Proxy) -> set[str]:
        tags: set[str] = set()

        for rule in self.rules:
            if rule.matches(proxy):
                tags.add(rule.tag)

        if proxy.country:
            tags.add(f"country:{proxy.country}")

        for name, result in proxy.target_checks.items():
            if result == "passed":
                tags.add(f"{name}-passed")

        proxy.tags = tags
        return tags

    def apply_tags_batch(self, proxies: list[Proxy]) -> None:
        for proxy in proxies:
            self.apply_tags(proxy)

    def add_rule(self, rule: TagRule) -> None:
        self.rules.append(rule)

    def remove_rule(self, name: str) -> bool:
        original_len = len(self.rules)
        self.rules = [r for r in self.rules if r.name != name]
        return len(self.rules) < original_len
