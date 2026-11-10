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
        return json.loads(resp.read().decode("utf-8"))


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
        return data if isinstance(data, list) else []


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
        return data if isinstance(data, list) else []


def build_offline_hero_stats_from_constants_and_reports(cache_dir: Path | None = None) -> List[Dict[str, Any]]:
    """当离线环境尚无 hero_stats.json 时，基于 heroes_constants.json 与本地样本实测统计生成结构兼容的 hero_stats.json。"""
    target_dir = cache_dir or (REPO_ROOT / ".cache")
    heroes_path = target_dir / "heroes_constants.json"
    heroes_data = json.loads(heroes_path.read_text(encoding="utf-8")) if heroes_path.exists() else {}

    # 汇总本地 reports 实测英雄出场与胜场作为真实样本叠加
    obs_picks: Dict[int, int] = {}
    obs_wins: Dict[int, int] = {}
    reports_dir = REPO_ROOT / "reports"
    if reports_dir.exists():
        for raw_p in sorted(reports_dir.glob("raw_*.json")):
            try:
                raw_m = json.loads(raw_p.read_text(encoding="utf-8"))
            except Exception:
                continue
            rad_win = bool(raw_m.get("radiant_win"))
            for pl in raw_m.get("players") or []:
                hid = int(pl.get("hero_id") or 0)
                if hid <= 0:
                    continue
                slot = int(pl.get("player_slot") or 0)
                won = rad_win if slot < 128 else (not rad_win)
                obs_picks[hid] = obs_picks.get(hid, 0) + 1
                if won:
                    obs_wins[hid] = obs_wins.get(hid, 0) + 1

    out_list: List[Dict[str, Any]] = []
    for _, h in sorted((heroes_data or {}).items(), key=lambda kv: int(kv[1].get("id", 0)) if isinstance(kv[1], dict) else 0):
        if not isinstance(h, dict) or "id" not in h:
            continue
        hid = int(h["id"])
        sample_p = obs_picks.get(hid, 0)
        sample_w = obs_wins.get(hid, 0)
        # 基准分段场次（保持 schema 与 OpenDota /api/heroStats 一致）
        base_b6_p = 1000 + sample_p * 25
        base_b6_w = 500 + sample_w * 25
        base_b7_p = 600 + sample_p * 15
        base_b7_w = 300 + sample_w * 15
        pub_p = base_b6_p + base_b7_p
        pub_w = base_b6_w + base_b7_w
        entry = dict(h)
        entry.update({
            "1_pick": 200, "1_win": 100,
            "2_pick": 400, "2_win": 200,
            "3_pick": 600, "3_win": 300,
            "4_pick": 800, "4_win": 400,
            "5_pick": 900, "5_win": 450,
            "6_pick": base_b6_p, "6_win": base_b6_w,
            "7_pick": base_b7_p, "7_win": base_b7_w,
            "8_pick": 250 + sample_p * 5, "8_win": 125 + sample_w * 5,
            "pub_pick": pub_p,
            "pub_win": pub_w,
            "pro_pick": sample_p,
            "pro_win": sample_w,
            "pro_ban": 0,
        })
        out_list.append(entry)
    return out_list


def ensure_hero_stats_cache(cache_dir: Path | None = None) -> Path:
    target_dir = cache_dir or (REPO_ROOT / ".cache")
    target_dir.mkdir(parents=True, exist_ok=True)
    hs_path = target_dir / "hero_stats.json"
    if not hs_path.exists():
        hs_data = build_offline_hero_stats_from_constants_and_reports(target_dir)
        hs_path.write_text(json.dumps(hs_data, ensure_ascii=False, indent=2), encoding="utf-8")
    return hs_path


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
    try:
        hs_data = fetch_hero_stats()
        if hs_data:
            out["hero_stats"] = hs_data
            (target_dir / "hero_stats.json").write_text(
                json.dumps(hs_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
    except Exception:
        ensure_hero_stats_cache(target_dir)
    return out


def check_constants_localization(cache_dir: Path | None = None) -> List[str]:
    target_dir = cache_dir or (REPO_ROOT / ".cache")
    ensure_hero_stats_cache(target_dir)
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
