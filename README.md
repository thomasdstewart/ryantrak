# ryantrak

A lightweight Ryanair price tracker that runs daily in GitHub Actions and records
prices to a CSV file. The initial configuration tracks **London Stansted (STN)**
→ **Milan Bergamo (BGY)**, returning **22 Aug – 4 Sept 2026**, for 1 adult.

## What it does

- Uses Selenium + Chrome to open the Ryanair booking flow.
- Extracts the return price and appends a row to `data/flight_prices.csv`.
- Saves debug artifacts (HTML + screenshots) for troubleshooting.
- Uploads logs/screenshots as workflow artifacts in GitHub Actions.

## Project layout

```
.
├── .github/workflows/ryanair-daily.yml  # scheduled GitHub Action
├── data/flight_dates.csv                # date pairs to query
├── data/flight_prices.csv               # time-series results
├── logs/                                # local logs (gitignored)
├── src/ryanair_scraper.py               # Selenium scraper
└── requirements.txt
```

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/ryanair_scraper.py --headless
```

### Common flags

```bash
python src/ryanair_scraper.py \
  --origin STN \
  --destination BGY \
  --date-out 2024-08-22 \
  --date-return 2024-09-04 \
  --currency GBP \
  --csv-path data/flight_prices.csv \
  --log-path logs/ryanair_scrape.log \
  --debug-dir debug_artifacts \
  --headless \
  --verbose
```

## GitHub Actions

The workflow in `.github/workflows/ryanair-daily.yml` runs once per day and also
supports manual dispatch. It:

1. Installs Chrome + dependencies.
2. Reads `data/flight_dates.csv` and runs the scraper for each line.
3. Uploads logs/screenshots as artifacts.
4. Commits updated CSV data back to the repo.

If you want a different schedule, update the cron expression in the workflow.

To change the queried routes and dates, edit `data/flight_dates.csv` with a
header row of `origin,destination,date_out,date_return` and one or more
route/date pairs below it.

## Notes on selectors

Ryanair updates their DOM frequently. If the selector in
`src/ryanair_scraper.py` stops working, inspect the page and update the CSS
selector in `fetch_return_price()`.

## Charting ideas

Once the CSV accumulates entries, you can graph it with pandas or a notebook
(e.g., `pandas.read_csv(...).plot(...)`).

## Generating charts in CI

The `src/plot_flight_prices.py` script converts `data/flight_prices.csv` into
PNG charts (one per unique origin/destination/departure time). Save images under
`site/static/charts` so the Hugo site can surface them.

Run it locally:

```bash
python src/plot_flight_prices.py \
  --csv-path data/flight_prices.csv \
  --output-dir site/static/charts
```

## Hugo dashboard

The `site/` directory is a Hugo project with a simple theme and a route filter
dropdown. Generate charts, then preview locally:

```bash
python src/plot_flight_prices.py --csv-path data/flight_prices.csv --output-dir site/static/charts
hugo server --source site
```
