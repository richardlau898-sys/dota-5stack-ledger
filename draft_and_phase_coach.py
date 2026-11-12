#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dota 2 阵容选择诊断 (BP & Combo 算账) + 分阶段个人/团队深度评价引擎
为每场比赛提供：
1. 阵容选择评估 (选得如何、六维成色对比、阵容先天优势与短板、克制关系)
2. 核心技能配合指南与实战兑现核查 (有什么配合可以打 + 这把实际打出来没有)
3. 前期 (0-10m) / 中期 (10-25m) / 后期 (25m+) 每个阶段 1-5 号位每个人的「做得好」「做得不好」「改进点」
4. 综合整个团队在前期、中期、后期如何进步的实战作业本
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dota_constants_zh import ACTIVE_SAVE_ITEMS_ZH, HEROES_ZH, get_held_active_save_items
from hero_profiles_126 import (
    HERO_PROFILES_126,
    build_hero_matchup_dossier,
    compute_hero_pair_counter,
    get_hero_profile_126,
)

_REPO_ROOT = Path(__file__).resolve().parent
_HERO_STATS_CACHE: Optional[Dict[int, Dict[str, Any]]] = None


def load_hero_stats_by_id(hs_path: Optional[Path] = None) -> Dict[int, Dict[str, Any]]:
    """从 .cache/hero_stats.json 加载 OpenDota /heroStats 真实分段位数据；文件不存在时返回空字典（绝不兜底伪造）。"""
    global _HERO_STATS_CACHE
    if hs_path is None and _HERO_STATS_CACHE is not None:
        return _HERO_STATS_CACHE

    target_path = hs_path if hs_path is not None else (_REPO_ROOT / ".cache" / "hero_stats.json")
    by_id: Dict[int, Dict[str, Any]] = {}
    if target_path.exists():
        try:
            raw_obj = json.loads(target_path.read_text(encoding="utf-8"))
            raw_list = raw_obj.get("heroes") if isinstance(raw_obj, dict) else raw_obj
            if isinstance(raw_list, list):
                for item in raw_list:
                    if isinstance(item, dict) and "id" in item:
                        by_id[int(item["id"])] = item
        except Exception:
            pass

    if hs_path is None:
        _HERO_STATS_CACHE = by_id
    return by_id


def load_squad_hero_pool_and_against_stats() -> Tuple[Dict[int, Dict[str, Any]], List[Dict[str, Any]]]:
    """
    R3-5: 聚合车队真实英雄池与交手记录（绝不读取已从 Vercel 包排除的原始录像 JSON）：
    1) 优先从 cloud_fetch_player_matches 读取全量历史对局英雄池（标注「车队全量对局」）
    2) 若全量表为空，则从已生成的 match_*.json 报告汇总我方英雄池（标注「已复盘对局」）与敌方英雄交手记录
    3) 若本地存在 .cache/player_heroes_against.json 则加载交手记录
    """
    import cloud_store
    import dota_analyst

    roster_ids = sorted({
        int(aid)
        for m in dota_analyst.iter_roster_accounts(dota_analyst.load_roster())
        for aid in m["account_ids"]
    })

    squad_pool: Dict[int, Dict[str, Any]] = {}
    against_map: Dict[int, Dict[str, int]] = {}

    # 1. 优先从 player_matches 全量历史读取车队个人英雄池
    pm_rows = cloud_store.cloud_fetch_player_matches(roster_ids)
    if pm_rows:
        seen_pm_keys = set()
        for r in pm_rows:
            if not isinstance(r, dict) or not r.get("match_id") or not r.get("account_id"):
                continue
            key = (int(r["account_id"]), int(r["match_id"]))
            if key in seen_pm_keys:
                continue
            seen_pm_keys.add(key)
            hid = int(r.get("hero_id") or 0)
            if hid <= 0:
                continue
            zh = r.get("hero_short_zh") or (HEROES_ZH.get(hid) or (f"英雄#{hid}",))[0]
            sp = squad_pool.setdefault(
                hid,
                {"hero_id": hid, "hero_short_zh": zh, "games": 0, "wins": 0, "source_zh": "车队全量对局"},
            )
            sp["games"] += 1
            if r.get("won"):
                sp["wins"] += 1

    # 2. 若存在 against 缓存快照则读取
    against_cache_path = _REPO_ROOT / ".cache" / "player_heroes_against.json"
    if against_cache_path.exists():
        try:
            raw_ag = json.loads(against_cache_path.read_text(encoding="utf-8"))
            rows = raw_ag if isinstance(raw_ag, list) else (raw_ag.get("heroes") or [])
            for r in rows:
                hid = int(r.get("hero_id") or 0)
                if hid <= 0:
                    continue
                ag_g = int(r.get("against_games") or 0)
                ag_w = int(r.get("against_win") or 0)
                if ag_g > 0:
                    slot = against_map.setdefault(hid, {"hero_id": hid, "against_games": 0, "against_win": 0})
                    slot["against_games"] += ag_g
                    slot["against_win"] += ag_w
                if not pm_rows:
                    own_g = int(r.get("games") or 0)
                    own_w = int(r.get("win") or 0)
                    if own_g > 0:
                        zh = (HEROES_ZH.get(hid) or (f"英雄#{hid}",))[0]
                        sp = squad_pool.setdefault(
                            hid,
                            {"hero_id": hid, "hero_short_zh": zh, "games": 0, "wins": 0, "source_zh": "车队全量对局"},
                        )
                        sp["games"] += own_g
                        sp["wins"] += own_w
        except Exception:
            pass

    # 3. 从打包在部署环境内的 match_*.json（以及 /tmp/dota_reports/match_*.json）汇总已复盘对局英雄池与敌方交手记录
    if not squad_pool or not against_map:
        need_pool = not bool(squad_pool)
        need_against = not bool(against_map)
        seen_mids = set()
        for scan_dir in (Path("/tmp/dota_reports"), _REPO_ROOT / "reports"):
            if not scan_dir.exists():
                continue
            for rep_p in sorted(scan_dir.glob("match_*.json")):
                try:
                    rep = json.loads(rep_p.read_text(encoding="utf-8"))
                except Exception:
                    continue
                mid = int(rep.get("match_id") or 0)
                if not mid or mid in seen_mids:
                    continue
                seen_mids.add(mid)
                focus_side = str(rep.get("focus_side") or "dire")
                rad_win = bool(rep.get("radiant_win"))
                squad_won = rad_win if focus_side == "radiant" else (not rad_win)
                own_list = rep.get("radiant_pos_1_to_5" if focus_side == "radiant" else "dire_pos_1_to_5") or []
                opp_list = rep.get("dire_pos_1_to_5" if focus_side == "radiant" else "radiant_pos_1_to_5") or []
                if need_pool:
                    for pl in own_list:
                        hid = int(pl.get("hero_id") or 0)
                        if hid <= 0:
                            continue
                        zh = pl.get("hero_short_zh") or (HEROES_ZH.get(hid) or (f"英雄#{hid}",))[0]
                        sp = squad_pool.setdefault(
                            hid,
                            {"hero_id": hid, "hero_short_zh": zh, "games": 0, "wins": 0, "source_zh": "已复盘对局"},
                        )
                        sp["games"] += 1
                        if squad_won:
                            sp["wins"] += 1
                if need_against:
                    for pl in opp_list:
                        hid = int(pl.get("hero_id") or 0)
                        if hid <= 0:
                            continue
                        slot = against_map.setdefault(hid, {"hero_id": hid, "against_games": 0, "against_win": 0})
                        slot["against_games"] += 1
                        if squad_won:
                            slot["against_win"] += 1

    return squad_pool, list(against_map.values())


def compute_real_bp_matchup_stats(
    own_picks: List[Dict[str, Any]],
    enemy_picks: List[Dict[str, Any]],
    squad_hero_pool: Optional[Dict[int, Dict[str, Any]]] = None,
    against_heroes_data: Optional[List[Dict[str, Any]]] = None,
    hero_stats_by_id: Optional[Dict[int, Dict[str, Any]]] = None,
    min_games: int = 10,
) -> Dict[str, Any]:
    """
    F5 真实数据 BP 评估：
    1. 车队自身全量英雄池（F1）：展示本方所选英雄的真实场次与胜率（<10 局 win_rate=None，标记 insufficient_sample=True）。
    2. OpenDota /players/{id}/heroes 的 against_games 与 against_win：计算对阵敌方英雄的真实胜率及“车队最常输给谁”（遵守 against_games >= 10）。
    3. OpenDota /heroStats：展示分段位（超凡/冠绝 6_pick+7_pick 与全分段 pub_pick）真实选取数与胜率。
    """
    hs_map = hero_stats_by_id if hero_stats_by_id is not None else load_hero_stats_by_id()
    if squad_hero_pool is None or against_heroes_data is None:
        default_pool, default_against = load_squad_hero_pool_and_against_stats()
        if squad_hero_pool is None:
            squad_hero_pool = default_pool
        if against_heroes_data is None:
            against_heroes_data = default_against

    against_by_hid: Dict[int, Dict[str, int]] = {}
    for row in against_heroes_data or []:
        hid = int(row.get("hero_id") or 0)
        if hid <= 0:
            continue
        slot = against_by_hid.setdefault(hid, {"hero_id": hid, "against_games": 0, "against_win": 0})
        slot["against_games"] += int(row.get("against_games") or 0)
        slot["against_win"] += int(row.get("against_win") or 0)

    def _extract_bracket_stats(hid: int) -> Dict[str, Any]:
        hs = hs_map.get(hid) or {}
        b_pick = int(hs.get("6_pick") or 0) + int(hs.get("7_pick") or 0) + int(hs.get("8_pick") or 0)
        b_win = int(hs.get("6_win") or 0) + int(hs.get("7_win") or 0) + int(hs.get("8_win") or 0)
        pub_pick = int(hs.get("pub_pick") or 0) or b_pick
        pub_win = int(hs.get("pub_win") or 0) or b_win
        return {
            "bracket_pick": b_pick if b_pick > 0 else None,
            "bracket_win": b_win if b_pick > 0 else None,
            "bracket_win_rate": round(b_win / b_pick * 100.0, 1) if b_pick > 0 else None,
            "pub_pick": pub_pick if pub_pick > 0 else None,
            "pub_win": pub_win if pub_pick > 0 else None,
            "pub_win_rate": round(pub_win / pub_pick * 100.0, 1) if pub_pick > 0 else None,
        }

    pool_source_zh = "车队全量对局" if any(
        isinstance(v, dict) and v.get("source_zh") == "车队全量对局"
        for v in (squad_hero_pool or {}).values()
    ) else "已复盘对局"

    own_hero_real_stats: List[Dict[str, Any]] = []
    for item in own_picks or []:
        hid = int(item.get("hero_id") or 0)
        if hid <= 0:
            continue
        pos = int(item.get("pos") or 1)
        zh = item.get("hero_short_zh") or (HEROES_ZH.get(hid) or (f"英雄#{hid}",))[0]
        sp = (squad_hero_pool or {}).get(hid) or {}
        g = int(sp.get("games") or 0)
        w = int(sp.get("wins") or 0)
        insuff = g < min_games
        wr = round(w / g * 100.0, 1) if (g >= min_games and g > 0) else None
        b_info = _extract_bracket_stats(hid)
        own_hero_real_stats.append({
            "pos": pos,
            "hero_id": hid,
            "hero_short_zh": zh,
            "player_name": item.get("player_name") or item.get("personaname") or "",
            "squad_games": g,
            "squad_wins": w,
            "squad_win_rate": wr,
            "squad_insufficient_sample": insuff,
            "squad_source_zh": str(sp.get("source_zh") or pool_source_zh),
            "bracket_source_zh": "OpenDota 超凡/冠绝",
            "pub_source_zh": "OpenDota 全分段",
            **b_info,
        })

    enemy_against_stats: List[Dict[str, Any]] = []
    for item in enemy_picks or []:
        hid = int(item.get("hero_id") or 0)
        if hid <= 0:
            continue
        pos = int(item.get("pos") or 1)
        zh = item.get("hero_short_zh") or (HEROES_ZH.get(hid) or (f"英雄#{hid}",))[0]
        ag = against_by_hid.get(hid) or {}
        ag_g = int(ag.get("against_games") or 0)
        ag_w = int(ag.get("against_win") or 0)
        ag_l = max(0, ag_g - ag_w)
        insuff = ag_g < min_games
        ag_wr = round(ag_w / ag_g * 100.0, 1) if (ag_g >= min_games and ag_g > 0) else None
        b_info = _extract_bracket_stats(hid)
        enemy_against_stats.append({
            "pos": pos,
            "hero_id": hid,
            "hero_short_zh": zh,
            "against_games": ag_g,
            "against_win": ag_w,
            "against_losses": ag_l,
            "against_win_rate": ag_wr,
            "insufficient_sample": insuff,
            "against_source_zh": "车队交手记录",
            "bracket_source_zh": "OpenDota 超凡/冠绝",
            "pub_source_zh": "OpenDota 全分段",
            **b_info,
        })

    most_lost_against_top: List[Dict[str, Any]] = []
    for hid, ag in against_by_hid.items():
        ag_g = int(ag.get("against_games") or 0)
        ag_w = int(ag.get("against_win") or 0)
        if ag_g < min_games:
            continue
        ag_l = max(0, ag_g - ag_w)
        ag_wr = round(ag_w / ag_g * 100.0, 1)
        zh = (HEROES_ZH.get(hid) or (f"英雄#{hid}",))[0]
        most_lost_against_top.append({
            "hero_id": hid,
            "hero_short_zh": zh,
            "against_games": ag_g,
            "against_win": ag_w,
            "against_losses": ag_l,
            "against_win_rate": ag_wr,
            "loss_rate": round(100.0 - ag_wr, 1),
            "insufficient_sample": False,
            "source_zh": "车队交手记录",
        })
    most_lost_against_top.sort(key=lambda x: (x["against_win_rate"], -x["against_losses"], -x["against_games"]))

    return {
        "min_games": min_games,
        "squad_pool_source_zh": pool_source_zh,
        "own_hero_real_stats": own_hero_real_stats,
        "enemy_against_stats": enemy_against_stats,
        "most_lost_against_top": most_lost_against_top[:10],
        "data_sources": {
            "squad_history": pool_source_zh,
            "against_stats": "车队交手记录",
            "bracket_stats": "OpenDota 超凡/冠绝",
            "uses_pro_only_matchups_endpoint": False,
            "stratz_token_configured": bool(os.environ.get("STRATZ_API_TOKEN")),
            "note": "OpenDota /heroes/{id}/matchups 仅统计职业比赛，不冒充路人局克制数据；本页所有数字均逐项标注真实数据来源。",
        },
    }


def get_hero_archetype(p: Dict[str, Any]) -> Dict[str, Any]:
    """基于 OpenDota /heroStats 官方角色与属性常量 + 126 英雄机制配置动态构建英雄画像（移除 59 英雄手写打分字典）。"""
    hid = int(p.get("hero_id") or 0)
    pos = int(p.get("pos") or 3)
    short = p.get("hero_short_zh") or p.get("hero_name") or (HEROES_ZH.get(hid) or (f"英雄#{hid}",))[0]
    prof = dict(get_hero_profile_126(hid, pos, short))
    hs = load_hero_stats_by_id().get(hid) or {}
    if hs:
        roles_api = set(hs.get("roles") or [])
        base_scores = dict(prof.get("scores") or {})
        b_pick = int(hs.get("6_pick") or 0) + int(hs.get("7_pick") or 0)
        b_win = int(hs.get("6_win") or 0) + int(hs.get("7_win") or 0)
        wr_delta = ((b_win / b_pick) - 0.50) * 20.0 if b_pick > 0 else 0.0
        str_gain = float(hs.get("str_gain") or 2.2)
        agi_gain = float(hs.get("agi_gain") or 2.0)
        int_gain = float(hs.get("int_gain") or 2.0)
        for k in ("init", "burst", "tf", "push", "pick", "late", "tank"):
            v = float(base_scores.get(k, 65)) + wr_delta
            if k == "tank":
                v += (str_gain - 2.4) * 3.0 + (4.0 if "Durable" in roles_api else 0.0)
            elif k == "init":
                v += 4.0 if "Initiator" in roles_api else 0.0
            elif k == "push":
                v += 4.0 if "Pusher" in roles_api else 0.0
            elif k == "burst":
                v += (int_gain - 2.2) * 1.5 + (3.0 if "Nuker" in roles_api else 0.0)
            elif k == "late":
                v += (agi_gain - 2.2) * 1.5 + (3.0 if "Carry" in roles_api else 0.0)
            base_scores[k] = max(25, min(98, int(round(v))))
        prof["scores"] = base_scores
        prof["key_spells"] = list(prof.get("signature_abilities") or [])
    return prof


def compute_team_draft_scores(team_players: List[Dict[str, Any]], opp_players: Optional[List[Dict[str, Any]]] = None) -> Dict[str, int]:
    if not team_players:
        return {"init": 60, "burst": 60, "tf": 60, "push": 60, "pick": 60, "late": 60, "tank": 60}
    archs = [get_hero_archetype(p) for p in team_players]
    out = {}
    for k in ("init", "burst", "tf", "push", "pick", "late", "tank"):
        vals = sorted([a["scores"].get(k, 60) for a in archs], reverse=True)
        top2_avg = sum(vals[:2]) / max(1, len(vals[:2]))
        all_avg = sum(vals) / len(vals)
        out[k] = int(round(top2_avg * 0.60 + all_avg * 0.40))

    # 阵容结构性奖惩修正 (Structural Composition Adjustments)
    by_pos = {int(p.get("pos") or i + 1): get_hero_archetype(p) for i, p in enumerate(team_players)}
    p1_arch = by_pos.get(1, archs[0])
    p2_arch = by_pos.get(2, archs[min(1, len(archs) - 1)])
    frontliners = sum(1 for a in archs if "frontline_tank" in a.get("synergy_tags", []) or a["scores"].get("tank", 50) >= 78)
    squishy_cnt = sum(1 for a in archs if "squishy_ranged" in a.get("synergy_tags", []) or a["scores"].get("tank", 50) <= 46)

    # 1) 双远程脆皮游走核 / 缺传统正面大核 (e.g. 1号位先知 + 2号位克林克兹)
    if "weak_frontal_carry" in p1_arch.get("synergy_tags", []) and "weak_frontal_carry" in p2_arch.get("synergy_tags", []):
        out["tf"] = max(45, out["tf"] - 12)
        out["late"] = max(48, out["late"] - 14)
        out["tank"] = max(42, out["tank"] - 10)
    elif "weak_frontal_carry" in p1_arch.get("synergy_tags", []):
        out["tf"] = max(50, out["tf"] - 6)
        out["late"] = max(52, out["late"] - 8)

    # 2) 单前排孤立 / 四脆皮阵容
    if frontliners == 0:
        out["tank"] = max(38, out["tank"] - 14)
        out["tf"] = max(48, out["tf"] - 8)
    elif frontliners == 1 and squishy_cnt >= 4:
        out["tank"] = max(44, out["tank"] - 9)
        out["tf"] = max(52, out["tf"] - 6)

    # 3) 对阵克制修正 (Matchup Counter Adjustments)
    if opp_players:
        opp_archs = [get_hero_archetype(p) for p in opp_players]
        opp_tags = {t for a in opp_archs for t in a.get("synergy_tags", [])}
        own_tags = {t for a in archs for t in a.get("synergy_tags", [])}
        # 带球/隐身抓单核遇到对手全图反打+瞥视框大 (e.g. 先知+小骷髅 遇到 破晓辰星+干扰者+小强)
        if "weak_frontal_carry" in own_tags and "anti_split_push" in opp_tags:
            out["pick"] = max(52, out["pick"] - 7)
            out["tf"] = max(48, out["tf"] - 5)
        # 单前排遇到黑鸟/小鱼人
        if frontliners == 1 and ("anti_tank_pure" in opp_tags or "anti_tank_steal" in opp_tags):
            out["tank"] = max(42, out["tank"] - 6)

    return out


