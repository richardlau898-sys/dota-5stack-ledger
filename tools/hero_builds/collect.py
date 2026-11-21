#!/usr/bin/env python3
"""Collect recent high-rank ranked matches for the current patch from OpenDota.

Stdlib only. Rate-limited to stay well under OpenDota's free limits
(60/min, 3000/day as reported by its response headers on 2026-11-22).
Raw match JSON is cached on disk so reruns only fetch new matches.

Usage:
  python3 collect.py --cache DIR --max-matches 1000 --min-rank 70 --day-reserve 1200
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

API = "https://api.opendota.com/api"
UA = "dota-hero-builds-collector/0.1"
RANKED_LOBBY = 7
ALL_PICK_MODES = {22}  # ranked All Pick; excludes Turbo (23) and others


class Limiter:
    def __init__(self, per_min: int, day_reserve: int):
        self.gap = 60.0 / per_min
        self.last = 0.0
        self.day_reserve = day_reserve
        self.day_left = None
        self.calls = 0

    def get(self, path: str):
        wait = self.gap - (time.time() - self.last)
        if wait > 0:
            time.sleep(wait)
        if self.day_left is not None and self.day_left <= self.day_reserve:
            raise SystemExit(f"stop: daily quota reserve reached (remaining {self.day_left})")
        req = urllib.request.Request(API + path, headers={"User-Agent": UA, "Accept": "application/json"})
        for attempt in range(4):
            self.last = time.time()
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    self.calls += 1
                    rm = resp.headers.get("x-rate-limit-remaining-minute")
                    rd = resp.headers.get("x-rate-limit-remaining-day")
                    if rd is not None:
                        self.day_left = int(rd)
                    if rm is not None and int(rm) < 3:
                        time.sleep(60)
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    time.sleep(65)
                    continue
                if e.code >= 500:
                    time.sleep(5 * (attempt + 1))
                    continue
                raise
            except (urllib.error.URLError, TimeoutError):
                time.sleep(5 * (attempt + 1))
        raise RuntimeError(f"giving up on {path}")


def prune_cache(match_dir: str, patch_id: int, keep: int) -> int:
    """Drop cached matches from other patches, then keep only the newest `keep` matches."""
    entries = []
    removed = 0
    for name in os.listdir(match_dir):
        if not name.endswith(".json"):
            continue
        path = os.path.join(match_dir, name)
        try:
            with open(path, encoding="utf-8") as fh:
                m = json.load(fh)
        except (OSError, ValueError):
            os.remove(path)
            removed += 1
            continue
        if m.get("patch") != patch_id:
            os.remove(path)
            removed += 1
        else:
            entries.append((m.get("start_time") or 0, path))
    entries.sort(reverse=True)
    for _, path in entries[keep:]:
        os.remove(path)
        removed += 1
    return removed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--max-matches", type=int, default=1000)
    ap.add_argument("--min-rank", type=int, default=70, help="minimum avg_rank_tier (70 = Divine)")
    ap.add_argument("--per-min", type=int, default=50)
    ap.add_argument("--day-reserve", type=int, default=1200, help="stop when daily quota left falls to this")
    ap.add_argument("--keep", type=int, default=30000, help="keep at most this many cached matches (newest first)")
    args = ap.parse_args()

    os.makedirs(os.path.join(args.cache, "matches"), exist_ok=True)
    lim = Limiter(args.per_min, args.day_reserve)

    patches = lim.get("/constants/patch")
    latest = max(patches, key=lambda p: p["id"])
    patch_id, patch_name = latest["id"], latest["name"]
    patch_start = int(time.mktime(time.strptime(latest["date"][:19], "%Y-%m-%dT%H:%M:%S")))
    print(f"patch {patch_name} (id {patch_id}) since {latest['date']}", flush=True)

    pruned = prune_cache(os.path.join(args.cache, "matches"), patch_id, args.keep)
    if pruned:
        print(f"pruned {pruned} cached matches (other patch or over --keep)", flush=True)
    have = {int(f[:-5]) for f in os.listdir(os.path.join(args.cache, "matches")) if f.endswith(".json")}
    fetched = 0
    kept = 0
    cursor = None
    seen_old = 0
    while fetched < args.max_matches:
        q = f"/publicMatches?min_rank={args.min_rank}" + (f"&less_than_match_id={cursor}" if cursor else "")
        page = lim.get(q)
        if not page:
            break
        cursor = min(m["match_id"] for m in page)
        for m in page:
            if m.get("start_time", 0) < patch_start:
                seen_old += 1
                continue
            if m.get("lobby_type") != RANKED_LOBBY or m.get("game_mode") not in ALL_PICK_MODES:
                continue
            if (m.get("avg_rank_tier") or 0) < args.min_rank or (m.get("duration") or 0) < 900:
                continue
            mid = int(m["match_id"])
            if mid in have:
                continue
            try:
                detail = lim.get(f"/matches/{mid}")
            except Exception as e:  # keep going on single-match failures
                print(f"skip {mid}: {type(e).__name__}", flush=True)
                continue
            fetched += 1
            if detail.get("patch") != patch_id or len(detail.get("players") or []) != 10:
                continue
            slim = {
                "match_id": mid,
                "patch": patch_id,
                "start_time": detail.get("start_time"),
                "duration": detail.get("duration"),
                "radiant_win": detail.get("radiant_win"),
                "avg_rank_tier": m.get("avg_rank_tier"),
                "players": [
                    {k: p.get(k) for k in (
                        "player_slot", "hero_id", "ability_upgrades_arr", "item_0", "item_1", "item_2",
                        "item_3", "item_4", "item_5", "backpack_0", "backpack_1", "backpack_2",
                        "item_neutral", "item_neutral2", "net_worth", "gold_per_min", "last_hits",
                        "level", "kills", "deaths", "assists", "aghanims_scepter", "aghanims_shard",
                    )}
                    for p in detail["players"]
                ],
            }
            with open(os.path.join(args.cache, "matches", f"{mid}.json"), "w", encoding="utf-8") as fh:
                json.dump(slim, fh, separators=(",", ":"))
            have.add(mid)
            kept += 1
            if kept % 50 == 0:
                print(f"kept {kept} (fetched {fetched}, api calls {lim.calls}, day left {lim.day_left})", flush=True)
            if fetched >= args.max_matches:
                break
        if seen_old > 300:
            print("reached matches older than the patch; stopping", flush=True)
            break
    print(f"done: kept {kept} new matches for {patch_name}; total cached {len(have)}; api calls {lim.calls}; day left {lim.day_left}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
