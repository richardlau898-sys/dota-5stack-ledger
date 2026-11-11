import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import dota_analyst
import dota_constants_zh
import hero_profiles_126


REPO_ROOT = Path(__file__).resolve().parent.parent


class TestP7ConstantsAndPatch(unittest.TestCase):
    def test_1_largo_has_zh_name_and_profile_and_abilities(self):
        """新英雄 Largo (id 155) 有中文名、英雄档案与技能中文名"""
        self.assertIn(155, dota_constants_zh.HEROES_ZH)
        short_zh, alias_zh, _ = dota_constants_zh.HEROES_ZH[155]
        self.assertTrue(any("\u4e00" <= c <= "\u9fff" for c in short_zh), f"Not Chinese: {short_zh}")
        self.assertNotIn("155", short_zh)
        self.assertEqual(dota_analyst.get_hero_name(155), f"{short_zh}({alias_zh})")
        self.assertIn(155, hero_profiles_126.HERO_PROFILES_126)

        for ab_key in (
            "largo_catchy_lick",
            "largo_frogstomp",
            "largo_croak_of_genius",
            "largo_amphibian_rhapsody",
        ):
            zh = dota_constants_zh.get_ability_zh(ab_key)
            self.assertTrue(zh, f"Missing ability zh for {ab_key}")
            self.assertNotIn("专属技能", zh, f"Generic fallback for {ab_key}: {zh}")

    def test_2_every_hero_in_constants_has_chinese_name_and_missing_items_covered(self):
        """常量表里的每个英雄都有中文名；3 个缺失物品有中文名；全部英雄基础技能不再落入'XX专属技能'"""
        by_id, _ = dota_analyst.get_hero_constants_map()
        self.assertGreaterEqual(len(by_id), 127)
        for hid, info in by_id.items():
            short_zh = info.get("short_zh") or ""
            self.assertTrue(
                any("\u4e00" <= c <= "\u9fff" for c in short_zh) and not short_zh.startswith("英雄#"),
                f"Hero {hid} lacks Chinese name: {info}",
            )

        for item_key in ("hydras_breath", "crellas_crozier", "specialists_array"):
            izh = dota_constants_zh.get_item_zh(item_key)
            self.assertTrue(
                izh and any("\u4e00" <= c <= "\u9fff" for c in izh),
                f"Item {item_key} lacks Chinese name: {izh!r}",
            )

        cat = json.loads((REPO_ROOT / "ability_id_catalog.json").read_text(encoding="utf-8"))
        hbs = cat.get("hero_basic_skills") or {}
        generic_fallbacks = []
        for npc, skills in hbs.items():
            for sk in skills:
                zh = dota_constants_zh.ABILITIES_ZH.get(sk) or dota_constants_zh.get_ability_zh(sk)
                if not zh or "专属技能" in zh:
                    generic_fallbacks.append((npc, sk, zh))
        self.assertEqual(
            generic_fallbacks,
            [],
            f"Found {len(generic_fallbacks)} hero basic skills falling back to '专属技能': {generic_fallbacks[:10]}",
        )

    def test_3_no_hardcoded_7_38_in_repo_and_patch_resolved_from_match_patch(self):
        """全仓库源码搜不到写死的 7.38；补丁号从 match.patch 解析"""
        target_str = "7." + "38"
        offenders = []
        for path in sorted(REPO_ROOT.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(REPO_ROOT).as_posix()
            if (
                rel.startswith(".git/")
                or rel.startswith("reports/")
                or rel.startswith("tests/")
                or rel.startswith(".cache/")
                or "__pycache__" in rel
            ):
                continue
            if path.suffix not in (".py", ".js", ".html", ".css", ".json", ".yml", ".yaml", ".sql"):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if target_str in text:
                offenders.append(rel)
        self.assertEqual(offenders, [], f"Hardcoded {target_str} found in files: {offenders}")

        self.assertEqual(dota_constants_zh.resolve_patch_name(57), target_str)
        self.assertEqual(dota_constants_zh.resolve_patch_name(58), "7.39")

    def test_4_refresh_constants_script_fetches_all_5_endpoints_and_check_mode_passes(self):
        """tools/refresh_constants.py 支持拉取 heroes/items/abilities/hero_abilities/patch 并通过 --check 校验"""
        script_path = REPO_ROOT / "tools" / "refresh_constants.py"
        self.assertTrue(script_path.exists(), "tools/refresh_constants.py does not exist")

        proc = subprocess.run(
            [sys.executable, str(script_path), "--check"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(proc.returncode, 0, f"STDOUT: {proc.stdout}\nSTDERR: {proc.stderr}")

        from tools import refresh_constants

        called_urls = []

        def fake_urlopen(req, timeout=20):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            called_urls.append(url)
            payload = {"1": {"id": 1, "name": "npc_dota_hero_antimage", "localized_name": "Anti-Mage"}}
            if url.endswith("/patch"):
                payload = [{"id": 57, "name": "7." + "38"}, {"id": 58, "name": "7.39"}]
            elif url.endswith("/heroStats"):
                payload = [{"id": 1, "name": "npc_dota_hero_antimage", "6_pick": 100, "6_win": 52, "pub_pick": 1000, "pub_win": 510}]
            resp = MagicMock()
            resp.read.return_value = json.dumps(payload).encode("utf-8")
            resp.__enter__.return_value = resp
            return resp

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                out = refresh_constants.refresh_all_constants(Path(tmpdir))
            for key in ("heroes", "items", "abilities", "hero_abilities", "patch"):
                self.assertIn(key, out)
                self.assertTrue((Path(tmpdir) / f"{key}_constants.json").exists())


if __name__ == "__main__":
    unittest.main()
