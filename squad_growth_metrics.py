#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阶段 4 (F2, F3, F4, F6, F7) 核心指标计算模块 (squad_growth_metrics.py)
严格遵循 AGENTS.md 与 T1-9：
- 只陈述数据事实，缺失数据返回 None（界面显示“无数据”），绝不用默认数值兜底。
- F2 首屏“下一把要改的 3 件事”只从 measured 结论中选择，团队优先，按胜负影响排序。
- F3 团队 7 项指标全部基于 OpenDota 原始字段精确定义。
- F4 个人趋势曲线与每周目标进度。
- F6 时长画像与连打疲劳（90 分钟同晚分桶，遵守 T1-9 最小样本量 >= 10 局）。
- F7 每场经济波动最大的 3 个复盘时刻（一句中性事实描述）。
"""

import statistics
from typing import Any, Dict, List, Optional, Tuple


def _fmt_mmss(sec: Any) -> str:
    try:
        s = int(round(float(sec)))
    except (TypeError, ValueError):
        return "00:00"
    neg = s < 0
    s = abs(s)
    m, rem = divmod(s, 60)
    return f"{'-' if neg else ''}{m:02d}:{rem:02d}"


def select_top3_measured_fixes(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    F2: 从候选改进项中：
    1. 严格过滤出 evidence == 'measured' 且具备真实 timestamp_str 的条目（剔除 inferred / template）。
    2. 团队层面 (scope == 'team') 优先于个人层面 (scope == 'player')，同层按 impact_score 降序排列。
    3. 取前 3 条并赋予 rank = 1..3。
    """
    measured_only: List[Dict[str, Any]] = []
    for c in candidates or []:
        if not isinstance(c, dict):
            continue
        if c.get("evidence") != "measured":
            continue
        ts = str(c.get("timestamp_str") or "").strip()
        title = str(c.get("title") or "").strip()
        fact = str(c.get("fact_evidence") or "").strip()
        action = str(c.get("action_item") or "").strip()
        if not ts or not title or not fact or not action:
            continue
        scope = "team" if c.get("scope") == "team" else "player"
        measured_only.append({
            "scope": scope,
            "evidence": "measured",
            "timestamp_sec": int(c.get("timestamp_sec") or 0),
            "timestamp_str": ts,
            "impact_score": round(float(c.get("impact_score") or 0.0), 1),
            "title": title,
            "fact_evidence": fact,
            "action_item": action,
        })

    measured_only.sort(
        key=lambda x: (1 if x["scope"] == "team" else 0, x["impact_score"]),
        reverse=True,
    )

    out: List[Dict[str, Any]] = []
    for idx, item in enumerate(measured_only[:3], start=1):
        out.append({"rank": idx, **item})
    return out


def _collect_hero_death_timestamps(match: Dict[str, Any]) -> Dict[int, List[int]]:
    """
    从敌方 players[].kills_log 与 teamfights 提取每个 player_slot 的精确阵亡秒数列表（升序去重）。
    """
    players = match.get("players") or []
    hero_key_to_slot: Dict[str, int] = {}
    slot_by_idx: Dict[int, int] = {}
    for idx, p in enumerate(players):
        slot = int(p.get("player_slot") if p.get("player_slot") is not None else idx)
        slot_by_idx[idx] = slot
        # OpenDota kills_log.key 形如 npc_dota_hero_antimage
        h_name = str(p.get("hero_name") or "")
        if h_name.startswith("npc_dota_hero_"):
            hero_key_to_slot[h_name] = slot

    # 若 raw match 的 player 没有 hero_name，则从 constants 映射
    if len(hero_key_to_slot) < len(players):
        try:
            from dota_analyst import get_hero_constants_map

            hmap = get_hero_constants_map()
            for p in players:
                slot = int(p.get("player_slot") or 0)
                hid = int(p.get("hero_id") or 0)
                c_entry = hmap.get(str(hid)) or hmap.get(hid) or {}
                cname = str(c_entry.get("name") or "")
                if cname.startswith("npc_dota_hero_"):
                    hero_key_to_slot[cname] = slot
        except Exception:
            pass

    deaths_by_slot: Dict[int, set] = {int(p.get("player_slot") or 0): set() for p in players}
    for p in players:
        for kl in p.get("kills_log") or []:
            if not isinstance(kl, dict):
                continue
            target_key = str(kl.get("key") or "")
            t_sec = kl.get("time")
            if target_key in hero_key_to_slot and t_sec is not None:
                deaths_by_slot.setdefault(hero_key_to_slot[target_key], set()).add(int(t_sec))

    for tf in match.get("teamfights") or []:
        tf_end = int(tf.get("end") or tf.get("start") or 0)
        for idx, tf_p in enumerate(tf.get("players") or []):
            if int(tf_p.get("deaths") or 0) > 0 and idx in slot_by_idx:
                slot = slot_by_idx[idx]
                # 若 kills_log 已有 [start-5, end+5] 内的精确时间则不重复加粗略时间
                existing = deaths_by_slot.setdefault(slot, set())
                tf_start = int(tf.get("start") or 0)
                if not any(tf_start - 5 <= d <= tf_end + 5 for d in existing):
                    existing.add(tf_end)

    return {slot: sorted(times) for slot, times in deaths_by_slot.items()}


def _is_objective_for_side(obj: Dict[str, Any], side: str) -> Optional[str]:
    """
    判断 objectives 条目是否属于 side ('radiant' | 'dire') 拿下的建筑或肉山。
    返回中文目标名称，若不属于则返回 None。
    """
    if not isinstance(obj, dict):
        return None
    otype = str(obj.get("type") or "")
    team = obj.get("team")
    slot = obj.get("player_slot")
    key = str(obj.get("key") or "")

    if otype == "CHAT_MESSAGE_ROSHAN_KILL":
        is_rad = (team == 2) or (slot is not None and int(slot) < 128)
        obj_side = "radiant" if is_rad else "dire"
        return "肉山" if obj_side == side else None

    if otype in ("CHAT_MESSAGE_TOWER_KILL", "CHAT_MESSAGE_BARRACKS_KILL", "building_kill"):
        # 摧毁敌方建筑记为本方收益：badguys 建筑被毁 -> radiant 收益；goodguys 建筑被毁 -> dire 收益
        if "badguys" in key:
            obj_side = "radiant"
        elif "goodguys" in key:
            obj_side = "dire"
        elif team in (2, 3):
            obj_side = "radiant" if int(team) == 2 else "dire"
        else:
            return None
        if obj_side != side:
            return None
        return "兵营" if "BARRACKS" in otype or "rax" in key else "防御塔"

    return None


