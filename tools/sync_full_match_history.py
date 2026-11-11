#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
F1 / R3-3 · 导入全量历史对局 (tools/sync_full_match_history.py)
- 数据源：OpenDota GET /players/{account_id}/matches（无需解析录像）
- 参数：significant=0（包含所有模式）、included_account_id（队友同场配对）、limit/offset（真正增量分页）、project（精简字段）
- 限速与配额：免费额度 60 次/分钟、2,000 次/天，增量同步 + 状态持久化
- 诚实缺省：不从 lane_role 推断 pos（无显式 pos 则留空 None）；party_size 缺失留空 None，不设默认 1 或 5
- 产出：public.player_matches 表记录 -> 服务器/总账读取 -> 前端总账展示
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
from cloud_store import cloud_fetch_player_matches, cloud_upsert_player_matches
from dota_constants_zh import get_hero_name

OPENDOTA_BASE_URL = "https://api.opendota.com/api"
CACHE_DIR = BASE_DIR / ".cache"
HISTORY_CACHE_PATH = CACHE_DIR / "player_matches_history.json"
HEROES_AGAINST_CACHE_PATH = CACHE_DIR / "player_heroes_against.json"
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


def _extract_explicit_pos(raw_row: Dict[str, Any]) -> Optional[int]:
    """R3-3: 仅当原始行显式包含合法 1..5 号位时保留；绝不从 lane_role / is_roaming / default_pos 推断。"""
    raw_pos = raw_row.get("pos")
    if isinstance(raw_pos, bool) or raw_pos is None:
        return None
    try:
        pos_val = int(raw_pos)
    except (TypeError, ValueError):
        return None
    return pos_val if 1 <= pos_val <= 5 else None


