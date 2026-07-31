# Proxy Scraper 2.0

A modular Python tool for harvesting, validating, classifying, rotating, and exporting proxy servers. Features a headless engine core and an optional PySide6 GUI.

## Features

- **Harvest** — Search for proxy sources via Google, Bing, and DuckDuckGo APIs, crawl result pages, and extract IP:port pairs with regex and HTML table parsing
- **Scan** — Multithreaded TCP port scanner with adaptive throttling (up to 500 conn/s)
- **Test** — Protocol detection (HTTP/HTTPS/SOCKS4/SOCKS5), anonymity classification (transparent/anonymous/elite), latency measurement, and MaxMind geolocation
- **Tag** — Rule-based smart tagging engine with default and custom rules
- **Filter** — Security blocklists (IP, CIDR, ASN), country allow/block lists, speed thresholds
- **Export** — File (TXT/CSV/JSON), FTP/FTPS, email (SMTP), HTTP webhook with trigger expressions
- **Serve** — Local forwarding proxy server with rotation strategies (per-request, sticky, on-failure) and self-healing pool
- **GUI** — PySide6 desktop app with dark/light themes, proxy table, log viewer, tag editor, and config dialog

## Requirements

- Python 3.11+
- API keys for Google Custom Search and/or Bing Web Search (optional — DuckDuckGo works without keys)
- MaxMind GeoLite2 City database (optional, for geolocation)

## Installation

```bash
# Clone the repo
git clone https://github.com/tbot396/Proxy-Scraper-2.git
cd Proxy-Scraper-2

# Install core
pip install -e .

# With GUI support
pip install -e ".[gui]"

# With dev tools (pytest, black, etc.)
pip install -e ".[gui,dev]"
```

## Configuration

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
```

All settings are in `config.yaml`. Key sections:

| Section | Purpose |
|---------|---------|
| `harvest.search` | Search engines, queries, freshness |
| `harvest.crawl` | Rate limiting, robots.txt compliance |
| `scan` | Worker count, timeouts, throttling |
| `testing` | Detection URLs, ping count, GeoIP path |
| `server` | Listen address, rotation strategy, health checks |
| `filters` | Blocklists, country filters, speed limits |
| `export` | Output sinks with triggers and formats |

Search tags are defined in `tags.json`.

## Usage

### CLI

```bash
# Run the full pipeline (harvest -> scan -> test -> tag -> export)
python -m proxyscraper run --config config.yaml

# Continuous mode with 30-minute interval
python -m proxyscraper run --continuous --interval 1800

# Individual stages
python -m proxyscraper harvest --engines google,bing
python -m proxyscraper check
python -m proxyscraper export --format txt --output proxies.txt

# Start local proxy server
python -m proxyscraper serve --port 8080 --rotation per_request
```

### GUI

```bash
python -m proxyscraper gui
```

### Export Sinks

Configure export sinks in `config.yaml`:

```yaml
export:
  sinks:
    - type: file
      format: txt
      path: out/proxies.txt
      trigger: "new_elite >= 10"

    - type: http
      url: https://api.example.com/proxies
      method: POST
      auth_header: "Bearer ${API_TOKEN}"
      trigger: "total >= 50"
```

Trigger expressions support: `total`, `alive`, `new_<tag>`, `count_<tag>` with operators `>=`, `<=`, `>`, `<`, `==`, `!=`.

## Architecture

```
proxyscraper/
  core/           Shared foundation (models, storage, config, events, async utils)
    search_engines/   Pluggable adapters (Google, Bing, DuckDuckGo)
  harvest/        Search crawler, regex extractor, source registry
  scan/           ThreadPoolExecutor-based port scanner
  testing/        Type detection, anonymity, latency, geo, tagging
  export/         Filters and sinks (file, FTP, email, HTTP)
  server/         Async proxy server with rotation
  ui/             PySide6 GUI (main window, config dialog, tag editor, themes)
  cli.py          argparse CLI with subcommands
```

**Key patterns:**
- Event bus decouples engine from GUI (thread-safe callbacks + Qt signals)
- Search adapters auto-register via `__init_subclass__`
- SQLite in WAL mode for proxy persistence, dedup by `(ip, port)`
- Pydantic-settings for typed config from YAML

## Tests

```bash
# Run all tests
pytest

# Verbose with specific file
pytest tests/test_extractor.py -v

# Single test by name
pytest -k "test_extract_proxies" -v
```

124 tests covering models, storage, config, events, extractor, filters, tagging, source registry, tag loader, export, search adapters, and proxy server.

## License

MIT
