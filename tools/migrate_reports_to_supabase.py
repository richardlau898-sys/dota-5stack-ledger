#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P3: 将现有本地 reports/ 下的复盘报告与原始比赛 JSON 迁移至 Supabase (dota_match_reports, match_players, Storage)
自动检测并重算旧版本 (engine_version != ENGINE_VERSION) 的报告。
"""

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from cloud_store import (
    cloud_save_coaching,
    cloud_save_match_report,
    cloud_save_raw_match,
    extract_match_players_rows,
    get_cloud_config,
)
from dota_analyst import ENGINE_VERSION, REPORTS_DIR, analyze_match_data, load_roster
from dota_constants_zh import sanitize_report_mixed_english


def migrate_all(reports_dir: Path = REPORTS_DIR, dry_run: bool = False) -> dict:
    roster = load_roster()
    main_aid = roster.get("main_account_id")
    cfg = get_cloud_config()
    has_supabase = bool(cfg.get("supabase_url") and cfg.get("supabase_key"))

    raw_files = {
        int(p.stem.split("_", 1)[1]): p
        for p in sorted(reports_dir.glob("raw_*.json"))
        if p.stem.split("_", 1)[1].isdigit()
    }
    match_files = {
        int(p.stem.split("_", 1)[1]): p
        for p in sorted(reports_dir.glob("match_*.json"))
        if p.stem.split("_", 1)[1].isdigit()
    }
    all_mids = sorted(set(raw_files.keys()) | set(match_files.keys()))

    stats = {
        "total_matches": len(all_mids),
        "rebuilt_stale": 0,
        "reports_migrated": 0,
        "raw_uploaded": 0,
        "player_rows_prepared": 0,
        "coaching_uploaded": 0,
        "failed_uploads": 0,
        "dry_run": dry_run,
        "supabase_configured": has_supabase,
    }

    for mid in all_mids:
        raw_data = None
        if mid in raw_files:
            try:
                raw_data = json.loads(raw_files[mid].read_text(encoding="utf-8"))
            except Exception:
                raw_data = None

        rep_data = None
        if mid in match_files:
            try:
                rep_data = json.loads(match_files[mid].read_text(encoding="utf-8"))
            except Exception:
                rep_data = None

        need_rebuild = (
            not isinstance(rep_data, dict)
            or rep_data.get("engine_version") != ENGINE_VERSION
            or not isinstance((rep_data.get("deep_forensics") or {}).get("minute_snapshots"), dict)
        )
        if need_rebuild and isinstance(raw_data, dict) and raw_data.get("match_id"):
            existing_grok = rep_data.get("grok_coaching") if isinstance(rep_data, dict) else None
            rep_data = analyze_match_data(raw_data, roster, focus_account_id=main_aid)
            if isinstance(existing_grok, dict) and existing_grok.get("title"):
                rep_data["grok_coaching"] = sanitize_report_mixed_english(existing_grok)
            stats["rebuilt_stale"] += 1

        if isinstance(rep_data, dict) and rep_data.get("match_id"):
            p_rows = extract_match_players_rows(rep_data)
            stats["player_rows_prepared"] += len(p_rows)
            if dry_run:
                stats["reports_migrated"] += 1
            elif has_supabase:
                if cloud_save_match_report(mid, rep_data):
                    stats["reports_migrated"] += 1
                else:
                    stats["failed_uploads"] += 1
            else:
                stats["failed_uploads"] += 1

        if isinstance(raw_data, dict) and raw_data.get("match_id"):
            if dry_run:
                stats["raw_uploaded"] += 1
            elif has_supabase:
                if cloud_save_raw_match(mid, raw_data):
                    stats["raw_uploaded"] += 1
                else:
                    stats["failed_uploads"] += 1
            else:
                stats["failed_uploads"] += 1

    for c_path in sorted(reports_dir.glob("coaching-*.json")):
        parts = c_path.stem.split("-")
        if len(parts) == 3 and parts[1].isdigit():
            mid = int(parts[1])
            side = parts[2]
            try:
                c_obj = json.loads(c_path.read_text(encoding="utf-8"))
                if isinstance(c_obj, dict):
                    if dry_run:
                        stats["coaching_uploaded"] += 1
                    elif has_supabase:
                        if cloud_save_coaching(mid, side, c_obj):
                            stats["coaching_uploaded"] += 1
                        else:
                            stats["failed_uploads"] += 1
                    else:
                        stats["failed_uploads"] += 1
            except Exception:
                pass

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate match reports & raw JSONs to Supabase")
    parser.add_argument("--dry-run", action="store_true", help="Validate & rebuild without network calls")
    parser.add_argument("--reports-dir", default=None, help="Optional custom reports directory")
    args = parser.parse_args()
    target_dir = Path(args.reports_dir) if args.reports_dir else REPORTS_DIR
    summary = migrate_all(target_dir, dry_run=args.dry_run)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not args.dry_run:
        if not summary.get("supabase_configured"):
            sys.stderr.write("ERROR: Supabase 未配置（缺少 SUPABASE_URL 或 SUPABASE_SERVICE_ROLE_KEY），迁移未执行。\n")
            return 1
        if summary.get("failed_uploads", 0) > 0 or (
            summary.get("total_matches", 0) > 0 and summary.get("reports_migrated", 0) == 0
        ):
            sys.stderr.write("ERROR: 连接或写入 Supabase 失败，存在未成功上传的记录。\n")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
