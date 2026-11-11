import os
import unittest

from tests.helpers import build_all_sample_reports

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VALID_EVIDENCE_TYPES = {"measured", "inferred", "template"}


class TestT110EvidenceTags(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sample_reports = build_all_sample_reports()

    def test_1_every_section_has_conclusion_objects_with_evidence(self):
        """测试断言每个分节的结论对象都有 evidence 字段，取值在 measured / inferred / template 之中"""
        self.assertGreater(len(self.sample_reports), 0)
        for mid, report in self.sample_reports.items():
            with self.subTest(match_id=mid):
                # 1. radiant_pos_1_to_5 & dire_pos_1_to_5
                for side_key in ("radiant_pos_1_to_5", "dire_pos_1_to_5"):
                    players = report.get(side_key) or []
                    self.assertEqual(len(players), 5)
                    for p in players:
                        self.assertIn(p.get("evidence"), VALID_EVIDENCE_TYPES, f"Player missing evidence in {side_key}")
                        coaching = p.get("coaching") or {}
                        self.assertIn(coaching.get("evidence"), VALID_EVIDENCE_TYPES)
                        conclusions = coaching.get("conclusions") if isinstance(coaching.get("conclusions"), list) else p.get("conclusions")
                        self.assertIsInstance(conclusions, list, f"Player missing conclusions list in {side_key}")
                        for c in conclusions:
                            self.assertIn(c.get("evidence"), VALID_EVIDENCE_TYPES, f"Invalid evidence on {c}")
                            txt = str(c.get("text") or "")
                            if "推断" in txt or "疑似" in txt:
                                self.assertEqual(c.get("evidence"), "inferred")
                        dossier = coaching.get("hero_matchup_dossier") or p.get("hero_matchup_dossier")
                        if isinstance(dossier, dict):
                            self.assertEqual(dossier.get("evidence"), "template")

                # 2. mvp section
                mvp_sec = report.get("mvp") or {}
                self.assertIn(mvp_sec.get("evidence"), VALID_EVIDENCE_TYPES)
                if isinstance(mvp_sec.get("mvp"), dict):
                    self.assertIn(mvp_sec["mvp"].get("evidence"), VALID_EVIDENCE_TYPES)
                if isinstance(mvp_sec.get("culprit"), dict):
                    self.assertIn(mvp_sec["culprit"].get("evidence"), VALID_EVIDENCE_TYPES)
                mvp_conclusions = mvp_sec.get("conclusions")
                self.assertIsInstance(mvp_conclusions, list)
                if report.get("is_parsed"):
                    self.assertGreater(len(mvp_conclusions), 0)
                for c in mvp_conclusions:
                    self.assertIn(c.get("evidence"), VALID_EVIDENCE_TYPES)

                # 3. match_narrative section
                narrative = report.get("match_narrative") or {}
                self.assertIn(narrative.get("evidence"), VALID_EVIDENCE_TYPES)
                for stage in narrative.get("stages") or []:
                    if isinstance(stage, dict):
                        self.assertIn(stage.get("evidence"), VALID_EVIDENCE_TYPES)
                for c in narrative.get("conclusions") or []:
                    self.assertIn(c.get("evidence"), VALID_EVIDENCE_TYPES)

                # 4. phases_data section
                phases = report.get("phases_data")
                if isinstance(phases, list):
                    phase_iter = phases
                elif isinstance(phases, dict):
                    phase_iter = list(phases.values())
                else:
                    phase_iter = []
                self.assertGreater(len(phase_iter), 0)
                for ph in phase_iter:
                    if not isinstance(ph, dict):
                        continue
                    self.assertIn(ph.get("evidence"), VALID_EVIDENCE_TYPES)
                    for pp in ph.get("players") or []:
                        if isinstance(pp, dict):
                            self.assertIn(pp.get("evidence"), VALID_EVIDENCE_TYPES)
                            for c in pp.get("conclusions") or []:
                                self.assertIn(c.get("evidence"), VALID_EVIDENCE_TYPES)

                # 5. draft_analysis & draft_analysis_by_side
                for side_k, da in (report.get("draft_analysis_by_side") or {}).items():
                    if not isinstance(da, dict):
                        continue
                    self.assertIn(da.get("evidence"), VALID_EVIDENCE_TYPES, f"draft_analysis_by_side[{side_k}] missing evidence")
                    for c in da.get("conclusions") or []:
                        self.assertIn(c.get("evidence"), VALID_EVIDENCE_TYPES)
                    for list_key in ("combos", "counters", "lane_matchups", "ban_eval", "hero_matchup_matrix"):
                        for item in da.get(list_key) or []:
                            if isinstance(item, dict):
                                self.assertIn(
                                    item.get("evidence"),
                                    VALID_EVIDENCE_TYPES,
                                    f"draft_analysis[{side_k}][{list_key}] item missing evidence",
                                )

                # 6. deep_forensics (all 13 *_by_side sections)
                df = report.get("deep_forensics") or {}
                self.assertIn(df.get("evidence"), VALID_EVIDENCE_TYPES)
                by_side_keys = [k for k in df.keys() if k.endswith("_by_side")]
                self.assertGreaterEqual(len(by_side_keys), 13)
                for mod_key in by_side_keys:
                    mod_val = df.get(mod_key) or {}
                    for side_k in ("dire", "radiant"):
                        side_block = mod_val.get(side_k)
                        if isinstance(side_block, dict):
                            self.assertIn(
                                side_block.get("evidence"),
                                VALID_EVIDENCE_TYPES,
                                f"deep_forensics.{mod_key}.{side_k} missing evidence",
                            )
                            for c in side_block.get("conclusions") or []:
                                self.assertIn(c.get("evidence"), VALID_EVIDENCE_TYPES)
                        elif isinstance(side_block, list):
                            for elem in side_block:
                                if isinstance(elem, dict):
                                    self.assertIn(
                                        elem.get("evidence"),
                                        VALID_EVIDENCE_TYPES,
                                        f"deep_forensics.{mod_key}.{side_k} list item missing evidence",
                                    )

    def test_2_frontend_numeric_fallbacks_removed_and_evidence_ui_present(self):
        """清理前端的数字兜底，且前端给 inferred/template 加上小标记并默认只展开 measured"""
        app_js_path = os.path.join(REPO_ROOT, "static", "app.js")
        with open(app_js_path, "r", encoding="utf-8") as f:
            content = f.read()

        forbidden_fallbacks = [
            '"万古流芳 5"',
            "wl.win_rate ?? 50",
            "vis.avg_lifespan_sec ?? 280",
            "rm.won_overall_cnt ?? 3",
            "r.damage ?? r.fighting ?? 55",
            "r.farm ?? r.farming ?? 55",
            "r.damage ?? r.fighting ?? 60",
            "plan.overall_score || 78",
            'plan.grade || "A"',
        ]
        for pat in forbidden_fallbacks:
            self.assertNotIn(pat, content, f"Forbidden numeric/rank fallback still in app.js: {pat}")

        # Must have evidence badge helper and default-collapsed details for inferred/template
        self.assertIn("evidence-badge", content)
        self.assertIn("evidence-inferred", content)
        self.assertIn("evidence-template", content)
        self.assertIn("evidence-fold", content)


if __name__ == "__main__":
    unittest.main()
