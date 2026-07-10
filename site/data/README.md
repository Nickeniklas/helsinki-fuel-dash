# site/data — JSON export shapes

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
