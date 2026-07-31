from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from proxyscraper.core.config import AppConfig
from proxyscraper.core.events import EventBus, EventType
from proxyscraper.core.tag_manager import TagManager
from proxyscraper.ui.tag_editor import TagEditor


class ConfigDialog(QDialog):
    def __init__(
        self,
        config: AppConfig,
        tag_manager: TagManager,
        event_bus: EventBus | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Konfiguration")
        self.setMinimumSize(600, 500)
        self.config = config
        self.tag_manager = tag_manager
        self.event_bus = event_bus
        self._widgets: dict[str, Any] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        tabs.addTab(self._build_harvest_tab(), "Harvesting")
        tabs.addTab(self._build_scan_tab(), "Scanner")
        tabs.addTab(self._build_testing_tab(), "Testing")
        tabs.addTab(self._build_server_tab(), "Server")
        tabs.addTab(self._build_filter_tab(), "Filter")
        tabs.addTab(TagEditor(self.tag_manager), "Tags")
        tabs.addTab(self._build_gui_tab(), "GUI")

        layout.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_harvest_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        widget = QWidget()
        form = QFormLayout(widget)

        engines = QLineEdit(",".join(self.config.harvest.search.engines))
        self._widgets["harvest.search.engines"] = engines
        form.addRow("Suchmaschinen (kommagetrennt):", engines)

        max_results = QSpinBox()
        max_results.setRange(1, 1000)
        max_results.setValue(self.config.harvest.search.max_results_per_query)
        self._widgets["harvest.search.max_results_per_query"] = max_results
        form.addRow("Max. Ergebnisse pro Suche:", max_results)

        freshness = QSpinBox()
        freshness.setRange(1, 365)
        freshness.setValue(self.config.harvest.search.freshness_days)
        self._widgets["harvest.search.freshness_days"] = freshness
        form.addRow("Frische (Tage):", freshness)

        respect_robots = QCheckBox()
        respect_robots.setChecked(self.config.harvest.crawl.respect_robots)
        self._widgets["harvest.crawl.respect_robots"] = respect_robots
        form.addRow("robots.txt beachten:", respect_robots)

        delay = QDoubleSpinBox()
        delay.setRange(0.1, 60.0)
        delay.setValue(self.config.harvest.crawl.request_delay_seconds)
        delay.setSingleStep(0.5)
        self._widgets["harvest.crawl.request_delay_seconds"] = delay
        form.addRow("Anfrage-Verzögerung (s):", delay)

        max_rpm = QSpinBox()
        max_rpm.setRange(1, 1000)
        max_rpm.setValue(self.config.harvest.crawl.max_requests_per_minute)
        self._widgets["harvest.crawl.max_requests_per_minute"] = max_rpm
        form.addRow("Max. Anfragen/Minute:", max_rpm)

        scroll.setWidget(widget)
        return scroll

    def _build_scan_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)

        workers = QSpinBox()
        workers.setRange(1, 2000)
        workers.setValue(self.config.scan.max_workers)
        self._widgets["scan.max_workers"] = workers
        form.addRow("Max. Worker:", workers)

        timeout = QDoubleSpinBox()
        timeout.setRange(0.5, 30.0)
        timeout.setValue(self.config.scan.connect_timeout_seconds)
        timeout.setSingleStep(0.5)
        self._widgets["scan.connect_timeout_seconds"] = timeout
        form.addRow("Connect Timeout (s):", timeout)

        cps = QSpinBox()
        cps.setRange(1, 10000)
        cps.setValue(self.config.scan.max_connections_per_second)
        self._widgets["scan.max_connections_per_second"] = cps
        form.addRow("Max. Verbindungen/s:", cps)

        retries = QSpinBox()
        retries.setRange(0, 10)
        retries.setValue(self.config.scan.retries)
        self._widgets["scan.retries"] = retries
        form.addRow("Wiederholungen:", retries)

        return widget

    def _build_testing_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)

        test_url = QLineEdit(self.config.testing.type_detector.test_url)
        self._widgets["testing.type_detector.test_url"] = test_url
        form.addRow("Test-URL:", test_url)

        echo_url = QLineEdit(self.config.testing.anonymity.echo_url)
        self._widgets["testing.anonymity.echo_url"] = echo_url
        form.addRow("Echo-URL (Anonymität):", echo_url)

        num_pings = QSpinBox()
        num_pings.setRange(1, 20)
        num_pings.setValue(self.config.testing.latency.num_pings)
        self._widgets["testing.latency.num_pings"] = num_pings
        form.addRow("Anzahl Pings:", num_pings)

        geo_path = QLineEdit(self.config.testing.geo.maxmind_db_path)
        self._widgets["testing.geo.maxmind_db_path"] = geo_path
        form.addRow("MaxMind DB Pfad:", geo_path)

        return widget

    def _build_server_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)

        host = QLineEdit(self.config.server.listen_host)
        self._widgets["server.listen_host"] = host
        form.addRow("Listen Host:", host)

        port = QSpinBox()
        port.setRange(1, 65535)
        port.setValue(self.config.server.listen_port)
        self._widgets["server.listen_port"] = port
        form.addRow("Listen Port:", port)

        rotation = QComboBox()
        rotation.addItems(["per_request", "sticky", "on_failure"])
        rotation.setCurrentText(self.config.server.rotation)
        self._widgets["server.rotation"] = rotation
        form.addRow("Rotation:", rotation)

        sticky_ttl = QSpinBox()
        sticky_ttl.setRange(10, 86400)
        sticky_ttl.setValue(self.config.server.sticky_ttl_seconds)
        self._widgets["server.sticky_ttl_seconds"] = sticky_ttl
        form.addRow("Sticky TTL (s):", sticky_ttl)

        max_retries = QSpinBox()
        max_retries.setRange(0, 20)
        max_retries.setValue(self.config.server.max_retries)
        self._widgets["server.max_retries"] = max_retries
        form.addRow("Max. Retries:", max_retries)

        health_interval = QSpinBox()
        health_interval.setRange(10, 3600)
        health_interval.setValue(self.config.server.health_check_interval_seconds)
        self._widgets["server.health_check_interval_seconds"] = health_interval
        form.addRow("Health-Check Intervall (s):", health_interval)

        return widget

    def _build_filter_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)

        country_mode = QComboBox()
        country_mode.addItems(["allow", "block"])
        country_mode.setCurrentText(self.config.filters.country.mode)
        self._widgets["filters.country.mode"] = country_mode
        form.addRow("Ländermodus:", country_mode)

        country_list = QLineEdit(",".join(self.config.filters.country.countries))
        self._widgets["filters.country.countries"] = country_list
        form.addRow("Länderliste (kommagetrennt):", country_list)

        max_latency = QSpinBox()
        max_latency.setRange(100, 60000)
        max_latency.setValue(self.config.filters.speed.max_latency_ms)
        self._widgets["filters.speed.max_latency_ms"] = max_latency
        form.addRow("Max. Latenz (ms):", max_latency)

        exclude_asns = QLineEdit(",".join(self.config.filters.security.exclude_asns))
        self._widgets["filters.security.exclude_asns"] = exclude_asns
        form.addRow("Ausgeschlossene ASNs:", exclude_asns)

        return widget

    def _build_gui_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)

        theme = QComboBox()
        theme.addItems(["dark", "light"])
        theme.setCurrentText(self.config.gui.theme)
        self._widgets["gui.theme"] = theme
        form.addRow("Theme:", theme)

        return widget

    def _save(self) -> None:
        # Harvest
        engines_text = self._widgets["harvest.search.engines"].text()
        self.config.harvest.search.engines = [e.strip() for e in engines_text.split(",") if e.strip()]
        self.config.harvest.search.max_results_per_query = self._widgets["harvest.search.max_results_per_query"].value()
        self.config.harvest.search.freshness_days = self._widgets["harvest.search.freshness_days"].value()
        self.config.harvest.crawl.respect_robots = self._widgets["harvest.crawl.respect_robots"].isChecked()
        self.config.harvest.crawl.request_delay_seconds = self._widgets["harvest.crawl.request_delay_seconds"].value()
        self.config.harvest.crawl.max_requests_per_minute = self._widgets["harvest.crawl.max_requests_per_minute"].value()

        # Scan
        self.config.scan.max_workers = self._widgets["scan.max_workers"].value()
        self.config.scan.connect_timeout_seconds = self._widgets["scan.connect_timeout_seconds"].value()
        self.config.scan.max_connections_per_second = self._widgets["scan.max_connections_per_second"].value()
        self.config.scan.retries = self._widgets["scan.retries"].value()

        # Testing
        self.config.testing.type_detector.test_url = self._widgets["testing.type_detector.test_url"].text()
        self.config.testing.anonymity.echo_url = self._widgets["testing.anonymity.echo_url"].text()
        self.config.testing.latency.num_pings = self._widgets["testing.latency.num_pings"].value()
        self.config.testing.geo.maxmind_db_path = self._widgets["testing.geo.maxmind_db_path"].text()

        # Server
        self.config.server.listen_host = self._widgets["server.listen_host"].text()
        self.config.server.listen_port = self._widgets["server.listen_port"].value()
        self.config.server.rotation = self._widgets["server.rotation"].currentText()
        self.config.server.sticky_ttl_seconds = self._widgets["server.sticky_ttl_seconds"].value()
        self.config.server.max_retries = self._widgets["server.max_retries"].value()
        self.config.server.health_check_interval_seconds = self._widgets["server.health_check_interval_seconds"].value()

        # Filters
        self.config.filters.country.mode = self._widgets["filters.country.mode"].currentText()
        country_text = self._widgets["filters.country.countries"].text()
        self.config.filters.country.countries = [c.strip() for c in country_text.split(",") if c.strip()]
        self.config.filters.speed.max_latency_ms = self._widgets["filters.speed.max_latency_ms"].value()
        asn_text = self._widgets["filters.security.exclude_asns"].text()
        self.config.filters.security.exclude_asns = [a.strip() for a in asn_text.split(",") if a.strip()]

        # GUI
        self.config.gui.theme = self._widgets["gui.theme"].currentText()

        self.config.save_yaml("config.yaml")

        if self.event_bus:
            self.event_bus.emit(EventType.CONFIG_UPDATED, config=self.config)

        self.accept()
