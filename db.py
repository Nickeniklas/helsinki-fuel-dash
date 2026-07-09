"""SQLite storage layer. Schema and dedupe rule: docs/SCRAPER.md.

Owns the only writes to fuel.db: station upsert, coordinate backfill, and
price upsert with same-day-overwrite dedupe on (station_id, fuel, date).
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import date
from pathlib import Path

from parser import PRICE_MAX, PRICE_MIN

logger = logging.getLogger(__name__)

LAT_MIN, LAT_MAX = 59.7, 70.1
LON_MIN, LON_MAX = 20.5, 31.6

SCHEMA = """
CREATE TABLE IF NOT EXISTS stations (
  station_id INTEGER PRIMARY KEY,
  name       TEXT NOT NULL,
  lat        REAL,
  lon        REAL,
  first_seen TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prices (
  station_id INTEGER NOT NULL REFERENCES stations(station_id),
  fuel       TEXT NOT NULL,
  date       TEXT NOT NULL,
  price      REAL NOT NULL,
  UNIQUE(station_id, fuel, date)
);
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open (creating if needed) the fuel DB and ensure the schema exists."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def upsert_station(conn: sqlite3.Connection, station_id: int, name: str, seen_on: date) -> None:
    """Register a station on first sight. Existing rows are left untouched —
    name/coords are handled by set_station_coords(), not overwritten here."""
    conn.execute(
        "INSERT OR IGNORE INTO stations (station_id, name, lat, lon, first_seen) "
        "VALUES (?, ?, NULL, NULL, ?)",
        (station_id, name, seen_on.isoformat()),
    )


def stations_missing_coords(conn: sqlite3.Connection) -> list[int]:
    """Station IDs that still need a coordinate fetch."""
    rows = conn.execute(
        "SELECT station_id FROM stations WHERE lat IS NULL OR lon IS NULL"
    ).fetchall()
    return [row[0] for row in rows]


def set_station_coords(conn: sqlite3.Connection, station_id: int, lat: float, lon: float) -> bool:
    """Cache coords for a station. Returns False (and logs) if out of the
    Finland bbox sanity bounds, per SCRAPER.md — coords are never refetched,
    so a bad value here would stick permanently if we didn't reject it."""
    if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
        logger.warning(
            "station %s: coords (%.5f, %.5f) outside Finland bbox "
            "[%.1f, %.1f] x [%.1f, %.1f] — skipping",
            station_id, lat, lon, LAT_MIN, LAT_MAX, LON_MIN, LON_MAX,
        )
        return False
    conn.execute(
        "UPDATE stations SET lat = ?, lon = ? WHERE station_id = ?",
        (lat, lon, station_id),
    )
    return True


def upsert_price(conn: sqlite3.Connection, station_id: int, fuel: str, price_date: str, price: float) -> bool:
    """Insert a price, overwriting same-day (station_id, fuel, date) — latest
    seen wins, per the dedupe rule. Returns False (and logs) if the price is
    outside sanity bounds; the row is skipped, not just the fuel field."""
    if not (PRICE_MIN <= price <= PRICE_MAX):
        logger.warning(
            "station %s %s %s: price %.3f outside sanity bounds [%.2f, %.2f] — skipping",
            station_id, fuel, price_date, price, PRICE_MIN, PRICE_MAX,
        )
        return False
    conn.execute(
        "INSERT INTO prices (station_id, fuel, date, price) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(station_id, fuel, date) DO UPDATE SET price = excluded.price",
        (station_id, fuel, price_date, price),
    )
    return True


def ingest_rows(conn: sqlite3.Connection, rows: list[dict], seen_on: date) -> None:
    """Upsert a batch of parser.parse_page() rows: register any new stations,
    then upsert each present fuel price. Safe to call twice with the same
    rows (idempotent) — same-day prices just overwrite themselves."""
    for row in rows:
        upsert_station(conn, row["station_id"], row["station_name"], seen_on)
        for fuel, price in row["prices"].items():
            if price is not None:
                upsert_price(conn, row["station_id"], fuel, row["date"], price)
    conn.commit()
