from __future__ import annotations


class ProxyScraperError(Exception):
    pass


class ConfigError(ProxyScraperError):
    pass


class StorageError(ProxyScraperError):
    pass


class NetworkError(ProxyScraperError):
    pass


class ExtractionError(ProxyScraperError):
    pass
