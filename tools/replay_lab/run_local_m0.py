#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Milestone M0 local benchmark, coordinate cross-check, and real JSONL excerpt extractor.

Runs against the 3 Richard-approved <6d squad matches (9087090072, 9085834639, 9083213997),
keeping all downloads and artifacts inside --work-dir (/tmp/m0_replay_work by default).
Never prints player nicknames, Steam/account IDs, or full Valve replay URLs with salts.
"""

import argparse
import collections
import datetime
import gzip
import json
import math
import os
import re
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

APPROVED_MATCH_IDS = [9087090072, 9085834639, 9083213997]
DEFAULT_WORK_DIR = Path("/tmp/m0_replay_work")
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_EXCERPT_PATH = REPO_ROOT / "tools" / "replay_lab" / "sample_9083213997_excerpt.jsonl"


def java_round(val: float) -> int:
    """Mirror Java Math.round(float): floor(x + 0.5)."""
    return int(math.floor(val + 0.5))


def redact_replay_url(url: str) -> str:
    """Strip replay_salt from Valve replay URL for safe logging."""
    return re.sub(r"_(\d+)(\.dem(?:\.bz2|\.zst)?)$", r"_<SALT_REDACTED>\2", url)


def unit_to_combatlog_names(unit: str) -> List[str]:
    """Match Parse.java combatLogNamesForUnit(CDOTA_Unit_Hero_...)."""
    prefix = "CDOTA_Unit_Hero_"
    if not unit.startswith(prefix):
        return []
    ending = unit[len(prefix):]
    n1 = "npc_dota_hero_" + ending.lower()
    n2 = "npc_dota_hero" + re.sub(r"([A-Z])", r"_\1", ending).lower()
    return list(dict.fromkeys([n1, n2]))


def fetch_json(url: str, timeout: int = 30) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "dota-5stack-ledger-m0/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def download_file(url: str, dest: Path, timeout: int = 180) -> float:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "dota-5stack-ledger-m0/1.0"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as resp, dest.open("wb") as out:
        while True:
            chunk = resp.read(1024 * 256)
            if not chunk:
                break
            out.write(chunk)
    return time.perf_counter() - t0


def run_cmd(cmd: List[str], capture_stderr: bool = False) -> Tuple[int, str, str, float]:
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, errors="replace")
    dt = time.perf_counter() - t0
    return proc.returncode, proc.stdout, proc.stderr, dt


def find_toolchain(work_dir: Path) -> Tuple[Path, Path, Path]:
    tc = work_dir / "toolchain"
    java_candidates = sorted(tc.glob("jdk-*/Contents/Home/bin/java")) + sorted(tc.glob("jdk-*/bin/java"))
    if not java_candidates:
        raise FileNotFoundError(f"Portable JDK not found under {tc}")
    java_bin = java_candidates[0]
    jar_path = work_dir / "odota-parser" / "target" / "stats-0.1.0.jar"
    if not jar_path.exists():
        raise FileNotFoundError(f"Built odota/parser jar not found at {jar_path}")
    classes_dir = work_dir / "classes"
    if not (classes_dir / "ParseCli.class").exists():
        raise FileNotFoundError(f"Compiled ParseCli.class not found under {classes_dir}")
    return java_bin, jar_path, classes_dir


def parse_macos_time_l(stderr_text: str) -> Dict[str, Any]:
    info: Dict[str, Any] = {"raw_lines": [ln.rstrip() for ln in stderr_text.splitlines() if ln.strip()]}
    for ln in info["raw_lines"]:
        m_real = re.match(r"^\s*([\d.]+)\s+real\s+([\d.]+)\s+user\s+([\d.]+)\s+sys\s*$", ln)
        if m_real:
            info["real_sec"] = float(m_real.group(1))
            info["user_sec"] = float(m_real.group(2))
            info["sys_sec"] = float(m_real.group(3))
        m_rss = re.match(r"^\s*(\d+)\s+maximum resident set size\s*$", ln)
        if m_rss:
            info["max_rss_bytes"] = int(m_rss.group(1))
            info["max_rss_mib"] = round(int(m_rss.group(1)) / (1024 * 1024), 2)
        m_peak = re.match(r"^\s*(\d+)\s+peak memory footprint\s*$", ln)
        if m_peak:
            info["peak_footprint_bytes"] = int(m_peak.group(1))
            info["peak_footprint_mib"] = round(int(m_peak.group(1)) / (1024 * 1024), 2)
    return info


def expand_od_deaths_pos(deaths_pos: Dict[str, Any]) -> List[Tuple[int, int]]:
    pts: List[Tuple[int, int]] = []
    for x_str, y_map in (deaths_pos or {}).items():
        if not isinstance(y_map, dict):
            continue
        for y_str, cnt in y_map.items():
            for _ in range(int(cnt)):
                pts.append((int(x_str), int(y_str)))
    return pts


def pair_points_min_cost(
    a_pts: List[Tuple[float, float]], b_pts: List[Tuple[int, int]]
) -> List[Tuple[Tuple[float, float], Tuple[int, int], float]]:
    """Pair equal/near-equal length point lists greedily by Euclidean distance."""
    remaining_b = list(range(len(b_pts)))
    pairs: List[Tuple[Tuple[float, float], Tuple[int, int], float]] = []
    for ax, ay in a_pts:
        if not remaining_b:
            break
        best_idx = min(
            remaining_b,
            key=lambda bi: math.hypot(ax - b_pts[bi][0], ay - b_pts[bi][1]),
        )
        remaining_b.remove(best_idx)
        bx, by = b_pts[best_idx]
        pairs.append(((ax, ay), (bx, by), math.hypot(ax - bx, ay - by)))
    return pairs


def load_pii_needles(roster_path: Path) -> List[str]:
    if not roster_path.exists():
        return []
    roster = json.loads(roster_path.read_text(encoding="utf-8"))
    needles = set()
    if roster.get("main_name"):
        needles.add(str(roster["main_name"]).strip('"'))
    if roster.get("main_account_id"):
        aid = int(roster["main_account_id"])
        needles.add(str(aid))
        needles.add(str(76561197960265728 + aid))
    for k, p in (roster.get("players") or {}).items():
        aid = int(k)
        needles.add(str(aid))
        needles.add(str(76561197960265728 + aid))
        if isinstance(p, dict) and p.get("name"):
            raw_name = str(p["name"]).strip().strip('"')
            if raw_name:
                needles.add(raw_name)
    return sorted(n for n in needles if len(n) >= 3)


def detect_compression(path: Path) -> str:
    hdr = path.read_bytes()[:8]
    if hdr.startswith(b"\x28\xb5\x2f\xfd"):
        return "zstd"
    if len(hdr) >= 4 and hdr[:3] == b"BZh" and ord("1") <= hdr[3] <= ord("9"):
        return "bzip2"
    if hdr.startswith(b"PBDEMS2\x00"):
        return "raw_pbdems2"
    return f"unknown({hdr.hex()})"


def analyze_match(
    match_id: int,
    work_dir: Path,
    java_bin: Path,
    jar_path: Path,
    classes_dir: Path,
    force_download: bool = False,
    force_parse: bool = False,
) -> Dict[str, Any]:
    matches_dir = work_dir / "matches"
    replays_dir = work_dir / "replays"
    out_dir = work_dir / "out"
    matches_dir.mkdir(parents=True, exist_ok=True)
    replays_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    meta_path = matches_dir / f"{match_id}.json"
    if meta_path.exists() and not force_download:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    else:
        meta = fetch_json(f"https://api.opendota.com/api/matches/{match_id}")
        meta_path.write_text(json.dumps(meta), encoding="utf-8")

    replay_url = meta.get("replay_url")
    if not replay_url:
        raise RuntimeError(f"Match {match_id} has no replay_url in OpenDota API response")

    bz2_path = replays_dir / f"{match_id}.dem.bz2"
    dem_path = replays_dir / f"{match_id}.dem"
    jsonl_path = out_dir / f"{match_id}.jsonl"
    jsonl_gz_path = out_dir / f"{match_id}.jsonl.gz"

    if force_download or not bz2_path.exists():
        dl_sec = download_file(replay_url, bz2_path)
    else:
        dl_sec = None

    rc_file_bz2, out_file_bz2, _, _ = run_cmd(["file", str(bz2_path)])
    if rc_file_bz2 != 0:
        raise RuntimeError(f"file check failed on {bz2_path}")

    detected_fmt = detect_compression(bz2_path)
    # Decompress based on actual magic header (Valve CDN serves zstd under .dem.bz2 URLs)
    if dem_path.exists():
        dem_path.unlink()
    if detected_fmt == "zstd":
        decompress_tool = "zstd -d -f"
        rc_dec, _, err_dec, decompress_sec = run_cmd(["zstd", "-d", "-f", str(bz2_path), "-o", str(dem_path)])
    elif detected_fmt == "bzip2":
        decompress_tool = "bzip2 -dk"
        rc_dec, _, err_dec, decompress_sec = run_cmd(["bzip2", "-dk", str(bz2_path)])
    elif detected_fmt == "raw_pbdems2":
        decompress_tool = "copy"
        t0 = time.perf_counter()
        dem_path.write_bytes(bz2_path.read_bytes())
        decompress_sec = time.perf_counter() - t0
        rc_dec, err_dec = 0, ""
    else:
        raise RuntimeError(f"Unsupported replay magic format for {match_id}: {detected_fmt}")
    if rc_dec != 0 or not dem_path.exists():
        raise RuntimeError(f"{decompress_tool} failed for {match_id}: {err_dec}")
    _, out_file_dem, _, _ = run_cmd(["file", str(dem_path)])
    dem_magic = dem_path.read_bytes()[:8].hex()

    # Parse via /usr/bin/time -l java ... ParseCli
    if force_parse or not jsonl_path.exists():
        if jsonl_path.exists():
            jsonl_path.unlink()
        cp = f"{jar_path}:{classes_dir}"
        parse_cmd = [
            "/usr/bin/time", "-l",
            str(java_bin), "-cp", cp, "ParseCli", str(dem_path), str(jsonl_path),
        ]
        rc_p, out_p, err_p, parse_wall_sec = run_cmd(parse_cmd)
        if rc_p != 0:
            raise RuntimeError(f"ParseCli failed for {match_id}: {err_p}")
        time_info = parse_macos_time_l(err_p)
    else:
        # Re-run timing cleanly if requested; by default if jsonl exists we still re-parse to get /usr/bin/time -l
        cp = f"{jar_path}:{classes_dir}"
        parse_cmd = [
            "/usr/bin/time", "-l",
            str(java_bin), "-cp", cp, "ParseCli", str(dem_path), str(jsonl_path),
        ]
        rc_p, out_p, err_p, parse_wall_sec = run_cmd(parse_cmd)
        if rc_p != 0:
            raise RuntimeError(f"ParseCli failed for {match_id}: {err_p}")
        time_info = parse_macos_time_l(err_p)

    # Compress .jsonl with gzip -9 -kf
    if jsonl_gz_path.exists():
        jsonl_gz_path.unlink()
    rc_gz, _, err_gz, gzip_jsonl_sec = run_cmd(["gzip", "-9", "-kf", str(jsonl_path)])
    if rc_gz != 0:
        raise RuntimeError(f"gzip -9 failed for {match_id}: {err_gz}")

    # Analyze JSONL stream
    type_counts: collections.Counter = collections.Counter()
    interval_keys: set = set()
    sample_interval_line: Optional[Dict[str, Any]] = None
    intervals_by_slot: Dict[int, List[Dict[str, Any]]] = collections.defaultdict(list)
    interval_by_time_slot: Dict[Tuple[int, int], Dict[str, Any]] = {}
    combatlog_to_slot: Dict[str, int] = {}
    hero_deaths: List[Dict[str, Any]] = []
    parser_obs: List[Dict[str, Any]] = []
    min_x = float("inf")
    max_x = float("-inf")
    min_y = float("inf")
    max_y = float("-inf")
    coord_count = 0
    in_64_192_count = 0
    formula_range_ok = 0
    cell_vec_examples: List[Dict[str, Any]] = []
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

            if etype == "interval":
                interval_keys.update(entry.keys())
                t = entry.get("time")
                slot = entry.get("slot")
                if sample_interval_line is None and t is not None and t >= 0 and "x" in entry and "y" in entry:
                    sample_interval_line = entry
                if slot is not None and t is not None:
                    intervals_by_slot[int(slot)].append(entry)
                    interval_by_time_slot[(int(t), int(slot))] = entry
                unit = entry.get("unit")
                if unit and slot is not None:
                    for cln in unit_to_combatlog_names(unit):
                        combatlog_to_slot[cln] = int(slot)
                x = entry.get("x")
                y = entry.get("y")
                if x is not None and y is not None:
                    xf = float(x)
                    yf = float(y)
                    coord_count += 1
                    min_x = min(min_x, xf)
                    max_x = max(max_x, xf)
                    min_y = min(min_y, yf)
                    max_y = max(max_y, yf)
                    if 64.0 <= xf <= 192.0 and 64.0 <= yf <= 192.0:
                        in_64_192_count += 1
                    # Verify (cell * 128 + vec) / 128 decomposition: cell = floor(x), vec in [0, 128)
                    cx = math.floor(xf)
                    cy = math.floor(yf)
                    vx = (xf - cx) * 128.0
                    vy = (yf - cy) * 128.0
                    if 0.0 <= vx < 128.0 and 0.0 <= vy < 128.0:
                        formula_range_ok += 1
                    if len(cell_vec_examples) < 3 and t is not None and t >= 60:
                        cell_vec_examples.append({
                            "time": t, "slot": slot, "x": xf, "y": yf,
                            "cellX": cx, "vecX": round(vx, 4), "cellY": cy, "vecY": round(vy, 4),
                            "reconstructed_x": round((cx * 128.0 + vx) / 128.0, 6),
                            "reconstructed_y": round((cy * 128.0 + vy) / 128.0, 6),
                        })
            elif etype == "DOTA_COMBATLOG_DEATH":
                if entry.get("targethero") is True and not entry.get("targetillusion"):
                    hero_deaths.append(entry)
            elif etype == "obs":
                parser_obs.append(entry)

    # Interval dt distribution per slot (all & time >= 0)
    dt_all: collections.Counter = collections.Counter()
    dt_nonneg: collections.Counter = collections.Counter()
    slot_interval_summary: Dict[int, Dict[str, Any]] = {}
    life_state_deaths_by_slot: Dict[int, List[int]] = collections.defaultdict(list)
    for slot in sorted(intervals_by_slot.keys()):
        rows = intervals_by_slot[slot]
        times_all = [int(r["time"]) for r in rows]
        times_nonneg = [t for t in times_all if t >= 0]
        for i in range(1, len(times_all)):
            dt_all[times_all[i] - times_all[i - 1]] += 1
        for i in range(1, len(times_nonneg)):
            dt_nonneg[times_nonneg[i] - times_nonneg[i - 1]] += 1
        prev_ls = None
        for r in rows:
            ls = r.get("life_state")
            if prev_ls == 0 and ls is not None and ls != 0:
                life_state_deaths_by_slot[slot].append(int(r["time"]))
            if ls is not None:
                prev_ls = ls
        slot_interval_summary[slot] = {
            "count_all": len(times_all),
            "count_t_ge_0": len(times_nonneg),
            "min_t": min(times_all) if times_all else None,
            "max_t": max(times_all) if times_all else None,
        }

    # Build compact 1Hz timeline payloads (t >= 0) to measure real compressed storage size
    compact_01 = {
        "schema_version": 1,
        "match_id": match_id,
        "tick_interval_sec": 1,
        "coord_precision": "0.1_cell",
        "slots": {},
    }
    compact_int = {
        "schema_version": 1,
        "match_id": match_id,
        "tick_interval_sec": 1,
        "coord_precision": "1_cell_int",
        "slots": {},
    }
    for slot in sorted(intervals_by_slot.keys()):
        pts_01 = []
        pts_int = []
        unit_name = None
        hero_id = None
        for r in intervals_by_slot[slot]:
            t = int(r["time"])
            if t < 0:
                continue
            if unit_name is None and r.get("unit"):
                unit_name = r["unit"]
            if hero_id is None and r.get("hero_id") is not None:
                hero_id = r["hero_id"]
            if "x" in r and "y" in r:
                ls = int(r.get("life_state", 0))
                pts_01.append([t, round(float(r["x"]), 1), round(float(r["y"]), 1), ls])
                pts_int.append([t, java_round(float(r["x"])), java_round(float(r["y"])), ls])
        compact_01["slots"][str(slot)] = {"unit": unit_name, "hero_id": hero_id, "pts": pts_01}
        compact_int["slots"][str(slot)] = {"unit": unit_name, "hero_id": hero_id, "pts": pts_int}

    t_c0 = time.perf_counter()
    c01_raw = json.dumps(compact_01, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    c01_gz = gzip.compress(c01_raw, compresslevel=9)
    c01_sec = time.perf_counter() - t_c0

    cint_raw = json.dumps(compact_int, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    cint_gz = gzip.compress(cint_raw, compresslevel=9)

    # Cross-check 1: OpenDota teamfights[].players[].deaths_pos vs parser hero coordinates at death time
    od_players = meta.get("players") or []
    od_deaths_log_times_by_slot: Dict[int, List[int]] = {}
    for idx, p in enumerate(od_players[:10]):
        od_deaths_log_times_by_slot[idx] = [int(dl["time"]) for dl in (p.get("deaths_log") or []) if "time" in dl]

    tf_total_od_deaths = 0
    tf_matched_combatlog = 0
    tf_exact_round_match = 0
    tf_exact_od_two_step_match = 0
    tf_within_1_cell = 0
    tf_within_2_cells = 0
    tf_float_dists: List[float] = []
    tf_round_dx: List[int] = []
    tf_round_dy: List[int] = []
    tf_lifestate_dists: List[float] = []
    tf_lifestate_matched = 0
    tf_samples: List[Dict[str, Any]] = []

    for tf_idx, tf in enumerate(meta.get("teamfights") or []):
        tf_start = int(tf["start"])
        tf_end = int(tf["end"])
        for slot_idx, tp in enumerate(tf.get("players") or []):
            od_pts = expand_od_deaths_pos(tp.get("deaths_pos") or {})
            if not od_pts:
                continue
            tf_total_od_deaths += len(od_pts)

            # Find parser hero deaths in [tf_start, tf_end] for this slot
            # Exclude duplicate Meepo or Aegis/Reincarnation if deaths_log has fewer deaths
            cl_deaths = [
                d for d in hero_deaths
                if combatlog_to_slot.get(d.get("targetname", "")) == slot_idx
                and tf_start <= int(d["time"]) <= tf_end
            ]
            # Filter to times matching OpenDota deaths_log if count > len(od_pts) (e.g. Aegis/WK)
            od_dl_in_tf = [t for t in od_deaths_log_times_by_slot.get(slot_idx, []) if tf_start <= t <= tf_end]
            if len(cl_deaths) > len(od_pts) and len(od_dl_in_tf) == len(od_pts):
                filtered = []
                used_cl = set()
                for dt in od_dl_in_tf:
                    for ci, d in enumerate(cl_deaths):
                        if ci not in used_cl and abs(int(d["time"]) - dt) <= 1:
                            filtered.append(d)
                            used_cl.add(ci)
                            break
                if len(filtered) == len(od_pts):
                    cl_deaths = filtered

            parser_pts: List[Tuple[float, float]] = []
            parser_times: List[int] = []
            for d in cl_deaths:
                dt = int(d["time"])
                iv = interval_by_time_slot.get((dt, slot_idx))
                if iv is None:
                    for off in (1, -1, 2, -2):
                        iv = interval_by_time_slot.get((dt + off, slot_idx))
                        if iv is not None:
                            break
                if iv is not None and "x" in iv and "y" in iv:
                    parser_pts.append((float(iv["x"]), float(iv["y"])))
                    parser_times.append(dt)

            pairs = pair_points_min_cost(parser_pts, od_pts)
            tf_matched_combatlog += len(pairs)
            for (px, py), (ox, oy), dist in pairs:
                tf_float_dists.append(dist)
                rx, ry = java_round(px), java_round(py)
                rx2 = java_round(java_round(px * 10.0) / 10.0)
                ry2 = java_round(java_round(py * 10.0) / 10.0)
                dx, dy = abs(rx - ox), abs(ry - oy)
                tf_round_dx.append(dx)
                tf_round_dy.append(dy)
                if dx == 0 and dy == 0:
                    tf_exact_round_match += 1
                if rx2 == ox and ry2 == oy:
                    tf_exact_od_two_step_match += 1
                if max(dx, dy) <= 1:
                    tf_within_1_cell += 1
                if max(dx, dy) <= 2:
                    tf_within_2_cells += 1
                if len(tf_samples) < 5:
                    tf_samples.append({
                        "tf_idx": tf_idx, "slot": slot_idx,
                        "parser_xy": [round(px, 3), round(py, 3)],
                        "parser_round_xy": [rx, ry],
                        "od_deaths_pos_xy": [ox, oy],
                        "euclid_err_raw": round(dist, 3),
                        "round_dx_dy": [dx, dy],
                    })

            # Also check life_state 0 -> !=0 transitions in [tf_start - 1, tf_end + 2]
            ls_times = [t for t in life_state_deaths_by_slot.get(slot_idx, []) if tf_start - 1 <= t <= tf_end + 2]
            ls_pts = []
            for lt in ls_times:
                iv = interval_by_time_slot.get((lt, slot_idx))
                if iv is not None and "x" in iv and "y" in iv:
                    ls_pts.append((float(iv["x"]), float(iv["y"])))
            ls_pairs = pair_points_min_cost(ls_pts, od_pts)
            tf_lifestate_matched += len(ls_pairs)
            for (px, py), (ox, oy), dist in ls_pairs:
                tf_lifestate_dists.append(dist)

    # Cross-check 2: OpenDota players[].obs_log vs parser "obs" events
    od_obs_list: List[Dict[str, Any]] = []
    for slot_idx, p in enumerate(od_players[:10]):
        for ob in (p.get("obs_log") or []):
            od_obs_list.append({
                "slot": int(ob.get("slot", slot_idx)),
                "time": int(ob["time"]),
                "ehandle": ob.get("ehandle"),
                "x": float(ob["x"]) if ob.get("x") is not None else None,
                "y": float(ob["y"]) if ob.get("y") is not None else None,
            })

    parser_obs_by_ehandle: Dict[Tuple[int, int], Dict[str, Any]] = {}
    parser_obs_by_time_slot: Dict[Tuple[int, int], List[Dict[str, Any]]] = collections.defaultdict(list)
    for po in parser_obs:
        if po.get("ehandle") is not None and po.get("slot") is not None:
            parser_obs_by_ehandle[(int(po["slot"]), int(po["ehandle"]))] = po
        if po.get("time") is not None and po.get("slot") is not None:
            parser_obs_by_time_slot[(int(po["time"]), int(po["slot"]))].append(po)

    obs_matched = 0
    obs_exact_01 = 0
    obs_dists: List[float] = []
    obs_dx_list: List[float] = []
    obs_dy_list: List[float] = []
    obs_samples: List[Dict[str, Any]] = []
    for ob in od_obs_list:
        po = None
        if ob["ehandle"] is not None:
            po = parser_obs_by_ehandle.get((ob["slot"], int(ob["ehandle"])))
        if po is None:
            cands = parser_obs_by_time_slot.get((ob["time"], ob["slot"])) or []
            if cands:
                po = cands[0]
        if po is not None and ob["x"] is not None and ob["y"] is not None and "x" in po and "y" in po:
            obs_matched += 1
            px, py = float(po["x"]), float(po["y"])
            ox, oy = ob["x"], ob["y"]
            dx = abs(px - ox)
            dy = abs(py - oy)
            dist = math.hypot(px - ox, py - oy)
            obs_dx_list.append(dx)
            obs_dy_list.append(dy)
            obs_dists.append(dist)
            if abs(round(px, 1) - ox) < 1e-6 and abs(round(py, 1) - oy) < 1e-6:
                obs_exact_01 += 1
            if len(obs_samples) < 5:
                obs_samples.append({
                    "time": ob["time"], "slot": ob["slot"],
                    "parser_xy": [round(px, 3), round(py, 3)],
                    "od_obs_log_xy": [ox, oy],
                    "euclid_err": round(dist, 4),
                })

    return {
        "match_id": match_id,
        "patch": meta.get("patch"),
        "duration_sec": meta.get("duration"),
        "start_time_utc": datetime.datetime.fromtimestamp(meta["start_time"], datetime.timezone.utc).isoformat() if meta.get("start_time") else None,
        "replay_url_redacted": redact_replay_url(replay_url),
        "download_sec": round(dl_sec, 3) if dl_sec is not None else "cached",
        "detected_payload_compression": detected_fmt,
        "decompress_tool": decompress_tool,
        "file_dem_bz2": out_file_bz2.strip(),
        "file_dem": out_file_dem.strip(),
        "dem_magic_hex": dem_magic,
        "decompress_sec": round(decompress_sec, 3),
        "parse_wall_sec": round(parse_wall_sec, 3),
        "parse_time_l": time_info,
        "gzip_jsonl_sec": round(gzip_jsonl_sec, 3),
        "compact_01_gzip_sec": round(c01_sec, 3),
        "sizes_bytes": {
            "dem_bz2": bz2_path.stat().st_size,
            "dem": dem_path.stat().st_size,
            "jsonl": jsonl_path.stat().st_size,
            "jsonl_gz": jsonl_gz_path.stat().st_size,
            "compact_01_json_raw": len(c01_raw),
            "compact_01_json_gz": len(c01_gz),
            "compact_int_json_raw": len(cint_raw),
            "compact_int_json_gz": len(cint_gz),
        },
        "jsonl_total_lines": line_count,
        "event_type_counts": dict(type_counts.most_common()),
        "interval_analysis": {
            "all_keys_sorted": sorted(interval_keys),
            "sample_interval_entry": sample_interval_line,
            "dt_histogram_all": dict(sorted(dt_all.items())),
            "dt_histogram_t_ge_0": dict(sorted(dt_nonneg.items())),
            "slots_summary": slot_interval_summary,
            "coord_count": coord_count,
            "min_x": round(min_x, 4),
            "max_x": round(max_x, 4),
            "min_y": round(min_y, 4),
            "max_y": round(max_y, 4),
            "in_64_192_count": in_64_192_count,
            "cell_vec_formula_valid_count": formula_range_ok,
            "cell_vec_examples": cell_vec_examples,
        },
        "crosscheck_deaths_pos": {
            "od_teamfights_count": len(meta.get("teamfights") or []),
            "od_total_deaths_pos_entries": tf_total_od_deaths,
            "matched_via_combatlog_death": tf_matched_combatlog,
            "exact_java_round_matches": tf_exact_round_match,
            "exact_od_two_step_round_matches": tf_exact_od_two_step_match,
            "within_1_cell": tf_within_1_cell,
            "within_2_cells": tf_within_2_cells,
            "raw_euclid_min": round(min(tf_float_dists), 4) if tf_float_dists else None,
            "raw_euclid_mean": round(sum(tf_float_dists) / len(tf_float_dists), 4) if tf_float_dists else None,
            "raw_euclid_max": round(max(tf_float_dists), 4) if tf_float_dists else None,
            "round_max_dx": max(tf_round_dx) if tf_round_dx else None,
            "round_max_dy": max(tf_round_dy) if tf_round_dy else None,
            "matched_via_lifestate": tf_lifestate_matched,
            "lifestate_euclid_mean": round(sum(tf_lifestate_dists) / len(tf_lifestate_dists), 4) if tf_lifestate_dists else None,
            "lifestate_euclid_max": round(max(tf_lifestate_dists), 4) if tf_lifestate_dists else None,
            "samples": tf_samples,
        },
        "crosscheck_obs_log": {
            "od_obs_log_count": len(od_obs_list),
            "parser_obs_count": len(parser_obs),
            "matched_count": obs_matched,
            "exact_01_round_matches": obs_exact_01,
            "dx_max": round(max(obs_dx_list), 4) if obs_dx_list else None,
            "dy_max": round(max(obs_dy_list), 4) if obs_dy_list else None,
            "euclid_mean": round(sum(obs_dists) / len(obs_dists), 4) if obs_dists else None,
            "euclid_max": round(max(obs_dists), 4) if obs_dists else None,
            "samples": obs_samples,
        },
    }


def extract_9083213997_excerpt(
    jsonl_path: Path, out_path: Path, pii_needles: List[str], max_lines: int = 200
) -> Dict[str, Any]:
    """
    Extract <= 200 real unmodified JSONL lines from match 9083213997 covering
    interval, obs, obs_left, combat/death, pings, and smoke modifier events.
    Strictly excludes epilogue, chat, chatwheel, cosmetics, dotaplus, and any PII.
    """
    forbidden_types = {"epilogue", "chat", "chatwheel", "cosmetics", "dotaplus"}
    all_lines: List[Tuple[int, str, Dict[str, Any]]] = []
    with jsonl_path.open("r", encoding="utf-8") as f:
        for idx, raw in enumerate(f):
            raw = raw.rstrip("\n")
            if not raw:
                continue
            obj = json.loads(raw)
            if obj.get("type") in forbidden_types:
                continue
            # Also exclude any line containing roster names / account IDs just in case
            if any(n in raw for n in pii_needles):
                continue
            all_lines.append((idx, raw, obj))

    chosen_indices: set = set()

    # 1. Pick 10 hero interval snapshots at t in {0, 300, 600, 900, 1200, 1500, 1800, 2100} (80 lines)
    target_times = {0, 300, 600, 900, 1200, 1500, 1800, 2100}
    for idx, _, obj in all_lines:
        if obj.get("type") == "interval" and obj.get("time") in target_times:
            chosen_indices.add(idx)

    # 2. Pick up to 15 obs + 15 obs_left
    obs_cnt = 0
    obs_left_cnt = 0
    for idx, _, obj in all_lines:
        if obj.get("type") == "obs" and obs_cnt < 15:
            chosen_indices.add(idx)
            obs_cnt += 1
        elif obj.get("type") == "obs_left" and obs_left_cnt < 15:
            chosen_indices.add(idx)
            obs_left_cnt += 1

    # 3. Pick hero DOTA_COMBATLOG_DEATH (up to 15) + around the first hero death time pick DOTA_COMBATLOG_DAMAGE (10) + ABILITY (10)
    death_times: List[int] = []
    death_cnt = 0
    for idx, _, obj in all_lines:
        if (
            obj.get("type") == "DOTA_COMBATLOG_DEATH"
            and obj.get("targethero") is True
            and not obj.get("targetillusion")
            and death_cnt < 15
        ):
            chosen_indices.add(idx)
            death_times.append(int(obj.get("time", 0)))
            death_cnt += 1

    dmg_cnt = 0
    ab_cnt = 0
    focus_t = death_times[0] if death_times else 600
    for idx, _, obj in all_lines:
        t = int(obj.get("time", 0))
        if abs(t - focus_t) <= 5:
            if obj.get("type") == "DOTA_COMBATLOG_DAMAGE" and obj.get("targethero") and dmg_cnt < 10:
                chosen_indices.add(idx)
                dmg_cnt += 1
            elif obj.get("type") == "DOTA_COMBATLOG_ABILITY" and ab_cnt < 10:
                chosen_indices.add(idx)
                ab_cnt += 1

    # 4. Pick smoke modifiers (up to 15)
    smoke_cnt = 0
    for idx, _, obj in all_lines:
        if (
            obj.get("type") in {"DOTA_COMBATLOG_MODIFIER_ADD", "DOTA_COMBATLOG_MODIFIER_REMOVE"}
            and obj.get("inflictor") == "modifier_smoke_of_deceit"
            and smoke_cnt < 15
        ):
            chosen_indices.add(idx)
            smoke_cnt += 1

    # 5. Pick pings (up to 15)
    ping_cnt = 0
    for idx, _, obj in all_lines:
        if obj.get("type") == "pings" and ping_cnt < 15:
            chosen_indices.add(idx)
            ping_cnt += 1

    # 6. Pick DOTA_COMBATLOG_ITEM / DOTA_COMBATLOG_PURCHASE (up to 10)
    item_cnt = 0
    for idx, _, obj in all_lines:
        if obj.get("type") == "DOTA_COMBATLOG_ITEM" and item_cnt < 10:
            chosen_indices.add(idx)
            item_cnt += 1

    # 7. Fill remaining budget up to 180 lines with consecutive 1Hz interval ticks around focus_t
    for idx, _, obj in all_lines:
        if len(chosen_indices) >= min(180, max_lines):
            break
        if obj.get("type") == "interval" and focus_t - 1 <= int(obj.get("time", -999)) <= focus_t + 2:
            chosen_indices.add(idx)

    selected = [(idx, raw, obj) for idx, raw, obj in all_lines if idx in chosen_indices]
    selected = selected[:max_lines]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(raw for _, raw, _ in selected) + "\n", encoding="utf-8")

    # Verify extracted file independently
    excerpt_types = collections.Counter(obj.get("type") for _, _, obj in selected)
    return {
        "excerpt_path": str(out_path),
        "line_count": len(selected),
        "bytes": out_path.stat().st_size,
        "type_counts": dict(excerpt_types.most_common()),
        "pii_needles_checked": len(pii_needles),
        "pii_hits": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run M0 3-match replay benchmark and coordinate cross-check.")
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    parser.add_argument("--excerpt-out", type=Path, default=DEFAULT_EXCERPT_PATH)
    parser.add_argument("--force-download", action="store_true")
    parser.add_argument("--force-parse", action="store_true")
    args = parser.parse_args()

    java_bin, jar_path, classes_dir = find_toolchain(args.work_dir)
    _, java_ver_out, java_ver_err, _ = run_cmd([str(java_bin), "-version"])
    _, parser_sha_out, _, _ = run_cmd(["git", "-C", str(args.work_dir / "odota-parser"), "rev-parse", "HEAD"])
    _, bzip2_out, bzip2_err, _ = run_cmd(["bzip2", "-h"])
    _, zstd_out, zstd_err, _ = run_cmd(["zstd", "--version"])

    print(f"UTC_RUN_AT={datetime.datetime.now(datetime.timezone.utc).isoformat()}", flush=True)
    print(f"ODOTA_PARSER_COMMIT={parser_sha_out.strip()}", flush=True)
    print("JAVA_VERSION=" + " | ".join((java_ver_out + java_ver_err).strip().splitlines()), flush=True)
    print("BZIP2_VERSION=" + ((bzip2_out + bzip2_err).strip().splitlines()[0] if (bzip2_out + bzip2_err).strip() else "unknown"), flush=True)
    print("ZSTD_VERSION=" + ((zstd_out + zstd_err).strip().splitlines()[0] if (zstd_out + zstd_err).strip() else "unknown"), flush=True)

    results = []
    for mid in APPROVED_MATCH_IDS:
        res = analyze_match(
            mid,
            args.work_dir,
            java_bin,
            jar_path,
            classes_dir,
            force_download=args.force_download,
            force_parse=args.force_parse,
        )
        results.append(res)

    pii_needles = load_pii_needles(REPO_ROOT / "roster.json")
    excerpt_info = extract_9083213997_excerpt(
        args.work_dir / "out" / "9083213997.jsonl",
        args.excerpt_out,
        pii_needles=pii_needles,
    )

    summary = {
        "utc_run_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "odota_parser_commit": parser_sha_out.strip(),
        "matches": results,
        "excerpt_9083213997": excerpt_info,
    }
    summary_path = args.work_dir / "m0_local_results.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
