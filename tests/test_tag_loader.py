from __future__ import annotations

import json

from proxyscraper.core.tag_manager import TagManager
from proxyscraper.harvest.tag_loader import TagLoader


class TestTagLoader:
    def test_get_search_queries_with_tags(self, tmp_path):
        tag_file = tmp_path / "tags.json"
        tag_file.write_text(json.dumps({"search_tags": ["proxy list", "socks5"]}))

        tm = TagManager(str(tag_file))
        loader = TagLoader(tm)
        queries = loader.get_search_queries()
        assert queries == ["proxy list", "socks5"]

    def test_get_search_queries_with_base(self, tmp_path):
        tag_file = tmp_path / "tags.json"
        tag_file.write_text(json.dumps({"search_tags": ["socks5"]}))

        tm = TagManager(str(tag_file))
        loader = TagLoader(tm)
        queries = loader.get_search_queries(base_queries=["base query"])
        assert "base query" in queries
        assert "socks5" in queries

    def test_no_duplicates(self, tmp_path):
        tag_file = tmp_path / "tags.json"
        tag_file.write_text(json.dumps({"search_tags": ["same"]}))

        tm = TagManager(str(tag_file))
        loader = TagLoader(tm)
        queries = loader.get_search_queries(base_queries=["same"])
        assert queries.count("same") == 1

    def test_empty_tags(self, tmp_path):
        tag_file = tmp_path / "tags.json"
        tag_file.write_text(json.dumps({"search_tags": []}))

        tm = TagManager(str(tag_file))
        loader = TagLoader(tm)
        queries = loader.get_search_queries()
        assert queries == []
