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


def build_space_damage_econ_sections(ctx: Dict[str, Any]) -> Dict[str, Any]:
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
    # 七、地图空间理解与「大哥带无聊危险线 / 落单乱逛被抓死」空间取证 (Map Space & Solo Pickoffs)
    # =========================================================================
    raw_objectives = match.get("objectives") or []

    def analyze_side_map_space_and_pickoffs(side_key: str) -> Dict[str, Any]:
        own_players = radiant_players if side_key == "radiant" else dire_players
        opp_players = dire_players if side_key == "radiant" else radiant_players
        is_rad = (side_key == "radiant")

        # 收集我方整局假眼存活区间与坐标（优先按 ehandle 精确匹配），用于判断死的时候是不是黑图盲区
        own_obs_wards: List[Dict[str, Any]] = []
        for fp in own_players:
            rp = raw_by_slot.get(int(fp["player_slot"]), {})
            obs_l = rp.get("obs_log") or []
            left_l = rp.get("obs_left_log") or []
            for idx_w, w in enumerate(obs_l):
                t_in = int(w.get("time") or 0)
                w_eh = w.get("ehandle")
                w_key = w.get("key")
                matched_ol = []
                if w_eh is not None:
                    matched_ol = [ol for ol in left_l if ol.get("ehandle") == w_eh and int(ol.get("time") or 0) >= t_in]
                if not matched_ol:
                    matched_ol = [ol for ol in left_l if ol.get("key") == w_key and int(ol.get("time") or 0) >= t_in]
                if matched_ol:
                    t_out = int(matched_ol[0].get("time") or (t_in + 360))
                else:
                    t_out = int(left_l[idx_w].get("time") or (t_in + 360)) if idx_w < len(left_l) else (t_in + 360)
                own_obs_wards.append({
                    "x": float(w.get("x") or 128),
                    "y": float(w.get("y") or 128),
                    "t_in": t_in,
                    "t_out": t_out,
                })

        # 从敌方 kills_log 的 smoke 字段和团战 item_uses.smoke_of_deceit 读取真实破雾击杀记录（不用购买时间推断）
        opp_smoke_kill_times: List[int] = []
        for op in opp_players:
            orp = raw_by_slot.get(int(op["player_slot"]), {})
            for ke in orp.get("kills_log") or []:
                if isinstance(ke, dict) and ke.get("smoke"):
                    opp_smoke_kill_times.append(int(ke.get("time") or 0))
        for tf in raw_tfs:
            tf_pl = tf.get("players") or []
            opp_range = range(5, 10) if is_rad else range(0, 5)
            for j in opp_range:
                if j < len(tf_pl) and int((tf_pl[j].get("item_uses") or {}).get("smoke_of_deceit") or 0) > 0:
                    opp_smoke_kill_times.append(int(tf.get("start") or 0))

        solo_pickoff_events: List[Dict[str, Any]] = []
        player_space_rows: List[Dict[str, Any]] = []
        total_solo_pickoffs = 0
        total_unsmoked_blind_feeds = 0
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
            p_unsmoked_cnt = 0
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
                death_zone_zh: Optional[str] = None
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
                            p_deep_death_cnt += 1

                    if own_d == 1 and opp_d == 0 and zero_dmg_allies >= 3:
                        is_solo_pickoff = True

                if is_solo_pickoff:
                    p_solo_cnt += 1
                    total_solo_pickoffs += 1
                    p_solo_gold_fed += gold_fed

                    is_enemy_smoke_gank = any(abs(t_sec - st) <= 15 for st in opp_smoke_kill_times)
                    gank_nature_tag = "🌫️ 敌方破雾击杀" if is_enemy_smoke_gank else "非团战期单人阵亡"
                    vision_tag = "🌫️ 敌方诡计之雾击杀" if is_enemy_smoke_gank else ""

                    # 死后 70 秒内的地图事件（并列陈述事实，不作因果断言）
                    consequence_list = []
                    for obj in raw_objectives:
                        ot = int(obj.get("time") or 0)
                        if t_sec <= ot <= t_sec + 70:
                            otype = str(obj.get("type") or "")
                            okey = str(obj.get("key") or "")
                            if otype == "CHAT_MESSAGE_ROSHAN_KILL":
                                oteam = int(obj.get("team") or 0)
                                if (is_rad and oteam == 3) or ((not is_rad) and oteam == 2):
                                    consequence_list.append(f"{fmt_mmss(ot)} 敌方控下肉山盾")
                            elif otype == "building_kill":
                                if (is_rad and "goodguys" in okey) or ((not is_rad) and "badguys" in okey):
                                    b_zh = "高地塔/兵营" if ("3" in okey or "rax" in okey) else "外塔"
                                    consequence_list.append(f"{fmt_mmss(ot)} 本方损失{b_zh}")

                    conseq_str = (
                        f"；随后 70 秒内：{'、'.join(consequence_list[:2])}。"
                        if consequence_list
                        else "。"
                    )
                    zone_clause = f"在【{death_zone_zh}】" if death_zone_zh else ""
                    smoke_clause = f"（{vision_tag}）" if vision_tag else ""
                    detail_txt = (
                        f"[{fmt_mmss(t_sec)}] {pos_i}号位 {fp['hero_short_zh']} {zone_clause}被 {killer_zh} 击杀{smoke_clause}"
                        f"（读秒 {dead_s}s · 损失 {gold_fed} 金）{conseq_str}"
                    )
                    p_pickoff_details.append(f"{fmt_mmss(t_sec)}(被{killer_zh}击杀)")
                    solo_pickoff_events.append({
                        "time_str": fmt_mmss(t_sec),
                        "time_sec": t_sec,
                        "pos": pos_i,
                        "hero_short_zh": fp["hero_short_zh"],
                        "hero_img": fp["hero_img"],
                        "personaname": fp["personaname"],
                        "zone_zh": death_zone_zh,
                        "killer_zh": killer_zh,
                        "is_enemy_smoke_gank": is_enemy_smoke_gank,
                        "gank_nature_tag": gank_nature_tag,
                        "vision_tag": vision_tag,
                        "gold_fed": gold_fed,
                        "time_dead": dead_s,
                        "consequence": "、".join(consequence_list[:2]) if consequence_list else "",
                        "detail": detail_txt,
                    })

            # 判定该选手的「地图空间理解画像」（结合英雄内置强势期曲线 timing_curve）
            is_core = pos_i in (1, 2, 3)
            prof_space = get_hero_profile_126(int(fp.get("hero_id") or 0), pos_i, fp["hero_short_zh"])
            is_hyper_carry = prof_space.get("timing_curve") == "late_hyper_carry"
            hdmg_share_val = float(fp.get("hero_damage_share_pct") or 0.0)
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
            elif is_core and is_hyper_carry and jungle_farm_pct >= 52.0 and hdmg_share_val >= 22.0 and p_solo_cnt <= 1:
                style_badge = "🌾➡️⚔️ 大核闭关成型·出山收割"
                grade = "good"
                verdict = (
                    f"✓ 符合【{fp['hero_short_zh']}】后期大核特性的空间分配：前中期避开无效乱战高效收野（野区 {neutral_kills} / 兵线 {lane_kills}），"
                    f"核心装成型后出山轰出全队 {hdmg_share_val:.1f}% 英雄伤害且仅 {p_solo_cnt} 次落单被抓，完美兑现『前期避战刷钱 -> 后期接管收割』！"
                )
            elif is_core and jungle_farm_pct >= 58.0 and tower_dmg < 1800 and kp_pct < 55.0:
                style_badge = "📉 大核刷野未兑现收割" if is_hyper_carry else "🧛 缩壳野区吸血鬼"
                grade = "warn"
                verdict = (
                    f"⚠️ {'身为后期大核前中期钻野发育合理，但出山后未能将经济转化为收割与推塔' if is_hyper_carry else '地图空间利用偏消极'}：野区补刀占 {jungle_farm_pct}%（{neutral_kills}野 vs {lane_kills}线），"
                    f"推塔 {tower_dmg}，参战率仅有 {kp_pct}%。"
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
                "unsmoked_blind_cnt": p_unsmoked_cnt,
                "solo_gold_fed": p_solo_gold_fed,
                "deep_death_cnt": p_deep_death_cnt,
                "space_style_badge": style_badge,
                "grade": grade,
                "verdict": verdict,
            })

        solo_pickoff_events.sort(key=lambda x: x["time_sec"])
        if total_solo_pickoffs <= 3:
            side_verdict = (
                f"✓ 团队地图空间记录：9 分钟后全队共发生 {total_solo_pickoffs} 次非团战单人阵亡，"
                f"收线与抱团衔接较紧凑。"
            )
        else:
            side_verdict = (
                f"⚠️ 地图空间记录：9 分钟后全队共发生 {total_solo_pickoffs} 次非团战单人阵亡。"
            )

        return {
            "side": side_key,
            "side_verdict": side_verdict,
            "total_solo_pickoffs": total_solo_pickoffs,
            "total_unsmoked_blind_feeds": total_unsmoked_blind_feeds,
            "solo_pickoff_events": solo_pickoff_events[:12],
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
            lane_g = max(0, int(gr.get(GOLD_REASON_KEYS["lane_creep"]) or 0))
            jungle_g = max(0, int(gr.get(GOLD_REASON_KEYS["neutral_creep"]) or 0))
            kill_g = max(0, int(gr.get(GOLD_REASON_KEYS["hero_kill"]) or 0))
            obj_g = (
                max(0, int(gr.get(GOLD_REASON_KEYS["building"]) or 0))
                + max(0, int(gr.get(GOLD_REASON_KEYS["roshan"]) or 0))
            )
            bounty_ward_g = (
                max(0, int(gr.get(GOLD_REASON_KEYS["courier"]) or 0))
                + max(0, int(gr.get(GOLD_REASON_KEYS["bounty_rune"]) or 0))
                + max(0, int(gr.get(GOLD_REASON_KEYS["ward_kill"]) or 0))
            )
            death_loss = abs(int(gr.get(GOLD_REASON_KEYS["death_loss"]) or 0))
            buyback_loss = abs(min(0, int(gr.get(GOLD_REASON_KEYS["buyback"]) or 0)))

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

    return {
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
    }
