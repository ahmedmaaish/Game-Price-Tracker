# Game Price Tracker

A CamelCamelCamel-style price tracker for PC games. A GitHub Actions cron job
checks prices once a day, stores the history in Supabase, and publishes an
interactive charts page on GitHub Pages. Everything runs on free tiers.

## How it works

```
GitHub Actions (daily cron)  ->  scraper.py
        |                            |
        |          CheapShark API (free, no key)
        v                            |
   Supabase (Postgres)  <------- price history
        |
        v
   docs/data.json  ->  GitHub Pages (the charts site)
```

The browser only ever reads the static `docs/data.json`, so visitors never hit
the database -- Supabase stays well inside its free limits no matter the traffic.

## One-time setup

### 1. Supabase (the database)
1. Create a free account at https://supabase.com and start a new project.
2. Open **SQL Editor -> New query**, paste the contents of `schema.sql`, run it.
3. Click **Connect** (top bar) -> **Session pooler** -> copy the URI.
   Use the **Session pooler** string, not "Direct connection" -- the direct one
   is IPv6-only and fails on GitHub's runners. Replace `[YOUR-PASSWORD]` with
   your database password.

### 2. GitHub
1. Create a new repository and push the contents of this folder to it
   (this folder is the repo root).
2. **Settings -> Secrets and variables -> Actions -> New repository secret**:
   name `SUPABASE_DB_URL`, value = the connection string from step 1.3.
3. **Settings -> Pages**: Source = "Deploy from a branch", branch = `main`,
   folder = `/docs`. Save.

### 3. First run
- **Actions** tab -> **Track prices** -> **Run workflow**.
- When it finishes, the site is live at `https://<username>.github.io/<repo>/`.

## Day-to-day

- Edit `watchlist.json` to choose which games to track (matched by title).
- The workflow runs daily at 06:00 UTC and also has a manual "Run workflow"
  button.

## Run locally

```
pip install -r requirements.txt
$env:SUPABASE_DB_URL = "postgresql://..."   # PowerShell
python scraper.py
```

Then open `docs/index.html` in a browser.

## Making money from it

The "View deal" buttons currently use CheapShark's redirect links. To earn
commission, join store affiliate programs (Fanatical, Green Man Gaming, Humble),
then swap your own affiliate links into `docs/index.html`. Once the page gets
steady search traffic, display ads (e.g. AdSense) are the second revenue stream.
