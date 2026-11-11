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


def build_hero_execution_section(ctx: Dict[str, Any]) -> Dict[str, Any]:
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
        insight_conclusions: List[Dict[str, Any]] = []
        headline_badges: List[Dict[str, str]] = []

        def _add_insight(
            txt: str,
            ev: str,
            source_fields: Optional[List[str]] = None,
            prepend: bool = False,
            insert_at: Optional[int] = None,
        ) -> None:
            c_obj: Dict[str, Any] = {"text": txt, "kind": "hero_execution", "evidence": ev}
            if ev == "measured" and source_fields:
                c_obj["source_fields"] = list(source_fields)
            if prepend:
                special_insights.insert(0, txt)
                insight_conclusions.insert(0, c_obj)
            elif insert_at is not None:
                special_insights.insert(insert_at, txt)
                insight_conclusions.insert(insert_at, c_obj)
            else:
                special_insights.append(txt)
                insight_conclusions.append(c_obj)

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
                elif tfr["deaths"] > 0 and tfr["start_sec"] >= 420 and cfg.get("type") != "single_nuke_ult":
                    # 7分钟后有大招时期在团战阵亡但本波未释放大招（排除斩杀类单点大招）
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

            has_ult_dmg = (ab_key in di and dmg > 0)
            if not has_ult_dmg:
                grade = "neutral"
                if casts > 0:
                    freq_min = round(duration_min / max(1, casts), 1)
                    verdict_text = (
                        f"全场施放 {casts} 次《{cfg['zh']}》（平均每 {freq_min} 分钟 1 次，其中 {len(tf_casts_waves)} 波团战施放），无直接伤害记录，不作伤害次数评级。"
                    )
                    badge_text = f"{cfg['zh']}: 施放{casts}次"
                else:
                    verdict_text = f"整局比赛《{cfg['zh']}》施放记录为 0（无直接伤害记录，不评级）。"
                    badge_text = f"{cfg['zh']}: 0施放"
            elif cfg["type"] == "team_buff_ult":
                # 如白虎群体隐身大、人马奔袭大
                freq_min = round(duration_min / max(1, casts), 1)
                grade = "good" if casts >= max(4, int(duration_min / 3.8)) else "warn"
                verdict_text = (
                    f"全场施放 {casts} 次（平均每 {freq_min} 分钟开大 1 次，每次施放造成 {avg_hits} 次伤害），其中 {len(tf_casts_waves)} 波关键团战开启大招掩护/冲阵。"
                )
                badge_text = f"{cfg['zh']}: {casts}次(每次{avg_hits}次伤害)"
            else:
                if avg_hits >= cfg["good_avg_hits"]:
                    grade = "good"
                    verdict_text = (
                        f"全场施放 {casts} 次《{cfg['zh']}》，每次施放造成 {avg_hits} 次伤害（累计 {hits} 次伤害，造成 {dmg:,} 点伤害）"
                        + (f"，在 {', '.join(tf_casts_waves[:4])} 团战施放" if tf_casts_waves else "")
                        + (f"；主要灌伤目标：{'、'.join(victim_breakdown[:3])}" if victim_breakdown else "")
                        + "。"
                    )
                    badge_text = f"{cfg['zh']}: {casts}放/每次{avg_hits}次伤害"
                elif avg_hits >= cfg["warn_avg_hits"]:
                    grade = "warn"
                    verdict_text = (
                        f"全场施放 {casts} 次《{cfg['zh']}》，每次施放造成 {avg_hits} 次伤害（累计 {hits} 次伤害，伤害 {dmg:,}）"
                        + (f"；在 {', '.join(tf_held_death_waves[:3])} 团战中本波未释放大招。" if tf_held_death_waves else "。")
                    )
                    badge_text = f"{cfg['zh']}: 每次{avg_hits}次伤害"
                else:
                    grade = "bad"
                    verdict_text = (
                        f"全场施放 {casts} 次《{cfg['zh']}》，每次施放造成 {avg_hits} 次伤害（累计 {hits} 次伤害，伤害 {dmg:,}）"
                        + (f"，且在 {', '.join(tf_held_death_waves[:3])} 等 {len(tf_held_death_waves)} 波关键团战中本波未释放大招。" if tf_held_death_waves else "。")
                    )
                    badge_text = f"{cfg['zh']}: {casts}放/每次{avg_hits}次伤害"

            ult_ev = "measured" if (not has_ult_dmg and casts > 0) else "inferred"
            ult_sf = ["players[].ability_uses", "teamfights[].players[].ability_uses"] if ult_ev == "measured" else None
            ult_entry: Dict[str, Any] = {
                "ability_key": ab_key,
                "ability_zh": cfg["zh"],
                "casts": casts,
                "hits": hits,
                "avg_hits": avg_hits,
                "unit_label": "次伤害",
                "damage": dmg,
                "tf_casts_count": len(tf_casts_waves),
                "tf_casts_waves": tf_casts_waves,
                "tf_held_death_count": len(tf_held_death_waves),
                "tf_held_death_waves": tf_held_death_waves,
                "victim_breakdown": victim_breakdown,
                "grade": grade,
                "verdict_text": verdict_text,
                "evidence": ult_ev,
            }
            if ult_sf:
                ult_entry["source_fields"] = ult_sf
            ult_audits.append(ult_entry)
            headline_badges.append({"text": badge_text, "tone": grade})
            _add_insight(verdict_text, ult_ev, ult_sf)

        # 2) 检查核心非指向性/控制小技能每次施放造成伤害次数 (如白虎箭、猛犸拱、屠夫钩、人马踩、莱恩刺、骨法棒子等)
        for ab_key, scfg in SKILLSHOT_CATALOG.items():
            casts = au.get(ab_key, 0)
            if casts <= 0:
                continue
            hits = hh.get(ab_key, 0)
            dmg = di.get(ab_key, 0)
            avg_dmg_hits = round(hits / max(1, casts), 2)
            has_dmg_record = (ab_key in di and dmg > 0)

            if ab_key == "pugna_nether_ward":
                target_dmg_map = dt.get(ab_key) or {}
                zapped = []
                for npc_k, d_val in sorted(target_dmg_map.items(), key=lambda x: int(x[1] or 0), reverse=True):
                    vhid = npc_to_hid.get(npc_k, 0)
                    vp = fmt_by_hid.get(vhid)
                    if vp and vp["side"] != fp["side"] and int(d_val or 0) > 0:
                        zapped.append(f"{vp['hero_short_zh']}({int(d_val):,}血)")
                grade = "neutral" if not has_dmg_record else ("good" if dmg >= 5000 else "warn")
                txt = (
                    f"《幽冥守卫》全场插下 {casts} 根法力棒，每次施放造成 {avg_dmg_hits} 次伤害（累计电击敌方施法者 {hits} 次，轰出 {dmg:,} 点反伤"
                    + (f"，重点目标：{'、'.join(zapped[:3])}）。" if zapped else "）。")
                )
                skillshot_audits.append({
                    "ability_key": ab_key,
                    "ability_zh": scfg["zh"],
                    "casts": casts,
                    "hits": hits,
                    "avg_dmg_hits": avg_dmg_hits,
                    "hit_pct": None,
                    "damage": dmg,
                    "grade": grade,
                    "detail": txt,
                    "evidence": "inferred",
                })
                headline_badges.append({"text": f"幽冥棒: {casts}根/每次{avg_dmg_hits}次伤害({dmg:,}伤)", "tone": grade})
                _add_insight(txt, "inferred")
            else:
                if not has_dmg_record:
                    grade = "neutral"
                    txt = f"《{scfg['zh']}》全场施放 {casts} 次，无直接伤害记录，不作伤害次数评级。"
                    badge_str = f"{scfg['zh'].split(' ')[0]}: 施放{casts}次"
                    ss_ev = "measured"
                    ss_sf: Optional[List[str]] = ["players[].ability_uses"]
                else:
                    good_avg = scfg["good_pct"] / 100.0
                    warn_avg = scfg["warn_pct"] / 100.0
                    grade = "good" if avg_dmg_hits >= good_avg else ("warn" if avg_dmg_hits >= warn_avg else "bad")
                    txt = (
                        f"《{scfg['zh']}》全场施放 {casts} 次，每次施放造成 {avg_dmg_hits} 次伤害（累计造成 {hits} 次伤害，共 {dmg:,} 伤害）。"
                    )
                    badge_str = f"{scfg['zh'].split(' ')[0]}: {casts}放/每次{avg_dmg_hits}次伤害"
                    ss_ev = "inferred"
                    ss_sf = None
                ss_entry: Dict[str, Any] = {
                    "ability_key": ab_key,
                    "ability_zh": scfg["zh"],
                    "casts": casts,
                    "hits": hits,
                    "avg_dmg_hits": avg_dmg_hits,
                    "hit_pct": None,
                    "damage": dmg,
                    "grade": grade,
                    "detail": txt,
                    "evidence": ss_ev,
                }
                if ss_sf:
                    ss_entry["source_fields"] = ss_sf
                skillshot_audits.append(ss_entry)
                headline_badges.append({"text": badge_str, "tone": grade})
                _add_insight(txt, ss_ev, ss_sf)

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
                f"《授予力量》增益覆盖审计：{duration_min:.0f} 分钟比赛共施放 {emp_casts} 次（分均仅 {emp_per_min} 次）"
                + (f"，帮助队友打出 {'、'.join(ally_emp_details)}。" if ally_emp_details else "。")
                + ("⚠️ 作为工具人猛犸，中后期给主C续分裂增益的频率偏低，刷钱与打团前务必保持主C身上常驻分裂！" if emp_tone == "bad" else "")
            )
            _add_insight(emp_msg, "inferred")
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
            _add_insight(pugna_msg, "inferred")

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
            _add_insight(jugg_msg, "inferred")
            headline_badges.append({"text": f"治疗守卫: {ward_casts}根(奶队友{fp.get('hero_healing',0):,})", "tone": "good" if ward_casts >= 10 else "warn"})

        # 3d. 拉比克 (Rubick) 偷到了什么技能、放了几次、砸中几人
        if hid == 86:
            steal_casts = au.get("rubick_spell_steal", 0)
            stolen_used = []
            for k_ab, cnt_ab in sorted(au.items(), key=lambda x: x[1], reverse=True):
                if k_ab.startswith("rubick_") or k_ab in ("ability_capture", "ability_lamp_use", "twin_gate_portal_warp", "plus_high_five", "seasonal_dark_carnival_pie"):
                    continue
                ab_zh = get_ability_zh(k_ab)
                if not ab_zh:
                    continue
                h_ab = hh.get(k_ab, 0)
                d_ab = di.get(k_ab, 0)
                stolen_used.append(
                    f"偷《{ab_zh}》放 {cnt_ab} 次"
                    + (f"({h_ab}次伤害/{d_ab:,}伤)" if (h_ab > 0 or d_ab > 0) else "")
                )
            rub_msg = (
                f"《技能窃取》实战审计：全场大招偷取 {steal_casts} 次，"
                + (f"成功用出的敌方核心技能包括：{'、'.join(stolen_used[:5])}！" if stolen_used else "但偷到后实际放出有效伤害的技能偏少。")
            )
            _add_insight(rub_msg, "inferred")
            headline_badges.append({"text": f"偷技能: {steal_casts}次", "tone": "good" if steal_casts >= 18 else "warn"})

        # 3e. 凤凰 (Phoenix) 超新星变蛋释放统计与烈日炙烤(激光)覆盖率审计（不推断蛋是否被打碎）
        if hid == 110 or au.get("phoenix_supernova", 0) > 0:
            egg_casts = au.get("phoenix_supernova", 0)
            egg_dmg = di.get("phoenix_supernova", 0)
            egg_hits = hh.get("phoenix_supernova", 0)
            ray_casts = au.get("phoenix_sun_ray", 0)
            ray_dmg = di.get("phoenix_sun_ray", 0)
            spirits_casts = au.get("phoenix_fire_spirits", 0)
            dive_casts = au.get("phoenix_icarus_dive", 0)
            total_heal = int(fp.get("hero_healing") or 0)

            egg_tf_waves = []
            egg_held_death_waves = []
            for tfr in tf_list:
                c_egg = int((tfr["ability_uses"] or {}).get("phoenix_supernova", 0))
                if c_egg > 0:
                    egg_tf_waves.append(tfr["time_range"])
                elif tfr["deaths"] > 0 and tfr["start_sec"] >= 420:
                    egg_held_death_waves.append(tfr["time_range"])

            tf_egg_total = len(egg_tf_waves)
            egg_grade = "neutral" if ("phoenix_supernova" not in di or egg_dmg <= 0) else ("good" if egg_casts >= 4 else "warn")
            egg_verdict = (
                f"🥚《超新星(变蛋)》释放记录：全场共释放 {egg_casts} 次（造成 {egg_dmg:,} 伤害），其中在 {tf_egg_total} 波正面团战中释放"
                + (f"（{', '.join(egg_tf_waves)}）" if egg_tf_waves else "")
                + (f"；另有 {len(egg_held_death_waves)} 波团战（{', '.join(egg_held_death_waves[:3])}）本波未释放大招。" if egg_held_death_waves else "。")
            )
            ult_audits.insert(0, {
                "ability_key": "phoenix_supernova",
                "ability_zh": "超新星 (凤凰变蛋)",
                "casts": egg_casts,
                "hits": egg_hits,
                "avg_hits": round(egg_hits / max(1, egg_casts), 2),
                "unit_label": "次伤害跳数",
                "damage": egg_dmg,
                "tf_casts_count": tf_egg_total,
                "tf_casts_waves": egg_tf_waves,
                "tf_held_death_count": len(egg_held_death_waves),
                "tf_held_death_waves": egg_held_death_waves,
                "victim_breakdown": [],
                "grade": egg_grade,
                "verdict_text": egg_verdict,
                "evidence": "inferred",
            })
            headline_badges.insert(0, {
                "text": f"🥚 超新星: {egg_casts}次(团战{tf_egg_total}次)",
                "tone": egg_grade,
            })
            _add_insight(egg_verdict, "inferred", prepend=True)

            ray_grade = "good" if ray_casts >= int(duration_min * 0.45) else "warn"
            ray_msg = (
                f"☀️《烈日炙烤(激光) & 烈火精灵》机制审计：{duration_min:.0f} 分钟比赛开启《烈日炙烤》{ray_casts} 次（造成 {ray_dmg:,} 伤害、全队治疗 {total_heal:,} 点），"
                f"召唤《烈火精灵》{spirits_casts} 次（造成 {di.get('phoenix_fire_spirits', 0):,} 伤害）、《伊卡洛斯之翼》{dive_casts} 次。"
            )
            headline_badges.insert(1, {
                "text": f"烈日炙烤: {ray_casts}次(奶{total_heal:,})",
                "tone": ray_grade,
            })
            _add_insight(ray_msg, "measured", ["players[].ability_uses", "players[].damage_inflictor", "players[].hero_healing"], insert_at=1)
            fp["phoenix_egg_audit"] = {
                "total_casts": egg_casts,
                "tf_egg_total": tf_egg_total,
                "held_death_waves": egg_held_death_waves,
                "sun_ray_casts": ray_casts,
                "sun_ray_dmg": ray_dmg,
                "fire_spirits_casts": spirits_casts,
                "hero_healing": total_heal,
            }

        # 3g. 脆皮高爆发炮台核心 (莉娜/宙斯/天怒/狙击手) 「死前火力倾泻与每死换伤兑现度」审计
        if hid in (25, 22, 101, 35):
            hdmg = int(fp.get("hero_damage") or 0)
            deaths_cnt = max(1, int(fp.get("deaths") or 1))
            dmg_per_death = int(round(hdmg / deaths_cnt))
            team_total_hdmg = max(1, sum(int(x.get("hero_damage") or 0) for x in allies))
            hdmg_share = round(hdmg / team_total_hdmg * 100.0, 1)
            if dmg_per_death >= 3000 or hdmg_share >= 20.0:
                turret_msg = (
                    f"🔥《炮台核心死前灌伤兑现》审计：作为无逃生脆皮炮台，虽然全场阵亡 { int(fp.get('deaths') or 0) } 次，但每次倒下前均把技能与平A倾泻干净——"
                    f"全场轰出 {hdmg:,} 点英雄伤害（占全队 {hdmg_share}%，平均每次阵亡换取 {dmg_per_death:,} 点高额伤害）！"
                )
                headline_badges.insert(0, {"text": f"🔥 炮台换伤: {dmg_per_death:,}伤/死({hdmg_share}%)", "tone": "good"})
                _add_insight(turret_msg, "inferred", prepend=True)

        # 4) 硬控总时长勋章
        if stuns_sec >= 15.0:
            headline_badges.append({
                "text": f"总硬控: {stuns_sec}秒",
                "tone": "good" if stuns_sec >= 40.0 else "warn",
            })
            _add_insight(
                f"全场累计对敌方英雄造成 {stuns_sec} 秒硬控眩晕（平均每分钟控制 {stuns_sec/duration_min:.2f} 秒）。",
                "measured",
                ["players[].stuns", "duration"],
            )

        # 5) 全 126 英雄内置特性与强势期曲线审计 (HERO_PROFILES_126)
        prof126 = get_hero_profile_126(hid, int(fp["pos"]), fp["hero_short_zh"])
        curve126 = prof126.get("timing_curve", "")
        has_shard_any = bool(int(rp.get("aghanims_shard") or 0) or fp.get("aghanims_shard"))
        if prof126.get("shard_desc") and "必出" in prof126.get("shard_desc", "") and duration_min >= 25 and not has_shard_any:
            headline_badges.insert(0, {"text": f"🚫 {duration_min:.0f}m未出命脉魔晶!", "tone": "bad"})
            _add_insight(
                f"🚨 专属魔晶缺失：打到 {duration_min:.0f} 分钟仍未购买该英雄质变魔晶【{prof126['shard_desc']}】！",
                "inferred",
                prepend=True,
            )

        # 补充全英雄招牌主动技能释放与命中统计
        top_abs = [
            (k, v) for k, v in sorted(au.items(), key=lambda x: x[1], reverse=True)
            if get_ability_zh(k)
        ][:3]
        if top_abs:
            parts = [
                f"《{get_ability_zh(k)}》×{v}"
                + (f"({hh.get(k,0)}次伤害/{di.get(k,0):,}伤)" if (hh.get(k, 0) > 0 or di.get(k, 0) > 0) else "")
                for k, v in top_abs
            ]
            role_tag = (prof126.get("roles") or ["核心机制"])[0]
            if not special_insights:
                _add_insight(
                    f"【{role_tag}】招牌技能兑现：" + "；".join(parts) + "。",
                    "measured",
                    ["players[].ability_uses", "players[].hero_hits", "players[].damage_inflictor"],
                )
            elif len(special_insights) < 3:
                _add_insight(
                    f"【英雄定位：{role_tag}】技能释放：" + "、".join(parts) + "。",
                    "measured",
                    ["players[].ability_uses", "players[].hero_hits", "players[].damage_inflictor"],
                )

        trimmed_conclusions = insight_conclusions[:4]
        has_inferred_exec = any(c.get("evidence") == "inferred" for c in trimmed_conclusions) or any(
            x.get("evidence") == "inferred" for x in (ult_audits + skillshot_audits)
        )
        res: Dict[str, Any] = {
            "pos": fp["pos"],
            "player_slot": pslot,
            "side": side_key,
            "hero_id": hid,
            "hero_short_zh": fp["hero_short_zh"],
            "hero_img": fp["hero_img"],
            "personaname": fp["personaname"],
            "timing_curve": curve126,
            "hero_roles": prof126.get("roles", []),
            "stuns_sec": stuns_sec,
            "ult_audits": ult_audits,
            "skillshot_audits": skillshot_audits,
            "headline_badges": headline_badges[:4],
            "special_insights": special_insights[:4],
            "conclusions": trimmed_conclusions,
            "evidence": "inferred" if has_inferred_exec else "measured",
        }
        if res["evidence"] == "measured":
            res["source_fields"] = ["players[].ability_uses", "players[].hero_hits", "players[].damage_inflictor", "players[].stuns"]
        fp["hero_execution_audit"] = res
        return res

    all_hero_exec = [analyze_player_hero_execution(p) for p in all_formatted]

    return {
        "hero_execution_by_side": {
            "dire": [x for x in all_hero_exec if x["side"] == "dire"],
            "radiant": [x for x in all_hero_exec if x["side"] == "radiant"],
        },
    }
