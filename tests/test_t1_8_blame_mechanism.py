import copy
import inspect
import unittest

import ai_coach_engine
from tests.helpers import build_all_sample_reports, iter_report_strings


class TestT18BlameMechanism(unittest.TestCase):
    def test_1_no_clear_culprit_when_max_blame_below_threshold(self):
        reports = list(build_all_sample_reports().values())
        rep = copy.deepcopy(reports[0])
        rad = copy.deepcopy(rep["radiant_pos_1_to_5"])
        dire = copy.deepcopy(rep["dire_pos_1_to_5"])
        for p in rad + dire:
            p["raw_blame_points"] = 18.0
            p["blame_share_pct"] = 20.0
        res = ai_coach_engine.select_match_mvp_and_culprit(
            rad, dire, radiant_win=False, user_team_side="radiant"
        )
        self.assertTrue(res.get("no_clear_culprit"))
        self.assertEqual(res.get("culprit_label"), "无明显责任人")
        self.assertIn("无明显责任人", res["culprit_player"]["verdict"])

    def test_2_slark_no_exclusive_blame_branch(self):
        src = inspect.getsource(ai_coach_engine.evaluate_player_deeply)
        self.assertNotIn("hid_cur == 93", src)
        self.assertNotIn("hid_cur != 93", src)
        self.assertNotIn("三大致命败因", src)

    def test_3_death_penalty_normalized_by_position_and_10m(self):
        reports = list(build_all_sample_reports().values())
        rep = copy.deepcopy(reports[0])
        team = copy.deepcopy(rep["radiant_pos_1_to_5"])
        enemy = copy.deepcopy(rep["dire_pos_1_to_5"])

        # Pos 5 in a 50-minute match with 8 deaths -> 1.6 deaths/10m (should NOT trigger high-death penalty)
        p5 = copy.deepcopy(next(p for p in team if p["pos"] == 5))
        p5["deaths"] = 8
        p5["dead_seconds"] = 180
        res_p5_50m = ai_coach_engine.evaluate_player_deeply(
            copy.deepcopy(p5), team, enemy, won=False, duration_min=50.0, is_parsed=True, is_turbo=False
        )
        self.assertFalse(
            any("高频阵亡" in w for w in res_p5_50m["weaknesses"]),
            f"Pos 5 with 8 deaths in 50m should not be penalized: {res_p5_50m['weaknesses']}",
        )

        # Pos 1 in a 25-minute match with 8 deaths -> 3.2 deaths/10m (SHOULD trigger high-death penalty)
        p1 = copy.deepcopy(next(p for p in team if p["pos"] == 1))
        p1["deaths"] = 8
        p1["dead_seconds"] = 240
        res_p1_25m = ai_coach_engine.evaluate_player_deeply(
            copy.deepcopy(p1), team, enemy, won=False, duration_min=25.0, is_parsed=True, is_turbo=False
        )
        self.assertTrue(
            any("高频阵亡" in w for w in res_p1_25m["weaknesses"]),
            f"Pos 1 with 8 deaths in 25m should be penalized: {res_p1_25m['weaknesses']}",
        )

    def test_4_zero_smokes_and_dusts_counted_by_team_not_individual(self):
        reports = list(build_all_sample_reports().values())
        rep = copy.deepcopy(reports[0])
        team = copy.deepcopy(rep["radiant_pos_1_to_5"])
        enemy = copy.deepcopy(rep["dire_pos_1_to_5"])
        enemy[0]["final_items"] = ["微光披风"]

        p5 = copy.deepcopy(next(p for p in team if p["pos"] == 5))
        p5["smokes_bought"] = 0
        p5["dusts_bought"] = 0
        # Team has 0 smokes and 0 dusts
        for tp in team:
            tp["smokes_bought"] = 0
            tp["dusts_bought"] = 0
        res_zero = ai_coach_engine.evaluate_player_deeply(
            copy.deepcopy(p5), team, enemy, won=False, duration_min=35.0, is_parsed=True, is_turbo=False
        )
        # Team has 3 smokes and 2 dusts bought by teammate (pos 4), while p5 has 0
        team_with_items = copy.deepcopy(team)
        for tp in team_with_items:
            if tp["pos"] == 4:
                tp["smokes_bought"] = 3
                tp["dusts_bought"] = 2
        res_teammate_bought = ai_coach_engine.evaluate_player_deeply(
            copy.deepcopy(p5), team_with_items, enemy, won=False, duration_min=35.0, is_parsed=True, is_turbo=False
        )
        # Individual blame points must not be penalized for 0 smokes / 0 dusts
        self.assertEqual(res_zero["raw_blame_points"], res_teammate_bought["raw_blame_points"])
        self.assertFalse(any("零买雾" in w or "零买粉" in w for w in res_teammate_bought["weaknesses"]))

    def test_5_bkb_timing_only_audits_cores(self):
        reports = list(build_all_sample_reports().values())
        rep = copy.deepcopy(reports[0])
        team = copy.deepcopy(rep["radiant_pos_1_to_5"])
        enemy = copy.deepcopy(rep["dire_pos_1_to_5"])
        for ep in enemy:
            ep["stuns_sec"] = 25.0

        p5 = copy.deepcopy(next(p for p in team if p["pos"] == 5))
        p5["key_item_timings_rich"] = [{"key": "black_king_bar", "time_sec": 2100, "time_str": "35:00"}]
        p5["active_item_uses"] = {"black_king_bar": {"count": 0}}
        res_p5 = ai_coach_engine.evaluate_player_deeply(
            copy.deepcopy(p5), team, enemy, won=False, duration_min=42.0, is_parsed=True, is_turbo=False
        )
        for w in res_p5["weaknesses"]:
            self.assertNotIn("BKB 严重难产", w)
            self.assertNotIn("BKB 沦为摆设", w)

    def test_6_first_death_in_teamfight_neutral_wording(self):
        for mid, rep in build_all_sample_reports().items():
            for path, s in iter_report_strings(rep):
                self.assertNotIn("导致正面瞬间陷入 4打5", s, f"Match {mid} {path}")
                self.assertNotIn("导致 4 打 5", s, f"Match {mid} {path}")

    def test_7_winning_team_never_labeled_lying_win(self):
        for mid, rep in build_all_sample_reports().items():
            rad_win = bool(rep.get("radiant_win"))
            win_players = rep["radiant_pos_1_to_5"] if rad_win else rep["dire_pos_1_to_5"]
            for p in win_players:
                self.assertNotIn("躺赢", str(p.get("rating_tier") or ""))
                self.assertNotIn("躺赢", str(p.get("contrib_tier") or ""))
                self.assertNotIn("躺赢", str(p.get("praise_talk") or ""))
            win_side = "radiant" if rad_win else "dire"
            mc = ai_coach_engine.select_match_mvp_and_culprit(
                rep["radiant_pos_1_to_5"], rep["dire_pos_1_to_5"], rad_win, win_side
            )
            self.assertNotIn("躺赢", str(mc["culprit_player"].get("verdict") or ""))
            self.assertNotIn("躺赢", str(mc["culprit_player"].get("contrib_tier") or ""))


if __name__ == "__main__":
    unittest.main()
