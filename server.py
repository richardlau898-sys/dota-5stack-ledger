#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dota 2 战后算账 & 录像级复盘工作台 - Web 后端服务 (server.py)
基于 Python 标准库 http.server，零外部依赖，默认自动接入 .env.local 中的 xAI Grok (grok-4.7)。
API 路由:
- GET  /api/init                   -> 获取主账号花名册、模型状态、最近比赛列表及最新比赛完整复盘
- GET  /api/recent?account_id=...  -> 获取指定玩家最近比赛列表（支持好友ID / Steam64 / Steam主页URL）
- GET  /api/match/<match_id>       -> 获取单场比赛的完整 1-5 号位深度复盘 JSON
- POST /api/parse/<match_id>       -> 请求 OpenDota 深度解析该比赛录像
- POST /api/roster                 -> 更新主账号或好友备注/位置
- POST /api/llm_review             -> 调用 xAI Grok (grok-4.7) / Gemini / OpenAI 生成结构化赛后算账 JSON
"""

import datetime
import json
import mimetypes
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional

from ai_coach_engine import call_llm_coach_review, call_llm_pregame_coach, get_llm_status_safe
from cloud_store import (
    cloud_fetch_match_report,
    cloud_save_coaching,
    cloud_save_match_report,
    get_cloud_analyzed_match_ids,
    get_cloud_db_status_safe,
)
from dota_analyst import (
    REPORTS_DIR,
    STEAM64_OFFSET,
    analyze_match_data,
    api_get,
    api_post,
    format_duration,
    get_hero_constants_map,
    load_roster,
    normalize_account_id,
    render_markdown_report,
    save_roster,
)
from dota_constants_zh import get_hero_name, get_mode_and_lobby, sanitize_report_mixed_english
from draft_and_phase_coach import build_pregame_strategy_plan, build_squad_history_ledger

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


def resolve_player_input(raw_input: str) -> int:
    """
    支持用户输入:
    1. Dota 2 好友 ID (Steam32, 如 86080912)
    2. Steam64 ID (如 76561198046346640)
    3. Steam 个人主页 URL (如 https://steamcommunity.com/id/richardlau898/ 或 /profiles/76561198...)
    """
    s = raw_input.strip()
    if "steamcommunity.com/profiles/" in s:
        m = re.search(r"steamcommunity\.com/profiles/(\d+)", s)
        if m:
            return normalize_account_id(m.group(1))
    if "steamcommunity.com/id/" in s or not s.isdigit():
        url = s if s.startswith("http") else f"https://steamcommunity.com/id/{s.strip('/')}"
        xml_url = url.split("?")[0].rstrip("/") + "/?xml=1"
        req = urllib.request.Request(xml_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            xml_data = resp.read().decode("utf-8", errors="ignore")
        root = ET.fromstring(xml_data)
        steam64_txt = root.findtext("steamID64")
        if not steam64_txt:
            raise ValueError(f"无法从 Steam 链接解析出 steamID64: {raw_input}")
        return normalize_account_id(steam64_txt)
    return normalize_account_id(s)


TMP_REPORTS_DIR = Path("/tmp/dota_reports")


def is_match_already_analyzed(match_id: Any) -> bool:
    if not match_id:
        return False
    mid = int(match_id)
    if (
        (REPORTS_DIR / f"match_{mid}.json").exists()
        or (TMP_REPORTS_DIR / f"match_{mid}.json").exists()
    ):
        return True
    return mid in get_cloud_analyzed_match_ids()


_RECENT_MATCHES_CACHE: Dict[int, Dict[str, Any]] = {}


def fetch_recent_matches_formatted(account_id: int, limit: int = 12) -> list:
    import time

    now_ts = time.time()
    cached = _RECENT_MATCHES_CACHE.get(account_id)
    if cached and (now_ts - cached.get("ts", 0) < 120) and cached.get("items"):
        out_cached = cached["items"]
        for item in out_cached:
            item["is_analyzed"] = is_match_already_analyzed(item.get("match_id"))
        return out_cached[:limit]

    hero_map, _ = get_hero_constants_map()
    recent_cache_file = REPORTS_DIR / f"recent_matches_{account_id}.json"
    tmp_recent_cache_file = TMP_REPORTS_DIR / f"recent_matches_{account_id}.json"

    raw_list = None
    try:
        raw_list = api_get(f"/players/{account_id}/recentMatches")
        if isinstance(raw_list, list) and raw_list:
            try:
                REPORTS_DIR.mkdir(parents=True, exist_ok=True)
                recent_cache_file.write_text(json.dumps(raw_list, ensure_ascii=False), encoding="utf-8")
            except OSError:
                TMP_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
                tmp_recent_cache_file.write_text(json.dumps(raw_list, ensure_ascii=False), encoding="utf-8")
    except Exception:
        for cf in (recent_cache_file, tmp_recent_cache_file):
            if cf.exists():
                try:
                    raw_list = json.loads(cf.read_text(encoding="utf-8"))
                    break
                except Exception:
                    raw_list = None

    out = []
    for m in (raw_list or [])[:limit]:
        mid = m.get("match_id")
        is_rad = (m.get("player_slot", 0) < 128)
        won = (is_rad and m.get("radiant_win")) or (not is_rad and not m.get("radiant_win"))
        start_time = m.get("start_time") or 0
        dt_str = (
            datetime.datetime.fromtimestamp(start_time).strftime("%m-%d %H:%M")
            if start_time
            else ""
        )
        psize = m.get("party_size") or 1
        hid = int(m.get("hero_id") or 0)
        hinfo = hero_map.get(hid) or {}
        out.append({
            "match_id": mid,
            "start_time_str": dt_str,
            "won": bool(won),
            "result": "胜利" if won else "失败",
            "hero_id": hid,
            "hero_name": get_hero_name(hid),
            "hero_short_zh": hinfo.get("short_zh") or get_hero_name(hid),
            "hero_img": hinfo.get("img") or "",
            "hero_icon": hinfo.get("icon") or "",
            "kills": m.get("kills", 0),
            "deaths": m.get("deaths", 0),
            "assists": m.get("assists", 0),
            "kda": f"{m.get('kills',0)}/{m.get('deaths',0)}/{m.get('assists',0)}",
            "gpm": m.get("gold_per_min", 0),
            "xpm": m.get("xp_per_min", 0),
            "duration": format_duration(m.get("duration", 0)),
            "duration_str": format_duration(m.get("duration", 0)),
            "party_size": psize,
            "party_label": f"{psize}人黑" if psize > 1 else "单排",
            "is_parsed": bool(m.get("version")),
            "is_analyzed": is_match_already_analyzed(mid),
            "mode_str": get_mode_and_lobby(m.get("game_mode", 0), m.get("lobby_type", 0)),
        })

    if not out:
        # Synthesize fallback list from local analyzed match_*.json files so /api/init never fails
        for mf in sorted(REPORTS_DIR.glob("match_*.json"), reverse=True)[:limit]:
            try:
                rep = json.loads(mf.read_text(encoding="utf-8"))
                mid = rep.get("match_id")
                if not mid:
                    continue
                all_p = (rep.get("radiant_pos_1_to_5") or []) + (rep.get("dire_pos_1_to_5") or [])
                me_p = next((p for p in all_p if p.get("is_me")), None) or (all_p[0] if all_p else {})
                won = bool(rep.get("user_won", rep.get("radiant_win")))
                out.append({
                    "match_id": mid,
                    "start_time_str": rep.get("start_time_str", ""),
                    "won": won,
                    "result": "胜利" if won else "失败",
                    "hero_id": me_p.get("hero_id", 0),
                    "hero_name": me_p.get("hero_name", ""),
                    "hero_short_zh": me_p.get("hero_short_zh", "未知英雄"),
                    "hero_img": me_p.get("hero_img", ""),
                    "hero_icon": me_p.get("hero_icon", ""),
                    "kills": me_p.get("kills", 0),
                    "deaths": me_p.get("deaths", 0),
                    "assists": me_p.get("assists", 0),
                    "kda": me_p.get("kda", "0/0/0"),
                    "gpm": me_p.get("gpm", 0),
                    "xpm": me_p.get("xpm", 0),
                    "duration": rep.get("duration_str", ""),
                    "duration_str": rep.get("duration_str", ""),
                    "party_size": 5,
                    "party_label": "5人黑",
                    "is_parsed": bool(rep.get("is_parsed", True)),
                    "is_analyzed": True,
                    "mode_str": rep.get("mode_str", "全英雄选择"),
                })
            except Exception:
                pass

    if out:
        _RECENT_MATCHES_CACHE[account_id] = {"ts": now_ts, "items": out}
    return out


def _has_complete_grok_coaching(gc: Any) -> bool:
    if not isinstance(gc, dict):
        return False
    players = gc.get("players")
    if not isinstance(players, list) or len(players) < 5:
        return False
    has_stages = isinstance(gc.get("stage_reviews"), dict) and bool(gc["stage_reviews"].get("early_lanes"))
    has_deep = any(isinstance(p, dict) and p.get("deep_verdict") and p.get("grok_score") is not None for p in players)
    return has_stages and has_deep


def _hydrate_grok_from_caches(report: Dict[str, Any], match_id: int) -> Dict[str, Any]:
    """Attach the newest grok_coaching from /tmp, reports/coaching-*.json, or Supabase Cloud DB if report lacks it."""
    if not isinstance(report, dict):
        return report
    if _has_complete_grok_coaching(report.get("grok_coaching")):
        return report

    side = report.get("focus_side") or "dire"
    for cdir in (TMP_REPORTS_DIR, REPORTS_DIR):
        for s_candidate in (side, "radiant", "dire"):
            cf = cdir / f"coaching-{match_id}-{s_candidate}.json"
            if cf.exists():
                try:
                    c_data = json.loads(cf.read_text(encoding="utf-8"))
                    if isinstance(c_data, dict) and isinstance(c_data.get("players"), list) and len(c_data["players"]) >= 5:
                        report["grok_coaching"] = c_data
                        if _has_complete_grok_coaching(c_data):
                            return report
                except Exception:
                    pass

    try:
        cloud_rep = cloud_fetch_match_report(match_id)
        if isinstance(cloud_rep, dict) and isinstance(cloud_rep.get("grok_coaching"), dict):
            c_gc = cloud_rep["grok_coaching"]
            if _has_complete_grok_coaching(c_gc) or not report.get("grok_coaching"):
                report["grok_coaching"] = c_gc
    except Exception:
        pass
    return report


def _ensure_grok_coaching(
    report: Dict[str, Any],
    match_id: int,
    json_cache: Path,
    tmp_json_cache: Path,
    force: bool = False,
) -> Dict[str, Any]:
    """Ensure every match report has deep xAI Grok 4.7 LLM coaching (stage_reviews + 5 players deep_verdict & grok_score)."""
    if not isinstance(report, dict):
        return report
    if not force:
        report = _hydrate_grok_from_caches(report, match_id)
        if _has_complete_grok_coaching(report.get("grok_coaching")):
            return report

    try:
        llm_res = call_llm_coach_review(report)
        if isinstance(llm_res, dict) and llm_res.get("ok") and isinstance(llm_res.get("structured"), dict):
            structured = llm_res["structured"]
            structured["model"] = llm_res.get("model", "grok-4.7")
            report["grok_coaching"] = structured
            rep_txt = json.dumps(report, ensure_ascii=False, indent=2)
            try:
                REPORTS_DIR.mkdir(parents=True, exist_ok=True)
                json_cache.write_text(rep_txt, encoding="utf-8")
            except OSError:
                TMP_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
                tmp_json_cache.write_text(rep_txt, encoding="utf-8")
            try:
                cloud_save_match_report(match_id, report)
                cloud_save_coaching(match_id, report.get("focus_side", "radiant"), structured)
            except Exception:
                pass
    except Exception:
        pass
    return report


def get_or_build_match_report(
    match_id: int,
    focus_account_id: Optional[int] = None,
    force_refresh: bool = False,
    allow_build: bool = True,
    require_ai: bool = False,
    skip_llm: bool = False,
) -> Optional[Dict[str, Any]]:
    import time

    json_cache = REPORTS_DIR / f"match_{match_id}.json"
    md_cache = REPORTS_DIR / f"match_{match_id}.md"
    raw_cache = REPORTS_DIR / f"raw_{match_id}.json"

    tmp_json_cache = TMP_REPORTS_DIR / f"match_{match_id}.json"
    tmp_md_cache = TMP_REPORTS_DIR / f"match_{match_id}.md"
    tmp_raw_cache = TMP_REPORTS_DIR / f"raw_{match_id}.json"

    fallback_unparsed_rep = None
    if not force_refresh:
        # Check tmp_json_cache FIRST (writable on Vercel runtime), then json_cache
        for jc in (tmp_json_cache, json_cache):
            if jc.exists():
                try:
                    cached_rep = json.loads(jc.read_text(encoding="utf-8"))
                    if (
                        isinstance(cached_rep, dict)
                        and cached_rep.get("_zh_schema_v") == 2
                        and cached_rep.get("deep_forensics", {}).get("unpressed_saves_by_side") is not None
                    ):
                        cached_rep = _hydrate_grok_from_caches(cached_rep, match_id)
                        # Only serve immediately if replay is parsed
                        if cached_rep.get("is_parsed"):
                            if (allow_build or require_ai) and not skip_llm:
                                cached_rep = _ensure_grok_coaching(cached_rep, match_id, json_cache, tmp_json_cache, force=False)
                            return sanitize_report_mixed_english(cached_rep)
                        fallback_unparsed_rep = cached_rep
                except Exception:
                    pass

        # Read-through from Cloud DB (Supabase / GitHub Cloud) when container /tmp was wiped
        cloud_rep = cloud_fetch_match_report(match_id)
        if isinstance(cloud_rep, dict) and cloud_rep.get("match_id"):
            cloud_rep = _hydrate_grok_from_caches(cloud_rep, match_id)
            if cloud_rep.get("is_parsed"):
                if (allow_build or require_ai) and not skip_llm:
                    cloud_rep = _ensure_grok_coaching(cloud_rep, match_id, json_cache, tmp_json_cache, force=False)
                return sanitize_report_mixed_english(cloud_rep)
            fallback_unparsed_rep = cloud_rep

    if not allow_build and fallback_unparsed_rep is None and not json_cache.exists() and not tmp_json_cache.exists():
        return None

    roster = load_roster()
    aid = focus_account_id or roster.get("main_account_id")

    raw_match = None
    if not force_refresh:
        for rc in (raw_cache, tmp_raw_cache):
            if rc.exists():
                try:
                    candidate_raw = json.loads(rc.read_text(encoding="utf-8"))
                    if candidate_raw and candidate_raw.get("version"):
                        raw_match = candidate_raw
                        break
                except Exception:
                    raw_match = None

    if not raw_match:
        try:
            raw_match = api_get(f"/matches/{match_id}")
            # If the match just ended and OpenDota hasn't parsed the .dem replay yet, auto-request parse and poll briefly!
            if raw_match and not raw_match.get("version"):
                try:
                    api_post(f"/request/{match_id}")
                    if allow_build:
                        for _ in range(2):
                            time.sleep(1.5)
                            retry_raw = api_get(f"/matches/{match_id}")
                            if retry_raw and retry_raw.get("version"):
                                raw_match = retry_raw
                                break
                except Exception:
                    pass
                if not raw_match.get("version") and fallback_unparsed_rep and not force_refresh:
                    return sanitize_report_mixed_english(fallback_unparsed_rep)
            # Only cache raw_match on disk if it is parsed (version is not None)
            if raw_match and raw_match.get("version"):
                raw_txt = json.dumps(raw_match, ensure_ascii=False)
                try:
                    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
                    raw_cache.write_text(raw_txt, encoding="utf-8")
                except OSError:
                    TMP_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
                    tmp_raw_cache.write_text(raw_txt, encoding="utf-8")
        except Exception:
            if fallback_unparsed_rep:
                return sanitize_report_mixed_english(fallback_unparsed_rep)
            raise

    report = analyze_match_data(raw_match, roster, focus_account_id=aid)

    # Preserve existing deep Grok coaching if not force-refreshing, otherwise auto-invoke xAI Grok 4.7 LLM review
    existing_grok = None
    if not force_refresh:
        for jc in (json_cache, tmp_json_cache):
            if jc.exists():
                try:
                    old_d = json.loads(jc.read_text(encoding="utf-8"))
                    if isinstance(old_d, dict) and _has_complete_grok_coaching(old_d.get("grok_coaching")):
                        existing_grok = old_d["grok_coaching"]
                        break
                except Exception:
                    pass
        if not existing_grok:
            hydrated = _hydrate_grok_from_caches(report, match_id)
            if _has_complete_grok_coaching(hydrated.get("grok_coaching")):
                existing_grok = hydrated["grok_coaching"]
    if existing_grok:
        report["grok_coaching"] = existing_grok
    elif not skip_llm:
        try:
            llm_res = call_llm_coach_review(report)
            if isinstance(llm_res, dict) and llm_res.get("ok") and isinstance(llm_res.get("structured"), dict):
                structured = llm_res["structured"]
                structured["model"] = llm_res.get("model", "grok-4.7")
                report["grok_coaching"] = structured
                focus_side = report.get("focus_side", "radiant")
                try:
                    cloud_save_coaching(match_id, focus_side, structured)
                except Exception:
                    pass
        except Exception:
            pass

    report = sanitize_report_mixed_english(report)
    md_text = render_markdown_report(report)
    rep_txt = json.dumps(report, ensure_ascii=False, indent=2)
    try:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        json_cache.write_text(rep_txt, encoding="utf-8")
        md_cache.write_text(md_text, encoding="utf-8")
    except OSError:
        TMP_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        tmp_json_cache.write_text(rep_txt, encoding="utf-8")
        tmp_md_cache.write_text(md_text, encoding="utf-8")

    # Write-through to Cloud DB (Supabase / GitHub Cloud) so serverless redeployments never lose reports
    try:
        cloud_save_match_report(match_id, report)
    except Exception:
        pass
    return report


import base64
from concurrent.futures import ThreadPoolExecutor

_ICON_B64_CACHE: Dict[str, str] = {}


def fetch_match_icons_base64(match_id: int) -> Dict[str, str]:
    report = get_or_build_match_report(match_id, allow_build=True)
    if not report:
        return {}
    players = (report.get("radiant_pos_1_to_5") or []) + (report.get("dire_pos_1_to_5") or [])
    urls = set()
    for p in players:
        if p.get("hero_img"):
            urls.add(p["hero_img"])
        for it in (p.get("final_items_rich") or []):
            if it.get("img"):
                urls.add(it["img"])
        if (p.get("neutral_item_rich") or {}).get("img"):
            urls.add(p["neutral_item_rich"]["img"])

    missing = [u for u in urls if u and u not in _ICON_B64_CACHE]
    if missing:
        def _dl(u: str):
            try:
                req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    raw = resp.read()
                    if raw:
                        return u, "data:image/png;base64," + base64.b64encode(raw).decode("ascii")
            except Exception:
                pass
            return u, ""

        with ThreadPoolExecutor(max_workers=20) as ex:
            for u, b64 in ex.map(_dl, missing):
                if b64:
                    _ICON_B64_CACHE[u] = b64

    return {u: _ICON_B64_CACHE[u] for u in urls if u in _ICON_B64_CACHE}


class DotaAnalystHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write(f"[DotaLedgerServer] {self.address_string()} - {fmt % args}\n")

    def _send_json(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw) if raw else {}

    def _resolve_path_and_qs(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)
        if "__vercel_path" in qs and qs["__vercel_path"]:
            raw_vpath = qs["__vercel_path"][0]
            v_parsed = urllib.parse.urlparse(raw_vpath)
            path = v_parsed.path or "/"
            if v_parsed.query:
                extra_qs = urllib.parse.parse_qs(v_parsed.query)
                for k, v in extra_qs.items():
                    if k not in qs:
                        qs[k] = v
        elif path == "/api/index.py":
            hdr_path = (
                self.headers.get("x-forwarded-uri")
                or self.headers.get("x-original-url")
                or self.headers.get("x-rewrite-url")
                or "/"
            )
            h_parsed = urllib.parse.urlparse(hdr_path)
            if h_parsed.path and h_parsed.path != "/api/index.py":
                path = h_parsed.path
            else:
                path = "/"
        if not path.startswith("/"):
            path = "/" + path
        return path, qs

    def do_GET(self) -> None:
        path, qs = self._resolve_path_and_qs()

        try:
            if path == "/api/match_icons":
                mid_str = (qs.get("match_id") or [""])[0].strip()
                mid = int(mid_str) if mid_str.isdigit() else 0
                icons = fetch_match_icons_base64(mid) if mid else {}
                self._send_json({"ok": True, "match_id": mid, "icons": icons})
                return

            if path == "/api/heroes":
                hero_map, _ = get_hero_constants_map()
                heroes_list = sorted(hero_map.values(), key=lambda x: x["id"])
                self._send_json({"ok": True, "heroes": heroes_list})
                return

            if path == "/api/init":
                roster = load_roster()
                main_id = roster.get("main_account_id") or 86080912
                recent = fetch_recent_matches_formatted(main_id, limit=12)
                wins = sum(1 for m in recent if m.get("won"))
                losses = len(recent) - wins
                win_rate = round((wins / len(recent)) * 100, 1) if recent else 0.0
                latest_report = None
                analyzed_in_recent = [m for m in recent if m.get("is_analyzed")]
                if analyzed_in_recent:
                    latest_report = get_or_build_match_report(
                        analyzed_in_recent[0]["match_id"],
                        focus_account_id=main_id,
                        allow_build=False,
                    )
                elif recent:
                    # Fallback to latest match_*.json in REPORTS_DIR without auto-analyzing unanalyzed matches
                    existing_files = sorted(REPORTS_DIR.glob("match_*.json"), reverse=True)
                    if existing_files:
                        try:
                            latest_report = json.loads(existing_files[0].read_text(encoding="utf-8"))
                        except Exception:
                            latest_report = None
                profile_obj = {
                    "profile": {
                        "account_id": main_id,
                        "personaname": roster.get("main_name") or roster.get("main_player_name") or "Flame = ez mute",
                        "rank_label": "万古流芳 5 [75]",
                    },
                    "wl": {"win": wins, "lose": losses, "win_rate": win_rate},
                    "recent_matches": recent,
                }
                squad_ledger = build_squad_history_ledger(REPORTS_DIR, roster, recent)
                hero_map, _ = get_hero_constants_map()
                heroes_catalog = sorted(hero_map.values(), key=lambda x: x["id"])
                self._send_json({
                    "ok": True,
                    "roster": roster,
                    "profile": profile_obj,
                    "llm_status": get_llm_status_safe(),
                    "cloud_db": get_cloud_db_status_safe(),
                    "recent_matches": recent,
                    "squad_ledger": squad_ledger,
                    "heroes_catalog": heroes_catalog,
                    "latest_report": latest_report,
                    "latest_match_report": latest_report,
                })
                return

            if path in ("/api/recent", "/api/player"):
                raw_q = (qs.get("query") or qs.get("q") or qs.get("account_id") or [""])[0].strip()
                roster = load_roster()
                aid = resolve_player_input(raw_q) if raw_q else (roster.get("main_account_id") or 86080912)
                recent = fetch_recent_matches_formatted(aid, limit=12)
                wins = sum(1 for m in recent if m.get("won"))
                losses = len(recent) - wins
                win_rate = round((wins / len(recent)) * 100, 1) if recent else 0.0
                analyzed_in_recent = [m for m in recent if m.get("is_analyzed")]
                latest_report = (
                    get_or_build_match_report(
                        analyzed_in_recent[0]["match_id"], focus_account_id=aid, allow_build=False
                    )
                    if analyzed_in_recent
                    else None
                )
                profile_obj = {
                    "profile": {
                        "account_id": aid,
                        "personaname": str(aid),
                        "rank_label": "Dota 2 玩家",
                    },
                    "wl": {"win": wins, "lose": losses, "win_rate": win_rate},
                    "recent_matches": recent,
                }
                squad_ledger = build_squad_history_ledger(REPORTS_DIR, roster, recent)
                self._send_json({
                    "ok": True,
                    "account_id": aid,
                    "profile": profile_obj,
                    "recent_matches": recent,
                    "squad_ledger": squad_ledger,
                    "latest_match_report": latest_report,
                })
                return

            if path == "/api/match" or path.startswith("/api/match/"):
                if path.startswith("/api/match/"):
                    mid_str = path.split("/api/match/", 1)[1].strip("/")
                else:
                    mid_str = (qs.get("match_id") or [""])[0].strip()
                mid = int(mid_str)
                force = (qs.get("refresh") or ["0"])[0] == "1"
                analyze_now = (qs.get("analyze") or ["0"])[0] == "1"
                skip_llm = (qs.get("skip_llm") or ["0"])[0] == "1"
                aid_str = (qs.get("account_id") or [""])[0].strip()
                aid = resolve_player_input(aid_str) if aid_str else None
                report = get_or_build_match_report(
                    mid,
                    focus_account_id=aid,
                    force_refresh=force,
                    allow_build=(force or analyze_now),
                    require_ai=(not skip_llm),
                    skip_llm=skip_llm,
                )
                roster = load_roster()
                squad_ledger = build_squad_history_ledger(REPORTS_DIR, roster, [])
                if report is None:
                    self._send_json({
                        "ok": True,
                        "not_analyzed": True,
                        "match_id": mid,
                        "squad_ledger": squad_ledger,
                    })
                    return
                self._send_json({"ok": True, "report": report, "squad_ledger": squad_ledger})
                return

            # 静态文件服务 (支持 /, /pregame, 以及公开分享链接 /match/<id>)
            if path in ("/", "", "/pregame", "/pregame.html") or path.startswith("/match/"):
                file_path = STATIC_DIR / "index.html"
            else:
                rel = path.lstrip("/")
                file_path = (STATIC_DIR / rel).resolve()
                if not str(file_path).startswith(str(STATIC_DIR.resolve())):
                    self._send_json({"ok": False, "error": "Forbidden"}, status=403)
                    return

            if not file_path.exists() or not file_path.is_file():
                self._send_json({"ok": False, "error": f"Not found: {path}"}, status=404)
                return

            ctype, _ = mimetypes.guess_type(str(file_path))
            if not ctype:
                ctype = "application/octet-stream"
            if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
                ctype += "; charset=utf-8"

            content = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(content)

        except Exception as e:
            self._send_json({"ok": False, "error": str(e)}, status=500)

    def do_POST(self) -> None:
        path, qs = self._resolve_path_and_qs()

        try:
            if path == "/api/pregame_plan":
                body = self._read_json_body()
                own_picks = body.get("own_picks") or body.get("our_heroes") or []
                enemy_picks = body.get("enemy_picks") or body.get("enemy_heroes") or []
                use_llm = bool(body.get("use_llm", False))
                roster = load_roster()
                hero_map, _ = get_hero_constants_map()
                plan = build_pregame_strategy_plan(own_picks, enemy_picks, roster, hero_map)
                if use_llm:
                    llm_res = call_llm_pregame_coach(
                        plan=plan,
                        api_key=body.get("api_key") or "",
                        provider=body.get("provider") or "",
                        model_name=body.get("model") or "",
                        base_url=body.get("base_url") or "",
                    )
                    if llm_res.get("ok") and llm_res.get("grok_live_brief"):
                        plan["grok_live_brief"] = llm_res["grok_live_brief"]
                    elif llm_res.get("error"):
                        plan["llm_error"] = llm_res["error"]
                self._send_json({"ok": True, "plan": plan})
                return

            if path == "/api/request_parse" or path.startswith("/api/parse/"):
                if path.startswith("/api/parse/"):
                    mid = int(path.split("/api/parse/", 1)[1].strip("/"))
                else:
                    body = self._read_json_body()
                    mid = int(body.get("match_id"))
                resp = api_post(f"/request/{mid}")
                job_id = (resp.get("job") or {}).get("jobId")
                msg = f"已向 OpenDota 提交录像解析请求 (Job #{job_id})，稍后点击【重新读取】即可获取完整时间轴数据。"
                self._send_json({
                    "ok": True,
                    "match_id": mid,
                    "job_id": job_id,
                    "message": msg,
                    "parse_result": {"job_id": job_id, "message": msg},
                })
                return

            if path == "/api/roster":
                body = self._read_json_body()
                roster = load_roster()
                main_in = body.get("main_account_input") or body.get("main_account_id")
                if main_in:
                    aid = resolve_player_input(str(main_in))
                    mname = body.get("main_name") or body.get("main_player_name") or roster.get("main_name") or "Flame = ez mute"
                    roster["main_account_id"] = aid
                    roster["main_name"] = mname
                    roster["main_player_name"] = mname
                    roster.setdefault("players", {})[str(aid)] = {
                        "name": mname,
                        "nickname": mname,
                        "usual_pos": "主力",
                        "note": "本人主账号",
                    }
                fid = body.get("friend_id")
                fname = body.get("friend_name") or body.get("friend_nickname")
                if fid and fname:
                    faid = resolve_player_input(str(fid))
                    fname_clean = str(fname).strip()
                    fpos = str(body.get("friend_pos") or "常驻队友").strip()
                    existing = roster.setdefault("players", {}).get(str(faid), {})
                    existing.update({
                        "name": fname_clean,
                        "nickname": fname_clean,
                        "usual_pos": fpos,
                        "note": "开黑队友",
                    })
                    roster["players"][str(faid)] = existing
                    roster.setdefault("teammates", {})[str(faid)] = existing
                save_roster(roster)
                self._send_json({"ok": True, "roster": roster})
                return

            if path in ("/api/llm_review", "/api/llm_coach"):
                body = self._read_json_body()
                mid = int(body.get("match_id"))
                api_key = body.get("api_key") or ""
                provider = body.get("provider") or ""
                model_name = body.get("model_name") or body.get("model") or ""
                base_url = body.get("base_url") or ""
                side = body.get("side") or "dire"
                force = bool(body.get("force", True))
                report = get_or_build_match_report(mid, allow_build=True, require_ai=False, skip_llm=True)
                if not force and isinstance(report, dict) and _has_complete_grok_coaching(report.get("grok_coaching")):
                    self._send_json({
                        "ok": True,
                        "cached": True,
                        "structured": report["grok_coaching"],
                        "report": sanitize_report_mixed_english(report),
                    })
                    return
                res = call_llm_coach_review(
                    report=report,
                    api_key=api_key,
                    provider=provider,
                    model_name=model_name,
                    base_url=base_url,
                )
                if res.get("ok") and res.get("structured"):
                    res["structured"] = sanitize_report_mixed_english(res["structured"])
                    report["grok_coaching"] = res["structured"]
                    rep_txt = json.dumps(report, ensure_ascii=False, indent=2)
                    try:
                        (REPORTS_DIR / f"match_{mid}.json").write_text(rep_txt, encoding="utf-8")
                    except OSError:
                        TMP_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
                        (TMP_REPORTS_DIR / f"match_{mid}.json").write_text(rep_txt, encoding="utf-8")
                    try:
                        cloud_save_match_report(mid, report)
                        cloud_save_coaching(mid, side, res["structured"])
                    except Exception:
                        pass
                res["report"] = sanitize_report_mixed_english(report)
                self._send_json(res)
                return

            self._send_json({"ok": False, "error": f"Unknown endpoint: {path}"}, status=404)
        except Exception as e:
            self._send_json({"ok": False, "error": str(e)}, status=500)


def main() -> None:
    port = int(os.environ.get("PORT", "8788"))
    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer(("127.0.0.1", port), DotaAnalystHandler)
    print(f"Dota 2 战后算账工作台已启动: http://127.0.0.1:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
