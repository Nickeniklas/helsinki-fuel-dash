"""Coordinate fetching for polttoaine.net stations. Contract: docs/SCRAPER.md.

The bulk `ajax.php?act=map` endpoint was tested 2026-07-09 and returns an
empty body under every param/method/header combination tried — see
SCRAPER.md and probe_coords.py. This module uses the confirmed-working
fallback instead: one request per station to its map page.
"""

from __future__ import annotations

import logging
import re
import time
from sqlite3 import Connection

import requests

from db import set_station_coords, stations_missing_coords
from parser import USER_AGENT

logger = logging.getLogger(__name__)

MAP_PAGE_URL = "https://polttoaine.net/index.php?cmd=map&id={station_id}"

LATLNG_RE = re.compile(r"new google\.maps\.LatLng\(\s*(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)\s*\)")
LAT_RE = re.compile(r"lat\s*[:=]\s*'(-?\d+\.\d+)'")
LON_RE = re.compile(r"lon\s*[:=]\s*'(-?\d+\.\d+)'")

REQUEST_SLEEP_S = 0.1


def fetch_coords(station_id: int) -> tuple[float, float] | None:
    """Fetch and parse one station's coords from its map page.

    Tries the `new google.maps.LatLng(lat, lon)` call first, falls back to
    separate `lat:'..'` / `lon:'..'` literals per SCRAPER.md. Returns None
    (and logs) if neither pattern is found.
    """
    url = MAP_PAGE_URL.format(station_id=station_id)
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
    response.raise_for_status()
    response.encoding = "cp1252"
    text = response.text

    match = LATLNG_RE.search(text)
    if match:
        return float(match.group(1)), float(match.group(2))

    lat_match, lon_match = LAT_RE.search(text), LON_RE.search(text)
    if lat_match and lon_match:
        return float(lat_match.group(1)), float(lon_match.group(1))

    logger.warning("station %s: no coordinate pattern found on %s", station_id, url)
    return None


def fetch_missing_coords(conn: Connection) -> int:
    """Fetch and cache coords for every station in the DB that doesn't have
    them yet. Politely spaced (REQUEST_SLEEP_S between requests), same as
    page crawling. Returns the count of stations successfully updated.
    """
    station_ids = stations_missing_coords(conn)
    updated = 0
    for station_id in station_ids:
        coords = fetch_coords(station_id)
        if coords is not None:
            lat, lon = coords
            if set_station_coords(conn, station_id, lat, lon):
                updated += 1
        time.sleep(REQUEST_SLEEP_S)
    conn.commit()
    return updated
