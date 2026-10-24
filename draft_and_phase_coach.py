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
    1: {  # 敌法师 Anti-Mage
        "short": "敌法师",
        "roles": ["闪烁极限带球刷钱", "法力虚空引爆高蓝核", "法术反制克制点控法师"],
        "scores": {"init": 42, "burst": 78, "tf": 68, "push": 84, "pick": 74, "late": 94, "tank": 64},
        "dmg_type": "physical",
        "synergy_tags": ["hard_carry", "split_pusher", "anti_mage"],
    },
    2: {  # 斧王 Axe
        "short": "斧王",
        "roles": ["跳刀狂战士之吼无视BKB群嘲", "反击螺旋克制近战与多段平A", "淘汰之刃斩杀收割"],
        "scores": {"init": 94, "burst": 76, "tf": 86, "push": 52, "pick": 86, "late": 76, "tank": 92},
        "dmg_type": "pure",
        "synergy_tags": ["frontline_tank", "bkb_pierce_init", "instant_stun"],
    },
    5: {  # 水晶室女 Crystal Maiden
        "short": "水晶室女",
        "roles": ["冰封禁制先手留人", "奥术光环全队回蓝", "极寒领域团战高额AOE"],
        "scores": {"init": 68, "burst": 76, "tf": 84, "push": 38, "pick": 75, "late": 55, "tank": 28},
        "dmg_type": "magical",
        "synergy_tags": ["root_setup", "mana_aura", "squishy_ranged"],
    },
    7: {  # 撼地者 Earthshaker
        "short": "撼地者",
        "roles": ["沟壑超远封路留人", "跳刀回音击毁天灭地反手清场", "余震连环控制克制幻象与扎堆"],
        "scores": {"init": 92, "burst": 90, "tf": 94, "push": 42, "pick": 82, "late": 78, "tank": 64},
        "dmg_type": "magical",
        "synergy_tags": ["aoe_teamfight", "instant_stun"],
    },
    8: {  # 主宰 Juggernaut
        "short": "主宰",
        "roles": ["奶棒推进核", "魔免剑刃风暴", "无敌斩收割"],
        "scores": {"init": 38, "burst": 84, "tf": 78, "push": 92, "pick": 68, "late": 86, "tank": 68},
        "dmg_type": "physical",
        "synergy_tags": ["hard_carry", "siege_healer", "empower_carrier"],
    },
    9: {  # 米拉娜 Mirana
        "short": "米拉娜",
        "roles": ["超远穿云箭接控", "全图月之暗面开雾", "流星爆发补伤害"],
        "scores": {"init": 62, "burst": 72, "tf": 68, "push": 55, "pick": 88, "late": 65, "tank": 45},
        "dmg_type": "magical",
        "synergy_tags": ["follow_up_stun", "team_invis_gank", "squishy_ranged"],
    },
    11: {  # 影魔 Shadow Fiend
        "short": "影魔",
        "roles": ["三压高爆发清线刷钱", "魂之挽歌团战恐惧AOE", "魔王降临减甲拆塔"],
        "scores": {"init": 45, "burst": 92, "tf": 82, "push": 86, "pick": 62, "late": 84, "tank": 44},
        "dmg_type": "mixed",
        "synergy_tags": ["glass_cannon_core", "squishy_ranged", "no_stun_greedy"],
    },
    12: {  # 幻影长矛手 Phantom Lancer
        "short": "幻影长矛手",
        "roles": ["并列幻象海无限拉扯消蓝", "神行百变躲技能切后排", "大后期无AOE阵容的绝对噩梦"],
        "scores": {"init": 38, "burst": 68, "tf": 84, "push": 78, "pick": 64, "late": 95, "tank": 76},
        "dmg_type": "physical",
        "synergy_tags": ["hard_carry", "illusion_swarm"],
    },
    13: {  # 帕克 Puck
        "short": "帕克",
        "roles": ["梦境缠绕留人断TP", "新月之痕沉默接幻象法球高机动拉扯", "相位转移无伤秀翻后排"],
        "scores": {"init": 88, "burst": 84, "tf": 88, "push": 62, "pick": 90, "late": 82, "tank": 52},
        "dmg_type": "magical",
        "synergy_tags": ["aoe_teamfight", "high_mobility_core"],
    },
    14: {  # 帕吉 Pudge
        "short": "帕吉",
        "roles": ["肉钩超远破阵先手/救人", "肢解无视BKB点控", "腐肉堆积高血量肉盾"],
        "scores": {"init": 78, "burst": 76, "tf": 70, "push": 40, "pick": 88, "late": 72, "tank": 86},
        "dmg_type": "magical",
        "synergy_tags": ["frontline_tank", "bkb_pierce_init"],
    },
    15: {  # 剃刀 Razor
        "short": "剃刀",
        "roles": ["静电连接抽干敌方物理主C攻击力", "风暴之眼减甲持续冲脸", "等离子场范围减速压制"],
        "scores": {"init": 58, "burst": 68, "tf": 84, "push": 76, "pick": 72, "late": 78, "tank": 82},
        "dmg_type": "physical",
        "synergy_tags": ["frontline_tank", "anti_carry_link"],
    },
    21: {  # 风行者 Windranger
        "short": "风行者",
        "roles": ["束缚击双人长晕", "集中火力定点秒杀核心与拆塔", "风行高闪避机动切入"],
        "scores": {"init": 76, "burst": 88, "tf": 72, "push": 84, "pick": 88, "late": 82, "tank": 52},
        "dmg_type": "physical",
        "synergy_tags": ["pickoff_roamer", "squishy_ranged"],
    },
    22: {  # 宙斯 Zeus
        "short": "宙斯",
        "roles": ["雷神之怒全图支援与开视野", "雷击反隐排眼克制隐身系", "超远距离法系炮台"],
        "scores": {"init": 40, "burst": 96, "tf": 90, "push": 48, "pick": 78, "late": 80, "tank": 34},
        "dmg_type": "magical",
        "synergy_tags": ["global_presence", "true_sight_reveal", "squishy_ranged"],
    },
    23: {  # 昆卡 Kunkka
        "short": "昆卡",
        "roles": ["X标记+洪流+幽灵船三连无解先手", "朗姆酒全队50%减伤", "潮汐使者水刀高额AOE"],
        "scores": {"init": 88, "burst": 84, "tf": 94, "push": 68, "pick": 86, "late": 78, "tank": 86},
        "dmg_type": "mixed",
        "synergy_tags": ["frontline_tank", "aoe_teamfight"],
    },
    25: {  # 莉娜 Lina
        "short": "莉娜",
        "roles": ["神灭斩+光击阵超高单体秒杀", "炽魂高攻速远程物理/法系双修炮台", "龙破斩远程清线推塔"],
        "scores": {"init": 64, "burst": 96, "tf": 78, "push": 82, "pick": 84, "late": 82, "tank": 40},
        "dmg_type": "mixed",
        "synergy_tags": ["glass_cannon_core", "squishy_ranged"],
    },
    26: {  # 莱恩 Lion
        "short": "莱恩",
        "roles": ["瞬发变羊+穿刺双控", "死亡一指高额单体秒杀", "抽蓝限制前排"],
        "scores": {"init": 88, "burst": 92, "tf": 65, "push": 30, "pick": 92, "late": 60, "tank": 28},
        "dmg_type": "magical",
        "synergy_tags": ["instant_hex_stun", "high_magic_nuke", "squishy_ranged"],
    },
    27: {  # 暗影萨满 Shadow Shaman
        "short": "暗影萨满",
        "roles": ["妖术+枷锁超长双点控", "群蛇守卫强拆外塔与高地", "苍穹震击清线消耗"],
        "scores": {"init": 88, "burst": 74, "tf": 76, "push": 96, "pick": 90, "late": 66, "tank": 32},
        "dmg_type": "magical",
        "synergy_tags": ["instant_hex_stun", "tower_melter", "squishy_ranged"],
    },
    28: {  # 斯拉达 Slardar
        "short": "斯拉达",
        "roles": ["跳刀鱼人碎击瞬发群晕", "侵蚀雾霭巨额减甲+真视克制隐身与肉核", "深海重击被动连晕"],
        "scores": {"init": 90, "burst": 78, "tf": 80, "push": 62, "pick": 92, "late": 78, "tank": 86},
        "dmg_type": "physical",
        "synergy_tags": ["frontline_tank", "instant_stun", "true_sight_reveal", "armor_reduction"],
    },
    29: {  # 潮汐猎人 Tidehunter
        "short": "潮汐猎人",
        "roles": ["毁灭超大范围团控", "海妖外壳强解状态顶前排", "锚击降低敌方物理攻击"],
        "scores": {"init": 94, "burst": 62, "tf": 98, "push": 58, "pick": 60, "late": 78, "tank": 95},
        "dmg_type": "magical",
        "synergy_tags": ["aoe_ravage_stun", "frontline_tank", "aoe_teamfight"],
    },
    30: {  # 巫医 Witch Doctor
        "short": "巫医",
        "roles": ["麻痹药剂弹射群控", "诅咒百分比掉血结算", "死亡守卫毁灭团战输出"],
        "scores": {"init": 68, "burst": 94, "tf": 92, "push": 42, "pick": 82, "late": 72, "tank": 35},
        "dmg_type": "magical",
        "synergy_tags": ["maledict_burst_amp", "channeled_ward_ult", "squishy_ranged"],
    },
    31: {  # 巫妖 Lich
        "short": "巫妖",
        "roles": ["冰霜护甲提供前排高额物理减伤", "邪恶凝视瞬发拉人点控", "连环霜冻弹射毁灭扎堆阵型"],
        "scores": {"init": 74, "burst": 88, "tf": 90, "push": 40, "pick": 80, "late": 68, "tank": 36},
        "dmg_type": "magical",
        "synergy_tags": ["aoe_teamfight", "save_support", "squishy_ranged"],
    },
    32: {  # 力丸 Riki
        "short": "力丸",
        "roles": ["烟幕范围沉默致盲", "隐身视野压制切后排", "绝杀秘技规避伤害"],
        "scores": {"init": 72, "burst": 82, "tf": 70, "push": 38, "pick": 95, "late": 78, "tank": 45},
        "dmg_type": "physical",
        "synergy_tags": ["aoe_silence_cloud", "backline_assassin"],
    },
    35: {  # 狙击手 Sniper
        "short": "狙击手",
        "roles": ["超远射程无伤点塔与守高地", "榴霰弹视野压制消耗", "极怕冲脸切后排的纯炮台核"],
        "scores": {"init": 25, "burst": 76, "tf": 80, "push": 88, "pick": 45, "late": 86, "tank": 32},
        "dmg_type": "physical",
        "synergy_tags": ["glass_cannon_core", "squishy_ranged", "no_stun_greedy"],
    },
    36: {  # 瘟疫法师 Necrophos
        "short": "瘟疫法师",
        "roles": ["死神镰刀斩杀加读秒", "竭心光环百分比磨血+死亡脉冲续航顶前排", "幽魂护罩物理免疫"],
        "scores": {"init": 68, "burst": 84, "tf": 88, "push": 72, "pick": 74, "late": 80, "tank": 86},
        "dmg_type": "magical",
        "synergy_tags": ["frontline_tank", "regen_core"],
    },
    40: {  # 剧毒术士 Venomancer
        "short": "剧毒术士",
        "roles": ["瘟疫守卫铺视野守塔推进", "瘴气+毒刺持续减速折磨短腿前排", "恶性瘟疫百分比持续掉血"],
        "scores": {"init": 45, "burst": 58, "tf": 84, "push": 78, "pick": 64, "late": 62, "tank": 40},
        "dmg_type": "magical",
        "synergy_tags": ["squishy_ranged", "no_stun_greedy"],
    },
    41: {  # 虚空假面 Faceless Void
        "short": "虚空假面",
        "roles": ["时间结界无视BKB毁天灭地大招", "时间漫游回血规避爆发", "时间锁定被动晕眩后期真神"],
        "scores": {"init": 95, "burst": 86, "tf": 98, "push": 80, "pick": 82, "late": 98, "tank": 76},
        "dmg_type": "physical",
        "synergy_tags": ["hard_carry", "bkb_pierce_init", "aoe_teamfight"],
    },
    43: {  # 死亡先知 Death Prophet
        "short": "死亡先知",
        "roles": ["驱使恶灵团战清场与无解拆塔", "吸魂巫术百分比抽血续航", "沉默魔法范围沉默断连招"],
        "scores": {"init": 62, "burst": 74, "tf": 90, "push": 96, "pick": 70, "late": 78, "tank": 78},
        "dmg_type": "physical",
        "synergy_tags": ["tower_melter", "aoe_teamfight"],
    },
    44: {  # 幻影刺客 Phantom Assassin
        "short": "幻影刺客",
        "roles": ["高暴击物理切入收割", "模糊闪避物理平A", "BKB成型期瞬秒后排"],
        "scores": {"init": 55, "burst": 95, "tf": 75, "push": 62, "pick": 85, "late": 92, "tank": 58},
        "dmg_type": "physical",
        "synergy_tags": ["hard_carry", "backline_assassin", "empower_carrier"],
    },
    45: {  # 帕格纳 Pugna
        "short": "帕格纳",
        "roles": ["爆轰磨塔快推", "衰老虚无增伤/救人", "幽冥守卫反法系"],
        "scores": {"init": 30, "burst": 85, "tf": 78, "push": 98, "pick": 65, "late": 62, "tank": 30},
        "dmg_type": "magical",
        "synergy_tags": ["magic_amp", "tower_melter", "anti_caster_ward", "squishy_ranged"],
    },
    49: {  # 龙骑士 Dragon Knight
        "short": "龙骑士",
        "roles": ["瞬发神龙摆尾先手", "古龙形态腐蚀推塔", "高护甲前排顶梁柱"],
        "scores": {"init": 86, "burst": 68, "tf": 78, "push": 90, "pick": 80, "late": 80, "tank": 90},
        "dmg_type": "physical",
        "synergy_tags": ["instant_stun", "frontline_tank", "empower_carrier"],
    },
    53: {  # 先知 Nature's Prophet
        "short": "先知",
        "roles": ["全图传送支援收割与带球牵制", "发芽框人克制无推推近战", "正面5v5硬刚与抗冲脸能力偏弱的机动核"],
        "scores": {"init": 64, "burst": 74, "tf": 60, "push": 95, "pick": 90, "late": 70, "tank": 44},
        "dmg_type": "physical",
        "synergy_tags": ["global_presence", "split_pusher", "squishy_ranged", "weak_frontal_carry"],
    },
    55: {  # 黑暗贤者 Dark Seer
        "short": "黑暗贤者",
        "roles": ["真空+复制之墙团战完美聚怪", "离子外壳推线消耗近战", "奔腾极限加速切入/救人"],
        "scores": {"init": 90, "burst": 68, "tf": 96, "push": 62, "pick": 72, "late": 86, "tank": 80},
        "dmg_type": "magical",
        "synergy_tags": ["aoe_teamfight", "frontline_tank"],
    },
    56: {  # 克林克兹 Clinkz
        "short": "克林克兹",
        "roles": ["骨隐步全图隐身抓单偷塔", "炽烈火雨+焦油炸弹减甲点杀脆皮", "身板极脆、缺乏团控且怕反隐强留的刺客核"],
        "scores": {"init": 42, "burst": 90, "tf": 58, "push": 90, "pick": 92, "late": 70, "tank": 38},
        "dmg_type": "physical",
        "synergy_tags": ["invis_roamer", "split_pusher", "squishy_ranged", "weak_frontal_carry", "no_stun_greedy"],
    },
    59: {  # 哈斯卡 Huskar
        "short": "哈斯卡",
        "roles": ["狂战士之血残血极限魔抗攻速", "牺牲冲脸强换前排", "极怕远古冰魄禁疗与高物理爆发的节奏核"],
        "scores": {"init": 72, "burst": 86, "tf": 76, "push": 84, "pick": 78, "late": 64, "tank": 84},
        "dmg_type": "magical",
        "synergy_tags": ["frontline_tank", "regen_core"],
    },
    60: {  # 暗夜魔王 Night Stalker
        "short": "暗夜魔王",
        "roles": ["暗夜猎影高空视野+无视地形切后排", "伤残恐惧近身持续沉默法师", "夜晚统治力极强的冲脸前排"],
        "scores": {"init": 88, "burst": 82, "tf": 82, "push": 62, "pick": 94, "late": 76, "tank": 86},
        "dmg_type": "physical",
        "synergy_tags": ["frontline_tank", "backline_assassin"],
    },
    62: {  # 赏金猎人 Bounty Hunter
        "short": "赏金猎人",
        "roles": ["追踪术提供真视视野与团队高额赏金滚雪球", "暗影步破隐晕眩骚扰", "正面团战偏脆的游走节奏点"],
        "scores": {"init": 62, "burst": 74, "tf": 60, "push": 40, "pick": 92, "late": 64, "tank": 48},
        "dmg_type": "mixed",
        "synergy_tags": ["true_sight_reveal", "invis_roamer"],
    },
    63: {  # 编织者 Weaver
        "short": "编织者",
        "roles": ["缩地极速切入与拉扯", "时光倒流回到5秒前满血解状态", "凰虫减甲配合连击点杀脆皮"],
        "scores": {"init": 48, "burst": 84, "tf": 72, "push": 80, "pick": 86, "late": 82, "tank": 52},
        "dmg_type": "physical",
        "synergy_tags": ["invis_roamer", "squishy_ranged", "no_stun_greedy"],
    },
    64: {  # 杰奇洛 Jakiro
        "short": "杰奇洛",
        "roles": ["冰封路径超远群控留人", "液态火/液态冰无伤磨塔降攻速", "烈焰焚身狭窄地形毁灭AOE"],
        "scores": {"init": 78, "burst": 76, "tf": 88, "push": 84, "pick": 76, "late": 66, "tank": 52},
        "dmg_type": "magical",
        "synergy_tags": ["aoe_teamfight", "tower_melter", "squishy_ranged"],
    },
    67: {  # 幽鬼 Spectre
        "short": "幽鬼",
        "roles": ["暗影步/鬼影重重全图定点切后排", "折射反弹伤害大后期无解肉核", "荒芜纯粹伤害克制落单"],
        "scores": {"init": 82, "burst": 78, "tf": 90, "push": 62, "pick": 92, "late": 96, "tank": 92},
        "dmg_type": "mixed",
        "synergy_tags": ["hard_carry", "global_presence", "frontline_tank", "backline_assassin"],
    },
    68: {  # 远古冰魄 Ancient Apparition
        "short": "远古冰魄",
        "roles": ["冰晶爆轰全图斩杀+100%禁疗天克回血核", "寒霜之足+冰霜漩涡远程增伤留人", "极寒之触超远消耗"],
        "scores": {"init": 64, "burst": 86, "tf": 88, "push": 42, "pick": 80, "late": 78, "tank": 30},
        "dmg_type": "magical",
        "synergy_tags": ["global_presence", "anti_heal_ult", "squishy_ranged"],
    },
    71: {  # 裂魂人 Spirit Breaker
        "short": "裂魂人",
        "roles": ["暗影冲刺全图跨地形锁定支援与破带球", "幽冥一击无视BKB击退", "威吓高状态抗性冲散敌方后排"],
        "scores": {"init": 92, "burst": 78, "tf": 80, "push": 48, "pick": 96, "late": 74, "tank": 86},
        "dmg_type": "magical",
        "synergy_tags": ["global_presence", "bkb_pierce_init", "frontline_tank", "anti_split_push"],
    },
    73: {  # 炼金术士 Alchemist
        "short": "炼金术士",
        "roles": ["贪魔的贪婪超高速刷钱养A杖", "化学狂暴高回血中期平推肉盾", "极怕冰魂禁疗与拖入大后期"],
        "scores": {"init": 72, "burst": 76, "tf": 82, "push": 88, "pick": 74, "late": 72, "tank": 88},
        "dmg_type": "physical",
        "synergy_tags": ["frontline_tank", "regen_core"],
    },
    76: {  # 殁境神蚀者 Outworld Destroyer
        "short": "殁境神蚀者",
        "roles": ["星体禁锢断节奏救人", "奥术天球纯粹法球巨额点杀单前排", "神智之蚀大招清场"],
        "scores": {"init": 76, "burst": 95, "tf": 88, "push": 55, "pick": 84, "late": 90, "tank": 64},
        "dmg_type": "pure",
        "synergy_tags": ["save_banish", "pure_damage_core", "anti_tank_pure"],
    },
    83: {  # 树精卫士 Treant Protector
        "short": "树精卫士",
        "roles": ["疯狂生长无视BKB大范围捆绑", "活体护甲全图修塔保人", "寄生种子+自然卷握强力线上消耗"],
        "scores": {"init": 88, "burst": 58, "tf": 90, "push": 45, "pick": 74, "late": 74, "tank": 82},
        "dmg_type": "magical",
        "synergy_tags": ["bkb_pierce_init", "save_support", "frontline_tank"],
    },
    86: {  # 拉比克 Rubick
        "short": "拉比克",
        "roles": ["隔空取物瞬发先手举", "技能窃取反制大招", "弱化能流减攻清线"],
        "scores": {"init": 80, "burst": 70, "tf": 85, "push": 45, "pick": 82, "late": 78, "tank": 35},
        "dmg_type": "magical",
        "synergy_tags": ["instant_lift_stun", "spell_steal_counter", "squishy_ranged"],
    },
    87: {  # 干扰者 Disruptor
        "short": "干扰者",
        "roles": ["瞥视千里抓回TP与隐身逃生英雄", "静态风暴+动能场框大范围沉默禁用物品", "天克先知/小骷髅等高机动游走核"],
        "scores": {"init": 90, "burst": 78, "tf": 94, "push": 38, "pick": 95, "late": 82, "tank": 34},
        "dmg_type": "magical",
        "synergy_tags": ["anti_split_push", "aoe_teamfight", "squishy_ranged"],
    },
    88: {  # 司夜刺客 Nyx Assassin
        "short": "司夜刺客",
        "roles": ["复仇隐身超高爆发猎杀脆皮远程核", "尖刺外壳完美反弹敌方AOE先手", "穿刺+心灵焦灼控制消蓝"],
        "scores": {"init": 84, "burst": 92, "tf": 76, "push": 36, "pick": 95, "late": 72, "tank": 62},
        "dmg_type": "magical",
        "synergy_tags": ["invis_roamer", "backline_assassin", "anti_squishy_ranged"],
    },
    93: {  # 斯拉克 Slark
        "short": "斯拉克",
        "roles": ["能量转移无限偷属性越打越猛", "黑暗契约强解一切非光环硬控", "暗影之舞+魔晶深海劫掠无敌切入与救人"],
        "scores": {"init": 78, "burst": 84, "tf": 86, "push": 68, "pick": 94, "late": 94, "tank": 78},
        "dmg_type": "physical",
        "synergy_tags": ["hard_carry", "anti_tank_steal", "regen_core"],
    },
    96: {  # 半人马战行者 Centaur Warrunner
        "short": "半人马战行者",
        "roles": ["跳刀马蹄践踏稳定先手群晕", "奔袭冲撞全队极限加速开团/撤退", "双刃剑+反击高血量肉盾"],
        "scores": {"init": 90, "burst": 76, "tf": 86, "push": 60, "pick": 82, "late": 78, "tank": 94},
        "dmg_type": "magical",
        "synergy_tags": ["frontline_tank", "instant_stun", "aoe_teamfight"],
    },
    97: {  # 马格纳斯 Magnus
        "short": "马格纳斯",
        "roles": ["授予力量刷钱引擎", "跳刀两极反转团控", "巨角冲撞破坏阵型"],
        "scores": {"init": 95, "burst": 65, "tf": 96, "push": 72, "pick": 78, "late": 88, "tank": 75},
        "dmg_type": "mixed",
        "synergy_tags": ["aoe_vacuum_stun", "empower_buffer", "reposition", "bkb_pierce_init"],
    },
    99: {  # 钢背兽 Bristleback
        "short": "钢背兽",
        "roles": ["粘稠鼻涕叠甲减移速", "刺针扫射持续肉搏", "前排吸收成吨火力"],
        "scores": {"init": 45, "burst": 60, "tf": 84, "push": 72, "pick": 58, "late": 76, "tank": 96},
        "dmg_type": "physical",
        "synergy_tags": ["armor_reduction", "frontline_tank"],
    },
    101: {  # 天怒法师 Skywrath Mage
        "short": "天怒法师",
        "roles": ["上古封印法系增伤沉默", "神秘之耀超高单体法术轰炸", "身板极脆怕冲脸的后排法核/辅助"],
        "scores": {"init": 68, "burst": 98, "tf": 72, "push": 34, "pick": 88, "late": 66, "tank": 26},
        "dmg_type": "magical",
        "synergy_tags": ["high_magic_nuke", "squishy_ranged"],
    },
    105: {  # 工程师 Techies
        "short": "工程师",
        "roles": ["爆破起飞远程跳脸沉默群伤", "感应地雷阵地封锁与清线磨塔", "粘性炸弹拉扯但缺乏瞬发硬控"],
        "scores": {"init": 74, "burst": 86, "tf": 78, "push": 74, "pick": 76, "late": 66, "tank": 44},
        "dmg_type": "magical",
        "synergy_tags": ["squishy_ranged"],
    },
    112: {  # 寒冬飞龙 Winter Wyvern
        "short": "寒冬飞龙",
        "roles": ["寒冬诅咒无视BKB反手团控克制抱团物理核", "极寒之拥物理免疫救人", "严寒烧灼超远距离百分比消耗"],
        "scores": {"init": 82, "burst": 66, "tf": 90, "push": 42, "pick": 70, "late": 82, "tank": 38},
        "dmg_type": "magical",
        "synergy_tags": ["bkb_pierce_init", "save_support", "squishy_ranged"],
    },
    114: {  # 齐天大圣 Monkey King
        "short": "齐天大圣",
        "roles": ["猴子猴孙超大范围阵地团战封锁", "如意棒法叠被动高额吸血暴击", "丛林之舞树顶高机动视野侦察"],
        "scores": {"init": 76, "burst": 86, "tf": 92, "push": 74, "pick": 86, "late": 88, "tank": 68},
        "dmg_type": "physical",
        "synergy_tags": ["hard_carry", "aoe_teamfight"],
    },
    123: {  # 森海飞霞 Hoodwink
        "short": "森海飞霞",
        "roles": ["野地奇袭捆树群控", "神枪在手超远破被动百分比狙杀", "松鼠步高机动游走逃生"],
        "scores": {"init": 76, "burst": 86, "tf": 76, "push": 52, "pick": 88, "late": 68, "tank": 36},
        "dmg_type": "magical",
        "synergy_tags": ["squishy_ranged", "follow_up_stun"],
    },
    131: {  # 环轨百戏王 Ringmaster
        "short": "环轨百戏王",
        "roles": ["逃生魔盒无敌救下被集火核心", "奇观轮团战大范围魅惑控场", "驯兽长鞭恐惧打断"],
        "scores": {"init": 76, "burst": 78, "tf": 88, "push": 44, "pick": 78, "late": 74, "tank": 38},
        "dmg_type": "magical",
        "synergy_tags": ["save_support", "aoe_teamfight", "squishy_ranged"],
    },
    135: {  # 破晓辰星 Dawnbreaker
        "short": "破晓辰星",
        "roles": ["天光现世全图空降回血群晕反打（天克抓单/带球体系）", "星破天惊+熠熠生辉高额前排肉搏回血", "上佳的一线全图反手三号位"],
        "scores": {"init": 84, "burst": 80, "tf": 92, "push": 72, "pick": 84, "late": 80, "tank": 88},
        "dmg_type": "physical",
        "synergy_tags": ["frontline_tank", "global_presence", "anti_split_push", "save_support"],
    },
    136: {  # 玛西 Marci
        "short": "玛西",
        "roles": ["回身踢+健步强先手留人", "怒拳破高爆发冲脸", "护卫反击提供吸血攻击力"],
        "scores": {"init": 88, "burst": 90, "tf": 80, "push": 68, "pick": 94, "late": 78, "tank": 76},
        "dmg_type": "physical",
        "synergy_tags": ["dive_initiator", "burst_brawler"],
    },
}


