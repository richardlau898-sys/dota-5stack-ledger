# -*- coding: utf-8 -*-
import math
from typing import Any, Dict, List, Optional, Set, Tuple
from dota_constants_zh import (
    ACTIVE_SAVE_ITEMS_ZH,
    GOLD_REASON_KEYS,
    ITEMS_ZH,
    get_ability_zh,
    get_held_active_save_items,
)
from hero_profiles_126 import get_hero_profile_126
from tactical_microscope_engine import (
    BIG_ULTIMATE_CATALOG,
    RUNE_TYPES_ZH,
    SKILLSHOT_CATALOG,
    classify_ward_map_zone,
    fmt_mmss,
)


def build_itemization_and_quality_sections(ctx: Dict[str, Any]) -> Dict[str, Any]:
    match = ctx["match"]
    radiant_players = ctx["radiant_players"]
    dire_players = ctx["dire_players"]
    hero_const_by_id = ctx["hero_const_by_id"]
    npc_to_hid = ctx["npc_to_hid"]
    all_formatted = ctx["all_formatted"]
    fmt_by_slot = ctx["fmt_by_slot"]
    fmt_by_hid = ctx["fmt_by_hid"]
    raw_players_list = ctx["raw_players_list"]
    raw_by_slot = ctx["raw_by_slot"]
    duration_sec = ctx["duration_sec"]
    duration_min = ctx["duration_min"]
    raw_tfs = ctx["raw_tfs"]
    tf_records_by_slot = ctx["tf_records_by_slot"]
    raw_objectives = ctx["raw_objectives"]
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
    # =========================================================================
    # 十三、全员出装路线与「蠢装/漏出克制装/憋大件断档」处刑台 (Itemization & Counter-Build Audit)
    # =========================================================================
    HIGH_REGEN_HERO_IDS = {
        36: "死灵法师(高回血/魔晶护罩)",
        59: "哈斯卡(狂战士之血回血)",
        93: "斯拉克(暗影之舞高回血)",
        73: "炼金术士(化学狂暴回血)",
        99: "钢背兽(法术吸血/高恢复)",
        54: "噬魂鬼(盛宴吸血)",
        58: "魅惑魔女(自然之助加血)",
        45: "帕格纳(生命汲取)",
        8: "主宰(治疗守卫)",
        10: "变体精灵(属性转换/高吸血)",
        98: "伐木机(活性护甲回血)",
        104: "军团指挥官(勇气之霎吸血)",
        42: "冥魂大帝(吸血光环)",
        102: "亚巴顿(回光返照)",
        110: "凤凰(烈日炙烤百分比回血)",
        69: "末日使者(焦土回血)",
    }

    PASSIVE_MONSTER_HERO_IDS = {
        99: "钢背兽(刚毛后背减伤)",
        67: "幽鬼(折射反弹)",
        93: "斯拉克(能量转移偷属性)",
        44: "幻影刺客(模糊闪避/暴击)",
        96: "半人马战行者(反击/高肉度)",
        29: "潮汐猎人(海妖外壳解控减伤)",
        58: "魅惑魔女(不可侵犯减攻速)",
        49: "龙骑士(龙族血统护甲)",
        6: "卓尔游侠(射手天赋穿透)",
        98: "伐木机(活性护甲)",
        47: "冥界亚龙(腐蚀皮肤魔抗)",
        42: "冥魂大帝(本命一击)",
        102: "亚巴顿(魔霭诅咒)",
    }

    PURGEABLE_SAVE_HERO_IDS = {
        36: "死灵法师(幽魂护罩绿身)",
        57: "全能骑士(物理免疫/驱散)",
        58: "魅惑魔女(小精灵加血)",
        45: "帕格纳(衰老虚无)",
        21: "风行者(风步100%闪避)",
        79: "暗影恶魔(崩裂禁锢/驱散)",
        111: "神谕者(气运之末/救人)",
        13: "帕克(吹风/相位转移拉扯)",
    }

    SKIP_MINOR_ITEMS = {
        "tpscroll", "ward_observer", "ward_sentry", "smoke_of_deceit", "dust",
        "clarity", "faerie_fire", "enchanted_mango", "tango", "flask", "blood_grenade",
        "branches", "magic_stick", "sobi_mask", "ring_of_protection", "quelling_blade",
        "circlet", "mantle", "gauntlets", "slippers", "robe", "belt_of_strength",
        "band_of_elvenskin", "staff_of_wizardry", "blades_of_attack", "gloves",
        "chainmail", "helm_of_iron_will", "broadsword", "claymore", "javelin",
        "mithril_hammer", "ogre_axe", "blade_of_alacrity", "vitality_booster",
        "energy_booster", "point_booster", "platemail", "talisman_of_evasion",
        "hyperstone", "ultimate_orb", "demon_edge", "mystic_staff", "reaver", "eagle",
        "relic", "crown", "wind_lace", "infused_raindrop", "blight_stone", "orb_of_venom",
        "fluffy_hat", "cloak", "void_stone", "ring_of_health", "morbid_mask",
        "voodoo_mask", "shadow_amulet", "ghost", "boots", "magic_wand", "bracer",
        "wraith_band", "null_talisman", "soul_ring", "bottle", "orb_of_corrosion",
        "falcon_blade", "urn_of_shadows", "buckler", "headdress", "ring_of_basilius",
    }

    def analyze_side_itemization_and_counters(side_key: str) -> Dict[str, Any]:
        own_players = sorted(
            radiant_players if side_key == "radiant" else dire_players,
            key=lambda x: int(x.get("pos") or 9),
        )
        opp_players = sorted(
            dire_players if side_key == "radiant" else radiant_players,
            key=lambda x: int(x.get("pos") or 9),
        )

        # 收集双方所有买过的装备与终局装备
        own_item_buyers: Dict[str, List[str]] = {}
        opp_item_buyers: Dict[str, List[str]] = {}

        for fp in own_players:
            pslot = int(fp["player_slot"])
            rp = raw_by_slot.get(pslot, {})
            f_keys = {str(it.get("key") or "") for it in (fp.get("final_items_rich") or [])}
            for entry in rp.get("purchase_log") or []:
                ik = str(entry.get("key") or "")
                if ik:
                    f_keys.add(ik)
            if int(rp.get("aghanims_shard") or 0) or fp.get("aghanims_shard"):
                f_keys.add("aghanims_shard")
            if int(rp.get("aghanims_scepter") or 0) or fp.get("aghanims_scepter"):
                f_keys.add("ultimate_scepter")
            for ik in f_keys:
                own_item_buyers.setdefault(ik, []).append(f"{fp['pos']}号位{fp['hero_short_zh']}")

        for op in opp_players:
            pslot = int(op["player_slot"])
            rp = raw_by_slot.get(pslot, {})
            f_keys = {str(it.get("key") or "") for it in (op.get("final_items_rich") or [])}
            for entry in rp.get("purchase_log") or []:
                ik = str(entry.get("key") or "")
                if ik:
                    f_keys.add(ik)
            for ik in f_keys:
                opp_item_buyers.setdefault(ik, []).append(op["hero_short_zh"])

        team_counter_checks: List[Dict[str, Any]] = []

        # 1) 🩸 减疗/禁疗审计（克制高回血/吸血怪）
        regen_threats = []
        for op in opp_players:
            ohid = int(op.get("hero_id") or 0)
            if ohid in HIGH_REGEN_HERO_IDS:
                regen_threats.append(HIGH_REGEN_HERO_IDS[ohid])
        for r_item, r_zh in [("satanic", "撒旦之邪力"), ("heart", "恐鳌之心"), ("eternal_shroud", "永世法衣"), ("bloodstone", "血精石")]:
            if opp_item_buyers.get(r_item):
                regen_threats.append(f"{'/'.join(opp_item_buyers[r_item])}({r_zh})")

        anti_heal_owners = []
        for ah_item, ah_zh in [("spirit_vessel", "魂之灵瓮(大骨灰)"), ("skadi", "斯嘉蒂之眼(冰眼)"), ("shivas_guard", "希瓦的守护")]:
            for buyer in own_item_buyers.get(ah_item, []):
                anti_heal_owners.append(f"{buyer}【{ah_zh}】")
        if any(int(fp.get("hero_id") or 0) == 68 for fp in own_players):
            anti_heal_owners.append("远古冰魄【冰晶爆轰】")

        if regen_threats:
            if anti_heal_owners:
                team_counter_checks.append({
                    "category": "🩸 减疗/禁疗克制装审计",
                    "enemy_threats": "、".join(regen_threats[:4]),
                    "our_response": "、".join(anti_heal_owners),
                    "grade": "good",
                    "verdict": f"✓ 针对敌方【{'、'.join(regen_threats[:3])}】的高回血/吸血体系，本方由 {'、'.join(anti_heal_owners)} 做出减疗装应对。",
                })
            else:
                team_counter_checks.append({
                    "category": "🩸 减疗/禁疗克制装审计",
                    "enemy_threats": "、".join(regen_threats[:4]),
                    "our_response": "🚨 全队 0 大骨灰 / 0 冰眼 / 0 希瓦",
                    "grade": "bad",
                    "verdict": f"🚨 严重漏出克制装：敌方坐拥【{'、'.join(regen_threats[:3])}】强回血/吸血体系，但我方全队竟然 0 把大骨灰(魂之灵瓮)、0 把冰眼、0 把希瓦，团战白打无效伤害！",
                })

        # 2) 🗡️ 破坏被动审计（克制被动怪）
        passive_threats = [
            PASSIVE_MONSTER_HERO_IDS[int(op.get("hero_id") or 0)]
            for op in opp_players
            if int(op.get("hero_id") or 0) in PASSIVE_MONSTER_HERO_IDS
        ]
        break_owners = [f"{b}【白银之锋(大隐刀)】" for b in own_item_buyers.get("silver_edge", [])]
        for fp in own_players:
            hid_own = int(fp.get("hero_id") or 0)
            if hid_own == 47:
                break_owners.append(f"{fp['hero_short_zh']}【剧毒攻击/幽冥剧毒】")
            elif hid_own == 123:
                break_owners.append(f"{fp['hero_short_zh']}【一箭穿心破被动】")
            elif hid_own == 79 and ("ultimate_scepter" in own_item_buyers):
                break_owners.append(f"{fp['hero_short_zh']}【A杖邪恶净化】")

        if passive_threats:
            if break_owners:
                team_counter_checks.append({
                    "category": "🗡️ 破坏被动(Break)审计",
                    "enemy_threats": "、".join(passive_threats[:4]),
                    "our_response": "、".join(break_owners),
                    "grade": "good",
                    "verdict": f"✓ 针对敌方【{'、'.join(passive_threats[:3])}】的核心被动，本方配置了 {'、'.join(break_owners)} 进行破坏。",
                })
            else:
                team_counter_checks.append({
                    "category": "🗡️ 破坏被动(Break)审计",
                    "enemy_threats": "、".join(passive_threats[:4]),
                    "our_response": "⚠️ 全队 0 把大隐刀(白银之锋)",
                    "grade": "warn" if len(passive_threats) == 1 else "bad",
                    "verdict": f"⚠️ 缺乏破被动手段：面对敌方【{'、'.join(passive_threats[:3])}】，本方 1~3 号位无人合成【白银之锋(大隐刀)】，正面硬啃敌方被动极其吃力。",
                })

        # 3) 🔮 驱散/否决审计（克制绿杖/吹风/护盾救人）
        purge_threats = [
            PURGEABLE_SAVE_HERO_IDS[int(op.get("hero_id") or 0)]
            for op in opp_players
            if int(op.get("hero_id") or 0) in PURGEABLE_SAVE_HERO_IDS
        ]
        for p_item, p_zh in [("ghost", "幽魂权杖(绿杖)"), ("ethereal_blade", "虚灵之刃"), ("cyclone", "Eul的神圣法杖(吹风)"), ("wind_waker", "风之杖(大吹风)"), ("glimmer_cape", "微光披风")]:
            if opp_item_buyers.get(p_item):
                purge_threats.append(f"{'/'.join(opp_item_buyers[p_item])}({p_zh})")

        purge_owners = []
        for pg_item, pg_zh in [("nullifier", "否决坠饰"), ("disperser", "驱散之刃"), ("diffusal_blade", "净魂之刃(散失)"), ("cyclone", "吹风杖"), ("wind_waker", "风之杖")]:
            for buyer in own_item_buyers.get(pg_item, []):
                purge_owners.append(f"{buyer}【{pg_zh}】")

        if purge_threats:
            has_nullifier = bool(own_item_buyers.get("nullifier"))
            if has_nullifier or len(purge_owners) >= 2:
                team_counter_checks.append({
                    "category": "🔮 进攻驱散/否决克制审计",
                    "enemy_threats": "、".join(purge_threats[:4]),
                    "our_response": "、".join(purge_owners),
                    "grade": "good",
                    "verdict": f"✓ 面对敌方【{'、'.join(purge_threats[:3])}】的保命拉扯装，本方由 {'、'.join(purge_owners)} 做出驱散/否决克制。",
                })
            else:
                team_counter_checks.append({
                    "category": "🔮 进攻驱散/否决克制审计",
                    "enemy_threats": "、".join(purge_threats[:4]),
                    "our_response": "、".join(purge_owners) if purge_owners else "🚨 全队 0 否决坠饰 / 0 驱散装",
                    "grade": "bad" if len(purge_threats) >= 2 else "warn",
                    "verdict": f"🚨 进攻驱散缺失：敌方拥有【{'、'.join(purge_threats[:3])}】等保命装，但我方物理核心整局 0 把【否决坠饰(Nullifier)】，缺乏进攻驱散手段限制敌方救人装！",
                })

        # 4) 🛡️ 团队解控与辅助救人装审计（BKB/分身/微光/推推/莲花）
        core_bkb_owners = own_item_buyers.get("black_king_bar", [])
        sup_save_owners = []
        for sv_item, sv_zh in [("glimmer_cape", "微光披风"), ("force_staff", "原力法杖(推推)"), ("hurricane_pike", "大推推"), ("lotus_orb", "清莲宝珠(莲花)"), ("solar_crest", "炎阳纹章"), ("pipe", "洞察烟斗(笛子)")]:
            for buyer in own_item_buyers.get(sv_item, []):
                sup_save_owners.append(f"{buyer}【{sv_zh}】")

        team_counter_checks.append({
            "category": "🛡️ 核心免控(BKB)与团队救人装审计",
            "enemy_threats": f"敌方先手控制与爆发体系（共 {sum(int(op.get('kills') or 0) for op in opp_players)} 次击杀）",
            "our_response": (
                f"BKB：{len(core_bkb_owners)}把（{'/'.join(core_bkb_owners) if core_bkb_owners else '无'}）｜"
                f"团队救人装：{'、'.join(sup_save_owners[:4]) if sup_save_owners else '🚨 0微光/0推推/0莲花'}"
            ),
            "grade": "good" if (len(core_bkb_owners) >= 2 and len(sup_save_owners) >= 2) else ("bad" if (len(core_bkb_owners) == 0 or len(sup_save_owners) == 0) else "warn"),
            "verdict": (
                f"✓ 免控与团队救人装齐备：本方共做出 {len(core_bkb_owners)} 把 BKB 与 {len(sup_save_owners)} 件团队保护装（{'、'.join(sup_save_owners[:3])}）。"
                if (len(core_bkb_owners) >= 2 and len(sup_save_owners) >= 2)
                else f"🚨 防守装备断层：全队仅 {len(core_bkb_owners)} 把 BKB、{len(sup_save_owners)} 件团队救人装（微光/推推/莲花/笛子），团战容错率极低！"
            ),
        })

        # 个人出装路线、卡壳断档期 & 命脉装审判
        player_item_rows: List[Dict[str, Any]] = []
        bad_build_cnt = 0

        for fp in own_players:
            pslot = int(fp["player_slot"])
            pos_i = int(fp["pos"])
            hid = int(fp.get("hero_id") or 0)
            rp = raw_by_slot.get(pslot, {})
            plog = rp.get("purchase_log") or []
            dlog = rp.get("deaths_log") or []
            prof = get_hero_profile_126(hid, pos_i, fp["hero_short_zh"])

            # 提取主件购买时间线（去重，过滤消耗品与小散件）
            major_timeline: List[Dict[str, Any]] = []
            seen_major = set()
            prev_t = 0
            max_gap_sec = 0
            stall_start_sec = 0
            stall_end_sec = 0

            for entry in plog:
                ik = str(entry.get("key") or "")
                t_sec = int(entry.get("time") or 0)
                if not ik or ik in SKIP_MINOR_ITEMS or ik.startswith("recipe_"):
                    continue
                if ik not in ITEMS_ZH or ik in seen_major:
                    continue
                seen_major.add(ik)
                gap_s = max(0, t_sec - prev_t) if prev_t > 0 else max(0, t_sec)
                if prev_t >= 480 and gap_s > max_gap_sec:
                    max_gap_sec = gap_s
                    stall_start_sec = prev_t
                    stall_end_sec = t_sec
                if t_sec >= 0:
                    prev_t = t_sec
                major_timeline.append({
                    "key": ik,
                    "zh": ITEMS_ZH.get(ik, ik),
                    "time_sec": t_sec,
                    "time_str": fmt_mmss(t_sec),
                    "gap_min": round(gap_s / 60.0, 1),
                    "img": f"https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/items/{ik}.png",
                })

            # 检查最后一件成装到比赛结束是否也存在超长断档
            if prev_t >= 600 and (duration_sec - prev_t) > max_gap_sec:
                max_gap_sec = duration_sec - prev_t
                stall_start_sec = prev_t
                stall_end_sec = duration_sec

            deaths_in_stall = sum(
                1 for d in dlog
                if stall_start_sec <= int(d.get("time") or 0) <= stall_end_sec
            ) if max_gap_sec >= 600 else 0

            max_gap_min = round(max_gap_sec / 60.0, 1)
            if max_gap_min >= 11.5:
                stall_window_zh = f"🚨 {fmt_mmss(stall_start_sec)}–{fmt_mmss(stall_end_sec)} 卡壳断档 {max_gap_min} 分钟（期间连死 {deaths_in_stall} 次憋不出大件）"
            elif max_gap_min >= 8.5:
                stall_window_zh = f"⚠️ {fmt_mmss(stall_start_sec)}–{fmt_mmss(stall_end_sec)} 发育放缓 {max_gap_min} 分钟（期间死 {deaths_in_stall} 次）"
            else:
                stall_window_zh = f"✓ 出装丝滑（最大间隔仅 {max_gap_min} 分钟）"

            # 检查本英雄命脉装与魔晶是否漏出
            has_shard = bool(int(rp.get("aghanims_shard") or 0) or fp.get("aghanims_shard") or ("aghanims_shard" in seen_major))
            has_bkb = "black_king_bar" in seen_major
            bkb_time_str = next((x["time_str"] for x in major_timeline if x["key"] == "black_king_bar"), "")

            issues_list: List[str] = []
            fix_list: List[str] = []

            shard_desc = prof.get("shard_desc") or ""
            core_hint_str = prof.get("core_item_hint") or "标准核心装"
            if ("必出" in shard_desc or hid in (93, 27, 30, 86, 64, 90, 18, 114)) and duration_min >= 24 and not has_shard:
                issues_list.append(f"🚫 整局漏出命脉魔晶（{shard_desc or '核心机制质变装'}）")
                fix_list.append("20分钟前必须补出1400金【阿哈利姆魔晶】产生质变")

            if pos_i in (1, 2, 3):
                needs_bkb_by_prof = ("BKB" in core_hint_str) or ("黑皇杖" in core_hint_str) or (pos_i in (1, 2) and hid not in (94, 67, 61, 110))
                if needs_bkb_by_prof and (not has_bkb) and int(fp.get("deaths") or 0) >= 5 and duration_min >= 26:
                    issues_list.append(f"🚫 阵亡 {fp.get('deaths')} 次却整局不出 BKB 黑皇杖")
                    fix_list.append(f"第二/三件大件必须果断锁下【黑皇杖(BKB)】保证团战输出环境（推荐路线：{core_hint_str}）")
                elif (not needs_bkb_by_prof) and int(fp.get("deaths") or 0) >= 9 and not any(k in seen_major for k in ("black_king_bar", "lotus_orb", "cyclone", "wind_waker", "aeon_disk", "pipe", "heavens_halberd")):
                    issues_list.append(f"🚫 阵亡 {fp.get('deaths')} 次却缺乏解控/自救装（无吹风/莲花/BKB/盘子）")
                    fix_list.append(f"面对敌方高频沉默/打断，应补出【吹风杖 / 清莲宝珠 / BKB】保证技能释放与生存容错（推荐路线：{core_hint_str}）")
                elif has_bkb:
                    bkb_sec = next((x["time_sec"] for x in major_timeline if x["key"] == "black_king_bar"), 0)
                    if bkb_sec >= 2100 and int(fp.get("deaths") or 0) >= 6:
                        issues_list.append(f"⚠️ BKB 拖到 {bkb_time_str} 才憋出来（此前已死多次）")
                        fix_list.append("逆风局切忌贪输出装，应把 BKB 顺位提前到 24 分钟前")
                if regen_threats and not anti_heal_owners and pos_i in (1, 3):
                    fix_list.append("面对敌方高回血怪应补出【斯嘉蒂之眼(冰眼) / 希瓦的守护】")
                if passive_threats and not break_owners and pos_i in (1, 2):
                    fix_list.append("面对敌方被动怪应合成【白银之锋(大隐刀)】破除被动")
                if purge_threats and not own_item_buyers.get("nullifier") and pos_i == 1:
                    fix_list.append("后期切后排必补【否决坠饰(Nullifier)】直接废掉敌方绿杖/吹风/护罩")
            else:
                has_any_save = any(k in seen_major for k in ("glimmer_cape", "force_staff", "solar_crest", "lotus_orb", "blink", "aeon_disk", "wind_waker"))
                if not has_any_save and duration_min >= 24:
                    issues_list.append("🚫 辅助整局 0 救人装（无微光/推推/莲花/跳刀）")
                    fix_list.append(f"辅助第一件成装优先做【微光披风 / 原力法杖(推推)】（推荐路线：{core_hint_str}）")
                if regen_threats and not own_item_buyers.get("spirit_vessel") and pos_i == 4:
                    fix_list.append("面对敌方高回血阵容，4号位第一件应直奔【魂之灵瓮(大骨灰)】")

            if issues_list:
                bad_build_cnt += 1
                grade = "bad"
                verdict_badge = "🚨 出装路线事故"
            elif max_gap_min >= 11.5:
                grade = "warn"
                verdict_badge = "⚠️ 中期憋装断档"
            else:
                grade = "good"
                verdict_badge = "✓ 出装契合局势"

            if not fix_list:
                fix_list.append(f"本局核心出装契合【{fp['hero_short_zh']}】定位（推荐路线：{core_hint_str}）")

            player_item_rows.append({
                "pos": pos_i,
                "hero_short_zh": fp["hero_short_zh"],
                "hero_img": fp["hero_img"],
                "personaname": fp["personaname"],
                "core_reference_zh": core_hint_str,
                "shard_reference_zh": shard_desc,
                "has_shard": has_shard,
                "has_bkb": has_bkb,
                "bkb_time_str": bkb_time_str,
                "major_timeline": major_timeline,
                "max_gap_min": max_gap_min,
                "deaths_in_stall": deaths_in_stall,
                "stall_window_zh": stall_window_zh,
                "issues_list": issues_list,
                "fix_advice_zh": "；".join(fix_list[:2]) + "。",
                "verdict_badge": verdict_badge,
                "grade": grade,
                "evidence": "inferred",
            })

        for tcc in team_counter_checks:
            tcc["evidence"] = "inferred"

        bad_counter_cnt = sum(1 for c in team_counter_checks if c["grade"] == "bad")
        if bad_counter_cnt == 0 and bad_build_cnt == 0:
            side_verdict = "✓ 全队出装理解在线：针对敌方阵容的克制装备（减疗/破被动/驱散/免控救人）与个人核心命脉装均已到位！"
        else:
            side_verdict = (
                f"🚨 出装审判抓包：全队存在 {bad_counter_cnt} 项【针对敌方阵容的克制装严重缺失】、"
                f"{bad_build_cnt} 名选手出现【漏出命脉魔晶 / 整局不出BKB / 辅助0救人装】！"
            )

        return {
            "side": side_key,
            "evidence": "inferred",
            "side_verdict": side_verdict,
            "conclusions": [{"text": side_verdict, "kind": "side_verdict", "evidence": "inferred"}],
            "bad_counter_cnt": bad_counter_cnt,
            "bad_build_cnt": bad_build_cnt,
            "team_counter_checks": team_counter_checks,
            "player_item_rows": player_item_rows,
        }

    # =========================================================================
    # 14. 伤害含金量拆解（真切核 vs 刮肉盾假伤害）· 1~18级加点天赋审判 · 永久Buff叠层审计
    # =========================================================================
    import json as _json
    from pathlib import Path as _Path

    _catalog_path = _Path(__file__).resolve().parent.parent / "ability_id_catalog.json"
    try:
        _ABILITY_CATALOG = _json.loads(_catalog_path.read_text(encoding="utf-8"))
    except Exception:
        _ABILITY_CATALOG = {"by_id": {}, "hero_basic_skills": {}}
    _AID_BY_ID: Dict[str, Dict[str, Any]] = _ABILITY_CATALOG.get("by_id") or {}
    _HERO_BASIC_SKILLS: Dict[str, List[str]] = _ABILITY_CATALOG.get("hero_basic_skills") or {}
    _HERO_TALENT_TIERS: Dict[str, Dict[str, str]] = _ABILITY_CATALOG.get("hero_talent_tiers") or {}

    TANK_SPONGE_HERO_KEYS = {
        "pudge", "brewmaster", "bristleback", "centaur", "tidehunter",
        "axe", "abyssal_underlord", "undying", "skeleton_king", "dragon_knight",
        "primal_beast", "shredder", "abaddon", "ogre_magi", "treant",
        "kunkka", "alchemist", "necrolyte", "huskar", "mars", "earth_spirit",
        "elder_titan", "sand_king", "spirit_breaker", "night_stalker", "clockwerk",
    }

    PERMANENT_BUFF_CATALOG: Dict[int, Dict[str, Any]] = {
        1: {"zh": "🌙 银月之晶吞噬", "unit": "层(+60攻速)"},
        2: {"zh": "👑 阿哈利姆神杖赐福(融A杖)", "unit": ""},
        3: {"zh": "🧠 沉默术士·智力窃取", "unit": "点永久智力", "good_per_min": 0.6, "warn_per_min": 0.3},
        4: {"zh": "🥩 帕吉·腐肉堆积", "unit": "层永久力量", "good_per_min": 0.55, "warn_per_min": 0.3},
        5: {"zh": "⚔️ 军团指挥官·决斗加攻", "unit": "点永久攻击力", "good_per_min": 3.5, "warn_per_min": 1.2},
        6: {"zh": "📖 知识之书", "unit": "本"},
        7: {"zh": "⚡ 莱恩·死亡一指叠层", "unit": "层(+40伤害/层)", "good_per_min": 0.22, "warn_per_min": 0.08},
        8: {"zh": "🐟 斯拉克·能量转移永久敏捷", "unit": "层永久敏捷", "good_per_min": 0.5, "warn_per_min": 0.32},
        9: {"zh": "🛡️ 孽主·衰退光环永久加攻", "unit": "点攻击力"},
        10: {"zh": "💰 赏金猎人·忍术/追踪劫掠金", "unit": "金", "good_per_min": 25.0, "warn_per_min": 12.0},
        12: {"zh": "💎 阿哈利姆魔晶激活", "unit": ""},
        13: {"zh": "🪓 斧王·淘汰之刃永久护甲", "unit": "层护甲", "good_per_min": 0.18, "warn_per_min": 0.08},
        14: {"zh": "💀 瘟疫法师·死神镰刀叠层", "unit": "层永久恢复", "good_per_min": 0.18, "warn_per_min": 0.08},
        19: {"zh": "✨ 英雄先天/命石成长累计值", "unit": "点"},
        22: {"zh": "❄️ 寒冬飞龙·极寒赐福", "unit": ""},
        23: {"zh": "🪄 拉比克·奥术至尊/窃取叠层", "unit": "层", "good_per_min": 0.4, "warn_per_min": 0.2},
        24: {"zh": "🌊 潮汐猎人·海妖外壳永久格挡", "unit": "层格挡", "good_per_min": 0.45, "warn_per_min": 0.22},
        25: {"zh": "🔥 先天被动觉醒", "unit": "阶"},
    }

    HERO_EXPECTED_STACK_BUFF: Dict[str, Tuple[int, str, float]] = {
        "slark": (8, "能量转移永久敏捷", 0.35),
        "pudge": (4, "腐肉堆积力量层数", 0.32),
        "lion": (7, "死亡一指叠层", 0.10),
        "legion_commander": (5, "决斗永久攻击力", 1.5),
        "silencer": (3, "永久智力窃取", 0.35),
        "axe": (13, "淘汰之刃永久护甲", 0.08),
        "necrolyte": (14, "死神镰刀永久恢复层数", 0.08),
        "bounty_hunter": (10, "忍术/追踪劫掠金钱", 12.0),
        "tidehunter": (24, "海妖外壳永久格挡", 0.25),
        "rubick": (23, "奥术至尊窃取叠层", 0.20),
    }

    SUB_SKILL_REMAP: Dict[str, str] = {
        "phoenix_launch_fire_spirit": "phoenix_fire_spirits",
        "phoenix_icarus_dive_stop": "phoenix_icarus_dive",
        "phoenix_sun_ray_stop": "phoenix_sun_ray",
        "phoenix_sun_ray_toggle_move": "phoenix_sun_ray",
        "kunkka_return": "kunkka_x_marks_the_spot",
        "puck_ethereal_jaunt": "puck_illusory_orb",
        "Tiny_toss_tree": "tiny_avalanche",
        "monkey_king_primal_spring": "monkey_king_tree_dance",
        "monkey_king_primal_spring_early": "monkey_king_tree_dance",
        "nevermore_shadowraze2": "nevermore_shadowraze1",
        "nevermore_shadowraze3": "nevermore_shadowraze1",
        "alchemist_unstable_concoction_throw": "alchemist_unstable_concoction",
        "pangolier_gyroshell_stop": "pangolier_gyroshell",
        "ancient_apparition_ice_blast_release": "ancient_apparition_ice_blast",
        "bane_nightmare_end": "bane_nightmare",
        "shadow_demon_shadow_poison_release": "shadow_demon_shadow_poison",
        "dawnbreaker_converge": "dawnbreaker_celestial_hammer",
        "hoodwink_sharpshooter_release": "hoodwink_sharpshooter",
        "ringmaster_tame_the_beasts_crack": "ringmaster_tame_the_beasts",
        "rubick_telekinesis_land": "rubick_telekinesis",
        "rubick_telekinesis_land_self": "rubick_telekinesis",
        "faceless_void_time_walk_reverse": "faceless_void_time_walk",
        "nyx_assassin_unburrow": "nyx_assassin_burrow",
        "spectre_reality": "spectre_haunt",
        "tusk_launch_snowball": "tusk_snowball",
        "elder_titan_return_spirit": "elder_titan_ancestral_spirit",
        "wisp_tether_break": "wisp_tether",
        "keeper_of_the_light_illuminate_end": "keeper_of_the_light_illuminate",
        "templar_assassin_trap": "templar_assassin_psionic_trap",
        "techies_reactive_tazer_stop": "techies_reactive_tazer",
    }

    _hid_to_npc: Dict[int, str] = {int(v): str(k) for k, v in (npc_to_hid or {}).items()}

    def _hero_npc_from_player(p_obj: Dict[str, Any], raw_obj: Dict[str, Any]) -> str:
        hid = int(p_obj.get("hero_id") or raw_obj.get("hero_id") or 0)
        if hid in _hid_to_npc:
            return _hid_to_npc[hid]
        hc = hero_const_by_id.get(hid) or {}
        if hc.get("name"):
            return str(hc["name"])
        return str(p_obj.get("hero_npc") or "")

    def analyze_side_damage_quality_and_skill_builds(side_key: str) -> Dict[str, Any]:
        own_list = dire_players if side_key == "dire" else radiant_players
        opp_list = radiant_players if side_key == "dire" else dire_players
        own_ordered = sorted(own_list, key=lambda x: int(x.get("pos") or 9))
        opp_ordered = sorted(opp_list, key=lambda x: int(x.get("pos") or 9))

        opp_by_npc: Dict[str, Dict[str, Any]] = {}
        for op in opp_ordered:
            raw_op = raw_by_slot.get(int(op.get("player_slot", -1)), {})
            h_npc = _hero_npc_from_player(op, raw_op)
            if h_npc:
                opp_by_npc[h_npc] = op

        # 识别敌方「前排肉盾海绵」：3号位 或 处于坦克池中的3/4/5号位（排除1/2号位脆皮/远敏核心，确保打1/2号位算切核）
        opp_tank_npcs = set()
        for h_npc, op in opp_by_npc.items():
            short_k = h_npc.replace("npc_dota_hero_", "")
            op_pos = int(op.get("pos") or 3)
            if op_pos == 3 or (op_pos in (3, 4, 5) and short_k in TANK_SPONGE_HERO_KEYS):
                opp_tank_npcs.add(h_npc)

        player_rows = []
        fake_dmg_suspects_cnt = 0
        true_core_slayers_cnt = 0
        skill_build_issues_cnt = 0

        for p in own_ordered:
            slot = int(p.get("player_slot", -1))
            raw_p = raw_by_slot.get(slot, {})
            pos = int(p.get("pos") or 1)
            h_short = p.get("hero_short_zh") or ""
            h_npc = _hero_npc_from_player(p, raw_p)
            h_key = h_npc.replace("npc_dota_hero_", "")
            total_hero_dmg = int(p.get("hero_damage") or raw_p.get("hero_damage") or 0)
            total_kills = int(p.get("kills") or raw_p.get("kills") or 0)

            # 1) 拆解对敌方 5 人的伤害与击杀分布
            raw_dmg_dict = raw_p.get("damage") or {}
            raw_killed_dict = raw_p.get("killed") or {}
            target_breakdown = []
            sum_enemy_dmg = 0
            core_12_dmg = 0
            core_12_kills = 0
            tank_sponge_dmg = 0
            tank_sponge_kills = 0
            backline_sup_dmg = 0
            backline_sup_kills = 0
            tank_victim_names = []

            for op_npc, op_obj in opp_by_npc.items():
                d_val = int(raw_dmg_dict.get(op_npc) or 0)
                k_val = int(raw_killed_dict.get(op_npc) or 0)
                op_pos = int(op_obj.get("pos") or 3)
                op_zh = op_obj.get("hero_short_zh") or op_npc.replace("npc_dota_hero_", "")
                is_tank = op_npc in opp_tank_npcs
                is_core_12 = op_pos in (1, 2)
                sum_enemy_dmg += d_val
                if is_core_12:
                    core_12_dmg += d_val
                    core_12_kills += k_val
                if is_tank:
                    tank_sponge_dmg += d_val
                    tank_sponge_kills += k_val
                    if d_val >= 3500:
                        tank_victim_names.append(f"{op_pos}号位{op_zh}")
                elif not is_core_12:
                    backline_sup_dmg += d_val
                    backline_sup_kills += k_val

                target_breakdown.append({
                    "hero_short_zh": op_zh,
                    "hero_img": op_obj.get("hero_img") or "",
                    "pos": op_pos,
                    "is_tank_sponge": is_tank,
                    "is_core_12": is_core_12,
                    "role_tag_zh": "🥩 前排肉盾" if is_tank else ("🎯 核心双C" if is_core_12 else "🪶 脆皮后排"),
                    "dmg": d_val,
                    "kills": k_val,
                })

            denom_dmg = max(1, sum_enemy_dmg)
            for tb in target_breakdown:
                tb["dmg_pct"] = round(tb["dmg"] * 100.0 / denom_dmg, 1)
            target_breakdown.sort(key=lambda x: x["dmg"], reverse=True)

            core_12_pct = round(core_12_dmg * 100.0 / denom_dmg, 1)
            tank_sponge_pct = round(tank_sponge_dmg * 100.0 / denom_dmg, 1)
            backline_sup_pct = round(backline_sup_dmg * 100.0 / denom_dmg, 1)
            effective_non_tank_pct = round(max(0.0, 100.0 - tank_sponge_pct), 1)
            dmg_per_kill = int(round(total_hero_dmg / max(1, total_kills))) if total_kills > 0 else total_hero_dmg

            # 单发最高爆发峰值 (max_hero_hit) + 清莲宝珠反弹/反伤智能识别
            mhh = raw_p.get("max_hero_hit") or {}
            max_hit_val = int(mhh.get("value") or 0)
            max_hit_time = fmt_mmss(mhh.get("time") or 0) if mhh.get("time") is not None else "--:--"
            max_hit_target_npc = str(mhh.get("key") or "")
            max_hit_target_zh = (opp_by_npc.get(max_hit_target_npc) or {}).get("hero_short_zh") or max_hit_target_npc.replace("npc_dota_hero_", "")
            max_hit_inflictor = str(mhh.get("inflictor") or "")
            p_all_items_str = " ".join(str(x) for x in (p.get("key_item_timings") or []) + (p.get("items") or []))
            has_lotus_orb = ("清莲宝珠" in p_all_items_str) or ("lotus_orb" in str(raw_p.get("item_uses") or {}))
            if max_hit_inflictor in ("", "null", "None"):
                max_hit_source_zh = "普攻暴击/平A"
            elif max_hit_inflictor in ITEMS_ZH:
                max_hit_source_zh = ITEMS_ZH[max_hit_inflictor]
            elif max_hit_inflictor in NEUTRAL_ITEMS_ZH:
                max_hit_source_zh = NEUTRAL_ITEMS_ZH[max_hit_inflictor]
            else:
                norm_inflictor = SUB_SKILL_REMAP.get(max_hit_inflictor, max_hit_inflictor)
                raw_ab_zh = get_ability_zh(norm_inflictor) or get_ability_zh(max_hit_inflictor) or "英雄技能"
                is_foreign_spell = (
                    h_key
                    and (not norm_inflictor.startswith(h_key))
                    and h_key not in ("rubick", "morphling")
                    and any(norm_inflictor.startswith(op_n.replace("npc_dota_hero_", "")) for op_n in opp_by_npc)
                )
                if is_foreign_spell and has_lotus_orb:
                    max_hit_source_zh = f"🪷 清莲宝珠反弹·{raw_ab_zh}"
                elif is_foreign_spell:
                    max_hit_source_zh = f"🔄 技能反弹·{raw_ab_zh}"
                else:
                    max_hit_source_zh = raw_ab_zh
            max_hit_summary_zh = (
                f"{max_hit_time} 用【{max_hit_source_zh}】对 {max_hit_target_zh} 单发打出 {max_hit_val:,} 点伤害"
                if max_hit_val > 0
                else "无单发高爆发记录"
            )

            # 1.5) 技能 × 敌方目标精准命中与伤害矩阵 (ability_targets + damage_targets)
            raw_ab_targets = raw_p.get("ability_targets") or {}
            raw_dmg_targets = raw_p.get("damage_targets") or {}
            all_spell_keys = list(dict.fromkeys(list(raw_dmg_targets.keys()) + list(raw_ab_targets.keys())))
            spell_target_matrix = []
            for sk in all_spell_keys:
                if not sk or sk in ("soul_ring",) or sk.startswith(("seasonal_", "plus_", "ability_", "twin_gate_")):
                    continue
                t_dmg_map = raw_dmg_targets.get(sk) or {}
                t_cast_map = raw_ab_targets.get(sk) or {}
                if not isinstance(t_dmg_map, dict):
                    t_dmg_map = {}
                if not isinstance(t_cast_map, dict):
                    t_cast_map = {}
                enemy_hits = []
                tot_sk_dmg = 0
                tot_sk_casts = 0
                for op_npc, op_obj in opp_by_npc.items():
                    d_v = int(t_dmg_map.get(op_npc) or 0)
                    c_v = int(t_cast_map.get(op_npc) or 0)
                    if d_v <= 0 and c_v <= 0:
                        continue
                    tot_sk_dmg += d_v
                    tot_sk_casts += c_v
                    enemy_hits.append({
                        "hero_short_zh": op_obj.get("hero_short_zh") or op_npc.replace("npc_dota_hero_", ""),
                        "pos": int(op_obj.get("pos") or 3),
                        "dmg": d_v,
                        "casts": c_v,
                    })
                if not enemy_hits:
                    continue
                enemy_hits.sort(key=lambda x: (x["dmg"], x["casts"]), reverse=True)
                if sk in ("null", "None", "attack", "default_attack"):
                    sk_zh = "🗡️ 普通攻击(平A)"
                    sk_type = "attack"
                elif sk in ITEMS_ZH:
                    sk_zh = f"🎒 {ITEMS_ZH[sk]}"
                    sk_type = "item"
                elif sk in NEUTRAL_ITEMS_ZH:
                    sk_zh = f"🎲 {NEUTRAL_ITEMS_ZH[sk]}"
                    sk_type = "item"
                else:
                    sk_norm = SUB_SKILL_REMAP.get(sk, sk)
                    base_ab_zh = get_ability_zh(sk_norm) or get_ability_zh(sk) or "英雄技能"
                    is_foreign = (
                        h_key
                        and (not sk_norm.startswith(h_key))
                        and h_key not in ("rubick", "morphling")
                        and any(sk_norm.startswith(op_n.replace("npc_dota_hero_", "")) for op_n in opp_by_npc)
                    )
                    if is_foreign and has_lotus_orb:
                        sk_zh = f"🪷 清莲宝珠反弹·{base_ab_zh}"
                        sk_type = "reflect"
                    elif is_foreign:
                        sk_zh = f"🔄 反弹·{base_ab_zh}"
                        sk_type = "reflect"
                    else:
                        sk_zh = f"⚡ {base_ab_zh}"
                        sk_type = "ability"
                target_parts = []
                for eh in enemy_hits[:4]:
                    if eh["dmg"] > 0 and eh["casts"] > 0:
                        target_parts.append(f"{eh['pos']}号位{eh['hero_short_zh']} {eh['dmg']:,}伤({eh['casts']}次)")
                    elif eh["dmg"] > 0:
                        target_parts.append(f"{eh['pos']}号位{eh['hero_short_zh']} {eh['dmg']:,}伤")
                    else:
                        target_parts.append(f"命中{eh['pos']}号位{eh['hero_short_zh']} {eh['casts']}次")
                spell_target_matrix.append({
                    "key": sk,
                    "zh_name": sk_zh,
                    "type": sk_type,
                    "total_dmg": tot_sk_dmg,
                    "total_casts": tot_sk_casts,
                    "targets": enemy_hits,
                    "summary_zh": f"{sk_zh}（{'共 ' + format(tot_sk_dmg, ',') + ' 伤' if tot_sk_dmg > 0 else f'共命中 {tot_sk_casts} 次'}）：{' · '.join(target_parts)}",
                })
            spell_target_matrix.sort(key=lambda x: (1 if x["type"] != "attack" else 0, x["total_dmg"], x["total_casts"]), reverse=True)

            # 判定伤害含金量等级
            dmg_audit_notes = []
            top_target = target_breakdown[0] if target_breakdown else None
            if pos in (1, 2, 3) and (tank_sponge_pct >= 50.0 or (tank_sponge_pct >= 45.0 and core_12_kills <= 2)):
                fake_dmg_suspects_cnt += 1
                dmg_quality_badge = "🚨 刮肉刷伤 · 切核乏力"
                dmg_quality_grade = "bad"
                dmg_audit_notes.append(
                    f"🚨 伤害虚胖警告：全场高达 {tank_sponge_pct}% 的伤害（{tank_sponge_dmg:,} 点）全灌在敌方前排肉盾【{'/'.join(tank_victim_names[:2]) or '肉盾'}】身上，而打在敌方 1/2 号位双核身上的伤害仅占 {core_12_pct}%（{core_12_dmg:,} 点，杀 {core_12_kills} 次）！"
                )
            elif pos in (1, 2) and total_kills >= 8 and tank_sponge_kills >= max(4, int(total_kills * 0.45)) and core_12_kills <= 2:
                fake_dmg_suspects_cnt += 1
                dmg_quality_badge = "⚠️ 技能灌肉 · 秒C偏少"
                dmg_quality_grade = "warn"
                dmg_audit_notes.append(
                    f"⚠️ 集火目标偏移：全场 {total_kills} 个人头中有 {tank_sponge_kills} 个是杀敌方前排肉盾拿的，而对敌方 1/2 号位双核仅完成 {core_12_kills} 次终结（打双核伤害占 {core_12_pct}%）。"
                )
            elif core_12_pct >= 42.0 and core_12_kills >= 3:
                true_core_slayers_cnt += 1
                dmg_quality_badge = "🔥 刀刀见血 · 精准切核"
                dmg_quality_grade = "good"
                dmg_audit_notes.append(
                    f"✓ 高含金量切核：对敌方 1/2 号位双核倾泻了 {core_12_dmg:,} 点真伤害（占 {core_12_pct}%），并亲手终结敌方双核 {core_12_kills} 次！"
                )
            elif effective_non_tank_pct >= 58.0:
                dmg_quality_badge = "⚡ 有效压制后排/核心"
                dmg_quality_grade = "good"
                dmg_audit_notes.append(
                    f"✓ 伤害分布健康：{effective_non_tank_pct}% 的伤害精准打在敌方双核与脆皮后排身上（打 1/2 号位占 {core_12_pct}%，打后排辅助占 {backline_sup_pct}%）。"
                )
            else:
                dmg_quality_badge = "⚖️ 常规前排拉扯输出"
                dmg_quality_grade = "normal"
                dmg_audit_notes.append(
                    f"对敌方 1/2 号位双核伤害占 {core_12_pct}%（杀 {core_12_kills} 次），对前排肉盾伤害占 {tank_sponge_pct}%（杀 {tank_sponge_kills} 次）。"
                )

            if top_target:
                dmg_audit_notes.append(
                    f"🎯 头号集火沙包：全场打【{top_target['pos']}号位·{top_target['hero_short_zh']}】最多，共造成 {top_target['dmg']:,} 点伤害（占个人总伤 {top_target['dmg_pct']}%，击杀 {top_target['kills']} 次）。"
                )

            # 2) 1~18级加点路线与 10/15/20/25级天赋审计
            upgrades_arr = raw_p.get("ability_upgrades_arr") or []
            basic_skills_order = _HERO_BASIC_SKILLS.get(h_npc) or []
            skill_slot_map: Dict[str, str] = {}
            for idx_sk, sk_key in enumerate(basic_skills_order[:3]):
                skill_slot_map[sk_key] = f"{idx_sk + 1}技能"
            if len(basic_skills_order) >= 4:
                skill_slot_map[basic_skills_order[3]] = "大招"

            level_sequence = []
            talents_chosen = []
            skill_counts_by_lvl8: Dict[str, int] = {}
            skill_counts_by_lvl9: Dict[str, int] = {}
            first_learned_lvl: Dict[str, int] = {}
            maxed_4_lvl: Dict[str, int] = {}
            running_skill_pts: Dict[str, int] = {}
            early_attr_pts = 0

            talent_tiers = ["10级天赋", "15级天赋", "20级天赋", "25级天赋"]
            talent_idx = 0
            hero_tal_map = _HERO_TALENT_TIERS.get(h_npc) or {}
            ult_key = basic_skills_order[3] if len(basic_skills_order) >= 4 else None
            p_hid = int(p.get("hero_id") or raw_p.get("hero_id") or 0)
            is_invoker = p_hid == 74 or h_npc == "npc_dota_hero_invoker"
            is_meepo = p_hid == 82 or h_npc == "npc_dota_hero_meepo"
            is_lone_druid = p_hid == 80 or h_npc == "npc_dota_hero_lone_druid"
            cur_lvl = 0
            manual_attr_used = 0
            auto_attr_used = 0
            ult_rank = 0
            tal_rank = 0

            for pt_idx, raw_aid in enumerate(upgrades_arr, 1):
                cat_entry = _AID_BY_ID.get(str(raw_aid)) or {}
                akey = cat_entry.get("key") or f"ability_{raw_aid}"
                akey_norm = SUB_SKILL_REMAP.get(akey, akey)
                azh = cat_entry.get("zh") or get_ability_zh(akey_norm) or "技能升级"
                is_tal = bool(cat_entry.get("is_talent"))
                is_attr = bool(cat_entry.get("is_attr"))
                slot_lbl = skill_slot_map.get(akey_norm, "技能")
                is_ult = (not is_invoker) and (not is_tal) and (not is_attr) and bool(ult_key and akey_norm == ult_key)

                cur_lvl += 1
                min_req_lvl = 1
                if is_attr:
                    manual_attr_used += 1
                elif is_tal:
                    tal_rank += 1
                    eff_tal_rank = ((tal_rank + 1) // 2) if is_lone_druid else tal_rank
                    min_req_lvl = {1: 10, 2: 15, 3: 20, 4: 25, 5: 26, 6: 27, 7: 28, 8: 29}.get(eff_tal_rank, 29)
                elif is_ult:
                    ult_rank += 1
                    if is_meepo:
                        min_req_lvl = {1: 4, 2: 11, 3: 18}.get(ult_rank, 18)
                    else:
                        min_req_lvl = {1: 6, 2: 12, 3: 18}.get(ult_rank, 18)

                while cur_lvl < min_req_lvl and (manual_attr_used + auto_attr_used) < 7:
                    auto_attr_used += 1
                    cur_lvl += 1
                lv_idx = cur_lvl

                if is_tal:
                    t_label = (
                        hero_tal_map.get(akey)
                        or cat_entry.get("tier")
                        or talent_tiers[min(talent_idx, len(talent_tiers) - 1)]
                    )
                    talent_idx += 1
                    talents_chosen.append({
                        "tier": t_label,
                        "level_taken": lv_idx,
                        "zh": azh,
                    })
                    level_sequence.append({
                        "level": lv_idx,
                        "zh": azh,
                        "short_tag": f"L{lv_idx}:🌟{azh}",
                        "type": "talent",
                    })
                elif is_attr:
                    if lv_idx <= 9:
                        early_attr_pts += 1
                    level_sequence.append({
                        "level": lv_idx,
                        "zh": "全属性黄点",
                        "short_tag": f"L{lv_idx}:➕黄点",
                        "type": "attr",
                    })
                else:
                    running_skill_pts[akey_norm] = running_skill_pts.get(akey_norm, 0) + 1
                    cur_pt = running_skill_pts[akey_norm]
                    if akey_norm not in first_learned_lvl:
                        first_learned_lvl[akey_norm] = lv_idx
                    if cur_pt == 4 and akey_norm not in maxed_4_lvl:
                        maxed_4_lvl[akey_norm] = lv_idx
                    if lv_idx <= 8:
                        skill_counts_by_lvl8[akey_norm] = cur_pt
                    if lv_idx <= 9:
                        skill_counts_by_lvl9[akey_norm] = cur_pt
                    short_zh = azh.split("(")[0].strip()
                    level_sequence.append({
                        "level": lv_idx,
                        "zh": azh,
                        "short_tag": f"L{lv_idx}:{short_zh}({cur_pt}级)",
                        "type": "ult" if is_ult else "skill",
                    })

            # 提炼主副技能路线描述
            maxed_sorted = sorted(maxed_4_lvl.items(), key=lambda x: x[1])
            if len(maxed_sorted) >= 2:
                m1_zh = (_AID_BY_ID.get(str(next((k for k, v in _AID_BY_ID.items() if v.get("key") == maxed_sorted[0][0]), "")), {}).get("zh") or get_ability_zh(maxed_sorted[0][0])).split("(")[0]
                m2_zh = (_AID_BY_ID.get(str(next((k for k, v in _AID_BY_ID.items() if v.get("key") == maxed_sorted[1][0]), "")), {}).get("zh") or get_ability_zh(maxed_sorted[1][0])).split("(")[0]
                skill_route_summary_zh = f"主【{m1_zh}】(L{maxed_sorted[0][1]}满) 副【{m2_zh}】(L{maxed_sorted[1][1]}满)"
            elif len(maxed_sorted) == 1:
                m1_zh = get_ability_zh(maxed_sorted[0][0]).split("(")[0]
                skill_route_summary_zh = f"主【{m1_zh}】(L{maxed_sorted[0][1]}满)"
            else:
                skill_route_summary_zh = "均衡对点路线"

            # 自动抓包奇葩/偏科加点
            skill_build_flags = []
            skill_build_grade = "good"

            # 检查基础三技能是否有前8~9级完全不学的情况
            for idx_b, b_skill in enumerate(basic_skills_order[:3]):
                b_norm = SUB_SKILL_REMAP.get(b_skill, b_skill)
                learned_lv = first_learned_lvl.get(b_norm)
                if learned_lv is None:
                    continue
                b_zh = get_ability_zh(b_norm)
                if learned_lv >= 9:
                    skill_build_issues_cnt += 1
                    if b_norm == "lina_light_strike_array":
                        skill_build_grade = "bad"
                        skill_build_flags.append(
                            f"🚨 奇葩加点抓包：前 {learned_lv - 1} 级完全不学二技能【{b_zh}】（0级眩晕，主龙破斩副炽魂），直到 L{learned_lv} 才点出 1 级眩晕，导致前中期支援与小规模团战 0 控制留人！"
                        )
                    elif b_norm == "phoenix_sun_ray":
                        skill_build_grade = "warn"
                        skill_build_flags.append(
                            f"⚠️ 偏科加点抓包：前 {learned_lv - 1} 级完全不学三技能【{b_zh}】（把小鸟和F飞全点满），直到 L{learned_lv} 才点出 1 级激光，前中期面对敌方前排肉盾缺失百分比灼烧与远距离救人奶量！"
                        )
                    else:
                        if skill_build_grade == "good":
                            skill_build_grade = "warn"
                        skill_build_flags.append(
                            f"⚠️ 偏科加点：前 {learned_lv - 1} 级完全没学【{b_zh}】（直到 L{learned_lv} 才点 1 级），前中期少一个技能维度。"
                        )

            # 检查关键救人/叠层技能是否只点1级拖到12级后才补
            if h_key == "ringmaster" and first_learned_lvl.get("ringmaster_the_box", 99) <= 5:
                pts_by_9 = skill_counts_by_lvl9.get("ringmaster_the_box", 0)
                if pts_by_9 == 1:
                    skill_build_flags.append(
                        f"💡 技能取舍：前 9 级仅保留 {pts_by_9} 级【逃生暗箱(救人箱)】（主【{skill_route_summary_zh}】打消耗），中期救人箱冷却偏长、施法距离较短。"
                    )
            if h_key == "slark" and skill_counts_by_lvl9.get("slark_saltwater_shiv", 0) <= 1:
                shiv_pts_9 = skill_counts_by_lvl9.get("slark_saltwater_shiv", 0)
                skill_build_flags.append(
                    f"💡 加点路线：{skill_route_summary_zh}，前 9 级仅点 {shiv_pts_9} 级【能量转移】（刷钱快但前中期每次平A偷属性持续时间短）。"
                )
            if early_attr_pts >= 2:
                skill_build_issues_cnt += 1
                skill_build_grade = "warn"
                skill_build_flags.append(
                    f"⚠️ 复古黄点流：前 9 级不学技能反而点了 {early_attr_pts} 级【+2全属性黄点】，技能等级严重滞后。"
                )

            if not skill_build_flags:
                skill_build_flags.append(f"✓ 加点路线合理（{skill_route_summary_zh}，三技能衔接顺畅）。")

            # 3) 永久 Buff 与英雄成长叠层审计 (permanent_buffs + 命石 hero_variant)
            raw_pbuffs = raw_p.get("permanent_buffs") or []
            perm_buff_badges = []
            perm_buff_notes = []
            found_buff_ids = {}
            h_variant = raw_p.get("hero_variant")
            if h_variant:
                perm_buff_badges.append(f"🪨 命石 #{int(h_variant)}")

            for pb in raw_pbuffs:
                bid = int(pb.get("permanent_buff") or 0)
                stacks = int(pb.get("stack_count") or 0)
                gtime = int(pb.get("grant_time") or 0)
                found_buff_ids[bid] = stacks
                meta = PERMANENT_BUFF_CATALOG.get(bid)
                if not meta:
                    continue
                if bid == 12:
                    perm_buff_badges.append(f"💎 魔晶激活 ({fmt_mmss(gtime)})")
                elif bid == 2:
                    perm_buff_badges.append(f"👑 融A杖赐福 ({fmt_mmss(gtime)})")
                elif bid == 1:
                    perm_buff_badges.append("🌙 吞噬银月之晶")
                elif stacks > 0:
                    perm_buff_badges.append(f"{meta['zh']}：{stacks} {meta['unit']}")

            # 检查是否是必须叠层的成长型英雄
            if h_key in HERO_EXPECTED_STACK_BUFF:
                exp_bid, exp_name, exp_per_min = HERO_EXPECTED_STACK_BUFF[h_key]
                actual_stacks = int(found_buff_ids.get(exp_bid, 0))
                target_stacks = max(4, int(round(duration_min * exp_per_min)))
                if actual_stacks == 0:
                    perm_buff_notes.append(
                        f"🚨 成长机制荒废：身为【{h_short}】整局 {duration_min:.0f} 分钟竟然 0 层【{exp_name}】（合格线 ≥{target_stacks}）！"
                    )
                    if dmg_quality_grade == "good":
                        dmg_quality_grade = "warn"
                elif actual_stacks < target_stacks:
                    perm_buff_notes.append(
                        f"⚠️ 叠层偏少：{duration_min:.0f} 分钟仅叠出 {actual_stacks} 层【{exp_name}】（同局时长合格线 ≥{target_stacks} 层），团战存活拉扯或终结收割频次不足。"
                    )
                else:
                    perm_buff_notes.append(
                        f"🔥 叠层丰厚：全场累计叠出 {actual_stacks} 层【{exp_name}】（远超合格线 {target_stacks} 层），成长叠层速度出色！"
                    )

            overall_grade = "bad" if (dmg_quality_grade == "bad" or skill_build_grade == "bad") else (
                "warn" if (dmg_quality_grade == "warn" or skill_build_grade == "warn") else dmg_quality_grade
            )

            player_rows.append({
                "pos": pos,
                "hero_short_zh": h_short,
                "hero_img": p.get("hero_img") or "",
                "personaname": p.get("personaname") or "匿名玩家",
                "total_hero_dmg": total_hero_dmg,
                "total_kills": total_kills,
                "dmg_per_kill": dmg_per_kill,
                "core_12_dmg": core_12_dmg,
                "core_12_pct": core_12_pct,
                "core_12_kills": core_12_kills,
                "tank_sponge_dmg": tank_sponge_dmg,
                "tank_sponge_pct": tank_sponge_pct,
                "tank_sponge_kills": tank_sponge_kills,
                "backline_sup_dmg": backline_sup_dmg,
                "backline_sup_pct": backline_sup_pct,
                "backline_sup_kills": backline_sup_kills,
                "effective_non_tank_pct": effective_non_tank_pct,
                "max_hit_val": max_hit_val,
                "max_hit_summary_zh": max_hit_summary_zh,
                "target_breakdown": target_breakdown,
                "spell_target_matrix": spell_target_matrix[:5],
                "dmg_quality_badge": dmg_quality_badge,
                "dmg_audit_notes": dmg_audit_notes,
                "skill_route_summary_zh": skill_route_summary_zh,
                "level_sequence": level_sequence,
                "talents_chosen": talents_chosen,
                "skill_build_flags": skill_build_flags,
                "skill_build_grade": skill_build_grade,
                "perm_buff_badges": perm_buff_badges,
                "perm_buff_notes": perm_buff_notes,
                "grade": overall_grade,
                "evidence": "inferred",
            })

        side_zh = "夜魇" if side_key == "dire" else "天辉"
        if fake_dmg_suspects_cnt > 0 or skill_build_issues_cnt > 0:
            side_verdict = (
                f"🚨 {side_zh}伤害含金量与加点审判：抓出 {fake_dmg_suspects_cnt} 名队员存在「大量伤害灌在敌方前排肉盾身上、切敌方1/2号位双核乏力」的假伤害现象，"
                f"且有 {skill_build_issues_cnt} 处前中期关键控制/核心技能 0 级不学的偏科加点！"
            )
        else:
            side_verdict = (
                f"✅ {side_zh}伤害含金量与加点审判：全队集火目标明确（共 {true_core_slayers_cnt} 人打出高比例切核真伤害），且 1~5 号位前中期技能加点与天赋抉择均无明显毒点。"
            )

        return {
            "side": side_key,
            "evidence": "inferred",
            "side_verdict": side_verdict,
            "conclusions": [{"text": side_verdict, "kind": "side_verdict", "evidence": "inferred"}],
            "fake_dmg_suspects_cnt": fake_dmg_suspects_cnt,
            "true_core_slayers_cnt": true_core_slayers_cnt,
            "skill_build_issues_cnt": skill_build_issues_cnt,
            "player_rows": player_rows,
        }

    return {
        "itemization_audit_by_side": {
            "dire": analyze_side_itemization_and_counters("dire"),
            "radiant": analyze_side_itemization_and_counters("radiant"),
        },
        "damage_quality_and_build_by_side": {
            "dire": analyze_side_damage_quality_and_skill_builds("dire"),
            "radiant": analyze_side_damage_quality_and_skill_builds("radiant"),
        },
    }
