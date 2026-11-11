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


def build_laning_tp_saves_sections(ctx: Dict[str, Any]) -> Dict[str, Any]:
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
                f"而敌方抢下了 {opp_lotus_total} 朵莲花（{'、'.join(opp_lotus_breakdown)}）！3分钟 / 6分钟 / 9分钟整点莲花池争夺吃亏。"
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
            wisdom_verdict = f"⚠️ 智慧经验符落后：本方仅吃到 {own_wisdom_cnt} 颗经验符 vs 敌方吃到 {opp_wisdom_cnt} 颗！7分钟与14分钟必须提前 15 秒去劣势路祭坛蹲守经验符。"

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

        # 预先提取每位玩家的阵亡读秒时间窗 (dt, dt + time_dead)
        death_windows_by_slot: Dict[int, List[Tuple[int, int]]] = {}
        for fp_w in own_players:
            ps_w = int(fp_w["player_slot"])
            rp_w = raw_by_slot.get(ps_w, {})
            wins_w: List[Tuple[int, int]] = []
            for d_ev in rp_w.get("deaths_log") or []:
                if isinstance(d_ev, dict):
                    dt_v = int(d_ev.get("time") or 0)
                    td_v = int(d_ev.get("time_dead") or 30)
                    wins_w.append((dt_v, dt_v + td_v))
            death_windows_by_slot[ps_w] = wins_w

        # 逐波团战检查：谁使用了 TP，谁在我方死人的团战里全程无参战记录
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
                heal_val = int(tp_obj.get("healing") or 0)
                ab_used = tp_obj.get("ability_uses") or {}
                it_used = tp_obj.get("item_uses") or {}
                tp_in_tf = int(it_used.get("tpscroll") or 0) + int(it_used.get("travel_boots") or 0) + int(it_used.get("travel_boots_2") or 0)
                was_dead_at_start = any(dt <= s_sec < respawn_t for dt, respawn_t in death_windows_by_slot.get(pslot, []))

                if d_cnt > 0:
                    own_deaths_heroes.append(fp["hero_short_zh"])
                if tp_in_tf > 0 and (dmg_val > 0 or len(ab_used) > 0 or d_cnt > 0 or heal_val > 0):
                    tp_responders.append(f"{fp['hero_short_zh']}({fp['personaname']})")
                    tp_saviors_objs.append({
                        "pos": fp["pos"],
                        "hero_short_zh": fp["hero_short_zh"],
                        "personaname": fp["personaname"],
                        "damage": dmg_val,
                    })
                elif (
                    not was_dead_at_start
                    and d_cnt == 0
                    and dmg_val == 0
                    and heal_val == 0
                    and len(ab_used) == 0
                    and tp_in_tf == 0
                ):
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
                    "detail": f"在 {t_range} 交战中，{'、'.join(tp_responders)} 本波使用了 TP（该波 {opp_deaths_cnt} 换 {len(own_deaths_heroes)}）。",
                })

            # 如果本波我方死了至少 2 人，且有存活队友无伤害/技能/治疗/TP记录
            if len(own_deaths_heroes) >= 2 and spectators and s_sec >= 360:
                spec_names = "、".join(f"{sp['pos']}号位{sp['hero_short_zh']}" for sp in spectators)
                absent_warnings.append({
                    "time_range": t_range,
                    "victims": "、".join(own_deaths_heroes),
                    "spectators": spec_names,
                    "evidence": "inferred",
                    "detail": f"⚠️ {t_range} 我方【{'、'.join(own_deaths_heroes)}】阵亡时，{spec_names} 本波无英雄伤害、无技能/治疗记录且未使用 TP（推断未参战）。",
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
            p_death_wins = death_windows_by_slot.get(pslot, [])

            tf_tp_cnt = 0
            tf_tp_times: List[str] = []
            tf_joined_cnt = 0
            tf_absent_cnt = 0
            tf_absent_times: List[str] = []
            for tfr in tfs_for_p:
                own_d = tfr["rad_deaths"] if is_rad else tfr["dire_deaths"]
                it_u = tfr["item_uses"] or {}
                ab_u_tf = tfr.get("ability_uses") or {}
                heal_tf = int(tfr.get("healing") or 0)
                has_tp = (int(it_u.get("tpscroll") or 0) + int(it_u.get("travel_boots") or 0) + int(it_u.get("travel_boots_2") or 0)) > 0
                was_dead_tf = any(dt <= tfr["start_sec"] < respawn_t for dt, respawn_t in p_death_wins)
                participated = (tfr["damage"] > 0 or tfr["deaths"] > 0 or has_tp or heal_tf > 0 or len(ab_u_tf) > 0)
                if has_tp:
                    tf_tp_cnt += 1
                    tf_tp_times.append(fmt_mmss(tfr["start_sec"]))
                if participated:
                    tf_joined_cnt += 1
                elif not was_dead_tf and own_d >= 2 and tfr["start_sec"] >= 360:
                    tf_absent_cnt += 1
                    tf_absent_times.append(fmt_mmss(tfr["start_sec"]))

            total_tf_tp_saves += tf_tp_cnt
            if tp_bought == 0:
                zero_buy_heroes.append(f"{fp['pos']}号位{fp['hero_short_zh']}")

            # 检测「买TP后45秒内阵亡」
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
                verdict = f"全场使用 {tp_used} 次 TP，其中 {tf_tp_cnt} 波团战（{'、'.join(tf_tp_times)}）本波使用了 TP，参团率 {fp.get('kill_participation_pct')}%。"
            elif tp_used <= max(4, int(duration_min / 6.5)):
                grade = "bad"
                verdict = (
                    f"⚠️ TP 使用频次偏低：{duration_min:.0f} 分钟使用 {tp_used} 次 TP（主动买 {tp_bought} 张，团战使用 TP {tf_tp_cnt} 次），"
                    + (f"在 {tf_absent_cnt} 波队友阵亡的团战中无参战记录。" if tf_absent_cnt > 0 else "。")
                )
            elif tp_bought == 0 and deaths_total >= 6:
                grade = "warn"
                verdict = (
                    f"全场阵亡 {deaths_total} 次、主动购买 TP 0 张（共使用 {tp_used} 次，团战使用 TP {tf_tp_cnt} 次），"
                    f"连续存活刷钱时注意检查背包是否断 TP。"
                )
            elif tf_absent_cnt >= 2:
                grade = "warn"
                verdict = f"全场使用 {tp_used} 次 TP（团战使用 TP {tf_tp_cnt} 次），在 {tf_absent_cnt} 波队友多人阵亡的团战（{'、'.join(tf_absent_times)}）中无伤害/技能/TP记录。"
            else:
                grade = "good" if tf_absent_cnt == 0 else "warn"
                verdict = (
                    f"全场使用 {tp_used} 次 TP（主动购买 {tp_bought} 张，团战使用 TP {tf_tp_cnt} 次），参战 {tf_joined_cnt}/{len(tfs_for_p)} 波关键团"
                    + (f"（无记录波次 {'、'.join(tf_absent_times)}）" if tf_absent_times else "")
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
    # 六、团战内主动保命装持有与使用记录 (Active Save Items In Teamfight Deaths)
    # =========================================================================
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
            owned_save_times = get_held_active_save_items(plog, duration_sec + 60)

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

                held_at_tf = get_held_active_save_items(plog, s_sec - 3)
                unpressed_crit_zh: List[str] = []
                for ik, buy_t in held_at_tf.items():
                    if buy_t <= s_sec - 3 and int(it_u.get(ik) or 0) == 0:
                        unpressed_crit_zh.append(ACTIVE_SAVE_ITEMS_ZH[ik])

                is_zero_spell = (s_sec >= 480 and len(ab_u) == 0)
                if is_zero_spell:
                    zero_spell_cnt += 1
                    zero_spell_total += 1

                if unpressed_crit_zh:
                    unpressed_core_cnt += 1
                    critical_total += 1

                if unpressed_crit_zh or is_zero_spell:
                    severity = "warn"
                    parts = []
                    if unpressed_crit_zh:
                        parts.append(f"阵亡时持有【{' / '.join(unpressed_crit_zh)}】，本波未使用")
                    if is_zero_spell:
                        parts.append(f"本波团战无技能释放记录（打出 {dmg_val} 点伤害）")
                    desc = "；".join(parts)
                    p_incidents.append(f"{fmt_mmss(s_sec)} {desc}")
                    incidents.append({
                        "time_range": t_range,
                        "start_sec": s_sec,
                        "pos": int(fp["pos"]),
                        "hero_short_zh": fp["hero_short_zh"],
                        "hero_img": fp["hero_img"],
                        "personaname": fp["personaname"],
                        "unpressed_items": unpressed_crit_zh,
                        "zero_abilities": is_zero_spell,
                        "tf_damage": dmg_val,
                        "severity": severity,
                        "evidence": "inferred",
                        "detail": f"[{t_range}] {fp['pos']}号位 {fp['hero_short_zh']}：{desc}（推断：无法确认当时冷却与受控状态）。",
                    })

            # 统计整局主动保命装总按键次数
            iu_all = rp.get("item_uses") or {}
            owned_summary = []
            for ik, buy_t in owned_save_times.items():
                zh_label = ACTIVE_SAVE_ITEMS_ZH[ik]
                owned_summary.append(f"{zh_label}({fmt_mmss(buy_t)}出·按{int(iu_all.get(ik) or 0)}次)")

            if unpressed_core_cnt == 0 and zero_spell_cnt == 0:
                grade = "good"
                verdict = (
                    f"✓ 本局 {tf_deaths} 次团战阵亡中，已持有的主动保命装与核心技能均有使用记录。"
                    if tf_deaths > 0
                    else "✓ 全局关键团战无阵亡记录。"
                )
            else:
                grade = "warn"
                verdict = (
                    f"ℹ️ 记录到 {unpressed_core_cnt} 次团战阵亡时持有主动保命装本波未使用、{zero_spell_cnt} 次团战无技能释放记录："
                    + "；".join(p_incidents[:3])
                )

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
                "evidence": "inferred",
                "verdict": verdict,
            })

        incidents.sort(key=lambda x: x["start_sec"])
        if critical_total == 0 and zero_spell_total == 0:
            side_verdict = "✓ 全队团战技能与主动保命装均有释放记录。"
        else:
            side_verdict = (
                f"ℹ️ 团战记录：全队共 {critical_total} 人次团战阵亡时持有主动保命装本波未使用、"
                f"{zero_spell_total} 人次中后期团战无技能释放记录（推断，未计入评分与责任占比）。"
            )

        return {
            "side": side_key,
            "side_verdict": side_verdict,
            "critical_total": critical_total,
            "zero_spell_total": zero_spell_total,
            "incidents": incidents[:10],
            "player_rows": player_rows,
        }

    return {
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
    }
