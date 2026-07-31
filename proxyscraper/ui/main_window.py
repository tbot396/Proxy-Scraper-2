from __future__ import annotations

import asyncio
import logging
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt, Signal, QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMenu,
    QMenuBar,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTableView,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from proxyscraper.core.config import AppConfig
from proxyscraper.core.events import EventBus, EventType
from proxyscraper.core.storage import Storage
from proxyscraper.core.tag_manager import TagManager
from proxyscraper.harvest.source_registry import SourceRegistry
from proxyscraper.ui.config_dialog import ConfigDialog

logger = logging.getLogger(__name__)

_PROXY_HEADERS = [
    "IP", "Port", "Protokolle", "Anonymität", "Latenz (ms)",
    "Land", "Stadt", "ASN", "Tags", "Alive", "Zuletzt geprüft",
]


class EngineSignals(QObject):
    log_message = Signal(str)
    progress_update = Signal(int, int)
    scan_progress = Signal(int, int, int)
    harvest_progress = Signal(str, int, int)
    proxies_changed = Signal()
    pipeline_finished = Signal(str)


class ProxyTableModel(QAbstractTableModel):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._proxies: list[Any] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._proxies)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(_PROXY_HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return _PROXY_HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid() or role != Qt.DisplayRole:
            return None

        proxy = self._proxies[index.row()]
        col = index.column()

        if col == 0:
            return proxy.ip
        if col == 1:
            return proxy.port
        if col == 2:
            return ", ".join(proxy.protocols)
        if col == 3:
            return proxy.anonymity or ""
        if col == 4:
            return proxy.latency_ms if proxy.latency_ms is not None else ""
        if col == 5:
            return proxy.country or ""
        if col == 6:
            return proxy.city or ""
        if col == 7:
            return proxy.asn or ""
        if col == 8:
            return ", ".join(sorted(proxy.tags))
        if col == 9:
            return "Ja" if proxy.alive else "Nein"
        if col == 10:
            return proxy.last_checked.strftime("%Y-%m-%d %H:%M") if proxy.last_checked else ""
        return None

    def set_proxies(self, proxies: list[Any]) -> None:
        self.beginResetModel()
        self._proxies = list(proxies)
        self.endResetModel()


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig, config_path: str = "config.yaml") -> None:
        super().__init__()
        self.config = config
        self.config_path = config_path
        self.event_bus = EventBus()
        self.storage = Storage(config.database_path)
        self.tag_manager = TagManager(config.harvest.search.tag_file, self.event_bus)
        self.source_registry = SourceRegistry(self.storage)

        self.signals = EngineSignals()
        self._engine_thread: threading.Thread | None = None
        self._engine_running = False

        self.setWindowTitle("Proxy Scraper 2.0")
        self.setMinimumSize(1100, 700)

        self._init_ui()
        self._connect_events()
        self._apply_theme()
        self._refresh_table()

    def _init_ui(self) -> None:
        # Menu bar
        menubar = self.menuBar()

        file_menu = menubar.addMenu("Datei")
        config_action = QAction("Konfiguration...", self)
        config_action.triggered.connect(self._open_config)
        file_menu.addAction(config_action)
        file_menu.addSeparator()
        quit_action = QAction("Beenden", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        view_menu = menubar.addMenu("Ansicht")
        refresh_action = QAction("Aktualisieren", self)
        refresh_action.triggered.connect(self._refresh_table)
        view_menu.addAction(refresh_action)

        # Toolbar
        toolbar = QToolBar("Pipeline")
        self.addToolBar(toolbar)

        self.start_btn = QPushButton("Start Pipeline")
        self.start_btn.setObjectName("startButton")
        self.start_btn.clicked.connect(self._start_pipeline)
        toolbar.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stopp")
        self.stop_btn.setObjectName("stopButton")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_pipeline)
        toolbar.addWidget(self.stop_btn)

        toolbar.addSeparator()

        harvest_btn = QPushButton("Harvest")
        harvest_btn.clicked.connect(lambda: self._run_step("harvest"))
        toolbar.addWidget(harvest_btn)

        check_btn = QPushButton("Check")
        check_btn.clicked.connect(lambda: self._run_step("check"))
        toolbar.addWidget(check_btn)

        export_btn = QPushButton("Export")
        export_btn.clicked.connect(lambda: self._run_step("export"))
        toolbar.addWidget(export_btn)

        serve_btn = QPushButton("Server")
        serve_btn.clicked.connect(lambda: self._run_step("serve"))
        toolbar.addWidget(serve_btn)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        splitter = QSplitter(Qt.Vertical)

        # Proxy table
        self.proxy_model = ProxyTableModel()
        self.sort_proxy = QSortFilterProxyModel()
        self.sort_proxy.setSourceModel(self.proxy_model)
        self.sort_proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)

        self.table_view = QTableView()
        self.table_view.setModel(self.sort_proxy)
        self.table_view.setSortingEnabled(True)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QTableView.SelectRows)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table_view.horizontalHeader().setStretchLastSection(True)

        splitter.addWidget(self.table_view)

        # Log / tabs area
        bottom_tabs = QTabWidget()

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        bottom_tabs.addTab(self.log_output, "Log")

        from proxyscraper.ui.tag_editor import TagEditor
        self.tag_editor = TagEditor(self.tag_manager)
        bottom_tabs.addTab(self.tag_editor, "Tags")

        splitter.addWidget(bottom_tabs)
        splitter.setSizes([500, 200])

        layout.addWidget(splitter)

        # Status bar
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)

        self.status_label = QLabel("Bereit")
        self.statusbar.addWidget(self.status_label, 1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        self.statusbar.addPermanentWidget(self.progress_bar)

        self.count_label = QLabel("")
        self.statusbar.addPermanentWidget(self.count_label)

    def _connect_events(self) -> None:
        self.signals.log_message.connect(self._append_log)
        self.signals.proxies_changed.connect(self._refresh_table)
        self.signals.pipeline_finished.connect(self._on_pipeline_finished)
        self.signals.harvest_progress.connect(self._on_harvest_progress)
        self.signals.scan_progress.connect(self._on_scan_progress)

        self.event_bus.subscribe(EventType.HARVEST_PROGRESS, self._emit_harvest_progress)
        self.event_bus.subscribe(EventType.HARVEST_COMPLETE, self._emit_harvest_complete)
        self.event_bus.subscribe(EventType.SCAN_PROGRESS, self._emit_scan_progress)
        self.event_bus.subscribe(EventType.SCAN_COMPLETE, self._emit_scan_complete)
        self.event_bus.subscribe(EventType.ERROR, self._emit_error)

    def _emit_harvest_progress(self, url: str = "", count: int = 0, total: int = 0, **kw: object) -> None:
        self.signals.harvest_progress.emit(url, count, total)
        self.signals.log_message.emit(f"[Harvest] {count} Proxies von {url} (Gesamt: {total})")

    def _emit_harvest_complete(self, total: int = 0, **kw: object) -> None:
        self.signals.log_message.emit(f"[Harvest] Abgeschlossen: {total} Proxies gefunden")
        self.signals.proxies_changed.emit()

    def _emit_scan_progress(self, completed: int = 0, total: int = 0, alive: int = 0, **kw: object) -> None:
        self.signals.scan_progress.emit(completed, total, alive)

    def _emit_scan_complete(self, total: int = 0, alive: int = 0, **kw: object) -> None:
        self.signals.log_message.emit(f"[Scan] Abgeschlossen: {alive}/{total} erreichbar")
        self.signals.proxies_changed.emit()

    def _emit_error(self, message: str = "", **kw: object) -> None:
        self.signals.log_message.emit(f"[FEHLER] {message}")

    def _on_harvest_progress(self, url: str, count: int, total: int) -> None:
        self.status_label.setText(f"Harvesting... {total} Proxies gefunden")

    def _on_scan_progress(self, completed: int, total: int, alive: int) -> None:
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(completed)
        self.status_label.setText(f"Scanning {completed}/{total} — {alive} erreichbar")

    def _append_log(self, msg: str) -> None:
        self.log_output.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    def _refresh_table(self) -> None:
        proxies = self.storage.get_proxies()
        self.proxy_model.set_proxies(proxies)
        alive_count = sum(1 for p in proxies if p.alive)
        self.count_label.setText(f"{len(proxies)} Proxies ({alive_count} aktiv)")

    def _apply_theme(self) -> None:
        theme = self.config.gui.theme
        qss_path = Path(__file__).parent / "styles" / f"{theme}.qss"
        if qss_path.exists():
            with open(qss_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())

    def _open_config(self) -> None:
        dialog = ConfigDialog(self.config, self.tag_manager, self.event_bus, self)
        if dialog.exec():
            self._apply_theme()
            self._refresh_table()
            self._append_log("Konfiguration gespeichert")

    def _start_pipeline(self) -> None:
        self._run_step("run")

    def _run_step(self, step: str) -> None:
        if self._engine_running:
            self._append_log("Pipeline läuft bereits")
            return

        self._engine_running = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(0)
        self.status_label.setText(f"{step.capitalize()} wird ausgeführt...")
        self._append_log(f"Starte: {step}")

        self._engine_thread = threading.Thread(
            target=self._engine_worker, args=(step,), daemon=True
        )
        self._engine_thread.start()

    def _engine_worker(self, step: str) -> None:
        try:
            if step == "harvest":
                self._run_harvest()
            elif step == "check":
                self._run_check()
            elif step == "export":
                self._run_export()
            elif step == "serve":
                self._run_serve()
            elif step == "run":
                self._run_full_pipeline()
            self.signals.pipeline_finished.emit(f"{step} abgeschlossen")
        except Exception as e:
            logger.exception("Pipeline error")
            self.signals.log_message.emit(f"[FEHLER] {e}")
            self.signals.pipeline_finished.emit(f"{step} fehlgeschlagen")

    def _run_harvest(self) -> None:
        import proxyscraper.core.search_engines.google_adapter  # noqa: F401
        import proxyscraper.core.search_engines.bing_adapter  # noqa: F401
        import proxyscraper.core.search_engines.duckduckgo_adapter  # noqa: F401

        from proxyscraper.harvest.search_crawler import SearchCrawler
        from proxyscraper.harvest.tag_loader import TagLoader

        tag_loader = TagLoader(self.tag_manager)
        queries = tag_loader.get_search_queries(self.config.harvest.search.queries)
        crawler = SearchCrawler(self.config.harvest, self.storage, self.source_registry, self.event_bus)

        loop = asyncio.new_event_loop()
        loop.run_until_complete(crawler.run(queries))
        loop.close()

    def _run_check(self) -> None:
        from proxyscraper.scan.port_scanner import PortScanner
        from proxyscraper.testing.type_detector import TypeDetector
        from proxyscraper.testing.anonymity import AnonymityChecker
        from proxyscraper.testing.latency import LatencyMeasurer
        from proxyscraper.testing.geo import GeoLocator
        from proxyscraper.testing.target_checks import TargetChecker
        from proxyscraper.testing.tagging import TagEngine

        proxies = self.storage.get_proxies()
        if not proxies:
            self.signals.log_message.emit("Keine Proxies zum Prüfen vorhanden")
            return

        scanner = PortScanner(self.config.scan, self.event_bus)
        alive = scanner.scan_batch(proxies)

        loop = asyncio.new_event_loop()

        type_detector = TypeDetector(self.config.testing.type_detector)
        anon_checker = AnonymityChecker(self.config.testing.anonymity)
        latency_measurer = LatencyMeasurer(self.config.testing.latency)
        geo = GeoLocator(self.config.testing.geo)

        for proxy in alive:
            if not self._engine_running:
                break
            loop.run_until_complete(type_detector.detect(proxy))
            loop.run_until_complete(anon_checker.check(proxy))
            loop.run_until_complete(latency_measurer.measure(proxy))
            geo.enrich_proxy(proxy)

        if self.config.testing.target_checks:
            checker = TargetChecker(self.config.testing.target_checks)
            for proxy in alive:
                if not self._engine_running:
                    break
                loop.run_until_complete(checker.run_checks(proxy))

        loop.close()
        geo.close()

        tag_engine = TagEngine()
        tag_engine.apply_tags_batch(alive)

        now = datetime.utcnow()
        for proxy in alive:
            proxy.last_checked = now
        self.storage.upsert_proxies(alive)

        alive_addrs = {p.address for p in alive}
        for proxy in proxies:
            if proxy.address not in alive_addrs:
                self.storage.mark_dead(proxy.ip, proxy.port)

        for proxy in alive:
            self.storage.record_history(proxy)

    def _run_export(self) -> None:
        from proxyscraper.export.filters import ProxyFilter
        from proxyscraper.export.file_export import FileExporter

        pf = ProxyFilter(self.config.filters, self.storage)
        proxies = pf.filter()

        if not proxies:
            self.signals.log_message.emit("Keine Proxies für Export gefunden")
            return

        for sink in self.config.export.sinks:
            if sink.type == "file":
                exporter = FileExporter()
                exporter.export(proxies, sink.path, sink.format)
                self.signals.log_message.emit(f"Exportiert: {len(proxies)} Proxies nach {sink.path}")

        if not self.config.export.sinks:
            exporter = FileExporter()
            exporter.export(proxies, "out/proxies.txt", "txt")
            self.signals.log_message.emit(f"Exportiert: {len(proxies)} Proxies nach out/proxies.txt")

    def _run_serve(self) -> None:
        from proxyscraper.server.proxy_server import ProxyServer

        server = ProxyServer(self.config.server, self.storage, self.event_bus)
        self.signals.log_message.emit(
            f"Server gestartet auf {self.config.server.listen_host}:{self.config.server.listen_port}"
        )

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(server.start())
        except Exception:
            pass
        finally:
            loop.close()

    def _run_full_pipeline(self) -> None:
        self.signals.log_message.emit("=== Vollständige Pipeline ===")
        self._run_harvest()
        if self._engine_running:
            self._run_check()
        if self._engine_running:
            self._run_export()
        self.signals.log_message.emit("=== Pipeline abgeschlossen ===")

    def _stop_pipeline(self) -> None:
        self._engine_running = False
        self._append_log("Pipeline wird gestoppt...")

    def _on_pipeline_finished(self, message: str) -> None:
        self._engine_running = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.status_label.setText(message)
        self._refresh_table()
        self._append_log(message)

    def closeEvent(self, event: Any) -> None:
        self._engine_running = False
        self.storage.close()
        super().closeEvent(event)


def run_gui(config_path: str = "config.yaml") -> None:
    config = AppConfig.from_yaml(config_path)

    app = QApplication(sys.argv)
    window = MainWindow(config, config_path)
    window.show()
    sys.exit(app.exec())
