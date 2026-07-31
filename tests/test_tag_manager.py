from __future__ import annotations

import json
import os

from proxyscraper.core.events import EventBus, EventType
from proxyscraper.core.tag_manager import TagManager


class TestTagManager:
    def test_load_tags_from_file(self, tmp_path):
        tag_file = tmp_path / "tags.json"
        tag_file.write_text(json.dumps({"search_tags": ["proxy list", "socks5"]}))

        tm = TagManager(str(tag_file))
        assert tm.get_tags() == ["proxy list", "socks5"]

    def test_load_tags_missing_file(self, tmp_path):
        tm = TagManager(str(tmp_path / "nonexistent.json"))
        assert tm.get_tags() == []

    def test_add_tag(self, tmp_path):
        tag_file = tmp_path / "tags.json"
        tag_file.write_text(json.dumps({"search_tags": []}))

        tm = TagManager(str(tag_file))
        assert tm.add_tag("new tag") is True
        assert "new tag" in tm.get_tags()

        # Verify persisted
        with open(tag_file) as f:
            data = json.load(f)
        assert "new tag" in data["search_tags"]

    def test_add_duplicate_tag(self, tmp_path):
        tag_file = tmp_path / "tags.json"
        tag_file.write_text(json.dumps({"search_tags": ["existing"]}))

        tm = TagManager(str(tag_file))
        assert tm.add_tag("existing") is False

    def test_add_empty_tag(self, tmp_path):
        tag_file = tmp_path / "tags.json"
        tag_file.write_text(json.dumps({"search_tags": []}))

        tm = TagManager(str(tag_file))
        assert tm.add_tag("") is False
        assert tm.add_tag("  ") is False

    def test_remove_tag(self, tmp_path):
        tag_file = tmp_path / "tags.json"
        tag_file.write_text(json.dumps({"search_tags": ["a", "b", "c"]}))

        tm = TagManager(str(tag_file))
        assert tm.remove_tag("b") is True
        assert tm.get_tags() == ["a", "c"]

    def test_remove_nonexistent_tag(self, tmp_path):
        tag_file = tmp_path / "tags.json"
        tag_file.write_text(json.dumps({"search_tags": ["a"]}))

        tm = TagManager(str(tag_file))
        assert tm.remove_tag("z") is False

    def test_set_tags(self, tmp_path):
        tag_file = tmp_path / "tags.json"
        tag_file.write_text(json.dumps({"search_tags": []}))

        tm = TagManager(str(tag_file))
        tm.set_tags(["x", "y", "z"])
        assert tm.get_tags() == ["x", "y", "z"]

    def test_events_on_add_remove(self, tmp_path):
        tag_file = tmp_path / "tags.json"
        tag_file.write_text(json.dumps({"search_tags": ["existing"]}))

        bus = EventBus()
        added = []
        removed = []
        bus.subscribe(EventType.TAG_ADDED, lambda tag="", **kw: added.append(tag))
        bus.subscribe(EventType.TAG_REMOVED, lambda tag="", **kw: removed.append(tag))

        tm = TagManager(str(tag_file), bus)
        tm.add_tag("new")
        tm.remove_tag("existing")

        assert added == ["new"]
        assert removed == ["existing"]
