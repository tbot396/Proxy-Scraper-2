from __future__ import annotations

import pytest

from proxyscraper.core.search_engines.base_adapter import BaseSearchAdapter

# Import adapters to register them
import proxyscraper.core.search_engines.google_adapter  # noqa: F401
import proxyscraper.core.search_engines.bing_adapter  # noqa: F401
import proxyscraper.core.search_engines.duckduckgo_adapter  # noqa: F401


class TestBaseSearchAdapter:
    def test_registry_populated(self):
        adapters = BaseSearchAdapter.available_adapters()
        assert "google" in adapters
        assert "bing" in adapters
        assert "duckduckgo" in adapters

    def test_get_adapter_by_name(self):
        adapter = BaseSearchAdapter.get_adapter("google")
        assert adapter.name == "google"

    def test_get_adapter_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown search engine"):
            BaseSearchAdapter.get_adapter("nonexistent_engine")

    def test_all_adapters_instantiable(self):
        for name in BaseSearchAdapter.available_adapters():
            adapter = BaseSearchAdapter.get_adapter(name)
            assert hasattr(adapter, "search")
            assert hasattr(adapter, "name")
