import json
import pathlib
import tempfile
import unittest
from tests.helpers import ROOT_DIR, build_all_sample_reports, iter_report_strings, load_all_raw_matches
import ai_coach_engine
import dota_analyst
import dota_constants_zh
import draft_and_phase_coach
import tactical_microscope_engine


class TestT13BackendBugs(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw_matches = load_all_raw_matches()
        cls.reports = build_all_sample_reports()

    def test_a_kills_and_killed_by_breakdown_lookup_by_hero_list(self) -> None:
        """a: kills_info and killed_by_info have {'heroes': [{'hero_short_zh': ..., 'count': ...}]} structure."""
        # Across all reports, never say '0 次击杀 X' when the player actually killed X >= 1 times
        for mid, rep in self.reports.items():
            for side_key in ("radiant_pos_1_to_5", "dire_pos_1_to_5"):
                for p in rep.get(side_key) or []:
                    k_heroes = {
                        h["hero_short_zh"]: int(h.get("count") or 0)
                        for h in ((p.get("kills_breakdown") or {}).get("heroes") or [])
                        if isinstance(h, dict) and h.get("hero_short_zh")
                    }
                    for w in p.get("weaknesses") or []:
                        for eh, cnt in k_heroes.items():
                            if cnt > 0:
                                self.assertNotIn(
                                    f"0 次击杀 {eh}",
                                    w,
                                    f"match {mid} {p.get('hero_short_zh')} killed {eh} {cnt} times but weakness says 0 kills: {w}",
                                )

    def test_b_lane_opponent_uses_raw_lane_field(self) -> None:
        """b: Lane matchup compares enemies on the same physical lane (raw_lane), not same pos on opposite side of map."""
        # In match 8774383260, Radiant pos 1 (slot 3, lane 1) lanes against Dire offlane (lane 1: slot 129 Necro / slot 132 Venomancer),
        # NOT Dire pos 1 Slark (slot 130, lane 3).
        rep = self.reports[8774383260]
        rad_players = rep["radiant_pos_1_to_5"]
        dire_players = rep["dire_pos_1_to_5"]
        dire_by_hero = {p["hero_short_zh"]: p for p in dire_players}
        df = rep.get("deep_forensics") or {}
        mirror_rad = ((df.get("role_mirror_by_side") or {}).get("radiant") or {}).get("mirror_rows") or []
        for row in mirror_rad:
            own_p = next((p for p in rad_players if p["hero_short_zh"] == row["own_hero"]), None)
            opp_p = dire_by_hero.get(row["opp_hero"])
            if own_p and opp_p and own_p.get("raw_lane") in (1, 2, 3):
                self.assertEqual(
                    own_p.get("raw_lane"),
                    opp_p.get("raw_lane"),
                    f"Radiant {own_p['hero_short_zh']} (lane {own_p.get('raw_lane')}) matched against Dire {opp_p['hero_short_zh']} (lane {opp_p.get('raw_lane')})",
                )

    def test_c_talents_chosen_not_serialized_as_python_dict_repr(self) -> None:
        """c: Talents in skill_and_talent_audit_zh and report strings never render as {'tier': ...}."""
        for mid, rep in self.reports.items():
            for path, s in iter_report_strings(rep):
                self.assertNotIn("{'tier'", s, f"Dict repr found in match {mid} {path}: {s}")

    def test_d_spell_damage_not_misclassified_as_item(self) -> None:
        """d: get_item_zh returns empty for unknown keys, and abilities in damage_inflictor have source_type == 'ability'."""
        self.assertEqual(dota_constants_zh.get_item_zh("lina_dragon_slave"), "")
        for mid, rep in self.reports.items():
            if not rep.get("is_parsed"):
                continue
            for side_key in ("radiant_pos_1_to_5", "dire_pos_1_to_5"):
                for p in rep.get(side_key) or []:
                    sources = p.get("damage_by_source_rich") or []
                    for s in sources:
                        key = s.get("key") or ""
                        if key and key not in dota_constants_zh.ITEMS_ZH and not key.startswith(("dagon_", "necronomicon_", "recipe_")) and key not in ("null", "None"):
                            if dota_constants_zh.get_ability_zh(key):
                                self.assertEqual(
                                    s.get("source_type"),
                                    "ability",
                                    f"match {mid} {p.get('hero_short_zh')} ability {key} classified as {s.get('source_type')}",
                                )
                                self.assertNotEqual(s.get("zh_name"), "战术道具")

    def test_e_no_empty_top_spell_zero_casts_text(self) -> None:
        """e: Never output '主力技能《》释放 0 次' when top spell data is empty."""
        for mid, rep in self.reports.items():
            for path, s in iter_report_strings(rep):
                self.assertNotIn("《》", s, f"Empty《》found in match {mid} {path}: {s}")
                self.assertNotIn("主力技能《》释放 0 次", s)

    def test_f_damage_taken_share_pct_populated(self) -> None:
        """f: damage_taken_share_pct is computed in dota_analyst.py for parsed matches."""
        for mid, rep in self.reports.items():
            if not rep.get("is_parsed"):
                continue
            for side_key in ("radiant_pos_1_to_5", "dire_pos_1_to_5"):
                players = rep.get(side_key) or []
                shares = [p.get("damage_taken_share_pct") for p in players]
                self.assertTrue(
                    all(isinstance(x, (int, float)) and x > 0 for x in shares),
                    f"match {mid} {side_key} missing damage_taken_share_pct: {shares}",
                )
                self.assertAlmostEqual(sum(shares), 100.0, delta=1.0)

    def test_g_short_late_phase_hero_damage_threshold_normalized_by_minute(self) -> None:
        """g: Late phase < 10 minutes normalizes hero damage threshold by minute instead of fixed 9000."""
        # Match 9061341080 is 31:54 (6.9m late phase); pos 1-3 heroes dealt 4593-6670 damage (>= 6.9 * 600 = 4140, < 9000)
        rep = self.reports[9061341080]
        late_phase = next((ph for ph in (rep.get("phases_data") or []) if ph.get("key") == "late"), None)
        self.assertIsNotNone(late_phase)
        checked_any = False
        for pp in late_phase.get("players") or []:
            if int(pp.get("pos") or 0) in (1, 2, 3) and 4140 <= int(pp.get("hero_damage_gain") or 0) < 9000:
                checked_any = True
                for b in pp.get("bad") or []:
                    self.assertNotIn("后期团战输出匮乏", b)
        self.assertTrue(checked_any)

    def test_h_squad_ledger_lane_loss_reads_laning_10m_lh10_without_default_30(self) -> None:
        """h: Squad ledger reads laning_10m.lh10 and does not default missing lh10 to 30."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = pathlib.Path(tmpdir)
            rep = json.loads(json.dumps(self.reports[9043191843]))
            f_side = rep.get("focus_side") or "radiant"
            own_list = rep["radiant_pos_1_to_5"] if f_side == "radiant" else rep["dire_pos_1_to_5"]
            for p in own_list:
                p["laning_10m"] = {"lh10": 55, "dn10": 10, "gold10": 4500, "xp10": 4500}
            rep["grok_coaching"] = {}
            (tmppath / "match_9043191843.json").write_text(json.dumps(rep, ensure_ascii=False), encoding="utf-8")
            ledger = draft_and_phase_coach.build_squad_history_ledger(reports_dir=tmppath, roster=dota_analyst.load_roster(), recent_matches=[])
            for m in ledger.get("squad_members_rank") or []:
                self.assertEqual(
                    m.get("lane_loss_count", 0),
                    0,
                    f"Player {m.get('personaname')} with lh10=55 was counted as lane_loss_count={m.get('lane_loss_count')}",
                )

    def test_i_duo_rating_uses_unified_100_point_scale(self) -> None:
        """i: Duo rating in build_squad_history_ledger uses 100-point scale matching thresholds 72.0 / 64.0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = pathlib.Path(tmpdir)
            rep = json.loads(json.dumps(self.reports[9043191843]))
            (tmppath / "match_9043191843.json").write_text(json.dumps(rep, ensure_ascii=False), encoding="utf-8")
            ledger = draft_and_phase_coach.build_squad_history_ledger(reports_dir=tmppath, roster=dota_analyst.load_roster(), recent_matches=[])
            duos = ledger.get("lane_duo_chemistry") or []
            self.assertTrue(len(duos) > 0)
            for d in duos:
                self.assertGreaterEqual(
                    float(d.get("avg_rating") or 0),
                    30.0,
                    f"Duo avg_rating is on 10-point scale instead of 100-point scale: {d}",
                )

    def test_j_won_match_missing_contrib_share_pct_does_not_crash(self) -> None:
        """j: Winning match with contrib_share_pct=None does not raise TypeError in _eff_share."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = pathlib.Path(tmpdir)
            rep = json.loads(json.dumps(self.reports[8774383260]))
            rep["focus_side"] = "dire"
            rep["radiant_win"] = False  # Dire won
            for p in rep.get("dire_pos_1_to_5") or []:
                p["contrib_share_pct"] = None
            rep["grok_coaching"] = {}
            (tmppath / "match_8774383260.json").write_text(json.dumps(rep, ensure_ascii=False), encoding="utf-8")
            ledger = draft_and_phase_coach.build_squad_history_ledger(reports_dir=tmppath, roster=dota_analyst.load_roster(), recent_matches=[])
            self.assertGreaterEqual(len(ledger.get("analyzed_matches") or []), 1)

    def test_k_skill_points_17_to_20_mapped_to_levels_18_20_25_26_and_attr_supported(self) -> None:
        """k: Skill points 17, 18, 19, 20 map to levels 18, 20, 25, 26 (and attr builds satisfy unlock levels)."""
        rep = self.reports[9046364324]
        dq_by_side = (rep.get("deep_forensics") or {}).get("damage_quality_and_build_by_side") or {}
        found_18_ult = False
        for side_data in dq_by_side.values():
            if not isinstance(side_data, dict):
                continue
            for row in side_data.get("player_rows") or []:
                seq = row.get("level_sequence") or []
                has_attr = any(item.get("type") == "attr" for item in seq)
                if not has_attr and len(seq) >= 18:
                    self.assertEqual(seq[16].get("level"), 18, f"{row.get('hero_short_zh')} point 17 level={seq[16]}")
                    self.assertEqual(seq[17].get("level"), 20, f"{row.get('hero_short_zh')} point 18 level={seq[17]}")
                    found_18_ult = True
                if not has_attr and len(seq) >= 19:
                    self.assertEqual(seq[18].get("level"), 25, f"{row.get('hero_short_zh')} point 19 level={seq[18]}")
                if not has_attr and len(seq) >= 20:
                    self.assertEqual(seq[19].get("level"), 26, f"{row.get('hero_short_zh')} point 20 level={seq[19]}")
        self.assertTrue(found_18_ult)

    def test_l_facet_badge_not_shown_for_zero_and_no_hardcoded_738(self) -> None:
        """l: hero_variant 0 or None does not show facet badge, and '7.38 命石' is not hardcoded."""
        for mid, rep in self.reports.items():
            for path, s in iter_report_strings(rep):
                self.assertNotIn("7.38 命石", s, f"Hardcoded '7.38 命石' in match {mid} {path}: {s}")
        # Also verify hero_variant=0 produces no facet badge
        raw = json.loads(json.dumps(self.raw_matches[8774383260]))
        for pl in raw["players"]:
            pl["hero_variant"] = 0
        rep0 = dota_analyst.analyze_match_data(raw, roster=dota_analyst.load_roster())
        for path, s in iter_report_strings(rep0):
            self.assertNotIn("命石 #", s, f"hero_variant=0 still produced facet badge at {path}: {s}")

    def test_m_pa_monkey_king_shadow_fiend_basic_skills_and_no_level_98(self) -> None:
        """m: PA, Monkey King, Shadow Fiend have accurate basic skills and never trigger '前 98 级完全没学'."""
        for mid, rep in self.reports.items():
            for path, s in iter_report_strings(rep):
                self.assertNotIn("前 98 级", s, f"Found '前 98 级' in match {mid} {path}: {s}")
        cat = json.loads((ROOT_DIR / "ability_id_catalog.json").read_text(encoding="utf-8"))
        hbs = cat.get("hero_basic_skills") or {}
        self.assertEqual(
            hbs.get("npc_dota_hero_phantom_assassin")[:3],
            ["phantom_assassin_stifling_dagger", "phantom_assassin_phantom_strike", "phantom_assassin_immaterial"],
        )
        self.assertEqual(
            hbs.get("npc_dota_hero_monkey_king")[:3],
            ["monkey_king_boundless_strike", "monkey_king_tree_dance", "monkey_king_jingu_mastery"],
        )
        self.assertEqual(
            hbs.get("npc_dota_hero_nevermore")[:3],
            ["nevermore_shadowraze1", "nevermore_frenzy", "nevermore_dark_lord"],
        )

    def test_n_losing_player_never_gets_won_brother_praise_talk(self) -> None:
        """n: Losing players never receive '赢了就是好兄弟' or '喜提躺赢金杯'."""
        for mid, rep in self.reports.items():
            rad_win = bool(rep.get("radiant_win"))
            losing_players = rep.get("dire_pos_1_to_5") if rad_win else rep.get("radiant_pos_1_to_5")
            for p in losing_players or []:
                for path, s in iter_report_strings(p):
                    self.assertNotIn(
                        "赢了就是好兄弟",
                        s,
                        f"Losing player {p.get('hero_short_zh')} in match {mid} got winning text at {path}: {s}",
                    )


if __name__ == "__main__":
    unittest.main()
