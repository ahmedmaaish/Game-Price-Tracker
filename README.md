# Game Price Tracker

A CamelCamelCamel-style price tracker for PC games. A GitHub Actions cron job
checks prices once a day and saves the history straight into this repo; a
GitHub Pages site shows interactive charts. Runs entirely free — no database
and no accounts to manage.

## How it works

```
GitHub Actions (daily cron) -> scraper.py -> CheapShark API (free, no key)
                                   |
                                   v
                       docs/data.json  (committed back to the repo)
                                   |
                                   v
                       GitHub Pages  (the charts site)
```

Price history lives in `docs/data.json`. Each daily run adds that day's prices
and the workflow commits the file — so git itself is the database.

## Setup

The code is already here. Two switches to flip:

1. **GitHub Pages** — repo **Settings → Pages**: Source = "Deploy from a
   branch", branch = `main`, folder = `/docs`, then **Save**.
2. **Run it once** — **Actions** tab → **Track prices** → **Run workflow**.
   (It also runs on its own every day at 06:00 UTC.)

The site goes live at `https://<username>.github.io/<repo>/`.

## Day-to-day

- Nothing required — the tracker auto-discovers the top trending deals daily.
- Optional: pin always-tracked favourites by adding titles to `watchlist.json`.

## Run locally

```
pip install -r requirements.txt
python scraper.py
```

Then open `docs/index.html` in a browser.

## Making money from it

The "View deal" buttons use CheapShark's redirect links. To earn commission,
join store affiliate programs (Fanatical, Green Man Gaming, Humble) and swap
your own affiliate links into `docs/index.html`. Once the page gets steady
search traffic, display ads (e.g. AdSense) are the second revenue stream.
