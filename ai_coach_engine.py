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

    # --- (C) 推进与建筑伤害审计 ---
    if tdmg >= 6500 or (pos in (1, 2) and tdmg_share >= 45.0 and tdmg >= 3500):
        strengths.append(
            f"推进终结能力极强：单人打出 {tdmg:,} 建筑伤害（包揽全队 {tdmg_share:.0f}% 拆塔量），赢下团战后能迅速将人头优势转化为塔数。"
        )
    elif pos == 1 and tdmg < 1200 and duration_min >= 25:
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
        has_innate_spell_immunity = any(k in hero_name for k in ["主宰", "噬魂鬼"])
        if deaths >= 7 and enemy_total_stuns >= 70 and not has_innate_spell_immunity:
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

    if deaths <= 4 and duration_min >= 30:
        strengths.append(
            f"极高生存容错：{duration_min:.0f} 分钟高强度对抗仅阵亡 {deaths} 次（读秒总计 {dead_min}分{dead_rem_s:02d}秒，仅占全场 {dead_pct:.1f}%），团战站位拉扯极佳。"
        )
    elif deaths >= 8:
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
            f"保持当前 {hero_name} 的刷钱与参战节奏，继续卡死 7/14 分钟经验符和 20 分钟痛苦魔方节点。"
        )

    # 计算胜局贡献点数 (raw_contrib_points) 与凯旋庆功贺词 (praise_talk)
    contrib_points = max(8.0, (mvp_score - 28.0) ** 1.35)
    if hdmg_share >= 28.0:
        contrib_points += 20.0
    elif hdmg_share >= 22.0:
        contrib_points += 11.0
    if tdmg_share >= 40.0 and tdmg >= 3000:
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
    if deaths >= 10:
        contrib_points = max(6.0, contrib_points * 0.72)

    if pos in (1, 2) and hdmg_share >= 26.0:
        praise_talk = f"@{pname} 这把 {hero_name} 火力全开狂轰 {hdmg:,} 伤害（包揽全队 {hdmg_share:.0f}% 输出）+ {tdmg:,} 拆塔，真大腿带飞全场，兄弟们排队敬茶！"
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
    elif rating_score >= 8.8:
        trash_talk = f"@{pname} 这把 {hero_name} 评分 {rating_score} 全队唯一真爹，另外四个兄弟建议自觉排队敬茶！"
    else:
        trash_talk = f"@{pname} 这把 {kills}/{deaths}/{assists} 标准打卡下班，背锅占比 {blame_points:.0f} 点，赢了跟着笑，输了怪队友！"

    return {
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
        "key_teamfights": report.get("key_teamfights"),
        "phases_data": report.get("phases_data"),
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
                "key_item_timings": p.get("key_item_timings"),
                "active_item_uses": {k: v["count"] for k, v in (p.get("active_item_uses") or {}).items()},
                "ability_uses": {a["zh_name"]: a["count"] for a in (p.get("ability_uses_rich") or [])[:6]},
                "hero_execution_audit": p.get("hero_execution_audit"),
                "killed_by": p.get("killed_by_breakdown"),
                "blame_share_pct": p.get("blame_share_pct"),
            }
            for p in own_team
        ],
        "tactical_microscope": {
            "support_vision": ((report.get("deep_forensics") or {}).get("support_vision_by_side") or {}).get(focus_side),
            "stacking_and_smoke": ((report.get("deep_forensics") or {}).get("stacking_and_smoke_by_side") or {}).get(focus_side),
            "laning_mechanics": ((report.get("deep_forensics") or {}).get("laning_mechanics_by_side") or {}).get(focus_side),
            "tp_rotation": ((report.get("deep_forensics") or {}).get("tp_rotation_by_side") or {}).get(focus_side),
        },
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
                "hero_execution_audit": p.get("hero_execution_audit"),
            }
            for p in opp_team
        ],
    }

    system_prompt = (
        "你是懂 Dota 2 高端局细节的开黑老哥，给车队五人做赛后算账复盘。中文，像损友聊天：有数据的问题直接点名说，拒绝空洞套话与重复数据罗列。\n"
        "必须重点结合 tactical_microscope 与 hero_execution_audit 中的硬核细节：\n"
        "1) 英雄本身机制与大招质量：如猛犸两极反转大到几个人（场均命中人数）、哪几波团憋大暴毙、授予力量给主C套了几次；白虎箭命中率；骨法棒子电了谁多少血；剑圣奶棒与无敌斩质量；拉比克偷了什么大招。\n"
        "2) 辅助眼位质量：插眼是过于激进深入还是过于保守缩家？假眼平均存活寿命、哪颗眼刚插下就被秒排、有没有在同一个高台头铁连插死磕。\n"
        "3) 辅助堆野与开雾找节奏：辅助堆了几波野 vs 大哥自己动手堆了几波野？全场开了几次雾、哪波雾抓死人破局、哪波雾撞墙送团。\n"
        "4) 对线期细节：4/5号位有没有拉野消兵、边路3/6/9分钟疗伤莲花抢了几朵、7/14/21分钟智慧经验符被谁吃了、有没有走双生门游走和点灯塔。\n"
        "5) TP 救人及时性：谁在团战第一时间亮 TP 落地救人、谁在队友被干时全程 0 伤害 0 技能挂机旁观、谁全靠死后系统送的免费抚恤 TP 过日子。\n"
        "请严格返回一个 JSON 对象（不要带 Markdown 代码块围栏），结构如下：\n"
        "{\n"
        '  "title": "一句话点透本局胜负关键与最大槽点",\n'
        '  "summary": "整局经济差走势、关键转折点与五人整体表现账本（120-200字）",\n'
        '  "verdict": "有证据的输赢机制及谁最该背锅、谁是真大腿",\n'
        '  "team_practice": "下一局开黑最该统一执行的一个具体配合动作",\n'
        '  "mvp": {"slot": 132, "runner_up_slot": 130, "confidence": "高", "reason": "为何选他当MVP", "comparison": "对比亚军胜在哪里", "evidence": ["数据证据1", "数据证据2"]},\n'
        '  "players": [\n'
        '    {"slot": 132, "headline": "一句犀利判词", "assessment": "结合英雄专属机制(大招命中人数/憋大/Buff覆盖)、对线细节(拉野/莲花/经验符/走门)、眼位进攻防守质量、堆野开雾与TP支援的具体算账", "good": ["亮点1", "亮点2"], "bad": ["问题或待回看1", "问题或待回看2"], "practice": "下一局改进动作"}\n'
        "  ],\n"
        '  "phases": [\n'
        '    {"key": "lane", "label": "前期对线", "time_label": "00:00–10:00", "summary": "本阶段团队判断(含拉野/莲花/圣水符/经验符/走门)", "turning_point": "本阶段关键节点", "players": [{"slot": 132, "assessment": "本阶段表现", "good": ["阶段亮点"], "bad": ["阶段问题"], "focus": "阶段改法"}]},\n'
        '    {"key": "mid", "label": "中期运营", "time_label": "10:00–25:00", "summary": "本阶段团队判断(含开雾找节奏/堆野收矿/眼位进攻防守/TP支援)", "turning_point": "...", "players": [...]},\n'
        '    {"key": "late", "label": "后期决策", "time_label": "25:00–终局", "summary": "本阶段团队判断(含关键大招释放/买活/高地肉山决策)", "turning_point": "...", "players": [...]}\n'
        "  ],\n"
        '  "windows": [\n'
        '    {"time_label": "团战时间段", "title": "这波为什么关键", "detail": "具体技能、伤害、阵亡与得失分析"}\n'
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
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
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
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "response_format": {"type": "json_object"},
                "stream": False,
                "max_tokens": 10000,
            }
            if prov == "xai":
                payload["reasoning_effort"] = "medium"
            req = urllib.request.Request(
                url,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Authorization": f"Bearer {key}",
                },
            )
            with urllib.request.urlopen(req, timeout=180) as resp:
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
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": usr_prompt},
            ],
            "response_format": {"type": "json_object"},
            "stream": False,
            "max_tokens": 3500,
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {key}",
            },
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
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


