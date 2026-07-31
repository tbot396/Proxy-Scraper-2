from __future__ import annotations

import pytest

from proxyscraper.core.config import AppConfig
from proxyscraper.core.events import EventBus
from proxyscraper.core.models import Proxy
from proxyscraper.core.storage import Storage


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def config():
    return AppConfig()


@pytest.fixture
def storage(tmp_path):
    db = Storage(tmp_path / "test.db")
    yield db
    db.close()


@pytest.fixture
def sample_proxy():
    return Proxy(ip="1.2.3.4", port=8080, source_url="http://example.com")


@pytest.fixture
def sample_proxies():
    return [
        Proxy(ip="1.2.3.4", port=8080, source_url="http://example.com", alive=True, latency_ms=100, country="DE"),
        Proxy(ip="5.6.7.8", port=3128, source_url="http://example.com", alive=True, latency_ms=500, country="US"),
        Proxy(ip="9.10.11.12", port=1080, source_url="http://example.com", alive=False, latency_ms=2000, country="CN"),
    ]
