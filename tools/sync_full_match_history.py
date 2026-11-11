#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
F1 · 导入全量历史对局 (tools/sync_full_match_history.py)
- 数据源：OpenDota GET /players/{account_id}/matches（无需解析录像）
- 参数：significant=0（包含所有模式）、included_account_id（可选）、project（精简字段）
- 限速与配额：免费额度 60 次/分钟、2,000 次/天，增量同步 + 状态持久化
- 产出：public.player_matches 表记录；每人英雄胜率、位置胜率；各人数组合与固定车队组合胜率（遵守 T1-9 最小样本量 >= 10 局规则）
"""

import argparse
import datetime
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import dota_analyst
from cloud_store import cloud_upsert_player_matches
from dota_constants_zh import get_hero_name

OPENDOTA_BASE_URL = "https://api.opendota.com/api"
CACHE_DIR = BASE_DIR / ".cache"
HISTORY_CACHE_PATH = CACHE_DIR / "player_matches_history.json"
SYNC_STATE_PATH = CACHE_DIR / "opendota_sync_state.json"

MATCH_PROJECT_FIELDS: Tuple[str, ...] = (
    "hero_id",
    "start_time",
    "duration",
    "player_slot",
    "radiant_win",
    "game_mode",
    "lobby_type",
    "kills",
    "deaths",
    "assists",
    "party_size",
    "lane_role",
    "is_roaming",
)

MIN_SAMPLE_GAMES = 10


def build_player_matches_url(
    account_id: int,
    included_account_id: Optional[int] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    significant: int = 0,
    project_fields: Tuple[str, ...] = MATCH_PROJECT_FIELDS,
) -> str:
    """构造 OpenDota /players/{account_id}/matches 查询 URL"""
    aid = int(account_id)
    query_pairs: List[Tuple[str, str]] = [("significant", str(int(significant)))]
    if included_account_id is not None:
        query_pairs.append(("included_account_id", str(int(included_account_id))))
    if limit is not None:
        query_pairs.append(("limit", str(int(limit))))
    if offset is not None:
        query_pairs.append(("offset", str(int(offset))))
    for field in project_fields:
        query_pairs.append(("project", str(field)))
    qs = urllib.parse.urlencode(query_pairs)
    return f"{OPENDOTA_BASE_URL}/players/{aid}/matches?{qs}"


def _estimate_pos_from_summary(raw_row: Dict[str, Any], default_pos: int = 0) -> int:
    """从 /players/{id}/matches 的 lane_role / is_roaming 或花名册默认位置估算 1..5 号位"""
    pos = int(raw_row.get("pos") or 0)
    if 1 <= pos <= 5:
        return pos
    lane_role = int(raw_row.get("lane_role") or 0)
    is_roaming = bool(raw_row.get("is_roaming"))
    if is_roaming:
        return 4
    if lane_role == 1:
        return 1
    if lane_role == 2:
        return 2
    if lane_role == 3:
        return 3
    if 1 <= default_pos <= 5:
        return default_pos
    return 0


def normalize_player_match_row(
    account_id: int,
    raw_row: Dict[str, Any],
    default_pos: int = 0,
    included_roster_ids: Optional[List[int]] = None,
) -> Optional[Dict[str, Any]]:
    if not isinstance(raw_row, dict) or not raw_row.get("match_id"):
        return None
    mid = int(raw_row["match_id"])
    slot = int(raw_row.get("player_slot") or 0)
    rad_win = bool(raw_row.get("radiant_win"))
    is_radiant = slot < 128
    won = rad_win if is_radiant else (not rad_win)
    hero_id = int(raw_row.get("hero_id") or 0)
    hero_info = get_hero_name(hero_id) if hero_id > 0 else ("", "")
    if isinstance(hero_info, (tuple, list)):
        hero_zh_default = str(hero_info[1] if len(hero_info) > 1 else (hero_info[0] if hero_info else ""))
    elif isinstance(hero_info, dict):
        hero_zh_default = str(hero_info.get("short_zh") or hero_info.get("name_zh") or "")
    else:
        hero_zh_default = str(hero_info or "")
    hero_zh = str(raw_row.get("hero_short_zh") or hero_zh_default)
    pos = _estimate_pos_from_summary(raw_row, default_pos=default_pos)
    return {
        "account_id": int(account_id),
        "match_id": mid,
        "player_slot": slot,
        "radiant_win": rad_win,
        "won": bool(raw_row["won"]) if "won" in raw_row and raw_row["won"] is not None else won,
        "hero_id": hero_id,
        "hero_short_zh": hero_zh,
        "pos": pos,
        "lane_role": int(raw_row.get("lane_role") or 0),
        "kills": int(raw_row.get("kills") or 0),
        "deaths": int(raw_row.get("deaths") or 0),
        "assists": int(raw_row.get("assists") or 0),
        "duration": int(raw_row.get("duration") or 0),
        "start_time": int(raw_row.get("start_time") or 0),
        "game_mode": int(raw_row.get("game_mode") or 0),
        "lobby_type": int(raw_row.get("lobby_type") or 0),
        "party_size": int(raw_row.get("party_size") or 1),
        "included_roster_ids": sorted(set(int(x) for x in (included_roster_ids or raw_row.get("included_roster_ids") or []) if x)),
    }


def default_opendota_fetcher(url: str) -> List[Dict[str, Any]]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "dota-5stack-ledger-history-sync/1.0", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data if isinstance(data, list) else []


def sync_player_matches_incremental(
    account_id: int,
    existing_rows: Optional[List[Dict[str, Any]]] = None,
    included_account_id: Optional[int] = None,
    default_pos: int = 0,
    fetcher: Callable[[str], List[Dict[str, Any]]] = default_opendota_fetcher,
    min_interval_sec: float = 0.0,
    daily_used: int = 0,
    daily_limit: int = 2000,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    增量同步单个玩家的比赛列表：
    - 若已存在历史记录，计算 max_existing_match_id，只合并更新的 match_id（或缺失的 match_id）。
    - 严格遵守每日请求上限 daily_limit 与最小请求间隔 min_interval_sec。
    """
    aid = int(account_id)
    by_match_id: Dict[int, Dict[str, Any]] = {}
    max_existing_mid = 0
    for r in existing_rows or []:
        if not isinstance(r, dict) or int(r.get("account_id") or 0) != aid:
            continue
        norm = normalize_player_match_row(aid, r, default_pos=default_pos)
        if norm:
            by_match_id[norm["match_id"]] = norm
            if norm["match_id"] > max_existing_mid:
                max_existing_mid = norm["match_id"]

    if daily_used >= daily_limit:
        merged_list = sorted(by_match_id.values(), key=lambda x: x["match_id"], reverse=True)
        return merged_list, {
            "account_id": aid,
            "new_matches_added": 0,
            "total_matches": len(merged_list),
            "max_match_id": max_existing_mid,
            "daily_used": daily_used,
            "skipped_due_to_quota": True,
        }

    if min_interval_sec > 0:
        time.sleep(min_interval_sec)

    url = build_player_matches_url(
        account_id=aid,
        included_account_id=included_account_id,
    )
    fetched = fetcher(url) or []
    daily_used += 1

    new_added = 0
    inc_ids = [int(included_account_id)] if included_account_id else []
    for raw in fetched:
        if not isinstance(raw, dict) or not raw.get("match_id"):
            continue
        mid = int(raw["match_id"])
        if mid in by_match_id:
            if inc_ids:
                cur_inc = set(by_match_id[mid].get("included_roster_ids") or [])
                cur_inc.update(inc_ids)
                by_match_id[mid]["included_roster_ids"] = sorted(cur_inc)
            continue
        norm = normalize_player_match_row(
            aid,
            raw,
            default_pos=default_pos,
            included_roster_ids=inc_ids,
        )
        if norm:
            by_match_id[mid] = norm
            new_added += 1

    merged_list = sorted(by_match_id.values(), key=lambda x: x["match_id"], reverse=True)
    max_mid = merged_list[0]["match_id"] if merged_list else max_existing_mid
    return merged_list, {
        "account_id": aid,
        "new_matches_added": new_added,
        "total_matches": len(merged_list),
        "max_match_id": max_mid,
        "daily_used": daily_used,
        "skipped_due_to_quota": False,
    }


