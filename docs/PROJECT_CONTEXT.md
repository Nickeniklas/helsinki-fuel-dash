PROJECT CONTEXT — fuel-dash
Paste-ready summary for the Claude project. Condensed from docs/PLAN.md (replanned
2026-07-08); if the plan changes, update both.

Status (2026-07-16): parser, coordinate resolution, SQLite schema/upsert, the
poller (poll.py), JSON export (export.py), the GH Actions poll+deploy
workflow (.github/workflows/poll.yml), and dashboard v1 (site/index.html,
style.css, app.js) are all built, committed, and live. 52 unit tests pass.
The cron has fired every ~12 h without a miss since 2026-07-12 — production
is stable. fuel.db has 89 stations (all geocoded) and 474 price rows across
dates 2026-07-05 to 2026-07-16 (~11 days of accumulated history). Build
order is done through step 7 of 8; currently in step 8, letting data
accumulate toward the "weeks of data" bar for v2. Live at
https://nickeniklas.github.io/fuel-dash/. Repo renamed 2026-07-16
(gas-price-dashboard → helsinki-fuel-dash → fuel-dash) to drop the city
name from the project's identity ahead of planned international expansion;
the Helsinki-area scope itself hasn't changed, only the name.
The project
Niklas (GitHub: Nickeniklas) is building a personal fuel price tracker for the
Helsinki area. No service provides long-term price trends or a sorted area-wide
list, so this project collects its own history and visualizes it.
History: the original plan used the unofficial Tankille API. It blocked us on day
one (2026-07-08) and was dropped completely, clean DB, no workarounds. Don't
suggest returning to it.
How it works

Source: scraping polttoaine.net, an independent crowdsourced price site
(~395 active stations, reports visible 5 days, plain HTML, no auth). Parsing
spec derived from Pumperly (GPL-3.0), spec only, no code copied, and
documented in docs/SCRAPER.md.
Poller: Python + requests + SQLite (poll.py), GH Actions cron every 12 h.
Crawls a config list of pages (starting: Helsinki, PK-Seutu, Kehä I, Kehä
III), dedupes stations across pages by the cmd=map&id= station ID. No
backfill exists in this source, so history accumulates from the first poll.
Export: export.py reads fuel.db and writes site/data/stations.json (all
stations, coords, latest price per fuel), site/data/history.json
(per-station history), and site/data/medians.json (daily area median per
fuel) — exact shapes in site/data/README.md.
Workflow: .github/workflows/poll.yml runs poll.py, then export.py, commits
fuel.db + site/data/*.json back to main (skipped if nothing changed), then
deploys site/ to GH Pages in the same run. It shares the "pages" concurrency
group with pages.yml, because GITHUB_TOKEN-authored pushes don't trigger
other workflows' push triggers — poll.yml has to do its own deploy.
Dashboard: static HTML + Chart.js + Leaflet in site/, served by GH Pages,
reading only site/data/*.json. v1 is built and confirmed working in a
browser: sticky fuel (95/98/dsl) and radius (15 km / all) controls; a
cheapest-first price table colored vs each station's 7-day average; a dark
Leaflet map (CartoDB dark tiles) with marker color showing spatial cheapness;
a per-station trend chart with picker; area median lines for 95/98/dsl.
Config constants (HELSINKI_CENTER, RADIUS_KM, AVG_WINDOW_DAYS, STALE_DAYS,
COLOR_EPSILON) live at the top of app.js. v2 (deferred until weeks of data
exist): day-of-week heatmap, "fill now or wait" signal.

Key decisions and rules

Ingest every row from every configured page; the 15 km Helsinki radius is a
display-time filter in the dashboard (config), never an ingest filter
Dedupe on UNIQUE(station_id, fuel, date); source has date-only resolution
(DD.MM., no year: rollover rule resolves it), latest price wins within a day
Coordinates are static: cached in a stations table, fetched once per new station.
The hoped-for ajax.php?act=map bulk endpoint turned out dead (always returns an
empty body, tested 2026-07-09) — coords come from one request per new station's
map page instead, cached forever
Parse rows by 5-td count, not class (regional pages omit the E10 class); strip
the V-Power */E99 marker from 98E; skip the ~5-8 % of rows without map links
Sanity bounds: price 0.80–4.00 EUR, Finland bbox lat 59.7–70.1, lon 20.5–31.6
Politeness is hard policy: 12 h cadence, 100 ms between requests, honest
User-Agent, respect robots.txt (someone else's crowdsourced site)
GH Pages serves site/, never docs/ (plan docs live there)
No LLM in the poller (deterministic script; Claude Code Routine rejected)
GITHUB_TOKEN-authored pushes don't trigger other workflows' push triggers, so
poll.yml can't rely on pages.yml firing after its commit — it has its own
deploy job instead, sharing the "pages" concurrency group

Niklas's working context
Builds with Claude Code on Windows. Comfortable with Python, SQLite, Git, GH
Actions, Chart.js (used in his tech-digest and news-summarizer projects). Prefers
minimal direct answers, no em dashes, English responses. Global rule: Claude Code
never commits or pushes autonomously.