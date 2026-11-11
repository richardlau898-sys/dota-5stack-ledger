#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dota 2 战后算账 & 赛前锦囊 - 云端持久化数据库引擎 (cloud_store.py)
基于 Supabase PostgreSQL (`dota_match_reports`, `match_players`, `dota_llm_tasks`) 与 Supabase Storage (`dota-reports`)，
零外部依赖，纯 Python 标准库 `urllib.request`。
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

BASE_DIR = Path(__file__).resolve().parent
REPORTS_DIR = BASE_DIR / "reports"
TMP_REPORTS_DIR = Path("/tmp/dota_reports")


def _load_env_vars() -> Dict[str, str]:
    env = dict(os.environ)
    for fname in (".env.local", ".env"):
        fpath = BASE_DIR / fname
        if fpath.exists():
            try:
                for line in fpath.read_text(encoding="utf-8", errors="ignore").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k and k not in env:
                        env[k] = v
            except Exception:
                pass
    return env


def get_cloud_config() -> Dict[str, str]:
    env = _load_env_vars()
    return {
        "supabase_url": (env.get("SUPABASE_URL") or env.get("NEXT_PUBLIC_SUPABASE_URL") or "").rstrip("/"),
        "supabase_key": (
            env.get("SUPABASE_SERVICE_ROLE_KEY")
            or env.get("SUPABASE_SECRET_KEY")
            or env.get("SUPABASE_KEY")
            or ""
        ).strip(),
        "supabase_bucket": (env.get("SUPABASE_BUCKET") or "dota-reports").strip(),
    }


def get_cloud_db_status_safe() -> Dict[str, Any]:
    cfg = get_cloud_config()
    has_supabase = bool(cfg["supabase_url"] and cfg["supabase_key"])
    backends = ["Supabase PostgreSQL/Storage"] if has_supabase else []
    return {
        "configured": has_supabase,
        "has_supabase": has_supabase,
        "backends": backends,
        "label": "Supabase PostgreSQL/Storage" if has_supabase else "Local /tmp Cache Only",
    }


def _supabase_headers(key: str, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    h = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "User-Agent": "dota-ai-analyst-cloud-store/2.0",
    }
    if extra:
        h.update(extra)
    return h


