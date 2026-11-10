import unittest
from tests.helpers import build_all_sample_reports, iter_report_strings, load_all_raw_matches


class TestT10Invariants(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw_matches = load_all_raw_matches()
        cls.reports = build_all_sample_reports()

    @unittest.expectedFailure  # T1-6: 命中率按实际含义展示（当前 hit_pct 用伤害次数/施放次数导致 > 100%）
    def test_t1_6_skillshot_hit_pct_at_most_100(self) -> None:
        violations = []
        for mid, report in self.reports.items():
            df = report.get("deep_forensics") or {}
            he_by_side = df.get("hero_execution_by_side") or {}
            for side, players_list in he_by_side.items():
                if not isinstance(players_list, list):
                    continue
                for p in players_list:
                    for sa in p.get("skillshot_audits") or []:
                        hit_pct = sa.get("hit_pct")
                        if isinstance(hit_pct, (int, float)) and hit_pct > 100.0:
                            violations.append(
                                f"match {mid} {side} {p.get('hero_short_zh')} {sa.get('ability_zh')}: hit_pct={hit_pct}%"
                            )
        self.assertEqual(violations, [], f"Found skillshot hit_pct > 100%: {violations[:5]}")

    def test_t1_1_zero_buybacks_means_zero_buyback_loss(self) -> None:
        violations = []
        for mid, report in self.reports.items():
            df = report.get("deep_forensics") or {}
            econ_by_side = df.get("economy_and_pings_by_side") or {}
            for side, side_key in (("radiant", "radiant_pos_1_to_5"), ("dire", "dire_pos_1_to_5")):
                team_players = report.get(side_key) or []
                bb_by_hero = {p.get("hero_short_zh"): int(p.get("buybacks") or 0) for p in team_players}
                side_data = econ_by_side.get(side) or {}
                for row in side_data.get("econ_rows") or []:
                    hero_zh = row.get("hero_short_zh")
                    if bb_by_hero.get(hero_zh, 0) == 0 and int(row.get("buyback_loss") or 0) != 0:
                        violations.append(
                            f"match {mid} {side} {hero_zh}: buybacks=0 but buyback_loss={row.get('buyback_loss')}"
                        )
        self.assertEqual(violations, [], f"Found buybacks=0 with non-zero buyback_loss: {violations[:5]}")

    @unittest.expectedFailure  # T1-5: 团战开始时已在读秒的选手不在团战缺席列表里
    def test_t1_5_dead_at_teamfight_start_not_marked_absent(self) -> None:
        violations = []
        for mid, report in self.reports.items():
            raw = self.raw_matches[mid]
            raw_players = raw.get("players") or []
            raw_tfs = raw.get("teamfights") or []
            if not raw_tfs or len(raw_players) < 10:
                continue

            df = report.get("deep_forensics") or {}
            tp_by_side = df.get("tp_rotation_by_side") or {}
            all_rep_players = (report.get("radiant_pos_1_to_5") or []) + (report.get("dire_pos_1_to_5") or [])
            hero_by_slot = {p.get("player_slot"): p.get("hero_short_zh") for p in all_rep_players}

            death_windows_by_hero = {}
            for rp in raw_players:
                slot = rp.get("player_slot")
                h_zh = hero_by_slot.get(slot)
                if not h_zh:
                    continue
                windows = []
                for d_ev in rp.get("deaths_log") or []:
                    if isinstance(d_ev, dict):
                        dt = int(d_ev.get("time") or 0)
                        td = int(d_ev.get("time_dead") or 30)
                        windows.append((dt, dt + td))
                death_windows_by_hero[h_zh] = windows

            for side, tp_data in tp_by_side.items():
                if not isinstance(tp_data, dict):
                    continue
                for ev in tp_data.get("teamfight_tp_events") or []:
                    tf_idx = int(ev.get("tf_index") or 1) - 1
                    if tf_idx < 0 or tf_idx >= len(raw_tfs):
                        continue
                    s_sec = int(raw_tfs[tf_idx].get("start") or 0)
                    for sp in ev.get("spectators") or []:
                        h_zh = sp.get("hero_short_zh")
                        windows = death_windows_by_hero.get(h_zh, [])
                        if any(dt < s_sec < respawn_t for dt, respawn_t in windows):
                            violations.append(
                                f"match {mid} {side} tf#{tf_idx+1}@{s_sec}s: {h_zh} was dead at start but marked spectator"
                            )
                for p_row in tp_data.get("player_tp_rows") or []:
                    h_zh = p_row.get("hero_short_zh")
                    windows = death_windows_by_hero.get(h_zh, [])
                    for abs_mmss in p_row.get("tf_absent_times") or []:
                        for rtf in raw_tfs:
                            s_sec = int(rtf.get("start") or 0)
                            mmss = f"{s_sec//60:02d}:{s_sec%60:02d}"
                            if mmss == abs_mmss and any(dt < s_sec < respawn_t for dt, respawn_t in windows):
                                violations.append(
                                    f"match {mid} {side} @{mmss}: {h_zh} was dead at start but in tf_absent_times"
                                )
        self.assertEqual(violations, [], f"Found dead-at-start players marked absent: {violations[:5]}")

    @unittest.expectedFailure  # T1-3: 报告任意字符串字段不含 {' (Python dict repr) 或 undefined
    def test_t1_3_no_dict_repr_or_undefined_in_report_strings(self) -> None:
        violations = []
        for mid, report in self.reports.items():
            for path, val in iter_report_strings(report):
                if "{'" in val or "undefined" in val:
                    violations.append(f"match {mid} {path}: {val[:120]}")
        self.assertEqual(violations, [], f"Found dict repr or undefined in strings: {violations[:5]}")


if __name__ == "__main__":
    unittest.main()
