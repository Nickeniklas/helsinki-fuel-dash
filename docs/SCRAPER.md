# SCRAPER contract — polttoaine.net

Parsing spec written from reading Pumperly (GPL-3.0) plus our own checks, 2026-07-08.
Facts only; all code in this repo is written from scratch. If the site changes,
update this doc first, then the parser.

## Pages to crawl (config list)

- City page: `index.php?t=Helsinki` style
- Regional views: `?t=PK-Seutu` etc.
- Highway pages: `1-tie`, `4-tie`, `Kehä I`, `Kehä III (E18)`, ...
- Starting set: Helsinki, PK-Seutu, Kehä I, Kehä III. Dedupe stations across pages
  by station ID; the same station appears on multiple pages.

## Row format

- Price rows are `<tr>` with exactly **5 `<td>`**:
  1. station name + map link
  2. date, `DD.MM.` with **no year**
  3. 95E10
  4. 98E
  5. Diesel
- **Key on the td count, not on class.** Regional pages (`?t=PK-Seutu` etc.) omit
  the `E10` class on `<tr>`, city pages have it.
- Station ID comes from the map link: `cmd=map&id=XXXX`. This is the canonical ID.
- ~5–8 % of rows have no map link → **skip** (no ID, can't geocode).
- 98E cell may carry a `*` V-Power marker, sometimes wrapped in
  `<span class="E99">` → strip marker and span, keep the number.
- Empty price cells happen (not every report covers all three fuels) → store NULL,
  never 0.

## Date resolution

Source gives `DD.MM.` only. Resolve year at parse time:
- Attach the current year; if the resulting date is in the future, subtract one year
  (handles the days around New Year).
- Reports older than 5 days shouldn't appear at all; if one parses to > 7 days old,
  log it, it means the rule or the site changed.

## Sanity checks (drop row + log on failure)

- Price bounds: 0.80–4.00 EUR
- Coordinate bounds (Finland bbox): lat 59.7–70.1, lon 20.5–31.6

## Coordinates

- Static per station → fetch **once**, cache in `stations` table, never refetch.
- Preferred (unverified, test first): `ajax.php` with `act=map` returns all station
  locations without prices in one call.
- Fallback: per-station map page, parse `new google.maps.LatLng(lat, lon)`;
  secondary fallback `lat:'..'` / `lon:'..'` patterns.

## Schema

```sql
CREATE TABLE stations (
  station_id INTEGER PRIMARY KEY,   -- polttoaine.net id from cmd=map&id=
  name       TEXT NOT NULL,
  lat        REAL,
  lon        REAL,
  first_seen TEXT NOT NULL          -- ISO date
);

CREATE TABLE prices (
  station_id INTEGER NOT NULL REFERENCES stations(station_id),
  fuel       TEXT NOT NULL,         -- '95' | '98' | 'dsl'
  date       TEXT NOT NULL,         -- ISO date, resolved from DD.MM.
  price      REAL NOT NULL,
  UNIQUE(station_id, fuel, date)    -- ON CONFLICT: overwrite price (latest wins)
);
```

Date-only resolution is a source limitation: no timestamps exist, so one row per
station/fuel/day, same-day changes overwrite to the latest seen value.

## Politeness rules (hard)

- Poll every 12 h, never faster (Pumperly's cadence; 5-day price visibility makes
  more frequent polling pointless anyway)
- 100 ms sleep between page requests
- Honest User-Agent naming the project and a contact/repo URL
- Respect robots.txt: checked manually before first crawl AND the poller re-checks
  and aborts if crawling becomes disallowed

## Export

Poller writes `site/data/*.json`: all stations with coords, current prices,
per-station history, area medians. No geographic filtering here; the dashboard
applies the 15 km display radius client-side (config).
