"""Daily price collector for the game price tracker.

Resolves a watchlist of game titles to CheapShark game IDs, fetches their
current cheapest prices, and appends today's prices to docs/data.json.
That JSON file IS the database -- the GitHub Actions workflow commits it
back to the repo after every run, so price history builds up in git.
"""
import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

API = "https://www.cheapshark.com/api/1.0"
ROOT = Path(__file__).resolve().parent
WATCHLIST = ROOT / "watchlist.json"
DATA = ROOT / "docs" / "data.json"
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
        raise SystemExit("watchlist.json has no games -- add some titles and retry.")
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


def load_existing():
    """Return {game_id: game_record} from the current data.json, if any."""
    if not DATA.exists():
        return {}
    try:
        data = json.loads(DATA.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    return {g["id"]: g for g in data.get("games", [])}


def trim(history):
    """Drop entries older than the retention window and sort by date."""
    cutoff = (date.today() - timedelta(days=HISTORY_DAYS)).isoformat()
    kept = [h for h in history if h.get("date", "") >= cutoff]
    kept.sort(key=lambda h: h["date"])
    return kept


def main():
    today = date.today().isoformat()
    titles = load_watchlist()
    ids = resolve_ids(titles)
    if not ids:
        raise SystemExit("Could not resolve any watchlist titles to game IDs.")
    stores = fetch_stores()
    details = fetch_game_details(list(ids.keys()))
    existing = load_existing()

    games = []
    recorded = 0
    for gid, game in details.items():
        game_id = int(gid)
        info = game.get("info") or {}
        ever = game.get("cheapestPriceEver") or {}
        deal = cheapest_deal(game)

        prev = existing.get(game_id, {})
        history = [h for h in prev.get("history", []) if h.get("date") != today]

        if deal:
            price = float(deal["price"])
            history.append({"date": today, "price": price})
            current = {
                "date": today,
                "price": price,
                "store_id": deal.get("storeID"),
                "deal_id": deal.get("dealID"),
            }
            recorded += 1
        else:
            current = prev.get("current")
            print(f"  {info.get('title', gid)}: no active deal today")

        games.append({
            "id": game_id,
            "title": info.get("title") or ids.get(gid) or f"Game {gid}",
            "thumb": info.get("thumb"),
            "steam_app_id": info.get("steamAppID"),
            "cheapest_ever": float(ever["price"]) if ever.get("price") else None,
            "current": current,
            "history": trim(history),
        })

    games.sort(key=lambda g: g["title"].lower())
    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps({
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stores": stores,
        "games": games,
    }, indent=2), encoding="utf-8")
    print(f"Done -- {len(games)} games tracked, {recorded} prices recorded for {today}.")


if __name__ == "__main__":
    main()
