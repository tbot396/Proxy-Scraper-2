from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from .models import Proxy, Source

logger = logging.getLogger(__name__)

_PROXY_COLUMNS = (
    "ip", "port", "source_url", "protocols", "anonymity",
    "latency_ms", "country", "city", "asn", "org",
    "tags", "first_seen", "last_checked", "alive", "target_checks",
)


class Storage:
    def __init__(self, db_path: str | Path = "proxyscraper.db") -> None:
        self.db_path = str(db_path)
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.row_factory = None
            self.create_tables()
        return self._conn

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Cursor]:
        cur = self.conn.cursor()
        try:
            yield cur
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def create_tables(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS proxies (
                ip TEXT NOT NULL,
                port INTEGER NOT NULL,
                source_url TEXT DEFAULT '',
                protocols TEXT DEFAULT '[]',
                anonymity TEXT,
                latency_ms INTEGER,
                country TEXT,
                city TEXT,
                asn TEXT,
                org TEXT,
                tags TEXT DEFAULT '[]',
                first_seen TEXT NOT NULL,
                last_checked TEXT,
                alive INTEGER DEFAULT 0,
                target_checks TEXT DEFAULT '{}',
                PRIMARY KEY (ip, port)
            );

            CREATE TABLE IF NOT EXISTS sources (
                url TEXT PRIMARY KEY,
                last_crawled TEXT,
                proxy_count INTEGER DEFAULT 0,
                enabled INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip TEXT NOT NULL,
                port INTEGER NOT NULL,
                checked_at TEXT NOT NULL,
                alive INTEGER NOT NULL,
                latency_ms INTEGER,
                anonymity TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_proxies_alive ON proxies(alive);
            CREATE INDEX IF NOT EXISTS idx_proxies_country ON proxies(country);
            CREATE INDEX IF NOT EXISTS idx_proxies_latency ON proxies(latency_ms);
            CREATE INDEX IF NOT EXISTS idx_history_ip_port ON history(ip, port);
        """)

    def upsert_proxy(self, proxy: Proxy) -> None:
        cols = ", ".join(_PROXY_COLUMNS)
        placeholders = ", ".join(["?"] * len(_PROXY_COLUMNS))
        update_cols = ", ".join(
            f"{c}=excluded.{c}" for c in _PROXY_COLUMNS if c not in ("ip", "port", "first_seen")
        )
        sql = f"""
            INSERT INTO proxies ({cols}) VALUES ({placeholders})
            ON CONFLICT(ip, port) DO UPDATE SET {update_cols}
        """
        self.conn.execute(sql, proxy.to_row())
        self.conn.commit()

    def upsert_proxies(self, proxies: list[Proxy]) -> None:
        if not proxies:
            return
        cols = ", ".join(_PROXY_COLUMNS)
        placeholders = ", ".join(["?"] * len(_PROXY_COLUMNS))
        update_cols = ", ".join(
            f"{c}=excluded.{c}" for c in _PROXY_COLUMNS if c not in ("ip", "port", "first_seen")
        )
        sql = f"""
            INSERT INTO proxies ({cols}) VALUES ({placeholders})
            ON CONFLICT(ip, port) DO UPDATE SET {update_cols}
        """
        with self.transaction() as cur:
            cur.executemany(sql, [p.to_row() for p in proxies])

    def get_proxy(self, ip: str, port: int) -> Proxy | None:
        row = self.conn.execute(
            "SELECT * FROM proxies WHERE ip=? AND port=?", (ip, port)
        ).fetchone()
        return Proxy.from_row(row) if row else None

    def get_proxies(
        self,
        alive_only: bool = False,
        country: str | None = None,
        max_latency_ms: int | None = None,
        protocols: list[str] | None = None,
        anonymity: str | None = None,
        require_tags: list[str] | None = None,
        exclude_tags: list[str] | None = None,
        limit: int | None = None,
    ) -> list[Proxy]:
        conditions: list[str] = []
        params: list[object] = []

        if alive_only:
            conditions.append("alive=1")
        if country:
            conditions.append("country=?")
            params.append(country)
        if max_latency_ms is not None:
            conditions.append("(latency_ms IS NULL OR latency_ms<=?)")
            params.append(max_latency_ms)
        if anonymity:
            conditions.append("anonymity=?")
            params.append(anonymity)

        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        order = " ORDER BY latency_ms ASC NULLS LAST"
        limit_clause = f" LIMIT {limit}" if limit else ""

        rows = self.conn.execute(
            f"SELECT * FROM proxies{where}{order}{limit_clause}", params
        ).fetchall()

        results = [Proxy.from_row(r) for r in rows]

        if protocols:
            proto_set = set(protocols)
            results = [p for p in results if proto_set & set(p.protocols)]
        if require_tags:
            req = set(require_tags)
            results = [p for p in results if req <= p.tags]
        if exclude_tags:
            exc = set(exclude_tags)
            results = [p for p in results if not (exc & p.tags)]

        return results

    def count_proxies(self, alive_only: bool = False) -> int:
        cond = " WHERE alive=1" if alive_only else ""
        row = self.conn.execute(f"SELECT COUNT(*) FROM proxies{cond}").fetchone()
        return row[0] if row else 0

    def mark_dead(self, ip: str, port: int) -> None:
        self.conn.execute(
            "UPDATE proxies SET alive=0, last_checked=? WHERE ip=? AND port=?",
            (datetime.utcnow().isoformat(), ip, port),
        )
        self.conn.commit()

    def delete_proxy(self, ip: str, port: int) -> None:
        self.conn.execute("DELETE FROM proxies WHERE ip=? AND port=?", (ip, port))
        self.conn.commit()

    def delete_dead_proxies(self) -> int:
        with self.transaction() as cur:
            cur.execute("DELETE FROM proxies WHERE alive=0")
            return cur.rowcount

    def record_history(self, proxy: Proxy) -> None:
        self.conn.execute(
            "INSERT INTO history (ip, port, checked_at, alive, latency_ms, anonymity) VALUES (?, ?, ?, ?, ?, ?)",
            (proxy.ip, proxy.port, datetime.utcnow().isoformat(), int(proxy.alive), proxy.latency_ms, proxy.anonymity),
        )
        self.conn.commit()

    # --- Source management ---

    def upsert_source(self, source: Source) -> None:
        self.conn.execute(
            """INSERT INTO sources (url, last_crawled, proxy_count, enabled) VALUES (?, ?, ?, ?)
               ON CONFLICT(url) DO UPDATE SET last_crawled=excluded.last_crawled,
               proxy_count=excluded.proxy_count, enabled=excluded.enabled""",
            source.to_row(),
        )
        self.conn.commit()

    def get_sources(self, enabled_only: bool = True) -> list[Source]:
        cond = " WHERE enabled=1" if enabled_only else ""
        rows = self.conn.execute(f"SELECT * FROM sources{cond}").fetchall()
        return [Source.from_row(r) for r in rows]

    def get_due_sources(self, max_age_hours: int = 24) -> list[Source]:
        cutoff = datetime.utcnow().isoformat()
        rows = self.conn.execute(
            """SELECT * FROM sources WHERE enabled=1
               AND (last_crawled IS NULL OR julianday(?) - julianday(last_crawled) > ?)""",
            (cutoff, max_age_hours / 24.0),
        ).fetchall()
        return [Source.from_row(r) for r in rows]

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
