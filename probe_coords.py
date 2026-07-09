"""Standalone probe for polttoaine.net's coordinate endpoints.

Not part of the poller or test suite — run manually to check whether the
site's coordinate response formats still match docs/SCRAPER.md. As of
2026-07-09: `ajax.php?act=map` returns an empty body under every combination
of params/method/headers tried (see SCRAPER.md for the full list); the
per-station map page (`index.php?cmd=map&id=<id>`) works and is what
coords.py actually uses. Update SCRAPER.md first if this probe finds the
site has changed, then coords.py.

Usage: python probe_coords.py [station_id]
"""

from __future__ import annotations

import sys

import requests

from coords import LATLNG_RE, MAP_PAGE_URL
from parser import USER_AGENT

BULK_URL = "https://polttoaine.net/ajax.php?act=map"


def probe_bulk() -> None:
    response = requests.get(BULK_URL, headers={"User-Agent": USER_AGENT}, timeout=15)
    print(f"[bulk] {BULK_URL}")
    print(f"  status={response.status_code} content-type={response.headers.get('Content-Type')} "
          f"bytes={len(response.content)}")
    if response.content:
        print("  --- first 500 chars ---")
        print(" ", response.text[:500])
    else:
        print("  empty body -- bulk endpoint not usable, see SCRAPER.md")


def probe_station_page(station_id: int) -> None:
    url = MAP_PAGE_URL.format(station_id=station_id)
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
    response.encoding = "cp1252"
    print(f"\n[per-station] {url}")
    print(f"  status={response.status_code} bytes={len(response.content)}")
    match = LATLNG_RE.search(response.text)
    print(f"  LatLng match: {match.group(0) if match else None}")


def main() -> None:
    station_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1051
    probe_bulk()
    probe_station_page(station_id)


if __name__ == "__main__":
    main()
