"""Daily price collector for the game price tracker.

Resolves a watchlist of game titles to CheapShark game IDs, fetches their
current cheapest prices across stores, stores everything in Supabase
(Postgres), and exports docs/data.json for the GitHub Pages frontend.

Env:
    SUPABASE_DB_URL  Postgres connection string (use the Session pooler URI).
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
import requests
from psycopg2.extras import execute_values

API = "https://www.cheapshark.com/api/1.0"
ROOT = Path(__file__).resolve().parent
WATCHLIST = ROOT / "watchlist.json"
OUTPUT = ROOT / "docs" / "data.json"
HISTORY_DAYS = 180
ID_BATCH = 25  # CheapShark /games accepts a comma-separated id list


def get(path, params):
    r = requests.get(f"{API}/{path}", params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def load_watchlist():
    titles = json.loads(WATCHLIST.read_text(encoding="utf-8")).get("games", [])
    titles = [t.strip() for t in titles if t.strip()]
    if not titles:
        sys.exit("watchlist.json has no games -- add some titles and retry.")
    return titles


def resolve_ids(titles):
    """Map each watchlist title to a CheapShark gameID via title search."""
    ids = {}
    for title in titles:
        results = get("games", {"title": title, "limit": 1})
        if not results:
            print(f"  no match for '{title}' -- skipping")
            continue
        ids[str(results[0]["gameID"])] = title
        time.sleep(0.3)  # be polite to the free API
    return ids


def fetch_stores():
    return {s["storeID"]: s["storeName"]
            for s in get("stores", {}) if s.get("isActive")}


def fetch_game_details(game_ids):
    details = {}
    for i in range(0, len(game_ids), ID_BATCH):
        batch = game_ids[i:i + ID_BATCH]
        details.update(get("games", {"ids": ",".join(batch)}))
        time.sleep(0.3)
    return details


def cheapest_deal(game):
    deals = game.get("deals") or []
    return min(deals, key=lambda d: float(d["price"]), default=None)


def collect():
    titles = load_watchlist()
    ids = resolve_ids(titles)
    if not ids:
        sys.exit("Could not resolve any watchlist titles to game IDs.")
    stores = fetch_stores()
    details = fetch_game_details(list(ids.keys()))

    games, prices = [], []
    for gid, game in details.items():
        info = game.get("info") or {}
        ever = game.get("cheapestPriceEver") or {}
        games.append((
            int(gid),
            info.get("title") or ids.get(gid) or f"Game {gid}",
            info.get("thumb"),
            info.get("steamAppID"),
            float(ever["price"]) if ever.get("price") else None,
        ))
        deal = cheapest_deal(game)
        if deal:
            prices.append((int(gid), float(deal["price"]),
                           deal.get("storeID"), deal.get("dealID")))
        else:
            print(f"  {info.get('title', gid)}: no active deal today")
    return stores, games, prices


def save(stores, games, prices):
    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        sys.exit("SUPABASE_DB_URL is not set.")

    with psycopg2.connect(db_url) as conn, conn.cursor() as cur:
        execute_values(cur, """
            insert into games (id, title, thumb, steam_app_id, cheapest_ever)
            values %s
            on conflict (id) do update set
                title = excluded.title,
                thumb = excluded.thumb,
                steam_app_id = excluded.steam_app_id,
                cheapest_ever = excluded.cheapest_ever,
                updated_at = now()
        """, games)

        if prices:
            execute_values(cur, """
                insert into price_history (game_id, price, store_id, deal_id)
                values %s
                on conflict (game_id, recorded_at) do update set
                    price = excluded.price,
                    store_id = excluded.store_id,
                    deal_id = excluded.deal_id
            """, prices)

        cur.execute("select id, title, thumb, steam_app_id, cheapest_ever from games")
        meta = {r[0]: r for r in cur.fetchall()}

        cur.execute("""
            select game_id, recorded_at, price, store_id, deal_id
            from price_history
            where recorded_at >= current_date - %s
            order by game_id, recorded_at
        """, (HISTORY_DAYS,))
        history = {}
        for game_id, day, price, store_id, deal_id in cur.fetchall():
            history.setdefault(game_id, []).append({
                "date": day.isoformat(),
                "price": float(price),
                "store_id": store_id,
                "deal_id": deal_id,
            })

    return export(stores, meta, history)


def export(stores, meta, history):
    games = []
    for gid, row in meta.items():
        hist = history.get(gid, [])
        games.append({
            "id": gid,
            "title": row[1],
            "thumb": row[2],
            "steam_app_id": row[3],
            "cheapest_ever": float(row[4]) if row[4] is not None else None,
            "current": hist[-1] if hist else None,
            "history": [{"date": h["date"], "price": h["price"]} for h in hist],
        })
    games.sort(key=lambda g: g["title"].lower())

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stores": stores,
        "games": games,
    }, indent=2), encoding="utf-8")
    return len(games)


def main():
    stores, games, prices = collect()
    count = save(stores, games, prices)
    print(f"Done -- {count} games tracked, {len(prices)} prices recorded today.")


if __name__ == "__main__":
    main()
