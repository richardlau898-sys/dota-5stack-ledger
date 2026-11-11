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


def build_vision_stack_smoke_sections(ctx: Dict[str, Any]) -> Dict[str, Any]:
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

                # 匹配消失事件计算寿命（优先使用 ehandle 精确匹配，回退 key 匹配）
                o_ehandle = o.get("ehandle")
                matched_l = []
                if o_ehandle is not None:
                    matched_l = [
                        ol for ol in o_left
                        if ol.get("ehandle") == o_ehandle and int(ol.get("time") or 0) >= ot
                    ]
                if not matched_l:
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
                            "evidence": "measured",
                            "source_fields": ["players[].obs_log", "players[].obs_left_log"],
                        })

                obs_records.append({
                    "time_sec": ot,
                    "end_sec": ot + lifespan,
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
                    "evidence": "measured",
                    "source_fields": ["players[].obs_log", "players[].obs_left_log"],
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
                    "evidence": "inferred",
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
                    "evidence": "inferred",
                })

        # 提取「✨ 满时长封神眼 (god_tier_wards)」与「🌑 全图黑灯瞎火真空期 (blackout_windows)」
        god_tier_wards: List[Dict[str, Any]] = []
        for r in obs_records:
            if (not r.get("was_dewarded")) and r.get("lifespan_sec", 0) >= 330 and r.get("posture") in ("aggressive", "river_roshan"):
                god_tier_wards.append({
                    "time_str": r["time_str"],
                    "planter_hero": r["planter_hero"],
                    "pos": r["planter_pos"],
                    "zone_zh": r["zone_zh"],
                    "posture_zh": r["posture_zh"],
                    "lifespan_sec": r["lifespan_sec"],
                    "evidence": "measured",
                    "source_fields": ["players[].obs_log", "players[].obs_left_log"],
                })

        blackout_windows: List[Dict[str, Any]] = []
        own_deaths_all: List[Tuple[int, str]] = []
        for fp in own_players:
            rp_d = raw_by_slot.get(int(fp["player_slot"]), {})
            for de in rp_d.get("deaths_log") or []:
                own_deaths_all.append((int(de.get("time") or 0), fp["hero_short_zh"]))

        max_min_chk = max(10, int(duration_sec // 60))
        cur_bo = None
        for m_idx in range(8, max_min_chk):
            t_start = m_idx * 60
            t_end = (m_idx + 1) * 60
            t_mid = t_start + 30
            alive_obs = sum(1 for r in obs_records if r["time_sec"] <= t_mid <= r.get("end_sec", r["time_sec"] + 360))
            victims_in_m = [h for dt, h in own_deaths_all if t_start <= dt < t_end]
            if alive_obs <= 1:
                if cur_bo is None:
                    cur_bo = {
                        "start_min": m_idx,
                        "end_min": m_idx + 1,
                        "min_obs": alive_obs,
                        "victims": list(victims_in_m),
                    }
                else:
                    cur_bo["end_min"] = m_idx + 1
                    cur_bo["min_obs"] = min(cur_bo["min_obs"], alive_obs)
                    cur_bo["victims"].extend(victims_in_m)
            else:
                if cur_bo is not None:
                    if len(cur_bo["victims"]) >= 1 or (cur_bo["end_min"] - cur_bo["start_min"]) >= 2:
                        v_uniq = list(dict.fromkeys(cur_bo["victims"]))
                        tr_str = f"{cur_bo['start_min']:02d}:00–{cur_bo['end_min']:02d}:00"
                        blackout_windows.append({
                            "time_range": tr_str,
                            "duration_min": cur_bo["end_min"] - cur_bo["start_min"],
                            "min_obs": cur_bo["min_obs"],
                            "deaths_cnt": len(cur_bo["victims"]),
                            "victims_str": "、".join(v_uniq[:4]) if v_uniq else "无阵亡",
                            "detail": (
                                f"🌑 {tr_str}（持续 {cur_bo['end_min'] - cur_bo['start_min']} 分钟己方场上假眼至多 {cur_bo['min_obs']} 颗）："
                                + (f"同期本方【{'、'.join(v_uniq[:4])}】累计阵亡 {len(cur_bo['victims'])} 人次。" if v_uniq else "同期我方无英雄阵亡。")
                            ),
                            "evidence": "inferred",
                        })
                    cur_bo = None
        if cur_bo is not None and (len(cur_bo["victims"]) >= 1 or (cur_bo["end_min"] - cur_bo["start_min"]) >= 2):
            v_uniq = list(dict.fromkeys(cur_bo["victims"]))
            tr_str = f"{cur_bo['start_min']:02d}:00–{cur_bo['end_min']:02d}:00"
            blackout_windows.append({
                "time_range": tr_str,
                "duration_min": cur_bo["end_min"] - cur_bo["start_min"],
                "min_obs": cur_bo["min_obs"],
                "deaths_cnt": len(cur_bo["victims"]),
                "victims_str": "、".join(v_uniq[:4]) if v_uniq else "无阵亡",
                "detail": (
                    f"🌑 {tr_str}（持续 {cur_bo['end_min'] - cur_bo['start_min']} 分钟己方场上假眼至多 {cur_bo['min_obs']} 颗）："
                    + (f"同期本方【{'、'.join(v_uniq[:4])}】累计阵亡 {len(cur_bo['victims'])} 人次。" if v_uniq else "同期我方无英雄阵亡。")
                ),
                "evidence": "inferred",
            })

        total_obs = max(1, len(obs_records))
        agg_pct = round(posture_counts["aggressive"] / total_obs * 100, 1)
        riv_pct = round(posture_counts["river_roshan"] / total_obs * 100, 1)
        def_pct = round(posture_counts["defensive"] / total_obs * 100, 1)
        avg_team_life = int(round(sum(r["lifespan_sec"] for r in obs_records) / total_obs, 0)) if obs_records else 0

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
            "evidence": "inferred",
            "conclusions": [{"text": posture_verdict, "kind": "posture_verdict", "evidence": "inferred"}],
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
            "instant_dewards": instant_dewards[:8],
            "god_tier_wards": god_tier_wards[:6],
            "blackout_windows": blackout_windows[:6],
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
                "evidence": "measured",
                "source_fields": ["players[].camps_stacked", "players[].creeps_stacked", "players[].camps_stacked_t"],
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

        # 2) 开雾记录统计（仅读取团战数据中的 item_uses.smoke_of_deceit，不按买雾时间推断）
        own_smoke_uses_total = 0
        per_player_smokes: List[Dict[str, Any]] = []
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
                    "evidence": "inferred",
                })

        opp_smoke_uses_total = sum(
            int((raw_by_slot.get(int(op["player_slot"]), {}).get("item_uses") or {}).get("smoke_of_deceit") or 0)
            for op in opp_players
        )

        raw_tfs = match.get("teamfights") or []
        raw_players_list = match.get("players") or []
        own_idx_range = range(0, 5) if side_key == "radiant" else range(5, 10)
        opp_idx_range = range(5, 10) if side_key == "radiant" else range(0, 5)

        smoke_events: List[Dict[str, Any]] = []
        for tf in raw_tfs:
            tf_pl = tf.get("players") or []
            smoke_users_in_tf: List[Dict[str, Any]] = []
            for j in own_idx_range:
                if j < len(tf_pl):
                    tf_s_used = int((tf_pl[j].get("item_uses") or {}).get("smoke_of_deceit") or 0)
                    if tf_s_used > 0:
                        rp_j = raw_players_list[j] if j < len(raw_players_list) else {}
                        fp_j = fmt_by_hid.get(int(rp_j.get("hero_id") or 0))
                        smoke_users_in_tf.append({
                            "hero_short_zh": fp_j["hero_short_zh"] if fp_j else "本方英雄",
                            "personaname": fp_j["personaname"] if fp_j else "",
                            "pos": fp_j["pos"] if fp_j else 5,
                            "count": tf_s_used,
                        })
            if not smoke_users_in_tf:
                continue

            t0 = int(tf.get("start") or 0)
            t_end = int(tf.get("end") or t0)
            own_d = sum(int(tf_pl[j].get("deaths") or 0) for j in own_idx_range if j < len(tf_pl))
            opp_d = sum(int(tf_pl[j].get("deaths") or 0) for j in opp_idx_range if j < len(tf_pl))

            if t0 < 600:
                phase_tag = "对线期团战雾"
            elif t0 < 1500:
                phase_tag = "中期团战雾"
            else:
                phase_tag = "后期团战雾"

            initiator = smoke_users_in_tf[0]
            if opp_d > own_d:
                outcome = "success"
                outcome_label = f"🟢 团战占优 ({opp_d}换{own_d})"
                detail = f"团战期间（{fmt_mmss(t0)}–{fmt_mmss(t_end)}）使用诡计之雾，敌方阵亡 {opp_d} 人、本方阵亡 {own_d} 人。"
            elif own_d > opp_d:
                outcome = "loss"
                outcome_label = f"🔴 团战阵亡偏多 ({opp_d}换{own_d})"
                detail = f"团战期间（{fmt_mmss(t0)}–{fmt_mmss(t_end)}）使用诡计之雾，本方阵亡 {own_d} 人、敌方阵亡 {opp_d} 人。"
            elif opp_d > 0:
                outcome = "trade"
                outcome_label = f"⚖️ 团战互换 ({opp_d}换{own_d})"
                detail = f"团战期间（{fmt_mmss(t0)}–{fmt_mmss(t_end)}）使用诡计之雾，双方各阵亡 {own_d} 人。"
            else:
                outcome = "dry"
                outcome_label = "🟡 团战未产生阵亡 (0换0)"
                detail = f"团战期间（{fmt_mmss(t0)}–{fmt_mmss(t_end)}）使用诡计之雾，未产生阵亡。"

            smoke_events.append({
                "time_sec": t0,
                "time_str": fmt_mmss(t0),
                "phase_tag": phase_tag,
                "initiator_hero": initiator["hero_short_zh"],
                "initiator_player": initiator["personaname"],
                "initiator_pos": initiator["pos"],
                "outcome": outcome,
                "outcome_label": outcome_label,
                "detail": detail,
                "evidence": "inferred",
            })

        succ_smokes = sum(1 for e in smoke_events if e["outcome"] == "success")
        if own_smoke_uses_total == 0:
            smoke_verdict = f"本方全场使用诡计之雾 0 次（敌方使用 {opp_smoke_uses_total} 次）。"
        elif not smoke_events:
            smoke_verdict = (
                f"本方全场累计使用诡计之雾 {own_smoke_uses_total} 次（敌方 {opp_smoke_uses_total} 次），"
                f"团战记录中未包含诡计之雾施放事件。"
            )
        else:
            smoke_verdict = (
                f"本方全场累计使用诡计之雾 {own_smoke_uses_total} 次（敌方 {opp_smoke_uses_total} 次），"
                f"其中 {len(smoke_events)} 次出现在团战记录中（团战占优 {succ_smokes} 波）。"
            )

        return {
            "side": side_key,
            "evidence": "inferred",
            "conclusions": [
                {"text": stack_verdict, "kind": "stack_verdict", "evidence": "inferred"},
                {"text": smoke_verdict, "kind": "smoke_verdict", "evidence": "inferred"},
            ],
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

    return {
        "support_vision_by_side": {
            "dire": analyze_side_vision_quality("dire"),
            "radiant": analyze_side_vision_quality("radiant"),
        },
        "stacking_and_smoke_by_side": {
            "dire": analyze_side_stacking_and_smokes("dire"),
            "radiant": analyze_side_stacking_and_smokes("radiant"),
        },
    }
