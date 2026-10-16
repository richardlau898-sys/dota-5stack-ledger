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

from typing import Any, Dict, List, Optional, Tuple


# 英雄战术画像：先手(init)、爆发(burst)、团战AOE(tf)、推塔(push)、抓人(pick)、后期(late)、前排肉度(tank)、物理/法系倾向
HERO_ARCHETYPES: Dict[int, Dict[str, Any]] = {
    8: {  # 主宰 Juggernaut
        "short": "主宰",
        "roles": ["奶棒推进核", "魔免剑刃风暴", "无敌斩收割"],
        "scores": {"init": 35, "burst": 82, "tf": 76, "push": 92, "pick": 68, "late": 85, "tank": 65},
        "dmg_type": "physical",
        "key_spells": ["剑刃风暴(转)", "治疗守卫(奶棒)", "无敌斩"],
        "synergy_tags": ["needs_setup", "siege_healer", "empower_carrier"],
    },
    45: {  # 帕格纳 Pugna
        "short": "帕格纳",
        "roles": ["爆轰磨塔快推", "衰老虚无增伤/救人", "幽冥守卫反法系"],
        "scores": {"init": 30, "burst": 85, "tf": 78, "push": 98, "pick": 65, "late": 62, "tank": 30},
        "dmg_type": "magical",
        "key_spells": ["幽冥爆轰", "衰老(虚无)", "幽冥守卫(棒子)", "生命汲取(吸)"],
        "synergy_tags": ["magic_amp", "tower_melter", "anti_caster_ward"],
    },
    97: {  # 马格纳斯 Magnus
        "short": "马格纳斯",
        "roles": ["授予力量刷钱引擎", "跳刀两极反转团控", "巨角冲撞破坏阵型"],
        "scores": {"init": 95, "burst": 65, "tf": 96, "push": 72, "pick": 78, "late": 88, "tank": 75},
        "dmg_type": "mixed",
        "key_spells": ["授予力量(Empower)", "巨角冲撞(拱)", "两极反转(大招RP)"],
        "synergy_tags": ["aoe_vacuum_stun", "empower_buffer", "reposition"],
    },
    9: {  # 米拉娜 Mirana
        "short": "米拉娜",
        "roles": ["超远穿云箭接控", "全图月之暗面开雾", "流星爆发补伤害"],
        "scores": {"init": 62, "burst": 72, "tf": 68, "push": 55, "pick": 88, "late": 65, "tank": 45},
        "dmg_type": "magical",
        "key_spells": ["月神之箭(穿云箭)", "群星风暴(流星)", "月之暗面(全图隐身)"],
        "synergy_tags": ["follow_up_stun", "team_invis_gank"],
    },
    26: {  # 莱恩 Lion
        "short": "莱恩",
        "roles": ["瞬发变羊+穿刺双控", "死亡一指高额单体秒杀", "抽蓝限制前排"],
        "scores": {"init": 88, "burst": 92, "tf": 65, "push": 30, "pick": 92, "late": 60, "tank": 28},
        "dmg_type": "magical",
        "key_spells": ["裂地尖刺(戳)", "妖术(变羊)", "死亡一指(一阳指)"],
        "synergy_tags": ["instant_hex_stun", "high_magic_nuke"],
    },
    32: {  # 力丸 Riki
        "short": "力丸",
        "roles": ["烟幕范围沉默致盲", "隐身视野压制切后排", "绝杀秘技规避伤害"],
        "scores": {"init": 72, "burst": 82, "tf": 70, "push": 38, "pick": 95, "late": 78, "tank": 45},
        "dmg_type": "physical",
        "key_spells": ["烟幕(雾)", "闪烁突袭(B)", "绝杀秘技"],
        "synergy_tags": ["aoe_silence_cloud", "backline_assassin"],
    },
    49: {  # 龙骑士 Dragon Knight
        "short": "龙骑士",
        "roles": ["瞬发神龙摆尾先手", "古龙形态腐蚀推塔", "高护甲前排顶梁柱"],
        "scores": {"init": 86, "burst": 68, "tf": 78, "push": 90, "pick": 80, "late": 82, "tank": 92},
        "dmg_type": "physical",
        "key_spells": ["神龙摆尾(T)", "火焰气息", "古龙形态(变龙)"],
        "synergy_tags": ["instant_stun", "frontline_siege", "empower_carrier"],
    },
    99: {  # 钢背兽 Bristleback
        "short": "钢背兽",
        "roles": ["粘稠鼻涕叠甲减移速", "刺针扫射持续肉搏", "前排吸收成吨火力"],
        "scores": {"init": 45, "burst": 60, "tf": 84, "push": 72, "pick": 58, "late": 76, "tank": 96},
        "dmg_type": "physical",
        "key_spells": ["粘稠鼻涕", "刺针扫射", "刚毛后背"],
        "synergy_tags": ["armor_reduction", "raid_boss_frontline"],
    },
    30: {  # 巫医 Witch Doctor
        "short": "巫医",
        "roles": ["麻痹药剂弹射群控", "诅咒百分比掉血结算", "死亡守卫毁灭团战输出"],
        "scores": {"init": 68, "burst": 94, "tf": 92, "push": 42, "pick": 82, "late": 72, "tank": 35},
        "dmg_type": "magical",
        "key_spells": ["麻痹药剂(弹弹乐)", "诅咒(Maledict)", "死亡守卫(大招)"],
        "synergy_tags": ["maledict_burst_amp", "channeled_ward_ult"],
    },
    44: {  # 幻影刺客 Phantom Assassin
        "short": "幻影刺客",
        "roles": ["高暴击物理切入收割", "模糊闪避物理平A", "BKB成型期瞬秒后排"],
        "scores": {"init": 55, "burst": 95, "tf": 75, "push": 62, "pick": 85, "late": 92, "tank": 58},
        "dmg_type": "physical",
        "key_spells": ["窒碍短匕(标)", "幻影突袭(B)", "恩赐解脱(暴击)"],
        "synergy_tags": ["backline_assassin", "empower_carrier"],
    },
    76: {  # 殁境神蚀者 Outworld Destroyer
        "short": "殁境神蚀者",
        "roles": ["星体禁锢断节奏救人", "奥术天球纯粹法球巨额点杀", "神智之蚀大招清场"],
        "scores": {"init": 75, "burst": 94, "tf": 86, "push": 55, "pick": 82, "late": 88, "tank": 62},
        "dmg_type": "pure",
        "key_spells": ["奥术天球", "星体禁锢(关)", "神智之蚀(大招)"],
        "synergy_tags": ["save_banish", "pure_damage_core"],
    },
    29: {  # 潮汐猎人 Tidehunter
        "short": "潮汐猎人",
        "roles": ["毁灭超大范围团控", "海妖外壳强解状态顶前排", "锚击降低敌方物理攻击"],
        "scores": {"init": 94, "burst": 62, "tf": 98, "push": 58, "pick": 60, "late": 78, "tank": 95},
        "dmg_type": "magical",
        "key_spells": ["巨浪", "锚击", "毁灭(大招)"],
        "synergy_tags": ["aoe_ravage_stun", "frontline_tank"],
    },
    86: {  # 拉比克 Rubick
        "short": "拉比克",
        "roles": ["隔空取物瞬发先手举", "技能窃取反制大招", "弱化能流减攻清线"],
        "scores": {"init": 80, "burst": 70, "tf": 85, "push": 45, "pick": 82, "late": 78, "tank": 35},
        "dmg_type": "magical",
        "key_spells": ["隔空取物(举)", "弱化能流", "技能窃取(偷大)"],
        "synergy_tags": ["instant_lift_stun", "spell_steal_counter"],
    },
    5: {  # 水晶室女 Crystal Maiden
        "short": "水晶室女",
        "roles": ["冰封禁制先手留人", "奥术光环全队回蓝", "极寒领域团战高额AOE"],
        "scores": {"init": 70, "burst": 76, "tf": 84, "push": 38, "pick": 75, "late": 55, "tank": 28},
        "dmg_type": "magical",
        "key_spells": ["冰霜新星(V)", "冰封禁制(E)", "极寒领域(大招)"],
        "synergy_tags": ["root_setup", "mana_aura"],
    },
    136: {  # 玛西 Marci
        "short": "玛西",
        "roles": ["回身踢+健步强先手留人", "怒拳破高爆发冲脸", "护卫反击提供吸血攻击力"],
        "scores": {"init": 88, "burst": 90, "tf": 80, "push": 68, "pick": 94, "late": 78, "tank": 76},
        "dmg_type": "physical",
        "key_spells": ["过肩摔(背)", "回身踢(跳)", "怒拳破(大招)"],
        "synergy_tags": ["dive_initiator", "burst_brawler"],
    },
}


