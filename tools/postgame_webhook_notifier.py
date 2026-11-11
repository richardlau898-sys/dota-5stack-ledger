#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
F8 · 赛后自动推送（D5 Webhook）
检查花名册成员的新比赛，请求 OpenDota 解析，解析完成后生成报告，
并将赛后摘要（比分、时长、下一把要改的 3 件事、3 个复盘时刻、报告链接）推送到群 Webhook。
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import cloud_store  # noqa: E402
import dota_analyst  # noqa: E402

DEFAULT_PUBLIC_APP_URL = "https://dota-ai-analyst.vercel.app"


def _default_fetch_recent(account_id: int) -> List[Dict[str, Any]]:
    data = dota_analyst.api_get(f"/players/{int(account_id)}/recentMatches")
    return data if isinstance(data, list) else []


def _default_fetch_match(match_id: int) -> Dict[str, Any]:
    data = dota_analyst.api_get(f"/matches/{int(match_id)}")
    return data if isinstance(data, dict) else {}


def _default_request_parse(match_id: int) -> Dict[str, Any]:
    data = dota_analyst.api_post(f"/request/{int(match_id)}")
    return data if isinstance(data, dict) else {}


def _default_send_webhook(webhook_url: str, payload: Dict[str, Any]) -> bool:
    if not webhook_url:
        return False
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=body,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "dota-ai-analyst-webhook/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return 200 <= int(getattr(resp, "status", 200)) < 300