def build_team_combos(
    own_players: List[Dict[str, Any]],
    opp_players: List[Dict[str, Any]],
    is_parsed: bool = True,
) -> List[Dict[str, Any]]:
    """
    识别本方阵容最具威胁的 3~4 套多英雄配合 (Combo)，并结合本局真实释放次数与数据核验执行效果
    """
    by_hid = {int(p.get("hero_id") or 0): p for p in own_players}
    by_pos = {int(p.get("pos") or i + 1): p for i, p in enumerate(own_players)}
    opp_names = [p.get("hero_short_zh") or p.get("hero_name") for p in opp_players]

    def ab_count(p: Dict[str, Any], keyword: str) -> int:
        for ab in p.get("ability_uses_rich") or []:
            if keyword in (ab.get("zh_name") or "") or keyword in (ab.get("key") or ""):
                return int(ab.get("count") or 0)
        return 0

    combos: List[Dict[str, Any]] = []

    # 专项配合规则 1: 马格纳斯 (97) + 物理大核 (主宰 8 / 龙骑 49 / 力丸 32 / PA 44 / 1号位)
    if 97 in by_hid:
        mag = by_hid[97]
        carry = by_hid.get(8) or by_hid.get(49) or by_hid.get(32) or by_pos.get(1)
        if carry and carry["player_slot"] != mag["player_slot"]:
            emp_cnt = ab_count(mag, "授予力量") or ab_count(mag, "empower")
            rp_cnt = ab_count(mag, "两极反转") or ab_count(mag, "reverse_polarity")
            skewer_cnt = ab_count(mag, "巨角冲撞") or ab_count(mag, "skewer")
            c_short = carry["hero_short_zh"]
            combos.append({
                "title": f"【马格纳斯 + {c_short}】授予力量刷钱引擎 & 两极反转 (RP) 团灭链",
                "window": "10分钟至终局 · 刷钱提速与团战一锤定音",
                "heroes": [
                    {"short": mag["hero_short_zh"], "img": mag["hero_img"], "pos": mag["pos"], "personaname": mag["personaname"]},
                    {"short": c_short, "img": carry["hero_img"], "pos": carry["pos"], "personaname": carry["personaname"]},
                ],
                "how_to_play": (
                    f"1) 发育期：马格纳斯必须卡冷却给 {c_short} 套上『授予力量』，让 {c_short} 拥有分裂与额外攻击力高速清远古与兵线；"
                    f"2) 团战期：马格纳斯切忌第一波裸跳送死，等敌方关键救人/反手（如{'、'.join(opp_names[:2])}）露头后，跳刀『两极反转』吸住多人或把核心拱回，"
                    f"{c_short} 立即接大招/溅射输出瞬间融化敌方前排。"
                ),
                "execution_audit": (
                    f"本局实战验货：马格纳斯整局释放『授予力量』{emp_cnt} 次、『两极反转』{rp_cnt} 次、『巨角冲撞』{skewer_cnt} 次；"
                    f"{c_short} 终局刷出 {carry['gpm']} GPM（净资产 {carry['net_worth']:,} 金，英雄伤害 {carry['hero_damage']:,}）。"
                ),
            })

    # 专项配合规则 2: 莱恩 (26) + 米拉娜 (9) + 线上/中单爆发
    if 26 in by_hid and 9 in by_hid:
        lion = by_hid[26]
        pom = by_hid[9]
        impale_cnt = ab_count(lion, "裂地尖刺")
        hex_cnt = ab_count(lion, "妖术")
        arrow_cnt = ab_count(pom, "月神之箭")
        moon_cnt = ab_count(pom, "月之暗面")
        combos.append({
            "title": "【莱恩瞬发戳羊 + 米拉娜穿云箭】长达 6 秒的无解点控秒人链",
            "window": "2–25分钟 · 线上击杀与月之暗面抓单节奏",
            "heroes": [
                {"short": lion["hero_short_zh"], "img": lion["hero_img"], "pos": lion["pos"], "personaname": lion["personaname"]},
                {"short": pom["hero_short_zh"], "img": pom["hero_img"], "pos": pom["pos"], "personaname": pom["personaname"]},
            ],
            "how_to_play": (
                "绝不能由米拉娜先手随缘摸奖射箭！标准打法是：开启米拉娜『月之暗面』或诡计之雾双游，"
                "由莱恩直接走脸上或跳刀先手『妖术(变羊) / 裂地尖刺(戳)』定住目标，米拉娜在侧翼卡视野直接接『月神之箭』必中满晕，"
                "两人再补『群星风暴』+『死亡一指』，前期任何敌方核心吃满这套必死。"
            ),
            "execution_audit": (
                f"本局实战验货：莱恩整局释放『裂地尖刺』{impale_cnt} 次、『妖术』{hex_cnt} 次；米拉娜射出『月神之箭』{arrow_cnt} 次、开启『月之暗面』{moon_cnt} 次。"
                f"两人合计参战率分别为 {lion['kill_participation_pct']}% 与 {pom['kill_participation_pct']}%，"
                f"整局合计阵亡 {lion['deaths'] + pom['deaths']} 次（莱恩 {lion['deaths']} 死 / 米拉娜 {pom['deaths']} 死）。"
            ),
        })

    # 专项配合规则 3: 帕格纳 (45) + 莱恩 (26) / 法系爆发 & 幽冥守卫反制
    if 45 in by_hid:
        pugna = by_hid[45]
        blast_cnt = ab_count(pugna, "幽冥爆轰")
        decrep_cnt = ab_count(pugna, "衰老")
        ward_cnt = ab_count(pugna, "幽冥守卫")
        drain_cnt = ab_count(pugna, "生命汲取")
        partner = by_hid.get(26) or by_hid.get(8) or by_pos.get(1)
        p_list = [{"short": pugna["hero_short_zh"], "img": pugna["hero_img"], "pos": pugna["pos"], "personaname": pugna["personaname"]}]
        if partner and partner["player_slot"] != pugna["player_slot"]:
            p_list.append({"short": partner["hero_short_zh"], "img": partner["hero_img"], "pos": partner["pos"], "personaname": partner["personaname"]})
        combos.append({
            "title": "【帕格纳衰老增伤 + 幽冥守卫反法系 + 爆轰速推】阵地折磨与高地拆迁体系",
            "window": "8分钟至终局 · 推塔压制与限制敌方冲脸/高耗蓝法师",
            "heroes": p_list,
            "how_to_play": (
                "1) 团战开打前：帕格纳必须先把『幽冥守卫(棒子)』插在侧翼树林或高坡后方，让敌方法师每放一个大招都先掉半管血；"
                "2) 集火与救人：队友被敌方物理核跳砍时立刻给『衰老(虚无)』废掉其物理平A；集火敌方时套『衰老』配合幽冥爆轰与队友法系爆发瞬间融化（注意别在己方物理核正要平A输出时乱给衰老！）；"
                "3) 推塔：站在兵线后高频使用『幽冥爆轰』磨塔消耗防御塔血量。"
            ),
            "execution_audit": (
                f"本局实战验货：帕格纳整局轰出 {blast_cnt} 次『幽冥爆轰』、插下 {ward_cnt} 根『幽冥守卫』、释放 {decrep_cnt} 次『衰老』与 {drain_cnt} 次『生命汲取』，"
                f"打出 {pugna['hero_damage']:,} 英雄伤害与 {pugna['tower_damage']:,} 建筑伤害（整局阵亡 {pugna['deaths']} 次）。"
            ),
        })

    # 专项配合规则 4: 力丸 (32) + 马格纳斯 (97) / 龙骑士 (49) / 巫医 (30)
    if 32 in by_hid:
        riki = by_hid[32]
        cloud_cnt = ab_count(riki, "烟幕")
        blink_cnt = ab_count(riki, "闪烁突袭")
        setup_hero = by_hid.get(49) or by_hid.get(97) or by_pos.get(3)
        wd_hero = by_hid.get(30)
        hero_chips = [{"short": riki["hero_short_zh"], "img": riki["hero_img"], "pos": riki["pos"], "personaname": riki["personaname"]}]
        if setup_hero and setup_hero["player_slot"] != riki["player_slot"]:
            hero_chips.append({"short": setup_hero["hero_short_zh"], "img": setup_hero["hero_img"], "pos": setup_hero["pos"], "personaname": setup_hero["personaname"]})
        if wd_hero:
            hero_chips.append({"short": wd_hero["hero_short_zh"], "img": wd_hero["hero_img"], "pos": wd_hero["pos"], "personaname": wd_hero["personaname"]})
        setup_name = setup_hero["hero_short_zh"] if setup_hero else "先手前排"

        combos.append({
            "title": f"【{setup_name}先手跳控 + 力丸烟幕沉默致盲】关门打狗连招",
            "window": "12–30分钟 · 中期抓人与小规模团战",
            "heroes": hero_chips,
            "how_to_play": (
                "力丸本身没有硬眩晕，最怕对面直接推推/BKB或反手硬控！标准打法是："
                f"必须等 {setup_name} 先手定住人的瞬间，力丸立刻在目标脚下铺开『烟幕(雾)』使其沉默+丢失平A无法按出逃生技能，"
                "在烟幕持续时间内配合队友爆发完成击杀。"
            ),
            "execution_audit": (
                f"本局实战验货：力丸整局释放 {cloud_cnt} 次『烟幕』、{blink_cnt} 次『闪烁突袭』，打出 {riki['hero_damage']:,} 伤害（KDA {riki['kda']}）。"
            ),
        })

    # 专项配合规则 5: 龙骑士 (49) + 钢背兽 (99) + 巫医 (30)
    if 49 in by_hid and 99 in by_hid:
        dk = by_hid[49]
        bb = by_hid[99]
        stun_cnt = ab_count(dk, "神龙摆尾")
        dragon_cnt = ab_count(dk, "古龙形态")
        quill_cnt = ab_count(bb, "刺针扫射")
        snot_cnt = ab_count(bb, "粘稠鼻涕")
        combos.append({
            "title": "【钢背兽前排叠刺减甲 + 龙骑士变龙跳晕推进】双肉平推抱团战车",
            "window": "10–25分钟 · 变龙逼塔与正面肉搏期",
            "heroes": [
                {"short": dk["hero_short_zh"], "img": dk["hero_img"], "pos": dk["pos"], "personaname": dk["personaname"]},
                {"short": bb["hero_short_zh"], "img": bb["hero_img"], "pos": bb["pos"], "personaname": bb["personaname"]},
            ],
            "how_to_play": (
                "龙骑+钢背的精髓在于『12~22分钟抱团顶着塔强推』：钢背兽顶在最前面吃第一波技能并疯狂叠『粘稠鼻涕』减甲与『刺针扫射』，"
                "龙骑士开启『古龙形态』喷毒磨塔，谁敢上来守塔龙骑直接『神龙摆尾』晕住配合减甲秒掉。"
                "一旦这个时间窗不抱团推塔而是分散刷钱，拖到对面大核做出大炮/否决/银月，双肉就会彻底沦为超级兵！"
            ),
            "execution_audit": (
                f"本局实战验货：龙骑士开启『古龙形态』{dragon_cnt} 次、『神龙摆尾』{stun_cnt} 次（建筑伤害 {dk['tower_damage']:,}）；"
                f"钢背兽释放『刺针扫射』{quill_cnt} 次、『粘稠鼻涕』{snot_cnt} 次（建筑伤害 {bb['tower_damage']:,}，阵亡 {bb['deaths']} 次）。"
            ),
        })

    # 专项配合规则 6: 幽鬼 (67) + 司夜刺客 (88)/裂魂人 (71)/先知 (53)/赏金 (62) + 瘟疫法师 (36)
    if 67 in by_hid:
        spec = by_hid[67]
        spotter = by_hid.get(88) or by_hid.get(71) or by_hid.get(62) or by_hid.get(53) or by_pos.get(4)
        necro = by_hid.get(36)
        step_cnt = ab_count(spec, "暗影步") or ab_count(spec, "鬼影重重") or ab_count(spec, "幽鬼之刃")
        spot_cnt = (ab_count(spotter, "穿刺") or ab_count(spotter, "暗影冲刺") or ab_count(spotter, "发芽")) if spotter else 0
        scythe_cnt = ab_count(necro, "死神镰刀") if necro else 0
        hero_chips = [{"short": spec["hero_short_zh"], "img": spec["hero_img"], "pos": spec["pos"], "personaname": spec["personaname"]}]
        if spotter and spotter["player_slot"] != spec["player_slot"]:
            hero_chips.insert(0, {"short": spotter["hero_short_zh"], "img": spotter["hero_img"], "pos": spotter["pos"], "personaname": spotter["personaname"]})
        if necro and necro["player_slot"] not in {h["pos"] for h in hero_chips}:
            hero_chips.append({"short": necro["hero_short_zh"], "img": necro["hero_img"], "pos": necro["pos"], "personaname": necro["personaname"]})
        spot_name = spotter["hero_short_zh"] if spotter else "4号位游走"
        combos.append({
            "title": f"【{spot_name}隐身/视野锁头 + 幽鬼《暗影步》全图空降" + (" + 瘟疫法师《死神镰刀》斩杀】全球定点猎杀链" if necro else "】全图定点提款链"),
            "window": "6–28分钟 · 幽鬼提速发育与全图抓落单核心窗口",
            "heroes": hero_chips,
            "how_to_play": (
                f"幽鬼天生对线弱、打野慢，绝不能死蹲野区等崩盘！标准打法是：由 {spot_name} 深入敌方野区/后排充当全图雷达，"
                f"一旦先手留住敌方落单脆皮（如{'、'.join(opp_names[:2])}），幽鬼第一时间开启《暗影步》全图飞脸挂《幽鬼之刃》触发《荒芜》纯粹伤害，"
                + ("同时瘟疫法师跟上《死神镰刀》定点斩杀加读秒，打完幽鬼立刻传回原线继续收兵！" if necro else "打完幽鬼立刻传回原线继续收兵，实现刷钱打架两不误！")
            ),
            "execution_audit": (
                f"本局实战验货：{spot_name}释放先手控制 {spot_cnt} 次，幽鬼释放核心技能 {step_cnt} 次（KDA {spec['kda']}，参战率 {spec['kill_participation_pct']}%，GPM {spec['gpm']}）"
                + (f"，瘟疫法师斩出《死神镰刀》{scythe_cnt} 次（KDA {necro['kda']}）。" if necro else "。")
            ),
        })

    # 专项配合规则 7: 潮汐猎人 (29)/斧王 (2) + 电炎绝手 (128)/杰奇洛 (64)/天穹守望者 (113)/卓尔游侠 (6)/工程师 (105)
    init_big = by_hid.get(29) or by_hid.get(2)
    artillery_big = by_hid.get(128) or by_hid.get(64) or by_hid.get(113) or by_hid.get(6) or by_hid.get(105)
    if init_big and artillery_big and init_big["player_slot"] != artillery_big["player_slot"]:
        i_name = init_big["hero_short_zh"]
        a_name = artillery_big["hero_short_zh"]
        i_ult = "毁灭" if int(init_big["hero_id"]) == 29 else "狂战士之吼"
        i_cnt = ab_count(init_big, i_ult) or ab_count(init_big, "锚击") or ab_count(init_big, "淘汰之刃")
        a_prof = get_hero_profile_126(int(artillery_big["hero_id"]), int(artillery_big.get("pos") or 4), a_name)
        a_sig = (a_prof.get("signature_abilities") or ["核心AOE"])[-1]
        a_cnt = ab_count(artillery_big, a_sig)
        cookie_cnt = ab_count(artillery_big, "驯良之饼") if int(artillery_big["hero_id"]) == 128 else 0
        combos.append({
            "title": f"【{init_big['pos']}号位{i_name}《{i_ult}》团控 + {artillery_big['pos']}号位{a_name}《{a_sig}》" + ("/《驯良之饼》】跨地形开团与重炮洗地链" if cookie_cnt or int(artillery_big["hero_id"]) == 128 else "】团控聚怪与重炮洗地链"),
            "window": "12分钟至终局 · 正面5v5团战与高地攻防决胜招",
            "heroes": [
                {"short": i_name, "img": init_big["hero_img"], "pos": init_big["pos"], "personaname": init_big["personaname"]},
                {"short": a_name, "img": artillery_big["hero_img"], "pos": artillery_big["pos"], "personaname": artillery_big["personaname"]},
            ],
            "how_to_play": (
                f"1) 先手投送与留人：{i_name}利用跳刀"
                + (f"（或由电炎绝手喂《驯良之饼》跨地形弹射进场）" if int(artillery_big["hero_id"]) == 128 else "")
                + f"直接切入敌方阵型中心释放《{i_ult}》控住多人；"
                f"2) 远程火力覆盖：{a_name}严禁走第一排吃控制，必须站在侧后方安全距离，在《{i_ult}》眩晕/嘲讽命中的瞬间倾泻《{a_sig}》，把敌方核心死死摁在AOE火海里融化！"
            ),
            "execution_audit": (
                (
                    f"本局实战验货：{i_name}释放《{i_ult}/核心控》{i_cnt} 次（全场控制 {init_big.get('stuns_sec') or 0} 秒，承伤 {init_big.get('damage_taken', 0):,}），"
                    f"{a_name}释放《{a_sig}》{a_cnt} 次"
                    + (f"、《驯良之饼》{cookie_cnt} 次" if int(artillery_big["hero_id"]) == 128 else "")
                    + f"（轰出 {artillery_big['hero_damage']:,} 英雄伤害）。"
                )
                if is_parsed
                else f"本局实战验货：{i_name}交出 KDA {init_big['kda']}，{a_name}轰出 {artillery_big['hero_damage']:,} 英雄伤害（技能释放次数与控制时长需先解析录像）。"
            ),
        })

    # 专项配合规则 8: 斯拉克 (93) + 编织者 (63)/拉比克 (86)/莱恩 (26)
    if 93 in by_hid and (63 in by_hid or 86 in by_hid or 26 in by_hid):
        slark = by_hid[93]
        supp_ctrl = by_hid.get(26) or by_hid.get(86) or by_pos.get(4)
        weaver = by_hid.get(63)
        pounce_cnt = ab_count(slark, "突袭")
        pact_cnt = ab_count(slark, "黑暗契约")
        hero_chips = [{"short": slark["hero_short_zh"], "img": slark["hero_img"], "pos": slark["pos"], "personaname": slark["personaname"]}]
        if supp_ctrl:
            hero_chips.insert(0, {"short": supp_ctrl["hero_short_zh"], "img": supp_ctrl["hero_img"], "pos": supp_ctrl["pos"], "personaname": supp_ctrl["personaname"]})
        if weaver:
            hero_chips.append({"short": weaver["hero_short_zh"], "img": weaver["hero_img"], "pos": weaver["pos"], "personaname": weaver["personaname"]})
        supp_name = supp_ctrl["hero_short_zh"] if supp_ctrl else "辅助"
        combos.append({
            "title": f"【{supp_name}瞬发先手 + 斯拉克《突袭》锁人偷属性" + (" + 编织者《凰虫》减甲收割】" if weaver else "】机动抓单链"),
            "window": "8–28分钟 · 抓单滚雪球与双黑雾拉扯",
            "heroes": hero_chips,
            "how_to_play": (
                f"斯拉克《突袭》无指向性，极怕敌方走位扭开！必须由 {supp_name} 瞬发控制先手定住目标，"
                "斯拉克立刻接《突袭》拴住并开启《黑暗契约》"
                + ("，同时编织者释放《凰虫》群体减甲开视野，让斯拉克安全叠满《能量转移》敏捷层数。" if weaver else "，安全叠起《能量转移》敏捷层数。")
            ),
            "execution_audit": (
                f"本局实战验货：斯拉克释放《突袭》{pounce_cnt} 次、《黑暗契约》{pact_cnt} 次（KDA {slark['kda']}，英雄伤害 {slark['hero_damage']:,}）。"
            ),
        })

    # 动态英雄专属技能组合生成器（彻底告别无技能名的通用模板，根据本局真实 5 名英雄的专属技能动态合成！）
    if len(combos) < 3:
        p1 = by_pos.get(1) or own_players[0]
        p2 = by_pos.get(2) or own_players[min(1, len(own_players) - 1)]
        p3 = by_pos.get(3) or own_players[min(2, len(own_players) - 1)]
        p4 = by_pos.get(4) or own_players[min(3, len(own_players) - 1)]
        p5 = by_pos.get(5) or own_players[-1]

        def _sig_list(px: Dict[str, Any]) -> List[str]:
            pr = get_hero_profile_126(int(px.get("hero_id") or 0), int(px.get("pos") or 3), px.get("hero_short_zh", ""))
            return pr.get("signature_abilities") or ["核心技能"]

        p1_sigs = _sig_list(p1)
        p2_sigs = _sig_list(p2)
        p3_sigs = _sig_list(p3)
        p4_sigs = _sig_list(p4)
        p5_sigs = _sig_list(p5)

        if len(combos) < 2:
            p4_s0 = p4_sigs[0]
            p2_s0 = p2_sigs[-1]
            p4_c = ab_count(p4, p4_s0)
            p2_c = ab_count(p2, p2_s0)
            combos.append({
                "title": f"【{p4['pos']}号位{p4['hero_short_zh']}《{p4_s0}》游走先手 + {p2['pos']}号位{p2['hero_short_zh']}《{p2_s0}》爆发收割】前中期节奏带动链",
                "window": "4–20分钟 · 河道控符与前中期开雾抓单窗口",
                "heroes": [
                    {"short": p4["hero_short_zh"], "img": p4["hero_img"], "pos": p4["pos"], "personaname": p4["personaname"]},
                    {"short": p2["hero_short_zh"], "img": p2["hero_img"], "pos": p2["pos"], "personaname": p2["personaname"]},
                    {"short": p5["hero_short_zh"], "img": p5["hero_img"], "pos": p5["pos"], "personaname": p5["personaname"]},
                ],
                "how_to_play": (
                    f"前中期节奏铁律：由4号位 {p4['hero_short_zh']} 围绕6/8分钟河道神符与夜晚视野，利用《{p4_s0}》先手留人或破阵，"
                    f"5号位 {p5['hero_short_zh']} 补上《{p5_sigs[0]}》控制/保护，2号位中单 {p2['hero_short_zh']} 第一时间切入倾泻《{p2_s0}》完成定点秒杀，打断敌方核心发育节奏。"
                ),
                "execution_audit": (
                    f"本局实战验货：{p4['hero_short_zh']} 释放《{p4_s0}》{p4_c} 次（参战率 {p4['kill_participation_pct']}%），"
                    f"{p2['hero_short_zh']} 释放《{p2_s0}》{p2_c} 次（参战率 {p2['kill_participation_pct']}%，英雄伤害 {p2['hero_damage']:,}），"
                    f"双辅助整局合计买雾 {(p4.get('smokes_bought') or 0) + (p5.get('smokes_bought') or 0)} 根、插假眼 {(p4.get('obs_placed') or 0) + (p5.get('obs_placed') or 0)} 颗。"
                ),
            })

        p3_s0 = p3_sigs[-1] if len(p3_sigs) > 1 else p3_sigs[0]
        p1_s0 = p1_sigs[-1]
        p3_c = ab_count(p3, p3_s0)
        p1_c = ab_count(p1, p1_s0)
        combos.append({
            "title": f"【{p3['pos']}号位{p3['hero_short_zh']}《{p3_s0}》破阵吃伤 + {p1['pos']}号位{p1['hero_short_zh']}《{p1_s0}》收割 + {p5['pos']}号位{p5['hero_short_zh']}《{p5_sigs[0]}》反手保核】决胜团战链",
            "window": "18分钟至终局 · 肉山团与高地攻坚战",
            "heroes": [
                {"short": p3["hero_short_zh"], "img": p3["hero_img"], "pos": p3["pos"], "personaname": p3["personaname"]},
                {"short": p1["hero_short_zh"], "img": p1["hero_img"], "pos": p1["pos"], "personaname": p1["personaname"]},
                {"short": p5["hero_short_zh"], "img": p5["hero_img"], "pos": p5["pos"], "personaname": p5["personaname"]},
            ],
            "how_to_play": (
                f"团战分工铁律：由3号位 {p3['hero_short_zh']} 顶在第一排释放《{p3_s0}》先手开团并吸收敌方第一波爆发，"
                f"5号位 {p5['hero_short_zh']} 蹲在侧后方用《{p5_sigs[0]}》与微光/推推保护后排，"
                f"1号位大核 {p1['hero_short_zh']} 看准敌方控制技能真空期开启BKB与《{p1_s0}》切入收割残局。"
            ),
            "execution_audit": (
                f"本局实战验货：{p3['hero_short_zh']} 释放《{p3_s0}》{p3_c} 次（承受伤害 {p3.get('hero_damage_taken') or p3.get('damage_taken') or 0:,}），"
                f"{p1['hero_short_zh']} 释放《{p1_s0}》{p1_c} 次（打出 {p1['hero_damage']:,} 英雄伤害与 {p1['tower_damage']:,} 建筑伤害）。"
            ),
        })

    if not is_parsed:
        for cb in combos:
            cb["execution_audit"] = "需要先解析录像"
    for cb in combos:
        cb["evidence"] = "template"
    return combos[:4]


def build_draft_and_combo_analysis(
    radiant_players: List[Dict[str, Any]],
    dire_players: List[Dict[str, Any]],
    match: Dict[str, Any],
    focus_side: str,
) -> Dict[str, Any]:
    """
    生成双方阵容选择诊断报告（包含 radiant 与 dire 双视角，前端切换视角时自动适配）
    """
    rad_scores = compute_team_draft_scores(radiant_players, dire_players)
    dire_scores = compute_team_draft_scores(dire_players, radiant_players)

    dim_names = {
        "init": "先手开团",
        "burst": "瞬间爆发",
        "tf": "阵地团战",
        "push": "推进拆塔",
        "pick": "游走抓人",
        "late": "后期上限",
        "tank": "前排肉度",
    }

    def build_for_side(own: List[Dict[str, Any]], opp: List[Dict[str, Any]], own_s: Dict[str, int], opp_s: Dict[str, int], side_key: str) -> Dict[str, Any]:
        side_zh = "天辉" if side_key == "radiant" else "夜魇"
        opp_zh = "夜魇" if side_key == "radiant" else "天辉"
        own_heroes_str = " + ".join(p["hero_short_zh"] for p in own)
        opp_heroes_str = " + ".join(p["hero_short_zh"] for p in opp)

        own_archs = [get_hero_archetype(p) for p in own]
        opp_archs = [get_hero_archetype(p) for p in opp]
        by_pos_p = {int(p.get("pos") or i + 1): p for i, p in enumerate(own)}
        by_pos_arch = {int(p.get("pos") or i + 1): get_hero_archetype(p) for i, p in enumerate(own)}
        opp_hids = {int(p["hero_id"]): p["hero_short_zh"] for p in opp}
        own_hids = {int(p["hero_id"]): p["hero_short_zh"] for p in own}

        p1 = by_pos_p.get(1, own[0])
        p2 = by_pos_p.get(2, own[min(1, len(own) - 1)])
        p3 = by_pos_p.get(3, own[min(2, len(own) - 1)])
        p1_arch = by_pos_arch.get(1, own_archs[0])
        p2_arch = by_pos_arch.get(2, own_archs[min(1, len(own_archs) - 1)])

        frontliners = [p["hero_short_zh"] for p, a in zip(own, own_archs) if "frontline_tank" in a.get("synergy_tags", []) or a["scores"].get("tank", 50) >= 78]
        squishies = [p["hero_short_zh"] for p, a in zip(own, own_archs) if "squishy_ranged" in a.get("synergy_tags", []) or a["scores"].get("tank", 50) <= 46]

        structural_flaws: List[str] = []
        counter_disadvantages: List[str] = []
        strengths: List[str] = []
        weaknesses: List[str] = []

        # 1) 结构性短板检测
        if "weak_frontal_carry" in p1_arch.get("synergy_tags", []) and "weak_frontal_carry" in p2_arch.get("synergy_tags", []):
            flaw_msg = (
                f"【双远程脆皮游走核、缺正面站桩大核】1号位『{p1['hero_short_zh']}』与2号位『{p2['hero_short_zh']}』同属靠机动抓单与带球偷塔的脆皮远程，"
                f"缺乏传统正面硬刚大核，一旦拖入5v5阵地肉搏或被敌方冲脸切入，正面团战（{own_s['tf']} vs {opp_s['tf']}）与后期硬刚（{own_s['late']} vs {opp_s['late']}）极易断档。"
            )
            structural_flaws.append(flaw_msg)
            weaknesses.append(flaw_msg)
        elif "weak_frontal_carry" in p1_arch.get("synergy_tags", []):
            flaw_msg = (
                f"【一号位非传统正面硬刚大核】1号位『{p1['hero_short_zh']}』偏机动牵制与支援，大后期正面5v5硬刚能力弱于敌方主C，必须靠前中期节奏滚起雪球。"
            )
            structural_flaws.append(flaw_msg)
            weaknesses.append(flaw_msg)

        if len(frontliners) == 0:
            flaw_msg = f"【全队无扎实前排肉盾（前排仅{own_s['tank']}分）】五人普遍身板偏脆，团战无人能顶在视野第一线吃第一波技能，视野一旦落后极易被冲脸融化。"
            structural_flaws.append(flaw_msg)
            weaknesses.append(flaw_msg)
        elif len(frontliners) == 1 and len(squishies) >= 3:
            flaw_msg = (
                f"【单前排孤立无援（4远程/脆皮配单前排）】全队仅靠『{frontliners[0]}』一人顶前排（前排肉度 {own_s['tank']}分），"
                f"其余『{'、'.join(squishies[:4])}』全为脆皮，一旦{frontliners[0]}被先手控制或关住，后排瞬间暴露。"
            )
            structural_flaws.append(flaw_msg)
            weaknesses.append(flaw_msg)

        # 2) 基于真实历史交手 (against_games / against_win) 与分段位胜率的克制检测
        real_bp_stats = compute_real_bp_matchup_stats(own_picks=own, enemy_picks=opp)
        for opp_stat in real_bp_stats.get("enemy_against_stats") or []:
            if not opp_stat.get("insufficient_sample") and opp_stat.get("against_win_rate") is not None:
                if opp_stat["against_win_rate"] < 45.0:
                    cnt_msg = (
                        f"【真实交手克制数据】车队历史对阵『{opp_stat['hero_short_zh']}』累计 {opp_stat['against_games']} 局"
                        f"（{opp_stat['against_win']}胜 {opp_stat['against_losses']}负，胜率 {opp_stat['against_win_rate']}%），需重点针对其核心节奏。"
                    )
                    counter_disadvantages.append(cnt_msg)
                    weaknesses.append(cnt_msg)
        for own_stat in real_bp_stats.get("own_hero_real_stats") or []:
            if not own_stat.get("squad_insufficient_sample") and own_stat.get("squad_win_rate") is not None:
                if own_stat["squad_win_rate"] >= 58.0:
                    strengths.append(
                        f"【车队真实高胜率英雄】『{own_stat['hero_short_zh']}』车队历史 {own_stat['squad_games']} 局 {own_stat['squad_wins']} 胜（胜率 {own_stat['squad_win_rate']}%）。"
                    )

        # 2.5) 逐英雄扫描 5v5 敌我专属机制克制与反克制关系（优先挂载最核心的英雄克制与破局点）
        dur_min = float(match.get("duration") or 2400) / 60.0
        side_won = bool(match.get("radiant_win")) if side_key == "radiant" else not bool(match.get("radiant_win"))
        hero_matchup_matrix: List[Dict[str, Any]] = []
        specific_counter_advs: List[str] = []
        specific_counter_disadvs: List[str] = []
        for op_p in own:
            dossier = build_hero_matchup_dossier(op_p, own, opp, dur_min, side_won)
            dossier["evidence"] = "template"
            dossier["hero_img"] = op_p.get("hero_img", "")
            dossier["personaname"] = op_p.get("personaname", "")
            dossier["kda"] = op_p.get("kda", "")
            hero_matchup_matrix.append(dossier)
            for c_adv in dossier.get("counters_enemies") or []:
                if "克制【" in c_adv or "天克【" in c_adv or "猎杀目标【" in c_adv:
                    msg_a = f"【{op_p['pos']}号位·{op_p['hero_short_zh']}】{c_adv}"
                    if msg_a not in specific_counter_advs:
                        specific_counter_advs.append(msg_a)
            for c_dis in dossier.get("countered_by_enemies") or []:
                if "被【" in c_dis or "受制于【" in c_dis or "提防【" in c_dis:
                    msg_d = f"【{op_p['pos']}号位·{op_p['hero_short_zh']}】{c_dis}"
                    if msg_d not in specific_counter_disadvs:
                        specific_counter_disadvs.append(msg_d)

        for adv_item in reversed(specific_counter_advs[:3]):
            strengths.insert(0, adv_item)
        for dis_item in specific_counter_disadvs[:3]:
            if dis_item not in weaknesses:
                weaknesses.insert(0, dis_item)

        # 3) 自动诊断阵容优势
        if own_s["push"] >= 82 or own_s["push"] - opp_s["push"] >= 8:
            strengths.append(
                f"【推进牵制与拆塔速度占优 ({own_s['push']} vs {opp_s['push']})】阵容具备较强的兵线牵制与建筑消耗能力，一旦赢下局部碰撞或抓死人，拆外塔效率高于{opp_zh}。"
            )
        if own_s["init"] >= 84 or own_s["init"] - opp_s["init"] >= 5:
            strengths.append(
                f"【先手开团与点控留人稳定 ({own_s['init']} vs {opp_s['init']})】具备可靠的瞬发点控/团控先手，中期开雾找节奏的主动权较清晰。"
            )
        if own_s["burst"] >= 85:
            strengths.append(
                f"【瞬间爆发秒人线高 ({own_s['burst']}分)】控制接高额爆发可在敌方开出BKB或救人技能前完成定点秒杀。"
            )
        if own_s["tf"] >= 85 and own_s["tf"] >= opp_s["tf"]:
            strengths.append(
                f"【五人阵地团战上限高 ({own_s['tf']} vs {opp_s['tf']})】拥有高价值团控大招与AOE反手，肉山团与高地攻坚战容错率高。"
            )
        if own_s["tank"] >= 82:
            strengths.append(
                f"【前排肉度扎实 ({own_s['tank']}分)】前排冲脸吃伤害能力强，能为后排核心撑起输出空间。"
            )
        if len(strengths) < 2:
            strengths.append(
                f"【局部游走抓人与支援机动性不错 ({own_s['pick']}分)】小规模Gank配合紧凑，可通过多打少抓单来弥补5v5正面团战短板。"
            )
        if len(weaknesses) < 2:
            if own_s["push"] <= 68:
                weaknesses.append(
                    f"【持续磨高地能力偏弱 ({own_s['push']}分)】缺乏远程无伤磨塔手段，中期打赢团若不果断推外塔，后期上高地会非常依赖肉山盾。"
                )
            else:
                weaknesses.append(
                    "【中期关键保命装（BKB/推推/微光）真空期怕被强冲】12~22分钟核心装未成型前，分路带线过深容易被敌方开雾突破。"
                )

        # 4) 科学、自洽的阵容评级（绝不出现“极其考验执行却给A级”的矛盾评价）
        avg_own = sum(own_s.values()) / len(own_s)
        avg_opp = sum(opp_s.values()) / len(opp_s)
        diff = avg_own - avg_opp
        total_flaws = len(structural_flaws) + len(counter_disadvantages)

        if avg_own >= 80 and diff >= 3 and total_flaws == 0:
            grade = "S 级 · 体系完备且先天克制对手"
        elif avg_own >= 75 and diff >= 0 and total_flaws == 0:
            grade = "A 级 · 攻守兼备 · 团战与推进容错率高"
        elif avg_own >= 72 and total_flaws <= 1 and diff >= -2.5:
            grade = "B+ 级 · 局部支点明确但存在结构短板"
        elif total_flaws >= 2 or diff <= -4.5:
            grade = "C+ 级 · 阵容结构偏科且正面被对手克制（容错率极低）"
        else:
            grade = "B 级 · 偏科走钢丝 · 容错率偏低且极其考验执行"

        # 5) 动态生成与评级完全匹配的 verdict_summary
        sorted_adv = sorted(
            ("init", "burst", "tf", "push", "pick", "late", "tank"),
            key=lambda k: (own_s[k] - opp_s[k], own_s[k]),
            reverse=True,
        )
        sorted_dis = sorted(
            ("init", "burst", "tf", "push", "pick", "late", "tank"),
            key=lambda k: (own_s[k] - opp_s[k], own_s[k]),
        )
        best1, best2 = sorted_adv[0], sorted_adv[1]
        worst1, worst2 = sorted_dis[0], sorted_dis[1]

        if grade.startswith("S") or grade.startswith("A"):
            verdict_summary = (
                f"{side_zh}这套『{own_heroes_str}』迎战{opp_zh}『{opp_heroes_str}』，阵容结构均衡扎实："
                f"在【{dim_names[best1]} ({own_s[best1]} vs {opp_s[best1]})】与【{dim_names[best2]} ({own_s[best2]} vs {opp_s[best2]})】上占优，"
                f"前排、控制与输出衔接自然，正面5v5团战容错率高，只要稳扎稳打控盾推塔即可拿下比赛。"
            )
        elif grade.startswith("B+"):
            verdict_summary = (
                f"{side_zh}这套『{own_heroes_str}』迎战{opp_zh}『{opp_heroes_str}』，"
                f"虽然在【{dim_names[best1]} ({own_s[best1]} vs {opp_s[best1]})】与【{dim_names[best2]} ({own_s[best2]} vs {opp_s[best2]})】上具备明确支点，"
                f"但在【{dim_names[worst1]} ({own_s[worst1]} vs {opp_s[worst1]})】上存在局部短板，中期需主动带起开雾推塔节奏，避免陷入被动防守。"
            )
        else:
            flaw_brief = (
                f"『{p1['hero_short_zh']}+{p2['hero_short_zh']}』双远程脆皮游走核配『{p3['hero_short_zh']}』单前排，正面硬刚与抗冲脸能力严重不足"
                if ("weak_frontal_carry" in p1_arch.get("synergy_tags", []) and "weak_frontal_carry" in p2_arch.get("synergy_tags", []))
                else f"在【{dim_names[worst1]} ({own_s[worst1]} vs {opp_s[worst1]})】与【{dim_names[worst2]} ({own_s[worst2]} vs {opp_s[worst2]})】上处于明显劣势"
            )
            counter_brief = (
                f"，且历史交手胜率偏低（{counter_disadvantages[0]}）"
                if counter_disadvantages
                else ""
            )
            verdict_summary = (
                f"{side_zh}这套『{own_heroes_str}』迎战{opp_zh}『{opp_heroes_str}』属于典型的偏科走钢丝阵容："
                f"仅在【{dim_names[best1]} ({own_s[best1]} vs {opp_s[best1]})】上有局部支点，但{flaw_brief}{counter_brief}；"
                f"正面5v5团战（{own_s['tf']} vs {opp_s['tf']}）容错率极低，完全仰仗带线牵制、抓落单与后排保命装的极限执行。"
            )

        return {
            "evidence": "template",
            "conclusions": [{"text": verdict_summary, "kind": "draft_verdict", "evidence": "template"}],
            "side": side_key,
            "side_zh": side_zh,
            "lineup_str": own_heroes_str,
            "opp_lineup_str": opp_heroes_str,
            "grade": grade,
            "scores": own_s,
            "opp_scores": opp_s,
            "verdict_summary": verdict_summary,
            "strengths": strengths[:4],
            "weaknesses": weaknesses[:4],
            "real_data_bp_stats": real_bp_stats,
            "combos": build_team_combos(own, opp, is_parsed=bool(match.get("version"))),
            "hero_matchup_matrix": hero_matchup_matrix,
            "heroes_brief": [
                {
                    "pos": p["pos"],
                    "pos_label": p["pos_label"],
                    "hero_short_zh": p["hero_short_zh"],
                    "hero_img": p["hero_img"],
                    "personaname": p["personaname"],
                    "is_me": p.get("is_me", False),
                    "roles": get_hero_archetype(p)["roles"],
                    "kda": p["kda"],
                }
                for p in own
            ],
        }

    return {
        "radiant": build_for_side(radiant_players, dire_players, rad_scores, dire_scores, "radiant"),
        "dire": build_for_side(dire_players, radiant_players, dire_scores, rad_scores, "dire"),
    }