def build_team_metrics_by_side(match: Dict[str, Any], report_dict: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    F3 · 计算单局双方团队指标：
    1. fight_conversion: 赢团（己方阵亡比敌方少 >= 2）后 90s 内是否拿到建筑或肉山
    2. first_roshan: 第一条肉山击杀的时间和归属
    3. throw_comeback_window: 最大经济领先 >= 10,000 却输掉的翻盘局 + 3 分钟最大经济跌幅窗口及其中团战
    4. buyback_diebacks: buyback_log 时间到下一次阵亡 <= 60s
    5. smoke_effectiveness: 开雾次数与窗口（标注基于购买时间窗口推断）
    6. high_risk_ward_spots: 本局存活 < 120s 的假眼明细
    7. lane_duo_networth_diff: 按真实同路队友和真实对位统计 10 分钟净值差
    """
    is_parsed = bool(report_dict.get("is_parsed"))
    raw_tfs = match.get("teamfights") or []
    objectives = sorted(
        [o for o in (match.get("objectives") or []) if isinstance(o, dict) and o.get("time") is not None],
        key=lambda o: int(o.get("time") or 0),
    )
    gold_adv = match.get("radiant_gold_adv") or report_dict.get("radiant_gold_adv") or []
    radiant_win = bool(report_dict.get("radiant_win"))
    deaths_by_slot = _collect_hero_death_timestamps(match) if is_parsed else {}

    # 1. 第一个肉山时间
    first_roshan: Optional[Dict[str, Any]] = None
    for obj in objectives:
        if obj.get("type") == "CHAT_MESSAGE_ROSHAN_KILL":
            t_sec = int(obj.get("time") or 0)
            team = obj.get("team")
            slot = obj.get("player_slot")
            is_rad = (team == 2) or (slot is not None and int(slot) < 128)
            r_side = "radiant" if is_rad else "dire"
            first_roshan = {
                "time_sec": t_sec,
                "time_str": _fmt_mmss(t_sec),
                "side": r_side,
                "side_zh": "天辉" if r_side == "radiant" else "夜魇",
                "evidence": "measured",
            }
            break

    out_by_side: Dict[str, Dict[str, Any]] = {}
    for side in ("radiant", "dire"):
        side_won = radiant_win if side == "radiant" else (not radiant_win)
        own_players = (
            report_dict.get("radiant_pos_1_to_5")
            if side == "radiant"
            else report_dict.get("dire_pos_1_to_5")
        ) or []
        opp_players = (
            report_dict.get("dire_pos_1_to_5")
            if side == "radiant"
            else report_dict.get("radiant_pos_1_to_5")
        ) or []

        # (A) 赢团转化率
        won_fights_rows: List[Dict[str, Any]] = []
        if is_parsed and raw_tfs:
            for tf in raw_tfs:
                tf_p = tf.get("players") or []
                if len(tf_p) < 10:
                    continue
                rad_d = sum(1 for i in range(5) if int(tf_p[i].get("deaths") or 0) > 0)
                dire_d = sum(1 for i in range(5, 10) if int(tf_p[i].get("deaths") or 0) > 0)
                our_d = rad_d if side == "radiant" else dire_d
                opp_d = dire_d if side == "radiant" else rad_d
                if opp_d - our_d < 2:
                    continue
                start_s = int(tf.get("start") or 0)
                end_s = int(tf.get("end") or start_s)
                objs_taken: List[str] = []
                for obj in objectives:
                    ot = int(obj.get("time") or 0)
                    if end_s <= ot <= end_s + 90:
                        label = _is_objective_for_side(obj, side)
                        if label:
                            objs_taken.append(f"{_fmt_mmss(ot)} {label}")
                won_fights_rows.append({
                    "start_sec": start_s,
                    "end_sec": end_s,
                    "time_str": f"{_fmt_mmss(start_s)}–{_fmt_mmss(end_s)}",
                    "our_deaths": our_d,
                    "opp_deaths": opp_d,
                    "converted": len(objs_taken) > 0,
                    "objectives_taken": objs_taken,
                    "evidence": "measured",
                })
        won_cnt = len(won_fights_rows)
        conv_cnt = sum(1 for r in won_fights_rows if r["converted"])
        fight_conversion = {
            "available": is_parsed,
            "won_fights_count": won_cnt if is_parsed else None,
            "converted_count": conv_cnt if is_parsed else None,
            "conversion_rate_pct": round(conv_cnt * 100.0 / won_cnt, 1) if (is_parsed and won_cnt > 0) else None,
            "fights": won_fights_rows,
            "evidence": "measured",
        }

        # (B) 翻盘局与 3 分钟最大跌幅窗口
        our_adv_series = [
            int(v) if side == "radiant" else -int(v)
            for v in gold_adv
            if isinstance(v, (int, float))
        ]
        max_lead = max(our_adv_series) if our_adv_series else None
        is_throw_loss = bool(max_lead is not None and max_lead >= 10000 and not side_won)
        worst_3m_window: Optional[Dict[str, Any]] = None
        if len(our_adv_series) >= 2:
            best_drop = 0
            best_pair = (0, 1)
            for i in range(len(our_adv_series)):
                for j in range(i + 1, min(len(our_adv_series), i + 4)):
                    drop = our_adv_series[j] - our_adv_series[i]
                    if drop < best_drop:
                        best_drop = drop
                        best_pair = (i, j)
            if best_drop < 0:
                m_s, m_e = best_pair
                w_tfs = []
                for tf in report_dict.get("key_teamfights") or []:
                    tf_s = int(tf.get("start_sec") or 0)
                    if m_s * 60 <= tf_s <= m_e * 60:
                        raw_swing = tf.get("net_swing_radiant")
                        if raw_swing is None and isinstance(tf.get("gold_swing"), (int, float)):
                            raw_swing = tf.get("gold_swing")
                        swing_int = int(raw_swing or 0)
                        w_tfs.append({
                            "time_str": tf.get("time_range") or tf.get("time_window_str") or _fmt_mmss(tf_s),
                            "gold_swing": swing_int if side == "radiant" else -swing_int,
                        })
                worst_3m_window = {
                    "start_min": m_s,
                    "end_min": m_e,
                    "window_str": f"{m_s:02d}:00–{m_e:02d}:00",
                    "gold_delta": int(best_drop),
                    "teamfights": w_tfs,
                    "evidence": "measured",
                }
        throw_comeback_audit = {
            "available": bool(our_adv_series),
            "max_gold_lead": max_lead,
            "is_10k_throw_loss": is_throw_loss if our_adv_series else None,
            "worst_3min_window": worst_3m_window,
            "evidence": "measured",
        }

        # (C) 买活后 60 秒内再死
        raw_players_by_slot = {
            int(rp.get("player_slot") or 0): rp for rp in (match.get("players") or []) if isinstance(rp, dict)
        }
        bb_diebacks: List[Dict[str, Any]] = []
        if is_parsed:
            for p in own_players:
                slot = int(p.get("player_slot") or 0)
                rp = raw_players_by_slot.get(slot) or {}
                d_times = deaths_by_slot.get(slot) or []
                for bb in rp.get("buyback_log") or []:
                    if not isinstance(bb, dict) or bb.get("time") is None:
                        continue
                    bb_t = int(bb["time"])
                    next_d = next((dt for dt in d_times if 0 < dt - bb_t <= 60), None)
                    if next_d is not None:
                        bb_diebacks.append({
                            "player_slot": slot,
                            "pos": p.get("pos"),
                            "hero_short_zh": p.get("hero_short_zh") or "",
                            "personaname": p.get("personaname") or "",
                            "buyback_time_sec": bb_t,
                            "buyback_time_str": _fmt_mmss(bb_t),
                            "death_time_sec": next_d,
                            "death_time_str": _fmt_mmss(next_d),
                            "delta_sec": next_d - bb_t,
                            "evidence": "measured",
                        })

        # (D) 开雾效果（关联 deep_forensics.stacking_and_smoke_by_side，保留 T1-5 说明）
        df_ss = (
            ((report_dict.get("deep_forensics") or {}).get("stacking_and_smoke_by_side") or {})
            .get(side, {})
        )
        smoke_effectiveness = {
            "available": is_parsed,
            "own_smokes_used": df_ss.get("own_smoke_uses") if is_parsed else None,
            "smoke_windows": df_ss.get("smoke_events") or [],
            "note": "基于雾购买时间窗口推断，非实际使用时间",
            "evidence": "inferred",
        }

        # (E) 本局短命高危眼位 (<120s)
        short_wards = []
        for w in ((report_dict.get("vision_and_map_data") or {}).get("wards") or []):
            if not isinstance(w, dict) or w.get("side") != side or w.get("type") != "obs":
                continue
            life = w.get("lifespan_sec")
            if life is not None and int(life) < 120:
                short_wards.append({
                    "time_str": w.get("time_str") or _fmt_mmss(w.get("time_sec") or 0),
                    "x": w.get("x"),
                    "y": w.get("y"),
                    "lifespan_sec": int(life),
                    "was_dewarded": bool(w.get("was_dewarded")),
                })

        # (F) 分路组合 10 分钟净值差（按真实同路队友与真实对位）
        def _p_lane(pl: Dict[str, Any]) -> int:
            return int(pl.get("raw_lane") or pl.get("lane_id") or pl.get("lane") or 0)

        def _p_nw10(pl: Dict[str, Any]) -> Optional[int]:
            if pl.get("net_worth_10m") is not None:
                return int(pl["net_worth_10m"])
            l10 = pl.get("laning_10m")
            if isinstance(l10, dict) and l10.get("gold10") is not None:
                return int(l10["gold10"])
            nwt = pl.get("networth_t")
            if isinstance(nwt, list) and len(nwt) > 10 and nwt[10] is not None:
                return int(nwt[10])
            return None

        lane_duos: List[Dict[str, Any]] = []
        if is_parsed:
            for lane_id, lane_zh in ((1, "下路"), (2, "中路"), (3, "上路")):
                allies_in_lane = [
                    p for p in own_players if _p_lane(p) == lane_id and _p_nw10(p) is not None
                ]
                opps_in_lane = [
                    p for p in opp_players if _p_lane(p) == lane_id and _p_nw10(p) is not None
                ]
                if not allies_in_lane or not opps_in_lane:
                    continue
                our_nw10 = sum(int(_p_nw10(p) or 0) for p in allies_in_lane)
                opp_nw10 = sum(int(_p_nw10(p) or 0) for p in opps_in_lane)
                lane_duos.append({
                    "lane": lane_id,
                    "lane_zh": lane_zh,
                    "allies": [p.get("hero_short_zh") or "" for p in allies_in_lane],
                    "ally_account_ids": [p.get("account_id") for p in allies_in_lane if p.get("account_id")],
                    "opponents": [p.get("hero_short_zh") or "" for p in opps_in_lane],
                    "our_net_worth_10m": our_nw10,
                    "opp_net_worth_10m": opp_nw10,
                    "net_worth_diff_10m": our_nw10 - opp_nw10,
                    "evidence": "measured",
                })

        out_by_side[side] = {
            "fight_conversion": fight_conversion,
            "first_roshan": first_roshan,
            "throw_comeback_audit": throw_comeback_audit,
            "buyback_diebacks": bb_diebacks,
            "smoke_effectiveness": smoke_effectiveness,
            "short_lived_wards_under_2m": short_wards,
            "lane_duo_networth_diff": lane_duos,
        }

    return out_by_side


def aggregate_high_risk_ward_spots(
    raw_matches: List[Dict[str, Any]],
    max_median_lifespan_sec: float = 120.0,
    min_samples: int = 2,
) -> List[Dict[str, Any]]:
    """
    F3 · 跨局聚合 obs_log 与 obs_left_log，找出存活中位数 < 2 分钟（120 秒）的固定高危眼位。
    """
    spot_lifespans: Dict[Tuple[int, int], List[int]] = {}
    for m in raw_matches or []:
        if not isinstance(m, dict):
            continue
        # 支持从已生成的报告 vision_and_map_data.wards 聚合，或从原始录像 players[].obs_log/obs_left_log 聚合
        v_wards = (m.get("vision_and_map_data") or {}).get("wards")
        if isinstance(v_wards, list) and v_wards:
            for w in v_wards:
                if not isinstance(w, dict) or w.get("type") != "obs":
                    continue
                if w.get("x") is None or w.get("y") is None or w.get("lifespan_sec") is None:
                    continue
                gx = int(round(float(w["x"]) / 4.0) * 4)
                gy = int(round(float(w["y"]) / 4.0) * 4)
                spot_lifespans.setdefault((gx, gy), []).append(max(0, int(w["lifespan_sec"])))
            continue
        for p in m.get("players") or []:
            if not isinstance(p, dict):
                continue
            obs_log = p.get("obs_log") or []
            left_log = p.get("obs_left_log") or []
            left_by_handle = {
                ev.get("ehandle"): ev
                for ev in left_log
                if isinstance(ev, dict) and ev.get("ehandle") is not None
            }
            for ob in obs_log:
                if not isinstance(ob, dict) or ob.get("x") is None or ob.get("y") is None:
                    continue
                t_placed = int(ob.get("time") or 0)
                eh = ob.get("ehandle")
                left_ev = left_by_handle.get(eh) if eh is not None else None
                if left_ev is None:
                    # 按相同坐标匹配最近的移除事件
                    for cand in left_log:
                        if (
                            isinstance(cand, dict)
                            and cand.get("x") == ob.get("x")
                            and cand.get("y") == ob.get("y")
                            and int(cand.get("time") or 0) >= t_placed
                        ):
                            left_ev = cand
                            break
                if left_ev is None or left_ev.get("time") is None:
                    continue
                life = max(0, int(left_ev["time"]) - t_placed)
                # 4 单位网格聚类固定眼位
                gx = int(round(float(ob["x"]) / 4.0) * 4)
                gy = int(round(float(ob["y"]) / 4.0) * 4)
                spot_lifespans.setdefault((gx, gy), []).append(life)

    results: List[Dict[str, Any]] = []
    for (gx, gy), lives in spot_lifespans.items():
        if len(lives) < min_samples:
            continue
        med = float(statistics.median(lives))
        if med < max_median_lifespan_sec:
            results.append({
                "x": gx,
                "y": gy,
                "sample_count": len(lives),
                "median_lifespan_sec": round(med, 1),
                "min_lifespan_sec": min(lives),
                "max_lifespan_sec": max(lives),
                "evidence": "measured",
            })
    results.sort(key=lambda r: (r["median_lifespan_sec"], -r["sample_count"]))
    return results


def build_next_game_top3_fixes_by_side(
    match: Dict[str, Any],
    report_dict: Dict[str, Any],
    team_metrics_by_side: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    F2 · 为天辉/夜魇生成首屏“下一把要改的 3 件事”（只取 measured 结论，团队优先，按影响排序）。
    """
    if team_metrics_by_side is None:
        team_metrics_by_side = build_team_metrics_by_side(match, report_dict)

    is_parsed = bool(report_dict.get("is_parsed"))
    duration_str = str(report_dict.get("duration_str") or "00:00")
    duration_sec = int(float(report_dict.get("duration_min") or 0) * 60)

    out: Dict[str, List[Dict[str, Any]]] = {}
    for side in ("radiant", "dire"):
        candidates: List[Dict[str, Any]] = []
        tm = team_metrics_by_side.get(side) or {}
        own_players = (
            report_dict.get("radiant_pos_1_to_5")
            if side == "radiant"
            else report_dict.get("dire_pos_1_to_5")
        ) or []
        df = report_dict.get("deep_forensics") or {}

        # 1. 团队级：赢团后 90 秒 0 建筑/肉山转化
        fc = tm.get("fight_conversion") or {}
        for f in fc.get("fights") or []:
            if not f.get("converted"):
                diff_d = int(f.get("opp_deaths") or 0) - int(f.get("our_deaths") or 0)
                candidates.append({
                    "scope": "team",
                    "evidence": "measured",
                    "timestamp_sec": int(f.get("end_sec") or 0),
                    "timestamp_str": str(f.get("time_str") or _fmt_mmss(f.get("end_sec") or 0)),
                    "impact_score": 1400.0 + diff_d * 350.0,
                    "title": f"{f.get('time_str')} 赢团（{f.get('our_deaths')}换{f.get('opp_deaths')}）后 90 秒零建筑/肉山转化",
                    "fact_evidence": f"本方在 {f.get('time_str')} 团战打出 {f.get('our_deaths')} 换 {f.get('opp_deaths')}，但随后 90 秒内摧毁建筑与肉山记录为 0。",
                    "action_item": "赢下人数差 >=2 的团战后，全队立即就近推塔或打肉山，不在野区分散刷钱。",
                })

        # 2. 团队级：3 分钟最大经济跌幅窗口 / 惨败团战
        tc = (tm.get("throw_comeback_audit") or {}).get("worst_3min_window")
        if isinstance(tc, dict) and int(tc.get("gold_delta") or 0) <= -1500:
            drop_abs = abs(int(tc["gold_delta"]))
            candidates.append({
                "scope": "team",
                "evidence": "measured",
                "timestamp_sec": int(tc.get("start_min") or 0) * 60,
                "timestamp_str": str(tc.get("window_str") or "10:00–13:00"),
                "impact_score": float(drop_abs),
                "title": f"{tc.get('window_str')} 窗口团队经济下跌 {drop_abs:,} 金",
                "fact_evidence": f"在 {tc.get('window_str')} 的 3 分钟窗口内，本方团队净值差下跌 {drop_abs:,} 金。",
                "action_item": "关键技能或大招冷却期内避免连续接团，劣势窗口先处理兵线守高台视野。",
            })

        # 3. 团队级：视野断档期（场上假眼 <= 1 颗）阵亡
        vis_side = ((df.get("support_vision_by_side") or {}).get(side)) or {}
        for bw in vis_side.get("blackout_windows") or []:
            if not isinstance(bw, dict):
                continue
            bw_deaths = int(bw.get("deaths_cnt") or bw.get("deaths_in_blackout") or 0)
            bw_dur_min = int(bw.get("duration_min") or 0)
            ts_str = str(bw.get("time_range") or "").strip()
            if bw_dur_min >= 2 and ts_str:
                start_part = ts_str.split("–")[0].split("-")[0].strip()
                start_sec = int(start_part.split(":")[0]) * 60 if ":" in start_part and start_part.split(":")[0].isdigit() else 600
                min_obs = int(bw.get("min_obs") or 0)
                candidates.append({
                    "scope": "team",
                    "evidence": "measured",
                    "timestamp_sec": start_sec,
                    "timestamp_str": ts_str,
                    "impact_score": 950.0 + bw_deaths * 450.0 + bw_dur_min * 120.0,
                    "title": f"{ts_str} 视野断档期（场上假眼至多 {min_obs} 颗，持续 {bw_dur_min} 分钟）阵亡 {bw_deaths} 人次",
                    "fact_evidence": f"在 {ts_str} 持续 {bw_dur_min} 分钟内，本方场上存活假眼至多 {min_obs} 颗，同期阵亡 {bw_deaths} 人次。",
                    "action_item": "辅助在旧眼到期前 30 秒提前补充河道或主野区入口假眼，避免视野真空期接团。",
                })

        # 4. 团队级：10 分钟分路组合净值差落后
        for ld in tm.get("lane_duo_networth_diff") or []:
            diff10 = int(ld.get("net_worth_diff_10m") or 0)
            if diff10 <= -800:
                allies_str = " + ".join(ld.get("allies") or [])
                opps_str = " + ".join(ld.get("opponents") or [])
                t10_str = _fmt_mmss(600)
                candidates.append({
                    "scope": "team",
                    "evidence": "measured",
                    "timestamp_sec": 600,
                    "timestamp_str": t10_str,
                    "impact_score": float(abs(diff10)),
                    "title": f"{t10_str} {ld.get('lane_zh')}组合（{allies_str}）净值落后 {abs(diff10):,} 金",
                    "fact_evidence": f"在 {t10_str} 节点，{ld.get('lane_zh')} {allies_str} 合计净值 {ld.get('our_net_worth_10m'):,} 金，对比对位 {opps_str}（{ld.get('opp_net_worth_10m'):,} 金）落后 {abs(diff10):,} 金。",
                    "action_item": "对线期劣势路优先拉野控线与护符保发育，避免强拼连续送头扩大对位经济差。",
                })

        # 5. 个人级：买活后 60 秒内再死 (measured)
        for bbd in tm.get("buyback_diebacks") or []:
            hero_zh = bbd.get("hero_short_zh") or ""
            bb_ts = bbd.get("buyback_time_str") or "00:00"
            d_ts = bbd.get("death_time_str") or "00:00"
            delta_s = int(bbd.get("delta_sec") or 0)
            candidates.append({
                "scope": "player",
                "evidence": "measured",
                "timestamp_sec": int(bbd.get("buyback_time_sec") or 0),
                "timestamp_str": bb_ts,
                "impact_score": 1300.0,
                "title": f"{bb_ts} {hero_zh} 买活后 {delta_s} 秒（{d_ts}）再次阵亡",
                "fact_evidence": f"{hero_zh} 在 {bb_ts} 买活，{delta_s} 秒后于 {d_ts} 再次阵亡。",
                "action_item": "买活落地后先等队友控制技能对齐再切入，严禁无视野单人冲高坡追击。",
            })

        # 6. 个人级：10 分钟后团战外阵亡记录 (measured)
        for p in own_players:
            pickoffs = (p.get("phase_telemetry") or {}).get("solo_pickoffs") or []
            post10_pickoffs = [
                sp for sp in pickoffs if isinstance(sp, dict) and int(sp.get("time_sec") or 0) >= 600
            ]
            if len(post10_pickoffs) >= 2:
                first_sp = post10_pickoffs[0]
                sp_ts = str(first_sp.get("time_str") or _fmt_mmss(first_sp.get("time_sec") or 600))
                h_zh = p.get("hero_short_zh") or ""
                candidates.append({
                    "scope": "player",
                    "evidence": "measured",
                    "timestamp_sec": int(first_sp.get("time_sec") or 600),
                    "timestamp_str": sp_ts,
                    "impact_score": 850.0 + len(post10_pickoffs) * 180.0,
                    "title": f"{h_zh}（{p.get('pos')}号位）对线期后团战外阵亡 {len(post10_pickoffs)} 次（首例 {sp_ts}）",
                    "fact_evidence": f"对线期结束后 {h_zh} 在非团战期间累计阵亡 {len(post10_pickoffs)} 次（如 {sp_ts}）。",
                    "action_item": f"{h_zh} 带线过河道或敌方英雄消失在视野时及时缩回安全区或呼叫队友蹲守。",
                })

        # 7. 兜底实测数据（如全胜碾压局或未解析录像局，直接取终局实测面板差距最大的客观指标）
        total_team_deaths = sum(int(p.get("deaths") or 0) for p in own_players)
        total_team_td = sum(int(p.get("tower_damage") or 0) for p in own_players)
        if total_team_deaths > 0:
            candidates.append({
                "scope": "team",
                "evidence": "measured",
                "timestamp_sec": duration_sec,
                "timestamp_str": duration_str,
                "impact_score": float(total_team_deaths * 35),
                "title": f"全场累计阵亡 {total_team_deaths} 次，建筑总伤害 {total_team_td:,}",
                "fact_evidence": f"截至终局 {duration_str}，本方五人合计阵亡 {total_team_deaths} 次，全队建筑伤害 {total_team_td:,}。",
                "action_item": "减少无掩护过河道与落单带线阵亡，把人数优势转化为防御塔推进。",
            })
        for p in sorted(own_players, key=lambda x: int(x.get("deaths") or 0), reverse=True)[:2]:
            d_cnt = int(p.get("deaths") or 0)
            if d_cnt >= 5:
                h_zh = p.get("hero_short_zh") or ""
                candidates.append({
                    "scope": "player",
                    "evidence": "measured",
                    "timestamp_sec": duration_sec,
                    "timestamp_str": duration_str,
                    "impact_score": float(d_cnt * 60),
                    "title": f"{h_zh}（{p.get('pos')}号位）全场阵亡 {d_cnt} 次（KDA {p.get('kills')}/{d_cnt}/{p.get('assists')}）",
                    "fact_evidence": f"截至 {duration_str}，{h_zh} 本局记录为 {p.get('kills')} 杀 {d_cnt} 死 {p.get('assists')} 助。",
                    "action_item": f"{h_zh} 需控制中后期阵亡次数，敌方抓人核心消失在视野时及时后撤。",
                })

        out[side] = select_top3_measured_fixes(candidates)
    return out


def build_top3_replay_moments(match: Dict[str, Any], report_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    F7 · 每场选出经济波动最大的 3 次团战，给出时间点和一句中性描述，供大家进客户端一起看录像。
    """
    key_tfs = report_dict.get("key_teamfights") or []
    raw_tfs = match.get("teamfights") or []
    moments_pool: List[Dict[str, Any]] = []

    if key_tfs:
        for tf in key_tfs:
            if not isinstance(tf, dict):
                continue
            start_s = int(tf.get("start_sec") or 0)
            end_s = int(tf.get("end_sec") or start_s)
            raw_swing = tf.get("net_swing_radiant")
            if raw_swing is None and isinstance(tf.get("gold_swing"), (int, float)):
                raw_swing = tf.get("gold_swing")
            swing = int(raw_swing or 0)
            rad_d = int(tf.get("rad_deaths") if tf.get("rad_deaths") is not None else (tf.get("radiant_deaths") or 0))
            dire_d = int(tf.get("dire_deaths") or 0)
            loc = str(tf.get("location_zh") or "团战交火区")
            tw = str(tf.get("time_range") or tf.get("time_window_str") or f"{_fmt_mmss(start_s)}–{_fmt_mmss(end_s)}")
            swing_side_zh = "天辉" if swing >= 0 else "夜魇"
            moments_pool.append({
                "start_sec": start_s,
                "end_sec": end_s,
                "timestamp_str": _fmt_mmss(start_s),
                "time_window_str": tw,
                "client_replay_time_str": f"客户端录像跳转时间点 {_fmt_mmss(start_s)}",
                "gold_swing": swing,
                "abs_gold_swing": abs(swing),
                "radiant_deaths": rad_d,
                "dire_deaths": dire_d,
                "location_zh": loc,
                "neutral_summary": (
                    f"[{tw}] {loc}，天辉阵亡 {rad_d} 人、夜魇阵亡 {dire_d} 人，"
                    f"经济向{swing_side_zh}变动 {abs(swing):,} 金。"
                ),
                "evidence": "measured",
            })
    elif raw_tfs:
        for tf in raw_tfs:
            if not isinstance(tf, dict):
                continue
            tf_p = tf.get("players") or []
            start_s = int(tf.get("start") or 0)
            end_s = int(tf.get("end") or start_s)
            rad_d = sum(1 for i in range(min(5, len(tf_p))) if int(tf_p[i].get("deaths") or 0) > 0)
            dire_d = sum(1 for i in range(5, min(10, len(tf_p))) if int(tf_p[i].get("deaths") or 0) > 0)
            rad_g = sum(int(tf_p[i].get("gold_delta") or 0) for i in range(min(5, len(tf_p))))
            dire_g = sum(int(tf_p[i].get("gold_delta") or 0) for i in range(5, min(10, len(tf_p))))
            swing = rad_g - dire_g
            tw = f"{_fmt_mmss(start_s)}–{_fmt_mmss(end_s)}"
            swing_side_zh = "天辉" if swing >= 0 else "夜魇"
            moments_pool.append({
                "start_sec": start_s,
                "end_sec": end_s,
                "timestamp_str": _fmt_mmss(start_s),
                "time_window_str": tw,
                "client_replay_time_str": f"客户端录像跳转时间点 {_fmt_mmss(start_s)}",
                "gold_swing": swing,
                "abs_gold_swing": abs(swing),
                "radiant_deaths": rad_d,
                "dire_deaths": dire_d,
                "location_zh": "团战交火区",
                "neutral_summary": (
                    f"[{tw}] 团战交火，天辉阵亡 {rad_d} 人、夜魇阵亡 {dire_d} 人，"
                    f"经济向{swing_side_zh}变动 {abs(swing):,} 金。"
                ),
                "evidence": "measured",
            })

    moments_pool.sort(key=lambda x: (x["abs_gold_swing"], x["radiant_deaths"] + x["dire_deaths"]), reverse=True)
    return [{"rank": idx, **m} for idx, m in enumerate(moments_pool[:3], start=1)]


def build_personal_trends_and_goals(
    reports: List[Dict[str, Any]],
    roster: Optional[Dict[str, Any]] = None,
    weekly_goals: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    F4 · 个人趋势和每周目标：
    每人随比赛变化的 4 条曲线：
    1. non_teamfight_deaths_after_10m: 10 分钟后团战外阵亡数
    2. lane_nw_diff_10m: 对真实对位的 10 分钟净值差
    3. support_wards_per_min: 辅助位每分钟插眼数（假眼+真眼/分钟，非辅助位为 None）
    4. key_item_timing_delta_sec: 关键装备完成时间相对本人中位数的偏差秒数
    并支持每人每周设定一个目标值，计算当前进度。
    """
    roster = roster or {}
    friends = roster.get("friends") or roster.get("teammates") or {}
    weekly_goals = weekly_goals or roster.get("weekly_goals") or {}
    allowed_aids = set()
    if roster.get("main_account_id"):
        try:
            allowed_aids.add(int(roster["main_account_id"]))
        except Exception:
            pass
    for k in friends.keys():
        try:
            allowed_aids.add(int(k))
        except Exception:
            pass
    for k in weekly_goals.keys():
        try:
            allowed_aids.add(int(k))
        except Exception:
            pass

    sorted_reports = sorted(
        [r for r in (reports or []) if isinstance(r, dict) and r.get("match_id")],
        key=lambda r: int(r.get("start_time") or r.get("match_id") or 0),
    )

    raw_series_by_acc: Dict[int, List[Dict[str, Any]]] = {}
    for rep in sorted_reports:
        mid = int(rep["match_id"])
        dur_min = float(rep.get("duration_min") or 0.0)
        is_parsed = bool(rep.get("is_parsed"))
        start_str = str(rep.get("start_time_str") or "")
        for side_key, list_key in (("radiant", "radiant_pos_1_to_5"), ("dire", "dire_pos_1_to_5")):
            opp_list = (
                rep.get("dire_pos_1_to_5") if side_key == "radiant" else rep.get("radiant_pos_1_to_5")
            ) or []
            for p in rep.get(list_key) or []:
                if not isinstance(p, dict) or not p.get("account_id"):
                    continue
                aid = int(p["account_id"])
                if allowed_aids and aid not in allowed_aids:
                    continue
                pos = int(p.get("pos") or 0)
                lane = int(p.get("raw_lane") or p.get("lane_id") or p.get("lane") or 0)

                # (1) 10 分钟后团战外阵亡数
                pt = p.get("phase_telemetry") or {}
                pickoffs = pt.get("solo_pickoffs")
                if is_parsed and isinstance(pickoffs, list):
                    non_tf_deaths_10m = sum(
                        1
                        for sp in pickoffs
                        if isinstance(sp, dict) and int(sp.get("time_sec") or sp.get("time") or 601) >= 600
                    )
                else:
                    non_tf_deaths_10m = None

                # (2) 对真实对位的 10 分钟净值差
                def _get_nw10(pl_item: Dict[str, Any]) -> Optional[float]:
                    if pl_item.get("net_worth_10m") is not None:
                        return float(pl_item["net_worth_10m"])
                    l10_obj = pl_item.get("laning_10m")
                    if isinstance(l10_obj, dict) and l10_obj.get("gold10") is not None:
                        return float(l10_obj["gold10"])
                    return None

                nw10 = _get_nw10(p)
                opp_same_lane = [
                    op
                    for op in opp_list
                    if int(op.get("raw_lane") or op.get("lane_id") or op.get("lane") or 0) == lane
                    and _get_nw10(op) is not None
                ]
                if is_parsed and nw10 is not None and opp_same_lane:
                    opp_avg_nw10 = sum(float(_get_nw10(op) or 0.0) for op in opp_same_lane) / len(opp_same_lane)
                    lane_nw_diff = round(float(nw10) - opp_avg_nw10, 1)
                else:
                    lane_nw_diff = None

                # (3) 辅助每分钟插眼数
                if pos in (4, 5) and dur_min > 0:
                    obs_p = int(p.get("obs_placed") or 0)
                    sen_p = int(p.get("sen_placed") or 0)
                    wards_per_min = round((obs_p + sen_p) / dur_min, 2)
                else:
                    wards_per_min = None

                # (4) 关键装备（BKB/跳刀/A杖等首件核心成装）时间秒数
                key_item_sec: Optional[int] = None
                for it in p.get("final_items_rich") or []:
                    if not isinstance(it, dict):
                        continue
                    ikey = str(it.get("key") or "")
                    p_sec = it.get("purchase_time_sec")
                    if p_sec is None and it.get("purchase_time_str"):
                        parts = str(it["purchase_time_str"]).split(":")
                        if len(parts) == 2 and parts[0].lstrip("-").isdigit() and parts[1].isdigit():
                            p_sec = int(parts[0]) * 60 + int(parts[1])
                    if ikey in ("black_king_bar", "blink", "ultimate_scepter", "manta", "bfury", "radiance", "force_staff", "glimmer_cape") and p_sec and int(p_sec) > 0:
                        key_item_sec = int(p_sec)
                        break

                raw_series_by_acc.setdefault(aid, []).append({
                    "match_id": mid,
                    "start_time_str": start_str,
                    "pos": pos,
                    "hero_short_zh": p.get("hero_short_zh") or "",
                    "non_teamfight_deaths_after_10m": non_tf_deaths_10m,
                    "lane_nw_diff_10m": lane_nw_diff,
                    "support_wards_per_min": wards_per_min,
                    "_raw_key_item_sec": key_item_sec,
                })

    players_trends: Dict[str, Any] = {}
    for aid, pts in raw_series_by_acc.items():
        item_secs = [pt["_raw_key_item_sec"] for pt in pts if pt.get("_raw_key_item_sec") is not None]
        median_item_sec = float(statistics.median(item_secs)) if item_secs else None
        points_out: List[Dict[str, Any]] = []
        for pt in pts:
            raw_sec = pt.get("_raw_key_item_sec")
            delta_sec = round(float(raw_sec) - median_item_sec, 1) if (raw_sec is not None and median_item_sec is not None) else None
            points_out.append({
                "match_id": pt["match_id"],
                "start_time_str": pt["start_time_str"],
                "pos": pt["pos"],
                "hero_short_zh": pt["hero_short_zh"],
                "non_teamfight_deaths_after_10m": pt["non_teamfight_deaths_after_10m"],
                "lane_nw_diff_10m": pt["lane_nw_diff_10m"],
                "support_wards_per_min": pt["support_wards_per_min"],
                "key_item_timing_delta_sec": delta_sec,
            })

        f_entry = friends.get(str(aid)) or {}
        p_name = f_entry.get("name", str(aid)) if isinstance(f_entry, dict) else str(f_entry or aid)

        # 每周目标计算
        goal_cfg = weekly_goals.get(str(aid)) or (f_entry.get("weekly_goal") if isinstance(f_entry, dict) else None)
        if not isinstance(goal_cfg, dict):
            # 默认按常打位置分配客观目标
            sup_vals = [x["support_wards_per_min"] for x in points_out if x["support_wards_per_min"] is not None]
            if len(sup_vals) >= len(points_out) / 2 and sup_vals:
                goal_cfg = {
                    "metric": "support_wards_per_min",
                    "label_zh": "辅助每分钟插眼数 >= 0.85",
                    "direction": "min",
                    "target": 0.85,
                }
            else:
                goal_cfg = {
                    "metric": "non_teamfight_deaths_after_10m",
                    "label_zh": "10分钟后团战外阵亡 <= 2.0 次/局",
                    "direction": "max",
                    "target": 2.0,
                }

        m_key = str(goal_cfg.get("metric") or "non_teamfight_deaths_after_10m")
        target_val = float(goal_cfg.get("target") or 2.0)
        direction = str(goal_cfg.get("direction") or ("min" if m_key in ("support_wards_per_min", "lane_nw_diff_10m") else "max"))
        recent_vals = [
            float(x[m_key])
            for x in points_out[-7:]
            if x.get(m_key) is not None
        ]
        current_avg = round(sum(recent_vals) / len(recent_vals), 2) if recent_vals else None
        if current_avg is None:
            achieved = None
            progress_pct = None
        elif direction == "min":
            achieved = current_avg >= target_val
            progress_pct = round(min(100.0, max(0.0, (current_avg / target_val) * 100.0)), 1) if target_val > 0 else 100.0
        else:
            achieved = current_avg <= target_val
            progress_pct = 100.0 if current_avg <= target_val else round(max(0.0, (target_val / max(current_avg, 0.01)) * 100.0), 1)

        players_trends[str(aid)] = {
            "account_id": aid,
            "personaname": p_name,
            "games_count": len(points_out),
            "median_key_item_sec": round(median_item_sec, 1) if median_item_sec is not None else None,
            "series": points_out,
            "weekly_goal": {
                "metric": m_key,
                "label_zh": goal_cfg.get("label_zh") or m_key,
                "direction": direction,
                "target": target_val,
                "current_avg": current_avg,
                "sample_games": len(recent_vals),
                "achieved": achieved,
                "progress_pct": progress_pct,
            },
        }

    return {"players": players_trends}


def compute_duration_and_session_tilt_buckets(
    player_match_rows: List[Dict[str, Any]],
    min_games: int = 10,
    session_gap_sec: int = 5400,
) -> Dict[str, Any]:
    """
    F6 · 时长画像和连打疲劳：
    1. 按比赛时长分桶 (<30m, 30-40m, 40-50m, >=50m) 的胜率
    2. 按“当晚第几局”分桶（两局开始时间间隔 < 90 分钟即 5400 秒算同一晚）的胜率
    所有分桶遵守 T1-9 最小样本量规则（< min_games 时 win_rate 为 None，标记 insufficient_sample=True）。
    """
    # 按 match_id 去重（同一场五黑只算一局团队对局，或按传入账号的对局序列去重）
    by_mid: Dict[int, Dict[str, Any]] = {}
    for r in player_match_rows or []:
        if not isinstance(r, dict) or not r.get("match_id"):
            continue
        mid = int(r["match_id"])
        if mid not in by_mid:
            by_mid[mid] = r

    matches_sorted = sorted(
        by_mid.values(),
        key=lambda x: (int(x.get("start_time") or 0), int(x.get("match_id") or 0)),
    )

    dur_defs = [
        ("under_30m", "<30 分钟", 0, 1800),
        ("30_to_40m", "30–40 分钟", 1800, 2400),
        ("40_to_50m", "40–50 分钟", 2400, 3000),
        ("over_50m", ">=50 分钟", 3000, 10**9),
    ]
    dur_counts = {k: {"key": k, "label_zh": lbl, "games": 0, "wins": 0} for k, lbl, _, _ in dur_defs}

    for m in matches_sorted:
        dur = int(m.get("duration") or 0)
        won = bool(m.get("won"))
        for k, _lbl, lo, hi in dur_defs:
            if lo <= dur < hi:
                dur_counts[k]["games"] += 1
                if won:
                    dur_counts[k]["wins"] += 1
                break

    duration_buckets: List[Dict[str, Any]] = []
    for k, _lbl, _, _ in dur_defs:
        b = dur_counts[k]
        g = b["games"]
        w = b["wins"]
        sufficient = g >= min_games
        duration_buckets.append({
            "key": k,
            "label_zh": b["label_zh"],
            "games": g,
            "wins": w,
            "losses": g - w,
            "win_rate": round(w * 100.0 / g, 1) if sufficient else None,
            "insufficient_sample": not sufficient,
        })

    # 按两局开始时间间隔 < 90 分钟 (5400s) 切分同一晚 Session
    session_defs = [
        (1, "当晚第 1 局"),
        (2, "当晚第 2 局"),
        (3, "当晚第 3 局"),
        (4, "当晚第 4+ 局"),
    ]
    sess_counts = {idx: {"game_index": idx, "label_zh": lbl, "games": 0, "wins": 0} for idx, lbl in session_defs}

    prev_start: Optional[int] = None
    cur_idx = 0
    for m in matches_sorted:
        st = int(m.get("start_time") or 0)
        won = bool(m.get("won"))
        if st <= 0:
            continue
        if prev_start is not None and 0 <= (st - prev_start) < session_gap_sec:
            cur_idx += 1
        else:
            cur_idx = 1
        prev_start = st
        bucket_idx = min(4, cur_idx)
        sess_counts[bucket_idx]["games"] += 1
        if won:
            sess_counts[bucket_idx]["wins"] += 1

    session_buckets: List[Dict[str, Any]] = []
    for idx, _lbl in session_defs:
        b = sess_counts[idx]
        g = b["games"]
        w = b["wins"]
        sufficient = g >= min_games
        session_buckets.append({
            "game_index": idx,
            "label_zh": b["label_zh"],
            "games": g,
            "wins": w,
            "losses": g - w,
            "win_rate": round(w * 100.0 / g, 1) if sufficient else None,
            "insufficient_sample": not sufficient,
        })

    return {
        "min_sample_games": min_games,
        "session_gap_minutes": round(session_gap_sec / 60.0, 1),
        "duration_buckets": duration_buckets,
        "session_game_buckets": session_buckets,
    }
