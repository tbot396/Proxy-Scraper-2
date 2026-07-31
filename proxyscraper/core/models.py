from __future__ import annotations

import enum
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional


class ProxyProtocol(enum.Enum):
    HTTP = "http"
    HTTPS = "https"
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"


class AnonymityLevel(enum.Enum):
    TRANSPARENT = "transparent"
    ANONYMOUS = "anonymous"
    ELITE = "elite"


class RotationStrategy(enum.Enum):
    PER_REQUEST = "per_request"
    STICKY = "sticky"
    ON_FAILURE = "on_failure"


@dataclass
class Proxy:
    ip: str
    port: int
    source_url: str = ""
    protocols: list[str] = field(default_factory=list)
    anonymity: str | None = None
    latency_ms: int | None = None
    country: str | None = None
    city: str | None = None
    asn: str | None = None
    org: str | None = None
    tags: set[str] = field(default_factory=set)
    first_seen: datetime = field(default_factory=datetime.utcnow)
    last_checked: datetime | None = None
    alive: bool = False
    target_checks: dict[str, str] = field(default_factory=dict)

    @property
    def address(self) -> str:
        return f"{self.ip}:{self.port}"

    def to_row(self) -> tuple:
        return (
            self.ip,
            self.port,
            self.source_url,
            json.dumps(self.protocols),
            self.anonymity,
            self.latency_ms,
            self.country,
            self.city,
            self.asn,
            self.org,
            json.dumps(sorted(self.tags)),
            self.first_seen.isoformat(),
            self.last_checked.isoformat() if self.last_checked else None,
            int(self.alive),
            json.dumps(self.target_checks),
        )

    @classmethod
    def from_row(cls, row: tuple) -> Proxy:
        return cls(
            ip=row[0],
            port=row[1],
            source_url=row[2] or "",
            protocols=json.loads(row[3]) if row[3] else [],
            anonymity=row[4],
            latency_ms=row[5],
            country=row[6],
            city=row[7],
            asn=row[8],
            org=row[9],
            tags=set(json.loads(row[10])) if row[10] else set(),
            first_seen=datetime.fromisoformat(row[11]) if row[11] else datetime.utcnow(),
            last_checked=datetime.fromisoformat(row[12]) if row[12] else None,
            alive=bool(row[13]),
            target_checks=json.loads(row[14]) if row[14] else {},
        )


@dataclass
class TestResult:
    proxy: Proxy
    protocols: list[str] = field(default_factory=list)
    anonymity: str | None = None
    latency_ms: int | None = None
    country: str | None = None
    asn: str | None = None
    target_checks: dict[str, str] = field(default_factory=dict)
    tags: set[str] = field(default_factory=set)
    alive: bool = False


@dataclass
class Source:
    url: str
    last_crawled: datetime | None = None
    proxy_count: int = 0
    enabled: bool = True

    def to_row(self) -> tuple:
        return (
            self.url,
            self.last_crawled.isoformat() if self.last_crawled else None,
            self.proxy_count,
            int(self.enabled),
        )

    @classmethod
    def from_row(cls, row: tuple) -> Source:
        return cls(
            url=row[0],
            last_crawled=datetime.fromisoformat(row[1]) if row[1] else None,
            proxy_count=row[2],
            enabled=bool(row[3]),
        )


@dataclass
class TagRule:
    name: str
    field: str
    operator: str  # ==, !=, <, >, <=, >=, in, contains
    value: Any
    tag: str  # tag to apply when rule matches

    def matches(self, proxy: Proxy) -> bool:
        actual = getattr(proxy, self.field, None)
        if actual is None:
            return False
        ops: dict[str, Callable[[Any, Any], bool]] = {
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
            "<": lambda a, b: a < b,
            ">": lambda a, b: a > b,
            "<=": lambda a, b: a <= b,
            ">=": lambda a, b: a >= b,
            "in": lambda a, b: a in b,
            "contains": lambda a, b: b in a,
        }
        op_fn = ops.get(self.operator)
        if op_fn is None:
            return False
        try:
            return op_fn(actual, self.value)
        except (TypeError, ValueError):
            return False
