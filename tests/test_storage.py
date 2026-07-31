from __future__ import annotations

from datetime import datetime

from proxyscraper.core.models import Proxy, Source
from proxyscraper.core.storage import Storage


class TestStorage:
    def test_upsert_and_get_proxy(self, storage):
        p = Proxy(ip="1.2.3.4", port=8080, source_url="http://example.com")
        storage.upsert_proxy(p)

        got = storage.get_proxy("1.2.3.4", 8080)
        assert got is not None
        assert got.ip == "1.2.3.4"
        assert got.port == 8080

    def test_upsert_updates_existing(self, storage):
        p = Proxy(ip="1.2.3.4", port=8080, alive=False)
        storage.upsert_proxy(p)

        p.alive = True
        p.latency_ms = 200
        storage.upsert_proxy(p)

        got = storage.get_proxy("1.2.3.4", 8080)
        assert got.alive is True
        assert got.latency_ms == 200

    def test_upsert_proxies_batch(self, storage):
        proxies = [
            Proxy(ip="1.2.3.4", port=80),
            Proxy(ip="5.6.7.8", port=3128),
            Proxy(ip="9.10.11.12", port=1080),
        ]
        storage.upsert_proxies(proxies)
        assert storage.count_proxies() == 3

    def test_get_proxy_not_found(self, storage):
        assert storage.get_proxy("99.99.99.99", 1234) is None

    def test_get_proxies_alive_only(self, storage, sample_proxies):
        storage.upsert_proxies(sample_proxies)
        alive = storage.get_proxies(alive_only=True)
        assert len(alive) == 2
        assert all(p.alive for p in alive)

    def test_get_proxies_country_filter(self, storage, sample_proxies):
        storage.upsert_proxies(sample_proxies)
        de_proxies = storage.get_proxies(country="DE")
        assert len(de_proxies) == 1
        assert de_proxies[0].country == "DE"

    def test_get_proxies_max_latency(self, storage, sample_proxies):
        storage.upsert_proxies(sample_proxies)
        fast = storage.get_proxies(max_latency_ms=500)
        assert all(p.latency_ms <= 500 for p in fast if p.latency_ms is not None)

    def test_get_proxies_require_tags(self, storage):
        p1 = Proxy(ip="1.2.3.4", port=80, tags={"elite", "fast"})
        p2 = Proxy(ip="5.6.7.8", port=80, tags={"anonymous"})
        storage.upsert_proxies([p1, p2])

        result = storage.get_proxies(require_tags=["elite"])
        assert len(result) == 1
        assert result[0].ip == "1.2.3.4"

    def test_get_proxies_exclude_tags(self, storage):
        p1 = Proxy(ip="1.2.3.4", port=80, tags={"elite", "fast"})
        p2 = Proxy(ip="5.6.7.8", port=80, tags={"slow"})
        storage.upsert_proxies([p1, p2])

        result = storage.get_proxies(exclude_tags=["slow"])
        assert len(result) == 1
        assert result[0].ip == "1.2.3.4"

    def test_get_proxies_limit(self, storage, sample_proxies):
        storage.upsert_proxies(sample_proxies)
        result = storage.get_proxies(limit=1)
        assert len(result) == 1

    def test_count_proxies(self, storage, sample_proxies):
        storage.upsert_proxies(sample_proxies)
        assert storage.count_proxies() == 3
        assert storage.count_proxies(alive_only=True) == 2

    def test_mark_dead(self, storage):
        p = Proxy(ip="1.2.3.4", port=80, alive=True)
        storage.upsert_proxy(p)
        storage.mark_dead("1.2.3.4", 80)

        got = storage.get_proxy("1.2.3.4", 80)
        assert got.alive is False
        assert got.last_checked is not None

    def test_delete_proxy(self, storage):
        p = Proxy(ip="1.2.3.4", port=80)
        storage.upsert_proxy(p)
        storage.delete_proxy("1.2.3.4", 80)
        assert storage.get_proxy("1.2.3.4", 80) is None

    def test_delete_dead_proxies(self, storage):
        p1 = Proxy(ip="1.2.3.4", port=80, alive=True)
        p2 = Proxy(ip="5.6.7.8", port=80, alive=False)
        p3 = Proxy(ip="9.10.11.12", port=80, alive=False)
        storage.upsert_proxies([p1, p2, p3])

        deleted = storage.delete_dead_proxies()
        assert deleted == 2
        assert storage.count_proxies() == 1

    def test_record_history(self, storage):
        p = Proxy(ip="1.2.3.4", port=80, alive=True, latency_ms=100, anonymity="elite")
        storage.upsert_proxy(p)
        storage.record_history(p)

        rows = storage.conn.execute("SELECT * FROM history WHERE ip=? AND port=?", ("1.2.3.4", 80)).fetchall()
        assert len(rows) == 1


class TestSourceStorage:
    def test_upsert_and_get_sources(self, storage):
        s = Source(url="http://example.com", proxy_count=10)
        storage.upsert_source(s)

        sources = storage.get_sources()
        assert len(sources) == 1
        assert sources[0].url == "http://example.com"

    def test_get_due_sources(self, storage):
        s1 = Source(url="http://old.com", last_crawled=None)
        s2 = Source(url="http://recent.com", last_crawled=datetime.utcnow())
        storage.upsert_source(s1)
        storage.upsert_source(s2)

        due = storage.get_due_sources(max_age_hours=24)
        assert any(s.url == "http://old.com" for s in due)

    def test_dedup_on_upsert(self, storage):
        storage.upsert_proxy(Proxy(ip="1.2.3.4", port=80, source_url="a"))
        storage.upsert_proxy(Proxy(ip="1.2.3.4", port=80, source_url="b"))
        assert storage.count_proxies() == 1
        got = storage.get_proxy("1.2.3.4", 80)
        assert got.source_url == "b"
