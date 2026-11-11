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


def build_snapshots_matchups_objectives_sections(ctx: Dict[str, Any]) -> Dict[str, Any]:
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
    # 十、0:00 ~ 终局逐分钟时空回放器快照 (Minute-by-Minute Interactive Scrubber)
    # =========================================================================
    def build_minute_snapshots() -> Dict[str, Any]:
        r_gold_adv = match.get("radiant_gold_adv") or []
        r_xp_adv = match.get("radiant_xp_adv") or []
        max_idx = len(r_gold_adv)
        if max_idx == 0:
            for rp in raw_players_list:
                t_arr = rp.get("times") or []
                if len(t_arr) > max_idx:
                    max_idx = len(t_arr)
        if max_idx == 0:
            return {
                "format": "columnar_v1",
                "minutes": [],
                "radiant_gold_adv": [],
                "radiant_xp_adv": [],
                "events": [],
                "item_zh_map": {},
                "players": [],
            }

        # 预先整理每位玩家的最近购买记录（最近 6 次购买，非消耗品）
        SKIP_CONSUMABLES = {
            "tpscroll", "ward_observer", "ward_sentry", "smoke_of_deceit", "dust",
            "clarity", "faerie_fire", "enchanted_mango", "tango", "flask", "blood_grenade",
            "branches", "magic_stick", "sobi_mask", "ring_of_protection", "quelling_blade",
        }
        player_core_purchases: Dict[int, List[Dict[str, Any]]] = {}
        item_zh_map: Dict[str, str] = {}
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
                zh_val = ITEMS_ZH.get(ik, ik)
                item_zh_map[ik] = zh_val
                core_list.append({
                    "key": ik,
                    "zh": zh_val,
                    "time": int(entry.get("time") or 0),
                })
            player_core_purchases[pslot] = core_list

        minutes_col = list(range(max_idx))
        g_adv_col = [int(r_gold_adv[m]) if m < len(r_gold_adv) else 0 for m in range(max_idx)]
        x_adv_col = [int(r_xp_adv[m]) if m < len(r_xp_adv) else 0 for m in range(max_idx)]
        events_col: List[List[str]] = [[] for _ in range(max_idx)]

        players_col: List[Dict[str, Any]] = []
        for fp in all_formatted:
            pslot = int(fp["player_slot"])
            rp = raw_by_slot.get(pslot, {})
            nw_arr = rp.get("networth_t") or rp.get("gold_t") or []
            lh_arr = rp.get("lh_t") or []
            dn_arr = rp.get("dn_t") or []
            xp_arr = rp.get("xp_t") or []
            hdmg_arr = rp.get("hero_damage_t") or []
            tdmg_arr = rp.get("tower_damage_t") or []

            h_img = str(fp.get("hero_img") or "")
            h_key = str(fp.get("hero_key") or "")
            if not h_key and "/heroes/" in h_img:
                h_key = h_img.rsplit("/heroes/", 1)[-1].replace("icons/", "").split(".png")[0]

            nw_series: List[int] = []
            lh_series: List[int] = []
            dn_series: List[int] = []
            xp_series: List[int] = []
            hdmg_series: List[int] = []
            tdmg_series: List[int] = []
            dead_series: List[Any] = []
            rec_purchases_compact = [
                {"key": it["key"], "t": it["time"]}
                for it in player_core_purchases.get(pslot, [])
            ]

            p_deaths_log = rp.get("deaths_log") or []
            p_kills_log = rp.get("kills_log") or []

            for m in range(max_idx):
                sec_cutoff = m * 60
                sec_prev = (m - 1) * 60
                nw_val = int(nw_arr[m]) if m < len(nw_arr) else int(fp.get("net_worth") or 0)
                lh_val = int(lh_arr[m]) if m < len(lh_arr) else int(fp.get("last_hits") or 0)
                dn_val = int(dn_arr[m]) if m < len(dn_arr) else int(fp.get("denies") or 0)
                xp_val = int(xp_arr[m]) if m < len(xp_arr) else 0
                hdmg_val = int(hdmg_arr[m]) if m < len(hdmg_arr) else (int(fp.get("hero_damage") or 0) if m == max_idx - 1 else 0)
                tdmg_val = int(tdmg_arr[m]) if m < len(tdmg_arr) else (int(fp.get("tower_damage") or 0) if m == max_idx - 1 else 0)

                for d_ev in p_deaths_log:
                    dt = int(d_ev.get("time") or 0)
                    t_dead = int(d_ev.get("time_dead") or 25)
                    if (dt <= sec_cutoff <= dt + t_dead) or (m > 0 and sec_prev < dt <= sec_cutoff):
                        k_hid = npc_to_hid.get(str(d_ev.get("key") or ""), 0)
                        k_fp = fmt_by_hid.get(k_hid)
                        k_zh = k_fp["hero_short_zh"] if k_fp else str(d_ev.get("key") or "").replace("npc_dota_hero_", "")
                        rem_s = max(0, (dt + t_dead) - sec_cutoff) if dt <= sec_cutoff <= dt + t_dead else t_dead
                        dead_series.append([
                            m,
                            1 if (dt <= sec_cutoff <= dt + t_dead) else 0,
                            fmt_mmss(dt),
                            t_dead,
                            rem_s,
                            int(d_ev.get("gold_lost") or 0),
                            int(d_ev.get("gold_fed") or 0),
                            k_zh or "敌方",
                        ])
                        break

                nw_series.append(nw_val)
                lh_series.append(lh_val)
                dn_series.append(dn_val)
                xp_series.append(xp_val)
                hdmg_series.append(hdmg_val)
                tdmg_series.append(tdmg_val)

                if m > 0:
                    for k_ev in p_kills_log:
                        kt = int(k_ev.get("time") or 0)
                        if sec_prev < kt <= sec_cutoff:
                            v_hid = npc_to_hid.get(str(k_ev.get("key") or ""), 0)
                            v_fp = fmt_by_hid.get(v_hid)
                            v_zh = v_fp["hero_short_zh"] if v_fp else "敌方英雄"
                            if len(events_col[m]) < 6:
                                events_col[m].append(f"⚔️ {fmt_mmss(kt)} {fp['hero_short_zh']} 击杀 {v_zh}")

            players_col.append({
                "slot": pslot,
                "side": "radiant" if pslot < 128 else "dire",
                "pos": int(fp["pos"]),
                "hero_key": h_key,
                "hero_short_zh": fp["hero_short_zh"],
                "personaname": fp["personaname"],
                "networth": nw_series,
                "lh": lh_series,
                "dn": dn_series,
                "xp": xp_series,
                "hero_damage": hdmg_series,
                "tower_damage": tdmg_series,
                "dead_status": dead_series,
                "recent_purchases": rec_purchases_compact,
            })

        for m in range(1, max_idx):
            sec_cutoff = m * 60
            sec_prev = (m - 1) * 60
            for obj in raw_objectives:
                ot = int(obj.get("time") or 0)
                if sec_prev < ot <= sec_cutoff and len(events_col[m]) < 6:
                    otype = str(obj.get("type") or "")
                    if otype == "CHAT_MESSAGE_ROSHAN_KILL":
                        events_col[m].append(f"🐉 {fmt_mmss(ot)} 肉山被击杀")
                    elif otype == "building_kill":
                        events_col[m].append(f"🏰 {fmt_mmss(ot)} 建筑被摧毁")

        return {
            "format": "columnar_v1",
            "minutes": minutes_col,
            "radiant_gold_adv": g_adv_col,
            "radiant_xp_adv": x_adv_col,
            "events": events_col,
            "item_zh_map": item_zh_map,
            "players": players_col,
        }

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
            own_slot = int(own_p["player_slot"])
            own_rp = raw_by_slot.get(own_slot, {})
            own_lane = own_rp.get("lane") if own_rp.get("lane") is not None else own_p.get("raw_lane")
            same_lane_opps = [
                ep
                for ep in opp_players
                if own_lane in (1, 2, 3)
                and (
                    raw_by_slot.get(int(ep["player_slot"]), {}).get("lane")
                    if raw_by_slot.get(int(ep["player_slot"]), {}).get("lane") is not None
                    else ep.get("raw_lane")
                )
                == own_lane
            ]
            if same_lane_opps:
                if pos_i in (1, 2, 3):
                    core_opps = [ep for ep in same_lane_opps if int(ep.get("pos") or 0) in (1, 2, 3)]
                    opp_p = sorted(core_opps or same_lane_opps, key=lambda ep: int(ep.get("pos") or 9))[0]
                else:
                    sup_opps = [ep for ep in same_lane_opps if int(ep.get("pos") or 0) in (4, 5)]
                    opp_p = sorted(sup_opps or same_lane_opps, key=lambda ep: int(ep.get("pos") or 0), reverse=True)[0]
            else:
                opp_p = opp_by_pos.get(pos_i) or (opp_players[pos_i - 1] if pos_i - 1 < len(opp_players) else opp_players[0])
            opp_slot = int(opp_p["player_slot"])
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
            rating_own = float(own_p["rating_score"]) if own_p.get("rating_score") is not None else None
            rating_opp = float(opp_p["rating_score"]) if opp_p.get("rating_score") is not None else None

            # 4) 全球同英雄百分位 (OpenDota Benchmarks)
            def extract_benchmarks(rp_obj: Dict[str, Any]) -> Tuple[Optional[float], List[Dict[str, Any]]]:
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
                avg_pct = round(sum(pct_vals) / len(pct_vals), 1) if pct_vals else None
                return avg_pct, items[:4]

            own_bm_avg, own_bm_top = extract_benchmarks(own_rp)
            opp_bm_avg, opp_bm_top = extract_benchmarks(opp_rp)

            # 5) 计算同位置对位胜负指数 (own_edge: 正数代表我方占优，负数代表敌方占优)
            is_core = pos_i in (1, 2, 3)
            r_own_calc = rating_own if rating_own is not None else 0.0
            r_opp_calc = rating_opp if rating_opp is not None else 0.0
            if is_core:
                own_power = (
                    r_own_calc * 1.1
                    + (nw_own / 1000.0) * 1.4
                    + (dmg_own / 1000.0) * 1.1
                    + (td_own / 1000.0) * 1.2
                    + (gold10_own / 1000.0) * 1.8
                    + h2h_own_kills * 4.5
                )
                opp_power = (
                    r_opp_calc * 1.1
                    + (nw_opp / 1000.0) * 1.4
                    + (dmg_opp / 1000.0) * 1.1
                    + (td_opp / 1000.0) * 1.2
                    + (gold10_opp / 1000.0) * 1.8
                    + h2h_opp_kills * 4.5
                )
            else:
                own_power = (
                    r_own_calc * 1.1
                    + kp_own * 0.45
                    + wards_own * 1.4
                    + dew_own * 3.2
                    + stuns_own * 0.45
                    + (dmg_own / 1000.0) * 0.8
                    + h2h_own_kills * 4.0
                )
                opp_power = (
                    r_opp_calc * 1.1
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
                verdict_tag = "👑 对位完爆 (大优)"
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
                "evidence": "inferred",
            })

        side_verdict = (
            f"1~5 号位同位置正面对账：本方在 {won_overall_cnt}/5 个位置上打出对位优势（10 分钟对线期占优 {won_lanes_cnt}/5 路）。"
            + (f" 最大对位压制点：【{biggest_gap_pair[0]}】；" if biggest_gap_pair[1] > 0 else "")
            + (f" 最大对位出血点：【{biggest_loss_pair[0]}】。" if biggest_loss_pair[1] < -2.0 else "")
        )
        return {
            "side": side_key,
            "evidence": "inferred",
            "side_verdict": side_verdict,
            "conclusions": [{"text": side_verdict, "kind": "side_verdict", "evidence": "inferred"}],
            "won_lanes_cnt": won_lanes_cnt,
            "won_overall_cnt": won_overall_cnt,
            "mirror_rows": mirror_rows,
        }

    # =========================================================================
    # 十二、买活死尸检 · 信使惨案 · 肉山盾/魔晶归属 · 中立装备锻造附魔审计
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
                    outcome_tag = "💀 致命买活死"
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
                    "evidence": "inferred",
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
                    "evidence": "inferred" if is_laning_courier else "measured",
                    **(
                        {}
                        if is_laning_courier
                        else {"source_fields": ["objectives"]}
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

        # 3) 阿哈利姆魔晶时间轴 & 中立装备锻造附魔审计
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

            # 解析 neutral_item_history
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
                "evidence": "inferred",
            })

        side_verdict = (
            f"全队共交出 {len(buyback_events)} 次买活（其中 {dieback_cnt} 次致命买活死、{clutch_bb_cnt} 次有效救世买活）｜"
            f"信使博弈：击杀敌方 {own_couriers_killed} 只信使 / 本方掉鸡 {own_couriers_lost} 只｜"
            f"阿哈利姆魔晶普及率：{shard_count}/5 人。"
        )
        return {
            "side": side_key,
            "evidence": "inferred",
            "side_verdict": side_verdict,
            "conclusions": [{"text": side_verdict, "kind": "side_verdict", "evidence": "inferred"}],
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

    ctx["NEUTRAL_ITEMS_ZH"] = NEUTRAL_ITEMS_ZH
    return {
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
