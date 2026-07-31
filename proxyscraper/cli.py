from __future__ import annotations

import argparse
import asyncio
import logging
import logging.handlers
import sys
import time
from datetime import datetime
from pathlib import Path

from proxyscraper.core.config import AppConfig
from proxyscraper.core.events import EventBus, EventType
from proxyscraper.core.storage import Storage
from proxyscraper.core.tag_manager import TagManager
from proxyscraper.harvest.search_crawler import SearchCrawler
from proxyscraper.harvest.source_registry import SourceRegistry
from proxyscraper.harvest.tag_loader import TagLoader


def setup_logging(config: AppConfig) -> None:
    root = logging.getLogger()
    root.setLevel(getattr(logging, config.logging.level.upper(), logging.INFO))

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    root.addHandler(console)

    if config.logging.file:
        file_handler = logging.handlers.RotatingFileHandler(
            config.logging.file,
            maxBytes=config.logging.max_bytes,
            backupCount=config.logging.backup_count,
        )
        file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        root.addHandler(file_handler)


def create_app_context(config_path: str = "config.yaml"):
    config = AppConfig.from_yaml(config_path)
    event_bus = EventBus()
    storage = Storage(config.database_path)
    tag_manager = TagManager(config.harvest.search.tag_file, event_bus)
    source_registry = SourceRegistry(storage)
    return config, event_bus, storage, tag_manager, source_registry


def _register_adapters() -> None:
    import proxyscraper.core.search_engines.google_adapter  # noqa: F401
    import proxyscraper.core.search_engines.bing_adapter  # noqa: F401
    import proxyscraper.core.search_engines.duckduckgo_adapter  # noqa: F401


def _run_harvest(config, event_bus, storage, tag_manager, source_registry, engines=None):
    _register_adapters()
    tag_loader = TagLoader(tag_manager)
    queries = tag_loader.get_search_queries(config.harvest.search.queries)
    engine_list = engines or config.harvest.search.engines

    crawler = SearchCrawler(config.harvest, storage, source_registry, event_bus)
    return asyncio.run(crawler.run(queries, engine_list))


def _run_check(config, event_bus, storage):
    from proxyscraper.scan.port_scanner import PortScanner
    from proxyscraper.testing.type_detector import TypeDetector
    from proxyscraper.testing.anonymity import AnonymityChecker
    from proxyscraper.testing.latency import LatencyMeasurer
    from proxyscraper.testing.geo import GeoLocator
    from proxyscraper.testing.target_checks import TargetChecker
    from proxyscraper.testing.tagging import TagEngine

    proxies = storage.get_proxies()
    if not proxies:
        print("No proxies in database to check")
        return []

    print(f"Checking {len(proxies)} proxies...")

    scanner = PortScanner(config.scan, event_bus)
    alive = scanner.scan_batch(proxies)
    print(f"Port scan: {len(alive)}/{len(proxies)} alive")

    type_detector = TypeDetector(config.testing.type_detector)
    anon_checker = AnonymityChecker(config.testing.anonymity)
    latency_measurer = LatencyMeasurer(config.testing.latency)
    geo = GeoLocator(config.testing.geo)

    print("Testing proxies...")
    for i, proxy in enumerate(alive, 1):
        if i % 10 == 0:
            print(f"  Testing {i}/{len(alive)}...")
        asyncio.run(type_detector.detect(proxy))
        asyncio.run(anon_checker.check(proxy))
        asyncio.run(latency_measurer.measure(proxy))
        geo.enrich_proxy(proxy)

    if config.testing.target_checks:
        checker = TargetChecker(config.testing.target_checks)
        for proxy in alive:
            asyncio.run(checker.run_checks(proxy))

    geo.close()

    tag_engine = TagEngine()
    tag_engine.apply_tags_batch(alive)

    now = datetime.utcnow()
    for proxy in alive:
        proxy.last_checked = now
    storage.upsert_proxies(alive)

    alive_addrs = {p.address for p in alive}
    for proxy in proxies:
        if proxy.address not in alive_addrs:
            storage.mark_dead(proxy.ip, proxy.port)
    for proxy in alive:
        storage.record_history(proxy)

    print(f"Check complete: {len(alive)} alive, {len(proxies) - len(alive)} dead")
    return alive


def _run_export(config, storage, event_bus):
    from proxyscraper.export.filters import ProxyFilter
    from proxyscraper.export.export_manager import ExportManager

    pf = ProxyFilter(config.filters, storage)
    filtered = pf.filter()

    if not filtered:
        print("No proxies match filter criteria")
        return filtered

    manager = ExportManager(config.export, event_bus)
    manager.export_all(filtered)

    if not config.export.sinks:
        from proxyscraper.export.file_export import FileExporter
        FileExporter().export(filtered, "out/proxies.txt", "txt")
        print(f"Exported {len(filtered)} proxies to out/proxies.txt")
    else:
        print(f"Exported {len(filtered)} proxies via {len(config.export.sinks)} sink(s)")

    return filtered


