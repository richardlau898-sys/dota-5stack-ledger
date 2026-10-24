#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dota 2 战后算账 & 赛前锦囊 - 云端持久化数据库引擎 (cloud_store.py)
支持双核云端持久化 (零外部依赖，纯 Python 标准库 urllib.request):
1. Supabase 云数据库 / Storage (配置 SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY 即可自动读写 dota_match_reports 表与 dota-reports 存储桶)
2. GitHub Cloud JSON Database (配置 GITHUB_TOKEN + GITHUB_REPO 即可将每次新生成的复盘报告、Grok 4.7 毒舌判词、车队花名册实时回写至云端仓库)

工作原理:
- 写入时 (Write-Through): 本地/临时目录 (/tmp/dota_reports) 写入后，立即同步持久化至云端 (Supabase / GitHub API)。
- 读取与冷启动自愈 (Read-Through & Cold-Start Sync): 当 Vercel Serverless 容器重启或重新部署导致 /tmp 清空时，
  自动从云端拉取已分析比赛索引与完整 JSON 报告并回填至 /tmp/dota_reports，彻底杜绝“刚复盘完重新部署又显示未复盘”的问题。
"""

import base64
import json
import os
import re
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
        "github_token": (env.get("GITHUB_TOKEN") or env.get("GH_TOKEN") or "").strip(),
        "github_repo": (env.get("GITHUB_REPO") or "richardlau898-sys/dota-5stack-ledger").strip(),
        "github_branch": (env.get("GITHUB_BRANCH") or "main").strip(),
    }


def get_cloud_db_status_safe() -> Dict[str, Any]:
    cfg = get_cloud_config()
    has_supabase = bool(cfg["supabase_url"] and cfg["supabase_key"])
    has_github = bool(cfg["github_token"] and cfg["github_repo"])
    backends = []
    if has_supabase:
        backends.append("Supabase PostgreSQL/Storage")
    if has_github:
        backends.append(f"GitHub Cloud DB ({cfg['github_repo']})")
    return {
        "configured": has_supabase or has_github,
        "has_supabase": has_supabase,
        "has_github": has_github,
        "backends": backends,
        "label": " + ".join(backends) if backends else "Local Disk Only",
    }


# =========================================================================
# 1. Supabase PostgreSQL REST (`dota_match_reports`) & Storage (`dota-reports`)
# =========================================================================

def _supabase_headers(key: str, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    h = {
        "apikey": key,
        "User-Agent": "dota-ai-analyst-cloud-store/1.0",
    }
    # Only attach Bearer if key is a JWT (eyJ...); new sb_secret_... keys use apikey header directly
    if key.startswith("eyJ"):
        h["Authorization"] = f"Bearer {key}"
    else:
        h["Authorization"] = f"Bearer {key}"
    if extra:
        h.update(extra)
    return h


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

    # Try PostgREST table `dota_match_reports` upsert first
    try:
        req_data = json.dumps(row_payload, ensure_ascii=False).encode("utf-8")
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
                return True
    except Exception:
        pass

    # Fallback: Supabase Storage bucket `dota-reports/match_<id>.json`
    bucket = cfg["supabase_bucket"]
    try:
        raw_bytes = json.dumps(report_dict, ensure_ascii=False).encode("utf-8")
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

    # 1. Try PostgREST table `dota_match_reports`
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

    # 2. Try Supabase Storage bucket `dota-reports`
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
            f"{url}/rest/v1/dota_match_reports?select=match_id&limit=200",
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


# =========================================================================
# 2. GitHub Cloud JSON Database (Contents & Git Trees API)
# =========================================================================

def _github_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "dota-ai-analyst-cloud-db/1.0",
    }


def _github_save_file(rel_path: str, content_str: str, commit_msg: str, cfg: Dict[str, str]) -> bool:
    token = cfg["github_token"]
    repo = cfg["github_repo"]
    branch = cfg["github_branch"]
    if not token or not repo:
        return False

    api_url = f"https://api.github.com/repos/{repo}/contents/{rel_path.lstrip('/')}"
    existing_sha = None
    try:
        get_req = urllib.request.Request(
            f"{api_url}?ref={urllib.parse.quote(branch)}",
            headers=_github_headers(token),
        )
        with urllib.request.urlopen(get_req, timeout=8) as resp:
            meta = json.loads(resp.read().decode("utf-8"))
            existing_sha = meta.get("sha")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            pass
    except Exception:
        pass

    b64_content = base64.b64encode(content_str.encode("utf-8")).decode("ascii")
    payload: Dict[str, Any] = {
        "message": commit_msg,
        "content": b64_content,
        "branch": branch,
    }
    if existing_sha:
        payload["sha"] = existing_sha

    try:
        put_req = urllib.request.Request(
            api_url,
            data=json.dumps(payload).encode("utf-8"),
            method="PUT",
            headers={**_github_headers(token), "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(put_req, timeout=15) as resp:
            return resp.status in (200, 201)
    except Exception:
        return False


def _github_fetch_json_file(rel_path: str, cfg: Dict[str, str]) -> Optional[Dict[str, Any]]:
    token = cfg["github_token"]
    repo = cfg["github_repo"]
    branch = cfg["github_branch"]
    if not token or not repo:
        return None

    # Use raw media type so files up to 100MB are returned directly as raw JSON
    api_url = f"https://api.github.com/repos/{repo}/contents/{rel_path.lstrip('/')}?ref={urllib.parse.quote(branch)}"
    headers = _github_headers(token)
    headers["Accept"] = "application/vnd.github.raw+json"
    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw_txt = resp.read().decode("utf-8")
            data = json.loads(raw_txt)
            if isinstance(data, dict):
                return data
    except Exception:
        return None
    return None


def _github_list_analyzed_ids(cfg: Dict[str, str]) -> Set[int]:
    token = cfg["github_token"]
    repo = cfg["github_repo"]
    branch = cfg["github_branch"]
    ids: Set[int] = set()
    if not token or not repo:
        return ids

    api_url = f"https://api.github.com/repos/{repo}/contents/reports?ref={urllib.parse.quote(branch)}"
    try:
        req = urllib.request.Request(api_url, headers=_github_headers(token))
        with urllib.request.urlopen(req, timeout=7) as resp:
            items = json.loads(resp.read().decode("utf-8"))
            if isinstance(items, list):
                for item in items:
                    name = item.get("name") or ""
                    m = re.match(r"^match_(\d+)\.json$", name)
                    if m:
                        ids.add(int(m.group(1)))
    except Exception:
        pass
    return ids


# =========================================================================
# 3. Unified Public Cloud Store API (Used by server.py & dota_analyst.py)
# =========================================================================

_CLOUD_IDS_CACHE: Dict[str, Any] = {"ts": 0.0, "ids": set()}


def get_cloud_analyzed_match_ids(ttl_sec: int = 45) -> Set[int]:
    now = time.time()
    if now - _CLOUD_IDS_CACHE["ts"] < ttl_sec and _CLOUD_IDS_CACHE["ids"]:
        return set(_CLOUD_IDS_CACHE["ids"])

    cfg = get_cloud_config()
    ids: Set[int] = set()
    if cfg["supabase_url"] and cfg["supabase_key"]:
        ids.update(_supabase_list_analyzed_ids(cfg))
    if cfg["github_token"] and cfg["github_repo"]:
        ids.update(_github_list_analyzed_ids(cfg))

    if ids:
        _CLOUD_IDS_CACHE["ts"] = now
        _CLOUD_IDS_CACHE["ids"] = set(ids)
    return ids


def cloud_save_match_report(match_id: int, report_dict: Dict[str, Any]) -> bool:
    """
    Persist an analyzed match report (including Grok 4.7 coaching) to cloud DB.
    Updates the in-memory cloud ID cache immediately.
    """
    if not match_id or not isinstance(report_dict, dict):
        return False

    _CLOUD_IDS_CACHE["ids"].add(int(match_id))
    _CLOUD_IDS_CACHE["ts"] = time.time()

    cfg = get_cloud_config()
    saved_any = False

    if cfg["supabase_url"] and cfg["supabase_key"]:
        if _supabase_save_report(int(match_id), report_dict, cfg):
            saved_any = True

    if cfg["github_token"] and cfg["github_repo"]:
        # Save compact JSON to keep cloud storage fast and lean
        compact_txt = json.dumps(report_dict, ensure_ascii=False, separators=(",", ":"))
        msg = f"chore(db): persist analyzed report match_{match_id}.json [skip ci]"
        if _github_save_file(f"reports/match_{int(match_id)}.json", compact_txt, msg, cfg):
            saved_any = True

    return saved_any


def cloud_fetch_match_report(match_id: int) -> Optional[Dict[str, Any]]:
    """
    Fetch an analyzed match report from Cloud DB (Supabase or GitHub Cloud)
    and automatically cache it in /tmp/dota_reports so subsequent reads are 0ms.
    """
    if not match_id:
        return None

    cfg = get_cloud_config()
    rep = None
    if cfg["supabase_url"] and cfg["supabase_key"]:
        rep = _supabase_fetch_report(int(match_id), cfg)
    if rep is None and cfg["github_token"] and cfg["github_repo"]:
        rep = _github_fetch_json_file(f"reports/match_{int(match_id)}.json", cfg)

    if isinstance(rep, dict) and rep.get("match_id"):
        _CLOUD_IDS_CACHE["ids"].add(int(match_id))
        try:
            TMP_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            (TMP_REPORTS_DIR / f"match_{int(match_id)}.json").write_text(
                json.dumps(rep, ensure_ascii=False), encoding="utf-8"
            )
        except Exception:
            pass
        return rep
    return None


def cloud_save_coaching(match_id: int, side: str, coaching_dict: Dict[str, Any]) -> bool:
    cfg = get_cloud_config()
    saved = False
    if cfg["github_token"] and cfg["github_repo"]:
        txt = json.dumps(coaching_dict, ensure_ascii=False, indent=2)
        msg = f"chore(db): persist Grok coaching for match {match_id} ({side}) [skip ci]"
        if _github_save_file(f"reports/coaching-{int(match_id)}-{side}.json", txt, msg, cfg):
            saved = True
    return saved