def extract_match_players_rows(report_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
    """从复盘报告提取 10 名玩家的标准化行，用于写入 match_players 表做跨局 SQL 统计"""
    if not isinstance(report_dict, dict) or not report_dict.get("match_id"):
        return []
    mid = int(report_dict["match_id"])
    rad_win = bool(report_dict.get("radiant_win"))
    start_time_str = str(report_dict.get("start_time_str") or "")
    duration_min = float(report_dict.get("duration_min") or 0.0)
    rows: List[Dict[str, Any]] = []
    for side_key, list_key in (("radiant", "radiant_pos_1_to_5"), ("dire", "dire_pos_1_to_5")):
        side_won = rad_win if side_key == "radiant" else (not rad_win)
        for p in report_dict.get(list_key) or []:
            if not isinstance(p, dict):
                continue
            rows.append({
                "match_id": mid,
                "player_slot": int(p.get("player_slot") or 0),
                "account_id": int(p["account_id"]) if p.get("account_id") is not None else None,
                "personaname": str(p.get("personaname") or "匿名玩家"),
                "side": side_key,
                "pos": int(p.get("pos") or 0),
                "hero_id": int(p.get("hero_id") or 0),
                "hero_short_zh": str(p.get("hero_short_zh") or ""),
                "won": side_won,
                "kills": int(p.get("kills") or 0),
                "deaths": int(p.get("deaths") or 0),
                "assists": int(p.get("assists") or 0),
                "net_worth": int(p.get("net_worth") or 0),
                "gpm": int(p.get("gpm") or 0),
                "xpm": int(p.get("xpm") or 0),
                "hero_damage": int(p.get("hero_damage") or 0),
                "tower_damage": int(p.get("tower_damage") or 0),
                "score_100": float(p["score_100"]) if p.get("score_100") is not None else None,
                "blame_share_pct": float(p.get("blame_share_pct") or 0.0),
                "contrib_share_pct": float(p.get("contrib_share_pct") or 0.0),
                "start_time_str": start_time_str,
                "duration_min": duration_min,
            })
    return rows


def _supabase_save_match_players(match_id: int, report_dict: Dict[str, Any], cfg: Dict[str, str]) -> bool:
    url = cfg["supabase_url"]
    key = cfg["supabase_key"]
    if not url or not key:
        return False
    rows = extract_match_players_rows(report_dict)
    if not rows:
        return False
    try:
        req_data = json.dumps(rows, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            f"{url}/rest/v1/match_players?on_conflict=match_id,player_slot",
            data=req_data,
            method="POST",
            headers=_supabase_headers(
                key,
                {
                    "Content-Type": "application/json",
                    "Prefer": "resolution=merge-duplicates,return=minimal",
                },
            ),
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in (200, 201, 204)
    except Exception:
        return False


def _supabase_save_report(match_id: int, report_dict: Dict[str, Any], cfg: Dict[str, str]) -> bool:
    url = cfg["supabase_url"]
    key = cfg["supabase_key"]
    if not url or not key:
        return False

    f_side = report_dict.get("focus_side") or "dire"
    won = bool(
        report_dict.get(
            "user_won",
            report_dict.get("radiant_win") if f_side == "radiant" else not report_dict.get("radiant_win"),
        )
    )
    row_payload = {
        "match_id": int(match_id),
        "engine_version": str(report_dict.get("engine_version") or ""),
        "focus_side": f_side,
        "won": won,
        "score": report_dict.get("score") or f"{report_dict.get('radiant_score', 0)}:{report_dict.get('dire_score', 0)}",
        "duration_str": report_dict.get("duration_str") or "",
        "start_time_str": report_dict.get("start_time_str") or "",
        "is_parsed": bool(report_dict.get("is_parsed", True)),
        "has_grok": bool(report_dict.get("grok_coaching")),
        "report_json": report_dict,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    saved = False
    try:
        req_data = json.dumps(row_payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        req = urllib.request.Request(
            f"{url}/rest/v1/dota_match_reports?on_conflict=match_id",
            data=req_data,
            method="POST",
            headers=_supabase_headers(
                key,
                {
                    "Content-Type": "application/json",
                    "Prefer": "resolution=merge-duplicates,return=minimal",
                },
            ),
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            if resp.status in (200, 201, 204):
                saved = True
    except Exception:
        pass

    _supabase_save_match_players(int(match_id), report_dict, cfg)
    if saved:
        return True

    bucket = cfg["supabase_bucket"]
    try:
        raw_bytes = json.dumps(report_dict, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        up_req = urllib.request.Request(
            f"{url}/storage/v1/object/{bucket}/match_{match_id}.json",
            data=raw_bytes,
            method="POST",
            headers=_supabase_headers(
                key,
                {
                    "Content-Type": "application/json",
                    "x-upsert": "true",
                },
            ),
        )
        with urllib.request.urlopen(up_req, timeout=12) as resp:
            return resp.status in (200, 201)
    except Exception:
        return False


def _supabase_fetch_report(match_id: int, cfg: Dict[str, str]) -> Optional[Dict[str, Any]]:
    url = cfg["supabase_url"]
    key = cfg["supabase_key"]
    if not url or not key:
        return None

    try:
        req = urllib.request.Request(
            f"{url}/rest/v1/dota_match_reports?match_id=eq.{int(match_id)}&select=report_json",
            headers=_supabase_headers(key, {"Accept": "application/json"}),
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            rows = json.loads(resp.read().decode("utf-8"))
            if isinstance(rows, list) and rows and isinstance(rows[0].get("report_json"), dict):
                return rows[0]["report_json"]
    except Exception:
        pass

    bucket = cfg["supabase_bucket"]
    try:
        req = urllib.request.Request(
            f"{url}/storage/v1/object/{bucket}/match_{int(match_id)}.json",
            headers=_supabase_headers(key),
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, dict) and data.get("match_id"):
                return data
    except Exception:
        pass

    return None


def _supabase_list_analyzed_ids(cfg: Dict[str, str]) -> Set[int]:
    url = cfg["supabase_url"]
    key = cfg["supabase_key"]
    ids: Set[int] = set()
    if not url or not key:
        return ids

    try:
        req = urllib.request.Request(
            f"{url}/rest/v1/dota_match_reports?select=match_id&limit=500",
            headers=_supabase_headers(key, {"Accept": "application/json"}),
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            rows = json.loads(resp.read().decode("utf-8"))
            if isinstance(rows, list):
                for r in rows:
                    if r.get("match_id"):
                        ids.add(int(r["match_id"]))
    except Exception:
        pass
    return ids


def cloud_save_raw_match(match_id: int, raw_match: Dict[str, Any]) -> bool:
    """将 OpenDota 原始比赛 JSON 存入 Supabase Storage (`dota-reports/raw/raw_<id>.json`)"""
    if not match_id or not isinstance(raw_match, dict):
        return False
    cfg = get_cloud_config()
    url = cfg["supabase_url"]
    key = cfg["supabase_key"]
    bucket = cfg["supabase_bucket"]
    if not url or not key:
        return False
    try:
        raw_bytes = json.dumps(raw_match, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        req = urllib.request.Request(
            f"{url}/storage/v1/object/{bucket}/raw/raw_{int(match_id)}.json",
            data=raw_bytes,
            method="POST",
            headers=_supabase_headers(
                key,
                {
                    "Content-Type": "application/json",
                    "x-upsert": "true",
                },
            ),
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status in (200, 201)
    except Exception:
        return False


def cloud_fetch_raw_match(match_id: int) -> Optional[Dict[str, Any]]:
    """从 Supabase Storage 读取原始比赛 JSON (`dota-reports/raw/raw_<id>.json`)"""
    if not match_id:
        return None
    cfg = get_cloud_config()
    url = cfg["supabase_url"]
    key = cfg["supabase_key"]
    bucket = cfg["supabase_bucket"]
    if not url or not key:
        return None
    try:
        req = urllib.request.Request(
            f"{url}/storage/v1/object/{bucket}/raw/raw_{int(match_id)}.json",
            headers=_supabase_headers(key),
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, dict) and data.get("match_id"):
                return data
    except Exception:
        pass
    return None


_CLOUD_IDS_CACHE: Dict[str, Any] = {"ts": 0.0, "ids": set()}


def get_cloud_analyzed_match_ids(ttl_sec: int = 45) -> Set[int]:
    now = time.time()
    if now - _CLOUD_IDS_CACHE["ts"] < ttl_sec and _CLOUD_IDS_CACHE["ids"]:
        return set(_CLOUD_IDS_CACHE["ids"])

    cfg = get_cloud_config()
    ids: Set[int] = set()
    if cfg["supabase_url"] and cfg["supabase_key"]:
        ids.update(_supabase_list_analyzed_ids(cfg))

    if ids:
        _CLOUD_IDS_CACHE["ts"] = now
        _CLOUD_IDS_CACHE["ids"] = set(ids)
    return ids


def cloud_save_match_report(match_id: int, report_dict: Dict[str, Any]) -> bool:
    """将复盘报告与 10 人明细持久化到 Supabase（唯一数据源）"""
    if not match_id or not isinstance(report_dict, dict):
        return False

    _CLOUD_IDS_CACHE["ids"].add(int(match_id))
    _CLOUD_IDS_CACHE["ts"] = time.time()

    cfg = get_cloud_config()
    if cfg["supabase_url"] and cfg["supabase_key"]:
        return _supabase_save_report(int(match_id), report_dict, cfg)
    return False


def cloud_fetch_match_report(match_id: int, persist_tmp: bool = True) -> Optional[Dict[str, Any]]:
    """从 Supabase 拉取复盘报告（仅在 persist_tmp=True 时写 /tmp 缓存）"""
    if not match_id:
        return None

    cfg = get_cloud_config()
    rep = None
    if cfg["supabase_url"] and cfg["supabase_key"]:
        rep = _supabase_fetch_report(int(match_id), cfg)

    if isinstance(rep, dict) and rep.get("match_id"):
        _CLOUD_IDS_CACHE["ids"].add(int(match_id))
        if persist_tmp:
            try:
                TMP_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
                (TMP_REPORTS_DIR / f"match_{int(match_id)}.json").write_text(
                    json.dumps(rep, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
                )
            except Exception:
                pass
        return rep
    return None


def cloud_save_coaching(match_id: int, side: str, coaching_dict: Dict[str, Any]) -> bool:
    """将判词 JSON 存入 Supabase Storage"""
    if not match_id or not isinstance(coaching_dict, dict):
        return False
    cfg = get_cloud_config()
    url = cfg["supabase_url"]
    key = cfg["supabase_key"]
    bucket = cfg["supabase_bucket"]
    if not url or not key:
        return False
    try:
        raw_bytes = json.dumps(coaching_dict, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        req = urllib.request.Request(
            f"{url}/storage/v1/object/{bucket}/coaching/coaching-{int(match_id)}-{side}.json",
            data=raw_bytes,
            method="POST",
            headers=_supabase_headers(
                key,
                {
                    "Content-Type": "application/json",
                    "x-upsert": "true",
                },
            ),
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in (200, 201)
    except Exception:
        return False


# =========================================================================
# Async LLM Review Task State Persistence (Supabase + /tmp cache)
# =========================================================================

_LLM_TASKS_MEM: Dict[str, Dict[str, Any]] = {}


def _supabase_upsert_llm_task(task_id: str, task_obj: Dict[str, Any], cfg: Optional[Dict[str, str]] = None) -> bool:
    if cfg is None:
        cfg = get_cloud_config()
    url = cfg.get("supabase_url") or ""
    key = cfg.get("supabase_key") or ""
    if not url or not key:
        return False

    row_payload = {
        "task_id": str(task_id),
        "match_id": int(task_obj.get("match_id") or 0),
        "side": str(task_obj.get("side") or "dire"),
        "status": str(task_obj.get("status") or "pending"),
        "error": task_obj.get("error"),
        "task_json": task_obj,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    try:
        req = urllib.request.Request(
            f"{url}/rest/v1/dota_llm_tasks?on_conflict=task_id",
            data=json.dumps(row_payload, ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers=_supabase_headers(key, {"Prefer": "resolution=merge-duplicates,return=minimal"}),
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            if 200 <= resp.status < 300:
                return True
    except Exception:
        pass

    bucket = cfg.get("supabase_bucket") or "dota-reports"
    try:
        req = urllib.request.Request(
            f"{url}/storage/v1/object/{bucket}/tasks/{task_id}.json",
            data=json.dumps(task_obj, ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers=_supabase_headers(key, {"x-upsert": "true"}),
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False


def _supabase_fetch_llm_task(task_id: str, cfg: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
    if cfg is None:
        cfg = get_cloud_config()
    url = cfg.get("supabase_url") or ""
    key = cfg.get("supabase_key") or ""
    if not url or not key:
        return None

    try:
        req = urllib.request.Request(
            f"{url}/rest/v1/dota_llm_tasks?task_id=eq.{urllib.parse.quote(str(task_id))}&select=task_json",
            headers=_supabase_headers(key, {"Accept": "application/json"}),
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            rows = json.loads(resp.read().decode("utf-8"))
            if isinstance(rows, list) and rows and isinstance(rows[0].get("task_json"), dict):
                return rows[0]["task_json"]
    except Exception:
        pass

    bucket = cfg.get("supabase_bucket") or "dota-reports"
    try:
        req = urllib.request.Request(
            f"{url}/storage/v1/object/{bucket}/tasks/{urllib.parse.quote(str(task_id))}.json",
            headers=_supabase_headers(key),
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, dict) and data.get("task_id"):
                return data
    except Exception:
        pass
    return None


def cloud_save_llm_task(task_id: str, task_obj: Dict[str, Any]) -> bool:
    if not task_id or not isinstance(task_obj, dict):
        return False
    _LLM_TASKS_MEM[task_id] = dict(task_obj)
    try:
        tasks_dir = TMP_REPORTS_DIR / "tasks"
        tasks_dir.mkdir(parents=True, exist_ok=True)
        (tasks_dir / f"{task_id}.json").write_text(
            json.dumps(task_obj, ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        pass
    cfg = get_cloud_config()
    return _supabase_upsert_llm_task(task_id, task_obj, cfg)


def cloud_load_llm_task(task_id: str) -> Optional[Dict[str, Any]]:
    if not task_id:
        return None
    cfg = get_cloud_config()
    remote = _supabase_fetch_llm_task(task_id, cfg)
    if isinstance(remote, dict):
        _LLM_TASKS_MEM[task_id] = remote
        return remote
    if task_id in _LLM_TASKS_MEM:
        return _LLM_TASKS_MEM[task_id]
    try:
        p = TMP_REPORTS_DIR / "tasks" / f"{task_id}.json"
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                _LLM_TASKS_MEM[task_id] = data
                return data
    except Exception:
        pass
    return None


def cloud_upsert_player_matches(rows: List[Dict[str, Any]], cfg: Optional[Dict[str, str]] = None) -> bool:
    """F1: 批量写入或更新 public.player_matches 表"""
    if not rows:
        return True
    if cfg is None:
        cfg = get_cloud_config()
    url = cfg.get("supabase_url") or ""
    key = cfg.get("supabase_key") or ""
    if not url or not key:
        return False
    headers = _supabase_headers(
        key,
        {
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
    )
    ok_all = True
    for idx in range(0, len(rows), 500):
        batch = rows[idx : idx + 500]
        try:
            body = json.dumps(batch, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                f"{url}/rest/v1/player_matches?on_conflict=account_id,match_id",
                data=body,
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                if resp.status not in (200, 201, 204):
                    ok_all = False
        except Exception:
            ok_all = False
    return ok_all

