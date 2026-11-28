#!/usr/bin/env python3
"""Download the reference data build.py needs. Stdlib only.

OpenDota constants:  patch, heroes, items, item_ids, abilities, ability_ids, hero_abilities
Valve dota2.com datafeed (official Simplified Chinese):
  herolist, itemlist, herodata for every hero, and the patch notes of the latest patch.

Usage: python3 fetch_constants.py --out DIR
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

OD = "https://api.opendota.com/api/constants/"
DF = "https://www.dota2.com/datafeed/"
UA = "dota-hero-builds-constants/0.1"


def get(url, tries=4):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if i == tries - 1:
                raise
            # 429: the per-minute quota is shared with collect.py, so wait for the next minute.
            time.sleep(65 if e.code == 429 else 3 * (i + 1))
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(3 * (i + 1))


def save(path, raw):
    json.loads(raw)  # refuse to write anything that is not valid JSON
    tmp = path + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(raw)
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(os.path.join(a.out, "herodata"), exist_ok=True)
    for name in ("patch", "heroes", "items", "item_ids", "abilities", "ability_ids", "hero_abilities"):
        save(os.path.join(a.out, f"{name}.json"), get(OD + name))
        time.sleep(1.2)
    save(os.path.join(a.out, "df_herolist.json"), get(DF + "herolist?language=schinese"))
    save(os.path.join(a.out, "df_itemlist.json"), get(DF + "itemlist?language=schinese"))
    heroes = json.load(open(os.path.join(a.out, "df_herolist.json"), encoding="utf-8"))["result"]["data"]["heroes"]
    for h in heroes:
        save(os.path.join(a.out, "herodata", f"{h['id']}.json"),
             get(DF + f"herodata?language=schinese&hero_id={h['id']}"))
        time.sleep(0.3)
    plist = json.loads(get(DF + "patchnoteslist?language=schinese"))
    latest = plist["patches"][-1]["patch_name"]
    save(os.path.join(a.out, "df_patchnotes.json"), get(DF + f"patchnotes?version={latest}&language=schinese"))
    print(f"constants saved to {a.out}: {len(heroes)} heroes, patch notes {latest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
