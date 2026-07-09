# helsinki-fuel-dash

Personal fuel price tracker for the Helsinki area. Scrapes the crowdsourced site
polttoaine.net on a 12 h GitHub Actions cron, accumulates price history in SQLite,
and will publish a static Chart.js dashboard on GitHub Pages: current prices sorted
cheapest-first, per-station price history, and area median trends for 95E10 / 98E /
diesel.

No auth, no API key, no credentials needed anywhere in this project.

Full design: [docs/PLAN.md](docs/PLAN.md) · Scraper contract: [docs/SCRAPER.md](docs/SCRAPER.md)

## Status

Build order (see `docs/PLAN.md`) is at step 2 of 8: the polttoaine.net parser is
written and unit-tested against saved HTML fixtures. Coordinate resolution, the
SQLite schema, JSON export, the Actions workflow, and the dashboard don't exist yet.

## Local setup

```
pip install -r requirements.txt
python -m unittest discover -s tests -t .
```

There's no poller or dashboard to run yet — `parser.py` currently exposes
`parse_page()` (HTML → list of price-row dicts) and `fetch_page()` (polite GET with
the project's honest User-Agent, decoded per docs/SCRAPER.md).

## Politeness

12 h poll cadence, 100 ms between page requests, honest User-Agent, robots.txt
respected — see `docs/SCRAPER.md` for the full contract. This is someone else's
crowdsourced site; don't shorten the cadence.
