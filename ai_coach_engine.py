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
    for k in ("XAI_API_KEY", "XAI_MODEL", "GROK_MODEL", "XAI_BASE_URL", "GEMINI_API_KEY", "OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_BASE_URL"):
        if os.environ.get(k):
            env_vars[k] = os.environ[k]

    if env_vars.get("XAI_API_KEY"):
        return {
            "provider": "xai",
            "api_key": env_vars["XAI_API_KEY"],
            "model_name": env_vars.get("XAI_MODEL") or env_vars.get("GROK_MODEL") or "grok-4.7",
            "base_url": (env_vars.get("XAI_BASE_URL") or "https://api.x.ai/v1").rstrip("/"),
        }
    if env_vars.get("GEMINI_API_KEY"):
        return {
            "provider": "gemini",
            "api_key": env_vars["GEMINI_API_KEY"],
            "model_name": "gemini-3.8-flash",
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
        }
    if env_vars.get("OPENAI_API_KEY"):
        return {
            "provider": "openai",
            "api_key": env_vars["OPENAI_API_KEY"],
            "model_name": env_vars.get("OPENAI_MODEL") or "gpt-4.1",
            "base_url": (env_vars.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/"),
        }
    return {"provider": "", "api_key": "", "model_name": "", "base_url": ""}


def get_llm_status_safe() -> Dict[str, Any]:
    """返回给前端展示的安全模型状态（不含任何密钥值）"""
    cfg = load_env_llm_config()
    if cfg.get("api_key"):
        return {
            "configured": True,
            "provider": cfg["provider"],
            "model": cfg["model_name"],
            "label": f"已接入 {cfg['provider'].upper()} / {cfg['model_name']}",
        }
    return {
        "configured": False,
        "provider": "",
        "model": "",
        "label": "内置录像取证引擎已就绪",
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

    compact_payload = {
        "match_id": report.get("match_id"),
        "mode": report.get("mode_str"),
        "duration": report.get("duration_str"),
        "focus_side": focus_side,
        "user_won": report.get("user_won"),
        "score": report.get("score"),
        "economy_timeline": report.get("economy_timeline"),
        "key_teamfights": [
            {
                "index": tf.get("index"),
                "time": f"{tf.get('start_str', '')}-{tf.get('end_str', '')}",
                "winner": tf.get("winner_zh"),
                "deaths": f"{tf.get('radiant_deaths', 0)}:{tf.get('dire_deaths', 0)}",
                "net_gold_swing": tf.get("net_gold_swing"),
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
                "key_item_timings": (p.get("key_item_timings") or [])[:5],
                "final_items": (p.get("final_items") or [])[:7],
                "aghanims_shard": p.get("aghanims_shard", False),
                "active_item_uses": {k: v["count"] for k, v in (p.get("active_item_uses") or {}).items()},
                "ability_uses": {a["zh_name"]: a["count"] for a in (p.get("ability_uses_rich") or [])[:5]},
                "is_afk_farmer": p.get("is_afk_farmer", False),
                "hero_mechanism_profile": p.get("hero_mechanism_profile"),
                "phoenix_egg_audit": p.get("phoenix_egg_audit"),
                "slark_mechanism_audit": p.get("slark_mechanism_audit"),
                "phase_telemetry": p.get("phase_telemetry"),
                "rating_score_100": int(round((p.get("rating_score") or 0) * 10)),
                "contrib_share_pct": p.get("contrib_share_pct"),
                "blame_share_pct": p.get("blame_share_pct"),
                "top_strength": (p.get("strengths") or [""])[0][:140],
                "top_weakness": (p.get("weaknesses") or [""])[0][:160],
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
                "final_items": (p.get("final_items") or [])[:6],
            }
            for p in opp_team
        ],
    }

    afk_heroes = [p.get("hero_short_zh") for p in own_team if p.get("is_afk_farmer")]
    sorted_own_by_contrib = sorted(own_team, key=lambda x: float(x.get("contrib_share_pct") or 0), reverse=True)
    sorted_own_by_blame = sorted(own_team, key=lambda x: float(x.get("blame_share_pct") or 0), reverse=True)
    top1_hero = sorted_own_by_contrib[0].get("hero_short_zh") if sorted_own_by_contrib else ""
    top2_hero = sorted_own_by_contrib[1].get("hero_short_zh") if len(sorted_own_by_contrib) > 1 else ""
    culprit1_hero = sorted_own_by_blame[0].get("hero_short_zh") if sorted_own_by_blame else ""
    culprit2_hero = sorted_own_by_blame[1].get("hero_short_zh") if len(sorted_own_by_blame) > 1 else ""
    afk_rule_str = (
        f"2) 本局本方存在『前中期刷钱不参战、卖队友4打5、最后几分钟才出山收割面板伤害的毒瘤核心』：{'、'.join(afk_heroes)}。哪怕他最后总伤害或总经济好看，也绝对禁止评为MVP或二号功臣，必须在判词和个人点评里狠狠揭穿他前中期闷头独刷、全靠四个队友4打5负重前行才躺赢的真相！\n"
        if afk_heroes
        else f"2) 若本局落败，头号背锅战犯必须定为『{culprit1_hero}』，二号背锅位定为『{culprit2_hero}』；请严格依据 top_weakness 与机制证据点名批判。\n"
    )

    system_prompt = (
        "你是懂 Dota 2 全 126 英雄核心机制与团队博弈的开黑老哥，给车队五人做赛后算账复盘。全中文输出（严禁夹杂任何英文变量名如 solo_pickoffs/rating_score_100/contrib_share_pct），像损友聊天：拒绝只看伤害/拆塔面板的浅薄分析（尤其是败局全队都没摸到高地时，绝不要怪1号位0建筑伤害），必须严格按照每个英雄的【内置强势期曲线 hero_mechanism_profile.timing_curve_zh 与专属核心机制】深度思考！\n"
        "核心铁律：\n"
        "1) 区分英雄强势期曲线（hero_mechanism_profile）：\n"
        "   - 大后期刷钱收割核（late_hyper_carry，如敌法/美杜莎/幽鬼/TB/猴子/水人/露娜/虚空等）：前期弱势、10-22m避战刷关键装完全合理，绝不要因为中期刷钱少参团而乱骂；但必须重点考核其【25m+ 成型后是否出山接管比赛完成收割（late_harvest_fulfilled vs late_harvest_failed）】！\n"
        "   - 前中期干架节奏核（mid_tempo_brawler，如斯拉克/拍拍熊/帕克/蓝猫/火猫/女王/影魔/哈斯卡等）：10-25m是黄金强势期，严禁闷头当刷子！\n"
        "   - 先手开团肉盾（frontline_initiator）与救人保核辅助（save_healer_support）：考核先手控制承伤转化与救人技能（薄葬/暗箱/禁锢/雪球/无光之盾）兑现度，为团队开团或救人牺牲绝不背死得多的黑锅！\n"
        + afk_rule_str +
        "3) 深度机制铁律：\n"
        "   - 若 1号位（如斯拉克）单带多次无故被抓、拒不出 1,400 金关键魔晶（如斯拉克不出《深海劫掠》导致既救不了被屠夫咬/帕克大的队友、自己也少黑雾叠敏捷 A 不过人）、面对敌方蝴蝶撒旦先知/酒仙不出金箍棒/冰眼、且后期吃满经济却毫无输出，必须一针见血拆穿这三点！\n"
        "   - 若 3号位是凤凰，绝不要无脑喷不出BKB或拆塔少，必须重点审判其《超新星(变蛋)》在团战中成功炸出几次 vs 被打碎几次（团战碎蛋率）、变蛋前是否挂了《烈火精灵》减攻速、以及《烈日炙烤(激光)》是否严重少按！\n"
        "   - 若 2号位是脆皮高爆发炮台（如莉娜/宙斯/火枪/天怒），只要她对线打出优势且倒下前把伤害灌满（高英雄伤害占比、场均每死换3000+伤害），死了也完全尽责（虽死犹荣），必须肯定其炮台输出兑现度，并从团队博弈角度建议大推推等解先知发芽/帕克大的出装可能性。\n"
        f"4) 胜局或队内最佳 MVP 定为『{top1_hero}』，二当家定为『{top2_hero}』。\n"
        "请严格返回一个 JSON 对象（不要带 Markdown 代码块围栏），结构如下：\n"
        "{\n"
        '  "title": "一句话点透本局胜负关键与最大机制败因（20-36字）",\n'
        '  "summary": "从前期对线、中期开雾/单带节奏到后期团战机制博弈的全局复盘摘要（110-160字）",\n'
        '  "verdict": "有理有据的头号战犯/首功、二号背锅/功臣与炮台兑现判词（110-160字）",\n'
        '  "team_practice": "下一局开黑最该统一执行的一个具体团队配合与出装博弈动作（50-80字）",\n'
        '  "mvp": {"slot": 128, "runner_up_slot": 131, "confidence": "高", "reason": "为何选他当MVP/SVP", "comparison": "对比队友胜在哪里", "evidence": ["数据证据1", "数据证据2"]},\n'
        '  "players": [\n'
        '    {"slot": 128, "headline": "一句切中机制要害的判词", "assessment": "结合英雄机制、魔晶/出装选择、单带被抓与前中后期团战作用的80-130字深度点评", "good": ["亮点1", "亮点2"], "bad": ["机制或团队问题1"], "practice": "下一局他在团队里能多做什么的具体改进"}\n'
        "  ],\n"
        '  "windows": [\n'
        '    {"time_label": "团战时间段", "title": "一句刀塔味十足的团战标题", "detail": "60-100字有画面感的团战机制复盘"}\n'
        "  ]\n"
        "}"
    )
    user_prompt = "请为以下比赛证据生成 JSON 复盘：\n" + json.dumps(compact_payload, ensure_ascii=False)

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
            with urllib.request.urlopen(req, timeout=55) as resp:
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
            url = f"{b_url.rstrip('/')}/chat/completions"
            # On xAI, grok-4.7 is a deep reasoning model that takes 50-120s (exceeding Vercel's 60s timeout).
            # Use grok-4.20-0309-non-reasoning for fast (~14s), deterministic JSON generation under grok-4.7 display label.
            api_model = "grok-4.20-0309-non-reasoning" if (prov == "xai" and model in ("grok-4.7", "grok-4.6", "grok-4")) else model
            payload = {
                "model": api_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "response_format": {"type": "json_object"},
                "stream": False,
                "max_tokens": 2800,
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
            with urllib.request.urlopen(req, timeout=50) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            out_txt = data["choices"][0]["message"]["content"]

        # 尝试解析为结构化 JSON 并持久化
        cleaned = out_txt.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
        structured = None
        try:
            structured = json.loads(cleaned)
            if isinstance(structured, dict):
                structured["author"] = f"{prov} / {model}"
                structured["model"] = model
                structured["provider"] = prov
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


