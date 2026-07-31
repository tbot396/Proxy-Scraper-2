from __future__ import annotations

import csv
import json
import os

from proxyscraper.core.models import Proxy
from proxyscraper.export.file_export import FileExporter
from proxyscraper.export.export_manager import evaluate_trigger


class TestFileExporter:
    def _sample_proxies(self):
        return [
            Proxy(ip="1.2.3.4", port=8080, protocols=["http"], anonymity="elite",
                  latency_ms=100, country="DE", tags={"fast", "elite"}),
            Proxy(ip="5.6.7.8", port=3128, protocols=["socks5"], anonymity="anonymous",
                  latency_ms=500, country="US", tags={"medium"}),
        ]

    def test_export_txt(self, tmp_path):
        path = str(tmp_path / "proxies.txt")
        exporter = FileExporter()
        exporter.export(self._sample_proxies(), path, "txt")

        with open(path) as f:
            lines = f.read().strip().splitlines()
        assert lines == ["1.2.3.4:8080", "5.6.7.8:3128"]

    def test_export_csv(self, tmp_path):
        path = str(tmp_path / "proxies.csv")
        exporter = FileExporter()
        exporter.export(self._sample_proxies(), path, "csv")

        with open(path) as f:
            reader = csv.reader(f)
            rows = list(reader)
        assert rows[0][0] == "ip"  # header
        assert rows[1][0] == "1.2.3.4"
        assert rows[2][0] == "5.6.7.8"

    def test_export_json(self, tmp_path):
        path = str(tmp_path / "proxies.json")
        exporter = FileExporter()
        exporter.export(self._sample_proxies(), path, "json")

        with open(path) as f:
            data = json.load(f)
        assert len(data) == 2
        assert data[0]["ip"] == "1.2.3.4"
        assert data[0]["country"] == "DE"

    def test_to_string_txt(self):
        exporter = FileExporter()
        result = exporter.to_string(self._sample_proxies(), "txt")
        assert "1.2.3.4:8080" in result
        assert "5.6.7.8:3128" in result

    def test_to_string_json(self):
        exporter = FileExporter()
        result = exporter.to_string(self._sample_proxies(), "json")
        data = json.loads(result)
        assert len(data) == 2

    def test_export_creates_directories(self, tmp_path):
        path = str(tmp_path / "sub" / "dir" / "proxies.txt")
        exporter = FileExporter()
        exporter.export(self._sample_proxies(), path, "txt")
        assert os.path.exists(path)

    def test_export_empty_list(self, tmp_path):
        path = str(tmp_path / "empty.txt")
        exporter = FileExporter()
        exporter.export([], path, "txt")
        with open(path) as f:
            assert f.read() == ""


class TestEvaluateTrigger:
    def _proxies(self):
        return [
            Proxy(ip="1.2.3.4", port=80, tags={"elite", "fast"}),
            Proxy(ip="5.6.7.8", port=80, tags={"elite"}),
            Proxy(ip="9.10.11.12", port=80, tags={"anonymous"}),
        ]

    def test_empty_trigger_always_true(self):
        assert evaluate_trigger("", self._proxies()) is True

    def test_total_count(self):
        assert evaluate_trigger("total >= 3", self._proxies()) is True
        assert evaluate_trigger("total > 5", self._proxies()) is False

    def test_new_tag_count(self):
        assert evaluate_trigger("new_elite >= 2", self._proxies()) is True
        assert evaluate_trigger("new_elite >= 5", self._proxies()) is False

    def test_operators(self):
        p = self._proxies()
        assert evaluate_trigger("total == 3", p) is True
        assert evaluate_trigger("total != 3", p) is False
        assert evaluate_trigger("total <= 3", p) is True
        assert evaluate_trigger("total < 3", p) is False

    def test_invalid_trigger_returns_true(self):
        assert evaluate_trigger("not valid syntax!!", self._proxies()) is True
