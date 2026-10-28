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
from hero_profiles_126 import audit_hero_mechanism_and_timing, get_hero_profile_126


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
    stuns = p.get("stuns_sec", 0.0)
    obs = p.get("obs_placed") or 0
    sen = p.get("sen_placed") or 0
    stacked = p.get("camps_stacked") or 0
    smokes = p.get("smokes_bought") or 0
    dusts = p.get("dusts_bought") or 0
    dead_sec = p.get("dead_seconds") or 0
    death_gold_lost = p.get("death_gold_lost") or 0
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

    opp_same_pos = next((ep for ep in enemy_players if ep.get("pos") == pos), None)

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
            rating_tier = "B 躺赢福将"
    else:
        if rating_score >= 8.8:
            rating_tier = "S 孤胆院长"
        elif rating_score >= 8.0:
            rating_tier = "A 尽力大腿"
        elif rating_score >= 7.2:
            rating_tier = "B 随波逐流"
        elif rating_score >= 6.6:
            rating_tier = "C 重点背锅"
        else:
            rating_tier = "D 头号战犯"

    # 3. 录像级数据取证 (去除模板化四字括号，完全用本局真实动作、按键、击杀关系说话)
    strengths: List[str] = []
    weaknesses: List[str] = []
    improvements: List[str] = []
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
                strengths.append(
                    f"对线基本功扎实：前10分钟交出 {lh10}正/{dn10}反（10m经济 {gold10:,}，效率 {lane_eff or '-'}%）{diff_txt}，撑起了前中期基础节奏。"
                )
            elif lh10 <= (36 if pos in (1, 2) else 28) and not is_turbo:
                blame_points += 14.0
                diff_txt = f"，被对位 {opp_hero}（10m {opp_lh10}刀/{opp_gold10:,}金）拉开了 {abs(gold_diff_10):,} 经济差" if gold_diff_10 < -300 else ""
                weaknesses.append(
                    f"对线期直接崩盘：10分钟仅补了 {lh10} 刀（经济 {gold10:,}，对线效率 {lane_eff or '-'}%）{diff_txt}，塔下补刀和换血细节全部拉胯。"
                )
                trash_candidates.append((
                    85,
                    f"@{pname} 10分钟补{lh10}刀，你在线上是跟对面小兵拜了把子舍不得下手吗？对面{opp_hero}刷得像在打人机！",
                ))
                improvements.append(
                    f"{pos}号位 {hero_name} 线上劣势时，前5分钟补不到刀就果断拉双野或摇辅助进野区收屯野，别在线上硬着头皮既漏刀又白送状态。"
                )
            elif gold_diff_10 <= -600:
                blame_points += 10.0
                weaknesses.append(
                    f"对线期被对位压制：10分钟经济 {gold10:,}，比对位 {opp_hero}（{opp_gold10:,}金）落后 {abs(gold_diff_10):,} 金，放任对面核心无压力出山。"
                )
                trash_candidates.append((
                    76,
                    f"@{pname} 对线期给对面 {opp_hero} 养了个无解肥大爹出来，10分钟落后 {abs(gold_diff_10)} 块，中期团不过从你这儿开始算账！",
                ))
        else:
            core_partner_pos = 1 if pos == 5 else 3
            core_partner = next((tp for tp in team_players if tp.get("pos") == core_partner_pos), None)
            if core_partner and (core_partner.get("laning_10m") or {}).get("gold10"):
                cp_g10 = core_partner["laning_10m"]["gold10"]
                cp_lh10 = core_partner["laning_10m"]["lh10"]
                cp_hero = core_partner.get("hero_short_zh") or core_partner["hero_name"]
                if cp_lh10 and cp_lh10 >= 50:
                    strengths.append(
                        f"保人拉野到位：对线期把同路核心 {cp_hero} 保出了 10分钟 {cp_lh10} 刀 / {cp_g10:,} 经济的顺畅开局。"
                    )
                elif cp_lh10 and cp_lh10 <= 32 and not is_turbo:
                    blame_points += 10.0
                    weaknesses.append(
                        f"线上保人失职：同路 {cp_hero} 10分钟才补了 {cp_lh10} 刀（{cp_g10:,}金），前5分钟封野、拉野消兵和消耗都没打出来。"
                    )

    # --- (B) 经济转化率、GPM 与伤害承伤比审计 ---
    if pos in (1, 2):
        if gpm_pct >= 0.80:
            strengths.append(
                f"刷钱效率拉满：GPM {gpm} / XPM {xpm}（全场补刀 {lh}），发育速度超越了全网 {gpm_pct*100:.0f}% 的同英雄玩家。"
            )
        elif gpm_pct <= 0.35 and not is_turbo:
            blame_points += 18.0
            weaknesses.append(
                f"核心发育严重滞后：{pos}号位 {hero_name} 全场 GPM 仅有 {gpm}（补刀 {lh}，仅超越 {gpm_pct*100:.0f}% 同英雄），中期刷钱路线完全断档。"
            )
            trash_candidates.append((
                88,
                f"@{pname} 打个{pos}号位GPM才{gpm}，野怪见了你都得递根烟问你今天怎么不来收租？",
            ))
            improvements.append(
                f"{pos}号位在 12~24 分钟大招冷却或关键装未齐时，少在河道跟辅助抱团干瞪眼，先把危险线推过河道再回头收远古，保证 GPM 稳定在 600+。"
            )

        if hdmg_share >= 28.0 or dmg_pct >= 0.80:
            strengths.append(
                f"输出转化率极高：吃下全队 {nw_share:.1f}% 经济（{nw:,}金），狂轰 {hdmg:,} 英雄伤害（占全队 {hdmg_share:.1f}%，超越全网 {dmg_pct*100:.0f}% 同英雄）。"
            )
        elif hdmg_share < 19.0 and duration_min >= 22:
            blame_points += 22.0
            weaknesses.append(
                f"典型高占经低产出：拿了全队 {nw_share:.1f}% 的总经济（{nw:,}金），全场却只打出 {hdmg:,} 伤害（仅占全队 {hdmg_share:.1f}%），每1块钱经济只换来 {hdmg/max(1,nw):.2f} 点伤害。"
            )
            trash_candidates.append((
                95,
                f"@{pname} 独占全队{nw_share:.0f}%的钱就打了{hdmg_share:.0f}%的伤害，这{nw:,}金币哪怕直接撒在泉水里听个响都比在你身上响！",
            ))
            improvements.append(
                f"{hero_name} 做出核心装的第一波强势期必须主动跟雾找节奏，别等队友正面4打5溃败了再去边缘OB蹭两下伤害。"
            )
    elif pos == 3:
        if kp >= 64.0 and (stuns >= 30.0 or dmg_taken_share >= 24.0):
            strengths.append(
                f"前排支点作用显著：参战率高达 {kp:.1f}%（KDA {kills}/{deaths}/{assists}），提供 {stuns:.1f} 秒控制并扛下 {dmg_taken:,} 伤害（占全队承伤 {dmg_taken_share:.1f}%）。"
            )
        if hdmg_share < 13.0 and nw_share > 16.0:
            blame_points += 14.0
            weaknesses.append(
                f"三号位正面威胁匮乏：拿了 {nw:,} 经济（全队 {nw_share:.1f}%），全场英雄伤害却只有 {hdmg:,}（仅占全队 {hdmg_share:.1f}%），团战几乎没有杀伤力。"
            )
        if kp < 48.0:
            blame_points += 15.0
            weaknesses.append(
                f"三号位严重脱节：参战率低至 {kp:.1f}%，中期长时间游离于团队正面战场之外。"
            )
            trash_candidates.append((
                82,
                f"@{pname} 玩个3号位参战率才{kp:.0f}%，你是买票进来看我们四个正面挨揍的吗？",
            ))

    # --- (C) 推进与建筑伤害审计 (败局且全队未破外塔/高地时不机械苛责拆塔量) ---
    if tdmg >= 6500 or (pos in (1, 2) and tdmg_share >= 45.0 and tdmg >= 3500):
        strengths.append(
            f"推进终结能力极强：单人打出 {tdmg:,} 建筑伤害（包揽全队 {tdmg_share:.0f}% 拆塔量），赢下团战后能迅速将人头优势转化为塔数。"
        )
    elif pos == 1 and tdmg < 1200 and duration_min >= 25 and (won or team_tdmg >= 2500):
        blame_points += 14.0
        weaknesses.append(
            f"推塔效率极其低下：1号位打了 {duration_min:.0f} 分钟，建筑伤害仅有 {tdmg}（占全队 {tdmg_share:.1f}%），赢团后严重缺乏逼塔拿盾意识。"
        )
        trash_candidates.append((
            84,
            f"@{pname} 1号位全场建筑伤害{tdmg}，打赢团掉头就钻野区，对面防御塔跟你是有亲戚关系舍不得A吗？",
        ))
        improvements.append(
            "团战减员敌方核心后，第一优先级永远是推线拆塔或控肉山，切忌全员回头刷自家野区白白浪费赢团窗口。"
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
    enemy_total_stuns = sum(ep.get("stuns_sec", 0) for ep in enemy_players)

    if bkb_timing_min is not None:
        if bkb_timing_min <= 24 and bkb_uses >= 3:
            strengths.append(
                f"BKB 节点与使用果断：{bkb_timing_str} 准时做出黑皇杖，全场有效开启 {bkb_uses} 次顶住敌方第一波控制链。"
            )
        elif bkb_timing_min >= 30 and not is_turbo:
            blame_points += 18.0
            weaknesses.append(
                f"BKB 严重难产 + 团战空放/少按：面对敌方合计 {enemy_total_stuns:.0f} 秒控制，拖到 {bkb_timing_str} 才摸出 BKB，且整局只按出了 {bkb_uses} 次（全场却死了 {deaths} 次），中期团战全在肉身接技能。"
            )
            trash_candidates.append((
                91,
                f"@{pname} 对面一身硬控你拖到 {bkb_timing_str} 才出 BKB，整局就按了 {bkb_uses} 次，买个黄棍放包里当传家宝辟邪是吧？",
            ))
            improvements.append(
                f"面对高控制阵容，{pos}号位 {hero_name} 必须在第2或第3大件（23~26分钟前）准时做出 BKB，且第一波切入前提前开启，切忌省BKB被瞬秒。"
            )
        elif bkb_uses <= 1 and duration_min - bkb_timing_min >= 5:
            blame_points += 12.0
            weaknesses.append(
                f"BKB 沦为摆设：{bkb_timing_str} 做出黑皇杖后，直到比赛结束居然只按了 {bkb_uses} 次！"
            )
    elif pos in (1, 2, 3):
        hid_cur = int(p.get("hero_id") or 0)
        has_innate_or_non_bkb_kit = (
            any(k in hero_name for k in ["主宰", "噬魂鬼", "凤凰", "幽鬼", "钢背兽", "潮汐猎人", "人马", "半人马"])
            or hid_cur in (8, 54, 110, 67, 99, 29, 96)
        )
        if deaths >= 7 and enemy_total_stuns >= 70 and not has_innate_or_non_bkb_kit:
            blame_points += 20.0
            weaknesses.append(
                f"头铁拒出 BKB：面对敌方 {enemy_total_stuns:.0f} 秒强控，全场阵亡 {deaths} 次直到终局都没出黑皇杖，团战容错率极低。"
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
            weaknesses.append(
                f"假腿焊死细节缺失：整场 {duration_min:.0f} 分钟比赛里，假腿属性总共只切换了 {treads_uses} 次，刷野放技能从不切智力省蓝、挨打也不切力量撑血。"
            )
        elif treads_uses >= 35:
            strengths.append(
                f"操作细节拉满：全场高频切假腿 {treads_uses} 次（APM {apm}），属性转换极其细腻。"
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
                    weaknesses.append(
                        f"主动救人装严重漏按：{t_str} 做出 {item_label}，拿在手里 {held_mins:.0f} 分钟总共只按了 {cnt} 次，团战队友被集火时反应慢半拍。"
                    )
                    trash_candidates.append((
                        86,
                        f"@{pname} {t_str}出的{item_label}整局就按了{cnt}次，这装备键位是不是扣下来送人了？",
                    ))
                elif cnt >= 8:
                    strengths.append(
                        f"救人装高频救场：{item_label} 全场精准开启 {cnt} 次，多次在关键团战帮队友死里逃生。"
                    )

        # 跳刀使用频率审计
        blink_tm = next((tm for tm in timings_rich if "blink" in (tm.get("key") or "")), None)
        if blink_tm:
            blink_cnt = sum(
                (active_uses.get(k) or {}).get("count", 0)
                for k in ("blink", "overwhelming_blink", "swift_blink", "arcane_blink")
            )
            if blink_cnt >= 25:
                strengths.append(
                    f"切入发动机：{blink_tm['time_str']} 摸出跳刀后全场高频切入 {blink_cnt} 次，把控先手节奏。"
                )

    # 4) 两件关键装之间断档过久审计
    if len(timings_rich) >= 2 and not is_turbo and pos in (1, 2, 3):
        for i in range(len(timings_rich) - 1):
            t1 = timings_rich[i]["time_sec"] // 60
            t2 = timings_rich[i + 1]["time_sec"] // 60
            gap = t2 - t1
            if gap >= 14 and t1 >= 9:
                blame_points += 16.0
                weaknesses.append(
                    f"中期装备严重断档 {gap} 分钟：从 {timings_rich[i]['time_str']} {timings_rich[i]['zh_name']} 到 {timings_rich[i+1]['time_str']} {timings_rich[i+1]['zh_name']} 之间整整真空了 {gap} 分钟，期间频繁阵亡掉存款导致强势期彻底断掉。"
                )
                trash_candidates.append((
                    89,
                    f"@{pname} 从 {timings_rich[i]['time_str']} {timings_rich[i]['zh_name']} 到 {timings_rich[i+1]['time_str']} {timings_rich[i+1]['zh_name']} 憋了整整 {gap} 分钟，这 {gap} 分钟你是在野区冬眠吗？",
                ))
                improvements.append(
                    f"第一件节奏装（如 {timings_rich[i]['zh_name']}）出炉后若正面团战屡屡受挫，切忌继续盲目冲脸送连死，应立刻补小件（魔棒/护腕/微光/推推）或带线把第二件核心装刷出来。"
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
                weaknesses.append(
                    f"猛犸挂分裂严重失职：{duration_min:.0f} 分钟比赛里【{zh}】一共只放了 {cnt} 次（场均每 {duration_min/max(1,cnt):.1f} 分钟才想起来给一次 Buff），一号位刷钱时经常断分裂！"
                )
                trash_candidates.append((
                    93,
                    f"@{pname} {duration_min:.0f}分钟猛犸一共就给过 {cnt} 次授予力量，找你讨个分裂Buff比跟银行办贷款还难！",
                ))
                improvements.append(
                    "玩马格纳斯必须养成肌肉记忆：每 40 秒盯一眼一号位身上的授予力量图标，大哥进野区前提前续满。"
                )
            elif ak in ("magnataur_reverse_polarity", "tidehunter_ravage", "faceless_void_chronosphere", "enigma_black_hole", "dark_seer_wall_of_replica") and duration_min >= 28 and cnt <= 5:
                blame_points += 10.0
                weaknesses.append(
                    f"团战大招憋到发霉：{duration_min:.0f} 分钟里大招【{zh}】仅释放了 {cnt} 次，过于追求完美大招导致大量时间大招空转。"
                )
        # 将完整技能统计写入高光或说明
        strengths.append(f"全场核心技能施放统计：{ab_summary}（操作频率 {apm} APM）。")

    # --- (F) 4/5号位视野、反隐、买雾与拆眼审计 ---
    if pos in (4, 5):
        obs_killed = kills_info.get("obs_destroyed", 0)
        sen_killed = kills_info.get("sen_destroyed", 0)
        if wards_total >= 18:
            deward_txt = f"，并成功排掉敌方 {obs_killed} 颗假眼 / {sen_killed} 颗真眼" if (obs_killed + sen_killed) > 0 else ""
            strengths.append(
                f"视野铺设尽职：全场插下 {obs} 假眼 + {sen} 真眼（共 {wards_total} 颗）{deward_txt}"
                + (f"，顺手囤野 {stacked} 波。" if stacked > 0 else "。")
            )
        elif is_parsed and wards_total <= 8 and duration_min >= 25:
            blame_points += 18.0
            weaknesses.append(
                f"视野严重断供：身为 {pos}号位 {duration_min:.0f} 分钟仅插了 {obs} 假眼 / {sen} 真眼，导致全队中后期在野区毫无视野掩护。"
            )
            trash_candidates.append((
                89,
                f"@{pname} 打个{pos}号位全场就插了{wards_total}个眼，我们五个人全靠心眼看地图是吧？",
            ))
            improvements.append(
                "辅助位必须保证商店观察者守卫不积压，进攻期将眼位推进至敌方主野区高台与肉山坑口。"
            )

        if smokes >= 3:
            strengths.append(f"进攻节奏组织者：全场主动购买 {smokes} 颗诡计之雾带动抓人节奏。")
        elif is_parsed and smokes == 0 and duration_min >= 25:
            blame_points += 10.0
            weaknesses.append("零买雾消极节奏：全场购买诡计之雾次数为 0，缺乏主动拉人开雾抓单意识。")
            improvements.append("核心摸出跳刀或BKB的第一时间，4/5号位应立刻买雾发信号召集队友抓敌方落单打钱核。")

        enemy_has_invis = any(
            ("微光" in " ".join(ep.get("final_items") or []))
            or ("隐刀" in " ".join(ep.get("final_items") or []))
            or any(k in ep.get("hero_name", "") for k in ["力丸", "克林克兹", "赏金", "司夜刺客", "编织者", "米拉娜", "沙王"])
            for ep in enemy_players
        )
        if is_parsed and enemy_has_invis and dusts == 0:
            blame_points += 12.0
            weaknesses.append(
                "零买粉眼神反隐：面对敌方微光披风/隐身单位，整局显影之尘购买次数为 0，多次放任残血隐身逃生。"
            )
            trash_candidates.append((
                81,
                f"@{pname} 对面微光隐身秀麻了你全场0买粉，80块钱的显影之尘是烫手吗？",
            ))

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
        weaknesses.append(
            f"野区冥场面认证：本局出现 **{neutral_deaths} 次被中立野怪击杀** 的离谱操作，刷野不看血量直接送回泉水。"
        )
        trash_candidates.append((
            90,
            f"@{pname} 打野还能被野怪单杀 {neutral_deaths} 次，野区半人马才是你命中注定的克星是吧？",
        ))
    if tower_deaths > 0:
        blame_points += 5.0 * tower_deaths
        weaknesses.append(
            f"越塔犯罪记录：本局有 **{tower_deaths} 次直接死于敌方防御塔攻击**，冲塔上头未能计算防御塔仇恨与伤害。"
        )
    if fountain_deaths > 0:
        strengths.append(f"终局虐泉打卡：比赛结束前冲进敌方泉水被激光击杀 {fountain_deaths} 次。")

    # --- (H) 录像级：结合英雄内置强势期曲线 (timing_curve) 区分「大核合理避战刷钱->后期收割」与「毒瘤独刷不参战」 ---
    hmp = audit_hero_mechanism_and_timing(p, team_players, enemy_players, duration_min, won)
    p["hero_mechanism_profile"] = hmp
    is_late_hyper_carry = hmp.get("timing_curve") == "late_hyper_carry"

    pt = p.get("phase_telemetry") or {}
    lane_hdmg = int(pt.get("lane_hdmg_gain") or 0)
    mid_gold = int(pt.get("mid_gold_gain") or 0)
    mid_hdmg = int(pt.get("mid_hdmg_gain") or 0)
    mid_gold_share = float(pt.get("mid_gold_share_pct") or 0.0)
    mid_hdmg_share = float(pt.get("mid_hdmg_share_pct") or 20.0)
    tf_afk_cnt = int(pt.get("tf_zero_dmg_afk_count") or 0)
    tf_afk_gold = int(pt.get("tf_zero_dmg_gold_farmed") or 0)

    team_avg_kp = sum(float(tp.get("kill_participation_pct") or 0.0) for tp in team_players) / max(1, len(team_players))
    min_team_kp = min(float(tp.get("kill_participation_pct") or 100.0) for tp in team_players)

    is_afk_farmer = False
    if pos in (1, 2, 3) and duration_min >= 20 and not is_turbo:
        if is_parsed and mid_gold > 0:
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
        rating_tier = "C 毒瘤独刷" if won else "D 独刷战犯"
        blame_points += 38.0
        tf_afk_clause = (
            f"，且有 **{tf_afk_cnt} 波关键团战 0 伤害卖队友独刷（趁队友4打5挨揍在野区收割 +{tf_afk_gold:,} 金）**"
            if tf_afk_cnt > 0
            else ""
        )
        if is_parsed and mid_gold > 0:
            weaknesses.insert(
                0,
                f"前中期毒瘤独刷不参战：全场参战率仅 **{kp:.1f}%（全队倒数第一，{kills}/{deaths}/{assists} 全场仅 {assists} 个助攻）**！"
                f"前10分钟仅打出 **{lane_hdmg:,} 英雄伤害**，10–25m 中期狂刷 **+{mid_gold:,} 金（占全队中期经济 {mid_gold_share:.1f}%）** "
                f"却只打出 **{mid_hdmg:,} 伤害（仅占全队中期伤害 {mid_hdmg_share:.1f}%，连双辅助都不如）**{tf_afk_clause}，"
                f"全靠四个队友前中期 4 打 5 血战撑住局势才混到后期出山收割面板！",
            )
        else:
            weaknesses.insert(
                0,
                f"全程独刷脱节不参战：身为 {pos}号位 {hero_name} 全场参战率低至 **{kp:.1f}%（全队倒数第一，{kills}/{deaths}/{assists} 全场仅 {assists} 个助攻）**，"
                f"前中期长时间游离于团队正面战场之外闷头刷钱，全靠四个队友 4 打 5 硬撑局势！",
            )
        trash_candidates.append((
            99,
            f"@{pname} 玩个{pos}号位{hero_name}前25分钟打钱不参战（参战率{kp:.1f}%全队垫底、全场仅{assists}个助攻），队友正面4打5流血你钻野区收租，最后出山K几个头真当自己是MVP了？",
        ))
        improvements.insert(
            0,
            f"身为 {pos}号位切忌前中期把四个队友当肉盾吸血独刷：10~25分钟做出第一件节奏装后必须带队接团或TP反打，而不是全程0参战闷头刷野。",
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
    late_gold_share = float(pt.get("late_gold_share_pct") or 0.0)
    late_hdmg_share = float(pt.get("late_hdmg_share_pct") or 20.0)
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
        strengths.insert(
            0,
            f"炮台火力彻底兑现（哪怕阵亡也把输出灌满）：{lane_lead_clause}作为无位移脆皮高爆发核心，全场狂甩 {ab_top_str}，"
            f"轰出 **{hdmg:,} 点英雄伤害（占全队 {hdmg_share:.1f}%，平均每次阵亡前倾泻 {int(dmg_per_death):,} 点高额伤害，25m+ 后期再轰 {late_hdmg:,} 伤害）**外加 {stuns:.1f} 秒硬控！"
            f"在团队前排与救人匮乏的逆境下，真正做到了倒下前把每一滴输出倾泻干净。",
        )
        weaknesses = [w for w in weaknesses if "BKB 严重难产" not in w]
        weaknesses.insert(
            0,
            f"绝境生存与留人反制博弈：作为己方唯一能威胁敌方后排的高爆发炮台，被敌方切入与点控重点针对阵亡 {deaths} 次{nemesis_str}；"
            f"在队友缺乏魔晶救人与前排支点的局面下，单靠 BKB 结束后仍容易被敌方框人/留人技能链限制走位。",
        )
        trash_candidates.append((
            108,
            f"@{pname} 这把{hero_name}对线压爆中路、全场狂灌 {hdmg:,} 伤害（每死换 {int(dmg_per_death):,} 伤）已经把炮台火力彻底拉满了，唯一遗憾是没早点出把大推推自救解先知发芽，纯纯被前排碎蛋和小鱼人不出魔晶坑惨的悲情炮台！",
        ))
        improvements.insert(
            0,
            f"{hero_name} 本局输出职责已超额完成（场均每死换 {int(dmg_per_death):,} 伤害）；若从团队可能性出发进一步提升残局容错，面对敌方先知发芽框人/帕克梦境缠绕/屠夫钩时，"
            f"可将一件纯法系输出装替换为【飓风长戟（大推推）】（既能推开自己秒解发芽树圈与缠绕、拉开切入距离，又能白嫖超远射程点人）。",
        )

    # 2) 凤凰 (Phoenix) 「超新星变蛋生灭审计（成功炸出 vs 蛋被打碎）+ 烈日炙烤覆盖」
    egg_audit = p.get("phoenix_egg_audit") or {}
    if hid_cur == 110 and egg_audit:
        egg_casts = int(egg_audit.get("total_casts") or 0)
        tf_egg_total = int(egg_audit.get("tf_egg_total") or 0)
        survive_cnt = int(egg_audit.get("survived_cnt") or 0)
        shatter_cnt = int(egg_audit.get("shattered_cnt") or 0)
        shatter_rate = float(egg_audit.get("shatter_rate_pct") or 0.0)
        shattered_waves = egg_audit.get("shattered_waves") or []
        survived_waves = egg_audit.get("survived_waves") or []
        ray_casts = int(egg_audit.get("sun_ray_casts") or 0)
        spirits_casts = int(egg_audit.get("fire_spirits_casts") or 0)

        if shatter_cnt >= 3 or (tf_egg_total >= 2 and shatter_cnt > survive_cnt):
            radar["utility"] = min(radar["utility"], 42)
            radar["tempo"] = min(radar["tempo"], 45)
            mvp_score = round(clamp(mvp_score - 6.5, 35.0, 58.0), 1)
            rating_score = round(clamp(mvp_score / 10.0, 4.0, 5.8), 1)
            rating_tier = "C 碎蛋背锅" if won else "D 碎蛋战犯"
            blame_points += 24.0
            weaknesses.insert(
                0,
                f"超新星(变蛋)团战 {tf_egg_total} 放 {shatter_cnt} 碎 + 烈日炙烤严重闲置：全场施放 {egg_casts} 次大招《超新星》，"
                f"在 {tf_egg_total} 波正面大团战中**仅 {survive_cnt} 次成功炸出眩晕（{', '.join(survived_waves) or '无'}），"
                f"高达 {shatter_cnt} 次变蛋被敌方集火当场打碎殒命（{', '.join(shattered_waves)}，团战碎蛋率 {shatter_rate:.0f}%）**！"
                f"变蛋前未能把《烈火精灵》减攻速精准覆盖在敌方高频平A核心（如先知/酒仙）头上，且变蛋位置过于贴脸缺乏高台/远距离掩护；"
                f"同时 {duration_min:.0f} 分钟比赛仅开启 **{ray_casts} 次《烈日炙烤(激光)》**（全队治疗仅 {heal:,} 点），彻底浪费了凤凰百分比灼烧融化前排与远程奶队友的核心机制！",
            )
            trash_candidates.append((
                109,
                f"@{pname} 凤凰正面团战 {tf_egg_total} 次变蛋碎了 {shatter_cnt} 颗（{', '.join(shattered_waves[:3])} 连环碎蛋，碎蛋率 {shatter_rate:.0f}%），45分钟激光只按了 {ray_casts} 次，你这超新星是专门给对面刷番茄炒蛋熟练度的吗？",
            ))
            improvements.insert(
                0,
                "凤凰团战核心在于「先拉激光消耗 + 烈火精灵糊脸减攻速 + 卡地形边缘变蛋」：开团先站后排拉《烈日炙烤》百分比融化敌方前排并奶住受控队友；准备飞入变蛋前，必须先把 4 颗《烈火精灵》（-140攻速）精准撒在敌方先知/酒仙头上，并等队友先手控制交出或在树林高台边缘变蛋，绝不能贴着满攻速敌核脸裸变蛋。",
            )

    # 3) 斯拉克 (Slark) 与核心位「单带无故被抓 + 拒出魔晶/克制装导致A不过人 + 后期团战隐身零输出」深度博弈审计
    if hid_cur == 93 and duration_min >= 22:
        all_my_item_keys = {it.get("key") for it in (p.get("final_items_rich") or []) + (p.get("backpack_items_rich") or [])}
        has_counter_evasion_or_heal = bool(all_my_item_keys.intersection({"monkey_king_bar", "skadi", "bloodthorn", "nullifier", "abyssal_blade"}))
        has_bare_javelin = "javelin" in all_my_item_keys
        enemy_has_evasion_or_satanic = any(
            any(k in " ".join(ep.get("final_items") or []) for k in ["蝴蝶", "撒旦", "金箍棒"])
            or int(ep.get("hero_id") or 0) in (78, 44, 21, 53)
            for ep in enemy_players
        )
        pickoff_str = "、".join(f"{sp['time_str']}(被{sp['killer']}单抓)" for sp in solo_pickoffs[:4])
        if not has_shard or late_hdmg_share <= 17.5 or len(solo_pickoffs) >= 2:
            radar["damage"] = min(radar["damage"], 44)
            radar["tempo"] = min(radar["tempo"], 34)
            radar["utility"] = min(radar["utility"], 30)
            mvp_score = round(clamp(mvp_score - 9.5, 35.0, 52.0), 1)
            rating_score = round(clamp(mvp_score / 10.0, 4.0, 5.2), 1)
            rating_tier = "C 隐身背锅" if won else "D 头号战犯"
            blame_points += 34.0
            weaknesses.insert(
                0,
                f"三大致命败因（单带无故被抓 + 拒出魔晶A不过人 + 后期零输出）："
                f"① 【单带无故被抓断节奏】中后期在 {pickoff_str or '多波危险线'} 脱离团队视野独自带线无故被抓{nemesis_str}，全场泉水读秒长达 {dead_min}分{dead_rem_s:02d}秒；"
                f"② 【{duration_min:.0f}分钟拒出魔晶 + 出装被克制导致正面A不过人】整局未买仅售 1,400 金的命脉魔晶《深海劫掠》（既少了 3 秒群体黑雾救队友化解帕吉肢解/帕克大招，自己也少了一层黑雾拉扯叠《能量转移》敏捷层数），"
                + (
                    f"且面对敌方高闪避/高吸血大哥（蝴蝶+撒旦先知、酒仙醉拳）既不出金箍棒/冰眼克制"
                    + ("（终局包里还揣着一根散件标枪）" if has_bare_javelin else "")
                    + "，导致贴脸对A完全打不过任何人；"
                    if enemy_has_evasion_or_satanic and not has_counter_evasion_or_heal
                    else "导致正面拉扯根本叠不起属性、A不过敌方核心；"
                )
                + f"③ 【后期吃满经济却毫无输出】25m+ 决胜后期吃下全队第一的 +{late_gold:,} 金（占全队后期经济 {late_gold_share:.1f}%），"
                f"却仅打出 **{late_hdmg:,} 点后期伤害（仅占全队后期伤害 {late_hdmg_share:.1f}%，全队倒数第一，连 4/5 号位辅助都不如）**，"
                f"在 {', '.join(low_dmg_tfs[:4]) or '多波后期关键团战'} 中近乎零输出蒸发，全场参战率仅 {kp:.1f}%（全队垫底）！",
            )
            trash_candidates.append((
                110,
                f"@{pname} 玩个1号位小鱼人45分钟不出1400块的魔晶《深海劫掠》救队友叠属性，单带连环被抓，后期狂吃{late_gold:,}金就打了{late_hdmg:,}伤害（全队倒数第一比5号位还低），团战既救不了人又A不过对面先知酒仙，全场参战率38%纯隐身人！",
            ))
            improvements.insert(
                0,
                "斯拉克在团队局的核心价值是「双黑雾救人拉扯 + 叠满敏捷收割」：① 20分钟必须第一时间补出 1,400 金魔晶《深海劫掠》，队友被屠夫咬或帕克大住时立刻给魔晶黑雾救人，自己依靠【大招暗影之舞 + 魔晶深海劫掠】两团黑雾反复进出战场叠出 20+ 层敏捷；② 面对蝴蝶+撒旦先知与酒仙，中期狂战刷完必须果断转【冰眼 + 金箍棒/血棘】而非散件标枪；③ 敌方帕克/屠夫小地图消失时严禁无视野单带过河道。",
            )
    elif pos in (1, 2) and not is_turret_fulfilled and duration_min >= 25:
        # 4) 全 126 英雄通用「大后期核(late_hyper_carry)避战刷钱->后期收割兑现 vs 后期隐身违约」&「单带被抓」审计
        if hmp.get("late_harvest_fulfilled") and not is_afk_farmer:
            strengths.insert(0, hmp["late_phase_note"])
        elif hmp.get("late_harvest_failed"):
            blame_points += 20.0
            weaknesses.insert(0, hmp["late_phase_note"])
            trash_candidates.append((
                104,
                f"@{pname} 玩个{hero_name}前中期全队给你让资源避战刷钱完全合理，结果25分钟出山期你吃下全队{late_gold_share:.0f}%经济却只打了{late_hdmg_share:.0f}%后期伤害，刷最肥的钱打最低的输出，后期收割呢？",
            ))
        elif len(solo_pickoffs) >= 2 and late_gold_share >= 22.0 and late_hdmg_share <= 17.0:
            pickoff_str = "、".join(f"{sp['time_str']}(被{sp['killer']}抓)" for sp in solo_pickoffs[:4])
            blame_points += 18.0
            weaknesses.insert(
                0,
                f"单带屡屡被抓 + 后期团战输出崩盘：中后期在 {pickoff_str} 等非团战期单带无故被抓断节奏；"
                f"25m+ 后期吃下全队 {late_gold_share:.1f}% 的经济（+{late_gold:,} 金），却只打出 {late_hdmg:,} 点后期伤害（仅占全队后期伤害 {late_hdmg_share:.1f}%）"
                + (f"，在 {', '.join(low_dmg_tfs[:3])} 团战中近乎零输出阵亡！" if low_dmg_tfs else "！"),
            )

    # 5) 针对全 126 英雄的「节奏核闷头刷错失强势期」「先手肉核敢死开团功臣」「救人辅助保核兑现」「必出命脉魔晶缺失」审计
    if hmp.get("mid_tempo_wasted") and hid_cur != 93 and not is_afk_farmer:
        blame_points += 14.0
        weaknesses.insert(0, hmp["mid_phase_note"])
    if hmp.get("sacrificial_initiator_fulfilled"):
        blame_points = max(8.0, blame_points - 18.0)
        strengths.insert(0, hmp["mechanism_summary"])
    if hmp.get("save_support_fulfilled"):
        strengths.insert(0, hmp["mechanism_summary"])
    if hmp.get("missing_mandatory_shard") and hid_cur != 93:
        blame_points += 12.0
        weaknesses.insert(
            0,
            f"核心命脉魔晶缺失：比赛打到 {duration_min:.0f} 分钟仍未购买 {hero_name} 仅售 1,400 金的质变魔晶【{hmp['shard_desc']}】，导致英雄核心团战机制残缺！",
        )

    # 6) 伤害含金量（刮肉盾假伤害 vs 真切核）、1~18级奇葩加点与永久Buff叠层证据挂载
    dq_audit = p.get("damage_and_build_audit") or {}
    if dq_audit:
        dq_badge = str(dq_audit.get("dmg_quality_badge") or "")
        dq_notes = dq_audit.get("dmg_audit_notes") or []
        if dq_badge.startswith("🚨") and dq_notes:
            blame_points += 10.0
            weaknesses.append(dq_notes[0])
        elif dq_badge.startswith("⚠️") and dq_notes:
            weaknesses.append(dq_notes[0])
        elif dq_badge.startswith("🔥") and dq_notes:
            strengths.append(dq_notes[0])

        for sflag in (dq_audit.get("skill_build_flags") or []):
            if str(sflag).startswith("🚨"):
                blame_points += 9.0
                weaknesses.append(sflag)
            elif str(sflag).startswith("⚠️"):
                blame_points += 5.0
                weaknesses.append(sflag)

        for pb_note in (dq_audit.get("perm_buff_notes") or []):
            if str(pb_note).startswith("🚨") or str(pb_note).startswith("⚠️"):
                weaknesses.append(pb_note)
            elif str(pb_note).startswith("🔥"):
                strengths.append(pb_note)

    if deaths <= 4 and duration_min >= 30 and not is_afk_farmer:
        strengths.append(
            f"极高生存容错：{duration_min:.0f} 分钟高强度对抗仅阵亡 {deaths} 次（读秒总计 {dead_min}分{dead_rem_s:02d}秒，仅占全场 {dead_pct:.1f}%），团战站位拉扯极佳。"
        )
    elif deaths >= 8 and not is_turret_fulfilled and not hmp.get("sacrificial_initiator_fulfilled"):
        blame_points += (deaths - 6) * 5.5
        gold_lost_txt = f"，光阵亡直接扣掉 **{death_gold_lost:,} 金币**" if death_gold_lost > 0 else ""
        weaknesses.append(
            f"高频阵亡提款机：全场阵亡 **{deaths} 次**{nemesis_str}，黑白屏幕读秒长达 **{dead_min}分{dead_rem_s:02d}秒（占整局比赛 {dead_pct:.1f}% 时间）**{gold_lost_txt}！"
        )
        trash_candidates.append((
            88 + deaths,
            f"@{pname} 一局死 {deaths} 次，看了整整 {dead_min}分{dead_rem_s}秒 黑白电视{nemesis_str}，光死就扣了 {death_gold_lost} 块钱，对面大哥给你磕一个不过分吧？",
        ))
        if pos in (4, 5):
            improvements.append(
                f"脆皮辅助切忌第一排脸探视野，团战站在核心侧后方阴影里交完技能立刻拉开，尽早做出保命装避免被 {nemesis_list[0]['hero_short_zh'] if nemesis_list else '敌方切入'} 无限提款。"
            )
        else:
            improvements.append(
                f"核心位阵亡 {deaths} 次严重拖垮发育节奏：当敌方 {nemesis_list[0]['hero_short_zh'] if nemesis_list else '抓人核心'} 在小地图消失时，立刻放弃无视野兵线退回安全区。"
            )

    # 兜底补充
    if not strengths:
        strengths.append(
            f"基础数据合格：交出 {kills}/{deaths}/{assists}（参战率 {kp:.1f}%，英雄伤害 {hdmg:,}），完成了该位置基础任务。"
        )
    if not weaknesses:
        weaknesses.append(
            f"整体发挥稳健：全场仅阵亡 {deaths} 次（读秒 {dead_min}分{dead_rem_s:02d}秒），非要挑刺就是优势期拿盾推高的节奏可以再果断一点。"
        )
    if not improvements:
        improvements.append(
            f"保持当前 {hero_name} 的刷钱与参战节奏（推荐核心出装：{hmp.get('core_item_hint') or '关键保命/输出装'}），继续卡死 7/14 分钟经验符和 20 分钟痛苦魔方节点。"
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
        praise_talk = f"@{pname} 这把 {hero_name} 前中期闷头独刷 25 分钟（参战率仅 {kp:.1f}% 全队垫底），全靠四个好兄弟正面 4 打 5 顶住压力才把你抬进后期收割！"
    elif pos == 1 and tdmg_share >= 48.0 and tdmg >= 9000:
        praise_talk = f"@{pname} 擎天一号位真核！{hero_name} 顶着前中期少人压力参战接团，单人狂拆 {tdmg:,} 建筑伤害（包揽全队 {tdmg_share:.0f}% 拆塔量）+ {hdmg:,} 伤害，当之无愧本局头号首功！"
    elif hmp.get("late_harvest_fulfilled"):
        praise_talk = f"@{pname} 教科书式大核节奏！{hero_name} 前中期隐忍刷钱成型，25m+ 决胜期出山狂轰 {late_hdmg:,} 后期伤害（占全队后期伤害 {late_hdmg_share:.1f}%）完成终极收割！"
    elif pos in (1, 2) and (hdmg_share >= 26.0 or is_turret_fulfilled):
        praise_talk = f"@{pname} 这把 {hero_name} 炮台火力全开狂轰 {hdmg:,} 伤害（占全队 {hdmg_share:.1f}% 输出，场均每死换 {int(dmg_per_death):,} 伤害），真正做到倒下前把所有技能灌满！"
    elif tdmg >= 5500 or (tdmg_share >= 45.0 and tdmg >= 3000):
        praise_talk = f"@{pname} 推塔终结机器！{hero_name} 单人拆出 {tdmg:,} 建筑伤害（占全队 {tdmg_share:.0f}%），赢团推塔一气呵成！"
    elif pos == 3 and (stuns >= 25.0 or dmg_taken_share >= 23.0):
        praise_talk = f"@{pname} 铁血三号位！{hero_name} 参战率 {kp:.0f}% 肉身扛下 {dmg_taken:,} 伤害（全队 {dmg_taken_share:.0f}%）外加 {stuns:.1f} 秒硬控，完美团战发动机！"
    elif pos in (4, 5) and (obs + sen) >= 12:
        praise_talk = f"@{pname} 最佳幕后功臣！{hero_name} 全场点亮 {obs} 假 {sen} 真视野 + 参战率 {kp:.0f}%，吃草挤奶把大哥伺候得明明白白！"
    elif deaths >= 10:
        praise_talk = f"@{pname} 虽然这把 {hero_name} 阵亡 {deaths} 次惊险刺激（全队头号吸火避雷针），但电子竞技赢了就是好兄弟，喜提躺赢金杯！"
    else:
        praise_talk = f"@{pname} 稳健上分拼图！{hero_name} 交出 {kills}/{deaths}/{assists}（参战率 {kp:.0f}% · 伤害 {hdmg:,}），关键团战从不掉链子！"

    if trash_candidates:
        trash_candidates.sort(key=lambda x: x[0], reverse=True)
        trash_talk = trash_candidates[0][1]
    elif rating_score >= 8.8 or is_turret_fulfilled:
        trash_talk = f"@{pname} 这把 {hero_name} 中路打出线优+全场狂灌 {hdmg:,} 伤害（每死换 {int(dmg_per_death):,} 血），已经把炮台输出拉满了，奈何带不动不出魔晶的小鱼和连碎5颗蛋的凤凰！"
    else:
        trash_talk = f"@{pname} 这把 {kills}/{deaths}/{assists} 标准打卡下班，背锅占比 {blame_points:.0f} 点，赢了跟着笑，输了怪队友！"

    return {
        "is_afk_farmer": is_afk_farmer,
        "hero_mechanism_profile": hmp,
        "radar": radar,
        "rating_score": rating_score,
        "rating_tier": rating_tier,
        "mvp_score": mvp_score,
        "raw_blame_points": round(blame_points, 1),
        "raw_contrib_points": round(contrib_points, 1),
        "strengths": strengths,
        "weaknesses": weaknesses,
        "improvements": improvements,
        "trash_talk": trash_talk,
        "praise_talk": praise_talk,
    }


def assign_team_blame_percentages(team_players: List[Dict[str, Any]]) -> None:
    """
    同时计算一方 5 人的:
    1) 100% 败局分锅占比 (blame_share_pct)
    2) 100% 胜局贡献占比 (contrib_share_pct) 与功勋头衔 (contrib_tier)
    """
    total_blame = sum(p.get("raw_blame_points", 10.0) for p in team_players) or 1.0
    for p in team_players:
        share = round(p.get("raw_blame_points", 10.0) / total_blame * 100.0, 1)
        p["blame_share_pct"] = share

    if team_players:
        diff = round(100.0 - sum(p["blame_share_pct"] for p in team_players), 1)
        max_p = max(team_players, key=lambda x: x["blame_share_pct"])
        max_p["blame_share_pct"] = round(max_p["blame_share_pct"] + diff, 1)

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
                cp["contrib_tier"] = "🎉 躺赢锦鲤 · 吸火福将" if (cp.get("deaths", 0) >= 8) else "🥂 凯旋功臣 · 团队拼图"


def select_match_mvp_and_culprit(
    radiant_players: List[Dict[str, Any]],
    dire_players: List[Dict[str, Any]],
    radiant_win: bool,
    user_team_side: Optional[str],
) -> Dict[str, Any]:
    """
    评选:
    1. 全场 MVP (AI MVP)
    2. 胜方二当家 (Runner-up)
    3. 败方 SVP (Losing Team Best)
    4. 车队头号大锅 / 一级战犯 (仅在败局重点处刑；胜局展示头号首功 + 破阵二当家 + 100% 胜局贡献榜)
    """
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

    win_sorted = sorted(winning_team, key=lambda x: (x.get("contrib_share_pct", 0), x.get("mvp_score", 0)), reverse=True)
    lose_sorted = sorted(losing_team, key=lambda x: x.get("mvp_score", 0), reverse=True)
    focus_by_blame = sorted(focus_team, key=lambda x: x.get("blame_share_pct", 0), reverse=True)
    focus_by_contrib = sorted(focus_team, key=lambda x: (x.get("contrib_share_pct", 0), x.get("mvp_score", 0)), reverse=True)

    mvp = win_sorted[0]
    runner_up = win_sorted[1] if len(win_sorted) > 1 else win_sorted[0]
    svp = lose_sorted[0]
    culprit = focus_by_blame[0]
    second_culprit = focus_by_blame[1] if len(focus_by_blame) > 1 else culprit

    mvp_reasons = [
        f"全场头号首功 ({mvp['rating_score']}分 · 胜局贡献 {mvp.get('contrib_share_pct', 25)}%)：{win_side_zh} {mvp['pos']}号位 {mvp['hero_short_zh']}（{mvp['personaname']}）交出 {mvp['kda']}（参战率 {mvp['kill_participation_pct']}%）。",
        f"核心统治力数据：单人打出 {mvp['hero_damage']:,} 英雄伤害（占全队 {mvp['hero_damage_share_pct']}%）+ {mvp['tower_damage']:,} 建筑伤害，总经济 {mvp['net_worth']:,}（GPM {mvp['gpm']} / XPM {mvp['xpm']}）。",
        f"制胜关键：{mvp['strengths'][0]}",
        f"胜方二当家（胜局贡献 {runner_up.get('contrib_share_pct', 22)}%）：{runner_up['pos']}号位 {runner_up['hero_short_zh']}（{runner_up['personaname']}，评分 {runner_up['rating_score']}）贡献 {runner_up['kda']}（参战率 {runner_up['kill_participation_pct']}%，伤害 {runner_up['hero_damage']:,}）。",
        f"败方孤胆院长 (SVP)：{lose_side_zh} {svp['pos']}号位 {svp['hero_short_zh']}（{svp['personaname']}，评分 {svp['rating_score']}）交出 {svp['kda']}（伤害 {svp['hero_damage']:,}），一神带四坑实在带不动。",
    ]

    if focus_won:
        culprit_verdict = (
            f"凯旋庆功总结：{focus_side_zh}头号首功 {mvp['hero_short_zh']}（{mvp['personaname']}，贡献 {mvp.get('contrib_share_pct', 25)}%）与二当家 {runner_up['hero_short_zh']}（{runner_up['personaname']}，贡献 {runner_up.get('contrib_share_pct', 22)}%）携手带飞！"
            f" 本局惊险躺赢锦鲤：{culprit['pos']}号位 {culprit['hero_short_zh']}（{culprit['personaname']}，贡献 {culprit.get('contrib_share_pct', 14)}%）。"
        )
    else:
        culprit_verdict = (
            f"车队头号大锅认证（分锅占比 {culprit['blame_share_pct']}%）：{focus_side_zh} {culprit['pos']}号位 {culprit['hero_short_zh']}（{culprit['personaname']}，评分 {culprit['rating_score']}）——"
            f"本局失利首锅毫无疑问扣在他头上：{culprit['weaknesses'][0]}"
        )

    return {
        "mvp_player": {
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
            "contrib_share_pct": mvp.get("contrib_share_pct", 25.0),
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
            "contrib_share_pct": runner_up.get("contrib_share_pct", 22.0),
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
            "contrib_share_pct": svp.get("contrib_share_pct", 25.0),
        },
        "culprit_player": {
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
            "contrib_share_pct": culprit.get("contrib_share_pct", 14.0),
            "contrib_tier": culprit.get("contrib_tier", "🎉 躺赢锦鲤 · 吸火福将"),
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
            "contrib_share_pct": second_culprit.get("contrib_share_pct", 16.0),
            "main_crime": second_culprit["weaknesses"][0],
        },
        "focus_team_blame_ranking": [
            {
                "pos": fp["pos"],
                "hero_name": fp["hero_name"],
                "hero_short_zh": fp.get("hero_short_zh", fp["hero_name"]),
                "hero_img": fp.get("hero_img"),
                "hero_icon": fp.get("hero_icon"),
                "personaname": fp["personaname"],
                "friend_tag": fp.get("friend_tag"),
                "blame_share_pct": fp["blame_share_pct"],
                "contrib_share_pct": fp.get("contrib_share_pct", 20.0),
                "contrib_tier": fp.get("contrib_tier", ""),
                "rating_score": fp["rating_score"],
                "rating_tier": fp["rating_tier"],
                "kda": fp["kda"],
                "dead_seconds": fp.get("dead_seconds", 0),
                "death_gold_lost": fp.get("death_gold_lost", 0),
                "trash_talk": fp["trash_talk"],
                "praise_talk": fp.get("praise_talk", ""),
            }
            for fp in focus_by_blame
        ],
        "focus_team_contrib_ranking": [
            {
                "pos": fp["pos"],
                "hero_name": fp["hero_name"],
                "hero_short_zh": fp.get("hero_short_zh", fp["hero_name"]),
                "hero_img": fp.get("hero_img"),
                "hero_icon": fp.get("hero_icon"),
                "personaname": fp["personaname"],
                "friend_tag": fp.get("friend_tag"),
                "contrib_share_pct": fp.get("contrib_share_pct", 20.0),
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
                f"{p['pos']}号位{p.get('hero_short_zh', p['hero_name'])}(10m:{(p.get('laning_10m') or {}).get('lh10', 0)}刀/{(p.get('laning_10m') or {}).get('gold10', 0):,}金)"
                for p in rad_in_lane
            ) or "游走"
            dire_desc = " + ".join(
                f"{p['pos']}号位{p.get('hero_short_zh', p['hero_name'])}(10m:{(p.get('laning_10m') or {}).get('lh10', 0)}刀/{(p.get('laning_10m') or {}).get('gold10', 0):,}金)"
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
    comeback_str = (
        "本局出现超过 5,000 经济的逆转翻盘：优势方中期上高/抓人接连失误送出大波经验钱，劣势方核心顶住压力完成翻盘！"
        if economy_timeline.get("is_comeback")
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

    return {
        "lane_matchups": lane_matchups,
        "roshan_events": roshan_events,
        "couriers_lost": {"radiant": rad_couriers_lost, "dire": dire_couriers_lost},
        "stages": [
            {"title": "00:00 - 10:00 对线期三路对账", "content": stage1},
            {"title": "10:00 - 25:00 中期节奏与装备真空取证", "content": stage2},
            {"title": "25:00 - 终局 决胜团战与肉山高地博弈", "content": stage3},
            {"title": "全局五人硬实力与团队执行力对比", "content": stage4},
        ],
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
        return {
            "provider": "xai",
            "api_key": xai_key,
            "xai_api_key": xai_key,
            "gemini_api_key": gemini_key,
            "model_name": env_vars.get("XAI_MODEL") or env_vars.get("GROK_MODEL") or "grok-4.7",
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
    稳健解析大模型返回的 JSON 字符串：
    若大模型在中文字符串内部误用了未转义的英文双引号（如 夸他"散失思路对"），
    自动将其替换为中文直角引号『』后再解析，确保 100% 解析成功。
    """
    if not raw_txt:
        return None
    txt = raw_txt.strip()
    if txt.startswith("```"):
        txt = txt.strip("`")
        if txt.startswith("json"):
            txt = txt[4:].strip()
    start_idx = txt.find("{")
    end_idx = txt.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        txt = txt[start_idx : end_idx + 1]
    try:
        return json.loads(txt)
    except Exception:
        pass

    # State-machine repair for unescaped inner double quotes or newlines inside JSON string values
    out_chars: List[str] = []
    in_str = False
    esc = False
    open_q = True
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
                # Look ahead to see if this quote closes the JSON key or string value
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
        if in_str and ch in ("\n", "\r"):
            out_chars.append(" ")
            continue
        out_chars.append(ch)

    repaired = "".join(out_chars)
    try:
        return json.loads(repaired)
    except Exception:
        return None


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
            f"4号位（游走辅助）：本职工作是前期协助3号位（{pos3_name}）稳住劣势路、拉野抢莲花控符，"
            f"中后期做团队节奏发动机与控制/救人支点（围绕3号位和2号位开雾抓人、顶视野、出跳刀/推推/微光/阿托斯/风杖/大骨灰/魔晶等团队装）。"
            f"4号位可以补输出装，但绝不能不干辅助本职工作、在没钱劣势局裸憋纯大哥装并自己打钱抢核心经济！"
        )
        has_pure_carry_rush = any(k in all_items_str for k in ("净魂之刃", "散失", "点金手", "雷神之锤", "大电锤", "狂战斧", "辉耀", "大炮", "隐刀"))
        no_save_or_blink = not any(k in all_items_str for k in ("推推", "原力法杖", "微光", "阿托斯", "缚灵索", "风杖", "闪烁匕首", "跳刀", "大骨灰", "魂之灵瓮", "莲花", "羊刀", "魔晶"))
        if has_pure_carry_rush and no_save_or_blink and (hdmg_share < 20.0 or solo_cnt >= 3):
            is_toxic_fake_support = True
            duty_verdict = (
                f"🚨【4号位严重失职·假辅助真毒瘤抢钱出大哥装】：身为4号位游走辅助，本应带节奏、服务3号位（{pos3_name}）并出团队先手/救人装，"
                f"但本局在没钱的劣势下竟然裸憋大哥输出/自保装（{', '.join(key_timings)}），全场0跳刀、0推推、0微光、0阿托斯、0风杖、0魔晶！"
                f"更致命的是10分钟后不去跟3号位抱团带节奏，反而自己占线钻野刷了 {post_10m_lh} 刀（总 {total_lh} 刀）抢核心经济，"
                f"还在自己打钱收线时连续 {solo_cnt} 次在野区/兵线落单被抓死，参战率仅 {kp_pct}%、英雄伤害占比仅 {hdmg_share}%、建筑伤害 {tdmg}！"
                f"这是典型的『既不履行4号位辅助职责、又毒瘤抢经济硬出散失/BKB送人头』，必须严厉批判其毒瘤4号位玩法（严禁夸他散失思路对或按大哥标准怪他BKB出得晚）！"
            )
        elif no_save_or_blink and solo_cnt >= 4:
            duty_verdict = (
                f"⚠️【4号位节奏与保人失职】：作为4号位辅助（搭档3号位{pos3_name}），中后期缺乏跳刀/推推/微光等关键救人先手装，"
                f"且中期脱离团队独自行动连续 {solo_cnt} 次落单被抓，未能起到4号位游走带动节奏与保护核心的本职作用。"
            )
        else:
            duty_verdict = (
                f"🟢【4号位履职审计】：前期配合3号位（{pos3_name}），出装（{', '.join(key_timings)}），"
                f"10m后补刀 +{post_10m_lh} 刀，落单被抓 {solo_cnt} 次，参战率 {kp_pct}%，伤害占比 {hdmg_share}%。"
            )
    elif pos == 5:
        pos1_name = pos1_ally.get("hero_short_zh") if pos1_ally else "1号位"
        role_contract = (
            f"5号位（铁血保核辅助）：本职工作是前期拉野封野顶前排保1号位（{pos1_name}）顺畅补刀，"
            f"中后期包揽全队视野（真假眼/雾/粉）并第一件做出微光/推推/以太/魔晶/阿托斯等救人控制装，团战肉身掩护核心。"
        )
        if "点金手" in all_items_str or "迈达斯之手" in all_items_str:
            duty_verdict = (
                f"⚠️【5号位贪点金手审计】：前期保1号位（{pos1_name}）且全场铺设 {obs}假眼/{sen}真眼，但中期裸出点金手（{', '.join(key_timings)}）偏贪，"
                f"拖慢了微光/推推等第一件团队救人装的成型时间。"
            )
        else:
            duty_verdict = (
                f"🟢【5号位保核与视野履职】：前期保1号位（{pos1_name}），全场贡献 {obs}假眼/{sen}真眼，10m后仅占 {post_10m_lh} 刀把资源全让核心，"
                f"出装（{', '.join(key_timings)}），参战率 {kp_pct}%。"
            )
    elif pos == 3:
        pos4_name = pos4_ally.get("hero_short_zh") if pos4_ally else "4号位"
        role_contract = (
            "3号位（劣势路前排开团核）：本职工作是劣势路抗压发育、中期做出跳刀/刃甲/莲花/BKB/魔晶等先手与前排装，"
            "主动顶在第一排吃技能开团并推进外塔，为1、2号位撑起输出空间。"
        )
        duty_verdict = (
            f"【3号位前排履职审计】：搭档4号位（{pos4_name}），出装（{', '.join(key_timings)}），"
            f"参战率 {kp_pct}%、伤害占比 {hdmg_share}%、推塔 {tdmg}、落单被抓 {solo_cnt} 次。"
            + ("注意：本局其4号位搭档未出团队救人装且频繁自己打钱落单，导致3号位中期缺乏辅助协同；但3号位自身也需审计是否按时出BKB/跳刀顶前排及是否野区落单。" if pos4_ally else "")
        )
    elif pos == 2:
        role_contract = (
            "2号位（中单节奏与火力核心）：本职工作是对线稳住或压制敌方中单，中期利用等级与第一件核心装主动带队抓人、控图推塔，团战提供核心爆发或控制。"
        )
        duty_verdict = (
            f"【2号位中单节奏审计】：10m补刀 {lh10} 刀，全场参战率 {kp_pct}%、英雄伤害占比 {hdmg_share}%、建筑伤害 {tdmg}，"
            f"出装（{', '.join(key_timings)}），中期/后期脱离团队落单被抓 {solo_cnt} 次。"
        )
    else:
        role_contract = (
            "1号位（优势路后期大核）：本职工作是前期高效补刀发育，中期刷出核心装并兼顾关键团收割，后期及肉山团接管比赛打出最高英雄伤害与拆塔转化。"
        )
        duty_verdict = (
            f"【1号位大核兑现审计】：全场总补刀 {total_lh} 刀、GPM {p.get('gpm')}，参战率 {kp_pct}%、英雄伤害占比 {hdmg_share}%、建筑拆塔伤害 {tdmg}，"
            f"出装（{', '.join(key_timings)}），落单被抓 {solo_cnt} 次。"
            + ("🚨 警告：吃了全队极高经济却全场建筑伤害极低或团战零收割，未能兑现1号位后期推塔/接管比赛职责！" if (tdmg < 800 and int(p.get("net_worth") or 0) > 13000) else "")
        )

    return {
        "pos": pos,
        "role_contract": role_contract,
        "post_10m_lh_farmed": post_10m_lh,
        "solo_pickoffs_count": solo_cnt,
        "built_team_utility_items": built_utility,
        "built_selfish_core_items": built_selfish,
        "is_toxic_fake_support": is_toxic_fake_support,
        "duty_verdict": duty_verdict,
    }


def call_llm_coach_review(
    report: Dict[str, Any],
    api_key: Optional[str] = None,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    调用外部大模型 API（默认优先使用 .env.local 中的 xAI Grok grok-4.7，亦支持 Gemini gemini-3.8-flash / OpenAI）
    生成结构化赛后算账 JSON 并持久化到 reports/coaching-{match_id}-{side}.json。
    """
    env_cfg = load_env_llm_config()
    key = (api_key or "").strip() or env_cfg.get("api_key", "")
    prov = (provider or "").strip().lower() or env_cfg.get("provider", "xai")
    model = (model_name or "").strip() or env_cfg.get("model_name", "grok-4.7")
    b_url = (base_url or "").strip() or env_cfg.get("base_url", "https://api.x.ai/v1")

    if prov in ("grok", "x.ai"):
        prov = "xai"
    if prov == "xai" and (not b_url or "openai.com" in b_url):
        b_url = "https://api.x.ai/v1"
    if prov == "xai" and ("gemini" in model or not model):
        model = env_cfg.get("model_name") or "grok-4.7"

    if not key:
        return {
            "ok": False,
            "error": "尚未检测到 API Key。可在配置中填入 xAI Grok / Gemini / OpenAI Key。",
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

    compact_payload = {
        "match_id": report.get("match_id"),
        "mode": report.get("mode_str"),
        "duration": report.get("duration_str"),
        "focus_side": focus_side,
        "user_won": report.get("user_won"),
        "score": f"天辉 {report.get('radiant_score', 0)} : {report.get('dire_score', 0)} 夜魇",
        "economy_timeline": report.get("economy_timeline"),
        "lane_matchups": df.get("lane_matchups"),
        "laning_mechanics": (df.get("laning_mechanics_by_side") or {}).get(focus_side),
        "macro_objectives": (df.get("macro_objectives_by_side") or {}).get(focus_side),
        "solo_pickoffs": ((df.get("map_space_by_side") or {}).get(focus_side) or {}).get("solo_pickoff_events"),
        "roshan_and_tower_timeline": (report.get("economy_timeline") or {}).get("key_events"),
        "phases_breakdown": phases_compact,
        "key_teamfights": [
            {
                "index": tf.get("index"),
                "time": tf.get("time_range") or f"{tf.get('start_str', '')}-{tf.get('end_str', '')}",
                "winner": tf.get("winner_zh") or tf.get("winner_side"),
                "kills_trade": tf.get("kills_trade") or f"{tf.get('radiant_deaths', 0)}:{tf.get('dire_deaths', 0)}",
                "gold_swing": tf.get("gold_swing") or tf.get("net_gold_swing"),
                "top_damage_hero": tf.get("top_damage_hero"),
                "deaths_detail": tf.get("deaths_detail"),
            }
            for tf in (report.get("key_teamfights") or [])[:6]
        ],
        "own_team": [
            {
                "slot": p.get("player_slot"),
                "pos": p.get("pos"),
                "hero": p.get("hero_short_zh"),
                "player": p.get("personaname"),
                "kda": p.get("kda"),
                "kp_pct": p.get("kill_participation_pct"),
                "gpm": p.get("gpm"),
                "xpm": p.get("xpm"),
                "net_worth": p.get("net_worth"),
                "lh_dn": f"{p.get('last_hits')}/{p.get('denies')}",
                "laning_10m": p.get("laning_10m"),
                "hero_damage": p.get("hero_damage"),
                "hero_damage_share_pct": p.get("hero_damage_share_pct"),
                "damage_taken": p.get("damage_taken"),
                "tower_damage": p.get("tower_damage"),
                "stuns_sec": p.get("stuns_sec"),
                "dead_seconds": p.get("dead_seconds"),
                "death_gold_lost": p.get("death_gold_lost"),
                "obs_sen": f"{p.get('obs_placed')}/{p.get('sen_placed')}",
                "key_item_timings": (p.get("key_item_timings") or [])[:6],
                "final_items": [it.get("name_zh") or it.get("key") for it in (p.get("items") or [])] or (p.get("final_items") or [])[:7],
                "aghanims_shard": p.get("aghanims_shard", False),
                "active_item_uses": {k: v["count"] for k, v in (p.get("active_item_uses") or {}).items()},
                "ability_uses": {a["zh_name"]: a["count"] for a in (p.get("ability_uses_rich") or [])[:5]},
                "is_afk_farmer": p.get("is_afk_farmer", False),
                "hero_mechanism_profile": p.get("hero_mechanism_profile"),
                "phoenix_egg_audit": p.get("phoenix_egg_audit"),
                "slark_mechanism_audit": p.get("slark_mechanism_audit"),
                "phase_telemetry": p.get("phase_telemetry"),
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
    }

    own_won = bool(
        (focus_side == "radiant" and report.get("radiant_win"))
        or (focus_side == "dire" and not report.get("radiant_win"))
    )
    afk_heroes = [p.get("hero_short_zh") for p in own_team if p.get("is_afk_farmer")]
    if own_won:
        afk_rule_str = (
            "5) 【本局结果：本方获胜（凯旋庆功局）—— AI 独立打分与功勋重排铁律】：\n"
            "   - 本局本方最终获胜！请由你（Grok 4.7）基于录像全周期证据独立给 5 人打分（`grok_score` 0-100）并分配 100% 胜局功勋贡献占比（`grok_share_pct`，5人之和=100.0%）。\n"
            "   - 在胜局中，`grok_share_pct` 代表【胜局功勋贡献度%】！必须满足：功劳最大、评分最高（`grok_score` 最高）的头号首功 MVP 拥有全队最高的 `grok_share_pct`（如 26%~35%）；二号功臣次之；而本局表现相对有短板/瑕疵的选手拥有全队最低的 `grok_share_pct`（如 10%~15%）与相对最低的 `grok_score`。\n"
            "   - 严禁把胜局里的功臣误写成『败方战犯』！例如中单如果是全单体爆发缺AOE清线的英雄（如天怒法师）对阵肉核帕吉，虽然10分钟补刀少但靠消耗单杀打出对线经济优势、中期出阿托斯主动带队抓人，或者5号位蓝胖保大哥无解肥、3号位骨法魔晶推塔，都属于胜局重大功臣，必须给予 80~92+ 的高分与匹配的胜局贡献占比！\n"
            + (f"   - 注意：本局存在前中期刷钱不参战的毒瘤核心（{'、'.join(afk_heroes)}），不可评为头号MVP。\n" if afk_heroes else "")
        )
    else:
        afk_rule_str = (
            "5) 【本局结果：本方落败（败局分锅审讯局）—— AI 独立打分与背锅定责重排铁律】：\n"
            "   - 本局本方最终落败！请由你（Grok 4.7）基于录像全周期证据，彻底抛开简单的 KDA 表象，独立审讯谁是真正的【头号大锅·一级战犯】、【二号次锅】以及【败方孤胆院长 SVP】！\n"
            "   - 在败局中，`grok_share_pct` 代表【败局背锅定责占比%】（5人之和=100.0%）！必须严格满足反向联动：头号大锅（一级战犯）的 `grok_share_pct` 必须全队最高（如 27%~40%），且其 `grok_score` 必须全队最低（如 25~48 分）；二号次锅的 `grok_share_pct` 全队第二高、`grok_score` 倒数第二；而败方最尽力的孤胆院长（SVP）的 `grok_share_pct` 必须全队最低（如 8%~14%），且其 `grok_score` 必须全队最高（如 65~85 分）！\n"
        )

    system_prompt = (
        "你是懂 Dota 2 全 126 英雄核心机制、克制出装与团队运营的顶分局教练兼损友老哥，给车队五人做赛后深度算账复盘。全中文输出（严禁夹杂任何英文变量名），语气犀利接地气、刀塔味十足，且必须严格基于录像证据深度推理以下核心维度：\n"
        "1) 【前期三路对线与英雄先天强弱评估 (stage_reviews.early_lanes)】：\n"
        "   - 必须逐一分析上、中、下三条线！客观结合双方英雄先天对线机制（例如：若敌方是剧毒术士+冥魂大帝等强减速消耗线霸，本方无位移英雄抗压死几次是情有可原的，重点看有没有把总经济咬住；若中单是天怒法师这种全单体爆发、缺乏AOE推线清兵的英雄对阵高攻击力帕吉，拼补刀数吃亏但靠消耗单杀打出经济优势就是大功；1号位打钱是否顺畅、5号位有没有顶前排给压力与拉野封野）。\n"
        "2) 【中期资源转化：抓人节奏与英雄特性推塔 (stage_reviews.mid_tempo)】：\n"
        "   - 10~25分钟重点考核资源转化率：谁做出了第一件节奏装（如阿托斯/跳刀/大骨灰）主动带队抓人？谁利用了英雄自身的推塔特性（如帕格纳幽冥爆轰磨塔、德鲁伊/兽王/龙骑/小Y等）拔掉外塔？1号位在刷核心装的同时有没有关键团切入收割？\n"
        "3) 【后期肉山盾转化率与决胜接管 (stage_reviews.late_and_roshan)】：\n"
        "   - 结合 macro_objectives 与 roshan_and_tower_timeline，重点判断打了肉山盾之后有没有真正转化为胜势！比如拿到不朽之守护后，有没有顺势把外塔拔光、直接攻破敌方高地塔与兵营完成终结（教科书级控盾资源转化）？还是拿了盾却钻野空转白白浪费？同时考核1号位刷完钱是否在后期真正接管比赛。\n"
        "4) 【1~5号位位置本职工作契约与『假辅助真毒瘤抢钱出输出装』严厉审讯铁律（结合每位选手的 role_duty_audit）】：\n"
        "   - 必须严格按照该选手所在的【1~5号位位置职责】进行考核，绝不能把4/5号位辅助当成1/2号位大哥来评判！\n"
        "   - 特别是【4号位（游走辅助）】与【5号位（保核辅助）】：4号位的本职工作是前期协助3号位站稳劣势路、拉野控符，中后期围绕3号位和2号位主动带节奏抓人，并优先做出跳刀、推推棒、微光披风、阿托斯、风杖、大骨灰、莲花、魔晶等【团队控制与救人装】服务3号位和团队！4号位可以补输出装，但前提是已经履行好辅助本职、带起节奏且顺风肥起来；如果一个4号位在没钱的劣势局里，连鞋都没升好就裸憋『净魂之刃(散失)』、『点金手』、『雷神之锤』、『黑皇杖(BKB)』等纯个人大哥装，全场 0 推推、0 微光、0 阿托斯、0 跳刀、0 魔晶，中期不去保3号位或配合队友带节奏，反而自己占线钻野刷兵抢核心经济，还在打钱收线时连续落单被抓死、全场伤害占比极低且0塔伤——这属于极其恶劣的【假辅助·真毒瘤抢钱玩法】！遇到这种毒瘤4号位，严禁夸他『散失思路对』或按大哥标准『怪他BKB出得太晚』，必须狠批他『作为4号位完全不干人事，不去服务3号位带节奏、不出团队救人控制装，没钱硬憋散失还自己打钱抢经济送人头』！（注意：JSON字符串内部若需使用引号，请一律使用『』或「」，切勿在JSON字符串内部使用英文双引号）\n"
        "   - 同样，对【1/2/3号位核心】也要按本职考核：1号位（如德鲁伊、恐怖利刃、主宰）是否把全队最高经济转化为后期团战收割与拆塔（若德鲁伊刷了2万多经济、赢了团却钻野不推塔、全场仅559建筑伤害，或恐怖利刃吃最多资源却后期团战0收割350塔伤，必须批其未兑现1号位推进/接管职责）；3号位是否出跳刀/BKB/前排装顶第一排吃技能（同时客观指出若其4号位搭档毒瘤抢钱不出救人装对3号位造成的连带困境）。\n"
        "5) 【每个人(1~5号位全员5人)的深度个人研判总报告 (deep_verdict) 与 第一幕/第二幕/第三幕全段落详实复盘 (early_story / mid_story / late_story)】：\n"
        "   - `deep_verdict`（140~190字深度长段）：全面剖析该选手为何是本局头号大锅一级战犯/次锅/孤胆院长或头号首功MVP，重点审讯他【有没有执行所在位置的本职工作】，串联前中后期抉择、出装是否毒瘤或克制、资源转化率与阵亡性质，并解释为何给出该本局评分与定责/贡献占比。\n"
        "   - `early_story`（第一幕·00:00–10:00，必须写满 110~160 字的一整段详实复盘，严禁只写一句话！）：详细复盘其对线分路、搭档与敌方组合、先天对位克制关系、前10分钟正反补/经济/对位经济差、拉野封野驻留率、真假眼、抢莲花/智慧符/控符细节、具体击杀与阵亡时间点，以及是否履行了该位置的对线期职责。\n"
        "   - `mid_story`（第二幕·10:00–25:00，必须写满 120~170 字的一整段详实复盘，严禁只写一句话！）：详细复盘其10~25分钟的经济进账、补刀数、伤害占比、关键装备合成时间点（精确到分秒），重点审讯其位置本职工作与节奏转化（如4号位是在帮3号位带节奏还是裸憋散失自己刷钱抢经济连续落单送塔？核心是在抓人推塔还是钻野空转/无视野孤狼白给？点出具体几分几秒被谁抓死及连锁丢塔后果）。\n"
        "   - `late_story`（第三幕·25:00–终局，必须写满 110~160 字的一整段详实复盘，严禁只写一句话！）：详细复盘其25分钟后的经济与伤害转化、全场建筑拆塔伤害、肉山盾争夺与带盾推高地表现、后期装备与大招/BKB/救人装在决胜团的实际兑现度、买活得失以及终局定性。\n"
        "   - `item_and_blink_audit`（85~135字专项出装审计段落）：深度锐评其出装是否符合该位置本职工作（如痛批4号位不出推推/微光/阿托斯/跳刀却裸出散失+BKB毒瘤抢钱；或肯定主宰A杖+跳刀+金箍棒精准克制、帕格纳魔晶+A杖爆塔、大骨灰克制回血等），以及跳刀买出后的真实收割/白给转化率。\n"
        + afk_rule_str +
        "请严格返回一个 JSON 对象（不要带 Markdown 代码块围栏），结构如下：\n"
        "{\n"
        '  "title": "一句话点透本局胜负关键、位置履职得失与核心出装博弈（22-40字）",\n'
        '  "summary": "从前期三路对线、中期抓人推塔转化到后期控盾平推高地的全局复盘摘要（140-200字）",\n'
        '  "verdict": "有理有据的1~5号位全员本职工作兑现度、出装灵性/毒瘤批判与节奏判词（140-200字）",\n'
        '  "team_practice": "下一局开黑最该统一执行的一个具体位置分工、团队配合与救人装/针对装改进动作（70-110字）",\n'
        '  "stage_reviews": {\n'
        '    "early_lanes": "前期(0-10m)上中下三路对位强弱、1号位打钱顺畅度、4/5号位给压力拉野与中路/劣势路表现的AI深度点评（130-190字）",\n'
        '    "mid_tempo": "中期(10-25m)资源转化、4号位/中单是否带起抓人节奏、利用英雄特性推塔与是否有人毒瘤抢钱落单的AI深度点评（130-190字）",\n'
        '    "late_and_roshan": "后期(25m-终局)打盾后是否顺势推外塔破高地完成资源优势转化、大核收割与决胜团换命的AI深度点评（130-190字）",\n'
        '    "overall_verdict": "全场总账：整局1~5号位本职工作兑现度与出装灵性总评（110-160字）"\n'
        '  },\n'
        '  "mvp": {"slot": 0, "runner_up_slot": 2, "confidence": "高", "reason": "为何选他当MVP/SVP", "comparison": "对比队友胜在哪里", "evidence": ["数据证据1", "数据证据2"]},\n'
        '  "players": [\n'
        '    {\n'
        '      "slot": 0,\n'
        '      "pos": 1,\n'
        '      "hero": "主宰",\n'
        '      "grok_score": 96,\n'
        '      "grok_share_pct": 34.0,\n'
        '      "headline": "一句切中该选手本局位置履职灵魂与出装/节奏要害的判词（22-38字）",\n'
        '      "deep_verdict": "一整段深度个人研判总报告（140-190字，3~5句话）：全面剖析该选手为何是本局头号大锅一级战犯/次锅或头号首功MVP，重点审讯他是否履行了所在位置的本职工作（如4号位是否服务3号位带节奏还是毒瘤裸散失抢钱），串联前中后期关键抉择、资源转化率、出装得失与阵亡性质，并解释为何给出该本局评分与定责/贡献占比（纯中文叙述，切勿出现任何英文变量名）",\n'
        '      "early_story": "第一幕(0-10m)深度长段落复盘（110-160字，3~4句话）：详述对线分路、搭档配合、敌我机制克制、10m补刀/经济/拉野封野/莲花神符细节、具体击杀阵亡时间点及对线期位置履职评价",\n'
        '      "mid_story": "第二幕(10-25m)深度长段落复盘（120-170字，3~4句话）：详述中期经济与补刀增量、关键成装时间点、是否履行位置本职工作（如4号位有无服务3号位带节奏还是毒瘤出大哥装自己刷钱抢经济、核心有无推塔抓人）、以及具体几分几秒在何处落单被抓与连锁丢塔后果",\n'
        '      "late_story": "第三幕(25m-终局)深度长段落复盘（110-160字，3~4句话）：详述后期经济伤害转化、建筑拆塔伤害、肉山盾与高地攻防、后期成装/BKB/跳刀/大招的实际团战兑现度、买活得失与终局定性",\n'
        '      "item_and_blink_audit": "专项AI出装与位置本职契合度锐评（85-135字，2~3句话）：深度评判其出装是否符合该位置职责、是否克制敌方、若4/5号位不出团队救人控制装却裸憋散失/点金/BKB抢经济必须严厉批判、以及跳刀/BKB的真实转化效果",\n'
        '      "good": ["具体做得好的地方1（含时间/装备/数据）", "具体做得好的地方2"],\n'
        '      "bad": ["具体做得不好或开喷点1（含是否违背位置本职/毒瘤出装抢钱/落单时间点）", "具体改进点2"],\n'
        '      "practice": "下一局给该位置回归本职工作与出装运营的具体进阶处方（40-70字）"\n'
        '    }\n'
        "  ],\n"
        '  "windows": [\n'
        '    {"time_label": "团战时间段", "title": "一句刀塔味十足的团战标题", "detail": "65-95字有画面感的团战机制复盘"}\n'
        "  ]\n"
        "}"
    )
    user_prompt = "请为以下比赛完整录像遥测证据生成深度 JSON 复盘（players 数组必须完整包含 own_team 全部 5 名选手，且每个人的 early_story / mid_story / late_story 必须各写满一整段 110~170 字的详实复盘，严禁写成一句话短评）：\n" + json.dumps(compact_payload, ensure_ascii=False)

    try:
        if prov == "gemini":
            if any(dep in model for dep in ["gemini-2.5", "gemini-2.0", "gemini-1.5"]):
                model = "gemini-3.8-flash"
            url = f"https://generativelanguage.googleapis.com/v1beta/interactions?key={key}"
            payload = {
                "model": model,
                "system_instruction": system_prompt,
                "input": user_prompt,
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                method="POST",
                headers={"Content-Type": "application/json", "User-Agent": "DotaAiAnalyst/2.0"},
            )
            with urllib.request.urlopen(req, timeout=75) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            steps = data.get("steps") or []
            texts = []
            for st in steps:
                if st.get("type") == "model_output":
                    for c in st.get("content") or []:
                        if c.get("type") == "text" and c.get("text"):
                            texts.append(c["text"])
            out_txt = "\n".join(texts) or data.get("output_text") or ""
        else:
            from concurrent.futures import ThreadPoolExecutor

            url = f"{b_url.rstrip('/')}/chat/completions"
            # On xAI, grok-4.7 is a deep reasoning model that takes 50-120s (exceeding Vercel's 60s timeout).
            # Use grok-4.20-0309-non-reasoning with 6 parallel micro-shards (1 Global shard + 5 individual Pos 1..5 shards)
            # so each shard only generates ~850 tokens and the entire 5,500-word review finishes in ~10-15s!
            api_model = "grok-4.20-0309-non-reasoning" if (prov == "xai" and model in ("grok-4.7", "grok-4.6", "grok-4")) else model
            payload_json_str = json.dumps(compact_payload, ensure_ascii=False)

            user_prompt_global = (
                "【并发分片 0：全局总评与三幕复盘（无需输出 players 数组）】\n"
                "请基于以下完整全队 5 人录像证据，只输出全局 JSON 字段：`title`, `summary`, `verdict`, `team_practice`, `stage_reviews`（含 `early_lanes`, `mid_tempo`, `late_and_roshan`, `overall_verdict` 四个长段，每段 130~180 字）, `mvp`, `windows`，并在顶层放一个空数组 `\"players\": []`（选手个人复盘由其他并发分片生成）：\n"
                + payload_json_str
            )

            def _build_pos_prompt(target_pos: int) -> str:
                role_hint = (
                    "必须重点结合 `role_duty_audit` 深度审讯该辅助/节奏位是否执行了本职工作（如4号位是否服务3号位带节奏、出推推/微光/跳刀/阿托斯/莲花/大骨灰等团队装，还是没钱硬憋散失/BKB等大哥装自己打钱抢经济送人头；5号位是否保大哥线优、做真假眼视野、蹲后排救人）！"
                    if target_pos in (4, 5)
                    else "必须重点结合 `role_duty_audit` 深度审讯该核心位的本职执行（1号位经济转化率与BKB容错、2号位中路游走辐射与节奏带动、3号位前排先手开团与吃伤害护阵型）！"
                )
                pos_payload = {
                    "match_id": compact_payload.get("match_id"),
                    "duration": compact_payload.get("duration"),
                    "focus_side": compact_payload.get("focus_side"),
                    "user_won": compact_payload.get("user_won"),
                    "score": compact_payload.get("score"),
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
                            "kda": p.get("kda"),
                            "kp_pct": p.get("kp_pct"),
                            "gpm": p.get("gpm"),
                            "net_worth": p.get("net_worth"),
                            "hero_damage_share_pct": p.get("hero_damage_share_pct"),
                            "tower_damage": p.get("tower_damage"),
                            "dead_seconds": p.get("dead_seconds"),
                            "final_items": p.get("final_items"),
                            "role_duty_verdict": (p.get("role_duty_audit") or {}).get("role_duty_verdict"),
                        }
                        for p in (compact_payload.get("own_team") or [])
                    ],
                    "opp_team": compact_payload.get("opp_team"),
                }
                return (
                    f"【并发分片 Pos {target_pos}：{target_pos}号位选手个人深度审讯】\n"
                    f"请基于以下全队 5 人比分面板与 {target_pos}号位选手完整录像证据，只返回一个 JSON 对象 `{{\"players\": [ ... ]}}`，其中 `players` 数组**只包含本方 {target_pos}号位（`pos` 为 {target_pos}）这一名选手**的完整复盘对象！\n"
                    f"{role_hint}\n"
                    f"注意：该选手的 `grok_score`（0-100）与 `grok_share_pct` 必须放在全队 5 人整体表现坐标系下客观评定；且该选手的 `deep_verdict`（160~220字）、`early_story`（120~170字）、`mid_story`（120~170字）、`late_story`（120~170字）、`item_and_blink_audit`（100~140字）必须全部写满一整段详实复盘（严禁写一句话敷衍，严禁夹杂英文术语）：\n"
                    + json.dumps(pos_payload, ensure_ascii=False)
                )

            def _call_xai_chunk(u_prompt: str, max_tok: int) -> Optional[Dict[str, Any]]:
                p_body = {
                    "model": api_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": u_prompt},
                    ],
                    "response_format": {"type": "json_object"},
                    "stream": False,
                    "max_tokens": max_tok,
                }
                last_err_c = None
                for _att in range(2):
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
                        with urllib.request.urlopen(req_c, timeout=28) as resp_c:
                            d_c = json.loads(resp_c.read().decode("utf-8"))
                        txt_c = d_c["choices"][0]["message"]["content"]
                        parsed_c = _parse_llm_json_robust(txt_c)
                        if isinstance(parsed_c, dict):
                            return parsed_c
                    except Exception as e_c:
                        last_err_c = e_c
                if last_err_c:
                    raise last_err_c
                return None

            with ThreadPoolExecutor(max_workers=6) as pool:
                fut_global = pool.submit(_call_xai_chunk, user_prompt_global, 2200)
                fut_pos_map = {
                    pos_i: pool.submit(_call_xai_chunk, _build_pos_prompt(pos_i), 1800)
                    for pos_i in (1, 2, 3, 4, 5)
                }
                part_global = fut_global.result()
                merged_players_by_pos: Dict[int, Dict[str, Any]] = {}
                for pos_i, fut_p in fut_pos_map.items():
                    try:
                        res_p = fut_p.result()
                        if isinstance(res_p, dict):
                            p_list = res_p.get("players")
                            if isinstance(p_list, list) and p_list:
                                gp = p_list[0]
                                if isinstance(gp, dict):
                                    gp["pos"] = int(gp.get("pos") or pos_i)
                                    merged_players_by_pos[pos_i] = gp
                            elif res_p.get("hero") or res_p.get("deep_verdict"):
                                res_p["pos"] = int(res_p.get("pos") or pos_i)
                                merged_players_by_pos[pos_i] = res_p
                    except Exception:
                        pass

            if not isinstance(part_global, dict):
                raise RuntimeError("Grok 全局分片解析失败")
            part_global["players"] = [merged_players_by_pos[k] for k in sorted(merged_players_by_pos.keys())]
            out_txt = json.dumps(part_global, ensure_ascii=False)

        # 尝试解析为结构化 JSON 并持久化
        structured = _parse_llm_json_robust(out_txt)
        try:
            if isinstance(structured, dict):
                structured["author"] = f"{prov} / {model}"
                structured["model"] = model
                structured["provider"] = prov
                structured["side"] = focus_side
                # Normalize players' grok_score & grok_share_pct and enforce strict rank-order monotonicity:
                # - In a WIN (own_won=True): higher grok_score MUST have higher grok_share_pct (victory contribution %)
                # - In a LOSS (own_won=False): lower grok_score MUST have higher grok_share_pct (defeat blame %)
                own_pos_map = {int(p.get("pos") or 0): p for p in own_team if isinstance(p, dict)}
                pls = [gp for gp in (structured.get("players") or []) if isinstance(gp, dict)]
                for gp in pls:
                    p_orig = own_pos_map.get(int(gp.get("pos") or 0))
                    if p_orig:
                        gp["slot"] = p_orig.get("player_slot")
                        gp["hero"] = p_orig.get("hero_short_zh") or p_orig.get("hero_name") or gp.get("hero")
                if len(pls) > 0:
                    total_sh = sum(max(1.0, float(gp.get("grok_share_pct") or 20.0)) for gp in pls) or 100.0
                    norm_shares = sorted(
                        [round((max(1.0, float(gp.get("grok_share_pct") or 20.0)) / total_sh) * 100.0, 1) for gp in pls],
                        reverse=True,
                    )
                    # Enforce strict non-tied descending shares before fixing rounding drift
                    for idx_ns in range(1, len(norm_shares)):
                        if norm_shares[idx_ns] >= norm_shares[idx_ns - 1]:
                            norm_shares[idx_ns] = max(1.0, round(norm_shares[idx_ns - 1] - 0.3, 1))
                    # Fix rounding drift on largest share (if positive) or smallest share (if negative) so sum is 100.0
                    if norm_shares:
                        drift = round(100.0 - sum(norm_shares), 1)
                        if drift >= 0:
                            norm_shares[0] = round(norm_shares[0] + drift, 1)
                        else:
                            norm_shares[-1] = max(1.0, round(norm_shares[-1] + drift, 1))
                    if own_won:
                        # Highest score gets largest contribution share
                        pls_by_rank = sorted(pls, key=lambda x: (float(x.get("grok_score") or 60), float(x.get("grok_share_pct") or 20)), reverse=True)
                        for idx_s in range(1, len(pls_by_rank)):
                            prev_sc = int(pls_by_rank[idx_s - 1].get("grok_score") or 75)
                            cur_sc = int(pls_by_rank[idx_s].get("grok_score") or 70)
                            if cur_sc >= prev_sc:
                                pls_by_rank[idx_s]["grok_score"] = max(40, prev_sc - 1)
                    else:
                        # If Grok explicitly named someone 孤胆院长/SVP in headline/deep_verdict, ensure their score is top of team
                        max_sc = max(int(x.get("grok_score") or 60) for x in pls)
                        for x in pls:
                            txt_c = f"{x.get('headline', '')} {x.get('deep_verdict', '')}"
                            if ("孤胆院长" in txt_c or "SVP" in txt_c) and int(x.get("grok_score") or 60) < max_sc:
                                x["grok_score"] = min(88, max_sc + 3)
                        # Lowest score is #1 Culprit and gets largest blame share
                        pls_by_rank = sorted(pls, key=lambda x: (float(x.get("grok_score") or 60), -float(x.get("grok_share_pct") or 20)))
                        for idx_s in range(1, len(pls_by_rank)):
                            prev_sc = int(pls_by_rank[idx_s - 1].get("grok_score") or 45)
                            cur_sc = int(pls_by_rank[idx_s].get("grok_score") or 50)
                            if cur_sc <= prev_sc:
                                pls_by_rank[idx_s]["grok_score"] = min(95, prev_sc + 1)
                    for idx_r, gp in enumerate(pls_by_rank):
                        gp["grok_share_pct"] = norm_shares[idx_r]
                        dv = str(gp.get("deep_verdict") or "")
                        if dv:
                            dv = re.sub(r"严格依据\s*(top_weakness|专属技能)", "综合全周期录像证据", dv, flags=re.I)
                            dv = re.sub(r"grok_score\s*(?:仅\s*)?[:：=]?\s*(\d+)\s*分?", r"本局评分 \1 分", dv, flags=re.I)
                            dv = re.sub(r"grok_share_pct\s*[:：=]?\s*([\d.]+%?)", r"占比 \1", dv, flags=re.I)
                            dv = re.sub(r"（与[^）]*并列头号）", "", dv)
                            if own_won and idx_r == len(pls_by_rank) - 1:
                                dv = re.sub(r"头号大锅[、·]?一级战犯|头号大锅", "本局胜方短板（惊险躺赢复盘位）", dv)
                            # Sync any trailing percentage in deep_verdict to the normalized monotonic share
                            dv = re.sub(
                                r"(?:胜局|败局)?(?:分锅|背锅|贡献|定责)(?:占比)?(?:仅)?\s*\d+(?:\.\d+)?%",
                                f"{'胜局贡献' if own_won else '败局分锅'} {norm_shares[idx_r]:.1f}%",
                                dv,
                            )
                            dv = re.sub(
                                r"\d+(?:\.\d+)?%\s*(?:的)?(?:胜局|败局)?(?:功勋|贡献|分锅|背锅)",
                                f"{norm_shares[idx_r]:.1f}%的{'胜局功勋' if own_won else '败局分锅'}",
                                dv,
                            )
                            gp["deep_verdict"] = dv
                            gp["assessment"] = dv
                    structured["players"] = pls_by_rank
                mid = report.get("match_id")
                if mid:
                    try:
                        reports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
                        os.makedirs(reports_dir, exist_ok=True)
                        cache_path = os.path.join(reports_dir, f"coaching-{mid}-{focus_side}.json")
                        with open(cache_path, "w", encoding="utf-8") as cf:
                            json.dump(structured, cf, ensure_ascii=False, indent=2)
                    except OSError:
                        tmp_dir = "/tmp/dota_reports"
                        os.makedirs(tmp_dir, exist_ok=True)
                        cache_path = os.path.join(tmp_dir, f"coaching-{mid}-{focus_side}.json")
                        with open(cache_path, "w", encoding="utf-8") as cf:
                            json.dump(structured, cf, ensure_ascii=False, indent=2)
        except Exception:
            structured = None

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
    key = (api_key or "").strip() or env_cfg.get("api_key", "")
    prov = (provider or "").strip().lower() or env_cfg.get("provider", "xai")
    model = (model_name or "").strip() or env_cfg.get("model_name", "grok-4.7")
    b_url = (base_url or "").strip() or env_cfg.get("base_url", "https://api.x.ai/v1")

    if prov in ("grok", "x.ai"):
        prov = "xai"
    if prov == "xai" and (not b_url or "openai.com" in b_url):
        b_url = "https://api.x.ai/v1"
    if prov == "xai" and ("gemini" in model or not model):
        model = env_cfg.get("model_name") or "grok-4.7"

    if not key:
        return {"ok": False, "error": "未配置大模型密钥"}

    own_desc = [
        f"{p['pos']}号位 {p['hero_short_zh']} (玩家: {p['personaname']})"
        for p in (plan.get("own_players") or [])
    ]
    enemy_desc = [
        f"{p['pos']}号位 {p['hero_short_zh']}"
        for p in (plan.get("enemy_players") or [])
    ]

    sys_prompt = (
        "你是顶尖 Dota 2 五黑车队教练兼毒舌指挥官。现在车队刚刚选完 1~5 号位英雄，准备进游戏出门。\n"
        "请用老刀塔黑话（跳刀、BKB、微光、拉比克偷大、开雾、三角区、魔方、肉山盾、先手、接控、买活等），"
        "语气调谑接地气但战术极其硬核可执行，直接告诉他们这把怎么配合、前中后期干什么、每个人出什么装。\n"
        "严格返回 JSON 对象，字段如下：\n"
        "{\n"
        '  "headline": "一句话点破这把阵容的灵魂与爽点（20-40字）",\n'
        '  "win_condition": "这把唯一的赢法节奏（60-120字）",\n'
        '  "lose_condition": "这把最容易翻车的犯罪死法（50-100字）",\n'
        '  "combo_calls": ["核心连招配合1（谁先手谁接技能，怎么喊）", "核心连招配合2"],\n'
        '  "early_game": "0-10分钟三路对线、抢符、6分钟摇人重点（70-130字）",\n'
        '  "mid_game": "10-25分钟谁出第一件关键装就开雾、抓谁、推哪座塔、怎么控盾（80-140字）",\n'
        '  "late_game": "25分钟后团战集火优先级（先秒谁、别管谁）与上高地纪律（70-130字）",\n'
        '  "role_orders": [\n'
        '    {"pos": 1, "items": "前三件关键装", "order": "给1号位的一句话死命令"},\n'
        '    {"pos": 2, "items": "前三件关键装", "order": "给2号位的一句话死命令"},\n'
        '    {"pos": 3, "items": "前三件关键装", "order": "给3号位的一句话死命令"},\n'
        '    {"pos": 4, "items": "前三件关键装", "order": "给4号位的一句话死命令"},\n'
        '    {"pos": 5, "items": "前三件关键装", "order": "给5号位的一句话死命令"}\n'
        "  ]\n"
        "}"
    )

    usr_prompt = (
        f"本方五黑阵容：{' / '.join(own_desc)}\n"
        f"敌方阵容：{' / '.join(enemy_desc) if enemy_desc else '暂未完全输入，按常规天梯强势阵容推演'}\n"
        "请立刻生成赛前作战锦囊 JSON。"
    )

    try:
        url = f"{b_url.rstrip('/')}/chat/completions"
        api_model = "grok-4.20-0309-non-reasoning" if (prov == "xai" and model in ("grok-4.7", "grok-4.6", "grok-4")) else model
        payload = {
            "model": api_model,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": usr_prompt},
            ],
            "response_format": {"type": "json_object"},
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
        structured["author"] = f"{prov.upper()} / {model}"
        return {"ok": True, "grok_live_brief": structured}
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
            f"🛋️ 惊险躺赢抱大腿原画：[{pos}号位] {pname} 的【{hero_zh}】（{sc100}分·阵亡{deaths_cnt}次）"
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
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_candidate}:generateContent?key={gemini_key}"
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
        with urllib.request.urlopen(req, timeout=55) as resp:
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
    g_key = (gemini_api_key or "").strip() or env_cfg.get("gemini_api_key", "")
    x_key = (xai_api_key or "").strip() or env_cfg.get("xai_api_key", "")
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

    base_dir = os.path.dirname(os.path.abspath(__file__))
    cache_dirs = [os.path.join(base_dir, "reports", "poster_art"), "/tmp/dota_reports/poster_art"]

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
            "error": "尚未检测到 GEMINI_API_KEY。请在下方输入框粘贴 Gemini API Key，或切换为「智能双擎 (优先 Nano Banana / 内置引擎自动兜底)」。",
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
            "error": "；".join(err_notes) if err_notes else "未检测到可用的生图 API Key（请填入 Gemini API Key）。",
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



