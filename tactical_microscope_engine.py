#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dota 2 录像级深度战术显微镜引擎 (tactical_microscope_engine.py)
专为解决以下 6 大高阶复盘痛点而设计：
1. 英雄本身的专属机制与关键大招/非指向性技能审判（如猛犸大招大到几个人、场均命中、团战憋大死、白虎箭命中率、拉比克偷大招战果、猛犸授予力量覆盖率、帕格纳棒子反伤与输血奶量等）
2. 辅助眼位质量深度定性（进攻深入眼 vs 河道肉山博弈眼 vs 被动防守眼、分阶段眼位姿态诊断、假眼存活寿命、存活<90秒的秒排白给眼、同高台头铁连插）
3. 辅助堆野 vs 大哥自力更生堆野审计（精确到第几分钟堆野、堆出几波几只野怪）
4. 开雾找节奏（Smoke of Deceit）全链路还原（谁买的雾、几点几分开雾、开雾后90秒内是抓死人破局还是逛街空雾/撞墙送团）
5. 对线期细节显微镜（0-10m 拉野区驻留与消兵反补、3/6/9m 疗伤莲花争夺、7/14/21m 智慧经验符归属时间轴、2/4m 河道圣水符、双生门传送走门游走、观察者视野灯塔点亮）
6. TP 救人及时性与团战支援审计（团战窗口亮 TP 落地救人次数、队友被围剿时 0 伤害 0 技能挂机旁观缺席点名、复活买 TP 飞脸上连环死）
"""

from typing import Any, Dict, List, Optional, Tuple
from dota_constants_zh import get_ability_zh, ITEMS_ZH


RUNE_TYPES_ZH: Dict[str, str] = {
    "0": "双倍伤害符",
    "1": "极速神符",
    "2": "幻象神符",
    "3": "隐身神符",
    "4": "恢复神符",
    "5": "赏金神符",
    "6": "奥术神符",
    "7": "圣水神符(中路水符)",
    "8": "智慧神符(经验符)",
    "9": "护盾神符",
}

# 关键团控/爆发大招配置：用于重点审计「放了几次大、累计大到几个人、场均大几人、有没有憋大死」
BIG_ULTIMATE_CATALOG: Dict[str, Dict[str, Any]] = {
    "magnataur_reverse_polarity": {
        "zh": "两极反转 (猛犸大)",
        "type": "aoe_disable_ult",
        "good_avg_hits": 2.0,
        "warn_avg_hits": 1.4,
        "unit_label": "人次",
    },
    "tidehunter_ravage": {
        "zh": "毁灭 (潮汐大)",
        "type": "aoe_disable_ult",
        "good_avg_hits": 2.5,
        "warn_avg_hits": 1.6,
        "unit_label": "人次",
    },
    "faceless_void_chronosphere": {
        "zh": "时间结界 (虚空大罩)",
        "type": "zone_ult",
        "good_avg_hits": 1.5,
        "warn_avg_hits": 1.0,
        "unit_label": "次结界",
    },
    "enigma_black_hole": {
        "zh": "黑洞 (谜团大)",
        "type": "aoe_disable_ult",
        "good_avg_hits": 2.0,
        "warn_avg_hits": 1.2,
        "unit_label": "人次",
    },
    "earthshaker_echo_slam": {
        "zh": "回音击 (牛头大)",
        "type": "aoe_disable_ult",
        "good_avg_hits": 2.2,
        "warn_avg_hits": 1.4,
        "unit_label": "人次",
    },
    "dark_seer_vacuum": {
        "zh": "真空 (黑贤拉)",
        "type": "aoe_disable_ult",
        "good_avg_hits": 2.0,
        "warn_avg_hits": 1.3,
        "unit_label": "人次",
    },
    "dark_seer_wall_of_replica": {
        "zh": "复制之墙 (黑贤墙)",
        "type": "aoe_disable_ult",
        "good_avg_hits": 1.8,
        "warn_avg_hits": 1.1,
        "unit_label": "人次",
    },
    "juggernaut_omni_slash": {
        "zh": "无敌斩 (剑圣大)",
        "type": "multi_slash_ult",
        "good_avg_hits": 7.5,
        "warn_avg_hits": 4.5,
        "unit_label": "刀斩击",
    },
    "crystal_maiden_freezing_field": {
        "zh": "极寒领域 (冰女大)",
        "type": "multi_slash_ult",
        "good_avg_hits": 5.0,
        "warn_avg_hits": 2.5,
        "unit_label": "段冰爆",
    },
    "obsidian_destroyer_sanity_eclipse": {
        "zh": "神智之蚀 (黑鸟大)",
        "type": "aoe_disable_ult",
        "good_avg_hits": 1.8,
        "warn_avg_hits": 1.1,
        "unit_label": "人次",
    },
    "lion_finger_of_death": {
        "zh": "死亡一指 (莱恩大)",
        "type": "single_nuke_ult",
        "good_avg_hits": 0.95,
        "warn_avg_hits": 0.8,
        "unit_label": "人次",
    },
    "lich_chain_frost": {
        "zh": "连环霜冻 (巫妖冰球)",
        "type": "multi_slash_ult",
        "good_avg_hits": 3.5,
        "warn_avg_hits": 2.0,
        "unit_label": "次弹射",
    },
    "ancient_apparition_ice_blast": {
        "zh": "冰晶爆轰 (冰魂大)",
        "type": "multi_slash_ult",
        "good_avg_hits": 3.0,
        "warn_avg_hits": 1.5,
        "unit_label": "段命中",
    },
    "centaur_stampede": {
        "zh": "奔袭冲撞 (人马大)",
        "type": "team_buff_ult",
        "good_avg_hits": 0.5,
        "warn_avg_hits": 0.2,
        "unit_label": "人次",
    },
    "mirana_invis": {
        "zh": "月光暗影 (白虎群体隐身大)",
        "type": "team_buff_ult",
        "good_avg_hits": 0.0,
        "warn_avg_hits": 0.0,
        "unit_label": "次全队隐身",
    },
    "furion_wrath_of_nature": {
        "zh": "自然之怒 (先知大)",
        "type": "aoe_disable_ult",
        "good_avg_hits": 2.2,
        "warn_avg_hits": 1.3,
        "unit_label": "人次",
    },
    "pudge_dismember": {
        "zh": "肢解 (屠夫咬)",
        "type": "multi_slash_ult",
        "good_avg_hits": 3.0,
        "warn_avg_hits": 1.8,
        "unit_label": "段吞噬",
    },
    "mars_arena_of_blood": {
        "zh": "热血竞技场 (玛尔斯框大)",
        "type": "aoe_disable_ult",
        "good_avg_hits": 1.8,
        "warn_avg_hits": 1.1,
        "unit_label": "人次",
    },
    "disruptor_static_storm": {
        "zh": "静态风暴 (萨尔框大)",
        "type": "aoe_disable_ult",
        "good_avg_hits": 2.0,
        "warn_avg_hits": 1.2,
        "unit_label": "人次",
    },
    "puck_dream_coil": {
        "zh": "梦境缠绕 (帕克大)",
        "type": "aoe_disable_ult",
        "good_avg_hits": 2.0,
        "warn_avg_hits": 1.2,
        "unit_label": "人次",
    },
}

# 核心非指向性/控制/绝活小技能目录：用于审计技能命中率（如白虎箭、屠夫钩、猛犸拱、人马踩、鱼人踩等）
SKILLSHOT_CATALOG: Dict[str, Dict[str, Any]] = {
    "mirana_arrow": {"zh": "月神之箭 (摸奖神箭)", "good_pct": 38.0, "warn_pct": 22.0},
    "pudge_meat_hook": {"zh": "肉钩 (出钩命中)", "good_pct": 42.0, "warn_pct": 25.0},
    "magnataur_skewer": {"zh": "巨角冲撞 (猛犸拱人)", "good_pct": 70.0, "warn_pct": 50.0},
    "magnataur_shockwave": {"zh": "震荡波", "good_pct": 65.0, "warn_pct": 40.0},
    "centaur_hoof_stomp": {"zh": "马蹄践踏 (人马踩)", "good_pct": 55.0, "warn_pct": 35.0},
    "slardar_slithereen_crush": {"zh": "鱼人碎击 (大鱼踩)", "good_pct": 55.0, "warn_pct": 35.0},
    "lion_impale": {"zh": "裂地尖刺 (莱恩穿刺)", "good_pct": 85.0, "warn_pct": 65.0},
    "nyx_assassin_impale": {"zh": "穿刺 (小强戳)", "good_pct": 65.0, "warn_pct": 40.0},
    "nyx_assassin_spiked_carapace": {"zh": "尖刺外壳 (开壳反晕)", "good_pct": 55.0, "warn_pct": 35.0},
    "hoodwink_sharpshooter": {"zh": "一击必杀 (松鼠狙击大)", "good_pct": 70.0, "warn_pct": 45.0},
    "hoodwink_acorn_shot": {"zh": "橡果栗鼠", "good_pct": 65.0, "warn_pct": 40.0},
    "dragon_knight_dragon_tail": {"zh": "神龙摆尾 (龙骑拍晕)", "good_pct": 85.0, "warn_pct": 65.0},
    "dragon_knight_fireball": {"zh": "魔晶火球", "good_pct": 80.0, "warn_pct": 50.0},
    "pugna_nether_ward": {"zh": "幽冥守卫 (骨法插棒子电人)", "good_pct": 100.0, "warn_pct": 60.0},
    "pugna_nether_blast": {"zh": "幽冥爆轰 (爆塔/爆人)", "good_pct": 35.0, "warn_pct": 20.0},
    "furion_sprout": {"zh": "发芽 (先知框人)", "good_pct": 70.0, "warn_pct": 45.0},
    "marci_grapple": {"zh": "过肩摔 (玛西背人)", "good_pct": 65.0, "warn_pct": 40.0},
}


def fmt_mmss(sec: Any) -> str:
    s = int(sec or 0)
    if s < 0:
        return f"-{abs(s)//60:02d}:{abs(s)%60:02d}"
    return f"{s//60:02d}:{s%60:02d}"


def classify_ward_map_zone(x: float, y: float, planter_side: str) -> Dict[str, str]:
    """
    根据 Dota 2 真实小地图坐标 (x, y in 64..192) 与插眼方阵营 ('radiant' 或 'dire')：
    1. 给出具体战术点位名称 (zone_zh)
    2. 定性为：
       - 'aggressive' (⚔️ 进攻深入眼：插在敌方半场野区/三角区/高地口)
       - 'river_roshan' (⚖️ 河道/肉山争夺眼：插在河道中线/肉山坑/符点)
       - 'defensive' (🛡️ 防守保护眼：插在己方半场野区/外塔后/高地)
    """
    diag_sum = x + y  # 256 为左下到右上河道中心线；<246 天辉半场，>266 夜魇半场
    # 具体区域命名
    if 246.0 <= diag_sum <= 266.0:
        if x < 118 and y > 134:
            zone_zh = "上路河道 / 肉山坑口"
        elif x > 136 and y < 118:
            zone_zh = "下路河道 / 魔晶区"
        else:
            zone_zh = "中路河道高坡 / 符点"
        territory = "neutral"
    elif diag_sum < 246.0:
        territory = "radiant"
        if x < 104 and y < 104:
            zone_zh = "天辉基地高地 / 三塔内"
        elif x < 108 and y >= 122:
            zone_zh = "天辉上路三角区 / 二塔高台"
        elif x >= 132 and y < 110:
            zone_zh = "天辉下路主野区高台 / 一塔林区"
        else:
            zone_zh = "天辉中路野区腹地"
    else:
        territory = "dire"
        if x > 148 and y > 148:
            zone_zh = "夜魇基地高地 / 三塔内"
        elif x < 124 and y >= 145:
            zone_zh = "夜魇上路主野区高台 / 一塔林区"
        elif x >= 142 and y < 126:
            zone_zh = "夜魇下路三角区 / 二塔高台"
        else:
            zone_zh = "夜魇中路野区腹地"

    if territory == "neutral":
        posture = "river_roshan"
        posture_zh = "⚖️ 河道/肉山博弈眼"
    elif territory == planter_side:
        posture = "defensive"
        posture_zh = "🛡️ 被动防守保护眼"
    else:
        posture = "aggressive"
        posture_zh = "⚔️ 深入敌后进攻眼"

    return {
        "zone_zh": zone_zh,
        "territory": territory,
        "posture": posture,
        "posture_zh": posture_zh,
    }


def build_tactical_microscope(
    match: Dict[str, Any],
    radiant_players: List[Dict[str, Any]],
    dire_players: List[Dict[str, Any]],
    hero_const_by_id: Dict[int, Dict[str, Any]],
    npc_to_hid: Dict[str, int],
) -> Dict[str, Any]:
    """
    构建完整的赛后五大显微镜（支持按 radiant / dire 视角即时切换，同时把个人专属英雄审判挂载到每位 player 上）：
    1. hero_execution_by_side: 英雄专属机制与大招/控制审判（猛犸RP场均人数、团战憋大死、技能命中率、Empower覆盖、骨法棒子反伤等）
    2. support_vision_by_side: 辅助眼位质量诊断（进攻/河道/防守眼比例、分期姿态、假眼平均寿命、存活<90s秒排眼、同高台死磕）
    3. stacking_and_smoke_by_side: 辅助堆野 vs 大哥自堆（精确到分钟）+ 开雾找节奏时间轴与破雾战果定性
    4. laning_mechanics_by_side: 对线期拉野消兵、3/6/9m 疗伤莲花池对比、7/14/21m 智慧经验符归属时间轴、2/4m 圣水符、双生门传送、观察者灯塔
    5. tp_rotation_by_side: TP 救人及时性、团战亮 TP 落地参战、队友阵亡时 0 参战挂机旁观抓包、买 TP 飞脸上连死
    """
    all_formatted = radiant_players + dire_players
    fmt_by_slot = {int(p["player_slot"]): p for p in all_formatted}
    fmt_by_hid = {int(p["hero_id"]): p for p in all_formatted}
    raw_players_list = match.get("players") or []
    raw_by_slot = {int(rp.get("player_slot", 0)): rp for rp in raw_players_list}
    duration_sec = int(match.get("duration") or 2400)
    duration_min = max(1.0, duration_sec / 60.0)
    raw_tfs = match.get("teamfights") or []

    # 预先构建团战索引：每个 slot 在每波团战的技能释放、伤害、死亡、TP使用
    tf_records_by_slot: Dict[int, List[Dict[str, Any]]] = {int(p["player_slot"]): [] for p in all_formatted}
    for tf_idx, tf in enumerate(raw_tfs):
        tf_pl = tf.get("players") or []
        if len(tf_pl) < 10:
            continue
        s_sec = int(tf.get("start") or 0)
        e_sec = int(tf.get("end") or 0)
        rad_deaths = sum(int(tf_pl[i].get("deaths") or 0) for i in range(5))
        dire_deaths = sum(int(tf_pl[i].get("deaths") or 0) for i in range(5, 10))
        if rad_deaths + dire_deaths < 2:
            continue
        for i in range(10):
            rp_i = raw_players_list[i] if i < len(raw_players_list) else {}
            pslot = int(rp_i.get("player_slot", i if i < 5 else i + 123))
            tp_obj = tf_pl[i]
            if pslot in tf_records_by_slot:
                tf_records_by_slot[pslot].append({
                    "tf_num": tf_idx + 1,
                    "start_sec": s_sec,
                    "end_sec": e_sec,
                    "time_range": f"{fmt_mmss(s_sec)}–{fmt_mmss(e_sec)}",
                    "deaths": int(tp_obj.get("deaths") or 0),
                    "damage": int(tp_obj.get("damage") or 0),
                    "healing": int(tp_obj.get("healing") or 0),
                    "ability_uses": tp_obj.get("ability_uses") or {},
                    "item_uses": tp_obj.get("item_uses") or {},
                    "rad_deaths": rad_deaths,
                    "dire_deaths": dire_deaths,
                })

    # =========================================================================
    # 一、英雄本身与关键大招 / 核心技能深度审判 (Hero Execution & Ultimate Audit)
    # =========================================================================
    def analyze_player_hero_execution(fp: Dict[str, Any]) -> Dict[str, Any]:
        pslot = int(fp["player_slot"])
        rp = raw_by_slot.get(pslot, {})
        hid = int(fp["hero_id"])
        h_npc = hero_const_by_id.get(hid, {}).get("npc") or f"npc_dota_hero_{hid}"
        h_prefix = h_npc.replace("npc_dota_hero_", "")
        side_key = "radiant" if pslot < 128 else "dire"
        allies = radiant_players if side_key == "radiant" else dire_players
        enemies = dire_players if side_key == "radiant" else radiant_players

        au: Dict[str, int] = {k: int(v or 0) for k, v in (rp.get("ability_uses") or {}).items()}
        hh: Dict[str, int] = {k: int(v or 0) for k, v in (rp.get("hero_hits") or {}).items()}
        dt: Dict[str, Dict[str, int]] = rp.get("damage_targets") or {}
        di: Dict[str, int] = {k: int(v or 0) for k, v in (rp.get("damage_inflictor") or {}).items()}
        heal_dict: Dict[str, int] = {k: int(v or 0) for k, v in (rp.get("healing") or {}).items()}
        stuns_sec = round(float(rp.get("stuns") or 0.0), 1)
        tf_list = tf_records_by_slot.get(pslot, [])

        ult_audits: List[Dict[str, Any]] = []
        skillshot_audits: List[Dict[str, Any]] = []
        special_insights: List[str] = []
        headline_badges: List[Dict[str, str]] = []

        # 1) 检查该玩家是否拥有关键团控/爆发大招
        for ab_key, cfg in BIG_ULTIMATE_CATALOG.items():
            casts = au.get(ab_key, 0)
            # 只有该英雄本尊或确实释放过的技能才进入审计
            if casts <= 0 and not ab_key.startswith(h_prefix):
                continue
            hits = hh.get(ab_key, 0)
            dmg = di.get(ab_key, 0)
            avg_hits = round(hits / max(1, casts), 2) if casts > 0 else 0.0

            # 统计团战中该大招的释放波数 vs 团战未放大就阵亡的波数
            tf_casts_waves = []
            tf_held_death_waves = []
            for tfr in tf_list:
                c_in_tf = int((tfr["ability_uses"] or {}).get(ab_key, 0))
                if c_in_tf > 0:
                    tf_casts_waves.append(f"{tfr['time_range']}(×{c_in_tf})")
                elif tfr["deaths"] > 0 and tfr["start_sec"] >= 420:
                    # 7分钟后有大招时期在团战阵亡但没放出大招
                    tf_held_death_waves.append(tfr["time_range"])

            # 拆解该大招打在哪些敌方英雄身上
            target_dmg_map = dt.get(ab_key) or {}
            victim_breakdown = []
            for npc_k, d_val in sorted(target_dmg_map.items(), key=lambda x: int(x[1] or 0), reverse=True):
                if int(d_val or 0) <= 0:
                    continue
                vhid = npc_to_hid.get(npc_k, 0)
                vp = fmt_by_hid.get(vhid)
                if vp and vp["side"] != fp["side"]:
                    victim_breakdown.append(f"{vp['hero_short_zh']}({int(d_val):,}伤)")

            if cfg["type"] == "team_buff_ult":
                # 如白虎群体隐身大、人马奔袭大
                freq_min = round(duration_min / max(1, casts), 1)
                grade = "good" if casts >= max(4, int(duration_min / 3.8)) else "warn"
                verdict_text = (
                    f"全场释放 {casts} 次（平均每 {freq_min} 分钟开大 1 次），其中 {len(tf_casts_waves)} 波关键团战开启大招掩护/冲阵。"
                )
                badge_text = f"{cfg['zh']}: {casts}次"
            else:
                if casts == 0:
                    grade = "bad"
                    verdict_text = f"整局比赛 {cfg['zh']} 释放记录为 0！"
                    badge_text = f"{cfg['zh']}: 0释放"
                elif avg_hits >= cfg["good_avg_hits"]:
                    grade = "good"
                    verdict_text = (
                        f"大招质量极高！全场释放 {casts} 次，累计打出 {hits} {cfg['unit_label']}（场均每大 {avg_hits} {cfg['unit_label']}，造成 {dmg:,} 点伤害）"
                        + (f"，在 {', '.join(tf_casts_waves[:4])} 团战完美兑现" if tf_casts_waves else "")
                        + (f"；主要灌伤目标：{'、'.join(victim_breakdown[:3])}" if victim_breakdown else "")
                        + "。"
                    )
                    badge_text = f"{cfg['zh']}: {casts}放/{hits}{cfg['unit_label']}(均{avg_hits})"
                elif avg_hits >= cfg["warn_avg_hits"]:
                    grade = "warn"
                    verdict_text = (
                        f"大招中规中矩：全场释放 {casts} 次，累计 {hits} {cfg['unit_label']}（场均每大 {avg_hits} {cfg['unit_label']}，伤害 {dmg:,}）"
                        + (f"；但在 {', '.join(tf_held_death_waves[:3])} 团战中未放出大招即阵亡！" if tf_held_death_waves else "。")
                    )
                    badge_text = f"{cfg['zh']}: 场均{avg_hits}{cfg['unit_label']}"
                else:
                    grade = "bad"
                    verdict_text = (
                        f"⚠️ 大招严重低效/空大频发：全场放了 {casts} 次《{cfg['zh']}》，累计仅命中 {hits} {cfg['unit_label']}（场均每次大招仅 {avg_hits} {cfg['unit_label']}！）"
                        + (f"，且在 {', '.join(tf_held_death_waves[:3])} 等 {len(tf_held_death_waves)} 波关键团战中没按出大招就躺下读秒！" if tf_held_death_waves else "，多次出现单大或空大脱节！")
                    )
                    badge_text = f"🚨 {cfg['zh']}: {casts}大仅{hits}{cfg['unit_label']}(均{avg_hits})"

            ult_audits.append({
                "ability_key": ab_key,
                "ability_zh": cfg["zh"],
                "casts": casts,
                "hits": hits,
                "avg_hits": avg_hits,
                "unit_label": cfg["unit_label"],
                "damage": dmg,
                "tf_casts_count": len(tf_casts_waves),
                "tf_casts_waves": tf_casts_waves,
                "tf_held_death_count": len(tf_held_death_waves),
                "tf_held_death_waves": tf_held_death_waves,
                "victim_breakdown": victim_breakdown,
                "grade": grade,
                "verdict_text": verdict_text,
            })
            headline_badges.append({"text": badge_text, "tone": grade})
            special_insights.append(verdict_text)

        # 2) 检查核心非指向性/控制小技能命中率 (如白虎箭、猛犸拱、屠夫钩、人马踩、莱恩刺、骨法棒子等)
        for ab_key, scfg in SKILLSHOT_CATALOG.items():
            casts = au.get(ab_key, 0)
            if casts <= 0:
                continue
            hits = hh.get(ab_key, 0)
            dmg = di.get(ab_key, 0)
            hit_pct = round((hits / max(1, casts)) * 100.0, 1)

            if ab_key == "pugna_nether_ward":
                # 骨法棒子特殊计算：插了几根棒子 -> 电击敌方多少次 -> 分别电了谁多少血
                target_dmg_map = dt.get(ab_key) or {}
                zapped = []
                for npc_k, d_val in sorted(target_dmg_map.items(), key=lambda x: int(x[1] or 0), reverse=True):
                    vhid = npc_to_hid.get(npc_k, 0)
                    vp = fmt_by_hid.get(vhid)
                    if vp and vp["side"] != fp["side"] and int(d_val or 0) > 0:
                        zapped.append(f"{vp['hero_short_zh']}({int(d_val):,}血)")
                txt = (
                    f"《幽冥守卫》阵地威慑拉满：全场插下 {casts} 根法力棒，累计电击敌方施法者 {hits} 次，轰出 {dmg:,} 点反伤"
                    + (f"（重点电麻：{'、'.join(zapped[:3])}）！" if zapped else "！")
                )
                skillshot_audits.append({
                    "ability_zh": scfg["zh"],
                    "casts": casts,
                    "hits": hits,
                    "hit_pct": hit_pct,
                    "damage": dmg,
                    "grade": "good" if dmg >= 5000 else "warn",
                    "detail": txt,
                })
                headline_badges.append({"text": f"幽冥棒: {casts}根电{hits}次({dmg:,}伤)", "tone": "good"})
                special_insights.append(txt)
            else:
                grade = "good" if hit_pct >= scfg["good_pct"] else ("warn" if hit_pct >= scfg["warn_pct"] else "bad")
                txt = (
                    f"《{scfg['zh']}》全场施放 {casts} 次，命中敌方英雄 {hits} 人次（有效命中比 {hit_pct}%，造成 {dmg:,} 伤害）"
                    + ("，手感火热！" if grade == "good" else ("，大量技能落空或仅用于清兵逃生。" if grade == "bad" else "。"))
                )
                skillshot_audits.append({
                    "ability_zh": scfg["zh"],
                    "casts": casts,
                    "hits": hits,
                    "hit_pct": hit_pct,
                    "damage": dmg,
                    "grade": grade,
                    "detail": txt,
                })
                headline_badges.append({"text": f"{scfg['zh'].split(' ')[0]}: {casts}放/{hits}中({hit_pct}%)", "tone": grade})
                special_insights.append(txt)

        # 3) 专属英雄机制深度挖掘：
        # 3a. 猛犸 Empower (授予力量) 给全队套了几次、主C靠溅射打了多少伤害
        if hid == 97 or au.get("magnataur_empower", 0) > 0:
            emp_casts = au.get("magnataur_empower", 0)
            emp_per_min = round(emp_casts / duration_min, 2)
            # 统计全队队友靠 magnataur_empower 溅射造成的伤害
            ally_emp_details = []
            total_emp_cleave_dmg = 0
            for ally_p in allies:
                arp = raw_by_slot.get(int(ally_p["player_slot"]), {})
                a_hh = int((arp.get("hero_hits") or {}).get("magnataur_empower", 0))
                a_dt = (arp.get("damage_targets") or {}).get("magnataur_empower") or {}
                a_dmg = sum(int(v or 0) for v in a_dt.values())
                if a_hh > 0 or a_dmg > 0:
                    total_emp_cleave_dmg += a_dmg
                    ally_emp_details.append(f"{ally_p['hero_short_zh']}(溅射{a_hh}刀/{a_dmg:,}伤)")
            emp_tone = "good" if emp_casts >= int(duration_min * 0.75) else "bad"
            emp_msg = (
                f"《授予力量》Buff 覆盖审计：{duration_min:.0f} 分钟比赛共施放 {emp_casts} 次（分均仅 {emp_per_min} 次）"
                + (f"，帮助队友打出 {'、'.join(ally_emp_details)}。" if ally_emp_details else "。")
                + ("⚠️ 作为工具人猛犸，中后期给主C续 Buff 的频率偏低，刷钱与打团前务必保持主C身上常驻分裂！" if emp_tone == "bad" else "")
            )
            special_insights.append(emp_msg)
            headline_badges.append({"text": f"授予力量: {emp_casts}次(分均{emp_per_min})", "tone": emp_tone})

        # 3b. 帕格纳 (Pugna) 生命汲取给队友输血 & 衰老次数
        if hid == 45:
            ally_heals = []
            for npc_k, h_val in sorted(heal_dict.items(), key=lambda x: int(x[1] or 0), reverse=True):
                if "illusion" in npc_k or int(h_val or 0) <= 0:
                    continue
                thid = npc_to_hid.get(npc_k, 0)
                tp_ally = fmt_by_hid.get(thid)
                if tp_ally and tp_ally["side"] == fp["side"] and tp_ally["hero_id"] != 45:
                    ally_heals.append(f"{tp_ally['hero_short_zh']}(+{int(h_val):,}血)")
            dec_casts = au.get("pugna_decrepify", 0)
            drain_casts = au.get("pugna_life_drain", 0)
            pugna_msg = (
                f"《生命汲取 & 衰老》机制审计：全场吸星大法开启 {drain_casts} 次，不仅打出高额法系输出，"
                + (f"还给队友输血续命：{'、'.join(ally_heals[:3])}；" if ally_heals else "")
                + f"全场释放《衰老》{dec_casts} 次救人/加深法伤。"
            )
            special_insights.append(pugna_msg)

        # 3c. 主宰 (Juggernaut) 治疗守卫奶棒次数与治疗量
        if hid == 8:
            ward_casts = au.get("juggernaut_healing_ward", 0)
            fury_casts = au.get("juggernaut_blade_fury", 0)
            ally_heals = []
            self_heal = 0
            for npc_k, h_val in sorted(heal_dict.items(), key=lambda x: int(x[1] or 0), reverse=True):
                if "illusion" in npc_k or int(h_val or 0) <= 0:
                    continue
                thid = npc_to_hid.get(npc_k, 0)
                tp_ally = fmt_by_hid.get(thid)
                if tp_ally and tp_ally["side"] == fp["side"]:
                    if tp_ally["hero_id"] == 8:
                        self_heal += int(h_val)
                    else:
                        ally_heals.append(f"{tp_ally['hero_short_zh']}(+{int(h_val):,}血)")
            jugg_msg = (
                f"《治疗守卫 & 剑刃风暴》审计：全场插下 {ward_casts} 根治疗图腾（为队友治疗 {fp.get('hero_healing',0):,} 点"
                + (f"：{'、'.join(ally_heals[:3])}" if ally_heals else "")
                + (f"，另为自身恢复 {self_heal:,} 点生命" if self_heal > 0 else "")
                + f"），转出 {fury_casts} 次剑刃风暴规避控制并打满 AOE。"
            )
            special_insights.append(jugg_msg)
            headline_badges.append({"text": f"治疗守卫: {ward_casts}根(奶队友{fp.get('hero_healing',0):,})", "tone": "good" if ward_casts >= 10 else "warn"})

        # 3d. 拉比克 (Rubick) 偷到了什么技能、放了几次、砸中几人
        if hid == 86:
            steal_casts = au.get("rubick_spell_steal", 0)
            stolen_used = []
            for k_ab, cnt_ab in sorted(au.items(), key=lambda x: x[1], reverse=True):
                if k_ab.startswith("rubick_") or k_ab in ("ability_capture", "ability_lamp_use", "twin_gate_portal_warp", "plus_high_five", "seasonal_dark_carnival_pie"):
                    continue
                h_ab = hh.get(k_ab, 0)
                d_ab = di.get(k_ab, 0)
                stolen_used.append(
                    f"偷《{get_ability_zh(k_ab)}》放 {cnt_ab} 次"
                    + (f"(中{h_ab}人/{d_ab:,}伤)" if (h_ab > 0 or d_ab > 0) else "")
                )
            rub_msg = (
                f"《技能窃取》实战审计：全场大招偷取 {steal_casts} 次，"
                + (f"成功用出的敌方核心技能包括：{'、'.join(stolen_used[:5])}！" if stolen_used else "但偷到后实际放出有效伤害的技能偏少。")
            )
            special_insights.append(rub_msg)
            headline_badges.append({"text": f"偷技能: {steal_casts}次", "tone": "good" if steal_casts >= 18 else "warn"})

        # 4) 硬控总时长勋章
        if stuns_sec >= 15.0:
            headline_badges.append({
                "text": f"总硬控: {stuns_sec}秒",
                "tone": "good" if stuns_sec >= 40.0 else "warn",
            })
            special_insights.append(f"全场累计对敌方英雄造成 {stuns_sec} 秒硬控眩晕（平均每分钟控制 {stuns_sec/duration_min:.2f} 秒）。")

        # 兜底：如果该英雄没有在上面特殊目录里命中，自动提取其施放次数最多的前 3 个主动技能与命中人次
        if not special_insights:
            top_abs = [
                (k, v) for k, v in sorted(au.items(), key=lambda x: x[1], reverse=True)
                if k not in ("ability_capture", "ability_lamp_use", "twin_gate_portal_warp", "plus_high_five")
            ][:3]
            if top_abs:
                parts = [f"《{get_ability_zh(k)}》释放 {v} 次(命中 {hh.get(k,0)} 人次 / {di.get(k,0):,} 伤害)" for k, v in top_abs]
                special_insights.append("核心技能释放与转化：" + "；".join(parts) + "。")

        res = {
            "pos": fp["pos"],
            "player_slot": pslot,
            "side": side_key,
            "hero_id": hid,
            "hero_short_zh": fp["hero_short_zh"],
            "hero_img": fp["hero_img"],
            "personaname": fp["personaname"],
            "stuns_sec": stuns_sec,
            "ult_audits": ult_audits,
            "skillshot_audits": skillshot_audits,
            "headline_badges": headline_badges[:4],
            "special_insights": special_insights[:4],
        }
        fp["hero_execution_audit"] = res
        return res

    all_hero_exec = [analyze_player_hero_execution(p) for p in all_formatted]

    # =========================================================================
    # 二、辅助眼位质量诊断：进攻眼 vs 防守眼 vs 河道眼、寿命、秒排眼、同高台死磕
    # =========================================================================
    def analyze_side_vision_quality(side_key: str) -> Dict[str, Any]:
        own_players = radiant_players if side_key == "radiant" else dire_players
        opp_players = dire_players if side_key == "radiant" else radiant_players
        side_zh = "天辉" if side_key == "radiant" else "夜魇"

        obs_records: List[Dict[str, Any]] = []
        sen_records: List[Dict[str, Any]] = []
        instant_dewards: List[Dict[str, Any]] = []
        cliff_spots: List[Dict[str, Any]] = []

        posture_counts = {"aggressive": 0, "river_roshan": 0, "defensive": 0}
        phase_posture = {
            "lane": {"label": "对线期 (0-10m)", "aggressive": 0, "river_roshan": 0, "defensive": 0},
            "mid": {"label": "中期节奏 (10-25m)", "aggressive": 0, "river_roshan": 0, "defensive": 0},
            "late": {"label": "后期决战 (25m+)", "aggressive": 0, "river_roshan": 0, "defensive": 0},
        }

        per_support_vision: List[Dict[str, Any]] = []

        for fp in sorted(own_players, key=lambda x: int(x["pos"])):
            rp = raw_by_slot.get(int(fp["player_slot"]), {})
            o_log = rp.get("obs_log") or []
            o_left = rp.get("obs_left_log") or []
            s_log = rp.get("sen_log") or []
            s_left = rp.get("sen_left_log") or []

            p_agg = 0
            p_riv = 0
            p_def = 0
            p_lifespans = []
            p_dewarded_cnt = 0

            for o in o_log:
                ox = float(o.get("x") or 128.0)
                oy = float(o.get("y") or 128.0)
                ot = int(o.get("time") or 0)
                okey = o.get("key")
                zinfo = classify_ward_map_zone(ox, oy, side_key)
                post = zinfo["posture"]
                posture_counts[post] += 1
                if post == "aggressive":
                    p_agg += 1
                elif post == "river_roshan":
                    p_riv += 1
                else:
                    p_def += 1

                p_key = "lane" if ot < 600 else ("mid" if ot < 1500 else "late")
                phase_posture[p_key][post] += 1

                # 匹配消失事件计算寿命
                matched_l = [
                    ol for ol in o_left
                    if ol.get("key") == okey and int(ol.get("time") or 0) >= ot
                ]
                if matched_l:
                    ol = matched_l[0]
                    lt = int(ol.get("time") or ot)
                    lifespan = max(1, min(360, lt - ot))
                    att_npc = str(ol.get("attackername") or "")
                    att_hid = npc_to_hid.get(att_npc, 0)
                    att_fp = fmt_by_hid.get(att_hid)
                    was_dewarded = bool(att_fp and att_fp["side"] != fp["side"] and lifespan < 345)
                    killer_zh = att_fp["hero_short_zh"] if was_dewarded else ("自然到期" if lifespan >= 345 else "被排/到期")
                else:
                    # 比赛结束时仍存活
                    lifespan = max(1, min(360, duration_sec - ot))
                    was_dewarded = False
                    killer_zh = "终局仍存活"

                p_lifespans.append(lifespan)
                if was_dewarded:
                    p_dewarded_cnt += 1
                    if lifespan <= 135:
                        instant_dewards.append({
                            "time_str": fmt_mmss(ot),
                            "planter_hero": fp["hero_short_zh"],
                            "planter_player": fp["personaname"],
                            "pos": fp["pos"],
                            "zone_zh": zinfo["zone_zh"],
                            "posture_zh": zinfo["posture_zh"],
                            "coords": f"({ox:.0f},{oy:.0f})",
                            "lifespan_sec": lifespan,
                            "dewarded_by": killer_zh,
                        })

                obs_records.append({
                    "time_sec": ot,
                    "time_str": fmt_mmss(ot),
                    "planter_hero": fp["hero_short_zh"],
                    "planter_pos": fp["pos"],
                    "x": ox,
                    "y": oy,
                    "zone_zh": zinfo["zone_zh"],
                    "posture": post,
                    "posture_zh": zinfo["posture_zh"],
                    "lifespan_sec": lifespan,
                    "was_dewarded": was_dewarded,
                    "killer_zh": killer_zh,
                })

            for s in s_log:
                sx = float(s.get("x") or 128.0)
                sy = float(s.get("y") or 128.0)
                st = int(s.get("time") or 0)
                zinfo = classify_ward_map_zone(sx, sy, side_key)
                sen_records.append({
                    "time_sec": st,
                    "time_str": fmt_mmss(st),
                    "planter_hero": fp["hero_short_zh"],
                    "planter_pos": fp["pos"],
                    "x": sx,
                    "y": sy,
                    "zone_zh": zinfo["zone_zh"],
                })

            if len(o_log) > 0 or len(s_log) > 0 or int(fp["pos"]) in (4, 5):
                avg_life = round(sum(p_lifespans) / len(p_lifespans), 0) if p_lifespans else 0
                tot_o = max(1, len(o_log))
                pos_num = int(fp["pos"])
                # 评价做眼风格（区分 4/5 号位辅助与 1~3 号位大哥顺手补眼）
                if len(o_log) == 0:
                    style_note = "全场 0 假眼投放（仅插真眼反隐）。" if len(s_log) > 0 else "全场 0 真假眼投放。"
                elif pos_num in (1, 2, 3) and len(o_log) <= 2:
                    style_note = f"{pos_num}号位核心自备视野：顺手插下 {len(o_log)} 颗假眼 / {len(s_log)} 颗真眼（进攻 {p_agg} / 河道 {p_riv} / 防守保护 {p_def}），平均存活 {int(avg_life)}s。"
                elif p_agg / tot_o >= 0.5:
                    style_note = f"做眼风格偏【激进深插】（⚔️进攻眼 {p_agg} 颗 / ⚖️河道眼 {p_riv} 颗 / 🛡️防守眼 {p_def} 颗），平均寿命 {int(avg_life)}s。"
                elif p_def / tot_o >= 0.55:
                    style_note = f"做眼风格偏【保守缩家】（🛡️防守保护眼 {p_def} 颗 / ⚖️河道眼 {p_riv} 颗 / ⚔️进攻眼仅 {p_agg} 颗），平均寿命 {int(avg_life)}s。"
                else:
                    style_note = f"做眼攻守均衡（⚔️进攻眼 {p_agg} 颗 / ⚖️河道肉山眼 {p_riv} 颗 / 🛡️防守眼 {p_def} 颗），平均寿命 {int(avg_life)}s。"

                per_support_vision.append({
                    "pos": fp["pos"],
                    "hero_short_zh": fp["hero_short_zh"],
                    "hero_img": fp["hero_img"],
                    "personaname": fp["personaname"],
                    "obs_total": len(o_log),
                    "sen_total": len(s_log),
                    "obs_killed": int(rp.get("observer_kills") or 0),
                    "sen_killed": int(rp.get("sentry_kills") or 0),
                    "aggressive_cnt": p_agg,
                    "river_cnt": p_riv,
                    "defensive_cnt": p_def,
                    "avg_lifespan_sec": int(avg_life),
                    "dewarded_cnt": p_dewarded_cnt,
                    "style_note": style_note,
                })

        # 聚类检测「同高台头铁连插」(半径 4.5 内插了 >= 3 颗守卫)
        all_wards_combined = [
            {"type": "假眼", **r} for r in obs_records
        ] + [
            {"type": "真眼", **r} for r in sen_records
        ]
        clusters: List[Dict[str, Any]] = []
        for w in all_wards_combined:
            placed = False
            for c in clusters:
                if abs(w["x"] - c["cx"]) <= 4.5 and abs(w["y"] - c["cy"]) <= 4.5:
                    c["items"].append(w)
                    placed = True
                    break
            if not placed:
                clusters.append({"cx": w["x"], "cy": w["y"], "zone_zh": w["zone_zh"], "items": [w]})

        for c in sorted(clusters, key=lambda x: len(x["items"]), reverse=True):
            if len(c["items"]) >= 3:
                obs_c = sum(1 for x in c["items"] if x["type"] == "假眼")
                sen_c = sum(1 for x in c["items"] if x["type"] == "真眼")
                planters = sorted({x["planter_hero"] for x in c["items"]})
                times_s = "、".join(x["time_str"] for x in c["items"][:5])
                cliff_spots.append({
                    "zone_zh": c["zone_zh"],
                    "coords": f"({c['cx']:.0f},{c['cy']:.0f})",
                    "total_count": len(c["items"]),
                    "obs_count": obs_c,
                    "sen_count": sen_c,
                    "planters": " / ".join(planters),
                    "times_str": times_s,
                    "comment": f"在【{c['zone_zh']} ({c['cx']:.0f},{c['cy']:.0f})】同一个眼位重复插了 {len(c['items'])} 颗眼（{obs_c}假/{sen_c}真，时间：{times_s}），属于典型的固定高台死磕！",
                })

        total_obs = max(1, len(obs_records))
        agg_pct = round(posture_counts["aggressive"] / total_obs * 100, 1)
        riv_pct = round(posture_counts["river_roshan"] / total_obs * 100, 1)
        def_pct = round(posture_counts["defensive"] / total_obs * 100, 1)
        avg_team_life = int(round(sum(r["lifespan_sec"] for r in obs_records) / total_obs, 0)) if obs_records else 0

        # 生成本方眼位姿态毒舌诊断结论
        mid_agg = phase_posture["mid"]["aggressive"]
        mid_def = phase_posture["mid"]["defensive"]
        late_agg = phase_posture["late"]["aggressive"]
        late_def = phase_posture["late"]["defensive"]

        if def_pct >= 52.0:
            posture_verdict = (
                f"⚠️ 眼位整体偏保守缩家：本方全场 {len(obs_records)} 颗假眼中，有 {posture_counts['defensive']} 颗（{def_pct}%）插在己方半场，"
                f"河道/肉山争夺眼 {posture_counts['river_roshan']} 颗（{riv_pct}%），深入敌方野区的进攻眼仅有 {posture_counts['aggressive']} 颗（{agg_pct}%）。"
                f"当队伍需要过河抓人或压制敌方主野区时，缺乏提前铺设的侵略视野。"
            )
        elif agg_pct >= 45.0:
            posture_verdict = (
                f"⚔️ 眼位极具进攻侵略性：本方 {len(obs_records)} 颗假眼中有 {posture_counts['aggressive']} 颗（{agg_pct}%）直接插进敌方半场野区/三角区，"
                f"另有 {posture_counts['river_roshan']} 颗（{riv_pct}%）控制河道与肉山，防守眼仅 {posture_counts['defensive']} 颗（{def_pct}%）。"
                + (f"但要注意其中有 {len(instant_dewards)} 颗假眼被敌方快速排掉，深入做眼最好配合开雾推进！" if instant_dewards else "视野压制非常到位！")
            )
        else:
            posture_verdict = (
                f"⚖️ 眼位攻守结构均衡：全场 {len(obs_records)} 颗假眼中，⚔️ 进攻深入眼 {posture_counts['aggressive']} 颗（{agg_pct}%）、"
                f"⚖️ 河道/肉山眼 {posture_counts['river_roshan']} 颗（{riv_pct}%）、🛡️ 防守保护眼 {posture_counts['defensive']} 颗（{def_pct}%），"
                f"假眼平均存活寿命 {avg_team_life} 秒（满分 360 秒）。"
            )

        dewarded_total = sum(1 for r in obs_records if r.get("was_dewarded"))
        dewarded_pct = round(dewarded_total / total_obs * 100, 1) if obs_records else 0.0

        return {
            "side": side_key,
            "side_zh": side_zh,
            "total_obs": len(obs_records),
            "total_sen": len(sen_records),
            "dewarded_total": dewarded_total,
            "dewarded_pct": dewarded_pct,
            "avg_lifespan_sec": avg_team_life,
            "posture_counts": posture_counts,
            "posture_pcts": {
                "aggressive": agg_pct,
                "river_roshan": riv_pct,
                "defensive": def_pct,
            },
            "phase_posture": phase_posture,
            "posture_verdict": posture_verdict,
            "per_support_vision": per_support_vision,
            "instant_dewards": instant_dewards[:6],
            "cliff_spots": cliff_spots[:4],
            "obs_records": obs_records,
        }

    # =========================================================================
    # 三、辅助堆野 vs 大哥自堆 & 开雾找节奏全链路还原 (Stacking & Smoke Rhythms)
    # =========================================================================
    def analyze_side_stacking_and_smokes(side_key: str) -> Dict[str, Any]:
        own_players = radiant_players if side_key == "radiant" else dire_players
        opp_players = dire_players if side_key == "radiant" else radiant_players

        # 1) 堆野审计 (camps_stacked, creeps_stacked, camps_stacked_t)
        stack_rows: List[Dict[str, Any]] = []
        sup_stacks = 0
        core_stacks = 0
        total_stacks = 0
        total_creeps = 0

        for fp in sorted(own_players, key=lambda x: int(x["pos"])):
            rp = raw_by_slot.get(int(fp["player_slot"]), {})
            c_stacked = int(rp.get("camps_stacked") or 0)
            cr_stacked = int(rp.get("creeps_stacked") or 0)
            st_t = rp.get("camps_stacked_t") or []
            stack_mins: List[str] = []
            for m_idx in range(1, len(st_t)):
                diff = int(st_t[m_idx] or 0) - int(st_t[m_idx - 1] or 0)
                if diff > 0:
                    stack_mins.append(f"{m_idx}:00" + (f"(×{diff})" if diff > 1 else ""))

            pos_i = int(fp["pos"])
            if pos_i in (4, 5):
                sup_stacks += c_stacked
            else:
                core_stacks += c_stacked
            total_stacks += c_stacked
            total_creeps += cr_stacked

            stack_rows.append({
                "pos": pos_i,
                "hero_short_zh": fp["hero_short_zh"],
                "hero_img": fp["hero_img"],
                "personaname": fp["personaname"],
                "camps_stacked": c_stacked,
                "creeps_stacked": cr_stacked,
                "stack_mins": stack_mins,
                "role_tag": "辅助本职" if pos_i in (4, 5) else "大哥自力更生",
            })

        opp_total_stacks = sum(
            int(raw_by_slot.get(int(op["player_slot"]), {}).get("camps_stacked") or 0)
            for op in opp_players
        )

        if sup_stacks == 0 and core_stacks > 0:
            stack_verdict = (
                f"🚨 辅助 0 堆野警告：本方全场共堆野 {total_stacks} 波（{total_creeps} 只野怪），"
                f"竟然全部是 1~3 号位大哥自己动手堆的（{core_stacks} 波），4/5 号位双辅助堆野记录为 0！对比敌方全队堆野 {opp_total_stacks} 波。"
            )
        elif core_stacks > sup_stacks:
            stack_verdict = (
                f"⚠️ 大哥比辅助还会堆野：本方全队堆野 {total_stacks} 波（{total_creeps} 只怪），"
                f"其中 1~3 号位核心自己顺手堆了 {core_stacks} 波，而 4/5 号位双辅助合计仅堆了 {sup_stacks} 波（敌方全队堆野 {opp_total_stacks} 波）。"
                f"辅助路过三角区与主野区整点 53~55 秒拉野屯矿的肌肉记忆还不够强！"
            )
        elif sup_stacks >= 4:
            stack_verdict = (
                f"✓ 辅助屯野合格：本方全队累计堆野 {total_stacks} 波（{total_creeps} 只野怪，其中双辅助贡献 {sup_stacks} 波、核心自堆 {core_stacks} 波），"
                f"对比敌方全队 {opp_total_stacks} 波，有效加速了本方核心中期经济起飞。"
            )
        else:
            stack_verdict = (
                f"全队累计堆野 {total_stacks} 波（{total_creeps} 只野怪，辅助 {sup_stacks} 波 / 核心 {core_stacks} 波；敌方 {opp_total_stacks} 波）。"
                f"建议 4/5 号位在 6~18 分钟控符与插眼路过三角区时多帮主C屯远古与大野。"
            )

        # 2) 开雾找节奏审计 (smoke_of_deceit purchase_log + item_uses + 90s 战果关联)
        raw_smoke_buys: List[Dict[str, Any]] = []
        own_smoke_uses_total = 0
        per_player_smokes: List[Dict[str, Any]] = []

        # 收集全队击杀与阵亡时间戳用于关联开雾战果
        team_kills_timeline: List[Dict[str, Any]] = []
        team_deaths_timeline: List[Dict[str, Any]] = []
        for fp in own_players:
            rp = raw_by_slot.get(int(fp["player_slot"]), {})
            s_used = int((rp.get("item_uses") or {}).get("smoke_of_deceit") or 0)
            s_bought = sum(1 for x in (rp.get("purchase_log") or []) if x.get("key") == "smoke_of_deceit")
            own_smoke_uses_total += s_used
            if s_used > 0 or s_bought > 0 or int(fp["pos"]) in (3, 4, 5):
                per_player_smokes.append({
                    "pos": fp["pos"],
                    "hero_short_zh": fp["hero_short_zh"],
                    "personaname": fp["personaname"],
                    "bought": s_bought,
                    "used": s_used,
                })
            for pe in rp.get("purchase_log") or []:
                if pe.get("key") == "smoke_of_deceit":
                    raw_smoke_buys.append({
                        "time_sec": int(pe.get("time") or 0),
                        "hero_short_zh": fp["hero_short_zh"],
                        "personaname": fp["personaname"],
                        "pos": fp["pos"],
                    })
            for ke in rp.get("kills_log") or []:
                vhid = npc_to_hid.get(str(ke.get("key") or ""), 0)
                vfp = fmt_by_hid.get(vhid)
                team_kills_timeline.append({
                    "time_sec": int(ke.get("time") or 0),
                    "killer": fp["hero_short_zh"],
                    "victim": vfp["hero_short_zh"] if vfp else "敌方英雄",
                })
            for de in rp.get("deaths_log") or []:
                team_deaths_timeline.append({
                    "time_sec": int(de.get("time") or 0),
                    "victim": fp["hero_short_zh"],
                })

        opp_smoke_uses_total = sum(
            int((raw_by_slot.get(int(op["player_slot"]), {}).get("item_uses") or {}).get("smoke_of_deceit") or 0)
            for op in opp_players
        )

        # 合并相近 30 秒内的买雾事件并追踪随后 105 秒战果
        raw_smoke_buys.sort(key=lambda x: x["time_sec"])
        smoke_events: List[Dict[str, Any]] = []
        for sb in raw_smoke_buys:
            t0 = sb["time_sec"]
            if smoke_events and abs(t0 - smoke_events[-1]["time_sec"]) <= 35:
                continue
            window_end = t0 + 105
            k_after = [k for k in team_kills_timeline if max(0, t0) <= k["time_sec"] <= window_end]
            d_after = [d for d in team_deaths_timeline if max(0, t0) <= d["time_sec"] <= window_end]

            if t0 < 0:
                phase_tag = "出门一级团雾"
            elif t0 < 600:
                phase_tag = "对线期游走雾"
            elif t0 < 1500:
                phase_tag = "中期抓人/推进雾"
            else:
                phase_tag = "后期决胜/控盾雾"

            if len(k_after) > len(d_after) and len(k_after) >= 1:
                victims_str = "、".join(f"{ fmt_mmss(k['time_sec']) } 抓死{k['victim']}" for k in k_after[:3])
                outcome = "success"
                outcome_label = f"🟢 破雾奏效 ({len(k_after)}换{len(d_after)})"
                detail = f"买雾/开雾后迅速打开节奏：{victims_str}。"
            elif len(d_after) > len(k_after) and len(d_after) >= 1:
                dead_str = "、".join(d["victim"] for d in d_after[:3])
                outcome = "backfire"
                outcome_label = f"🔴 开雾撞墙 ({len(k_after)}换{len(d_after)})"
                detail = f"开雾切入后反遭敌方反打，导致我方 {dead_str} 阵亡。"
            elif len(k_after) > 0 and len(k_after) == len(d_after):
                outcome = "trade"
                outcome_label = f"⚖️ 破雾互换 ({len(k_after)}换{len(d_after)})"
                detail = f"开雾遭遇战双方打出 {len(k_after)} 换 {len(d_after)} 人头互换。"
            else:
                outcome = "dry"
                outcome_label = "🟡 哑火空雾 (0击杀)"
                detail = "买雾/屯雾后 100 秒内未产生任何击杀（蹲人落空或仅用于安全做视野）。"

            smoke_events.append({
                "time_sec": t0,
                "time_str": fmt_mmss(t0),
                "phase_tag": phase_tag,
                "initiator_hero": sb["hero_short_zh"],
                "initiator_player": sb["personaname"],
                "initiator_pos": sb["pos"],
                "outcome": outcome,
                "outcome_label": outcome_label,
                "detail": detail,
            })

        mid_smokes = sum(1 for e in smoke_events if 600 <= e["time_sec"] <= 1500)
        succ_smokes = sum(1 for e in smoke_events if e["outcome"] == "success")

        if own_smoke_uses_total <= 1:
            smoke_verdict = (
                f"🚨 全场几乎不开雾找节奏：本方 {duration_min:.0f} 分钟累计仅开雾 {own_smoke_uses_total} 次（敌方开雾 {opp_smoke_uses_total} 次）！"
                f"10~25 分钟中期节奏期极度缺乏主动买雾抓单与控盾意识，全靠走明牌视野硬撞。"
            )
        elif mid_smokes == 0:
            smoke_verdict = (
                f"⚠️ 中期（10–25m）零开雾真空：本方全场共开雾 {own_smoke_uses_total} 次（敌方 {opp_smoke_uses_total} 次），"
                f"但最关键的 10~25 分钟跳刀/大招节奏期竟然没有组织起有效的买雾抓人！"
            )
        else:
            smoke_verdict = (
                f"本方全场累计激活诡计之雾 {own_smoke_uses_total} 次（敌方 {opp_smoke_uses_total} 次），"
                f"共捕获 {len(smoke_events)} 波买雾节奏，其中 {succ_smokes} 波在 100 秒内直接转化为击杀破局。"
            )

        return {
            "side": side_key,
            "total_stacks": total_stacks,
            "total_creeps_stacked": total_creeps,
            "support_stacks": sup_stacks,
            "core_stacks": core_stacks,
            "enemy_total_stacks": opp_total_stacks,
            "stack_verdict": stack_verdict,
            "stack_rows": stack_rows,
            "own_smoke_uses": own_smoke_uses_total,
            "enemy_smoke_uses": opp_smoke_uses_total,
            "smoke_verdict": smoke_verdict,
            "per_player_smokes": per_player_smokes,
            "smoke_events": smoke_events[:8],
        }

    # =========================================================================
    # 四、对线期细节显微镜：拉野、双生门走门、疗伤莲花、7/14m 智慧经验符、2/4m 圣水符
    # =========================================================================
    # 预先汇总全场所有 10 人的智慧神符 (key == '8') 与 圣水符 (key == '7') 时间轴
    all_wisdom_runes: List[Dict[str, Any]] = []
    all_water_runes: List[Dict[str, Any]] = []
    for fp in all_formatted:
        rp = raw_by_slot.get(int(fp["player_slot"]), {})
        p_side = "radiant" if int(fp["player_slot"]) < 128 else "dire"
        for rl in rp.get("runes_log") or []:
            rkey = str(rl.get("key"))
            rtime = int(rl.get("time") or 0)
            entry = {
                "time_sec": rtime,
                "time_str": fmt_mmss(rtime),
                "side": p_side,
                "side_zh": fp["side"],
                "pos": fp["pos"],
                "hero_short_zh": fp["hero_short_zh"],
                "hero_img": fp["hero_img"],
                "personaname": fp["personaname"],
            }
            if rkey == "8":
                all_wisdom_runes.append(entry)
            elif rkey == "7":
                all_water_runes.append(entry)

    all_wisdom_runes.sort(key=lambda x: x["time_sec"])
    all_water_runes.sort(key=lambda x: x["time_sec"])

    def analyze_side_laning_mechanics(side_key: str) -> Dict[str, Any]:
        own_players = radiant_players if side_key == "radiant" else dire_players
        opp_players = dire_players if side_key == "radiant" else radiant_players

        # 1) 对线期拉野与消兵审计 (0–10m)
        # 利用辅助在野区拉野坐标带的 lane_pos 驻留权重 + 前10分钟反补 dn10 + 前8分钟封野真眼
        pulling_rows: List[Dict[str, Any]] = []
        for fp in sorted(own_players, key=lambda x: int(x["pos"])):
            pos_i = int(fp["pos"])
            if pos_i not in (4, 5):
                continue
            rp = raw_by_slot.get(int(fp["player_slot"]), {})
            lpos = rp.get("lane_pos") or {}
            pull_ticks = 0
            lane_ticks = 0
            for x_s, yd in lpos.items():
                if not isinstance(yd, dict):
                    continue
                for y_s, w_cnt in yd.items():
                    try:
                        lx = float(x_s)
                        ly = float(y_s)
                        w = int(w_cnt or 0)
                        lane_ticks += w
                        # 天辉下路拉野带 (138..172, 74..108) 或 夜魇上路拉野带 (82..118, 148..182)
                        if (138 <= lx <= 172 and 74 <= ly <= 108) or (82 <= lx <= 118 and 148 <= ly <= 182):
                            pull_ticks += w
                    except Exception:
                        pass

            pull_ratio_pct = round((pull_ticks / max(1, lane_ticks)) * 100, 1)
            dn10 = int((fp.get("laning_10m") or {}).get("dn10") or 0)
            lh10 = int((fp.get("laning_10m") or {}).get("lh10") or 0)
            early_sen = sum(
                1 for s in (rp.get("sen_log") or []) if int(s.get("time") or 9999) <= 540
            )
            if pull_ticks >= 18 or dn10 >= 4 or early_sen >= 2:
                status_tag = "🟢 积极拉野/封野控线"
                comment = (
                    f"前10分钟在边路拉野/野店区域活动占比 {pull_ratio_pct}%（驻留权重 {pull_ticks}），"
                    f"配合插下 {early_sen} 颗对线封野/反封真眼，贡献 {lh10} 正补 / {dn10} 反补。"
                )
            else:
                status_tag = "🟡 占线偏多/拉野偏少"
                comment = (
                    f"前10分钟拉野区活动权重仅 {pull_ticks}（反补 {dn10} 刀，前9分钟真眼 {early_sen} 颗），"
                    f"更多时间站在兵线上耗血或游走，拉野消兵频率偏低。"
                )
            pulling_rows.append({
                "pos": pos_i,
                "hero_short_zh": fp["hero_short_zh"],
                "hero_img": fp["hero_img"],
                "personaname": fp["personaname"],
                "pull_ticks": pull_ticks,
                "pull_ratio_pct": pull_ratio_pct,
                "dn10": dn10,
                "lh10": lh10,
                "early_sentries": early_sen,
                "status_tag": status_tag,
                "comment": comment,
            })

        # 2) 疗伤莲花 (Lotus: famango / great_famango / greater_famango) 争夺
        own_lotus_total = 0
        opp_lotus_total = 0
        own_lotus_breakdown = []
        opp_lotus_breakdown = []

        for fp in own_players:
            rp = raw_by_slot.get(int(fp["player_slot"]), {})
            iu = rp.get("item_uses") or {}
            cnt = int(iu.get("famango") or 0) + int(iu.get("great_famango") or 0) + int(iu.get("greater_famango") or 0)
            own_lotus_total += cnt
            if cnt > 0:
                own_lotus_breakdown.append(f"{fp['hero_short_zh']}({cnt}朵)")

        for op in opp_players:
            rp = raw_by_slot.get(int(op["player_slot"]), {})
            iu = rp.get("item_uses") or {}
            cnt = int(iu.get("famango") or 0) + int(iu.get("great_famango") or 0) + int(iu.get("greater_famango") or 0)
            opp_lotus_total += cnt
            if cnt > 0:
                opp_lotus_breakdown.append(f"{op['hero_short_zh']}({cnt}朵)")

        if own_lotus_total < opp_lotus_total:
            lotus_verdict = (
                f"⚠️ 边路莲花池被压制：本方全队仅吃下 {own_lotus_total} 朵疗伤莲花（{'、'.join(own_lotus_breakdown) or '全员0莲花'}），"
                f"而敌方抢下了 {opp_lotus_total} 朵莲花（{'、'.join(opp_lotus_breakdown)}）！03:00 / 06:00 / 09:00 整点莲花池争夺吃亏。"
            )
        elif own_lotus_total > opp_lotus_total:
            lotus_verdict = (
                f"✓ 边路莲花池掌控出色：本方累计控下 {own_lotus_total} 朵疗伤莲花（{'、'.join(own_lotus_breakdown)}），"
                f"压制了敌方的 {opp_lotus_total} 朵（{'、'.join(opp_lotus_breakdown) or '0'}），线上换血续航占优。"
            )
        else:
            lotus_verdict = (
                f"双方疗伤莲花平分秋色：本方吃下 {own_lotus_total} 朵（{'、'.join(own_lotus_breakdown) or '0'}） vs 敌方 {opp_lotus_total} 朵。"
            )

        # 3) 双生门走门 (twin_gate_portal_warp) & 观察者灯塔 (ability_lamp_use) & 前哨 (ability_capture)
        own_gate_total = 0
        opp_gate_total = 0
        own_lamp_total = 0
        opp_lamp_total = 0
        map_interact_rows = []

        for fp in sorted(own_players, key=lambda x: int(x["pos"])):
            rp = raw_by_slot.get(int(fp["player_slot"]), {})
            au = rp.get("ability_uses") or {}
            iu = rp.get("item_uses") or {}
            g_cnt = int(au.get("twin_gate_portal_warp") or 0)
            l_cnt = int(au.get("ability_lamp_use") or 0)
            c_cnt = int(au.get("ability_capture") or 0)
            lot_cnt = int(iu.get("famango") or 0) + int(iu.get("great_famango") or 0) + int(iu.get("greater_famango") or 0)
            r_list = rp.get("runes_log") or []
            w_cnt = sum(1 for r in r_list if str(r.get("key")) == "8")
            water_cnt = sum(1 for r in r_list if str(r.get("key")) == "7")
            bounty_cnt = sum(1 for r in r_list if str(r.get("key")) == "5")
            power_cnt = sum(1 for r in r_list if str(r.get("key")) not in ("5", "7", "8"))

            own_gate_total += g_cnt
            own_lamp_total += l_cnt

            map_interact_rows.append({
                "pos": fp["pos"],
                "hero_short_zh": fp["hero_short_zh"],
                "hero_img": fp["hero_img"],
                "personaname": fp["personaname"],
                "twin_gate": g_cnt,
                "watcher_lamp": l_cnt,
                "outpost_capture": c_cnt,
                "lotus_used": lot_cnt,
                "wisdom_runes": w_cnt,
                "water_runes": water_cnt,
                "bounty_runes": bounty_cnt,
                "power_runes": power_cnt,
            })

        for op in opp_players:
            rp = raw_by_slot.get(int(op["player_slot"]), {})
            au = rp.get("ability_uses") or {}
            opp_gate_total += int(au.get("twin_gate_portal_warp") or 0)
            opp_lamp_total += int(au.get("ability_lamp_use") or 0)

        # 4) 智慧经验符 (7:00 / 14:00 / 21:00) 比分与评语
        own_wisdom_cnt = sum(1 for w in all_wisdom_runes if w["side"] == side_key)
        opp_wisdom_cnt = sum(1 for w in all_wisdom_runes if w["side"] != side_key)
        if own_wisdom_cnt >= opp_wisdom_cnt and own_wisdom_cnt > 0:
            wisdom_verdict = f"✓ 智慧经验符控制占优：本方抢下 {own_wisdom_cnt} 颗经验符 vs 敌方 {opp_wisdom_cnt} 颗，辅助等级与天赋节点没有落入下风。"
        else:
            wisdom_verdict = f"⚠️ 智慧经验符落后：本方仅吃到 {own_wisdom_cnt} 颗经验符 vs 敌方吃到 {opp_wisdom_cnt} 颗！07:00 与 14:00 必须提前 15 秒去劣势路祭坛蹲守经验符。"

        return {
            "side": side_key,
            "pulling_rows": pulling_rows,
            "own_lotus_total": own_lotus_total,
            "opp_lotus_total": opp_lotus_total,
            "lotus_verdict": lotus_verdict,
            "own_gate_total": own_gate_total,
            "opp_gate_total": opp_gate_total,
            "own_lamp_total": own_lamp_total,
            "opp_lamp_total": opp_lamp_total,
            "own_wisdom_cnt": own_wisdom_cnt,
            "opp_wisdom_cnt": opp_wisdom_cnt,
            "wisdom_verdict": wisdom_verdict,
            "wisdom_timeline": all_wisdom_runes,
            "water_runes_timeline": all_water_runes,
            "map_interact_rows": map_interact_rows,
        }

    # =========================================================================
    # 五、TP 救人及时性与团战支援/缺席旁观审计 (TP Responsiveness & Rotation Audit)
    # =========================================================================
    def analyze_side_tp_and_rotations(side_key: str) -> Dict[str, Any]:
        own_players = radiant_players if side_key == "radiant" else dire_players
        is_rad = (side_key == "radiant")

        player_tp_rows: List[Dict[str, Any]] = []
        rotation_highlights: List[Dict[str, Any]] = []
        absent_warnings: List[Dict[str, Any]] = []
        teamfight_tp_events: List[Dict[str, Any]] = []

        # 逐波团战检查：谁亮了 TP 参战，谁在我方死人的团战里全程 0 英雄伤害 0 阵亡 0 TP 旁观/刷野
        for tf_idx, tf in enumerate(raw_tfs):
            tf_pl = tf.get("players") or []
            if len(tf_pl) < 10:
                continue
            s_sec = int(tf.get("start") or 0)
            e_sec = int(tf.get("end") or 0)
            own_indices = range(0, 5) if is_rad else range(5, 10)
            opp_indices = range(5, 10) if is_rad else range(0, 5)

            own_deaths_heroes = []
            opp_deaths_cnt = sum(int(tf_pl[i].get("deaths") or 0) for i in opp_indices)
            tp_responders = []
            tp_saviors_objs = []
            spectators = []
            spectators_objs = []

            for i in own_indices:
                rp_i = raw_players_list[i] if i < len(raw_players_list) else {}
                pslot = int(rp_i.get("player_slot", i if i < 5 else i + 123))
                fp = fmt_by_slot.get(pslot)
                if not fp:
                    continue
                tp_obj = tf_pl[i]
                d_cnt = int(tp_obj.get("deaths") or 0)
                dmg_val = int(tp_obj.get("damage") or 0)
                ab_used = tp_obj.get("ability_uses") or {}
                it_used = tp_obj.get("item_uses") or {}
                tp_in_tf = int(it_used.get("tpscroll") or 0) + int(it_used.get("travel_boots") or 0) + int(it_used.get("travel_boots_2") or 0)

                if d_cnt > 0:
                    own_deaths_heroes.append(fp["hero_short_zh"])
                if tp_in_tf > 0 and (dmg_val > 0 or len(ab_used) > 0 or d_cnt > 0):
                    tp_responders.append(f"{fp['hero_short_zh']}({fp['personaname']})")
                    tp_saviors_objs.append({
                        "pos": fp["pos"],
                        "hero_short_zh": fp["hero_short_zh"],
                        "personaname": fp["personaname"],
                        "damage": dmg_val,
                    })
                elif d_cnt == 0 and dmg_val == 0 and tp_in_tf == 0:
                    spectators.append(fp)
                    spectators_objs.append({
                        "pos": fp["pos"],
                        "hero_short_zh": fp["hero_short_zh"],
                        "personaname": fp["personaname"],
                    })

            t_range = f"{fmt_mmss(s_sec)}–{fmt_mmss(e_sec)}"
            if len(own_deaths_heroes) + opp_deaths_cnt >= 2:
                teamfight_tp_events.append({
                    "tf_index": tf_idx + 1,
                    "time_range": t_range,
                    "own_deaths": len(own_deaths_heroes),
                    "opp_kills": opp_deaths_cnt,
                    "tp_saviors": tp_saviors_objs,
                    "spectators": spectators_objs if len(own_deaths_heroes) >= 2 else [],
                })

            if tp_responders and (len(own_deaths_heroes) + opp_deaths_cnt >= 2):
                rotation_highlights.append({
                    "time_range": t_range,
                    "responders": "、".join(tp_responders),
                    "trade_str": f"打成 {opp_deaths_cnt} 换 {len(own_deaths_heroes)}",
                    "detail": f"在 {t_range} 交战中，{'、'.join(tp_responders)} 第一时间亮 TP 落地支援参战（该波 {opp_deaths_cnt} 换 {len(own_deaths_heroes)}）。",
                })

            # 如果本波我方死了至少 2 人，且有队友 0 英雄伤害 0 阵亡 0 TP 旁观/远处刷野
            if len(own_deaths_heroes) >= 2 and spectators and s_sec >= 360:
                spec_names = "、".join(f"{sp['pos']}号位{sp['hero_short_zh']}" for sp in spectators)
                absent_warnings.append({
                    "time_range": t_range,
                    "victims": "、".join(own_deaths_heroes),
                    "spectators": spec_names,
                    "detail": f"⚠️ {t_range} 我方【{'、'.join(own_deaths_heroes)}】遭围剿阵亡时，{spec_names} 全程对敌方英雄 0 伤害、未交 TP 支援（在另一侧带线/刷野未赶到）。",
                })

        zero_buy_heroes = []
        total_tf_tp_saves = 0
        for fp in sorted(own_players, key=lambda x: int(x["pos"])):
            pslot = int(fp["player_slot"])
            rp = raw_by_slot.get(pslot, {})
            iu = rp.get("item_uses") or {}
            tp_used = int(iu.get("tpscroll") or 0) + int(iu.get("travel_boots") or 0) + int(iu.get("travel_boots_2") or 0)
            tp_bought = int(rp.get("purchase_tpscroll") or sum(1 for x in (rp.get("purchase_log") or []) if x.get("key") == "tpscroll"))
            early_tp_cnt = sum(
                1 for x in (rp.get("purchase_log") or [])
                if x.get("key") == "tpscroll" and int(x.get("time") or 9999) <= 720
            )
            tfs_for_p = tf_records_by_slot.get(pslot, [])

            tf_tp_cnt = 0
            tf_tp_times: List[str] = []
            tf_joined_cnt = 0
            tf_absent_cnt = 0
            tf_absent_times: List[str] = []
            for tfr in tfs_for_p:
                own_d = tfr["rad_deaths"] if is_rad else tfr["dire_deaths"]
                it_u = tfr["item_uses"] or {}
                has_tp = (int(it_u.get("tpscroll") or 0) + int(it_u.get("travel_boots") or 0) + int(it_u.get("travel_boots_2") or 0)) > 0
                participated = (tfr["damage"] > 0 or tfr["deaths"] > 0 or has_tp)
                if has_tp:
                    tf_tp_cnt += 1
                    tf_tp_times.append(fmt_mmss(tfr["start_sec"]))
                if participated:
                    tf_joined_cnt += 1
                elif own_d >= 2 and tfr["start_sec"] >= 360:
                    tf_absent_cnt += 1
                    tf_absent_times.append(fmt_mmss(tfr["start_sec"]))

            total_tf_tp_saves += tf_tp_cnt
            if tp_bought == 0:
                zero_buy_heroes.append(f"{fp['pos']}号位{fp['hero_short_zh']}")

            # 检测「买TP/用TP后40秒内暴毙（TP飞脸送）」
            tp_buy_times = [int(x.get("time") or 0) for x in (rp.get("purchase_log") or []) if x.get("key") == "tpscroll"]
            tp_feed_times = []
            for de in rp.get("deaths_log") or []:
                dt_s = int(de.get("time") or 0)
                if any(0 <= (dt_s - bt) <= 45 for bt in tp_buy_times):
                    tp_feed_times.append(fmt_mmss(dt_s))

            pos_i = int(fp["pos"])
            deaths_total = int(fp.get("deaths") or 0)
            if tp_used >= 10 and tf_tp_cnt >= 2:
                grade = "good"
                verdict = f"支援极快：全场使用 {tp_used} 次 TP，其中 {tf_tp_cnt} 波团战（{'、'.join(tf_tp_times)}）直接亮 TP 落地救人/反打，参团率 {fp.get('kill_participation_pct')}%。"
            elif tp_used <= max(4, int(duration_min / 6.5)):
                grade = "bad"
                verdict = (
                    f"⚠️ 支援频次偏低：{duration_min:.0f} 分钟仅使用 {tp_used} 次 TP（主动买 {tp_bought} 张，团战亮 TP {tf_tp_cnt} 次），"
                    + (f"在 {tf_absent_cnt} 波队友阵亡的团战中未能及时赶到！" if tf_absent_cnt > 0 else "跑图大多靠双腿！")
                )
            elif tp_bought == 0 and deaths_total >= 6:
                grade = "warn"
                verdict = (
                    f"全靠阵亡赠送的免费抚恤 TP 过日子（全场死 {deaths_total} 次、主动花钱买 TP 0 张，共使用 {tp_used} 次，团战亮 TP {tf_tp_cnt} 次），"
                    f"连续存活刷钱时注意检查背包是否断 TP！"
                )
            elif tf_absent_cnt >= 2:
                grade = "warn"
                verdict = f"全场使用 {tp_used} 次 TP（团战亮 TP {tf_tp_cnt} 次），但在 {tf_absent_cnt} 波队友多人阵亡的团战（{'、'.join(tf_absent_times)}）中对敌方 0 伤害未亮 TP。"
            else:
                grade = "good" if tf_absent_cnt == 0 else "warn"
                verdict = (
                    f"全场使用 {tp_used} 次 TP（主动购买 {tp_bought} 张，团战亮 TP {tf_tp_cnt} 次），参战 {tf_joined_cnt}/{len(tfs_for_p)} 波关键团"
                    + (f"（缺席 {'、'.join(tf_absent_times)}）" if tf_absent_times else "")
                    + (f"，注意在 {'、'.join(tp_feed_times[:2])} 刚买 TP 后不久即阵亡。" if tp_feed_times else "。")
                )

            player_tp_rows.append({
                "pos": pos_i,
                "hero_short_zh": fp["hero_short_zh"],
                "hero_img": fp["hero_img"],
                "personaname": fp["personaname"],
                "tp_bought": tp_bought,
                "tp_used": tp_used,
                "early_tp_cnt": early_tp_cnt,
                "tf_tp_cnt": tf_tp_cnt,
                "tf_tp_times": tf_tp_times,
                "tf_joined_cnt": tf_joined_cnt,
                "tf_total_cnt": len(tfs_for_p),
                "tf_absent_cnt": tf_absent_cnt,
                "tf_absent_times": tf_absent_times,
                "tp_feed_times": tp_feed_times,
                "grade": grade,
                "verdict": verdict,
            })

        tp_verdict_parts = [
            f"本方全队在关键团战中共亮出 {total_tf_tp_saves} 人次 TP 落地支援（共触发 {len(rotation_highlights)} 波多英雄 TP 集结）。"
        ]
        if zero_buy_heroes:
            tp_verdict_parts.append(
                f"⚠️ 其中【{'、'.join(zero_buy_heroes)}】整局主动花钱买 TP 为 0 张，全靠阵亡复活赠送的免费 TP！"
            )
        if absent_warnings:
            tp_verdict_parts.append(
                f"🚨 抓包 {len(absent_warnings)} 波团战在队友成片阵亡时有人全程 0 英雄伤害且未亮 TP 支援！"
            )

        return {
            "side": side_key,
            "tp_verdict": " ".join(tp_verdict_parts),
            "player_tp_rows": player_tp_rows,
            "rotation_highlights": rotation_highlights[:6],
            "absent_warnings": absent_warnings[:6],
            "teamfight_tp_events": teamfight_tp_events,
        }

    # =========================================================================
    # 六、憋死 BKB / 救命装 / 团战 0 技能暴毙尸检 (Died With Cooldown Ready)
    # =========================================================================
    SAVE_ACTIVE_ITEMS: Dict[str, Tuple[str, str]] = {
        "black_king_bar": ("BKB黑皇杖", "critical"),
        "satanic": ("撒旦之邪力", "critical"),
        "manta": ("分身斧", "critical"),
        "aeon_disk": ("永恒之盘", "critical"),
        "hurricane_pike": ("飓风长戟(大推推)", "critical"),
        "force_staff": ("推推棒", "critical"),
        "glimmer_cape": ("微光披风", "critical"),
        "ghost": ("幽魂权杖(绿杖)", "critical"),
        "ethereal_blade": ("虚灵之刃", "critical"),
        "cyclone": ("吹风杖", "critical"),
        "wind_waker": ("风之杖(大吹风)", "critical"),
        "lotus_orb": ("清莲宝珠", "critical"),
        "cheese": ("奶酪", "critical"),
        "blade_mail": ("刃甲", "warn"),
        "shivas_guard": ("希瓦的守护", "warn"),
        "pipe": ("洞察烟斗(笛子)", "warn"),
        "crimson_guard": ("赤红甲", "warn"),
        "magic_wand": ("大魔棒", "warn"),
    }

    def analyze_side_unpressed_saves(side_key: str) -> Dict[str, Any]:
        own_players = radiant_players if side_key == "radiant" else dire_players
        incidents: List[Dict[str, Any]] = []
        player_rows: List[Dict[str, Any]] = []
        critical_total = 0
        zero_spell_total = 0

        for fp in sorted(own_players, key=lambda x: int(x["pos"])):
            pslot = int(fp["player_slot"])
            rp = raw_by_slot.get(pslot, {})
            plog = rp.get("purchase_log") or []
            owned_save_times: Dict[str, int] = {}
            for entry in plog:
                ik = str(entry.get("key") or "")
                t_buy = int(entry.get("time") or 0)
                if ik in SAVE_ACTIVE_ITEMS and ik not in owned_save_times:
                    owned_save_times[ik] = t_buy

            tfs_for_p = tf_records_by_slot.get(pslot, [])
            tf_deaths = 0
            unpressed_core_cnt = 0
            unpressed_wand_cnt = 0
            zero_spell_cnt = 0
            p_incidents: List[str] = []

            for tfr in tfs_for_p:
                if int(tfr.get("deaths") or 0) <= 0:
                    continue
                tf_deaths += 1
                s_sec = int(tfr.get("start_sec") or 0)
                e_sec = int(tfr.get("end_sec") or 0)
                t_range = f"{fmt_mmss(s_sec)}–{fmt_mmss(e_sec)}"
                it_u = tfr.get("item_uses") or {}
                ab_u = tfr.get("ability_uses") or {}
                dmg_val = int(tfr.get("damage") or 0)

                unpressed_crit_zh: List[str] = []
                unpressed_warn_zh: List[str] = []
                for ik, buy_t in owned_save_times.items():
                    if buy_t + 15 <= s_sec and int(it_u.get(ik) or 0) == 0:
                        zh_label, sev = SAVE_ACTIVE_ITEMS[ik]
                        if sev == "critical":
                            unpressed_crit_zh.append(zh_label)
                        else:
                            unpressed_warn_zh.append(zh_label)

                is_zero_spell = (s_sec >= 480 and len(ab_u) == 0)
                if is_zero_spell:
                    zero_spell_cnt += 1
                    zero_spell_total += 1

                if unpressed_crit_zh:
                    unpressed_core_cnt += 1
                    critical_total += 1
                elif unpressed_warn_zh:
                    unpressed_wand_cnt += 1

                if unpressed_crit_zh or is_zero_spell or unpressed_warn_zh:
                    severity = "critical" if (unpressed_crit_zh or is_zero_spell) else "warn"
                    parts = []
                    if unpressed_crit_zh:
                        parts.append(f"身怀【{' / '.join(unpressed_crit_zh)}】却 0 次按下直接阵亡")
                    elif unpressed_warn_zh:
                        parts.append(f"背包有【{' / '.join(unpressed_warn_zh)}】未按出即阵亡")
                    if is_zero_spell:
                        parts.append(f"整波团战 0 技能释放（仅打出 {dmg_val} 点伤害）秒躺")
                    desc = "，且".join(parts)
                    p_incidents.append(f"{fmt_mmss(s_sec)} {desc}")
                    incidents.append({
                        "time_range": t_range,
                        "start_sec": s_sec,
                        "pos": int(fp["pos"]),
                        "hero_short_zh": fp["hero_short_zh"],
                        "hero_img": fp["hero_img"],
                        "personaname": fp["personaname"],
                        "unpressed_items": unpressed_crit_zh + unpressed_warn_zh,
                        "zero_abilities": is_zero_spell,
                        "tf_damage": dmg_val,
                        "severity": severity,
                        "detail": f"[{t_range}] {fp['pos']}号位 {fp['hero_short_zh']}({fp['personaname']})：{desc}。",
                    })

            # 统计整局主动保命装总按键次数
            iu_all = rp.get("item_uses") or {}
            owned_summary = []
            for ik, buy_t in owned_save_times.items():
                zh_label, _ = SAVE_ACTIVE_ITEMS[ik]
                owned_summary.append(f"{zh_label}({fmt_mmss(buy_t)}出·按{int(iu_all.get(ik) or 0)}次)")

            if unpressed_core_cnt == 0 and zero_spell_cnt == 0 and unpressed_wand_cnt == 0:
                grade = "good"
                verdict = (
                    f"✓ 团战反应拉满：本局 {tf_deaths} 次团战阵亡中，所有已合成保命装与核心技能均在死前完整交出，0 次憋死！"
                    if tf_deaths > 0
                    else "✓ 团战零阵亡金身：全局关键团战未发生暴毙憋技能情况！"
                )
            elif unpressed_core_cnt > 0 or zero_spell_cnt > 0:
                grade = "bad"
                verdict = (
                    f"🚨 抓包 {unpressed_core_cnt} 次憋死核心保命装、{zero_spell_cnt} 次团战 0 技能秒躺："
                    + "；".join(p_incidents[:3])
                )
                # 同步挂一条徽章到玩家卡片
                audit_obj = fp.get("hero_execution_audit")
                if isinstance(audit_obj, dict):
                    badges = audit_obj.setdefault("headline_badges", [])
                    if unpressed_core_cnt > 0:
                        badges.append({"text": f"💀 憋死救命装 ×{unpressed_core_cnt}次", "tone": "bad"})
                    elif zero_spell_cnt > 0:
                        badges.append({"text": f"💀 团战0技能秒躺 ×{zero_spell_cnt}次", "tone": "bad"})
            else:
                grade = "warn"
                verdict = f"⚠️ 核心保命装均有按出，但有 {unpressed_wand_cnt} 波团战阵亡前未按出大魔棒/刃甲（{'；'.join(p_incidents[:2])}）。"

            player_rows.append({
                "pos": int(fp["pos"]),
                "hero_short_zh": fp["hero_short_zh"],
                "hero_img": fp["hero_img"],
                "personaname": fp["personaname"],
                "tf_deaths": tf_deaths,
                "unpressed_core_cnt": unpressed_core_cnt,
                "unpressed_wand_cnt": unpressed_wand_cnt,
                "zero_spell_cnt": zero_spell_cnt,
                "owned_saves_str": " ｜ ".join(owned_summary) if owned_summary else "未合成主动保命装",
                "grade": grade,
                "verdict": verdict,
            })

        incidents.sort(key=lambda x: (0 if x["severity"] == "critical" else 1, x["start_sec"]))
        if critical_total == 0 and zero_spell_total == 0:
            side_verdict = "✓ 全队团战技能与救命装释放及格：未出现身怀 BKB/推推/微光/分身斧却在团战暴毙未按出的重大犯罪。"
        else:
            side_verdict = (
                f"🚨 团战尸检抓包：全队共发生 {critical_total} 人次【身怀 BKB/分身/推推/绿杖等救命装却 0 次按下暴毙】、"
                f"{zero_spell_total} 人次【中后期团战 0 技能释放直接秒躺】！"
            )

        return {
            "side": side_key,
            "side_verdict": side_verdict,
            "critical_total": critical_total,
            "zero_spell_total": zero_spell_total,
            "incidents": incidents[:10],
            "player_rows": player_rows,
        }

    # =========================================================================
    # 七、地图空间理解与「大哥带无聊危险线 / 落单乱逛被抓死」空间取证 (Map Space & Solo Pickoffs)
    # =========================================================================
    raw_objectives = match.get("objectives") or []

    def analyze_side_map_space_and_pickoffs(side_key: str) -> Dict[str, Any]:
        own_players = radiant_players if side_key == "radiant" else dire_players
        is_rad = (side_key == "radiant")

        # 收集我方整局假眼存活区间与坐标，用于判断死的时候是不是黑图盲区
        own_obs_wards: List[Dict[str, Any]] = []
        for fp in own_players:
            rp = raw_by_slot.get(int(fp["player_slot"]), {})
            obs_l = rp.get("obs_log") or []
            left_l = rp.get("obs_left_log") or []
            for idx_w, w in enumerate(obs_l):
                t_in = int(w.get("time") or 0)
                t_out = int(left_l[idx_w].get("time") or (t_in + 360)) if idx_w < len(left_l) else (t_in + 360)
                own_obs_wards.append({
                    "x": float(w.get("x") or 128),
                    "y": float(w.get("y") or 128),
                    "t_in": t_in,
                    "t_out": t_out,
                })

        solo_pickoff_events: List[Dict[str, Any]] = []
        player_space_rows: List[Dict[str, Any]] = []
        total_solo_pickoffs = 0
        total_pointless_deaths = 0

        for fp in sorted(own_players, key=lambda x: int(x["pos"])):
            pslot = int(fp["player_slot"])
            pos_i = int(fp["pos"])
            rp = raw_by_slot.get(pslot, {})
            dlog = rp.get("deaths_log") or []
            lane_kills = int(rp.get("lane_kills") or 0)
            neutral_kills = int(rp.get("neutral_kills") or 0)
            total_creeps = max(1, lane_kills + neutral_kills)
            lane_farm_pct = round(lane_kills * 100.0 / total_creeps, 1)
            jungle_farm_pct = round(neutral_kills * 100.0 / total_creeps, 1)
            tower_dmg = int(fp.get("tower_damage") or 0)
            kp_pct = float(fp.get("kill_participation_pct") or 0.0)

            p_solo_cnt = 0
            p_solo_gold_fed = 0
            p_deep_death_cnt = 0
            p_pickoff_details: List[str] = []

            for d_entry in dlog:
                t_sec = int(d_entry.get("time") or 0)
                if t_sec < 540:  # 9分钟前算对线期阵亡
                    continue
                gold_fed = int(d_entry.get("gold_fed") or 0) + int(d_entry.get("gold_lost") or 0)
                dead_s = int(d_entry.get("time_dead") or 0)
                killer_npc = str(d_entry.get("key") or "")
                killer_hid = npc_to_hid.get(killer_npc, 0)
                killer_fp = fmt_by_hid.get(killer_hid)
                killer_zh = killer_fp["hero_short_zh"] if killer_fp else get_ability_zh(killer_npc)

                # 检查是否在大规模团战内
                matched_tf = None
                for tf in raw_tfs:
                    if int(tf.get("start") or 0) - 12 <= t_sec <= int(tf.get("end") or 0) + 12:
                        matched_tf = tf
                        break

                is_solo_pickoff = False
                death_zone_zh = "野区/兵线交界处"
                is_deep_enemy_half = False
                dx_val, dy_val = None, None

                if matched_tf is None:
                    is_solo_pickoff = True
                else:
                    tf_pl = matched_tf.get("players") or []
                    own_range = range(0, 5) if is_rad else range(5, 10)
                    opp_range = range(5, 10) if is_rad else range(0, 5)
                    own_d = sum(int(tf_pl[j].get("deaths") or 0) for j in own_range) if len(tf_pl) >= 10 else 1
                    opp_d = sum(int(tf_pl[j].get("deaths") or 0) for j in opp_range) if len(tf_pl) >= 10 else 0
                    zero_dmg_allies = sum(
                        1 for j in own_range
                        if len(tf_pl) >= 10 and int(tf_pl[j].get("damage") or 0) == 0 and int(tf_pl[j].get("deaths") or 0) == 0
                    )
                    # 提取该玩家在团战中的死亡坐标
                    p_idx_in_raw = next((idx for idx, item in enumerate(raw_players_list) if int(item.get("player_slot", -1)) == pslot), None)
                    if p_idx_in_raw is not None and p_idx_in_raw < len(tf_pl):
                        dpos = tf_pl[p_idx_in_raw].get("deaths_pos") or {}
                        for kx, vy in dpos.items():
                            if isinstance(vy, dict):
                                for ky in vy.keys():
                                    dx_val, dy_val = float(kx), float(ky)
                                    break
                            if dx_val is not None:
                                break
                    if dx_val is not None and dy_val is not None:
                        zinfo = classify_ward_map_zone(dx_val, dy_val, side_key)
                        death_zone_zh = zinfo["zone_zh"]
                        if zinfo["posture"] == "aggressive":
                            is_deep_enemy_half = True
                            p_deep_death_cnt += 1

                    # 如果这波只有他 1 个人死、对面 0 死，且至少 3 个队友 0 伤害（队友根本不在身边，自己落单带线/逛街被抓）
                    if own_d == 1 and opp_d == 0 and zero_dmg_allies >= 3:
                        is_solo_pickoff = True

                if is_solo_pickoff:
                    p_solo_cnt += 1
                    total_solo_pickoffs += 1
                    p_solo_gold_fed += gold_fed

                    # 检查当时场上我方存活假眼数量与视野保护
                    active_wards = [
                        w for w in own_obs_wards
                        if w["t_in"] <= t_sec <= w["t_out"]
                    ]
                    has_nearby_ward = False
                    if dx_val is not None and dy_val is not None:
                        has_nearby_ward = any(
                            ((w["x"] - dx_val) ** 2 + (w["y"] - dy_val) ** 2) ** 0.5 <= 28.0
                            for w in active_wards
                        )
                    vision_tag = (
                        "🌑 黑图无眼盲区孤立深带"
                        if (not has_nearby_ward and len(active_wards) <= 2)
                        else f"👁️ 场上虽有 {len(active_wards)} 颗眼仍未警觉蹲伏"
                    )

                    # 检查死后 70 秒内是否连累团队丢塔/丢肉山
                    consequence_list = []
                    for obj in raw_objectives:
                        ot = int(obj.get("time") or 0)
                        if t_sec <= ot <= t_sec + 70:
                            otype = str(obj.get("type") or "")
                            okey = str(obj.get("key") or "")
                            if otype == "CHAT_MESSAGE_ROSHAN_KILL":
                                oteam = int(obj.get("team") or 0)
                                if (is_rad and oteam == 3) or ((not is_rad) and oteam == 2):
                                    consequence_list.append(f"{fmt_mmss(ot)} 敌方趁机控下肉山盾")
                            elif otype == "building_kill":
                                if (is_rad and "goodguys" in okey) or ((not is_rad) and "badguys" in okey):
                                    b_zh = "高地塔/兵营" if ("3" in okey or "rax" in okey) else "外塔"
                                    consequence_list.append(f"{fmt_mmss(ot)} 连累本方丢掉{b_zh}")

                    if not consequence_list:
                        total_pointless_deaths += 1

                    conseq_str = (
                        f" → 💥 连锁掉点：{'、'.join(consequence_list[:2])}！"
                        if consequence_list
                        else " → 🚫 零战略收益的无聊带线/乱逛白给！"
                    )
                    detail_txt = (
                        f"[{fmt_mmss(t_sec)}] {pos_i}号位 {fp['hero_short_zh']} 在【{death_zone_zh}】落单被 {killer_zh} 等人抓死"
                        f"（{vision_tag} · 读秒 {dead_s}s · 送出 {gold_fed} 金）{conseq_str}"
                    )
                    p_pickoff_details.append(f"{fmt_mmss(t_sec)}({death_zone_zh})")
                    solo_pickoff_events.append({
                        "time_str": fmt_mmss(t_sec),
                        "time_sec": t_sec,
                        "pos": pos_i,
                        "hero_short_zh": fp["hero_short_zh"],
                        "hero_img": fp["hero_img"],
                        "personaname": fp["personaname"],
                        "zone_zh": death_zone_zh,
                        "killer_zh": killer_zh,
                        "vision_tag": vision_tag,
                        "gold_fed": gold_fed,
                        "time_dead": dead_s,
                        "consequence": "、".join(consequence_list[:2]) if consequence_list else "无战略收益白给",
                        "detail": detail_txt,
                    })

            # 判定该选手的「地图空间理解画像」
            is_core = pos_i in (1, 2, 3)
            if is_core and p_solo_cnt >= 2 and tower_dmg < 2500:
                style_badge = "🚨 危险呆刷 · 无聊带线提款机"
                grade = "bad"
                verdict = (
                    f"🚨 空间感亮红灯：线上补刀 {lane_kills} / 野区 {neutral_kills}（推塔仅 {tower_dmg}），"
                    f"中后期发生 {p_solo_cnt} 次无掩护落单被抓（{'、'.join(p_pickoff_details[:3])}，累计白给 {p_solo_gold_fed} 金），带了最危险的线却没换成塔伤！"
                )
                audit_obj = fp.get("hero_execution_audit")
                if isinstance(audit_obj, dict):
                    audit_obj.setdefault("headline_badges", []).append(
                        {"text": f"🗺️ 落单带线被抓 ×{p_solo_cnt}次", "tone": "bad"}
                    )
            elif is_core and jungle_farm_pct >= 58.0 and tower_dmg < 1800 and kp_pct < 55.0:
                style_badge = "🧛 缩壳野区吸血鬼"
                grade = "warn"
                verdict = (
                    f"⚠️ 地图空间利用偏消极：野区补刀占 {jungle_farm_pct}%（{neutral_kills}野 vs {lane_kills}线），"
                    f"长期缩在自家野区刷安全钱，既少顶危险线牵制（推塔 {tower_dmg}），参战率也仅有 {kp_pct}%。"
                )
            elif is_core and tower_dmg >= 4000 and p_solo_cnt <= 1:
                style_badge = "👑 顶级带线牵制大师"
                grade = "good"
                verdict = (
                    f"✓ 教科书级空间牵制：收线补刀 {lane_kills}（占 {lane_farm_pct}%）+ 建筑推塔高达 {tower_dmg}，"
                    f"全局中后期仅 {p_solo_cnt} 次落单被抓，真正做到了『带线逼塔牵制、看着小地图极限全身而退』！"
                )
                audit_obj = fp.get("hero_execution_audit")
                if isinstance(audit_obj, dict):
                    audit_obj.setdefault("headline_badges", []).append(
                        {"text": f"🗺️ 顶级带线牵制(塔伤{tower_dmg})", "tone": "good"}
                    )
            elif p_solo_cnt >= 3:
                style_badge = "🚨 迷雾乱逛提款机"
                grade = "bad"
                verdict = (
                    f"🚨 中后期高达 {p_solo_cnt} 次脱离大部队独自在迷雾/危险线乱逛被抓（{'、'.join(p_pickoff_details[:3])}），"
                    f"累计送出 {p_solo_gold_fed} 金，极大断送了本方控图节奏！"
                )
                audit_obj = fp.get("hero_execution_audit")
                if isinstance(audit_obj, dict):
                    audit_obj.setdefault("headline_badges", []).append(
                        {"text": f"🗺️ 迷雾落单被抓 ×{p_solo_cnt}次", "tone": "bad"}
                    )
            elif kp_pct >= 62.0 and p_solo_cnt <= 1:
                style_badge = "⚔️ 侵略控图发动机"
                grade = "good"
                verdict = (
                    f"✓ 空间嗅觉敏锐：参团率 {kp_pct}%，中后期仅 {p_solo_cnt} 次落单掉点，"
                    f"兵线/野区分配合理（收线 {lane_kills} / 刷野 {neutral_kills}），始终在有视野或队友掩护区活动。"
                )
            else:
                style_badge = "🛡️ 稳健抱团驻守" if p_solo_cnt <= 1 else "⚠️ 偶有盲区深带掉点"
                grade = "good" if p_solo_cnt <= 1 else "warn"
                verdict = (
                    f"收线补刀 {lane_kills}（{lane_farm_pct}%）/ 刷野 {neutral_kills}（{jungle_farm_pct}%），推塔伤害 {tower_dmg}；"
                    f"中后期发生 {p_solo_cnt} 次落单被抓"
                    + (f"（{'、'.join(p_pickoff_details[:2])}，喂钱 {p_solo_gold_fed} 金）。" if p_solo_cnt > 0 else "，位置感保持稳健。")
                )

            player_space_rows.append({
                "pos": pos_i,
                "hero_short_zh": fp["hero_short_zh"],
                "hero_img": fp["hero_img"],
                "personaname": fp["personaname"],
                "lane_kills": lane_kills,
                "neutral_kills": neutral_kills,
                "lane_farm_pct": lane_farm_pct,
                "jungle_farm_pct": jungle_farm_pct,
                "tower_damage": tower_dmg,
                "solo_pickoff_cnt": p_solo_cnt,
                "solo_gold_fed": p_solo_gold_fed,
                "deep_death_cnt": p_deep_death_cnt,
                "space_style_badge": style_badge,
                "grade": grade,
                "verdict": verdict,
            })

        solo_pickoff_events.sort(key=lambda x: x["time_sec"])
        if total_solo_pickoffs <= 3:
            side_verdict = (
                f"✓ 团队地图空间纪律严明：9 分钟后全队仅发生 {total_solo_pickoffs} 次落单被抓，"
                f"大哥收线与辅助抱团衔接紧凑，极少给对手白捡落单提款的机会。"
            )
        else:
            side_verdict = (
                f"🚨 地图空间警报：9 分钟后全队共发生 {total_solo_pickoffs} 次【脱离团队落单带无聊线 / 盲区乱逛被抓死】！"
                f"切忌在无假眼保护、无队友蹲后的情况下一个人过河道深带收线。"
            )

        return {
            "side": side_key,
            "side_verdict": side_verdict,
            "total_solo_pickoffs": total_solo_pickoffs,
            "solo_pickoff_events": solo_pickoff_events[:10],
            "player_space_rows": player_space_rows,
        }

    # =========================================================================
    # 八、承伤来源拆解与针对性防装审计 (Damage Inflictor Received & Defense Audit)
    # =========================================================================
    def analyze_side_damage_received(side_key: str) -> Dict[str, Any]:
        own_players = radiant_players if side_key == "radiant" else dire_players
        rows: List[Dict[str, Any]] = []
        team_auto_dmg = 0
        team_spell_dmg = 0

        for fp in sorted(own_players, key=lambda x: int(x["pos"])):
            pslot = int(fp["player_slot"])
            rp = raw_by_slot.get(pslot, {})
            dir_map = rp.get("damage_inflictor_received") or {}
            auto_dmg = int(dir_map.get("null") or 0)
            spell_entries: List[Tuple[str, int]] = []
            for k, v in dir_map.items():
                if k == "null":
                    continue
                iv = int(v or 0)
                if iv > 0:
                    spell_entries.append((str(k), iv))
            spell_entries.sort(key=lambda x: x[1], reverse=True)
            spell_dmg = sum(v for _, v in spell_entries)
            total_dmg = max(1, auto_dmg + spell_dmg)
            auto_pct = round(auto_dmg * 100.0 / total_dmg, 1)
            spell_pct = round(spell_dmg * 100.0 / total_dmg, 1)

            team_auto_dmg += auto_dmg
            team_spell_dmg += spell_dmg

            top_killers_zh: List[Dict[str, Any]] = []
            for k, v in spell_entries[:4]:
                zh_name = ITEMS_ZH.get(k) or get_ability_zh(k) or k
                top_killers_zh.append({
                    "key": k,
                    "zh_name": zh_name,
                    "damage": v,
                    "share_pct": round(v * 100.0 / total_dmg, 1),
                })

            final_keys = {str(it.get("key") or "") for it in (fp.get("final_items_rich") or [])}
            magic_def_owned = [
                ITEMS_ZH.get(k, k)
                for k in ("black_king_bar", "pipe", "glimmer_cape", "eternal_shroud", "mage_slayer", "sphere", "aeon_disk")
                if k in final_keys
            ]
            phys_def_owned = [
                ITEMS_ZH.get(k, k)
                for k in ("ghost", "crimson_guard", "shivas_guard", "assault", "butterfly", "solar_crest", "lotus_orb", "blade_mail", "hurricane_pike", "force_staff")
                if k in final_keys
            ]

            deaths_cnt = int(fp.get("deaths") or 0)
            top1_str = (
                f"{top_killers_zh[0]['zh_name']}({top_killers_zh[0]['damage']:,}伤)"
                if top_killers_zh
                else "平A普攻"
            )
            if spell_pct >= 62.0 and deaths_cnt >= 5 and not magic_def_owned:
                grade = "bad"
                verdict = (
                    f"🚨 防装严重缺失：全场高达 {spell_pct}% 承伤来自技能/法系爆发（头号凶手：{top1_str}），"
                    f"阵亡 {deaths_cnt} 次却到终局都没出 BKB / 微光 / 笛子 / 法师克星！"
                )
            elif auto_pct >= 52.0 and deaths_cnt >= 5 and not phys_def_owned:
                grade = "warn"
                verdict = (
                    f"⚠️ 物理防护不足：全场 {auto_pct}% 承伤（{auto_dmg:,}点）来自敌方物理平A右击，"
                    f"阵亡 {deaths_cnt} 次但缺乏绿杖 / 强袭 / 希瓦 / 推推等针对性防物理拉扯装。"
                )
            else:
                grade = "good"
                def_all = magic_def_owned + phys_def_owned
                def_txt = f"已配防装【{'、'.join(def_all[:3])}】" if def_all else "站位保持较好"
                verdict = (
                    f"✓ 承伤结构：{spell_pct}% 技能伤害（{spell_dmg:,}） vs {auto_pct}% 物理平A（{auto_dmg:,}），"
                    f"最大威胁源为 {top1_str}，{def_txt}。"
                )

            rows.append({
                "pos": int(fp["pos"]),
                "hero_short_zh": fp["hero_short_zh"],
                "hero_img": fp["hero_img"],
                "personaname": fp["personaname"],
                "total_dmg_taken": auto_dmg + spell_dmg,
                "auto_dmg": auto_dmg,
                "spell_dmg": spell_dmg,
                "auto_pct": auto_pct,
                "spell_pct": spell_pct,
                "top_killers": top_killers_zh,
                "def_items_owned": (magic_def_owned + phys_def_owned)[:4],
                "grade": grade,
                "verdict": verdict,
            })

        tot_team = max(1, team_auto_dmg + team_spell_dmg)
        t_spell_pct = round(team_spell_dmg * 100.0 / tot_team, 1)
        t_auto_pct = round(team_auto_dmg * 100.0 / tot_team, 1)
        side_verdict = (
            f"全队合计承受英雄伤害 {tot_team:,} 点：其中技能/物品伤害占 {t_spell_pct}%（{team_spell_dmg:,}），"
            f"物理平A普攻占 {t_auto_pct}%（{team_auto_dmg:,}）。"
        )
        return {
            "side": side_key,
            "side_verdict": side_verdict,
            "team_spell_pct": t_spell_pct,
            "team_auto_pct": t_auto_pct,
            "rows": rows,
        }

    # =========================================================================
    # 九、经济来源结构拆解 & 局内信号/暂停/公屏互动档案 (Gold Reasons & Pings/Pauses/Chat)
    # =========================================================================
    raw_pauses = match.get("pauses") or []
    raw_chat = match.get("chat") or []
    comeback_val = int(match.get("comeback") or 0)
    stomp_val = int(match.get("stomp") or 0)

    def analyze_side_economy_and_pings(side_key: str) -> Dict[str, Any]:
        own_players = radiant_players if side_key == "radiant" else dire_players
        econ_rows: List[Dict[str, Any]] = []
        max_ping_player = ("", 0)

        for fp in sorted(own_players, key=lambda x: int(x["pos"])):
            pslot = int(fp["player_slot"])
            rp = raw_by_slot.get(pslot, {})
            gr = rp.get("gold_reasons") or {}
            lane_g = max(0, int(gr.get("12") or 0))
            jungle_g = max(0, int(gr.get("13") or 0))
            kill_g = max(0, int(gr.get("11") or 0))
            obj_g = max(0, int(gr.get("6") or 0)) + max(0, int(gr.get("14") or 0))
            bounty_ward_g = max(0, int(gr.get("16") or 0)) + max(0, int(gr.get("20") or 0)) + max(0, int(gr.get("15") or 0))
            death_loss = abs(int(gr.get("0") or 0))
            buyback_loss = abs(min(0, int(gr.get("1") or 0)))

            pos_earned = max(1, lane_g + jungle_g + kill_g + obj_g + bounty_ward_g)
            lane_pct = round(lane_g * 100.0 / pos_earned, 1)
            jungle_pct = round(jungle_g * 100.0 / pos_earned, 1)
            kill_pct = round(kill_g * 100.0 / pos_earned, 1)
            obj_pct = round((obj_g + bounty_ward_g) * 100.0 / pos_earned, 1)

            pings_cnt = int(rp.get("pings") or 0)
            if pings_cnt > max_ping_player[1]:
                max_ping_player = (f"{fp['hero_short_zh']}({fp['personaname']})", pings_cnt)

            chatwheel_cnt = sum(
                1 for c in raw_chat
                if int(c.get("player_slot", -1)) == pslot
            )

            dmg_share = float(fp.get("hero_damage_share_pct") or 0.0)
            if kill_pct >= 32.0:
                econ_tag = "⚔️ 以战养战提款王"
            elif jungle_pct >= 38.0 and dmg_share < 18.0:
                econ_tag = "🧛 野区只进不出吸尘器"
            elif lane_pct >= 45.0:
                econ_tag = "🌾 扎实兵线收割机"
            elif death_loss + buyback_loss >= 2400:
                econ_tag = "💸 阵亡/买活散财童子"
            else:
                econ_tag = "⚖️ 均衡发育节奏手"

            econ_rows.append({
                "pos": int(fp["pos"]),
                "hero_short_zh": fp["hero_short_zh"],
                "hero_img": fp["hero_img"],
                "personaname": fp["personaname"],
                "lane_gold": lane_g,
                "jungle_gold": jungle_g,
                "kill_gold": kill_g,
                "obj_gold": obj_g + bounty_ward_g,
                "death_loss": death_loss,
                "buyback_loss": buyback_loss,
                "lane_pct": lane_pct,
                "jungle_pct": jungle_pct,
                "kill_pct": kill_pct,
                "obj_pct": obj_pct,
                "pings": pings_cnt,
                "chatwheel_cnt": chatwheel_cnt,
                "econ_tag": econ_tag,
            })

        total_pause_sec = sum(int(p.get("duration") or 0) for p in raw_pauses)
        pause_str = (
            f"全场共触发 {len(raw_pauses)} 次暂停（累计停表 {total_pause_sec} 秒）"
            if raw_pauses
            else "全场 0 暂停顺畅打完"
        )
        ping_king_str = (
            f"📡 信号狂点王：{max_ping_player[0]}（狂点 {max_ping_player[1]} 次地图信号）"
            if max_ping_player[1] > 0
            else "全员静默开黑"
        )
        swing_str = (
            f"📈 极限翻盘指数 {comeback_val:,} 金 / 碾压指数 {stomp_val:,} 金"
            if (comeback_val or stomp_val)
            else ""
        )

        return {
            "side": side_key,
            "side_verdict": " ｜ ".join(x for x in [ping_king_str, pause_str, swing_str] if x),
            "pause_count": len(raw_pauses),
            "pause_total_sec": total_pause_sec,
            "comeback": comeback_val,
            "stomp": stomp_val,
            "econ_rows": econ_rows,
        }

    # =========================================================================
    # 十、0:00 ~ 终局逐分钟时空回放器快照 (Minute-by-Minute Interactive Scrubber)
    # =========================================================================
    def build_minute_snapshots() -> List[Dict[str, Any]]:
        r_gold_adv = match.get("radiant_gold_adv") or []
        r_xp_adv = match.get("radiant_xp_adv") or []
        max_idx = len(r_gold_adv)
        if max_idx == 0:
            for rp in raw_players_list:
                t_arr = rp.get("times") or []
                if len(t_arr) > max_idx:
                    max_idx = len(t_arr)
        if max_idx == 0:
            return []

        # 预先整理每位玩家的核心成装购买时间表 (cost >= 1400 或在 ITEMS_ZH 中且非消耗品)
        SKIP_CONSUMABLES = {
            "tpscroll", "ward_observer", "ward_sentry", "smoke_of_deceit", "dust",
            "clarity", "faerie_fire", "enchanted_mango", "tango", "flask", "blood_grenade",
            "branches", "magic_stick", "sobi_mask", "ring_of_protection", "quelling_blade",
        }
        player_core_purchases: Dict[int, List[Dict[str, Any]]] = {}
        for fp in all_formatted:
            pslot = int(fp["player_slot"])
            rp = raw_by_slot.get(pslot, {})
            plog = rp.get("purchase_log") or []
            seen_items = set()
            core_list = []
            for entry in plog:
                ik = str(entry.get("key") or "")
                if not ik or ik in SKIP_CONSUMABLES or ik.startswith("recipe_"):
                    continue
                if ik not in ITEMS_ZH:
                    continue
                if ik in seen_items:
                    continue
                seen_items.add(ik)
                core_list.append({
                    "key": ik,
                    "zh": ITEMS_ZH.get(ik, ik),
                    "time": int(entry.get("time") or 0),
                    "img": f"https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/items/{ik}.png",
                })
            player_core_purchases[pslot] = core_list

        snapshots: List[Dict[str, Any]] = []
        for m in range(max_idx):
            sec_cutoff = m * 60
            sec_prev = (m - 1) * 60
            g_adv = int(r_gold_adv[m]) if m < len(r_gold_adv) else 0
            x_adv = int(r_xp_adv[m]) if m < len(r_xp_adv) else 0

            p_snap_list = []
            events_in_min: List[str] = []

            for fp in all_formatted:
                pslot = int(fp["player_slot"])
                rp = raw_by_slot.get(pslot, {})
                nw_arr = rp.get("networth_t") or rp.get("gold_t") or []
                lh_arr = rp.get("lh_t") or []
                dn_arr = rp.get("dn_t") or []
                xp_arr = rp.get("xp_t") or []

                nw_val = int(nw_arr[m]) if m < len(nw_arr) else int(fp.get("net_worth") or 0)
                lh_val = int(lh_arr[m]) if m < len(lh_arr) else int(fp.get("last_hits") or 0)
                dn_val = int(dn_arr[m]) if m < len(dn_arr) else int(fp.get("denies") or 0)
                xp_val = int(xp_arr[m]) if m < len(xp_arr) else 0

                items_now = [
                    {"key": it["key"], "zh": it["zh"], "img": it["img"]}
                    for it in player_core_purchases.get(pslot, [])
                    if it["time"] <= sec_cutoff
                ][-6:]

                p_snap_list.append({
                    "slot": pslot,
                    "side": "radiant" if pslot < 128 else "dire",
                    "pos": int(fp["pos"]),
                    "hero_short_zh": fp["hero_short_zh"],
                    "hero_img": fp["hero_img"],
                    "personaname": fp["personaname"],
                    "networth": nw_val,
                    "lh": lh_val,
                    "dn": dn_val,
                    "xp": xp_val,
                    "items": items_now,
                })

                # 收集这一分钟内该玩家的击杀事件
                if m > 0:
                    for k_ev in rp.get("kills_log") or []:
                        kt = int(k_ev.get("time") or 0)
                        if sec_prev < kt <= sec_cutoff:
                            v_hid = npc_to_hid.get(str(k_ev.get("key") or ""), 0)
                            v_fp = fmt_by_hid.get(v_hid)
                            v_zh = v_fp["hero_short_zh"] if v_fp else "敌方英雄"
                            events_in_min.append(f"⚔️ {fmt_mmss(kt)} {fp['hero_short_zh']} 击杀 {v_zh}")

            if m > 0:
                for obj in raw_objectives:
                    ot = int(obj.get("time") or 0)
                    if sec_prev < ot <= sec_cutoff:
                        otype = str(obj.get("type") or "")
                        if otype == "CHAT_MESSAGE_ROSHAN_KILL":
                            events_in_min.append(f"🐉 {fmt_mmss(ot)} 肉山被击杀")
                        elif otype == "building_kill":
                            events_in_min.append(f"🏰 {fmt_mmss(ot)} 建筑被摧毁")

            p_snap_list.sort(key=lambda x: x["networth"], reverse=True)
            snapshots.append({
                "minute": m,
                "time_str": f"{m:02d}:00",
                "radiant_gold_adv": g_adv,
                "radiant_xp_adv": x_adv,
                "players": p_snap_list,
                "events": events_in_min[:6],
            })

        return snapshots

    # =========================================================================
    # 十一、1~5 号位同位置宿敌 1v1 正面对位审判 & OpenDota 全球同英雄百分位标尺
    # =========================================================================
    BENCHMARK_LABELS_ZH: Dict[str, str] = {
        "gold_per_min": "GPM打钱",
        "xp_per_min": "XPM经验",
        "kills_per_min": "击杀效率",
        "last_hits_per_min": "补刀效率",
        "hero_damage_per_min": "英雄输出",
        "hero_healing_per_min": "团队治疗",
        "tower_damage": "建筑推塔",
        "stuns_per_min": "硬控眩晕",
        "lhten": "10分钟补刀",
    }

    def analyze_side_role_mirrors(side_key: str) -> Dict[str, Any]:
        own_players = sorted(
            radiant_players if side_key == "radiant" else dire_players,
            key=lambda x: int(x.get("pos") or 9),
        )
        opp_players = sorted(
            dire_players if side_key == "radiant" else radiant_players,
            key=lambda x: int(x.get("pos") or 9),
        )
        opp_by_pos = {int(p.get("pos") or 0): p for p in opp_players}

        mirror_rows: List[Dict[str, Any]] = []
        won_lanes_cnt = 0
        won_overall_cnt = 0
        biggest_gap_pair = ("", -999.0)
        biggest_loss_pair = ("", 999.0)

        for own_p in own_players:
            pos_i = int(own_p.get("pos") or 1)
            opp_p = opp_by_pos.get(pos_i) or (opp_players[pos_i - 1] if pos_i - 1 < len(opp_players) else opp_players[0])
            own_slot = int(own_p["player_slot"])
            opp_slot = int(opp_p["player_slot"])
            own_rp = raw_by_slot.get(own_slot, {})
            opp_rp = raw_by_slot.get(opp_slot, {})

            own_hid = int(own_p.get("hero_id") or 0)
            opp_hid = int(opp_p.get("hero_id") or 0)
            own_npc = hero_const_by_id.get(own_hid, {}).get("npc") or f"npc_dota_hero_{own_hid}"
            opp_npc = hero_const_by_id.get(opp_hid, {}).get("npc") or f"npc_dota_hero_{opp_hid}"

            # 1) 宿敌直接互杀比 (Direct 1v1 Kills)
            h2h_own_kills = int((own_rp.get("killed") or {}).get(opp_npc, 0))
            h2h_opp_kills = int((opp_rp.get("killed") or {}).get(own_npc, 0))

            # 2) 10 分钟对位补刀与经济
            own_gt = own_rp.get("gold_t") or own_rp.get("networth_t") or []
            opp_gt = opp_rp.get("gold_t") or opp_rp.get("networth_t") or []
            own_lht = own_rp.get("lh_t") or []
            opp_lht = opp_rp.get("lh_t") or []
            own_dnt = own_rp.get("dn_t") or []
            opp_dnt = opp_rp.get("dn_t") or []

            gold10_own = int(own_gt[10]) if len(own_gt) > 10 else int(own_p.get("gold_at_10m") or 0)
            gold10_opp = int(opp_gt[10]) if len(opp_gt) > 10 else int(opp_p.get("gold_at_10m") or 0)
            lh10_own = int(own_lht[10]) if len(own_lht) > 10 else 0
            lh10_opp = int(opp_lht[10]) if len(opp_lht) > 10 else 0
            dn10_own = int(own_dnt[10]) if len(own_dnt) > 10 else 0
            dn10_opp = int(opp_dnt[10]) if len(opp_dnt) > 10 else 0
            gold10_diff = gold10_own - gold10_opp
            if gold10_diff >= 200:
                won_lanes_cnt += 1

            # 3) 全场核心硬指标对比
            nw_own = int(own_p.get("net_worth") or 0)
            nw_opp = int(opp_p.get("net_worth") or 0)
            nw_diff = nw_own - nw_opp
            gpm_own = int(own_p.get("gpm") or 0)
            gpm_opp = int(opp_p.get("gpm") or 0)
            dmg_own = int(own_p.get("hero_damage") or 0)
            dmg_opp = int(opp_p.get("hero_damage") or 0)
            dmg_diff = dmg_own - dmg_opp
            td_own = int(own_p.get("tower_damage") or 0)
            td_opp = int(opp_p.get("tower_damage") or 0)
            kp_own = float(own_p.get("kill_participation_pct") or 0.0)
            kp_opp = float(opp_p.get("kill_participation_pct") or 0.0)
            stuns_own = round(float(own_rp.get("stuns") or 0.0), 1)
            stuns_opp = round(float(opp_rp.get("stuns") or 0.0), 1)
            wards_own = int(own_p.get("obs_placed") or 0) + int(own_p.get("sen_placed") or 0)
            wards_opp = int(opp_p.get("obs_placed") or 0) + int(opp_p.get("sen_placed") or 0)
            dew_own = int(own_p.get("obs_destroyed") or 0)
            dew_opp = int(opp_p.get("obs_destroyed") or 0)
            rating_own = float(own_p.get("rating_score") or 60.0)
            rating_opp = float(opp_p.get("rating_score") or 60.0)

            # 4) 全球同英雄百分位 (OpenDota Benchmarks)
            def extract_benchmarks(rp_obj: Dict[str, Any]) -> Tuple[float, List[Dict[str, Any]]]:
                bm = rp_obj.get("benchmarks") or {}
                items = []
                pct_vals = []
                for k, label_zh in BENCHMARK_LABELS_ZH.items():
                    cell = bm.get(k)
                    if isinstance(cell, dict) and cell.get("pct") is not None:
                        pct_val = round(float(cell.get("pct") or 0.0) * 100.0, 1)
                        raw_val = cell.get("raw") or 0
                        if k == "hero_healing_per_min" and float(raw_val or 0) <= 5:
                            continue
                        if k == "stuns_per_min" and float(raw_val or 0) <= 0.05:
                            continue
                        pct_vals.append(pct_val)
                        items.append({
                            "key": k,
                            "label_zh": label_zh,
                            "pct": pct_val,
                            "raw": round(float(raw_val or 0), 1),
                        })
                items.sort(key=lambda x: x["pct"], reverse=True)
                avg_pct = round(sum(pct_vals) / max(1, len(pct_vals)), 1) if pct_vals else 50.0
                return avg_pct, items[:4]

            own_bm_avg, own_bm_top = extract_benchmarks(own_rp)
            opp_bm_avg, opp_bm_top = extract_benchmarks(opp_rp)

            # 5) 计算同位置对位胜负指数 (own_edge: 正数代表我方占优，负数代表敌方占优)
            is_core = pos_i in (1, 2, 3)
            if is_core:
                own_power = (
                    rating_own * 1.1
                    + (nw_own / 1000.0) * 1.4
                    + (dmg_own / 1000.0) * 1.1
                    + (td_own / 1000.0) * 1.2
                    + (gold10_own / 1000.0) * 1.8
                    + h2h_own_kills * 4.5
                )
                opp_power = (
                    rating_opp * 1.1
                    + (nw_opp / 1000.0) * 1.4
                    + (dmg_opp / 1000.0) * 1.1
                    + (td_opp / 1000.0) * 1.2
                    + (gold10_opp / 1000.0) * 1.8
                    + h2h_opp_kills * 4.5
                )
            else:
                own_power = (
                    rating_own * 1.1
                    + kp_own * 0.45
                    + wards_own * 1.4
                    + dew_own * 3.2
                    + stuns_own * 0.45
                    + (dmg_own / 1000.0) * 0.8
                    + h2h_own_kills * 4.0
                )
                opp_power = (
                    rating_opp * 1.1
                    + kp_opp * 0.45
                    + wards_opp * 1.4
                    + dew_opp * 3.2
                    + stuns_opp * 0.45
                    + (dmg_opp / 1000.0) * 0.8
                    + h2h_opp_kills * 4.0
                )

            tot_power = max(1.0, own_power + opp_power)
            own_share_pct = round(own_power * 100.0 / tot_power, 1)
            opp_share_pct = round(100.0 - own_share_pct, 1)
            edge_pts = round(own_share_pct - 50.0, 1)

            if edge_pts > biggest_gap_pair[1]:
                biggest_gap_pair = (f"{pos_i}号位 {own_p['hero_short_zh']} vs {opp_p['hero_short_zh']}", edge_pts)
            if edge_pts < biggest_loss_pair[1]:
                biggest_loss_pair = (f"{pos_i}号位 {own_p['hero_short_zh']} vs {opp_p['hero_short_zh']}", edge_pts)

            if edge_pts >= 6.5:
                won_overall_cnt += 1
                verdict_tag = "👑 对位完爆 (GAP)"
                grade = "good"
            elif edge_pts >= 2.0:
                won_overall_cnt += 1
                verdict_tag = "⚔️ 对位压制 (小优)"
                grade = "good"
            elif edge_pts > -2.0:
                verdict_tag = "⚖️ 旗鼓相当 (均势)"
                grade = "even"
            elif edge_pts > -6.5:
                verdict_tag = "⚠️ 对位小劣 (被压)"
                grade = "warn"
            else:
                verdict_tag = "🚨 对位被打穿 (被爆金币)"
                grade = "bad"

            if is_core:
                summary_txt = (
                    f"10m对线经济 {gold10_own:,} vs {gold10_opp:,}（{'+' if gold10_diff>=0 else ''}{gold10_diff:,}）｜"
                    f"终局经济 {nw_own:,} vs {nw_opp:,}（{'+' if nw_diff>=0 else ''}{nw_diff:,}）｜"
                    f"英雄输出 {dmg_own:,} vs {dmg_opp:,}｜正面对位互杀 {h2h_own_kills} : {h2h_opp_kills}。"
                )
            else:
                summary_txt = (
                    f"参战率 {kp_own}% vs {kp_opp}%｜真假眼 {wards_own}颗(排{dew_own}) vs {wards_opp}颗(排{dew_opp})｜"
                    f"硬控 {stuns_own}s vs {stuns_opp}s｜正面对位互杀 {h2h_own_kills} : {h2h_opp_kills}。"
                )

            mirror_rows.append({
                "pos": pos_i,
                "own_hero": own_p["hero_short_zh"],
                "own_img": own_p["hero_img"],
                "own_player": own_p["personaname"],
                "own_kda": own_p["kda"],
                "own_rating": rating_own,
                "opp_hero": opp_p["hero_short_zh"],
                "opp_img": opp_p["hero_img"],
                "opp_player": opp_p["personaname"],
                "opp_kda": opp_p["kda"],
                "opp_rating": rating_opp,
                "h2h_own_kills": h2h_own_kills,
                "h2h_opp_kills": h2h_opp_kills,
                "gold10_own": gold10_own,
                "gold10_opp": gold10_opp,
                "gold10_diff": gold10_diff,
                "lh10_own": f"{lh10_own}/{dn10_own}",
                "lh10_opp": f"{lh10_opp}/{dn10_opp}",
                "nw_own": nw_own,
                "nw_opp": nw_opp,
                "nw_diff": nw_diff,
                "gpm_own": gpm_own,
                "gpm_opp": gpm_opp,
                "dmg_own": dmg_own,
                "dmg_opp": dmg_opp,
                "dmg_diff": dmg_diff,
                "td_own": td_own,
                "td_opp": td_opp,
                "kp_own": kp_own,
                "kp_opp": kp_opp,
                "stuns_own": stuns_own,
                "stuns_opp": stuns_opp,
                "wards_own": f"{wards_own}眼/排{dew_own}",
                "wards_opp": f"{wards_opp}眼/排{dew_opp}",
                "own_bm_avg": own_bm_avg,
                "opp_bm_avg": opp_bm_avg,
                "own_bm_top": own_bm_top,
                "opp_bm_top": opp_bm_top,
                "own_share_pct": own_share_pct,
                "opp_share_pct": opp_share_pct,
                "verdict_tag": verdict_tag,
                "grade": grade,
                "summary_txt": summary_txt,
            })

        side_verdict = (
            f"1~5 号位同位置正面对账：本方在 {won_overall_cnt}/5 个位置上打出对位优势（10 分钟对线期占优 {won_lanes_cnt}/5 路）。"
            + (f" 最大对位压制点：【{biggest_gap_pair[0]}】；" if biggest_gap_pair[1] > 0 else "")
            + (f" 最大对位出血点：【{biggest_loss_pair[0]}】。" if biggest_loss_pair[1] < -2.0 else "")
        )
        return {
            "side": side_key,
            "side_verdict": side_verdict,
            "won_lanes_cnt": won_lanes_cnt,
            "won_overall_cnt": won_overall_cnt,
            "mirror_rows": mirror_rows,
        }

    # =========================================================================
    # 十二、买活死尸检 · 信使惨案 · 肉山盾/魔晶归属 · 7.38 中立装备锻造附魔审计
    # =========================================================================
    NEUTRAL_ITEMS_ZH: Dict[str, str] = {
        "dormant_curio": "休眠珍品",
        "polliwog_charm": "蝌蚪护符",
        "chipped_vest": "碎裂背心",
        "possessed_mask": "附魔面具",
        "seeds_of_serenity": "宁静之种",
        "kobold_cup": "狗头人酒杯",
        "occult_bracelet": "秘术手镯",
        "ash_legion_shield": "灰烬军团盾",
        "duelist_gloves": "决斗家手套",
        "mana_draught": "魔力药饮",
        "pogo_stick": "弹跳玩偶",
        "searing_signet": "灼热印记",
        "essence_ring": "精华指环",
        "dezun_bloodrite": "德尊血仪",
        "gunpowder_gauntlets": "火药护手",
        "serrated_shiv": "锯齿短刀",
        "jidi_pollen_bag": "吉迪花粉袋",
        "spellslinger": "咒术投石索",
        "stormcrafter": "造风者",
        "cloak_of_flames": "火焰斗篷",
        "rattlecage": "响笼",
        "crippling_crossbow": "致残弩",
        "unrelenting_eye": "不屈之眼",
        "giant_maul": "巨型战锤",
        "spider_legs": "蜘蛛腿",
        "fallen_sky": "天崩",
        "desolator_2": "寂灭",
        "poor_mans_shield": "穷鬼盾",
        "psychic_headband": "通灵头带",
        "riftshadow_prism": "裂影棱镜",
        "conjurers_catalyst": "咒术师催化剂",
        "heavy_blade": "巫术重刃",
        "stonefeather_satchel": "石羽行囊",
        "enchanters_bauble": "附魔师饰品",
        "prophets_pendulum": "先知钟摆",
        "partisans_brand": "游击队烙印",
        "weighted_dice": "灌铅骰子",
        "foragers_kit": "采集者工具包",
        "idol_of_screeauk": "丝克瑞奥克神像",
        "dagger_of_ristul": "瑞斯图尔匕首",
        "medallion_of_courage": "勇气勋章",
        "dandelion_amulet": "蒲公英护符",
        "flayers_bota": "剥皮者皮囊",
        "guardian_shell": "守护甲壳",
    }

    ENHANCEMENTS_ZH: Dict[str, str] = {
        "enhancement_greedy": "贪婪(+GPM/-攻击)",
        "enhancement_quickened": "迅捷(+移速)",
        "enhancement_tough": "坚韧(+护甲/攻)",
        "enhancement_brawny": "强壮(+生命/回血)",
        "enhancement_mystical": "神秘(+回蓝/魔抗)",
        "enhancement_alert": "机敏(+攻速/夜视)",
        "enhancement_keen_eyed": "敏锐(+施法距离)",
        "enhancement_timeless": "永恒(+技能增强)",
        "enhancement_vampiric": "吸血(+双吸血)",
        "enhancement_vital": "生机(+生命恢复)",
        "enhancement_evolved": "演化(+主属性)",
        "enhancement_fleetfooted": "轻捷(+移速)",
    }

    def analyze_side_macro_and_neutrals(side_key: str) -> Dict[str, Any]:
        own_players = sorted(
            radiant_players if side_key == "radiant" else dire_players,
            key=lambda x: int(x.get("pos") or 9),
        )
        is_rad = (side_key == "radiant")

        # 1) 买活战果与「买活死 Dieback」尸检
        buyback_events: List[Dict[str, Any]] = []
        dieback_cnt = 0
        clutch_bb_cnt = 0

        for fp in own_players:
            pslot = int(fp["player_slot"])
            rp = raw_by_slot.get(pslot, {})
            bblog = rp.get("buyback_log") or []
            dlog = rp.get("deaths_log") or []
            klog = rp.get("kills_log") or []
            tfs_for_p = tf_records_by_slot.get(pslot, [])

            for bb in bblog:
                bb_sec = int(bb.get("time") or 0)
                # 检查买活后 100 秒内是否再次阵亡（买活死 Dieback）
                dieback_death = next(
                    (d for d in dlog if bb_sec < int(d.get("time") or 0) <= bb_sec + 100),
                    None,
                )
                kills_after = [
                    k for k in klog if bb_sec <= int(k.get("time") or 0) <= bb_sec + 95
                ]
                tf_after = [
                    tfr for tfr in tfs_for_p
                    if tfr["end_sec"] >= bb_sec and tfr["start_sec"] <= bb_sec + 90
                ]
                dmg_after = sum(int(t.get("damage") or 0) for t in tf_after)

                if dieback_death is not None:
                    dieback_cnt += 1
                    db_t = int(dieback_death.get("time") or bb_sec)
                    db_dead_s = int(dieback_death.get("time_dead") or 80)
                    outcome_tag = "💀 致命买活死 (Dieback)"
                    severity = "bad"
                    detail = (
                        f"在 {fmt_mmss(bb_sec)} 交出买活后仅存活 {db_t - bb_sec} 秒，于 {fmt_mmss(db_t)} 再次暴毙（买活死读秒 {db_dead_s}s 无法买活）！"
                    )
                    audit_obj = fp.get("hero_execution_audit")
                    if isinstance(audit_obj, dict):
                        audit_obj.setdefault("headline_badges", []).append(
                            {"text": f"💀 {fmt_mmss(db_t)} 致命买活死", "tone": "bad"}
                        )
                elif len(kills_after) > 0 or dmg_after >= 1200:
                    clutch_bb_cnt += 1
                    outcome_tag = "🟢 救世有效买活"
                    severity = "good"
                    detail = (
                        f"在 {fmt_mmss(bb_sec)} 果断买活返场，90秒内收下 {len(kills_after)} 颗人头、打出 {dmg_after:,} 点团战伤害，成功稳住局势！"
                    )
                else:
                    outcome_tag = "🟡 空买观望 (0战果)"
                    severity = "warn"
                    detail = (
                        f"在 {fmt_mmss(bb_sec)} 交出买活，但返场后 90 秒内 0 击杀、团战伤害仅 {dmg_after:,} 点，白白亏损买活金与长 CD。"
                    )

                buyback_events.append({
                    "time_str": fmt_mmss(bb_sec),
                    "time_sec": bb_sec,
                    "pos": int(fp["pos"]),
                    "hero_short_zh": fp["hero_short_zh"],
                    "hero_img": fp["hero_img"],
                    "personaname": fp["personaname"],
                    "outcome_tag": outcome_tag,
                    "severity": severity,
                    "detail": detail,
                })

        buyback_events.sort(key=lambda x: x["time_sec"])

        # 2) 信使击杀与掉鸡惨案 (CHAT_MESSAGE_COURIER_LOST) + 肉山盾归属
        courier_events: List[Dict[str, Any]] = []
        own_couriers_lost = 0
        own_couriers_killed = 0
        roshan_events: List[Dict[str, Any]] = []

        for obj in raw_objectives:
            ot = int(obj.get("time") or 0)
            otype = str(obj.get("type") or "")
            if otype == "CHAT_MESSAGE_COURIER_LOST":
                lost_team = int(obj.get("team") or 0)  # 2=Radiant lost courier, 3=Dire lost courier
                killer_slot = obj.get("killer")
                killer_fp = fmt_by_slot.get(int(killer_slot)) if killer_slot is not None and int(killer_slot) >= 0 else None
                killer_str = (
                    f"{killer_fp['pos']}号位 {killer_fp['hero_short_zh']}({killer_fp['personaname']})"
                    if killer_fp
                    else "敌方英雄/防御塔"
                )
                is_own_lost = (is_rad and lost_team == 2) or ((not is_rad) and lost_team == 3)
                if is_own_lost:
                    own_couriers_lost += 1
                else:
                    own_couriers_killed += 1
                is_laning_courier = (ot <= 600)
                courier_events.append({
                    "time_str": fmt_mmss(ot),
                    "time_sec": ot,
                    "is_own_lost": is_own_lost,
                    "event_tag": (
                        "🚨 本方掉鸡惨案 (对线断补给)" if (is_own_lost and is_laning_courier)
                        else ("⚠️ 本方信使阵亡" if is_own_lost else "🎯 狙杀敌方信使")
                    ),
                    "detail": (
                        f"{fmt_mmss(ot)} {'本方' if is_own_lost else '敌方'}信使被 {killer_str} 击杀"
                        + ("（对线期断运鞋/大药/魔瓶，极大伤线！）" if is_laning_courier else "。")
                    ),
                })
            elif otype in ("CHAT_MESSAGE_ROSHAN_KILL", "CHAT_MESSAGE_AEGIS", "CHAT_MESSAGE_AEGIS_STOLEN"):
                pslot_r = obj.get("player_slot")
                fp_r = fmt_by_slot.get(int(pslot_r)) if pslot_r is not None else None
                if otype == "CHAT_MESSAGE_AEGIS_STOLEN" and fp_r:
                    side_zh_r = "天辉" if fp_r.get("side") in ("radiant", "天辉") else "夜魇"
                    roshan_events.append(
                        f"🚨 {fmt_mmss(ot)} 惊天抢盾！{side_zh_r} {fp_r['pos']}号位 {fp_r['hero_short_zh']}({fp_r['personaname']}) 虎口夺食抢走不朽之守护！"
                    )
                elif otype == "CHAT_MESSAGE_AEGIS" and fp_r:
                    side_zh_r = "天辉" if fp_r.get("side") in ("radiant", "天辉") else "夜魇"
                    roshan_events.append(
                        f"🛡️ {fmt_mmss(ot)} {side_zh_r} {fp_r['pos']}号位 {fp_r['hero_short_zh']}({fp_r['personaname']}) 拾取肉山不朽盾"
                    )

        # 3) 阿哈利姆魔晶时间轴 & 7.38 中立装备锻造附魔审计
        neutral_craft_rows: List[Dict[str, Any]] = []
        shard_count = 0

        for fp in own_players:
            pslot = int(fp["player_slot"])
            pos_i = int(fp["pos"])
            rp = raw_by_slot.get(pslot, {})

            # 查找魔晶 (permanent_buff == 12) 获取时间
            pbuffs = rp.get("permanent_buffs") or []
            shard_buff = next((b for b in pbuffs if int(b.get("permanent_buff") or 0) == 12), None)
            if shard_buff is not None:
                shard_count += 1
                gt = int(shard_buff.get("grant_time") or 0)
                shard_str = f"💎 {fmt_mmss(gt)} 获得魔晶"
            elif int(rp.get("aghanims_shard") or 0) > 0:
                shard_count += 1
                shard_str = "💎 已装备魔晶"
            else:
                shard_str = "未获魔晶"

            # 解析 7.38 neutral_item_history
            nhist = rp.get("neutral_item_history") or []
            craft_steps: List[str] = []
            greedy_on_core = False
            for nh in nhist:
                t_nh = int(nh.get("time") or 0)
                in_key = str(nh.get("item_neutral") or "")
                en_key = str(nh.get("item_neutral_enhancement") or "")
                in_zh = NEUTRAL_ITEMS_ZH.get(in_key) or ITEMS_ZH.get(in_key) or in_key
                en_zh = ENHANCEMENTS_ZH.get(en_key) or en_key
                if pos_i in (1, 2) and en_key == "enhancement_greedy":
                    greedy_on_core = True
                if in_zh and en_zh:
                    craft_steps.append(f"{fmt_mmss(t_nh)}【{in_zh} · {en_zh}】")
                elif in_zh:
                    craft_steps.append(f"{fmt_mmss(t_nh)}【{in_zh}】")
                elif en_zh:
                    craft_steps.append(f"{fmt_mmss(t_nh)} 附魔【{en_zh}】")

            if greedy_on_core:
                craft_verdict = "⚠️ 1/2号位核心选了【贪婪】附魔（虽然加钱但直接扣攻击力），中后期团战切忌留贪婪词条！"
                grade = "warn"
            elif len(craft_steps) == 0:
                craft_verdict = "⚠️ 整局未记录到中立装备锻造切换记录。"
                grade = "warn"
            else:
                craft_verdict = f"✓ 共迭代 {len(craft_steps)} 次中立装与附魔词条，节奏正常。"
                grade = "good"

            neutral_craft_rows.append({
                "pos": pos_i,
                "hero_short_zh": fp["hero_short_zh"],
                "hero_img": fp["hero_img"],
                "personaname": fp["personaname"],
                "shard_str": shard_str,
                "craft_steps": craft_steps,
                "craft_verdict": craft_verdict,
                "grade": grade,
            })

        side_verdict = (
            f"全队共交出 {len(buyback_events)} 次买活（其中 {dieback_cnt} 次致命买活死、{clutch_bb_cnt} 次有效救世买活）｜"
            f"信使博弈：击杀敌方 {own_couriers_killed} 只信使 / 本方掉鸡 {own_couriers_lost} 只｜"
            f"阿哈利姆魔晶普及率：{shard_count}/5 人。"
        )
        return {
            "side": side_key,
            "side_verdict": side_verdict,
            "dieback_cnt": dieback_cnt,
            "clutch_bb_cnt": clutch_bb_cnt,
            "own_couriers_lost": own_couriers_lost,
            "own_couriers_killed": own_couriers_killed,
            "shard_count": shard_count,
            "buyback_events": buyback_events,
            "courier_events": courier_events,
            "roshan_events": roshan_events,
            "neutral_craft_rows": neutral_craft_rows,
        }

    return {
        "hero_execution_by_side": {
            "dire": [x for x in all_hero_exec if x["side"] == "dire"],
            "radiant": [x for x in all_hero_exec if x["side"] == "radiant"],
        },
        "support_vision_by_side": {
            "dire": analyze_side_vision_quality("dire"),
            "radiant": analyze_side_vision_quality("radiant"),
        },
        "stacking_and_smoke_by_side": {
            "dire": analyze_side_stacking_and_smokes("dire"),
            "radiant": analyze_side_stacking_and_smokes("radiant"),
        },
        "laning_mechanics_by_side": {
            "dire": analyze_side_laning_mechanics("dire"),
            "radiant": analyze_side_laning_mechanics("radiant"),
        },
        "tp_rotation_by_side": {
            "dire": analyze_side_tp_and_rotations("dire"),
            "radiant": analyze_side_tp_and_rotations("radiant"),
        },
        "unpressed_saves_by_side": {
            "dire": analyze_side_unpressed_saves("dire"),
            "radiant": analyze_side_unpressed_saves("radiant"),
        },
        "map_space_by_side": {
            "dire": analyze_side_map_space_and_pickoffs("dire"),
            "radiant": analyze_side_map_space_and_pickoffs("radiant"),
        },
        "damage_received_by_side": {
            "dire": analyze_side_damage_received("dire"),
            "radiant": analyze_side_damage_received("radiant"),
        },
        "economy_and_pings_by_side": {
            "dire": analyze_side_economy_and_pings("dire"),
            "radiant": analyze_side_economy_and_pings("radiant"),
        },
        "role_mirror_by_side": {
            "dire": analyze_side_role_mirrors("dire"),
            "radiant": analyze_side_role_mirrors("radiant"),
        },
        "macro_objectives_by_side": {
            "dire": analyze_side_macro_and_neutrals("dire"),
            "radiant": analyze_side_macro_and_neutrals("radiant"),
        },
        "minute_snapshots": build_minute_snapshots(),
    }