def build_roster_names_map(roster: Optional[Dict[str, Any]] = None) -> Dict[int, str]:
    """从统一花名册 iter_roster_accounts 提取 canonical_id -> 队员名称映射。"""
    out: Dict[int, str] = {}
    for m in dota_analyst.iter_roster_accounts(roster):
        out[int(m["canonical_id"])] = str(m["name"])
    return out


def aggregate_full_history_stats(
    rows: List[Dict[str, Any]],
    roster_names: Optional[Dict[int, str]] = None,
    min_games: int = MIN_SAMPLE_GAMES,
    roster: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    聚合全量历史对局统计（严格执行 T1-9 最小样本量规则）：
    - players[account_id].hero_winrates
    - players[account_id].position_winrates
    - party_size_winrates
    - combo_winrates（同场比赛同一阵营出现的花名册成员组合）
    """
    if roster_names is None and isinstance(roster, dict):
        roster_names = build_roster_names_map(roster)
    roster_names = roster_names or {}
    by_account: Dict[int, List[Dict[str, Any]]] = {}
    by_match_side: Dict[Tuple[int, str], List[Dict[str, Any]]] = {}
    party_buckets: Dict[int, Dict[str, int]] = {}

    for raw in rows or []:
        if not isinstance(raw, dict) or not raw.get("account_id") or not raw.get("match_id"):
            continue
        raw_aid = int(raw["account_id"])
        aid = (
            int(dota_analyst.resolve_canonical_account_id(raw_aid, roster) or raw_aid)
            if isinstance(roster, dict)
            else raw_aid
        )
        norm = normalize_player_match_row(aid, raw)
        if not norm:
            continue
        by_account.setdefault(aid, []).append(norm)
        side = "radiant" if int(norm["player_slot"]) < 128 else "dire"
        by_match_side.setdefault((int(norm["match_id"]), side), []).append(norm)

    players_out: Dict[int, Dict[str, Any]] = {}
    for aid, p_rows in by_account.items():
        dedup_by_mid: Dict[int, Dict[str, Any]] = {}
        for r in p_rows:
            dedup_by_mid[r["match_id"]] = r
        unique_rows = list(dedup_by_mid.values())
        total_games = len(unique_rows)
        total_wins = sum(1 for r in unique_rows if r["won"])

        hero_buckets: Dict[int, Dict[str, Any]] = {}
        pos_buckets: Dict[int, Dict[str, int]] = {}
        for r in unique_rows:
            hid = int(r.get("hero_id") or 0)
            if hid > 0:
                hb = hero_buckets.setdefault(
                    hid,
                    {"hero_id": hid, "hero_short_zh": r.get("hero_short_zh") or "", "games": 0, "wins": 0},
                )
                hb["games"] += 1
                if r["won"]:
                    hb["wins"] += 1
            pos = int(r.get("pos") or 0)
            if 1 <= pos <= 5:
                pb = pos_buckets.setdefault(pos, {"pos": pos, "games": 0, "wins": 0})
                pb["games"] += 1
                if r["won"]:
                    pb["wins"] += 1

            ps = int(r.get("party_size") or 0)
            if ps >= 1:
                ps_b = party_buckets.setdefault(ps, {"party_size": ps, "games": 0, "wins": 0})
                ps_b["games"] += 1
                if r["won"]:
                    ps_b["wins"] += 1

        hero_list: List[Dict[str, Any]] = []
        for hid, hb in hero_buckets.items():
            g = hb["games"]
            w = hb["wins"]
            sufficient = g >= min_games
            hero_list.append({
                "hero_id": hid,
                "hero_short_zh": hb["hero_short_zh"],
                "games": g,
                "wins": w,
                "losses": g - w,
                "win_rate": round(w * 100.0 / g, 1) if sufficient else None,
                "insufficient_sample": not sufficient,
            })
        hero_list.sort(key=lambda x: (x["games"], x["wins"]), reverse=True)

        pos_list: List[Dict[str, Any]] = []
        for pos in range(1, 6):
            pb = pos_buckets.get(pos, {"pos": pos, "games": 0, "wins": 0})
            g = pb["games"]
            w = pb["wins"]
            sufficient = g >= min_games
            pos_list.append({
                "pos": pos,
                "games": g,
                "wins": w,
                "losses": g - w,
                "win_rate": round(w * 100.0 / g, 1) if sufficient else None,
                "insufficient_sample": not sufficient,
            })

        players_out[aid] = {
            "account_id": aid,
            "personaname": roster_names.get(aid) or f"Player {aid}",
            "total_games": total_games,
            "total_wins": total_wins,
            "win_rate": round(total_wins * 100.0 / total_games, 1) if total_games >= min_games else None,
            "insufficient_sample": total_games < min_games,
            "hero_winrates": hero_list,
            "position_winrates": pos_list,
        }

    # 聚合固定车队人数组合胜率 (2~5 人同局同阵营)
    combo_buckets: Dict[Tuple[int, ...], Dict[str, Any]] = {}
    for (_mid, _side), m_rows in by_match_side.items():
        aids = tuple(sorted({int(r["account_id"]) for r in m_rows}))
        if len(aids) < 2:
            continue
        won = bool(m_rows[0]["won"])
        cb = combo_buckets.setdefault(
            aids,
            {
                "account_ids": list(aids),
                "player_names": [roster_names.get(a, str(a)) for a in aids],
                "party_count": len(aids),
                "games": 0,
                "wins": 0,
            },
        )
        cb["games"] += 1
        if won:
            cb["wins"] += 1

    combo_list: List[Dict[str, Any]] = []
    for cb in combo_buckets.values():
        g = cb["games"]
        w = cb["wins"]
        sufficient = g >= min_games
        combo_list.append({
            **cb,
            "losses": g - w,
            "win_rate": round(w * 100.0 / g, 1) if sufficient else None,
            "insufficient_sample": not sufficient,
        })
    combo_list.sort(key=lambda x: (x["games"], x["wins"]), reverse=True)

    party_size_list: List[Dict[str, Any]] = []
    for ps, pb in sorted(party_buckets.items()):
        g = pb["games"]
        w = pb["wins"]
        sufficient = g >= min_games
        party_size_list.append({
            "party_size": ps,
            "games": g,
            "wins": w,
            "losses": g - w,
            "win_rate": round(w * 100.0 / g, 1) if sufficient else None,
            "insufficient_sample": not sufficient,
        })

    from squad_growth_metrics import compute_duration_and_session_tilt_buckets

    all_norm_rows = [r for p_rows in by_account.values() for r in p_rows]
    duration_and_session_tilt = compute_duration_and_session_tilt_buckets(all_norm_rows, min_games=min_games)

    return {
        "min_sample_games": min_games,
        "players": players_out,
        "combo_winrates": combo_list,
        "party_size_winrates": party_size_list,
        "duration_and_session_tilt": duration_and_session_tilt,
    }


def build_rows_from_local_raw_reports(roster: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """从本地 reports/raw_*.json 提取历史对局行（用于离线测试或初始种子）"""
    reports_dir = BASE_DIR / "reports"
    roster = roster if isinstance(roster, dict) else dota_analyst.load_roster()
    member_by_aid = {
        acc_id: m
        for m in dota_analyst.iter_roster_accounts(roster)
        for acc_id in m["account_ids"]
    }
    rows: List[Dict[str, Any]] = []
    for raw_file in sorted(reports_dir.glob("raw_*.json")):
        try:
            m = json.loads(raw_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        mid = int(m.get("match_id") or 0)
        if not mid:
            continue
        rad_win = bool(m.get("radiant_win"))
        duration = int(m.get("duration") or 0)
        start_time = int(m.get("start_time") or 0)
        game_mode = int(m.get("game_mode") or 0)
        lobby_type = int(m.get("lobby_type") or 0)
        party_size = int(m.get("party_size") or 5)
        for p in m.get("players") or []:
            aid = p.get("account_id")
            if not aid:
                continue
            member = member_by_aid.get(int(aid))
            default_pos = int(member["pos"] or 0) if member and member.get("pos") else 0
            row = normalize_player_match_row(
                int(aid),
                {
                    "match_id": mid,
                    "player_slot": p.get("player_slot", 0),
                    "radiant_win": rad_win,
                    "hero_id": p.get("hero_id", 0),
                    "lane_role": p.get("lane_role", 0),
                    "is_roaming": p.get("is_roaming", False),
                    "kills": p.get("kills", 0),
                    "deaths": p.get("deaths", 0),
                    "assists": p.get("assists", 0),
                    "duration": duration,
                    "start_time": start_time,
                    "game_mode": game_mode,
                    "lobby_type": lobby_type,
                    "party_size": p.get("party_size") or party_size,
                },
                default_pos=default_pos,
            )
            if row:
                rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="F1: 增量同步车队成员 OpenDota 全量历史对局")
    parser.add_argument("--offline-seed", action="store_true", help="仅使用本地 raw_*.json 生成种子，不联网请求")
    parser.add_argument("--push-supabase", action="store_true", help="将同步结果批量写入 Supabase player_matches 表")
    args = parser.parse_args()

    roster = dota_analyst.load_roster()
    members = dota_analyst.iter_roster_accounts(roster)
    roster_names = build_roster_names_map(roster)
    account_default_pos = {
        aid: int(m["pos"] or 0)
        for m in members
        for aid in m["account_ids"]
    }

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    existing_rows: List[Dict[str, Any]] = []
    if HISTORY_CACHE_PATH.exists():
        try:
            cached = json.loads(HISTORY_CACHE_PATH.read_text(encoding="utf-8"))
            if isinstance(cached, dict) and isinstance(cached.get("rows"), list):
                existing_rows = cached["rows"]
        except Exception:
            pass

    if not existing_rows:
        existing_rows = build_rows_from_local_raw_reports(roster)

    if not args.offline_seed:
        today_str = datetime.date.today().isoformat()
        sync_state = {"date": today_str, "daily_used": 0}
        if SYNC_STATE_PATH.exists():
            try:
                st = json.loads(SYNC_STATE_PATH.read_text(encoding="utf-8"))
                if isinstance(st, dict) and st.get("date") == today_str:
                    sync_state = st
            except Exception:
                pass
        all_rows: List[Dict[str, Any]] = []
        for aid in sorted(account_default_pos.keys()):
            default_pos = account_default_pos.get(aid, 0)
            acc_existing = [r for r in existing_rows if int(r.get("account_id") or 0) == aid]
            merged, meta = sync_player_matches_incremental(
                account_id=aid,
                existing_rows=acc_existing,
                default_pos=default_pos,
                min_interval_sec=1.05,
                daily_used=int(sync_state.get("daily_used") or 0),
                daily_limit=2000,
            )
            sync_state["daily_used"] = meta["daily_used"]
            all_rows.extend(merged)
        existing_rows = all_rows
        SYNC_STATE_PATH.write_text(json.dumps(sync_state, indent=2, ensure_ascii=False), encoding="utf-8")

    stats = aggregate_full_history_stats(existing_rows, roster_names=roster_names, roster=roster)
    HISTORY_CACHE_PATH.write_text(
        json.dumps({"rows": existing_rows, "stats": stats}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if args.push_supabase:
        cloud_upsert_player_matches(existing_rows)
    print(f"OK: synced {len(existing_rows)} player_matches rows across {len(stats['players'])} players.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
