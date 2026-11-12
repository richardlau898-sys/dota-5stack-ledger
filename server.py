#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dota 2 五黑复盘与赛前作战室 - Web 后端服务 (server.py)
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
import gzip
import hashlib
import hmac
import json
import mimetypes
import os
import re
import sys
import time
import traceback
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from ai_coach_engine import (
    call_llm_coach_review,
    call_llm_pregame_coach,
    call_nano_banana_poster_art,
    get_llm_status_safe,
)
from cloud_store import (
    cloud_fetch_match_players,
    cloud_fetch_match_report,
    cloud_fetch_raw_match,
    cloud_load_llm_task,
    cloud_save_coaching,
    cloud_save_llm_task,
    cloud_save_match_report,
    cloud_save_raw_match,
    get_cloud_analyzed_match_ids,
    get_cloud_db_status_safe,
)
from dota_analyst import (
    ENGINE_VERSION,
    REPORTS_DIR,
    SITE_NAME,
    SITE_SUBTITLE,
    STEAM64_OFFSET,
    analyze_match_data,
    api_get,
    api_post,
    extract_report_part,
    format_duration,
    get_hero_constants_map,
    iter_roster_accounts,
    load_roster,
    normalize_account_id,
    render_markdown_report,
    save_roster,
    strip_report_cdn_urls_to_keys,
)
from dota_constants_zh import get_hero_name, get_mode_and_lobby, sanitize_report_mixed_english
from draft_and_phase_coach import (
    build_pregame_strategy_plan,
    build_squad_history_ledger,
    load_or_build_squad_ledger,
    refresh_persisted_squad_ledger,
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


def resolve_player_input(raw_input: str) -> int:
    """
    支持用户输入（严格限制防 SSRF）:
    1. 纯数字 ID（Steam32 好友 ID 或 Steam64 ID）
    2. 主机名严格等于 steamcommunity.com 的 https 链接（/id/<short> 或 /profiles/<digits>）
    3. 匹配 ^[A-Za-z0-9_-]{2,32}$ 的自定义短名
    其余一律抛出 ValueError（由 HTTP 层返回 400）。
    """
    s = (raw_input or "").strip()
    if not s:
        raise ValueError("玩家输入不能为空")

    if re.fullmatch(r"\d+", s):
        return normalize_account_id(s)

    vanity = None
    if "://" in s or s.startswith("http") or "/" in s:
        parsed = urllib.parse.urlparse(s)
        hostname = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or hostname != "steamcommunity.com" or parsed.port is not None:
            raise ValueError("仅支持 https://steamcommunity.com 域名的 Steam 主页链接")
        m_prof = re.fullmatch(r"/profiles/(\d+)/?", parsed.path or "")
        if m_prof:
            return normalize_account_id(m_prof.group(1))
        m_id = re.fullmatch(r"/id/([A-Za-z0-9_-]{2,32})/?", parsed.path or "")
        if not m_id:
            raise ValueError("Steam 主页链接路径格式无效")
        vanity = m_id.group(1)
    elif re.fullmatch(r"[A-Za-z0-9_-]{2,32}", s):
        vanity = s
    else:
        raise ValueError("无效的玩家 ID、Steam 链接或自定义短名")

    xml_url = f"https://steamcommunity.com/id/{vanity}/?xml=1"
    req = urllib.request.Request(xml_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        xml_data = resp.read().decode("utf-8", errors="ignore")
    root = ET.fromstring(xml_data)
    steam64_txt = root.findtext("steamID64")
    if not steam64_txt or not re.fullmatch(r"\d+", steam64_txt.strip()):
        raise ValueError("无法从 Steam 主页解析出有效的 steamID64")
    return normalize_account_id(steam64_txt.strip())


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


def fetch_recent_matches_formatted(
    account_id: int,
    limit: int = 12,
    allow_network: bool = True,
) -> list:
    import time

    now_ts = time.time()
    cached = _RECENT_MATCHES_CACHE.get(account_id)
    if (
        cached
        and (now_ts - cached.get("ts", 0) < 120)
        and cached.get("items")
        and (not allow_network or cached.get("from_network"))
    ):
        out_cached = cached["items"]
        for item in out_cached:
            item["is_analyzed"] = is_match_already_analyzed(item.get("match_id"))
        return out_cached[:limit]

    hero_map, _ = get_hero_constants_map(allow_network=allow_network)
    recent_cache_file = REPORTS_DIR / f"recent_matches_{account_id}.json"
    tmp_recent_cache_file = TMP_REPORTS_DIR / f"recent_matches_{account_id}.json"

    raw_list = None
    fetched_from_network = False
    if allow_network:
        try:
            raw_list = api_get(f"/players/{account_id}/recentMatches")
            if isinstance(raw_list, list) and raw_list:
                fetched_from_network = True
                try:
                    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
                    recent_cache_file.write_text(json.dumps(raw_list, ensure_ascii=False), encoding="utf-8")
                except OSError:
                    TMP_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
                    tmp_recent_cache_file.write_text(json.dumps(raw_list, ensure_ascii=False), encoding="utf-8")
        except Exception:
            raw_list = None

    if raw_list is None:
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
        start_time = int(m.get("start_time") or 0)
        psize = m.get("party_size") or 1
        hid = int(m.get("hero_id") or 0)
        hinfo = hero_map.get(hid) or {}
        out.append({
            "match_id": mid,
            "start_time": start_time if start_time > 0 else None,
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
        # R1-8: 从 Supabase match_players 表读取比赛列表（不依赖本地 reports/ 目录）
        mp_rows = cloud_fetch_match_players(limit=max(120, limit * 12))
        if mp_rows:
            roster = load_roster()
            roster_members = iter_roster_accounts(roster)
            target_aids = {int(account_id)} if account_id else set()
            all_roster_aids = set()
            for m in roster_members:
                aids_set = set(m["account_ids"])
                all_roster_aids.update(aids_set)
                if int(account_id) in aids_set:
                    target_aids.update(aids_set)

            by_mid: Dict[int, list] = {}
            for r in mp_rows:
                mid_val = int(r.get("match_id") or 0)
                if mid_val > 0:
                    by_mid.setdefault(mid_val, []).append(r)

            for mid in sorted(by_mid.keys(), reverse=True)[:limit]:
                m_rows = by_mid[mid]
                me_r = next((r for r in m_rows if r.get("account_id") in target_aids), None)
                ref_r = (
                    me_r
                    or next((r for r in m_rows if r.get("account_id") in all_roster_aids), None)
                    or m_rows[0]
                )
                won = bool(ref_r.get("won"))
                dur_sec = int(round(float(ref_r.get("duration_min") or 0.0) * 60))
                dur_str = format_duration(dur_sec)
                roster_side_cnt = sum(
                    1
                    for r in m_rows
                    if r.get("side") == ref_r.get("side") and r.get("account_id") in all_roster_aids
                )
                psize = roster_side_cnt if roster_side_cnt >= 2 else None
                if me_r is not None:
                    hid = int(me_r.get("hero_id") or 0)
                    hinfo = hero_map.get(hid) or {}
                    k = int(me_r.get("kills") or 0)
                    d = int(me_r.get("deaths") or 0)
                    a = int(me_r.get("assists") or 0)
                    hero_name_val = get_hero_name(hid)
                    hero_short_val = me_r.get("hero_short_zh") or hinfo.get("short_zh") or hero_name_val
                    hero_img_val = hinfo.get("img") or ""
                    hero_icon_val = hinfo.get("icon") or ""
                    kda_val = f"{k}/{d}/{a}"
                    gpm_val = int(me_r.get("gpm") or 0)
                    xpm_val = int(me_r.get("xpm") or 0)
                else:
                    hid = 0
                    k = None
                    d = None
                    a = None
                    hero_name_val = ""
                    hero_short_val = "无数据"
                    hero_img_val = ""
                    hero_icon_val = ""
                    kda_val = None
                    gpm_val = None
                    xpm_val = None
                out.append({
                    "match_id": mid,
                    "start_time": None,
                    "won": won,
                    "result": "胜利" if won else "失败",
                    "hero_id": hid,
                    "hero_name": hero_name_val,
                    "hero_short_zh": hero_short_val,
                    "hero_img": hero_img_val,
                    "hero_icon": hero_icon_val,
                    "kills": k,
                    "deaths": d,
                    "assists": a,
                    "kda": kda_val,
                    "gpm": gpm_val,
                    "xpm": xpm_val,
                    "duration": dur_str,
                    "duration_str": dur_str,
                    "party_size": psize,
                    "party_label": f"{psize}人黑" if (psize and psize > 1) else "无数据",
                    "is_parsed": True,
                    "is_analyzed": True,
                    "mode_str": "全英雄选择",
                })

    if not out and REPORTS_DIR.exists():
        # Synthesize fallback list from local analyzed match_*.json files when Supabase is unconfigured
        roster = load_roster()
        all_roster_aids = {int(aid) for m in iter_roster_accounts(roster) for aid in m["account_ids"]}
        for mf in sorted(REPORTS_DIR.glob("match_*.json"), reverse=True)[:limit]:
            try:
                rep = json.loads(mf.read_text(encoding="utf-8"))
                mid = rep.get("match_id")
                if not mid:
                    continue
                all_p = (rep.get("radiant_pos_1_to_5") or []) + (rep.get("dire_pos_1_to_5") or [])
                me_p = next(
                    (
                        p
                        for p in all_p
                        if p.get("is_me")
                        or (account_id and p.get("account_id") is not None and int(p.get("account_id") or 0) == int(account_id))
                    ),
                    None,
                )
                f_side_rep = rep.get("focus_side") or "dire"
                own_p_rep = (rep.get("radiant_pos_1_to_5") if f_side_rep == "radiant" else rep.get("dire_pos_1_to_5")) or []
                roster_cnt_rep = sum(
                    1
                    for p in own_p_rep
                    if p.get("account_id") is not None and int(p.get("account_id") or 0) in all_roster_aids
                )
                psize_rep = (
                    int(me_p["party_size"])
                    if (me_p and me_p.get("party_size") is not None)
                    else (roster_cnt_rep if roster_cnt_rep >= 2 else None)
                )
                won = bool(rep.get("user_won", rep.get("radiant_win")))
                out.append({
                    "match_id": mid,
                    "start_time": rep.get("start_time"),
                    "won": won,
                    "result": "胜利" if won else "失败",
                    "hero_id": me_p.get("hero_id", 0) if me_p else 0,
                    "hero_name": me_p.get("hero_name", "") if me_p else "",
                    "hero_short_zh": (me_p.get("hero_short_zh") or "无数据") if me_p else "无数据",
                    "hero_img": me_p.get("hero_img", "") if me_p else "",
                    "hero_icon": me_p.get("hero_icon", "") if me_p else "",
                    "kills": me_p.get("kills") if me_p else None,
                    "deaths": me_p.get("deaths") if me_p else None,
                    "assists": me_p.get("assists") if me_p else None,
                    "kda": me_p.get("kda") if me_p else None,
                    "gpm": me_p.get("gpm") if me_p else None,
                    "xpm": me_p.get("xpm") if me_p else None,
                    "duration": rep.get("duration_str", ""),
                    "duration_str": rep.get("duration_str", ""),
                    "party_size": psize_rep,
                    "party_label": (f"{psize_rep}人黑" if psize_rep >= 2 else "单排") if psize_rep is not None else "无数据",
                    "is_parsed": bool(rep.get("is_parsed", True)),
                    "is_analyzed": True,
                    "mode_str": rep.get("mode_str", "全英雄选择"),
                })
            except Exception:
                pass

    if out:
        _RECENT_MATCHES_CACHE[account_id] = {
            "ts": now_ts,
            "items": out,
            "from_network": fetched_from_network,
        }
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


def _hydrate_grok_from_caches(
    report: Dict[str, Any],
    match_id: int,
    allow_cloud: bool = True,
) -> Dict[str, Any]:
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

    if allow_cloud:
        try:
            cloud_rep = cloud_fetch_match_report(match_id, persist_tmp=False)
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
            if llm_res.get("model"):
                structured["model"] = llm_res["model"]
            report["grok_coaching"] = structured
            rep_txt = json.dumps(report, ensure_ascii=False, separators=(",", ":"))
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


def _ensure_v69_hero_matchup_matrix(report: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure any cached or cloud-loaded report has v7.0.0 hero_matchup_matrix, counter_ledger, and lane_chemistry_by_side."""
    if not isinstance(report, dict):
        return report
    da = report.get("draft_analysis") or {}
    hmm = da.get("hero_matchup_matrix")
    df = report.get("deep_forensics") or {}
    raw_lms = df.get("lane_matchups")
    lms_unavail = (
        df.get("available") is False
        or (isinstance(raw_lms, dict) and raw_lms.get("available") is False)
    )
    lms = raw_lms if (not lms_unavail and isinstance(raw_lms, list)) else []
    has_v70_matrix = (
        isinstance(hmm, list)
        and len(hmm) >= 5
        and isinstance(hmm[0], dict)
        and "counter_ledger" in hmm[0]
    )
    has_v70_lanes = (
        lms_unavail
        or not lms
        or (isinstance(lms[0], dict) and "lane_chemistry_by_side" in lms[0])
    )
    if has_v70_matrix and has_v70_lanes:
        return report
    try:
        from draft_and_phase_coach import build_draft_and_combo_analysis
        from hero_profiles_126 import build_hero_matchup_dossier, analyze_lane_matchup_chemistry

        rad = report.get("radiant_pos_1_to_5") or []
        dire = report.get("dire_pos_1_to_5") or []
        if rad and dire:
            f_side = report.get("focus_side") or "radiant"
            r_win = bool(report.get("radiant_win"))
            dur_min = float(report.get("duration_min") or 40.0)
            dur_sec = int(dur_min * 60)
            for p in rad:
                p["hero_matchup_dossier"] = build_hero_matchup_dossier(p, rad, dire, dur_min, r_win)
            for p in dire:
                p["hero_matchup_dossier"] = build_hero_matchup_dossier(p, dire, rad, dur_min, not r_win)
            draft_res = build_draft_and_combo_analysis(
                rad, dire, {"duration": dur_sec, "radiant_win": r_win}, f_side
            )
            report["draft_analysis_by_side"] = draft_res.get("by_side") or draft_res
            report["draft_analysis"] = report["draft_analysis_by_side"].get(f_side) or draft_res
            if lms:
                rad_by_pos = {int(p.get("pos") or 0): p for p in rad}
                dire_by_pos = {int(p.get("pos") or 0): p for p in dire}
                for ln in lms:
                    if not isinstance(ln, dict):
                        continue
                    lnum = int(ln.get("lane_id") or 2)
                    r_lp = [rad_by_pos.get(int(h.get("pos") or 0), h) for h in (ln.get("radiant_heroes") or [])]
                    d_lp = [dire_by_pos.get(int(h.get("pos") or 0), h) for h in (ln.get("dire_heroes") or [])]
                    diff_dire = int(ln.get("dire_gold10") or 0) - int(ln.get("radiant_gold10") or 0)
                    ln["lane_chemistry_by_side"] = analyze_lane_matchup_chemistry(lnum, r_lp, d_lp, diff_dire)
    except Exception:
        pass
    return report


def check_team_token_auth(
    provided_token: Optional[str],
    expected_token: Optional[str] = None,
    is_vercel: Optional[bool] = None,
) -> Tuple[bool, int, str]:
    """
    校验车队口令 (X-Team-Token)：
    - 若配置了 TEAM_TOKEN：必须提供且 hmac.compare_digest 相等，否则返回 401；
    - 若未配置 TEAM_TOKEN：在 Vercel 生产环境一律返回 503，本地开发环境放行 (200)。
    """
    expected = (expected_token if expected_token is not None else os.environ.get("TEAM_TOKEN", "")).strip()
    vercel_env = is_vercel if is_vercel is not None else bool(os.environ.get("VERCEL"))
    if not expected:
        if vercel_env:
            return False, 503, "服务端未配置 TEAM_TOKEN，已拒绝写入与算力操作"
        return True, 200, ""
    candidate = (provided_token or "").strip()
    if not candidate:
        return False, 401, "需要输入车队口令 (X-Team-Token)"
    if not hmac.compare_digest(candidate.encode("utf-8"), expected.encode("utf-8")):
        return False, 401, "车队口令无效，请核对后重试"
    return True, 200, ""


def match_has_roster_player(
    raw_or_report: Dict[str, Any],
    roster: Dict[str, Any],
    allow_anonymous: bool = False,
) -> bool:
    """检查比赛的 10 名玩家里是否至少有 1 名在花名册中（或带口令新建时存在隐藏资料玩家）。"""
    if not isinstance(raw_or_report, dict) or not isinstance(roster, dict):
        return False
    roster_ids = {
        aid
        for m in iter_roster_accounts(roster)
        for aid in m["account_ids"]
    }
    if not roster_ids:
        return False

    candidates = list(raw_or_report.get("players") or [])
    if not candidates:
        candidates = list(raw_or_report.get("radiant_pos_1_to_5") or []) + list(
            raw_or_report.get("dire_pos_1_to_5") or []
        )
    has_anon = False
    for p in candidates:
        if isinstance(p, dict):
            if p.get("account_id") is None:
                has_anon = True
                continue
            try:
                if int(p["account_id"]) in roster_ids:
                    return True
            except (ValueError, TypeError):
                pass
    if allow_anonymous and has_anon:
        return True
    return False


def get_or_build_match_report(
    match_id: int,
    focus_account_id: Optional[int] = None,
    force_refresh: bool = False,
    allow_build: bool = True,
    require_ai: bool = False,
    skip_llm: bool = True,
) -> Optional[Dict[str, Any]]:
    import time

    json_cache = REPORTS_DIR / f"match_{match_id}.json"
    md_cache = REPORTS_DIR / f"match_{match_id}.md"
    raw_cache = REPORTS_DIR / f"raw_{match_id}.json"

    tmp_json_cache = TMP_REPORTS_DIR / f"match_{match_id}.json"
    tmp_md_cache = TMP_REPORTS_DIR / f"match_{match_id}.md"
    tmp_raw_cache = TMP_REPORTS_DIR / f"raw_{match_id}.json"

    # R1-1: 不带口令的只读模式（allow_build=False）严格只读已有报告，零写入、零 OpenDota 请求、不拦非花名册/匿名读取
    if not allow_build:
        for jc in (json_cache, tmp_json_cache):
            if jc.exists():
                try:
                    cached_rep = json.loads(jc.read_text(encoding="utf-8"))
                    if isinstance(cached_rep, dict) and cached_rep.get("match_id"):
                        rep_out = dict(cached_rep)
                        rep_out = _ensure_v69_hero_matchup_matrix(rep_out)
                        rep_out = _hydrate_grok_from_caches(rep_out, match_id, allow_cloud=False)
                        rep_out = sanitize_report_mixed_english(rep_out)
                        if rep_out.get("engine_version") != ENGINE_VERSION:
                            rep_out["stale"] = True
                        return rep_out
                except Exception:
                    pass

        cloud_rep = cloud_fetch_match_report(match_id, persist_tmp=False)
        if isinstance(cloud_rep, dict) and cloud_rep.get("match_id"):
            rep_out = dict(cloud_rep)
            rep_out = _ensure_v69_hero_matchup_matrix(rep_out)
            rep_out = _hydrate_grok_from_caches(rep_out, match_id, allow_cloud=False)
            rep_out = sanitize_report_mixed_english(rep_out)
            if rep_out.get("engine_version") != ENGINE_VERSION:
                rep_out["stale"] = True
            return rep_out
        return None

    fallback_unparsed_rep = None
    stale_cached_rep = None
    if not force_refresh:
        for jc in (json_cache, tmp_json_cache):
            if jc.exists():
                try:
                    cached_rep = json.loads(jc.read_text(encoding="utf-8"))
                    if (
                        isinstance(cached_rep, dict)
                        and cached_rep.get("_zh_schema_v") == 2
                        and cached_rep.get("deep_forensics", {}).get("unpressed_saves_by_side") is not None
                    ):
                        cached_rep = _ensure_v69_hero_matchup_matrix(cached_rep)
                        cached_rep = _hydrate_grok_from_caches(cached_rep, match_id)
                        if cached_rep.get("engine_version") == ENGINE_VERSION:
                            if cached_rep.get("is_parsed"):
                                return sanitize_report_mixed_english(cached_rep)
                            fallback_unparsed_rep = cached_rep
                        else:
                            stale_cached_rep = cached_rep
                except Exception:
                    pass

        cloud_rep = cloud_fetch_match_report(match_id)
        if isinstance(cloud_rep, dict) and cloud_rep.get("match_id"):
            cloud_rep = _ensure_v69_hero_matchup_matrix(cloud_rep)
            cloud_rep = _hydrate_grok_from_caches(cloud_rep, match_id)
            if cloud_rep.get("engine_version") == ENGINE_VERSION:
                if cloud_rep.get("is_parsed"):
                    return sanitize_report_mixed_english(cloud_rep)
                fallback_unparsed_rep = cloud_rep
            elif stale_cached_rep is None:
                stale_cached_rep = cloud_rep

    already_analyzed = (
        json_cache.exists()
        or tmp_json_cache.exists()
        or (stale_cached_rep is not None)
        or (fallback_unparsed_rep is not None)
    )
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
                cloud_raw = cloud_fetch_raw_match(match_id)
                if isinstance(cloud_raw, dict) and cloud_raw.get("match_id"):
                    raw_match = cloud_raw
            except Exception:
                pass

    if not raw_match:
        try:
            raw_match = api_get(f"/matches/{match_id}")
            if not already_analyzed and raw_match and not match_has_roster_player(raw_match, roster, allow_anonymous=True):
                raise PermissionError("该比赛 10 名玩家均不在车队花名册中，拒绝分析与落库")
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
            # Only cache raw_match on disk/Storage if it is parsed (version is not None)
            if raw_match and raw_match.get("version"):
                raw_txt = json.dumps(raw_match, ensure_ascii=False, separators=(",", ":"))
                try:
                    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
                    raw_cache.write_text(raw_txt, encoding="utf-8")
                except OSError:
                    TMP_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
                    tmp_raw_cache.write_text(raw_txt, encoding="utf-8")
                try:
                    cloud_save_raw_match(match_id, raw_match)
                except Exception:
                    pass
        except PermissionError:
            raise
        except Exception:
            if fallback_unparsed_rep:
                return sanitize_report_mixed_english(fallback_unparsed_rep)
            if stale_cached_rep:
                return sanitize_report_mixed_english(stale_cached_rep)
            raise

    if not already_analyzed and raw_match and not match_has_roster_player(raw_match, roster, allow_anonymous=True):
        raise PermissionError("该比赛 10 名玩家均不在车队花名册中，拒绝分析与落库")

    report = analyze_match_data(raw_match, roster, focus_account_id=aid)

    # Preserve existing deep Grok coaching from cache only (GET/build never calls LLM; only POST /api/llm_review does)
    existing_grok = None
    for jc in (tmp_json_cache, json_cache):
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

    report = strip_report_cdn_urls_to_keys(sanitize_report_mixed_english(report))
    md_text = render_markdown_report(report)
    rep_txt = json.dumps(report, ensure_ascii=False, separators=(",", ":"))
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
    try:
        refresh_persisted_squad_ledger(REPORTS_DIR, roster, [])
    except Exception:
        pass
    return report


import base64
from concurrent.futures import ThreadPoolExecutor

_ICON_B64_CACHE: Dict[str, str] = {}


def fetch_match_icons_base64(match_id: int, allow_network: bool = False) -> Dict[str, str]:
    report = get_or_build_match_report(match_id, allow_build=False)
    if not report:
        return {}
    players = (report.get("radiant_pos_1_to_5") or []) + (report.get("dire_pos_1_to_5") or [])
    steam_base = "https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react"
    urls = set()
    for p in players:
        h_url = p.get("hero_img") or (f"{steam_base}/heroes/{p['hero_key']}.png" if p.get("hero_key") else "")
        if h_url:
            urls.add(h_url)
        for it in (p.get("final_items_rich") or []):
            it_key = it.get("item_key") or it.get("key")
            it_url = it.get("img") or (f"{steam_base}/items/{it_key}.png" if it_key else "")
            if it_url:
                urls.add(it_url)
        n_it = p.get("neutral_item_rich") or {}
        n_key = n_it.get("item_key") or n_it.get("key")
        n_url = n_it.get("img") or (f"{steam_base}/items/{n_key}.png" if n_key else "")
        if n_url:
            urls.add(n_url)

    missing = [u for u in urls if u and u not in _ICON_B64_CACHE]
    if allow_network and missing:
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


_LLM_TASK_POOL = ThreadPoolExecutor(max_workers=4)

_SENSITIVE_ERROR_MARKERS = (
    "Traceback",
    "invalid literal",
    'File "',
    "/Users/",
    "/home/",
    "/var/",
    "/etc/",
    "/tmp/",
    "\\",
    ".py",
    "ValueError",
    "TypeError",
    "KeyError",
    "RuntimeError",
    "URLError",
    "HTTPError",
)


def _sanitize_client_error(raw_err: Any, fallback: str = "请求处理失败，请稍后重试") -> str:
    txt = str(raw_err or "").strip()
    if not txt:
        return fallback
    if any(m in txt for m in _SENSITIVE_ERROR_MARKERS):
        return fallback
    if not any("\u4e00" <= ch <= "\u9fff" for ch in txt):
        return fallback
    return txt


def _execute_llm_review_task(
    task_id: str,
    match_id: int,
    side: str,
    report: Dict[str, Any],
    tone_mode: str = "coach",
) -> Dict[str, Any]:
    running_state = {
        "task_id": task_id,
        "match_id": int(match_id),
        "side": side,
        "status": "running",
        "updated_at": int(time.time()),
    }
    cloud_save_llm_task(task_id, running_state)
    try:
        res = call_llm_coach_review(report=report, tone_mode=tone_mode)
        if res.get("ok") and res.get("structured"):
            res["structured"] = sanitize_report_mixed_english(res["structured"])
            report["grok_coaching"] = res["structured"]
            rep_txt = json.dumps(report, ensure_ascii=False, separators=(",", ":"))
            try:
                (REPORTS_DIR / f"match_{int(match_id)}.json").write_text(rep_txt, encoding="utf-8")
            except OSError:
                TMP_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
                (TMP_REPORTS_DIR / f"match_{int(match_id)}.json").write_text(rep_txt, encoding="utf-8")
            try:
                cloud_save_match_report(int(match_id), report)
            except Exception:
                pass
            try:
                refresh_persisted_squad_ledger(REPORTS_DIR, load_roster(), [])
            except Exception:
                pass
            sanitized_rep = sanitize_report_mixed_english(report)
            done_state = {
                "task_id": task_id,
                "match_id": int(match_id),
                "side": side,
                "status": "completed",
                "structured": res["structured"],
                "report": sanitized_rep,
                "model": res.get("model") or res["structured"].get("model"),
                "provider": res.get("provider") or res["structured"].get("provider"),
                "updated_at": int(time.time()),
            }
            cloud_save_llm_task(task_id, done_state)
            return done_state
        else:
            raw_err = res.get("error")
            if raw_err:
                sys.stderr.write(f"[DotaLedgerServer] LLM review failed ({task_id}): {raw_err}\n")
            err_msg = _sanitize_client_error(raw_err, "大模型判词生成失败，请稍后重试")
            fail_state = {
                "task_id": task_id,
                "match_id": int(match_id),
                "side": side,
                "status": "failed",
                "error": err_msg,
                "updated_at": int(time.time()),
            }
            cloud_save_llm_task(task_id, fail_state)
            return fail_state
    except Exception:
        traceback.print_exc(file=sys.stderr)
        fail_state = {
            "task_id": task_id,
            "match_id": int(match_id),
            "side": side,
            "status": "failed",
            "error": "判词后台任务执行失败，请稍后重试",
            "updated_at": int(time.time()),
        }
        cloud_save_llm_task(task_id, fail_state)
        return fail_state


def start_async_llm_review_task(
    match_id: int,
    side: str,
    report: Dict[str, Any],
    run_async: bool = True,
    tone_mode: str = "coach",
) -> Dict[str, Any]:
    task_id = f"llm-{int(match_id)}-{side}-{int(time.time() * 1000)}"
    init_state = {
        "task_id": task_id,
        "match_id": int(match_id),
        "side": side,
        "status": "pending",
        "created_at": int(time.time()),
        "updated_at": int(time.time()),
    }
    cloud_save_llm_task(task_id, init_state)
    if run_async:
        _LLM_TASK_POOL.submit(_execute_llm_review_task, task_id, int(match_id), side, report, tone_mode)
        return {
            "ok": True,
            "task_id": task_id,
            "match_id": int(match_id),
            "side": side,
            "status": "pending",
        }
    final_state = _execute_llm_review_task(task_id, int(match_id), side, report, tone_mode)
    return {
        "ok": final_state.get("status") == "completed",
        **final_state,
    }


CSP_REPORT_ONLY_VALUE = (
    "default-src 'self'; "
    "script-src 'self' https://cdnjs.cloudflare.com; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob: https:; "
    "connect-src 'self'; "
    "font-src 'self' data:; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'"
)


class DotaAnalystHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write(f"[DotaLedgerServer] {self.address_string()} - {fmt % args}\n")

    def _accepts_gzip(self) -> bool:
        if not hasattr(self, "headers") or not self.headers:
            return False
        return "gzip" in str(self.headers.get("Accept-Encoding") or "").lower()

    def _send_json(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        use_gzip = self._accepts_gzip() and len(body) >= 512
        if use_gzip:
            body = gzip.compress(body, compresslevel=9)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        if use_gzip:
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Vary", "Accept-Encoding")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Robots-Tag", "noindex")
        self.send_header("Content-Security-Policy-Report-Only", CSP_REPORT_ONLY_VALUE)
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

    def do_HEAD(self) -> None:
        self.do_GET()

    def _has_provided_valid_token(self) -> bool:
        if not hasattr(self, "headers") or not self.headers:
            return False
        provided = (self.headers.get("X-Team-Token") or "").strip()
        if not provided:
            return False
        ok, _, _ = check_team_token_auth(provided)
        return bool(ok)

    def do_GET(self) -> None:
        path, qs = self._resolve_path_and_qs()
        has_token = self._has_provided_valid_token()

        try:
            if path == "/favicon.ico":
                self.send_response(204)
                self.send_header("Cache-Control", "public, max-age=86400")
                self.end_headers()
                return

            if path == "/api/match_icons":
                mid_str = (qs.get("match_id") or [""])[0].strip()
                mid = int(mid_str) if mid_str.isdigit() else 0
                icons = fetch_match_icons_base64(mid, allow_network=has_token) if mid else {}
                self._send_json({"ok": True, "match_id": mid, "icons": icons})
                return

            if path == "/api/heroes":
                hero_map, _ = get_hero_constants_map(allow_network=has_token)
                heroes_list = sorted(hero_map.values(), key=lambda x: x["id"])
                self._send_json({"ok": True, "heroes": heroes_list})
                return

            if path == "/api/init":
                roster = load_roster()
                main_id = int(roster.get("main_account_id") or 0)
                recent = fetch_recent_matches_formatted(main_id, limit=12, allow_network=has_token) if main_id else []
                wins = sum(1 for m in recent if m.get("won"))
                losses = len(recent) - wins
                win_rate = round((wins / len(recent)) * 100, 1) if recent else 0.0
                latest_mid = None
                analyzed_in_recent = [m for m in recent if m.get("is_analyzed")]
                if analyzed_in_recent:
                    latest_mid = int(analyzed_in_recent[0]["match_id"])
                else:
                    existing_files = sorted(REPORTS_DIR.glob("match_*.json"), reverse=True)
                    for ef in existing_files:
                        m_id = re.fullmatch(r"match_(\d+)\.json", ef.name)
                        if m_id:
                            latest_mid = int(m_id.group(1))
                            break
                profile_obj = {
                    "profile": {
                        "account_id": main_id,
                        "personaname": roster.get("main_name") or roster.get("main_player_name") or "主视角玩家",
                        "rank_label": "万古流芳 5 [75]",
                    },
                    "wl": {"win": wins, "lose": losses, "win_rate": win_rate},
                    "recent_matches": recent,
                }
                squad_ledger = load_or_build_squad_ledger(REPORTS_DIR, roster, recent, allow_write=has_token)
                hero_map, _ = get_hero_constants_map(allow_network=has_token)
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
                    "latest_match_id": latest_mid,
                })
                return

            if path in ("/api/recent", "/api/player"):
                raw_q = (qs.get("query") or qs.get("q") or qs.get("account_id") or [""])[0].strip()
                roster = load_roster()
                aid = resolve_player_input(raw_q) if raw_q else int(roster.get("main_account_id") or 0)
                recent = fetch_recent_matches_formatted(aid, limit=12, allow_network=has_token)
                wins = sum(1 for m in recent if m.get("won"))
                losses = len(recent) - wins
                win_rate = round((wins / len(recent)) * 100, 1) if recent else 0.0
                analyzed_in_recent = [m for m in recent if m.get("is_analyzed")]
                latest_mid = int(analyzed_in_recent[0]["match_id"]) if analyzed_in_recent else None
                profile_obj = {
                    "profile": {
                        "account_id": aid,
                        "personaname": str(aid),
                        "rank_label": "Dota 2 玩家",
                    },
                    "wl": {"win": wins, "lose": losses, "win_rate": win_rate},
                    "recent_matches": recent,
                }
                squad_ledger = load_or_build_squad_ledger(REPORTS_DIR, roster, recent, allow_write=has_token)
                self._send_json({
                    "ok": True,
                    "account_id": aid,
                    "profile": profile_obj,
                    "recent_matches": recent,
                    "squad_ledger": squad_ledger,
                    "latest_match_id": latest_mid,
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
                if force or analyze_now:
                    if not self._require_team_token():
                        return
                aid_str = (qs.get("account_id") or [""])[0].strip()
                aid = resolve_player_input(aid_str) if aid_str else None
                report = get_or_build_match_report(
                    mid,
                    focus_account_id=aid,
                    force_refresh=force,
                    allow_build=(force or analyze_now),
                    require_ai=False,
                    skip_llm=True,
                )
                if report is None:
                    self._send_json({
                        "ok": True,
                        "not_analyzed": True,
                        "match_id": mid,
                    })
                    return
                is_stale = bool(report.get("stale"))
                part_param = (qs.get("part") or [""])[0].strip().lower()
                if part_param in ("summary", "timeline", "microscope"):
                    resp_obj: Dict[str, Any] = {
                        "ok": True,
                        "part": part_param,
                        "report": extract_report_part(report, part_param),
                    }
                    if is_stale:
                        resp_obj["stale"] = True
                    self._send_json(resp_obj)
                    return
                resp_full: Dict[str, Any] = {"ok": True, "report": report}
                if is_stale:
                    resp_full["stale"] = True
                self._send_json(resp_full)
                return

            if path == "/api/llm_review_status":
                task_id = (qs.get("task_id") or [""])[0].strip()
                if not task_id:
                    self._send_json({"ok": False, "error": "缺少 task_id 参数"}, status=400)
                    return
                task_data = cloud_load_llm_task(task_id)
                if not isinstance(task_data, dict):
                    self._send_json({"ok": False, "error": "未找到对应的判词任务"}, status=404)
                    return
                safe_task = dict(task_data)
                if safe_task.get("error") is not None:
                    safe_task["error"] = _sanitize_client_error(
                        safe_task.get("error"), "判词后台任务执行失败，请稍后重试"
                    )
                self._send_json({"ok": True, **safe_task})
                return

            # 静态文件服务 (支持 /, /pregame, 以及公开分享链接 /match/<id>)
            is_html_route = path in ("/", "", "/pregame", "/pregame.html") or path.startswith("/match/")
            is_hashed_asset = False
            if is_html_route:
                file_path = STATIC_DIR / "index.html"
            else:
                rel = path.lstrip("/")
                if rel.startswith("static/"):
                    rel = rel[len("static/"):]
                m_js = re.fullmatch(r"app\.([0-9a-f]{8,})\.js", rel)
                m_css = re.fullmatch(r"styles\.([0-9a-f]{8,})\.css", rel)
                if m_js:
                    app_js_file = STATIC_DIR / "app.js"
                    cur_js_hash = hashlib.sha256(app_js_file.read_bytes()).hexdigest()[: len(m_js.group(1))] if app_js_file.is_file() else ""
                    if m_js.group(1) == cur_js_hash:
                        rel = "app.js"
                        is_hashed_asset = True
                elif m_css:
                    styles_css_file = STATIC_DIR / "styles.css"
                    cur_css_hash = hashlib.sha256(styles_css_file.read_bytes()).hexdigest()[: len(m_css.group(1))] if styles_css_file.is_file() else ""
                    if m_css.group(1) == cur_css_hash:
                        rel = "styles.css"
                        is_hashed_asset = True
                file_path = (STATIC_DIR / rel).resolve()
                if not str(file_path).startswith(str(STATIC_DIR.resolve())):
                    self._send_json({"ok": False, "error": "拒绝访问该路径"}, status=403)
                    return

            if not file_path.exists() or not file_path.is_file():
                self._send_json({"ok": False, "error": "未找到请求的资源"}, status=404)
                return

            ctype, _ = mimetypes.guess_type(str(file_path))
            if not ctype:
                ctype = "application/octet-stream"
            if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
                ctype += "; charset=utf-8"

            content = file_path.read_bytes()
            etag = f'"{hashlib.sha256(content).hexdigest()[:16]}"'
            is_static_bundle = file_path.suffix.lower() in (".js", ".css") and is_hashed_asset
            cache_ctrl = "public, max-age=31536000, immutable" if is_static_bundle else "no-cache"

            inm = (self.headers.get("If-None-Match") or "").strip() if hasattr(self, "headers") and self.headers else ""
            if inm and inm == etag:
                self.send_response(304)
                self.send_header("Cache-Control", cache_ctrl)
                self.send_header("ETag", etag)
                self.send_header("X-Robots-Tag", "noindex")
                self.send_header("Content-Security-Policy-Report-Only", CSP_REPORT_ONLY_VALUE)
                self.end_headers()
                return

            is_compressible = (
                ctype.startswith("text/")
                or "javascript" in ctype
                or "json" in ctype
                or "svg" in ctype
            )
            use_gzip = is_compressible and self._accepts_gzip() and len(content) >= 512
            wire_body = gzip.compress(content, compresslevel=9) if use_gzip else content

            self.send_response(200)
            self.send_header("Content-Type", ctype)
            if use_gzip:
                self.send_header("Content-Encoding", "gzip")
                self.send_header("Vary", "Accept-Encoding")
            self.send_header("Content-Length", str(len(wire_body)))
            self.send_header("Cache-Control", cache_ctrl)
            self.send_header("ETag", etag)
            self.send_header("X-Robots-Tag", "noindex")
            self.send_header("Content-Security-Policy-Report-Only", CSP_REPORT_ONLY_VALUE)
            self.end_headers()
            self.wfile.write(wire_body)

        except ValueError as ve:
            sys.stderr.write(f"[DotaLedgerServer] ValueError on GET {path}: {ve}\n")
            self._send_json({"ok": False, "error": "请求参数格式无效，请检查后重试"}, status=400)
        except PermissionError as pe:
            sys.stderr.write(f"[DotaLedgerServer] PermissionError on GET {path}: {pe}\n")
            self._send_json({"ok": False, "error": "该比赛不在车队花名册范围内，拒绝操作"}, status=403)
        except Exception:
            traceback.print_exc(file=sys.stderr)
            self._send_json({"ok": False, "error": "服务器内部错误，请稍后重试"}, status=500)

    def _require_team_token(self) -> bool:
        provided = self.headers.get("X-Team-Token") or ""
        ok, status, err_msg = check_team_token_auth(provided)
        if not ok:
            self._send_json(
                {"ok": False, "need_team_token": status == 401, "error": err_msg},
                status=status,
            )
            return False
        return True

    def do_POST(self) -> None:
        path, qs = self._resolve_path_and_qs()

        try:
            if not self._require_team_token():
                return

            if path == "/api/pregame_plan":
                body = self._read_json_body()
                own_picks = body.get("own_picks") or body.get("our_heroes") or []
                enemy_picks = body.get("enemy_picks") or body.get("enemy_heroes") or []
                use_llm = bool(body.get("use_llm", False))
                roster = load_roster()
                hero_map, _ = get_hero_constants_map()
                plan = build_pregame_strategy_plan(own_picks, enemy_picks, roster, hero_map)
                if use_llm:
                    llm_res = call_llm_pregame_coach(plan=plan)
                    if llm_res.get("ok") and llm_res.get("grok_live_brief"):
                        plan["grok_live_brief"] = llm_res["grok_live_brief"]
                    elif llm_res.get("error"):
                        sys.stderr.write(f"[DotaLedgerServer] Pregame LLM error: {llm_res.get('error')}\n")
                        plan["llm_error"] = _sanitize_client_error(llm_res["error"], "赛前建议生成失败，请稍后重试")
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
                    mname = body.get("main_name") or body.get("main_player_name") or roster.get("main_name") or "主视角玩家"
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
                save_roster(roster)
                self._send_json({"ok": True, "roster": roster})
                return

            if path == "/api/player_goals":
                import cloud_store
                from dota_analyst import resolve_canonical_account_id
                from draft_and_phase_coach import refresh_persisted_squad_ledger

                body = self._read_json_body()
                roster = load_roster()
                raw_aid = body.get("account_id")
                if not raw_aid:
                    self._send_json({"ok": False, "error": "缺少队员 account_id"}, status=400)
                    return
                aid = int(resolve_canonical_account_id(int(raw_aid), roster) or int(raw_aid))
                action = str(body.get("action") or "save").strip().lower()
                if action in ("clear", "delete"):
                    cloud_store.cloud_upsert_player_goal(aid, None)
                    ledger = refresh_persisted_squad_ledger(REPORTS_DIR, roster, [], persist_disk=True)
                    self._send_json({
                        "ok": True,
                        "account_id": aid,
                        "goal": None,
                        "personal_trends_and_goals": ledger.get("personal_trends_and_goals") or {"players": {}},
                    })
                    return

                allowed_metrics = {
                    "non_teamfight_deaths_after_10m": ("max", lambda t: f"10分钟后团战外阵亡 <= {t:g} 次/局"),
                    "lane_nw_diff_10m": ("min", lambda t: f"对位10分钟净值差 >= {t:+g}"),
                    "support_wards_per_min": ("min", lambda t: f"辅助每分钟插眼数 >= {t:g}/m"),
                    "key_item_timing_delta_sec": ("max", lambda t: f"关键装相对中位数偏差 <= {t:+g}s"),
                }
                metric = str(body.get("metric") or "").strip()
                if metric not in allowed_metrics:
                    self._send_json({"ok": False, "error": "不支持的目标指标"}, status=400)
                    return
                raw_target = body.get("target")
                if raw_target is None or str(raw_target).strip() == "":
                    self._send_json({"ok": False, "error": "请输入目标数值"}, status=400)
                    return
                target_val = round(float(raw_target), 2)
                default_dir, label_fn = allowed_metrics[metric]
                direction = str(body.get("direction") or default_dir)
                if direction not in ("min", "max"):
                    direction = default_dir
                label_zh = str(body.get("label_zh") or label_fn(target_val))
                goal_obj = {
                    "metric": metric,
                    "direction": direction,
                    "target": target_val,
                    "label_zh": label_zh,
                }
                cloud_store.cloud_upsert_player_goal(aid, goal_obj)
                ledger = refresh_persisted_squad_ledger(REPORTS_DIR, roster, [], persist_disk=True)
                self._send_json({
                    "ok": True,
                    "account_id": aid,
                    "goal": goal_obj,
                    "personal_trends_and_goals": ledger.get("personal_trends_and_goals") or {"players": {}},
                })
                return

            if path in ("/api/llm_review", "/api/llm_coach"):
                body = self._read_json_body()
                mid = int(body.get("match_id"))
                side = body.get("side") or "dire"
                force = bool(body.get("force", True))
                tone_mode = "roast" if str(body.get("tone_mode") or "").strip().lower() == "roast" else "coach"

                # Fast-path: load existing match report from local/tmp disk in 0ms without blocking on OpenDota parse polling
                report = None
                for jc_fast in (TMP_REPORTS_DIR / f"match_{mid}.json", REPORTS_DIR / f"match_{mid}.json"):
                    if jc_fast.exists():
                        try:
                            cand_rep = json.loads(jc_fast.read_text(encoding="utf-8"))
                            if isinstance(cand_rep, dict) and cand_rep.get("match_id"):
                                report = _hydrate_grok_from_caches(cand_rep, mid)
                                break
                        except Exception:
                            pass
                if not isinstance(report, dict):
                    report = get_or_build_match_report(mid, allow_build=True, require_ai=False, skip_llm=True)

                cached_gc = report.get("grok_coaching") if isinstance(report, dict) else None
                cached_tone = ((cached_gc or {}).get("_meta") or {}).get("tone_mode") or "coach"
                if (
                    not force
                    and isinstance(report, dict)
                    and _has_complete_grok_coaching(cached_gc)
                    and cached_tone == tone_mode
                ):
                    self._send_json({
                        "ok": True,
                        "task_id": f"cached-{mid}-{side}",
                        "status": "completed",
                        "cached": True,
                        "structured": report["grok_coaching"],
                        "report": sanitize_report_mixed_english(report),
                    })
                    return
                run_async = not bool(body.get("sync", False))
                task_resp = start_async_llm_review_task(
                    match_id=mid,
                    side=side,
                    report=report,
                    run_async=run_async,
                    tone_mode=tone_mode,
                )
                self._send_json(task_resp)
                return

            if path == "/api/poster_art":
                body = self._read_json_body()
                mid_raw = body.get("match_id")
                player_slot = body.get("player_slot")
                style_mode = str(body.get("style_mode") or "auto")
                cosmetic_mode = str(body.get("cosmetic_mode") or "arcana")
                custom_scene = str(body.get("custom_scene") or "")
                engine_pref = str(body.get("engine_pref") or "auto")
                career_member = body.get("career_member")
                force = bool(body.get("force", False))

                report = None
                if mid_raw:
                    try:
                        mid = int(mid_raw)
                        report = get_or_build_match_report(mid, allow_build=True, require_ai=False, skip_llm=True)
                    except Exception:
                        report = body.get("report")
                elif isinstance(body.get("report"), dict):
                    report = body.get("report")

                res = call_nano_banana_poster_art(
                    report=report,
                    player_slot=int(player_slot) if player_slot is not None and str(player_slot) != "" else None,
                    style_mode=style_mode,
                    cosmetic_mode=cosmetic_mode,
                    custom_scene=custom_scene,
                    engine_pref=engine_pref,
                    career_member=career_member if isinstance(career_member, dict) else None,
                    force=force,
                )
                if isinstance(res, dict) and not res.get("ok") and res.get("error"):
                    sys.stderr.write(f"[DotaLedgerServer] Poster error: {res.get('error')}\n")
                    res = dict(res)
                    res["error"] = _sanitize_client_error(res.get("error"), "海报生成失败，请稍后重试")
                self._send_json(res)
                return

            self._send_json({"ok": False, "error": "请求的接口不存在"}, status=404)
        except ValueError as ve:
            sys.stderr.write(f"[DotaLedgerServer] ValueError on POST {path}: {ve}\n")
            self._send_json({"ok": False, "error": "请求参数格式无效，请检查后重试"}, status=400)
        except PermissionError as pe:
            sys.stderr.write(f"[DotaLedgerServer] PermissionError on POST {path}: {pe}\n")
            self._send_json({"ok": False, "error": "该比赛不在车队花名册范围内，拒绝操作"}, status=403)
        except Exception:
            traceback.print_exc(file=sys.stderr)
            self._send_json({"ok": False, "error": "服务器内部错误，请稍后重试"}, status=500)


def main() -> None:
    port = int(os.environ.get("PORT", "8788"))
    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer(("127.0.0.1", port), DotaAnalystHandler)
    print(f"{SITE_NAME} ({SITE_SUBTITLE}) 已启动: http://127.0.0.1:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
