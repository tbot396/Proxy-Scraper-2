from __future__ import annotations

from proxyscraper.harvest.source_registry import SourceRegistry


class TestSourceRegistry:
    def test_add_source(self, storage):
        reg = SourceRegistry(storage)
        assert reg.add_source("http://example.com/proxies") is True
        assert len(reg.get_enabled_sources()) == 1

    def test_add_source_normalizes_url(self, storage):
        reg = SourceRegistry(storage)
        reg.add_source("example.com/proxies/")
        sources = reg.get_enabled_sources()
        assert sources[0].url == "http://example.com/proxies"

    def test_add_duplicate_source(self, storage):
        reg = SourceRegistry(storage)
        assert reg.add_source("http://example.com") is True
        assert reg.add_source("http://example.com") is False

    def test_add_sources_batch(self, storage):
        reg = SourceRegistry(storage)
        count = reg.add_sources(["http://a.com", "http://b.com", "http://a.com"])
        assert count == 2

    def test_add_invalid_source(self, storage):
        reg = SourceRegistry(storage)
        assert reg.add_source("") is False
        assert reg.add_source("   ") is False

    def test_mark_crawled(self, storage):
        reg = SourceRegistry(storage)
        reg.add_source("http://example.com")
        reg.mark_crawled("http://example.com", proxy_count=42)

        sources = reg.get_enabled_sources()
        assert sources[0].proxy_count == 42
        assert sources[0].last_crawled is not None

    def test_disable_source(self, storage):
        reg = SourceRegistry(storage)
        reg.add_source("http://example.com")
        reg.disable_source("http://example.com")
        assert len(reg.get_enabled_sources()) == 0

    def test_get_due_sources(self, storage):
        reg = SourceRegistry(storage)
        reg.add_source("http://never-crawled.com")
        due = reg.get_due_sources(max_age_hours=24)
        assert len(due) == 1
