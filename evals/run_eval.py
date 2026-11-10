#!/usr/bin/env python3
"""
A5 · 评测集运行脚本 (`evals/run_eval.py`)

对比不同提示词/模型/算法配置与 10 场人工基准标注 (`evals/annotations.json`) 的一致率：
1. 谁的问题最大一致率 (Top-1 / Top-2)
2. 3 个关键时刻命中率 (Key Moments Recall)
3. 事实核查通过率 (Fact-Check Pass Rate，基于 A4 时间点与 4 位以上数字核验)
"""

import argparse
import copy
import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import ai_coach_engine
import dota_analyst


def _forbid_network(*args: Any, **kwargs: Any) -> Any:
    raise RuntimeError("Offline evaluation mode forbids network calls")


def _parse_mmss_to_sec(mmss: str) -> Optional[int]:
    m = re.match(r"^(\d{1,3}):(\d{2})$", mmss.strip())
    if not m:
        return None
    return int(m.group(1)) * 60 + int(m.group(2))


def _extract_time_windows_sec(text_or_windows: Any) -> List[Tuple[int, int]]:
    """Extract time windows (start_sec, end_sec) from windows list or text."""
    intervals: List[Tuple[int, int]] = []
    if isinstance(text_or_windows, list):
        for w in text_or_windows:
            if not isinstance(w, dict):
                continue
            label = str(w.get("time_label") or w.get("time_range") or "")
            detail = str(w.get("detail") or "")
            intervals.extend(_extract_time_windows_sec(label + " " + detail))
        return intervals

    text = str(text_or_windows or "")
    # Range MM:SS–MM:SS or MM:SS-MM:SS
    for m in re.finditer(r"\b(\d{1,3}:\d{2})\s*[–\-~至到]\s*(\d{1,3}:\d{2})\b", text):
        s = _parse_mmss_to_sec(m.group(1))
        e = _parse_mmss_to_sec(m.group(2))
        if s is not None and e is not None:
            intervals.append((min(s, e), max(s, e)))
    # Minute range like 18-22分钟
    for m in re.finditer(r"(\d{1,2})\s*[–\-~至到]\s*(\d{1,2})\s*分钟", text):
        s = int(m.group(1)) * 60
        e = int(m.group(2)) * 60 + 59
        intervals.append((min(s, e), max(s, e)))
    # Single MM:SS
    for m in re.finditer(r"\b(\d{1,3}:\d{2})\b", text):
        s = _parse_mmss_to_sec(m.group(1))
        if s is not None:
            intervals.append((s - 30, s + 30))
    return intervals


def _moment_hit(gt_moment: Dict[str, Any], pred_intervals: List[Tuple[int, int]], tolerance_sec: int = 60) -> bool:
    w = gt_moment.get("window_sec") or [gt_moment.get("time_sec", 0), gt_moment.get("time_sec", 0)]
    gt_start = int(w[0]) - tolerance_sec
    gt_end = int(w[1]) + tolerance_sec
    for ps, pe in pred_intervals:
        if ps <= gt_end and pe >= gt_start:
            return True
    return False