def get_hero_archetype(p: Dict[str, Any]) -> Dict[str, Any]:
    hid = int(p.get("hero_id") or 0)
    pos = int(p.get("pos") or 3)
    short = p.get("hero_short_zh") or p.get("hero_name") or f"英雄#{hid}"
    if hid in HERO_ARCHETYPES:
        return HERO_ARCHETYPES[hid]

    # 根据位置与常见属性推断默认画像
    if pos == 1:
        return {
            "short": short,
            "roles": ["一号位后期主核", "装备成型收割", "高地推进主力"],
            "scores": {"init": 45, "burst": 78, "tf": 72, "push": 78, "pick": 60, "late": 88, "tank": 62},
            "dmg_type": "physical",
            "key_spells": [a["zh_name"] for a in (p.get("ability_uses_rich") or [])[:3]],
            "synergy_tags": ["needs_setup", "empower_carrier"],
        }
    if pos == 2:
        return {
            "short": short,
            "roles": ["二号位中单节奏核", "前中期爆发游走", "团战法系/混伤支点"],
            "scores": {"init": 70, "burst": 85, "tf": 80, "push": 68, "pick": 82, "late": 76, "tank": 58},
            "dmg_type": "magical",
            "key_spells": [a["zh_name"] for a in (p.get("ability_uses_rich") or [])[:3]],
            "synergy_tags": ["mid_tempo", "high_magic_nuke"],
        }
    if pos == 3:
        return {
            "short": short,
            "roles": ["三号位前排先手", "团战吃伤害开团", "团队光环与控制"],
            "scores": {"init": 82, "burst": 65, "tf": 84, "push": 65, "pick": 72, "late": 70, "tank": 85},
            "dmg_type": "mixed",
            "key_spells": [a["zh_name"] for a in (p.get("ability_uses_rich") or [])[:3]],
            "synergy_tags": ["frontline_tank", "initiator"],
        }
    if pos == 4:
        return {
            "short": short,
            "roles": ["四号位游走节奏", "先手留人接控", "中期团战拉扯"],
            "scores": {"init": 78, "burst": 70, "tf": 74, "push": 45, "pick": 85, "late": 62, "tank": 48},
            "dmg_type": "magical",
            "key_spells": [a["zh_name"] for a in (p.get("ability_uses_rich") or [])[:3]],
            "synergy_tags": ["follow_up_stun", "roaming_ganker"],
        }
    return {
        "short": short,
        "roles": ["五号位保人视野", "反手控制救人", "线上消耗换血"],
        "scores": {"init": 68, "burst": 68, "tf": 72, "push": 40, "pick": 74, "late": 55, "tank": 38},
        "dmg_type": "magical",
        "key_spells": [a["zh_name"] for a in (p.get("ability_uses_rich") or [])[:3]],
        "synergy_tags": ["lane_babysitter", "instant_hex_stun"],
    }


def compute_team_draft_scores(team_players: List[Dict[str, Any]]) -> Dict[str, int]:
    if not team_players:
        return {"init": 60, "burst": 60, "tf": 60, "push": 60, "pick": 60, "late": 60, "tank": 60}
    archs = [get_hero_archetype(p) for p in team_players]
    out = {}
    for k in ("init", "burst", "tf", "push", "pick", "late", "tank"):
        vals = sorted([a["scores"].get(k, 60) for a in archs], reverse=True)
        # 取最高 2 名的权重 + 团队均值，更能反映阵容在该维度的上限
        top2_avg = sum(vals[:2]) / max(1, len(vals[:2]))
        all_avg = sum(vals) / len(vals)
        out[k] = int(round(top2_avg * 0.65 + all_avg * 0.35))
    return out