def enrich_phases_with_evaluations(
    phases_data: List[Dict[str, Any]],
    all_formatted_players: List[Dict[str, Any]],
    grok_coaching: Optional[Dict[str, Any]],
    is_parsed: bool = True,
) -> List[Dict[str, Any]]:
    """
    为前期对线 (0-10m) / 中期运营 (10-25m) / 后期决策 (25m+) 的每一位玩家生成：
    - assessment (阶段总结)
    - good (这一阶段哪里做得好，列表)
    - bad (这一阶段哪里做得不好/犯病点，列表)
    - focus (下把这一阶段怎么改)
    同时为整个团队生成每个阶段的「团队做得好」「团队病根」「团队怎么进步」作业本！
    如果 Grok 已经生成了 phases 评价，则智能融合 Grok 的洞察与录像硬指标。
    """
    if not is_parsed:
        for pd in phases_data:
            pd["available"] = False
            pd["evidence"] = "measured"
            pd["source_fields"] = ["version"]
            pd["conclusions"] = []
            for pp in pd.get("players") or []:
                pp["evidence"] = "measured"
                pp["source_fields"] = ["version"]
                pp["conclusions"] = []
                pp["assessment"] = "需要先解析录像"
                pp["good"] = []
                pp["bad"] = []
                pp["focus"] = "需要先解析录像"
            pd["team_diagnostics"] = {
                "radiant": {
                    "available": False,
                    "evidence": "measured",
                    "source_fields": ["version"],
                    "summary": "需要先解析录像",
                    "turning_point": "",
                    "team_good": "需要先解析录像",
                    "team_bad": "需要先解析录像",
                    "team_action": "",
                },
                "dire": {
                    "available": False,
                    "evidence": "measured",
                    "source_fields": ["version"],
                    "summary": "需要先解析录像",
                    "turning_point": "",
                    "team_good": "需要先解析录像",
                    "team_bad": "需要先解析录像",
                    "team_action": "",
                },
            }
        return phases_data
    # 建立 Grok 阶段评价索引: grok_phase_map[phase_key] = {summary, turning_point, player_by_slot: {slot: {...}}}
    grok_phase_map: Dict[str, Dict[str, Any]] = {}
    if isinstance(grok_coaching, dict):
        raw_gphases = grok_coaching.get("phases")
        if isinstance(raw_gphases, list):
            for gp in raw_gphases:
                if isinstance(gp, dict) and gp.get("key"):
                    p_by_slot = {}
                    for pp in gp.get("players") or []:
                        if isinstance(pp, dict) and pp.get("slot") is not None:
                            p_by_slot[int(pp["slot"])] = pp
                    grok_phase_map[gp["key"]] = {
                        "summary": gp.get("summary") or "",
                        "turning_point": gp.get("turning_point") or "",
                        "players": p_by_slot,
                    }
        elif isinstance(raw_gphases, dict):
            for pkey, gp in raw_gphases.items():
                if isinstance(gp, dict):
                    p_by_slot = {}
                    raw_pl = gp.get("players")
                    if isinstance(raw_pl, list):
                        for pp in raw_pl:
                            if isinstance(pp, dict) and pp.get("slot") is not None:
                                p_by_slot[int(pp["slot"])] = pp
                    elif isinstance(raw_pl, dict):
                        for sk, pp in raw_pl.items():
                            try:
                                p_by_slot[int(sk)] = pp if isinstance(pp, dict) else {"assessment": str(pp)}
                            except Exception:
                                pass
                    grok_phase_map[pkey] = {
                        "summary": gp.get("summary") or "",
                        "turning_point": gp.get("turning_point") or "",
                        "players": p_by_slot,
                    }

    full_player_by_slot = {int(p["player_slot"]): p for p in all_formatted_players}

    for pd in phases_data:
        pkey = pd.get("key", "lane")
        plabel = pd.get("label", "")
        tlabel = pd.get("time_label", "")
        g_phase = grok_phase_map.get(pkey, {})
        raw_phase_sec = max(0, int(pd.get("end_sec") or 0) - int(pd.get("start_sec") or 0))
        raw_phase_min = raw_phase_sec / 60.0
        phase_min = max(1.0, raw_phase_min)

        if pkey == "late" and raw_phase_min < 5.0:
            pd["available"] = False
            short_late_msg = f"25 分钟后仅持续 {raw_phase_min:.1f} 分钟（不足 5 分钟），不输出阶段判词。"
            pd["evidence"] = "measured"
            pd["source_fields"] = ["duration"]
            pd["conclusions"] = [
                {
                    "text": short_late_msg,
                    "kind": "phase_summary",
                    "evidence": "measured",
                    "source_fields": ["duration"],
                }
            ]
            for pp in pd.get("players") or []:
                slot = int(pp.get("slot", 0))
                full_p = full_player_by_slot.get(slot) or {}
                hmp = full_p.get("hero_mechanism_profile") or {}
                pp["timing_curve_zh"] = hmp.get("timing_curve_zh") or ""
                pp["evidence"] = "measured"
                pp["source_fields"] = ["duration"]
                pp["conclusions"] = []
                pp["assessment"] = short_late_msg
                pp["good"] = []
                pp["bad"] = []
                pp["focus"] = ""
            pd["team_diagnostics"] = {
                "radiant": {
                    "available": False,
                    "evidence": "measured",
                    "source_fields": ["duration"],
                    "summary": short_late_msg,
                    "turning_point": "",
                    "team_good": "",
                    "team_bad": "",
                    "team_action": "",
                },
                "dire": {
                    "available": False,
                    "evidence": "measured",
                    "source_fields": ["duration"],
                    "summary": short_late_msg,
                    "turning_point": "",
                    "team_good": "",
                    "team_bad": "",
                    "team_action": "",
                },
            }
            continue

        for pp in pd.get("players") or []:
            slot = int(pp.get("slot", 0))
            pos = int(pp.get("pos") or 3)
            short = pp.get("hero_short_zh") or "该英雄"
            kills = int(pp.get("kills_count") or 0)
            deaths = int(pp.get("deaths_count") or 0)
            gold_gain = int(pp.get("gold_gain") or 0)
            gpm_p = float(pp.get("gpm_phase") or 0.0)
            lh_gain = int(pp.get("lh_gain") or 0)
            dn_gain = int(pp.get("dn_gain") or 0)
            raw_hd_gain = pp.get("hero_damage_gain")
            has_hd_data = raw_hd_gain is not None
            hd_gain = int(raw_hd_gain or 0)
            td_gain = int(pp.get("tower_damage_gain") or 0)
            obs_p = int(pp.get("obs_placed") or 0)
            sen_p = int(pp.get("sen_placed") or 0)
            items_b = pp.get("items_bought") or []
            _consumable_names = ("诡计之雾", "显影之尘", "侦察守卫", "岗哨守卫", "回城卷轴", "净化药水", "魔法芒果", "治疗药膏", "树之祭祀", "腥红榴弹", "仙灵之火")
            equip_b = [
                it
                for it in items_b
                if not any(cn in str(it.get("zh_name") or "") for cn in _consumable_names)
            ]
            items_str = "、".join(f"{it['time_str']} {it['zh_name']}" for it in equip_b[:4])
            death_times = [f"{d['time_str']}(被{d.get('killer','敌方')}击杀)" for d in (pp.get("deaths_events") or [])]
            kill_times = [f"{k['time_str']}(杀{k.get('victim_hero','敌方')})" for k in (pp.get("kills_events") or [])]

            good_list: List[str] = []
            bad_list: List[str] = []
            ph_item_meta: Dict[str, Tuple[str, Optional[List[str]]]] = {}

            def _add_ph_item(
                bucket: List[str],
                txt: str,
                ev: str,
                source_fields: Optional[List[str]] = None,
                prepend: bool = False,
            ) -> None:
                ph_item_meta[txt] = (ev, list(source_fields) if (ev == "measured" and source_fields) else None)
                if prepend:
                    bucket.insert(0, txt)
                else:
                    bucket.append(txt)

            focus_tip = ""

            full_p = full_player_by_slot.get(slot) or {}
            pt_meta = full_p.get("phase_telemetry") or {}
            solo_picks = pt_meta.get("solo_pickoffs") or []
            phoenix_audit = full_p.get("phoenix_egg_audit")
            is_turret_ok = bool(full_p.get("is_turret_fulfilled"))
            hmp = full_p.get("hero_mechanism_profile") or {}
            t_curve = hmp.get("timing_curve") or ""
            t_curve_zh = hmp.get("timing_curve_zh") or ""
            early_farm_ok = bool(hmp.get("early_farm_reasonable"))
            late_harvest_ok = bool(hmp.get("late_harvest_fulfilled"))
            late_harvest_fail = bool(hmp.get("late_harvest_failed"))
            mid_tempo_bad = bool(hmp.get("mid_tempo_wasted"))
            pp["timing_curve_zh"] = t_curve_zh

            # 1. 前期对线 (00:00–10:00) 规则诊断
            if pkey == "lane":
                if pos in (1, 2):
                    if lh_gain >= 50:
                        _add_ph_item(
                            good_list,
                            f"对线基本功扎实（{t_curve_zh or '核心'}）：前10分钟斩获 {lh_gain} 正补 / {dn_gain} 反补，阶段 GPM 高达 {gpm_p:.0f}，无解肥发育。",
                            "measured",
                            ["players[].lh_t", "players[].dn_t", "players[].gold_t"],
                        )
                    elif lh_gain >= 38:
                        _add_ph_item(
                            good_list,
                            f"抗压补刀合格（{t_curve_zh or '核心'}）：10分钟补出 {lh_gain} 正补 / {dn_gain} 反补（经济 +{gold_gain:,}），稳住了核心发育线。",
                            "measured",
                            ["players[].lh_t", "players[].dn_t", "players[].gold_t"],
                        )
                    elif t_curve == "late_hyper_carry" and lh_gain >= 32 and deaths <= 1:
                        _add_ph_item(
                            good_list,
                            f"大核对线隐忍抗压（{t_curve_zh}）：前期身板弱势情况下稳住 {lh_gain} 补刀（+{gold_gain:,} 金），成功过渡至刷钱装。",
                            "inferred",
                        )
                    else:
                        _add_ph_item(
                            bad_list,
                            f"对线补刀严重不达标：作为 {pos} 号位（{t_curve_zh or '核心'}）前10分钟仅有 {lh_gain} 刀（经济 +{gold_gain:,}），早期发育直接断档。",
                            "inferred",
                        )
                elif pos == 3:
                    if lh_gain >= 32:
                        _add_ph_item(
                            good_list,
                            f"劣势路占线出色（{t_curve_zh or '三号位'}）：10分钟补刀 {lh_gain}/{dn_gain}，打出 {hd_gain:,} 对线消耗伤害。",
                            "measured",
                            ["players[].lh_t", "players[].dn_t", "teamfights[].players[].damage"],
                        )
                    else:
                        _add_ph_item(
                            bad_list,
                            f"劣势路混线艰难：10分钟仅 {lh_gain} 补刀（阶段 GPM {gpm_p:.0f}），未能压制敌方优势路大哥。",
                            "inferred",
                        )
                else:
                    # 4/5 号位辅助
                    if kills >= 1 or hd_gain >= 2200:
                        _add_ph_item(
                            good_list,
                            f"线上消耗与游走积极（{t_curve_zh or '辅助'}）：前期打出 {hd_gain:,} 英雄伤害" + (f"，在 {', '.join(kill_times)} 拿人头打开局面。" if kill_times else "，有效压低了敌方血量。"),
                            "inferred",
                        )
                    if obs_p + sen_p >= 3:
                        _add_ph_item(
                            good_list,
                            f"前期视野勤勉：前10分钟插下 {obs_p} 假眼 / {sen_p} 真眼保障线眼与抢符视野。",
                            "measured",
                            ["players[].obs_log", "players[].sen_log"],
                        )
                    elif obs_p + sen_p == 0 and pos == 5:
                        _add_ph_item(bad_list, "对线期 0 真假眼记录：线上既没封敌方野店也没给中路补保护眼。", "inferred")

                if deaths == 0:
                    _add_ph_item(
                        good_list,
                        "对线期保持 0 阵亡，没有给对位英雄送出任何额外提款。",
                        "measured",
                        ["players[].deaths_log"],
                    )
                elif deaths >= 2:
                    _add_ph_item(
                        bad_list,
                        f"对线期连续阵亡 {deaths} 次（{', '.join(death_times)}），直接养肥了对位核心并亏损大量兵线经验。",
                        "inferred",
                    )
                elif deaths == 1:
                    _add_ph_item(bad_list, f"在 {death_times[0]} 阵亡 1 次，断了一波线上节奏与补给。", "inferred")

                if items_str and not good_list:
                    _add_ph_item(good_list, f"按部就班做出前期过渡装：{items_str}。", "measured", ["players[].purchase_log"])
                if not bad_list:
                    _add_ph_item(bad_list, f"前10分钟推塔伤害为 {td_gain:,}，对线期拿到优势后未能进一步磨掉敌方一塔血量。", "inferred")

                focus_tip = (
                    f"前期改进重点（{hmp.get('early_rule') or ('注意 3 分钟莲花与 6 分钟河道动力符时间点，残血及时补大药别硬拼送人头。' if deaths >= 1 else '保持当前补刀手感，6级后主动呼叫辅助打第一波推进或支援。')}）"
                )

            # 2. 中期运营 (10:00–25:00) 规则诊断
            elif pkey == "mid":
                if pos in (1, 2):
                    if early_farm_ok:
                        _add_ph_item(
                            good_list,
                            f"刷核发育期合理避战（{t_curve_zh}）：前中期弱势期不盲目接劣势团，15分钟内高速刷出 +{gold_gain:,} 金（阶段 GPM {gpm_p:.0f}，补刀 +{lh_gain}）"
                            + (f"，加速成型 {items_str} 为后期出山收割奠定基础。" if items_str else "，为后期出山收割奠定基础。"),
                            "inferred",
                            prepend=True,
                        )
                    elif gpm_p >= 580:
                        _add_ph_item(
                            good_list,
                            f"中期刷钱效率拉满：15分钟内经济狂涨 +{gold_gain:,}（阶段 GPM {gpm_p:.0f}，补刀 +{lh_gain}）" + (f"，顺利掏出 {items_str}。" if items_str else "。"),
                            "measured",
                            ["players[].gold_t", "players[].lh_t", "players[].purchase_log"],
                        )
                    elif gpm_p < 420:
                        _add_ph_item(
                            bad_list,
                            f"中期刷钱节奏断档：10~25分钟阶段 GPM 仅有 {gpm_p:.0f}（经济 +{gold_gain:,}），核心装备成型过慢。",
                            "inferred",
                        )
                    if hd_gain >= 8000:
                        _add_ph_item(
                            good_list,
                            f"中期团战火力支柱：单阶段轰出 {hd_gain:,} 英雄伤害并斩获 {kills} 个人头。",
                            "measured",
                            ["teamfights[].players[].damage", "players[].kills_log"],
                        )
                    elif mid_tempo_bad:
                        _add_ph_item(
                            bad_list,
                            f"中期干架强势期失职（{t_curve_zh}）：10~25m 本该带队抓人逼塔，却当大核闷头刷钱（阶段 +{gold_gain:,} 金仅打 {hd_gain:,} 伤害），白白浪费英雄最强节奏窗！",
                            "inferred",
                            prepend=True,
                        )
                    elif hd_gain < 4000 and not early_farm_ok:
                        _add_ph_item(
                            bad_list,
                            f"中期打架参与度偏低：15分钟内仅打出 {hd_gain:,} 英雄伤害，队友正面接团时输出存在真空。",
                            "inferred",
                        )
                elif pos == 3:
                    if items_str:
                        _add_ph_item(
                            good_list,
                            f"中期关键先手/团队装成型（{t_curve_zh or '三号位'}）：{items_str}，阶段打出 {hd_gain:,} 伤害与 {kills} 次击杀。",
                            "measured",
                            ["players[].purchase_log", "teamfights[].players[].damage", "players[].kills_log"],
                        )
                    if td_gain >= 1000:
                        _add_ph_item(good_list, f"中期主动带队逼塔，造成 {td_gain:,} 点建筑伤害。", "measured", ["objectives", "players[].tower_damage"])
                else:
                    # 4/5 号位
                    if obs_p + sen_p >= 6:
                        _add_ph_item(
                            good_list,
                            f"中期视野铺设到位：10~25分钟插下 {obs_p} 颗假眼与 {sen_p} 颗真眼，努力支撑团队视野。",
                            "measured",
                            ["players[].obs_log", "players[].sen_log"],
                        )
                    if kills >= 2 or hd_gain >= 4500:
                        _add_ph_item(
                            good_list,
                            f"中期接团技能释放果断：阶段贡献 {kills} 杀与 {hd_gain:,} 伤害" + (f"（出装：{items_str}）。" if items_str else "。"),
                            "measured",
                            ["players[].kills_log", "teamfights[].players[].damage", "players[].purchase_log"],
                        )

                mid_solos = [
                    (f"{s.get('time_str')} 被 {s.get('killer','敌方')} 击杀" if isinstance(s, dict) else str(s))
                    for s in solo_picks
                    if 600 <= int(s.get("time", 0) if isinstance(s, dict) else int(str(s).split(":")[0]) * 60) < 1500
                ]
                if mid_solos:
                    _add_ph_item(
                        bad_list,
                        f"中期团战外阵亡：{'、'.join(mid_solos)}。",
                        "inferred",
                        prepend=True,
                    )

                if deaths == 0:
                    _add_ph_item(good_list, "中期 15 分钟保持 0 阵亡，走位与防抓单警觉性极高！", "inferred")
                elif deaths >= 4:
                    _add_ph_item(
                        bad_list,
                        f"中期阵亡偏多：15分钟内阵亡 {deaths} 次（{', '.join(death_times[:4])}）。",
                        "measured",
                        ["players[].deaths_log"],
                    )
                elif deaths >= 2 and not mid_solos:
                    _add_ph_item(bad_list, f"中期阵亡 {deaths} 次（{', '.join(death_times)}）。", "measured", ["players[].deaths_log"])

                if not good_list:
                    _add_ph_item(
                        good_list,
                        f"中期稳步过渡，经济增量 +{gold_gain:,}，造成 {hd_gain:,} 伤害。",
                        "measured",
                        ["players[].gold_t", "teamfights[].players[].damage"],
                    )
                if not bad_list:
                    _add_ph_item(bad_list, "中期赢下小规模遭遇战后转推外塔或压制敌方野区不够果断。", "template")

                focus_tip = (
                    f"中期改进重点（{hmp.get('mid_rule') or ('第一件关键装成形后围绕队友抱团推进，减少无视野深带。' if (deaths >= 3 or mid_solos) else '中期打赢团战后及时集合推进外塔与压制野区。')}）"
                )

            # 3. 后期决策 (25分钟–终局) 规则诊断
            else:
                late_hdmg_pct_val = pt_meta.get("late_hdmg_share_pct")
                late_gold_pct_val = pt_meta.get("late_gold_share_pct")
                late_hdmg_pct_str = f"{late_hdmg_pct_val}%" if late_hdmg_pct_val is not None else "无数据"
                late_gold_pct_str = f"{late_gold_pct_val}%" if late_gold_pct_val is not None else "无数据"
                dmg_per_death_val = full_p.get("dmg_per_death")
                dmg_per_death_str = f"{int(dmg_per_death_val):,}" if dmg_per_death_val is not None else "无数据"

                if late_harvest_ok:
                    _add_ph_item(
                        good_list,
                        f"大核出山收割完全兑现（{t_curve_zh}）：前中期闭关刷钱成型后，25m+ 决胜期轰出 {hd_gain:,} 英雄伤害（占全队 {late_hdmg_pct_str}）与 {td_gain:,} 推塔伤害，完美回馈团队空间！",
                        "inferred",
                        prepend=True,
                    )
                elif hd_gain >= 12000 or kills >= 5:
                    _add_ph_item(
                        good_list,
                        f"后期决战火力全开：单阶段砍下 {kills} 杀、轰出 {hd_gain:,} 英雄伤害" + (f"，更新 {items_str}。" if items_str else "。"),
                        "measured",
                        ["players[].kills_log", "teamfights[].players[].damage", "players[].purchase_log"],
                    )
                if is_turret_ok:
                    _add_ph_item(
                        good_list,
                        f"炮台法核输出职责兑现（{t_curve_zh}）：后期顶着敌方强切入轰出 {hd_gain:,} 英雄伤害（全场每死换出 {dmg_per_death_str} 伤害），死前把爆发倾泻拉满！",
                        "inferred",
                        prepend=True,
                    )
                if hmp.get("sacrificial_initiator_fulfilled"):
                    stun_clause = (
                        f"贡献 {full_p.get('stuns_sec')} 秒硬控并"
                        if (full_p.get("stuns_sec") is not None and float(full_p.get("stuns_sec") or 0) > 0)
                        else ""
                    )
                    _add_ph_item(
                        good_list,
                        f"前排先手开团与承伤兑现（{t_curve_zh}）：全场{stun_clause}抗下全队 {full_p.get('damage_taken_share_pct') or 0}% 伤害，果断肉身开团为后排创造输出空间！",
                        "inferred",
                        prepend=True,
                    )
                if hmp.get("save_support_fulfilled"):
                    _add_ph_item(
                        good_list,
                        f"救人续航辅助职责兑现（{t_curve_zh}）：关键团战倾力提供救人技能与 {full_p.get('hero_healing', 0):,} 点英雄治疗，尽心尽力兜底大哥！",
                        "inferred",
                        prepend=True,
                    )
                if td_gain >= 3500 and not late_harvest_ok:
                    _add_ph_item(
                        good_list,
                        f"高地拆迁绝对主力：后期独自轰出 {td_gain:,} 点建筑伤害，打赢团战后拆塔破路毫不手软！",
                        "measured",
                        ["players[].tower_damage", "objectives"],
                    )
                if pos in (4, 5) and (obs_p + sen_p >= 5 or items_str):
                    _add_ph_item(
                        good_list,
                        f"后期辅助尽职尽责：插下 {obs_p} 假眼 / {sen_p} 真眼" + (f"，做出 {items_str} 保护核心。" if items_str else "。"),
                        "measured",
                        ["players[].obs_log", "players[].sen_log", "players[].purchase_log"],
                    )

                if late_harvest_fail:
                    _add_ph_item(
                        bad_list,
                        f"后期出山收割断档（{t_curve_zh}）：25m+ 吃下 +{gold_gain:,} 金（占全队 {late_gold_pct_str}），却仅打出 {hd_gain:,} 伤害（占全队 {late_hdmg_pct_str}），前中期刷的资源未能转化为决胜团战收割！",
                        "inferred",
                        prepend=True,
                    )

                if hmp.get("missing_mandatory_shard"):
                    _add_ph_item(
                        bad_list,
                        f"整局拒出 1400 金质变魔晶（{hmp.get('shard_desc', '核心技能机制加强')}），后期团战少一个关键救人/切入/输出机制！",
                        "inferred",
                    )

                if deaths == 0:
                    _add_ph_item(good_list, "后期决胜阶段 0 阵亡，团战拉扯与切入时机无懈可击！", "inferred")
                elif deaths >= 3 and not is_turret_ok and not hmp.get("sacrificial_initiator_fulfilled"):
                    _add_ph_item(
                        bad_list,
                        f"后期阶段阵亡 {deaths} 次（{', '.join(death_times[:4])}），读秒时间偏长。",
                        "measured",
                        ["players[].deaths_log"],
                    )
                elif deaths >= 1:
                    if pp.get("buybacks"):
                        _add_ph_item(
                            bad_list,
                            f"后期阵亡 {deaths} 次（{', '.join(death_times)}），并交出 {pp.get('buybacks',0)} 次买活。",
                            "measured",
                            ["players[].deaths_log", "players[].buyback_log"],
                        )
                    else:
                        _add_ph_item(
                            bad_list,
                            f"后期阵亡 {deaths} 次（{', '.join(death_times)}），后期高地/肉山团站位与自保装需更到位。",
                            "inferred",
                        )

                if has_hd_data and pos in (1, 2, 3) and hd_gain < phase_min * 600.0 and not late_harvest_fail and not hmp.get("sacrificial_initiator_fulfilled"):
                    _add_ph_item(
                        bad_list,
                        f"后期团战输出匮乏：25分钟后吃下 +{gold_gain:,} 金却仅打出 +{hd_gain:,} 英雄伤害，未能承担核心收割职责。",
                        "inferred",
                    )

                if not good_list:
                    _add_ph_item(
                        good_list,
                        f"后期阶段贡献 {kills} 杀、经济 +{gold_gain:,}、英雄伤害 +{hd_gain:,}。",
                        "measured",
                        ["players[].kills_log", "players[].gold_t", "teamfights[].players[].damage"],
                    )
                if not bad_list:
                    _add_ph_item(bad_list, "后期上高地与买活反打阶段需要更严格地盯防敌方先手与买活反扑。", "template")

                if is_turret_ok:
                    focus_tip = "后期改进重点：炮台法核输出已拉满，面对敌方强留人/框人控制时可补出《飓风长戟（大推推）》推开自己自救！"
                elif hmp.get("late_rule"):
                    focus_tip = f"后期改进重点（{hmp.get('late_rule')}）"
                else:
                    focus_tip = "后期改进重点：25分钟后严格遵守『带盾上高地、差钱留买活、抱团抓信息差』三大铁律，后排辅助务必站在大哥侧后方树林蹲反手。"

            default_assessment = (
                f"{tlabel} 阶段斩获 {kills} 杀 {deaths} 死，经济 +{gold_gain:,} (GPM {gpm_p:.0f})，英雄伤害 +{hd_gain:,}，推塔 +{td_gain:,}。"
            )

            # 融合 Grok 阶段个人评价 (若存在且匹配该 slot)
            g_p = (g_phase.get("players") or {}).get(slot)
            if isinstance(g_p, dict):
                pp["assessment"] = g_p.get("assessment") or default_assessment
                g_good = [x for x in (g_p.get("good") or []) if x]
                g_bad = [x for x in (g_p.get("bad") or []) if x]
                merged_good = g_good + [x for x in good_list if x not in g_good]
                merged_bad = g_bad + [x for x in bad_list if x not in g_bad]
                pp["good"] = merged_good[:3]
                pp["bad"] = merged_bad[:3]
                pp["focus"] = g_p.get("focus") or focus_tip
            else:
                pp["assessment"] = default_assessment
                pp["good"] = good_list[:3]
                pp["bad"] = bad_list[:3]
                pp["focus"] = focus_tip

            pp_conclusions: List[Dict[str, Any]] = []
            for kind_k, seq_k in (("good", pp["good"][:1]), ("bad", pp["bad"][:1])):
                for item_t in seq_k:
                    t_clean = str(item_t or "").strip()
                    if not t_clean:
                        continue
                    ev_t, sf_t = ph_item_meta.get(t_clean, ("inferred", None))
                    c_entry: Dict[str, Any] = {"text": t_clean, "kind": kind_k, "evidence": ev_t}
                    if ev_t == "measured" and sf_t:
                        c_entry["source_fields"] = list(sf_t)
                    pp_conclusions.append(c_entry)
            pp["evidence"] = "inferred"
            pp["conclusions"] = pp_conclusions

        # 为该阶段的 radiant 和 dire 双方分别生成「团队本阶段复盘与进步指南」
        team_diagnostics = {}
        for side_k in ("radiant", "dire"):
            side_zh = "天辉" if side_k == "radiant" else "夜魇"
            s_players = [p for p in (pd.get("players") or []) if p.get("side") == side_k]
            o_players = [p for p in (pd.get("players") or []) if p.get("side") != side_k]
            s_kills = sum(int(p.get("kills_count") or 0) for p in s_players)
            o_kills = sum(int(p.get("kills_count") or 0) for p in o_players)
            s_obs = sum(int(p.get("obs_placed") or 0) for p in s_players)
            s_sen = sum(int(p.get("sen_placed") or 0) for p in s_players)
            s_td = sum(int(p.get("tower_damage_gain") or 0) for p in s_players)
            top_g = sorted(s_players, key=lambda x: x.get("gold_gain") or 0, reverse=True)[0] if s_players else None
            most_d = sorted(s_players, key=lambda x: x.get("deaths_count") or 0, reverse=True)[0] if s_players else None
            top_g_name = top_g["hero_short_zh"] if top_g else "主核"
            top_g_lh = int((top_g.get("lh_gain") if top_g else 0) or 0)
            top_g_gold = int((top_g.get("gold_gain") if top_g else 0) or 0)
            most_d_name = most_d["hero_short_zh"] if most_d else "队友"
            most_d_cnt = int((most_d.get("deaths_count") if most_d else 0) or 0)

            if pkey == "lane":
                t_good = (
                    f"1号位/核心（{top_g_name}）前10分钟补出 {top_g_lh} 刀稳住了基本盘，全队打出 {s_kills}:{o_kills} 人头交换。"
                )
                t_bad = (
                    f"{most_d_name} 在对线期阵亡 {most_d_cnt} 次成为早期突破口，全队前10分钟未能率先拔掉敌方外塔。"
                    if most_d_cnt >= 2
                    else "三路对线虽然稳住，但双辅助游走中路与抢 6 分钟河道神符的联动压制力还不够紧凑。"
                )
                t_action = (
                    "【前期团队怎么进步 (0–10分钟)】：① 3分钟边路莲花与 6分钟/8分钟河道动力符必须由 4 号位提前 15 秒靠过去配合中单控下；"
                    "② 优势路 5 号位前 5 分钟以拉野消兵、保 1 号位无解肥补刀为第一铁律，别盲目TP支援导致大哥线被冲；"
                    "③ 一旦中单或三号位到 6 级有大招，立刻带辅助推掉敌方优势路一塔解放野区。"
                )
            elif pkey == "mid":
                t_good = (
                    f"主核 {top_g_name} 在 10~25 分钟保持 +{top_g_gold:,} 高速发育，全队插下 {s_obs} 假眼 / {s_sen} 真眼维持视野拉扯。"
                )
                t_bad = (
                    f"中期 10~25 分钟全队打出 {s_kills}:{o_kills} 的人头劣势（{most_d_name} 单阶段阵亡 {most_d_cnt} 次），"
                    "出现典型的『大哥在钻野刷关键装、四个人在外面无视野乱接团连送』的节奏脱节！"
                    if s_kills < o_kills
                    else f"中期拿到击杀优势后推塔转化率偏低（阶段全队建筑伤害 {s_td:,}），没有在 20 分钟前早早控下一代肉山盾锁死胜局。"
                )
                t_action = (
                    "【中期团队怎么进步 (10–25分钟)】：① 明确中期带队核心：当 1 号位正在刷狂战/分身/BKB 关键成型点时，2/3/4/5 号位要么开雾去抓敌方落单刷钱核，要么蹲在己方刷钱大哥侧翼高坡反蹲，绝不无脑 4 打 5 强冲；"
                    "② 3 号位跳刀出炉的第一时间必须立刻买雾打第一波信息差先手，打赢顺势拔掉敌方中一塔与优势路一塔；"
                    "③ 20~24 分钟一旦抓死敌方双核或大招流辅助，全队立刻集合打掉第一代肉山，拒绝散开各刷各的野！"
                )
            else:
                t_good = (
                    f"25分钟后全队打出 {s_kills}:{o_kills} 的决战表现，合计轰出 {s_td:,} 点建筑伤害，抓住了关键团战与肉山窗口完成终结。"
                    if s_kills >= o_kills
                    else f"后期逆风局全队仍努力寻找先手抓单机会（阶段击杀 {s_kills} 次，插眼 {s_obs} 假 / {s_sen} 真）。"
                )
                t_bad = (
                    f"后期关键团战前后出现减员（{most_d_name} 阶段阵亡 {most_d_cnt} 次），"
                    "上高地或压三塔时存在抗塔过深、技能交完不果断后撤被敌方买活反打的惊险失误！"
                )
                t_action = (
                    "【后期团队怎么进步 (25分钟至终局)】：① 25 分钟后全员严守『买活钱红线』，差 500 金以内买大件时优先留买活；"
                    "② 上高地前必须确保带盾（或敌方至少减员 2 人且无买活），由带盾核心上前拆塔，后排控制蹲在台阶下专门断对面冲高地反扑；"
                    "③ 破掉一路高地或逼出对面双买活后，全队立刻语音喊撤退转打肉山/控魔晶，绝不残血赖在敌方高地上送翻盘！"
                )

            team_diagnostics[side_k] = {
                "evidence": "inferred",
                "summary": g_phase.get("summary") or "",
                "turning_point": g_phase.get("turning_point") or "",
                "team_good": t_good,
                "team_bad": t_bad,
                "team_action": t_action,
            }

        pd["team_diagnostics"] = team_diagnostics
        ts_obj = pd.get("team_summary") or {}
        g_sum_str = str(g_phase.get("summary") or "").strip()
        if g_sum_str:
            pd["evidence"] = "inferred"
            pd["conclusions"] = [{"text": g_sum_str, "kind": "phase_summary", "evidence": "inferred"}]
        else:
            ph_fact = (
                f"{plabel}（{tlabel}）：经济差变动 {int(ts_obj.get('income_diff_change') or 0):+,} 金，"
                f"推塔 {int(ts_obj.get('towers_taken') or 0)}:{int(ts_obj.get('towers_lost') or 0)}，"
                f"肉山 {int(ts_obj.get('roshan_taken') or 0)}:{int(ts_obj.get('roshan_lost') or 0)}。"
            )
            pd["evidence"] = "inferred"
            pd["conclusions"] = [
                {
                    "text": ph_fact,
                    "kind": "phase_summary",
                    "evidence": "measured",
                    "source_fields": ["radiant_gold_adv", "objectives"],
                }
            ]

    return phases_data