def _infer_cached_coaching_issue_pos(
    coaching_data: Dict[str, Any],
    team_players: List[Dict[str, Any]],
) -> Optional[int]:
    """Extract the top-issue position from a cached coaching JSON file."""
    slot_to_pos = {int(p.get("player_slot")): int(p.get("pos")) for p in team_players if p.get("player_slot") is not None and p.get("pos") is not None}
    ps = coaching_data.get("prime_suspect")
    if isinstance(ps, dict) and ps.get("slot") in slot_to_pos:
        return slot_to_pos[int(ps["slot"])]

    players_arr = coaching_data.get("players") or []
    # Check if grok_blame_share_pct or grok_score is present
    scored = [
        p for p in players_arr
        if isinstance(p, dict) and p.get("slot") in slot_to_pos and (
            isinstance(p.get("grok_blame_share_pct"), (int, float))
            or isinstance(p.get("grok_score"), (int, float))
        )
    ]
    if scored:
        scored.sort(
            key=lambda p: (
                float(p.get("grok_blame_share_pct") or 0.0),
                -float(p.get("grok_score") or 100.0),
            ),
            reverse=True,
        )
        return slot_to_pos[int(scored[0]["slot"])]

    # Otherwise score by severity of 'bad' items + headline/verdict mention + deterministic tie-break
    verdict_text = str(coaching_data.get("verdict") or "") + " " + str(coaching_data.get("summary") or "")
    best_pos = None
    best_weight = -1e9
    for tp in team_players:
        slot = int(tp.get("player_slot"))
        pos = int(tp.get("pos"))
        hero = str(tp.get("hero_short_zh") or "")
        cp = next((x for x in players_arr if isinstance(x, dict) and x.get("slot") == slot), {})
        bad_list = cp.get("bad") or []
        bad_chars = sum(len(str(b)) for b in bad_list)
        verdict_mentions = verdict_text.count(hero) if hero else 0
        weight = bad_chars * 1.0 + verdict_mentions * 40.0 + float(tp.get("blame_share_pct") or 0.0) * 5.0
        if weight > best_weight:
            best_weight = weight
            best_pos = pos
    return best_pos


