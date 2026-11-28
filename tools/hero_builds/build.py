#!/usr/bin/env python3
"""Aggregate cached matches into per-hero build stats for the hero page.

Inputs
  --cache DIR     cache/matches/*.json written by collect.py
  --const DIR     OpenDota constants (ability_ids, hero_abilities, items, item_ids, abilities)
                  + Valve datafeed (df_herolist.json, df_itemlist.json, df_patchnotes.json,
                  herodata/<id>.json), as written by fetch_constants.py
Outputs (at least one)
  --bundle FILE   one gzipped JSON {"index": ..., "heroes": {"<id>": ...}} served by the site
  --out-dir DIR   index.json + heroes/<id>.json, handy for looking at the data locally

Every number is a count from the sampled matches. Nothing is estimated:
roles are inferred from team net-worth rank and are labelled as inferred.
"""
import argparse
import collections
import glob
import gzip
import json
import os
import re
import time

CDN = "https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react"
MAX_POINTS = 25
TALENT_TIER_LEVEL = {1: 10, 2: 15, 3: 20, 4: 25}
MIN_SCOPE_GAMES = 12
SKIP_ITEMS = {
    "tango", "flask", "clarity", "faerie_fire", "enchanted_mango", "ward_observer", "ward_sentry",
    "ward_dispenser", "smoke_of_deceit", "dust", "tpscroll", "blood_grenade", "aegis", "cheese",
    "refresher_shard", "tome_of_knowledge", "famango", "great_famango", "greater_famango",
}
BOOTS = {
    "boots", "power_treads", "phase_boots", "arcane_boots", "tranquil_boots", "travel_boots",
    "travel_boots_2", "guardian_greaves", "boots_of_bearing", "berserkers_sabatons",
}


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def fmt_num(v):
    if isinstance(v, (int, float)):
        return str(int(v)) if float(v).is_integer() else f"{v:g}"
    return str(v)


def resolve_talent_text(text, talent_name, abilities, talent_obj):
    """Fill {s:bonus_X} / {s:X} placeholders from the official ability data."""
    unresolved = False

    def repl(m):
        nonlocal unresolved
        key = m.group(1)
        base = key[6:] if key.startswith("bonus_") else key
        for ab in abilities:
            for sv in ab.get("special_values") or []:
                if sv.get("name") in (base, key):
                    for b in sv.get("bonuses") or []:
                        if b.get("name") == talent_name:
                            return fmt_num(b.get("value"))
        for sv in (talent_obj or {}).get("special_values") or []:
            if sv.get("name") in (key, base) and sv.get("values_float"):
                return fmt_num(sv["values_float"][0])
        unresolved = True
        return "?"

    out = re.sub(r"\{s:([A-Za-z0-9_]+)\}", repl, text or "")
    out = re.sub(r"<[^>]+>", "", out).replace("%%", "%").replace("+-", "-").replace("-+", "-").strip()
    return out, unresolved


def wr(w, n):
    return round(100.0 * w / n, 1) if n else None


