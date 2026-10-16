#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dota 2 战后算账与录像级复盘引擎 (dota_analyst.py)
功能:
1. 好友与五黑车队花名册管理 (roster.json) - 自动识别 Steam32 / Steam64 ID
2. 查询玩家最近比赛列表 (recent)
3. 深度分析单场比赛 (analyze):
   - 自动推断双方 1~5 号位
   - 官方 Valve/Steam CDN 英雄立绘、英雄小图标、六神装+中立道具+背包图标、技能图标
   - 主动道具按键次数审计 (item_uses) 与技能释放次数统计 (ability_uses)
   - 击杀/被杀提款矩阵 (killed / killed_by)、野怪/防御塔/泉水击杀取证、读秒时长与阵亡扣钱
   - 2D 战术小地图真假眼坐标 (obs_log / sen_log) 与对线期走位热力图 (lane_pos)
   - 十人分钟级净资产曲线 (networth_t) 与前/中/后三阶段 (0-10m / 10-25m / 25m+) 差分账本
   - 自动挂载或调用 xAI Grok (grok-4.7) 结构化复盘数据
"""

import argparse
import datetime
import json
import math
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dota_constants_zh import (
    HEROES_ZH,
    ITEMS_ZH,
    LANE_ROLE_ZH,
    get_ability_zh,
    get_hero_default_pos,
    get_hero_name,
    get_mode_and_lobby,
    get_rank_name,
)
from ai_coach_engine import (
    assign_team_blame_percentages,
    build_four_stage_narrative,
    evaluate_player_deeply,
    select_match_mvp_and_culprit,
)

BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / ".cache"
ROSTER_FILE = BASE_DIR / "roster.json"
REPORTS_DIR = BASE_DIR / "reports"

STEAM64_OFFSET = 76561197960265728
OPENDOTA_BASE = "https://api.opendota.com/api"
VALVE_CDN = "https://cdn.cloudflare.steamstatic.com"


def normalize_account_id(raw_id: Any) -> int:
    """支持输入 Steam32 (好友ID) 或 17位 Steam64 ID，统一转为 Steam32 account_id"""
    val = int(str(raw_id).strip())
    if val >= STEAM64_OFFSET:
        return val - STEAM64_OFFSET
    return val


def api_get(endpoint: str, timeout: int = 15) -> Any:
    url = f"{OPENDOTA_BASE}{endpoint}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Dota2AIAnalyst/2.0",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def api_post(endpoint: str, timeout: int = 15) -> Any:
    url = f"{OPENDOTA_BASE}{endpoint}"
    req = urllib.request.Request(
        url,
        data=b"",
        method="POST",
        headers={
            "User-Agent": "Dota2AIAnalyst/2.0",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


TMP_ROSTER_FILE = Path("/tmp/dota_roster.json")
TMP_CACHE_DIR = Path("/tmp/dota_cache")


def load_roster() -> Dict[str, Any]:
    for rfile in (TMP_ROSTER_FILE, ROSTER_FILE):
        if rfile.exists():
            try:
                return json.loads(rfile.read_text(encoding="utf-8"))
            except Exception:
                pass
    return {
        "main_account_id": None,
        "main_name": "我",
        "players": {},
    }


def save_roster(roster: Dict[str, Any]) -> None:
    payload = json.dumps(roster, ensure_ascii=False, indent=2)
    try:
        ROSTER_FILE.write_text(payload, encoding="utf-8")
    except OSError:
        TMP_ROSTER_FILE.write_text(payload, encoding="utf-8")


def get_hero_constants_map() -> Tuple[Dict[int, Dict[str, Any]], Dict[str, int]]:
    """
    返回:
    1. hero_id -> {"id": int, "npc": str, "slug": str, "short_zh": str, "alias": str, "full_zh": str, "img": str, "icon": str}
    2. npc_dota_hero_xxx -> hero_id
    """
    cache_file = CACHE_DIR / "heroes_constants.json"
    tmp_cache_file = TMP_CACHE_DIR / "heroes_constants.json"
    heroes_data = None
    for cf in (cache_file, tmp_cache_file):
        if cf.exists():
            try:
                heroes_data = json.loads(cf.read_text(encoding="utf-8"))
                break
            except Exception:
                heroes_data = None

    if not heroes_data:
        try:
            heroes_data = api_get("/constants/heroes", timeout=15)
            try:
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                cache_file.write_text(
                    json.dumps(heroes_data, ensure_ascii=False), encoding="utf-8"
                )
            except OSError:
                TMP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                tmp_cache_file.write_text(
                    json.dumps(heroes_data, ensure_ascii=False), encoding="utf-8"
                )
        except Exception:
            heroes_data = {}

    by_id: Dict[int, Dict[str, Any]] = {}
    npc_to_id: Dict[str, int] = {}

    for k, val in (heroes_data or {}).items():
        if not isinstance(val, dict) or "id" not in val:
            continue
        hid = int(val["id"])
        npc = val.get("name") or f"npc_dota_hero_{hid}"
        slug = npc.replace("npc_dota_hero_", "")
        img_path = (val.get("img") or f"/apps/dota2/images/dota_react/heroes/{slug}.png").split("?")[0]
        icon_path = (val.get("icon") or f"/apps/dota2/images/dota_react/heroes/icons/{slug}.png").split("?")[0]
        if hid in HEROES_ZH:
            short_zh, alias, _ = HEROES_ZH[hid]
            full_zh = f"{short_zh}({alias})"
        else:
            short_zh = val.get("localized_name") or f"英雄#{hid}"
            alias = short_zh
            full_zh = short_zh

        by_id[hid] = {
            "id": hid,
            "npc": npc,
            "slug": slug,
            "short_zh": short_zh,
            "alias": alias,
            "full_zh": full_zh,
            "img": f"{VALVE_CDN}{img_path}",
            "icon": f"{VALVE_CDN}{icon_path}",
        }
        npc_to_id[npc] = hid

    # 补齐本地常量表里可能存在但未在缓存中的英雄
    for hid, (short_zh, alias, _) in HEROES_ZH.items():
        if hid not in by_id:
            by_id[hid] = {
                "id": hid,
                "npc": f"npc_dota_hero_{hid}",
                "slug": "",
                "short_zh": short_zh,
                "alias": alias,
                "full_zh": f"{short_zh}({alias})",
                "img": "",
                "icon": "",
            }

    return by_id, npc_to_id


def get_item_constants_map() -> Tuple[Dict[int, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """
    返回:
    1. item_id -> {"id": int, "key": str, "zh_name": str, "img": str, "cost": int}
    2. item_key -> {"id": int, "key": str, "zh_name": str, "img": str, "cost": int}
    """
    cache_file = CACHE_DIR / "items_constants.json"
    tmp_cache_file = TMP_CACHE_DIR / "items_constants.json"
    items_data = None
    for cf in (cache_file, tmp_cache_file):
        if cf.exists():
            try:
                items_data = json.loads(cf.read_text(encoding="utf-8"))
                break
            except Exception:
                items_data = None

    if not items_data:
        try:
            items_data = api_get("/constants/items", timeout=15)
            try:
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                cache_file.write_text(
                    json.dumps(items_data, ensure_ascii=False), encoding="utf-8"
                )
            except OSError:
                TMP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                tmp_cache_file.write_text(
                    json.dumps(items_data, ensure_ascii=False), encoding="utf-8"
                )
        except Exception:
            items_data = {}

    by_id: Dict[int, Dict[str, Any]] = {}
    by_key: Dict[str, Dict[str, Any]] = {}
    for key, val in (items_data or {}).items():
        if isinstance(val, dict) and "id" in val:
            item_id = int(val["id"])
            dname = val.get("dname") or key
            zh_name = ITEMS_ZH.get(key, dname)
            raw_img = (val.get("img") or f"/apps/dota2/images/dota_react/items/{key}.png").split("?")[0]
            img_url = f"{VALVE_CDN}{raw_img}" if raw_img.startswith("/") else raw_img
            cost = int(val.get("cost") or 0)
            info = {
                "id": item_id,
                "key": key,
                "zh_name": zh_name,
                "dname": dname,
                "img": img_url,
                "cost": cost,
            }
            by_id[item_id] = info
            by_key[key] = info
    return by_id, by_key


def format_duration(seconds: Optional[int]) -> str:
    if seconds is None:
        return "00:00"
    neg = seconds < 0
    s = abs(int(seconds))
    m, sec = divmod(s, 60)
    return f"{'-' if neg else ''}{m:02d}:{sec:02d}"


def infer_positions_1_to_5(team_players: List[Dict[str, Any]], is_parsed: bool) -> List[Dict[str, Any]]:
    """智能推断一方 5 名玩家的 1~5 号位"""
    pos_labels = {
        1: "1号位 · 优势路核心",
        2: "2号位 · 中路核心",
        3: "3号位 · 劣势路核心",
        4: "4号位 · 游走辅助",
        5: "5号位 · 纯辅助",
    }

    players = list(team_players)
    if len(players) != 5:
        for idx, p in enumerate(players, 1):
            p["inferred_pos"] = idx
            p["pos_label"] = pos_labels.get(idx, f"{idx}号位")
        return players

    max_nw = max((p.get("net_worth") or p.get("total_gold") or 1) for p in players) or 1
    max_lh = max((p.get("last_hits") or 1) for p in players) or 1

    if is_parsed and all(p.get("lane_role") in (1, 2, 3, 4) for p in players):
        def laning_farm_score(p: Dict[str, Any]) -> float:
            lh10 = (p.get("lh_t") or [0] * 11)[min(10, len(p.get("lh_t") or [0]) - 1)] if p.get("lh_t") else 0
            nw = p.get("net_worth") or 0
            lh = p.get("last_hits") or 0
            prior = get_hero_default_pos(p.get("hero_id", 0))
            return (lh10 * 150) + (nw * 0.4) + (lh * 35) - (prior * 1200)

        assigned: Dict[int, Dict[str, Any]] = {}
        remaining = list(players)

        mid_candidates = [p for p in remaining if p.get("lane_role") == 2 and not p.get("is_roaming")]
        if mid_candidates:
            mid_p = max(mid_candidates, key=laning_farm_score)
            assigned[2] = mid_p
            remaining.remove(mid_p)

        safe_candidates = [p for p in remaining if p.get("lane_role") == 1]
        if safe_candidates:
            safe_p = max(safe_candidates, key=laning_farm_score)
            assigned[1] = safe_p
            remaining.remove(safe_p)

        off_candidates = [p for p in remaining if p.get("lane_role") == 3]
        if off_candidates:
            off_p = max(off_candidates, key=laning_farm_score)
            assigned[3] = off_p
            remaining.remove(off_p)

        for core_pos in (1, 2, 3):
            if core_pos not in assigned and remaining:
                best_core = max(remaining, key=laning_farm_score)
                assigned[core_pos] = best_core
                remaining.remove(best_core)

        def support_4_score(p: Dict[str, Any]) -> float:
            nw = p.get("net_worth") or 0
            lh = p.get("last_hits") or 0
            sen = p.get("sen_placed") or 0
            prior = get_hero_default_pos(p.get("hero_id", 0))
            return nw + (lh * 40) - (sen * 250) - (prior * 800)

        remaining.sort(key=support_4_score, reverse=True)
        if len(remaining) >= 1:
            assigned[4] = remaining[0]
        if len(remaining) >= 2:
            assigned[5] = remaining[1]

        result = []
        for pos in range(1, 6):
            p = assigned[pos]
            p["inferred_pos"] = pos
            p["pos_label"] = pos_labels[pos]
            result.append(p)
        return result

    def unparsed_pos_score(p: Dict[str, Any]) -> float:
        prior = get_hero_default_pos(p.get("hero_id", 0))
        nw_ratio = (p.get("net_worth") or 0) / max_nw
        lh_ratio = (p.get("last_hits") or 0) / max_lh
        farm_index = 0.55 * nw_ratio + 0.45 * lh_ratio
        return 0.45 * prior + 0.55 * (5.0 - 4.0 * farm_index)

    sorted_by_role = sorted(players, key=unparsed_pos_score)
    cores = sorted_by_role[:3]
    supports = sorted_by_role[3:]

    assigned_unparsed: Dict[int, Dict[str, Any]] = {}
    rem_cores = list(cores)

    pos1 = min(
        rem_cores,
        key=lambda p: (
            abs(get_hero_default_pos(p.get("hero_id", 0)) - 1.0) * 1.5
            - ((p.get("last_hits") or 0) / max_lh)
            - ((p.get("net_worth") or 0) / max_nw)
        ),
    )
    assigned_unparsed[1] = pos1
    rem_cores.remove(pos1)

    pos3 = max(
        rem_cores,
        key=lambda p: (
            get_hero_default_pos(p.get("hero_id", 0)) * 1.5
            - ((p.get("xp_per_min") or 0) / 1000.0)
        ),
    )
    assigned_unparsed[3] = pos3
    rem_cores.remove(pos3)
    assigned_unparsed[2] = rem_cores[0]

    supports.sort(
        key=lambda p: (
            (p.get("net_worth") or 0) / max_nw
            + (p.get("last_hits") or 0) / max_lh
            - get_hero_default_pos(p.get("hero_id", 0)) * 0.25
        ),
        reverse=True,
    )
    assigned_unparsed[4] = supports[0]
    assigned_unparsed[5] = supports[1]

    result = []
    for pos in range(1, 6):
        p = assigned_unparsed[pos]
        p["inferred_pos"] = pos
        p["pos_label"] = pos_labels[pos]
        result.append(p)
    return result


def generate_player_tags(
    p: Dict[str, Any],
    team_kills: int,
    team_hero_dmg: int,
    team_tower_dmg: int,
    duration_min: float,
) -> List[str]:
    """生成克制、无AI表情包堆砌的战术速览标签"""
    tags: List[str] = []
    pos = p.get("inferred_pos", 3)
    kills = p.get("kills", 0)
    deaths = p.get("deaths", 0)
    assists = p.get("assists", 0)
    kp = (kills + assists) / max(1, team_kills)
    dmg_share = (p.get("hero_damage") or 0) / max(1, team_hero_dmg)
    tdmg = p.get("tower_damage") or 0
    gpm = p.get("gold_per_min") or 0
    obs = p.get("obs_placed")
    sen = p.get("sen_placed")
    stacked = p.get("camps_stacked")

    if dmg_share >= 0.30:
        tags.append(f"全队输出支柱 ({dmg_share*100:.0f}%)")
    elif pos in (1, 2) and dmg_share < 0.16 and duration_min > 20:
        tags.append(f"输出占比偏低 ({dmg_share*100:.0f}%)")

    if kp >= 0.70:
        tags.append(f"高参战率 ({kp*100:.0f}%)")
    elif pos in (1, 2, 3) and kp < 0.38 and duration_min > 20:
        if gpm >= 550:
            tags.append(f"单带刷钱为主 (参战{kp*100:.0f}%)")
        else:
            tags.append(f"低参战率 ({kp*100:.0f}%)")

    deaths_per_10m = deaths / max(1.0, duration_min / 10.0)
    if deaths <= 3 and duration_min >= 25:
        tags.append(f"极少阵亡 ({deaths}死)")
    elif pos in (1, 2) and deaths >= 8 and deaths_per_10m >= 2.1:
        tags.append(f"核心高频阵亡 ({deaths}死)")
    elif pos in (3, 4, 5) and deaths >= 10:
        tags.append(f"阵亡偏多 ({deaths}死)")

    if tdmg >= 6000 or (team_tower_dmg > 3000 and tdmg / max(1, team_tower_dmg) >= 0.45):
        tags.append(f"推进核心 (塔伤{tdmg:,})")
    elif pos == 1 and tdmg < 800 and duration_min > 25:
        tags.append("低建筑伤害")

    lh_t = p.get("lh_t")
    if lh_t and len(lh_t) > 10:
        lh10 = lh_t[10]
        if pos in (1, 2) and lh10 >= 58:
            tags.append(f"10m补刀优势 ({lh10}刀)")
        elif pos in (1, 2) and lh10 <= 38:
            tags.append(f"10m补刀受限 ({lh10}刀)")

    if obs is not None or sen is not None:
        total_wards = (obs or 0) + (sen or 0)
        if pos in (4, 5) and total_wards >= 20:
            tags.append(f"视野高产 ({obs or 0}假/{sen or 0}真)")
        elif pos == 5 and total_wards <= 6 and duration_min > 20:
            tags.append(f"视野偏少 ({obs or 0}假/{sen or 0}真)")
    if stacked and stacked >= 4:
        tags.append(f"囤野 {stacked} 波")

    bm = p.get("benchmarks") or {}
    gpm_pct = (bm.get("gold_per_min") or {}).get("pct")
    if gpm_pct and gpm_pct >= 0.85 and pos in (1, 2, 3):
        tags.append(f"GPM同英雄前{max(1, 100 - int(gpm_pct*100))}%")

    return tags


def extract_rich_items_and_abilities(
    p: Dict[str, Any],
    item_by_id: Dict[int, Dict[str, Any]],
    item_by_key: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """提取带 Valve CDN 图标、购买时间、主动使用次数的装备与技能详情"""
    purchase_log = p.get("purchase_log") or []
    item_uses = p.get("item_uses") or {}
    ability_uses = p.get("ability_uses") or {}

    # 记录每件物品最近一次或首次购买时间
    first_purchase_time: Dict[str, int] = {}
    last_purchase_time: Dict[str, int] = {}
    for entry in purchase_log:
        k = entry.get("key")
        t = entry.get("time")
        if k and isinstance(t, (int, float)):
            ti = int(t)
            if k not in first_purchase_time:
                first_purchase_time[k] = ti
            last_purchase_time[k] = ti

    final_items: List[str] = []
    final_items_rich: List[Dict[str, Any]] = []
    for idx, slot in enumerate(["item_0", "item_1", "item_2", "item_3", "item_4", "item_5"]):
        iid = p.get(slot) or 0
        if iid and iid in item_by_id:
            info = item_by_id[iid]
            key = info["key"]
            zh = info["zh_name"]
            final_items.append(zh)
            pt = last_purchase_time.get(key)
            final_items_rich.append({
                "slot": idx,
                "key": key,
                "zh_name": zh,
                "img": info["img"],
                "purchase_time_sec": pt,
                "purchase_time_str": format_duration(pt) if pt is not None else None,
                "use_count": item_uses.get(key, 0),
            })

    backpack_items_rich: List[Dict[str, Any]] = []
    for idx, slot in enumerate(["backpack_0", "backpack_1", "backpack_2"]):
        iid = p.get(slot) or 0
        if iid and iid in item_by_id:
            info = item_by_id[iid]
            key = info["key"]
            backpack_items_rich.append({
                "slot": idx,
                "key": key,
                "zh_name": info["zh_name"],
                "img": info["img"],
                "use_count": item_uses.get(key, 0),
            })

    neutral_item_rich = None
    neutral_id = p.get("item_neutral") or 0
    if neutral_id and neutral_id in item_by_id:
        info = item_by_id[neutral_id]
        key = info["key"]
        final_items.append(f"[中立]{info['zh_name']}")
        neutral_item_rich = {
            "key": key,
            "zh_name": info["zh_name"],
            "img": info["img"],
            "use_count": item_uses.get(key, 0),
        }

    has_scepter = bool(p.get("aghanims_scepter"))
    has_shard = bool(p.get("aghanims_shard"))
    for buff in p.get("permanent_buffs") or []:
        if buff.get("permanent_buff") == 2:
            has_scepter = True
        elif buff.get("permanent_buff") == 12:
            has_shard = True

    if has_scepter:
        final_items.append("[A杖加持]")
    if has_shard:
        final_items.append("[魔晶加持]")

    KEY_TIMING_ITEMS = {
        "blink", "overwhelming_blink", "swift_blink", "arcane_blink",
        "black_king_bar", "bfury", "maelstrom", "mjollnir", "gungir",
        "radiance", "desolator", "diffusal_blade", "disperser", "manta",
        "sange_and_yasha", "kaya_and_sange", "yasha_and_kaya",
        "hand_of_midas", "echo_sabre", "harpoon",
        "armlet", "invis_sword", "silver_edge", "orchid", "bloodthorn",
        "nullifier", "ethereal_blade", "octarine_core", "bloodstone",
        "aether_lens", "phylactery", "angels_demise", "spirit_vessel",
        "solar_crest", "pavise", "vladmir", "boots_of_bearing",
        "guardian_greaves", "mekansm", "pipe", "crimson_guard",
        "blade_mail", "shivas_guard", "assault", "heart", "satanic",
        "skadi", "butterfly", "greater_crit", "monkey_king_bar",
        "abyssal_blade", "basher", "aghanims_scepter", "ultimate_scepter",
        "aghanims_shard", "refresher", "sheepstick", "cyclone", "wind_waker",
        "force_staff", "hurricane_pike", "glimmer_cape", "aeon_disk", "lotus_orb",
        "mage_slayer", "eternal_shroud", "sphere", "helm_of_the_overlord",
        "witch_blade", "devastator", "revenants_brooch", "rapier",
        "arcane_boots", "phase_boots", "power_treads", "tranquil_boots", "travel_boots",
    }

    timings: List[str] = []
    timings_rich: List[Dict[str, Any]] = []
    seen_keys = set()
    for entry in purchase_log:
        key = entry.get("key")
        t = entry.get("time", 0)
        if key in KEY_TIMING_ITEMS and key not in seen_keys and t > 0:
            seen_keys.add(key)
            info = item_by_key.get(key) or {}
            zh = ITEMS_ZH.get(key) or info.get("zh_name") or key
            img_url = info.get("img") or f"{VALVE_CDN}/apps/dota2/images/dota_react/items/{key}.png"
            t_str = format_duration(t)
            timings.append(f"{t_str} {zh}")
            timings_rich.append({
                "time_sec": int(t),
                "time_str": t_str,
                "key": key,
                "zh_name": zh,
                "img": img_url,
                "use_count": item_uses.get(key, 0),
            })

    active_item_uses: Dict[str, Dict[str, Any]] = {}
    for k, cnt in sorted(item_uses.items(), key=lambda x: x[1], reverse=True):
        info = item_by_key.get(k) or {}
        zh = ITEMS_ZH.get(k) or info.get("zh_name") or k
        img_url = info.get("img") or f"{VALVE_CDN}/apps/dota2/images/dota_react/items/{k}.png"
        active_item_uses[k] = {
            "key": k,
            "zh_name": zh,
            "count": int(cnt),
            "img": img_url,
        }

    ability_uses_rich: List[Dict[str, Any]] = []
    for ak, cnt in sorted(ability_uses.items(), key=lambda x: x[1], reverse=True):
        zh = get_ability_zh(ak)
        if not zh:
            continue
        ability_uses_rich.append({
            "key": ak,
            "zh_name": zh,
            "count": int(cnt),
            "img": f"{VALVE_CDN}/apps/dota2/images/dota_react/abilities/{ak}.png",
        })

    return {
        "final_items": final_items,
        "final_items_rich": final_items_rich,
        "backpack_items_rich": backpack_items_rich,
        "neutral_item_rich": neutral_item_rich,
        "aghanims_scepter": has_scepter,
        "aghanims_shard": has_shard,
        "key_item_timings": timings,
        "key_item_timings_rich": timings_rich,
        "active_item_uses": active_item_uses,
        "ability_uses_rich": ability_uses_rich,
    }


def build_three_phases_breakdown(
    match: Dict[str, Any],
    all_formatted_players: List[Dict[str, Any]],
    raw_players_by_slot: Dict[int, Dict[str, Any]],
    hero_map: Dict[int, Dict[str, Any]],
    npc_to_id: Dict[str, int],
    item_by_key: Dict[str, Dict[str, Any]],
    focus_side: str,
) -> List[Dict[str, Any]]:
    """
    构建前期对线 (00:00–10:00)、中期运营 (10:00–25:00)、后期决策 (25:00–终局) 的精确差分账本
    """
    duration = int(match.get("duration") or 0)
    if duration <= 0:
        return []
    is_turbo = (match.get("game_mode") == 23)
    boundaries = (0, 300, 900, duration) if is_turbo else (0, 600, 1500, duration)
    phase_defs = [
        ("lane", "前期对线", boundaries[0], min(boundaries[1], duration)),
        ("mid", "中期运营", boundaries[1], min(boundaries[2], duration)),
        ("late", "后期决策", boundaries[2], duration),
    ]
    gold_adv = match.get("radiant_gold_adv") or []
    xp_adv = match.get("radiant_xp_adv") or []
    objectives = match.get("objectives") or []
    sign = 1 if focus_side == "radiant" else -1

    # 从所有人的 kills_log 反推每个人的英雄被杀时间点 (若原始数据无 deaths_log)
    inferred_deaths_by_npc: Dict[str, List[Dict[str, Any]]] = {}
    for slot, rp in raw_players_by_slot.items():
        killer_hid = rp.get("hero_id", 0)
        killer_hinfo = hero_map.get(killer_hid, {})
        killer_short = killer_hinfo.get("short_zh", f"英雄#{killer_hid}")
        for ke in rp.get("kills_log") or []:
            victim_npc = ke.get("key", "")
            t = ke.get("time")
            if victim_npc.startswith("npc_dota_hero_") and isinstance(t, (int, float)):
                inferred_deaths_by_npc.setdefault(victim_npc, []).append({
                    "time": int(t),
                    "time_str": format_duration(int(t)),
                    "killer": killer_short,
                    "killer_hero_id": killer_hid,
                })

    def sample_series(rp: Dict[str, Any], field: str, sec: int, is_final: bool, terminal_field: Optional[str] = None) -> Optional[int]:
        if is_final and terminal_field and isinstance(rp.get(terminal_field), (int, float)):
            return int(rp[terminal_field])
        arr = rp.get(field)
        if not isinstance(arr, list) or not arr:
            return None
        idx = min(max(0, sec // 60), len(arr) - 1)
        val = arr[idx]
        return int(val) if isinstance(val, (int, float)) else None

    phases_out = []
    for key, label, start_s, end_s in phase_defs:
        if start_s >= duration:
            continue
        is_final = (end_s == duration)
        start_m = start_s // 60
        end_m = min(end_s // 60, max(0, len(gold_adv) - 1)) if gold_adv else 0

        inc_start = sign * int(gold_adv[start_m]) if gold_adv and start_m < len(gold_adv) else None
        inc_end = sign * int(gold_adv[end_m]) if gold_adv and end_m < len(gold_adv) else None
        inc_delta = (inc_end - inc_start) if (inc_start is not None and inc_end is not None) else None

        xp_start = sign * int(xp_adv[start_m]) if xp_adv and start_m < len(xp_adv) else None
        xp_end = sign * int(xp_adv[end_m]) if xp_adv and end_m < len(xp_adv) else None
        xp_delta = (xp_end - xp_start) if (xp_start is not None and xp_end is not None) else None

        # 统计阶段内推塔与肉山
        towers_for = 0
        towers_against = 0
        rosh_for = 0
        rosh_against = 0
        phase_events = []
        for obj in objectives:
            t = obj.get("time")
            if not isinstance(t, (int, float)):
                continue
            ti = int(t)
            if not (start_s <= ti < end_s or (is_final and ti == end_s)):
                continue
            otype = obj.get("type", "")
            if otype == "CHAT_MESSAGE_ROSHAN_KILL":
                r_side = "radiant" if obj.get("team") == 2 else "dire"
                if r_side == focus_side:
                    rosh_for += 1
                else:
                    rosh_against += 1
                phase_events.append({
                    "time": ti,
                    "time_str": format_duration(ti),
                    "kind": "roshan",
                    "text": f"{'我方' if r_side == focus_side else '对方'}击杀肉山",
                })
            elif otype == "building_kill":
                bkey = str(obj.get("key") or "")
                # goodguys 建筑被毁代表 dire 拆塔
                destroyed_side = "radiant" if "goodguys" in bkey else ("dire" if "badguys" in bkey else "")
                if destroyed_side:
                    if destroyed_side != focus_side:
                        towers_for += 1
                    else:
                        towers_against += 1

        phase_players = []
        elapsed_min = max(1.0, (end_s - start_s) / 60.0)
        for fp in all_formatted_players:
            slot = fp["player_slot"]
            rp = raw_players_by_slot.get(slot, {})
            hid = fp["hero_id"]
            h_npc = hero_map.get(hid, {}).get("npc", "")

            g0 = sample_series(rp, "gold_t", start_s, False)
            g1 = sample_series(rp, "gold_t", end_s, is_final)
            nw0 = sample_series(rp, "networth_t", start_s, False)
            nw1 = sample_series(rp, "networth_t", end_s, is_final, "net_worth")
            lh0 = sample_series(rp, "lh_t", start_s, False)
            lh1 = sample_series(rp, "lh_t", end_s, is_final, "last_hits")
            dn0 = sample_series(rp, "dn_t", start_s, False)
            dn1 = sample_series(rp, "dn_t", end_s, is_final, "denies")
            hd0 = sample_series(rp, "hero_damage_t", start_s, False)
            hd1 = sample_series(rp, "hero_damage_t", end_s, is_final, "hero_damage")
            td0 = sample_series(rp, "tower_damage_t", start_s, False)
            td1 = sample_series(rp, "tower_damage_t", end_s, is_final, "tower_damage")

            gold_gain = max(0, g1 - g0) if (g0 is not None and g1 is not None) else None
            lh_gain = max(0, lh1 - lh0) if (lh0 is not None and lh1 is not None) else None
            dn_gain = max(0, dn1 - dn0) if (dn0 is not None and dn1 is not None) else None
            hd_gain = max(0, hd1 - hd0) if (hd0 is not None and hd1 is not None) else None
            td_gain = max(0, td1 - td0) if (td0 is not None and td1 is not None) else None
            gpm_phase = round(gold_gain / elapsed_min, 1) if gold_gain is not None else None

            # 阶段内击杀
            kills_in_phase = []
            for ke in rp.get("kills_log") or []:
                kt = ke.get("time")
                v_npc = str(ke.get("key") or "")
                if isinstance(kt, (int, float)) and v_npc.startswith("npc_dota_hero_"):
                    kti = int(kt)
                    if start_s <= kti < end_s or (is_final and kti == end_s):
                        vhid = npc_to_id.get(v_npc, 0)
                        vshort = hero_map.get(vhid, {}).get("short_zh", v_npc.replace("npc_dota_hero_", ""))
                        kills_in_phase.append({
                            "time": kti,
                            "time_str": format_duration(kti),
                            "victim_hero": vshort,
                        })

            # 阶段内阵亡 (优先使用 deaths_log，否则使用从全员 kills_log 反推的记录)
            deaths_in_phase = []
            raw_dlog = rp.get("deaths_log")
            if isinstance(raw_dlog, list):
                for de in raw_dlog:
                    dt_val = de.get("time")
                    if isinstance(dt_val, (int, float)):
                        dti = int(dt_val)
                        if start_s <= dti < end_s or (is_final and dti == end_s):
                            k_npc = str(de.get("key") or "")
                            khid = npc_to_id.get(k_npc, 0)
                            kshort = hero_map.get(khid, {}).get("short_zh") or k_npc.replace("npc_dota_hero_", "")
                            deaths_in_phase.append({
                                "time": dti,
                                "time_str": format_duration(dti),
                                "killer": kshort,
                                "gold_lost": de.get("gold_lost"),
                                "time_dead": de.get("time_dead"),
                            })
            else:
                for de in inferred_deaths_by_npc.get(h_npc, []):
                    dti = de["time"]
                    if start_s <= dti < end_s or (is_final and dti == end_s):
                        deaths_in_phase.append(de)

            # 阶段内出装 (价格 >= 900 或关键鞋类/保命装)
            items_in_phase = []
            for pe in rp.get("purchase_log") or []:
                pt = pe.get("time")
                ikey = pe.get("key")
                if isinstance(pt, (int, float)) and ikey:
                    pti = int(pt)
                    if start_s <= pti < end_s or (is_final and pti == end_s):
                        info = item_by_key.get(ikey) or {}
                        cost = info.get("cost", 0)
                        if cost >= 900 or ikey in ("boots", "magic_wand", "dust", "smoke_of_deceit", "aghanims_shard"):
                            items_in_phase.append({
                                "time": pti,
                                "time_str": format_duration(pti),
                                "key": ikey,
                                "zh_name": ITEMS_ZH.get(ikey) or info.get("zh_name") or ikey,
                                "img": info.get("img") or f"{VALVE_CDN}/apps/dota2/images/dota_react/items/{ikey}.png",
                            })

            obs_cnt = sum(
                1 for e in (rp.get("obs_log") or [])
                if isinstance(e.get("time"), (int, float)) and (start_s <= int(e["time"]) < end_s or (is_final and int(e["time"]) == end_s))
            )
            sen_cnt = sum(
                1 for e in (rp.get("sen_log") or [])
                if isinstance(e.get("time"), (int, float)) and (start_s <= int(e["time"]) < end_s or (is_final and int(e["time"]) == end_s))
            )
            bb_cnt = sum(
                1 for e in (rp.get("buyback_log") or [])
                if isinstance(e.get("time"), (int, float)) and (start_s <= int(e["time"]) < end_s or (is_final and int(e["time"]) == end_s))
            )

            phase_players.append({
                "slot": slot,
                "side": "radiant" if slot < 128 else "dire",
                "pos": fp["pos"],
                "personaname": fp["personaname"],
                "hero_id": hid,
                "hero_short_zh": fp["hero_short_zh"],
                "hero_img": fp["hero_img"],
                "hero_icon": fp["hero_icon"],
                "gold_gain": gold_gain,
                "gpm_phase": gpm_phase,
                "net_worth_start": nw0,
                "net_worth_end": nw1,
                "lh_gain": lh_gain,
                "dn_gain": dn_gain,
                "hero_damage_gain": hd_gain,
                "tower_damage_gain": td_gain,
                "kills_count": len(kills_in_phase),
                "deaths_count": len(deaths_in_phase),
                "kills_events": kills_in_phase,
                "deaths_events": deaths_in_phase,
                "obs_placed": obs_cnt,
                "sen_placed": sen_cnt,
                "buybacks": bb_cnt,
                "items_bought": items_in_phase,
            })

        phases_out.append({
            "key": key,
            "label": label,
            "time_label": f"{format_duration(start_s)}–{format_duration(end_s)}",
            "start_sec": start_s,
            "end_sec": end_s,
            "team_summary": {
                "income_diff_start": inc_start,
                "income_diff_end": inc_end,
                "income_diff_change": inc_delta,
                "xp_diff_start": xp_start,
                "xp_diff_end": xp_end,
                "xp_diff_change": xp_delta,
                "towers_taken": towers_for,
                "towers_lost": towers_against,
                "roshan_taken": rosh_for,
                "roshan_lost": rosh_against,
            },
            "events": phase_events,
            "players": phase_players,
        })

    return phases_out


def load_cached_grok_coaching(match_id: int, side: str) -> Optional[Dict[str, Any]]:
    """读取已缓存的 Grok 结构化教练复盘 JSON (若存在)"""
    candidates = [
        REPORTS_DIR / f"coaching-{match_id}-{side}.json",
        REPORTS_DIR / f"coaching-{match_id}-dire.json",
        REPORTS_DIR / f"coaching-{match_id}-radiant.json",
    ]
    for path in candidates:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
    return None


def analyze_match_data(
    match: Dict[str, Any],
    roster: Dict[str, Any],
    focus_account_id: Optional[int] = None,
) -> Dict[str, Any]:
    """将 OpenDota 原始 match JSON 转化为录像级深度分析报告"""
    hero_map, npc_to_id = get_hero_constants_map()
    item_by_id, item_by_key = get_item_constants_map()

    match_id = match.get("match_id")
    duration = match.get("duration") or 0
    duration_min = max(1.0, duration / 60.0)
    radiant_win = bool(match.get("radiant_win"))
    radiant_score = match.get("radiant_score") or 0
    dire_score = match.get("dire_score") or 0
    start_time = match.get("start_time") or 0
    start_dt = (
        datetime.datetime.fromtimestamp(start_time).strftime("%Y-%m-%d %H:%M")
        if start_time
        else "未知时间"
    )
    is_parsed = bool(match.get("version"))

    players = match.get("players") or []
    raw_players_by_slot = {int(p.get("player_slot", 0)): p for p in players if isinstance(p, dict)}
    radiant_raw = [p for p in players if p.get("isRadiant") or (p.get("player_slot", 0) < 128)]
    dire_raw = [p for p in players if not (p.get("isRadiant") or (p.get("player_slot", 0) < 128))]

    main_id = focus_account_id or roster.get("main_account_id")
    roster_players = roster.get("players") or {}

    focus_party_ids = set()
    user_team_side = None
    for p in players:
        aid = p.get("account_id")
        is_rad = p.get("isRadiant") or (p.get("player_slot", 0) < 128)
        if aid and (aid == main_id or str(aid) in roster_players):
            if p.get("party_id") is not None and (p.get("party_size") or 1) > 1:
                focus_party_ids.add(p.get("party_id"))
            if aid == main_id:
                user_team_side = "radiant" if is_rad else "dire"
            elif user_team_side is None:
                user_team_side = "radiant" if is_rad else "dire"

    focus_side_resolved = user_team_side or ("radiant" if radiant_win else "dire")

    radiant_sorted = infer_positions_1_to_5(radiant_raw, is_parsed)
    dire_sorted = infer_positions_1_to_5(dire_raw, is_parsed)

    # 收集全图真假眼坐标与对线期走位热力点
    all_wards_map: List[Dict[str, Any]] = []
    all_lane_heatmaps: List[Dict[str, Any]] = []

    def format_team_players(team_list: List[Dict[str, Any]], side_key: str) -> List[Dict[str, Any]]:
        team_kills = sum(p.get("kills", 0) for p in team_list)
        team_dmg = sum(p.get("hero_damage") or 0 for p in team_list)
        team_tdmg = sum(p.get("tower_damage") or 0 for p in team_list)
        out = []
        for p in team_list:
            slot = int(p.get("player_slot", 0))
            aid = p.get("account_id")
            persona = p.get("personaname") or "匿名玩家"
            friend_tag = None
            is_me = False
            if aid and aid == roster.get("main_account_id"):
                friend_tag = f"我 · {roster.get('main_name', persona)}"
                is_me = True
            elif aid and str(aid) in roster_players:
                friend_tag = f"车队好友 · {roster_players[str(aid)].get('name')}"
            elif aid and focus_account_id and aid == focus_account_id:
                friend_tag = "当前视角"
                is_me = True
            elif p.get("party_id") is not None and p.get("party_id") in focus_party_ids:
                friend_tag = "同车队队友"
            elif (p.get("party_size") or 1) > 1:
                friend_tag = f"{p.get('party_size')}人黑"

            hid = int(p.get("hero_id") or 0)
            hinfo = hero_map.get(hid) or {
                "short_zh": get_hero_name(hid),
                "alias": "",
                "full_zh": get_hero_name(hid),
                "img": "",
                "icon": "",
            }

            rich_assets = extract_rich_items_and_abilities(p, item_by_id, item_by_key)
            tags = generate_player_tags(p, team_kills, team_dmg, team_tdmg, duration_min)

            lh10 = p["lh_t"][10] if p.get("lh_t") and len(p["lh_t"]) > 10 else None
            dn10 = p["dn_t"][10] if p.get("dn_t") and len(p["dn_t"]) > 10 else None
            gold10 = p["gold_t"][10] if p.get("gold_t") and len(p["gold_t"]) > 10 else None
            xp10 = p["xp_t"][10] if p.get("xp_t") and len(p["xp_t"]) > 10 else None

            bm = p.get("benchmarks") or {}
            bm_summary = {}
            raw_bm = {}
            for k, label in [
                ("gold_per_min", "GPM同英雄分位"),
                ("xp_per_min", "XPM同英雄分位"),
                ("hero_damage_per_min", "分均伤害分位"),
                ("kills_per_min", "分均击杀分位"),
                ("last_hits_per_min", "分均补刀分位"),
                ("tower_damage", "推塔分位"),
            ]:
                if k in bm and bm[k].get("pct") is not None:
                    raw_bm[k] = float(bm[k]["pct"])
                    bm_summary[label] = f"超越 {bm[k]['pct']*100:.0f}% 同英雄"

            kills = p.get("kills", 0)
            deaths = p.get("deaths", 0)
            assists = p.get("assists", 0)
            kp = (kills + assists) / max(1, team_kills) * 100.0
            dmg_pct = (p.get("hero_damage") or 0) / max(1, team_dmg) * 100.0

            purchase_counts = p.get("purchase") or {}
            smokes_bought = purchase_counts.get("smoke_of_deceit", 0)
            dusts_bought = purchase_counts.get("dust", 0)

            # 解析承受伤害、读秒时长、阵亡扣钱、被谁提款与击杀了谁
            dmg_taken_dict = p.get("damage_taken") or {}
            total_dmg_taken = sum(int(v) for v in dmg_taken_dict.values() if isinstance(v, (int, float)))
            hero_dmg_taken = sum(
                int(v) for k, v in dmg_taken_dict.items()
                if str(k).startswith("npc_dota_hero_") and isinstance(v, (int, float))
            )

            dead_seconds = int(p.get("life_state_dead") or 0)
            gold_reasons = p.get("gold_reasons") or {}
            death_gold_lost = abs(int(gold_reasons.get("1") or 0))
            buybacks = int(p.get("buyback_count") or len(p.get("buyback_log") or []))

            killed_by_raw = p.get("killed_by") or {}
            kb_heroes = []
            neutral_deaths = 0
            tower_deaths = 0
            fountain_deaths = 0
            for k_unit, cnt in sorted(killed_by_raw.items(), key=lambda x: x[1], reverse=True):
                c_int = int(cnt)
                if k_unit.startswith("npc_dota_hero_"):
                    khid = npc_to_id.get(k_unit, 0)
                    khinfo = hero_map.get(khid, {})
                    kb_heroes.append({
                        "hero_id": khid,
                        "hero_short_zh": khinfo.get("short_zh") or k_unit.replace("npc_dota_hero_", ""),
                        "hero_icon": khinfo.get("icon") or "",
                        "count": c_int,
                    })
                elif "neutral" in k_unit:
                    neutral_deaths += c_int
                elif "tower" in k_unit:
                    tower_deaths += c_int
                elif "fountain" in k_unit:
                    fountain_deaths += c_int

            killed_raw = p.get("killed") or {}
            k_heroes = []
            for v_unit, cnt in sorted(killed_raw.items(), key=lambda x: x[1], reverse=True):
                if v_unit.startswith("npc_dota_hero_"):
                    vhid = npc_to_id.get(v_unit, 0)
                    vhinfo = hero_map.get(vhid, {})
                    k_heroes.append({
                        "hero_id": vhid,
                        "hero_short_zh": vhinfo.get("short_zh") or v_unit.replace("npc_dota_hero_", ""),
                        "hero_icon": vhinfo.get("icon") or "",
                        "count": int(cnt),
                    })
            obs_destroyed = int(killed_raw.get("npc_dota_observer_wards") or p.get("observer_kills") or 0)
            sen_destroyed = int(killed_raw.get("npc_dota_sentry_wards") or p.get("sentry_kills") or 0)

            # 提取眼位坐标 (x, y in [64, 192] -> nx, ny in [0, 100])
            for wtype, wlog in [("obs", p.get("obs_log") or []), ("sen", p.get("sen_log") or [])]:
                for we in wlog:
                    wx = we.get("x")
                    wy = we.get("y")
                    wt = we.get("time", 0)
                    if isinstance(wx, (int, float)) and isinstance(wy, (int, float)):
                        nx = round(max(2.0, min(98.0, (float(wx) - 64.0) / 128.0 * 100.0)), 1)
                        ny = round(max(2.0, min(98.0, (1.0 - (float(wy) - 64.0) / 128.0) * 100.0)), 1)
                        all_wards_map.append({
                            "side": side_key,
                            "type": wtype,
                            "pos": p.get("inferred_pos"),
                            "personaname": persona,
                            "hero_short_zh": hinfo["short_zh"],
                            "hero_icon": hinfo["icon"],
                            "time_sec": int(wt),
                            "time_str": format_duration(int(wt)),
                            "x": round(float(wx), 1),
                            "y": round(float(wy), 1),
                            "nx": nx,
                            "ny": ny,
                        })

            # 提取对线期走位热力点
            lane_pos = p.get("lane_pos") or {}
            if isinstance(lane_pos, dict):
                for lx_str, y_dict in lane_pos.items():
                    if not isinstance(y_dict, dict):
                        continue
                    try:
                        lx = float(lx_str)
                    except Exception:
                        continue
                    for ly_str, weight in y_dict.items():
                        try:
                            ly = float(ly_str)
                            w_val = int(weight)
                        except Exception:
                            continue
                        if w_val >= 2:
                            nx = round(max(2.0, min(98.0, (lx - 64.0) / 128.0 * 100.0)), 1)
                            ny = round(max(2.0, min(98.0, (1.0 - (ly - 64.0) / 128.0) * 100.0)), 1)
                            all_lane_heatmaps.append({
                                "side": side_key,
                                "pos": p.get("inferred_pos"),
                                "personaname": persona,
                                "hero_short_zh": hinfo["short_zh"],
                                "nx": nx,
                                "ny": ny,
                                "weight": w_val,
                            })

            out.append({
                "player_slot": slot,
                "side": side_key,
                "pos": p.get("inferred_pos"),
                "pos_label": p.get("pos_label"),
                "account_id": aid,
                "personaname": persona,
                "friend_tag": friend_tag,
                "is_me": is_me,
                "rank": get_rank_name(p.get("rank_tier")),
                "hero_id": hid,
                "hero_name": hinfo["full_zh"],
                "hero_short_zh": hinfo["short_zh"],
                "hero_alias": hinfo["alias"],
                "hero_img": hinfo["img"],
                "hero_icon": hinfo["icon"],
                "raw_lane": p.get("lane"),
                "lane_role": LANE_ROLE_ZH.get(p.get("lane_role"), "未知分路") if is_parsed else "按经济推断",
                "lane_efficiency_pct": p.get("lane_efficiency_pct"),
                "kda": f"{kills}/{deaths}/{assists}",
                "kills": kills,
                "deaths": deaths,
                "assists": assists,
                "kill_participation_pct": round(kp, 1),
                "net_worth": p.get("net_worth") or p.get("total_gold") or 0,
                "gpm": p.get("gold_per_min") or 0,
                "xpm": p.get("xp_per_min") or 0,
                "last_hits": p.get("last_hits") or 0,
                "denies": p.get("denies") or 0,
                "hero_damage": p.get("hero_damage") or 0,
                "hero_damage_share_pct": round(dmg_pct, 1),
                "damage_taken": total_dmg_taken,
                "hero_damage_taken": hero_dmg_taken,
                "tower_damage": p.get("tower_damage") or 0,
                "hero_healing": p.get("hero_healing") or 0,
                "stuns_sec": round(float(p.get("stuns") or 0), 1),
                "obs_placed": p.get("obs_placed"),
                "sen_placed": p.get("sen_placed"),
                "obs_destroyed": obs_destroyed,
                "sen_destroyed": sen_destroyed,
                "camps_stacked": p.get("camps_stacked"),
                "smokes_bought": smokes_bought,
                "dusts_bought": dusts_bought,
                "apm": p.get("actions_per_min") or 0,
                "pings": p.get("pings") or 0,
                "dead_seconds": dead_seconds,
                "death_gold_lost": death_gold_lost,
                "buybacks": buybacks,
                "networth_t": p.get("networth_t") or p.get("gold_t") or [],
                "lh_t": p.get("lh_t") or [],
                "killed_by_breakdown": {
                    "heroes": kb_heroes,
                    "neutral_deaths": neutral_deaths,
                    "tower_deaths": tower_deaths,
                    "fountain_deaths": fountain_deaths,
                },
                "kills_breakdown": {
                    "heroes": k_heroes,
                    "obs_destroyed": obs_destroyed,
                    "sen_destroyed": sen_destroyed,
                },
                "laning_10m": {
                    "lh10": lh10,
                    "dn10": dn10,
                    "gold10": gold10,
                    "xp10": xp10,
                },
                **rich_assets,
                "benchmarks": bm_summary,
                "raw_benchmarks": raw_bm,
                "tags": tags,
            })
        return out

    radiant_report = format_team_players(radiant_sorted, "radiant")
    dire_report = format_team_players(dire_sorted, "dire")

    is_turbo = (match.get("game_mode") == 23)
    for rp in radiant_report:
        eval_res = evaluate_player_deeply(
            rp, radiant_report, dire_report, radiant_win, duration_min, is_parsed, is_turbo
        )
        rp.update(eval_res)
    for dp in dire_report:
        eval_res = evaluate_player_deeply(
            dp, dire_report, radiant_report, not radiant_win, duration_min, is_parsed, is_turbo
        )
        dp.update(eval_res)

    assign_team_blame_percentages(radiant_report)
    assign_team_blame_percentages(dire_report)

    # 经济走势与转折点分析
    gold_adv = match.get("radiant_gold_adv") or []
    xp_adv = match.get("radiant_xp_adv") or []
    economy_timeline = {}
    if gold_adv:
        max_rad_adv = max(gold_adv)
        max_rad_min = gold_adv.index(max_rad_adv)
        max_dire_adv = min(gold_adv)
        max_dire_min = gold_adv.index(max_dire_adv)

        checkpoints = {}
        for m in [10, 15, 20, 25, 30, 35, 40, 45, 50]:
            if m < len(gold_adv):
                val = gold_adv[m]
                leader = "天辉" if val >= 0 else "夜魇"
                checkpoints[f"{m}分钟"] = f"{leader} +{abs(val):,}"

        is_comeback = (radiant_win and max_dire_adv <= -5000) or (not radiant_win and max_rad_adv >= 5000)
        economy_timeline = {
            "radiant_max_lead": f"{max_rad_min}分钟 天辉最高 +{max_rad_adv:,} 金" if max_rad_adv > 0 else "天辉全场未曾领先",
            "dire_max_lead": f"{max_dire_min}分钟 夜魇最高 +{abs(max_dire_adv):,} 金" if max_dire_adv < 0 else "夜魇全场未曾领先",
            "is_comeback": is_comeback,
            "checkpoints": checkpoints,
        }

    # 关键团战提取与参与者明细
    teamfights_raw = match.get("teamfights") or []
    key_teamfights = []
    if teamfights_raw:
        scored_tfs = []
        for tf in teamfights_raw:
            start_s = tf.get("start", 0)
            end_s = tf.get("end", 0)
            tf_players = tf.get("players") or []
            rad_deaths = sum(tp.get("deaths", 0) for tp in tf_players[:5])
            dire_deaths = sum(tp.get("deaths", 0) for tp in tf_players[5:10])
            rad_gold_delta = sum(tp.get("gold_delta", 0) for tp in tf_players[:5])
            dire_gold_delta = sum(tp.get("gold_delta", 0) for tp in tf_players[5:10])
            net_swing = rad_gold_delta - dire_gold_delta
            total_deaths = rad_deaths + dire_deaths
            if total_deaths >= 2 or abs(net_swing) >= 1500:
                top_dmg_idx = max(range(min(10, len(tf_players))), key=lambda i: tf_players[i].get("damage", 0))
                top_dmg_val = tf_players[top_dmg_idx].get("damage", 0)
                top_hid = players[top_dmg_idx].get("hero_id", 0) if top_dmg_idx < len(players) else 0
                top_hero = hero_map.get(top_hid, {}).get("short_zh") or get_hero_name(top_hid)

                participants_detail = []
                for idx_p, tp in enumerate(tf_players[:10]):
                    if idx_p >= len(players):
                        continue
                    raw_p = players[idx_p]
                    phid = raw_p.get("hero_id", 0)
                    phinfo = hero_map.get(phid, {})
                    dmg_v = int(tp.get("damage") or 0)
                    d_v = int(tp.get("deaths") or 0)
                    g_v = int(tp.get("gold_delta") or 0)
                    ab_used = [
                        f"{get_ability_zh(ak)}×{cnt}"
                        for ak, cnt in (tp.get("ability_uses") or {}).items()
                        if get_ability_zh(ak)
                    ]
                    it_used = [
                        f"{ITEMS_ZH.get(ik, ik)}×{cnt}"
                        for ik, cnt in (tp.get("item_uses") or {}).items()
                    ]
                    if dmg_v > 0 or d_v > 0 or ab_used:
                        participants_detail.append({
                            "side": "radiant" if idx_p < 5 else "dire",
                            "personaname": raw_p.get("personaname") or "匿名",
                            "hero_short_zh": phinfo.get("short_zh") or f"英雄#{phid}",
                            "hero_icon": phinfo.get("icon") or "",
                            "damage": dmg_v,
                            "deaths": d_v,
                            "gold_delta": g_v,
                            "abilities": ab_used[:4],
                            "items": it_used[:4],
                        })

                scored_tfs.append({
                    "importance": total_deaths * 600 + abs(net_swing),
                    "start_sec": start_s,
                    "end_sec": end_s,
                    "minute": round(start_s / 60.0, 1),
                    "time_range": f"{format_duration(start_s)}–{format_duration(end_s)}",
                    "rad_deaths": rad_deaths,
                    "dire_deaths": dire_deaths,
                    "net_swing_radiant": net_swing,
                    "kills_trade": f"天辉阵亡 {rad_deaths} : 夜魇阵亡 {dire_deaths}",
                    "gold_swing": f"{'天辉' if net_swing >= 0 else '夜魇'}经济 +{abs(net_swing):,}",
                    "top_damage_hero": f"{top_hero} ({top_dmg_val:,} 伤害)",
                    "participants": participants_detail,
                })
        scored_tfs.sort(key=lambda x: x["importance"], reverse=True)
        key_teamfights = sorted(scored_tfs[:6], key=lambda x: x["start_sec"])

    # 提取关键建筑与肉山事件标记用于绘制在经济曲线上
    objective_markers = []
    for obj in match.get("objectives") or []:
        t = obj.get("time")
        if not isinstance(t, (int, float)) or t < 0:
            continue
        ti = int(t)
        otype = obj.get("type", "")
        if otype == "CHAT_MESSAGE_ROSHAN_KILL":
            r_side = "radiant" if obj.get("team") == 2 else "dire"
            objective_markers.append({
                "time_sec": ti,
                "minute": round(ti / 60.0, 1),
                "time_str": format_duration(ti),
                "type": "roshan",
                "side": r_side,
                "label": f"{'天辉' if r_side == 'radiant' else '夜魇'}击杀肉山",
            })
        elif otype == "building_kill" and ("rax" in str(obj.get("key", "")) or "tower3" in str(obj.get("key", ""))):
            bkey = str(obj.get("key") or "")
            attacker_side = "dire" if "goodguys" in bkey else "radiant"
            btype_zh = "高地兵营" if "rax" in bkey else "高地三塔"
            objective_markers.append({
                "time_sec": ti,
                "minute": round(ti / 60.0, 1),
                "time_str": format_duration(ti),
                "type": "barracks",
                "side": attacker_side,
                "label": f"{'天辉' if attacker_side == 'radiant' else '夜魇'}攻破{btype_zh}",
            })

    mvp_and_culprit = select_match_mvp_and_culprit(
        radiant_report, dire_report, radiant_win, user_team_side
    )
    match_narrative = build_four_stage_narrative(
        match, radiant_report, dire_report, economy_timeline, key_teamfights, user_team_side
    )

    phases_data = build_three_phases_breakdown(
        match=match,
        all_formatted_players=radiant_report + dire_report,
        raw_players_by_slot=raw_players_by_slot,
        hero_map=hero_map,
        npc_to_id=npc_to_id,
        item_by_key=item_by_key,
        focus_side=focus_side_resolved,
    )

    grok_coaching = load_cached_grok_coaching(match_id, focus_side_resolved)

    from draft_and_phase_coach import (
        build_deep_replay_forensics,
        build_draft_and_combo_analysis,
        enrich_phases_with_evaluations,
    )

    deep_forensics = build_deep_replay_forensics(
        match=match,
        radiant_players=radiant_report,
        dire_players=dire_report,
        hero_const_by_id=hero_map,
        npc_to_hid=npc_to_id,
    )

    phases_data = enrich_phases_with_evaluations(
        phases_data=phases_data,
        all_formatted_players=radiant_report + dire_report,
        grok_coaching=grok_coaching,
    )

    draft_analysis_by_side = build_draft_and_combo_analysis(
        radiant_players=radiant_report,
        dire_players=dire_report,
        match=match,
        focus_side=focus_side_resolved,
    )
    draft_analysis = draft_analysis_by_side.get(
        focus_side_resolved, draft_analysis_by_side.get("dire")
    )

    all_wards_map.sort(key=lambda w: w["time_sec"])

    return {
        "match_id": match_id,
        "mode_str": get_mode_and_lobby(match.get("game_mode", 0), match.get("lobby_type", 0)),
        "start_time_str": start_dt,
        "duration_str": format_duration(duration),
        "duration_min": round(duration_min, 1),
        "is_parsed": is_parsed,
        "winner": "天辉 (Radiant)" if radiant_win else "夜魇 (Dire)",
        "radiant_win": radiant_win,
        "radiant_score": radiant_score,
        "dire_score": dire_score,
        "score": f"天辉 {radiant_score} : {dire_score} 夜魇",
        "user_team_side": user_team_side,
        "focus_side": focus_side_resolved,
        "user_won": (
            (radiant_win if user_team_side == "radiant" else not radiant_win)
            if user_team_side is not None
            else None
        ),
        "radiant_gold_adv": gold_adv,
        "radiant_xp_adv": xp_adv,
        "objective_markers": objective_markers,
        "vision_and_map_data": {
            "wards": all_wards_map,
            "lane_heatmaps": all_lane_heatmaps,
        },
        "economy_timeline": economy_timeline,
        "key_teamfights": key_teamfights,
        "draft_analysis": draft_analysis,
        "draft_analysis_by_side": draft_analysis_by_side,
        "deep_forensics": deep_forensics,
        "phases_data": phases_data,
        "grok_coaching": grok_coaching,
        "mvp": mvp_and_culprit,
        "match_narrative": match_narrative,
        "radiant_pos_1_to_5": radiant_report,
        "dire_pos_1_to_5": dire_report,
    }


def render_markdown_report(report: Dict[str, Any]) -> str:
    """将结构化报告渲染为无废话的复盘账本 Markdown"""
    lines: List[str] = []
    mid = report["match_id"]
    lines.append(f"# Dota 2 赛后复盘账本 (Match `{mid}`)")
    lines.append("")
    user_status = ""
    if report["user_won"] is True:
        user_status = " | 本方获胜 (WIN)"
    elif report["user_won"] is False:
        user_status = " | 本方落败 (LOSS)"

    parse_badge = (
        "已解析录像 (含分路/10分钟对线/出装时间点/主动按键/眼位坐标/团战窗口)"
        if report["is_parsed"]
        else "基础统计模式 (可请求 OpenDota 解析录像补齐分钟级曲线与事件)"
    )

    lines.append(
        f"- **模式与时间**: {report.get('mode_str', '未知模式')} | {report['start_time_str']} | 时长 {report['duration_str']} ({report['duration_min']} 分钟)"
    )
    lines.append(f"- **比分与结果**: {report['score']} — 胜方：{report['winner']}{user_status}")
    lines.append(f"- **证据完整度**: {parse_badge}")
    lines.append("")

    for side_key, side_title in [
        ("radiant_pos_1_to_5", "天辉阵容 (Radiant) — 1~5号位账本"),
        ("dire_pos_1_to_5", "夜魇阵容 (Dire) — 1~5号位账本"),
    ]:
        team = report[side_key]
        lines.append(f"## {side_title}")
        lines.append("")
        lines.append(
            "| 位置 | 英雄 | 玩家 | 段位 | K/D/A (参战) | 净资产 (GPM/XPM) | 补刀 (10m) | 英雄伤害 (占比) | 承受伤害 | 建筑伤害 | 读秒时长 | 分锅占比 |"
        )
        lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for p in team:
            l10 = p["laning_10m"]
            lh10_str = f" ({l10['lh10']}/{l10['dn10']})" if l10["lh10"] is not None else ""
            d_sec = p.get("dead_seconds") or 0
            lines.append(
                f"| {p['pos']}号位 | {p['hero_short_zh']} | `{p['personaname']}` | {p['rank']} | "
                f"{p['kda']} ({p['kill_participation_pct']}%) | {p['net_worth']:,} ({p['gpm']}/{p['xpm']}) | "
                f"{p['last_hits']}/{p['denies']}{lh10_str} | {p['hero_damage']:,} ({p['hero_damage_share_pct']}%) | "
                f"{p.get('damage_taken', 0):,} | {p['tower_damage']:,} | {d_sec//60}m{d_sec%60:02d}s | {p.get('blame_share_pct', 0)}% |"
            )
        lines.append("")

    return "\n".join(lines)


def cmd_roster(args: argparse.Namespace) -> None:
    roster = load_roster()
    if args.set_main:
        aid = normalize_account_id(args.set_main[0])
        name = args.set_main[1] if len(args.set_main) > 1 else "我"
        roster["main_account_id"] = aid
        roster["main_name"] = name
        roster.setdefault("players", {})[str(aid)] = {
            "name": name,
            "usual_pos": "主力",
            "note": "本人账号",
        }
        save_roster(roster)
        print(f"已设置主账号: {name} (Steam32: {aid})")

    if args.add_friend:
        aid = normalize_account_id(args.add_friend[0])
        name = args.add_friend[1]
        pos = args.add_friend[2] if len(args.add_friend) > 2 else "常驻队友"
        roster.setdefault("players", {})[str(aid)] = {
            "name": name,
            "usual_pos": pos,
            "note": "开黑队友",
        }
        save_roster(roster)
        print(f"已添加开黑好友: {name} (ID: {aid}, 常用位置: {pos})")

    print(json.dumps(roster, ensure_ascii=False, indent=2))


def cmd_recent(args: argparse.Namespace) -> None:
    roster = load_roster()
    aid = normalize_account_id(args.account_id) if args.account_id else roster.get("main_account_id")
    if not aid:
        print("请提供 --account-id")
        sys.exit(1)

    matches = api_get(f"/players/{aid}/recentMatches")
    limit = min(args.limit, len(matches))
    for m in matches[:limit]:
        mid = m.get("match_id")
        is_rad = (m.get("player_slot", 0) < 128)
        won = (is_rad and m.get("radiant_win")) or (not is_rad and not m.get("radiant_win"))
        res_str = "胜" if won else "负"
        hero_str = get_hero_name(m.get("hero_id", 0))
        kda = f"{m.get('kills',0)}/{m.get('deaths',0)}/{m.get('assists',0)}"
        dur = format_duration(m.get("duration", 0))
        dt = datetime.datetime.fromtimestamp(m.get("start_time", 0)).strftime("%m-%d %H:%M")
        print(f"Match {mid} | {dt} | {res_str} | {hero_str:<14} | KDA: {kda:<9} | 时长: {dur}")


def cmd_analyze(args: argparse.Namespace) -> None:
    roster = load_roster()
    aid = normalize_account_id(args.account_id) if args.account_id else roster.get("main_account_id")
    match_id = args.match_id

    if not match_id:
        recent = api_get(f"/players/{aid}/recentMatches")
        match_id = recent[0]["match_id"]

    raw_cache = REPORTS_DIR / f"raw_{match_id}.json"
    if raw_cache.exists():
        match_data = json.loads(raw_cache.read_text(encoding="utf-8"))
    else:
        match_data = api_get(f"/matches/{match_id}")
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        raw_cache.write_text(json.dumps(match_data, ensure_ascii=False), encoding="utf-8")

    report = analyze_match_data(match_data, roster, focus_account_id=aid)
    md_text = render_markdown_report(report)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    md_path = REPORTS_DIR / f"match_{match_id}.md"
    json_path = REPORTS_DIR / f"match_{match_id}.json"
    md_path.write_text(md_text, encoding="utf-8")
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告已生成: {json_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Dota 2 复盘引擎 CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_roster = sub.add_parser("roster")
    p_roster.add_argument("--set-main", nargs="+")
    p_roster.add_argument("--add-friend", nargs="+")

    p_recent = sub.add_parser("recent")
    p_recent.add_argument("--account-id", type=str)
    p_recent.add_argument("--limit", type=int, default=5)

    p_analyze = sub.add_parser("analyze")
    p_analyze.add_argument("--match-id", type=int)
    p_analyze.add_argument("--account-id", type=str)
    p_analyze.add_argument("--request-parse", action="store_true")

    args = parser.parse_args()
    if args.cmd == "roster":
        cmd_roster(args)
    elif args.cmd == "recent":
        cmd_recent(args)
    elif args.cmd == "analyze":
        cmd_analyze(args)


if __name__ == "__main__":
    main()