def normalize_player_match_row(
    account_id: int,
    raw_row: Dict[str, Any],
    default_pos: int = 0,
    included_roster_ids: Optional[List[int]] = None,
) -> Optional[Dict[str, Any]]:
    del default_pos  # R3-3: 不使用默认位置填充未解析对局
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

    pos = _extract_explicit_pos(raw_row)
    raw_lr = raw_row.get("lane_role")
    lane_role: Optional[int] = None
    if raw_lr is not None and not isinstance(raw_lr, bool):
        try:
            lr_int = int(raw_lr)
            if 1 <= lr_int <= 4:
                lane_role = lr_int
        except (TypeError, ValueError):
            lane_role = None

    raw_ps = raw_row.get("party_size")
    party_size: Optional[int] = None
    if raw_ps is not None and not isinstance(raw_ps, bool):
        try:
            ps_int = int(raw_ps)
            if ps_int >= 1:
                party_size = ps_int
        except (TypeError, ValueError):
            party_size = None

    merged_inc = set()
    for x in (raw_row.get("included_roster_ids") or []):
        if x:
            merged_inc.add(int(x))
    for x in (included_roster_ids or []):
        if x:
            merged_inc.add(int(x))
    merged_inc.discard(int(account_id))

    return {
        "account_id": int(account_id),
        "match_id": mid,
        "player_slot": slot,
        "radiant_win": rad_win,
        "won": bool(raw_row["won"]) if "won" in raw_row and raw_row["won"] is not None else won,
        "hero_id": hero_id,
        "hero_short_zh": hero_zh,
        "pos": pos,
        "lane_role": lane_role,
        "kills": int(raw_row.get("kills") or 0),
        "deaths": int(raw_row.get("deaths") or 0),
        "assists": int(raw_row.get("assists") or 0),
        "duration": int(raw_row.get("duration") or 0),
        "start_time": int(raw_row.get("start_time") or 0),
        "game_mode": int(raw_row.get("game_mode") or 0),
        "lobby_type": int(raw_row.get("lobby_type") or 0),
        "party_size": party_size,
        "included_roster_ids": sorted(merged_inc),
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
    page_size: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    真正增量分页同步单个玩家的比赛列表：
    - 使用 limit / offset 按页请求，遇到 <= max_existing_mid 的已同步记录立即停止翻页。
    - 若传入 included_account_id，则按已包含该队友标记的最大 match_id 作为增量水位线。
    """
    del default_pos
    aid = int(account_id)
    inc_id = int(included_account_id) if included_account_id is not None else None
    inc_ids = [inc_id] if inc_id and inc_id != aid else []

    by_match_id: Dict[int, Dict[str, Any]] = {}
    max_existing_mid = 0
    for r in existing_rows or []:
        if not isinstance(r, dict) or int(r.get("account_id") or 0) != aid:
            continue
        norm = normalize_player_match_row(aid, r)
        if norm:
            by_match_id[norm["match_id"]] = norm
            if inc_id is None:
                if norm["match_id"] > max_existing_mid:
                    max_existing_mid = norm["match_id"]
            else:
                if inc_id in (norm.get("included_roster_ids") or []) and norm["match_id"] > max_existing_mid:
                    max_existing_mid = norm["match_id"]

    if daily_used >= daily_limit:
        merged_list = sorted(by_match_id.values(), key=lambda x: x["match_id"], reverse=True)
        return merged_list, {
            "account_id": aid,
            "new_matches_added": 0,
            "total_matches": len(merged_list),
            "max_match_id": merged_list[0]["match_id"] if merged_list else max_existing_mid,
            "daily_used": daily_used,
            "skipped_due_to_quota": True,
        }

    eff_page_size = int(page_size) if page_size and page_size > 0 else (100 if max_existing_mid > 0 else 500)
    offset = 0
    new_added = 0

    while daily_used < daily_limit:
        if min_interval_sec > 0:
            time.sleep(min_interval_sec)

        url = build_player_matches_url(
            account_id=aid,
            included_account_id=inc_id,
            limit=eff_page_size,
            offset=offset,
        )
        fetched = fetcher(url) or []
        daily_used += 1

        if not fetched:
            break

        reached_watermark = False
        for raw in fetched:
            if not isinstance(raw, dict) or not raw.get("match_id"):
                continue
            mid = int(raw["match_id"])
            if max_existing_mid > 0 and mid <= max_existing_mid:
                reached_watermark = True
                if mid in by_match_id and inc_ids:
                    cur_inc = set(by_match_id[mid].get("included_roster_ids") or [])
                    cur_inc.update(inc_ids)
                    by_match_id[mid]["included_roster_ids"] = sorted(cur_inc)
                continue
            if mid in by_match_id:
                if inc_ids:
                    cur_inc = set(by_match_id[mid].get("included_roster_ids") or [])
                    cur_inc.update(inc_ids)
                    by_match_id[mid]["included_roster_ids"] = sorted(cur_inc)
                continue
            norm = normalize_player_match_row(
                aid,
                raw,
                included_roster_ids=inc_ids,
            )
            if norm:
                by_match_id[mid] = norm
                new_added += 1

        if reached_watermark or len(fetched) < eff_page_size:
            break
        offset += len(fetched)

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


def sync_roster_matches(
    roster: Dict[str, Any],
    existing_rows: Optional[List[Dict[str, Any]]] = None,
    fetcher: Callable[[str], List[Dict[str, Any]]] = default_opendota_fetcher,
    min_interval_sec: float = 1.05,
    daily_used: int = 0,
    daily_limit: int = 2000,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    R3-3: 同步花名册全部账号的个人历史，并对主账号逐个传入 included_account_id 补齐同场车队组合标记。
    """
    members = dota_analyst.iter_roster_accounts(roster)
    all_aids = sorted({int(aid) for m in members for aid in m["account_ids"]})
    rows_by_aid: Dict[int, List[Dict[str, Any]]] = {aid: [] for aid in all_aids}
    for r in existing_rows or []:
        if not isinstance(r, dict) or not r.get("account_id"):
            continue
        aid = int(r["account_id"])
        rows_by_aid.setdefault(aid, []).append(r)

    new_total = 0
    for aid in all_aids:
        merged, meta = sync_player_matches_incremental(
            account_id=aid,
            existing_rows=rows_by_aid.get(aid, []),
            fetcher=fetcher,
            min_interval_sec=min_interval_sec,
            daily_used=daily_used,
            daily_limit=daily_limit,
        )
        rows_by_aid[aid] = merged
        daily_used = int(meta["daily_used"])
        new_total += int(meta["new_matches_added"])

    main_aid = int((roster or {}).get("main_account_id") or 0)
    if main_aid > 0 and main_aid in rows_by_aid:
        for peer_aid in all_aids:
            if peer_aid == main_aid:
                continue
            merged_main, meta_pair = sync_player_matches_incremental(
                account_id=main_aid,
                existing_rows=rows_by_aid.get(main_aid, []),
                included_account_id=peer_aid,
                fetcher=fetcher,
                min_interval_sec=min_interval_sec,
                daily_used=daily_used,
                daily_limit=daily_limit,
            )
            rows_by_aid[main_aid] = merged_main
            daily_used = int(meta_pair["daily_used"])
            new_total += int(meta_pair["new_matches_added"])

    # 同局同阵营出现的多名花名册账号互相补齐 included_roster_ids
    by_mid_side: Dict[Tuple[int, str], List[Dict[str, Any]]] = {}
    flat_rows: List[Dict[str, Any]] = []
    for aid in sorted(rows_by_aid.keys()):
        for r in rows_by_aid[aid]:
            flat_rows.append(r)
            side = "radiant" if int(r.get("player_slot") or 0) < 128 else "dire"
            by_mid_side.setdefault((int(r["match_id"]), side), []).append(r)

    for (_mid, _side), m_rows in by_mid_side.items():
        if len(m_rows) < 2:
            continue
        side_aids = {int(r["account_id"]) for r in m_rows}
        for r in m_rows:
            cur_inc = set(int(x) for x in (r.get("included_roster_ids") or []) if x)
            cur_inc.update(side_aids - {int(r["account_id"])})
            r["included_roster_ids"] = sorted(cur_inc)

    return flat_rows, {
        "daily_used": daily_used,
        "new_matches_added": new_total,
        "synced_accounts": sum(1 for rows in rows_by_aid.values() if rows),
        "total_rows": len(flat_rows),
    }


def sync_player_heroes_against(
    account_id: int,
    fetcher: Callable[[str], List[Dict[str, Any]]] = default_opendota_fetcher,
    cache_path: Path = HEROES_AGAINST_CACHE_PATH,
    min_interval_sec: float = 0.0,
) -> List[Dict[str, Any]]:
    """从 OpenDota /players/{account_id}/heroes?significant=0 同步真实交手胜负并写入缓存文件。"""
    if min_interval_sec > 0:
        time.sleep(min_interval_sec)
    url = f"{OPENDOTA_BASE_URL}/players/{int(account_id)}/heroes?significant=0"
    raw_rows = fetcher(url) or []
    cleaned: List[Dict[str, Any]] = []
    for r in raw_rows:
        if not isinstance(r, dict):
            continue
        hid = int(r.get("hero_id") or 0)
        if hid <= 0:
            continue
        cleaned.append({
            "hero_id": hid,
            "games": int(r.get("games") or 0),
            "win": int(r.get("win") or 0),
            "with_games": int(r.get("with_games") or 0),
            "with_win": int(r.get("with_win") or 0),
            "against_games": int(r.get("against_games") or 0),
            "against_win": int(r.get("against_win") or 0),
        })
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(
            {
                "account_id": int(account_id),
                "downloaded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "heroes": cleaned,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return cleaned


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
    - players[account_id].position_winrates（仅统计显式有 pos 1..5 的记录）
    - party_size_winrates（仅统计显式有 party_size >= 1 的记录）
    - combo_winrates（同场比赛同一阵营或 included_roster_ids 标记的花名册成员组合）
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
    dedup_all_rows: List[Dict[str, Any]] = []
    for aid, p_rows in by_account.items():
        dedup_by_mid: Dict[int, Dict[str, Any]] = {}
        for r in p_rows:
            mid = r["match_id"]
            if mid in dedup_by_mid:
                prev_inc = set(dedup_by_mid[mid].get("included_roster_ids") or [])
                prev_inc.update(r.get("included_roster_ids") or [])
                dedup_by_mid[mid]["included_roster_ids"] = sorted(prev_inc)
                if dedup_by_mid[mid].get("pos") is None and r.get("pos") is not None:
                    dedup_by_mid[mid]["pos"] = r["pos"]
                if dedup_by_mid[mid].get("party_size") is None and r.get("party_size") is not None:
                    dedup_by_mid[mid]["party_size"] = r["party_size"]
            else:
                dedup_by_mid[mid] = dict(r)
        unique_rows = list(dedup_by_mid.values())
        dedup_all_rows.extend(unique_rows)
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
            pos = r.get("pos")
            if isinstance(pos, int) and 1 <= pos <= 5:
                pb = pos_buckets.setdefault(pos, {"pos": pos, "games": 0, "wins": 0})
                pb["games"] += 1
                if r["won"]:
                    pb["wins"] += 1

            ps = r.get("party_size")
            if isinstance(ps, int) and ps >= 1:
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

    # 聚合固定车队人数组合胜率 (2~5 人同局同阵营，合并 included_roster_ids)
    combo_buckets: Dict[Tuple[int, ...], Dict[str, Any]] = {}
    for (_mid, _side), m_rows in by_match_side.items():
        aids_set = {int(r["account_id"]) for r in m_rows}
        for r in m_rows:
            for inc_raw in r.get("included_roster_ids") or []:
                if not inc_raw:
                    continue
                inc_int = int(inc_raw)
                inc_canon = (
                    int(dota_analyst.resolve_canonical_account_id(inc_int, roster) or inc_int)
                    if isinstance(roster, dict)
                    else inc_int
                )
                aids_set.add(inc_canon)
        aids = tuple(sorted(aids_set))
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

    duration_and_session_tilt = compute_duration_and_session_tilt_buckets(dedup_all_rows, min_games=min_games)
    unique_mids = {int(r["match_id"]) for r in dedup_all_rows if r.get("match_id")}

    return {
        "min_sample_games": min_games,
        "synced_rows_count": len(rows or []),
        "synced_players_count": len(players_out),
        "unique_matches_count": len(unique_mids),
        "players": players_out,
        "combo_winrates": combo_list,
        "party_size_winrates": party_size_list,
        "duration_and_session_tilt": duration_and_session_tilt,
    }


def build_rows_from_local_raw_reports(roster: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """从本地 reports/raw_*.json 提取历史对局行（仅当显式传入 --offline-seed 时使用；不设默认 party_size 或推断 pos）"""
    reports_dir = BASE_DIR / "reports"
    roster = roster if isinstance(roster, dict) else dota_analyst.load_roster()
    roster_aids = {
        acc_id
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
        match_party_size = m.get("party_size")
        for p in m.get("players") or []:
            aid = p.get("account_id")
            if not aid or int(aid) not in roster_aids:
                continue
            raw_ps = p.get("party_size") if p.get("party_size") is not None else match_party_size
            row = normalize_player_match_row(
                int(aid),
                {
                    "match_id": mid,
                    "player_slot": p.get("player_slot", 0),
                    "radiant_win": rad_win,
                    "hero_id": p.get("hero_id", 0),
                    "lane_role": p.get("lane_role"),
                    "is_roaming": p.get("is_roaming", False),
                    "kills": p.get("kills", 0),
                    "deaths": p.get("deaths", 0),
                    "assists": p.get("assists", 0),
                    "duration": duration,
                    "start_time": start_time,
                    "game_mode": game_mode,
                    "lobby_type": lobby_type,
                    "party_size": raw_ps,
                },
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
    roster_names = build_roster_names_map(roster)
    all_aids = sorted({aid for m in dota_analyst.iter_roster_accounts(roster) for aid in m["account_ids"]})

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    existing_rows: List[Dict[str, Any]] = []
    if HISTORY_CACHE_PATH.exists():
        try:
            cached = json.loads(HISTORY_CACHE_PATH.read_text(encoding="utf-8"))
            if isinstance(cached, dict) and isinstance(cached.get("rows"), list):
                existing_rows = cached["rows"]
        except Exception:
            pass

    if not existing_rows and not args.offline_seed:
        existing_rows = cloud_fetch_player_matches(all_aids)

    if args.offline_seed:
        if not existing_rows:
            existing_rows = build_rows_from_local_raw_reports(roster)
    else:
        today_str = datetime.date.today().isoformat()
        sync_state = {"date": today_str, "daily_used": 0}
        if SYNC_STATE_PATH.exists():
            try:
                st = json.loads(SYNC_STATE_PATH.read_text(encoding="utf-8"))
                if isinstance(st, dict) and st.get("date") == today_str:
                    sync_state = st
            except Exception:
                pass
        existing_rows, sync_meta = sync_roster_matches(
            roster=roster,
            existing_rows=existing_rows,
            min_interval_sec=1.05,
            daily_used=int(sync_state.get("daily_used") or 0),
            daily_limit=2000,
        )
        members = dota_analyst.iter_roster_accounts(roster)
        if members and int(sync_meta["daily_used"]) < 2000:
            sync_player_heroes_against(
                account_id=int(members[0]["canonical_id"]),
                min_interval_sec=1.05,
            )
            sync_meta["daily_used"] += 1
        sync_state["daily_used"] = sync_meta["daily_used"]
        SYNC_STATE_PATH.write_text(json.dumps(sync_state, indent=2, ensure_ascii=False), encoding="utf-8")

    stats = aggregate_full_history_stats(existing_rows, roster_names=roster_names, roster=roster)
    HISTORY_CACHE_PATH.write_text(
        json.dumps({"rows": existing_rows, "stats": stats}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    pushed = False
    if args.push_supabase:
        pushed = cloud_upsert_player_matches(existing_rows)
    print(
        f"OK: synced {len(existing_rows)} player_matches rows across {len(stats['players'])} players "
        f"({stats['unique_matches_count']} unique matches; supabase_pushed={pushed})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
