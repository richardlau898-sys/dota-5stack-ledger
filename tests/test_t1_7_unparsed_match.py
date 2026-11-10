import pathlib
import unittest
from tests.helpers import build_all_sample_reports, iter_report_strings


class TestT17UnparsedMatch(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.reports = build_all_sample_reports()
        cls.unparsed_report = cls.reports[8646427108]

    def test_1_unparsed_match_sections_return_available_false(self) -> None:
        """build_tactical_microscope and build_deep_replay_forensics return {'available': False} per section when match.version is missing."""
        df = self.unparsed_report.get("deep_forensics") or {}
        self.assertIs(df.get("available"), False)
        expected_sections = (
            "picks_order",
            "lane_matchups",
            "rubick_steal_ledger",
            "key_spell_targets",
            "courier_graveyard",
            "ping_pressure_rank",
            "focus_fire_matrix",
            "teamfight_forensics",
            "hero_execution_by_side",
            "itemization_audit_by_side",
            "damage_quality_and_build_by_side",
            "support_vision_by_side",
            "stacking_and_smoke_by_side",
            "laning_mechanics_by_side",
            "tp_rotation_by_side",
            "unpressed_saves_by_side",
            "map_space_by_side",
            "damage_received_by_side",
            "economy_and_pings_by_side",
            "role_mirror_by_side",
            "macro_objectives_by_side",
        )
        for sec in expected_sections:
            val = df.get(sec)
            self.assertIsInstance(val, dict, f"Section {sec} should be a dict with available=False, got {type(val)}")
            self.assertIs(val.get("available"), False, f"Section {sec} should have available=False, got {val}")

    def test_2_unparsed_match_phase_telemetry_no_fake_20_pct(self) -> None:
        """Unparsed match must not fill fake 20.0% into phase_telemetry share fields."""
        all_players = (self.unparsed_report.get("radiant_pos_1_to_5") or []) + (
            self.unparsed_report.get("dire_pos_1_to_5") or []
        )
        for p in all_players:
            pt = p.get("phase_telemetry") or {}
            for k in (
                "lane_hdmg_share_pct",
                "mid_gold_share_pct",
                "mid_hdmg_share_pct",
                "late_gold_share_pct",
                "late_hdmg_share_pct",
            ):
                self.assertIsNone(
                    pt.get(k),
                    f"Player {p.get('hero_short_zh')} {k} should be None when unparsed, got {pt.get(k)}",
                )

    def test_3_unparsed_match_no_zero_casts_or_zero_records_verdicts(self) -> None:
        """Unparsed match 8646427108 report must not contain '0 次', '为 0', '不开雾' verdicts."""
        import re
        pattern = re.compile(r"(?<!\d)(0\s*次|为\s*0|不开雾|0\s*根|0\s*颗)")
        violations = []
        for path, s in iter_report_strings(self.unparsed_report):
            m = pattern.search(s)
            if m:
                violations.append(f"{path} ({m.group(0)}): {s[:120]}")
        self.assertEqual(violations, [], f"Found forbidden 0-verdicts in unparsed match: {violations[:5]}")

    def test_4_frontend_displays_need_parse_replay_message(self) -> None:
        """Frontend static/app.js checks available===false and displays '需要先解析录像'."""
        app_js = (pathlib.Path(__file__).resolve().parent.parent / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("需要先解析录像", app_js)


if __name__ == "__main__":
    unittest.main()