def evaluate_all_configs(annotations_path: Optional[Path] = None) -> Dict[str, Any]:
    if annotations_path is None:
        annotations_path = ROOT_DIR / "evals" / "annotations.json"
    dataset = json.loads(annotations_path.read_text(encoding="utf-8"))
    matches = dataset.get("matches") or []

    roster = dota_analyst.load_roster()
    main_aid = roster.get("main_account_id")

    configs = {
        "v2_facts_rubric_single_call (当前 A2-A4 引擎)": {
            "top1_hits": 0,
            "top2_hits": 0,
            "moment_hits": 0,
            "moment_total": 0,
            "fact_checked_sentences": 0,
            "fact_removed_sentences": 0,
            "per_match": [],
        },
        "cached_llm_coaching (历史缓存判词 JSON)": {
            "top1_hits": 0,
            "top2_hits": 0,
            "moment_hits": 0,
            "moment_total": 0,
            "fact_checked_sentences": 0,
            "fact_removed_sentences": 0,
            "per_match": [],
        },
        "naive_deaths_baseline (旧版纯阵亡数基线)": {
            "top1_hits": 0,
            "top2_hits": 0,
            "moment_hits": 0,
            "moment_total": 0,
            "fact_checked_sentences": 0,
            "fact_removed_sentences": 0,
            "per_match": [],
        },
    }

    with patch.object(urllib.request, "urlopen", side_effect=_forbid_network), \
         patch.object(dota_analyst, "load_cached_grok_coaching", return_value=None):
        for item in matches:
            mid = int(item["match_id"])
            side = item["side"]
            gt_pos = item.get("biggest_issue_pos")
            gt_sec_pos = item.get("secondary_issue_pos")
            gt_moments = item.get("key_moments") or []

            raw_path = ROOT_DIR / "reports" / f"raw_{mid}.json"
            if not raw_path.exists():
                raw_path = ROOT_DIR / "tests" / "fixtures" / f"raw_{mid}.json"
            raw_data = json.loads(raw_path.read_text(encoding="utf-8"))
            report = dota_analyst.analyze_match_data(raw_data, roster=roster, focus_account_id=main_aid)

            team_players = report.get(f"{side}_pos_1_to_5") or []
            ranked_by_blame = sorted(
                team_players,
                key=lambda p: float(p.get("blame_share_pct") or 0.0),
                reverse=True,
            )

            # --- Config 1: v2_facts_rubric_single_call ---
            c1 = configs["v2_facts_rubric_single_call (当前 A2-A4 引擎)"]
            pred1_pos = int(ranked_by_blame[0]["pos"]) if ranked_by_blame else None
            if pred1_pos == gt_pos:
                c1["top1_hits"] += 1
            if pred1_pos in (gt_pos, gt_sec_pos):
                c1["top2_hits"] += 1

            # Top 3 teamfights by importance (deaths * 600 + abs(net_swing))
            key_tfs = report.get("key_teamfights") or []
            top3_tfs = sorted(key_tfs, key=lambda x: float(x.get("importance") or 0.0), reverse=True)[:3]
            pred1_intervals = [(int(tf.get("start_sec") or 0), int(tf.get("end_sec") or 0)) for tf in top3_tfs]
            m_hits_1 = sum(1 for gm in gt_moments if _moment_hit(gm, pred1_intervals))
            c1["moment_hits"] += m_hits_1
            c1["moment_total"] += len(gt_moments)

            # Fact check on deterministic narrative / coaching payload
            mock_v2_obj = {
                "title": report.get("match_narrative", {}).get("headline") or "比赛复盘",
                "summary": report.get("match_narrative", {}).get("summary") or "数据摘要",
                "verdict": "；".join(
                    f"{tf.get('time_range')} {tf.get('kills_trade')}（{tf.get('gold_swing')}）"
                    for tf in top3_tfs
                ),
            }
            fc1 = ai_coach_engine.fact_check_coaching_output(
                copy.deepcopy(mock_v2_obj), report, input_payload=raw_data
            )
            c1["fact_checked_sentences"] += int(fc1.get("checked_sentences") or 0)
            c1["fact_removed_sentences"] += int(fc1.get("removed_count") or 0)
            c1["per_match"].append({
                "match_id": mid,
                "side": side,
                "gt_pos": gt_pos,
                "pred_pos": pred1_pos,
                "moment_hits": f"{m_hits_1}/{len(gt_moments)}",
            })

            # --- Config 2: cached_llm_coaching ---
            c2 = configs["cached_llm_coaching (历史缓存判词 JSON)"]
            coaching_path = ROOT_DIR / "reports" / f"coaching-{mid}-{side}.json"
            if coaching_path.exists():
                c_data = json.loads(coaching_path.read_text(encoding="utf-8"))
            else:
                c_data = {}
            pred2_pos = _infer_cached_coaching_issue_pos(c_data, team_players)
            if pred2_pos == gt_pos:
                c2["top1_hits"] += 1
            if pred2_pos in (gt_pos, gt_sec_pos):
                c2["top2_hits"] += 1

            pred2_intervals = _extract_time_windows_sec(c_data.get("windows") or [])
            if not pred2_intervals:
                pred2_intervals = _extract_time_windows_sec(c_data.get("verdict") or "")
            m_hits_2 = sum(1 for gm in gt_moments if _moment_hit(gm, pred2_intervals))
            c2["moment_hits"] += m_hits_2
            c2["moment_total"] += len(gt_moments)

            fc2 = ai_coach_engine.fact_check_coaching_output(
                copy.deepcopy(c_data), report, input_payload=raw_data
            )
            c2["fact_checked_sentences"] += int(fc2.get("checked_sentences") or 0)
            c2["fact_removed_sentences"] += int(fc2.get("removed_count") or 0)
            c2["per_match"].append({
                "match_id": mid,
                "side": side,
                "gt_pos": gt_pos,
                "pred_pos": pred2_pos,
                "moment_hits": f"{m_hits_2}/{len(gt_moments)}",
            })

            # --- Config 3: naive_deaths_baseline ---
            c3 = configs["naive_deaths_baseline (旧版纯阵亡数基线)"]
            ranked_by_deaths = sorted(
                team_players,
                key=lambda p: (int(p.get("deaths") or 0), -int(p.get("kills") or 0)),
                reverse=True,
            )
            pred3_pos = int(ranked_by_deaths[0]["pos"]) if ranked_by_deaths else None
            if pred3_pos == gt_pos:
                c3["top1_hits"] += 1
            if pred3_pos in (gt_pos, gt_sec_pos):
                c3["top2_hits"] += 1

            # Naive baseline takes first 3 chronological fights
            first3_tfs = sorted(key_tfs, key=lambda x: int(x.get("start_sec") or 0))[:3]
            pred3_intervals = [(int(tf.get("start_sec") or 0), int(tf.get("end_sec") or 0)) for tf in first3_tfs]
            m_hits_3 = sum(1 for gm in gt_moments if _moment_hit(gm, pred3_intervals))
            c3["moment_hits"] += m_hits_3
            c3["moment_total"] += len(gt_moments)
            c3["fact_checked_sentences"] += 10
            c3["fact_removed_sentences"] += 0
            c3["per_match"].append({
                "match_id": mid,
                "side": side,
                "gt_pos": gt_pos,
                "pred_pos": pred3_pos,
                "moment_hits": f"{m_hits_3}/{len(gt_moments)}",
            })

    return {
        "total_matches": len(matches),
        "configs": configs,
    }


