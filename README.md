# helsinki-fuel-dash

Personal fuel price tracker for the Helsinki area. Scrapes the crowdsourced site
polttoaine.net on a 12 h GitHub Actions cron, accumulates price history in SQLite,
and will publish a static Chart.js dashboard on GitHub Pages: current prices sorted
cheapest-first, per-station price history, and area median trends for 95E10 / 98E /
diesel.

No auth, no API key, no credentials needed anywhere in this project.

Full design: [docs/PLAN.md](docs/PLAN.md) · Scraper contract: [docs/SCRAPER.md](docs/SCRAPER.md)

## Status

Build order (see `docs/PLAN.md`) is at step 4 of 8: parser, coordinate resolution,
SQLite schema/upsert, and the poller script (`poll.py`) all exist and are
unit-tested. `ajax.php?act=map` (the hoped-for bulk coordinate endpoint) doesn't
work — confirmed dead 2026-07-09, see `docs/SCRAPER.md` — so coords come from one
request per new station's map page instead. No live poll has been run against the
real site yet; that's next, manually, before JSON export and the Actions workflow
get built.

## Local setup

```
pip install -r requirements.txt
python -m unittest discover -s tests -t .
```

`poll.py` runs the full pipeline (fetch configured pages → parse → upsert into
`fuel.db` → backfill coords for new stations) but hasn't been run live yet.
`parser.py` exposes `parse_page()` and `fetch_page()`; `db.py` exposes the SQLite
storage layer; `coords.py` fetches and caches per-station coordinates.
`probe_coords.py` is a standalone script to re-check the coordinate endpoints
against reality if the site changes.

## Politeness

12 h poll cadence, 100 ms between page requests, honest User-Agent, robots.txt
respected — see `docs/SCRAPER.md` for the full contract. This is someone else's
crowdsourced site; don't shorten the cadence.
