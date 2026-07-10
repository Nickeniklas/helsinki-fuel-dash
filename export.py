"""JSON export: fuel.db -> site/data/*.json for the static dashboard.

File shapes are documented in site/data/README.md (written by this module).
No geographic filtering here -- the dashboard applies the 15 km display
radius client-side, per docs/PLAN.md.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from statistics import median

from db import connect

logger = logging.getLogger(__name__)

FUELS = ("95", "98", "dsl")

DB_PATH = Path(__file__).resolve().parent / "fuel.db"
OUT_DIR = Path(__file__).resolve().parent / "site" / "data"

DATA_README = """# site/data — JSON export shapes

Written by export.py from fuel.db. No geographic filtering: every station in
the DB is included, the dashboard applies the 15 km display radius itself.

## stations.json

Array of every known station, its coords, and its latest seen price per
fuel (independently -- a fuel's latest price can be from an earlier date
than another fuel's if it wasn't reported on the most recent day). `lat`/
`lon` are `null` until a station's coords have been backfilled. A fuel is
`null` under `latest` if that station has never reported it.

```json
[
  {
    "station_id": 1051,
    "name": "St1, Lauttasaari Heikkilantie 12",
    "lat": 60.156120,
    "lon": 24.883408,
    "latest": {
      "95": {"date": "2026-07-09", "price": 2.099},
      "98": {"date": "2026-07-09", "price": 2.199},
      "dsl": null
    }
  }
]
```

## history.json

Object keyed by station_id (as a string, JSON object keys are always
strings). Each value is that station's full price history, one entry per
date it has any price, sorted oldest to newest. A fuel key is only present
on a date if that fuel was reported that day.

```json
{
  "1051": [
    {"date": "2026-07-08", "95": 2.089, "98": 2.189},
    {"date": "2026-07-09", "95": 2.099, "98": 2.199, "dsl": 2.129}
  ]
}
```

## medians.json

Array of daily area-wide medians per fuel, one entry per date that has any
price data, sorted oldest to newest. A fuel is `null` on a date if no
station reported it that day.

```json
[
  {"date": "2026-07-08", "95": 2.089, "98": 2.189, "dsl": null},
  {"date": "2026-07-09", "95": 2.079, "98": 2.199, "dsl": 2.129}
]
```
"""


def build_stations(conn) -> list[dict]:
    """All stations with coords and each fuel's latest seen price, independently."""
    price_rows = conn.execute(
        "SELECT station_id, fuel, date, price FROM prices ORDER BY date"
    ).fetchall()
    latest: dict[int, dict[str, dict]] = {}
    for station_id, fuel, price_date, price in price_rows:
        # ORDER BY date ascending -> the last write per (station, fuel) is the latest;
        # UNIQUE(station_id, fuel, date) means no same-date tie is possible.
        latest.setdefault(station_id, {})[fuel] = {"date": price_date, "price": price}

    station_rows = conn.execute(
        "SELECT station_id, name, lat, lon FROM stations ORDER BY station_id"
    ).fetchall()
    return [
        {
            "station_id": station_id,
            "name": name,
            "lat": lat,
            "lon": lon,
            "latest": {fuel: latest.get(station_id, {}).get(fuel) for fuel in FUELS},
        }
        for station_id, name, lat, lon in station_rows
    ]


def build_history(conn) -> dict[str, list[dict]]:
    """Per-station price history, one entry per date, oldest to newest."""
    rows = conn.execute(
        "SELECT station_id, fuel, date, price FROM prices ORDER BY station_id, date"
    ).fetchall()
    by_station: dict[int, dict[str, dict]] = {}
    for station_id, fuel, price_date, price in rows:
        day = by_station.setdefault(station_id, {}).setdefault(price_date, {"date": price_date})
        day[fuel] = price
    return {
        str(station_id): sorted(days.values(), key=lambda d: d["date"])
        for station_id, days in by_station.items()
    }


def build_medians(conn) -> list[dict]:
    """Daily area-wide median price per fuel, oldest to newest."""
    rows = conn.execute("SELECT date, fuel, price FROM prices ORDER BY date").fetchall()
    by_date: dict[str, dict[str, list[float]]] = {}
    for price_date, fuel, price in rows:
        by_date.setdefault(price_date, {}).setdefault(fuel, []).append(price)
    return [
        {
            "date": price_date,
            **{
                fuel: round(median(by_date[price_date][fuel]), 3) if fuel in by_date[price_date] else None
                for fuel in FUELS
            },
        }
        for price_date in sorted(by_date)
    ]


def _write_json(path: Path, data) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def export(db_path: Path = DB_PATH, out_dir: Path = OUT_DIR) -> None:
    """Read fuel.db and write stations.json, history.json, medians.json to out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    try:
        _write_json(out_dir / "stations.json", build_stations(conn))
        _write_json(out_dir / "history.json", build_history(conn))
        _write_json(out_dir / "medians.json", build_medians(conn))
    finally:
        conn.close()
    (out_dir / "README.md").write_text(DATA_README, encoding="utf-8")
    logger.info("exported JSON to %s", out_dir)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    export()
