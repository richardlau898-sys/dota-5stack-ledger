# -*- coding: utf-8 -*-
"""
Dota 2 录像级战术复盘与车队分锅引擎 (ai_coach_engine.py)
基于 OpenDota 录像深度遥测数据 (item_uses, ability_uses, killed_by, killed, life_state_dead, gold_reasons, damage_taken):
1. 1~5 号位六维战力模型 + 全队 100% 责任分摊计算
2. 全场 MVP / 胜方次席 / 败方 SVP / 车队头号背锅位 评选与证据链
3. 主动道具按键审计 (BKB/假腿/微光/跳刀/魔棒使用次数)、技能释放频率审计、黑白屏幕读秒时长、阵亡损失存款、天敌提款机与野怪/防御塔单杀取证
4. 四阶段对局走势复盘与外接大模型接口 (支持 Gemini gemini-3.8-flash / gemini-4-argon 与 OpenAI 兼容接口)
"""

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple
from dota_constants_zh import resolve_patch_name
from hero_profiles_126 import (
    audit_hero_mechanism_and_timing,
    build_hero_matchup_dossier,
    get_hero_profile_126,
)


def clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def evaluate_player_deeply(
    p: Dict[str, Any],
    team_players: List[Dict[str, Any]],
    enemy_players: List[Dict[str, Any]],
    won: bool,
    duration_min: float,
    is_parsed: bool,
    is_turbo: bool,
) -> Dict[str, Any]:
    """
    针对单个玩家的位置 (1~5号位) 进行录像级取证与毒舌复盘:
    生成:
    - radar: 六维能力值 (0~100): farm(发育), damage(输出), tempo(节奏), push(推进), utility(功能), survival(生存)
    - rating_score (1.0 ~ 10.0), rating_tier (S+ / S / A / B / C)
    - mvp_score (0 ~ 100), raw_blame_points (用于计算全队五人分锅百分比)
    - strengths: List[str] (高光与扎实操作证据)
    - weaknesses: List[str] (失误、断档与犯罪现场取证)
    - improvements: List[str] (针对性复盘改进建议)
    - trash_talk: str (群聊/YY一键分锅锐评)
    """
    pos = p.get("pos", 3)
    hero_name = p.get("hero_short_zh") or p.get("hero_name", "未知英雄")
    pname = p.get("personaname", "匿名玩家")
    kills = p.get("kills", 0)
    deaths = p.get("deaths", 0)
    assists = p.get("assists", 0)
    kp = p.get("kill_participation_pct", 0.0)
    gpm = p.get("gold_per_min") or p.get("gpm", 0)
    xpm = p.get("xp_per_min") or p.get("xpm", 0)
    nw = p.get("net_worth", 0)
    lh = p.get("last_hits", 0)
    dn = p.get("denies", 0)
    hdmg = p.get("hero_damage", 0)
    hdmg_share = p.get("hero_damage_share_pct", 0.0)
    tdmg = p.get("tower_damage", 0)
    dmg_taken = p.get("damage_taken", 0)
    heal = p.get("hero_healing", 0)
    stuns = float(p.get("stuns_sec") or 0.0)
    obs = p.get("obs_placed") or 0
    sen = p.get("sen_placed") or 0
    stacked = p.get("camps_stacked") or 0
    smokes = p.get("smokes_bought") or 0
    dusts = p.get("dusts_bought") or 0
    dead_sec = int(p.get("dead_seconds") or 0)
    death_gold_lost = int(p.get("death_gold_lost") or 0)
    buybacks = p.get("buybacks") or 0
    apm = p.get("apm") or 0
    pings = p.get("pings") or 0

    l10 = p.get("laning_10m") or {}
    lh10 = l10.get("lh10")
    dn10 = l10.get("dn10")
    gold10 = l10.get("gold10")
    lane_eff = p.get("lane_efficiency_pct")
    raw_bm = p.get("raw_benchmarks") or {}

    team_tdmg = sum(tp.get("tower_damage", 0) for tp in team_players) or 1
    team_nw = sum(tp.get("net_worth", 0) for tp in team_players) or 1
    team_dmg_taken = sum(tp.get("damage_taken", 0) for tp in team_players) or 1
    nw_share = nw / team_nw * 100.0
    tdmg_share = tdmg / team_tdmg * 100.0
    dmg_taken_share = dmg_taken / team_dmg_taken * 100.0

    my_lane = p.get("raw_lane") if p.get("raw_lane") is not None else p.get("lane")
    same_lane_enemies = [
        ep
        for ep in enemy_players
        if my_lane in (1, 2, 3)
        and (ep.get("raw_lane") if ep.get("raw_lane") is not None else ep.get("lane")) == my_lane
    ]
    if same_lane_enemies:
        if pos in (1, 2, 3):
            core_cands = [ep for ep in same_lane_enemies if int(ep.get("pos") or 0) in (1, 2, 3)]
            opp_same_pos = sorted(core_cands or same_lane_enemies, key=lambda ep: int(ep.get("pos") or 9))[0]
        else:
            sup_cands = [ep for ep in same_lane_enemies if int(ep.get("pos") or 0) in (4, 5)]
            opp_same_pos = sorted(sup_cands or same_lane_enemies, key=lambda ep: int(ep.get("pos") or 0), reverse=True)[0]
    else:
        opp_same_pos = None

    # 1. 计算六维雷达图 (0~100)
    gpm_pct = raw_bm.get("gold_per_min", 0.5)
    dmg_pct = raw_bm.get("hero_damage_per_min", 0.5)
    lh_pct = raw_bm.get("last_hits_per_min", 0.5)
    tdmg_pct = raw_bm.get("tower_damage", 0.5)

    if pos in (1, 2):
        farm_score = clamp(gpm_pct * 75 + lh_pct * 25 + (10 if gpm >= 650 else 0), 15, 99)
    elif pos == 3:
        farm_score = clamp(gpm_pct * 70 + 25, 20, 98)
    else:
        farm_score = clamp(gpm_pct * 65 + 30, 25, 96)

    damage_score = clamp(dmg_pct * 60 + (hdmg_share / 35.0) * 40, 15, 99)
    tempo_score = clamp((kp / 80.0) * 75 + (smokes * 5) + (15 if assists >= 18 else 5), 15, 99)
    if pos in (1, 2, 3):
        push_score = clamp(tdmg_pct * 55 + (tdmg / max(3000.0, duration_min * 180.0)) * 45, 10, 99)
    else:
        push_score = clamp(tdmg_pct * 60 + 30, 20, 95)

    wards_total = obs + sen
    if pos in (4, 5):
        utility_score = clamp(
            35 + min(30, wards_total * 1.4) + min(25, stuns * 0.35) + min(15, (smokes + stacked) * 3.5) + min(10, heal / 500.0),
            20,
            99,
        )
    else:
        utility_score = clamp(
            30 + min(40, stuns * 0.65) + min(20, heal / 400.0) + min(15, (wards_total + smokes + stacked) * 3.0),
            20,
            98,
        )

    deaths_per_10m = deaths / max(1.0, duration_min / 10.0)
    if pos in (1, 2):
        survival_score = clamp(98 - deaths_per_10m * 24, 15, 99)
    elif pos == 3:
        survival_score = clamp(95 - deaths_per_10m * 19, 18, 98)
    else:
        survival_score = clamp(95 - deaths_per_10m * 16, 18, 98)

    radar = {
        "farm": round(farm_score),
        "damage": round(damage_score),
        "tempo": round(tempo_score),
        "push": round(push_score),
        "utility": round(utility_score),
        "survival": round(survival_score),
    }

    # 2. 按位置加权计算综合表现分 (mvp_score 0~100)
    if pos == 1:
        base_score = (
            farm_score * 0.24
            + damage_score * 0.24
            + push_score * 0.20
            + survival_score * 0.18
            + tempo_score * 0.14
        )
    elif pos == 2:
        base_score = (
            damage_score * 0.28
            + tempo_score * 0.22
            + farm_score * 0.18
            + survival_score * 0.16
            + push_score * 0.10
            + utility_score * 0.06
        )
    elif pos == 3:
        base_score = (
            tempo_score * 0.24
            + utility_score * 0.24
            + survival_score * 0.18
            + damage_score * 0.14
            + farm_score * 0.12
            + push_score * 0.08
        )
    elif pos == 4:
        base_score = (
            tempo_score * 0.30
            + utility_score * 0.30
            + survival_score * 0.15
            + damage_score * 0.15
            + farm_score * 0.10
        )
    else:
        base_score = (
            utility_score * 0.38
            + tempo_score * 0.28
            + survival_score * 0.16
            + damage_score * 0.10
            + farm_score * 0.08
        )

    kda_ratio = (kills + assists) / max(1.0, float(deaths))
    bonus = min(8.0, kda_ratio * 1.1) + (3.5 if won else -1.5)
    mvp_score = round(clamp(base_score + bonus, 35.0, 99.0), 1)
    rating_score = round(clamp(mvp_score / 10.0, 4.0, 9.9), 1)

    if won:
        if rating_score >= 9.0:
            rating_tier = "S+ 擎天战神"
        elif rating_score >= 8.3:
            rating_tier = "S 凯旋真核"
        elif rating_score >= 7.6:
            rating_tier = "A 功勋大腿"
        elif rating_score >= 6.8:
            rating_tier = "B+ 稳健功臣"
        else:
            rating_tier = "B 团队拼图"
    else:
        if rating_score >= 8.8:
            rating_tier = "S 孤胆院长"
        elif rating_score >= 8.0:
            rating_tier = "A 尽力大腿"
        elif rating_score >= 7.2:
            rating_tier = "B 随波逐流"
        elif not is_parsed:
            rating_tier = "C 待解析复盘"
        elif rating_score >= 6.6:
            rating_tier = "C 重点短板"
        else:
            rating_tier = "D 关键失误"

    # 3. 录像级数据取证 (去除模板化四字括号，完全用本局真实动作、按键、击杀关系说话)
    strengths: List[str] = []
    weaknesses: List[str] = []
    improvements: List[str] = []
    conclusion_meta: Dict[str, Tuple[str, Optional[List[str]]]] = {}

    def _add_conclusion(
        bucket: List[str],
        txt: str,
        ev: str,
        source_fields: Optional[List[str]] = None,
        prepend: bool = False,
    ) -> None:
        conclusion_meta[txt] = (ev, list(source_fields) if (ev == "measured" and source_fields) else None)
        if prepend:
            bucket.insert(0, txt)
        else:
            bucket.append(txt)

    trash_candidates: List[Tuple[int, str]] = []
    blame_points = max(4.0, 102.0 - mvp_score)

    active_uses = p.get("active_item_uses") or {}
    ability_list = p.get("ability_uses_rich") or []
    killed_by_info = p.get("killed_by_breakdown") or {}
    kills_info = p.get("kills_breakdown") or {}

    # --- (A) 对线期 0-10 分钟真实补刀与对位经济差 ---
    if is_parsed and lh10 is not None and gold10 is not None:
        opp_gold10 = (opp_same_pos.get("laning_10m") or {}).get("gold10") if opp_same_pos else None
        opp_lh10 = (opp_same_pos.get("laning_10m") or {}).get("lh10") if opp_same_pos else None
        opp_hero = (opp_same_pos.get("hero_short_zh") or opp_same_pos.get("hero_name")) if opp_same_pos else "对位"
        gold_diff_10 = (gold10 - opp_gold10) if opp_gold10 is not None else 0

        if pos in (1, 2, 3):
            target_lh = 50 if pos in (1, 2) else 38
            if is_turbo:
                target_lh = int(target_lh * 0.8)
            if lh10 >= target_lh:
                diff_txt = f"，10分钟净压对位 {opp_hero} {gold_diff_10} 金" if gold_diff_10 > 250 else ""
                _add_conclusion(
                    strengths,
                    f"对线基本功扎实：前10分钟交出 {lh10}正/{dn10}反（10m经济 {gold10:,}，效率 {lane_eff or '-'}%）{diff_txt}，撑起了前中期基础节奏。",
                    "measured",
                    ["players[].lh_t", "players[].dn_t", "players[].gold_t", "players[].lane_efficiency_pct"],
                )
            elif lh10 <= (36 if pos in (1, 2) else 28) and not is_turbo:
                blame_points += 14.0
                diff_txt = f"，被对位 {opp_hero}（10m {opp_lh10}刀/{opp_gold10:,}金）拉开了 {abs(gold_diff_10):,} 经济差" if gold_diff_10 < -300 else ""
                _add_conclusion(
                    weaknesses,
                    f"对线期直接崩盘：10分钟仅补了 {lh10} 刀（经济 {gold10:,}，对线效率 {lane_eff or '-'}%）{diff_txt}，塔下补刀和换血细节全部拉胯。",
                    "inferred",
                )
                trash_candidates.append((
                    85,
                    f"@{pname} 10分钟补{lh10}刀，你在线上是跟对面小兵拜了把子舍不得下手吗？对面{opp_hero}刷得像在打人机！",
                ))
                _add_conclusion(
                    improvements,
                    f"{pos}号位 {hero_name} 线上劣势时，前5分钟补不到刀就果断拉双野或摇辅助进野区收屯野，别在线上硬着头皮既漏刀又白送状态。",
                    "template",
                )
            elif gold_diff_10 <= -600:
                blame_points += 10.0
                _add_conclusion(
                    weaknesses,
                    f"对线期被对位压制：10分钟经济 {gold10:,}，比对位 {opp_hero}（{opp_gold10:,}金）落后 {abs(gold_diff_10):,} 金，放任对面核心无压力出山。",
                    "inferred",
                )
                trash_candidates.append((
                    76,
                    f"@{pname} 对线期给对面 {opp_hero} 养了个无解肥大爹出来，10分钟落后 {abs(gold_diff_10)} 块，中期团不过从你这儿开始算账！",
                ))
        else:
            core_partner = None
            if my_lane in (1, 2, 3):
                core_partner = next(
                    (
                        tp
                        for tp in team_players
                        if tp.get("player_slot") != p.get("player_slot")
                        and (tp.get("raw_lane") if tp.get("raw_lane") is not None else tp.get("lane")) == my_lane
                        and int(tp.get("pos") or 0) in (1, 2, 3)
                    ),
                    None,
                )
            if not core_partner:
                core_partner_pos = 1 if pos == 5 else 3
                core_partner = next((tp for tp in team_players if tp.get("pos") == core_partner_pos), None)
            if core_partner and (core_partner.get("laning_10m") or {}).get("gold10"):
                cp_g10 = core_partner["laning_10m"]["gold10"]
                cp_lh10 = core_partner["laning_10m"]["lh10"]
                cp_hero = core_partner.get("hero_short_zh") or core_partner["hero_name"]
                if cp_lh10 and cp_lh10 >= 50:
                    _add_conclusion(
                        strengths,
                        f"保人拉野到位：对线期把同路核心 {cp_hero} 保出了 10分钟 {cp_lh10} 刀 / {cp_g10:,} 经济的顺畅开局。",
                        "inferred",
                    )
                elif cp_lh10 and cp_lh10 <= 32 and not is_turbo:
                    blame_points += 10.0
                    _add_conclusion(
                        weaknesses,
                        f"线上保人失职：同路 {cp_hero} 10分钟才补了 {cp_lh10} 刀（{cp_g10:,}金），前5分钟封野、拉野消兵和消耗都没打出来。",
                        "inferred",
                    )

    # --- (B) 经济转化率、GPM 与伤害承伤比审计 ---
    if pos in (1, 2):
        if gpm_pct >= 0.80:
            _add_conclusion(
                strengths,
                f"刷钱效率拉满：GPM {gpm} / XPM {xpm}（全场补刀 {lh}），发育速度超越了全网 {gpm_pct*100:.0f}% 的同英雄玩家。",
                "measured",
                ["players[].gold_per_min", "players[].xp_per_min", "players[].last_hits", "players[].benchmarks.gold_per_min"],
            )
        elif gpm_pct <= 0.35 and not is_turbo:
            blame_points += 18.0
            _add_conclusion(
                weaknesses,
                f"核心发育严重滞后：{pos}号位 {hero_name} 全场 GPM 仅有 {gpm}（补刀 {lh}，仅超越 {gpm_pct*100:.0f}% 同英雄），中期刷钱路线完全断档。",
                "inferred",
            )
            trash_candidates.append((
                88,
                f"@{pname} 打个{pos}号位GPM才{gpm}，野怪见了你都得递根烟问你今天怎么不来收租？",
            ))
            _add_conclusion(
                improvements,
                f"{pos}号位在 12~24 分钟大招冷却或关键装未齐时，少在河道跟辅助抱团干瞪眼，先把危险线推过河道再回头收远古，保证 GPM 稳定在 600+。",
                "template",
            )

        if hdmg_share >= 28.0 or dmg_pct >= 0.80:
            _add_conclusion(
                strengths,
                f"输出转化率极高：吃下全队 {nw_share:.1f}% 经济（{nw:,}金），狂轰 {hdmg:,} 英雄伤害（占全队 {hdmg_share:.1f}%，超越全网 {dmg_pct*100:.0f}% 同英雄）。",
                "measured",
                ["players[].net_worth", "players[].hero_damage", "players[].benchmarks.hero_damage_per_min"],
            )
        elif hdmg_share < 19.0 and duration_min >= 22:
            blame_points += 22.0
            _add_conclusion(
                weaknesses,
                f"典型高占经低产出：拿了全队 {nw_share:.1f}% 的总经济（{nw:,}金），全场却只打出 {hdmg:,} 伤害（仅占全队 {hdmg_share:.1f}%），每1块钱经济只换来 {hdmg/max(1,nw):.2f} 点伤害。",
                "measured",
                ["players[].net_worth", "players[].hero_damage"],
            )
            trash_candidates.append((
                95,
                f"@{pname} 独占全队{nw_share:.0f}%的钱就打了{hdmg_share:.0f}%的伤害，这{nw:,}金币哪怕直接撒在泉水里听个响都比在你身上响！",
            ))
            _add_conclusion(
                improvements,
                f"{hero_name} 做出核心装的第一波强势期必须主动跟雾找节奏，别等队友正面4打5溃败了再去边缘OB蹭两下伤害。",
                "template",
            )
    elif pos == 3:
        if kp >= 64.0 and (stuns >= 30.0 or dmg_taken_share >= 24.0):
            _add_conclusion(
                strengths,
                f"前排支点作用显著：参战率高达 {kp:.1f}%（KDA {kills}/{deaths}/{assists}），提供 {stuns:.1f} 秒控制并扛下 {dmg_taken:,} 伤害（占全队承伤 {dmg_taken_share:.1f}%）。",
                "measured",
                ["players[].kills", "players[].deaths", "players[].assists", "players[].stuns", "players[].damage_inflictor_received"],
            )
        if hdmg_share < 13.0 and nw_share > 16.0:
            blame_points += 14.0
            _add_conclusion(
                weaknesses,
                f"三号位正面威胁匮乏：拿了 {nw:,} 经济（全队 {nw_share:.1f}%），全场英雄伤害却只有 {hdmg:,}（仅占全队 {hdmg_share:.1f}%），团战几乎没有杀伤力。",
                "inferred",
            )
        if kp < 48.0:
            blame_points += 15.0
            _add_conclusion(
                weaknesses,
                f"三号位严重脱节：参战率低至 {kp:.1f}%，中期长时间游离于团队正面战场之外。",
                "inferred",
            )
            trash_candidates.append((
                82,
                f"@{pname} 玩个3号位参战率才{kp:.0f}%，你是买票进来看我们四个正面挨揍的吗？",
            ))

    # --- (C) 推进与建筑伤害审计 (败局且全队未破外塔/高地时不机械苛责拆塔量) ---
    if tdmg >= 6500 or (pos in (1, 2) and tdmg_share >= 45.0 and tdmg >= 3500):
        _add_conclusion(
            strengths,
            f"推进终结能力极强：单人打出 {tdmg:,} 建筑伤害（包揽全队 {tdmg_share:.0f}% 拆塔量），赢下团战后能迅速将人头优势转化为塔数。",
            "measured",
            ["players[].tower_damage"],
        )
    elif pos == 1 and tdmg < 1200 and duration_min >= 25 and (won or team_tdmg >= 2500):
        blame_points += 14.0
        _add_conclusion(
            weaknesses,
            f"推塔效率极其低下：1号位打了 {duration_min:.0f} 分钟，建筑伤害仅有 {tdmg}（占全队 {tdmg_share:.1f}%），赢团后严重缺乏逼塔拿盾意识。",
            "inferred",
        )
        trash_candidates.append((
            84,
            f"@{pname} 1号位全场建筑伤害{tdmg}，打赢团掉头就钻野区，对面防御塔跟你是有亲戚关系舍不得A吗？",
        ))
        _add_conclusion(
            improvements,
            "团战减员敌方核心后，第一优先级永远是推线拆塔或控肉山，切忌全员回头刷自家野区白白浪费赢团窗口。",
            "template",
        )

    # --- (D) 录像级：出装时间轴 + 主动道具按键次数审计 (item_uses) ---
    final_items_str = " ".join(p.get("final_items") or [])
    timings = p.get("key_item_timings") or []
    timings_rich = p.get("key_item_timings_rich") or []

    # 1) BKB 出装时间与按键次数双重审计
    bkb_timing_min = None
    bkb_timing_str = None
    for tm in timings_rich:
        if tm.get("key") == "black_king_bar":
            bkb_timing_min = int(tm.get("time_sec", 0) // 60)
            bkb_timing_str = tm.get("time_str")
            break
    bkb_uses = (active_uses.get("black_king_bar") or {}).get("count", 0)
    enemy_total_stuns = sum(float(ep.get("stuns_sec") or 0.0) for ep in enemy_players)

    if pos in (1, 2, 3) and bkb_timing_min is not None:
        if bkb_timing_min <= 24 and bkb_uses >= 3:
            _add_conclusion(
                strengths,
                f"BKB 节点与使用果断：{bkb_timing_str} 准时做出黑皇杖，全场有效开启 {bkb_uses} 次顶住敌方第一波控制链。",
                "inferred",
            )
        elif bkb_timing_min >= 30 and not is_turbo:
            blame_points += 18.0
            _add_conclusion(
                weaknesses,
                f"BKB 严重难产 + 团战空放/少按：面对敌方合计 {enemy_total_stuns:.0f} 秒控制，拖到 {bkb_timing_str} 才摸出 BKB，且整局只按出了 {bkb_uses} 次（全场却死了 {deaths} 次），中期团战全在肉身接技能。",
                "inferred",
            )
            trash_candidates.append((
                91,
                f"@{pname} 对面一身硬控你拖到 {bkb_timing_str} 才出 BKB，整局就按了 {bkb_uses} 次，买个黄棍放包里当传家宝辟邪是吧？",
            ))
            _add_conclusion(
                improvements,
                f"面对高控制阵容，{pos}号位 {hero_name} 必须在第2或第3大件（23~26分钟前）准时做出 BKB，且第一波切入前提前开启，切忌省BKB被瞬秒。",
                "template",
            )
        elif bkb_uses <= 1 and duration_min - bkb_timing_min >= 5:
            blame_points += 12.0
            _add_conclusion(
                weaknesses,
                f"BKB 沦为摆设：{bkb_timing_str} 做出黑皇杖后，直到比赛结束居然只按了 {bkb_uses} 次！",
                "inferred",
            )
    elif pos in (1, 2, 3):
        hid_cur = int(p.get("hero_id") or 0)
        has_innate_or_non_bkb_kit = (
            any(k in hero_name for k in ["主宰", "噬魂鬼", "凤凰", "幽鬼", "钢背兽", "潮汐猎人", "人马", "半人马"])
            or hid_cur in (8, 54, 110, 67, 99, 29, 96)
        )
        if deaths >= 7 and enemy_total_stuns >= 70 and not has_innate_or_non_bkb_kit:
            blame_points += 20.0
            _add_conclusion(
                weaknesses,
                f"头铁拒出 BKB：面对敌方 {enemy_total_stuns:.0f} 秒强控，全场阵亡 {deaths} 次直到终局都没出黑皇杖，团战容错率极低。",
                "inferred",
            )
            trash_candidates.append((
                92,
                f"@{pname} 死了{deaths}次硬是不出BKB，BKB这件装备在你的商店里是被G胖下架了吗？",
            ))

    # 2) 假腿切换次数审计 (power_treads)
    has_treads = any(it.get("key") == "power_treads" for it in (p.get("final_items_rich") or [])) or any(
        tm.get("key") == "power_treads" for tm in timings_rich
    )
    if is_parsed and has_treads and duration_min >= 20:
        treads_uses = (active_uses.get("power_treads") or {}).get("count", 0)
        if treads_uses <= 6:
            blame_points += 5.0
            _add_conclusion(
                weaknesses,
                f"假腿焊死细节缺失：整场 {duration_min:.0f} 分钟比赛里，假腿属性总共只切换了 {treads_uses} 次，刷野放技能从不切智力省蓝、挨打也不切力量撑血。",
                "inferred",
            )
        elif treads_uses >= 35:
            _add_conclusion(
                strengths,
                f"操作细节拉满：全场高频切假腿 {treads_uses} 次（APM {apm}），属性转换极其细腻。",
                "measured",
                ["players[].item_uses", "players[].actions_per_min"],
            )

    # 3) 辅助/核心主动救人装与切入装按键审计 (微光/推推/跳刀/莲花/魔晶)
    if is_parsed:
        for item_key, item_label, min_expected in [
            ("glimmer_cape", "微光披风", 5),
            ("force_staff", "推推棒", 5),
            ("hurricane_pike", "大推推", 4),
            ("lotus_orb", "清莲宝珠", 4),
            ("pipe", "洞察烟斗", 3),
        ]:
            bought_tm = next((tm for tm in timings_rich if tm.get("key") == item_key), None)
            has_now = any(it.get("key") == item_key for it in (p.get("final_items_rich") or []))
            if bought_tm or has_now:
                cnt = (active_uses.get(item_key) or {}).get("count", 0)
                t_str = bought_tm["time_str"] if bought_tm else "中后期"
                held_mins = duration_min - (bought_tm["time_sec"] / 60.0 if bought_tm else duration_min * 0.6)
                if held_mins >= 8 and cnt <= 3:
                    blame_points += 11.0
                    _add_conclusion(
                        weaknesses,
                        f"主动救人装严重漏按：{t_str} 做出 {item_label}，拿在手里 {held_mins:.0f} 分钟总共只按了 {cnt} 次，团战队友被集火时反应慢半拍。",
                        "inferred",
                    )
                    trash_candidates.append((
                        86,
                        f"@{pname} {t_str}出的{item_label}整局就按了{cnt}次，这装备键位是不是扣下来送人了？",
                    ))
                elif cnt >= 8:
                    _add_conclusion(
                        strengths,
                        f"救人装高频救场：{item_label} 全场精准开启 {cnt} 次，多次在关键团战帮队友死里逃生。",
                        "inferred",
                    )

        # 跳刀使用频率审计
        blink_tm = next((tm for tm in timings_rich if "blink" in (tm.get("key") or "")), None)
        if blink_tm:
            blink_cnt = sum(
                (active_uses.get(k) or {}).get("count", 0)
                for k in ("blink", "overwhelming_blink", "swift_blink", "arcane_blink")
            )
            if blink_cnt >= 25:
                _add_conclusion(
                    strengths,
                    f"切入发动机：{blink_tm['time_str']} 摸出跳刀后全场高频切入 {blink_cnt} 次，把控先手节奏。",
                    "measured",
                    ["players[].purchase_log", "players[].item_uses"],
                )

    # 4) 两件关键装之间断档过久审计
    if len(timings_rich) >= 2 and not is_turbo and pos in (1, 2, 3):
        for i in range(len(timings_rich) - 1):
            t1 = timings_rich[i]["time_sec"] // 60
            t2 = timings_rich[i + 1]["time_sec"] // 60
            gap = t2 - t1
            if gap >= 14 and t1 >= 9:
                blame_points += 16.0
                _add_conclusion(
                    weaknesses,
                    f"中期装备严重断档 {gap} 分钟：从 {timings_rich[i]['time_str']} {timings_rich[i]['zh_name']} 到 {timings_rich[i+1]['time_str']} {timings_rich[i+1]['zh_name']} 之间整整真空了 {gap} 分钟，期间频繁阵亡掉存款导致强势期彻底断掉。",
                    "inferred",
                )
                trash_candidates.append((
                    89,
                    f"@{pname} 从 {timings_rich[i]['time_str']} {timings_rich[i]['zh_name']} 到 {timings_rich[i+1]['time_str']} {timings_rich[i+1]['zh_name']} 憋了整整 {gap} 分钟，这 {gap} 分钟你是在野区冬眠吗？",
                ))
                _add_conclusion(
                    improvements,
                    f"第一件节奏装（如 {timings_rich[i]['zh_name']}）出炉后若正面团战屡屡受挫，切忌继续盲目冲脸送连死，应立刻补小件（魔棒/护腕/微光/推推）或带线把第二件核心装刷出来。",
                    "template",
                )
                break

    # --- (E) 录像级：核心技能释放频率审计 (ability_uses_rich) ---
    if is_parsed and ability_list:
        ab_summary = " / ".join(f"{ab['zh_name']} {ab['count']}次" for ab in ability_list[:4])
        # 针对特定低频关键技能直接点名
        for ab in ability_list:
            ak = ab["key"]
            cnt = ab["count"]
            zh = ab["zh_name"]
            if ak == "magnataur_empower" and duration_min >= 25 and cnt < duration_min * 0.7:
                blame_points += 14.0
                _add_conclusion(
                    weaknesses,
                    f"猛犸挂分裂严重失职：{duration_min:.0f} 分钟比赛里【{zh}】一共只放了 {cnt} 次（场均每 {duration_min/max(1,cnt):.1f} 分钟才想起来给一次 Buff），一号位刷钱时经常断分裂！",
                    "inferred",
                )
                trash_candidates.append((
                    93,
                    f"@{pname} {duration_min:.0f}分钟猛犸一共就给过 {cnt} 次授予力量，找你讨个分裂Buff比跟银行办贷款还难！",
                ))
                _add_conclusion(
                    improvements,
                    "玩马格纳斯必须养成肌肉记忆：每 40 秒盯一眼一号位身上的授予力量图标，大哥进野区前提前续满。",
                    "template",
                )
            elif ak in ("magnataur_reverse_polarity", "tidehunter_ravage", "faceless_void_chronosphere", "enigma_black_hole", "dark_seer_wall_of_replica") and duration_min >= 28 and cnt <= 5:
                blame_points += 10.0
                _add_conclusion(
                    weaknesses,
                    f"团战大招憋到发霉：{duration_min:.0f} 分钟里大招【{zh}】仅释放了 {cnt} 次，过于追求完美大招导致大量时间大招空转。",
                    "inferred",
                )
        # 将完整技能统计写入高光或说明
        _add_conclusion(
            strengths,
            f"全场核心技能施放统计：{ab_summary}（操作频率 {apm} APM）。",
            "measured",
            ["players[].ability_uses", "players[].actions_per_min"],
        )

    # --- (F) 4/5号位视野、反隐、买雾与拆眼审计 ---
    if pos in (4, 5):
        obs_killed = kills_info.get("obs_destroyed", 0)
        sen_killed = kills_info.get("sen_destroyed", 0)
        if wards_total >= 18:
            deward_txt = f"，并成功排掉敌方 {obs_killed} 颗假眼 / {sen_killed} 颗真眼" if (obs_killed + sen_killed) > 0 else ""
            _add_conclusion(
                strengths,
                f"视野铺设尽职：全场插下 {obs} 假眼 + {sen} 真眼（共 {wards_total} 颗）{deward_txt}"
                + (f"，顺手囤野 {stacked} 波。" if stacked > 0 else "。"),
                "measured",
                ["players[].obs_placed", "players[].sen_placed", "players[].observer_kills", "players[].sentry_kills", "players[].camps_stacked"],
            )
        elif is_parsed and wards_total <= 8 and duration_min >= 25:
            blame_points += 18.0
            _add_conclusion(
                weaknesses,
                f"视野严重断供：身为 {pos}号位 {duration_min:.0f} 分钟仅插了 {obs} 假眼 / {sen} 真眼，导致全队中后期在野区毫无视野掩护。",
                "inferred",
            )
            trash_candidates.append((
                89,
                f"@{pname} 打个{pos}号位全场就插了{wards_total}个眼，我们五个人全靠心眼看地图是吧？",
            ))
            _add_conclusion(
                improvements,
                "辅助位必须保证商店观察者守卫不积压，进攻期将眼位推进至敌方主野区高台与肉山坑口。",
                "template",
            )

        team_smokes = sum(int(tp.get("smokes_bought") or 0) for tp in team_players)
        team_dusts = sum(int(tp.get("dusts_bought") or 0) for tp in team_players)

        if smokes >= 3:
            _add_conclusion(
                strengths,
                f"进攻节奏组织者：全场主动购买 {smokes} 颗诡计之雾带动抓人节奏。",
                "inferred",
            )
        elif is_parsed and team_smokes == 0 and duration_min >= 25:
            _add_conclusion(
                weaknesses,
                "全队零买雾：本方五人全场购买诡计之雾总次数为 0，缺乏开雾抓单组织。",
                "inferred",
            )
            _add_conclusion(
                improvements,
                "核心摸出跳刀或BKB的第一时间，全队应及时买雾发信号召集队友抓敌方落单打钱核。",
                "template",
            )

        enemy_has_invis = any(
            ("微光" in " ".join(ep.get("final_items") or []))
            or ("隐刀" in " ".join(ep.get("final_items") or []))
            or any(k in ep.get("hero_name", "") for k in ["力丸", "克林克兹", "赏金", "司夜刺客", "编织者", "米拉娜", "沙王"])
            for ep in enemy_players
        )
        if is_parsed and enemy_has_invis and team_dusts == 0:
            _add_conclusion(
                weaknesses,
                "全队零买粉：面对敌方微光披风/隐身单位，本方五人显影之尘总购买次数为 0。",
                "inferred",
            )

    # --- (G) 录像级：黑白电视时长、阵亡扣钱、天敌提款机与野怪/塔杀取证 ---
    dead_min, dead_rem_s = divmod(int(dead_sec), 60)
    dead_pct = (dead_sec / max(1.0, duration_min * 60.0)) * 100.0
    nemesis_list = killed_by_info.get("heroes") or []
    nemesis_str = ""
    if nemesis_list:
        top_nem = nemesis_list[0]
        nemesis_str = f"（其中被敌方【{top_nem['hero_short_zh']}】单人提款 {top_nem['count']} 次）"

    neutral_deaths = killed_by_info.get("neutral_deaths", 0)
    tower_deaths = killed_by_info.get("tower_deaths", 0)
    fountain_deaths = killed_by_info.get("fountain_deaths", 0)

    if neutral_deaths > 0:
        blame_points += 6.0 * neutral_deaths
        _add_conclusion(
            weaknesses,
            f"野区冥场面认证：本局出现 **{neutral_deaths} 次被中立野怪击杀** 的离谱操作，刷野不看血量直接送回泉水。",
            "inferred",
        )
        trash_candidates.append((
            90,
            f"@{pname} 打野还能被野怪单杀 {neutral_deaths} 次，野区半人马才是你命中注定的克星是吧？",
        ))
    if tower_deaths > 0:
        blame_points += 5.0 * tower_deaths
        _add_conclusion(
            weaknesses,
            f"越塔阵亡记录：本局有 **{tower_deaths} 次直接死于敌方防御塔攻击**，冲塔上头未能计算防御塔仇恨与伤害。",
            "inferred",
        )
    if fountain_deaths > 0:
        _add_conclusion(
            strengths,
            f"终局虐泉打卡：比赛结束前冲进敌方泉水被激光击杀 {fountain_deaths} 次。",
            "measured",
            ["players[].killed_by", "players[].deaths_log"],
        )

    # --- (H) 录像级：结合英雄内置强势期曲线 (timing_curve) 区分「大核合理避战刷钱->后期收割」与「毒瘤独刷不参战」 ---
    hmp = audit_hero_mechanism_and_timing(p, team_players, enemy_players, duration_min, won)
    p["hero_mechanism_profile"] = hmp
    is_late_hyper_carry = hmp.get("timing_curve") == "late_hyper_carry"

    pt = p.get("phase_telemetry") or {}
    lane_hdmg = int(pt.get("lane_hdmg_gain") or 0)
    mid_gold = int(pt.get("mid_gold_gain") or 0)
    mid_hdmg = int(pt.get("mid_hdmg_gain") or 0)
    mid_gold_share = float(pt["mid_gold_share_pct"]) if pt.get("mid_gold_share_pct") is not None else None
    mid_hdmg_share = float(pt["mid_hdmg_share_pct"]) if pt.get("mid_hdmg_share_pct") is not None else None
    tf_afk_cnt = int(pt.get("tf_zero_dmg_afk_count") or 0)
    tf_afk_gold = int(pt.get("tf_zero_dmg_gold_farmed") or 0)

    team_avg_kp = sum(float(tp.get("kill_participation_pct") or 0.0) for tp in team_players) / max(1, len(team_players))
    min_team_kp = min(float(tp.get("kill_participation_pct") or 100.0) for tp in team_players)

    is_afk_farmer = False
    if pos in (1, 2, 3) and duration_min >= 20 and not is_turbo:
        if is_parsed and mid_gold > 0 and mid_gold_share is not None and mid_hdmg_share is not None:
            # 如果是天生后期大核 (敌法/美杜莎/幽鬼/TB/猴子/水人/露娜/虚空等)，前中期(10-25m)避战刷钱是合理的！
            # 只有当他属于前中期节奏核，或者大核在后期也没参战(kp < 42% 或 assists <= 4)时，才判定为毒瘤独刷
            if is_late_hyper_carry and hmp.get("late_harvest_fulfilled") and kp >= 42.0 and assists >= 5:
                is_afk_farmer = False
            elif (
                kp < 48.5
                and mid_gold_share >= 22.5
                and mid_hdmg_share <= 14.5
                and (kp <= min_team_kp + 2.0 or tf_afk_cnt >= 2)
            ):
                is_afk_farmer = True
        else:
            low_kp_mid = pos == 2 and (kp < 46.0 and kp <= min_team_kp + 0.1 and kp < team_avg_kp - 10.0)
            low_kp_core = pos in (1, 3) and (kp < 40.0 and kp <= min_team_kp + 0.1 and kp < team_avg_kp - 14.0)
            if low_kp_mid or low_kp_core:
                is_afk_farmer = True

    if is_afk_farmer:
        radar["tempo"] = min(radar["tempo"], 26)
        radar["survival"] = min(radar["survival"], 50)
        mvp_score = round(clamp(mvp_score - 21.0, 35.0, 61.0), 1)
        rating_score = round(clamp(mvp_score / 10.0, 4.0, 6.1), 1)
        rating_tier = "C 毒瘤独刷" if won else ("C 脱节刷钱" if not is_parsed else "D 脱节独刷")
        blame_points += 38.0
        tf_afk_clause = (
            f"，且有 **{tf_afk_cnt} 波关键团战 0 伤害卖队友独刷（趁队友4打5挨揍在野区收割 +{tf_afk_gold:,} 金）**"
            if tf_afk_cnt > 0
            else ""
        )
        if is_parsed and mid_gold > 0:
            afk_tail = "才混到后期出山收割面板！" if duration_min >= 30 else "，与团队正面节奏严重脱节！"
            _add_conclusion(
                weaknesses,
                f"前中期毒瘤独刷不参战：全场参战率仅 **{kp:.1f}%（全队倒数第一，{kills}/{deaths}/{assists} 全场仅 {assists} 个助攻）**！"
                f"前10分钟仅打出 **{lane_hdmg:,} 英雄伤害**，10–25m 中期狂刷 **+{mid_gold:,} 金（占全队中期经济 {mid_gold_share:.1f}%）** "
                f"却只打出 **{mid_hdmg:,} 伤害（仅占全队中期伤害 {mid_hdmg_share:.1f}%，连双辅助都不如）**{tf_afk_clause}，"
                f"全靠四个队友前中期 4 打 5 血战撑住局势{afk_tail}",
                "inferred",
                prepend=True,
            )
        else:
            _add_conclusion(
                weaknesses,
                f"全程独刷脱节不参战：身为 {pos}号位 {hero_name} 全场参战率低至 **{kp:.1f}%（全队倒数第一，{kills}/{deaths}/{assists} 全场仅 {assists} 个助攻）**，"
                f"前中期长时间游离于团队正面战场之外闷头刷钱，全靠四个队友 4 打 5 硬撑局势！",
                "inferred",
                prepend=True,
            )
        trash_candidates.append((
            99,
            f"@{pname} 玩个{pos}号位{hero_name}前25分钟打钱不参战（参战率{kp:.1f}%全队垫底、全场仅{assists}个助攻），队友正面4打5流血你钻野区收租，最后出山K几个头真当自己是MVP了？",
        ))
        _add_conclusion(
            improvements,
            f"身为 {pos}号位切忌前中期把四个队友当肉盾吸血独刷：10~25分钟做出第一件节奏装后必须带队接团或TP反打，而不是全程0参战闷头刷野。",
            "template",
            prepend=True,
        )
    elif pos == 1 and tdmg_share >= 48.0 and tdmg >= 9000 and kp >= 50.0:
        mvp_score = round(clamp(mvp_score + 4.5, 35.0, 99.0), 1)
        rating_score = round(clamp(mvp_score / 10.0, 4.0, 9.9), 1)
        if won and rating_score >= 8.3:
            rating_tier = "S+ 擎天战神"

    # --- (I) 全 126 英雄专属机制、前中后期强势期契约、单带被抓、魔晶/克制装与炮台兑现深度审计 ---
    hid_cur = int(p.get("hero_id") or 0)
    has_shard = bool(p.get("aghanims_shard"))
    solo_pickoffs = pt.get("solo_pickoffs") or []
    low_dmg_tfs = pt.get("low_dmg_tfs") or []
    late_gold = int(pt.get("late_gold_gain") or 0)
    late_hdmg = int(pt.get("late_hdmg_gain") or 0)
    late_gold_share = float(pt["late_gold_share_pct"]) if pt.get("late_gold_share_pct") is not None else None
    late_hdmg_share = float(pt["late_hdmg_share_pct"]) if pt.get("late_hdmg_share_pct") is not None else None
    dmg_per_death = hdmg / max(1, deaths)

    # 1) 脆皮高爆发炮台核心 (莉娜/宙斯/天怒/狙击手/修补匠/卡尔/黑鸟等) 「虽死犹荣 · 火力倾泻兑现」判定
    is_glass_cannon_turret = hmp.get("timing_curve") == "glass_cannon_turret" or hid_cur in (25, 22, 101, 35)
    is_turret_fulfilled = (
        is_glass_cannon_turret
        and duration_min >= 20
        and (hdmg_share >= 20.0 or dmg_per_death >= 3000)
        and hdmg >= 22000
    )

    if is_turret_fulfilled:
        radar["damage"] = max(radar["damage"], 85)
        radar["tempo"] = max(radar["tempo"], 72)
        radar["survival"] = max(radar["survival"], 60)
        mvp_score = round(clamp(mvp_score + 22.0, 73.0, 89.0), 1)
        rating_score = round(clamp(mvp_score / 10.0, 7.3, 8.9), 1)
        rating_tier = ("A 凯旋炮台" if rating_score >= 8.0 else "B+ 功勋炮台") if won else ("A 尽力真核" if rating_score >= 7.8 else "B+ 悲情炮台")
        blame_points = max(8.0, blame_points - 36.0)
        ab_top_str = " + ".join(f"{ab['zh_name']}×{ab['count']}" for ab in ability_list[:3]) if ability_list else "高频技能轰炸"
        lane_lead_clause = ""
        if gold10 and opp_same_pos and (opp_same_pos.get("laning_10m") or {}).get("gold10"):
            g_diff = gold10 - opp_same_pos["laning_10m"]["gold10"]
            if g_diff >= 400:
                lane_lead_clause = f"前期对线 10m 交出 {lh10}正/{dn10}反（{gold10:,} 金，压制对位 {opp_same_pos.get('hero_short_zh','')} +{g_diff:,} 金）打出优势；"
        late_turret_clause = (
            f"，25m+ 后期再轰 {late_hdmg:,} 伤害"
            if (is_parsed and duration_min >= 30 and late_hdmg_share is not None and late_hdmg > 0)
            else ""
        )
        stun_turret_clause = f"外加 {stuns:.1f} 秒硬控" if (is_parsed and stuns > 0) else ""
        _add_conclusion(
            strengths,
            f"炮台火力彻底兑现（哪怕阵亡也把输出灌满）：{lane_lead_clause}作为无位移脆皮高爆发核心，全场狂甩 {ab_top_str}，"
            f"轰出 **{hdmg:,} 点英雄伤害（占全队 {hdmg_share:.1f}%，平均每次阵亡前倾泻 {int(dmg_per_death):,} 点高额伤害{late_turret_clause}）**{stun_turret_clause}！"
            f"在团队前排与救人匮乏的逆境下，真正做到了倒下前把每一滴输出倾泻干净。",
            "inferred",
            prepend=True,
        )
        weaknesses = [w for w in weaknesses if "BKB 严重难产" not in w]
        _add_conclusion(
            weaknesses,
            f"绝境生存与留人反制博弈：作为己方唯一能威胁敌方后排的高爆发炮台，被敌方切入与点控重点针对阵亡 {deaths} 次{nemesis_str}；"
            f"在队友缺乏魔晶救人与前排支点的局面下，单靠 BKB 结束后仍容易被敌方框人/留人技能链限制走位。",
            "inferred",
            prepend=True,
        )
        trash_candidates.append((
            108,
            f"@{pname} 这把{hero_name}对线压爆中路、全场狂灌 {hdmg:,} 伤害（每死换 {int(dmg_per_death):,} 伤），已经把炮台火力彻底拉满了！",
        ))
        _add_conclusion(
            improvements,
            f"{hero_name} 本局输出职责已超额完成（场均每死换 {int(dmg_per_death):,} 伤害）；若从团队可能性出发进一步提升残局容错，面对敌方强留人/框人控制时，"
            f"可将一件纯法系输出装替换为【飓风长戟（大推推）】（既能推开自己拉开切入距离，又能补充射程点人）。",
            "template",
            prepend=True,
        )

    # 2) 凤凰 (Phoenix) 烈日炙烤覆盖审计（不推断变蛋是否被打碎）
    egg_audit = p.get("phoenix_egg_audit") or {}
    if hid_cur == 110 and egg_audit:
        egg_casts = int(egg_audit.get("total_casts") or 0)
        tf_egg_total = int(egg_audit.get("tf_egg_total") or 0)
        ray_casts = int(egg_audit.get("sun_ray_casts") or 0)
        if ray_casts < int(duration_min * 0.25) and duration_min >= 20:
            _add_conclusion(
                improvements,
                f"凤凰本局共施放 {egg_casts} 次《超新星》（团战 {tf_egg_total} 次）、{ray_casts} 次《烈日炙烤》（全队治疗 {heal:,} 点），可提高团战中后排《烈日炙烤》开启频率以兼顾消耗与治疗。",
                "template",
                prepend=True,
            )

    # 3) 全 126 英雄通用「大后期核(late_hyper_carry)避战刷钱->后期收割兑现 vs 后期隐身违约」审计（推断类团战外阵亡不计入分锅；后期空值或不足5分钟跳过）
    if (
        is_parsed
        and late_gold_share is not None
        and late_hdmg_share is not None
        and pos in (1, 2)
        and not is_turret_fulfilled
        and duration_min >= 30
    ):
        if hmp.get("late_harvest_fulfilled") and not is_afk_farmer:
            _add_conclusion(strengths, hmp["late_phase_note"], "inferred", prepend=True)
        elif hmp.get("late_harvest_failed"):
            blame_points += 20.0
            _add_conclusion(weaknesses, hmp["late_phase_note"], "inferred", prepend=True)
            trash_candidates.append((
                104,
                f"@{pname} 玩个{hero_name}前中期全队给你让资源避战刷钱完全合理，结果25分钟出山期你吃下全队{late_gold_share:.0f}%经济却只打了{late_hdmg_share:.0f}%后期伤害，刷最肥的钱打最低的输出，后期收割呢？",
            ))

    # 5) 针对全 126 英雄的「节奏核闷头刷错失强势期」「先手肉核敢死开团功臣」「救人辅助保核兑现」「必出命脉魔晶缺失」审计
    if hmp.get("mid_tempo_wasted") and not is_afk_farmer:
        blame_points += 14.0
        _add_conclusion(weaknesses, hmp["mid_phase_note"], "inferred", prepend=True)
    if hmp.get("sacrificial_initiator_fulfilled"):
        blame_points = max(8.0, blame_points - 18.0)
        _add_conclusion(strengths, hmp["mechanism_summary"], "inferred", prepend=True)
    if hmp.get("save_support_fulfilled"):
        _add_conclusion(strengths, hmp["mechanism_summary"], "inferred", prepend=True)
    if hmp.get("missing_mandatory_shard"):
        blame_points += 12.0
        _add_conclusion(
            weaknesses,
            f"核心命脉魔晶缺失：比赛打到 {duration_min:.0f} 分钟仍未购买 {hero_name} 仅售 1,400 金的质变魔晶【{hmp['shard_desc']}】，导致英雄核心团战机制残缺！",
            "inferred",
            prepend=True,
        )

    # 6) 伤害含金量（刮肉盾假伤害 vs 真切核）、1~18级奇葩加点与永久Buff叠层证据挂载
    dq_audit = p.get("damage_and_build_audit") or {}
    if dq_audit:
        dq_badge = str(dq_audit.get("dmg_quality_badge") or "")
        dq_notes = dq_audit.get("dmg_audit_notes") or []
        if dq_badge.startswith("🚨") and dq_notes:
            blame_points += 10.0
            _add_conclusion(weaknesses, dq_notes[0], "inferred")
        elif dq_badge.startswith("⚠️") and dq_notes:
            _add_conclusion(weaknesses, dq_notes[0], "inferred")
        elif dq_badge.startswith("🔥") and dq_notes:
            _add_conclusion(strengths, dq_notes[0], "inferred")

        for sflag in (dq_audit.get("skill_build_flags") or []):
            if str(sflag).startswith("🚨"):
                blame_points += 9.0
                _add_conclusion(weaknesses, sflag, "inferred")
            elif str(sflag).startswith("⚠️"):
                blame_points += 5.0
                _add_conclusion(weaknesses, sflag, "inferred")

        for pb_note in (dq_audit.get("perm_buff_notes") or []):
            if str(pb_note).startswith("🚨") or str(pb_note).startswith("⚠️"):
                _add_conclusion(weaknesses, pb_note, "inferred")
            elif str(pb_note).startswith("🔥"):
                _add_conclusion(strengths, pb_note, "inferred")

    # 6.5) 深度流派识别 + 全量成装时间轴 + 技能/道具伤害占比 + 加点与天赋树 + 中立道具与附魔全维度取证
    playstyle_audit = build_player_playstyle_and_build_forensics(
        p, team_players, enemy_players, duration_min, won
    )
    p["playstyle_archetype_audit"] = playstyle_audit
    if playstyle_audit:
        if playstyle_audit.get("is_smart_playstyle_pivot"):
            blame_points = max(8.0, blame_points - 14.0)
            mvp_score = round(clamp(mvp_score + 6.0, 45.0, 96.0), 1)
            rating_score = round(clamp(mvp_score / 10.0, 4.5, 9.6), 1)
            _add_conclusion(strengths, playstyle_audit["archetype_analysis_zh"], "inferred", prepend=True)
        elif playstyle_audit.get("archetype_analysis_zh"):
            _add_conclusion(strengths, playstyle_audit["archetype_analysis_zh"], "inferred")
        if playstyle_audit.get("spell_damage_breakdown_zh"):
            _add_conclusion(
                strengths,
                playstyle_audit["spell_damage_breakdown_zh"],
                "measured",
                ["players[].damage_inflictor", "players[].ability_uses"],
            )
        if playstyle_audit.get("skill_and_talent_audit_zh"):
            _add_conclusion(strengths, playstyle_audit["skill_and_talent_audit_zh"], "inferred")
        if playstyle_audit.get("neutral_and_enchantment_audit_zh"):
            _add_conclusion(strengths, playstyle_audit["neutral_and_enchantment_audit_zh"], "inferred")

    # 7) 逐英雄独特机制 × 1~5号位差异化打法 × 队友技能配合 × 敌我克制关系深度取证 (hero_matchup_dossier)
    dossier = hmp.get("hero_matchup_dossier") or build_hero_matchup_dossier(
        p, team_players, enemy_players, duration_min, won
    )
    if isinstance(dossier, dict):
        dossier["evidence"] = "template"
    if isinstance(hmp, dict):
        hmp["evidence"] = "template"
    p["hero_matchup_dossier"] = dossier
    if dossier:
        c_enemies = dossier.get("counters_enemies") or []
        cb_enemies = dossier.get("countered_by_enemies") or []
        synergies = dossier.get("best_ally_synergies") or []
        pos_role_title = dossier.get("pos_role_title") or f"{pos}号位·{hero_name}"

        def _lookup_hero_count(breakdown: Dict[str, Any], h_short: str) -> int:
            if not h_short or not isinstance(breakdown, dict):
                return 0
            h_list = breakdown.get("heroes")
            if isinstance(h_list, list):
                for entry in h_list:
                    if isinstance(entry, dict) and entry.get("hero_short_zh") == h_short:
                        return int(entry.get("count") or 0)
            return int(breakdown.get(h_short, 0) or 0)

        # 检查是否兑现了对敌方特定英雄的先天克制
        for ce in c_enemies[:2]:
            ce_txt = ce if isinstance(ce, str) else f"{ce.get('label', '')}：{ce.get('reason', '')}"
            matched_eh = next((ep.get("hero_short_zh", "") for ep in enemy_players if ep.get("hero_short_zh") and ep.get("hero_short_zh") in ce_txt), "")
            k_cnt = _lookup_hero_count(kills_info, matched_eh) if matched_eh else 0
            if matched_eh and k_cnt >= 2:
                _add_conclusion(
                    strengths,
                    f"⚔️ 【英雄机制克制完美兑现（手刃 {matched_eh}×{k_cnt}）】：{ce_txt} 本局精准锁定并击杀 {matched_eh} {k_cnt} 次，彻底打出英雄克制链价值！",
                    "inferred",
                )
            elif is_parsed and not won and matched_eh and k_cnt == 0 and pos in (1, 2, 3, 4) and ("天克" in ce_txt or "克制【" in ce_txt):
                _add_conclusion(
                    weaknesses,
                    f"⚠️ 【未发挥先天英雄克制优势（本应克制 {matched_eh}）】：{ce_txt} 但本局全场 0 次击杀 {matched_eh}，未能针对敌方被克制点打开突破口。",
                    "inferred",
                )

        # 检查是否被敌方天敌英雄机制针对提款，并给出专属破局出装
        for cbe in cb_enemies[:2]:
            cbe_txt = cbe if isinstance(cbe, str) else f"{cbe.get('label', '')}：{cbe.get('reason', '')} {cbe.get('item_solution', '')}"
            matched_eh = next((ep.get("hero_short_zh", "") for ep in enemy_players if ep.get("hero_short_zh") and ep.get("hero_short_zh") in cbe_txt), "")
            d_cnt = _lookup_hero_count(killed_by_info, matched_eh) if matched_eh else 0
            if matched_eh and d_cnt >= 2:
                _add_conclusion(
                    weaknesses,
                    f"🚨 【惨遭敌方天敌机制克制（被 {matched_eh} 击杀 {d_cnt} 次）】：{cbe_txt}",
                    "inferred",
                )
                _add_conclusion(
                    improvements,
                    f"🛡️ 【反制天敌 {matched_eh} 破局方案】：{cbe_txt}",
                    "template",
                    prepend=True,
                )

        # 注入该英雄在当前位置 (1~5号位) 的专属打法、禁忌与队友配合化学反应处方
        syn_hint = f" | 最佳队友配合：{synergies[0]}" if synergies else ""
        _add_conclusion(
            improvements,
            f"🎯 【{pos_role_title} · 英雄×位置专属法则】：{dossier.get('pos_playstyle')} 禁忌：{dossier.get('pos_taboo')}（出装铁律：{dossier.get('pos_item_rule')}{syn_hint}）",
            "template",
        )

    deaths_per_10m = deaths / max(1.0, duration_min / 10.0)
    death_rate_threshold = 2.0 if pos in (1, 2) else (2.4 if pos == 3 else 2.8)
    death_rate_weight = 10.0 if pos in (1, 2) else (8.0 if pos == 3 else 6.0)

    if deaths <= 4 and duration_min >= 30 and not is_afk_farmer:
        dead_ok_clause = (
            f"（读秒总计 {dead_min}分{dead_rem_s:02d}秒，仅占全场 {dead_pct:.1f}%）"
            if (is_parsed and dead_sec > 0)
            else ""
        )
        _add_conclusion(
            strengths,
            f"极高生存容错：{duration_min:.0f} 分钟高强度对抗仅阵亡 {deaths} 次{dead_ok_clause}，团战站位拉扯极佳。",
            "inferred",
        )
    elif deaths >= 6 and deaths_per_10m >= death_rate_threshold and not is_turret_fulfilled and not hmp.get("sacrificial_initiator_fulfilled"):
        blame_points += (deaths_per_10m - death_rate_threshold + 0.5) * death_rate_weight
        gold_lost_txt = f"，光阵亡直接扣掉 **{death_gold_lost:,} 金币**" if (is_parsed and death_gold_lost > 0) else ""
        dead_bad_clause = (
            f"，黑白屏幕读秒长达 **{dead_min}分{dead_rem_s:02d}秒（占整局比赛 {dead_pct:.1f}% 时间）**"
            if (is_parsed and dead_sec > 0)
            else ""
        )
        _add_conclusion(
            weaknesses,
            f"高频阵亡提款机：全场阵亡 **{deaths} 次**（每10分钟 {deaths_per_10m:.1f} 死）{nemesis_str}{dead_bad_clause}{gold_lost_txt}！",
            "measured",
            ["players[].deaths", "players[].killed_by", "players[].deaths_log", "players[].gold_reasons"],
        )
        roast_dead_txt = f"，看了整整 {dead_min}分{dead_rem_s}秒 黑白电视" if (is_parsed and dead_sec > 0) else ""
        roast_gold_txt = f"，光死就扣了 {death_gold_lost} 块钱" if (is_parsed and death_gold_lost > 0) else ""
        trash_candidates.append((
            88 + deaths,
            f"@{pname} 一局死 {deaths} 次{roast_dead_txt}{nemesis_str}{roast_gold_txt}，对面大哥给你磕一个不过分吧？",
        ))
        if pos in (4, 5):
            _add_conclusion(
                improvements,
                f"脆皮辅助切忌第一排脸探视野，团战站在核心侧后方阴影里交完技能立刻拉开，尽早做出保命装避免被 {nemesis_list[0]['hero_short_zh'] if nemesis_list else '敌方切入'} 无限提款。",
                "template",
            )
        else:
            _add_conclusion(
                improvements,
                f"核心位阵亡 {deaths} 次严重拖垮发育节奏：当敌方 {nemesis_list[0]['hero_short_zh'] if nemesis_list else '抓人核心'} 在小地图消失时，立刻放弃无视野兵线退回安全区。",
                "template",
            )

    # 兜底补充
    if not strengths:
        _add_conclusion(
            strengths,
            f"基础数据合格：交出 {kills}/{deaths}/{assists}（参战率 {kp:.1f}%，英雄伤害 {hdmg:,}），完成了该位置基础任务。",
            "measured",
            ["players[].kills", "players[].deaths", "players[].assists", "players[].hero_damage"],
        )
    if not weaknesses:
        steady_dead_clause = f"（读秒 {dead_min}分{dead_rem_s:02d}秒）" if (is_parsed and dead_sec > 0) else ""
        _add_conclusion(
            weaknesses,
            f"整体发挥稳健：全场仅阵亡 {deaths} 次{steady_dead_clause}，非要挑刺就是优势期拿盾推高的节奏可以再果断一点。",
            "template",
        )
    if not improvements:
        _add_conclusion(
            improvements,
            f"保持当前 {hero_name} 的刷钱与参战节奏（推荐核心出装：{hmp.get('core_item_hint') or '关键保命/输出装'}），继续卡死 7/14 分钟经验符和 20 分钟痛苦魔方节点。",
            "template",
        )

    # 计算胜局贡献点数 (raw_contrib_points) 与凯旋庆功贺词 (praise_talk)
    contrib_points = max(8.0, (mvp_score - 28.0) ** 1.35)
    if is_afk_farmer:
        contrib_points = max(6.0, contrib_points * 0.35)
    else:
        if hdmg_share >= 28.0:
            contrib_points += 20.0
        elif hdmg_share >= 22.0:
            contrib_points += 11.0
        if tdmg_share >= 50.0 and tdmg >= 9000:
            contrib_points += 32.0
        elif tdmg_share >= 40.0 and tdmg >= 3000:
            contrib_points += 15.0
        if kp >= 70.0:
            contrib_points += 14.0
        elif kp >= 60.0:
            contrib_points += 7.0
        if pos in (4, 5) and (obs + sen) >= 16:
            contrib_points += 15.0
        if stuns >= 35.0:
            contrib_points += 12.0
        if heal >= 4000:
            contrib_points += 9.0
        if stacked >= 4:
            contrib_points += 8.0
    if deaths >= 10 and not is_turret_fulfilled and not hmp.get("sacrificial_initiator_fulfilled"):
        contrib_points = max(6.0, contrib_points * 0.72)

    if is_afk_farmer:
        afk_praise_tail = "才把你抬进后期收割！" if duration_min >= 30 else "顶住正面压力！"
        praise_talk = f"@{pname} 这把 {hero_name} 前中期闷头独刷（参战率仅 {kp:.1f}% 全队垫底），全靠四个好兄弟正面 4 打 5 {afk_praise_tail}"
    elif pos == 1 and tdmg_share >= 48.0 and tdmg >= 9000:
        praise_talk = f"@{pname} 擎天一号位真核！{hero_name} 顶着前中期少人压力参战接团，单人狂拆 {tdmg:,} 建筑伤害（包揽全队 {tdmg_share:.0f}% 拆塔量）+ {hdmg:,} 伤害，当之无愧本局头号首功！"
    elif hmp.get("late_harvest_fulfilled") and late_hdmg_share is not None:
        praise_talk = f"@{pname} 教科书式大核节奏！{hero_name} 前中期隐忍刷钱成型，25m+ 决胜期出山狂轰 {late_hdmg:,} 后期伤害（占全队后期伤害 {late_hdmg_share:.1f}%）完成终极收割！"
    elif pos in (1, 2) and (hdmg_share >= 26.0 or is_turret_fulfilled):
        praise_talk = f"@{pname} 这把 {hero_name} 炮台火力全开狂轰 {hdmg:,} 伤害（占全队 {hdmg_share:.1f}% 输出，场均每死换 {int(dmg_per_death):,} 伤害），真正做到倒下前把所有技能灌满！"
    elif tdmg >= 5500 or (tdmg_share >= 45.0 and tdmg >= 3000):
        praise_talk = f"@{pname} 推塔终结机器！{hero_name} 单人拆出 {tdmg:,} 建筑伤害（占全队 {tdmg_share:.0f}%），赢团推塔一气呵成！"
    elif pos == 3 and (stuns >= 25.0 or dmg_taken_share >= 23.0):
        stun_praise_part = f"外加 {stuns:.1f} 秒硬控" if stuns > 0 else ""
        praise_talk = f"@{pname} 铁血三号位！{hero_name} 参战率 {kp:.0f}% 肉身扛下 {dmg_taken:,} 伤害（全队 {dmg_taken_share:.0f}%）{stun_praise_part}，完美团战发动机！"
    elif pos in (4, 5) and (obs + sen) >= 12:
        praise_talk = f"@{pname} 最佳幕后功臣！{hero_name} 全场点亮 {obs} 假 {sen} 真视野 + 参战率 {kp:.0f}%，吃草挤奶把大哥伺候得明明白白！"
    elif deaths >= 10:
        if won:
            praise_talk = f"@{pname} 这把 {hero_name} 阵亡 {deaths} 次吸引大量敌方火力，协助团队赢下比赛！"
        else:
            praise_dead_clause = f"（读秒 {dead_min}分{dead_rem_s:02d}秒）" if (is_parsed and dead_sec > 0) else ""
            praise_talk = f"@{pname} 这把 {hero_name} 阵亡 {deaths} 次承压严重{praise_dead_clause}，团战站位与切入时机亟待复盘优化。"
    else:
        praise_talk = f"@{pname} 稳健上分拼图！{hero_name} 交出 {kills}/{deaths}/{assists}（参战率 {kp:.0f}% · 伤害 {hdmg:,}），关键团战从不掉链子！"

    if trash_candidates:
        trash_candidates.sort(key=lambda x: x[0], reverse=True)
        trash_talk = trash_candidates[0][1]
    elif rating_score >= 8.8 or is_turret_fulfilled:
        trash_talk = f"@{pname} 这把 {hero_name} 中路打出线优+全场狂灌 {hdmg:,} 伤害（每死换 {int(dmg_per_death):,} 血），已经把炮台输出拉满了，已尽力扛起全队输出重任！"
    else:
        if won:
            trash_talk = f"@{pname} 这把 {kills}/{deaths}/{assists} 标准打卡下班，平稳跟团完成基础任务！"
        elif not is_parsed:
            trash_talk = f"@{pname} 这把 {kills}/{deaths}/{assists} 基础面板复盘（录像未解析，不计算分锅）。"
        else:
            trash_talk = f"@{pname} 这把 {kills}/{deaths}/{assists} 标准打卡下班，背锅占比 {blame_points:.0f} 点，逆风局未能站出来破局！"

    conclusions_out: List[Dict[str, Any]] = []
    for kind_name, seq in (("strength", strengths[:1]), ("weakness", weaknesses[:1]), ("improvement", improvements[:1])):
        for item_txt in seq:
            s_clean = str(item_txt or "").strip()
            if not s_clean:
                continue
            ev_decl, sf_decl = conclusion_meta.get(s_clean, ("template" if kind_name == "improvement" else "inferred", None))
            c_entry: Dict[str, Any] = {
                "text": s_clean,
                "kind": kind_name,
                "evidence": ev_decl,
            }
            if ev_decl == "measured" and sf_decl:
                c_entry["source_fields"] = sf_decl
            conclusions_out.append(c_entry)

    return {
        "evidence": "measured",
        "source_fields": ["players[].kills", "players[].deaths", "players[].assists", "players[].hero_damage", "players[].net_worth"],
        "coaching": {"evidence": "inferred"},
        "conclusions": conclusions_out,
        "is_afk_farmer": is_afk_farmer,
        "hero_mechanism_profile": hmp,
        "hero_matchup_dossier": dossier,
        "playstyle_archetype_audit": playstyle_audit,
        "radar": radar,
        "rating_score": rating_score,
        "rating_tier": rating_tier,
        "mvp_score": mvp_score,
        "raw_blame_points": round(blame_points, 1) if is_parsed else None,
        "raw_contrib_points": round(contrib_points, 1),
        "strengths": strengths,
        "weaknesses": weaknesses,
        "improvements": improvements,
        "trash_talk": trash_talk,
        "praise_talk": praise_talk,
    }


def build_player_playstyle_and_build_forensics(
    p: Dict[str, Any],
    own_team: List[Dict[str, Any]],
    opp_team: List[Dict[str, Any]],
    duration_min: float,
    won: bool,
) -> Dict[str, Any]:
    """
    为每位选手生成【实际打法流派识别 + 全量成装时间轴 + 技能/道具伤害占比 + 技能加点与10/15/20/25级天赋树 + 中立道具与附魔词条】全维度深度取证：
    避免只按呆板模板（如认为潮汐只能出笛子赤红甲站桩顶前排）评判选手，精准识别法系A杖巨浪炮台流、刷新双大流、速刷转型流、平A炮台流等灵性流派！
    """
    hid = int(p.get("hero_id") or 0)
    pos = int(p.get("pos") or 1)
    hero = str(p.get("hero_short_zh") or p.get("hero_name") or "")
    key_timings = [str(x) for x in (p.get("key_item_timings") or [])]
    final_items = [str(x) for x in (p.get("final_items") or [])]
    all_items_str = " | ".join(key_timings + final_items)
    full_chain_str = " → ".join(key_timings) if key_timings else ("、".join(final_items) or "基础装")

    dmg_sources = p.get("damage_by_source_rich") or []
    dq_audit = p.get("damage_and_build_audit") or {}
    nc_audit = p.get("neutral_craft_audit") or {}
    skill_route = str(dq_audit.get("skill_route_summary_zh") or "")
    talents = [
        str(t.get("zh") or t.get("tier") or "") if isinstance(t, dict) else str(t)
        for t in (dq_audit.get("talents_chosen") or [])
        if (t.get("zh") if isinstance(t, dict) else t)
    ]
    craft_steps = nc_audit.get("craft_steps") or []

    # 1) 技能与道具伤害占比拆解 (damage_by_source_rich)
    top_spells = [s for s in dmg_sources if s.get("source_type") == "ability"]
    top_items_dmg = [s for s in dmg_sources if s.get("source_type") == "item"]
    atk_entry = next((s for s in dmg_sources if s.get("source_type") == "attack"), None)
    atk_pct = float(atk_entry.get("share_pct") or 0.0) if atk_entry else 0.0
    spell_total_pct = round(sum(float(s.get("share_pct") or 0.0) for s in top_spells), 1)

    dmg_parts_zh: List[str] = []
    for s in dmg_sources[:5]:
        zh_n = s.get("zh_name") or s.get("key")
        d_val = int(s.get("damage") or 0)
        s_pct = float(s.get("share_pct") or 0.0)
        casts = int(s.get("casts") or 0)
        cast_txt = f"释放 {casts} 次" if casts > 0 else ""
        dmg_parts_zh.append(f"《{zh_n}》{cast_txt}造成 {d_val:,} 伤害（{s_pct:.1f}%）")
    spell_damage_breakdown_zh = (
        f"💥 【技能与道具伤害来源精细拆解（法系技能总占比 {spell_total_pct:.1f}% / 普攻占比 {atk_pct:.1f}%）】：{' ｜ '.join(dmg_parts_zh)}。"
        if dmg_parts_zh
        else ""
    )

    # 2) 技能加点路线 & 10/15/20/25级天赋树审计
    talents_str = " → ".join(talents) if talents else "未记录天赋"
    skill_and_talent_audit_zh = ""
    if skill_route or talents:
        talent_synergy_note = ""
        if hid == 29 and sum(1 for t in talents if "巨浪" in t) >= 2:
            talent_synergy_note = "（10/15/20级三连《巨浪》专属天赋拉满远程AOE减速、法系爆发与减甲，25级补《+1.0s 毁灭眩晕》配合刷新球双大控场，天赋与A杖夜慧玲珑心法系流派100%严丝合缝！）"
        elif any("冷却" in t or "施法距离" in t or "伤害" in t for t in talents):
            talent_synergy_note = "（天赋树选择与本局核心装备路线高度协同）"
        skill_and_talent_audit_zh = (
            f"🌿 【技能加点路线 & 10/15/20/25级天赋树拆解】：前中期加点【{skill_route or '常规主副技能'}】，"
            f"天赋树依次点出【{talents_str}】{talent_synergy_note}。"
        )

    # 3) 中立道具与附魔词条选择审计
    neutral_and_enchantment_audit_zh = ""
    has_greedy_ench = False
    has_timeless_or_mystic_ench = False
    if craft_steps:
        step_strs = []
        for cs in craft_steps:
            if isinstance(cs, str):
                step_strs.append(cs)
                if "贪婪" in cs:
                    has_greedy_ench = True
                if any(k in cs for k in ("永恒", "神秘", "敏锐", "高远", "催化剂", "火焰斗篷")):
                    has_timeless_or_mystic_ench = True
                continue
            t_s = cs.get("time_str") or ""
            tier = cs.get("tier") or "?"
            iz = cs.get("item_zh") or "中立道具"
            ez = cs.get("ench_zh") or ""
            if "贪婪" in ez:
                has_greedy_ench = True
            if any(k in ez for k in ("永恒", "神秘", "敏锐", "高远")):
                has_timeless_or_mystic_ench = True
            step_strs.append(f"{t_s}【T{tier}·{iz}{f' + {ez}' if ez else ''}】")
        ench_reason = ""
        if has_greedy_ench and has_timeless_or_mystic_ench:
            ench_reason = " —— 前中期选用【贪婪附魔(+GPM工资/蓝量)】加速核心大件的刷钱成型速度，后期切换【永恒/神秘附魔(+技能增强/负面状态持续时间)】将法系技能爆发与控制时长拉满！"
        elif has_greedy_ench:
            ench_reason = " —— 中期巧用【贪婪附魔(+GPM工资)】加速核心装备成型节奏。"
        elif has_timeless_or_mystic_ench:
            ench_reason = " —— 中后期选用【永恒/神秘/高远附魔】精准强化技能爆发与施法距离。"
        neutral_and_enchantment_audit_zh = (
            f"🎲 【中立道具演进与附魔词条审计】：{' → '.join(step_strs)}{ench_reason}"
        )

    # 4) 实际打法流派定性 (Playstyle Archetype Detection)
    has_aghs = any(k in all_items_str for k in ("阿哈利姆神杖", "阿哈利姆福佑", "[A杖加持]"))
    has_shard = any(k in all_items_str for k in ("阿哈利姆魔晶", "[魔晶加持]"))
    has_spell_amp_items = any(k in all_items_str for k in ("慧光", "夜慧对剑", "慧夜对剑", "血精石", "玲珑心", "以太之镜", "大灵匣", "达贡之神力", "纷争面纱", "巫师之刃", "英灵胸针"))
    has_refresher = "刷新球" in all_items_str
    has_blink = any(k in all_items_str for k in ("闪烁匕首", "跳刀", "盛势闪光", "迅疾闪光", "秘奥闪光"))
    has_lotus = "清莲宝珠" in all_items_str
    has_bkb = "黑皇杖" in all_items_str
    top_spell = top_spells[0] if top_spells else None
    top_spell_name = str(top_spell.get("zh_name") or "") if top_spell else ""
    top_spell_dmg = int(top_spell.get("damage") or 0) if top_spell else 0
    top_spell_pct = float(top_spell.get("share_pct") or 0.0) if top_spell else 0.0
    top_spell_casts = int(top_spell.get("casts") or 0) if top_spell else 0

    anti_tank_enemies = [
        str(ep.get("hero_short_zh") or "")
        for ep in opp_team
        if int(ep.get("hero_id") or 0) in (59, 114, 93, 70, 54, 47, 6, 36, 98)
    ]

    archetype_badge = f"⚔️ {pos}号位标准战术流"
    archetype_analysis_zh = ""
    is_smart_playstyle_pivot = False

    if hid == 29 and has_aghs and (has_spell_amp_items or top_spell_name == "巨浪" and top_spell_pct >= 30.0):
        # 潮汐猎人：法系A杖巨浪远程炮台 + 刷新双大流
        is_smart_playstyle_pivot = True
        archetype_badge = "🌊 法系A杖巨浪远程炮台 + 刷新双大流"
        anti_tank_clause = (
            f"面对敌方 {', '.join(anti_tank_enemies)} 这种专打笨重站桩前排的阵容（若走传统笛子赤红甲纯肉盾顶前排，只会沦为敌方核心叠被动的活靶子），"
            if anti_tank_enemies
            else "针对本局敌我阵容博弈，"
        )
        lotus_dmg_entry = next((s for s in top_items_dmg if "清莲宝珠" in str(s.get("zh_name") or "")), None)
        lotus_clause = (
            f"，并补出《清莲宝珠》反弹技能打出 {int(lotus_dmg_entry['damage']):,} 伤害"
            if lotus_dmg_entry
            else ("，并补出《清莲宝珠》针对敌方沉默与点控" if has_lotus else "")
        )
        gpm_val = int(p.get("gpm") or 0)
        archetype_analysis_zh = (
            f"🌊 【核心流派深度识别：{archetype_badge}（绝非传统挨打肉盾流！）】：{anti_tank_clause}"
            f"本局{hero}灵性转型「法系速刷A杖巨浪吐水炮台流」！完整出装链路为【{full_chain_str}】（全场 {gpm_val} GPM）{lotus_clause}，把法系技能增强与冷却缩减堆到极致！"
            f"全场狂吐 **{top_spell_casts} 次《{top_spell_name or '巨浪'}》轰出 {top_spell_dmg:,} 点英雄伤害（占自身总输出 {top_spell_pct:.1f}%，高居第一伤害源！）**，"
            f"配合天赋【{talents_str}】与中立附魔，既避免了肉身贴脸给敌方核心叠被动，又用超远距离高频巨浪减甲减速与大招控场接管了后期团战！"
        )
    elif has_aghs and has_spell_amp_items and spell_total_pct >= 55.0:
        is_smart_playstyle_pivot = True
        archetype_badge = f"🧙‍♂️ 法系A杖技能增强炮台流（技能伤占 {spell_total_pct:.0f}%）"
        archetype_analysis_zh = (
            f"🧙‍♂️ 【流派识别：{archetype_badge}】：本局 {hero} 走的是深度法系技能强化路线，完整出装时间轴为【{full_chain_str}】"
            + (
                f"。核心输出依靠《{top_spell_name}》（"
                + (f"释放 {top_spell_casts} 次" if top_spell_casts > 0 else "")
                + f"造成 {top_spell_dmg:,} 伤害，占自身总输出 {top_spell_pct:.1f}%），配合神杖/法系增伤装与天赋附魔打出高频远程法术压制。"
                if top_spell_name and top_spell_dmg > 0
                else "，配合神杖/法系增伤装与天赋附魔打出高频远程法术压制。"
            )
        )
    elif pos in (1, 2) and atk_pct >= 50.0:
        archetype_badge = f"🗡️ 物理平A核心收割流（普攻占 {atk_pct:.0f}%）"
        archetype_analysis_zh = (
            f"🗡️ 【流派识别：{archetype_badge}】：本局 {hero} 完整出装演进为【{full_chain_str}】，"
            f"普通攻击贡献 {atk_pct:.1f}% 伤害"
            + (f"，配合《{top_spell_name}》（{top_spell_dmg:,} 伤害 / {top_spell_pct:.1f}%）完成团战切入与收割。" if top_spell_name and top_spell_dmg > 0 else "。")
        )
    elif pos == 3 and has_blink:
        archetype_badge = "⚡ 跳刀先手控制 + 阵地反制流"
        archetype_analysis_zh = (
            f"⚡ 【流派识别：{archetype_badge}】：本局 3号位 {hero} 完整出装演进为【{full_chain_str}】，"
            f"主打跳刀先手开团与前中排技能拉扯"
            + (
                f"，主力技能《{top_spell_name}》"
                + (f"释放 {top_spell_casts} 次" if top_spell_casts > 0 else "")
                + f"造成 {top_spell_dmg:,} 伤害（{top_spell_pct:.1f}%）。"
                if top_spell_name and top_spell_dmg > 0
                else "。"
            )
        )
    else:
        archetype_badge = f"🧭 {pos}号位·{hero}战术出装流"
        archetype_analysis_zh = (
            f"🧭 【流派与全链路出装时间轴】：本局 {hero} 完整成装演进为【{full_chain_str}】"
            + (
                f"，主要伤害来源为《{top_spell_name}》（"
                + (f"释放 {top_spell_casts} 次" if top_spell_casts > 0 else "")
                + f"造成 {top_spell_dmg:,} 伤害，占 {top_spell_pct:.1f}%）。"
                if top_spell_name and top_spell_dmg > 0
                else "。"
            )
        )

    # 5) 技能×敌方目标精准命中账本 & 单发最高名场面 (spell_target_matrix + max_hit_summary_zh)
    st_matrix = dq_audit.get("spell_target_matrix") or []
    max_hit_str = str(dq_audit.get("max_hit_summary_zh") or "")
    st_summaries = [str(row.get("summary_zh") or "") for row in st_matrix[:5] if row.get("summary_zh")]
    spell_target_audit_zh = ""
    if st_summaries or (max_hit_str and "无单发" not in max_hit_str):
        mh_prefix = f"🔥 【单发最高名场面】：{max_hit_str} ｜ " if (max_hit_str and "无单发" not in max_hit_str) else ""
        spell_target_audit_zh = f"🎯 【技能×敌方目标精准命中账本】：{mh_prefix}{' ｜ '.join(st_summaries)}"

    # 6) 永久 Buff 叠层与命石审计 (perm_buff_badges + perm_buff_notes)
    pb_badges = [str(b) for b in (dq_audit.get("perm_buff_badges") or []) if b]
    pb_notes = [str(n) for n in (dq_audit.get("perm_buff_notes") or []) if n]
    perm_buff_audit_zh = ""
    if pb_badges or pb_notes:
        perm_buff_audit_zh = (
            f"♾️ 【永久 Buff 叠层 & 命石审计】：{' · '.join(pb_badges)}"
            + (f" —— {' '.join(pb_notes)}" if pb_notes else "")
        )

    return {
        "archetype_badge": archetype_badge,
        "is_smart_playstyle_pivot": is_smart_playstyle_pivot,
        "full_item_progression_zh": full_chain_str,
        "archetype_analysis_zh": archetype_analysis_zh,
        "spell_damage_breakdown_zh": spell_damage_breakdown_zh,
        "skill_and_talent_audit_zh": skill_and_talent_audit_zh,
        "neutral_and_enchantment_audit_zh": neutral_and_enchantment_audit_zh,
        "spell_target_audit_zh": spell_target_audit_zh,
        "perm_buff_audit_zh": perm_buff_audit_zh,
        "max_hit_summary_zh": max_hit_str,
        "spell_target_matrix": st_matrix,
        "perm_buff_badges": pb_badges,
        "perm_buff_notes": pb_notes,
        "talents_chosen": talents,
        "skill_route_summary_zh": skill_route,
        "neutral_craft_steps": craft_steps,
    }


def assign_team_blame_percentages(team_players: List[Dict[str, Any]], is_parsed: bool = True) -> None:
    """
    同时计算一方 5 人的:
    1) 100% 败局分锅占比 (blame_share_pct) —— 未解析比赛不计算分锅 (设为 None)
    2) 100% 胜局贡献占比 (contrib_share_pct) 与功勋头衔 (contrib_tier)
    """
    has_blame = bool(is_parsed) and any(p.get("raw_blame_points") is not None for p in team_players)
    if has_blame:
        total_blame = sum(float(p.get("raw_blame_points") or 10.0) for p in team_players) or 1.0
        for p in team_players:
            share = round(float(p.get("raw_blame_points") or 10.0) / total_blame * 100.0, 1)
            p["blame_share_pct"] = share

        if team_players:
            diff = round(100.0 - sum(p["blame_share_pct"] for p in team_players), 1)
            max_p = max(team_players, key=lambda x: x["blame_share_pct"])
            max_p["blame_share_pct"] = round(max_p["blame_share_pct"] + diff, 1)
    else:
        for p in team_players:
            p["blame_share_pct"] = None
            p["blame_rank"] = None

    total_contrib = sum(p.get("raw_contrib_points", 20.0) for p in team_players) or 1.0
    for p in team_players:
        c_share = round(p.get("raw_contrib_points", 20.0) / total_contrib * 100.0, 1)
        p["contrib_share_pct"] = c_share

    if team_players:
        c_diff = round(100.0 - sum(p["contrib_share_pct"] for p in team_players), 1)
        top_c = max(team_players, key=lambda x: x["contrib_share_pct"])
        top_c["contrib_share_pct"] = round(top_c["contrib_share_pct"] + c_diff, 1)

        sorted_by_c = sorted(team_players, key=lambda x: (x.get("contrib_share_pct", 0), x.get("mvp_score", 0)), reverse=True)
        for rank_idx, cp in enumerate(sorted_by_c):
            cp["contrib_rank"] = rank_idx + 1
            if rank_idx == 0:
                cp["contrib_tier"] = "👑 头号首功 · 擎天真神"
            elif rank_idx == 1:
                cp["contrib_tier"] = "⚔️ 破阵二当家 · 左膀右臂"
            elif rank_idx == 2:
                cp["contrib_tier"] = "👁️ 视野统帅 · 幕后功臣" if cp.get("pos") in (4, 5) else "🛡️ 定海神针 · 中坚功臣"
            elif rank_idx == 3:
                cp["contrib_tier"] = "🔥 黄金拼图 · 稳健节奏"
            else:
                cp["contrib_tier"] = "🛡️ 吸火支点 · 团队拼图" if (cp.get("deaths", 0) >= 8) else "🥂 凯旋功臣 · 团队拼图"


BLAME_CULPRIT_THRESHOLD = 45.0


def select_match_mvp_and_culprit(
    radiant_players: List[Dict[str, Any]],
    dire_players: List[Dict[str, Any]],
    radiant_win: bool,
    user_team_side: Optional[str],
    grok_coaching: Optional[Dict[str, Any]] = None,
    is_parsed: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    评选:
    1. 全场 MVP (AI MVP)
    2. 胜方二当家 (Runner-up)
    3. 败方 SVP (Losing Team Best)
    4. 车队头号大锅 / 一级战犯 (仅在已解析败局判定；未解析比赛不计算分锅)
    """
    all_ps = list(radiant_players or []) + list(dire_players or [])
    unparsed = (is_parsed is False) or (
        bool(all_ps)
        and all(p.get("raw_blame_points") is None and p.get("blame_share_pct") is None for p in all_ps)
    )
    grok_side = (grok_coaching or {}).get("side") if isinstance(grok_coaching, dict) else None
    grok_players = (grok_coaching or {}).get("players") if isinstance(grok_coaching, dict) else None

    def _find_grok_entry(p: Dict[str, Any], side_key: str) -> Optional[Dict[str, Any]]:
        if not isinstance(grok_players, list) or not grok_players:
            return None
        if grok_side and grok_side != side_key:
            return None
        slot = p.get("player_slot")
        pos = p.get("pos")
        h_short = p.get("hero_short_zh")
        for gp in grok_players:
            if not isinstance(gp, dict):
                continue
            if slot is not None and gp.get("slot") is not None and int(gp.get("slot")) == int(slot):
                return gp
            if pos is not None and gp.get("pos") is not None and int(gp.get("pos")) == int(pos):
                return gp
            if h_short and gp.get("hero") == h_short:
                return gp
        return None

    rankings_by_side: Dict[str, Dict[str, Any]] = {}
    for side_key, team_players, side_won in (
        ("radiant", radiant_players, bool(radiant_win)),
        ("dire", dire_players, not bool(radiant_win)),
    ):
        for p in team_players:
            gp = _find_grok_entry(p, side_key)
            raw_sc = (
                gp.get("grok_score")
                if gp and gp.get("grok_score") is not None
                else round(float(p.get("rating_score") or 7.0) * 10)
            )
            p["score_100"] = max(15, min(99, int(round(float(raw_sc)))))
            if gp and gp.get("grok_share_pct") is not None and float(gp.get("grok_share_pct") or 0) > 0:
                if side_won:
                    p["contrib_share_pct"] = round(float(gp["grok_share_pct"]), 1)
                elif not unparsed:
                    p["blame_share_pct"] = round(float(gp["grok_share_pct"]), 1)

        if side_won:
            by_contrib = sorted(
                team_players,
                key=lambda x: (
                    float(x.get("contrib_share_pct") or 0),
                    int(x.get("score_100") or 0),
                    float(x.get("mvp_score") or 0),
                ),
                reverse=True,
            )
        else:
            by_contrib = sorted(
                team_players,
                key=lambda x: (
                    int(x.get("score_100") or 0),
                    float(x.get("mvp_score") or 0),
                    float(x.get("contrib_share_pct") or 0),
                ),
                reverse=True,
            )
        for idx, p in enumerate(by_contrib, start=1):
            p["contrib_rank"] = idx

        c_slots = [int(p["player_slot"]) for p in by_contrib]
        side_won = bool(radiant_win if side_key == "radiant" else not radiant_win)
        if unparsed:
            for p in team_players:
                p["blame_rank"] = None
            rankings_by_side[side_key] = {
                "no_clear_culprit": True,
                "mvp_slot": c_slots[0] if c_slots else 0,
                "runner_up_slot": c_slots[1] if len(c_slots) > 1 else (c_slots[0] if c_slots else 0),
                "culprit_slot": None,
                "second_culprit_slot": None,
                "contrib_order_slots": c_slots,
                "blame_order_slots": [],
            }
        else:
            by_blame = sorted(
                team_players,
                key=lambda x: (
                    float(x.get("blame_share_pct") or 0),
                    -int(x.get("score_100") or 0),
                ),
                reverse=True,
            )
            for idx, p in enumerate(by_blame, start=1):
                p["blame_rank"] = idx
            b_slots = [int(p["player_slot"]) for p in by_blame]
            side_max_blame = max((float(p.get("raw_blame_points") or 0.0) for p in team_players), default=0.0)
            side_no_clear = bool(side_won or side_max_blame < BLAME_CULPRIT_THRESHOLD)
            rankings_by_side[side_key] = {
                "no_clear_culprit": side_no_clear,
                "mvp_slot": c_slots[0] if c_slots else 0,
                "runner_up_slot": c_slots[1] if len(c_slots) > 1 else (c_slots[0] if c_slots else 0),
                "culprit_slot": b_slots[0] if b_slots else 0,
                "second_culprit_slot": b_slots[1] if len(b_slots) > 1 else (b_slots[0] if b_slots else 0),
                "contrib_order_slots": c_slots,
                "blame_order_slots": b_slots,
            }

    winning_team = radiant_players if radiant_win else dire_players
    losing_team = dire_players if radiant_win else radiant_players
    win_side_zh = "天辉" if radiant_win else "夜魇"
    lose_side_zh = "夜魇" if radiant_win else "天辉"

    focus_team = (
        radiant_players
        if user_team_side == "radiant"
        else (dire_players if user_team_side == "dire" else winning_team)
    )
    focus_side_zh = "天辉" if focus_team is radiant_players else "夜魇"
    focus_won = (radiant_win if focus_team is radiant_players else not radiant_win)

    win_sorted = sorted(winning_team, key=lambda x: int(x.get("contrib_rank") or 99))
    lose_sorted = sorted(losing_team, key=lambda x: int(x.get("contrib_rank") or 99))
    focus_by_contrib = sorted(focus_team, key=lambda x: int(x.get("contrib_rank") or 99))
    focus_by_blame = (
        list(reversed(focus_by_contrib))
        if unparsed
        else sorted(focus_team, key=lambda x: int(x.get("blame_rank") or 99))
    )

    mvp = win_sorted[0]
    runner_up = win_sorted[1] if len(win_sorted) > 1 else win_sorted[0]
    svp = lose_sorted[0]
    culprit = focus_by_blame[0]
    second_culprit = focus_by_blame[1] if len(focus_by_blame) > 1 else culprit

    def _fmt_pct(v: Any) -> str:
        return f"{v}%" if v is not None else "无数据"

    mvp_c_str = _fmt_pct(mvp.get("contrib_share_pct"))
    ru_c_str = _fmt_pct(runner_up.get("contrib_share_pct"))
    cul_c_str = _fmt_pct(culprit.get("contrib_share_pct"))

    mvp_reasons = [
        f"全场头号首功 ({mvp['rating_score']}分 · 胜局贡献 {mvp_c_str})：{win_side_zh} {mvp['pos']}号位 {mvp['hero_short_zh']}（{mvp['personaname']}）交出 {mvp['kda']}（参战率 {mvp['kill_participation_pct']}%）。",
        f"核心统治力数据：单人打出 {mvp['hero_damage']:,} 英雄伤害（占全队 {mvp['hero_damage_share_pct']}%）+ {mvp['tower_damage']:,} 建筑伤害，总经济 {mvp['net_worth']:,}（GPM {mvp['gpm']} / XPM {mvp['xpm']}）。",
        f"制胜关键：{mvp['strengths'][0]}",
        f"胜方二当家（胜局贡献 {ru_c_str}）：{runner_up['pos']}号位 {runner_up['hero_short_zh']}（{runner_up['personaname']}，评分 {runner_up['rating_score']}）贡献 {runner_up['kda']}（参战率 {runner_up['kill_participation_pct']}%，伤害 {runner_up['hero_damage']:,}）。",
        f"败方孤胆院长 (SVP)：{lose_side_zh} {svp['pos']}号位 {svp['hero_short_zh']}（{svp['personaname']}，评分 {svp['rating_score']}）交出 {svp['kda']}（伤害 {svp['hero_damage']:,}），一神带四坑实在带不动。",
    ]

    if unparsed:
        no_clear_culprit = True
        culprit_label = "未解析比赛不计责任占比"
        culprit_verdict = "本局录像未解析，不计算责任占比（需要先解析录像）。"
    else:
        max_blame_pts = max((float(p.get("raw_blame_points") or 0.0) for p in focus_team), default=0.0)
        no_clear_culprit = bool(focus_won or max_blame_pts < BLAME_CULPRIT_THRESHOLD)
        culprit_label = "无明显责任人" if no_clear_culprit else "主要问题焦点"
        if focus_won:
            culprit_verdict = (
                f"凯旋庆功总结：{focus_side_zh}头号首功 {mvp['hero_short_zh']}（{mvp['personaname']}，贡献 {mvp_c_str}）与二当家 {runner_up['hero_short_zh']}（{runner_up['personaname']}，贡献 {ru_c_str}）携手带飞！"
                f" 本局复盘短板位：{culprit['pos']}号位 {culprit['hero_short_zh']}（{culprit['personaname']}，贡献 {cul_c_str}）。"
            )
        elif no_clear_culprit:
            culprit_verdict = (
                f"无明显责任人：本局{focus_side_zh}五人最高失误点数（{max_blame_pts:.1f}）低于阈值（{BLAME_CULPRIT_THRESHOLD:.0f}），不指定主要责任人。"
                f" 相对待改进点（{culprit['pos']}号位 {culprit['hero_short_zh']}）：{culprit['weaknesses'][0]}"
            )
        else:
            culprit_verdict = (
                f"主要问题焦点（责任占比 {culprit['blame_share_pct']}%）：{focus_side_zh} {culprit['pos']}号位 {culprit['hero_short_zh']}（{culprit['personaname']}，评分 {culprit['rating_score']}）——"
                f"本局关键失误点：{culprit['weaknesses'][0]}"
            )

    mvp_st0_c = next((c for c in (mvp.get("conclusions") or []) if c.get("kind") == "strength"), None)
    st0_ev = mvp_st0_c.get("evidence", "inferred") if isinstance(mvp_st0_c, dict) else "inferred"
    st0_sf = mvp_st0_c.get("source_fields") if isinstance(mvp_st0_c, dict) else None
    st0_entry: Dict[str, Any] = {"text": mvp_reasons[2], "kind": "rationale", "evidence": st0_ev}
    if st0_ev == "measured" and st0_sf:
        st0_entry["source_fields"] = list(st0_sf)

    cul_entry: Dict[str, Any] = (
        {"text": culprit_verdict, "kind": "rationale", "evidence": "measured", "source_fields": ["version"]}
        if unparsed
        else {"text": culprit_verdict, "kind": "rationale", "evidence": "inferred"}
    )
    mvp_conclusions: List[Dict[str, Any]] = [
        {"text": mvp_reasons[0], "kind": "rationale", "evidence": "inferred"},
        {
            "text": mvp_reasons[1],
            "kind": "rationale",
            "evidence": "measured",
            "source_fields": [
                "players[].hero_damage",
                "players[].tower_damage",
                "players[].net_worth",
                "players[].gold_per_min",
                "players[].xp_per_min",
            ],
        },
        st0_entry,
        {"text": mvp_reasons[3], "kind": "rationale", "evidence": "inferred"},
        {"text": mvp_reasons[4], "kind": "rationale", "evidence": "inferred"},
        cul_entry,
    ]

    return {
        "evidence": "inferred",
        "conclusions": mvp_conclusions,
        "no_clear_culprit": no_clear_culprit,
        "culprit_label": culprit_label,
        "rankings_by_side": rankings_by_side,
        "mvp_player": {
            "evidence": "inferred",
            "player_slot": mvp["player_slot"],
            "side": win_side_zh,
            "pos": mvp["pos"],
            "pos_label": mvp["pos_label"],
            "hero_name": mvp["hero_name"],
            "hero_short_zh": mvp.get("hero_short_zh", mvp["hero_name"]),
            "hero_img": mvp.get("hero_img"),
            "hero_icon": mvp.get("hero_icon"),
            "personaname": mvp["personaname"],
            "friend_tag": mvp.get("friend_tag"),
            "kda": mvp["kda"],
            "rating_score": mvp["rating_score"],
            "rating_tier": mvp["rating_tier"],
            "mvp_score": mvp["mvp_score"],
            "blame_share_pct": mvp["blame_share_pct"],
            "contrib_share_pct": mvp.get("contrib_share_pct"),
            "contrib_tier": mvp.get("contrib_tier", "👑 头号首功 · 擎天真神"),
            "gpm": mvp["gpm"],
            "xpm": mvp["xpm"],
            "hero_damage": mvp["hero_damage"],
            "hero_damage_share_pct": mvp["hero_damage_share_pct"],
            "tower_damage": mvp["tower_damage"],
            "kill_participation_pct": mvp["kill_participation_pct"],
            "trash_talk": mvp["trash_talk"],
            "praise_talk": mvp.get("praise_talk", ""),
        },
        "runner_up_player": {
            "player_slot": runner_up["player_slot"],
            "side": win_side_zh,
            "pos": runner_up["pos"],
            "pos_label": runner_up["pos_label"],
            "hero_name": runner_up["hero_name"],
            "hero_short_zh": runner_up.get("hero_short_zh", runner_up["hero_name"]),
            "hero_img": runner_up.get("hero_img"),
            "hero_icon": runner_up.get("hero_icon"),
            "personaname": runner_up["personaname"],
            "friend_tag": runner_up.get("friend_tag"),
            "kda": runner_up["kda"],
            "gpm": runner_up["gpm"],
            "xpm": runner_up["xpm"],
            "hero_damage": runner_up["hero_damage"],
            "hero_damage_share_pct": runner_up["hero_damage_share_pct"],
            "tower_damage": runner_up["tower_damage"],
            "kill_participation_pct": runner_up["kill_participation_pct"],
            "rating_score": runner_up["rating_score"],
            "rating_tier": runner_up["rating_tier"],
            "blame_share_pct": runner_up["blame_share_pct"],
            "contrib_share_pct": runner_up.get("contrib_share_pct"),
            "contrib_tier": runner_up.get("contrib_tier", "⚔️ 破阵二当家 · 左膀右臂"),
            "strengths": runner_up.get("strengths", []),
            "praise_talk": runner_up.get("praise_talk", ""),
        },
        "svp_player": {
            "player_slot": svp["player_slot"],
            "side": lose_side_zh,
            "pos": svp["pos"],
            "pos_label": svp["pos_label"],
            "hero_name": svp["hero_name"],
            "hero_short_zh": svp.get("hero_short_zh", svp["hero_name"]),
            "hero_img": svp.get("hero_img"),
            "hero_icon": svp.get("hero_icon"),
            "personaname": svp["personaname"],
            "kda": svp["kda"],
            "gpm": svp["gpm"],
            "hero_damage": svp["hero_damage"],
            "tower_damage": svp["tower_damage"],
            "kill_participation_pct": svp["kill_participation_pct"],
            "rating_score": svp["rating_score"],
            "rating_tier": svp["rating_tier"],
            "blame_share_pct": svp["blame_share_pct"],
            "contrib_share_pct": svp.get("contrib_share_pct"),
        },
        "culprit_player": {
            "evidence": "measured" if unparsed else "inferred",
            "player_slot": culprit["player_slot"],
            "side": focus_side_zh,
            "pos": culprit["pos"],
            "pos_label": culprit["pos_label"],
            "hero_name": culprit["hero_name"],
            "hero_short_zh": culprit.get("hero_short_zh", culprit["hero_name"]),
            "hero_img": culprit.get("hero_img"),
            "hero_icon": culprit.get("hero_icon"),
            "personaname": culprit["personaname"],
            "friend_tag": culprit.get("friend_tag"),
            "kda": culprit["kda"],
            "rating_score": culprit["rating_score"],
            "rating_tier": culprit["rating_tier"],
            "blame_share_pct": culprit["blame_share_pct"],
            "contrib_share_pct": culprit.get("contrib_share_pct"),
            "contrib_tier": culprit.get("contrib_tier", "🥂 凯旋功臣 · 团队拼图"),
            "no_clear_culprit": no_clear_culprit,
            "culprit_label": culprit_label,
            "dead_seconds": culprit.get("dead_seconds", 0),
            "death_gold_lost": culprit.get("death_gold_lost", 0),
            "main_crime": culprit["weaknesses"][0],
            "trash_talk": culprit["trash_talk"],
            "praise_talk": culprit.get("praise_talk", ""),
            "verdict": culprit_verdict,
        },
        "second_culprit_player": {
            "player_slot": second_culprit["player_slot"],
            "side": focus_side_zh,
            "pos": second_culprit["pos"],
            "hero_name": second_culprit["hero_name"],
            "hero_short_zh": second_culprit.get("hero_short_zh", second_culprit["hero_name"]),
            "hero_img": second_culprit.get("hero_img"),
            "hero_icon": second_culprit.get("hero_icon"),
            "personaname": second_culprit["personaname"],
            "kda": second_culprit["kda"],
            "rating_score": second_culprit["rating_score"],
            "blame_share_pct": second_culprit["blame_share_pct"],
            "contrib_share_pct": second_culprit.get("contrib_share_pct"),
            "main_crime": second_culprit["weaknesses"][0],
        },
        "focus_team_blame_ranking": (
            []
            if unparsed
            else [
                {
                    "pos": fp["pos"],
                    "hero_name": fp["hero_name"],
                    "hero_short_zh": fp.get("hero_short_zh", fp["hero_name"]),
                    "hero_img": fp.get("hero_img"),
                    "hero_icon": fp.get("hero_icon"),
                    "personaname": fp["personaname"],
                    "friend_tag": fp.get("friend_tag"),
                    "blame_share_pct": fp["blame_share_pct"],
                    "contrib_share_pct": fp.get("contrib_share_pct"),
                    "contrib_tier": fp.get("contrib_tier", ""),
                    "rating_score": fp["rating_score"],
                    "rating_tier": fp["rating_tier"],
                    "kda": fp["kda"],
                    "dead_seconds": fp.get("dead_seconds"),
                    "death_gold_lost": fp.get("death_gold_lost"),
                    "trash_talk": fp["trash_talk"],
                    "praise_talk": fp.get("praise_talk", ""),
                }
                for fp in focus_by_blame
            ]
        ),
        "focus_team_contrib_ranking": [
            {
                "pos": fp["pos"],
                "hero_name": fp["hero_name"],
                "hero_short_zh": fp.get("hero_short_zh", fp["hero_name"]),
                "hero_img": fp.get("hero_img"),
                "hero_icon": fp.get("hero_icon"),
                "personaname": fp["personaname"],
                "friend_tag": fp.get("friend_tag"),
                "contrib_share_pct": fp.get("contrib_share_pct"),
                "contrib_tier": fp.get("contrib_tier", ""),
                "blame_share_pct": fp["blame_share_pct"],
                "rating_score": fp["rating_score"],
                "rating_tier": fp["rating_tier"],
                "kda": fp["kda"],
                "hero_damage": fp["hero_damage"],
                "tower_damage": fp["tower_damage"],
                "praise_talk": fp.get("praise_talk", ""),
            }
            for fp in focus_by_contrib
        ],
        "rationale_list": mvp_reasons + [culprit_verdict],
    }


def build_four_stage_narrative(
    match: Dict[str, Any],
    radiant_players: List[Dict[str, Any]],
    dire_players: List[Dict[str, Any]],
    economy_timeline: Dict[str, Any],
    key_teamfights: List[Dict[str, Any]],
    user_team_side: Optional[str],
) -> Dict[str, Any]:
    """生成四阶段对局剧本与三路对线数据对账"""
    is_parsed = bool(match.get("version"))
    radiant_win = bool(match.get("radiant_win"))
    duration_min = round((match.get("duration") or 0) / 60.0, 1)
    gold_adv = match.get("radiant_gold_adv") or []

    lane_matchups = []
    if is_parsed:
        lane_names = {
            3: "上路 (天辉劣势路 vs 夜魇优势路)",
            2: "中路 (双方 2 号位 1v1)",
            1: "下路 (天辉优势路 vs 夜魇劣势路)",
        }
        for lane_id in (3, 2, 1):
            rad_in_lane = [p for p in radiant_players if p.get("raw_lane") == lane_id]
            dire_in_lane = [p for p in dire_players if p.get("raw_lane") == lane_id]
            if not rad_in_lane and not dire_in_lane:
                continue
            rad_g10 = sum((p.get("laning_10m") or {}).get("gold10") or 0 for p in rad_in_lane)
            dire_g10 = sum((p.get("laning_10m") or {}).get("gold10") or 0 for p in dire_in_lane)
            diff = rad_g10 - dire_g10
            if abs(diff) <= 450:
                verdict = "均势互刷"
            elif diff > 1200:
                verdict = f"天辉打穿 (+{diff:,}金)"
            elif diff > 450:
                verdict = f"天辉小优 (+{diff:,}金)"
            elif diff < -1200:
                verdict = f"夜魇打穿 (+{abs(diff):,}金)"
            else:
                verdict = f"夜魇小优 (+{abs(diff):,}金)"

            rad_desc = " + ".join(
                f"{p['pos']}号位{p.get('hero_short_zh', p['hero_name'])}(10m:{int((p.get('laning_10m') or {}).get('lh10') or 0)}刀/{int((p.get('laning_10m') or {}).get('gold10') or 0):,}金)"
                for p in rad_in_lane
            ) or "游走"
            dire_desc = " + ".join(
                f"{p['pos']}号位{p.get('hero_short_zh', p['hero_name'])}(10m:{int((p.get('laning_10m') or {}).get('lh10') or 0)}刀/{int((p.get('laning_10m') or {}).get('gold10') or 0):,}金)"
                for p in dire_in_lane
            ) or "游走"

            lane_matchups.append({
                "lane_title": lane_names[lane_id],
                "radiant_heroes": rad_desc,
                "dire_heroes": dire_desc,
                "verdict": verdict,
                "diff_gold": diff,
            })

    objectives = match.get("objectives") or []
    rad_couriers_lost = 0
    dire_couriers_lost = 0
    roshan_events = []
    for obj in objectives:
        t = obj.get("time", 0)
        mm, ss = divmod(abs(int(t)), 60)
        t_str = f"{mm:02d}:{ss:02d}"
        otype = obj.get("type", "")
        if otype == "CHAT_MESSAGE_COURIER_LOST":
            if obj.get("team") == 2:
                rad_couriers_lost += 1
            elif obj.get("team") == 3:
                dire_couriers_lost += 1
        elif otype == "CHAT_MESSAGE_ROSHAN_KILL":
            killer = "天辉" if obj.get("team") == 2 else "夜魇"
            roshan_events.append(f"{t_str} {killer}控盾")

    g10_adv = gold_adv[10] if len(gold_adv) > 10 else 0
    g10_str = (
        f"10分钟对线期结束，{'天辉' if g10_adv >= 0 else '夜魇'}整体经济领先 {abs(g10_adv):,} 金。"
        if gold_adv
        else "双方完成前10分钟对线期博弈。"
    )
    courier_str = ""
    if rad_couriers_lost or dire_couriers_lost:
        courier_str = f" 对线与前中期信使击杀：天辉阵亡 {rad_couriers_lost} 只信使，夜魇阵亡 {dire_couriers_lost} 只信使。"

    is_parsed = bool(match.get("version"))
    if not is_parsed:
        my_team = radiant_players if user_team_side == "radiant" else (dire_players if user_team_side == "dire" else dire_players)
        enemy_team = dire_players if my_team is radiant_players else radiant_players
        my_side_zh = "天辉" if my_team is radiant_players else "夜魇"
        my_tdmg = sum(p.get("tower_damage", 0) for p in my_team)
        en_tdmg = sum(p.get("tower_damage", 0) for p in enemy_team)
        unp_stages = [
            {
                "title": "0–10分钟 对线期三路对账",
                "content": "需要先解析录像以获取对线期三路对账与信使记录。",
                "evidence": "measured",
                "source_fields": ["version"],
            },
            {
                "title": "10–25分钟 中期节奏与装备真空取证",
                "content": "需要先解析录像以获取中期经济差、开雾记录与装备成型时间。",
                "evidence": "inferred",
            },
            {
                "title": "25分钟至终局 决胜团战与肉山高地博弈",
                "content": f"最终{'天辉' if radiant_win else '夜魇'}在 {duration_min} 分钟推平遗迹终结比赛（团战与肉山细节需要先解析录像）。",
                "evidence": "measured",
                "source_fields": ["radiant_win", "duration", "version"],
            },
            {
                "title": "全局五人硬实力与团队执行力对比",
                "content": f"主视角（{my_side_zh}）车队全局数据对比：建筑伤害 {my_tdmg:,} vs 敌方 {en_tdmg:,}（控制时长、视野开雾、读秒时长需要先解析录像）。",
                "evidence": "inferred",
            },
        ]
        unp_conclusions: List[Dict[str, Any]] = []
        for stg in unp_stages:
            c_item: Dict[str, Any] = {
                "text": stg["content"],
                "kind": "stage_narrative",
                "evidence": stg["evidence"],
            }
            if stg["evidence"] == "measured" and stg.get("source_fields"):
                c_item["source_fields"] = list(stg["source_fields"])
            unp_conclusions.append(c_item)
        return {
            "evidence": "inferred",
            "conclusions": unp_conclusions,
            "lane_matchups": [],
            "roshan_events": [],
            "couriers_lost": {"radiant": None, "dire": None},
            "stages": unp_stages,
        }

    stage1 = f"{g10_str}{courier_str}"
    if lane_matchups:
        stage1 += " 三路10分钟对账：" + "；".join(
            f"{lm['lane_title']} [{lm['radiant_heroes']}] vs [{lm['dire_heroes']}] → {lm['verdict']}"
            for lm in lane_matchups
        ) + "。"

    g20_adv = gold_adv[min(20, len(gold_adv) - 1)] if len(gold_adv) > 12 else 0
    g25_adv = gold_adv[min(25, len(gold_adv) - 1)] if len(gold_adv) > 15 else g20_adv
    rad_smokes = sum(p.get("smokes_bought", 0) for p in radiant_players)
    dire_smokes = sum(p.get("smokes_bought", 0) for p in dire_players)
    stage2 = (
        f"20分钟时{'天辉' if g20_adv >= 0 else '夜魇'}经济领先 {abs(g20_adv):,} 金，"
        f"25分钟时{'天辉' if g25_adv >= 0 else '夜魇'}领先 {abs(g25_adv):,} 金。"
        f"全场天辉总计买雾 {rad_smokes} 次，夜魇买雾 {dire_smokes} 次。"
        f"中期谁出现 15 分钟以上的装备真空期、谁拖到30分钟后才摸出 BKB，在下方 1~5 号位时间轴与按键取证中一目了然。"
    )

    rosh_str = f"肉山争夺记录：{' → '.join(roshan_events)}。" if roshan_events else ""
    tf_str = ""
    if key_teamfights:
        top_tf = max(key_teamfights, key=lambda x: x.get("importance", 0))
        tf_str = f"全场最高权重胜负手团战爆发于 {top_tf['time_range']}（{top_tf['kills_trade']}，{top_tf['gold_swing']}，团战最高输出：{top_tf['top_damage_hero']}）。"
    is_comeback_nar = bool(economy_timeline.get("is_comeback"))
    comeback_str = (
        "本局出现超过 5,000 经济的逆转翻盘：优势方中期上高/抓人接连失误送出大波经验钱，劣势方核心顶住压力完成翻盘！"
        if is_comeback_nar
        else f"最终{'天辉' if radiant_win else '夜魇'}在 {duration_min} 分钟推平遗迹终结比赛。"
    )
    stage3 = f"{tf_str}{rosh_str}{comeback_str}"

    my_team = radiant_players if user_team_side == "radiant" else (dire_players if user_team_side == "dire" else dire_players)
    enemy_team = dire_players if my_team is radiant_players else radiant_players
    my_side_zh = "天辉" if my_team is radiant_players else "夜魇"
    my_wards = sum((p.get("obs_placed") or 0) + (p.get("sen_placed") or 0) for p in my_team)
    en_wards = sum((p.get("obs_placed") or 0) + (p.get("sen_placed") or 0) for p in enemy_team)
    my_stuns = sum(p.get("stuns_sec", 0) for p in my_team)
    en_stuns = sum(p.get("stuns_sec", 0) for p in enemy_team)
    my_tdmg = sum(p.get("tower_damage", 0) for p in my_team)
    en_tdmg = sum(p.get("tower_damage", 0) for p in enemy_team)
    my_dead = sum(p.get("dead_seconds", 0) for p in my_team)
    en_dead = sum(p.get("dead_seconds", 0) for p in enemy_team)

    stage4 = (
        f"主视角（{my_side_zh}）车队全局数据对比："
        f"① 控制时长：{my_stuns:.1f}秒 vs 敌方 {en_stuns:.1f}秒；"
        f"② 视野与开雾：插眼 {my_wards}颗（开雾 {sum(p.get('smokes_bought',0) for p in my_team)}次） vs 敌方插眼 {en_wards}颗（开雾 {sum(p.get('smokes_bought',0) for p in enemy_team)}次）；"
        f"③ 建筑伤害：{my_tdmg:,} vs 敌方 {en_tdmg:,}；"
        f"④ 全队泉水读秒总时长：{my_dead//60}分{my_dead%60:02d}秒 vs 敌方 {en_dead//60}分{en_dead%60:02d}秒。"
    )

    stage1_sf = ["radiant_gold_adv", "objectives", "players[].lane", "players[].lh_t", "players[].gold_t"]
    stage3_ev = "inferred" if is_comeback_nar else "measured"
    stage3_sf = ["teamfights", "objectives", "radiant_win", "duration"]
    parsed_stages: List[Dict[str, Any]] = [
        {"title": "0–10分钟 对线期三路对账", "content": stage1, "evidence": "measured", "source_fields": stage1_sf},
        {"title": "10–25分钟 中期节奏与装备真空取证", "content": stage2, "evidence": "inferred"},
        {
            "title": "25分钟至终局 决胜团战与肉山高地博弈",
            "content": stage3,
            "evidence": stage3_ev,
            **({"source_fields": stage3_sf} if stage3_ev == "measured" else {}),
        },
        {"title": "全局五人硬实力与团队执行力对比", "content": stage4, "evidence": "inferred"},
    ]
    nar_conclusions: List[Dict[str, Any]] = []
    for stg in parsed_stages:
        c_item = {
            "text": stg["content"],
            "kind": "stage_narrative",
            "evidence": stg["evidence"],
        }
        if stg["evidence"] == "measured" and stg.get("source_fields"):
            c_item["source_fields"] = list(stg["source_fields"])
        nar_conclusions.append(c_item)

    return {
        "evidence": "inferred",
        "conclusions": nar_conclusions,
        "lane_matchups": lane_matchups,
        "roshan_events": roshan_events,
        "couriers_lost": {"radiant": rad_couriers_lost, "dire": dire_couriers_lost},
        "stages": parsed_stages,
    }


def load_env_llm_config() -> Dict[str, str]:
    """从项目目录 .env.local、~/.env 或环境变量加载 XAI (Grok) / Gemini / OpenAI 配置（绝不向前端暴露密钥）"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    env_vars: Dict[str, str] = {}
    for candidate in [os.path.join(base_dir, ".env.local"), os.path.expanduser("~/.env")]:
        if os.path.exists(candidate):
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    for raw_line in f:
                        line = raw_line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        if line.startswith("export "):
                            line = line[7:].strip()
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k and v and k not in env_vars:
                            env_vars[k] = v
            except Exception:
                pass
    for k in ("XAI_API_KEY", "XAI_MODEL", "GROK_MODEL", "XAI_BASE_URL", "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_BASE_URL"):
        if os.environ.get(k):
            env_vars[k] = os.environ[k]

    gemini_key = env_vars.get("GEMINI_API_KEY") or env_vars.get("GOOGLE_API_KEY") or ""
    xai_key = env_vars.get("XAI_API_KEY") or ""

    if xai_key:
        raw_xai_model = env_vars.get("XAI_MODEL") or env_vars.get("GROK_MODEL") or "grok-4.20-0309-non-reasoning"
        if raw_xai_model in ("grok-4.7", "grok-4.6", "grok-4"):
            raw_xai_model = "grok-4.20-0309-non-reasoning"
        return {
            "provider": "xai",
            "api_key": xai_key,
            "xai_api_key": xai_key,
            "gemini_api_key": gemini_key,
            "model_name": raw_xai_model,
            "base_url": (env_vars.get("XAI_BASE_URL") or "https://api.x.ai/v1").rstrip("/"),
        }
    if gemini_key:
        return {
            "provider": "gemini",
            "api_key": gemini_key,
            "xai_api_key": xai_key,
            "gemini_api_key": gemini_key,
            "model_name": "gemini-3.8-flash",
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
        }
    if env_vars.get("OPENAI_API_KEY"):
        return {
            "provider": "openai",
            "api_key": env_vars["OPENAI_API_KEY"],
            "xai_api_key": xai_key,
            "gemini_api_key": gemini_key,
            "model_name": env_vars.get("OPENAI_MODEL") or "gpt-4.1",
            "base_url": (env_vars.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/"),
        }
    return {"provider": "", "api_key": "", "xai_api_key": "", "gemini_api_key": "", "model_name": "", "base_url": ""}


def get_llm_status_safe() -> Dict[str, Any]:
    """返回给前端展示的安全模型状态（不含任何密钥值）"""
    cfg = load_env_llm_config()
    has_gemini = bool(cfg.get("gemini_api_key"))
    has_xai = bool(cfg.get("xai_api_key"))
    if cfg.get("api_key"):
        return {
            "configured": True,
            "provider": cfg["provider"],
            "model": cfg["model_name"],
            "has_gemini_key": has_gemini,
            "has_xai_key": has_xai,
            "poster_engine": "gemini-nano-banana-2.1" if has_gemini else "grok-imagine-image-2.0",
            "label": f"已接入 {cfg['provider'].upper()} / {cfg['model_name']}",
        }
    return {
        "configured": False,
        "provider": "",
        "model": "",
        "has_gemini_key": has_gemini,
        "has_xai_key": has_xai,
        "poster_engine": "gemini-nano-banana-2.1" if has_gemini else "",
        "label": "内置录像取证引擎已就绪",
    }


def _parse_llm_json_robust(raw_txt: str) -> Optional[Dict[str, Any]]:
    """
    解析大模型返回的 JSON 字符串：
    - 拒绝截断的 JSON（如大括号/中括号未闭合或字符串未闭合），绝不硬补括号凑数；
    - 若字符串内部仅误用了未转义的英文双引号且整体结构完整闭合，替换为『』后解析。
    """
    if not raw_txt or not isinstance(raw_txt, str):
        return None
    txt = raw_txt.strip()
    if txt.startswith("```"):
        txt = txt.strip("`").strip()
        if txt.startswith("json"):
            txt = txt[4:].strip()
    if not txt.startswith("{") or not txt.endswith("}"):
        return None
    try:
        parsed = json.loads(txt)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass

    # State-machine repair ONLY for unescaped inner double quotes inside balanced JSON
    out_chars: List[str] = []
    in_str = False
    esc = False
    open_q = True
    brace_depth = 0
    bracket_depth = 0
    n = len(txt)
    for i, ch in enumerate(txt):
        if esc:
            out_chars.append(ch)
            esc = False
            continue
        if ch == "\\":
            out_chars.append(ch)
            esc = True
            continue
        if ch == '"':
            if not in_str:
                in_str = True
                out_chars.append(ch)
            else:
                j = i + 1
                while j < n and txt[j] in (" ", "\t", "\r", "\n"):
                    j += 1
                next_ch = txt[j] if j < n else ""
                if next_ch in (":", ",", "}", "]"):
                    in_str = False
                    out_chars.append(ch)
                else:
                    out_chars.append("『" if open_q else "』")
                    open_q = not open_q
            continue
        if not in_str:
            if ch == "{":
                brace_depth += 1
            elif ch == "}":
                brace_depth -= 1
            elif ch == "[":
                bracket_depth += 1
            elif ch == "]":
                bracket_depth -= 1
        if in_str and ch in ("\n", "\r"):
            out_chars.append(" ")
            continue
        out_chars.append(ch)

    if in_str or brace_depth != 0 or bracket_depth != 0:
        return None

    repaired = "".join(out_chars)
    try:
        parsed = json.loads(repaired)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _is_valid_number_in_range(val: Any, lo: float = 0.0, hi: float = 100.0) -> bool:
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        return False
    return lo <= float(val) <= hi


def _validate_mvp_consistency(
    structured: Dict[str, Any],
    own_team: Optional[List[Dict[str, Any]]] = None,
    rankings: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[bool, str]:
    """
    校验 mvp.slot 与最高分选手、以及 mvp.reason 中提及的位置/英雄名是否一致。
    不一致时直接判为无效（严禁事后强行篡改 mvp.slot 却保留旧的 mvp.reason）。
    """
    mvp = structured.get("mvp")
    if not isinstance(mvp, dict) or isinstance(mvp.get("slot"), bool) or not isinstance(mvp.get("slot"), int):
        return False, "mvp.slot 必须为整数"
    reason = mvp.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        return False, "mvp.reason 必须为非空字符串"

    mvp_slot = int(mvp["slot"])
    own_by_pos: Dict[int, Dict[str, Any]] = {}
    own_by_slot: Dict[int, Dict[str, Any]] = {}
    for p in (own_team or []):
        if not isinstance(p, dict):
            continue
        pos_v = int(p.get("pos") or 0)
        if pos_v in (1, 2, 3, 4, 5):
            own_by_pos[pos_v] = p
        if isinstance(p.get("player_slot"), int) and not isinstance(p.get("player_slot"), bool):
            own_by_slot[int(p["player_slot"])] = p

    cand_list = rankings if isinstance(rankings, list) and rankings else (structured.get("players") or [])
    rk_by_pos: Dict[int, Dict[str, Any]] = {}
    rk_by_slot: Dict[int, Dict[str, Any]] = {}
    for rk in cand_list:
        if not isinstance(rk, dict):
            continue
        pos_v = rk.get("pos")
        if not isinstance(pos_v, bool) and isinstance(pos_v, int) and pos_v in (1, 2, 3, 4, 5):
            rk_by_pos[pos_v] = rk
        sl_v = rk.get("slot")
        if not isinstance(sl_v, bool) and isinstance(sl_v, int):
            rk_by_slot[sl_v] = rk

    mvp_pos: Optional[int] = None
    if mvp_slot in own_by_slot:
        mvp_pos = int(own_by_slot[mvp_slot].get("pos") or 0) or None
    elif mvp_slot in rk_by_slot:
        p_v = rk_by_slot[mvp_slot].get("pos")
        if not isinstance(p_v, bool) and isinstance(p_v, int) and p_v in (1, 2, 3, 4, 5):
            mvp_pos = p_v

    if (own_by_pos or rk_by_pos) and mvp_pos is None:
        return False, f"mvp.slot ({mvp_slot}) 无法对应本方 1..5 号位任何选手"

    scored_pos: List[Tuple[int, float]] = []
    for pos_k, rk in rk_by_pos.items():
        sc = rk.get("grok_score")
        if _is_valid_number_in_range(sc, 0, 100):
            scored_pos.append((pos_k, float(sc)))
    if scored_pos and mvp_pos is not None:
        max_sc = max(sc for _, sc in scored_pos)
        top_positions = {pos_k for pos_k, sc in scored_pos if sc == max_sc}
        if mvp_pos not in top_positions:
            return False, f"mvp 对应 {mvp_pos}号位，但最高 grok_score 属于 {sorted(top_positions)}号位"

    if mvp_pos is not None:
        pos_mentions = [int(m.group(1)) for m in re.finditer(r"([1-5])\s*号位", reason)]
        if pos_mentions and (mvp_pos not in pos_mentions or pos_mentions[0] != mvp_pos):
            return False, f"mvp.reason 提及 {pos_mentions}号位，与 mvp.slot ({mvp_pos}号位) 不一致"

        team_heroes: List[Tuple[int, str]] = []
        for pos_k in (1, 2, 3, 4, 5):
            h_name = ""
            if pos_k in own_by_pos:
                h_name = str(own_by_pos[pos_k].get("hero_short_zh") or own_by_pos[pos_k].get("hero_name") or "").strip()
            if not h_name and pos_k in rk_by_pos:
                h_name = str(rk_by_pos[pos_k].get("hero") or "").strip()
            if h_name and h_name != "测试英雄":
                team_heroes.append((pos_k, h_name))

        mentioned_heroes = [(pos_k, h_name) for pos_k, h_name in team_heroes if h_name in reason]
        if mentioned_heroes:
            if all(pos_k != mvp_pos for pos_k, _ in mentioned_heroes):
                return False, f"mvp.reason 提及英雄 {[h for _, h in mentioned_heroes]}，与 mvp.slot ({mvp_pos}号位) 不一致"
            first_hero_pos = min(mentioned_heroes, key=lambda x: reason.find(x[1]))[0]
            if first_hero_pos != mvp_pos:
                return False, f"mvp.reason 首选英雄为 {first_hero_pos}号位，与 mvp.slot ({mvp_pos}号位) 不一致"

    return True, ""


def validate_coaching_schema(
    structured: Any,
    partial_mode: Optional[str] = None,
    own_team: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[bool, str]:
    """
    标准库结构校验函数：检查必填字段、类型及分数/占比范围 (0..100)，并核验 MVP 一致性。
    """
    if not isinstance(structured, dict):
        return False, "根对象不是字典"

    if partial_mode == "player":
        pls = structured.get("players")
        if isinstance(pls, list) and len(pls) >= 1 and isinstance(pls[0], dict):
            gp = pls[0]
        elif structured.get("hero") or structured.get("deep_verdict"):
            gp = structured
        else:
            return False, "个人分片缺少 players 列表"
        if not isinstance(gp.get("headline"), str) or not gp.get("headline", "").strip():
            return False, "个人分片缺少非空 headline"
        dv = gp.get("deep_verdict") or gp.get("assessment")
        if not isinstance(dv, str) or not dv.strip():
            return False, "个人分片缺少非空 deep_verdict"
        if gp.get("grok_score") is not None and not _is_valid_number_in_range(gp.get("grok_score"), 0, 100):
            return False, f"个人分片 grok_score 超出 0..100 范围: {gp.get('grok_score')}"
        if gp.get("grok_share_pct") is not None and not _is_valid_number_in_range(gp.get("grok_share_pct"), 0, 100):
            return False, f"个人分片 grok_share_pct 超出 0..100 范围: {gp.get('grok_share_pct')}"
        return True, ""

    for req_str_key in ("title", "summary", "verdict", "team_practice"):
        val = structured.get(req_str_key)
        if not isinstance(val, str) or not val.strip():
            return False, f"缺少必填字符串字段: {req_str_key}"

    sr = structured.get("stage_reviews")
    if not isinstance(sr, dict):
        return False, "缺少 stage_reviews 字典"
    for sr_key in ("early_lanes", "mid_tempo", "late_and_roshan", "overall_verdict"):
        if not isinstance(sr.get(sr_key), str) or not sr.get(sr_key, "").strip():
            return False, f"stage_reviews.{sr_key} 必须为非空字符串"

    if partial_mode == "global":
        rk_list = structured.get("player_rankings") or structured.get("players") or []
        if not isinstance(rk_list, list) or len(rk_list) < 5:
            return False, f"全局排名不足 5 条（当前 {len(rk_list) if isinstance(rk_list, list) else 0} 条）"
        seen_rk_pos = set()
        for rk in rk_list[:5]:
            if not isinstance(rk, dict):
                return False, "player_rankings 元素必须为字典"
            rk_pos = rk.get("pos")
            if isinstance(rk_pos, bool) or not isinstance(rk_pos, int) or rk_pos not in (1, 2, 3, 4, 5):
                return False, f"player_rankings pos 必须为 1..5 整数: {rk_pos}"
            seen_rk_pos.add(rk_pos)
            if not _is_valid_number_in_range(rk.get("grok_score"), 0, 100):
                return False, f"player_rankings grok_score 超出 0..100: {rk.get('grok_score')}"
            if not _is_valid_number_in_range(rk.get("grok_share_pct"), 0, 100):
                return False, f"player_rankings grok_share_pct 超出 0..100: {rk.get('grok_share_pct')}"
        if len(seen_rk_pos) != 5:
            return False, f"player_rankings 必须完整覆盖 1..5 号位，当前为: {sorted(seen_rk_pos)}"
        mvp_ok, mvp_err = _validate_mvp_consistency(structured, own_team=own_team, rankings=rk_list[:5])
        if not mvp_ok:
            return False, mvp_err
        return True, ""

    pls = structured.get("players")
    if not isinstance(pls, list) or len(pls) != 5:
        return False, "players 必须为包含 5 名选手的数组"

    seen_pos = set()
    for gp in pls:
        if not isinstance(gp, dict):
            return False, "players 元素必须为字典"
        pos_val = gp.get("pos")
        if isinstance(pos_val, bool) or not isinstance(pos_val, int) or pos_val not in (1, 2, 3, 4, 5):
            return False, f"选手 pos 必须为 1..5 整数: {pos_val}"
        seen_pos.add(pos_val)
        if not isinstance(gp.get("hero"), str) or not gp.get("hero", "").strip():
            return False, f"{pos_val}号位缺少非空 hero 字段"
        if not _is_valid_number_in_range(gp.get("grok_score"), 0, 100):
            return False, f"{pos_val}号位 grok_score 必须在 0..100 范围内: {gp.get('grok_score')}"
        if not _is_valid_number_in_range(gp.get("grok_share_pct"), 0, 100):
            return False, f"{pos_val}号位 grok_share_pct 必须在 0..100 范围内: {gp.get('grok_share_pct')}"
        if not isinstance(gp.get("headline"), str) or not gp.get("headline", "").strip():
            return False, f"{pos_val}号位缺少非空 headline"
        dv = gp.get("deep_verdict") or gp.get("assessment")
        if not isinstance(dv, str) or not dv.strip():
            return False, f"{pos_val}号位缺少非空 deep_verdict"

    if len(seen_pos) != 5:
        return False, f"players 必须完整覆盖 1..5 号位，当前为: {sorted(seen_pos)}"

    mvp_ok, mvp_err = _validate_mvp_consistency(structured, own_team=own_team, rankings=pls)
    if not mvp_ok:
        return False, mvp_err

    return True, ""


def _collect_ground_truth_tokens(
    report: Dict[str, Any], input_payload: Optional[Dict[str, Any]] = None
) -> Tuple[set, set]:
    """
    合法时间点严格只来自事件时间线（击杀、阵亡、购买、团战起止、目标），允许 ±5 秒；
    四位以上整数集合继续从比赛报告和输入 payload 中提取。
    """
    valid_time_secs: set = set()
    valid_big_nums: set = set()

    def _add_event_sec(sec_val: Any) -> None:
        if isinstance(sec_val, bool) or not isinstance(sec_val, (int, float)):
            return
        total_s = int(round(float(sec_val)))
        if 0 <= total_s <= 10800:
            for delta in range(-5, 6):
                if total_s + delta >= 0:
                    valid_time_secs.add(total_s + delta)

    def _add_event_time_str(val: Any) -> None:
        if not isinstance(val, str) or not val:
            return
        for m_ts in re.finditer(r"(?<!\d)(\d{1,3}):(\d{2})(?!\d)", val):
            m_int, s_int = int(m_ts.group(1)), int(m_ts.group(2))
            if 0 <= m_int <= 180 and 0 <= s_int < 60:
                _add_event_sec(m_int * 60 + s_int)
        for m_zh in re.finditer(r"(\d{1,3})分(\d{1,2})秒", val):
            m_int, s_int = int(m_zh.group(1)), int(m_zh.group(2))
            if 0 <= m_int <= 180 and 0 <= s_int < 60:
                _add_event_sec(m_int * 60 + s_int)

    def _extract_event_timelines(rep_obj: Dict[str, Any]) -> None:
        if not isinstance(rep_obj, dict):
            return
        # 1. 阶段流水：击杀、阵亡、购买、阶段关键事件
        raw_phases = rep_obj.get("phases_data") or []
        phases_iter = raw_phases if isinstance(raw_phases, list) else list(raw_phases.values())
        for pd in phases_iter:
            if not isinstance(pd, dict):
                continue
            for ev in (pd.get("events") or []):
                if isinstance(ev, dict):
                    _add_event_sec(ev.get("time_sec") if ev.get("time_sec") is not None else ev.get("time"))
                    _add_event_time_str(ev.get("time_str"))
                else:
                    _add_event_time_str(ev)
            for pl in (pd.get("players") or []):
                if not isinstance(pl, dict):
                    continue
                for ke in (pl.get("kills_events") or []):
                    if isinstance(ke, dict):
                        _add_event_sec(ke.get("time_sec") if ke.get("time_sec") is not None else ke.get("time"))
                        _add_event_time_str(ke.get("time_str"))
                    else:
                        _add_event_time_str(ke)
                for de in (pl.get("deaths_events") or []):
                    if isinstance(de, dict):
                        _add_event_sec(de.get("time_sec") if de.get("time_sec") is not None else de.get("time"))
                        _add_event_time_str(de.get("time_str"))
                    else:
                        _add_event_time_str(de)
                for it in (pl.get("items_bought") or []):
                    if isinstance(it, dict):
                        _add_event_sec(it.get("time_sec") if it.get("time_sec") is not None else it.get("time"))
                        _add_event_time_str(it.get("time_str"))
                    else:
                        _add_event_time_str(it)

        # 2. 选手关键装备购买时间轴
        for side_k in ("radiant_pos_1_to_5", "dire_pos_1_to_5"):
            for p in (rep_obj.get(side_k) or []):
                if not isinstance(p, dict):
                    continue
                for kt in (p.get("key_item_timings") or []):
                    _add_event_time_str(kt)
                for ktr in (p.get("key_item_timings_rich") or []):
                    if isinstance(ktr, dict):
                        _add_event_sec(ktr.get("time_sec") if ktr.get("time_sec") is not None else ktr.get("time"))
                        _add_event_time_str(ktr.get("time_str"))

        # 3. 团战起止时间
        for tf in (rep_obj.get("key_teamfights") or []):
            if isinstance(tf, dict):
                _add_event_sec(tf.get("start_sec"))
                _add_event_sec(tf.get("end_sec"))
                _add_event_time_str(tf.get("start_str"))
                _add_event_time_str(tf.get("end_str"))
                _add_event_time_str(tf.get("time_range"))
                _add_event_time_str(tf.get("time"))

        df = rep_obj.get("deep_forensics") or {}
        if isinstance(df, dict):
            for tf in (df.get("teamfight_forensics") or []):
                if isinstance(tf, dict):
                    _add_event_sec(tf.get("start_sec"))
                    _add_event_sec(tf.get("end_sec"))
                    _add_event_time_str(tf.get("time_range"))
            for side_ms in (df.get("map_space_by_side") or {}).values():
                if isinstance(side_ms, dict):
                    for sev in (side_ms.get("solo_pickoff_events") or []):
                        if isinstance(sev, dict):
                            _add_event_sec(sev.get("time_sec") if sev.get("time_sec") is not None else sev.get("time"))
                            _add_event_time_str(sev.get("time_str"))
            for side_mo in (df.get("macro_objectives_by_side") or {}).values():
                if isinstance(side_mo, dict):
                    for rev in (side_mo.get("roshan_events") or []):
                        if isinstance(rev, dict):
                            _add_event_sec(rev.get("time_sec") if rev.get("time_sec") is not None else rev.get("time"))
                            _add_event_time_str(rev.get("time_str"))
                        else:
                            _add_event_time_str(rev)

        # 4. 地图目标时间线（防御塔、兵营、肉山、魔方）与关键录像节点
        for list_k in ("objective_markers", "roshan_and_tower_timeline", "top3_replay_moments"):
            for item in (rep_obj.get(list_k) or []):
                if isinstance(item, dict):
                    _add_event_sec(item.get("time_sec") if item.get("time_sec") is not None else item.get("time"))
                    _add_event_time_str(item.get("time_str"))

    def _extract_payload_event_timelines(payload_obj: Dict[str, Any]) -> None:
        if not isinstance(payload_obj, dict):
            return
        for pb in (payload_obj.get("phases_breakdown") or []):
            if not isinstance(pb, dict):
                continue
            for pl in (pb.get("own_players") or []):
                if not isinstance(pl, dict):
                    continue
                for lst_k in ("items_bought", "kills_events", "deaths_events"):
                    for s_ev in (pl.get(lst_k) or []):
                        _add_event_time_str(s_ev)
        for tf in (payload_obj.get("key_teamfights") or []):
            if isinstance(tf, dict):
                _add_event_time_str(tf.get("time"))
        for p in (payload_obj.get("own_team") or []):
            if isinstance(p, dict):
                for kt in (p.get("key_item_timings") or []):
                    _add_event_time_str(kt)
        mo = payload_obj.get("macro_objectives") or {}
        if isinstance(mo, dict):
            for rev in (mo.get("roshan_events") or []):
                if isinstance(rev, dict):
                    _add_event_sec(rev.get("time_sec") if rev.get("time_sec") is not None else rev.get("time"))
                    _add_event_time_str(rev.get("time_str"))
                else:
                    _add_event_time_str(rev)

    def _add_num(n_val: int) -> None:
        if abs(n_val) >= 1000:
            valid_big_nums.add(abs(n_val))

    def _walk_numbers(obj: Any) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "grok_coaching":
                    continue
                _walk_numbers(v)
        elif isinstance(obj, list):
            for item in obj:
                _walk_numbers(item)
        elif isinstance(obj, bool):
            return
        elif isinstance(obj, int):
            _add_num(obj)
        elif isinstance(obj, float):
            _add_num(int(round(obj)))
            _add_num(int(obj))
        elif isinstance(obj, str):
            for m_num in re.finditer(r"(?<![:\d])\b\d{1,3}(?:,\d{3})+\b|(?<![:\d])\b\d{4,}\b", obj):
                raw_n = m_num.group(0).replace(",", "")
                if raw_n.isdigit():
                    _add_num(int(raw_n))

    _extract_event_timelines(report)
    _walk_numbers(report)
    if input_payload:
        _extract_payload_event_timelines(input_payload)
        _walk_numbers(input_payload)
    return valid_time_secs, valid_big_nums


def fact_check_coaching_output(
    structured: Dict[str, Any],
    report: Dict[str, Any],
    input_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    抽取判词里的 mm:ss 时间点和四位以上数字，与比赛输入数据比对；
    对不上的句子删掉，并把核查统计记入 structured['fact_check_audit']。
    """
    valid_time_secs, valid_big_nums = _collect_ground_truth_tokens(report, input_payload)
    verified_count = 0
    removed_count = 0
    removed_sentences: List[Dict[str, Any]] = []

    def _check_sentence(sent: str) -> Tuple[bool, bool, List[str]]:
        """返回 (has_fact_tokens, is_valid, bad_tokens)"""
        ts_matches = list(re.finditer(r"(?<!\d)(\d{1,3}):(\d{2})(?!\d)", sent))
        zh_ts_matches = list(re.finditer(r"(\d{1,3})分(\d{1,2})秒", sent))
        # Mask out timestamps before extracting 4+ digit numbers
        masked = re.sub(r"(?<!\d)\d{1,3}:\d{2}(?!\d)", " ", sent)
        masked = re.sub(r"\d{1,3}分\d{1,2}秒", " ", masked)
        num_matches = list(
            re.finditer(r"(?<![:\d.])\b\d{1,3}(?:,\d{3})+\b|(?<![:\d.])\b\d{4,}\b", masked)
        )

        if not ts_matches and not zh_ts_matches and not num_matches:
            return False, True, []

        bad_tokens: List[str] = []
        for m in ts_matches:
            mm, ss = int(m.group(1)), int(m.group(2))
            if (mm * 60 + ss) not in valid_time_secs:
                bad_tokens.append(m.group(0))
        for m in zh_ts_matches:
            mm, ss = int(m.group(1)), int(m.group(2))
            if (mm * 60 + ss) not in valid_time_secs:
                bad_tokens.append(m.group(0))
        for m in num_matches:
            raw_n = m.group(0).replace(",", "")
            if raw_n.isdigit() and int(raw_n) not in valid_big_nums:
                bad_tokens.append(m.group(0))

        return True, len(bad_tokens) == 0, bad_tokens

    def _filter_text(text: Any, field_label: str) -> str:
        nonlocal verified_count, removed_count
        if not isinstance(text, str) or not text.strip():
            return "" if not isinstance(text, str) else text
        parts = re.split(r"(?<=[。！？!?；;\n])", text)
        kept: List[str] = []
        for part in parts:
            if not part.strip():
                continue
            has_tokens, is_ok, bad_toks = _check_sentence(part)
            if not has_tokens:
                kept.append(part)
            elif is_ok:
                verified_count += 1
                kept.append(part)
            else:
                removed_count += 1
                removed_sentences.append({
                    "field": field_label,
                    "sentence": part.strip(),
                    "unmatched": bad_toks,
                })
        result = "".join(kept).strip()
        return result if result else "（相关具体时间或数值未通过事实核查已略去）"

    def _filter_list(items: Any, field_label: str) -> List[str]:
        nonlocal verified_count, removed_count
        if not isinstance(items, list):
            return []
        out_items: List[str] = []
        for item in items:
            if not isinstance(item, str) or not item.strip():
                continue
            has_tokens, is_ok, bad_toks = _check_sentence(item)
            if not has_tokens:
                out_items.append(item)
            elif is_ok:
                verified_count += 1
                out_items.append(item)
            else:
                removed_count += 1
                removed_sentences.append({
                    "field": field_label,
                    "sentence": item.strip(),
                    "unmatched": bad_toks,
                })
        return out_items

    for top_k in ("title", "summary", "verdict", "team_practice"):
        if isinstance(structured.get(top_k), str):
            structured[top_k] = _filter_text(structured[top_k], top_k)

    sr = structured.get("stage_reviews")
    if isinstance(sr, dict):
        for sr_k in ("early_lanes", "mid_tempo", "late_and_roshan", "overall_verdict"):
            if isinstance(sr.get(sr_k), str):
                sr[sr_k] = _filter_text(sr[sr_k], f"stage_reviews.{sr_k}")

    mvp = structured.get("mvp")
    if isinstance(mvp, dict):
        for m_k in ("reason", "comparison"):
            if isinstance(mvp.get(m_k), str):
                mvp[m_k] = _filter_text(mvp[m_k], f"mvp.{m_k}")
        if isinstance(mvp.get("evidence"), list):
            mvp["evidence"] = _filter_list(mvp["evidence"], "mvp.evidence")

    if isinstance(structured.get("windows"), list):
        for idx_w, win in enumerate(structured["windows"]):
            if isinstance(win, dict):
                for w_k in ("title", "detail"):
                    if isinstance(win.get(w_k), str):
                        win[w_k] = _filter_text(win[w_k], f"windows[{idx_w}].{w_k}")

    for gp in (structured.get("players") or []):
        if not isinstance(gp, dict):
            continue
        pos_tag = f"pos_{gp.get('pos')}"
        for p_k in ("headline", "deep_verdict", "early_story", "mid_story", "late_story", "item_and_blink_audit", "practice"):
            if isinstance(gp.get(p_k), str):
                gp[p_k] = _filter_text(gp[p_k], f"{pos_tag}.{p_k}")
        if gp.get("deep_verdict"):
            gp["assessment"] = gp["deep_verdict"]
        for l_k in ("good", "bad"):
            if isinstance(gp.get(l_k), list):
                gp[l_k] = _filter_list(gp[l_k], f"{pos_tag}.{l_k}")

    audit = {
        "checked_sentences": verified_count + removed_count,
        "verified_count": verified_count,
        "removed_count": removed_count,
        "removed_sentences": removed_sentences[:20],
    }
    structured["fact_check_audit"] = audit
    report["fact_check_audit"] = audit
    return audit


def _compute_player_role_duty_audit(
    p: Dict[str, Any],
    own_team: List[Dict[str, Any]],
    opp_team: List[Dict[str, Any]],
    df: Dict[str, Any],
    focus_side: str,
) -> Dict[str, Any]:
    """
    为 1~5 号位每位选手计算【位置本职工作契约与毒瘤/抢钱/假辅助玩法审计 (role_duty_audit)】，
    直接注入给大模型，让 AI 深度思考该选手是否执行了对应位置的本职工作（如 4 号位是否保 3 号位、
    是否带节奏、是否没钱还裸憋散失/BKB 等纯大哥装并自己打钱抢经济送人头）。
    """
    pos = int(p.get("pos") or 1)
    hero = str(p.get("hero_short_zh") or "")
    key_timings = [str(x) for x in (p.get("key_item_timings") or [])]
    final_items = [str(x) for x in (p.get("final_items") or [])]
    all_items_str = " | ".join(key_timings + final_items)

    team_utility_keywords = (
        "原力法杖", "推推", "飓风长戟", "微光披风", "闪烁匕首", "跳刀",
        "阿托斯", "缚灵索", "风杖", "神圣法杖", "风之杖", "魂之灵瓮", "大骨灰",
        "影之灵龛", "骨灰", "清莲宝珠", "莲花", "洞察烟斗", "笛子", "赤红甲",
        "梅肯", "卫士胫甲", "祭品", "邪恶镰刀", "羊刀", "阿哈利姆魔晶", "以太之镜",
        "幽魂权杖", "绿杖",
    )
    selfish_core_keywords = (
        "净魂之刃", "散失", "散魂剑", "迈达斯之手", "点金手", "漩涡", "小电锤",
        "雷神之锤", "大电锤", "狂战斧", "辉耀", "代达罗斯", "大炮", "水晶剑",
        "金箍棒", "蝴蝶", "撒旦", "影刃", "隐刀", "白银之锋", "大隐刀",
        "暗灭", "莫尔迪基安", "臂章", "疯狂面具", "分身斧", "幻影斧", "黑皇杖", "BKB",
        "绝刃", "大灵匣",
    )

    built_utility = [kw for kw in team_utility_keywords if kw in all_items_str]
    built_selfish = [kw for kw in selfish_core_keywords if kw in all_items_str]

    laning_10m = p.get("laning_10m") or {}
    lh10 = int(laning_10m.get("lh10") or 0)
    total_lh = int(p.get("last_hits") or 0)
    post_10m_lh = max(0, total_lh - lh10)
    hdmg_share = float(p.get("hero_damage_share_pct") or 0.0)
    tdmg = int(p.get("tower_damage") or 0)
    kp_pct = float(p.get("kill_participation_pct") or 0.0)
    obs = int(p.get("obs_placed") or 0)
    sen = int(p.get("sen_placed") or 0)

    ms = ((df.get("map_space_by_side") or {}).get(focus_side)) or {}
    solo_events = [
        ev for ev in (ms.get("solo_pickoff_events") or [])
        if int(ev.get("pos") or 0) == pos or ev.get("hero_short_zh") == hero
    ]
    solo_cnt = len(solo_events)

    pos3_ally = next((x for x in own_team if int(x.get("pos") or 0) == 3), None)
    pos1_ally = next((x for x in own_team if int(x.get("pos") or 0) == 1), None)
    pos4_ally = next((x for x in own_team if int(x.get("pos") or 0) == 4), None)

    role_contract = ""
    duty_verdict = ""
    is_toxic_fake_support = False

    if pos == 4:
        pos3_name = pos3_ally.get("hero_short_zh") if pos3_ally else "3号位"
        role_contract = (
            f"4号位（游走辅助）：前期协助3号位（{pos3_name}）劣势路对线、拉野控符，"
            f"中后期围绕3号位和2号位游走控图，评估团队控制与救人装配置。"
        )
        duty_verdict = (
            f"【4号位履职数据】：搭档3号位（{pos3_name}），关键出装时间（{', '.join(key_timings)}），"
            f"团队功能装（{', '.join(built_utility) or '无'}），输出核心装（{', '.join(built_selfish) or '无'}），"
            f"10m后补刀 +{post_10m_lh} 刀，团战外阵亡 {solo_cnt} 次，参战率 {kp_pct}%，伤害占比 {hdmg_share}%，建筑伤害 {tdmg}。"
        )
    elif pos == 5:
        pos1_name = pos1_ally.get("hero_short_zh") if pos1_ally else "1号位"
        role_contract = (
            f"5号位（保核辅助）：前期拉野封野保护1号位（{pos1_name}）发育，"
            f"中后期负责视野铺设与救人控制装。"
        )
        duty_verdict = (
            f"【5号位履职数据】：搭档1号位（{pos1_name}），全场 {obs}假眼/{sen}真眼，10m后补刀 +{post_10m_lh} 刀，"
            f"关键出装（{', '.join(key_timings)}），团队功能装（{', '.join(built_utility) or '无'}），参战率 {kp_pct}%。"
        )
    elif pos == 3:
        pos4_name = pos4_ally.get("hero_short_zh") if pos4_ally else "4号位"
        pa_audit = p.get("playstyle_archetype_audit") or build_player_playstyle_and_build_forensics(p, own_team, opp_team, 35.0, True)
        role_contract = (
            "3号位（劣势路先手与前排核心）：劣势路抗压发育，中期承担先手控制或团战支点职责。"
        )
        duty_verdict = (
            f"【3号位履职数据】：搭档4号位（{pos4_name}），流派【{pa_audit.get('archetype_badge')}】，"
            f"出装链（{pa_audit.get('full_item_progression_zh')}），"
            f"参战率 {kp_pct}%、伤害占比 {hdmg_share}%、推塔 {tdmg}、团战外阵亡 {solo_cnt} 次。"
        )
    elif pos == 2:
        role_contract = (
            "2号位（中单节奏与输出核心）：对线稳住或压制敌方中单，中期带队节奏与团战爆发。"
        )
        duty_verdict = (
            f"【2号位履职数据】：10m补刀 {lh10} 刀，全场参战率 {kp_pct}%、英雄伤害占比 {hdmg_share}%、建筑伤害 {tdmg}，"
            f"出装（{', '.join(key_timings)}），团战外阵亡 {solo_cnt} 次。"
        )
    else:
        role_contract = (
            "1号位（优势路后期核心）：前期补刀发育，中后期刷出关键装接管团战与推塔。"
        )
        duty_verdict = (
            f"【1号位履职数据】：总补刀 {total_lh} 刀、GPM {p.get('gpm')}，参战率 {kp_pct}%、英雄伤害占比 {hdmg_share}%、建筑伤害 {tdmg}，"
            f"出装（{', '.join(key_timings)}），团战外阵亡 {solo_cnt} 次。"
        )

    dossier = (
        p.get("hero_matchup_dossier")
        or (p.get("hero_mechanism_profile") or {}).get("hero_matchup_dossier")
        or build_hero_matchup_dossier(p, own_team, opp_team, 35.0, True)
    )
    pa_full = p.get("playstyle_archetype_audit") or build_player_playstyle_and_build_forensics(p, own_team, opp_team, 35.0, True)

    return {
        "pos": pos,
        "hero_pos_role_title": dossier.get("pos_role_title"),
        "role_contract": role_contract,
        "post_10m_lh_farmed": post_10m_lh,
        "solo_pickoffs_count": solo_cnt,
        "built_team_utility_items": built_utility,
        "built_selfish_core_items": built_selfish,
        "duty_verdict": duty_verdict,
        "playstyle_archetype_badge": pa_full.get("archetype_badge"),
        "full_item_progression_zh": pa_full.get("full_item_progression_zh"),
        "skill_and_talent_audit_zh": pa_full.get("skill_and_talent_audit_zh"),
        "neutral_and_enchantment_audit_zh": pa_full.get("neutral_and_enchantment_audit_zh"),
    }


def call_llm_coach_review(
    report: Dict[str, Any],
    api_key: Optional[str] = None,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    base_url: Optional[str] = None,
    tone_mode: str = "coach",
) -> Dict[str, Any]:
    """
    调用外部大模型 API（默认优先使用 .env.local 中的 xAI Grok grok-4.7，亦支持 Gemini gemini-3.8-flash / OpenAI）
    生成结构化赛后算账 JSON 并持久化到 reports/coaching-{match_id}-{side}.json。
    """
    env_cfg = load_env_llm_config()
    key = (env_cfg.get("api_key") or "").strip()
    prov = (env_cfg.get("provider") or "xai").strip().lower()
    model = (env_cfg.get("model_name") or "grok-4.20-0309-non-reasoning").strip()
    b_url = (env_cfg.get("base_url") or "https://api.x.ai/v1").strip()

    if prov in ("grok", "x.ai"):
        prov = "xai"
    if prov == "xai" and (not b_url or "openai.com" in b_url):
        b_url = "https://api.x.ai/v1"
    if prov == "xai" and ("gemini" in model or not model):
        model = env_cfg.get("model_name") or "grok-4.20-0309-non-reasoning"
    if prov == "xai" and model in ("grok-4.7", "grok-4.6", "grok-4"):
        model = "grok-4.20-0309-non-reasoning"

    if not key:
        return {
            "ok": False,
            "error": "服务端尚未配置大模型密钥。",
        }

    raw_side = report.get("focus_side") or report.get("user_team_side") or ("radiant" if report.get("radiant_win") else "dire")
    focus_side = "radiant" if raw_side in ("radiant", "天辉") else "dire"
    own_team = report.get("radiant_pos_1_to_5", []) if focus_side == "radiant" else report.get("dire_pos_1_to_5", [])
    opp_team = report.get("dire_pos_1_to_5", []) if focus_side == "radiant" else report.get("radiant_pos_1_to_5", [])
    df = report.get("deep_forensics") or {}
    raw_phases = report.get("phases_data") or []
    phases_list = raw_phases if isinstance(raw_phases, list) else list(raw_phases.values())
    phases_compact = []
    for pd in phases_list:
        if not isinstance(pd, dict):
            continue
        p_own = [
            {
                "pos": x.get("pos"),
                "hero": x.get("hero_short_zh"),
                "k": x.get("kills_count"),
                "d": x.get("deaths_count"),
                "gold_gain": x.get("gold_gain"),
                "lh_gain": x.get("lh_gain"),
                "dn_gain": x.get("dn_gain"),
                "hero_dmg_gain": x.get("hero_damage_gain"),
                "tower_dmg_gain": x.get("tower_damage_gain"),
                "items_bought": [
                    f"{it.get('zh_name') or it.get('key')}({it.get('time_str')})"
                    for it in (x.get("items_bought") or [])
                ],
                "kills_events": [
                    f"{ke.get('time_str')}杀{ke.get('victim_hero')}"
                    for ke in (x.get("kills_events") or [])[:6]
                ],
                "deaths_events": [
                    f"{de.get('time_str')}被{de.get('killer')}杀(读秒{de.get('time_dead')}s)"
                    for de in (x.get("deaths_events") or [])[:6]
                ],
            }
            for x in (pd.get("players") or [])
            if x.get("side") == focus_side
        ]
        phases_compact.append({
            "key": pd.get("key"),
            "label": pd.get("label"),
            "window": pd.get("window"),
            "team_summary": pd.get("team_summary"),
            "own_players": p_own,
        })

    nickname_map: Dict[str, str] = {}
    for _p_side in (report.get("radiant_pos_1_to_5") or []) + (report.get("dire_pos_1_to_5") or []):
        if isinstance(_p_side, dict):
            _pname = (_p_side.get("personaname") or "").strip()
            if _pname and len(_pname) >= 2:
                _hzh = _p_side.get("hero_short_zh") or _p_side.get("hero_name") or "选手"
                _pos = _p_side.get("pos") or ""
                nickname_map[_pname] = f"{_pos}号位{_hzh}" if _pos else str(_hzh)

    def _sanitize_for_llm(val: Any) -> Any:
        if isinstance(val, dict):
            cleaned = {}
            for k, v in val.items():
                if k in (
                    "personaname",
                    "player",
                    "player_name",
                    "name",
                    "avatar",
                    "img",
                    "icon",
                    "hero_img",
                    "item_img",
                    "economy_timeline",
                    "roshan_and_tower_timeline",
                    "phoenix_egg_audit",
                    "slark_mechanism_audit",
                    "playstyle_archetype_audit",
                    "hero_mechanism_profile",
                ):
                    continue
                if isinstance(v, str) and ("http://" in v or "https://" in v or "steamstatic.com" in v):
                    continue
                sv = _sanitize_for_llm(v)
                if sv is not None and sv != {} and sv != []:
                    cleaned[k] = sv
            return cleaned
        if isinstance(val, list):
            return [x for x in (_sanitize_for_llm(item) for item in val) if x is not None and x != {} and x != []]
        if isinstance(val, str):
            s = val
            if "http://" in s or "https://" in s or "steamstatic.com" in s:
                return None
            for nick, repl in nickname_map.items():
                if nick in s:
                    s = s.replace(nick, repl)
            return s
        return val

    raw_lanes = df.get("lane_matchups") or []
    lanes_compact = []
    if isinstance(raw_lanes, list):
        for lm in raw_lanes:
            if not isinstance(lm, dict):
                continue
            lanes_compact.append({
                "lane": lm.get("title") or lm.get("lane_zh") or lm.get("lane"),
                "verdict": lm.get("verdict_zh") or lm.get("winner"),
                "radiant": [
                    {
                        "pos": x.get("pos"),
                        "hero": x.get("hero_short_zh") or x.get("hero"),
                        "lh_10": x.get("lh10") if x.get("lh10") is not None else x.get("lh_10m"),
                        "nw_10": x.get("gold10") if x.get("gold10") is not None else x.get("nw_10m"),
                    }
                    for x in (lm.get("radiant_heroes") or lm.get("radiant_players") or lm.get("radiant") or [])
                    if isinstance(x, dict)
                ],
                "dire": [
                    {
                        "pos": x.get("pos"),
                        "hero": x.get("hero_short_zh") or x.get("hero"),
                        "lh_10": x.get("lh10") if x.get("lh10") is not None else x.get("lh_10m"),
                        "nw_10": x.get("gold10") if x.get("gold10") is not None else x.get("nw_10m"),
                    }
                    for x in (lm.get("dire_heroes") or lm.get("dire_players") or lm.get("dire") or [])
                    if isinstance(x, dict)
                ],
            })

    raw_macro = (df.get("macro_objectives_by_side") or {}).get(focus_side) or {}
    macro_compact = {
        k: v
        for k, v in raw_macro.items()
        if k in ("roshan_count", "tormentor_count", "towers_destroyed", "barracks_destroyed", "smoke_uses", "observer_wards", "sentry_wards", "dewards", "roshan_events")
        and v not in (None, [], {})
    }

    raw_patch_str = report.get("patch_str")
    raw_patch_id = report.get("patch")
    if raw_patch_str not in (None, ""):
        patch_val: Optional[str] = str(raw_patch_str)
    elif raw_patch_id not in (None, ""):
        patch_val = resolve_patch_name(raw_patch_id)
    else:
        patch_val = None
    lane_id_to_zh = {1: "下路", 2: "中路", 3: "上路"}

    compact_payload = _sanitize_for_llm({
        "match_id": report.get("match_id"),
        "patch": patch_val,
        "mode": report.get("mode_str"),
        "duration": report.get("duration_str"),
        "focus_side": focus_side,
        "user_won": report.get("user_won"),
        "score": f"天辉 {report.get('radiant_score', 0)} : {report.get('dire_score', 0)} 夜魇",
        "lane_matchups": lanes_compact,
        "macro_objectives": macro_compact,
        "phases_breakdown": phases_compact,
        "key_teamfights": [
            {
                "index": tf.get("index"),
                "time": tf.get("time_range") or f"{tf.get('start_str', '')}-{tf.get('end_str', '')}",
                "winner": tf.get("winner_zh") or tf.get("winner_side"),
                "kills_trade": tf.get("kills_trade") or f"{tf.get('radiant_deaths', 0)}:{tf.get('dire_deaths', 0)}",
                "gold_swing": tf.get("gold_swing") or tf.get("net_gold_swing"),
                "top_damage_hero": tf.get("top_damage_hero"),
            }
            for tf in (report.get("key_teamfights") or [])[:5]
        ],
        "own_team": [
            {
                "slot": p.get("player_slot"),
                "pos": p.get("pos"),
                "hero": p.get("hero_short_zh"),
                "lane": lane_id_to_zh.get(int(p.get("lane_id") or p.get("raw_lane") or 0)) or (p.get("laning_10m") or {}).get("lane_zh"),
                "kda": p.get("kda"),
                "kp_pct": p.get("kill_participation_pct"),
                "gpm": p.get("gpm"),
                "xpm": p.get("xpm"),
                "net_worth": p.get("net_worth"),
                "lh_dn": f"{p.get('last_hits')}/{p.get('denies')}",
                "laning_10m": {
                    k: (p.get("laning_10m") or {}).get(k)
                    for k in ("lh10", "dn10", "gold10", "xp10", "lane_zh", "lh_10m", "dn_10m", "nw_10m")
                    if isinstance(p.get("laning_10m"), dict) and (p.get("laning_10m") or {}).get(k) is not None
                },
                "hero_damage": p.get("hero_damage"),
                "hero_damage_share_pct": p.get("hero_damage_share_pct"),
                "damage_taken": p.get("damage_taken"),
                "tower_damage": p.get("tower_damage"),
                "stuns_sec": p.get("stuns_sec"),
                "dead_seconds": p.get("dead_seconds"),
                "death_gold_lost": p.get("death_gold_lost"),
                "obs_sen": f"{p.get('obs_placed')}/{p.get('sen_placed')}",
                "key_item_timings": (p.get("key_item_timings") or [])[:8],
                "final_items": [it.get("name_zh") or it.get("key") for it in (p.get("items") or [])] or (p.get("final_items") or [])[:6],
                "aghanims_scepter": p.get("aghanims_scepter", False),
                "aghanims_shard": p.get("aghanims_shard", False),
                "active_item_uses": {k: v["count"] for k, v in (p.get("active_item_uses") or {}).items() if isinstance(v, dict) and v.get("count")},
                "ability_uses": {a["zh_name"]: a["count"] for a in (p.get("ability_uses_rich") or [])[:5] if isinstance(a, dict) and a.get("zh_name")},
                "damage_by_source_top": [
                    {
                        "source": d.get("name_zh") or d.get("key"),
                        "hits": d.get("hits") or d.get("casts"),
                        "dmg": d.get("damage") or d.get("total_damage"),
                        "pct": d.get("share_pct") or d.get("pct"),
                    }
                    for d in (p.get("damage_by_source_rich") or [])[:4]
                    if isinstance(d, dict)
                ],
                "is_afk_farmer": p.get("is_afk_farmer", False),
                "role_duty_audit": _compute_player_role_duty_audit(p, own_team, opp_team, df, focus_side),
            }
            for p in own_team
        ],
        "opp_team": [
            {
                "slot": p.get("player_slot"),
                "pos": p.get("pos"),
                "hero": p.get("hero_short_zh"),
                "kda": p.get("kda"),
                "gpm": p.get("gpm"),
                "net_worth": p.get("net_worth"),
                "hero_damage": p.get("hero_damage"),
                "tower_damage": p.get("tower_damage"),
                "final_items": [it.get("name_zh") or it.get("key") for it in (p.get("items") or [])] or (p.get("final_items") or [])[:6],
            }
            for p in opp_team
        ],
    })
    compact_payload["patch"] = patch_val

    eff_tone = "roast" if str(tone_mode or "").strip().lower() == "roast" else "coach"
    own_won = bool(
        (focus_side == "radiant" and report.get("radiant_win"))
        or (focus_side == "dire" and not report.get("radiant_win"))
    )
    if own_won:
        outcome_rubric = (
            "   - 本方获胜：`grok_share_pct` 表示胜局贡献占比（5人之和=100%），贡献越大则 `grok_score` 与 `grok_share_pct` 越高。\n"
        )
    else:
        outcome_rubric = (
            "   - 本方落败：`grok_share_pct` 表示败局责任占比（5人之和=100%），失误与责任越大则 `grok_share_pct` 越高、`grok_score` 越低；若全队表现接近，责任占比应趋于平分。\n"
        )

    if eff_tone == "roast":
        tone_instruction = (
            "【语气模式：毒舌模式】在严格依据比赛事实数据、不编造时间点与数字的前提下，允许使用五黑熟人车队犀利调侃语气点评失误与分锅占比。\n"
        )
    else:
        tone_instruction = (
            "【语气模式：教练模式】围绕「本局主要问题」只客观陈述比赛事实数据与可执行改进建议，严禁使用讥讽攻击性词汇，统一使用“责任占比”“主要问题”“待改进点”等专业教练表述。\n"
        )

    system_prompt = (
        "你是 Dota 2 赛后复盘教练。请仅依据提供的比赛事实数据，用中文输出结构化 JSON 复盘报告（不夹杂英文变量名，不使用玩家昵称，一律用位置+英雄名代指）。\n"
        + tone_instruction +
        "一、【事实数据说明】\n"
        "1) 输入包含比赛补丁版本（patch）、对线分路（lane_matchups）、地图目标（macro_objectives）、三阶段表现（phases_breakdown）、关键团战（key_teamfights）及双方 1~5 号位完整遥测与职责数据（role_duty_audit）。\n"
        "2) 严禁编造输入数据中不存在的时间点、技能次数、伤害数字或装备记录；无法从数据直接得出的结论必须标为推断并使用中性措辞。\n"
        "二、【评分标准】\n"
        "1) 按 1~5 号位各自职责评估：核心位看对线补刀、经济转化率、关键装时间点、参战率、英雄伤害与建筑伤害；辅助位看视野控制、团队救人/先手装、控制时长与阵亡代价。\n"
        "2) 结合本局实际出装、技能伤害来源、天赋与中立道具附魔以及敌我阵容克制关系客观评判流派合理性。\n"
        "3) 为本方 5 名选手分别评定 `grok_score`（0~100 整数）与 `grok_share_pct`（浮点数，5人总和为 100.0）：\n"
        + outcome_rubric +
        "三、【输出 JSON 结构】\n"
        "请严格返回一个 JSON 对象（不带 Markdown 围栏），字段结构如下：\n"
        "{\n"
        '  "title": "本局胜负关键与阵容博弈总结",\n'
        '  "summary": "前期对线、中期节奏转化与后期团战控盾的全局复盘摘要",\n'
        '  "verdict": "本方 1~5 号位职责兑现度与出装流派复盘总结",\n'
        '  "team_practice": "下一局最需优先改进的一项团队配合或出装分工建议",\n'
        '  "stage_reviews": {\n'
        '    "early_lanes": "前期(0-10m)三路对位、补刀经济与游走支援点评",\n'
        '    "mid_tempo": "中期(10-25m)关键装成型、抓人推塔与资源转化点评",\n'
        '    "late_and_roshan": "后期(25m-终局)肉山控盾、高地攻防与团战执行点评",\n'
        '    "overall_verdict": "全场五人职责履行与阵容博弈总评"\n'
        '  },\n'
        '  "mvp": {"slot": "<整数>", "runner_up_slot": "<整数>", "confidence": "高/中/低", "reason": "评选依据", "comparison": "与队友对比", "evidence": ["数据依据1", "数据依据2"]},\n'
        '  "players": [\n'
        '    {\n'
        '      "slot": "<整数>",\n'
        '      "pos": "<1-5整数>",\n'
        '      "hero": "<英雄中文名>",\n'
        '      "grok_score": "<0-100整数>",\n'
        '      "grok_share_pct": "<占全队百分比浮点数>",\n'
        '      "headline": "该选手本局表现与出装节奏定性摘要",\n'
        '      "deep_verdict": "结合本局打法流派、出装时间轴、技能伤害占比、天赋与中立附魔及敌我克制关系的综合复盘",\n'
        '      "early_story": "前期(0-10m)分路对线、补刀经济与击杀阵亡复盘",\n'
        '      "mid_story": "中期(10-25m)经济增量、核心装成型时间点与参战复盘",\n'
        '      "late_story": "后期(25m-终局)成装演进、肉山高地团战与终局表现复盘",\n'
        '      "item_and_blink_audit": "出装顺序、技能伤害来源、天赋与中立道具附魔及主动装备使用效果评估",\n'
        '      "good": ["有数据支撑的亮点1", "有数据支撑的亮点2"],\n'
        '      "bad": ["有数据支撑的不足1", "有数据支撑的不足2"],\n'
        '      "practice": "针对该位置下一局的具体改进建议"\n'
        '    }\n'
        "  ],\n"
        '  "windows": [\n'
        '    {"time_label": "团战时间段", "title": "关键团战标题", "detail": "关键团战过程与技能交换复盘"}\n'
        "  ]\n"
        "}"
    )
    user_prompt = "以下为本局比赛事实数据，请严格按评分标准生成包含本方全部 5 名选手的 JSON 复盘报告：\n" + json.dumps(compact_payload, ensure_ascii=False)

    try:
        if prov == "gemini":
            if any(dep in model for dep in ["gemini-2.5", "gemini-2.0", "gemini-1.5"]):
                model = "gemini-3.8-flash"
            url = "https://generativelanguage.googleapis.com/v1beta/interactions"
            payload = {
                "model": model,
                "system_instruction": system_prompt,
                "input": user_prompt,
                "temperature": 0,
            }
            last_gem_err: Optional[Exception] = None
            out_txt = ""
            for _gem_att in range(2):
                try:
                    req = urllib.request.Request(
                        url,
                        data=json.dumps(payload).encode("utf-8"),
                        method="POST",
                        headers={
                            "Content-Type": "application/json",
                            "x-goog-api-key": key,
                            "User-Agent": "DotaAiAnalyst/2.0",
                        },
                    )
                    with urllib.request.urlopen(req, timeout=45) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                    steps = data.get("steps") or []
                    texts = []
                    for st in steps:
                        if st.get("type") == "model_output":
                            for c in st.get("content") or []:
                                if c.get("type") == "text" and c.get("text"):
                                    texts.append(c["text"])
                    cand_txt = "\n".join(texts) or data.get("output_text") or ""
                    parsed_gem = _parse_llm_json_robust(cand_txt)
                    if not isinstance(parsed_gem, dict):
                        raise ValueError("Gemini 返回的 JSON 截断或无法解析")
                    gem_ok, gem_err = validate_coaching_schema(parsed_gem, own_team=own_team)
                    if not gem_ok:
                        raise ValueError(f"Gemini JSON 结构校验未通过: {gem_err}")
                    out_txt = cand_txt
                    last_gem_err = None
                    break
                except Exception as e_gem:
                    last_gem_err = e_gem
            if last_gem_err is not None:
                raise last_gem_err
        else:
            from concurrent.futures import ThreadPoolExecutor

            url = f"{b_url.rstrip('/')}/chat/completions"
            # On xAI, grok-4.7 is a deep reasoning model that takes 50-120s (exceeding Vercel's 60s timeout).
            # Use grok-4.20-0309-non-reasoning with 6 parallel micro-shards (1 Global shard + 5 individual Pos 1..5 shards)
            # so each shard only generates ~800-1000 tokens and the entire review finishes in ~12-16s!
            api_model = "grok-4.20-0309-non-reasoning" if (prov == "xai" and model in ("grok-4.7", "grok-4.6", "grok-4")) else model
            model = api_model

            def _canonical_lane(p_dict: Dict[str, Any]) -> str:
                raw_ln = str(p_dict.get("lane") or ((p_dict.get("laning_10m") or {}).get("lane_zh") or "")).strip()
                for ln_tok in ("上路", "中路", "下路"):
                    if ln_tok in raw_ln:
                        return ln_tok
                pos_n = int(p_dict.get("pos") or 0)
                if pos_n == 2:
                    return "中路"
                if pos_n in (1, 5):
                    return "下路" if focus_side == "radiant" else "上路"
                return "上路" if focus_side == "radiant" else "下路"

            authoritative_lanes: Dict[int, str] = {
                int(p.get("pos") or 0): _canonical_lane(p)
                for p in (compact_payload.get("own_team") or [])
                if isinstance(p, dict) and int(p.get("pos") or 0) in (1, 2, 3, 4, 5)
            }

            global_payload = {
                "match_id": compact_payload.get("match_id"),
                "patch": compact_payload.get("patch"),
                "mode": compact_payload.get("mode"),
                "duration": compact_payload.get("duration"),
                "is_parsed": bool(report.get("is_parsed", True)),
                "focus_side": compact_payload.get("focus_side"),
                "user_won": compact_payload.get("user_won"),
                "score": compact_payload.get("score"),
                "authoritative_lanes": {
                    f"{pos_k}号位_{(next((x.get('hero') for x in (compact_payload.get('own_team') or []) if int(x.get('pos') or 0) == pos_k), ''))}": ln_v
                    for pos_k, ln_v in sorted(authoritative_lanes.items())
                },
                "lane_matchups": compact_payload.get("lane_matchups"),
                "macro_objectives": compact_payload.get("macro_objectives"),
                "key_teamfights": compact_payload.get("key_teamfights"),
                "own_team": [
                    {
                        "slot": p.get("slot"),
                        "pos": p.get("pos"),
                        "hero": p.get("hero"),
                        "lane": authoritative_lanes.get(int(p.get("pos") or 0), "上路"),
                        "kda": p.get("kda"),
                        "kp_pct": p.get("kp_pct"),
                        "gpm": p.get("gpm"),
                        "xpm": p.get("xpm"),
                        "net_worth": p.get("net_worth"),
                        "lh_dn": p.get("lh_dn"),
                        "hero_damage": p.get("hero_damage"),
                        "hero_damage_share_pct": p.get("hero_damage_share_pct"),
                        "tower_damage": p.get("tower_damage"),
                        "dead_seconds": p.get("dead_seconds"),
                        "obs_sen": p.get("obs_sen"),
                        "key_item_timings": p.get("key_item_timings"),
                        "final_items": p.get("final_items"),
                        "hero_pos_role_title": (p.get("role_duty_audit") or {}).get("hero_pos_role_title"),
                        "best_ally_synergies": ((p.get("role_duty_audit") or {}).get("best_ally_synergies") or [])[:2],
                        "counters_enemies": [c if isinstance(c, str) else c.get("label") for c in ((p.get("role_duty_audit") or {}).get("counters_enemies") or [])[:2]],
                        "countered_by_enemies": [c if isinstance(c, str) else c.get("label") for c in ((p.get("role_duty_audit") or {}).get("countered_by_enemies") or [])[:2]],
                        "role_duty_verdict": (p.get("role_duty_audit") or {}).get("duty_verdict"),
                    }
                    for p in (compact_payload.get("own_team") or [])
                ],
                "opp_team": compact_payload.get("opp_team"),
            }
            payload_json_str = json.dumps(global_payload, ensure_ascii=False)

            share_term_global = "分锅/贡献比例" if eff_tone == "roast" else "责任/贡献比例"
            user_prompt_global = (
                f"【全局定级与三幕复盘（单次调用统一产出 5 人打分、{share_term_global}与 MVP）】\n"
                f"请基于以下全部 5 名本方选手的事实数据与评分标准，在本次调用中统一完成全队 5 人的打分（`grok_score`）、{share_term_global}（`grok_share_pct`，5人总和=100.0）与 `mvp` 评选（`mvp.slot` 必须等于全队 `grok_score` 最高者的 `slot`），各英雄分路描述必须严格与 `authoritative_lanes` 一致。\n"
                "请输出 JSON 字段：`title`, `summary`, `verdict`, `team_practice`, `stage_reviews`（含 `early_lanes`, `mid_tempo`, `late_and_roshan`, `overall_verdict`）, `mvp`, `windows`（最多3条），以及包含全队 5 人打分定级的 `player_rankings`: `[{\"slot\": ..., \"pos\": 1..5, \"hero\": \"...\", \"lane\": \"上路/中路/下路\", \"grok_score\": 0..100, \"grok_share_pct\": ...}]`：\n"
                + payload_json_str
            )

            def _call_xai_chunk(
                u_prompt: str, max_tok: int, partial_mode: Optional[str] = None
            ) -> Optional[Dict[str, Any]]:
                import time as _t

                p_body = {
                    "model": api_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": u_prompt},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0,
                    "stream": False,
                    "max_tokens": max_tok,
                }
                t0_chunk = _t.time()
                last_err_c = None
                for _att in range(2):
                    if _att > 0 and (_t.time() - t0_chunk) > 16.0:
                        break
                    try:
                        req_c = urllib.request.Request(
                            url,
                            data=json.dumps(p_body, ensure_ascii=False).encode("utf-8"),
                            method="POST",
                            headers={
                                "Content-Type": "application/json",
                                "Accept": "application/json",
                                "Authorization": f"Bearer {key}",
                                "User-Agent": "DotaAiAnalyst/2.0",
                            },
                        )
                        with urllib.request.urlopen(req_c, timeout=36) as resp_c:
                            d_c = json.loads(resp_c.read().decode("utf-8"))
                        txt_c = d_c["choices"][0]["message"]["content"]
                        parsed_c = _parse_llm_json_robust(txt_c)
                        if not isinstance(parsed_c, dict):
                            raise ValueError("返回的 JSON 截断或无法解析")
                        if partial_mode:
                            is_valid_c, err_c = validate_coaching_schema(
                                parsed_c, partial_mode=partial_mode, own_team=own_team
                            )
                            if not is_valid_c:
                                raise ValueError(f"JSON 结构校验失败: {err_c}")
                        return parsed_c
                    except Exception as e_c:
                        last_err_c = e_c
                if last_err_c:
                    raise last_err_c
                return None

            part_global = _call_xai_chunk(user_prompt_global, 2200, partial_mode="global")
            if not isinstance(part_global, dict):
                raise RuntimeError("Grok 全局分片返回格式无效")

            global_rank_by_pos: Dict[int, Dict[str, Any]] = {}
            raw_rank_list = part_global.get("player_rankings") or part_global.get("players") or []
            if isinstance(raw_rank_list, list):
                for rk in raw_rank_list:
                    if isinstance(rk, dict) and int(rk.get("pos") or 0) in (1, 2, 3, 4, 5):
                        global_rank_by_pos[int(rk["pos"])] = rk
            if len(global_rank_by_pos) < 5:
                raise RuntimeError(f"Grok 全局排名不足 5 条（实际 {len(global_rank_by_pos)} 条）")

            global_conclusion = {
                "title": part_global.get("title"),
                "summary": part_global.get("summary"),
                "early_lanes": (part_global.get("stage_reviews") or {}).get("early_lanes"),
                "mvp": part_global.get("mvp"),
                "player_rankings": [
                    {
                        "pos": pos_k,
                        "lane": authoritative_lanes.get(pos_k),
                        "grok_score": global_rank_by_pos[pos_k]["grok_score"],
                        "grok_share_pct": global_rank_by_pos[pos_k]["grok_share_pct"],
                    }
                    for pos_k in (1, 2, 3, 4, 5)
                ],
            }

            def _build_pos_prompt(target_pos: int) -> str:
                role_hint = (
                    "请结合 `role_duty_audit` 评估该辅助/节奏位的英雄机制、4/5号位职责履行、团队装与视野贡献、队友配合及敌我克制关系。"
                    if target_pos in (4, 5)
                    else "请结合 `role_duty_audit` 评估该核心位的英雄机制、1/2/3号位职责履行、经济转化与关键装时间点、队友配合及敌我克制关系。"
                )
                assigned_rk = global_rank_by_pos[target_pos]
                target_lane = authoritative_lanes.get(target_pos, "上路")
                pos_payload = {
                    "match_id": compact_payload.get("match_id"),
                    "patch": compact_payload.get("patch"),
                    "duration": compact_payload.get("duration"),
                    "is_parsed": bool(report.get("is_parsed", True)),
                    "focus_side": compact_payload.get("focus_side"),
                    "user_won": compact_payload.get("user_won"),
                    "score": compact_payload.get("score"),
                    "authoritative_lane": target_lane,
                    "all_authoritative_lanes": authoritative_lanes,
                    "global_conclusion": global_conclusion,
                    "assigned_score": assigned_rk.get("grok_score"),
                    "assigned_share_pct": assigned_rk.get("grok_share_pct"),
                    "lane_matchups": compact_payload.get("lane_matchups"),
                    "key_teamfights": compact_payload.get("key_teamfights"),
                    "target_player_phases": [
                        {
                            "key": pd.get("key"),
                            "label": pd.get("label"),
                            "window": pd.get("window"),
                            "team_summary": pd.get("team_summary"),
                            "player_phase": [x for x in (pd.get("own_players") or []) if int(x.get("pos") or 0) == target_pos],
                        }
                        for pd in (compact_payload.get("phases_breakdown") or [])
                    ],
                    "target_player_full_forensics": [
                        p for p in (compact_payload.get("own_team") or []) if int(p.get("pos") or 0) == target_pos
                    ],
                    "teammates_scoreboard": [
                        {
                            "slot": p.get("slot"),
                            "pos": p.get("pos"),
                            "hero": p.get("hero"),
                            "lane": authoritative_lanes.get(int(p.get("pos") or 0), "上路"),
                            "kda": p.get("kda"),
                            "kp_pct": p.get("kp_pct"),
                            "gpm": p.get("gpm"),
                            "net_worth": p.get("net_worth"),
                            "hero_damage_share_pct": p.get("hero_damage_share_pct"),
                            "tower_damage": p.get("tower_damage"),
                            "dead_seconds": p.get("dead_seconds"),
                            "final_items": p.get("final_items"),
                            "role_duty_verdict": (p.get("role_duty_audit") or {}).get("duty_verdict"),
                        }
                        for p in (compact_payload.get("own_team") or [])
                    ],
                    "opp_team": compact_payload.get("opp_team"),
                }
                return (
                    f"【并发分片 Pos {target_pos}：{target_pos}号位选手个人复盘】\n"
                    f"请严格沿用 `global_conclusion` 已确定的全局结论、评分（`assigned_score`）、占比（`assigned_share_pct`）以及唯一分路 `authoritative_lane`（{target_lane}），只返回一个 JSON 对象 `{{\"players\": [ ... ]}}`，其中 `players` 数组只包含本方 {target_pos}号位（`pos` 为 {target_pos}）这一名选手的复盘对象。\n"
                    f"{role_hint}\n"
                    + json.dumps(pos_payload, ensure_ascii=False)
                )

            with ThreadPoolExecutor(max_workers=5) as pool:
                fut_pos_map = {
                    pos_i: pool.submit(_call_xai_chunk, _build_pos_prompt(pos_i), 2200, "player")
                    for pos_i in (1, 2, 3, 4, 5)
                }
                merged_players_by_pos: Dict[int, Dict[str, Any]] = {}
                for pos_i, fut_p in fut_pos_map.items():
                    res_p = fut_p.result()
                    if not isinstance(res_p, dict):
                        raise RuntimeError(f"Grok {pos_i}号位分片返回格式无效")
                    p_list = res_p.get("players")
                    if isinstance(p_list, list) and p_list and isinstance(p_list[0], dict):
                        gp = next(
                            (x for x in p_list if isinstance(x, dict) and int(x.get("pos") or 0) == pos_i),
                            p_list[0],
                        )
                        gp["pos"] = pos_i
                        merged_players_by_pos[pos_i] = gp
                    elif res_p.get("hero") or res_p.get("deep_verdict"):
                        res_p["pos"] = pos_i
                        merged_players_by_pos[pos_i] = res_p
                    else:
                        raise RuntimeError(f"Grok {pos_i}号位分片缺少选手数据")

            if len(merged_players_by_pos) < 5:
                raise RuntimeError("Grok 选手分片未全部成功返回")
            for pos_i, gp in merged_players_by_pos.items():
                rk_entry = global_rank_by_pos[pos_i]
                gp["grok_score"] = rk_entry["grok_score"]
                gp["grok_share_pct"] = rk_entry["grok_share_pct"]
                gp["lane"] = authoritative_lanes.get(pos_i, gp.get("lane") or "上路")
            part_global["players"] = [merged_players_by_pos[k] for k in sorted(merged_players_by_pos.keys())]
            out_txt = json.dumps(part_global, ensure_ascii=False)

        # 尝试解析为结构化 JSON 并持久化
        structured = _parse_llm_json_robust(out_txt)
        if not isinstance(structured, dict) or not isinstance(structured.get("players"), list) or len(structured["players"]) < 5:
            raise RuntimeError("大模型未返回完整的 5 人结构化判词 JSON")

        structured["author"] = f"{prov} / {model}"
        structured["model"] = model
        structured["provider"] = prov
        structured["side"] = focus_side
        own_pos_map = {int(p.get("pos") or 0): p for p in own_team if isinstance(p, dict)}
        own_valid_slots = {
            int(p["player_slot"])
            for p in own_team
            if isinstance(p, dict) and isinstance(p.get("player_slot"), int) and not isinstance(p.get("player_slot"), bool)
        }
        raw_slot_to_pos: Dict[int, int] = {}
        for rk_src in (structured.get("player_rankings") or []) + (structured.get("players") or []):
            if isinstance(rk_src, dict):
                sl_v = rk_src.get("slot")
                ps_v = rk_src.get("pos")
                if (
                    not isinstance(sl_v, bool)
                    and isinstance(sl_v, int)
                    and not isinstance(ps_v, bool)
                    and isinstance(ps_v, int)
                    and ps_v in (1, 2, 3, 4, 5)
                ):
                    raw_slot_to_pos[sl_v] = ps_v

        pls = [gp for gp in (structured.get("players") or []) if isinstance(gp, dict)]
        for gp in pls:
            pos_i = int(gp.get("pos") or 0)
            p_orig = own_pos_map.get(pos_i)
            if p_orig:
                gp["slot"] = p_orig.get("player_slot")
                gp["hero"] = p_orig.get("hero_short_zh") or p_orig.get("hero_name") or gp.get("hero")
            if gp.get("deep_verdict") and not gp.get("assessment"):
                gp["assessment"] = gp["deep_verdict"]

        mvp_obj = structured.get("mvp")
        if isinstance(mvp_obj, dict):
            raw_mvp_slot = mvp_obj.get("slot")
            if (
                not isinstance(raw_mvp_slot, bool)
                and isinstance(raw_mvp_slot, int)
                and raw_mvp_slot not in own_valid_slots
                and raw_mvp_slot in raw_slot_to_pos
            ):
                mapped_p = own_pos_map.get(raw_slot_to_pos[raw_mvp_slot])
                if mapped_p and mapped_p.get("player_slot") is not None:
                    mvp_obj["slot"] = mapped_p["player_slot"]

        structured["players"] = pls

        is_valid_full, full_err = validate_coaching_schema(structured, own_team=own_team)
        if not is_valid_full:
            raise RuntimeError(f"大模型返回结构校验未通过: {full_err}")

        fact_check_coaching_output(structured, report, compact_payload)
        meta_obj = structured.get("_meta")
        if not isinstance(meta_obj, dict):
            meta_obj = {}
            structured["_meta"] = meta_obj
        meta_obj["tone_mode"] = eff_tone
        out_txt = json.dumps(structured, ensure_ascii=False)
        mid = report.get("match_id")
        if mid:
            try:
                reports_dir = str(globals().get("REPORTS_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports"))
                os.makedirs(reports_dir, exist_ok=True)
                cache_path = os.path.join(reports_dir, f"coaching-{mid}-{focus_side}.json")
                with open(cache_path, "w", encoding="utf-8") as cf:
                    json.dump(structured, cf, ensure_ascii=False, indent=2)
            except OSError:
                import cloud_store

                tmp_dir = str(cloud_store.get_tmp_reports_dir())
                os.makedirs(tmp_dir, exist_ok=True)
                cache_path = os.path.join(tmp_dir, f"coaching-{mid}-{focus_side}.json")
                with open(cache_path, "w", encoding="utf-8") as cf:
                    json.dump(structured, cf, ensure_ascii=False, indent=2)

        return {
            "ok": True,
            "provider": prov,
            "model": model,
            "structured": structured,
            "text": out_txt,
        }
    except Exception as e:
        return {"ok": False, "error": f"调用 {prov} ({model}) 失败: {e}"}


def call_llm_pregame_coach(
    plan: Dict[str, Any],
    api_key: Optional[str] = None,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    调用 xAI Grok (grok-4.7) 为五黑选人结束后的赛前阵容做 10 秒实战推演。
    """
    env_cfg = load_env_llm_config()
    key = (env_cfg.get("api_key") or "").strip()
    prov = (env_cfg.get("provider") or "xai").strip().lower()
    model = (env_cfg.get("model_name") or "grok-4.20-0309-non-reasoning").strip()
    b_url = (env_cfg.get("base_url") or "https://api.x.ai/v1").strip()

    if prov in ("grok", "x.ai"):
        prov = "xai"
    if prov == "xai" and (not b_url or "openai.com" in b_url):
        b_url = "https://api.x.ai/v1"
    if prov == "xai" and ("gemini" in model or not model):
        model = env_cfg.get("model_name") or "grok-4.20-0309-non-reasoning"
    if prov == "xai" and model in ("grok-4.7", "grok-4.6", "grok-4"):
        model = "grok-4.20-0309-non-reasoning"

    if not key:
        return {"ok": False, "error": "未配置大模型密钥"}

    own_desc = [
        f"{p['pos']}号位 {p['hero_short_zh']}"
        for p in (plan.get("own_players") or [])
    ]
    enemy_desc = [
        f"{p['pos']}号位 {p['hero_short_zh']}"
        for p in (plan.get("enemy_players") or [])
    ]

    sys_prompt = (
        "你是 Dota 2 五黑车队教练。现在车队刚刚选完 1~5 号位英雄，准备进游戏出门。\n"
        "请用简洁准确的中文战术术语（跳刀、BKB、微光、开雾、三角区、魔方、肉山盾、先手、接控、买活等），"
        "直接给出本局配合要点、前中后期目标及每个位置的核心出装（严禁使用玩家昵称，一律用位置+英雄名代指）。\n"
        "严格返回 JSON 对象，字段如下：\n"
        "{\n"
        '  "headline": "一句话总结本局阵容核心思路",\n'
        '  "win_condition": "本局获胜的核心节奏条件",\n'
        '  "lose_condition": "本局最需防范的崩盘风险",\n'
        '  "combo_calls": ["核心连招配合1（谁先手谁接技能）", "核心连招配合2"],\n'
        '  "early_game": "0-10分钟三路对线、控符与支援重点",\n'
        '  "mid_game": "10-25分钟关键装节奏、开雾抓人与控盾推塔安排",\n'
        '  "late_game": "25分钟后团战集火优先级与上高地纪律",\n'
        '  "role_orders": [\n'
        '    {"pos": 1, "items": "前三件关键装", "order": "1号位职责要点"},\n'
        '    {"pos": 2, "items": "前三件关键装", "order": "2号位职责要点"},\n'
        '    {"pos": 3, "items": "前三件关键装", "order": "3号位职责要点"},\n'
        '    {"pos": 4, "items": "前三件关键装", "order": "4号位职责要点"},\n'
        '    {"pos": 5, "items": "前三件关键装", "order": "5号位职责要点"}\n'
        "  ]\n"
        "}"
    )

    usr_prompt = (
        f"本方五黑阵容：{' / '.join(own_desc)}\n"
        f"敌方阵容：{' / '.join(enemy_desc) if enemy_desc else '暂未完全输入，按常规阵容推演'}\n"
        "请生成赛前作战方案 JSON。"
    )

    try:
        url = f"{b_url.rstrip('/')}/chat/completions"
        api_model = "grok-4.20-0309-non-reasoning" if (prov == "xai" and model in ("grok-4.7", "grok-4.6", "grok-4")) else model
        model = api_model
        payload = {
            "model": api_model,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": usr_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "stream": False,
            "max_tokens": 2200,
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {key}",
                "User-Agent": "DotaAiAnalyst/2.0",
            },
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        out_txt = data["choices"][0]["message"]["content"].strip()
        if out_txt.startswith("```"):
            out_txt = out_txt.strip("`")
            if out_txt.startswith("json"):
                out_txt = out_txt[4:].strip()
        structured = json.loads(out_txt)
        structured["model"] = model
        structured["author"] = f"{prov.upper()} / {model}"
        return {"ok": True, "model": model, "grok_live_brief": structured}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ==============================================================================
# Nano Banana (gemini-nano-banana-2.1) & Grok Imagine 2.0 战报超燃/处刑原画生成引擎
# ==============================================================================

HERO_ARCANA_VISUAL_MAP: Dict[str, str] = {
    "主宰": (
        "Juggernaut (Yurnero) wearing his legendary 'Bladeform Legacy' Arcana (至宝剑心之遗): "
        "his ancient carved mask is split and cracked open down the center with blinding cyan-turquoise and fiery crimson "
        "dragon-fire pouring from his glowing eyes and glowing runes tattooed across his muscular chest; "
        "wielding a blazing dual-colored Immortal Dragon-Spirit Katana ('Edge of the Lost Order' / 'Serrakura'), "
        "while a colossal, roaring translucent turquoise-and-crimson Ancestral Dragon Spirit coils majestically in the sky "
        "directly behind him, and a glowing golden Immortal lucky-cat Healing Ward totem ('Fortune's Tout') radiates golden light"
    ),
    "瘟疫法师": (
        "Necrophos wearing his full Golden-and-Emerald Immortal set ('Sullen Hollow' & 'Sullen Rampart'): "
        "glowing golden plague-lord mantle and jade immortal shoulders, wielding a gigantic glowing emerald Immortal Grim Reaper Scythe"
    ),
    "马格纳斯": (
        "Magnus wearing his full Immortal set ('Shock of the Anvil' & Golden Lightning Horn): "
        "crackling golden-blue lightning horn and colossal molten-lava Immortal warhammer"
    ),
    "天怒法师": (
        "Skywrath Mage wearing his 'The Devotions of Dragonus' Arcana and Golden Immortal Wings: "
        "divine crimson-and-gold royal feathered wings, glowing arcane crown, and floating golden mystic staff"
    ),
    "莱恩": (
        "Lion wearing his full Rainbow Immortal set ('Hell-Spar Anathema' glowing neon emerald-and-crimson demonic arm, "
        "crystalline immortal shoulders, and golden hex staff)"
    ),
    "破晓辰星": (
        "Dawnbreaker in her Starforged celestial golden-nebula armor with blazing solar warhammer"
    ),
    "痛苦女王": (
        "Queen of Pain wearing her 'Eminence of Ristul' Arcana: fiery crimson demon-queen form with curved horns, "
        "bat wings, and a crackling blood-red sonic whip"
    ),
    "水晶室女": (
        "Crystal Maiden wearing her 'Frost Avalanche' Arcana: floating aurora-borealis winter cloak and glowing ice crystal staff"
    ),
    "龙骑士": (
        "Dragon Knight in his ornate crimson-and-gold scaled Davion dragon-slayer armor with dragon crest shield and burning broadsword"
    ),
    "风行者": (
        "Windranger wearing her 'Compass of the Rising Gale' Arcana: glowing turquoise wind-sylph armor and swirling gale longbow"
    ),
    "影魔": (
        "Shadow Fiend wearing his 'Demon Eater' Arcana: pitch-black demonic lord with roaring hellfire magma core and triple shadowraze flames"
    ),
    "帕吉": (
        "Pudge wearing his 'Feast of Abscession' Arcana with glowing green-and-crimson mechanical chainsaws and bloody Dragonclaw Hook"
    ),
    "幻影刺客": (
        "Phantom Assassin wearing her 'Manifold Paradox' Arcana: luminous paradoxical blue-and-gold spectral armor wielding twin dimensional rift blades"
    ),
    "敌法师": (
        "Anti-Mage wearing his Golden 'Basher Blades' Immortal glaives and purple energy mohawk crest"
    ),
    "斧王": (
        "Axe in his 'Axe Unleashed' Immortal form with blazing molten lava mantle and glowing golden Culling Blade greataxe"
    ),
    "斯拉克": (
        "Slark wearing his 'Sea Rake's Bridle' Golden Immortal shark-fin cowl and twin glowing hydrakan daggers"
    ),
    "卡尔": (
        "Invoker wearing his iconic 'Dark Artistry' purple Immortal cape with blazing Quas-Wex-Exort cosmic orbs"
    ),
    "祈求者": (
        "Invoker wearing his iconic 'Dark Artistry' purple Immortal cape with blazing Quas-Wex-Exort cosmic orbs"
    ),
    "拉比克": (
        "Rubick wearing his 'Magus Cypher' Arcana floating green-and-gold geometric cube cape and golden Fantoccini staff"
    ),
    "虚空假面": (
        "Faceless Void wearing his 'Claszian Apostasy' Arcana with eldritch cosmic purple tentacles and glowing Jewel of Aeons mace inside Chronosphere"
    ),
    "斯温": (
        "Sven wearing his 'Vigil Triumph' Immortal glowing blue-and-gold colossal greatsword in red God's Strength armor"
    ),
    "莉娜": (
        "Lina wearing her 'Fiery Soul of the Slayer' Arcana with blazing hair of pure fire and golden flame skirt"
    ),
    "宙斯": (
        "Zeus wearing his 'Tempest Helm of the Thundergod' Arcana riding a crackling storm cloud with divine thunderbolt spear"
    ),
    "幽鬼": (
        "Spectre wearing her 'Phantom Advent' Arcana floating spectral bladed armor with crimson energy daggers"
    ),
    "冥魂大帝": (
        "Wraith King wearing his 'The One True King' Skeleton King Arcana on a fiery bone throne with blazing hellfire greatsword"
    ),
    "撼地者": (
        "Earthshaker wearing his 'Planetfall' Arcana celestial starry-nebula form slamming a cosmic meteor totem"
    ),
    "卓尔游侠": (
        "Drow Ranger wearing her 'Dread Retribution' Arcana in dark crimson-and-silver armor wielding a giant vengeance crossbow"
    ),
    "齐天大圣": (
        "Monkey King wearing his 'Great Sage's Reckoning' Arcana in golden dragon-king armor riding a Nimbus cloud with glowing Golden Jingu Bang staff"
    ),
    "恐怖利刃": (
        "Terrorblade wearing his 'Fractal Horns of Inner Abysm' Arcana with glowing prismatic demon wings and twin metamorphosis scythes"
    ),
}

HERO_CLASSIC_VISUAL_MAP: Dict[str, str] = {
    "主宰": "Juggernaut (Yurnero, masked samurai bladesman wearing carved ivory-and-crimson tribal mask, fur shoulder armor, wielding a blazing katana)",
    "瘟疫法师": "Necrophos (Rotund'jere, glowing emerald-green plague prelate wielding a massive grim-reaper scythe surrounded by ghostly green souls)",
    "马格纳斯": "Magnus (Magnoceros, mighty armored centaur-rhino warrior with glowing horn and crackling shockwave poleaxe)",
    "天怒法师": "Skywrath Mage (Dragonus, winged celestial avian mage in golden-blue armor casting arcane mystic flares)",
    "莱恩": "Lion (Demon Witch with glowing crimson hellfire demonic hand and hex wand)",
    "破晓辰星": "Dawnbreaker (Valora, golden metallic celestial warrior maiden wielding a cosmic solar warhammer)",
    "痛苦女王": "Queen of Pain (Akasha, winged demoness succubus with curved horns, sapphire skin, and sonic scream energy)",
    "水晶室女": "Crystal Maiden (Rylai, frost sorceress in blue-and-white fur winter cloak with glowing ice crystal staff)",
    "龙骑士": "Dragon Knight (Davion in crimson-and-gold dragonscale knight armor with shield and broadsword)",
    "风行者": "Windranger (Lyralei, agile ginger archer in emerald woodland cloak with glowing windrun longbow)",
}

DEFEATED_ENEMY_PROPS_MAP: Dict[str, str] = {
    "破晓辰星": "fallen Dawnbreaker kneeling in the dark foreground rubble with her cracked golden warhammer on the ground",
    "水晶室女": "defeated Crystal Maiden collapsed in the shadows with her shattered ice staff",
    "痛苦女王": "defeated Queen of Pain knocked down in the lower smoke with torn demon wings",
    "龙骑士": "fallen Dragon Knight kneeling with his broken dragon shield in the foreground",
    "风行者": "defeated Windranger knocked back in the shadows with her dropped bow",
    "主宰": "fallen Juggernaut with a cracked mask and dropped katana in the rubble",
    "瘟疫法师": "defeated Necrophos knocked down in the shadows with his dropped scythe",
    "马格纳斯": "fallen Magnus collapsed in the rubble",
    "天怒法师": "defeated Skywrath Mage knocked down with scattered golden feathers",
    "莱恩": "defeated Lion knocked down in the dark foreground",
}


def _extract_hero_en_visual(hero_zh: str, img_url: str = "", cosmetic_mode: str = "arcana") -> str:
    clean_zh = (hero_zh or "").split("(")[0].strip()
    if cosmetic_mode != "classic" and clean_zh in HERO_ARCANA_VISUAL_MAP:
        base_arcana = HERO_ARCANA_VISUAL_MAP[clean_zh]
        if cosmetic_mode == "arcana_red" and clean_zh == "主宰":
            return (
                "Juggernaut (Yurnero) in his Stage-2 Crimson 'Bladeform Legacy' Arcana (二阶段赤红至宝剑心之遗): "
                "his split mask and armored body are wreathed in intense blood-crimson and molten-gold dragon fire, "
                "wielding a blazing crimson Immortal katana while a colossal roaring red-and-gold Ancestral Dragon Spirit "
                "erupts behind him"
            )
        return base_arcana
    if clean_zh in HERO_CLASSIC_VISUAL_MAP:
        return HERO_CLASSIC_VISUAL_MAP[clean_zh]
    slug = ""
    if img_url:
        m = re.search(r"/heroes/(?:icons/)?([a-z0-9_]+)\.", img_url)
        if m:
            slug = m.group(1).replace("_", " ").title()
    if slug:
        if cosmetic_mode != "classic":
            return f"Dota 2 hero {slug} ({clean_zh}) wearing their full glowing Arcana and Immortal cosmetic set"
        return f"Dota 2 hero {slug} ({clean_zh})"
    return f"Dota 2 hero {clean_zh}"


def _extract_defeated_enemy_prop(hero_zh: str, img_url: str = "") -> str:
    clean_zh = (hero_zh or "").split("(")[0].strip()
    if clean_zh in DEFEATED_ENEMY_PROPS_MAP:
        return DEFEATED_ENEMY_PROPS_MAP[clean_zh]
    slug = ""
    if img_url:
        m = re.search(r"/heroes/(?:icons/)?([a-z0-9_]+)\.", img_url)
        if m:
            slug = m.group(1).replace("_", " ").title()
    return f"defeated {slug or clean_zh} knocked down in the dark foreground rubble"


def build_dota_poster_art_prompt(
    report: Optional[Dict[str, Any]],
    player_slot: Optional[int] = None,
    style_mode: str = "auto",
    cosmetic_mode: str = "arcana",
    custom_scene: str = "",
    career_member: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    根据单局真实录像数据（击杀猎物、苦主天敌、大招斩击数、核心神装、Grok 评分与判词）或跨局生涯数据，
    构建专门针对 Nano Banana (gemini-nano-banana-2.1) 优化的高张力 Dota 2 视觉场景 Prompt：
    - 默认穿戴顶配至宝/不朽饰品（如至宝剑圣《剑心之遗》+ 巨型龙魂虚影 + 金色招财猫治疗守卫）；
    - 绝对凸显主角 MVP C位霸气（占画面中心 75% 仰拍特写，手下败将仅作为脚下暗处被击倒的残影与碎裂武器，绝不像队友并排站立）；
    - 画面 100% 纯净无任何文字/水印。
    """
    if career_member and not report:
        m_name = career_member.get("name") or career_member.get("personaname") or "五黑选手"
        sigs = career_member.get("signature_heroes") or []
        cursed = career_member.get("cursed_heroes") or []
        best_h = (sigs[0].get("hero_short_zh") or sigs[0].get("hero_zh")) if sigs else "主宰"
        best_img = sigs[0].get("hero_img", "") if sigs else ""
        worst_h = (cursed[0].get("hero_short_zh") or cursed[0].get("hero_zh")) if cursed else ""
        hero_vis = _extract_hero_en_visual(best_h, best_img, cosmetic_mode)
        if style_mode == "roast" and worst_h:
            w_vis = _extract_hero_en_visual(worst_h, cursed[0].get("hero_img", ""), cosmetic_mode)
            prompt = (
                f"Dark-fantasy comedic Dota 2 digital illustration, 16:9 widescreen artwork: "
                f"{w_vis} looking panicked and overwhelmed in the dark Dire jungle, surrounded by menacing enemy shadows "
                f"while dropping gold coins and holding unpressed items. Dramatic volumetric lighting, "
                f"Valve Dota 2 collector's art style, ultra-detailed, strictly NO text, NO letters, NO UI."
            )
            scene_zh = f"生涯暗黑处刑原画：{m_name} 的魔咒英雄【{worst_h}】在野区被围剿暴毙名场面"
        else:
            prompt = (
                f"Epic Dota 2 Collector's Edition key art splash illustration, 16:9 widescreen masterpiece: "
                f"SOLO MVP FOCUS on {hero_vis} dominating 75% of the center frame in a towering, godlike low-angle hero shot "
                f"atop the shattered enemy highground ancient throne, radiating golden Aegis of the Immortal light and divine aura. "
                f"Ultra-detailed 8k, strictly NO text, NO letters, NO watermarks."
            )
            scene_zh = f"生涯封神招牌原画：{m_name} 的本命绝活【{best_h}】（至宝神装形态）登顶遗迹王座"
        if custom_scene.strip():
            prompt += f" Specific user scene detail: {custom_scene.strip()}."
            scene_zh += f"（定制细节：{custom_scene.strip()}）"
        return {
            "prompt": prompt[:1150],
            "scene_summary_zh": scene_zh,
            "tone": "roast" if style_mode == "roast" else "epic",
            "hero_zh": best_h,
            "player_name": m_name,
        }

    report = report or {}
    all_players = (report.get("radiant_pos_1_to_5") or []) + (report.get("dire_pos_1_to_5") or [])
    raw_side = report.get("focus_side") or "dire"
    own_players = report.get("radiant_pos_1_to_5", []) if raw_side == "radiant" else report.get("dire_pos_1_to_5", [])
    won = bool((raw_side == "radiant" and report.get("radiant_win")) or (raw_side == "dire" and not report.get("radiant_win")))

    p = None
    if player_slot is not None:
        p = next((x for x in all_players if int(x.get("player_slot", -1)) == int(player_slot)), None)
    if not p:
        p = own_players[0] if own_players else (all_players[0] if all_players else {})

    hero_zh = p.get("hero_short_zh") or p.get("hero_name") or "主宰"
    pname = p.get("personaname") or "匿名玩家"
    pos = int(p.get("pos") or 1)
    hero_vis = _extract_hero_en_visual(hero_zh, p.get("hero_img", ""), cosmetic_mode)

    # Find Grok entry & score
    gc = report.get("grok_coaching") or {}
    gp = next(
        (
            g for g in (gc.get("players") or [])
            if isinstance(g, dict) and (g.get("slot") == p.get("player_slot") or int(g.get("pos") or 0) == pos)
        ),
        {},
    )
    sc100 = int(gp.get("grok_score") or round(float(p.get("mvp_score") or 75)))

    # Victims killed by this player
    kills_heroes = ((p.get("kills_breakdown") or {}).get("heroes") or [])[:3]
    defeated_props_list = [
        _extract_defeated_enemy_prop(v.get("hero_short_zh", ""), v.get("hero_icon", ""))
        for v in kills_heroes
        if v.get("hero_short_zh")
    ]
    victim_zh_list = [f"{v.get('hero_short_zh')}×{v.get('count', 1)}" for v in kills_heroes if v.get("hero_short_zh")]

    # Nemesis who killed this player
    killed_by_heroes = ((p.get("killed_by_breakdown") or {}).get("heroes") or [])[:3]
    nemesis_vis_list = [
        _extract_hero_en_visual(v.get("hero_short_zh", ""), v.get("hero_icon", ""), cosmetic_mode).split("(")[0].strip()
        for v in killed_by_heroes
        if v.get("hero_short_zh")
    ]
    nemesis_zh_list = [f"{v.get('hero_short_zh')}×{v.get('count', 1)}" for v in killed_by_heroes if v.get("hero_short_zh")]

    # Signature ult / spells
    exec_audit = p.get("hero_execution_audit") or {}
    ults = exec_audit.get("ult_audits") or []
    ult_zh = ults[0].get("ability_zh", "") if ults else ""
    ult_casts = ults[0].get("casts", 0) if ults else 0
    ult_hits = ults[0].get("hits", 0) if ults else 0
    ult_unit = ults[0].get("unit_label", "次") if ults else ""

    # Items
    final_items = [str(it).split("(")[0] for it in (p.get("final_items") or []) if it and not str(it).startswith("[中立]")][:4]

    # Compute team rank by Grok score & share
    def _p_score(px: Dict[str, Any]) -> int:
        gpx = next(
            (
                g for g in (gc.get("players") or [])
                if isinstance(g, dict) and (g.get("slot") == px.get("player_slot") or int(g.get("pos") or 0) == int(px.get("pos") or 0))
            ),
            {},
        )
        return int(gpx.get("grok_score") or round(float(px.get("mvp_score") or 70)))

    own_sorted_desc = sorted(own_players, key=_p_score, reverse=True)
    own_sorted_asc = sorted(own_players, key=_p_score)
    rank_desc_idx = next((i for i, x in enumerate(own_sorted_desc) if x.get("player_slot") == p.get("player_slot")), 2)
    rank_asc_idx = next((i for i, x in enumerate(own_sorted_asc) if x.get("player_slot") == p.get("player_slot")), 2)
    top_ally = own_sorted_desc[0] if own_sorted_desc else p
    top_ally_zh = top_ally.get("hero_short_zh") or top_ally.get("hero_name") or "主宰"
    top_ally_vis = _extract_hero_en_visual(top_ally_zh, top_ally.get("hero_img", ""), cosmetic_mode).split("(")[0].strip()

    # Crime / Forensics telemetry for this player
    df = report.get("deep_forensics") or {}
    role_audit = _compute_player_role_duty_audit(p, own_players, [], df, raw_side)
    is_toxic_supp = bool(role_audit.get("is_toxic_fake_support"))
    solo_cnt = int(role_audit.get("solo_pickoffs_count") or 0)
    hdmg_share = float(p.get("hero_damage_share_pct") or 0.0)
    deaths_cnt = int(p.get("deaths") or 0)

    unpressed_side = (df.get("unpressed_saves_by_side") or {}).get(raw_side) or {}
    unpressed_events = [
        ev for ev in (unpressed_side.get("events") or [])
        if int(ev.get("pos") or 0) == pos or ev.get("hero_short_zh") == hero_zh
    ]
    unpressed_cnt = len(unpressed_events)
    unpressed_item_zh = unpressed_events[0].get("item_zh", "BKB黑皇杖") if unpressed_events else "BKB/救命装"

    nemesis_en = ", ".join(nemesis_vis_list) if nemesis_vis_list else "enemy heroes"
    nemesis_zh = "、".join(nemesis_zh_list) if nemesis_zh_list else "敌方主力"
    defeated_en = "; ".join(defeated_props_list) if defeated_props_list else "defeated enemies knocked back in the shockwave"
    victims_zh = "、".join(victim_zh_list) if victim_zh_list else "敌方全员"

    # Determine specific scene archetype when style_mode == "auto"
    archetype = style_mode
    if style_mode == "auto":
        if won:
            if rank_desc_idx == 0:
                archetype = "epic"
            elif rank_desc_idx == 1:
                archetype = "win_co_carry"
            elif rank_asc_idx == 0 and (sc100 <= 70 or deaths_cnt >= 8 or solo_cnt >= 3):
                archetype = "passenger"
            else:
                archetype = "win_role_pillar"
        else:
            # Loss match: differentiate SVP vs #1/#2 Culprit (and specific crime type)
            if rank_desc_idx == 0 and sc100 >= 72:
                archetype = "svp"
            elif is_toxic_supp or (pos in (4, 5) and rank_asc_idx <= 1 and role_audit.get("built_selfish_core_items")):
                archetype = "roast_greedy"
            elif unpressed_cnt >= 2 and rank_asc_idx <= 2:
                archetype = "roast_bkb"
            elif pos in (1, 2) and hdmg_share < 18.0 and rank_asc_idx <= 1:
                archetype = "roast_zero_dmg"
            elif solo_cnt >= 3 or deaths_cnt >= 9:
                archetype = "roast_atm"
            else:
                archetype = "roast"

    cosmetic_label_zh = "经典造型" if cosmetic_mode == "classic" else ("二阶段赤红至宝" if cosmetic_mode == "arcana_red" else "顶配至宝+不朽神装")

    if archetype == "svp":
        prompt = (
            f"Tragic & heroic Dota 2 dark-fantasy cinematic masterpiece, 16:9 widescreen splash art. "
            f"SOLO TRAGIC SVP PROTAGONIST (70% center foreground): {hero_vis} in battle-scarred, blood-stained armor "
            f"standing defiantly alone on the burning steps of the crumbling Ancient throne, wielding glowing weapons "
            f"to single-handedly hold back an overwhelming tidal wave of cinque menacing enemy heroes ({nemesis_en}). "
            f"Behind him in the rubble lie his exhausted, fallen teammates. Intense volumetric fire and rain lighting, "
            f"lone warrior 1v5 last stand atmosphere, ultra-detailed 8k, strictly NO text, NO letters, NO UI, NO watermarks."
        )
        scene_zh = (
            f"🩸 悲情孤胆院长 1v5 原画（{cosmetic_label_zh}）：[{pos}号位] {pname} 的【{hero_zh}】（败方最高 {sc100}/100分）"
            f"在崩塌的遗迹前浴血独战敌方五人，一人扛起全队！"
        )
    elif archetype == "passenger":
        prompt = (
            f"Hilarious dark-fantasy Dota 2 cinematic illustration, 16:9 widescreen key art: "
            f"In the foreground, a battered, bruised, and bandaged {hero_vis} is lounging comfortably on a makeshift golden palanquin chair, "
            f"grinning sheepishly and sipping a healing salve potion while clutching spilled gold coins. "
            f"Right in front of him, a colossal, godlike {top_ally_vis} is doing all the work—unleashing devastating ultimate power "
            f"and effortlessly slaughtering the enemy team ({nemesis_en}) to carry him to victory. "
            f"Expressive Valve Dota 2 comic-fantasy painting style, ultra-detailed 8k, strictly NO text, NO letters, NO watermarks."
        )
        scene_zh = (
            f"🛋️ 团队拼图抱大腿原画：[{pos}号位] {pname} 的【{hero_zh}】（{sc100}分·阵亡{deaths_cnt}次）"
            f"鼻青脸肿坐在花轿上喝药看戏，全靠前方大腿【{top_ally_zh}】一刀砍翻全场带飞！"
        )
    elif archetype == "roast_greedy":
        selfish_str = "、".join((role_audit.get("built_selfish_core_items") or ["散失之刃", "点金手"])[:2])
        prompt = (
            f"Satirical dark-fantasy Dota 2 disaster illustration, 16:9 widescreen poster art: "
            f"{hero_vis} (supposed to be a support!) is crouching greedily inside a dark jungle camp, "
            f"ignoring the burning allied base in the distant background while hoarding huge overflowing sacks of gold coins "
            f"and clutching a glowing purple Diffusal Blade / Hand of Midas with zero observer wards anywhere. "
            f"Suddenly, towering menacing silhouettes of {nemesis_en} ambush him from the shadows right behind his back with glowing weapons raised! "
            f"Hilarious panicked expression, flying gold coins, Valve Dota 2 digital painting style, 8k, strictly NO text, NO letters, NO watermarks."
        )
        scene_zh = (
            f"💸 假辅助真毒瘤处刑原画：[{pos}号位] {pname} 的【{hero_zh}】（{sc100}分）不出救人装，"
            f"在黑图野区怀抱【{selfish_str}】偷刷钱抢经济，被敌方 {nemesis_zh} 当场瓮中捉鳖！"
        )
    elif archetype == "roast_bkb":
        prompt = (
            f"Satirical dark-fantasy Dota 2 disaster illustration, 16:9 widescreen poster art: "
            f"{hero_vis} in the center of a chaotic teamfight, completely frozen, stunned, and hexed under heavy magical chains "
            f"and arcane explosions from {nemesis_en}. In the close-up foreground, his golden Black King Bar (BKB) staff / defensive artifact "
            f"is strapped to his belt covered in thick cobwebs and a rusty padlock—glowing full of charge but NEVER pressed! "
            f"Comedic look of sheer regret and panic, dramatic lighting, Valve Dota 2 painting style, 8k, strictly NO text, NO letters, NO watermarks."
        )
        scene_zh = (
            f"🧤 憋死救命装处刑原画：[{pos}号位] {pname} 的【{hero_zh}】（{sc100}分）腰间的【{unpressed_item_zh}】"
            f"长满蜘蛛网省着下崽，被敌方 {nemesis_zh} 一套控到死秒躺！"
        )
    elif archetype == "roast_zero_dmg":
        prompt = (
            f"Satirical dark-fantasy Dota 2 disaster illustration, 16:9 widescreen poster art: "
            f"{hero_vis} dressed in absurdly heavy, oversized, glittering luxury golden armor and carrying a mountain of expensive treasure chests "
            f"and divine rapiers on his back, tripping flat on his face the very second he steps out of the jungle, "
            f"instantly flattened by {nemesis_en} while dealing zero damage and scattering treasure everywhere like a loot piñata! "
            f"Dark-humored Valve Dota 2 painting style, 8k, strictly NO text, NO letters, NO watermarks."
        )
        scene_zh = (
            f"📦 高占经低输出快递员原画：[{pos}号位] {pname} 的【{hero_zh}】（{sc100}分·伤害占比仅{hdmg_share:.1f}%）"
            f"刷了一整局豪华神装，出山一秒融化给 {nemesis_zh} 送温暖！"
        )
    elif archetype in ("roast_atm", "roast"):
        prompt = (
            f"Dark-fantasy satirical Dota 2 disaster illustration, 16:9 widescreen poster key art: "
            f"{hero_vis} caught out of position completely alone in a pitch-black, misty Dota 2 river without ward vision, "
            f"looking terrified and dropping overflowing showers of gold coins like a broken ATM machine while being ambushed "
            f"and surrounded from all sides by menacing {nemesis_en} leaping from the shadows. "
            f"Shattered armor, dramatic crimson-and-shadow volumetric lighting, Valve Dota 2 digital painting style, "
            f"ultra-detailed 8k, strictly NO text, NO letters, NO watermarks."
        )
        scene_zh = (
            f"🏧 黑图提款机处刑原画：[{pos}号位] {pname} 的【{hero_zh}】（{sc100}分·落单{solo_cnt}次/死{deaths_cnt}次）"
            f"在漆黑河道无视野单走，惨遭 {nemesis_zh} 围剿狂爆金币！"
        )
    elif archetype in ("win_co_carry", "win_role_pillar") and pos >= 3:
        role_action_en = (
            f"blinking into the center of the enemy formation and slamming the ground with a massive {ult_zh or 'crowd-control shockwave'}, "
            f"sending {defeated_en} flying into the air while shielding his teammates behind a wall of steel and magic"
            if pos == 3
            else f"emerging from purple Smoke of Deceit mist on a highground cliff surrounded by glowing blue and yellow Observer/Sentry wards, "
                 f"casting decisive arcane disables ({ult_zh or 'hex and mystic flares'}) that lock down {defeated_en}"
        )
        prompt = (
            f"Valve Dota 2 The International Collector's Edition splash art, dark-fantasy masterpiece, 16:9 widescreen. "
            f"CENTERPIECE PLAYMAKER PROTAGONIST (70% center foreground): {hero_vis}, {role_action_en}. "
            f"Dramatic low-angle heroic perspective, volumetric arcane and golden lighting, ultra-detailed 8k, "
            f"strictly NO text, NO letters, NO UI, NO watermarks."
        )
        scene_zh = (
            f"⚔️ {pos}号位破阵功臣原画（{cosmetic_label_zh}）：[{pos}号位] {pname} 的【{hero_zh}】（{sc100}/100分）"
            f"{'先手开团控场震碎敌阵' if pos == 3 else '诡计之雾致命先手+视野封锁'}，助队拿下大胜！"
        )
    else:
        allies_list = [
            _extract_hero_en_visual(a.get("hero_short_zh", ""), a.get("hero_img", ""), cosmetic_mode).split("(")[0].strip()
            for a in own_players
            if a.get("player_slot") != p.get("player_slot") and a.get("hero_short_zh")
        ][:2]
        allies_bg_en = (
            f"In the distant background behind him, his smaller ally silhouettes ({', '.join(allies_list)}) back up his charge, "
            if allies_list
            else ""
        )
        style_tag = (
            "Ufotable / MAPPA anime movie sakuga climax impact frame, 16:9 widescreen masterpiece"
            if archetype == "anime"
            else "Valve Dota 2 The International Collector's Edition MVP centerpiece splash art, dark-fantasy oil-and-digital masterpiece, 16:9 widescreen"
        )
        ult_en_hint = ""
        if "无敌斩" in ult_zh or "主宰" in hero_zh:
            ult_en_hint = (
                "in a dramatic heroic low-angle close-up dominating 70% of the center foreground under a blazing golden MVP spotlight, "
                "leaping forward and unleashing an unstoppable storm of Omnislash cyan-and-crimson dragon-spirit katana slashes"
            )
        elif "镰刀" in ult_zh or "瘟疫法师" in hero_zh:
            ult_en_hint = (
                "in a dramatic heroic low-angle close-up dominating 70% of the center foreground under a blazing golden-emerald MVP spotlight, "
                "summoning a colossal glowing emerald Immortal Reaper's Scythe execution beam"
            )
        elif "两极反转" in ult_zh or "马格纳斯" in hero_zh:
            ult_en_hint = (
                "in a dramatic heroic low-angle close-up dominating 70% of the center foreground under a blazing golden MVP spotlight, "
                "slamming his lightning Immortal warhammer to unleash a devastating Reverse Polarity shockwave"
            )
        elif ult_zh:
            ult_en_hint = (
                f"in a dramatic heroic low-angle close-up dominating 70% of the center foreground under a blazing golden MVP spotlight, "
                f"unleashing their signature ultimate ability ({ult_zh}) with overwhelming godlike MVP aura"
            )
        else:
            ult_en_hint = (
                "in a dramatic heroic low-angle close-up dominating 70% of the center foreground under a blazing golden MVP spotlight, "
                "radiating overwhelming godlike MVP conqueror aura"
            )

        prompt = (
            f"{style_tag}. UNDISPUTED CENTERPIECE MVP PROTAGONIST (2x larger in foreground): {hero_vis}, {ult_en_hint}. "
            f"{allies_bg_en}while in the lower corners and periphery his overwhelmed enemies ({defeated_en}) are being sent flying and cut down by his attack shockwave. "
            f"Extreme visual hierarchy making the center hero the unmistakable #1 MVP superstar of the battlefield, "
            f"blazing volumetric god-rays, flying sparks, ultra-detailed 8k, strictly NO text, NO letters, NO UI, NO watermarks."
        )
        ult_desc_zh = f"释放 {ult_casts} 次《{ult_zh}》狂砍 {ult_hits} {ult_unit}，" if ult_zh and ult_casts else ""
        scene_zh = (
            f"🔥 独尊 MVP 原画（{cosmetic_label_zh}）：[{pos}号位] {pname} 的【{hero_zh}】（评分 {sc100}/100）霸气独占C位，"
            f"{ult_desc_zh}将 {victims_zh} 斩于马下！"
        )

    if custom_scene.strip():
        prompt = f"{prompt[:920]} Additional specific scene detail requested: {custom_scene.strip()}."
        scene_zh += f" ｜ 定制细节：{custom_scene.strip()}"

    return {
        "prompt": prompt[:1150],
        "scene_summary_zh": scene_zh,
        "tone": "roast" if archetype.startswith("roast") or archetype == "passenger" else "epic",
        "archetype": archetype,
        "hero_zh": hero_zh,
        "player_name": pname,
        "score_100": sc100,
        "victims_zh": victim_zh_list,
        "nemesis_zh": nemesis_zh_list,
    }


def _call_gemini_nano_banana_api(prompt: str, gemini_key: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    使用 Google Gemini Nano Banana (`gemini-nano-banana-2.1`) 生成 16:9 纯净原画。
    优先走速度最快、响应最稳的 `v1beta/models/gemini-nano-banana-2.1:generateContent` (~15s)，
    若不可用再回退 `v1beta/interactions` 或 `gemini-3-pro-image`。
    返回: (data_uri, model_used, error_msg)
    """
    errors: List[str] = []

    # 1. Fast direct generateContent endpoint with gemini-nano-banana-2.1
    for model_candidate in ("gemini-nano-banana-2.1", "nano-banana-pro-preview", "gemini-3-pro-image"):
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_candidate}:generateContent"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": gemini_key,
                    "User-Agent": "DotaAiAnalyst/2.0",
                },
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            for cand in (data.get("candidates") or []):
                for part in ((cand.get("content") or {}).get("parts") or []):
                    inl = part.get("inlineData") or part.get("inline_data")
                    if isinstance(inl, dict) and inl.get("data"):
                        mime = inl.get("mimeType") or inl.get("mime_type") or "image/png"
                        return f"data:{mime};base64,{inl['data']}", model_candidate, None
        except urllib.error.HTTPError as he:
            body_err = ""
            try:
                body_err = he.read().decode("utf-8", errors="ignore")[:240]
            except Exception:
                pass
            errors.append(f"{model_candidate}(generateContent HTTP {he.code}): {body_err}")
        except Exception as e:
            errors.append(f"{model_candidate}(generateContent): {e}")

    # 2. Fallback to Interactions API
    for model_candidate in ("gemini-nano-banana-2.1", "gemini-3-pro-image"):
        try:
            url = "https://generativelanguage.googleapis.com/v1beta/interactions"
            payload = {
                "model": model_candidate,
                "input": [{"type": "text", "text": prompt}],
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": gemini_key,
                    "Api-Revision": "2026-05-20",
                    "User-Agent": "DotaAiAnalyst/2.0",
                },
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            out_img = data.get("output_image")
            if isinstance(out_img, dict) and out_img.get("data"):
                mime = out_img.get("mime_type") or "image/png"
                return f"data:{mime};base64,{out_img['data']}", model_candidate, None

            for item in (data.get("outputs") or []):
                if isinstance(item, dict) and item.get("type") == "image":
                    b64 = item.get("data") or (item.get("image") or {}).get("data")
                    mime = item.get("mime_type") or (item.get("image") or {}).get("mime_type") or "image/png"
                    if b64:
                        return f"data:{mime};base64,{b64}", model_candidate, None
        except Exception as e:
            errors.append(f"{model_candidate}(interactions): {e}")

    return None, None, " | ".join(errors[:2]) if errors else "Gemini Nano Banana 未返回有效图像数据"


def _call_xai_grok_image_api(prompt: str, xai_key: str, base_url: str = "https://api.x.ai/v1") -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    使用服务端已配置的 xAI 图像生成引擎 (`grok-imagine-image-2.0`) 生成高清英雄战斗原画。
    返回: (data_uri, model_used, error_msg)
    """
    try:
        url = f"{base_url.rstrip('/')}/images/generations"
        model_id = "grok-imagine-image-2.0"
        payload = {
            "model": model_id,
            "prompt": prompt,
            "n": 1,
            "response_format": "b64_json",
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {xai_key}",
                "User-Agent": "DotaAiAnalyst/2.0",
            },
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        items = data.get("data") or []
        if items and isinstance(items[0], dict):
            b64 = items[0].get("b64_json")
            mime = items[0].get("mime_type") or "image/jpeg"
            if b64:
                return f"data:{mime};base64,{b64}", model_id, None
        return None, None, "xAI Image API 未返回 b64_json 数据"
    except Exception as e:
        return None, None, str(e)


def call_nano_banana_poster_art(
    report: Optional[Dict[str, Any]],
    player_slot: Optional[int] = None,
    style_mode: str = "auto",
    cosmetic_mode: str = "arcana",
    custom_scene: str = "",
    engine_pref: str = "auto",
    gemini_api_key: str = "",
    xai_api_key: str = "",
    career_member: Optional[Dict[str, Any]] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """
    生成单人本局超燃/处刑海报原画（或生涯本命英雄原画）：
    - 若传入或配置了 `GEMINI_API_KEY`（且 engine_pref != "grok"），优先调用 Google Nano Banana (`gemini-nano-banana-2.1`)；
    - 若尚未配置 `GEMINI_API_KEY`（或选择了内置引擎/自动回退），自动使用服务端已内置的 `grok-imagine-image-2.0` 生成，确保零门槛即点即出图！
    """
    import hashlib

    env_cfg = load_env_llm_config()
    g_key = (env_cfg.get("gemini_api_key") or "").strip()
    x_key = (env_cfg.get("xai_api_key") or "").strip()
    x_base = env_cfg.get("base_url") or "https://api.x.ai/v1"
    if "x.ai" not in x_base:
        x_base = "https://api.x.ai/v1"

    prompt_info = build_dota_poster_art_prompt(
        report=report,
        player_slot=player_slot,
        style_mode=style_mode,
        cosmetic_mode=cosmetic_mode,
        custom_scene=custom_scene,
        career_member=career_member,
    )
    prompt = prompt_info["prompt"]

    # Check disk cache unless force=True
    mid = (report or {}).get("match_id") or "career"
    slot_key = str(player_slot if player_slot is not None else (career_member or {}).get("account_id", "team"))
    provider_tag = "gemini" if (g_key and engine_pref != "grok") else "xai"
    cache_hash = hashlib.md5(f"{mid}:{slot_key}:{style_mode}:{cosmetic_mode}:{provider_tag}:{custom_scene.strip()}".encode("utf-8")).hexdigest()[:12]
    cache_filename = f"poster_art_{mid}_{slot_key}_{cache_hash}.json"

    import cloud_store

    base_dir = os.path.dirname(os.path.abspath(__file__))
    cache_dirs = [os.path.join(base_dir, "reports", "poster_art"), str(cloud_store.get_tmp_reports_dir() / "poster_art")]

    if not force:
        for cdir in cache_dirs:
            cpath = os.path.join(cdir, cache_filename)
            if os.path.exists(cpath):
                try:
                    with open(cpath, "r", encoding="utf-8") as cf:
                        cached_obj = json.load(cf)
                    if cached_obj.get("ok") and cached_obj.get("image_data_url"):
                        cached_obj["cached"] = True
                        return cached_obj
                except Exception:
                    pass

    img_data_url = None
    model_used = None
    err_notes: List[str] = []

    # Try Nano Banana (gemini-nano-banana-2.1) first when gemini_api_key is available and engine_pref != 'grok'
    if engine_pref in ("auto", "nano_banana", "nano_banana_strict") and g_key:
        img_data_url, model_used, g_err = _call_gemini_nano_banana_api(prompt, g_key)
        if g_err:
            err_notes.append(f"Nano Banana 提示: {g_err}")

    # If Nano Banana strictly requested without a Gemini key and no fallback desired:
    if not img_data_url and engine_pref == "nano_banana_strict" and not g_key:
        return {
            "ok": False,
            "need_gemini_key": True,
            "error": "服务端尚未配置 GEMINI_API_KEY，请切换为「智能双擎」或在服务端环境变量中配置。",
            "prompt_info": prompt_info,
        }

    # Fallback or direct call to xAI Grok Imagine 2.0
    if not img_data_url and x_key:
        img_data_url, model_used, x_err = _call_xai_grok_image_api(prompt, x_key, x_base)
        if x_err:
            err_notes.append(f"Grok Imagine 提示: {x_err}")

    if not img_data_url:
        return {
            "ok": False,
            "need_gemini_key": not bool(g_key),
            "error": "；".join(err_notes) if err_notes else "服务端尚未配置可用的生图 API Key。",
            "prompt_info": prompt_info,
        }

    result_obj = {
        "ok": True,
        "cached": False,
        "model": model_used,
        "used_nano_banana": "nano-banana" in str(model_used or "") or "gemini" in str(model_used or ""),
        "has_server_gemini_key": bool(env_cfg.get("gemini_api_key")),
        "image_data_url": img_data_url,
        "prompt": prompt,
        "scene_summary_zh": prompt_info["scene_summary_zh"],
        "tone": prompt_info["tone"],
        "hero_zh": prompt_info["hero_zh"],
        "player_name": prompt_info["player_name"],
    }

    for cdir in cache_dirs:
        try:
            os.makedirs(cdir, exist_ok=True)
            with open(os.path.join(cdir, cache_filename), "w", encoding="utf-8") as cf:
                json.dump(result_obj, cf, ensure_ascii=False)
            break
        except OSError:
            continue

    return result_obj



