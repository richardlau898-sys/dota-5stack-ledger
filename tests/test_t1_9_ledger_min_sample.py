import inspect
import pathlib
import unittest

import dota_analyst
import draft_and_phase_coach


class TestT19LedgerMinSample(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reports_dir = pathlib.Path(__file__).resolve().parent.parent / "reports"
        cls.roster = dota_analyst.load_roster()
        cls.ledger = draft_and_phase_coach.build_squad_history_ledger(
            cls.reports_dir, cls.roster, recent_matches=[]
        )

    def test_1_heroes_and_positions_under_10_games_no_advice_ban_or_disaster(self):
        members = self.ledger.get("squad_members_rank") or []
        self.assertTrue(len(members) > 0)
        for m in members:
            g = int(m.get("games") or 0)
            hd = m.get("habit_diagnosis") or {}
            pos_verdict = str(hd.get("pos_verdict") or "")
            bp_mandate = str(hd.get("bp_and_team_mandate") or "")

            # Any cursed_heroes or signature_heroes entry must have >= 10 games
            for ch in m.get("cursed_heroes") or []:
                self.assertGreaterEqual(
                    int(ch.get("games") or 0),
                    10,
                    f"Cursed hero with <10 games should not be flagged: {ch}",
                )
            for sh in m.get("signature_heroes") or []:
                self.assertGreaterEqual(
                    int(sh.get("games") or 0),
                    10,
                    f"Signature hero with <10 games should not be evaluated: {sh}",
                )

            if m.get("worst_pos"):
                self.assertGreaterEqual(
                    int(m["worst_pos"].get("games") or 0),
                    10,
                    f"worst_pos with <10 games should not be flagged: {m['worst_pos']}",
                )

            # For members with < 10 games, must show 样本不足 and never 建议/禁选/重灾
            if g < 10:
                self.assertIn("样本不足", pos_verdict + " " + bp_mandate)
                for forbidden in ("建议", "禁选", "重灾"):
                    self.assertNotIn(forbidden, pos_verdict, f"Member {m['personaname']} ({g} games) pos_verdict")
                    self.assertNotIn(forbidden, bp_mandate, f"Member {m['personaname']} ({g} games) bp_mandate")

            # For members with < 20 games, must never output 建议 or 禁选 or 重灾
            if g < 20:
                for forbidden in ("建议", "禁选", "重灾"):
                    self.assertNotIn(forbidden, pos_verdict, f"Member {m['personaname']} ({g} games) pos_verdict")
                    self.assertNotIn(forbidden, bp_mandate, f"Member {m['personaname']} ({g} games) bp_mandate")

            # Check pos_breakdown entries with 1-9 games
            for pb in m.get("pos_breakdown") or []:
                if int(pb.get("games") or 0) < 10:
                    self.assertEqual(pb.get("sample_status"), "样本不足")
                self.assertIn("局", str(pb.get("win_rate_zh") or ""))

        for duo in self.ledger.get("lane_duo_chemistry") or []:
            dg = int(duo.get("games") or 0)
            tag = str(duo.get("chemistry_tag") or "")
            if dg < 10:
                self.assertIn("样本不足", tag)
            if dg < 20:
                self.assertNotIn("建议", tag)

    def test_2_no_llm_keyword_matching_in_support_grief_or_lane_loss(self):
        src = inspect.getsource(draft_and_phase_coach.build_squad_history_ledger)
        self.assertNotIn("grief_kws", src)
        self.assertNotIn("散失", src)
        self.assertNotIn("抢经济", src)
        self.assertNotIn("early_txt", src)

    def test_3_records_use_per_game_averages_not_cumulative_totals(self):
        for rec in self.ledger.get("guinness_records") or []:
            val = str(rec.get("value") or "")
            self.assertIn("场均", val, f"Guinness record must use per-game average: {rec}")
            self.assertNotIn("累计", val, f"Guinness record must not use cumulative total: {rec}")
        for m in self.ledger.get("squad_members_rank") or []:
            flaws = str((m.get("habit_diagnosis") or {}).get("habit_flaws_summary") or "")
            self.assertNotIn("累计", flaws, f"Flaw summary must use per-game average: {flaws}")

    def test_4_no_hardcoded_pos3_initiator_default_role_tag(self):
        src = inspect.getsource(draft_and_phase_coach.build_squad_history_ledger)
        self.assertNotIn("三号位开团中坚", src)
        for m in self.ledger.get("squad_members_rank") or []:
            self.assertNotIn("三号位开团中坚", str(m.get("role_tag") or ""))


if __name__ == "__main__":
    unittest.main()
