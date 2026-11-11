#!/usr/bin/env python3
"""
从 OpenDota /constants/ 与 /heroStats 拉取真实数据到 .cache/，
并提供 --check 模式供 CI 离线检查常量表里的每个英雄是否都有中文名（--check 不写任何文件）。
"""
import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import dota_analyst  # noqa: E402
import dota_constants_zh  # noqa: E402

CONSTANT_RESOURCES = ("heroes", "items", "abilities", "hero_abilities", "patch")
OPENDOTA_CONSTANTS_BASE = "https://api.opendota.com/api/constants"
OPENDOTA_API_BASE = "https://api.opendota.com/api"


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
        data = json.loads(resp.read().decode("utf-8"))
    if not data:
        raise RuntimeError(f"OpenDota /constants/{resource} returned empty payload")
    return data


def fetch_hero_stats(timeout: int = 20) -> List[Dict[str, Any]]:
    """从 OpenDota /api/heroStats 拉取分段位选取与胜率数据（1_pick..8_pick, 1_win..8_win, pub_pick, pub_win）。"""
    url = f"{OPENDOTA_API_BASE}/heroStats"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "dota-5stack-ledger-constants-refresher/1.0",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if not isinstance(data, list) or not data:
        raise RuntimeError("OpenDota /api/heroStats returned invalid or empty payload")
    return data


def fetch_player_heroes_against(account_id: int, timeout: int = 20) -> List[Dict[str, Any]]:
    """从 OpenDota /api/players/{account_id}/heroes 拉取个人历史英雄池与 against_games / against_win。"""
    url = f"{OPENDOTA_API_BASE}/players/{int(account_id)}/heroes"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "dota-5stack-ledger-constants-refresher/1.0",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if not isinstance(data, list):
        raise RuntimeError(f"OpenDota /players/{account_id}/heroes returned invalid payload")
    return data


def build_hero_stats_document(hs_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    downloaded_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "downloaded_at": downloaded_at,
        "source_url": f"{OPENDOTA_API_BASE}/heroStats",
        "heroes": hs_data,
    }


def refresh_hero_stats_only(cache_dir: Optional[Path] = None) -> Dict[str, Any]:
    target_dir = cache_dir or (REPO_ROOT / ".cache")
    hs_data = fetch_hero_stats()
    doc = build_hero_stats_document(hs_data)
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "hero_stats.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return doc


def refresh_all_constants(cache_dir: Optional[Path] = None) -> Dict[str, Any]:
    target_dir = cache_dir or (REPO_ROOT / ".cache")
    staged_constants: Dict[str, Any] = {}
    for res in CONSTANT_RESOURCES:
        staged_constants[res] = fetch_constant_resource(res)
    hs_data = fetch_hero_stats()
    hs_doc = build_hero_stats_document(hs_data)

    target_dir.mkdir(parents=True, exist_ok=True)
    for res, data in staged_constants.items():
        out_file = target_dir / f"{res}_constants.json"
        out_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    (target_dir / "hero_stats.json").write_text(
        json.dumps(hs_doc, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    out = dict(staged_constants)
    out["hero_stats"] = hs_doc
    return out


def check_constants_localization(cache_dir: Optional[Path] = None) -> List[str]:
    target_dir = cache_dir or (REPO_ROOT / ".cache")
    errors: List[str] = []

    heroes_path = target_dir / "heroes_constants.json"
    if not heroes_path.exists():
        errors.append(f"Missing {heroes_path}")
        return errors

    heroes_data = json.loads(heroes_path.read_text(encoding="utf-8"))
    for _k, val in (heroes_data or {}).items():
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


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh or check OpenDota constants cache.")
    parser.add_argument("--check", action="store_true", help="Offline check that all heroes have Chinese names (writes no files).")
    parser.add_argument("--hero-stats-only", action="store_true", help="Only fetch /api/heroStats into hero_stats.json.")
    parser.add_argument("--cache-dir", default=None, help="Override target .cache directory.")
    args = parser.parse_args(argv)

    target_dir = Path(args.cache_dir) if args.cache_dir else None

    if not args.check:
        try:
            if args.hero_stats_only:
                doc = refresh_hero_stats_only(target_dir)
                print(f"Refreshed hero_stats.json ({len(doc['heroes'])} heroes, downloaded_at={doc['downloaded_at']})")
                return 0
            refreshed = refresh_all_constants(target_dir)
            print(f"Refreshed {len(refreshed)} resources into {target_dir or (REPO_ROOT / '.cache')}")
        except Exception as exc:
            print(f"ERROR: Failed to refresh OpenDota constants/heroStats: {exc}", file=sys.stderr)
            return 1

    errs = check_constants_localization(target_dir)
    if errs:
        for e in errs:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print("OK: All heroes in constants cache have Chinese localization.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
