#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Milestone M0 Read-Only Probe:
1. Valve Replay Retention Probe (1, 3, 7, 10, 14, 21 days + extended boundary check)
   via OpenDota /api/players/{aid}/matches?date=35, /api/matches/{id}, and HTTP HEAD ONLY.
2. Past 4 Weeks (28 Days) Match Volume Tally across all 11 account IDs in roster.json.

Strict privacy/security guarantees:
- Read-only against dota-ai-analyst workspace (no files modified or created in repo).
- Never prints player nicknames, account IDs, API keys, or Valve replay_url / salt tokens.
- Uses HTTP HEAD only (timeout=15s) on Valve CDN URLs; never downloads .dem.bz2 payloads.
"""

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

def resolve_repo_root(explicit: Optional[str] = None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    here = Path(__file__).resolve()
    for cand in [here.parent, *here.parents, Path.cwd()]:
        if (cand / "roster.json").exists():
            return cand
    raise FileNotFoundError("Could not locate roster.json; pass --repo-root <path>")


OPENDOTA_BASE = "https://api.opendota.com/api"
USER_AGENT = "dota-5stack-ledger-m0-retention-probe/1.0"

TARGET_PROBE_DAYS = (1.0, 3.0, 7.0, 10.0, 14.0, 21.0)
EXTENDED_HISTORY_TARGETS = (60.0, 91.5, 100.5, 103.5, 180.0)


def load_patch_map(repo_root: Path) -> Dict[int, str]:
    patch_path = repo_root / ".cache" / "patch_constants.json"
    if not patch_path.exists():
        return {}
    rows = json.loads(patch_path.read_text(encoding="utf-8"))
    return {int(r["id"]): str(r["name"]) for r in rows if isinstance(r, dict) and "id" in r and "name" in r}


def load_roster_meta(repo_root: Path) -> Tuple[List[int], Dict[int, int], int, int]:
    roster_path = repo_root / "roster.json"
    roster = json.loads(roster_path.read_text(encoding="utf-8"))
    players = roster.get("players") or {}
    account_ids = sorted(int(k) for k in players.keys())
    aliases = {int(k): int(v) for k, v in (roster.get("account_aliases") or {}).items()}
    canonical_members = {aliases.get(aid, aid) for aid in account_ids}
    main_aid = int(roster.get("main_account_id") or account_ids[0])
    return account_ids, aliases, len(canonical_members), main_aid


def http_get_json(url: str, retries: int = 3) -> Any:
    for attempt in range(retries):
        req = urllib.request.Request(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(2.0 * (attempt + 1))
                continue
            raise
        except Exception:
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise


def http_head_only(url: str) -> Tuple[str, Optional[int]]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    req.get_method = lambda: "HEAD"
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            cl = resp.headers.get("Content-Length")
            return str(resp.status), int(cl) if cl is not None and cl.isdigit() else None
    except urllib.error.HTTPError as e:
        return str(e.code), None
    except Exception as e:
        return f"ERR:{type(e).__name__}", None


def fetch_and_deduplicate_matches(
    account_ids: List[int],
    aliases: Dict[int, int],
    date_days: int = 35,
    significant: Optional[int] = None,
) -> Dict[int, Dict[str, Any]]:
    by_match: Dict[int, Dict[str, Any]] = {}
    extra = f"&significant={significant}" if significant is not None else ""
    for aid in account_ids:
        url = f"{OPENDOTA_BASE}/players/{aid}/matches?date={date_days}{extra}"
        rows = http_get_json(url)
        canon = aliases.get(aid, aid)
        if isinstance(rows, list):
            for r in rows:
                mid = r.get("match_id")
                if not mid:
                    continue
                mid = int(mid)
                ent = by_match.setdefault(
                    mid,
                    {
                        "match_id": mid,
                        "start_time": int(r.get("start_time") or 0),
                        "duration": int(r.get("duration") or 0),
                        "game_mode": r.get("game_mode"),
                        "lobby_type": r.get("lobby_type"),
                        "version": r.get("version"),
                        "canon_any": set(),
                        "teams": {"rad": set(), "dire": set()},
                        "party_sizes": set(),
                    },
                )
                ent["canon_any"].add(canon)
                slot = r.get("player_slot")
                if slot is not None:
                    side = "rad" if int(slot) < 128 else "dire"
                    ent["teams"][side].add(canon)
                if r.get("party_size") is not None:
                    ent["party_sizes"].add(int(r["party_size"]))
                if r.get("version") is not None:
                    ent["version"] = r.get("version")
        time.sleep(0.35)

    for ent in by_match.values():
        ent["roster_any"] = len(ent["canon_any"])
        ent["roster_same_team"] = max(len(ent["teams"]["rad"]), len(ent["teams"]["dire"]))
        ent["has_party_5"] = 5 in ent["party_sizes"]
        ent["is_parsed"] = ent["version"] is not None
    return by_match


def summarize_window(matches: List[Dict[str, Any]], now_ts: float, max_days: float, min_days_excl: Optional[float] = None) -> Dict[str, int]:
    sub = []
    for m in matches:
        st = m["start_time"]
        if not st:
            continue
        age = (now_ts - st) / 86400.0
        if age < 0 or age > max_days:
            continue
        if min_days_excl is not None and age <= min_days_excl:
            continue
        sub.append(m)
    ge2 = [m for m in sub if m["roster_same_team"] >= 2]
    stack5 = [m for m in sub if m["roster_same_team"] >= 5]
    party5 = [m for m in sub if m["has_party_5"]]
    ge2_parsed = [m for m in ge2 if m["is_parsed"]]
    return {
        "total_unique": len(sub),
        "ge2_roster": len(ge2),
        "ge2_parsed": len(ge2_parsed),
        "stack5_roster": len(stack5),
        "party_size_5": len(party5),
    }


def probe_match(
    mid: int,
    roster_same_team: Optional[int],
    now_ts: float,
    patch_map: Dict[int, str],
    bucket: str,
) -> Dict[str, Any]:
    detail = http_get_json(f"{OPENDOTA_BASE}/matches/{mid}")
    time.sleep(0.35)
    start_time = int(detail.get("start_time") or 0)
    age_days = (now_ts - start_time) / 86400.0 if start_time else -1.0
    patch_id = detail.get("patch")
    patch_str = patch_map.get(int(patch_id), str(patch_id)) if patch_id is not None else "unknown"
    replay_url = detail.get("replay_url")
    version = detail.get("version")
    cluster = detail.get("cluster")
    if isinstance(replay_url, str) and replay_url.startswith("http"):
        http_status, content_len = http_head_only(replay_url)
        replay_note = "present"
    else:
        http_status, content_len = "N/A", None
        replay_note = "replay_url=None (unparsed on OpenDota)" if version is None else "replay_url=None"
    return {
        "bucket": bucket,
        "match_id": mid,
        "age_days": age_days,
        "stack_size": str(roster_same_team) if roster_same_team is not None else "n/a",
        "parsed": f"v{version}" if version is not None else "unparsed",
        "patch": patch_str,
        "cluster": cluster,
        "replay_note": replay_note,
        "http_status": http_status,
        "content_length": content_len,
    }


def select_probe_candidates(
    default_matches: Dict[int, Dict[str, Any]],
    sig0_matches: Dict[int, Dict[str, Any]],
    now_ts: float,
) -> List[Tuple[str, int, int]]:
    """
    Returns list of (bucket_label, match_id, roster_same_team) without duplicate match_id unless explicitly informative.
    """
    squad_all = [m for m in default_matches.values() if m["start_time"] and m["roster_same_team"] >= 2]
    squad_parsed = [m for m in squad_all if m["is_parsed"]]
    all_default = [m for m in default_matches.values() if m["start_time"]]
    all_sig0 = [m for m in sig0_matches.values() if m["start_time"]]

    chosen: List[Tuple[str, int, int]] = []
    seen_mids: Set[int] = set()

    for target in TARGET_PROBE_DAYS:
        t_label = f"{int(target)}d"
        if target == 1.0:
            under_2d_default = [m for m in all_default if (now_ts - m["start_time"]) / 86400.0 <= 2.0]
            under_2d_sig0 = [m for m in all_sig0 if (now_ts - m["start_time"]) / 86400.0 <= 2.0]
            if not under_2d_default and not under_2d_sig0:
                print(
                    "[NOTE] Target 1d: 0 roster matches found in [0.00d, 2.00d]; "
                    "using closest available >=2 squad match (and newest sig=0 solo match if newer)."
                )
            newest_squad = max(squad_all, key=lambda m: m["start_time"])
            newest_sig0 = max(all_sig0, key=lambda m: m["start_time"])
            if newest_sig0["match_id"] != newest_squad["match_id"] and newest_sig0["start_time"] > newest_squad["start_time"]:
                chosen.append(("1d (newest sig=0 solo)", newest_sig0["match_id"], newest_sig0["roster_same_team"]))
                seen_mids.add(newest_sig0["match_id"])

        best_squad = min(squad_all, key=lambda m: abs(((now_ts - m["start_time"]) / 86400.0) - target))
        if best_squad["match_id"] not in seen_mids:
            tag = f"{t_label} (closest >=2)" if best_squad["is_parsed"] else f"{t_label} (closest >=2, unparsed)"
            chosen.append((tag, best_squad["match_id"], best_squad["roster_same_team"]))
            seen_mids.add(best_squad["match_id"])
        else:
            distinct_squad = [m for m in squad_all if m["match_id"] not in seen_mids]
            if distinct_squad:
                alt = min(distinct_squad, key=lambda m: abs(((now_ts - m["start_time"]) / 86400.0) - target))
                chosen.append((f"{t_label} (next >=2)", alt["match_id"], alt["roster_same_team"]))
                seen_mids.add(alt["match_id"])

        if not best_squad["is_parsed"]:
            parsed_pool = [m for m in squad_parsed if m["match_id"] not in seen_mids]
            if parsed_pool:
                best_p = min(parsed_pool, key=lambda m: abs(((now_ts - m["start_time"]) / 86400.0) - target))
                chosen.append((f"{t_label} (parsed >=2)", best_p["match_id"], best_p["roster_same_team"]))
                seen_mids.add(best_p["match_id"])

    return chosen


def main() -> int:
    parser = argparse.ArgumentParser(description="M0 Valve Replay Retention & 28-Day Match Volume Probe")
    parser.add_argument("--repo-root", default=None, help="Path to repository root containing roster.json")
    args = parser.parse_args()

    repo_root = resolve_repo_root(args.repo_root)
    now_utc = datetime.now(timezone.utc)
    now_ts = now_utc.timestamp()

    account_ids, aliases, canon_count, main_aid = load_roster_meta(repo_root)
    patch_map = load_patch_map(repo_root)

    print("=== M0 RETENTION & STORAGE PROBE ===")
    print(f"Runtime UTC Timestamp : {now_utc.isoformat()}")
    print(f"Roster Source         : roster.json ({len(account_ids)} account IDs -> {canon_count} canonical members via account_aliases)")
    print("Sanitization          : Player nicknames, account IDs, and replay_url/salt tokens strictly omitted")
    print()

    default_matches = fetch_and_deduplicate_matches(account_ids, aliases, date_days=35, significant=None)
    sig0_matches = fetch_and_deduplicate_matches(account_ids, aliases, date_days=35, significant=0)

    def_list = list(default_matches.values())
    sig0_list = list(sig0_matches.values())

    print("--- PART A: MATCH VOLUME TALLY (DEFAULT /players/{aid}/matches?date=35) ---")
    print(f"{'Window':<18} {'Total Unique':>12} {'Roster >=2':>11} {'Parsed >=2':>11} {'5-Roster':>10} {'party_size=5':>13}")
    print("-" * 80)
    for label, d_max, d_min in [
        ("<= 3.00d", 3.0, None),
        ("Week -1 (0-7d]", 7.0, None),
        ("Week -2 (7-14d]", 14.0, 7.0),
        ("Week -3 (14-21d]", 21.0, 14.0),
        ("Week -4 (21-28d]", 28.0, 21.0),
        ("Past 28d Total", 28.0, None),
        ("Past 35d Total", 35.0, None),
    ]:
        s = summarize_window(def_list, now_ts, d_max, d_min)
        print(f"{label:<18} {s['total_unique']:>12} {s['ge2_roster']:>11} {s['ge2_parsed']:>11} {s['stack5_roster']:>10} {s['party_size_5']:>13}")
    print()

    print("--- PART B: ALL-MODES COMPARISON (significant=0, includes Turbo/AD) ---")
    print(f"{'Window':<18} {'Total Unique':>12} {'Roster >=2':>11} {'Parsed >=2':>11} {'5-Roster':>10} {'party_size=5':>13}")
    print("-" * 80)
    for label, d_max, d_min in [
        ("<= 3.00d", 3.0, None),
        ("Week -1 (0-7d]", 7.0, None),
        ("Week -2 (7-14d]", 14.0, 7.0),
        ("Week -3 (14-21d]", 21.0, 14.0),
        ("Week -4 (21-28d]", 28.0, 21.0),
        ("Past 28d Total", 28.0, None),
        ("Past 35d Total", 35.0, None),
    ]:
        s = summarize_window(sig0_list, now_ts, d_max, d_min)
        print(f"{label:<18} {s['total_unique']:>12} {s['ge2_roster']:>11} {s['ge2_parsed']:>11} {s['stack5_roster']:>10} {s['party_size_5']:>13}")
    print()

    print("--- PART A2: PAST 28D ROSTER STACK-SIZE DISTRIBUTION (ANONYMOUS) ---")
    def_28d = [m for m in def_list if m["start_time"] and 0 <= (now_ts - m["start_time"]) / 86400.0 <= 28.0]
    sig0_28d = [m for m in sig0_list if m["start_time"] and 0 <= (now_ts - m["start_time"]) / 86400.0 <= 28.0]
    print(f"{'Roster Stack (same team)':<28} {'Default (?date=35)':>18} {'All-Modes (sig=0)':>18}")
    print("-" * 68)
    for k in (1, 2, 3, 4, 5):
        c_def = sum(1 for m in def_28d if m["roster_same_team"] == k)
        c_s0 = sum(1 for m in sig0_28d if m["roster_same_team"] == k)
        lbl = f"{k}-roster (solo/external)" if k == 1 else f"{k}-roster"
        print(f"{lbl:<28} {c_def:>18} {c_s0:>18}")
    print()

    candidates = select_probe_candidates(default_matches, sig0_matches, now_ts)
    probe_results: List[Dict[str, Any]] = []
    for bucket_label, mid, stack_sz in candidates:
        probe_results.append(probe_match(mid, stack_sz, now_ts, patch_map, bucket_label))

    squad_parsed_all = [m for m in def_list if m["start_time"] and m["roster_same_team"] >= 2 and m["is_parsed"]]
    seen_ext = {r["match_id"] for r in probe_results}
    ext_results: List[Dict[str, Any]] = []
    for target in (28.0, 35.0):
        pool = [m for m in squad_parsed_all if m["match_id"] not in seen_ext]
        if pool:
            best = min(pool, key=lambda m: abs(((now_ts - m["start_time"]) / 86400.0) - target))
            seen_ext.add(best["match_id"])
            ext_results.append(probe_match(best["match_id"], best["roster_same_team"], now_ts, patch_map, f"Ext {int(target)}d (parsed >=2)"))

    hist_rows = http_get_json(f"{OPENDOTA_BASE}/players/{main_aid}/matches?date=200")
    time.sleep(0.35)
    if isinstance(hist_rows, list):
        hist_valid = [r for r in hist_rows if r.get("start_time") and r.get("match_id") not in seen_ext]
        for target in EXTENDED_HISTORY_TARGETS:
            ranked = sorted(
                hist_valid,
                key=lambda r: abs(((now_ts - int(r["start_time"])) / 86400.0) - target),
            )
            for cand in ranked[:4]:
                mid = int(cand["match_id"])
                if mid in seen_ext:
                    continue
                seen_ext.add(mid)
                res = probe_match(mid, None, now_ts, patch_map, f"Ext ~{target:g}d (boundary)")
                ext_results.append(res)
                if res["http_status"] != "N/A":
                    break

    def print_probe_table(title: str, rows: List[Dict[str, Any]]) -> None:
        print(title)
        hdr = f"{'Bucket':<28} {'Match ID':>11} {'Age(d)':>7} {'Stack':>5} {'OD Status':>9} {'Patch':>6} {'Cluster':>7} {'HTTP':>6} {'Content-Length':>15} {'Replay URL'}"
        print(hdr)
        print("-" * len(hdr))
        for r in rows:
            cl_str = f"{r['content_length']:,}" if r["content_length"] is not None else "-"
            cl_cluster = str(r["cluster"]) if r["cluster"] is not None else "-"
            print(
                f"{r['bucket']:<28} {r['match_id']:>11} {r['age_days']:>7.2f} {r['stack_size']:>5} "
                f"{r['parsed']:>9} {r['patch']:>6} {cl_cluster:>7} {r['http_status']:>6} {cl_str:>15} {r['replay_note']}"
            )
        print()

    print_probe_table("--- PART C: VALVE REPLAY RETENTION PROBE (HEAD ONLY, TARGETS 1/3/7/10/14/21d) ---", probe_results)
    print_probe_table("--- PART D: EXTENDED RETENTION BOUNDARY CHECK (28d-180d, HEAD ONLY) ---", ext_results)

    all_probed = probe_results + ext_results
    sizes_200 = [r["content_length"] for r in all_probed if r["http_status"] == "200" and r["content_length"]]
    max_200_age = max((r["age_days"] for r in all_probed if r["http_status"] == "200"), default=None)
    min_404_age = min((r["age_days"] for r in all_probed if r["http_status"] in ("404", "410")), default=None)
    if sizes_200:
        mb_vals = [x / (1024 * 1024) for x in sizes_200]
        print("--- PART E: MEASURED .dem.bz2 PAYLOAD SIZE & EMPIRICAL RETENTION SUMMARY ---")
        print(f"HTTP 200 samples          : {len(sizes_200)}")
        print(f"Min / Median / Mean / Max : {min(mb_vals):.2f} MiB / {statistics.median(mb_vals):.2f} MiB / {statistics.mean(mb_vals):.2f} MiB / {max(mb_vals):.2f} MiB")
        if max_200_age is not None and min_404_age is not None:
            print(f"Observed Valve CDN window : HTTP 200 up to {max_200_age:.2f}d; HTTP 404/410 from {min_404_age:.2f}d onward")
        elif max_200_age is not None:
            print(f"Observed Valve CDN window : HTTP 200 up to {max_200_age:.2f}d (no 404 in probed samples)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
