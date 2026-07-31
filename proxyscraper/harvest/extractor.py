from __future__ import annotations

import ipaddress
import logging
import re
from typing import Protocol

logger = logging.getLogger(__name__)

_IP_PORT_PATTERN = re.compile(
    r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*[:\s]\s*(\d{2,5})\b"
)

_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
]


class ExtractorPlugin(Protocol):
    name: str

    def extract(self, raw_text: str, source_url: str) -> list[tuple[str, int]]:
        ...


def is_valid_ipv4(ip: str) -> bool:
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    try:
        return all(0 <= int(p) <= 255 for p in parts)
    except ValueError:
        return False


def is_private_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
        return any(addr in net for net in _PRIVATE_NETWORKS)
    except ValueError:
        return True


def is_valid_port(port: int) -> bool:
    return 1 <= port <= 65535


def extract_proxies(
    text: str,
    source_url: str = "",
    allow_private: bool = False,
) -> list[tuple[str, int]]:
    results: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()

    for match in _IP_PORT_PATTERN.finditer(text):
        ip = match.group(1)
        try:
            port = int(match.group(2))
        except ValueError:
            continue

        if not is_valid_ipv4(ip):
            continue
        if not is_valid_port(port):
            continue
        if not allow_private and is_private_ip(ip):
            continue

        key = (ip, port)
        if key not in seen:
            seen.add(key)
            results.append(key)

    if results:
        logger.debug("Extracted %d proxies from %s", len(results), source_url or "<text>")

    return results


def extract_from_html(
    html: str,
    source_url: str = "",
    allow_private: bool = False,
) -> list[tuple[str, int]]:
    try:
        from selectolax.parser import HTMLParser
        tree = HTMLParser(html)
        text = tree.text(separator=" ") or ""
    except ImportError:
        text = re.sub(r"<[^>]+>", " ", html)
    return extract_proxies(text, source_url, allow_private)


class TableExtractor:
    """Extracts IP:port from HTML tables where IP and port are in separate columns."""
    name = "table"

    _IP_ONLY = re.compile(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b")
    _PORT_ONLY = re.compile(r"\b(\d{2,5})\b")

    def extract(self, raw_text: str, source_url: str = "") -> list[tuple[str, int]]:
        try:
            from selectolax.parser import HTMLParser
        except ImportError:
            return extract_proxies(raw_text, source_url)

        tree = HTMLParser(raw_text)
        results: list[tuple[str, int]] = []
        seen: set[tuple[str, int]] = set()

        for table in tree.css("table"):
            for row in table.css("tr"):
                cells = row.css("td")
                if len(cells) < 2:
                    continue
                ip_match = self._IP_ONLY.search(cells[0].text() or "")
                port_match = self._PORT_ONLY.search(cells[1].text() or "")
                if ip_match and port_match:
                    ip = ip_match.group(1)
                    port = int(port_match.group(1))
                    if is_valid_ipv4(ip) and is_valid_port(port) and not is_private_ip(ip):
                        key = (ip, port)
                        if key not in seen:
                            seen.add(key)
                            results.append(key)

        if not results:
            return extract_from_html(raw_text, source_url)

        return results
