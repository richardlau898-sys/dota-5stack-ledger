# -*- coding: utf-8 -*-
"""
说明：本脚本输出的逐秒坐标序列与压缩体积结果均为合成数据（未实测真实录像文件）。
因本地与测试环境未安装 JVM / Docker（无法运行 odota/parser），且仓库内的历史比赛录像均已超过 Valve 保留期，
本脚本仅用于模拟 interval JSONL 流的数据结构转换与 gzip 序列化流程，不得作为真实录像实测依据。
"""
import gzip
import json
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent


def extract_replay_url_from_raw_match(raw_match: Dict[str, Any]) -> Optional[str]:
    """从 OpenDota 原始比赛 JSON 提取或拼接 Valve .dem.bz2 录像下载地址。"""
    if not isinstance(raw_match, dict):
        return None
    direct_url = raw_match.get("replay_url")
    if isinstance(direct_url, str) and direct_url.startswith("http"):
        return direct_url
    match_id = raw_match.get("match_id")
    cluster = raw_match.get("cluster")
    replay_salt = raw_match.get("replay_salt")
    if match_id and cluster and replay_salt:
        return f"http://replay{int(cluster)}.valve.net/570/{int(match_id)}_{int(replay_salt)}.dem.bz2"
    return None


def parse_odota_parser_intervals_jsonl(jsonl_lines: Iterable[str]) -> Dict[str, List[List[int]]]:
    """
    解析 interval JSONL 流，提取每秒每个槽位（slot 0..9）的坐标 [time, x, y]。
    仅保留 type == 'interval' 且 time >= 0 且含有效 x, y 的记录。
    """
    trajectories: Dict[str, List[List[int]]] = {str(slot): [] for slot in range(10)}
    for raw_line in jsonl_lines:
        if not raw_line:
            continue
        entry = json.loads(raw_line) if isinstance(raw_line, str) else raw_line
        if entry.get("type") != "interval":
            continue
        slot = entry.get("slot")
        if slot is None or not (0 <= int(slot) <= 9):
            continue
        t = entry.get("time")
        x = entry.get("x")
        y = entry.get("y")
        if t is None or x is None or y is None or int(t) < 0:
            continue
        trajectories[str(int(slot))].append([int(t), int(x), int(y)])
    return trajectories


def simulate_interval_stream_compression(
    match_id: int,
    replay_url: str,
    jsonl_lines: Iterable[str],
) -> Dict[str, Any]:
    """
    对输入的 interval JSONL 流（合成数据）执行结构提取与 gzip 压缩模拟。
    返回结构摘要与字节数，明确标注 synthetic=True。
    """
    t0 = time.perf_counter()
    trajectories = parse_odota_parser_intervals_jsonl(jsonl_lines)
    parse_elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)

    active_slots = [s for s, pts in trajectories.items() if len(pts) > 0]
    total_ticks_per_hero = max((len(pts) for pts in trajectories.values()), default=0)

    payload = {
        "synthetic": True,
        "note": "合成数据，未实测真实录像",
        "match_id": int(match_id),
        "replay_url": replay_url,
        "tick_interval_sec": 1,
        "hero_count": len(active_slots),
        "total_ticks_per_hero": total_ticks_per_hero,
        "trajectories": trajectories,
    }

    t1 = time.perf_counter()
    raw_bytes = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    gzip_bytes = gzip.compress(raw_bytes, compresslevel=9)
    compress_elapsed_ms = round((time.perf_counter() - t1) * 1000.0, 2)

    raw_len = len(raw_bytes)
    gz_len = len(gzip_bytes)
    ratio = round(gz_len / raw_len, 4) if raw_len > 0 else 1.0

    return {
        "synthetic": True,
        "note": "合成数据，未实测真实录像",
        "match_id": int(match_id),
        "replay_url": replay_url,
        "hero_count": len(active_slots),
        "total_ticks_per_hero": total_ticks_per_hero,
        "total_coordinate_points": sum(len(pts) for pts in trajectories.values()),
        "parse_elapsed_ms": parse_elapsed_ms,
        "compress_elapsed_ms": compress_elapsed_ms,
        "raw_json_bytes": raw_len,
        "gzip_bytes": gz_len,
        "compression_ratio": ratio,
    }


def build_synthetic_interval_lines_from_match(
    raw_match: Dict[str, Any], duration_override: Optional[int] = None
) -> List[str]:
    """根据比赛分路热力锚点构造合成的 interval JSONL 序列（合成数据，非真实走位）。"""
    duration = int(duration_override or raw_match.get("duration") or 2400)
    players = raw_match.get("players") or []
    slot_anchors: Dict[int, List[tuple]] = {}
    for idx, p in enumerate(players[:10]):
        lp = p.get("lane_pos") or {}
        pts = []
        for x_str, y_map in lp.items():
            if isinstance(y_map, dict):
                for y_str, cnt in y_map.items():
                    try:
                        pts.append((int(x_str), int(y_str), int(cnt)))
                    except (ValueError, TypeError):
                        pass
        if not pts:
            base = 82 if idx < 5 else 170
            pts = [(base, base, 1)]
        pts.sort(key=lambda item: (-item[2], item[0], item[1]))
        slot_anchors[idx] = [(x, y) for x, y, _ in pts]

    for idx in range(10):
        if idx not in slot_anchors:
            base = 82 if idx < 5 else 170
            slot_anchors[idx] = [(base, base)]

    lines: List[str] = []
    for t in range(duration):
        for slot in range(10):
            anchors = slot_anchors[slot]
            ax, ay = anchors[(t // 15) % len(anchors)]
            dx = (t % 5) - 2
            dy = ((t // 3) % 5) - 2
            lines.append(
                json.dumps(
                    {
                        "time": t,
                        "type": "interval",
                        "slot": slot,
                        "x": max(64, min(192, ax + dx)),
                        "y": max(64, min(192, ay + dy)),
                        "life_state": 0,
                    },
                    separators=(",", ":"),
                )
            )
    return lines


def main() -> int:
    raw_path = REPO_ROOT / "reports" / "raw_8774383260.json"
    raw_match = json.loads(raw_path.read_text(encoding="utf-8"))
    replay_url = extract_replay_url_from_raw_match(raw_match) or ""
    match_id = int(raw_match["match_id"])

    synth_lines = build_synthetic_interval_lines_from_match(raw_match)
    result = simulate_interval_stream_compression(match_id, replay_url, synth_lines)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
