import copy
import unittest
from tests.helpers import build_all_sample_reports, iter_report_strings, load_all_raw_matches
import dota_analyst


class TestR23SkillLevelsAndLateThreshold(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw_matches = load_all_raw_matches()
        cls.reports = build_all_sample_reports()

    def test_1_standard_skill_points_20_plus_map_to_26_plus(self) -> None:
        """0 manual attribute points: point 17->18, 18->20, 19->25, 20->26, 21->27, 22->28, 23->29."""
        checked_20 = 0
        checked_23 = 0
        for mid, rep in self.reports.items():
            dq_by_side = (rep.get("deep_forensics") or {}).get("damage_quality_and_build_by_side") or {}
            for side_key, side_data in dq_by_side.items():
                if not isinstance(side_data, dict):
                    continue
                for row in side_data.get("player_rows") or []:
                    hero_zh = row.get("hero_short_zh") or ""
                    if hero_zh in ("祈求者", "德鲁伊", "米波"):
                        continue
                    seq = row.get("level_sequence") or []
                    if any(item.get("type") == "attr" for item in seq):
                        continue
                    if len(seq) >= 20:
                        checked_20 += 1
                        self.assertEqual(seq[16].get("level"), 18, f"[{mid}] {hero_zh} pt17: {seq[16]}")
                        self.assertEqual(seq[17].get("level"), 20, f"[{mid}] {hero_zh} pt18: {seq[17]}")
                        self.assertEqual(seq[18].get("level"), 25, f"[{mid}] {hero_zh} pt19: {seq[18]}")
                        self.assertEqual(seq[19].get("level"), 26, f"[{mid}] {hero_zh} pt20 should be L26: {seq[19]}")
                    if len(seq) >= 23:
                        checked_23 += 1
                        self.assertEqual(
                            [seq[i].get("level") for i in range(19, 23)],
                            [26, 27, 28, 29],
                            f"[{mid}] {hero_zh} pts 20..23: {seq[19:23]}",
                        )
        self.assertGreaterEqual(checked_20, 10)
        self.assertGreaterEqual(checked_23, 5)

    def test_2_players_who_leveled_attribute_bonus_have_valid_unlock_levels(self) -> None:
        """Players who manually leveled special_bonus_attributes must NOT be excluded and must satisfy unlock rules."""
        # 1) Real sample players who leveled special_bonus_attributes (e.g. 9049526926 Hoodwink, 9061341080 Terrorblade, 8646427108 Juggernaut, 9059875959 Oracle)
        attr_players_found = 0
        for mid, rep in self.reports.items():
            dq_by_side = (rep.get("deep_forensics") or {}).get("damage_quality_and_build_by_side") or {}
            for side_data in dq_by_side.values():
                if not isinstance(side_data, dict):
                    continue
                for row in side_data.get("player_rows") or []:
                    seq = row.get("level_sequence") or []
                    if not any(item.get("type") == "attr" for item in seq):
                        continue
                    attr_players_found += 1
                    levels = [int(item.get("level") or 0) for item in seq]
                    self.assertEqual(levels, sorted(levels), f"[{mid}] {row.get('hero_short_zh')} non-sorted: {levels}")
                    self.assertEqual(len(levels), len(set(levels)), f"[{mid}] {row.get('hero_short_zh')} duplicate levels: {levels}")
                    ults = [item for item in seq if item.get("type") == "ult"]
                    for u_idx, u_item in enumerate(ults, 1):
                        min_u = {1: 6, 2: 12, 3: 18}.get(u_idx, 18)
                        self.assertGreaterEqual(
                            u_item["level"],
                            min_u,
                            f"[{mid}] {row.get('hero_short_zh')} ult #{u_idx} below L{min_u}: {u_item}",
                        )
                    tals = [item for item in seq if item.get("type") == "talent"]
                    for t_idx, t_item in enumerate(tals, 1):
                        min_t = {1: 10, 2: 15, 3: 20, 4: 25, 5: 26, 6: 27, 7: 28, 8: 29}.get(t_idx, 29)
                        self.assertGreaterEqual(
                            t_item["level"],
                            min_t,
                            f"[{mid}] {row.get('hero_short_zh')} talent #{t_idx} below L{min_t}: {t_item}",
                        )
        self.assertGreaterEqual(attr_players_found, 3)

        # 2) Real match 9061341080 Terrorblade (took 1 manual attr at pt 11, ended at pt 18 sunder#3)
        # Extend his real ability_upgrades_arr with 20-talent, 25-talent, and unchosen 10-talent:
        # Old buggy code marked them L19, L20, L21 because has_explicit_attr=True!
        raw = copy.deepcopy(self.raw_matches[9061341080])
        tb_raw = next(p for p in raw["players"] if int(p.get("hero_id") or 0) == 109)
        # Append 20-talent (6145), 25-talent (6930), and unchosen talent (5918)
        tb_raw["ability_upgrades_arr"] = list(tb_raw["ability_upgrades_arr"]) + [6145, 6930, 5918]
        tb_raw["level"] = 27
        rep_ext = dota_analyst.analyze_match_data(raw, roster=dota_analyst.load_roster())
        dq_ext = (rep_ext.get("deep_forensics") or {}).get("damage_quality_and_build_by_side") or {}
        tb_row = next(
            r
            for sd in dq_ext.values()
            for r in (sd.get("player_rows") or [])
            if r.get("hero_short_zh") == "恐怖利刃"
        )
        tb_seq = tb_row["level_sequence"]
        self.assertTrue(any(item.get("type") == "attr" for item in tb_seq))
        # pt 18 = sunder #3 (L18), pt 19 = 20-talent (L20, skipping L19 auto-attr), pt 20 = 25-talent (L25), pt 21 = unchosen talent (L26)
        self.assertEqual(tb_seq[17]["level"], 18, f"TB pt18 ult3: {tb_seq[17]}")
        self.assertEqual(tb_seq[18]["level"], 20, f"TB pt19 20-talent must be L20, not L19: {tb_seq[18]}")
        self.assertEqual(tb_seq[19]["level"], 25, f"TB pt20 25-talent must be L25, not L20: {tb_seq[19]}")
        self.assertEqual(tb_seq[20]["level"], 26, f"TB pt21 unchosen talent must be L26: {tb_seq[20]}")

    def test_3_late_phase_under_5_minutes_emits_no_late_verdicts(self) -> None:
        """Match 8774383260 (27.3m -> 2.3m late phase < 5m) must NOT emit late-game performance verdicts."""
        rep = self.reports[8774383260]
        self.assertLess(int(rep.get("duration_sec") or 0) - 1500, 300)

        for side_key in ("radiant_pos_1_to_5", "dire_pos_1_to_5"):
            for p in rep.get(side_key) or []:
                hmp = p.get("hero_mechanism_profile") or {}
                self.assertFalse(hmp.get("late_harvest_failed"), f"{p.get('hero_short_zh')} falsely marked late_harvest_failed")
                self.assertFalse(hmp.get("late_harvest_fulfilled"), f"{p.get('hero_short_zh')} falsely marked late_harvest_fulfilled")

        late_phase = next((ph for ph in (rep.get("phases_data") or []) if ph.get("key") == "late"), None)
        self.assertIsNotNone(late_phase)
        self.assertFalse(bool(late_phase.get("available", True)))
        for pp in late_phase.get("players") or []:
            self.assertEqual(pp.get("good"), [], f"Unexpected late good verdict on 2.3m late phase: {pp}")
            self.assertEqual(pp.get("bad"), [], f"Unexpected late bad verdict on 2.3m late phase: {pp}")

        banned_late_verdicts = (
            "后期出山收割断档",
            "后期收割违约",
            "刷满经济后期未收割",
            "大核刷25m未兑现收割",
            "大核出山收割",
            "教科书式大核后期收割",
            "后期团战输出匮乏",
            "后期决胜阶段",
            "后期上高地与买活反打",
            "后期辅助尽职尽责",
            "后期改进重点",
            "后期团队怎么进步",
            "25分钟后全队打出",
            "后期逆风局全队",
            "后期推进与切后排接管职责",
            "后期收割呢",
        )
        for path, s in iter_report_strings(rep):
            for phrase in banned_late_verdicts:
                self.assertNotIn(phrase, s, f"Banned late verdict '{phrase}' found in 27.3m match at {path}: {s}")

    def test_4_no_empty_ability_brackets_in_any_sample_report(self) -> None:
        """Never emit '用【】' or empty '⚡ （' across all 21 regenerated sample reports."""
        for mid, rep in self.reports.items():
            for path, s in iter_report_strings(rep):
                self.assertNotIn("【】", s, f"Empty 【】 in match {mid} {path}: {s}")
                self.assertNotIn("⚡ （", s, f"Empty ability name '⚡ （' in match {mid} {path}: {s}")
                self.assertNotEqual(s, "⚡ ", f"Empty ability zh_name '⚡ ' in match {mid} {path}")


if __name__ == "__main__":
    unittest.main()
