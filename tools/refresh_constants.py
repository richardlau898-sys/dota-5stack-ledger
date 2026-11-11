#!/usr/bin/env python3
"""
从 OpenDota /constants/、/heroStats 与 Valve Dota 2 官方简体中文数据拉取真实数据到 .cache/，
并提供 --check 模式供 CI 离线检查常量表里的每个英雄及其技能是否都有中文名（--check 不写任何文件）。
"""
import argparse
import json
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import dota_analyst  # noqa: E402
import dota_constants_zh  # noqa: E402

CONSTANT_RESOURCES = ("heroes", "items", "abilities", "hero_abilities", "patch")
OPENDOTA_CONSTANTS_BASE = "https://api.opendota.com/api/constants"
OPENDOTA_API_BASE = "https://api.opendota.com/api"
VALVE_DATAFEED_BASE = "https://www.dota2.com/datafeed"
VALVE_ABILITIES_VDF_URL = (
    "https://raw.githubusercontent.com/dotabuff/d2vpkr/master/dota/resource/localization/abilities_schinese.txt"
)


def _http_get_text(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "dota-5stack-ledger-constants-refresher/1.0",
            "Accept": "application/json, text/plain, */*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def fetch_constant_resource(resource: str, timeout: int = 20) -> Any:
    raw = _http_get_text(f"{OPENDOTA_CONSTANTS_BASE}/{resource}", timeout=timeout)
    data = json.loads(raw)
    if not data:
        raise RuntimeError(f"OpenDota /constants/{resource} returned empty payload")
    return data


def fetch_hero_stats(timeout: int = 20) -> List[Dict[str, Any]]:
    """从 OpenDota /api/heroStats 拉取分段位选取与胜率数据（1_pick..8_pick, 1_win..8_win, pub_pick, pub_win）。"""
    raw = _http_get_text(f"{OPENDOTA_API_BASE}/heroStats", timeout=timeout)
    data = json.loads(raw)
    if not isinstance(data, list) or not data:
        raise RuntimeError("OpenDota /api/heroStats returned invalid or empty payload")
    return data


def fetch_player_heroes_against(account_id: int, timeout: int = 20) -> List[Dict[str, Any]]:
    """从 OpenDota /api/players/{account_id}/heroes 拉取个人历史英雄池与 against_games / against_win。"""
    raw = _http_get_text(f"{OPENDOTA_API_BASE}/players/{int(account_id)}/heroes", timeout=timeout)
    data = json.loads(raw)
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


def _format_num(val: Any) -> str:
    try:
        f = float(val)
        return str(int(f)) if f.is_integer() else f"{f:g}"
    except Exception:
        return str(val or "")


def _format_valve_talent_loc(talent: Dict[str, Any], hero_doc: Dict[str, Any]) -> str:
    loc = str(talent.get("name_loc") or "").strip()
    if not loc:
        return ""
    t_name = str(talent.get("name") or "")
    sv_map: Dict[str, str] = {}
    for sv in (talent.get("special_values") or []):
        nm = sv.get("name")
        vals = sv.get("values_float") or sv.get("values_int") or []
        if nm and vals:
            sv_map[str(nm)] = _format_num(vals[0])

    all_abs: List[Dict[str, Any]] = list(hero_doc.get("abilities") or [])
    for fa in (hero_doc.get("facet_abilities") or []):
        all_abs.extend(fa.get("abilities") or [])
    for ab in all_abs:
        for sv in (ab.get("special_values") or []):
            sv_name = str(sv.get("name") or "")
            for b in (sv.get("bonuses") or []):
                if b.get("name") == t_name and b.get("value") is not None:
                    fmt_v = _format_num(b.get("value"))
                    sv_map.setdefault(f"bonus_{sv_name}", fmt_v)
                    sv_map.setdefault("value", fmt_v)

    def _sub(m: re.Match) -> str:
        return sv_map.get(m.group(1), "")

    rendered = re.sub(r"\{s:([^}]+)\}", _sub, loc)
    rendered = re.sub(r"\s+", " ", rendered).strip()
    return rendered


def fetch_official_abilities_schinese(
    od_abilities: Optional[Dict[str, Any]] = None,
    timeout: int = 20,
) -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    结合 Valve 官方 Dota 2 简体中文 herodata 接口、官方 abilities_schinese.txt 与 OpenDota abilities 常量，
    生成覆盖全部英雄的 (by_key, by_id) 中文技能与天赋映射表。
    当测试中网络被 mock 为非 Valve 结构时安全返回空表。
    """
    by_key: Dict[str, str] = {}
    by_id: Dict[str, str] = {}

    try:
        vdf_txt = _http_get_text(VALVE_ABILITIES_VDF_URL, timeout=timeout)
        for m in re.finditer(r'"DOTA_Tooltip_[Aa]bility_([A-Za-z0-9_]+)"\s+"([^"]+)"', vdf_txt):
            k, v = m.group(1).strip(), m.group(2).strip()
            if not k or not v:
                continue
            if k.endswith(
                (
                    "_Description",
                    "_Lore",
                    "_Note0",
                    "_Note1",
                    "_Note2",
                    "_Note3",
                    "_Note4",
                    "_aghanim_description",
                    "_shard_description",
                )
            ):
                continue
            clean_v = re.sub(r"<[^>]+>", "", v).strip()
            if clean_v and any("\u4e00" <= ch <= "\u9fff" for ch in clean_v):
                by_key[k.lower()] = clean_v
    except Exception:
        pass

    try:
        hlist_doc = json.loads(_http_get_text(f"{VALVE_DATAFEED_BASE}/herolist?language=schinese", timeout=timeout))
        heroes_list = ((hlist_doc.get("result") or {}).get("data") or {}).get("heroes") or []
    except Exception:
        heroes_list = []

    if not isinstance(heroes_list, list) or not heroes_list:
        return by_key, by_id

    hero_ids = [int(h["id"]) for h in heroes_list if isinstance(h, dict) and "id" in h]

    def _fetch_pair(hid: int) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        zh_raw = json.loads(
            _http_get_text(f"{VALVE_DATAFEED_BASE}/herodata?language=schinese&hero_id={hid}", timeout=timeout)
        )
        en_raw = json.loads(
            _http_get_text(f"{VALVE_DATAFEED_BASE}/herodata?language=english&hero_id={hid}", timeout=timeout)
        )
        zh_heroes = ((zh_raw.get("result") or {}).get("data") or {}).get("heroes") or []
        en_heroes = ((en_raw.get("result") or {}).get("data") or {}).get("heroes") or []
        return (zh_heroes[0] if zh_heroes else {}, en_heroes[0] if en_heroes else {})

    with ThreadPoolExecutor(max_workers=12) as pool:
        pairs = list(pool.map(_fetch_pair, hero_ids))

    en_dname_to_zh: Dict[str, str] = {}
    for zh_h, en_h in pairs:
        en_id_to_dname: Dict[int, str] = {}
        for a in (en_h.get("abilities") or []):
            if a.get("id") and a.get("name_loc"):
                en_id_to_dname[int(a["id"])] = str(a["name_loc"]).strip()
        for fa in (en_h.get("facet_abilities") or []):
            for a in (fa.get("abilities") or []):
                if a.get("id") and a.get("name_loc"):
                    en_id_to_dname[int(a["id"])] = str(a["name_loc"]).strip()

        zh_abilities = list(zh_h.get("abilities") or [])
        for fa in (zh_h.get("facet_abilities") or []):
            zh_abilities.extend(fa.get("abilities") or [])

        for a in zh_abilities:
            aid = a.get("id")
            akey = str(a.get("name") or "").strip().lower()
            loc = re.sub(r"<[^>]+>", "", str(a.get("name_loc") or "")).strip()
            if not loc:
                continue
            if akey:
                by_key[akey] = loc
            if aid is not None:
                by_id[str(int(aid))] = loc
                en_dn = en_id_to_dname.get(int(aid))
                if en_dn:
                    en_dname_to_zh[en_dn.lower()] = loc

        for t in (zh_h.get("talents") or []):
            tid = t.get("id")
            tkey = str(t.get("name") or "").strip().lower()
            tloc = _format_valve_talent_loc(t, zh_h)
            if not tloc:
                continue
            if tkey:
                by_key[tkey] = tloc
            if tid is not None:
                by_id[str(int(tid))] = tloc

    if isinstance(od_abilities, dict):
        for akey, ainfo in od_abilities.items():
            if not isinstance(ainfo, dict):
                continue
            kl = str(akey).strip().lower()
            if kl in by_key:
                continue
            dname = str(ainfo.get("dname") or "").strip().lower()
            if dname and dname in en_dname_to_zh:
                by_key[kl] = en_dname_to_zh[dname]

    return by_key, by_id


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


def _compact_abilities_constants(raw_abilities: Any) -> Any:
    if not isinstance(raw_abilities, dict):
        return raw_abilities
    compact: Dict[str, Any] = {}
    for k, v in raw_abilities.items():
        if isinstance(v, dict):
            compact[k] = {
                "dname": v.get("dname"),
                "behavior": v.get("behavior"),
                "img": v.get("img"),
            }
        else:
            compact[k] = v
    return compact


def _sync_ability_id_catalog(
    catalog_path: Path,
    ability_ids: Optional[Dict[str, str]],
    by_key_zh: Dict[str, str],
    by_id_zh: Dict[str, str],
) -> None:
    if not catalog_path.is_file():
        return
    cat = json.loads(catalog_path.read_text(encoding="utf-8"))
    by_id_cat: Dict[str, Dict[str, Any]] = cat.get("by_id") or {}

    if isinstance(ability_ids, dict):
        for aid_str, akey in ability_ids.items():
            if not isinstance(akey, str):
                continue
            if aid_str not in by_id_cat:
                by_id_cat[aid_str] = {
                    "key": akey,
                    "zh": "",
                    "is_talent": akey.startswith("special_bonus_") and akey != "special_bonus_attributes",
                    "is_attr": akey == "special_bonus_attributes",
                }

    for aid_str, entry in by_id_cat.items():
        if not isinstance(entry, dict):
            continue
        akey = str(entry.get("key") or "").strip()
        cur_zh = str(entry.get("zh") or "").strip()
        if "专属技能" in cur_zh:
            cur_zh = ""
        resolved = (
            by_id_zh.get(aid_str)
            or by_key_zh.get(akey.lower())
            or dota_constants_zh.ABILITIES_ZH.get(akey)
            or cur_zh
        )
        if resolved and "专属技能" not in resolved:
            entry["zh"] = resolved
        else:
            entry["zh"] = ""

    cat["by_id"] = by_id_cat
    catalog_path.write_text(json.dumps(cat, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def refresh_all_constants(cache_dir: Optional[Path] = None) -> Dict[str, Any]:
    target_dir = cache_dir or (REPO_ROOT / ".cache")
    staged_constants: Dict[str, Any] = {}
    for res in CONSTANT_RESOURCES:
        staged_constants[res] = fetch_constant_resource(res)

    ability_ids_data: Optional[Dict[str, str]] = None
    try:
        aid_res = fetch_constant_resource("ability_ids")
        if isinstance(aid_res, dict):
            ability_ids_data = aid_res
    except Exception:
        ability_ids_data = None

    hs_data = fetch_hero_stats()
    hs_doc = build_hero_stats_document(hs_data)

    by_key_zh, by_id_zh = fetch_official_abilities_schinese(staged_constants.get("abilities"))

    target_dir.mkdir(parents=True, exist_ok=True)
    for res, data in staged_constants.items():
        out_file = target_dir / f"{res}_constants.json"
        to_write = _compact_abilities_constants(data) if res == "abilities" else data
        out_file.write_text(
            json.dumps(to_write, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    (target_dir / "hero_stats.json").write_text(
        json.dumps(hs_doc, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if by_key_zh:
        abilities_zh_doc = {
            "downloaded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source_urls": [
                f"{OPENDOTA_CONSTANTS_BASE}/abilities",
                f"{OPENDOTA_CONSTANTS_BASE}/hero_abilities",
                f"{VALVE_DATAFEED_BASE}/herodata?language=schinese",
                VALVE_ABILITIES_VDF_URL,
            ],
            "by_key": dict(sorted(by_key_zh.items())),
            "by_id": dict(sorted(by_id_zh.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0)),
        }
        (target_dir / "abilities_zh.json").write_text(
            json.dumps(abilities_zh_doc, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        for _k, _v in by_key_zh.items():
            if _k and _v and "专属技能" not in _v:
                dota_constants_zh.ABILITIES_ZH.setdefault(_k, _v)
        if cache_dir is None:
            _sync_ability_id_catalog(REPO_ROOT / "ability_id_catalog.json", ability_ids_data, by_key_zh, by_id_zh)

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

    ha_path = target_dir / "hero_abilities_constants.json"
    if ha_path.exists():
        ha_data = json.loads(ha_path.read_text(encoding="utf-8"))
        for npc, info in (ha_data or {}).items():
            if not isinstance(info, dict):
                continue
            for ab_key in (info.get("abilities") or []):
                if not isinstance(ab_key, str) or ab_key == "generic_hidden":
                    continue
                if ab_key in dota_constants_zh.IGNORED_SUB_OR_DUMMY_ABILITIES:
                    continue
                if "_empty" in ab_key or "_hidden" in ab_key:
                    continue
                zh = dota_constants_zh.get_ability_zh(ab_key)
                if not zh or "专属技能" in zh or not any("\u4e00" <= ch <= "\u9fff" for ch in zh):
                    errors.append(f"Ability {ab_key} ({npc}) lacks Chinese localization: {zh!r}")

    return errors


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh or check OpenDota constants cache.")
    parser.add_argument("--check", action="store_true", help="Offline check that all heroes & abilities have Chinese names.")
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
    print("OK: All heroes and abilities in constants cache have Chinese localization.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
