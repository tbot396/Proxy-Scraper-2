from __future__ import annotations

import os
import tempfile

import yaml

from proxyscraper.core.config import AppConfig


class TestAppConfig:
    def test_defaults(self):
        config = AppConfig()
        assert config.harvest.search.max_results_per_query == 50
        assert config.scan.max_workers == 200
        assert config.server.listen_port == 8080
        assert config.gui.theme == "dark"

    def test_from_yaml(self):
        config = AppConfig.from_yaml("config.yaml")
        assert config.harvest.search.engines == ["google", "bing", "duckduckgo"]
        assert config.harvest.crawl.respect_robots is True
        assert config.scan.connect_timeout_seconds == 3.0

    def test_from_yaml_missing_file(self):
        config = AppConfig.from_yaml("nonexistent.yaml")
        assert config.harvest.search.max_results_per_query == 50

    def test_save_yaml_roundtrip(self):
        config = AppConfig()
        config.harvest.search.engines = ["bing"]
        config.scan.max_workers = 100
        config.filters.country.countries = ["DE", "AT"]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            tmp = f.name

        try:
            config.save_yaml(tmp)

            with open(tmp, "r") as f:
                data = yaml.safe_load(f)

            assert data["harvest"]["search"]["engines"] == ["bing"]
            assert data["scan"]["max_workers"] == 100
            # Alias should serialize as 'list' not 'countries'
            assert data["filters"]["country"]["list"] == ["DE", "AT"]

            # Reload
            config2 = AppConfig.from_yaml(tmp)
            assert config2.harvest.search.engines == ["bing"]
            assert config2.scan.max_workers == 100
            assert config2.filters.country.countries == ["DE", "AT"]
        finally:
            os.unlink(tmp)

    def test_update_section(self):
        config = AppConfig()
        config.update_section("scan", {"max_workers": 500})
        assert config.scan.max_workers == 500

    def test_nested_config_defaults(self):
        config = AppConfig()
        assert config.testing.latency.num_pings == 3
        assert config.server.rotation == "per_request"
        assert config.filters.speed.max_latency_ms == 1500
        assert config.logging.level == "INFO"