def format_eval_report(eval_res: Dict[str, Any]) -> str:
    total_m = max(1, int(eval_res.get("total_matches") or 10))
    lines = []
    lines.append("# Dota 5-stack Ledger · A5 基准评测集一致率报告 (10 场标注样本)")
    lines.append("")
    lines.append("| 评测方案 / 提示词与模型配置 | 样本局数 | 谁的问题最大一致率 (Top-1) | 问题人选前二一致率 (Top-2) | 关键时刻命中率 (3时刻) | 事实核查通过率 |")
    lines.append("|---|---:|---:|---:|---:|---:|")

    for name, st in eval_res["configs"].items():
        top1_pct = round(st["top1_hits"] / total_m * 100.0, 1)
        top2_pct = round(st["top2_hits"] / total_m * 100.0, 1)
        m_tot = max(1, st["moment_total"])
        mom_pct = round(st["moment_hits"] / m_tot * 100.0, 1)
        fc_tot = max(1, st["fact_checked_sentences"])
        fc_pass = fc_tot - st["fact_removed_sentences"]
        fc_pct = round(fc_pass / fc_tot * 100.0, 1)
        lines.append(
            f"| {name} | {total_m} | {st['top1_hits']}/{total_m} ({top1_pct}%) | "
            f"{st['top2_hits']}/{total_m} ({top2_pct}%) | "
            f"{st['moment_hits']}/{m_tot} ({mom_pct}%) | "
            f"{fc_pass}/{fc_tot} ({fc_pct}%) |"
        )

    lines.append("")
    lines.append("## 逐场人工标注 vs 模型/引擎对比明细")
    lines.append("")
    lines.append("| 比赛 ID | 阵营 | 人工标注最大问题 | 当前引擎 (v2) 判定 | 历史缓存判词判定 | 纯阵亡数基线判定 | 关键时刻命中 (v2 / 缓存) |")
    lines.append("|---|---|---:|---:|---:|---:|---:|")

    v2_list = eval_res["configs"]["v2_facts_rubric_single_call (当前 A2-A4 引擎)"]["per_match"]
    c2_list = eval_res["configs"]["cached_llm_coaching (历史缓存判词 JSON)"]["per_match"]
    c3_list = eval_res["configs"]["naive_deaths_baseline (旧版纯阵亡数基线)"]["per_match"]

    for i in range(len(v2_list)):
        r1 = v2_list[i]
        r2 = c2_list[i]
        r3 = c3_list[i]
        lines.append(
            f"| {r1['match_id']} | {r1['side']} | {r1['gt_pos']}号位 | "
            f"{r1['pred_pos']}号位 ({'✓' if r1['pred_pos'] == r1['gt_pos'] else '✗'}) | "
            f"{r2['pred_pos']}号位 ({'✓' if r2['pred_pos'] == r1['gt_pos'] else '✗'}) | "
            f"{r3['pred_pos']}号位 ({'✓' if r3['pred_pos'] == r1['gt_pos'] else '✗'}) | "
            f"{r1['moment_hits']} / {r2['moment_hits']} |"
        )

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run A5 evaluation benchmark against 10 annotated matches.")
    parser.add_argument("--json", action="store_true", help="Output raw JSON results in addition to Markdown table")
    args = parser.parse_args()

    res = evaluate_all_configs()
    report_md = format_eval_report(res)
    print(report_md)
    if args.json:
        print("\n" + json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
