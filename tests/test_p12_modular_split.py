# -*- coding: utf-8 -*-
"""
P12 · 拆分大文件 单元测试
验证：
1. build_tactical_microscope 按分节拆成独立模块（microscope_sections/），原函数行数大幅缩减。
2. static/app.js 按"状态和接口、各标签页渲染、导出"拆成 ES 模块（static/modules/），且全屏报告和 PDF 改用打印样式复用页面 DOM，删掉冗余实现（缩减 >= 3,000 行）。
3. static/styles.css 合并多层版本补丁，统一成唯一一套 :root 变量。
4. 拆分前后，全部 22 个样本生成的报告 JSON 完全一致（100% SHA-256 对齐）。
"""
import hashlib
import json
import re
import unittest
from pathlib import Path

import dota_analyst

REPO_ROOT = Path(__file__).resolve().parent.parent

PRE_SPLIT_REPORT_SHA256 = {
    "raw_8646427108.json": "e3f68bc92f77c86497b6373a5be4cc84c319d01296e4f9c180faabd0e3658fd9",
    "raw_8774383260.json": "dfa532cc0ac44f43fc42b5cc2294ceca92a9f9efe9dc09b0e3b8125be20331d5",
    "raw_9043191843.json": "dc9c3797dedc08d32ff700ceaa919fa008c843b507e856eb97bb609aa2ff6822",
    "raw_9043295657.json": "52ed4bf9730e64714b8e2e679e6863a6a221c02b2d6a8976c62689d6f8fd32d7",
    "raw_9044767675.json": "e147d6d636f8a051d29aa87b60336dd1516436f48864c2326831a971d2915e41",
    "raw_9046276667.json": "9bc8fef710cf388ca6532118c2ac44541f1b72046276c5a5ebf6bdee5fcc52a2",
    "raw_9046364324.json": "e7f696930338637362f3404f7430968b765a913afe8521ed138676eb5c3ef887",
    "raw_9048059832.json": "4c359e319358ab888be105f680d28b46655a1a15d0dda0f9628bdf054a4e62d9",
    "raw_9049240640.json": "7804d9f60cccc9e714ab1b85b7c60629b991c99ff435a2d537f31dc82b7c7b17",
    "raw_9049336548.json": "7eee8b47fd11902312932ab4d689a7f9e18ddc2b154b9b1cc57afa08efcb0a64",
    "raw_9049526926.json": "8d715608f991252826e7329781400ae157e521b3093e284afecd97e4b1ba4837",
    "raw_9058105598.json": "4ac1f0a5eccba33813005976628c2ed7d8034f19df39e62623321a683da51d8e",
    "raw_9059717808.json": "b102383edb1fb5996e0b7feb5d8bbf20c302ec0c8e16108c0d3d0b518c87e8d0",
    "raw_9059800017.json": "9805024ad1eb6fd50e7ba38a7833fde1ddd3fd8d68ade77c2a4115be555ab60b",
    "raw_9059875959.json": "7657ebbb5afaae1aaea601fca62540c33c5d04541fffc399b2c03db79d84dea6",
    "raw_9059958125.json": "8d342ef3be2a8e18030946ac9956f315cf04befe4ae9a579736aa979da266b76",
    "raw_9061341080.json": "62876343f461f4cf9adbfb872c06d40f323c2d6cfd58f4017414e1816bf5fa02",
    "raw_9061423694.json": "0531a640aef94b2245ca3c859992760023da39d1331cae0c10cc6c706e20f85c",
    "raw_9061514691.json": "c2759eb9b9f3aa03a2052f16d69163a7604051a73b2764ee270b5951fd2d3053",
    "raw_9075979087.json": "c9ebe5a11acb8da88a6534dc7f21909a20855b3ea879ad86bbd25fa76185a8ea",
    "raw_9080176578.json": "de0b8bb1ee5cca5108b23160e7773ab16890a9751489e5300ab93378a6606f23",
    "raw_9080302651.json": "9a07baac96c73c50177c7669114c9a52f2229d4dde1f1a3083e74e613bd4ecb6",
}


class TestP12ModularSplit(unittest.TestCase):
    def test_1_tactical_microscope_split_into_section_modules(self):
        pkg_dir = REPO_ROOT / "microscope_sections"
        self.assertTrue(pkg_dir.is_dir(), "缺少 microscope_sections/ 独立分节模块目录")
        expected_modules = [
            "hero_execution.py",
            "vision_stack_smoke.py",
            "laning_tp_saves.py",
            "space_damage_econ.py",
            "snapshots_matchups_objectives.py",
            "itemization_and_quality.py",
        ]
        for mod_name in expected_modules:
            self.assertTrue((pkg_dir / mod_name).exists(), f"缺少分节模块 {mod_name}")

        engine_txt = (REPO_ROOT / "tactical_microscope_engine.py").read_text(encoding="utf-8")
        self.assertLess(
            len(engine_txt.splitlines()),
            600,
            "tactical_microscope_engine.py 拆分后应大幅缩减为轻量编排入口",
        )

    def test_2_frontend_split_into_es_modules_and_dom_reuse_print(self):
        mods_dir = REPO_ROOT / "static" / "modules"
        self.assertTrue(mods_dir.is_dir(), "缺少 static/modules/ ES 模块目录")
        for mod_name in ("state_api.js", "render_tabs.js", "export_report.js"):
            mod_path = mods_dir / mod_name
            self.assertTrue(mod_path.exists(), f"缺少 ES 模块 {mod_name}")
            self.assertIn("export ", mod_path.read_text(encoding="utf-8"))

        app_js = (REPO_ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("buildStructuredMicroTablesHtml", app_js)
        self.assertLess(
            len(app_js.splitlines()),
            18100,
            "static/app.js 删除另外两套全屏/PDF重复实现后应减少 >= 3000 行",
        )

    def test_3_css_single_unified_root_variables_and_no_version_patch_headers(self):
        css_txt = (REPO_ROOT / "static" / "styles.css").read_text(encoding="utf-8")
        root_blocks = re.findall(r":root\s*\{[^}]*\}", css_txt)
        self.assertEqual(
            len(root_blocks),
            1,
            f"styles.css 应合并为唯一一套 :root 变量，当前有 {len(root_blocks)} 处",
        )
        self.assertIn("--bg:", root_blocks[0])
        self.assertIn("--ws-canvas:", root_blocks[0])
        self.assertIn("@media print", css_txt)

    def test_4_all_sample_reports_identical_before_and_after_split(self):
        roster = dota_analyst.load_roster()
        for raw_name, expected_sha in PRE_SPLIT_REPORT_SHA256.items():
            raw_path = REPO_ROOT / "reports" / raw_name
            raw_match = json.loads(raw_path.read_text(encoding="utf-8"))
            rep = dota_analyst.analyze_match_data(raw_match, roster)
            payload = json.dumps(rep, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            actual_sha = hashlib.sha256(payload).hexdigest()
            self.assertEqual(
                actual_sha,
                expected_sha,
                f"样本 {raw_name} 拆分前后生成的报告 JSON 不一致！",
            )


if __name__ == "__main__":
    unittest.main()
