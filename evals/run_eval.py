#!/usr/bin/env python3
"""
A5 / R0-2 · 评测集运行脚本 (`evals/run_eval.py`)

仅在人工标注文件由 Richard 填写完成（annotated_by 确认为 Richard）时输出一致率指标；
未填写时拒绝输出任何一致率百分比，只提示「尚未人工标注」。
评测对象为已保存的 AI 判词（默认离线）和真实的 LLM 调用（--live 开关，由 Richard 本人运行）。
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
    raise RuntimeError("Offline evaluation mode forbids network calls (pass --live to call LLM)")


def _parse_mmss_to_sec(mmss: str) -> Optional[int]:
    m = re.match(r"^(\d{1,3}):(\d{2})$", str(mmss or "").strip())
    if not m:
        return None
    return int(m.group(1)) * 60 + int(m.group(2))


def _extract_time_windows_sec(text_or_windows: Any) -> List[Tuple[int, int]]:
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
    for m in re.finditer(r"\b(\d{1,3}:\d{2})\s*[–\-~至到]\s*(\d{1,3}:\d{2})\b", text):
        s = _parse_mmss_to_sec(m.group(1))
        e = _parse_mmss_to_sec(m.group(2))
        if s is not None and e is not None:
            intervals.append((min(s, e), max(s, e)))
    for m in re.finditer(r"(\d{1,2})\s*[–\-~至到]\s*(\d{1,2})\s*分钟", text):
        s = int(m.group(1)) * 60
        e = int(m.group(2)) * 60 + 59
        intervals.append((min(s, e), max(s, e)))
    for m in re.finditer(r"\b(\d{1,3}:\d{2})\b", text):
        s = _parse_mmss_to_sec(m.group(1))
        if s is not None:
            intervals.append((s - 30, s + 30))
    return intervals


def _moment_hit(gt_moment: Dict[str, Any], pred_intervals: List[Tuple[int, int]], tolerance_sec: int = 60) -> bool:
    w = gt_moment.get("window_sec")
    if isinstance(w, list) and len(w) == 2:
        gt_start = int(w[0]) - tolerance_sec
        gt_end = int(w[1]) + tolerance_sec
    else:
        ts = gt_moment.get("time_sec")
        if ts is None:
            ts = _parse_mmss_to_sec(str(gt_moment.get("time_str") or ""))
        if ts is None:
            return False
        gt_start = int(ts) - tolerance_sec
        gt_end = int(ts) + tolerance_sec
    for ps, pe in pred_intervals:
        if ps <= gt_end and pe >= gt_start:
            return True
    return False


def _infer_coaching_issue_pos(
    coaching_data: Dict[str, Any],
    team_players: List[Dict[str, Any]],
) -> Optional[int]:
    slot_to_pos = {
        int(p.get("player_slot")): int(p.get("pos"))
        for p in team_players
        if p.get("player_slot") is not None and p.get("pos") is not None
    }
    ps = coaching_data.get("prime_suspect")
    if isinstance(ps, dict) and ps.get("slot") in slot_to_pos:
        return slot_to_pos[int(ps["slot"])]

    players_arr = coaching_data.get("players") or []
    scored = [
        p
        for p in players_arr
        if isinstance(p, dict)
        and p.get("slot") in slot_to_pos
        and (
            isinstance(p.get("grok_blame_share_pct"), (int, float))
            or isinstance(p.get("grok_share_pct"), (int, float))
            or isinstance(p.get("grok_score"), (int, float))
        )
    ]
    if scored:
        scored.sort(
            key=lambda p: (
                -float(p.get("grok_score") if p.get("grok_score") is not None else 100.0),
                float(p.get("grok_blame_share_pct") or p.get("grok_share_pct") or 0.0),
            ),
            reverse=True,
        )
        return slot_to_pos[int(scored[0]["slot"])]
    return None


def _is_annotated_by_richard(matches: List[Dict[str, Any]]) -> bool:
    if not matches:
        return False
    for m in matches:
        annotator = str(m.get("annotated_by") or "").strip().lower()
        if annotator != "richard":
            return False
        reason = str(m.get("reason") or m.get("biggest_issue_reason_zh") or "").strip()
        if not reason:
            return False
        kms = m.get("key_moments") or []
        if not isinstance(kms, list) or len(kms) == 0:
            return False
        if not any(str(km.get("time_str") or "").strip() for km in kms if isinstance(km, dict)):
            return False
    return True


def _score_coaching_against_gt(
    bucket: Dict[str, Any],
    c_data: Dict[str, Any],
    item: Dict[str, Any],
    report: Dict[str, Any],
    raw_data: Dict[str, Any],
    team_players: List[Dict[str, Any]],
) -> None:
    mid = int(item["match_id"])
    side = item["side"]
    gt_pos = item.get("biggest_issue_pos")
    gt_sec_pos = item.get("secondary_issue_pos")
    gt_moments = item.get("key_moments") or []

    pred_pos = _infer_coaching_issue_pos(c_data, team_players)
    if pred_pos == gt_pos:
        bucket["top1_hits"] += 1
    if pred_pos in (gt_pos, gt_sec_pos):
        bucket["top2_hits"] += 1

    pred_intervals = _extract_time_windows_sec(c_data.get("windows") or [])
    if not pred_intervals:
        pred_intervals = _extract_time_windows_sec(c_data.get("verdict") or "")
    m_hits = sum(1 for gm in gt_moments if _moment_hit(gm, pred_intervals))
    bucket["moment_hits"] += m_hits
    bucket["moment_total"] += len(gt_moments)

    fc = ai_coach_engine.fact_check_coaching_output(
        copy.deepcopy(c_data), report, input_payload=raw_data
    )
    bucket["fact_checked_sentences"] += int(fc.get("checked_sentences") or 0)
    bucket["fact_removed_sentences"] += int(fc.get("removed_count") or 0)
    bucket["per_match"].append({
        "match_id": mid,
        "side": side,
        "gt_pos": gt_pos,
        "pred_pos": pred_pos,
        "moment_hits": f"{m_hits}/{len(gt_moments)}",
    })


def evaluate_all_configs(
    annotations_path: Optional[Path] = None,
    live: bool = False,
) -> Dict[str, Any]:
    if annotations_path is None:
        annotations_path = ROOT_DIR / "evals" / "annotations_template.json"
    dataset = json.loads(annotations_path.read_text(encoding="utf-8"))
    if "引擎输出" in str(dataset.get("source_note") or ""):
        return {"annotated": False, "message": "尚未人工标注"}
    matches = dataset.get("matches") or []
    if not _is_annotated_by_richard(matches):
        return {"annotated": False, "message": "尚未人工标注"}

    roster = dota_analyst.load_roster()
    main_aid = roster.get("main_account_id")

    configs: Dict[str, Dict[str, Any]] = {
        "saved_ai_coaching (已保存的 AI 判词)": {
            "top1_hits": 0,
            "top2_hits": 0,
            "moment_hits": 0,
            "moment_total": 0,
            "fact_checked_sentences": 0,
            "fact_removed_sentences": 0,
            "per_match": [],
        },
    }
    if live:
        configs["live_llm_coaching (实时 LLM 调用)"] = {
            "top1_hits": 0,
            "top2_hits": 0,
            "moment_hits": 0,
            "moment_total": 0,
            "fact_checked_sentences": 0,
            "fact_removed_sentences": 0,
            "per_match": [],
        }

    net_ctx = (
        patch.object(dota_analyst, "load_cached_grok_coaching", return_value=None)
        if live
        else patch.object(urllib.request, "urlopen", side_effect=_forbid_network)
    )
    with net_ctx:
        for item in matches:
            mid = int(item["match_id"])
            side = item["side"]
            raw_path = ROOT_DIR / "reports" / f"raw_{mid}.json"
            if not raw_path.exists():
                raw_path = ROOT_DIR / "tests" / "fixtures" / f"raw_{mid}.json"
            raw_data = json.loads(raw_path.read_text(encoding="utf-8"))
            with patch.object(dota_analyst, "load_cached_grok_coaching", return_value=None):
                report = dota_analyst.analyze_match_data(raw_data, roster=roster, focus_account_id=main_aid)
            report["focus_side"] = side
            team_players = report.get(f"{side}_pos_1_to_5") or []

            coaching_path = ROOT_DIR / "reports" / f"coaching-{mid}-{side}.json"
            c_saved = json.loads(coaching_path.read_text(encoding="utf-8")) if coaching_path.exists() else {}
            _score_coaching_against_gt(
                configs["saved_ai_coaching (已保存的 AI 判词)"],
                c_saved,
                item,
                report,
                raw_data,
                team_players,
            )

            if live:
                live_res = ai_coach_engine.call_llm_coach_review(copy.deepcopy(report))
                c_live = (live_res.get("structured") or {}) if isinstance(live_res, dict) and live_res.get("ok") else {}
                _score_coaching_against_gt(
                    configs["live_llm_coaching (实时 LLM 调用)"],
                    c_live,
                    item,
                    report,
                    raw_data,
                    team_players,
                )

    return {
        "annotated": True,
        "total_matches": len(matches),
        "configs": configs,
    }


def format_eval_report(eval_res: Dict[str, Any]) -> str:
    if not eval_res.get("annotated"):
        return str(eval_res.get("message") or "尚未人工标注")

    total_m = max(1, int(eval_res.get("total_matches") or 10))
    lines = [
        "# 评测集一致率报告（Richard 人工标注基准）",
        "",
        "| 评测对象 | 样本局数 | 谁的问题最大一致率 (Top-1) | 前二一致率 (Top-2) | 关键时刻命中率 (3时刻) | 事实核查通过率 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, st in eval_res["configs"].items():
        top1_pct = round(st["top1_hits"] / total_m * 100.0, 1)
        top2_pct = round(st["top2_hits"] / total_m * 100.0, 1)
        m_tot = max(1, st["moment_total"])
        mom_pct = round(st["moment_hits"] / m_tot * 100.0, 1)
        fc_tot = st["fact_checked_sentences"]
        if fc_tot > 0:
            fc_pass = fc_tot - st["fact_removed_sentences"]
            fc_str = f"{fc_pass}/{fc_tot} ({round(fc_pass / fc_tot * 100.0, 1)}%)"
        else:
            fc_str = "无数据"
        lines.append(
            f"| {name} | {total_m} | {st['top1_hits']}/{total_m} ({top1_pct}%) | "
            f"{st['top2_hits']}/{total_m} ({top2_pct}%) | "
            f"{st['moment_hits']}/{m_tot} ({mom_pct}%) | "
            f"{fc_str} |"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run evaluation benchmark against Richard's human-annotated matches.")
    parser.add_argument("--annotations", type=Path, default=None, help="Path to human annotations JSON")
    parser.add_argument("--live", action="store_true", help="Invoke live LLM calls (run manually by Richard)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON results")
    args = parser.parse_args()

    res = evaluate_all_configs(annotations_path=args.annotations, live=args.live)
    print(format_eval_report(res))
    if args.json and res.get("annotated"):
        print("\n" + json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