from hero_profiles_126 import HERO_PROFILES_126, get_hero_profile_126

# 将 126 英雄全量内置机制画像合并进 HERO_ARCHETYPES（保留手工精调项，补齐全部 126 英雄）
for _hid, _prof in HERO_PROFILES_126.items():
    _full_prof = get_hero_profile_126(_hid, 3, _prof.get("short", ""))
    _tc = _full_prof.get("timing_curve", "mid_tempo_brawler")
    _tc_zh = _full_prof.get("timing_curve_zh", "中期节奏支点")
    if _hid not in HERO_ARCHETYPES:
        HERO_ARCHETYPES[_hid] = {
            "short": _full_prof["short"],
            "roles": list(_full_prof["roles"]),
            "scores": dict(_full_prof["scores"]),
            "dmg_type": _full_prof["dmg_type"],
            "synergy_tags": list(_full_prof["synergy_tags"]),
            "timing_curve": _tc,
            "timing_curve_zh": _tc_zh,
            "early_rule": _full_prof.get("early_rule", ""),
            "mid_rule": _full_prof.get("mid_rule", ""),
            "late_rule": _full_prof.get("late_rule", ""),
            "shard_desc": _full_prof.get("shard_desc", ""),
            "core_item_hint": _full_prof.get("core_item_hint", ""),
        }
    else:
        HERO_ARCHETYPES[_hid]["timing_curve"] = _tc
        HERO_ARCHETYPES[_hid]["timing_curve_zh"] = _tc_zh
        for _k in ("early_rule", "mid_rule", "late_rule", "shard_desc", "core_item_hint"):
            if _k not in HERO_ARCHETYPES[_hid] and _k in _full_prof:
                HERO_ARCHETYPES[_hid][_k] = _full_prof[_k]


