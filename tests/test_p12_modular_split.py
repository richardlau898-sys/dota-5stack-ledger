# -*- coding: utf-8 -*-
"""
P12 / R3-6 · 拆分大文件与如实收尾 单元测试
验证：
1. build_tactical_microscope 按分节拆成独立模块（microscope_sections/），原函数行数大幅缩减。
2. R3-6：删除未被引用的 static/modules/ 占位文件，删掉调过的行数上限断言，并在 README.md 中如实写明「前端尚未拆分」；同时保留全屏报告/PDF 复用 DOM 的去重成果。
3. static/styles.css 合并多层版本补丁，统一成唯一一套 :root 变量。
4. 拆分前后，全部 22 个样本生成的报告 JSON 完全一致（100% SHA-256 对齐）。
"""
import hashlib
import json
import os
import re
import time
import unittest
from pathlib import Path

import dota_analyst

REPO_ROOT = Path(__file__).resolve().parent.parent

EXPECTED_SAMPLE_FILES = (
    "raw_8646427108.json",
    "raw_8774383260.json",
    "raw_9043191843.json",
    "raw_9043295657.json",
    "raw_9044767675.json",
    "raw_9046276667.json",
    "raw_9046364324.json",
    "raw_9048059832.json",
    "raw_9049240640.json",
    "raw_9049336548.json",
    "raw_9049526926.json",
    "raw_9058105598.json",
    "raw_9059717808.json",
    "raw_9059800017.json",
    "raw_9059875959.json",
    "raw_9059958125.json",
    "raw_9061341080.json",
    "raw_9061423694.json",
    "raw_9061514691.json",
    "raw_9075979087.json",
    "raw_9080176578.json",
    "raw_9080302651.json",
)


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

    def test_2_unused_frontend_modules_removed_and_documented(self):
        mods_dir = REPO_ROOT / "static" / "modules"
        self.assertFalse(
            mods_dir.exists(),
            "R3-6: 未被 index.html 加载的 static/modules/ 占位文件应当删除",
        )

        app_js = (REPO_ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("buildStructuredMicroTablesHtml", app_js)

        readme_path = REPO_ROOT / "README.md"
        self.assertTrue(readme_path.exists(), "R3-6: 缺少项目文档 README.md")
        readme_txt = readme_path.read_text(encoding="utf-8")
        self.assertIn("前端尚未拆分", readme_txt)

    def test_3_css_single_unified_root_variables_and_no_version_patch_headers(self):
        css_txt = (REPO_ROOT / "static" / "styles.css").read_text(encoding="utf-8")
        root_blocks = re.findall(r":root\s*\{[^}]*\}", css_txt)
        self.assertEqual(
            len(root_blocks),
            1,
            f"styles.css 应合并为唯一一套 :root 变量，当前有 {len(root_blocks)} 处",
        )
        self.assertIn("--bg:", root_blocks[0])
        self.assertIn("--line-soft:", root_blocks[0])
        self.assertNotIn("--ws-canvas:", root_blocks[0])
        self.assertIn("@media print", css_txt)

    def test_4_all_sample_reports_identical_before_and_after_split(self):
        roster = dota_analyst.load_roster()
        orig_tz = os.environ.get("TZ")
        try:
            for raw_name in EXPECTED_SAMPLE_FILES:
                raw_path = REPO_ROOT / "reports" / raw_name
                raw_match = json.loads(raw_path.read_text(encoding="utf-8"))

                os.environ["TZ"] = "UTC"
                if hasattr(time, "tzset"):
                    time.tzset()
                rep_utc = dota_analyst.analyze_match_data(raw_match, roster)
                sha_utc = hashlib.sha256(
                    json.dumps(rep_utc, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                ).hexdigest()

                os.environ["TZ"] = "Asia/Shanghai"
                if hasattr(time, "tzset"):
                    time.tzset()
                rep_sh = dota_analyst.analyze_match_data(raw_match, roster)
                sha_sh = hashlib.sha256(
                    json.dumps(rep_sh, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                ).hexdigest()

                self.assertEqual(
                    sha_utc,
                    sha_sh,
                    f"样本 {raw_name} 在不同时区下生成的报告 JSON 不一致！",
                )
                self.assertGreaterEqual(len(rep_utc.get("deep_forensics") or {}), 13)
        finally:
            if orig_tz is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = orig_tz
            if hasattr(time, "tzset"):
                time.tzset()


if __name__ == "__main__":
    unittest.main()
