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
from dota_constants_zh import (
    ACTIVE_SAVE_ITEMS_ZH,
    GOLD_REASON_KEYS,
    ITEMS_ZH,
    get_ability_zh,
    get_held_active_save_items,
)
from hero_profiles_126 import get_hero_profile_126


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
    "lina_laguna_blade": {
        "zh": "神灭斩 (火女大招)",
        "type": "single_nuke_ult",
        "good_avg_hits": 0.90,
        "warn_avg_hits": 0.75,
        "unit_label": "人次",
    },
    "ringmaster_wheel": {
        "zh": "奇观之轮 (百戏王转盘大)",
        "type": "aoe_disable_ult",
        "good_avg_hits": 2.2,
        "warn_avg_hits": 1.3,
        "unit_label": "人次",
    },
    "venomancer_noxious_plague": {
        "zh": "恶性瘟疫 (剧毒传染大)",
        "type": "aoe_disable_ult",
        "good_avg_hits": 2.0,
        "warn_avg_hits": 1.2,
        "unit_label": "人次",
    },
    "brewmaster_primal_split": {
        "zh": "元素分离 (酒仙大招分身)",
        "type": "team_buff_ult",
        "good_avg_hits": 0.0,
        "warn_avg_hits": 0.0,
        "unit_label": "次元素分身",
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
    "hoodwink_bushwhack": {"zh": "野地奇袭 (松鼠捆树)", "good_pct": 65.0, "warn_pct": 40.0},
    "dragon_knight_dragon_tail": {"zh": "神龙摆尾 (龙骑拍晕)", "good_pct": 85.0, "warn_pct": 65.0},
    "dragon_knight_fireball": {"zh": "魔晶火球", "good_pct": 80.0, "warn_pct": 50.0},
    "pugna_nether_ward": {"zh": "幽冥守卫 (骨法插棒子电人)", "good_pct": 100.0, "warn_pct": 60.0},
    "pugna_nether_blast": {"zh": "幽冥爆轰 (爆塔/爆人)", "good_pct": 35.0, "warn_pct": 20.0},
    "furion_sprout": {"zh": "发芽 (先知框人)", "good_pct": 70.0, "warn_pct": 45.0},
    "marci_grapple": {"zh": "过肩摔 (玛西背人)", "good_pct": 65.0, "warn_pct": 40.0},
    "lina_light_strike_array": {"zh": "光击阵 (火女T眩晕)", "good_pct": 58.0, "warn_pct": 38.0},
    "slark_pounce": {"zh": "突袭 (小鱼跳锁人)", "good_pct": 55.0, "warn_pct": 35.0},
    "ringmaster_impalement": {"zh": "穿刺飞刀 (百戏王飞刀)", "good_pct": 65.0, "warn_pct": 42.0},
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
    if not match.get("version"):
        for p in all_formatted:
            p["hero_execution_audit"] = {"available": False}
        unavail = {"available": False, "dire": {"available": False}, "radiant": {"available": False}}
        return {
            "available": False,
            "hero_execution_by_side": dict(unavail),
            "itemization_audit_by_side": dict(unavail),
            "damage_quality_and_build_by_side": dict(unavail),
            "support_vision_by_side": dict(unavail),
            "stacking_and_smoke_by_side": dict(unavail),
            "laning_mechanics_by_side": dict(unavail),
            "tp_rotation_by_side": dict(unavail),
            "unpressed_saves_by_side": dict(unavail),
            "map_space_by_side": dict(unavail),
            "damage_received_by_side": dict(unavail),
            "economy_and_pings_by_side": dict(unavail),
            "role_mirror_by_side": dict(unavail),
            "macro_objectives_by_side": dict(unavail),
            "minute_snapshots": {
                "format": "columnar_v1",
                "minutes": [],
                "radiant_gold_adv": [],
                "radiant_xp_adv": [],
                "events": [],
                "item_zh_map": {},
                "players": [],
            },
        }

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


    from microscope_sections.hero_execution import build_hero_execution_section
    from microscope_sections.itemization_and_quality import build_itemization_and_quality_sections
    from microscope_sections.laning_tp_saves import build_laning_tp_saves_sections
    from microscope_sections.snapshots_matchups_objectives import build_snapshots_matchups_objectives_sections
    from microscope_sections.space_damage_econ import build_space_damage_econ_sections
    from microscope_sections.vision_stack_smoke import build_vision_stack_smoke_sections

    ctx: Dict[str, Any] = {
        "match": match,
        "radiant_players": radiant_players,
        "dire_players": dire_players,
        "hero_const_by_id": hero_const_by_id,
        "npc_to_hid": npc_to_hid,
        "all_formatted": all_formatted,
        "fmt_by_slot": fmt_by_slot,
        "fmt_by_hid": fmt_by_hid,
        "raw_players_list": raw_players_list,
        "raw_by_slot": raw_by_slot,
        "duration_sec": duration_sec,
        "duration_min": duration_min,
        "raw_tfs": raw_tfs,
        "tf_records_by_slot": tf_records_by_slot,
        "raw_objectives": match.get("objectives") or [],
    }

    s_hero = build_hero_execution_section(ctx)
    s_item = build_itemization_and_quality_sections(ctx)
    s_vis = build_vision_stack_smoke_sections(ctx)
    s_lane = build_laning_tp_saves_sections(ctx)
    s_space = build_space_damage_econ_sections(ctx)
    s_snap = build_snapshots_matchups_objectives_sections(ctx)

    return {
        **s_hero,
        **s_item,
        **s_vis,
        **s_lane,
        **s_space,
        **s_snap,
    }
