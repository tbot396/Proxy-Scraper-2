# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Proxy Scraper 2.0 is a modular Python tool for harvesting, validating, classifying, rotating, and exporting proxy servers. It has a headless engine core (no GUI dependency) and an optional PySide6 GUI layer.

## Commands

```bash
# Install dependencies
pip install -e ".[gui,dev]"

# Run the full pipeline (harvest → scan → test → tag → export)
python -m proxyscraper run --config config.yaml

# Run individual stages
python -m proxyscraper harvest --engines google,bing
python -m proxyscraper check
python -m proxyscraper serve --port 8080 --rotation per_request
python -m proxyscraper export --format txt --output out/proxies.txt

# Launch GUI
python -m proxyscraper gui

# Run tests
pytest
pytest tests/test_extractor.py -v          # single test file
pytest -k "test_extract_proxies" -v        # single test by name
```

## Architecture

The project follows a strict **engine/presentation separation**:

- **`core/`** — Shared foundation: data models (`models.py`), SQLite persistence (`storage.py`), Pydantic config (`config.py`), event bus (`events.py`), tag manager (`tag_manager.py`), async utilities, and exceptions.
- **`core/search_engines/`** — Pluggable search adapters (Google, Bing, DuckDuckGo) using `__init_subclass__` auto-registration on `BaseSearchAdapter`. Adding a new engine = one file subclassing `BaseSearchAdapter` with a `name` class attribute.
- **`harvest/`** — Search crawler (drives adapters + rate limiting + robots.txt), regex extractor (IP:Port from HTML/text), source registry (SQLite-backed URL dedup), tag loader (reads `tags.json`).
- **`scan/`** — `ThreadPoolExecutor`-based TCP port scanner with adaptive throttling.
- **`testing/`** — Type detection (HTTP/HTTPS/SOCKS4/5 via handshake), anonymity classification (transparent/anonymous/elite via header analysis), latency measurement, MaxMind geolocation, custom URL target checks, and rule-based smart tagging engine.
- **`export/`** — Chainable filters (security blocklist, country allow/block, speed) and export sinks (file txt/csv/json, FTP, email/SMTP, HTTP webhook).
- **`server/`** — asyncio-based local forwarding proxy with rotation strategies (per_request, sticky, on_failure), self-healing pool, and periodic health checks.
- **`ui/`** — PySide6 GUI: `MainWindow` with proxy table + log + tag editor, `ConfigDialog` with tabs for all config sections, `TagEditor` widget. Dark/light themes via QSS stylesheets.
- **`cli.py`** — argparse CLI with subcommands: `harvest`, `check`, `serve`, `export`, `run`, `gui`.

### Key Design Patterns

- **Event bus** (`core/events.py`): Thread-safe callback registry (`EventBus`) decouples engine from GUI. Engine emits `EventType` enums; GUI subscribes and re-emits as Qt signals to cross the thread boundary.
- **Search adapter registration**: Subclasses of `BaseSearchAdapter` auto-register via `__init_subclass__`. Use `BaseSearchAdapter.get_adapter("name")` to instantiate.
- **Proxy persistence**: `Storage` class owns a single SQLite connection in WAL mode. `Proxy` dataclass has `to_row()`/`from_row()` for serialization. Dedup by `(ip, port)` composite primary key.
- **Config**: Single `AppConfig` (pydantic-settings) loaded from `config.yaml`. Nested models for each subsystem. GUI config dialog reads/writes through these same models.

### Concurrency Model

- **Port scanning**: `concurrent.futures.ThreadPoolExecutor` with blocking sockets.
- **Harvesting/testing**: `asyncio` with `httpx.AsyncClient`.
- **GUI**: Engine runs in a `threading.Thread`; events cross to the Qt thread via signals.
- **Proxy server**: `asyncio.start_server` with async stream piping.

## Configuration Files

- `config.yaml` — Main configuration (all subsystem settings).
- `tags.json` — Search tags for harvesting (JSON format, `{"search_tags": [...]}`).
- `.env` — API keys: `GOOGLE_API_KEY`, `GOOGLE_CX`, `BING_API_KEY` (loaded via env vars).

## Dependencies

Core: `httpx[socks]`, `python-socks`, `selectolax`, `geoip2`, `pydantic-settings`, `PyYAML`.
GUI: `PySide6`. Dev: `pytest`, `pytest-asyncio`, `black`, `respx`.

## Language

The GUI labels and user-facing strings are in **German**. Code identifiers, comments, and docstrings are in **English**.
