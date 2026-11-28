#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Anonymous GitHub Actions benchmark for Milestone M0 (ubuntu-latest).

Dynamically locates 1 recent patch=60 squad match from roster.json (main_account_id)
with an HTTP 200 Valve replay_url, downloads, decompresses, parses via odota/parser
under GNU `/usr/bin/time -v`, measures gzip-9 sizes and event counts inside /tmp/m0_gha/,
cleans up /tmp/m0_gha/, and prints ONLY anonymous aggregate metrics.

STRICT PUBLIC REPO PRIVACY:
Never prints match IDs, Valve URLs/salts, player names, account IDs, or raw JSONL lines,
including in exception messages.
"""

import collections
import datetime
import gzip
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GHA_WORK_DIR = Path("/tmp/m0_gha")
PARSER_DIR = Path("/tmp/m0_gha_parser")


class SafeBenchError(RuntimeError):
    """Exception whose message never carries URLs, match IDs, or account IDs."""


def safe_fetch_json(url: str, stage: str, timeout: int = 30) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "dota-5stack-ledger-m0-gha/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise SafeBenchError(f"{stage}: HTTPError status={exc.code}") from None
    except urllib.error.URLError:
        raise SafeBenchError(f"{stage}: URLError") from None
    except Exception as exc:
        raise SafeBenchError(f"{stage}: {type(exc).__name__}") from None


def safe_head_status(url: str, timeout: int = 15) -> Optional[int]:
    req = urllib.request.Request(url, headers={"User-Agent": "dota-5stack-ledger-m0-gha/1.0"})
    req.get_method = lambda: "HEAD"
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(getattr(resp, "status", 200))
    except urllib.error.HTTPError as exc:
        return int(exc.code)
    except Exception:
        return None


def safe_download(url: str, dest: Path, timeout: int = 180) -> float:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "dota-5stack-ledger-m0-gha/1.0"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp, dest.open("wb") as out:
            while True:
                chunk = resp.read(1024 * 256)
                if not chunk:
                    break
                out.write(chunk)
    except urllib.error.HTTPError as exc:
        raise SafeBenchError(f"download_replay: HTTPError status={exc.code}") from None
    except urllib.error.URLError:
        raise SafeBenchError("download_replay: URLError") from None
    except Exception as exc:
        raise SafeBenchError(f"download_replay: {type(exc).__name__}") from None
    return time.perf_counter() - t0


def collect_host_info() -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
    }
    meminfo = Path("/proc/meminfo")
    if meminfo.exists():
        for ln in meminfo.read_text(encoding="utf-8", errors="ignore").splitlines():
            if ln.startswith(("MemTotal:", "MemAvailable:")):
                k, v = ln.split(":", 1)
                info[k] = v.strip()
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        for ln in cpuinfo.read_text(encoding="utf-8", errors="ignore").splitlines():
            if ln.startswith("model name"):
                _, v = ln.split(":", 1)
                info["cpu_model"] = v.strip()
                break
    return info


def pick_latest_squad_replay(roster_path: Path) -> Dict[str, Any]:
    roster = json.loads(roster_path.read_text(encoding="utf-8"))
    main_aid = int(roster["main_account_id"])
    roster_aids = {int(k) for k in (roster.get("players") or {}).keys()}
    roster_aids.add(main_aid)

    candidates: List[Dict[str, Any]] = []
    recent = safe_fetch_json(
        f"https://api.opendota.com/api/players/{main_aid}/recentMatches",
        stage="fetch_recent_matches",
    )
    if isinstance(recent, list):
        candidates.extend(recent)

    if not candidates:
        hist = safe_fetch_json(
            f"https://api.opendota.com/api/players/{main_aid}/matches?date=14",
            stage="fetch_matches_14d",
        )
        if isinstance(hist, list):
            candidates.extend(hist)

    seen_ids = set()
    ordered = []
    for item in sorted(candidates, key=lambda r: int(r.get("start_time") or 0), reverse=True):
        mid = item.get("match_id")
        if mid and mid not in seen_ids:
            seen_ids.add(mid)
            ordered.append(item)

    for item in ordered[:25]:
        mid = int(item["match_id"])
        try:
            meta = safe_fetch_json(f"https://api.opendota.com/api/matches/{mid}", stage="fetch_match_detail")
        except SafeBenchError:
            continue
        if meta.get("patch") != 60:
            continue
        match_aids = {
            int(p["account_id"])
            for p in (meta.get("players") or [])
            if p.get("account_id") is not None
        }
        squad_count = len(roster_aids & match_aids)
        if squad_count < 2:
            continue
        replay_url = meta.get("replay_url")
        if not isinstance(replay_url, str) or not replay_url.startswith("http"):
            continue
        head_status = safe_head_status(replay_url)
        if head_status != 200:
            continue
        return {
            "replay_url": replay_url,
            "patch": int(meta["patch"]),
            "duration_sec": int(meta.get("duration") or 0),
            "squad_roster_count": squad_count,
            "head_status": head_status,
        }

    # Fallback: query 14d matches if recentMatches (max 20) had no eligible squad match
    hist = safe_fetch_json(
        f"https://api.opendota.com/api/players/{main_aid}/matches?date=14",
        stage="fetch_matches_14d_fallback",
    )
    if isinstance(hist, list):
        for item in sorted(hist, key=lambda r: int(r.get("start_time") or 0), reverse=True)[:30]:
            mid = item.get("match_id")
            if not mid or mid in seen_ids:
                continue
            seen_ids.add(mid)
            try:
                meta = safe_fetch_json(f"https://api.opendota.com/api/matches/{int(mid)}", stage="fetch_match_detail_fallback")
            except SafeBenchError:
                continue
            if meta.get("patch") != 60:
                continue
            match_aids = {
                int(p["account_id"])
                for p in (meta.get("players") or [])
                if p.get("account_id") is not None
            }
            squad_count = len(roster_aids & match_aids)
            if squad_count < 2:
                continue
            replay_url = meta.get("replay_url")
            if not isinstance(replay_url, str) or not replay_url.startswith("http"):
                continue
            head_status = safe_head_status(replay_url)
            if head_status == 200:
                return {
                    "replay_url": replay_url,
                    "patch": int(meta["patch"]),
                    "duration_sec": int(meta.get("duration") or 0),
                    "squad_roster_count": squad_count,
                    "head_status": head_status,
                }

    raise SafeBenchError("no_eligible_patch60_squad_replay_with_http_200_found")


def detect_compression(path: Path) -> str:
    hdr = path.read_bytes()[:8]
    if hdr.startswith(b"\x28\xb5\x2f\xfd"):
        return "zstd"
    if len(hdr) >= 4 and hdr[:3] == b"BZh" and ord("1") <= hdr[3] <= ord("9"):
        return "bzip2"
    if hdr.startswith(b"PBDEMS2\x00"):
        return "raw_pbdems2"
    return "unknown"


def run_benchmark() -> Dict[str, Any]:
    jar_path = PARSER_DIR / "target" / "stats-0.1.0.jar"
    classes_dir = PARSER_DIR / "cli_classes"
    if not jar_path.exists():
        raise SafeBenchError("missing_parser_jar")
    if not (classes_dir / "ParseCli.class").exists():
        raise SafeBenchError("missing_parsecli_class")

    parser_sha = subprocess.run(
        ["git", "-C", str(PARSER_DIR), "rev-parse", "HEAD"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    java_ver_proc = subprocess.run(["java", "-version"], stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True)
    java_ver = " | ".join((java_ver_proc.stdout + java_ver_proc.stderr).strip().splitlines())

    picked = pick_latest_squad_replay(REPO_ROOT / "roster.json")
    replay_url = picked.pop("replay_url")

    GHA_WORK_DIR.mkdir(parents=True, exist_ok=True)
    bz2_path = GHA_WORK_DIR / "replay.dem.bz2"
    dem_path = GHA_WORK_DIR / "replay.dem"
    jsonl_path = GHA_WORK_DIR / "parsed.jsonl"
    jsonl_gz_path = GHA_WORK_DIR / "parsed.jsonl.gz"
    time_v_path = GHA_WORK_DIR / "time_v.txt"

    dl_sec = safe_download(replay_url, bz2_path)
    bz2_bytes = bz2_path.stat().st_size

    detected_fmt = detect_compression(bz2_path)
    t0 = time.perf_counter()
    if detected_fmt == "zstd":
        decompress_tool = "zstd -d -f"
        dec_proc = subprocess.run(["zstd", "-d", "-f", str(bz2_path), "-o", str(dem_path)], stdin=subprocess.DEVNULL, capture_output=True, text=True)
    elif detected_fmt == "bzip2":
        decompress_tool = "bzip2 -dk"
        dec_proc = subprocess.run(["bzip2", "-dk", str(bz2_path)], stdin=subprocess.DEVNULL, capture_output=True, text=True)
    elif detected_fmt == "raw_pbdems2":
        decompress_tool = "copy"
        shutil.copyfile(bz2_path, dem_path)
        dec_proc = subprocess.CompletedProcess([], 0)
    else:
        raise SafeBenchError(f"unsupported_compression_fmt={detected_fmt}")
    decompress_sec = time.perf_counter() - t0
    if dec_proc.returncode != 0 or not dem_path.exists():
        raise SafeBenchError(f"decompress_failed tool={detected_fmt} rc={dec_proc.returncode}")
    dem_bytes = dem_path.stat().st_size

    cp = f"{jar_path}:{classes_dir}"
    t0 = time.perf_counter()
    parse_proc = subprocess.run(
        [
            "/usr/bin/time", "-v", "-o", str(time_v_path),
            "java", "-cp", cp, "ParseCli", str(dem_path), str(jsonl_path),
        ],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    parse_wall_sec = time.perf_counter() - t0
    if parse_proc.returncode != 0 or not jsonl_path.exists():
        raise SafeBenchError(f"parse_failed rc={parse_proc.returncode}")
    jsonl_bytes = jsonl_path.stat().st_size

    time_v_lines = [
        ln.rstrip()
        for ln in time_v_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        if ln.strip()
    ]

    t0 = time.perf_counter()
    gz_proc = subprocess.run(["gzip", "-9", "-kf", str(jsonl_path)], stdin=subprocess.DEVNULL, capture_output=True, text=True)
    gzip_jsonl_sec = time.perf_counter() - t0
    if gz_proc.returncode != 0 or not jsonl_gz_path.exists():
        raise SafeBenchError(f"gzip_failed rc={gz_proc.returncode}")
    jsonl_gz_bytes = jsonl_gz_path.stat().st_size

    type_counts: collections.Counter = collections.Counter()
    intervals_by_slot: Dict[int, List[Tuple[int, float, float, int]]] = collections.defaultdict(list)
    line_count = 0
    with jsonl_path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            line_count += 1
            entry = json.loads(raw_line)
            etype = entry.get("type", "<missing>")
            type_counts[etype] += 1
            if etype == "interval" and entry.get("slot") is not None and entry.get("time") is not None:
                t = int(entry["time"])
                if t >= 0 and "x" in entry and "y" in entry:
                    intervals_by_slot[int(entry["slot"])].append((
                        t,
                        float(entry["x"]),
                        float(entry["y"]),
                        int(entry.get("life_state", 0)),
                    ))

    dt_nonneg: collections.Counter = collections.Counter()
    compact_01_slots: Dict[str, List[List[Any]]] = {}
    compact_int_slots: Dict[str, List[List[Any]]] = {}
    for slot in sorted(intervals_by_slot.keys()):
        pts = intervals_by_slot[slot]
        for i in range(1, len(pts)):
            dt_nonneg[pts[i][0] - pts[i - 1][0]] += 1
        compact_01_slots[str(slot)] = [[t, round(x, 1), round(y, 1), ls] for t, x, y, ls in pts]
        compact_int_slots[str(slot)] = [
            [t, int(math.floor(x + 0.5)), int(math.floor(y + 0.5)), ls]
            for t, x, y, ls in pts
        ]

    t0 = time.perf_counter()
    c01_raw = json.dumps({"schema_version": 1, "tick_interval_sec": 1, "slots": compact_01_slots}, separators=(",", ":")).encode("utf-8")
    c01_gz = gzip.compress(c01_raw, compresslevel=9)
    compact_gz_sec = time.perf_counter() - t0

    cint_raw = json.dumps({"schema_version": 1, "tick_interval_sec": 1, "slots": compact_int_slots}, separators=(",", ":")).encode("utf-8")
    cint_gz = gzip.compress(cint_raw, compresslevel=9)

    return {
        "utc_run_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "host": collect_host_info(),
        "java_version": java_ver,
        "odota_parser_commit": parser_sha,
        "selected_match_anonymous": picked,
        "detected_payload_compression": detected_fmt,
        "decompress_tool": decompress_tool,
        "durations_sec": {
            "download_dem_bz2": round(dl_sec, 3),
            "decompress": round(decompress_sec, 3),
            "parse_wall": round(parse_wall_sec, 3),
            "gzip9_jsonl": round(gzip_jsonl_sec, 3),
            "compact_01_gzip9": round(compact_gz_sec, 3),
        },
        "sizes_bytes": {
            "dem_bz2": bz2_bytes,
            "dem": dem_bytes,
            "jsonl": jsonl_bytes,
            "jsonl_gz": jsonl_gz_bytes,
            "compact_01_json_raw": len(c01_raw),
            "compact_01_json_gz": len(c01_gz),
            "compact_int_json_raw": len(cint_raw),
            "compact_int_json_gz": len(cint_gz),
        },
        "jsonl_total_lines": line_count,
        "event_type_counts": dict(type_counts.most_common()),
        "interval_dt_t_ge_0": dict(sorted(dt_nonneg.items())),
        "gnu_time_v_lines": time_v_lines,
    }


def main() -> int:
    try:
        result = run_benchmark()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except SafeBenchError as exc:
        print(f"GHA_M0_BENCH_ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"GHA_M0_BENCH_ERROR: unexpected {type(exc).__name__}", file=sys.stderr)
        return 1
    finally:
        shutil.rmtree(GHA_WORK_DIR, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
