# helsinki-fuel-dash

Personal fuel price tracker for the Helsinki area. Scrapes the crowdsourced site
polttoaine.net on a 12 h GitHub Actions cron, accumulates price history in SQLite,
and will publish a static Chart.js dashboard on GitHub Pages: current prices sorted
cheapest-first, per-station price history, and area median trends for 95E10 / 98E /
diesel.

No auth, no API key, no credentials needed anywhere in this project.

Full design: [docs/PLAN.md](docs/PLAN.md) · Scraper contract: [docs/SCRAPER.md](docs/SCRAPER.md)

## Status

Build order (see `docs/PLAN.md`) is at step 6 of 8. The first live poll
(2026-07-09) succeeded: `fuel.db` holds 76 stations (all with coords) and 224
price rows across the full 5-day visibility window. `ajax.php?act=map` (the
hoped-for bulk coordinate endpoint) doesn't work — confirmed dead 2026-07-09,
see `docs/SCRAPER.md` — so coords come from one request per new station's map
page instead. JSON export (`export.py`) and the GH Actions poll+deploy
workflow (`.github/workflows/poll.yml`) are built and unit-tested (52 tests
passing) as of 2026-07-10, but not yet committed or run live — next step is
committing, then a manual `workflow_dispatch` run to verify the workflow
before trusting the cron. After that: dashboard v1.

## Local setup

```
pip install -r requirements.txt
python -m unittest discover -s tests -t .
python poll.py           # live poll: fetches configured pages, upserts fuel.db
python export.py         # writes site/data/{stations,history,medians}.json from fuel.db
```

`poll.py` runs the full pipeline (fetch configured pages → parse → upsert into
`fuel.db` → backfill coords for new stations) and has been run live successfully.
`export.py` reads `fuel.db` and writes `site/data/*.json` for the dashboard —
shapes documented in `site/data/README.md`. `parser.py` exposes `parse_page()`
and `fetch_page()`; `db.py` exposes the SQLite storage layer; `coords.py`
fetches and caches per-station coordinates. `probe_coords.py` is a standalone
script to re-check the coordinate endpoints against reality if the site changes.

`.github/workflows/poll.yml` runs the cron (every 12 h): `poll.py` →
`export.py` → commit `fuel.db` + `site/data/*.json` back to `main` (skipped if
nothing changed) → deploy `site/` to GH Pages in the same run. It shares the
`pages` concurrency group with `pages.yml` since GITHUB_TOKEN-authored pushes
don't trigger other workflows' push triggers — `poll.yml` has to do its own
deploy.

## Politeness

12 h poll cadence, 100 ms between page requests, honest User-Agent, robots.txt
respected — see `docs/SCRAPER.md` for the full contract. This is someone else's
crowdsourced site; don't shorten the cadence.
