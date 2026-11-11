# -*- coding: utf-8 -*-
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import dota_analyst

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestR19EngineVersionCheck(unittest.TestCase):
    """R1-9 · 引擎版本号：更新 ENGINE_VERSION 并在 CI 检查分析文件改动是否同步更新版本号"""

    def test_ci_workflow_runs_check_engine_version(self):
        script_path = REPO_ROOT / "tools" / "check_engine_version.py"
        self.assertTrue(script_path.exists(), "缺少 tools/check_engine_version.py")

        ci_text = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("fetch-depth: 0", ci_text)
        self.assertIn("tools/check_engine_version.py", ci_text)
        self.assertNotEqual(dota_analyst.ENGINE_VERSION, "2026.11.r0.6")

    def test_warns_when_analysis_file_modified_without_engine_version_bump(self):
        script_path = REPO_ROOT / "tools" / "check_engine_version.py"
        self.assertTrue(script_path.exists(), "缺少 tools/check_engine_version.py")

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True)

            (repo / "dota_analyst.py").write_text('ENGINE_VERSION = "1.0.0"\n', encoding="utf-8")
            (repo / "microscope_sections").mkdir()
            (repo / "microscope_sections" / "space_damage_econ.py").write_text("X = 1\n", encoding="utf-8")
            (repo / "README.md").write_text("hello\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

            # Case 1: Modify analysis file WITHOUT bumping ENGINE_VERSION -> emits ::warning:: (and fails --strict)
            (repo / "microscope_sections" / "space_damage_econ.py").write_text("X = 2\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "change analysis"], cwd=repo, check=True, capture_output=True)

            warn_run = subprocess.run(
                [sys.executable, str(script_path), "--repo", str(repo), "--base", "HEAD~1", "--head", "HEAD"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(warn_run.returncode, 0, warn_run.stderr)
            self.assertIn("::warning", warn_run.stdout)
            self.assertIn("microscope_sections/space_damage_econ.py", warn_run.stdout)

            strict_run = subprocess.run(
                [sys.executable, str(script_path), "--repo", str(repo), "--base", "HEAD~1", "--head", "HEAD", "--strict"],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(strict_run.returncode, 0)

            # Case 2: Modify analysis file AND bump ENGINE_VERSION -> OK, no warning
            (repo / "dota_analyst.py").write_text('ENGINE_VERSION = "1.0.1"\n', encoding="utf-8")
            (repo / "microscope_sections" / "space_damage_econ.py").write_text("X = 3\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "bump version"], cwd=repo, check=True, capture_output=True)

            ok_run = subprocess.run(
                [sys.executable, str(script_path), "--repo", str(repo), "--base", "HEAD~1", "--head", "HEAD", "--strict"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(ok_run.returncode, 0, ok_run.stdout + ok_run.stderr)
            self.assertNotIn("::warning", ok_run.stdout)


if __name__ == "__main__":
    unittest.main()