def load_notified_state(state_path: Optional[Path] = None) -> Dict[str, Any]:
    ids = set(cloud_store.cloud_load_notified_match_ids())
    if state_path and state_path.exists():
        try:
            data = json.loads(state_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for x in data.get("notified_match_ids") or []:
                    if str(x).isdigit():
                        ids.add(int(x))
        except Exception:
            pass
    return {"notified_match_ids": sorted(ids)}


def save_notified_state(state_path: Optional[Path], state: Dict[str, Any]) -> None:
    ids = {int(x) for x in (state.get("notified_match_ids") or []) if str(x).isdigit()}
    cloud_store.cloud_save_notified_match_ids(ids)
    if state_path:
        try:
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(
                json.dumps({"notified_match_ids": sorted(ids)}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass


def build_postgame_webhook_payload(report: Dict[str, Any], base_app_url: str) -> Dict[str, Any]:
    mid = int(report.get("match_id") or 0)
    base_clean = (base_app_url or DEFAULT_PUBLIC_APP_URL).rstrip("/")
    report_url = f"{base_clean}/?match={mid}"

    score_str = f"天辉 {report.get('radiant_score', 0)} : {report.get('dire_score', 0)} 夜魇"
    dur_str = str(report.get("duration_str") or "")
    res_str = str(report.get("user_result_str") or ("天辉获胜" if report.get("radiant_win") else "夜魇获胜"))
    top3_fixes = report.get("next_game_top3_fixes") or []
    top3_moments = report.get("top3_replay_moments") or []

    fix_lines = [
        f"  {idx}. [{f.get('timestamp_str', '')}] {f.get('title', '')} → {f.get('action_item', '')}"
        for idx, f in enumerate(top3_fixes[:3], start=1)
    ]
    moment_lines = [
        f"  #{m.get('rank', idx)} {m.get('neutral_summary', '')}"
        for idx, m in enumerate(top3_moments[:3], start=1)
    ]

    summary_lines = [
        f"📊 【战后算账 · 比赛 #{mid} 自动复盘简报】",
        f"• 结果：{res_str} ｜ 比分：{score_str} ｜ 时长：{dur_str}",
    ]
    if fix_lines:
        summary_lines.append("🔧 下一把要改的 3 件事（实测证据）：")
        summary_lines.extend(fix_lines)
    if moment_lines:
        summary_lines.append("🎬 本场 3 个关键复盘时刻：")
        summary_lines.extend(moment_lines)
    summary_lines.append(f"🔗 完整复盘报告链接：{report_url}")

    content_text = "\n".join(summary_lines)
    return {
        "match_id": mid,
        "report_url": report_url,
        "score_str": score_str,
        "duration_str": dur_str,
        "result_str": res_str,
        "next_game_top3_fixes": top3_fixes[:3],
        "top3_replay_moments": top3_moments[:3],
        "content": content_text,
        "text": content_text,
        "msg_type": "text",
    }


def run_postgame_notification_cycle(
    roster: Optional[Dict[str, Any]] = None,
    webhook_url: Optional[str] = None,
    base_app_url: Optional[str] = None,
    state_path: Optional[Path] = None,
    reports_dir: Optional[Path] = None,
    fetch_recent_fn: Callable[[int], List[Dict[str, Any]]] = _default_fetch_recent,
    fetch_match_fn: Callable[[int], Dict[str, Any]] = _default_fetch_match,
    request_parse_fn: Callable[[int], Dict[str, Any]] = _default_request_parse,
    send_webhook_fn: Callable[[str, Dict[str, Any]], bool] = _default_send_webhook,
    poll_wait_sec: float = 2.0,
    max_matches_per_cycle: int = 3,
) -> Dict[str, Any]:
    webhook_clean = (webhook_url if webhook_url is not None else os.environ.get("POSTGAME_WEBHOOK_URL", "")).strip()
    if not webhook_clean:
        return {
            "skipped_no_webhook": True,
            "checked_candidates": 0,
            "notified_count": 0,
            "notified_match_ids": [],
        }

    roster = roster or dota_analyst.load_roster()
    base_app_url = (base_app_url or os.environ.get("PUBLIC_APP_URL") or DEFAULT_PUBLIC_APP_URL).strip()
    reports_dir = reports_dir or (REPO_ROOT / "reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    state = load_notified_state(state_path)
    notified_set = {int(x) for x in (state.get("notified_match_ids") or []) if str(x).isdigit()}

    roster_members = dota_analyst.iter_roster_accounts(roster)
    main_aid = next(
        (int(m["canonical_id"]) for m in roster_members if m.get("is_main")),
        int(roster.get("main_account_id") or 0),
    )
    account_ids: List[int] = []
    for m in roster_members:
        for aid in m["account_ids"]:
            if aid > 0 and aid not in account_ids:
                account_ids.append(aid)

    candidate_mids: List[int] = []
    for aid in account_ids:
        try:
            recent = fetch_recent_fn(aid) or []
        except Exception as exc:
            sys.stderr.write(f"[postgame_webhook] fetch_recent failed for {aid}: {exc}\n")
            recent = []
        for m in recent[:5]:
            mid = int(m.get("match_id") or 0)
            if mid > 0 and mid not in notified_set and mid not in candidate_mids:
                candidate_mids.append(mid)

    notified_now: List[int] = []
    for mid in candidate_mids[:max_matches_per_cycle]:
        raw_match = fetch_match_fn(mid)
        if not raw_match or not raw_match.get("match_id"):
            continue
        if not raw_match.get("version"):
            try:
                request_parse_fn(mid)
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                sys.stderr.write(f"[postgame_webhook] request_parse network error for {mid}: {exc}\n")
            if poll_wait_sec > 0:
                time.sleep(poll_wait_sec)
            refetched = fetch_match_fn(mid)
            if isinstance(refetched, dict) and refetched.get("match_id"):
                raw_match = refetched

        report = dota_analyst.analyze_match_data(raw_match, roster, focus_account_id=main_aid or None)
        raw_out = reports_dir / f"raw_{mid}.json"
        rep_out = reports_dir / f"match_{mid}.json"
        try:
            raw_out.write_text(json.dumps(raw_match, ensure_ascii=False), encoding="utf-8")
            rep_out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

        payload = build_postgame_webhook_payload(report, base_app_url)
        sent_ok = send_webhook_fn(webhook_clean, payload)
        if sent_ok:
            notified_set.add(mid)
            notified_now.append(mid)

    state["notified_match_ids"] = sorted(notified_set)
    save_notified_state(state_path, state)
    return {
        "checked_candidates": len(candidate_mids),
        "notified_count": len(notified_now),
        "notified_match_ids": notified_now,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check roster new matches, parse, generate report, and push webhook.")
    parser.add_argument("--webhook-url", default=os.environ.get("POSTGAME_WEBHOOK_URL", ""), help="Webhook URL")
    parser.add_argument("--base-url", default=os.environ.get("PUBLIC_APP_URL", ""), help="Public base URL for report links")
    args = parser.parse_args()

    result = run_postgame_notification_cycle(
        webhook_url=args.webhook_url,
        base_app_url=args.base_url or DEFAULT_PUBLIC_APP_URL,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
