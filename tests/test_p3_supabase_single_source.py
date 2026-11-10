import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cloud_store
import dota_analyst
import draft_and_phase_coach
import server
from tests.helpers import build_all_sample_reports, load_all_raw_matches

ROOT_DIR = Path(__file__).resolve().parent.parent


class TestP3SupabaseSingleSource(unittest.TestCase):
    """P3 · Supabase 作为唯一数据源：删掉 GitHub 存储分支、match_players 表、raw JSON 存 Storage、vercel.json 去掉 reports/**、tests/fixtures 样本、engine_version 旧版自动重算、无本地 reports/ 目录正常运行"""

    @classmethod
    def setUpClass(cls):
        cls.sample_reports = build_all_sample_reports(force_rebuild=True)

    def test_1_github_storage_branch_deleted_from_cloud_store(self):
        """cloud_store.py 删除 GitHub 存储分支，只保留 Supabase"""
        src = (ROOT_DIR / "cloud_store.py").read_text(encoding="utf-8")
        self.assertNotIn("api.github.com", src)
        self.assertNotIn("_github_save_file", src)
        self.assertNotIn("_github_fetch_json_file", src)
        self.assertNotIn("_github_list_analyzed_ids", src)
        status = cloud_store.get_cloud_db_status_safe()
        self.assertNotIn("has_github", status)

    def test_2_supabase_schema_and_match_players_sync(self):
        """supabase_schema.sql 包含 match_players 表，且 cloud_save_match_report 同步写入 match_players 与 dota_match_reports"""
        schema_sql = (ROOT_DIR / "supabase_schema.sql").read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS public.match_players", schema_sql)
        self.assertIn("engine_version", schema_sql)

        rep = next(iter(self.sample_reports.values()))
        rows = cloud_store.extract_match_players_rows(rep)
        self.assertEqual(len(rows), 10)
        for r in rows:
            self.assertIn("match_id", r)
            self.assertIn("account_id", r)
            self.assertIn("hero_id", r)
            self.assertIn("pos", r)
            self.assertIn("won", r)

    def test_3_raw_match_storage_and_migration_script(self):
        """原始比赛 JSON 支持读写 Supabase Storage，且提供迁移脚本 tools/migrate_reports_to_supabase.py"""
        self.assertTrue(hasattr(cloud_store, "cloud_save_raw_match"))
        self.assertTrue(hasattr(cloud_store, "cloud_fetch_raw_match"))
        mig_path = ROOT_DIR / "tools" / "migrate_reports_to_supabase.py"
        self.assertTrue(mig_path.exists(), "tools/migrate_reports_to_supabase.py must exist")

    def test_4_vercel_json_excludes_reports_and_fixtures_present(self):
        """vercel.json 的 includeFiles 去掉 reports/**，且 tests/fixtures/ 留有 5-6 份原始样本"""
        vercel_cfg = json.loads((ROOT_DIR / "vercel.json").read_text(encoding="utf-8"))
        inc = vercel_cfg.get("functions", {}).get("api/index.py", {}).get("includeFiles", "")
        self.assertNotIn("reports/**", inc)
        fixtures_dir = ROOT_DIR / "tests" / "fixtures"
        self.assertTrue(fixtures_dir.exists())
        raw_fixtures = list(fixtures_dir.glob("raw_*.json"))
        self.assertGreaterEqual(len(raw_fixtures), 5)

    def test_5_engine_version_triggers_rebuild_when_stale_and_works_without_local_reports_dir(self):
        """报告带 engine_version 字段，旧版本自动重算；删掉/置空本地 reports/ 后站点功能正常"""
        rep = next(iter(self.sample_reports.values()))
        self.assertEqual(rep.get("engine_version"), dota_analyst.ENGINE_VERSION)

        raw_map = load_all_raw_matches()
        sample_mid = 9046276667
        raw_match = raw_map[sample_mid]

        with tempfile.TemporaryDirectory() as empty_reports_dir, tempfile.TemporaryDirectory() as tmp_cache_dir:
            empty_path = Path(empty_reports_dir)
            tmp_path = Path(tmp_cache_dir)
            # Write an old-version report into tmp_cache_dir
            stale_rep = dict(self.sample_reports[sample_mid])
            stale_rep["engine_version"] = "legacy_v0"
            stale_rep["sentinel_old"] = True
            (tmp_path / f"match_{sample_mid}.json").write_text(
                json.dumps(stale_rep, ensure_ascii=False), encoding="utf-8"
            )

            with patch.object(server, "REPORTS_DIR", empty_path), \
                 patch.object(server, "TMP_REPORTS_DIR", tmp_path), \
                 patch.object(cloud_store, "cloud_fetch_match_report", return_value=stale_rep), \
                 patch.object(cloud_store, "cloud_fetch_raw_match", return_value=raw_match), \
                 patch.object(cloud_store, "cloud_save_match_report", return_value=True):
                rebuilt = server.get_or_build_match_report(sample_mid, allow_build=True)
                self.assertIsNotNone(rebuilt)
                self.assertEqual(rebuilt.get("engine_version"), dota_analyst.ENGINE_VERSION)
                self.assertNotIn("sentinel_old", rebuilt)

                # Squad ledger also works when REPORTS_DIR is empty
                ledger = draft_and_phase_coach.load_or_build_squad_ledger(empty_path, dota_analyst.load_roster(), [])
                self.assertIsInstance(ledger, dict)


if __name__ == "__main__":
    unittest.main()