def get_hero_archetype(p: Dict[str, Any]) -> Dict[str, Any]:
    hid = int(p.get("hero_id") or 0)
    pos = int(p.get("pos") or 3)
    short = p.get("hero_short_zh") or p.get("hero_name") or f"英雄#{hid}"
    if hid in HERO_ARCHETYPES:
        return HERO_ARCHETYPES[hid]
    return get_hero_profile_126(hid, pos, short)


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
                    f"1) 发育期：马格纳斯必须卡冷却给 {c_short} 套上『授予力量』，让 {c_short} 拥有分裂与额外攻击力高速清远古与兵线；"
                    f"2) 团战期：马格纳斯切忌第一波裸跳送死，等敌方关键救人/反手（如{'、'.join(opp_names[:2])}）露头后，跳刀『两极反转』吸住多人或把核心拱回，"
                    f"{c_short} 立即接大招/溅射输出瞬间融化敌方前排。"
                ),
                "execution_audit": (
                    f"本局实战验货：马格纳斯整局释放『授予力量』{emp_cnt} 次、『两极反转』{rp_cnt} 次、『巨角冲撞』{skewer_cnt} 次；"
                    f"{c_short} 终局刷出 {carry['gpm']} GPM（净资产 {carry['net_worth']:,} 金，英雄伤害 {carry['hero_damage']:,}）。"
                    f"{'这套猛犸赋能+大招体系在后期团战成功兑现，是翻盘的核心引擎。' if carry['gpm'] >= 600 and rp_cnt >= 4 else '但本局中期多次出现猛犸与大哥脱节、大招控住人时核心不在场的断档情况，配合熟练度还得练！'}"
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
                "window": "04:00–15:00 · 6分钟动力符与夜晚第一波游走抓人",
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

        # 2) 先天克制检测
        anti_split_opps = [opp_hids[h] for h in (87, 135, 71, 88) if h in opp_hids]
        if ("weak_frontal_carry" in p1_arch.get("synergy_tags", []) or "weak_frontal_carry" in p2_arch.get("synergy_tags", [])) and len(anti_split_opps) >= 2:
            cnt_msg = (
                f"【机动带球与隐身抓单被敌方天克】敌方选出『{' + '.join(anti_split_opps)}』（如干扰者瞥视框大专抓TP/隐身、破晓辰星全图大招反打、司夜刺客隐身猎杀脆皮），"
                f"我方『{p1['hero_short_zh']}/{p2['hero_short_zh']}』一旦单带或先手抓人未秒掉，极易被敌方全图支援与留人反杀。"
            )
            counter_disadvantages.append(cnt_msg)
            weaknesses.append(cnt_msg)

        anti_tank_opps = [opp_hids[h] for h in (76, 93) if h in opp_hids]
        if len(frontliners) == 1 and len(anti_tank_opps) >= 1:
            cnt_msg = (
                f"【单前排『{frontliners[0]}』被敌方『{' + '.join(anti_tank_opps)}』克制】"
                f"{'殁境神蚀者星体禁锢+纯粹法球' if 76 in opp_hids else ''}{'与' if (76 in opp_hids and 93 in opp_hids) else ''}{'斯拉克能量转移无限偷属性' if 93 in opp_hids else ''}"
                f"天克我方唯一的单前排『{frontliners[0]}』，正面接团前排极难站住。"
            )
            counter_disadvantages.append(cnt_msg)
            weaknesses.append(cnt_msg)

        if 68 in opp_hids and any(h in own_hids for h in (59, 93, 73, 36)):
            regen_own = [own_hids[h] for h in (59, 93, 73, 36) if h in own_hids]
            cnt_msg = f"【回血核心被远古冰魄大招禁疗天克】我方『{'/'.join(regen_own)}』极度依赖回血续航，被敌方远古冰魄『冰晶爆轰』100%禁疗精准克制。"
            counter_disadvantages.append(cnt_msg)
            weaknesses.append(cnt_msg)

        if 45 in own_hids and 8 in own_hids:
            weaknesses.append(
                "【技能机制存在『衰老』冲突隐患】帕格纳的『衰老(虚无)』虽然能救人并加深法系伤害，但若在主宰平A输出或无敌斩期间误套给目标，会直接导致主宰物理砍不出伤害！"
            )

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
                f"，且极易被{opp_zh}『{'/'.join(anti_split_opps[:3])}』的反手留人与全图支援克制"
                if anti_split_opps
                else ""
            )
            verdict_summary = (
                f"{side_zh}这套『{own_heroes_str}』迎战{opp_zh}『{opp_heroes_str}』属于典型的偏科走钢丝阵容："
                f"仅在【{dim_names[best1]} ({own_s[best1]} vs {opp_s[best1]})】上有局部支点，但{flaw_brief}{counter_brief}；"
                f"正面5v5团战（{own_s['tf']} vs {opp_s['tf']}）容错率极低，完全仰仗带线牵制、抓落单与后排保命装的极限执行。"
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

            full_p = full_player_by_slot.get(slot) or {}
            pt_meta = full_p.get("phase_telemetry") or {}
            solo_picks = pt_meta.get("solo_pickoffs") or []
            slark_audit = full_p.get("slark_mechanism_audit")
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
                        good_list.append(f"对线基本功扎实（{t_curve_zh or '核心'}）：前10分钟斩获 {lh_gain} 正补 / {dn_gain} 反补，阶段 GPM 高达 {gpm_p:.0f}，无解肥发育。")
                    elif lh_gain >= 38:
                        good_list.append(f"抗压补刀合格（{t_curve_zh or '核心'}）：10分钟补出 {lh_gain} 正补 / {dn_gain} 反补（经济 +{gold_gain:,}），稳住了核心发育线。")
                    elif t_curve == "late_hyper_carry" and lh_gain >= 32 and deaths <= 1:
                        good_list.append(f"大核对线隐忍抗压（{t_curve_zh}）：前期身板弱势情况下稳住 {lh_gain} 补刀（+{gold_gain:,} 金），成功过渡至刷钱装。")
                    else:
                        bad_list.append(f"对线补刀严重不达标：作为 {pos} 号位（{t_curve_zh or '核心'}）前10分钟仅有 {lh_gain} 刀（经济 +{gold_gain:,}），早期发育直接断档。")
                elif pos == 3:
                    if lh_gain >= 32:
                        good_list.append(f"劣势路占线出色（{t_curve_zh or '三号位'}）：10分钟补刀 {lh_gain}/{dn_gain}，打出 {hd_gain:,} 对线消耗伤害。")
                    else:
                        bad_list.append(f"劣势路混线艰难：10分钟仅 {lh_gain} 补刀（阶段 GPM {gpm_p:.0f}），未能压制敌方优势路大哥。")
                else:
                    # 4/5 号位辅助
                    if kills >= 1 or hd_gain >= 2200:
                        good_list.append(f"线上消耗与游走积极（{t_curve_zh or '辅助'}）：前期打出 {hd_gain:,} 英雄伤害" + (f"，在 {', '.join(kill_times)} 拿人头打开局面。" if kill_times else "，有效压低了敌方血量。"))
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
                    f"前期改进重点（{hmp.get('early_rule') or ('注意 03:00 莲花与 06:00 河道动力符时间点，残血及时补大药别硬拼送人头。' if deaths >= 1 else '保持当前补刀手感，6级后主动呼叫辅助打第一波推进或支援。')}）"
                )

            # 2. 中期运营 (10:00–25:00) 规则诊断
            elif pkey == "mid":
                if pos in (1, 2):
                    if early_farm_ok:
                        good_list.insert(
                            0,
                            f"刷核发育期合理避战（{t_curve_zh}）：前中期弱势期不盲目接劣势团，15分钟内高速刷出 +{gold_gain:,} 金（阶段 GPM {gpm_p:.0f}，补刀 +{lh_gain}）"
                            + (f"，加速成型 {items_str} 为后期出山收割奠定基础。" if items_str else "，为后期出山收割奠定基础。"),
                        )
                    elif gpm_p >= 580:
                        good_list.append(f"中期刷钱效率拉满：15分钟内经济狂涨 +{gold_gain:,}（阶段 GPM {gpm_p:.0f}，补刀 +{lh_gain}）" + (f"，顺利掏出 {items_str}。" if items_str else "。"))
                    elif gpm_p < 420:
                        bad_list.append(f"中期刷钱节奏断档：10~25分钟阶段 GPM 仅有 {gpm_p:.0f}（经济 +{gold_gain:,}），核心装备成型过慢。")
                    if hd_gain >= 8000:
                        good_list.append(f"中期团战火力支柱：单阶段轰出 {hd_gain:,} 英雄伤害并斩获 {kills} 个人头。")
                    elif mid_tempo_bad:
                        bad_list.insert(
                            0,
                            f"中期干架强势期失职（{t_curve_zh}）：10~25m 本该带队抓人逼塔，却当大核闷头刷钱（阶段 +{gold_gain:,} 金仅打 {hd_gain:,} 伤害），白白浪费英雄最强节奏窗！",
                        )
                    elif hd_gain < 4000 and not early_farm_ok:
                        bad_list.append(f"中期打架参与度偏低：15分钟内仅打出 {hd_gain:,} 英雄伤害，队友正面接团时输出存在真空。")
                elif pos == 3:
                    if items_str:
                        good_list.append(f"中期关键先手/团队装成型（{t_curve_zh or '三号位'}）：{items_str}，阶段打出 {hd_gain:,} 伤害与 {kills} 次击杀。")
                    if td_gain >= 1000:
                        good_list.append(f"中期主动带队逼塔，造成 {td_gain:,} 点建筑伤害。")
                else:
                    # 4/5 号位
                    if obs_p + sen_p >= 6:
                        good_list.append(f"中期视野铺设到位：10~25分钟插下 {obs_p} 颗假眼与 {sen_p} 颗真眼，努力支撑团队视野。")
                    if kills >= 2 or hd_gain >= 4500:
                        good_list.append(f"中期接团技能释放果断：阶段贡献 {kills} 杀与 {hd_gain:,} 伤害" + (f"（出装：{items_str}）。" if items_str else "。"))

                if phoenix_audit and phoenix_audit.get("shattered_cnt", 0) >= 2:
                    mid_shatters = [t for t in (phoenix_audit.get("shattered_times") or []) if int(t.split(":")[0]) < 25]
                    if mid_shatters:
                        bad_list.insert(
                            0,
                            f"中期团战大招《超新星》变蛋连续被打碎（{'、'.join(mid_shatters)}），未提前铺满烈火精灵减攻速或卡高坡视野变蛋！",
                        )

                mid_solos = [
                    (f"{s.get('time_str')}(被{s.get('killer','敌方')}单抓)" if isinstance(s, dict) else str(s))
                    for s in solo_picks
                    if 600 <= int(s.get("time", 0) if isinstance(s, dict) else int(str(s).split(":")[0]) * 60) < 1500
                ]
                if mid_solos:
                    bad_list.insert(
                        0,
                        f"中期脱离团队单带无故被抓（{'、'.join(mid_solos)}），直接断送关键装强势期与控图节奏！",
                    )

                if deaths == 0:
                    good_list.append("中期 15 分钟保持 0 阵亡，走位与防抓单警觉性极高！")
                elif deaths >= 4:
                    bad_list.append(f"中期沦为突破口：15分钟内连续暴毙 {deaths} 次（{', '.join(death_times[:4])}），把前期积攒的节奏全送了出去！")
                elif deaths >= 2 and not mid_solos:
                    bad_list.append(f"中期阵亡 {deaths} 次（{', '.join(death_times)}），多次在团战或带线时被抓断节奏。")

                if not good_list:
                    good_list.append(f"中期稳步过渡，经济增量 +{gold_gain:,}，造成 {hd_gain:,} 伤害。")
                if not bad_list:
                    bad_list.append("中期赢下小规模遭遇战后转推外塔或压制敌方野区不够果断。")

                focus_tip = (
                    f"中期改进重点（{hmp.get('mid_rule') or ('第一件关键装到手后必须跟队友抱团打一波信息差，严禁在无视野河道或二塔前孤身带线白给！' if (deaths >= 3 or mid_solos) else '中期大核刷钱时注意看小地图敌方蹲人动向，打赢团第一时间集合拆外塔压野区。')}）"
                )

            # 3. 后期决策 (25:00–终局) 规则诊断
            else:
                if late_harvest_ok:
                    good_list.insert(
                        0,
                        f"大核出山收割完全兑现（{t_curve_zh}）：前中期闭关刷钱成型后，25m+ 决胜期轰出 {hd_gain:,} 英雄伤害（占全队 {pt_meta.get('late_hdmg_share_pct', 25)}%）与 {td_gain:,} 推塔伤害，完美回馈团队空间！",
                    )
                elif hd_gain >= 12000 or kills >= 5:
                    good_list.append(f"后期决战火力全开：单阶段砍下 {kills} 杀、轰出 {hd_gain:,} 英雄伤害" + (f"，更新 {items_str}。" if items_str else "。"))
                if is_turret_ok:
                    good_list.insert(
                        0,
                        f"炮台法核输出职责兑现（{t_curve_zh}）：后期顶着敌方强切入轰出 {hd_gain:,} 英雄伤害（全场每死换出 {full_p.get('dmg_per_death', 3000):,} 伤害），死前把爆发倾泻拉满！",
                    )
                if hmp.get("sacrificial_initiator_fulfilled"):
                    good_list.insert(
                        0,
                        f"前排先手开团与承伤兑现（{t_curve_zh}）：全场贡献 {full_p.get('stuns_sec', 0)} 秒硬控并抗下全队 {full_p.get('damage_taken_share_pct', 0)}% 伤害，果断肉身开团为后排创造输出空间！",
                    )
                if hmp.get("save_support_fulfilled"):
                    good_list.insert(
                        0,
                        f"救人续航辅助职责兑现（{t_curve_zh}）：关键团战倾力提供救人技能与 {full_p.get('hero_healing', 0):,} 点英雄治疗，尽心尽力兜底大哥！",
                    )
                if td_gain >= 3500 and not late_harvest_ok:
                    good_list.append(f"高地拆迁绝对主力：后期独自轰出 {td_gain:,} 点建筑伤害，打赢团战后拆塔破路毫不手软！")
                if pos in (4, 5) and (obs_p + sen_p >= 5 or items_str):
                    good_list.append(f"后期辅助尽职尽责：插下 {obs_p} 假眼 / {sen_p} 真眼" + (f"，做出 {items_str} 保护核心。" if items_str else "。"))

                if slark_audit:
                    late_solos = [
                        (f"{s.get('time_str')}(被{s.get('killer','敌方')}单抓)" if isinstance(s, dict) else str(s))
                        for s in solo_picks
                        if int(s.get("time", 0) if isinstance(s, dict) else int(str(s).split(":")[0]) * 60) >= 1500
                    ]
                    bad_list.insert(
                        0,
                        f"后期机制与输出双重断档：25m+ 吃下全队最高 +{gold_gain:,} 金（占全队 {pt_meta.get('late_gold_share_pct', 26)}%），却仅打出 {hd_gain:,} 伤害（占全队 {pt_meta.get('late_hdmg_share_pct', 15.5)}% 全队倒数第一）；"
                        + ("且整局拒出 1400 金核心魔晶《深海劫掠》（既救不了被抓队友也叠不起被动敏捷导致正面根本 A 不过人）！" if not slark_audit.get("has_shard") else "")
                        + (f" 外加 {'、'.join(late_solos)} 单带无故被抓！" if late_solos else ""),
                    )
                elif phoenix_audit and phoenix_audit.get("shattered_cnt", 0) >= 2:
                    late_shatters = [t for t in (phoenix_audit.get("shattered_times") or []) if int(t.split(":")[0]) >= 25]
                    bad_list.insert(
                        0,
                        f"后期团战大招《超新星》变蛋再次被秒碎（{'、'.join(late_shatters) if late_shatters else '碎蛋率 ' + str(phoenix_audit.get('shatter_rate_pct')) + '%'}），全场仅放 {phoenix_audit.get('sun_ray_casts', 0)} 次《烈日炙烤》激光，后期团战零控制零奶量！",
                    )
                elif late_harvest_fail:
                    bad_list.insert(
                        0,
                        f"后期出山收割断档（{t_curve_zh}）：25m+ 吃下 +{gold_gain:,} 金（占全队 {pt_meta.get('late_gold_share_pct', 22)}%），却仅打出 {hd_gain:,} 伤害（占全队 {pt_meta.get('late_hdmg_share_pct', 15)}%），前中期刷的资源未能转化为决胜团战收割！",
                    )

                if hmp.get("missing_mandatory_shard") and not slark_audit:
                    bad_list.append(
                        f"整局拒出 1400 金质变魔晶（{hmp.get('shard_desc', '核心技能机制加强')}），后期团战少一个关键救人/切入/输出机制！"
                    )

                if deaths == 0:
                    good_list.append("后期决胜阶段 0 阵亡，团战拉扯与切入时机无懈可击！")
                elif deaths >= 3 and not is_turret_ok and not hmp.get("sacrificial_initiator_fulfilled"):
                    bad_list.append(f"后期高价值人头连送 {deaths} 次（{', '.join(death_times[:4])}），后期每一次读秒都直接让队伍少人接团/守高地！")
                elif deaths >= 1 and not slark_audit:
                    bad_list.append(f"后期阵亡 {deaths} 次（{', '.join(death_times)}）" + (f"，并交出 {pp.get('buybacks',0)} 次买活。" if pp.get("buybacks") else "，后期高地/肉山团站位与自保装需更到位。"))

                if pos in (1, 2, 3) and hd_gain < 9000 and not slark_audit and not late_harvest_fail and not hmp.get("sacrificial_initiator_fulfilled"):
                    bad_list.append(f"后期团战输出匮乏：25分钟后吃下 +{gold_gain:,} 金却仅打出 +{hd_gain:,} 英雄伤害，未能承担核心收割职责。")

                if not good_list:
                    good_list.append(f"后期阶段贡献 {kills} 杀、经济 +{gold_gain:,}、英雄伤害 +{hd_gain:,}。")
                if not bad_list:
                    bad_list.append("后期上高地与买活反打阶段需要更严格地盯防敌方先手与买活反扑。")

                if slark_audit:
                    focus_tip = "后期改进重点：小鱼人 20 分钟后必补 1400 金阿哈利姆魔晶《深海劫掠》（救被控制队友+双倍叠敏捷），面对蝴蝶/高闪避核心必补金箍棒/冰眼，后期严禁无视野单带被抓！"
                elif phoenix_audit:
                    focus_tip = "后期改进重点：凤凰变蛋前必须先用《烈火精灵》精准挂上敌方物理核减攻速，并卡高坡/树林视野或出希瓦/刷新球保蛋，拉扯期多开《烈日炙烤》激光！"
                elif is_turret_ok:
                    focus_tip = "后期改进重点：炮台法核输出已拉满，面对先知发芽框人+帕克梦境缠绕务必把隐刀升级为《飓风长戟（大推推）》推开树圈自救！"
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
    from dota_constants_zh import get_ability_zh, ITEMS_ZH

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

    CRITICAL_SAVE_ITEMS: Dict[str, str] = {
        "black_king_bar": "黑皇杖(BKB)",
        "satanic": "撒旦之邪力",
        "manta": "幻影斧(分身)",
        "hurricane_pike": "飓风长戟(大推推)",
        "force_staff": "原力法杖(推推)",
        "glimmer_cape": "微光披风",
        "lotus_orb": "清莲宝珠(莲花)",
        "blade_mail": "刃甲",
        "shivas_guard": "希瓦的守护",
        "crimson_guard": "赤红甲",
        "pipe": "洞察烟斗(笛子)",
        "guardian_greaves": "卫士胫甲(大鞋)",
        "mekansm": "梅肯斯姆",
        "solar_crest": "炎阳纹章",
        "pavise": "长盾",
        "cyclone": "Eul的神圣法杖(吹风)",
        "wind_waker": "风之杖(大吹风)",
        "ghost": "幽灵权杖(绿杖)",
        "ethereal_blade": "虚灵之刃",
        "refresher": "刷新球",
        "sheepstick": "邪镰(羊刀)",
        "orchid": "紫怨",
        "bloodthorn": "血棘",
        "abyssal_blade": "深渊之刃(大晕锤)",
    }
    ITEM_UPGRADE_REPLACES: Dict[str, str] = {
        "force_staff": "hurricane_pike",
        "mekansm": "guardian_greaves",
        "pavise": "solar_crest",
        "cyclone": "wind_waker",
        "ghost": "ethereal_blade",
        "orchid": "bloodthorn",
        "invis_sword": "silver_edge",
    }
    TEAM_SAVE_KEYS = {"glimmer_cape", "force_staff", "lotus_orb", "solar_crest", "pavise", "guardian_greaves", "mekansm", "pipe", "crimson_guard"}
    SELF_SAVE_KEYS = {"black_king_bar", "satanic", "manta", "hurricane_pike", "blade_mail", "cyclone", "wind_waker", "ghost", "ethereal_blade", "refresher", "shivas_guard"}

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

            # 检查开团前 (time <= start_s - 3) 已购入但本波团 0 次按出的保命/救人装
            plog = raw_p.get("purchase_log") or []
            owned_before_tf = {
                str(entry.get("key"))
                for entry in plog
                if isinstance(entry, dict) and int(entry.get("time") or 0) <= start_s - 3
            }
            # 处理合成升级替换
            for base_k, upg_k in ITEM_UPGRADE_REPLACES.items():
                if base_k in owned_before_tf and upg_k in owned_before_tf:
                    owned_before_tf.discard(base_k)

            unused_self_saves: List[str] = []
            unused_team_saves: List[str] = []
            for ik in owned_before_tf:
                if ik not in CRITICAL_SAVE_ITEMS:
                    continue
                used_cnt = int(it_uses.get(ik) or 0)
                # 若合成前后任一键按过也算按出
                upg_k = ITEM_UPGRADE_REPLACES.get(ik)
                if upg_k and int(it_uses.get(upg_k) or 0) > 0:
                    used_cnt += int(it_uses.get(upg_k) or 0)
                if used_cnt == 0:
                    if ik in SELF_SAVE_KEYS and d_cnt > 0:
                        unused_self_saves.append(CRITICAL_SAVE_ITEMS[ik])
                    elif ik in TEAM_SAVE_KEYS and team_deaths >= 2 and (dmg_v > 0 or d_cnt > 0):
                        unused_team_saves.append(CRITICAL_SAVE_ITEMS[ik])

            # 审计核心大招释放与凤凰变蛋
            HERO_ULTIMATE_KEYS: Dict[int, Tuple[str, str]] = {
                1: ("antimage_mana_void", "法力虚空"),
                2: ("axe_culling_blade", "淘汰之刃"),
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
                25: ("lina_laguna_blade", "神灭斩"),
                26: ("lion_finger_of_death", "死亡一指"),
                27: ("shadow_shaman_mass_serpent_ward", "群蛇守卫"),
                29: ("tidehunter_ravage", "毁灭"),
                30: ("witch_doctor_death_ward", "死亡守卫"),
                31: ("lich_chain_frost", "连环霜冻"),
                33: ("enigma_black_hole", "黑洞"),
                36: ("necrolyte_reapers_scythe", "死神镰刀"),
                37: ("warlock_rain_of_chaos", "混乱之雨"),
                38: ("beastmaster_primal_roar", "原始咆哮"),
                39: ("queenofpain_sonic_wave", "超声冲击波"),
                40: ("venomancer_noxious_plague", "恶性瘟疫"),
                41: ("faceless_void_chronosphere", "时间结界"),
                43: ("death_prophet_exorcism", "驱使恶灵"),
                45: ("pugna_life_drain", "生命汲取"),
                48: ("luna_eclipse", "月蚀"),
                50: ("dazzle_shallow_grave", "薄葬"),
                53: ("furion_wrath_of_nature", "自然之怒"),
                55: ("dark_seer_wall_of_replica", "复制之墙"),
                57: ("omniknight_guardian_angel", "守护天使"),
                64: ("jakiro_macropyre", "烈焰焚身"),
                65: ("batrider_flaming_lasso", "燃烧枷锁"),
                68: ("ancient_apparition_ice_blast", "冰晶爆轰"),
                69: ("doom_bringer_doom", "末日"),
                72: ("gyrocopter_call_down", "召唤飞弹"),
                76: ("obsidian_destroyer_sanity_eclipse", "神智之蚀"),
                78: ("brewmaster_primal_split", "元素分离"),
                83: ("treant_overgrowth", "疯狂生长"),
                85: ("undying_tombstone", "墓碑"),
                87: ("disruptor_static_storm", "静态风暴"),
                89: ("naga_siren_song_of_the_siren", "海妖之歌"),
                93: ("slark_shadow_dance", "暗影之舞"),
                94: ("medusa_stone_gaze", "石化凝视"),
                95: ("troll_warlord_battle_trance", "战斗专注"),
                96: ("centaur_stampede", "奔袭冲撞"),
                97: ("magnataur_reverse_polarity", "两极反转"),
                104: ("legion_commander_duel", "决斗"),
                109: ("terrorblade_sunder", "魂断"),
                110: ("phoenix_supernova", "超新星"),
                111: ("oracle_false_promise", "虚妄之诺"),
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
                if egg_cnt > 0 and d_cnt > 0:
                    egg_shattered = True
                    ult_audit_zh = f"💔 开启【超新星】变蛋当场被打碎！（烈火精灵×{spirits_cnt} / 激光×{ray_cnt}）"
                elif egg_cnt > 0 and d_cnt == 0:
                    ult_audit_zh = f"🔥 变蛋【超新星】完美存活眩晕全场！（烈火精灵×{spirits_cnt}）"
                elif egg_cnt == 0 and d_cnt > 0 and start_s >= 420:
                    egg_unpressed = True
                    ult_audit_zh = "💀 团战连大招【超新星】都没按出来即被秒杀！"
            elif hid in HERO_ULTIMATE_KEYS and start_s >= 480:
                u_key, u_zh = HERO_ULTIMATE_KEYS[hid]
                u_cnt = int(ab_uses.get(u_key) or 0)
                # 环轨百戏王还常见放逃生暗箱救人
                if hid == 131:
                    box_cnt = int(ab_uses.get("ringmaster_the_box") or 0)
                    if u_cnt > 0 or box_cnt > 0:
                        ult_audit_zh = f"✓ 关键技能：奇观之轮×{u_cnt} / 逃生暗箱×{box_cnt}"
                    elif d_cnt > 0:
                        ult_unpressed_name = u_zh
                        ult_audit_zh = f"💀 大招【{u_zh}】与【逃生暗箱】0次释放即阵亡"
                else:
                    if u_cnt > 0:
                        ult_audit_zh = f"✓ 已交大招：【{u_zh}×{u_cnt}】"
                    elif d_cnt > 0:
                        ult_unpressed_name = u_zh
                        ult_audit_zh = f"💀 憋大暴毙：大招【{u_zh}】0次释放即阵亡"

            # 检查是否在队友阵亡 >= 2 人时 0 伤害野区独刷
            afk_farm_zh = ""
            is_afk_in_tf = False
            if team_deaths >= 2 and dmg_v == 0 and d_cnt == 0:
                lh_arr = raw_p.get("lh_t") or []
                g_arr = raw_p.get("gold_t") or []
                m0 = max(0, min(len(lh_arr) - 1, start_s // 60)) if lh_arr else 0
                m1 = max(0, min(len(lh_arr) - 1, end_s // 60 + 1)) if lh_arr else 0
                lh_gain_tf = max(0, int(lh_arr[m1] - lh_arr[m0])) if lh_arr and m1 >= m0 else 0
                g_gain_tf = max(0, int(g_arr[m1] - g_arr[m0])) if g_arr and m1 >= m0 else max(0, g_delta)
                tp_cnt_tf = int(it_uses.get("tpscroll") or 0)
                if lh_gain_tf > 0 or g_gain_tf >= 150 or tp_cnt_tf == 0:
                    is_afk_in_tf = True
                    afk_farm_zh = f"🌾 团战0伤害远端独刷（期间补刀 +{lh_gain_tf} 刀 / 进账 +{g_gain_tf} 金 / 0次亮TP支援）"

            # 生成个人本波团定性标签
            if egg_shattered:
                v_tag = "💔 当场碎蛋崩盘"
                v_tone = "bad"
            elif egg_unpressed:
                v_tag = "💀 未变蛋即被秒"
                v_tone = "bad"
            elif unused_self_saves and d_cnt > 0:
                v_tag = f"💀 憋{unused_self_saves[0].split('(')[0]}暴毙"
                v_tone = "bad"
            elif is_afk_in_tf:
                v_tag = "🌾 0伤独刷旁观"
                v_tone = "bad"
            elif ult_unpressed_name and d_cnt > 0:
                v_tag = f"💀 憋大({ult_unpressed_name})死"
                v_tone = "bad"
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
            init_parts.append(f"天辉先手切入：{'、'.join(rad_initiators[:3])}")
        if dire_initiators:
            init_parts.append(f"夜魇先手切入：{'、'.join(dire_initiators[:3])}")
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
            if ve.get("egg_shattered"):
                micro_notes.append("💔 变蛋【超新星】被敌方集火打碎！")
            elif ve.get("egg_unpressed"):
                micro_notes.append("💀 连大招【超新星】都未按出即暴毙！")
            elif ve.get("ult_unpressed_name"):
                micro_notes.append(f"💀 憋大暴毙：招牌【{ve['ult_unpressed_name']}】0次释放！")
            if ve.get("unused_self_saves_zh"):
                micro_notes.append(f"💀 包里揣着【{'/'.join(ve['unused_self_saves_zh'])}】却 0 次按出！")
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
                        f"① 先手掉点成突破口：开团仅 {fb_rel} 秒（{fmt_mmss(fb['time_sec'])}），本方 {fb['victim_pos']}号位 {fb['victim_hero']} 率先被 {fb['killer_hero']} 秒杀，导致正面瞬间陷入 4打5 被动！"
                    )
                else:
                    reasons.append(
                        f"① 先手破局：开团 {fb_rel} 秒（{fmt_mmss(fb['time_sec'])}）即集火秒掉敌方 {fb['victim_pos']}号位 {fb['victim_hero']}，后续{'乘胜追击扩大战果' if (own_gold_swing >= 0 or enemy_throne_fell or enemy_rax_fell) else '恋战深入被敌方反手大招反包'}。"
                    )

            # ② 大招碎蛋 / 憋大 / 憋BKB救人装犯罪点名
            crime_notes = []
            for pe in own_p_exec:
                if pe["egg_shattered"]:
                    crime_notes.append(f"{pe['pos']}号位{pe['hero_short_zh']}开启《超新星》变蛋当场被打碎")
                elif pe["egg_unpressed"]:
                    crime_notes.append(f"{pe['pos']}号位{pe['hero_short_zh']}连大招《超新星》都未按出即被秒")
                elif pe["ult_unpressed_name"]:
                    crime_notes.append(f"{pe['pos']}号位{pe['hero_short_zh']}招牌《{pe['ult_unpressed_name']}》0次释放暴毙")
                if pe["unused_self_saves_zh"]:
                    crime_notes.append(f"{pe['pos']}号位{pe['hero_short_zh']}包里揣着【{'/'.join(pe['unused_self_saves_zh'])}】0次按出暴毙")
                if pe["unused_team_saves_zh"]:
                    crime_notes.append(f"{pe['pos']}号位{pe['hero_short_zh']}未按救人装【{'/'.join(pe['unused_team_saves_zh'])}】")
                if pe["is_afk_in_tf"]:
                    crime_notes.append(f"{pe['pos']}号位{pe['hero_short_zh']}{pe['afk_farm_zh']}")
            if crime_notes:
                reasons.append(f"② 关键机制与微操失误：{'；'.join(crime_notes)}！")
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

    candidate_paths: Dict[str, Path] = {}
    tmp_rdir = Path("/tmp/dota_reports")
    for scan_dir in (rdir, tmp_rdir):
        if scan_dir.exists():
            for mp in scan_dir.glob("match_*.json"):
                candidate_paths[mp.name] = mp

    for mpath in sorted(candidate_paths.values(), key=lambda p: p.name, reverse=True):
        if True:
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
            sorted_contrib = sorted(
                own_list,
                key=lambda x: (float(x.get("contrib_share_pct") or 0), float(x.get("mvp_score") or 0)),
                reverse=True,
            )
            mvp_p = sorted_contrib[0] if sorted_contrib else ((rep.get("mvp") or {}).get("mvp_player") or own_list[0])
            runner_up_p = sorted_contrib[1] if len(sorted_contrib) > 1 else mvp_p
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
                "mvp_contrib_pct": round(float(mvp_p.get("contrib_share_pct") or 25.0), 1),
                "runner_up_hero": runner_up_p.get("hero_short_zh") or "",
                "runner_up_img": runner_up_p.get("hero_img") or "",
                "runner_up_player": runner_up_p.get("personaname") or "",
                "runner_up_contrib_pct": round(float(runner_up_p.get("contrib_share_pct") or 22.0), 1),
                "culprit_hero": culprit_p.get("hero_short_zh") or "",
                "culprit_img": culprit_p.get("hero_img") or "",
                "culprit_player": culprit_p.get("personaname") or "",
                "culprit_blame_pct": round(float(culprit_p.get("blame_share_pct") or 0), 1),
            })

            df_obj = rep.get("deep_forensics") or {}
            unpressed_rows = ((df_obj.get("unpressed_saves_by_side") or {}).get(f_side) or {}).get("player_rows") or []
            unpressed_by_pos = {int(r.get("pos") or 0): r for r in unpressed_rows}
            space_rows = ((df_obj.get("map_space_by_side") or {}).get(f_side) or {}).get("player_space_rows") or []
            space_by_pos = {int(r.get("pos") or 0): r for r in space_rows}
            item_rows = ((df_obj.get("itemization_audit_by_side") or {}).get(f_side) or {}).get("player_item_rows") or []
            item_by_pos = {int(r.get("pos") or 0): r for r in item_rows}

            for p in own_list:
                aid = p.get("account_id")
                pname = p.get("personaname") or "匿名玩家"
                if not aid and pname in ("匿名玩家", "Anonymous"):
                    continue
                pos_p = int(p.get("pos") or 1)
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
                        "unsmoked_blind_total": 0,
                        "bad_builds_total": 0,
                        "heroes": [],
                    },
                )
                st["games"] += 1
                if won:
                    st["wins"] += 1
                st["total_blame_pct"] += float(p.get("blame_share_pct") or 0)
                st["total_contrib_pct"] += float(p.get("contrib_share_pct") or 20.0)
                st["total_rating"] += float(p.get("rating_score") or 60)
                if int(p.get("player_slot", -1)) == int(mvp_p.get("player_slot", -2)):
                    st["mvp_count"] += 1
                if (not won) and int(p.get("player_slot", -1)) == int(culprit_p.get("player_slot", -2)):
                    st["culprit_count"] += 1
                st["total_kills"] += int(p.get("kills") or 0)
                st["total_deaths"] += int(p.get("deaths") or 0)
                st["total_assists"] += int(p.get("assists") or 0)
                st["total_dead_sec"] += int(p.get("dead_seconds") or 0)

                up_r = unpressed_by_pos.get(pos_p) or {}
                st["unpressed_saves_total"] += int(up_r.get("unpressed_core_cnt") or 0)
                sp_r = space_by_pos.get(pos_p) or {}
                st["solo_pickoffs_total"] += int(sp_r.get("solo_pickoff_cnt") or 0)
                st["unsmoked_blind_total"] += int(sp_r.get("unsmoked_blind_cnt") or 0)
                it_r = item_by_pos.get(pos_p) or {}
                if it_r.get("grade") == "bad":
                    st["bad_builds_total"] += 1

                st["heroes"].append({
                    "match_id": mid,
                    "hero_short_zh": p.get("hero_short_zh") or "",
                    "hero_img": p.get("hero_img") or "",
                    "pos": pos_p,
                    "kda": p.get("kda") or "",
                    "rating_score": round(float(p.get("rating_score") or 60.0), 1),
                    "blame_pct": round(float(p.get("blame_share_pct") or 0), 1),
                    "contrib_pct": round(float(p.get("contrib_share_pct") or 20.0), 1),
                    "won": won,
                })

    # 统计边路双人搭档与中野联动化学反应 (1+5 优势路 / 3+4 劣势路 / 2+4 中游联动)
    duo_buckets: Dict[str, Dict[str, Any]] = {}
    if rdir.exists():
        for mpath in sorted(rdir.glob("match_*.json"), reverse=True):
            try:
                rep = json.loads(mpath.read_text(encoding="utf-8"))
            except Exception:
                continue
            f_side = rep.get("focus_side") or "dire"
            own_list = rep.get("radiant_pos_1_to_5") if f_side == "radiant" else rep.get("dire_pos_1_to_5")
            if not own_list or len(own_list) < 5:
                continue
            won = (f_side == "radiant" and bool(rep.get("radiant_win"))) or (
                f_side == "dire" and not bool(rep.get("radiant_win"))
            )
            by_pos = {int(p.get("pos") or 0): p for p in own_list}
            for p_a, p_b, lane_label in [(1, 5, "优势路 1+5"), (3, 4, "劣势路 3+4"), (2, 4, "中野联动 2+4")]:
                pa = by_pos.get(p_a)
                pb = by_pos.get(p_b)
                if not pa or not pb:
                    continue
                na = roster_players.get(str(pa.get("account_id")), {}).get("name") or pa.get("personaname") or ""
                nb = roster_players.get(str(pb.get("account_id")), {}).get("name") or pb.get("personaname") or ""
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
                avg_r_pair = (float(pa.get("rating_score") or 60.0) + float(pb.get("rating_score") or 60.0)) / 2.0
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
        if wr >= 60.0 or avg_r >= 72.0:
            chem_tag = "🔥 黄金搭档 · 默契拉满"
            chem_tone = "good"
        elif wr <= 25.0 and avg_r < 64.0:
            chem_tag = "💣 灾难组合 · 建议拆伙"
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

        # 汇总该队员的个人绝活英雄与冥币英雄
        h_map: Dict[str, Dict[str, Any]] = {}
        for h_item in st["heroes"]:
            hz = h_item["hero_short_zh"]
            hm = h_map.setdefault(hz, {"hero_short_zh": hz, "hero_img": h_item["hero_img"], "games": 0, "wins": 0, "rating_sum": 0.0})
            hm["games"] += 1
            if h_item["won"]:
                hm["wins"] += 1
            hm["rating_sum"] += float(h_item.get("rating_score") or 60.0)
        h_summary = []
        for hm in h_map.values():
            hg = max(1, hm["games"])
            h_summary.append({
                "hero_short_zh": hm["hero_short_zh"],
                "hero_img": hm["hero_img"],
                "games": hm["games"],
                "wins": hm["wins"],
                "win_rate": round(hm["wins"] * 100.0 / hg, 1),
                "avg_rating": round(hm["rating_sum"] / hg, 1),
            })
        h_summary.sort(key=lambda x: (x["win_rate"], x["avg_rating"], x["games"]), reverse=True)
        best_hero = h_summary[0] if h_summary else None
        worst_hero = h_summary[-1] if len(h_summary) >= 2 and h_summary[-1]["avg_rating"] < 62.0 else None

        if st["mvp_count"] >= 1 and avg_contrib >= 22.0:
            role_tag = "👑 车队大腿 · 历史凯瑞王"
            tag_cls = "carry"
        elif st["culprit_count"] >= 1 or avg_blame >= 24.0:
            role_tag = "🚨 败局常客 · 重点分锅对象"
            tag_cls = "culprit"
        elif avg_deaths >= 10.0:
            role_tag = "💀 泉水常客 · 场均十死俱乐部"
            tag_cls = "culprit"
        else:
            role_tag = "⚖️ 车队中坚 · 稳定贡献"
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
            "avg_contrib_pct": avg_contrib,
            "avg_rating": avg_rating,
            "mvp_count": st["mvp_count"],
            "culprit_count": st["culprit_count"],
            "avg_kda": f"{st['total_kills']/g:.1f}/{avg_deaths:.1f}/{st['total_assists']/g:.1f}",
            "avg_dead_sec": avg_dead_sec,
            "unpressed_saves_total": st["unpressed_saves_total"],
            "solo_pickoffs_total": st["solo_pickoffs_total"],
            "unsmoked_blind_total": st["unsmoked_blind_total"],
            "bad_builds_total": st["bad_builds_total"],
            "best_hero": best_hero,
            "worst_hero": worst_hero,
            "role_tag": role_tag,
            "tag_cls": tag_cls,
            "heroes": st["heroes"][:5],
        })

    # 排序：先把主视角、车队好友、多局共同出场的排在前面，再按场均评分降序展示
    squad_members_rank.sort(
        key=lambda x: (1 if (x["is_me"] or x["is_roster_friend"] or x["games"] > 1) else 0, x["games"], x["avg_rating"]),
        reverse=True,
    )

    # 3. 车队历史吉尼斯之最 (Guinness Records)
    core_members = [m for m in squad_members_rank if m["games"] >= 2] or squad_members_rank
    guinness_records = []
    if core_members:
        top_carry = max(core_members, key=lambda x: (x["avg_rating"], x["mvp_count"]))
        guinness_records.append({
            "title": "👑 车队定海神针 (最高场均分)",
            "holder": top_carry["personaname"],
            "value": f"场均 {top_carry['avg_rating']} 分 · {top_carry['mvp_count']} 次首功/MVP",
            "tone": "good",
        })
        top_bkb_holder = max(core_members, key=lambda x: x["unpressed_saves_total"])
        if top_bkb_holder["unpressed_saves_total"] > 0:
            guinness_records.append({
                "title": "💀 憋死 BKB/救命装总冠军",
                "holder": top_bkb_holder["personaname"],
                "value": f"累计 {top_bkb_holder['unpressed_saves_total']} 次身怀救命装0按出暴毙",
                "tone": "bad",
            })
        top_pickoff_holder = max(core_members, key=lambda x: x["solo_pickoffs_total"])
        if top_pickoff_holder["solo_pickoffs_total"] > 0:
            guinness_records.append({
                "title": "🗺️ 孤狼单带迷路被抓王",
                "holder": top_pickoff_holder["personaname"],
                "value": f"累计 {top_pickoff_holder['solo_pickoffs_total']} 次落单被抓 (含 {top_pickoff_holder['unsmoked_blind_total']} 次未开雾白给)",
                "tone": "bad",
            })
        top_build_holder = max(core_members, key=lambda x: x["bad_builds_total"])
        if top_build_holder["bad_builds_total"] > 0:
            guinness_records.append({
                "title": "🎒 头铁出装事故王",
                "holder": top_build_holder["personaname"],
                "value": f"累计 {top_build_holder['bad_builds_total']} 局漏出命脉装/克制装",
                "tone": "warn",
            })
        top_dead_holder = max(core_members, key=lambda x: x["avg_dead_sec"])
        guinness_records.append({
            "title": "⏳ 泉水观光读秒王",
            "holder": top_dead_holder["personaname"],
            "value": f"场均黑屏读秒 {top_dead_holder['avg_dead_sec']} 秒 ({top_dead_holder['avg_kda']})",
            "tone": "warn",
        })

    # 4. 近期 12 场英雄池与组排红黑榜
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
        "guinness_records": guinness_records,
        "lane_duo_chemistry": lane_duo_chemistry[:8],
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



