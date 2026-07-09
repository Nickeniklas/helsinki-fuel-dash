"""Poller entry point: fetch configured pages, parse, upsert, backfill coords.

Run manually or on the GH Actions cron (12 h). Idempotent — same-day re-runs
just overwrite prices to the latest seen value, per the dedupe rule in
docs/SCRAPER.md.
"""

from __future__ import annotations

import logging
import time
from datetime import date
from pathlib import Path

from coords import fetch_missing_coords
from db import connect, ingest_rows
from parser import USER_AGENT, fetch_page, parse_page

logger = logging.getLogger(__name__)

BASE_URL = "https://polttoaine.net"

# Starting page set per docs/SCRAPER.md, all verified live 2026-07-09.
PAGES = [
    f"{BASE_URL}/Helsinki",
    f"{BASE_URL}/index.php?t=PK-Seutu",
    f"{BASE_URL}/Keha_%20I",
    f"{BASE_URL}/Keha_%20III%20(E18)",
]

PAGE_REQUEST_SLEEP_S = 0.1
DB_PATH = Path(__file__).resolve().parent / "fuel.db"


def poll(db_path: Path = DB_PATH, pages: list[str] = PAGES, reference: date | None = None) -> int:
    """Fetch every configured page, dedupe stations across pages by ID, and
    upsert everything into the DB. Returns the number of distinct rows
    ingested (post station-dedupe)."""
    if reference is None:
        reference = date.today()

    rows_by_key: dict[tuple[int, str], dict] = {}
    for i, url in enumerate(pages):
        html = fetch_page(url)
        for row in parse_page(html, reference=reference):
            rows_by_key[(row["station_id"], row["date"])] = row
        if i < len(pages) - 1:
            time.sleep(PAGE_REQUEST_SLEEP_S)

    rows = list(rows_by_key.values())
    conn = connect(db_path)
    try:
        ingest_rows(conn, rows, seen_on=reference)
        updated = fetch_missing_coords(conn)
        logger.info("ingested %d rows, fetched coords for %d new stations", len(rows), updated)
    finally:
        conn.close()
    return len(rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("polling with User-Agent: %s", USER_AGENT)
    poll()