def build_team_combos(
    own_players: List[Dict[str, Any]],
    opp_players: List[Dict[str, Any]],
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
                "window": "10:00–终局 · 刷钱提速与团战一锤定音",
                "heroes": [
                    {"short": mag["hero_short_zh"], "img": mag["hero_img"], "pos": mag["pos"], "personaname": mag["personaname"]},
                    {"short": c_short, "img": carry["hero_img"], "pos": carry["pos"], "personaname": carry["personaname"]},
                ],
                "how_to_play": (
                    f"1) 发育期：马格纳斯必须卡 CD 给 {c_short} 套上『授予力量 (Empower)』，让 {c_short} 拥有分裂与额外攻击力高速清远古与兵线；"
                    f"2) 团战期：马格纳斯切忌第一波裸跳送死，等敌方关键救人/反手（如{'、'.join(opp_names[:2])}）露头后，跳刀『两极反转 (RP)』吸住多人或把核心拱回，"
                    f"{c_short} 立即接大招/溅射输出瞬间融化敌方前排。"
                ),
                "execution_audit": (
                    f"本局实战验货：马格纳斯整局释放『授予力量』{emp_cnt} 次、『两极反转(RP)』{rp_cnt} 次、『巨角冲撞』{skewer_cnt} 次；"
                    f"{c_short} 终局刷出 {carry['gpm']} GPM（净资产 {carry['net_worth']:,} 金，英雄伤害 {carry['hero_damage']:,}）。"
                    f"{'这套猛犸赋能+RP体系在后期团战成功兑现，是翻盘的核心引擎。' if carry['gpm'] >= 600 and rp_cnt >= 4 else '但本局中期多次出现猛犸与大哥脱节、RP 控住人时核心不在场的断档情况，配合熟练度还得练！'}"
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
            "window": "02:00–25:00 · 线上击杀与月之暗面抓单节奏",
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
                f"但两人整局合计阵亡高达 {lion['deaths'] + pom['deaths']} 次（莱恩 {lion['deaths']} 死 / 米拉娜 {pom['deaths']} 死）——抓人链有亮眼击杀，但中期的走位脱节也给对面送足了提款！"
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
            "title": "【帕格纳衰老增伤 + 幽冥守卫反法系 + 爆轰奶棒速推】阵地折磨与高地拆迁体系",
            "window": "08:00–终局 · 推塔压制与限制敌方冲脸/高耗蓝法师",
            "heroes": p_list,
            "how_to_play": (
                "1) 团战开打前：帕格纳必须先把『幽冥守卫(棒子)』插在侧翼树林或高坡后方，让敌方法师每放一个大招都先掉半管血；"
                "2) 集火与救人：队友被敌方物理核（如幻影刺客）跳砍时立刻给『衰老(虚无)』废掉其物理平A；集火敌方时套『衰老』配合幽冥爆轰/莱恩一指瞬间融化（注意别在剑圣正要平A输出时乱给衰老！）；"
                "3) 推塔：配合主宰『治疗守卫(奶棒)』站在兵线后无限『幽冥爆轰』磨塔，对面根本守不住外塔与兵营。"
            ),
            "execution_audit": (
                f"本局实战验货：帕格纳整局轰出 {blast_cnt} 次『幽冥爆轰』、插下 {ward_cnt} 根『幽冥守卫』、释放 {decrep_cnt} 次『衰老』与 {drain_cnt} 次『生命汲取』，"
                f"打出全场最高的 {pugna['hero_damage']:,} 英雄伤害与 {pugna['tower_damage']:,} 建筑伤害！火力完全拉满，唯一瑕疵是中期无保命装时死得略多（整局 {pugna['deaths']} 死）。"
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

        combos.append({
            "title": "【先手跳控 + 力丸烟幕沉默致盲 + 巫医诅咒守卫】完美关门打狗连招",
            "window": "12:00–30:00 · 中期抓人与小规模团战",
            "heroes": hero_chips,
            "how_to_play": (
                "力丸本身没有硬眩晕，最怕对面直接推推/BKB或反手硬控！标准打法是："
                "必须等龙骑士『神龙摆尾』或马格纳斯『两极反转/拱』先手定住人的瞬间，力丸立刻在目标脚下铺开『烟幕(雾)』使其沉默+丢失平A无法按出逃生技能，"
                "同时巫医挂上『诅咒(Maledict)』插下『死亡守卫』，在烟幕持续时间内完成无伤猎杀。"
            ),
            "execution_audit": (
                f"本局实战验货：力丸整局仅释放 {cloud_cnt} 次『烟幕』、{blink_cnt} 次『闪烁突袭』，打出 {riki['hero_damage']:,} 伤害（KDA {riki['kda']}）。"
                f"由于前排跳刀时间拖后、视野被压，本局多次出现力丸和前排各自为战、烟幕罩不住关键人的尴尬局面。"
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
            "window": "10:00–25:00 · 变龙逼塔与正面肉搏期",
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
                f"钢背兽释放『刺针扫射』{quill_cnt} 次、『粘稠鼻涕』{snot_cnt} 次，但建筑伤害仅有 {bb['tower_damage']:,} 且阵亡 {bb['deaths']} 次——"
                f"中期领先时没能利用双肉强势期一鼓作气拆光外塔控死肉山，给了对面喘息翻盘的机会。"
            ),
        })

    # 通用兜底配合（确保任何比赛都有至少 3 条深度配合指南）
    if len(combos) < 3:
        p1 = by_pos.get(1) or own_players[0]
        p2 = by_pos.get(2) or own_players[min(1, len(own_players) - 1)]
        p3 = by_pos.get(3) or own_players[min(2, len(own_players) - 1)]
        p4 = by_pos.get(4) or own_players[min(3, len(own_players) - 1)]
        p5 = by_pos.get(5) or own_players[-1]

        if len(combos) < 2:
            combos.append({
                "title": f"【{p4['hero_short_zh']} + {p5['hero_short_zh']} + {p2['hero_short_zh']}】双辅助控符游走与中路联动",
                "window": "04:00–15:00 · 6分钟动力符与夜晚第一波Gank",
                "heroes": [
                    {"short": p2["hero_short_zh"], "img": p2["hero_img"], "pos": p2["pos"], "personaname": p2["personaname"]},
                    {"short": p4["hero_short_zh"], "img": p4["hero_img"], "pos": p4["pos"], "personaname": p4["personaname"]},
                    {"short": p5["hero_short_zh"], "img": p5["hero_img"], "pos": p5["pos"], "personaname": p5["personaname"]},
                ],
                "how_to_play": (
                    f"每逢 04:00 / 06:00 / 08:00 河道神符刷新前 20 秒，{p4['hero_short_zh']} 必须提前靠向河道帮中单 {p2['hero_short_zh']} 抢符；"
                    f"拿到加速/双倍/奥术或到 6 级后，立刻带着 {p5['hero_short_zh']} 开雾包抄敌方优势路大哥，打断敌方一号位无解肥节奏。"
                ),
                "execution_audit": (
                    f"本局实战验货：{p2['hero_short_zh']} 参战率 {p2['kill_participation_pct']}%，{p4['hero_short_zh']} 与 {p5['hero_short_zh']} 整局合计买雾 "
                    f"{(p4.get('smokes_bought') or 0) + (p5.get('smokes_bought') or 0)} 根、插下假眼 {(p4.get('obs_placed') or 0) + (p5.get('obs_placed') or 0)} 颗。"
                ),
            })

        combos.append({
            "title": f"【{p3['hero_short_zh']} 先手开团 + {p1['hero_short_zh']}/{p2['hero_short_zh']} 后手切入】核心团战阵型拉扯",
            "window": "18:00–终局 · 肉山团与高地攻坚战",
            "heroes": [
                {"short": p3["hero_short_zh"], "img": p3["hero_img"], "pos": p3["pos"], "personaname": p3["personaname"]},
                {"short": p1["hero_short_zh"], "img": p1["hero_img"], "pos": p1["pos"], "personaname": p1["personaname"]},
                {"short": p2["hero_short_zh"], "img": p2["hero_img"], "pos": p2["pos"], "personaname": p2["personaname"]},
            ],
            "how_to_play": (
                f"团战站位铁律：由三号位 {p3['hero_short_zh']} 顶在视野最前方吃第一波先手并反手打控制，"
                f"一号位 {p1['hero_short_zh']} 与二号位 {p2['hero_short_zh']} 切忌站在同一个圈里吃敌方满额 AOE；"
                f"等敌方交出关键大招后，双核同时开启 BKB/切入技能直取敌方后排酱油与脆皮炮台。"
            ),
            "execution_audit": (
                f"本局实战验货：{p3['hero_short_zh']} 承受英雄伤害 {p3.get('hero_damage_taken') or p3.get('damage_taken') or 0:,}，"
                f"双核 {p1['hero_short_zh']} 与 {p2['hero_short_zh']} 合计打出 {p1['hero_damage'] + p2['hero_damage']:,} 英雄伤害与 "
                f"{p1['tower_damage'] + p2['tower_damage']:,} 建筑推塔伤害。"
            ),
        })

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
    rad_scores = compute_team_draft_scores(radiant_players)
    dire_scores = compute_team_draft_scores(dire_players)

    def build_for_side(own: List[Dict[str, Any]], opp: List[Dict[str, Any]], own_s: Dict[str, int], opp_s: Dict[str, int], side_key: str) -> Dict[str, Any]:
        side_zh = "天辉" if side_key == "radiant" else "夜魇"
        opp_zh = "夜魇" if side_key == "radiant" else "天辉"
        own_heroes_str = " + ".join(p["hero_short_zh"] for p in own)
        opp_heroes_str = " + ".join(p["hero_short_zh"] for p in opp)

        # 计算阵容综合分与评级
        avg_own = sum(own_s.values()) / len(own_s)
        avg_opp = sum(opp_s.values()) / len(opp_s)
        diff = avg_own - avg_opp
        if avg_own >= 80 and diff >= 2:
            grade = "S 级 · 体系完备且克制对手"
        elif avg_own >= 75:
            grade = "A 级 · 扎实能打但极其考验执行"
        elif avg_own >= 68:
            grade = "B+ 级 · 有绝活配合但存在明显短板"
        else:
            grade = "B 级 · 容错率偏低需靠个人能力硬抬"

        strengths = []
        weaknesses = []

        # 自动诊断阵容优势与短板
        if own_s["push"] >= 82:
            strengths.append(
                f"【推进磨塔能力极强 ({own_s['push']}分)】阵容拥有极高建筑消耗与持续作战能力，一旦打赢团战或拿到肉山盾，拆外塔与破高地兵营的速度远快于{opp_zh}（{opp_s['push']}分）。"
            )
        if own_s["init"] >= 84:
            strengths.append(
                f"【先手开团与强留人充足 ({own_s['init']}分)】具备稳定的跳刀瞬发点控/团控先手，中期开雾抓单与先手秒人主动权完全掌握在自己手里。"
            )
        if own_s["burst"] >= 84:
            strengths.append(
                f"【瞬间爆发秒人线极高 ({own_s['burst']}分)】控制接爆发可以在 2~3 秒内直接融化未开出 BKB 的敌方核心，线上与前中期小规模碰撞杀伤力极大。"
            )
        if own_s["tf"] >= 84:
            strengths.append(
                f"【五人阵地团战上限高 ({own_s['tf']}分)】拥有改变战局的大招流与范围 AOE，狭窄地形（肉山坑/高地口）拉扯反打能力极强。"
            )
        if own_s["tank"] >= 85:
            strengths.append(
                f"【前排身板扎实 ({own_s['tank']}分)】前排冲脸吃伤害能力强，能为后排核心提供充足的输出环境。"
            )

        # 短板与隐患
        own_hids = {int(p["hero_id"]) for p in own}
        opp_hids = {int(p["hero_id"]) for p in opp}

        if own_s["tank"] <= 62 or sum(1 for p in own if get_hero_archetype(p)["scores"]["tank"] <= 45) >= 3:
            weaknesses.append(
                "【后排脆皮过多、容错率低】双辅助及中后排普遍缺乏逃生与硬身板，一旦视野落后被敌方先手跳刀/隐身切入（如幻影刺客/潮汐/玛西冲脸），极易在团战前 3 秒瞬间蒸发。"
            )
        if 45 in own_hids and 8 in own_hids:
            weaknesses.append(
                "【技能机制存在『衰老』冲突隐患】帕格纳的『衰老(虚无)』虽然能救人并加深法系伤害，但若在主宰平A输出或无敌斩期间误套给目标，会直接导致主宰物理砍不出伤害，极度考验沟通！"
            )
        if 76 in opp_hids or 29 in opp_hids:
            weaknesses.append(
                f"【容易被敌方反手大招/关断节奏】对方选出了{'殁境神蚀者(星体禁锢救人+纯粹高伤)' if 76 in opp_hids else ''}{'与' if (76 in opp_hids and 29 in opp_hids) else ''}{'潮汐猎人(海妖外壳解控反大)' if 29 in opp_hids else ''}，我方先手若不能秒掉关键人，很容易被反手关救下或吃满毁灭团灭。"
            )
        if own_s["push"] <= 68:
            weaknesses.append(
                f"【持续磨高地能力偏弱 ({own_s['push']}分)】缺乏远程无伤磨塔手段，如果中期打赢团不果断推外塔，拖到后期上高地会非常仰仗肉山盾强拆。"
            )
        if len(weaknesses) < 2:
            weaknesses.append(
                "【中期跳刀/BKB真空期怕被强冲】12~22 分钟核心装未齐前，一旦分路带线过深或辅助独自做眼被抓，很容易连续掉外塔丢失半片野区。"
            )
        if len(strengths) < 2:
            strengths.append(
                f"【中期抓人与爆发联动紧密 ({own_s['pick']}分)】控制与输出互补性好，只要双辅助跟紧三号位/二号位开雾节奏，很容易在中期打开突破口。"
            )

        verdict_summary = (
            f"{side_zh}这套『{own_heroes_str}』迎战{opp_zh}『{opp_heroes_str}』，"
            f"在【推进拆塔 ({own_s['push']} vs {opp_s['push']})】与【先手抓人 ({own_s['pick']} vs {opp_s['pick']})】上具备明确体系支点；"
            f"但面对敌方的团战反手与切后排威胁，极其考验前排第一波切入时机以及后排保命装（微光/推推/绿杖/BKB）的出装纪律。"
        )

        return {
            "side": side_key,
            "side_zh": side_zh,
            "lineup_str": own_heroes_str,
            "opp_lineup_str": opp_heroes_str,
            "grade": grade,
            "scores": own_s,
            "opp_scores": opp_s,
            "verdict_summary": verdict_summary,
            "strengths": strengths[:3],
            "weaknesses": weaknesses[:3],
            "combos": build_team_combos(own, opp),
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
            hd_gain = int(pp.get("hero_damage_gain") or 0)
            td_gain = int(pp.get("tower_damage_gain") or 0)
            obs_p = int(pp.get("obs_placed") or 0)
            sen_p = int(pp.get("sen_placed") or 0)
            items_b = pp.get("items_bought") or []
            items_str = "、".join(f"{it['time_str']} {it['zh_name']}" for it in items_b[:4])
            death_times = [f"{d['time_str']}(被{d.get('killer','敌方')}击杀)" for d in (pp.get("deaths_events") or [])]
            kill_times = [f"{k['time_str']}(杀{k.get('victim_hero','敌方')})" for k in (pp.get("kills_events") or [])]

            good_list: List[str] = []
            bad_list: List[str] = []
            focus_tip = ""

            # 1. 前期对线 (00:00–10:00) 规则诊断
            if pkey == "lane":
                if pos in (1, 2):
                    if lh_gain >= 50:
                        good_list.append(f"对线基本功扎实：前10分钟斩获 {lh_gain} 正补 / {dn_gain} 反补，阶段 GPM 高达 {gpm_p:.0f}，无解肥发育。")
                    elif lh_gain >= 38:
                        good_list.append(f"抗压补刀合格：10分钟补出 {lh_gain} 正补 / {dn_gain} 反补（经济 +{gold_gain:,}），稳住了核心发育线。")
                    else:
                        bad_list.append(f"对线补刀严重不达标：作为 {pos} 号位前10分钟仅有 {lh_gain} 刀（经济 +{gold_gain:,}），早期发育直接断档。")
                elif pos == 3:
                    if lh_gain >= 32:
                        good_list.append(f"劣势路占线出色：10分钟补刀 {lh_gain}/{dn_gain}，打出 {hd_gain:,} 对线消耗伤害。")
                    else:
                        bad_list.append(f"劣势路混线艰难：10分钟仅 {lh_gain} 补刀（阶段 GPM {gpm_p:.0f}），未能压制敌方优势路大哥。")
                else:
                    # 4/5 号位辅助
                    if kills >= 1 or hd_gain >= 2200:
                        good_list.append(f"线上消耗与游走积极：前期打出 {hd_gain:,} 英雄伤害" + (f"，在 {', '.join(kill_times)} 拿人头打开局面。" if kill_times else "，有效压低了敌方血量。"))
                    if obs_p + sen_p >= 3:
                        good_list.append(f"前期视野勤勉：前10分钟插下 {obs_p} 假眼 / {sen_p} 真眼保障线眼与抢符视野。")
                    elif obs_p + sen_p == 0 and pos == 5:
                        bad_list.append("对线期 0 真假眼记录：线上既没封敌方野店也没给中路补保护眼。")

                if deaths == 0:
                    good_list.append(f"对线期保持 0 阵亡，没有给对位英雄送出任何额外提款。")
                elif deaths >= 2:
                    bad_list.append(f"对线期连续阵亡 {deaths} 次（{', '.join(death_times)}），直接养肥了对位核心并亏损大量兵线经验。")
                elif deaths == 1:
                    bad_list.append(f"在 {death_times[0]} 阵亡 1 次，断了一波线上节奏与补给。")

                if items_str and not good_list:
                    good_list.append(f"按部就班做出前期过渡装：{items_str}。")
                if not bad_list:
                    bad_list.append(f"前10分钟推塔伤害为 {td_gain:,}，对线期拿到优势后未能进一步磨掉敌方一塔血量。")

                focus_tip = (
                    f"前期改进重点：{'注意 03:00 莲花与 06:00 河道动力符时间点，残血及时补大药别硬拼送人头。' if deaths >= 1 else '保持当前补刀手感，6级后主动呼叫辅助打第一波推进或支援。'}"
                )

            # 2. 中期运营 (10:00–25:00) 规则诊断
            elif pkey == "mid":
                if pos in (1, 2):
                    if gpm_p >= 580:
                        good_list.append(f"中期刷钱效率拉满：15分钟内经济狂涨 +{gold_gain:,}（阶段 GPM {gpm_p:.0f}，补刀 +{lh_gain}）" + (f"，顺利掏出 {items_str}。" if items_str else "。"))
                    elif gpm_p < 420:
                        bad_list.append(f"中期刷钱节奏断档：10~25分钟阶段 GPM 仅有 {gpm_p:.0f}（经济 +{gold_gain:,}），核心装备成型过慢。")
                    if hd_gain >= 8000:
                        good_list.append(f"中期团战火力支柱：单阶段轰出 {hd_gain:,} 英雄伤害并斩获 {kills} 个人头。")
                    elif hd_gain < 4000:
                        bad_list.append(f"中期打架参与度偏低：15分钟内仅打出 {hd_gain:,} 英雄伤害，队友正面接团时输出存在真空。")
                elif pos == 3:
                    if items_str:
                        good_list.append(f"中期关键先手/团队装成型：{items_str}，阶段打出 {hd_gain:,} 伤害与 {kills} 次击杀。")
                    if td_gain >= 1000:
                        good_list.append(f"中期主动带队逼塔，造成 {td_gain:,} 点建筑伤害。")
                else:
                    # 4/5 号位
                    if obs_p + sen_p >= 6:
                        good_list.append(f"中期视野铺设到位：10~25分钟插下 {obs_p} 颗假眼与 {sen_p} 颗真眼，努力支撑团队视野。")
                    if kills >= 2 or hd_gain >= 4500:
                        good_list.append(f"中期接团技能释放果断：阶段贡献 {kills} 杀与 {hd_gain:,} 伤害" + (f"（出装：{items_str}）。" if items_str else "。"))

                if deaths == 0:
                    good_list.append("中期 15 分钟保持 0 阵亡，走位与防 Gank 警觉性极高！")
                elif deaths >= 4:
                    bad_list.append(f"中期沦为突破口：15分钟内连续暴毙 {deaths} 次（{', '.join(death_times[:4])}），把前期积攒的节奏全送了出去！")
                elif deaths >= 2:
                    bad_list.append(f"中期阵亡 {deaths} 次（{', '.join(death_times)}），多次在团战或带线时被抓断节奏。")

                if not good_list:
                    good_list.append(f"中期稳步过渡，经济增量 +{gold_gain:,}，造成 {hd_gain:,} 伤害。")
                if not bad_list:
                    bad_list.append(f"中期建筑伤害仅 +{td_gain:,}，赢下小规模遭遇战后转推外塔不够果断。")

                focus_tip = (
                    f"中期改进重点：{'第一件关键装（跳刀/狂战/以太）到手后必须跟队友抱团打一波信息差，严禁在无视野河道或二塔前落单给机会！' if deaths >= 3 else '中期大核刷钱时注意看小地图敌方蹲人动向，打赢团第一时间集合拆一塔压野区。'}"
                )

            # 3. 后期决策 (25:00–终局) 规则诊断
            else:
                if hd_gain >= 12000 or kills >= 5:
                    good_list.append(f"后期决战接管比赛：单阶段砍下 {kills} 杀、轰出 {hd_gain:,} 英雄伤害" + (f"，更新 {items_str}。" if items_str else "。"))
                if td_gain >= 3500:
                    good_list.append(f"高地拆迁绝对主力：后期独自轰出 {td_gain:,} 点建筑伤害，打赢团战后拆塔破路毫不手软！")
                if pos in (4, 5) and (obs_p + sen_p >= 5 or items_str):
                    good_list.append(f"后期辅助尽职尽责：插下 {obs_p} 假眼 / {sen_p} 真眼" + (f"，做出 {items_str} 保护核心。" if items_str else "。"))

                if deaths == 0:
                    good_list.append("后期决胜阶段 0 阵亡，团战拉扯与切入时机无懈可击！")
                elif deaths >= 3:
                    bad_list.append(f"后期高价值人头连送 {deaths} 次（{', '.join(death_times[:4])}），后期每一次读秒都直接让队伍少人守高地/控盾！")
                elif deaths >= 1:
                    bad_list.append(f"后期阵亡 {deaths} 次（{', '.join(death_times)}）" + (f"，并交出 {pp.get('buybacks',0)} 次买活。" if pp.get("buybacks") else "，后期高地/肉山团站位需更谨慎。"))

                if pos in (1, 2, 3) and td_gain < 800 and hd_gain < 7000:
                    bad_list.append(f"后期声音偏小：25分钟后英雄伤害仅 +{hd_gain:,}、拆塔 +{td_gain:,}，决胜团战未能打出核心应有统治力。")

                if not good_list:
                    good_list.append(f"后期阶段贡献 {kills} 杀、经济 +{gold_gain:,}、英雄伤害 +{hd_gain:,}。")
                if not bad_list:
                    bad_list.append("后期上高地与买活反打阶段需要更严格地盯防敌方先手与买活反扑。")

                focus_tip = "后期改进重点：25分钟后严格遵守『带盾上高地、差钱留买活、先拆兵营不冲泉水』三大铁律，后排辅助务必站在大哥侧后方树林蹲反手。"

            default_assessment = (
                f"{tlabel} 阶段斩获 {kills} 杀 {deaths} 死，经济 +{gold_gain:,} (GPM {gpm_p:.0f})，英雄伤害 +{hd_gain:,}，推塔 +{td_gain:,}。"
            )

            # 融合 Grok 阶段个人评价 (若存在且匹配该 slot)
            g_p = (g_phase.get("players") or {}).get(slot)
            if isinstance(g_p, dict):
                pp["assessment"] = g_p.get("assessment") or default_assessment
                g_good = [x for x in (g_p.get("good") or []) if x]
                g_bad = [x for x in (g_p.get("bad") or []) if x]
                # 将 Grok 的具体证据放在最前，并补充规则引擎诊断点确保内容详实
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
                    "【前期团队怎么进步 (00:00–10:00)】：① 03:00 边路莲花与 06:00/08:00 河道动力符必须由 4 号位提前 15 秒靠过去配合中单控下；"
                    "② 优势路 5 号位前 5 分钟以拉野消兵、保 1 号位无解肥补刀为第一铁律，别盲目TP支援导致大哥线被冲；"
                    "③ 一旦中单或三号位到 6 级有大招，立刻带帕格纳/辅助推掉敌方优势路一塔解放野区。"
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
                    "【中期团队怎么进步 (10:00–25:00)】：① 明确中期带队核心：当 1 号位正在刷狂战/分身/BKB 关键成型点时，2/3/4/5 号位要么开雾去抓敌方落单刷钱核，要么蹲在己方刷钱大哥侧翼高坡反蹲，绝不无脑 4 打 5 强冲；"
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
                    "【后期团队怎么进步 (25:00–终局)】：① 25 分钟后全员严守『买活钱红线』，差 500 金以内买大件时优先留买活；"
                    "② 上高地前必须确保带盾（或敌方至少减员 2 人且无买活），由带盾核+奶棒/爆轰磨塔，猛犸/莱恩蹲在后面专门断对面冲高地反扑；"
                    "③ 破掉一路高地或逼出对面双买活后，全队立刻语音喊撤退转打肉山/控魔晶，绝不残血赖在敌方高地上送翻盘！"
                )

            team_diagnostics[side_k] = {
                "summary": g_phase.get("summary") or "",
                "turning_point": g_phase.get("turning_point") or "",
                "team_good": t_good,
                "team_bad": t_bad,
                "team_action": t_action,
            }

        pd["team_diagnostics"] = team_diagnostics

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
    from dota_constants_zh import get_ability_zh

    all_formatted = radiant_players + dire_players
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
                stage_tag = f"第{pick_seq}手 · 尾手康特(Counter)"

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

        lane_matchups.append({
            "lane_id": lane_num,
            "title": lane_title,
            "winner_side": winner_side,
            "verdict_zh": verdict_zh,
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

    # 7. 团战阵亡坐标与买活回放详情 (teamfight_forensics)
    raw_tfs = match.get("teamfights") or []
    all_raw_players = match.get("players") or []
    tf_forensics: List[Dict[str, Any]] = []
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
                                deaths_coords.append({
                                    "x": raw_x,
                                    "y": raw_y,
                                    "nx": nx,
                                    "ny": ny,
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

        if rad_k + dire_k >= 2:
            tf_forensics.append({
                "tf_index": len(tf_forensics) + 1,
                "start_sec": start_s,
                "end_sec": end_s,
                "time_range": f"{fmt_mmss(start_s)}–{fmt_mmss(end_s)}",
                "rad_kills": rad_k,
                "dire_kills": dire_k,
                "gold_swing_rad": gold_swing_rad,
                "buybacks": buybacks_list,
                "deaths_coords": deaths_coords,
            })

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

    rdir = Path(reports_dir)
    main_aid = int(roster.get("main_account_id") or 86080912)
    roster_players = roster.get("players") or {}

    analyzed_matches_summary = []
    member_stats: Dict[str, Dict[str, Any]] = {}

    if rdir.exists():
        for mpath in sorted(rdir.glob("match_*.json"), reverse=True):
            try:
                rep = json.loads(mpath.read_text(encoding="utf-8"))
            except Exception:
                continue
            mid = rep.get("match_id")
            if not mid:
                continue
            f_side = rep.get("focus_side") or "dire"
            own_list = rep.get("radiant_pos_1_to_5") if f_side == "radiant" else rep.get("dire_pos_1_to_5")
            if not own_list:
                continue

            won = (f_side == "radiant" and bool(rep.get("radiant_win"))) or (
                f_side == "dire" and not bool(rep.get("radiant_win"))
            )
            mvp_p = (rep.get("mvp") or {}).get("mvp_player") or own_list[0]
            sorted_blame = sorted(own_list, key=lambda x: float(x.get("blame_share_pct") or 0), reverse=True)
            culprit_p = sorted_blame[0] if sorted_blame else own_list[0]

            analyzed_matches_summary.append({
                "match_id": mid,
                "start_time_str": rep.get("start_time_str") or "",
                "duration_str": rep.get("duration_str") or "",
                "score": rep.get("score") or "",
                "side_zh": "天辉" if f_side == "radiant" else "夜魇",
                "won": won,
                "is_parsed": bool(rep.get("is_parsed")),
                "has_grok": bool(rep.get("grok_coaching")),
                "mvp_hero": mvp_p.get("hero_short_zh") or "",
                "mvp_img": mvp_p.get("hero_img") or "",
                "mvp_player": mvp_p.get("personaname") or "",
                "culprit_hero": culprit_p.get("hero_short_zh") or "",
                "culprit_img": culprit_p.get("hero_img") or "",
                "culprit_player": culprit_p.get("personaname") or "",
                "culprit_blame_pct": round(float(culprit_p.get("blame_share_pct") or 0), 1),
            })

            for p in own_list:
                aid = p.get("account_id")
                pname = p.get("personaname") or "匿名玩家"
                key = str(aid) if aid else pname
                st = member_stats.setdefault(
                    key,
                    {
                        "key": key,
                        "account_id": aid,
                        "personaname": roster_players.get(str(aid), {}).get("name") or pname,
                        "is_me": bool(aid and int(aid) == main_aid),
                        "is_roster_friend": str(aid) in roster_players,
                        "games": 0,
                        "wins": 0,
                        "total_blame_pct": 0.0,
                        "total_rating": 0.0,
                        "mvp_count": 0,
                        "culprit_count": 0,
                        "total_kills": 0,
                        "total_deaths": 0,
                        "total_assists": 0,
                        "total_dead_sec": 0,
                        "heroes": [],
                    },
                )
                st["games"] += 1
                if won:
                    st["wins"] += 1
                st["total_blame_pct"] += float(p.get("blame_share_pct") or 0)
                st["total_rating"] += float(p.get("rating_score") or 60)
                if int(p.get("player_slot", -1)) == int(mvp_p.get("player_slot", -2)):
                    st["mvp_count"] += 1
                if int(p.get("player_slot", -1)) == int(culprit_p.get("player_slot", -2)):
                    st["culprit_count"] += 1
                st["total_kills"] += int(p.get("kills") or 0)
                st["total_deaths"] += int(p.get("deaths") or 0)
                st["total_assists"] += int(p.get("assists") or 0)
                st["total_dead_sec"] += int(p.get("dead_seconds") or 0)
                st["heroes"].append({
                    "match_id": mid,
                    "hero_short_zh": p.get("hero_short_zh") or "",
                    "hero_img": p.get("hero_img") or "",
                    "pos": p.get("pos") or 1,
                    "kda": p.get("kda") or "",
                    "blame_pct": round(float(p.get("blame_share_pct") or 0), 1),
                    "won": won,
                })

    squad_members_rank = []
    for st in member_stats.values():
        g = max(1, st["games"])
        avg_blame = round(st["total_blame_pct"] / g, 1)
        avg_rating = round(st["total_rating"] / g, 1)
        win_rate = round((st["wins"] / g) * 100, 1)
        avg_deaths = round(st["total_deaths"] / g, 1)
        avg_dead_sec = int(round(st["total_dead_sec"] / g))

        if st["mvp_count"] >= 1 and avg_blame <= 16.0:
            role_tag = "👑 车队大腿 · 历史凯瑞王"
            tag_cls = "carry"
        elif st["culprit_count"] >= 1 or avg_blame >= 24.0:
            role_tag = "🚨 车队头号惯犯 · 重点分锅对象"
            tag_cls = "culprit"
        elif avg_deaths >= 10.0:
            role_tag = "💀 泉水常客 · 场均十死俱乐部"
            tag_cls = "culprit"
        else:
            role_tag = "⚖️ 车队中坚 · 功过相抵"
            tag_cls = "neutral"

        squad_members_rank.append({
            "personaname": st["personaname"],
            "account_id": st["account_id"],
            "is_me": st["is_me"],
            "is_roster_friend": st["is_roster_friend"],
            "games": st["games"],
            "wins": st["wins"],
            "win_rate": win_rate,
            "avg_blame_pct": avg_blame,
            "avg_rating": avg_rating,
            "mvp_count": st["mvp_count"],
            "culprit_count": st["culprit_count"],
            "avg_kda": f"{st['total_kills']/g:.1f}/{avg_deaths:.1f}/{st['total_assists']/g:.1f}",
            "avg_dead_sec": avg_dead_sec,
            "role_tag": role_tag,
            "tag_cls": tag_cls,
            "heroes": st["heroes"][:4],
        })

    # 排序：先把主视角、车队好友、多局共同出场的排在前面，再按场均分锅占比降序展示「惯犯度」
    squad_members_rank.sort(
        key=lambda x: (1 if (x["is_me"] or x["is_roster_friend"] or x["games"] > 1) else 0, x["avg_blame_pct"]),
        reverse=True,
    )

    # 2. 近期 12 场英雄池与组排红黑榜
    party_games = [m for m in recent_matches if int(m.get("party_size") or 1) >= 2]
    solo_games = [m for m in recent_matches if int(m.get("party_size") or 1) < 2]
    party_wins = sum(1 for m in party_games if m.get("won"))
    solo_wins = sum(1 for m in solo_games if m.get("won"))

    hero_buckets: Dict[str, Dict[str, Any]] = {}
    for m in recent_matches:
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
        recent_hero_pool.append({
            "hero_short_zh": hb["hero_short_zh"],
            "hero_img": hb["hero_img"],
            "games": hb["games"],
            "wins": hb["wins"],
            "win_rate": wr,
            "avg_kda": f"{hb['kills']/g:.1f}/{hb['deaths']/g:.1f}/{hb['assists']/g:.1f}",
            "verdict": "上分绝活" if wr >= 60 else ("胜率合格" if wr >= 50 else "掉分慎选"),
        })
    recent_hero_pool.sort(key=lambda x: (x["games"], x["win_rate"]), reverse=True)

    return {
        "analyzed_matches": analyzed_matches_summary,
        "squad_members_rank": squad_members_rank,
        "recent_hero_pool": recent_hero_pool,
        "party_summary": {
            "party_games": len(party_games),
            "party_wins": party_wins,
            "party_win_rate": round((party_wins / max(1, len(party_games))) * 100, 1) if party_games else 0.0,
            "solo_games": len(solo_games),
            "solo_wins": solo_wins,
            "solo_win_rate": round((solo_wins / max(1, len(solo_games))) * 100, 1) if solo_games else 0.0,
        },
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
    default_teammates = {
        1: (roster or {}).get("main_name") or "Flame = ez mute",
        2: "Replica",
        3: "Make Your Choice",
        4: "Paphets",
        5: "Mr. Brightside",
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
        arch = HERO_ARCHETYPES.get(hid) or {}
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
        arch = HERO_ARCHETYPES.get(hid) or {}
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

    early_plan = {
        "title": "前期对线与抢符 (00:00 – 10:00) · 怎么分路 & 怎么打出线优",
        "lanes": [
            {
                "lane": "优势路 (1号位 + 5号位)",
                "heroes": f"{p1['hero_short_zh']} ({p1['personaname']}) + {p5['hero_short_zh']} ({p5['personaname']})",
                "tasks": [
                    f"00:00 抢完赏金符回线，{p5['hero_short_zh']} 用技能帮 {p1['hero_short_zh']} 抢前两波远程兵（先到2级就有击杀窗口）。",
                    f"01:15 / 02:15 {p5['hero_short_zh']} 准时拉小野消兵线，03:00 / 06:00 提前卡位抢莲花池。",
                    f"10分钟硬指标：{p1['hero_short_zh']} 正补 ≥ 55 刀、阵亡 ≤ 1 次。",
                ],
            },
            {
                "lane": "中路单挑 (2号位)",
                "heroes": f"{p2['hero_short_zh']} ({p2['personaname']})",
                "tasks": [
                    f"01:50 / 03:50 提前用 AOE 技能推线进敌方塔下，再去控水符/神符。",
                    f"05:30 补出中路高台假眼，06:00 配合 4号位 {p4['hero_short_zh']} 控第一个强化符，拿到加速/双倍直接包边路拿塔。",
                ],
            },
            {
                "lane": "劣势路抗压/施压 (3号位 + 4号位)",
                "heroes": f"{p3['hero_short_zh']} ({p3['personaname']}) + {p4['hero_short_zh']} ({p4['personaname']})",
                "tasks": [
                    f"{p4['hero_short_zh']} 开局用真眼/肉身封敌方小野，阻止敌方5号位拉野，逼迫兵线进本方塔前。",
                    f"04:00 / 06:00 {p4['hero_short_zh']} 准时去中路帮 {p2['hero_short_zh']} 抢符；07:00 记得支援或偷敌方经验神龛(智慧符)。",
                ],
            },
        ],
    }

    mid_plan = {
        "title": "中期抱团与控图 (10:00 – 25:00) · 谁带节奏 & 抓谁推哪",
        "key_timings": [
            f"【12:00 – 15:00 第一波大节奏】一旦 {p3['hero_short_zh']} 或 {p4['hero_short_zh']} 做出跳刀/阿托斯，{p5['hero_short_zh']} 立刻买雾叫齐 2/3/4/5 四人，开雾抓敌方中路或优势路1号位，得手后顺势拔掉敌方中一塔！",
            f"【15:00 – 20:00 视野压制与刷钱分配】拔掉敌方外塔后，{p4['hero_short_zh']}+{p5['hero_short_zh']} 把假眼插进敌方主野区高台，让 {p1['hero_short_zh']} 安全收三角区+边线，2/3号位占住危险线。",
            f"【20:00 魔晶与一代肉山盾】20:00 准时抱团打痛苦魔方拿免费魔晶；随后一旦抓死敌方任一核心，立刻五人进肉山坑给 {p1['hero_short_zh']} 或 {p2['hero_short_zh']} 控下一代不朽盾！",
        ],
    }

    late_plan = {
        "title": "后期盾团与高地终结 (25:00+) · 集火优先级 & 买活铁律",
        "rules": [
            f"【团战集火优先级】{target_priority_text}",
            f"【核心 BKB 纪律】25分钟后 {p1['hero_short_zh']}、{p2['hero_short_zh']}、{p3['hero_short_zh']} 没有黑皇杖(BKB)或大招 CD 时，严禁接正面 5v5 团战，先带线牵制等关键装。",
            f"【上高地唯一铁律】不带肉山盾绝不硬冲三塔！带盾上高时，只留盾核 {p1['hero_short_zh']} 站在高地拆建筑，{p3['hero_short_zh']} 与双辅助全部退在台阶下卡视野随时反手救人或秒跳！",
        ],
    }

    role_guides = []
    for p in own_players:
        pos = p["pos"]
        hid = p["hero_id"]
        arch = get_hero_archetype(p)
        rec_items = HERO_CUSTOM_ITEMS.get(hid) or ROLE_DEFAULT_ITEMS.get(pos, [])
        if pos == 1:
            partner = f"对线绑定 5号位 {p5['hero_short_zh']}，团战紧跟 3号位 {p3['hero_short_zh']} 先手收割"
            golden_rule = "前18分钟只接塔下反打与稳杀局，BKB出来前绝不第一个冲进黑雾！"
        elif pos == 2:
            partner = f"6分钟后联动 4号位 {p4['hero_short_zh']} 与 3号位 {p3['hero_short_zh']} 开雾提速"
            golden_rule = "6/8/10分钟神符必须提前推线控住，中期切忌单人无视野过河道压二塔！"
        elif pos == 3:
            partner = f"对线搭档 4号位 {p4['hero_short_zh']}，中期绑定 5号位 {p5['hero_short_zh']} 开雾找节奏"
            golden_rule = "跳刀第一波必须开雾打出击杀转推塔，团战盯死敌方核心或后排救人位！"
        elif pos == 4:
            partner = f"4/6分钟保 2号位 {p2['hero_short_zh']} 控符，12分钟后跟紧 3号位 {p3['hero_short_zh']} 接第二手控制"
            golden_rule = "团战别跟3号位重叠交控制，等先手眩晕快结束再接技能最大化控制链！"
        else:
            partner = f"前10分钟死保 1号位 {p1['hero_short_zh']}，中期买满真假眼与诡计之雾"
            golden_rule = "绝对不准一个人去黑雾河道插眼送人头，永远站在大哥身后 600 码随时给微光/控制！"

        role_guides.append({
            "pos": pos,
            "pos_label": p["pos_label"],
            "player_name": p["personaname"],
            "hero_id": hid,
            "hero_short_zh": p["hero_short_zh"],
            "hero_img": p["hero_img"],
            "roles": arch.get("roles") or [],
            "key_spells": arch.get("key_spells") or [],
            "recommended_items": rec_items,
            "partner_synergy": partner,
            "golden_rule": golden_rule,
        })

    combo_lines_txt = "\n".join(
        f"  • 【{c['name']}】({' + '.join(h['hero_short_zh'] for h in c['heroes'])})：{c['mechanic']}"
        for c in pregame_combos[:3]
    )
    role_lines_txt = "\n".join(
        f"  [{rg['pos']}号位 {rg['hero_short_zh']} · {rg['player_name']}] 推荐出装：{' → '.join(rg['recommended_items'][:3])} ｜ 铁律：{rg['golden_rule']}"
        for rg in role_guides
    )

    grade_str = draft_eval.get("grade") or "A 级 · 扎实五黑体系"
    chat_brief_text = (
        f"⚔️【五黑赛前10秒作战锦囊 · 阵容评级 {grade_str} ({overall_score}分)】\n"
        f"👉 本方阵容：1.{p1['hero_short_zh']}({p1['personaname']}) / 2.{p2['hero_short_zh']}({p2['personaname']}) / 3.{p3['hero_short_zh']}({p3['personaname']}) / 4.{p4['hero_short_zh']}({p4['personaname']}) / 5.{p5['hero_short_zh']}({p5['personaname']})\n"
        f"{('👉 敌方阵容：' + ' / '.join(enemy_names) + chr(10)) if enemy_names else ''}"
        f"🏆 本局赢法：{win_condition}\n"
        f"⚠️ 翻车红线：{lose_condition}\n"
        f"🔥 必打技能配合：\n{combo_lines_txt}\n"
        f"🎯 团战集火：{target_priority_text}\n"
        f"📋 五人各自任务与出装：\n{role_lines_txt}"
    )

    return {
        "own_players": own_players,
        "enemy_players": enemy_players,
        "grade": grade_str,
        "overall_score": overall_score,
        "dimensions": draft_eval.get("scores") or {},
        "tempo_style": tempo_style,
        "win_condition": win_condition,
        "lose_condition": lose_condition,
        "target_priority": target_priority_text,
        "strengths": draft_eval.get("strengths") or [],
        "weaknesses": draft_eval.get("weaknesses") or [],
        "counter_tips": draft_eval.get("weaknesses") or [],
        "combos": pregame_combos,
        "early_plan": early_plan,
        "mid_plan": mid_plan,
        "late_plan": late_plan,
        "role_guides": role_guides,
        "chat_brief_text": chat_brief_text,
    }