def cmd_harvest(args: argparse.Namespace) -> None:
    config, event_bus, storage, tag_manager, source_registry = create_app_context(args.config)
    setup_logging(config)

    def on_progress(url: str = "", count: int = 0, total: int = 0, **kw: object) -> None:
        print(f"  [{total}] Found {count} proxies from {url}")

    event_bus.subscribe(EventType.HARVEST_PROGRESS, on_progress)

    engines = args.engines.split(",") if args.engines else None
    print(f"Starting harvest on {engines or config.harvest.search.engines}")
    total = _run_harvest(config, event_bus, storage, tag_manager, source_registry, engines)
    print(f"Harvest complete: {total} proxies found")
    print(f"Total proxies in database: {storage.count_proxies()}")
    storage.close()


def cmd_check(args: argparse.Namespace) -> None:
    config, event_bus, storage, tag_manager, source_registry = create_app_context(args.config)
    setup_logging(config)
    _run_check(config, event_bus, storage)
    storage.close()


def cmd_serve(args: argparse.Namespace) -> None:
    config, event_bus, storage, tag_manager, source_registry = create_app_context(args.config)
    setup_logging(config)

    from proxyscraper.server.proxy_server import ProxyServer

    if args.port:
        config.server.listen_port = args.port
    if args.rotation:
        config.server.rotation = args.rotation

    server = ProxyServer(config.server, storage, event_bus)
    print(f"Starting proxy server on {config.server.listen_host}:{config.server.listen_port}")
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        print("\nServer stopped")
    finally:
        storage.close()


def cmd_export(args: argparse.Namespace) -> None:
    config, event_bus, storage, tag_manager, source_registry = create_app_context(args.config)
    setup_logging(config)

    if args.output or args.format:
        from proxyscraper.export.filters import ProxyFilter
        from proxyscraper.export.file_export import FileExporter

        pf = ProxyFilter(config.filters, storage)
        proxies = pf.filter()
        if not proxies:
            print("No proxies match filter criteria")
        else:
            fmt = args.format or "txt"
            output = args.output or f"out/proxies.{fmt}"
            FileExporter().export(proxies, output, fmt)
            print(f"Exported {len(proxies)} proxies to {output}")
    else:
        _run_export(config, storage, event_bus)

    storage.close()


def cmd_run(args: argparse.Namespace) -> None:
    config, event_bus, storage, tag_manager, source_registry = create_app_context(args.config)
    setup_logging(config)

    continuous = getattr(args, "continuous", False)
    interval = getattr(args, "interval", 600)

    iteration = 0
    try:
        while True:
            iteration += 1
            prefix = f"[Iteration {iteration}] " if continuous else ""
            print(f"\n{prefix}=== Full Pipeline ===\n")

            # 1. Harvest
            print("[1/5] Harvesting...")
            harvest_count = _run_harvest(config, event_bus, storage, tag_manager, source_registry)
            print(f"  Found {harvest_count} proxies\n")

            # 2. Port scan + 3. Testing + 4. Tagging
            print("[2/5] Scanning & Testing...")
            alive = _run_check(config, event_bus, storage)
            print()

            # 5. Export
            print("[5/5] Exporting...")
            filtered = _run_export(config, storage, event_bus)
            count = len(filtered) if filtered else 0

            print(f"\n{prefix}=== Pipeline complete: {count} working proxies ===")

            if not continuous:
                break

            print(f"\nNext iteration in {interval} seconds (Ctrl+C to stop)...")
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\nPipeline stopped by user")
    finally:
        storage.close()


def cmd_gui(args: argparse.Namespace) -> None:
    try:
        from proxyscraper.ui.main_window import run_gui
        run_gui(args.config)
    except ImportError:
        print("PySide6 is required for the GUI. Install with: pip install PySide6", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="proxyscraper",
        description="Proxy Scraper 2.0 — harvest, validate, classify, and rotate proxies",
    )
    parser.add_argument("--config", default="config.yaml", help="Path to config file")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # harvest
    p_harvest = subparsers.add_parser("harvest", help="Search and collect proxy lists")
    p_harvest.add_argument("--engines", help="Comma-separated list of search engines")
    p_harvest.set_defaults(func=cmd_harvest)

    # check
    p_check = subparsers.add_parser("check", help="Test existing proxies")
    p_check.set_defaults(func=cmd_check)

    # serve
    p_serve = subparsers.add_parser("serve", help="Start local proxy server")
    p_serve.add_argument("--port", type=int, help="Listen port")
    p_serve.add_argument("--rotation", choices=["per_request", "sticky", "on_failure"])
    p_serve.set_defaults(func=cmd_serve)

    # export
    p_export = subparsers.add_parser("export", help="Export filtered proxies")
    p_export.add_argument("--format", choices=["txt", "csv", "json"], default=None)
    p_export.add_argument("--output", help="Output file path")
    p_export.set_defaults(func=cmd_export)

    # run
    p_run = subparsers.add_parser("run", help="Full pipeline: harvest -> scan -> test -> export")
    p_run.add_argument(
        "--continuous", action="store_true",
        help="Run pipeline continuously in a loop",
    )
    p_run.add_argument(
        "--interval", type=int, default=600,
        help="Seconds between iterations in continuous mode (default: 600)",
    )
    p_run.set_defaults(func=cmd_run)

    # gui
    p_gui = subparsers.add_parser("gui", help="Launch the graphical interface")
    p_gui.set_defaults(func=cmd_gui)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
