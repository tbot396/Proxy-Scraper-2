from __future__ import annotations

import logging
from pathlib import Path

from proxyscraper.core.config import GeoConfig
from proxyscraper.core.models import Proxy

logger = logging.getLogger(__name__)


class GeoLocator:
    def __init__(self, config: GeoConfig) -> None:
        self.config = config
        self._reader = None
        self._available = False
        self._init_reader()

    def _init_reader(self) -> None:
        db_path = Path(self.config.maxmind_db_path)
        if not db_path.exists():
            logger.warning("GeoLite2 database not found at %s — geolocation disabled", db_path)
            return
        try:
            import geoip2.database
            self._reader = geoip2.database.Reader(str(db_path))
            self._available = True
            logger.info("GeoLite2 database loaded from %s", db_path)
        except ImportError:
            logger.warning("geoip2 not installed — geolocation disabled")
        except Exception as e:
            logger.error("Failed to load GeoLite2 database: %s", e)

    def locate(self, ip: str) -> dict[str, str | None]:
        if not self._available or self._reader is None:
            return {"country": None, "city": None, "asn": None, "org": None}

        result: dict[str, str | None] = {
            "country": None, "city": None, "asn": None, "org": None,
        }

        try:
            resp = self._reader.city(ip)
            result["country"] = resp.country.iso_code
            result["city"] = resp.city.name
        except Exception:
            pass

        try:
            asn_resp = self._reader.asn(ip)
            result["asn"] = str(asn_resp.autonomous_system_number)
            result["org"] = asn_resp.autonomous_system_organization
        except Exception:
            pass

        return result

    def enrich_proxy(self, proxy: Proxy) -> None:
        info = self.locate(proxy.ip)
        proxy.country = info["country"]
        proxy.city = info["city"]
        proxy.asn = info["asn"]
        proxy.org = info["org"]

    def close(self) -> None:
        if self._reader:
            self._reader.close()
            self._reader = None
            self._available = False
