from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class SearchConfig(BaseModel):
    engines: list[str] = Field(default=["google", "bing", "duckduckgo"])
    queries: list[str] = Field(default_factory=list)
    freshness_days: int = 7
    max_results_per_query: int = 50
    tag_file: str = "tags.json"


class CrawlConfig(BaseModel):
    respect_robots: bool = True
    request_delay_seconds: float = 2.0
    max_requests_per_minute: int = 30


class HarvestConfig(BaseModel):
    search: SearchConfig = Field(default_factory=SearchConfig)
    crawl: CrawlConfig = Field(default_factory=CrawlConfig)


class ScanConfig(BaseModel):
    max_workers: int = 200
    connect_timeout_seconds: float = 3.0
    max_connections_per_second: int = 500
    retries: int = 1


class TypeDetectorConfig(BaseModel):
    test_url: str = "http://httpbin.org/ip"


class AnonymityConfig(BaseModel):
    echo_url: str = "http://httpbin.org/headers"


class LatencyConfig(BaseModel):
    test_url: str = "http://httpbin.org/ip"
    num_pings: int = 3


class GeoConfig(BaseModel):
    maxmind_db_path: str = "GeoLite2-City.mmdb"


class TargetCheck(BaseModel):
    name: str
    url: str
    expect_status: int = 200
    expect_contains: str = ""
    timeout_seconds: float = 10.0


class TestingConfig(BaseModel):
    type_detector: TypeDetectorConfig = Field(default_factory=TypeDetectorConfig)
    anonymity: AnonymityConfig = Field(default_factory=AnonymityConfig)
    latency: LatencyConfig = Field(default_factory=LatencyConfig)
    geo: GeoConfig = Field(default_factory=GeoConfig)
    target_checks: list[TargetCheck] = Field(default_factory=list)


class UpstreamFilter(BaseModel):
    require_tags: list[str] = Field(default_factory=list)
    exclude_tags: list[str] = Field(default_factory=list)


class ServerConfig(BaseModel):
    listen_host: str = "127.0.0.1"
    listen_port: int = 8080
    rotation: str = "per_request"
    sticky_ttl_seconds: int = 300
    upstream_filter: UpstreamFilter = Field(default_factory=UpstreamFilter)
    max_retries: int = 3
    health_check_interval_seconds: int = 60


class SecurityFilter(BaseModel):
    blocklist_files: list[str] = Field(default_factory=list)
    exclude_asns: list[str] = Field(default_factory=list)


class CountryFilter(BaseModel):
    model_config = {"populate_by_name": True}
    mode: str = "allow"
    countries: list[str] = Field(default_factory=list, alias="list")


class SpeedFilter(BaseModel):
    max_latency_ms: int = 1500


class FiltersConfig(BaseModel):
    security: SecurityFilter = Field(default_factory=SecurityFilter)
    country: CountryFilter = Field(default_factory=CountryFilter)
    speed: SpeedFilter = Field(default_factory=SpeedFilter)


class ExportSink(BaseModel):
    type: str  # file, http, ftp, email
    format: str = "txt"
    path: str = ""
    only_tags: list[str] = Field(default_factory=list)
    method: str = "POST"
    url: str = ""
    auth_header: str = ""
    interval_seconds: int = 300
    host: str = ""
    remote_path: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    to: list[str] = Field(default_factory=list)
    trigger: str = ""


class ExportConfig(BaseModel):
    sinks: list[ExportSink] = Field(default_factory=list)


class GUIConfig(BaseModel):
    show_tag_editor: bool = True
    show_config_dialog: bool = True
    theme: str = "dark"


class LoggingConfig(BaseModel):
    level: str = "INFO"
    file: str = "proxyscraper.log"
    max_bytes: int = 10_485_760
    backup_count: int = 3


class AppConfig(BaseSettings):
    harvest: HarvestConfig = Field(default_factory=HarvestConfig)
    scan: ScanConfig = Field(default_factory=ScanConfig)
    testing: TestingConfig = Field(default_factory=TestingConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    filters: FiltersConfig = Field(default_factory=FiltersConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)
    gui: GUIConfig = Field(default_factory=GUIConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    database_path: str = "proxyscraper.db"

    @classmethod
    def from_yaml(cls, path: str | Path) -> AppConfig:
        path = Path(path)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return cls(**data)
        return cls()

    def save_yaml(self, path: str | Path) -> None:
        path = Path(path)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(
                self.model_dump(mode="json", by_alias=True),
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )

    def update_section(self, section: str, values: dict[str, Any]) -> None:
        current = getattr(self, section, None)
        if current is not None and isinstance(current, BaseModel):
            updated = current.model_copy(update=values)
            object.__setattr__(self, section, updated)
