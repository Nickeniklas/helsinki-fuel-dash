# PLAN — helsinki-fuel-dash

Replanned 2026-07-08. Original plan (same date) used the unofficial Tankille API;
that source blocked us on day one and this plan replaces it entirely. No workarounds
against Tankille. New source: scraping polttoaine.net.

## What this is

A personal fuel price tracker for the Helsinki area. No existing service shows
long-term price trends or a sorted city-wide list, so this project collects its own
history and visualizes it. Poller collects prices into SQLite, exports JSON, a static
Chart.js dashboard on GH Pages reads the JSON.

## Source: polttoaine.net

Independent crowdsourced fuel price site, ~395 active stations across Finland.
Prices submitted by drivers, each report stays visible 5 days (confirmed from the
site footer, 2026-07-08). Plain server-rendered HTML, no auth, no API key.

Parsing spec derived from reading Pumperly (GPL-3.0). **Spec only: we describe the
page format in our own docs and write our own parser. No code is copied**, keeping
this repo's licensing clean.

Full parsing contract lives in `docs/SCRAPER.md`.

## Scope

**v1**
- Poller on GH Actions cron, every 12 h, scrapes configured polttoaine.net pages
- SQLite DB + exported JSON committed back to the repo
- Dashboard: current prices sorted, colored vs each station's 7-day average;
  per-station trend chart with picker; area median lines for 95E10 / 98E / Diesel

**v2 (deferred until weeks of data exist)**
- Day-of-week / price-cycle heatmap
- "Fill now or wait" signal

No backfill exists in this source (5 days visible, date-only resolution), so history
accumulates from the first poll onward. v2 waits accordingly.

## Decisions

| Decision | Choice | Why |
|---|---|---|
| Source | Scrape polttoaine.net | Tankille blocked us; polttoaine is public HTML, no auth, widest crowdsourced coverage (~395 stations) |
| Pumperly usage | Spec only, never code | Pumperly is GPL-3.0; copying code would infect the repo. Page-format facts are not copyrightable |
| Ingest scope | Ingest every row from every configured page, no geographic filter at ingest | More data is strictly better; filtering at ingest throws away history we can never recover |
| Geographic filter | 15 km radius from Helsinki center applied at display time, config value in the dashboard | Keeps the DB complete while the UI stays focused; radius can change later without data loss |
| Old Tankille schema | Dropped, clean DB | Tankille is not coming back soon; its ID space and timestamp semantics don't map to polttoaine anyway |
| Dedupe key | `UNIQUE(station_id, fuel, date)`, same-day re-poll overwrites price | Source has date-only resolution (DD.MM.), no timestamps; latest seen value per day is the best available truth |
| Poll cadence | Every 12 h, 100 ms between page requests, honest User-Agent | Matches Pumperly's observed politeness; with 5-day visibility 12 h loses nothing |
| Coordinates | Cached in a `stations` table, fetched once per new station | Coords are static; refetching per poll is wasted load on their server |
| Coord source | Per-station map page parse | `ajax.php?act=map` bulk endpoint tested 2026-07-09, returns empty under every param/method/header combo tried — not usable. N map-page fetches it is, cached forever per station |
| Poller runtime | Plain Python script, no LLM | Deterministic parsing needs no model; decision carried over from the original plan (Claude Code Routine rejected: shouldn't depend on the PC being on) |
| Hosting | GH Actions cron + GH Pages serving `site/`, never `docs/` | Free, no server, already the plan; plan docs live in `docs/` and must not be published |

## Architecture

```
GH Actions cron (12 h)          .github/workflows/poll.yml
  ├─ poll.py
  │    ├─ GET configured polttoaine.net pages (100 ms apart)
  │    ├─ parse rows            → docs/SCRAPER.md is the contract
  │    ├─ resolve new stations  → stations table (cached coords)
  │    └─ upsert prices         → fuel.db (SQLite)
  ├─ export.py
  │    └─ write site/data/*.json  (all stations, coords included — shapes in site/data/README.md)
  └─ commit fuel.db + site/data/*.json back to repo, then deploy Pages
       (own deploy job: GITHUB_TOKEN pushes don't trigger pages.yml's push trigger)

GH Pages ── serves site/ ── index.html + Chart.js
                              └─ reads site/data/*.json
                              └─ applies 15 km display radius (config)
```

## Build order

1. Manual robots.txt + terms check on polttoaine.net (done, 2026-07-09: `ajax.php`
   isn't disallowed; nothing else in the crawl path is either)
2. Parser: fetch one city page, parse rows to dicts, unit-test against saved HTML fixtures (done)
3. Coordinate resolution: test `ajax.php?act=map`, else map-page parse; `stations` table (done)
4. SQLite schema + upsert + dedupe (done)
5. JSON export (done, 2026-07-10: `export.py`, 14 unit tests)
6. GH Actions workflow: cron, run poller, commit (done, 2026-07-10:
   `.github/workflows/poll.yml`, not yet committed or run live)
7. Dashboard v1 views (done, 2026-07-11: `site/index.html`, `style.css`,
   `app.js`)
8. Let data accumulate; revisit v2

## Open items

- Exact page list for coverage (Helsinki + PK-Seutu + Kehä I + Kehä III as starting
  set) may grow; it's a config list.

## Resolved

- `ajax.php?act=map` tested 2026-07-09: doesn't work (empty body under every param
  combination tried). Coord strategy is the per-station map-page fallback instead.
  Detail in `docs/SCRAPER.md`.
- First live poll run 2026-07-09: succeeded end to end. `fuel.db` has 76 stations
  (coords backfilled for all of them) and 224 price rows spanning all 5 dates in
  the source's visibility window.
- JSON export + GH Actions workflow built 2026-07-10: `export.py` writes
  `site/data/{stations,history,medians}.json` (shapes in `site/data/README.md`,
  14 new unit tests, 52 total passing). `.github/workflows/poll.yml` runs
  poll → export → commit → deploy Pages, sharing the `pages` concurrency group
  with `pages.yml` (GITHUB_TOKEN pushes don't trigger `pages.yml`'s own push
  trigger, so `poll.yml` needs its own deploy job). Neither file is committed
  yet — awaiting manual commit and one `workflow_dispatch` run to verify live
  before trusting the cron. Build order is at step 6 of 8; dashboard v1 is next.
- Dashboard v1 built 2026-07-11: vanilla HTML/CSS/JS in `site/` (no build
  step), Chart.js + Leaflet from CDN, dark theme, CartoDB dark tiles for the
  map. Sticky fuel/radius controls drive a cheapest-first price table
  (colored vs each station's own 7-day average), a Leaflet map (marker color
  = spatial cheapness vs the displayed set's median), a per-station Chart.js
  trend line, and an area median chart. All tunables (`HELSINKI_CENTER`,
  `RADIUS_KM`, `AVG_WINDOW_DAYS`, `STALE_DAYS`, `COLOR_EPSILON`) live as
  constants at the top of `app.js`. Logic verified in Node against live
  `site/data/*.json` (no crashes, sane output) and then confirmed working in
  a real browser by the user. Not yet committed or pushed.
- Manual poll+export refresh 2026-07-11 08:xx UTC (~19.3 h after the
  2026-07-10 12:57 UTC poll, comfortably past the 12 h cadence floor):
  `fuel.db` now has 76 stations and 233 price rows (up from 224), dates
  2026-07-05..2026-07-10 — the source still hasn't produced a 2026-07-11
  report for any station yet, expected given date-only crowdsourced
  resolution. `site/data/*.json` regenerated to match. Still uncommitted.