BENCHMARK_LABELS_ZH: Dict[str, str] = {
    "gold_per_min": "GPM 打钱速率",
    "xp_per_min": "XPM 经验速率",
    "kills_per_min": "分均击杀",
    "last_hits_per_min": "分均正补",
    "hero_damage_per_min": "分均英雄伤害",
    "hero_healing_per_min": "分均治疗",
    "tower_damage": "建筑推塔伤害",
    "stuns_per_min": "分均控制时长",
}


def build_deep_replay_forensics(
    match: Dict[str, Any],
    radiant_players: List[Dict[str, Any]],
    dire_players: List[Dict[str, Any]],
    hero_const_by_id: Dict[int, Dict[str, Any]],
    npc_to_hid: Dict[str, int],
) -> Dict[str, Any]:
    """
    提取更深层的录像刑侦铁证：
    1. BP 选人先后手顺序还原 (picks_order)
    2. 三路对线 10 分钟对位胜负验尸台 (lane_matchups: 上路 / 中路 / 下路)
    3. 喂拉比克偷技能排行榜 (rubick_steal_ledger)
    4. 关键指向性技能施放目标明细 (key_spell_targets: 猛犸授予力量给谁、帕格纳衰老给谁、莱恩变羊给谁等)
    5. 信使阵亡墓志铭 (courier_graveyard) 与 地图 Ping 压力榜 (ping_pressure_rank)
    6. 为每位玩家挂载全球同英雄百分位 (benchmarks_list) 与个人技能目标拆解 (ability_targets_list)
    """
    from dota_constants_zh import get_ability_zh, ITEMS_ZH

    all_formatted = radiant_players + dire_players
    if not match.get("version"):
        from tactical_microscope_engine import build_tactical_microscope
        microscope = build_tactical_microscope(
            match=match,
            radiant_players=radiant_players,
            dire_players=dire_players,
            hero_const_by_id=hero_const_by_id,
            npc_to_hid=npc_to_hid,
        )
        for p in all_formatted:
            p["pings_count"] = None
            p["lane_id"] = None
            p["lane_efficiency_pct"] = None
            p["benchmarks_list"] = []
            p["ability_targets_list"] = []
        return {
            "available": False,
            "picks_order": {"available": False},
            "lane_matchups": {"available": False},
            "rubick_steal_ledger": {"available": False},
            "key_spell_targets": {"available": False},
            "courier_graveyard": {"available": False},
            "ping_pressure_rank": {"available": False},
            "focus_fire_matrix": {"available": False, "dire": {"available": False}, "radiant": {"available": False}},
            "teamfight_forensics": {"available": False},
            **microscope,
        }

    fmt_by_slot = {int(p["player_slot"]): p for p in all_formatted}
    fmt_by_hid = {int(p["hero_id"]): p for p in all_formatted}
    raw_by_slot = {int(rp.get("player_slot", 0)): rp for rp in (match.get("players") or [])}

    def fmt_mmss(sec: Any) -> str:
        s = int(sec or 0)
        if s < 0:
            return f"-{abs(s)//60:02d}:{abs(s)%60:02d}"
        return f"{s//60:02d}:{s%60:02d}"

    # 1. BP 选人先后手顺序还原
    picks_order: List[Dict[str, Any]] = []
    raw_pbs = match.get("picks_bans") or []
    pick_seq = 0
    for pb in sorted(raw_pbs, key=lambda x: int(x.get("order") or 0)):
        hid = int(pb.get("hero_id") or 0)
        is_pick = bool(pb.get("is_pick"))
        team_num = int(pb.get("team") or 0)  # 0 = Radiant, 1 = Dire
        side_key = "radiant" if team_num == 0 else "dire"
        side_zh = "天辉" if team_num == 0 else "夜魇"
        hinfo = hero_const_by_id.get(hid, {})
        matched_p = fmt_by_hid.get(hid)
        if is_pick:
            pick_seq += 1
        stage_tag = "禁用"
        if is_pick:
            if pick_seq <= 4:
                stage_tag = f"第{pick_seq}手 · 首轮盲选"
            elif pick_seq <= 8:
                stage_tag = f"第{pick_seq}手 · 二轮核心"
            else:
                stage_tag = f"第{pick_seq}手 · 尾手针对绝活"

        picks_order.append({
            "order": int(pb.get("order") or 0) + 1,
            "pick_seq": pick_seq if is_pick else None,
            "is_pick": is_pick,
            "side": side_key,
            "side_zh": side_zh,
            "stage_tag": stage_tag,
            "hero_id": hid,
            "hero_short_zh": matched_p["hero_short_zh"] if matched_p else (hinfo.get("short_zh") or f"英雄#{hid}"),
            "hero_img": matched_p["hero_img"] if matched_p else (hinfo.get("img") or ""),
            "pos": matched_p["pos"] if matched_p else None,
            "personaname": matched_p["personaname"] if matched_p else "",
        })

    # 2. 为每位玩家挂载全球同英雄百分位 (benchmarks_list) 与 个人技能目标拆解 (ability_targets_list)
    key_spell_targets: List[Dict[str, Any]] = []
    rubick_steal_ledger: List[Dict[str, Any]] = []

    for p in all_formatted:
        slot = int(p["player_slot"])
        rp = raw_by_slot.get(slot, {})
        p["pings_count"] = int(rp.get("pings") or 0)
        p["lane_id"] = int(rp.get("lane") or 0)
        p["lane_efficiency_pct"] = int(rp.get("lane_efficiency_pct") or 0)

        # 全球同英雄百分位
        raw_bm = rp.get("benchmarks") or {}
        bm_list = []
        for bm_key, bm_label in BENCHMARK_LABELS_ZH.items():
            b_obj = raw_bm.get(bm_key)
            if isinstance(b_obj, dict) and b_obj.get("pct") is not None:
                pct_val = round(float(b_obj["pct"]) * 100, 1)
                raw_val = b_obj.get("raw", 0)
                bm_list.append({
                    "key": bm_key,
                    "label": bm_label,
                    "pct": pct_val,
                    "raw": round(float(raw_val), 1) if isinstance(raw_val, (int, float)) else raw_val,
                    "tier": "top" if pct_val >= 75 else ("mid" if pct_val >= 40 else "low"),
                })
        p["benchmarks_list"] = bm_list

        # 技能目标明细 (ability_targets)
        raw_at = rp.get("ability_targets") or {}
        at_list = []
        for ab_key, target_dict in raw_at.items():
            if not isinstance(target_dict, dict) or not target_dict:
                continue
            ab_zh = get_ability_zh(ab_key)
            targets_formatted = []
            total_casts_on_heroes = 0
            for npc_name, cnt in sorted(target_dict.items(), key=lambda x: int(x[1] or 0), reverse=True):
                c_val = int(cnt or 0)
                if c_val <= 0:
                    continue
                total_casts_on_heroes += c_val
                t_hid = npc_to_hid.get(npc_name, 0)
                t_p = fmt_by_hid.get(t_hid)
                t_info = hero_const_by_id.get(t_hid, {})
                t_short = t_p["hero_short_zh"] if t_p else (t_info.get("short_zh") or npc_name.replace("npc_dota_hero_", ""))
                t_img = t_p["hero_img"] if t_p else (t_info.get("img") or "")
                is_ally = (t_p["side"] == p["side"]) if t_p else False
                targets_formatted.append({
                    "hero_short_zh": t_short,
                    "hero_img": t_img,
                    "count": c_val,
                    "is_ally": is_ally,
                    "personaname": t_p["personaname"] if t_p else "",
                })
            if targets_formatted:
                entry = {
                    "ability_key": ab_key,
                    "ability_zh": ab_zh,
                    "total_casts": total_casts_on_heroes,
                    "targets": targets_formatted[:5],
                }
                at_list.append(entry)

                # 如果是拉比克技能窃取，单独生成「喂拉比克嫌疑人榜」
                if ab_key == "rubick_spell_steal":
                    for tf in targets_formatted:
                        rubick_steal_ledger.append({
                            "rubick_player": p["personaname"],
                            "rubick_side": p["side"],
                            "victim_hero": tf["hero_short_zh"],
                            "victim_img": tf["hero_img"],
                            "victim_player": tf["personaname"],
                            "stolen_count": tf["count"],
                        })
                elif total_casts_on_heroes >= 4:
                    key_spell_targets.append({
                        "caster_hero": p["hero_short_zh"],
                        "caster_img": p["hero_img"],
                        "caster_player": p["personaname"],
                        "caster_side": "radiant" if p["side"] == "天辉" else "dire",
                        "caster_pos": p["pos"],
                        "ability_zh": ab_zh,
                        "total_casts": total_casts_on_heroes,
                        "targets": targets_formatted[:4],
                    })

        p["ability_targets_list"] = at_list[:4]

    # 3. 三路对线 10 分钟对位胜负验尸台 (lane_matchups)
    # OpenDota lane 定义: 1 = 下路 (天辉优势路 vs 夜魇劣势路), 2 = 中路, 3 = 上路 (天辉劣势路 vs 夜魇优势路)
    lane_defs = [
        (3, "上路对线 (夜魇优势路 vs 天辉劣势路)"),
        (2, "中路皇城 PK (1v1 对位)"),
        (1, "下路对线 (天辉优势路 vs 夜魇劣势路)"),
    ]
    lane_matchups: List[Dict[str, Any]] = []
    for lane_num, lane_title in lane_defs:
        rad_lp = [p for p in radiant_players if p.get("lane_id") == lane_num]
        dire_lp = [p for p in dire_players if p.get("lane_id") == lane_num]
        if not rad_lp and not dire_lp:
            continue

        rad_g10 = sum(int((p.get("laning_10m") or {}).get("gold10") or 0) for p in rad_lp)
        dire_g10 = sum(int((p.get("laning_10m") or {}).get("gold10") or 0) for p in dire_lp)
        rad_lh10 = sum(int((p.get("laning_10m") or {}).get("lh10") or 0) for p in rad_lp)
        dire_lh10 = sum(int((p.get("laning_10m") or {}).get("lh10") or 0) for p in dire_lp)
        rad_dn10 = sum(int((p.get("laning_10m") or {}).get("dn10") or 0) for p in rad_lp)
        dire_dn10 = sum(int((p.get("laning_10m") or {}).get("dn10") or 0) for p in dire_lp)

        diff_dire = dire_g10 - rad_g10
        if abs(diff_dire) < 350:
            winner_side = "even"
            verdict_zh = f"均势互发育 (10m 经济差 {diff_dire:+d} 金)"
        elif diff_dire >= 1000:
            winner_side = "dire"
            verdict_zh = f"夜魇打穿该路 (10m 领先 +{diff_dire:,} 金)"
        elif diff_dire > 0:
            winner_side = "dire"
            verdict_zh = f"夜魇对线小优 (10m 领先 +{diff_dire:,} 金)"
        elif diff_dire <= -1000:
            winner_side = "radiant"
            verdict_zh = f"天辉打穿该路 (10m 领先 +{abs(diff_dire):,} 金)"
        else:
            winner_side = "radiant"
            verdict_zh = f"天辉对线小优 (10m 领先 +{abs(diff_dire):,} 金)"

        from hero_profiles_126 import analyze_lane_matchup_chemistry
        lane_chem = analyze_lane_matchup_chemistry(lane_num, rad_lp, dire_lp, diff_dire)

        lane_matchups.append({
            "lane_id": lane_num,
            "title": lane_title,
            "winner_side": winner_side,
            "verdict_zh": verdict_zh,
            "lane_chemistry_by_side": lane_chem,
            "dire_gold10": dire_g10,
            "radiant_gold10": rad_g10,
            "dire_lh_dn": f"{dire_lh10}/{dire_dn10}",
            "radiant_lh_dn": f"{rad_lh10}/{rad_dn10}",
            "dire_heroes": [
                {
                    "pos": p["pos"],
                    "hero_short_zh": p["hero_short_zh"],
                    "hero_img": p["hero_img"],
                    "personaname": p["personaname"],
                    "gold10": (p.get("laning_10m") or {}).get("gold10") or 0,
                    "lh10": (p.get("laning_10m") or {}).get("lh10") or 0,
                    "dn10": (p.get("laning_10m") or {}).get("dn10") or 0,
                    "lane_eff": p.get("lane_efficiency_pct") or 0,
                }
                for p in dire_lp
            ],
            "radiant_heroes": [
                {
                    "pos": p["pos"],
                    "hero_short_zh": p["hero_short_zh"],
                    "hero_img": p["hero_img"],
                    "personaname": p["personaname"],
                    "gold10": (p.get("laning_10m") or {}).get("gold10") or 0,
                    "lh10": (p.get("laning_10m") or {}).get("lh10") or 0,
                    "dn10": (p.get("laning_10m") or {}).get("dn10") or 0,
                    "lane_eff": p.get("lane_efficiency_pct") or 0,
                }
                for p in rad_lp
            ],
        })

    # 4. 信使阵亡墓志铭 (courier_graveyard)
    courier_graveyard: List[Dict[str, Any]] = []
    for obj in match.get("objectives") or []:
        if obj.get("type") == "CHAT_MESSAGE_COURIER_LOST":
            t_sec = int(obj.get("time") or 0)
            lost_team = int(obj.get("team") or 0)  # 2 = Radiant lost courier, 3 = Dire lost courier
            lost_side_zh = "天辉" if lost_team == 2 else "夜魇"
            killer_slot = obj.get("killer")
            killer_p = fmt_by_slot.get(int(killer_slot)) if killer_slot is not None and int(killer_slot) in fmt_by_slot else None
            courier_graveyard.append({
                "time_str": fmt_mmss(t_sec),
                "lost_side": "radiant" if lost_team == 2 else "dire",
                "lost_side_zh": lost_side_zh,
                "killer_hero": killer_p["hero_short_zh"] if killer_p else "敌方小兵/英雄",
                "killer_player": killer_p["personaname"] if killer_p else "",
            })

    # 5. 地图 Ping 压力榜 (ping_pressure_rank)
    ping_pressure_rank = [
        {
            "pos": p["pos"],
            "side": "radiant" if p["side"] == "天辉" else "dire",
            "side_zh": p["side"],
            "hero_short_zh": p["hero_short_zh"],
            "hero_img": p["hero_img"],
            "personaname": p["personaname"],
            "pings": p.get("pings_count") or 0,
        }
        for p in sorted(all_formatted, key=lambda x: int(x.get("pings_count") or 0), reverse=True)
        if int(p.get("pings_count") or 0) > 0
    ]

    # 6. 5v5 集火流向与互相伤害矩阵 (focus_fire_matrix)
    def build_side_focus_matrix(attackers: List[Dict[str, Any]], defenders: List[Dict[str, Any]], side_key: str) -> Dict[str, Any]:
        att_sorted = sorted(attackers, key=lambda x: int(x.get("pos") or 9))
        def_sorted = sorted(defenders, key=lambda x: int(x.get("pos") or 9))
        def_npcs = []
        for dp in def_sorted:
            dhid = int(dp["hero_id"])
            npc_str = hero_const_by_id.get(dhid, {}).get("npc") or f"npc_dota_hero_{dhid}"
            def_npcs.append((npc_str, dp))

        rows = []
        col_totals = [0] * len(def_sorted)
        grand_total = 0
        max_cell = 1

        for ap in att_sorted:
            rp = raw_by_slot.get(int(ap["player_slot"]), {})
            dmg_dict = rp.get("damage") or {}
            cells = []
            row_total = 0
            for c_idx, (npc_str, dp) in enumerate(def_npcs):
                val = int(dmg_dict.get(npc_str) or 0)
                cells.append(val)
                row_total += val
                col_totals[c_idx] += val
                grand_total += val
                if val > max_cell:
                    max_cell = val
            rows.append({
                "pos": ap["pos"],
                "hero_short_zh": ap["hero_short_zh"],
                "hero_img": ap["hero_img"],
                "personaname": ap["personaname"],
                "row_total": row_total,
                "cells": cells,
            })

        targets_meta = [
            {
                "pos": dp["pos"],
                "hero_short_zh": dp["hero_short_zh"],
                "hero_img": dp["hero_img"],
                "personaname": dp["personaname"],
                "col_total": col_totals[idx],
                "col_share_pct": round((col_totals[idx] / max(1, grand_total)) * 100, 1),
            }
            for idx, (_, dp) in enumerate(def_npcs)
        ]

        # 诊断集火质量：看打在敌方 3 号位肉盾 vs 1/2 号位核心的比例
        pos3_share = next((t["col_share_pct"] for t in targets_meta if t["pos"] == 3), 0.0)
        pos3_name = next((t["hero_short_zh"] for t in targets_meta if t["pos"] == 3), "三号位")
        core12_share = sum(t["col_share_pct"] for t in targets_meta if t["pos"] in (1, 2))
        sup45_share = sum(t["col_share_pct"] for t in targets_meta if t["pos"] in (4, 5))

        if pos3_share >= 30.0:
            verdict = (
                f"⚠️ 集火警报：全队高达 {pos3_share}% 的英雄伤害全灌在了敌方三号位肉盾『{pos3_name}』身上！"
                f"对敌方 1/2 号位双核的有效伤害占比仅 {core12_share:.1f}%，团战明显被前排吸引过多火力，切后排与秒关键人不够坚决。"
            )
        elif core12_share >= 45.0:
            verdict = (
                f"✓ 集火目标明确：全队有 {core12_share:.1f}% 的火力精准倾泻在敌方 1/2 号位双核身上，"
                f"另有 {sup45_share:.1f}% 伤害用于秒杀敌方 4/5 号位后排酱油，没有在敌方三号位『{pos3_name}』({pos3_share}%) 身上无脑刮痧。"
            )
        else:
            verdict = (
                f"集火分布：敌方 1/2 号位双核承伤占 {core12_share:.1f}%，三号位『{pos3_name}』吃下 {pos3_share}% 伤害，"
                f"4/5 号位辅助吃下 {sup45_share:.1f}% 伤害。建议团战开打前先标定第一集火目标（先秒救人酱油或未开BKB主核）。"
            )

        return {
            "side": side_key,
            "grand_total": grand_total,
            "max_cell": max_cell,
            "targets": targets_meta,
            "rows": rows,
            "verdict": verdict,
        }

    focus_fire_matrix = {
        "dire": build_side_focus_matrix(dire_players, radiant_players, "dire"),
        "radiant": build_side_focus_matrix(radiant_players, dire_players, "radiant"),
    }

    # 7. 团战秒级剧本还原、崩盘第一现场与微操审判 (teamfight_forensics)
    raw_tfs = match.get("teamfights") or []
    all_raw_players = match.get("players") or []
    all_objectives = match.get("objectives") or []
    tf_forensics: List[Dict[str, Any]] = []

    def _coord_to_zone_zh(rx: float, ry: float) -> str:
        if rx < 98 and ry < 98:
            return "天辉高地 / 基地防线"
        if rx > 158 and ry > 158:
            return "夜魇高地 / 基地防线"
        if (104 <= rx <= 128 and 128 <= ry <= 152) or (128 <= rx <= 152 and 104 <= ry <= 128):
            return "河道中心 / 肉山巢穴区"
        if abs((rx - 64) + (ry - 64) - 128) <= 18 and 100 <= rx <= 156:
            return "中路河道交火区"
        if rx < 108 and ry >= 130:
            return "上路走廊 / 夜魇优势路区"
        if rx >= 130 and ry < 108:
            return "下路走廊 / 天辉优势路区"
        if ry >= 134 and 108 <= rx <= 158:
            return "夜魇主野区 / 远古三角区"
        if ry <= 122 and 96 <= rx <= 148:
            return "天辉主野区 / 远古三角区"
        return "中路河道 / 野区交界处"

    CRITICAL_SAVE_ITEMS: Dict[str, str] = dict(ACTIVE_SAVE_ITEMS_ZH)
    TEAM_SAVE_KEYS = {"glimmer_cape", "force_staff", "lotus_orb"}
    SELF_SAVE_KEYS = set(ACTIVE_SAVE_ITEMS_ZH.keys())

    BUILDING_NAME_ZH: Dict[str, str] = {
        "tower1_top": "上路一塔",
        "tower1_mid": "中路一塔",
        "tower1_bot": "下路一塔",
        "tower2_top": "上路二塔",
        "tower2_mid": "中路二塔",
        "tower2_bot": "下路二塔",
        "tower3_top": "上路高地塔",
        "tower3_mid": "中路高地塔",
        "tower3_bot": "下路高地塔",
        "tower4": "基地门牙双子塔",
        "melee_rax_top": "上路近战兵营",
        "range_rax_top": "上路远程兵营",
        "melee_rax_mid": "中路近战兵营",
        "range_rax_mid": "中路远程兵营",
        "melee_rax_bot": "下路近战兵营",
        "range_rax_bot": "下路远程兵营",
        "fort": "遗迹主基地",
    }

    for idx, tf in enumerate(raw_tfs):
        tf_players = tf.get("players") or []
        if len(tf_players) < 10:
            continue
        start_s = int(tf.get("start") or 0)
        end_s = int(tf.get("end") or 0)
        deaths_coords = []
        buybacks_list = []
        rad_k = 0
        dire_k = 0
        gold_swing_rad = 0
        rad_total_dmg = sum(int(tp.get("damage") or 0) for tp in tf_players[:5])
        dire_total_dmg = sum(int(tp.get("damage") or 0) for tp in tf_players[5:10])

        for p_i, tp in enumerate(tf_players[:10]):
            raw_p = all_raw_players[p_i] if p_i < len(all_raw_players) else {}
            pslot = int(raw_p.get("player_slot", p_i if p_i < 5 else p_i + 123))
            fp = fmt_by_slot.get(pslot)
            if not fp:
                continue
            d_cnt = int(tp.get("deaths") or 0)
            bb_cnt = int(tp.get("buybacks") or 0)
            g_delta = int(tp.get("gold_delta") or 0)
            if pslot < 128:
                dire_k += d_cnt
                gold_swing_rad += g_delta
            else:
                rad_k += d_cnt
                gold_swing_rad -= g_delta

            if bb_cnt > 0:
                buybacks_list.append(f"{fp['hero_short_zh']}({fp['personaname']})")

            d_pos = tp.get("deaths_pos") or {}
            if isinstance(d_pos, dict):
                for x_str, y_dict in d_pos.items():
                    if isinstance(y_dict, dict):
                        for y_str, cnt in y_dict.items():
                            try:
                                raw_x = float(x_str)
                                raw_y = float(y_str)
                                nx = round(max(4.0, min(96.0, (raw_x - 64.0) / 128.0 * 100.0)), 1)
                                ny = round(max(4.0, min(96.0, (1.0 - (raw_y - 64.0) / 128.0) * 100.0)), 1)
                                z_zh = _coord_to_zone_zh(raw_x, raw_y)
                                deaths_coords.append({
                                    "x": raw_x,
                                    "y": raw_y,
                                    "nx": nx,
                                    "ny": ny,
                                    "zone_zh": z_zh,
                                    "count": int(cnt or 1),
                                    "deaths": int(cnt or 1),
                                    "side": "radiant" if pslot < 128 else "dire",
                                    "side_zh": fp["side"],
                                    "pos": fp["pos"],
                                    "hero_short_zh": fp["hero_short_zh"],
                                    "hero_img": fp["hero_img"],
                                    "personaname": fp["personaname"],
                                })
                            except Exception:
                                pass

        if rad_k + dire_k < 2 and abs(gold_swing_rad) < 1500:
            continue

        # 确定交火地形名称
        if deaths_coords:
            avg_x = sum(c["x"] for c in deaths_coords) / len(deaths_coords)
            avg_y = sum(c["y"] for c in deaths_coords) / len(deaths_coords)
            location_zh = _coord_to_zone_zh(avg_x, avg_y)
        else:
            location_zh = "中路河道 / 野区交界处"

        # 1) 审计 10 位玩家在该波团战中的技能、目标、已购未按保命装、大招成败、野区独刷
        players_exec: List[Dict[str, Any]] = []
        exec_by_slot: Dict[int, Dict[str, Any]] = {}
        smoke_activators: List[str] = []
        rad_initiators: List[str] = []
        dire_initiators: List[str] = []

        for p_i, tp in enumerate(tf_players[:10]):
            raw_p = all_raw_players[p_i] if p_i < len(all_raw_players) else {}
            pslot = int(raw_p.get("player_slot", p_i if p_i < 5 else p_i + 123))
            fp = fmt_by_slot.get(pslot)
            if not fp:
                continue
            p_side = "radiant" if pslot < 128 else "dire"
            p_side_zh = "天辉" if p_side == "radiant" else "夜魇"
            team_tot_dmg = max(1, rad_total_dmg if p_side == "radiant" else dire_total_dmg)
            team_deaths = dire_k if p_side == "radiant" else rad_k
            enemy_deaths = rad_k if p_side == "radiant" else dire_k

            dmg_v = int(tp.get("damage") or 0)
            dmg_share = round(dmg_v / team_tot_dmg * 100.0, 1)
            heal_v = int(tp.get("healing") or 0)
            d_cnt = int(tp.get("deaths") or 0)
            bb_cnt = int(tp.get("buybacks") or 0)
            g_delta = int(tp.get("gold_delta") or 0)
            killed_dict = tp.get("killed") or {}
            kills_in_tf = sum(int(v or 0) for k, v in killed_dict.items() if str(k).startswith("npc_dota_hero_"))

            ab_uses = tp.get("ability_uses") or {}
            it_uses = tp.get("item_uses") or {}
            ab_targets = tp.get("ability_targets") or {}

            if it_uses.get("smoke_of_deceit"):
                smoke_activators.append(f"{p_side_zh}{fp['pos']}号位{fp['hero_short_zh']}")

            ab_used_zh_list = []
            for ak, cnt in sorted(ab_uses.items(), key=lambda x: int(x[1] or 0), reverse=True):
                azh = get_ability_zh(ak)
                if azh and int(cnt or 0) > 0:
                    ab_used_zh_list.append(f"{azh}×{cnt}")

            it_used_zh_list = []
            for ik, cnt in sorted(it_uses.items(), key=lambda x: int(x[1] or 0), reverse=True):
                izh = CRITICAL_SAVE_ITEMS.get(ik) or ITEMS_ZH.get(ik)
                if izh and int(cnt or 0) > 0 and ik not in ("ward_observer", "ward_sentry", "ward_dispenser", "famango", "tango", "clarity", "enchanted_mango"):
                    it_used_zh_list.append(f"{izh}×{cnt}")

            ab_targets_zh_list = []
            for ak, tdict in ab_targets.items():
                if not isinstance(tdict, dict):
                    continue
                azh = get_ability_zh(ak) or ak
                for npc_k, cnt in sorted(tdict.items(), key=lambda x: int(x[1] or 0), reverse=True):
                    if int(cnt or 0) <= 0:
                        continue
                    thid = npc_to_hid.get(npc_k, 0)
                    tfp = fmt_by_hid.get(thid)
                    tshort = tfp["hero_short_zh"] if tfp else npc_k.replace("npc_dota_hero_", "")
                    ab_targets_zh_list.append(f"{azh}➔{tshort}×{cnt}")

            if it_uses.get("blink") or ab_uses.get("furion_teleportation"):
                init_str = f"{fp['hero_short_zh']}(跳刀" + (f"+{ab_used_zh_list[0].split('×')[0]}" if ab_used_zh_list else "") + ")"
                if p_side == "radiant":
                    rad_initiators.append(init_str)
                else:
                    dire_initiators.append(init_str)

            # 只针对团战内的阵亡，检查阵亡时仍持有（未合成升级品）且本波未使用的 9 件主动保命装
            plog = raw_p.get("purchase_log") or []
            held_before_tf = get_held_active_save_items(plog, start_s - 3)

            unused_self_saves: List[str] = []
            unused_team_saves: List[str] = []
            if d_cnt > 0:
                for ik in held_before_tf:
                    if int(it_uses.get(ik) or 0) == 0:
                        unused_self_saves.append(ACTIVE_SAVE_ITEMS_ZH[ik])

            # 审计团战大招释放（排除斩杀类、保人类及薄葬/墓碑等非大招技能；不推断冷却与凤凰碎蛋）
            HERO_ULTIMATE_KEYS: Dict[int, Tuple[str, str]] = {
                5: ("crystal_maiden_freezing_field", "极寒领域"),
                7: ("earthshaker_echo_slam", "回音击"),
                8: ("juggernaut_omni_slash", "无敌斩"),
                11: ("nevermore_requiem", "魂之挽歌"),
                13: ("puck_dream_coil", "梦境缠绕"),
                14: ("pudge_dismember", "肢解"),
                15: ("razor_eye_of_the_storm", "风暴之眼"),
                16: ("sandking_epicenter", "地震"),
                18: ("sven_gods_strength", "神之力量"),
                22: ("zuus_thundergods_wrath", "雷神之怒"),
                23: ("kunkka_ghostship", "幽灵船"),
                27: ("shadow_shaman_mass_serpent_ward", "群蛇守卫"),
                29: ("tidehunter_ravage", "毁灭"),
                30: ("witch_doctor_death_ward", "死亡守卫"),
                31: ("lich_chain_frost", "连环霜冻"),
                33: ("enigma_black_hole", "黑洞"),
                37: ("warlock_rain_of_chaos", "混乱之雨"),
                38: ("beastmaster_primal_roar", "原始咆哮"),
                39: ("queenofpain_sonic_wave", "超声冲击波"),
                40: ("venomancer_noxious_plague", "恶性瘟疫"),
                41: ("faceless_void_chronosphere", "时间结界"),
                43: ("death_prophet_exorcism", "驱使恶灵"),
                45: ("pugna_life_drain", "生命汲取"),
                48: ("luna_eclipse", "月蚀"),
                53: ("furion_wrath_of_nature", "自然之怒"),
                55: ("dark_seer_wall_of_replica", "复制之墙"),
                64: ("jakiro_macropyre", "烈焰焚身"),
                65: ("batrider_flaming_lasso", "燃烧枷锁"),
                68: ("ancient_apparition_ice_blast", "冰晶爆轰"),
                69: ("doom_bringer_doom", "末日"),
                72: ("gyrocopter_call_down", "召唤飞弹"),
                76: ("obsidian_destroyer_sanity_eclipse", "神智之蚀"),
                78: ("brewmaster_primal_split", "元素分离"),
                83: ("treant_overgrowth", "疯狂生长"),
                87: ("disruptor_static_storm", "静态风暴"),
                89: ("naga_siren_song_of_the_siren", "海妖之歌"),
                94: ("medusa_stone_gaze", "石化凝视"),
                96: ("centaur_stampede", "奔袭冲撞"),
                97: ("magnataur_reverse_polarity", "两极反转"),
                104: ("legion_commander_duel", "决斗"),
                110: ("phoenix_supernova", "超新星"),
                112: ("winter_wyvern_winters_curse", "寒冬诅咒"),
                114: ("monkey_king_wukongs_command", "猴子猴孙"),
                120: ("pangolier_gyroshell", "地雷滚滚"),
                121: ("grimstroke_soulbind", "缚魂"),
                128: ("snapfire_mortimer_kisses", "蜥蜴绝吻"),
                129: ("mars_arena_of_blood", "热血竞技场"),
                131: ("ringmaster_wheel", "奇观之轮"),
                135: ("dawnbreaker_solar_guardian", "天光现世"),
                136: ("marci_unleash", "怒拳破"),
                137: ("primal_beast_pulverize", "捶搋"),
                138: ("muerta_pierce_the_veil", "越界"),
            }
            hid = int(fp.get("hero_id") or 0)
            ult_audit_zh = ""
            egg_shattered = False
            egg_unpressed = False
            ult_unpressed_name = ""

            if hid == 110:  # 凤凰 Phoenix
                egg_cnt = int(ab_uses.get("phoenix_supernova") or 0)
                spirits_cnt = int(ab_uses.get("phoenix_fire_spirits") or 0)
                ray_cnt = int(ab_uses.get("phoenix_sun_ray") or 0)
                if egg_cnt > 0:
                    ult_audit_zh = f"✓ 已交大招：【超新星×{egg_cnt}】（烈火精灵×{spirits_cnt} / 激光×{ray_cnt}）"
                elif d_cnt > 0 and start_s >= 420:
                    egg_unpressed = True
                    ult_audit_zh = "ℹ️ 本波未释放大招【超新星】"
            elif hid in HERO_ULTIMATE_KEYS and start_s >= 480:
                u_key, u_zh = HERO_ULTIMATE_KEYS[hid]
                u_cnt = int(ab_uses.get(u_key) or 0)
                if hid == 131:
                    box_cnt = int(ab_uses.get("ringmaster_the_box") or 0)
                    if u_cnt > 0 or box_cnt > 0:
                        ult_audit_zh = f"✓ 关键技能：奇观之轮×{u_cnt} / 逃生暗箱×{box_cnt}"
                    elif d_cnt > 0:
                        ult_unpressed_name = u_zh
                        ult_audit_zh = f"ℹ️ 本波未释放大招【{u_zh}】"
                else:
                    if u_cnt > 0:
                        ult_audit_zh = f"✓ 已交大招：【{u_zh}×{u_cnt}】"
                    elif d_cnt > 0:
                        ult_unpressed_name = u_zh
                        ult_audit_zh = f"ℹ️ 本波未释放大招【{u_zh}】"

            # 检查是否在队友阵亡 >= 2 人时无参战记录且期间有刷钱记录（排除团战开始时已阵亡、有治疗或有技能记录者）
            afk_farm_zh = ""
            is_afk_in_tf = False
            was_dead_at_start = any(
                int(d_ev.get("time") or 0) <= start_s < int(d_ev.get("time") or 0) + int(d_ev.get("time_dead") or 30)
                for d_ev in (raw_p.get("deaths_log") or [])
                if isinstance(d_ev, dict)
            )
            if (
                not was_dead_at_start
                and team_deaths >= 2
                and dmg_v == 0
                and d_cnt == 0
                and heal_v == 0
                and len(ab_uses) == 0
            ):
                lh_arr = raw_p.get("lh_t") or []
                g_arr = raw_p.get("gold_t") or []
                m0 = max(0, min(len(lh_arr) - 1, start_s // 60)) if lh_arr else 0
                m1 = max(0, min(len(lh_arr) - 1, end_s // 60 + 1)) if lh_arr else 0
                lh_gain_tf = max(0, int(lh_arr[m1] - lh_arr[m0])) if lh_arr and m1 >= m0 else 0
                g_gain_tf = max(0, int(g_arr[m1] - g_arr[m0])) if g_arr and m1 >= m0 else max(0, g_delta)
                if lh_gain_tf > 0 or g_gain_tf >= 150:
                    is_afk_in_tf = True
                    afk_farm_zh = f"🌾 本波无参战记录（期间补刀 +{lh_gain_tf} 刀 / 进账 +{g_gain_tf} 金）"

            # 生成个人本波团定性标签
            if egg_unpressed:
                v_tag = "ℹ️ 本波未放超新星"
                v_tone = "warn"
            elif unused_self_saves and d_cnt > 0:
                v_tag = f"ℹ️ 持有{unused_self_saves[0].split('(')[0]}未使用"
                v_tone = "warn"
            elif is_afk_in_tf:
                v_tag = "🌾 本波无参战记录"
                v_tone = "warn"
            elif ult_unpressed_name and d_cnt > 0:
                v_tag = f"ℹ️ 本波未放{ult_unpressed_name}"
                v_tone = "warn"
            elif d_cnt > 0 and dmg_v < 750 and int(fp["pos"]) in (1, 2, 3):
                v_tag = "💥 核心秒躺断档"
                v_tone = "bad"
            elif dmg_share >= 32.0 and (kills_in_tf >= 1 or d_cnt == 0):
                v_tag = f"🔥 团战战神 ({dmg_share:.0f}%伤害)"
                v_tone = "good"
            elif dmg_share >= 28.0 and d_cnt > 0:
                v_tag = f"🛡️ 悲情换命炮台 ({dmg_share:.0f}%伤害)"
                v_tone = "good"
            elif kills_in_tf >= 2:
                v_tag = f"⚔️ 收割 {kills_in_tf} 杀"
                v_tone = "good"
            elif unused_team_saves:
                v_tag = f"⚠️ 未按{unused_team_saves[0].split('(')[0]}"
                v_tone = "warn"
            elif d_cnt > 0:
                v_tag = "💀 团战阵亡"
                v_tone = "warn"
            else:
                v_tag = "✓ 存活拉扯"
                v_tone = "neutral"

            p_exec_obj = {
                "slot": pslot,
                "side": p_side,
                "side_zh": p_side_zh,
                "pos": fp["pos"],
                "hero_id": hid,
                "hero_short_zh": fp["hero_short_zh"],
                "hero_img": fp["hero_img"],
                "personaname": fp["personaname"],
                "damage": dmg_v,
                "damage_share_pct": dmg_share,
                "healing": heal_v,
                "deaths": d_cnt,
                "kills_in_tf": kills_in_tf,
                "buybacks": bb_cnt,
                "gold_delta": g_delta,
                "abilities_used_zh": ab_used_zh_list[:5],
                "ability_targets_zh": ab_targets_zh_list[:4],
                "items_used_zh": it_used_zh_list[:5],
                "unused_self_saves_zh": unused_self_saves,
                "unused_team_saves_zh": unused_team_saves,
                "ult_audit_zh": ult_audit_zh,
                "egg_shattered": egg_shattered,
                "egg_unpressed": egg_unpressed,
                "ult_unpressed_name": ult_unpressed_name,
                "afk_farm_zh": afk_farm_zh,
                "is_afk_in_tf": is_afk_in_tf,
                "verdict_tag": v_tag,
                "verdict_tone": v_tone,
            }
            players_exec.append(p_exec_obj)
            exec_by_slot[pslot] = p_exec_obj

        # 2) 构建「秒级交火时间轴剧本 (second_by_second_script)」
        raw_death_events: List[Dict[str, Any]] = []
        smoke_kills_set = set()
        for p_i, raw_p in enumerate(all_raw_players[:10]):
            for kev in (raw_p.get("kills_log") or []):
                kt = int(kev.get("time") or -999)
                if start_s - 6 <= kt <= end_s + 12 and kev.get("smoke"):
                    smoke_kills_set.add((kt, str(kev.get("key") or "")))

        for p_i, raw_p in enumerate(all_raw_players[:10]):
            pslot = int(raw_p.get("player_slot", p_i if p_i < 5 else p_i + 123))
            v_fp = fmt_by_slot.get(pslot)
            if not v_fp:
                continue
            v_exec = exec_by_slot.get(pslot, {})
            v_hid = int(v_fp.get("hero_id") or 0)
            v_npc = hero_const_by_id.get(v_hid, {}).get("name") or ""
            v_side_zh = "天辉" if pslot < 128 else "夜魇"
            for dev in (raw_p.get("deaths_log") or []):
                dt = int(dev.get("time") or -999)
                if start_s - 5 <= dt <= end_s + 10:
                    k_npc = str(dev.get("key") or "")
                    k_hid = npc_to_hid.get(k_npc, 0)
                    k_fp = fmt_by_hid.get(k_hid)
                    k_short = k_fp["hero_short_zh"] if k_fp else (hero_const_by_id.get(k_hid, {}).get("short_zh") or "敌方")
                    k_pos = k_fp["pos"] if k_fp else None
                    k_side_zh = ("天辉" if int(k_fp.get("player_slot", 0)) < 128 else "夜魇") if k_fp else ("夜魇" if pslot < 128 else "天辉")
                    is_smk = any(abs(kt - dt) <= 2 and (not v_npc or kv_npc == v_npc) for (kt, kv_npc) in smoke_kills_set) and (dt - start_s <= 20)
                    raw_death_events.append({
                        "time_sec": dt,
                        "victim_slot": pslot,
                        "victim_side": "radiant" if pslot < 128 else "dire",
                        "victim_side_zh": v_side_zh,
                        "victim_pos": v_fp["pos"],
                        "victim_hero": v_fp["hero_short_zh"],
                        "victim_name": v_fp["personaname"],
                        "killer_side_zh": k_side_zh,
                        "killer_pos": k_pos,
                        "killer_hero": k_short,
                        "is_smoke_kill": is_smk,
                        "gold_fed": int(dev.get("gold_fed") or 0),
                        "gold_lost": int(dev.get("gold_lost") or 0),
                        "time_dead": int(dev.get("time_dead") or 0),
                        "victim_exec": v_exec,
                    })

        raw_death_events.sort(key=lambda x: x["time_sec"])

        script_events: List[Dict[str, Any]] = []
        # Step 0: 团战导火索与先手开团
        init_parts = []
        if smoke_activators:
            init_parts.append(f"{'、'.join(smoke_activators)} 开启【诡计之雾】抱团破雾寻战")
        if rad_initiators:
            init_parts.append(f"天辉本波使用了跳刀/传送：{'、'.join(rad_initiators[:3])}")
        if dire_initiators:
            init_parts.append(f"夜魇本波使用了跳刀/传送：{'、'.join(dire_initiators[:3])}")
        trigger_zh = " ｜ ".join(init_parts) if init_parts else f"双方在【{location_zh}】爆发正面遭遇战"

        script_events.append({
            "time_sec": start_s,
            "time_str": fmt_mmss(start_s),
            "rel_str": "T+00s",
            "event_type": "ignition",
            "badge": "🌫️ 破雾开团" if smoke_activators else "⚡ 团战爆发",
            "tone": "info",
            "headline": f"【{location_zh}】{trigger_zh}",
            "detail": f"团战总时长 {max(1, end_s - start_s)} 秒 ｜ 天辉总输出 {rad_total_dmg:,} vs 夜魇总输出 {dire_total_dmg:,}",
        })

        # 逐秒击杀/阵亡事件
        for d_idx, de in enumerate(raw_death_events):
            rel_s = max(0, de["time_sec"] - start_s)
            ve = de["victim_exec"]
            is_fb = (d_idx == 0)
            micro_notes = []
            if de["is_smoke_kill"]:
                micro_notes.append("🌫️ 破雾突袭第一刀秒杀")
            if ve.get("egg_unpressed"):
                micro_notes.append("ℹ️ 本波未释放大招【超新星】")
            elif ve.get("ult_unpressed_name"):
                micro_notes.append(f"ℹ️ 本波未释放大招【{ve['ult_unpressed_name']}】")
            if ve.get("unused_self_saves_zh"):
                micro_notes.append(f"ℹ️ 阵亡时持有【{'/'.join(ve['unused_self_saves_zh'])}】，本波未使用")
            if ve.get("abilities_used_zh"):
                micro_notes.append(f"生前技能：{'/'.join(ve['abilities_used_zh'][:3])}")
            if ve.get("items_used_zh"):
                micro_notes.append(f"已按装备：{'/'.join(ve['items_used_zh'][:2])}")

            k_pos_label = f"{de['killer_pos']}号位" if de["killer_pos"] else ""
            script_events.append({
                "time_sec": de["time_sec"],
                "time_str": fmt_mmss(de["time_sec"]),
                "rel_str": f"T+{rel_s:02d}s",
                "event_type": "kill",
                "is_first_kill": is_fb,
                "victim_side": de["victim_side"],
                "badge": "🚨 首杀突破口" if is_fb else f"💀 第{d_idx+1}滴血",
                "tone": "kill",
                "headline": (
                    f"{de['killer_side_zh']}{k_pos_label}{de['killer_hero']} "
                    f"击杀 {de['victim_side_zh']}{de['victim_pos']}号位{de['victim_hero']}({de['victim_name']})"
                ),
                "detail": (
                    f"本波打出 {ve.get('damage', 0):,} 伤害（占全队 {ve.get('damage_share_pct', 0)}%）｜ "
                    f"送出 +{de['gold_fed']} 金 / 掉钱 -{de['gold_lost']} 金 / 泉水读秒 {de['time_dead']}s"
                    + (f" ｜ {'；'.join(micro_notes)}" if micro_notes else "")
                ),
            })

        # 买活事件
        if buybacks_list:
            script_events.append({
                "time_sec": end_s,
                "time_str": fmt_mmss(end_s),
                "rel_str": f"T+{max(0, end_s - start_s):02d}s",
                "event_type": "buyback",
                "badge": "💰 买活返场",
                "tone": "warn",
                "headline": f"买活交出：{'、'.join(buybacks_list)}",
                "detail": "试图强行续命接管残局或死守高地防线",
            })

        # 3) 扫描团战结束后 90 秒内的「连锁建筑/肉山后果 (consequence_chain)」
        consequence_items: List[str] = []
        for obj in all_objectives:
            ot = int(obj.get("time") or -999)
            if start_s <= ot <= end_s + 95:
                otype = str(obj.get("type") or "")
                rel_after = max(0, ot - end_s)
                rel_tag = f"战后+{rel_after}s" if ot > end_s else f"T+{max(0, ot - start_s):02d}s"
                if otype == "building_kill":
                    bkey = str(obj.get("key") or "")
                    lost_side_zh = "天辉" if "goodguys" in bkey else "夜魇"
                    b_label = "防御建筑"
                    for bk, bzh in BUILDING_NAME_ZH.items():
                        if bk in bkey:
                            b_label = bzh
                            break
                    c_str = f"{fmt_mmss(ot)} {lost_side_zh}痛失【{b_label}】"
                    consequence_items.append(c_str)
                    script_events.append({
                        "time_sec": ot,
                        "time_str": fmt_mmss(ot),
                        "rel_str": rel_tag,
                        "event_type": "consequence",
                        "badge": "🏰 连锁破塔/破路",
                        "tone": "consequence",
                        "headline": c_str,
                        "detail": f"团战阵亡读秒期间防线失守，直接丢失 {lost_side_zh}{b_label}",
                    })
                elif otype == "CHAT_MESSAGE_ROSHAN_KILL":
                    r_side_zh = "天辉" if obj.get("team") == 2 else "夜魇"
                    c_str = f"{fmt_mmss(ot)} {r_side_zh}控下【肉山不朽盾】"
                    consequence_items.append(c_str)
                    script_events.append({
                        "time_sec": ot,
                        "time_str": fmt_mmss(ot),
                        "rel_str": rel_tag,
                        "event_type": "consequence",
                        "badge": "🐉 连锁控肉山盾",
                        "tone": "consequence",
                        "headline": c_str,
                        "detail": f"{r_side_zh}乘胜追击无压力收下肉山盾，彻底掌握后期主动权",
                    })

        consequence_chain_zh = " ➔ ".join(consequence_items[:5]) if consequence_items else "双方拉扯后重回发育刷钱节奏，未直接丢高地或肉山"

        # 4) 从天辉/夜魇双视角生成「为什么这波团赢了/崩了」的四维定案 (by_side)
        def _build_side_tf_verdict(s_key: str) -> Dict[str, Any]:
            s_zh = "天辉" if s_key == "radiant" else "夜魇"
            o_zh = "夜魇" if s_key == "radiant" else "天辉"
            own_kills = rad_k if s_key == "radiant" else dire_k
            own_deaths = dire_k if s_key == "radiant" else rad_k
            own_gold_swing = gold_swing_rad if s_key == "radiant" else -gold_swing_rad
            own_dmg = rad_total_dmg if s_key == "radiant" else dire_total_dmg
            opp_dmg = dire_total_dmg if s_key == "radiant" else rad_total_dmg
            own_p_exec = sorted([x for x in players_exec if x["side"] == s_key], key=lambda x: x["pos"])
            opp_p_exec = sorted([x for x in players_exec if x["side"] != s_key], key=lambda x: x["damage"], reverse=True)

            enemy_throne_fell = any(f"{o_zh}痛失【遗迹主基地】" in c for c in consequence_items)
            own_throne_fell = any(f"{s_zh}痛失【遗迹主基地】" in c for c in consequence_items)
            enemy_rax_fell = any(f"{o_zh}痛失" in c and ("兵营" in c or "高地塔" in c) for c in consequence_items)
            own_rax_fell = any(f"{s_zh}痛失" in c and ("兵营" in c or "高地塔" in c) for c in consequence_items)

            if enemy_throne_fell:
                badge = f"👑 终局拆家决胜团 · {own_kills}换{own_deaths} 强拆敌方遗迹获胜"
                tone = "praise"
            elif own_throne_fell:
                badge = f"💀 终局防线崩盘 · {own_kills}换{own_deaths} 基地遗迹告破"
                tone = "roast"
            elif own_deaths >= 3 and (own_gold_swing <= -1200 or own_rax_fell):
                badge = f"🚨 崩盘第一现场 · {own_kills}换{own_deaths} 血亏 {own_gold_swing:+,} 金"
                tone = "roast"
            elif own_kills >= 3 and (own_gold_swing >= 1200 or enemy_rax_fell):
                badge = f"🏆 决胜团战大捷 · {own_kills}换{own_deaths} 狂赚 {own_gold_swing:+,} 金"
                tone = "praise"
            elif own_gold_swing < -400 or own_deaths > own_kills:
                badge = f"⚠️ 团战失利 · {own_kills}换{own_deaths} ({own_gold_swing:+,} 金)"
                tone = "roast"
            elif own_gold_swing > 400 or own_kills > own_deaths:
                badge = f"⚔️ 团战小捷 · {own_kills}换{own_deaths} ({own_gold_swing:+,} 金)"
                tone = "praise"
            else:
                badge = f"⚖️ 惨烈互换 · {own_kills}换{own_deaths} ({own_gold_swing:+,} 金)"
                tone = "mixed"

            reasons: List[str] = []
            # ① 首杀与先手复盘
            if raw_death_events:
                fb = raw_death_events[0]
                fb_rel = max(0, fb["time_sec"] - start_s)
                if fb["victim_side"] == s_key:
                    reasons.append(
                        f"① 本波最先阵亡：开团 {fb_rel} 秒（{fmt_mmss(fb['time_sec'])}），本方 {fb['victim_pos']}号位 {fb['victim_hero']} 被 {fb['killer_hero']} 击杀。"
                    )
                else:
                    reasons.append(
                        f"① 先手破局：开团 {fb_rel} 秒（{fmt_mmss(fb['time_sec'])}）即集火秒掉敌方 {fb['victim_pos']}号位 {fb['victim_hero']}，后续{'乘胜追击扩大战果' if (own_gold_swing >= 0 or enemy_throne_fell or enemy_rax_fell) else '恋战深入被敌方反手大招反包'}。"
                    )

            # ② 大招与主动保命装本波使用记录
            crime_notes = []
            for pe in own_p_exec:
                if pe["egg_unpressed"]:
                    crime_notes.append(f"{pe['pos']}号位{pe['hero_short_zh']}本波未释放大招《超新星》")
                elif pe["ult_unpressed_name"]:
                    crime_notes.append(f"{pe['pos']}号位{pe['hero_short_zh']}本波未释放大招《{pe['ult_unpressed_name']}》")
                if pe["unused_self_saves_zh"]:
                    crime_notes.append(f"{pe['pos']}号位{pe['hero_short_zh']}阵亡时持有【{'/'.join(pe['unused_self_saves_zh'])}】，本波未使用")
                if pe["is_afk_in_tf"]:
                    crime_notes.append(f"{pe['pos']}号位{pe['hero_short_zh']}{pe['afk_farm_zh']}")
            if crime_notes:
                reasons.append(f"② 关键机制记录：{'；'.join(crime_notes)}。")
            else:
                top_own = max(own_p_exec, key=lambda x: x["damage"]) if own_p_exec else None
                if top_own:
                    reasons.append(
                        f"② 技能与保命衔接：本方 {top_own['pos']}号位 {top_own['hero_short_zh']} 倾泻全队最高 {top_own['damage']:,} 伤害（{'、'.join(top_own['abilities_used_zh'][:3]) or '平A输出'}）。"
                    )

            # ③ 双方团战火力对账
            top_opp = opp_p_exec[0] if opp_p_exec else None
            top_own = max(own_p_exec, key=lambda x: x["damage"]) if own_p_exec else None
            reasons.append(
                f"③ 团战火力悬殊对账：本方五人合计打出 {own_dmg:,} 伤害（最高 {top_own['hero_short_zh'] if top_own else '-'} {top_own['damage'] if top_own else 0:,}），"
                f"对手 {o_zh} 轰出 {opp_dmg:,} 伤害（敌方 {top_opp['hero_short_zh'] if top_opp else '-'} 单人 {top_opp['damage'] if top_opp else 0:,} 伤害）。"
            )

            # ④ 连锁地图战果/代价
            if consequence_items:
                label_4 = "④ 团战连锁战果（90秒内）" if (enemy_throne_fell or (enemy_rax_fell and not own_rax_fell) or tone == "praise") else "④ 团战连锁崩盘代价（90秒内）"
                reasons.append(f"{label_4}：{' ➔ '.join(consequence_items[:4])}！")

            return {
                "outcome_badge": badge,
                "outcome_tone": tone,
                "own_kills": own_kills,
                "own_deaths": own_deaths,
                "own_gold_swing": own_gold_swing,
                "own_total_dmg": own_dmg,
                "opp_total_dmg": opp_dmg,
                "root_causes": reasons,
            }

        decisive_score = (
            abs(gold_swing_rad)
            + (rad_k + dire_k) * 550
            + len(consequence_items) * 1400
            + (1800 if start_s >= 1500 else (600 if start_s >= 900 else 0))
        )

        tf_forensics.append({
            "tf_index": len(tf_forensics) + 1,
            "start_sec": start_s,
            "end_sec": end_s,
            "duration_sec": max(1, end_s - start_s),
            "time_range": f"{fmt_mmss(start_s)}–{fmt_mmss(end_s)}",
            "location_zh": location_zh,
            "trigger_zh": trigger_zh,
            "rad_kills": rad_k,
            "dire_kills": dire_k,
            "rad_total_dmg": rad_total_dmg,
            "dire_total_dmg": dire_total_dmg,
            "gold_swing_rad": gold_swing_rad,
            "buybacks": buybacks_list,
            "deaths_coords": deaths_coords,
            "consequence_items": consequence_items,
            "consequence_chain_zh": consequence_chain_zh,
            "second_by_second_script": script_events,
            "players_execution_matrix": players_exec,
            "by_side": {
                "radiant": _build_side_tf_verdict("radiant"),
                "dire": _build_side_tf_verdict("dire"),
            },
            "decisive_score": decisive_score,
            "decisive_rank": None,
        })

    # 标记全场胜负转折权重最高的 Top 3 生死团 (decisive_rank = 1, 2, 3)
    for rank_i, tf_item in enumerate(sorted(tf_forensics, key=lambda x: x["decisive_score"], reverse=True)[:3]):
        tf_item["decisive_rank"] = rank_i + 1
    if len(tf_forensics) > 8:
        tf_forensics = sorted(
            sorted(tf_forensics, key=lambda x: x["decisive_score"], reverse=True)[:8],
            key=lambda x: x["start_sec"],
        )
        for idx_i, tf_item in enumerate(tf_forensics):
            tf_item["tf_index"] = idx_i + 1

    from tactical_microscope_engine import build_tactical_microscope
    microscope = build_tactical_microscope(
        match=match,
        radiant_players=radiant_players,
        dire_players=dire_players,
        hero_const_by_id=hero_const_by_id,
        npc_to_hid=npc_to_hid,
    )

    return {
        "picks_order": picks_order,
        "lane_matchups": lane_matchups,
        "rubick_steal_ledger": rubick_steal_ledger,
        "key_spell_targets": key_spell_targets,
        "courier_graveyard": courier_graveyard,
        "ping_pressure_rank": ping_pressure_rank,
        "focus_fire_matrix": focus_fire_matrix,
        "teamfight_forensics": tf_forensics,
        **microscope,
    }


def build_squad_history_ledger(
    reports_dir: Any,
    roster: Dict[str, Any],
    recent_matches: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    跨比赛汇总「五黑车队多局惯犯与大腿历史总账本」：
    1. 扫描 reports/match_*.json 中已深度解析的所有比赛，统计每位本方队员的：
       - 局数、胜率、场均综合分、场均分锅占比、拿 MVP 次数、当选头号战犯次数、场均阵亡、场均读秒时长
    2. 扫描主视角最近 12 场比赛 (recent_matches)，统计：
       - 开黑组排 vs 单排胜率与 KDA 对比
       - 近期英雄池红黑榜（上分绝活 vs 选出来就跪的背锅英雄）
    """
    import json
    from pathlib import Path
    import dota_analyst

    rdir = Path(reports_dir)
    main_aid = int(roster.get("main_account_id") or 0)
    roster_members_init = dota_analyst.iter_roster_accounts(roster)
    roster_member_by_aid = {
        acc_id: m
        for m in roster_members_init
        for acc_id in m["account_ids"]
    }
    main_aids = {main_aid} if main_aid else set()
    for m_init in roster_members_init:
        if m_init.get("is_main") or (main_aid and main_aid in m_init["account_ids"]):
            main_aids.update(int(x) for x in m_init["account_ids"])
    recent_by_mid = {
        int(rm["match_id"]): rm
        for rm in (recent_matches or [])
        if isinstance(rm, dict) and rm.get("match_id")
    }

    analyzed_matches_summary = []
    loaded_reports_for_growth: List[Dict[str, Any]] = []
    member_stats: Dict[str, Dict[str, Any]] = {}
    duo_buckets: Dict[str, Dict[str, Any]] = {}

    candidate_paths: Dict[str, Path] = {}
    tmp_rdir = Path("/tmp/dota_reports")
    scan_dirs = (rdir, tmp_rdir) if rdir.resolve() == dota_analyst.REPORTS_DIR.resolve() else (rdir,)
    for scan_dir in scan_dirs:
        if scan_dir.exists():
            for mp in scan_dir.glob("match_*.json"):
                candidate_paths[mp.name] = mp

    rep_sources: List[Dict[str, Any]] = []
    seen_mids = set()
    for mpath in sorted(candidate_paths.values(), key=lambda p: p.name, reverse=True):
        try:
            rep_disk = json.loads(mpath.read_text(encoding="utf-8"))
        except Exception:
            continue
        mid_disk = rep_disk.get("match_id")
        if mid_disk:
            seen_mids.add(int(mid_disk))
            rep_sources.append(rep_disk)

    # R1-8: 从 Supabase match_players 表补充/构建总账（无本地 reports/ 目录时完整可用）
    import cloud_store

    cloud_mp_rows = cloud_store.cloud_fetch_match_players(limit=5000)
    if cloud_mp_rows:
        hero_map_l, _ = dota_analyst.get_hero_constants_map(allow_network=False)
        mp_by_mid: Dict[int, List[Dict[str, Any]]] = {}
        for r in cloud_mp_rows:
            m_id_val = int(r.get("match_id") or 0)
            if m_id_val > 0 and m_id_val not in seen_mids:
                mp_by_mid.setdefault(m_id_val, []).append(r)

        for mid_c in sorted(mp_by_mid.keys(), reverse=True):
            m_rows = mp_by_mid[mid_c]
            rad_roster_cnt = sum(
                1
                for r in m_rows
                if r.get("side") == "radiant" and r.get("account_id") in roster_member_by_aid
            )
            dire_roster_cnt = sum(
                1
                for r in m_rows
                if r.get("side") == "dire" and r.get("account_id") in roster_member_by_aid
            )
            has_main_rad = any(
                r.get("side") == "radiant" and r.get("account_id") == main_aid for r in m_rows
            )
            has_main_dire = any(
                r.get("side") == "dire" and r.get("account_id") == main_aid for r in m_rows
            )
            if has_main_rad and not has_main_dire:
                f_side_c = "radiant"
            elif has_main_dire and not has_main_rad:
                f_side_c = "dire"
            else:
                f_side_c = "radiant" if rad_roster_cnt >= dire_roster_cnt else "dire"

            own_rows_c = sorted(
                [r for r in m_rows if r.get("side") == f_side_c],
                key=lambda r: (int(r.get("pos") or 99), int(r.get("player_slot") or 0)),
            )
            if not own_rows_c:
                continue
            won_c = bool(own_rows_c[0].get("won"))
            rad_kills = sum(int(r.get("kills") or 0) for r in m_rows if r.get("side") == "radiant")
            dire_kills = sum(int(r.get("kills") or 0) for r in m_rows if r.get("side") == "dire")
            dur_min_c = float(own_rows_c[0].get("duration_min") or 0.0)
            dur_str_c = dota_analyst.format_duration(int(round(dur_min_c * 60)))
            own_players_c = []
            for idx_p, r in enumerate(own_rows_c, 1):
                hid_p = int(r.get("hero_id") or 0)
                hinfo_p = hero_map_l.get(hid_p) or {}
                k_p = int(r.get("kills") or 0)
                d_p = int(r.get("deaths") or 0)
                a_p = int(r.get("assists") or 0)
                sc_p = float(r["score_100"]) if r.get("score_100") is not None else 60.0
                own_players_c.append({
                    "player_slot": int(r.get("player_slot") or 0),
                    "account_id": int(r["account_id"]) if r.get("account_id") is not None else None,
                    "personaname": str(r.get("personaname") or "匿名玩家"),
                    "pos": int(r.get("pos") or idx_p),
                    "hero_id": hid_p,
                    "hero_short_zh": str(r.get("hero_short_zh") or hinfo_p.get("short_zh") or ""),
                    "hero_img": hinfo_p.get("img") or "",
                    "kills": k_p,
                    "deaths": d_p,
                    "assists": a_p,
                    "kda": f"{k_p}/{d_p}/{a_p}",
                    "dead_seconds": 0,
                    "rating_score_100": sc_p,
                    "blame_share_pct": float(r.get("blame_share_pct") or 0.0),
                    "contrib_share_pct": float(r.get("contrib_share_pct") or 0.0),
                    "is_me": bool(r.get("account_id") is not None and int(r["account_id"]) in main_aids),
                })

            rep_sources.append({
                "match_id": mid_c,
                "start_time": None,
                "duration_min": dur_min_c,
                "duration_str": dur_str_c,
                "score": f"{rad_kills}:{dire_kills}",
                "focus_side": f_side_c,
                "radiant_win": won_c if f_side_c == "radiant" else (not won_c),
                "is_parsed": True,
                "radiant_pos_1_to_5": own_players_c if f_side_c == "radiant" else [],
                "dire_pos_1_to_5": own_players_c if f_side_c == "dire" else [],
                "deep_forensics": {},
            })

    rep_sources.sort(key=lambda r: int(r.get("match_id") or 0), reverse=True)

    for rep in rep_sources:
        if True:
            mid = rep.get("match_id")
            if not mid:
                continue
            loaded_reports_for_growth.append(rep)
            f_side = rep.get("focus_side") or "dire"
            own_list = rep.get("radiant_pos_1_to_5") if f_side == "radiant" else rep.get("dire_pos_1_to_5")
            if not own_list:
                continue

            won = (f_side == "radiant" and bool(rep.get("radiant_win"))) or (
                f_side == "dire" and not bool(rep.get("radiant_win"))
            )
            gc = rep.get("grok_coaching") if isinstance(rep.get("grok_coaching"), dict) else {}
            gc_players = gc.get("players") if isinstance(gc.get("players"), list) else []
            grok_by_pos = {int(gp.get("pos") or 0): gp for gp in gc_players if isinstance(gp, dict) and gp.get("pos")}

            def _eff_score(pl: Dict[str, Any]) -> float:
                gp = grok_by_pos.get(int(pl.get("pos") or 0))
                if gp and gp.get("grok_score") is not None:
                    return float(gp["grok_score"])
                raw_r = float(pl.get("rating_score_100") or pl.get("rating_score") or 60.0)
                return raw_r * 10.0 if raw_r <= 10.5 else raw_r

            def _eff_share(pl: Dict[str, Any]) -> float:
                gp = grok_by_pos.get(int(pl.get("pos") or 0))
                if gp and gp.get("grok_share_pct") is not None:
                    return float(gp["grok_share_pct"])
                return float((pl.get("contrib_share_pct") if won else pl.get("blame_share_pct")) or 20.0)

            if won:
                sorted_contrib = sorted(
                    own_list,
                    key=lambda x: (_eff_share(x), _eff_score(x)),
                    reverse=True,
                )
                mvp_p = sorted_contrib[0] if sorted_contrib else own_list[0]
                runner_up_p = sorted_contrib[1] if len(sorted_contrib) > 1 else mvp_p
                culprit_p = sorted_contrib[-1] if sorted_contrib else own_list[0]
            else:
                sorted_blame = sorted(
                    own_list,
                    key=lambda x: (_eff_share(x), -_eff_score(x)),
                    reverse=True,
                )
                culprit_p = sorted_blame[0] if sorted_blame else own_list[0]
                runner_up_p = sorted_blame[1] if len(sorted_blame) > 1 else culprit_p
                sorted_svp = sorted(
                    own_list,
                    key=lambda x: (_eff_score(x), -_eff_share(x)),
                    reverse=True,
                )
                mvp_p = sorted_svp[0] if sorted_svp else own_list[-1]

            is_parsed_rep = bool(rep.get("is_parsed"))
            mvp_rep_obj = rep.get("mvp") or {}
            match_no_clear = bool((not is_parsed_rep) or won or mvp_rep_obj.get("no_clear_culprit"))
            me_p = next(
                (
                    x
                    for x in own_list
                    if x.get("is_me")
                    or (x.get("account_id") is not None and int(x.get("account_id") or 0) in main_aids)
                ),
                None,
            )
            my_hero = (me_p.get("hero_short_zh") or me_p.get("hero_name") or None) if me_p else None
            my_hero_img = (me_p.get("hero_img") or None) if me_p else None
            my_kda = (
                (
                    me_p.get("kda")
                    or f"{int(me_p.get('kills') or 0)}/{int(me_p.get('deaths') or 0)}/{int(me_p.get('assists') or 0)}"
                )
                if me_p
                else None
            )
            rm_meta = recent_by_mid.get(int(mid)) or {}
            raw_psize = (
                rm_meta.get("party_size")
                if rm_meta.get("party_size") is not None
                else (me_p.get("party_size") if (me_p and me_p.get("party_size") is not None) else rep.get("party_size"))
            )
            if raw_psize is not None:
                eff_party_size = int(raw_psize)
            else:
                roster_own_cnt = sum(
                    1
                    for x in own_list
                    if x.get("account_id") is not None and int(x.get("account_id") or 0) in roster_member_by_aid
                )
                eff_party_size = roster_own_cnt if roster_own_cnt >= 2 else None
            eff_party_label = (
                (f"{eff_party_size}人黑" if eff_party_size >= 2 else "单排")
                if eff_party_size is not None
                else None
            )
            eff_start_time = rep.get("start_time") if rep.get("start_time") is not None else rm_meta.get("start_time")
            analyzed_matches_summary.append({
                "match_id": mid,
                "start_time": eff_start_time,
                "duration_str": rep.get("duration_str") or "",
                "score": rep.get("score") or "",
                "side_zh": "天辉" if f_side == "radiant" else "夜魇",
                "won": won,
                "is_parsed": is_parsed_rep,
                "no_clear_culprit": match_no_clear,
                "has_grok": bool(gc.get("title")),
                "grok_title": gc.get("title") or (rep.get("match_narrative") or {}).get("headline") or "",
                "my_hero": my_hero,
                "my_hero_img": my_hero_img,
                "my_kda": my_kda,
                "party_size": eff_party_size,
                "party_label": eff_party_label,
                "my_grok_score": int(round(_eff_score(me_p))) if me_p else None,
                "my_grok_share_pct": (round(_eff_share(me_p), 1) if (won or is_parsed_rep) else None) if me_p else None,
                "mvp_hero": mvp_p.get("hero_short_zh") or "",
                "mvp_img": mvp_p.get("hero_img") or "",
                "mvp_player": mvp_p.get("personaname") or "",
                "mvp_score_100": int(round(_eff_score(mvp_p))),
                "mvp_contrib_pct": round(_eff_share(mvp_p), 1),
                "runner_up_hero": runner_up_p.get("hero_short_zh") or "",
                "runner_up_img": runner_up_p.get("hero_img") or "",
                "runner_up_player": runner_up_p.get("personaname") or "",
                "runner_up_score_100": int(round(_eff_score(runner_up_p))),
                "runner_up_contrib_pct": round(_eff_share(runner_up_p), 1),
                "culprit_hero": culprit_p.get("hero_short_zh") or "",
                "culprit_img": culprit_p.get("hero_img") or "",
                "culprit_player": culprit_p.get("personaname") or "",
                "culprit_score_100": int(round(_eff_score(culprit_p))),
                "culprit_blame_pct": round(_eff_share(culprit_p), 1) if is_parsed_rep else None,
            })

            df_obj = rep.get("deep_forensics") or {}
            unpressed_rows = ((df_obj.get("unpressed_saves_by_side") or {}).get(f_side) or {}).get("player_rows") or []
            unpressed_by_pos = {int(r.get("pos") or 0): r for r in unpressed_rows}
            space_rows = ((df_obj.get("map_space_by_side") or {}).get(f_side) or {}).get("player_space_rows") or []
            space_by_pos = {int(r.get("pos") or 0): r for r in space_rows}
            item_rows = ((df_obj.get("itemization_audit_by_side") or {}).get(f_side) or {}).get("player_item_rows") or []
            item_by_pos = {int(r.get("pos") or 0): r for r in item_rows}

            for p in own_list:
                raw_aid = p.get("account_id")
                raw_aid_int = int(raw_aid) if isinstance(raw_aid, int) or (isinstance(raw_aid, str) and raw_aid.isdigit()) else None
                roster_member = roster_member_by_aid.get(raw_aid_int) if raw_aid_int else None
                aid = (
                    roster_member["canonical_id"]
                    if roster_member
                    else (dota_analyst.resolve_canonical_account_id(raw_aid, roster) if raw_aid is not None else None)
                )
                pname = p.get("personaname") or "匿名玩家"
                if not aid and pname in ("匿名玩家", "Anonymous"):
                    continue
                pos_p = int(p.get("pos") or 1)
                key = str(aid) if aid else pname
                init_merged_ids = (
                    list(roster_member["account_ids"])
                    if roster_member
                    else ([int(aid)] if aid else [])
                )
                st = member_stats.setdefault(
                    key,
                    {
                        "key": key,
                        "account_id": aid,
                        "merged_account_ids": list(init_merged_ids),
                        "personaname": (roster_member["name"] if roster_member else None) or pname,
                        "is_me": bool((roster_member and roster_member["is_main"]) or (aid and int(aid) == main_aid)),
                        "is_roster_friend": roster_member is not None,
                        "games": 0,
                        "wins": 0,
                        "total_blame_pct": 0.0,
                        "total_contrib_pct": 0.0,
                        "total_rating": 0.0,
                        "mvp_count": 0,
                        "culprit_count": 0,
                        "total_kills": 0,
                        "total_deaths": 0,
                        "total_assists": 0,
                        "total_dead_sec": 0,
                        "unpressed_saves_total": 0,
                        "solo_pickoffs_total": 0,
                        "bad_builds_total": 0,
                        "support_games": 0,
                        "support_grief_count": 0,
                        "support_grief_examples": [],
                        "core_games": 0,
                        "core_choke_count": 0,
                        "core_choke_examples": [],
                        "lane_loss_count": 0,
                        "pos_map": {},
                        "grok_quotes": [],
                        "heroes": [],
                    },
                )
                if raw_aid is not None and int(raw_aid) not in st["merged_account_ids"]:
                    st["merged_account_ids"].append(int(raw_aid))
                st["games"] += 1
                p_sc100 = _eff_score(p)
                p_sh = _eff_share(p)
                gp_cur = grok_by_pos.get(pos_p) or {}
                if won:
                    st["wins"] += 1
                    st["total_contrib_pct"] += p_sh
                    st["total_blame_pct"] += float(p.get("blame_share_pct") or 12.0)
                else:
                    st["total_blame_pct"] += p_sh
                    st["total_contrib_pct"] += float(p.get("contrib_share_pct") or 18.0)
                st["total_rating"] += p_sc100
                if int(p.get("player_slot", -1)) == int(mvp_p.get("player_slot", -2)):
                    st["mvp_count"] += 1
                if (not won) and (not match_no_clear) and int(p.get("player_slot", -1)) == int(culprit_p.get("player_slot", -2)):
                    st["culprit_count"] += 1
                st["total_kills"] += int(p.get("kills") or 0)
                st["total_deaths"] += int(p.get("deaths") or 0)
                st["total_assists"] += int(p.get("assists") or 0)
                st["total_dead_sec"] += int(p.get("dead_seconds") or 0)

                up_r = unpressed_by_pos.get(pos_p) or {}
                st["unpressed_saves_total"] += int(up_r.get("unpressed_core_cnt") or 0)
                sp_r = space_by_pos.get(pos_p) or {}
                st["solo_pickoffs_total"] += int(sp_r.get("solo_pickoff_cnt") or 0)
                it_r = item_by_pos.get(pos_p) or {}
                if it_r.get("grade") == "bad":
                    st["bad_builds_total"] += 1

                # Position tracking
                pm = st["pos_map"].setdefault(
                    pos_p,
                    {"pos": pos_p, "games": 0, "wins": 0, "rating_sum": 0.0, "share_sum": 0.0, "heroes": []},
                )
                pm["games"] += 1
                if won:
                    pm["wins"] += 1
                pm["rating_sum"] += p_sc100
                pm["share_sum"] += p_sh
                pm["heroes"].append(p.get("hero_short_zh") or "")

                # Support duty / greedy itemization audit vs Core choke audit (structured fields only)
                raw_lh10 = (p.get("laning_10m") or {}).get("lh10")
                lh10_val = int(raw_lh10) if isinstance(raw_lh10, (int, float)) else None
                if pos_p in (1, 2, 3) and lh10_val is not None and lh10_val > 0 and lh10_val < 32:
                    st["lane_loss_count"] += 1

                h_short = p.get("hero_short_zh") or ""
                if pos_p in (4, 5):
                    st["support_games"] += 1
                    playstyle_audit = p.get("playstyle_archetype_audit") or {}
                    built_selfish = bool(playstyle_audit.get("built_selfish_core_items"))
                    obs_sen = int(p.get("obs_placed") or 0) + int(p.get("sen_placed") or 0)
                    dur_m = float(rep.get("duration_min") or 30.0)
                    low_wards = bool(rep.get("is_parsed", True) and dur_m >= 25.0 and obs_sen < 4)
                    if built_selfish or it_r.get("grade") == "bad" or low_wards or p_sc100 <= 58.0:
                        st["support_grief_count"] += 1
                        reason_tag = (
                            "核心输出装偏移"
                            if built_selfish or it_r.get("grade") == "bad"
                            else ("视野偏少" if low_wards else f"评分偏低({int(round(p_sc100))}分)")
                        )
                        if len(st["support_grief_examples"]) < 3:
                            st["support_grief_examples"].append(
                                f"#{mid} {pos_p}号位{h_short} ({int(round(p_sc100))}分·{reason_tag})"
                            )
                else:
                    st["core_games"] += 1
                    is_clear_culprit = (
                        (not won)
                        and not match_no_clear
                        and int(p.get("player_slot", -1)) == int(culprit_p.get("player_slot", -2))
                    )
                    if p_sc100 <= 56.0 or is_clear_culprit:
                        st["core_choke_count"] += 1
                        if len(st["core_choke_examples"]) < 3:
                            st["core_choke_examples"].append(
                                f"#{mid} {pos_p}号位{h_short} ({int(round(p_sc100))}分·{'主要责任' if not won else '低迷'})"
                            )

                if gp_cur.get("headline") and len(st["grok_quotes"]) < 4:
                    st["grok_quotes"].append({
                        "match_id": mid,
                        "pos": pos_p,
                        "hero_short_zh": h_short,
                        "won": won,
                        "score": int(round(p_sc100)),
                        "verdict_tag": gp_cur.get("verdict_tag") or "",
                        "headline": gp_cur.get("headline") or "",
                        "practice": gp_cur.get("practice") or "",
                    })

                st["heroes"].append({
                    "match_id": mid,
                    "hero_short_zh": h_short,
                    "hero_img": p.get("hero_img") or "",
                    "pos": pos_p,
                    "kda": p.get("kda") or "",
                    "rating_score": round(p_sc100, 1),
                    "blame_pct": round(p_sh if not won else float(p.get("blame_share_pct") or 0), 1),
                    "contrib_pct": round(p_sh if won else float(p.get("contrib_share_pct") or 20.0), 1),
                    "won": won,
                })

            # 在同一次循环中统计边路双人搭档与中野联动化学反应 (不再二次读取解析 match_*.json)
            if len(own_list) >= 5:
                by_pos = {int(p.get("pos") or 0): p for p in own_list}
                for p_a, p_b, lane_label in [(1, 5, "优势路 1+5"), (3, 4, "劣势路 3+4"), (2, 4, "中野联动 2+4")]:
                    pa = by_pos.get(p_a)
                    pb = by_pos.get(p_b)
                    if not pa or not pb:
                        continue
                    pa_aid = pa.get("account_id")
                    pb_aid = pb.get("account_id")
                    ma = roster_member_by_aid.get(int(pa_aid)) if isinstance(pa_aid, int) or (isinstance(pa_aid, str) and pa_aid.isdigit()) else None
                    mb = roster_member_by_aid.get(int(pb_aid)) if isinstance(pb_aid, int) or (isinstance(pb_aid, str) and pb_aid.isdigit()) else None
                    na = (ma["name"] if ma else None) or pa.get("personaname") or ""
                    nb = (mb["name"] if mb else None) or pb.get("personaname") or ""
                    if na in ("匿名玩家", "Anonymous", "") or nb in ("匿名玩家", "Anonymous", ""):
                        continue
                    dkey = f"{lane_label}:{na}+{nb}"
                    db = duo_buckets.setdefault(
                        dkey,
                        {
                            "lane_label": lane_label,
                            "player_a": na,
                            "player_b": nb,
                            "games": 0,
                            "wins": 0,
                            "total_rating": 0.0,
                            "hero_pairs": [],
                        },
                    )
                    db["games"] += 1
                    if won:
                        db["wins"] += 1

                    def _to_score_100(pl_obj: Dict[str, Any]) -> float:
                        raw_val = float(
                            pl_obj.get("mvp_score")
                            or pl_obj.get("rating_score_100")
                            or pl_obj.get("rating_score")
                            or 60.0
                        )
                        return raw_val * 10.0 if raw_val <= 10.5 else raw_val

                    avg_r_pair = (_to_score_100(pa) + _to_score_100(pb)) / 2.0
                    db["total_rating"] += avg_r_pair
                    db["hero_pairs"].append({
                        "pair_zh": f"{pa.get('hero_short_zh')}+{pb.get('hero_short_zh')}",
                        "won": won,
                    })

    lane_duo_chemistry = []
    for db in duo_buckets.values():
        g = max(1, db["games"])
        wr = round(db["wins"] * 100.0 / g, 1)
        avg_r = round(db["total_rating"] / g, 1)
        if g < 10:
            chem_tag = f"样本不足（{g}局）"
            chem_tone = "warn"
        elif wr >= 60.0 or avg_r >= 72.0:
            chem_tag = "🔥 高胜率搭档 · 建议优先组合" if g >= 20 else "🔥 高胜率搭档"
            chem_tone = "good"
        elif wr <= 25.0 and avg_r < 64.0:
            chem_tag = "💣 低胜率组合 · 建议调整搭配" if g >= 20 else "📉 低胜率组合"
            chem_tone = "bad"
        else:
            chem_tag = "⚖️ 常规磨合组合"
            chem_tone = "warn"
        lane_duo_chemistry.append({
            "lane_label": db["lane_label"],
            "duo_names": f"{db['player_a']} & {db['player_b']}",
            "games": db["games"],
            "wins": db["wins"],
            "win_rate": wr,
            "win_rate_zh": f"{wr}% ({g}局)",
            "avg_rating": avg_r,
            "hero_pairs": db["hero_pairs"][:4],
            "chemistry_tag": chem_tag,
            "chemistry_tone": chem_tone,
        })
    lane_duo_chemistry.sort(key=lambda x: (x["games"], x["win_rate"], x["avg_rating"]), reverse=True)

    squad_members_rank = []
    for st in member_stats.values():
        g = max(1, st["games"])
        avg_blame = round(st["total_blame_pct"] / g, 1)
        avg_contrib = round(st["total_contrib_pct"] / g, 1)
        avg_rating = round(st["total_rating"] / g, 1)
        win_rate = round((st["wins"] / g) * 100, 1)
        avg_deaths = round(st["total_deaths"] / g, 1)
        avg_dead_sec = int(round(st["total_dead_sec"] / g))
        avg_mvp_rate = round(st["mvp_count"] / g, 2)
        avg_unpressed_saves = round(st["unpressed_saves_total"] / g, 2)
        avg_solo_pickoffs = round(st["solo_pickoffs_total"] / g, 2)
        avg_bad_builds = round(st["bad_builds_total"] / g, 2)

        # 汇总该队员的英雄统计（最小样本量门槛：<10局注明样本不足，不做绝活/低胜率定性；>=20局才给建议）
        h_map: Dict[str, Dict[str, Any]] = {}
        for h_item in st["heroes"]:
            hz = h_item["hero_short_zh"]
            hm = h_map.setdefault(
                hz,
                {
                    "hero_short_zh": hz,
                    "hero_img": h_item["hero_img"],
                    "games": 0,
                    "wins": 0,
                    "rating_sum": 0.0,
                    "pos_list": [],
                },
            )
            hm["games"] += 1
            if h_item["won"]:
                hm["wins"] += 1
            hm["rating_sum"] += float(h_item.get("rating_score") or 60.0)
            hm["pos_list"].append(int(h_item.get("pos") or 1))

        h_summary = []
        for hm in h_map.values():
            hg = max(1, hm["games"])
            h_wr = round(hm["wins"] * 100.0 / hg, 1)
            h_avg_r = round(hm["rating_sum"] / hg, 1)
            main_pos = max(set(hm["pos_list"]), key=hm["pos_list"].count) if hm["pos_list"] else 1
            h_summary.append({
                "hero_short_zh": hm["hero_short_zh"],
                "hero_img": hm["hero_img"],
                "games": hm["games"],
                "wins": hm["wins"],
                "losses": hm["games"] - hm["wins"],
                "win_rate": h_wr,
                "win_rate_zh": f"{h_wr}% ({hg}局)",
                "avg_rating": h_avg_r,
                "main_pos": main_pos,
                "sample_status": "样本不足" if hg < 10 else ("可评估" if hg < 20 else "可给建议"),
            })

        sig_sorted = sorted(
            h_summary,
            key=lambda x: (
                1 if x["games"] >= 10 else 0,
                x["wins"],
                x["avg_rating"],
                x["win_rate"],
            ),
            reverse=True,
        )
        signature_heroes = [
            x
            for x in sig_sorted
            if x["games"] >= 10 and (x["win_rate"] >= 50.0 or x["avg_rating"] >= 72.0)
        ][:3]

        cursed_candidates = [
            x
            for x in h_summary
            if x["games"] >= 10 and (x["win_rate"] <= 40.0 or x["avg_rating"] < 62.0)
        ]
        cursed_candidates.sort(
            key=lambda x: (
                x["losses"],
                -x["avg_rating"],
            ),
            reverse=True,
        )
        sig_names = {s["hero_short_zh"] for s in signature_heroes[:1]}
        cursed_heroes = [x for x in cursed_candidates if x["hero_short_zh"] not in sig_names][:3]

        best_hero = signature_heroes[0] if signature_heroes else None
        worst_hero = cursed_heroes[0] if cursed_heroes else None

        # 1-5号位分位置统计（<10局仅显示数字并标注样本不足）
        pos_breakdown = []
        for p_num, pm in sorted(st.get("pos_map", {}).items(), key=lambda kv: kv[1]["games"], reverse=True):
            pg = max(1, pm["games"])
            p_wr = round(pm["wins"] * 100.0 / pg, 1)
            p_ar = round(pm["rating_sum"] / pg, 1)
            top_h = max(set(pm["heroes"]), key=pm["heroes"].count) if pm["heroes"] else ""
            pos_breakdown.append({
                "pos": p_num,
                "pos_label": f"{p_num}号位",
                "games": pm["games"],
                "wins": pm["wins"],
                "win_rate": p_wr,
                "win_rate_zh": f"{p_wr}% ({pg}局)",
                "avg_rating": p_ar,
                "top_hero": top_h,
                "sample_status": "样本不足" if pg < 10 else ("可评估" if pg < 20 else "可给建议"),
            })

        qualified_pos = [x for x in pos_breakdown if x["games"] >= 10]
        best_pos = (
            max(
                qualified_pos,
                key=lambda x: (
                    x["win_rate"] * 0.40 + x["avg_rating"] * 0.60 + min(x["games"], 15) * 2.0
                ),
            )
            if qualified_pos
            else None
        )
        worst_pos_candidates = [
            x
            for x in qualified_pos
            if (x["avg_rating"] < 66.0 or x["win_rate"] <= 40.0)
            and (not best_pos or x["pos"] != best_pos["pos"])
        ]
        worst_pos = (
            min(
                worst_pos_candidates,
                key=lambda x: (x["win_rate"] * 0.45 + x["avg_rating"] * 0.55 - x["games"] * 1.5),
            )
            if worst_pos_candidates
            else None
        )

        sup_g = int(st.get("support_games") or 0)
        sup_grief = int(st.get("support_grief_count") or 0)
        sup_grief_rate = round((sup_grief / max(1, sup_g)) * 100, 1) if sup_g > 0 else 0.0
        core_g = int(st.get("core_games") or 0)
        core_choke = int(st.get("core_choke_count") or 0)
        core_choke_rate = round((core_choke / max(1, core_g)) * 100, 1) if core_g > 0 else 0.0
        lane_loss_c = int(st.get("lane_loss_count") or 0)
        lane_loss_rate = round((lane_loss_c / g) * 100, 1)

        pname_cur = st["personaname"]
        pos_stats_str = "；".join(
            f"{pb['pos_label']} 胜率 {pb['win_rate']}%（{pb['games']}局{' · 样本不足' if pb['games'] < 10 else ''}）· 场均 {pb['avg_rating']}分"
            for pb in pos_breakdown
        )
        if g < 10 or not best_pos:
            pos_verdict = (
                f"跨 {g} 局胜率 {win_rate}%（{g}局 · 样本不足），场均 {avg_rating}/100 分。"
                + (f"各位置数据：{pos_stats_str}。" if pos_stats_str else "")
            )
        elif best_pos and worst_pos:
            pos_verdict = (
                f"高胜率位置为【{best_pos['pos_label']}】（胜率 {best_pos['win_rate']}% ({best_pos['games']}局) · 场均 {best_pos['avg_rating']}分，常选：{best_pos['top_hero']}）；"
                f"低胜率位置为【{worst_pos['pos_label']}】（胜率 {worst_pos['win_rate']}% ({worst_pos['games']}局) · 场均 {worst_pos['avg_rating']}分，常选：{worst_pos['top_hero']}）。"
            )
        else:
            pos_verdict = (
                f"常驻主力位置为【{best_pos['pos_label']}】（胜率 {best_pos['win_rate']}% ({best_pos['games']}局) · 场均 {best_pos['avg_rating']}分，常选：{best_pos['top_hero']}）。"
            )

        flaw_parts = []
        if sup_grief > 0:
            ex_str = "、".join(st.get("support_grief_examples") or [])
            flaw_parts.append(
                f"💸【辅助位本职记录】打4/5号位共 {sup_g} 局中有 {sup_grief} 局（{sup_grief_rate}%）出现出装偏移或视野偏少（记录：{ex_str}）"
            )
        if core_choke > 0:
            ex_c = "、".join(st.get("core_choke_examples") or [])
            flaw_parts.append(
                f"📉【核心位低分记录】打1-3号位共 {core_g} 局中有 {core_choke} 局（{core_choke_rate}%）出现低分或高责任占比（记录：{ex_c}）"
            )
        if st["solo_pickoffs_total"] > 0:
            flaw_parts.append(
                f"🗺️【团战外阵亡统计】跨 {g} 局场均 {avg_solo_pickoffs:.2f} 次团战外阵亡"
            )
        if st["unpressed_saves_total"] > 0 or st["bad_builds_total"] > 0:
            flaw_parts.append(
                f"🧤【保命装与出装记录】场均 {avg_unpressed_saves:.2f} 次阵亡时持有主动保命装本波未使用，场均 {avg_bad_builds:.2f} 局出装偏离常规"
            )
        if not flaw_parts:
            flaw_parts.append(
                f"🛡️【基础数据统计】跨 {g} 局场均阵亡读秒 {avg_dead_sec} 秒。"
            )
        habit_flaws_summary = "；".join(flaw_parts) + "。"

        sig_txt = (
            "、".join(
                f"{h['hero_short_zh']}(胜率{h['win_rate']}% · {h['games']}局 · {h['avg_rating']}分)"
                for h in signature_heroes
            )
            if signature_heroes
            else ""
        )
        cursed_txt = (
            "、".join(
                f"{h['hero_short_zh']}(胜率{h['win_rate']}% · {h['games']}局 · {h['avg_rating']}分)"
                for h in cursed_heroes
            )
            if cursed_heroes
            else ""
        )
        if g < 10:
            bp_mandate = f"当前样本 {g} 局（样本不足），胜率 {win_rate}%（{g}局），场均 {avg_rating} 分。"
        elif g < 20:
            bp_mandate = (
                f"当前样本 {g} 局，胜率 {win_rate}%（{g}局），场均 {avg_rating} 分"
                + (f"，满 10 局代表英雄：{sig_txt}" if sig_txt else "")
                + "（未满 20 局暂不生成选人指引）。"
            )
        else:
            bp_mandate = (
                f"跨 {g} 局选人建议（胜率 {win_rate}% · {g}局）："
                + (f"建议优先选用【{sig_txt}】固定 {best_pos['pos_label'] if best_pos else '主力位'}；" if sig_txt else f"建议固定 {best_pos['pos_label'] if best_pos else '主力位'}；")
                + (
                    f"低胜率英雄【{cursed_txt}】建议少选。"
                    if cursed_txt
                    else (
                        f"位置 {worst_pos['pos_label']}（胜率 {worst_pos['win_rate']}% · {worst_pos['games']}局）建议少客串。"
                        if worst_pos
                        else "保持当前主力位置轮换。"
                    )
                )
            )

        most_played_pos_label = pos_breakdown[0]["pos_label"] if pos_breakdown else "多位置"
        if g < 10:
            role_tag = f"📊 样本不足（{g}局 · 常打{most_played_pos_label}）"
            tag_cls = "neutral"
        elif st["mvp_count"] >= 2 and avg_rating >= 75.0:
            role_tag = f"👑 车队高分主力 · {most_played_pos_label}"
            tag_cls = "carry"
        elif best_pos and best_pos["pos"] in (4, 5) and best_pos["avg_rating"] >= 75.0:
            role_tag = f"🎯 {best_pos['pos_label']}主力"
            tag_cls = "carry"
        elif st["culprit_count"] >= 3 or avg_rating < 66.5:
            role_tag = f"⚠️ {most_played_pos_label}待提升"
            tag_cls = "culprit"
        elif avg_rating >= 74.0:
            role_tag = f"🛡️ {most_played_pos_label}稳定主力"
            tag_cls = "carry"
        else:
            role_tag = f"⚖️ {most_played_pos_label}常客 · 团队轮换"
            tag_cls = "neutral"

        squad_members_rank.append({
            "personaname": st["personaname"],
            "account_id": st["account_id"],
            "merged_account_ids": st.get("merged_account_ids") or ([st["account_id"]] if st.get("account_id") else []),
            "is_me": st["is_me"],
            "is_roster_friend": st["is_roster_friend"],
            "games": st["games"],
            "wins": st["wins"],
            "win_rate": win_rate,
            "win_rate_zh": f"{win_rate}% ({g}局)",
            "sample_status": "样本不足" if g < 10 else ("可评估" if g < 20 else "可给建议"),
            "avg_blame_pct": avg_blame,
            "avg_contrib_pct": avg_contrib,
            "avg_rating": avg_rating,
            "mvp_count": st["mvp_count"],
            "avg_mvp_rate": avg_mvp_rate,
            "culprit_count": st["culprit_count"],
            "avg_kda": f"{st['total_kills']/g:.1f}/{avg_deaths:.1f}/{st['total_assists']/g:.1f}",
            "avg_dead_sec": avg_dead_sec,
            "unpressed_saves_total": st["unpressed_saves_total"],
            "avg_unpressed_saves": avg_unpressed_saves,
            "solo_pickoffs_total": st["solo_pickoffs_total"],
            "avg_solo_pickoffs": avg_solo_pickoffs,
            "bad_builds_total": st["bad_builds_total"],
            "avg_bad_builds": avg_bad_builds,
            "support_games": sup_g,
            "support_grief_count": sup_grief,
            "support_grief_rate": sup_grief_rate,
            "support_grief_examples": st.get("support_grief_examples") or [],
            "core_games": core_g,
            "core_choke_count": core_choke,
            "core_choke_rate": core_choke_rate,
            "core_choke_examples": st.get("core_choke_examples") or [],
            "lane_loss_count": lane_loss_c,
            "lane_loss_rate": lane_loss_rate,
            "pos_breakdown": pos_breakdown,
            "best_pos": best_pos,
            "worst_pos": worst_pos,
            "signature_heroes": signature_heroes,
            "cursed_heroes": cursed_heroes,
            "best_hero": best_hero,
            "worst_hero": worst_hero,
            "habit_diagnosis": {
                "archetype_title": role_tag,
                "pos_verdict": pos_verdict,
                "habit_flaws_summary": habit_flaws_summary,
                "bp_and_team_mandate": bp_mandate,
                "grok_quotes": st.get("grok_quotes") or [],
            },
            "role_tag": role_tag,
            "tag_cls": tag_cls,
            "heroes": st["heroes"][:6],
        })

    # 排序：先把主视角、车队好友、多局共同出场的排在前面，再按场均评分降序展示
    squad_members_rank.sort(
        key=lambda x: (1 if (x["is_me"] or x["is_roster_friend"] or x["games"] > 1) else 0, x["games"], x["avg_rating"]),
        reverse=True,
    )

    # 3. 车队历史场均纪录 (Per-game averages, never cumulative totals)
    core_members = [m for m in squad_members_rank if m["games"] >= 2] or squad_members_rank
    guinness_records = []
    if core_members:
        top_carry = max(core_members, key=lambda x: (x["avg_rating"], x["avg_mvp_rate"]))
        guinness_records.append({
            "title": "👑 车队定海神针 (最高场均分)",
            "holder": top_carry["personaname"],
            "value": f"场均 {top_carry['avg_rating']} 分 · 场均 {top_carry['avg_mvp_rate']:.2f} 次MVP（{top_carry['games']}局）",
            "tone": "good",
        })
        top_bkb_holder = max(core_members, key=lambda x: x["avg_unpressed_saves"])
        if top_bkb_holder["avg_unpressed_saves"] > 0:
            guinness_records.append({
                "title": "💀 场均阵亡持有保命装未按",
                "holder": top_bkb_holder["personaname"],
                "value": f"场均 {top_bkb_holder['avg_unpressed_saves']:.2f} 次阵亡时持有保命装本波未使用（{top_bkb_holder['games']}局）",
                "tone": "bad",
            })
        top_pickoff_holder = max(core_members, key=lambda x: x["avg_solo_pickoffs"])
        if top_pickoff_holder["avg_solo_pickoffs"] > 0:
            guinness_records.append({
                "title": "🗺️ 场均团战外阵亡",
                "holder": top_pickoff_holder["personaname"],
                "value": f"场均 {top_pickoff_holder['avg_solo_pickoffs']:.2f} 次团战外阵亡（{top_pickoff_holder['games']}局）",
                "tone": "bad",
            })
        top_build_holder = max(core_members, key=lambda x: x["avg_bad_builds"])
        if top_build_holder["avg_bad_builds"] > 0:
            guinness_records.append({
                "title": "🎒 场均出装偏离常规",
                "holder": top_build_holder["personaname"],
                "value": f"场均 {top_build_holder['avg_bad_builds']:.2f} 局漏出关键装/克制装（{top_build_holder['games']}局）",
                "tone": "warn",
            })
        top_dead_holder = max(core_members, key=lambda x: x["avg_dead_sec"])
        guinness_records.append({
            "title": "⏳ 场均泉水读秒时长",
            "holder": top_dead_holder["personaname"],
            "value": f"场均黑屏读秒 {top_dead_holder['avg_dead_sec']} 秒 ({top_dead_holder['avg_kda']} · {top_dead_holder['games']}局)",
            "tone": "warn",
        })

    recent_hero_pool, party_summary = _compute_recent_pool_and_party_summary(recent_matches)

    from squad_growth_metrics import (
        aggregate_high_risk_ward_spots,
        build_personal_trends_and_goals,
        compute_duration_and_session_tilt_buckets,
    )
    import cloud_store
    import dota_analyst
    from tools.sync_full_match_history import aggregate_full_history_stats

    high_risk_ward_spots = aggregate_high_risk_ward_spots(loaded_reports_for_growth)
    saved_goals = cloud_store.cloud_fetch_player_goals()
    personal_trends_and_goals = build_personal_trends_and_goals(
        loaded_reports_for_growth,
        roster=roster,
        weekly_goals=saved_goals,
    )

    roster_members_all = dota_analyst.iter_roster_accounts(roster)
    all_roster_aids = sorted({int(aid) for m in roster_members_all for aid in m["account_ids"]})
    pm_rows = cloud_store.cloud_fetch_player_matches(all_roster_aids)
    full_history_stats = aggregate_full_history_stats(pm_rows, roster=roster)
    # JSON-friendly string keys for players
    full_history_stats["players"] = {str(k): v for k, v in (full_history_stats.get("players") or {}).items()}

    tilt_rows: List[Dict[str, Any]] = []
    main_canon_aid = int(dota_analyst.resolve_canonical_account_id((roster or {}).get("main_account_id"), roster) or 0)
    main_all_aids = set()
    for m in roster_members_all:
        if m["canonical_id"] == main_canon_aid:
            main_all_aids.update(int(x) for x in m["account_ids"])
    main_pm_by_mid: Dict[int, Dict[str, Any]] = {}
    for pm in pm_rows:
        if isinstance(pm, dict) and pm.get("match_id") and (not main_all_aids or int(pm.get("account_id") or 0) in main_all_aids):
            mid_pm = int(pm["match_id"])
            if mid_pm not in main_pm_by_mid:
                main_pm_by_mid[mid_pm] = pm
            slot_val = int(pm.get("player_slot") or 0)
            rad_w = bool(pm.get("radiant_win"))
            won_pm = bool(pm["won"]) if pm.get("won") is not None else (rad_w if slot_val < 128 else (not rad_w))
            tilt_rows.append({
                "match_id": mid_pm,
                "start_time": int(pm.get("start_time") or 0),
                "duration": int(pm.get("duration") or 0),
                "won": won_pm,
            })
    for am_item in analyzed_matches_summary:
        pm_meta = main_pm_by_mid.get(int(am_item.get("match_id") or 0))
        if not pm_meta:
            continue
        if am_item.get("start_time") is None and pm_meta.get("start_time"):
            am_item["start_time"] = int(pm_meta["start_time"])
        if am_item.get("party_size") is None and pm_meta.get("party_size") is not None:
            ps_val = int(pm_meta["party_size"])
            am_item["party_size"] = ps_val
            am_item["party_label"] = f"{ps_val}人黑" if ps_val >= 2 else "单排"
    for rm in recent_matches or []:
        if isinstance(rm, dict) and rm.get("match_id"):
            raw_dur = rm.get("duration_sec") if rm.get("duration_sec") is not None else rm.get("duration")
            dur_sec = 0
            if isinstance(raw_dur, (int, float)):
                dur_sec = int(raw_dur)
            elif isinstance(raw_dur, str) and ":" in raw_dur:
                parts = raw_dur.strip().split(":")
                try:
                    dur_sec = int(parts[0]) * 60 + int(parts[1])
                except (ValueError, IndexError):
                    dur_sec = 0
            elif raw_dur is not None:
                try:
                    dur_sec = int(float(raw_dur))
                except (ValueError, TypeError):
                    dur_sec = 0
            if dur_sec <= 0 and rm.get("duration_min"):
                try:
                    dur_sec = int(float(rm.get("duration_min")) * 60)
                except (ValueError, TypeError):
                    dur_sec = 0
            tilt_rows.append({
                "match_id": int(rm["match_id"]),
                "start_time": int(rm.get("start_time") or 0),
                "duration": dur_sec,
                "won": bool(rm.get("won")),
            })
    for rep_item in loaded_reports_for_growth:
        f_side_i = rep_item.get("focus_side") or "dire"
        won_i = (f_side_i == "radiant" and bool(rep_item.get("radiant_win"))) or (
            f_side_i == "dire" and not bool(rep_item.get("radiant_win"))
        )
        tilt_rows.append({
            "match_id": int(rep_item["match_id"]),
            "start_time": int(rep_item.get("start_time") or 0),
            "duration": int(round(float(rep_item.get("duration_min") or 0) * 60)),
            "won": won_i,
        })
    duration_and_session_tilt = compute_duration_and_session_tilt_buckets(tilt_rows)

    return {
        "analyzed_matches": analyzed_matches_summary,
        "squad_members_rank": squad_members_rank,
        "guinness_records": guinness_records,
        "lane_duo_chemistry": lane_duo_chemistry[:8],
        "high_risk_ward_spots": high_risk_ward_spots,
        "personal_trends_and_goals": personal_trends_and_goals,
        "duration_and_session_tilt": duration_and_session_tilt,
        "full_history_stats": full_history_stats,
        "recent_hero_pool": recent_hero_pool,
        "party_summary": party_summary,
    }


_LEDGER_MEM_CACHE: Dict[str, Dict[str, Any]] = {}


def _compute_recent_pool_and_party_summary(
    recent_matches: Optional[List[Dict[str, Any]]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    rm_list = recent_matches or []
    party_games = [m for m in rm_list if int(m.get("party_size") or 1) >= 2]
    solo_games = [m for m in rm_list if int(m.get("party_size") or 1) < 2]
    party_wins = sum(1 for m in party_games if m.get("won"))
    solo_wins = sum(1 for m in solo_games if m.get("won"))

    hero_buckets: Dict[str, Dict[str, Any]] = {}
    for m in rm_list:
        hname = m.get("hero_short_zh") or m.get("hero_name") or "未知"
        hb = hero_buckets.setdefault(
            hname,
            {
                "hero_short_zh": hname,
                "hero_img": m.get("hero_img") or "",
                "games": 0,
                "wins": 0,
                "kills": 0,
                "deaths": 0,
                "assists": 0,
            },
        )
        hb["games"] += 1
        if m.get("won"):
            hb["wins"] += 1
        parts = str(m.get("kda") or "0/0/0").split("/")
        if len(parts) == 3:
            try:
                hb["kills"] += int(parts[0])
                hb["deaths"] += int(parts[1])
                hb["assists"] += int(parts[2])
            except Exception:
                pass

    recent_hero_pool = []
    for hb in hero_buckets.values():
        g = max(1, hb["games"])
        wr = round((hb["wins"] / g) * 100, 1)
        if g < 10:
            h_verdict = f"样本不足 ({g}局)"
        elif g < 20:
            h_verdict = "高胜率" if wr >= 60 else ("胜率合格" if wr >= 50 else "胜率偏低")
        else:
            h_verdict = "建议优先选用" if wr >= 60 else ("胜率合格" if wr >= 50 else "建议少选")
        recent_hero_pool.append({
            "hero_short_zh": hb["hero_short_zh"],
            "hero_img": hb["hero_img"],
            "games": hb["games"],
            "wins": hb["wins"],
            "win_rate": wr,
            "win_rate_zh": f"{wr}% ({g}局)",
            "avg_kda": f"{hb['kills']/g:.1f}/{hb['deaths']/g:.1f}/{hb['assists']/g:.1f}",
            "verdict": h_verdict,
        })
    recent_hero_pool.sort(key=lambda x: (x["games"], x["win_rate"]), reverse=True)
    party_summary = {
        "party_games": len(party_games),
        "party_wins": party_wins,
        "party_win_rate": round((party_wins / max(1, len(party_games))) * 100, 1) if party_games else 0.0,
        "solo_games": len(solo_games),
        "solo_wins": solo_wins,
        "solo_win_rate": round((solo_wins / max(1, len(solo_games))) * 100, 1) if solo_games else 0.0,
    }
    return recent_hero_pool, party_summary


def _ledger_dir_signature(reports_dir: Any, roster: Dict[str, Any]) -> str:
    import hashlib
    import json
    from pathlib import Path
    import cloud_store
    import dota_analyst

    rdir = Path(reports_dir)
    tmp_rdir = Path("/tmp/dota_reports")
    files = []
    for scan_dir in (rdir, tmp_rdir):
        if scan_dir.exists():
            for mp in scan_dir.glob("match_*.json"):
                try:
                    st = mp.stat()
                    files.append((mp.name, int(st.st_mtime_ns), int(st.st_size)))
                except OSError:
                    pass
    files.sort()
    cloud_cfg = cloud_store.get_cloud_config()
    cur_url = cloud_cfg.get("supabase_url") or ""
    cloud_ids = (
        sorted(cloud_store._CLOUD_IDS_CACHE.get("ids") or [])
        if (cur_url and cloud_store._CLOUD_IDS_CACHE.get("url") == cur_url)
        else []
    )
    pm_cache_rows = cloud_store._PLAYER_MATCHES_CACHE.get("rows") or []
    pm_cache_cnt = len(pm_cache_rows) if isinstance(pm_cache_rows, list) else 0
    local_pm_path = Path(__file__).resolve().parent / ".cache" / "player_matches_history.json"
    local_pm_mtime = int(local_pm_path.stat().st_mtime_ns) if local_pm_path.exists() else 0
    local_goals_path = Path("/tmp/dota_reports/player_goals.json")
    local_goals_mtime = int(local_goals_path.stat().st_mtime_ns) if local_goals_path.exists() else 0
    goals_cache_obj = cloud_store._PLAYER_GOALS_CACHE.get("goals")
    main_aid = int((roster or {}).get("main_account_id") or 0)
    players_cnt = len((roster or {}).get("players") or {})
    sig_payload = {
        "engine_version": dota_analyst.ENGINE_VERSION,
        "files": files,
        "cloud_url": cur_url,
        "cloud_ids": cloud_ids,
        "pm_cache_cnt": pm_cache_cnt,
        "local_pm_mtime": local_pm_mtime,
        "local_goals_mtime": local_goals_mtime,
        "goals_cache": goals_cache_obj if isinstance(goals_cache_obj, dict) else None,
    }
    digest = hashlib.sha256(json.dumps(sig_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"{rdir.resolve()}|{main_aid}|{players_cnt}|{len(files)}|{digest}"


def _ledger_cache_file_path(reports_dir: Any) -> Any:
    from pathlib import Path

    rdir = Path(reports_dir).resolve()
    repo_reports = (Path(__file__).resolve().parent / "reports").resolve()
    if rdir == repo_reports:
        return Path("/tmp/dota_reports/squad_ledger.json")
    return rdir / "squad_ledger.json"


def refresh_persisted_squad_ledger(
    reports_dir: Any,
    roster: Dict[str, Any],
    recent_matches: Optional[List[Dict[str, Any]]] = None,
    persist_disk: bool = True,
) -> Dict[str, Any]:
    """在报告入库或花名册变更时计算一次总账并持久化缓存（只读请求设 persist_disk=False）。"""
    import json

    ledger = build_squad_history_ledger(reports_dir, roster, recent_matches or [])
    sig = _ledger_dir_signature(reports_dir, roster)
    core_payload = {
        "_sig": sig,
        "analyzed_matches": ledger.get("analyzed_matches") or [],
        "squad_members_rank": ledger.get("squad_members_rank") or [],
        "guinness_records": ledger.get("guinness_records") or [],
        "lane_duo_chemistry": ledger.get("lane_duo_chemistry") or [],
        "high_risk_ward_spots": ledger.get("high_risk_ward_spots") or [],
        "personal_trends_and_goals": ledger.get("personal_trends_and_goals") or {"players": {}},
        "duration_and_session_tilt": ledger.get("duration_and_session_tilt") or {},
        "full_history_stats": ledger.get("full_history_stats") or {},
    }
    _LEDGER_MEM_CACHE[str(reports_dir)] = core_payload
    if persist_disk:
        cpath = _ledger_cache_file_path(reports_dir)
        try:
            cpath.parent.mkdir(parents=True, exist_ok=True)
            cpath.write_text(json.dumps(core_payload, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
    return ledger


def load_or_build_squad_ledger(
    reports_dir: Any,
    roster: Dict[str, Any],
    recent_matches: Optional[List[Dict[str, Any]]] = None,
    allow_write: bool = True,
) -> Dict[str, Any]:
    """请求时直接读取预计算好的总账缓存，不重复解析全部 match_*.json。"""
    import json

    sig = _ledger_dir_signature(reports_dir, roster)
    cached_core = _LEDGER_MEM_CACHE.get(str(reports_dir))
    if not isinstance(cached_core, dict) or cached_core.get("_sig") != sig:
        cpath = _ledger_cache_file_path(reports_dir)
        if cpath.exists():
            try:
                disk_core = json.loads(cpath.read_text(encoding="utf-8"))
                if isinstance(disk_core, dict) and disk_core.get("_sig") == sig:
                    cached_core = disk_core
                    _LEDGER_MEM_CACHE[str(reports_dir)] = cached_core
            except Exception:
                cached_core = None

    if not isinstance(cached_core, dict) or cached_core.get("_sig") != sig:
        return refresh_persisted_squad_ledger(reports_dir, roster, recent_matches, persist_disk=allow_write)

    recent_hero_pool, party_summary = _compute_recent_pool_and_party_summary(recent_matches)
    return {
        "analyzed_matches": cached_core.get("analyzed_matches") or [],
        "squad_members_rank": cached_core.get("squad_members_rank") or [],
        "guinness_records": cached_core.get("guinness_records") or [],
        "lane_duo_chemistry": cached_core.get("lane_duo_chemistry") or [],
        "high_risk_ward_spots": cached_core.get("high_risk_ward_spots") or [],
        "personal_trends_and_goals": cached_core.get("personal_trends_and_goals") or {"players": {}},
        "duration_and_session_tilt": cached_core.get("duration_and_session_tilt") or {},
        "full_history_stats": cached_core.get("full_history_stats") or {},
        "recent_hero_pool": recent_hero_pool,
        "party_summary": party_summary,
    }


def build_pregame_strategy_plan(
    own_picks: List[Dict[str, Any]],
    enemy_picks: List[Dict[str, Any]],
    roster: Dict[str, Any],
    heroes_by_id: Dict[int, Dict[str, Any]],
) -> Dict[str, Any]:
    """
    赛前五黑 BP 锦囊与三阶段作战室引擎：
    输入本方 1~5 号位选人 + 可选敌方 1~5 号位选人，
    立即输出：
    - 阵容六维评分与评级
    - 本局核心赢法 (Win Condition) 与 绝对翻车红线 (Lose Condition)
    - 必打核心技能 Combo 配合链与语音口令
    - 前期对线 (0-10m) / 中期节奏 (10-25m) / 后期团战 (25m+) 三阶段团队作战纲领
    - 1~5 号位每人专属出装与阶段任务小抄卡
    - 群聊/语音一键复制文本简报
    """
    pos_names_cfg = (roster or {}).get("default_pos_names") or {}
    default_teammates = {
        1: pos_names_cfg.get("1") or (roster or {}).get("main_name") or "1号位主核",
        2: pos_names_cfg.get("2") or "2号位中单",
        3: pos_names_cfg.get("3") or "3号位前排",
        4: pos_names_cfg.get("4") or "4号位游走",
        5: pos_names_cfg.get("5") or "5号位辅助",
    }

    ROLE_LABELS = {
        1: "1号位 · 优势路主核",
        2: "2号位 · 中路节奏核",
        3: "3号位 · 劣势路前排",
        4: "4号位 · 半辅助游走",
        5: "5号位 · 纯辅助视野",
    }

    ROLE_DEFAULT_ITEMS = {
        1: ["狂战斧 / 雷锤 (刷钱装)", "分身斧 / 双刀 (解状态)", "黑皇杖 BKB (团战刚需)", "深渊之刃 / 撒旦 (终局收割)"],
        2: ["魔瓶 + 属性鞋 (控符推线)", "跳刀 / 阿托斯 / 紫苑 (带节奏)", "黑皇杖 BKB / 希瓦 (中期接团)", "羊刀 / 刷新球 (后期决胜)"],
        3: ["护腕/魂戒 + 相位/秘法鞋", "跳刀 (12-15分钟第一波开雾)", "赤红甲 / 笛子 / 刃甲 (团队前排)", "黑皇杖 BKB / 莲花球 (二波切入)"],
        4: ["风灵之纹 + 真假眼 + 诡计之雾", "微光披风 / 推推杖 (救人拉扯)", "跳刀 / 阿托斯 (先手留人)", "羊刀 / 盘子 (后期保命控场)"],
        5: ["真假眼 + 榴弹 + 仙灵火 + 魔棒", "秘法鞋 + 微光披风 / 推推杖", "以太之镜 / 梅肯斯姆 (站位与奶量)", "全包真眼/粉 + 诡计之雾"],
    }

    HERO_CUSTOM_ITEMS = {
        8: ["狂战斧 / 电锤", "分身斧 (解沉默)", "阿哈利姆神杖(A杖小无敌斩)", "冰眼 / 蝴蝶 / 迅疾闪光"],
        45: ["秘法鞋 -> 以太之镜 (拆解)", "微光披风 / 达贡之神力", "阿哈利姆魔晶 (插棒子群吸)", "镇魂石 / 黑皇杖"],
        97: ["秘法/假腿 + 跳刀 (绝对核心)", "鱼叉 (连招必出)", "黑皇杖 BKB (防打断大招)", "刷新球 / 希瓦之守护"],
        9: ["秘法/卫士胫甲", "阿托斯之棍 (稳中穿云箭)", "微光披风 / 推推杖", "莲花球 / 羊刀"],
        26: ["静谧之鞋 + 魔杖", "跳刀 (瞬发先手变羊)", "以太之镜 + 阿哈利姆魔晶(魔免吸蓝)", "微光披风 / 推推杖"],
        49: ["假腿 + 臂章 / 雷锤", "跳刀 (瞬发神龙摆尾)", "黑皇杖 BKB", "强袭胸甲 / 大隐刀"],
        44: ["假腿 + 狂战斧", "黯灭 (第一波秒后排)", "黑皇杖 BKB (必出)", "深渊之刃 / 撒旦之邪力"],
        76: ["假腿 + 巫师之刃", "飓风长戟 (大推推)", "黑皇杖 BKB", "邪恶镰刀(羊刀) / 希瓦"],
        29: ["秘法鞋 + 护腕", "跳刀 / 梅肯斯姆 -> 大鞋", "魔晶 (锚链捆人)", "刷新球 (双大毁灭)"],
        86: ["秘法鞋 -> 以太之镜", "跳刀 / 推推杖", "阿哈利姆神杖 (偷双技能)", "微光披风 / 羊刀"],
        32: ["假腿 + 散失之刃", "分身斧 (解粉)", "阿哈利姆神杖 (切入群伤)", "大晕锤 / 否决坠饰"],
        99: ["先锋盾 / 秘法鞋", "永世法衣 + 血精石", "阿哈利姆魔晶 + 神杖(背刺齐射)", "莲花球 / 强袭"],
        30: ["秘法鞋 + 魔棒", "微光披风 (隐身放大招)", "阿哈利姆魔晶 (巫毒化身保命)", "阿哈利姆神杖 (弹射死亡守卫)"],
    }

    own_players: List[Dict[str, Any]] = []
    for idx, item in enumerate(own_picks[:5]):
        pos = int(item.get("pos") or (idx + 1))
        hid = int(item.get("hero_id") or 0)
        hinfo = heroes_by_id.get(hid) or {}
        short_zh = hinfo.get("short_zh") or item.get("hero_short_zh") or f"英雄#{hid}"
        player_name = item.get("player_name") or default_teammates.get(pos, f"{pos}号位队友")
        arch = get_hero_archetype({"hero_id": hid, "pos": pos, "hero_short_zh": short_zh})
        own_players.append({
            "player_slot": 128 + idx,
            "pos": pos,
            "pos_label": ROLE_LABELS.get(pos, f"{pos}号位"),
            "hero_id": hid,
            "hero_short_zh": short_zh,
            "hero_name": hinfo.get("full_zh") or short_zh,
            "hero_img": hinfo.get("img") or "",
            "hero_icon": hinfo.get("icon") or "",
            "personaname": player_name,
            "side": "夜魇",
            "kda": "0/0/0",
            "gpm": 500,
            "net_worth": 15000,
            "hero_damage": 18000,
            "tower_damage": 3000,
            "kill_participation_pct": 65,
            "deaths": 3,
            "ability_uses_rich": [{"zh_name": s, "count": 0} for s in (arch.get("key_spells") or [])],
            "active_item_uses": {},
        })

    own_players.sort(key=lambda x: x["pos"])

    enemy_players: List[Dict[str, Any]] = []
    for idx, item in enumerate(enemy_picks[:5]):
        pos = int(item.get("pos") or (idx + 1))
        hid = int(item.get("hero_id") or 0)
        if hid <= 0:
            continue
        hinfo = heroes_by_id.get(hid) or {}
        short_zh = hinfo.get("short_zh") or item.get("hero_short_zh") or f"英雄#{hid}"
        arch = get_hero_archetype({"hero_id": hid, "pos": pos, "hero_short_zh": short_zh})
        enemy_players.append({
            "player_slot": idx,
            "pos": pos,
            "pos_label": ROLE_LABELS.get(pos, f"{pos}号位"),
            "hero_id": hid,
            "hero_short_zh": short_zh,
            "hero_name": hinfo.get("full_zh") or short_zh,
            "hero_img": hinfo.get("img") or "",
            "hero_icon": hinfo.get("icon") or "",
            "personaname": f"敌方{pos}号位",
            "side": "天辉",
            "kda": "0/0/0",
            "gpm": 500,
            "net_worth": 15000,
            "hero_damage": 18000,
            "tower_damage": 3000,
            "kill_participation_pct": 60,
            "deaths": 4,
            "ability_uses_rich": [{"zh_name": s, "count": 0} for s in (arch.get("key_spells") or [])],
            "active_item_uses": {},
        })

    padded_enemy = list(enemy_players)
    while len(padded_enemy) < 5:
        pnum = len(padded_enemy) + 1
        padded_enemy.append({
            "player_slot": pnum - 1,
            "pos": pnum,
            "pos_label": ROLE_LABELS.get(pnum, f"{pnum}号位"),
            "hero_id": 0,
            "hero_short_zh": f"敌方{pnum}号位",
            "hero_name": f"敌方{pnum}号位",
            "hero_img": "",
            "personaname": f"敌方{pnum}号位",
            "side": "天辉",
            "kda": "0/0/0",
            "gpm": 450,
            "net_worth": 12000,
            "hero_damage": 12000,
            "tower_damage": 1500,
            "kill_participation_pct": 55,
            "deaths": 5,
            "ability_uses_rich": [],
            "active_item_uses": {},
        })

    draft_by_side = build_draft_and_combo_analysis(
        radiant_players=padded_enemy,
        dire_players=own_players,
        match={"match_id": 0, "duration": 2100},
        focus_side="dire",
    )
    draft_eval = draft_by_side.get("dire") or {}

    p1 = own_players[0] if len(own_players) > 0 else {"hero_short_zh": "1号位", "personaname": "1号位", "hero_id": 0}
    p2 = own_players[1] if len(own_players) > 1 else {"hero_short_zh": "2号位", "personaname": "2号位", "hero_id": 0}
    p3 = own_players[2] if len(own_players) > 2 else {"hero_short_zh": "3号位", "personaname": "3号位", "hero_id": 0}
    p4 = own_players[3] if len(own_players) > 3 else {"hero_short_zh": "4号位", "personaname": "4号位", "hero_id": 0}
    p5 = own_players[4] if len(own_players) > 4 else {"hero_short_zh": "5号位", "personaname": "5号位", "hero_id": 0}

    dims = draft_eval.get("scores") or {}
    push_score = dims.get("push", 70)
    pick_score = dims.get("pick", 70)
    tf_score = dims.get("tf", 75)
    overall_score = int(round(sum(dims.values()) / max(1, len(dims)))) if dims else 78

    if push_score >= 76:
        tempo_style = "中前期抱团推进体系（12–22分钟拔光外塔、压制野区）"
    elif pick_score >= 80:
        tempo_style = "高频开雾抓人提速体系（靠3/4/5号位先手不断制造多打少）"
    elif tf_score >= 82:
        tempo_style = "大招团战阵地体系（围绕3号位大招CD与肉山盾逼团）"
    else:
        tempo_style = "四保一/双核刷钱后期体系（拉扯带线拖大哥BKB与三件套成型）"

    enemy_names = [ep["hero_short_zh"] for ep in enemy_players]
    enemy_core_names = [ep["hero_short_zh"] for ep in enemy_players if ep["pos"] in (1, 2)]
    enemy_tank_names = [ep["hero_short_zh"] for ep in enemy_players if ep["pos"] == 3]
    enemy_sup_names = [ep["hero_short_zh"] for ep in enemy_players if ep["pos"] in (4, 5)]

    target_priority_text = (
        f"第一优先级秒敌方后排救人/反手 ({' / '.join(enemy_sup_names)}) 或脆皮输出核 ({' / '.join(enemy_core_names)})；"
        f"绝对禁止把第一套爆发全砸在敌方前排 ({' / '.join(enemy_tank_names) or '3号位肉盾'}) 身上！"
        if enemy_players
        else "第一优先级切敌方 4/5 号位救人辅助与无 BKB 的 2 号位；绝对禁止把第一波关键技能交在敌方 3 号位前排肉盾身上！"
    )

    win_condition = (
        f"本局核心赢法【{tempo_style}】：前10分钟保住 1号位 {p1['hero_short_zh']}({p1['personaname']}) 基础补刀与 2号位 {p2['hero_short_zh']} 等级；"
        f"12–18分钟围绕 3号位 {p3['hero_short_zh']} 与 4/5号位 ({p4['hero_short_zh']}+{p5['hero_short_zh']}) 第一件先手装抱团开雾，"
        f"抓人后立刻用 {p1['hero_short_zh']}/{p2['hero_short_zh']} 推掉中一塔与优势路一塔，20分钟准时控魔晶与一代肉山盾平推！"
    )

    lose_condition = (
        f"本局最忌讳死法：① 10–20分钟 {p3['hero_short_zh']} 与 {p1['hero_short_zh']} 各刷各的、辅助单走做眼连死；"
        f"② 打赢团战满血回头打野不推塔，白白浪费强势期；"
        f"③ 25分钟后没视野没盾强冲高地，或者团战技能全砸敌方前排肉盾导致后排被切烂。"
    )

    pregame_combos = []
    for c in draft_eval.get("combos") or []:
        c_heroes = [
            {
                "pos": h.get("pos", 1),
                "hero_short_zh": h.get("short") or h.get("hero_short_zh") or "",
                "hero_img": h.get("img") or h.get("hero_img") or "",
                "personaname": h.get("personaname") or "",
            }
            for h in (c.get("heroes") or [])
        ]
        pregame_combos.append({
            "name": c.get("title") or c.get("name") or "核心技能联动",
            "heroes": c_heroes,
            "mechanic": c.get("how_to_play") or c.get("mechanic") or "",
            "voice_call": f"语音口令：「{' → '.join(h['hero_short_zh'] for h in c_heroes)}，倒数 3-2-1 同步交技能，集火秒后排！」",
            "tip": "开团前先在语音里报大招/跳刀 CD 和蓝量，严禁一个人跳上去队友还在三百码外看戏。",
        })

    from hero_profiles_126 import get_hero_profile_126, build_hero_matchup_dossier

    prof1 = get_hero_profile_126(int(p1.get("hero_id") or 0), 1, p1.get("hero_short_zh", ""))
    prof2 = get_hero_profile_126(int(p2.get("hero_id") or 0), 2, p2.get("hero_short_zh", ""))
    prof3 = get_hero_profile_126(int(p3.get("hero_id") or 0), 3, p3.get("hero_short_zh", ""))
    prof4 = get_hero_profile_126(int(p4.get("hero_id") or 0), 4, p4.get("hero_short_zh", ""))
    prof5 = get_hero_profile_126(int(p5.get("hero_id") or 0), 5, p5.get("hero_short_zh", ""))

    ep_by_pos = {int(ep.get("pos") or 0): ep for ep in enemy_players}
    opp_offlane_str = (
        f"（预计对阵敌方 {ep_by_pos[3]['hero_short_zh']}" + (f" + {ep_by_pos[4]['hero_short_zh']}）" if 4 in ep_by_pos else "）")
        if 3 in ep_by_pos else ""
    )
    opp_mid_str = f"（预计 1v1 对决敌方 {ep_by_pos[2]['hero_short_zh']}）" if 2 in ep_by_pos else ""
    opp_safelane_str = (
        f"（预计施压敌方 {ep_by_pos[1]['hero_short_zh']}" + (f" + {ep_by_pos[5]['hero_short_zh']}）" if 5 in ep_by_pos else "）")
        if 1 in ep_by_pos else ""
    )

    early_plan = {
        "title": "前期对线与抢符 (0–10分钟) · 英雄专属对线化学反应 & 击杀窗口",
        "lanes": [
            {
                "lane": f"优势路 (1号位 + 5号位){opp_offlane_str}",
                "heroes": f"{p1['hero_short_zh']} ({p1['personaname']}) + {p5['hero_short_zh']} ({p5['personaname']})",
                "tasks": [
                    f"【英雄对线机制】{p1['hero_short_zh']}（{prof1.get('early_rule','稳住正反补')}）搭档 {p5['hero_short_zh']}（招牌：{'/'.join((prof5.get('signature_abilities') or ['控制消耗'])[:2])}），2级优先抢远程兵找第一波耗血/击杀窗口。",
                    f"第1–2分钟 {p5['hero_short_zh']} 准时拉小野消兵线并封死敌方大野，3分钟 / 6分钟提前卡位抢莲花池。",
                    f"10分钟硬指标：{p1['hero_short_zh']} 正补 ≥ 55 刀、阵亡 ≤ 1 次。",
                ],
            },
            {
                "lane": f"中路单挑 (2号位){opp_mid_str}",
                "heroes": f"{p2['hero_short_zh']} ({p2['personaname']})",
                "tasks": [
                    f"【中单英雄机制】{p2['hero_short_zh']}：{prof2.get('early_rule','利用核心技能推线控符')}。",
                    f"2分钟 / 4分钟前提前用《{(prof2.get('signature_abilities') or ['AOE技能'])[0]}》推线进塔控水符；6分钟配合 4号位 {p4['hero_short_zh']} 控第一个强化神符提速抓边。",
                ],
            },
            {
                "lane": f"劣势路抗压/施压 (3号位 + 4号位){opp_safelane_str}",
                "heroes": f"{p3['hero_short_zh']} ({p3['personaname']}) + {p4['hero_short_zh']} ({p4['personaname']})",
                "tasks": [
                    f"【双人施压组合】{p3['hero_short_zh']}（{prof3.get('early_rule','占线抗压消耗')}）配合 {p4['hero_short_zh']}（招牌：{'/'.join((prof4.get('signature_abilities') or ['游走控制'])[:2])}）强压敌方1号位补刀。",
                    f"{p4['hero_short_zh']} 开局封敌方小野，4分钟 / 6分钟准时去中路帮 {p2['hero_short_zh']} 抢符；7分钟必控经验神龛(智慧符)。",
                ],
            },
        ],
    }

    mid_plan = {
        "title": "中期抱团与控图 (10–25分钟) · 英雄强势期兑现 & 抓谁推哪",
        "key_timings": [
            f"【12–15分钟 第一波大节奏】围绕 3号位 {p3['hero_short_zh']}（{prof3.get('mid_rule','第一件先手装')}）与 2号位 {p2['hero_short_zh']}，由 {p5['hero_short_zh']} 买雾叫齐 2/3/4/5 四人抓敌方核心并拔掉中一塔！",
            f"【15–20分钟 英雄发育与控图】{p1['hero_short_zh']} 执行专属中期方针：{prof1.get('mid_rule','高效刷出核心三件套')}；{p4['hero_short_zh']}+{p5['hero_short_zh']} 将假眼铺入敌方主野区高台。",
            f"【20分钟 命脉魔晶与一代肉山盾】20分钟准时控下痛苦魔方（尤其关注本队质变魔晶），抓死敌方任一核心后立刻五人进肉山坑为 {p1['hero_short_zh']}/{p2['hero_short_zh']} 控下一代不朽盾！",
        ],
    }

    late_plan = {
        "title": "后期盾团与高地终结 (25分钟后) · 集火优先级 & 买活铁律",
        "rules": [
            f"【团战集火优先级】{target_priority_text}",
            f"【大核决胜准则】{p1['hero_short_zh']}：{prof1.get('late_rule','带BKB与核心装完成正面收割')}；{p3['hero_short_zh']}：{prof3.get('late_rule','顶前排先手开团吸收第一波集火')}。",
            f"【上高地唯一铁律】不带肉山盾绝不硬冲三塔！带盾上高时，只留盾核站在高地拆建筑，其余四人退在台阶下卡视野随时反手救人或秒跳！",
        ],
    }

    role_guides = []
    for p in own_players:
        pos = p["pos"]
        hid = p["hero_id"]
        prof = get_hero_profile_126(hid, pos, p["hero_short_zh"])
        dos = build_hero_matchup_dossier(p, own_players, enemy_players, duration_min=0.0, won=False)
        item_rule_str = dos.get("pos_item_rule") or prof.get("core_item_hint") or ""
        parsed_items = [x.strip() for x in item_rule_str.replace("->", "+").split("+") if x.strip()]
        rec_items = parsed_items if parsed_items else (HERO_CUSTOM_ITEMS.get(hid) or ROLE_DEFAULT_ITEMS.get(pos, []))
        partner = (dos.get("best_ally_synergies") or [""])[0] or f"与本队核心技能链保持同步切入"
        golden_rule = f"【本位置打法】{dos.get('pos_playstyle', '')} 【绝对禁忌】{dos.get('pos_taboo', '')}"

        role_guides.append({
            "pos": pos,
            "pos_label": dos.get("pos_role_title") or p["pos_label"],
            "player_name": p["personaname"],
            "hero_id": hid,
            "hero_short_zh": p["hero_short_zh"],
            "hero_img": p["hero_img"],
            "pos_role_title": dos.get("pos_role_title", p["pos_label"]),
            "pos_playstyle": dos.get("pos_playstyle", ""),
            "pos_taboo": dos.get("pos_taboo", ""),
            "roles": prof.get("roles") or [],
            "key_spells": prof.get("signature_abilities") or [],
            "recommended_items": rec_items,
            "partner_synergy": partner,
            "counters_enemies": dos.get("counters_enemies") or [],
            "countered_by_enemies": dos.get("countered_by_enemies") or [],
            "golden_rule": golden_rule,
        })

    combo_lines_txt = "\n".join(
        f"  • 【{c['name']}】({' + '.join(h['hero_short_zh'] for h in c['heroes'])})：{c['mechanic']}"
        for c in pregame_combos[:3]
    )
    role_lines_txt = "\n".join(
        f"  [{rg['pos_role_title']} · {rg['player_name']}]\n"
        f"    🛠️ 出装：{' → '.join(rg['recommended_items'][:4])}\n"
        f"    🤝 配合：{rg['partner_synergy']}\n"
        + (f"    ⚔️ 克制：{rg['counters_enemies'][0]}\n" if rg.get("counters_enemies") else "")
        + (f"    🛡️ 提防：{rg['countered_by_enemies'][0]}\n" if rg.get("countered_by_enemies") else "")
        + f"    🚫 禁忌：{rg['pos_taboo']}"
        for rg in role_guides
    )

    grade_str = draft_eval.get("grade") or "A 级 · 扎实五黑体系"
    chat_brief_text = (
        f"⚔️【五黑赛前10秒作战锦囊 · 阵容评级 {grade_str} ({overall_score}分 [通用知识])】\n"
        f"👉 本方阵容：1.{p1['hero_short_zh']}({p1['personaname']}) / 2.{p2['hero_short_zh']}({p2['personaname']}) / 3.{p3['hero_short_zh']}({p3['personaname']}) / 4.{p4['hero_short_zh']}({p4['personaname']}) / 5.{p5['hero_short_zh']}({p5['personaname']})\n"
        f"{('👉 敌方阵容：' + ' / '.join(enemy_names) + chr(10)) if enemy_names else ''}"
        f"🏆 本局赢法：{win_condition}\n"
        f"⚠️ 翻车红线：{lose_condition}\n"
        f"🔥 必打技能配合：\n{combo_lines_txt}\n"
        f"🎯 团战集火：{target_priority_text}\n"
        f"📋 1~5号位专属打法、克制与出装：\n{role_lines_txt}"
    )

    real_data_bp_stats = compute_real_bp_matchup_stats(
        own_picks=own_players,
        enemy_picks=enemy_players,
    )

    return {
        "own_players": own_players,
        "enemy_players": enemy_players,
        "grade": grade_str,
        "overall_score": overall_score,
        "score_source": "general_knowledge",
        "score_source_zh": "通用知识",
        "dimensions": draft_eval.get("scores") or {},
        "real_data_bp_stats": real_data_bp_stats,
        "tempo_style": tempo_style,
        "win_condition": win_condition,
        "lose_condition": lose_condition,
        "target_priority": target_priority_text,
        "strengths": draft_eval.get("strengths") or [],
        "weaknesses": draft_eval.get("weaknesses") or [],
        "counter_tips": draft_eval.get("weaknesses") or [],
        "hero_matchup_matrix": draft_eval.get("hero_matchup_matrix") or [],
        "combos": pregame_combos,
        "early_plan": early_plan,
        "mid_plan": mid_plan,
        "late_plan": late_plan,
        "role_guides": role_guides,
        "chat_brief_text": chat_brief_text,
    }



