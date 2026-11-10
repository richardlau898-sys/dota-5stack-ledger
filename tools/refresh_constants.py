#!/usr/bin/env python3
"""
从 OpenDota /constants/ 拉取 heroes、items、abilities、hero_abilities、patch 到 .cache/，
并提供 --check 模式供 CI 离线检查常量表里的每个英雄是否都有中文名。
"""
import argparse
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import dota_analyst  # noqa: E402
import dota_constants_zh  # noqa: E402

CONSTANT_RESOURCES = ("heroes", "items", "abilities", "hero_abilities", "patch")
OPENDOTA_CONSTANTS_BASE = "https://api.opendota.com/api/constants"


def fetch_constant_resource(resource: str, timeout: int = 20) -> Any:
    url = f"{OPENDOTA_CONSTANTS_BASE}/{resource}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "dota-5stack-ledger-constants-refresher/1.0",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def refresh_all_constants(cache_dir: Path | None = None) -> Dict[str, Any]:
    target_dir = cache_dir or (REPO_ROOT / ".cache")
    target_dir.mkdir(parents=True, exist_ok=True)
    out: Dict[str, Any] = {}
    for res in CONSTANT_RESOURCES:
        data = fetch_constant_resource(res)
        out[res] = data
        out_file = target_dir / f"{res}_constants.json"
        out_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return out


def check_constants_localization(cache_dir: Path | None = None) -> List[str]:
    target_dir = cache_dir or (REPO_ROOT / ".cache")
    errors: List[str] = []

    heroes_path = target_dir / "heroes_constants.json"
    if not heroes_path.exists():
        errors.append(f"Missing {heroes_path}")
        return errors

    heroes_data = json.loads(heroes_path.read_text(encoding="utf-8"))
    for k, val in (heroes_data or {}).items():
        if not isinstance(val, dict) or "id" not in val:
            continue
        hid = int(val["id"])
        if hid not in dota_constants_zh.HEROES_ZH:
            errors.append(f"Hero id={hid} ({val.get('localized_name') or val.get('name')}) missing in HEROES_ZH")
            continue
        short_zh = dota_constants_zh.HEROES_ZH[hid][0]
        if not any("\u4e00" <= ch <= "\u9fff" for ch in short_zh):
            errors.append(f"Hero id={hid} short_zh is not Chinese: {short_zh!r}")

    by_id, _ = dota_analyst.get_hero_constants_map()
    for hid, info in by_id.items():
        short_zh = str(info.get("short_zh") or "")
        if not any("\u4e00" <= ch <= "\u9fff" for ch in short_zh) or short_zh.startswith("英雄#"):
            errors.append(f"Hero id={hid} in get_hero_constants_map() lacks Chinese name: {short_zh!r}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh or check OpenDota constants cache.")
    parser.add_argument("--check", action="store_true", help="Offline check that all heroes have Chinese names.")
    args = parser.parse_args()

    if not args.check:
        refreshed = refresh_all_constants()
        print(f"Refreshed {len(refreshed)} constant tables into .cache/")

    errs = check_constants_localization()
    if errs:
        for e in errs:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print("OK: All heroes in constants cache have Chinese localization.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