def build(cache_dir, const_dir):
    """Return (index, heroes) where heroes maps hero id -> full per-hero stats."""
    c = const_dir

    ability_ids = load(os.path.join(c, "ability_ids.json"))
    hero_abilities = load(os.path.join(c, "hero_abilities.json"))
    od_items = load(os.path.join(c, "items.json"))
    item_ids = load(os.path.join(c, "item_ids.json"))
    od_abilities = load(os.path.join(c, "abilities.json"))
    herolist = load(os.path.join(c, "df_herolist.json"))["result"]["data"]["heroes"]
    itemlist = load(os.path.join(c, "df_itemlist.json"))["result"]["data"]["itemabilities"]
    df_item = {it["id"]: it for it in itemlist}
    pn_path = os.path.join(c, "df_patchnotes.json")
    patchnotes = load(pn_path) if os.path.exists(pn_path) else {}
    patch_names = {p["id"]: p["name"] for p in load(os.path.join(c, "patch.json"))}

    def clean_note(t):
        return re.sub(r"<[^>]+>", "", t or "").strip()

    def item_info(iid):
        key = item_ids.get(str(iid))
        if not key:
            return None
        df = df_item.get(int(iid)) or {}
        od = od_items.get(key) or {}
        tier = df.get("neutral_item_tier", -1)
        return {
            "key": key,
            "zh": df.get("name_loc") or od.get("dname") or key,
            "en": df.get("name_english_loc") or od.get("dname") or key,
            "cost": od.get("cost") or 0,
            "neutral_tier": (tier + 1) if isinstance(tier, int) and tier >= 0 else None,
            "img": f"{CDN}/items/{key}.png",
        }

    matches = [load(f) for f in glob.glob(os.path.join(cache_dir, "matches", "*.json"))]
    patch = max((m["patch"] for m in matches), default=None)
    matches = [m for m in matches if m["patch"] == patch]
    patch_name = patch_names.get(patch)
    # Only attach patch notes that belong to the patch the matches were played on.
    notes_match = bool(patch_name) and str(patchnotes.get("patch_name") or patchnotes.get("patch_number")) == patch_name
    pn_by_hero = {h.get("hero_id"): h for h in patchnotes.get("heroes") or []} if notes_match else {}
    rank_tiers = collections.Counter((m.get("avg_rank_tier") or 0) // 10 for m in matches)

    # Per hero, per scope -> accumulators
    acc = collections.defaultdict(lambda: collections.defaultdict(lambda: {
        "n": 0, "w": 0,
        "points": collections.defaultdict(collections.Counter),
        "point_wins": collections.defaultdict(collections.Counter),
        "orders": collections.Counter(), "order_wins": collections.Counter(),
        "max_first": collections.Counter(), "max_first_wins": collections.Counter(),
        "talents": collections.defaultdict(collections.Counter),
        "talent_wins": collections.defaultdict(collections.Counter),
        "neutral": collections.defaultdict(collections.Counter),
        "neutral_wins": collections.defaultdict(collections.Counter),
        "ench": collections.Counter(), "ench_wins": collections.Counter(),
        "items": collections.Counter(), "item_wins": collections.Counter(),
        "boots": collections.Counter(), "boot_wins": collections.Counter(),
        "scepter": 0, "shard": 0,
    }))

    hero_meta = {}
    for h in herolist:
        hd_path = os.path.join(c, "herodata", f"{h['id']}.json")
        hd = load(hd_path)["result"]["data"]["heroes"][0] if os.path.exists(hd_path) else {}
        npc = h["name"]
        short = npc.replace("npc_dota_hero_", "")
        ha = hero_abilities.get(npc) or {}
        talent_tier = {t["name"]: t["level"] for t in ha.get("talents") or []}
        abil_by_name = {a["name"]: a for a in hd.get("abilities") or []}
        basic = [a for a in (hd.get("abilities") or [])
                 if not a.get("ability_is_innate") and not a.get("ability_is_granted_by_scepter")
                 and not a.get("ability_is_granted_by_shard") and (a.get("max_level") or 0) > 1]
        talents_zh = {}
        unresolved_cnt = 0
        for t in hd.get("talents") or []:
            txt, bad = resolve_talent_text(t.get("name_loc"), t.get("name"), hd.get("abilities") or [], t)
            if bad:
                unresolved_cnt += 1
                en = (od_abilities.get(t.get("name")) or {}).get("dname")
                if en:
                    txt = f"{txt}（{en}）"
            talents_zh[t.get("name")] = txt
        ab_name_by_id = {a.get("id"): a.get("name_loc") for a in hd.get("abilities") or []}
        pn = pn_by_hero.get(h["id"]) or {}
        notes = []
        for n in pn.get("hero_notes") or []:
            notes.append({"sec": "英雄", "t": clean_note(n.get("note")), "info": clean_note(n.get("info"))})
        for ab in pn.get("abilities") or []:
            label = ab_name_by_id.get(ab.get("ability_id")) or "技能"
            for n in ab.get("ability_notes") or []:
                notes.append({"sec": label, "t": clean_note(n.get("note")), "info": clean_note(n.get("info"))})
        for n in pn.get("talent_notes") or []:
            notes.append({"sec": "天赋", "t": clean_note(n.get("note")), "info": clean_note(n.get("info"))})
        hero_meta[h["id"]] = {
            "patch_notes": [x for x in notes if x["t"]],
            "id": h["id"], "npc": npc, "short": short,
            "zh": h.get("name_loc"), "en": h.get("name_english_loc"),
            "attr": h.get("primary_attr"),
            "img": f"{CDN}/heroes/{short}.png",
            "abilities": [{
                "key": a["name"], "zh": a.get("name_loc"), "max": a.get("max_level"),
                "img": f"{CDN}/abilities/{a['name']}.png",
            } for a in basic],
            "_talent_tier": talent_tier,
            "_talents_zh": talents_zh,
            "_abil_max": {a["name"]: a.get("max_level") or 4 for a in basic},
            "_basic": {a["name"] for a in basic},
            "unresolved_talents": unresolved_cnt,
        }

    for m in matches:
        players = m["players"]
        for side in (0, 1):
            team = [p for p in players if (p["player_slot"] < 128) == (side == 0)]
            ranked = sorted(team, key=lambda p: -(p.get("net_worth") or 0))
            for rank, p in enumerate(ranked, 1):
                p["_role"] = "core" if rank <= 3 else "support"
        for p in players:
            hid = p.get("hero_id")
            meta = hero_meta.get(hid)
            if not meta:
                continue
            won = (p["player_slot"] < 128) == bool(m["radiant_win"])
            for scope in ("all", p["_role"]):
                a = acc[hid][scope]
                a["n"] += 1
                a["w"] += won
                # skills
                seq = [ability_ids.get(str(x), "") for x in (p.get("ability_upgrades_arr") or [])]
                basic_seq = []
                levels = collections.Counter()
                maxed = []
                for i, name in enumerate(seq[:MAX_POINTS]):
                    if name.startswith("special_bonus"):
                        tier = meta["_talent_tier"].get(name)
                        if tier:
                            a["talents"][tier][name] += 1
                            if won:
                                a["talent_wins"][tier][name] += 1
                        a["points"][i]["__talent__"] += 1
                        if won:
                            a["point_wins"][i]["__talent__"] += 1
                        continue
                    a["points"][i][name] += 1
                    if won:
                        a["point_wins"][i][name] += 1
                    if name in meta["_basic"]:
                        basic_seq.append(name)
                        levels[name] += 1
                        if levels[name] == meta["_abil_max"].get(name) and name not in maxed:
                            maxed.append(name)
                if len(basic_seq) >= 10:
                    key = ",".join(basic_seq[:10])
                    a["orders"][key] += 1
                    if won:
                        a["order_wins"][key] += 1
                non_ult = [x for x in maxed if (meta["_abil_max"].get(x) or 4) > 3]
                if non_ult:
                    a["max_first"][non_ult[0]] += 1
                    if won:
                        a["max_first_wins"][non_ult[0]] += 1
                # neutral item + enchantment (final state at game end)
                ni = item_info(p.get("item_neutral")) if p.get("item_neutral") else None
                if ni and ni["neutral_tier"]:
                    a["neutral"][ni["neutral_tier"]][ni["key"]] += 1
                    if won:
                        a["neutral_wins"][ni["neutral_tier"]][ni["key"]] += 1
                en = item_info(p.get("item_neutral2")) if p.get("item_neutral2") else None
                if en and en["key"].startswith("enhancement_"):
                    a["ench"][en["key"]] += 1
                    if won:
                        a["ench_wins"][en["key"]] += 1
                # final items (inventory + backpack), counted once per game
                keys = set()
                for slot in ("item_0", "item_1", "item_2", "item_3", "item_4", "item_5",
                             "backpack_0", "backpack_1", "backpack_2"):
                    info = item_info(p.get(slot)) if p.get(slot) else None
                    if info:
                        keys.add(info["key"])
                for k in keys:
                    if k in BOOTS:
                        a["boots"][k] += 1
                        if won:
                            a["boot_wins"][k] += 1
                    elif k not in SKIP_ITEMS and (od_items.get(k) or {}).get("cost", 0) >= 1200 \
                            and not k.startswith(("recipe_", "enhancement_")):
                        a["items"][k] += 1
                        if won:
                            a["item_wins"][k] += 1
                # The public-match aghanims_scepter flag is almost always 0 (2 of 2,700 players on
                # 2026-11-22), so count the Scepter only when it is in the final inventory.
                a["scepter"] += 1 if "ultimate_scepter" in keys else 0
                a["shard"] += 1 if p.get("aghanims_shard") else 0

    key_to_info = {}

    def info_by_key(k):
        if k not in key_to_info:
            od = od_items.get(k) or {}
            key_to_info[k] = item_info(od.get("id")) if od.get("id") else {"key": k, "zh": k, "en": k, "img": f"{CDN}/items/{k}.png"}
        return key_to_info[k]

    def ranked(counter, wins, n, limit):
        out = []
        for k, cnt in counter.most_common(limit):
            out.append({"k": k, "n": cnt, "pct": round(100.0 * cnt / n, 1) if n else None, "wr": wr(wins[k], cnt)})
        return out

    # Hero level at which the n-th ability upgrade happens, derived from this patch's data:
    # for each final hero level, the most common number of upgrades players have made.
    by_level = collections.defaultdict(collections.Counter)
    for m in matches:
        for p in m["players"]:
            lv, cnt = p.get("level"), len(p.get("ability_upgrades_arr") or [])
            if lv and cnt:
                by_level[lv][cnt] += 1
    upgrades_at_level = {lv: c.most_common(1)[0][0] for lv, c in by_level.items() if sum(c.values()) >= 8}
    # Few games end below level 7, so early levels have no samples. Below the lowest observed level
    # we assume one point per level, which matches the observed levels 7-9 (upgrades == level).
    lowest = min(upgrades_at_level, default=1)
    if upgrades_at_level.get(lowest) == lowest:
        for lv in range(1, lowest):
            upgrades_at_level[lv] = lv
    point_level = {}
    for i in range(1, MAX_POINTS + 1):
        lv = min((lv for lv, cnt in upgrades_at_level.items() if cnt >= i), default=None)
        point_level[i] = lv

    heroes_out = []
    total_slots = sum(len(m["players"]) for m in matches)
    for hid, meta in hero_meta.items():
        scopes = {}
        for scope, a in acc.get(hid, {}).items():
            n = a["n"]
            if n < MIN_SCOPE_GAMES and scope != "all":
                continue
            points = []
            for i in sorted(a["points"]):
                cnt = a["points"][i]
                reached = sum(cnt.values())
                if reached < max(5, n * 0.3):
                    continue
                top = cnt.most_common(2)
                points.append({
                    "i": i + 1, "lvl": point_level.get(i + 1), "reached": reached,
                    "top": [{"k": k, "pct": round(100.0 * v / reached, 1)} for k, v in top],
                })
            talents = []
            for tier in (1, 2, 3, 4):
                opts = a["talents"].get(tier, collections.Counter())
                taken = sum(opts.values())
                names = [t for t, lv in meta["_talent_tier"].items() if lv == tier]
                talents.append({
                    "tier": tier, "level": TALENT_TIER_LEVEL[tier], "taken": taken,
                    "options": [{
                        "k": t, "zh": meta["_talents_zh"].get(t, t),
                        "n": opts.get(t, 0),
                        "pct": round(100.0 * opts.get(t, 0) / taken, 1) if taken else None,
                        "wr": wr(a["talent_wins"][tier].get(t, 0), opts.get(t, 0)),
                    } for t in names],
                })
            neutral = []
            for tier in sorted(a["neutral"]):
                tot = sum(a["neutral"][tier].values())
                neutral.append({"tier": tier, "n": tot, "items": [
                    dict(r, **{"zh": info_by_key(r["k"])["zh"], "img": info_by_key(r["k"])["img"]})
                    for r in ranked(a["neutral"][tier], a["neutral_wins"][tier], tot, 5)]})
            ench_tot = sum(a["ench"].values())
            scopes[scope] = {
                "n": n, "wr": wr(a["w"], n),
                "points": points,
                "orders": [dict(o, order=o["k"].split(",")) for o in ranked(a["orders"], a["order_wins"], sum(a["orders"].values()), 3)],
                "max_first": ranked(a["max_first"], a["max_first_wins"], sum(a["max_first"].values()), 3),
                "talents": talents,
                "neutral": neutral,
                "ench": {"n": ench_tot, "items": [
                    dict(r, **{"zh": info_by_key(r["k"])["zh"], "img": info_by_key(r["k"])["img"]})
                    for r in ranked(a["ench"], a["ench_wins"], ench_tot, 6)]},
                "items": [dict(r, **{"zh": info_by_key(r["k"])["zh"], "img": info_by_key(r["k"])["img"]})
                          for r in ranked(a["items"], a["item_wins"], n, 12)],
                "boots": [dict(r, **{"zh": info_by_key(r["k"])["zh"], "img": info_by_key(r["k"])["img"]})
                          for r in ranked(a["boots"], a["boot_wins"], n, 4)],
                "scepter_pct": round(100.0 * a["scepter"] / n, 1) if n else None,
                "shard_pct": round(100.0 * a["shard"] / n, 1) if n else None,
            }
        all_n = scopes.get("all", {}).get("n", 0)
        heroes_out.append({
            "id": hid, "zh": meta["zh"], "en": meta["en"], "short": meta["short"], "attr": meta["attr"],
            "img": meta["img"], "abilities": meta["abilities"],
            "games": all_n, "pick_pct": round(100.0 * all_n / total_slots * 10, 2) if total_slots else None,
            "unresolved_talents": meta["unresolved_talents"],
            "scopes": scopes,
        })
    heroes_out.sort(key=lambda h: -h["games"])
    out = {
        "generated_at": int(time.time()),
        "patch_id": patch,
        "matches": len(matches),
        "rank_tier_mix": {str(k): v for k, v in sorted(rank_tiers.items())},
        "first_match_time": min((m["start_time"] for m in matches), default=None),
        "last_match_time": max((m["start_time"] for m in matches), default=None),
        "upgrades_at_level": {str(k): v for k, v in sorted(upgrades_at_level.items())},
        "patch_name": patch_name,
        "has_patch_notes": notes_match,
        "role_note": "核心/辅助按本队终局净值排名推断：前三为核心，后二为辅助",
        "neutral_note": "中立物品与附魔为比赛结束时携带的那一件",
        "heroes": [{k: v for k, v in h.items() if k not in ("scopes", "abilities")} for h in heroes_out],
    }
    heroes_full = {
        h["id"]: {"id": h["id"], "abilities": h["abilities"], "scopes": h["scopes"],
                  "patch_notes": hero_meta[h["id"]]["patch_notes"]}
        for h in heroes_out
    }
    return out, heroes_full


def write_outputs(index, heroes, bundle=None, out_dir=None):
    if bundle:
        os.makedirs(os.path.dirname(os.path.abspath(bundle)), exist_ok=True)
        payload = json.dumps({"index": index, "heroes": {str(k): v for k, v in heroes.items()}},
                             ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        tmp = bundle + ".tmp"
        with open(tmp, "wb") as fh:
            fh.write(gzip.compress(payload, compresslevel=9))
        os.replace(tmp, bundle)
    if out_dir:
        os.makedirs(os.path.join(out_dir, "heroes"), exist_ok=True)
        with open(os.path.join(out_dir, "index.json"), "w", encoding="utf-8") as fh:
            json.dump(index, fh, ensure_ascii=False, separators=(",", ":"))
        for hid, full in heroes.items():
            with open(os.path.join(out_dir, "heroes", f"{hid}.json"), "w", encoding="utf-8") as fh:
                json.dump(full, fh, ensure_ascii=False, separators=(",", ":"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--const", required=True)
    ap.add_argument("--bundle")
    ap.add_argument("--out-dir")
    args = ap.parse_args()
    if not args.bundle and not args.out_dir:
        ap.error("give --bundle and/or --out-dir")
    index, heroes = build(args.cache, args.const)
    if not index["matches"]:
        raise SystemExit("no matches for the current patch in the cache; nothing written")
    write_outputs(index, heroes, bundle=args.bundle, out_dir=args.out_dir)
    biggest = max((len(json.dumps(v, ensure_ascii=False)) for v in heroes.values()), default=0)
    print(f"patch {index['patch_name'] or index['patch_id']}: {index['matches']} matches, "
          f"{len(heroes)} heroes, largest hero {biggest // 1024} KB"
          + (f", bundle {os.path.getsize(args.bundle) // 1024} KB" if args.bundle else ""))


if __name__ == "__main__":
    main()
