"""Daily price collector for the game price tracker.

Auto-discovers trending PC game deals from the CheapShark API, fetches their
prices, and appends today's prices to docs/data.json. Optionally also tracks
"pinned" titles listed in watchlist.json. That JSON file IS the database --
the GitHub Actions workflow commits it back to the repo after every run, so
price history builds up in git.
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
HISTORY_DAYS = 180          # how long to keep each game's price history
KEEP_STALE_DAYS = 120       # drop games not seen in a deal for this long
DISCOVER_SORTS = ("Deal Rating", "Reviews", "Metacritic")
PAGE_SIZE = 60              # CheapShark /deals max page size
MAX_GAMES = 90
ID_BATCH = 25              # CheapShark /games accepts a comma-separated id list


def get(path, params):
    r = requests.get(f"{API}/{path}", params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def discover():
    """Find trending games from CheapShark's current top deals."""
    found = {}
    for sort in DISCOVER_SORTS:
        try:
            deals = get("deals", {"sortBy": sort, "pageSize": PAGE_SIZE})
        except requests.RequestException as e:
            print(f"  discover ({sort}) failed: {e}")
            continue
        for d in deals:
            gid = d.get("gameID")
            if gid:
                found[str(gid)] = d.get("title", "")
        time.sleep(0.3)
    return found


def load_pins():
    """Optional always-track titles from watchlist.json."""
    if not WATCHLIST.exists():
        return []
    try:
        titles = json.loads(WATCHLIST.read_text(encoding="utf-8")).get("games", [])
    except ValueError:
        return []
    return [t.strip() for t in titles if t.strip()]


def resolve_ids(titles):
    """Map pinned titles to CheapShark game IDs via title search."""
    ids = {}
    for title in titles:
        try:
            results = get("games", {"title": title, "limit": 1})
        except requests.RequestException:
            continue
        if results:
            ids[str(results[0]["gameID"])] = title
        time.sleep(0.3)
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
    if not DATA.exists():
        return {}
    try:
        data = json.loads(DATA.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    return {g["id"]: g for g in data.get("games", [])}


def trim(history):
    cutoff = (date.today() - timedelta(days=HISTORY_DAYS)).isoformat()
    kept = [h for h in history if h.get("date", "") >= cutoff]
    kept.sort(key=lambda h: h["date"])
    return kept


def main():
    today = date.today().isoformat()
    stale_cutoff = (date.today() - timedelta(days=KEEP_STALE_DAYS)).isoformat()

    ids = {}
    pins = load_pins()
    if pins:
        ids.update(resolve_ids(pins))   # pinned first so the cap never drops them
    ids.update(discover())
    if not ids:
        raise SystemExit("No games found -- CheapShark may be unreachable.")
    ids = dict(list(ids.items())[:MAX_GAMES])

    stores = fetch_stores()
    details = fetch_game_details(list(ids))
    existing = load_existing()

    games = []
    recorded = 0
    seen = set()
    for gid, game in details.items():
        game_id = int(gid)
        seen.add(game_id)
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
                "retail": float(deal["retailPrice"]) if deal.get("retailPrice") else None,
                "store_id": deal.get("storeID"),
                "deal_id": deal.get("dealID"),
            }
            recorded += 1
        else:
            current = prev.get("current")
        games.append({
            "id": game_id,
            "title": info.get("title") or ids.get(gid) or f"Game {gid}",
            "thumb": info.get("thumb"),
            "steam_app_id": info.get("steamAppID"),
            "cheapest_ever": float(ever["price"]) if ever.get("price") else None,
            "current": current,
            "history": trim(history),
        })

    # keep recently-seen games that aren't trending today so their history survives
    for game_id, rec in existing.items():
        if game_id in seen:
            continue
        hist = rec.get("history") or []
        if hist and hist[-1].get("date", "") >= stale_cutoff:
            rec["history"] = trim(hist)
            games.append(rec)

    games.sort(key=lambda g: g["title"].lower())
    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps({
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stores": stores,
        "games": games,
    }, indent=2), encoding="utf-8")
    print(f"Done -- {len(games)} games tracked, {recorded} fresh prices for {today}.")


if __name__ == "__main__":
    main()
