import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import ai_coach_engine
import dota_analyst
import dota_constants_zh


REPO_ROOT = Path(__file__).resolve().parent.parent


class TestR28ChineseAbilityNames(unittest.TestCase):
    def test_1_zero_zhuanshu_jineng_across_all_regenerated_sample_reports(self):
        """对全部样本重新生成报告，断言'专属技能'出现 0 次（JSON 与 Markdown 均 0 次）"""
        roster = dota_analyst.load_roster()
        raw_files = sorted((REPO_ROOT / "reports").glob("raw_*.json"))
        self.assertGreaterEqual(len(raw_files), 20)

        offending = []
        for rf in raw_files:
            raw = json.loads(rf.read_text(encoding="utf-8"))
            rep = dota_analyst.analyze_match_data(raw, roster)
            rep_json = json.dumps(rep, ensure_ascii=False)
            cnt_json = rep_json.count("专属技能")
            md = dota_analyst.render_markdown_report(rep)
            cnt_md = md.count("专属技能")
            if cnt_json or cnt_md:
                offending.append((rf.name, cnt_json, cnt_md))

        self.assertEqual(
            offending,
            [],
            f"Found '专属技能' in regenerated sample reports: {offending}",
        )

    def test_2_all_heroes_abilities_have_official_schinese_names_and_no_placeholder_fallback(self):
        """技能中文名从 OpenDota abilities/hero_abilities 常量与官方简体中文本地化生成，覆盖全部英雄，且无'专属技能'兜底"""
        ha_path = REPO_ROOT / ".cache" / "hero_abilities_constants.json"
        ab_zh_path = REPO_ROOT / ".cache" / "abilities_zh.json"
        self.assertTrue(ha_path.is_file(), f"Missing {ha_path}")
        self.assertTrue(ab_zh_path.is_file(), f"Missing {ab_zh_path}")

        hero_abilities = json.loads(ha_path.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(hero_abilities), 127)

        missing = []
        for npc, info in hero_abilities.items():
            for ab_key in (info.get("abilities") or []):
                if not isinstance(ab_key, str) or ab_key == "generic_hidden":
                    continue
                if ab_key in dota_constants_zh.IGNORED_SUB_OR_DUMMY_ABILITIES:
                    continue
                if "_empty" in ab_key or "_hidden" in ab_key:
                    continue
                zh = dota_constants_zh.get_ability_zh(ab_key)
                if not zh or "专属技能" in zh or not any("\u4e00" <= c <= "\u9fff" for c in zh):
                    missing.append((npc, ab_key, zh))

        self.assertEqual(
            missing,
            [],
            f"Hero abilities missing Chinese localization or hitting placeholder ({len(missing)}): {missing[:20]}",
        )

        # ability_id_catalog.json by_id must have 0 '专属技能'
        cat = json.loads((REPO_ROOT / "ability_id_catalog.json").read_text(encoding="utf-8"))
        cat_offenders = [
            (aid, entry.get("key"), entry.get("zh"))
            for aid, entry in (cat.get("by_id") or {}).items()
            if "专属技能" in str(entry.get("zh") or "")
        ]
        self.assertEqual(cat_offenders, [], f"ability_id_catalog.json contains 专属技能: {cat_offenders[:20]}")

        # Unknown ability must never synthesize 'XX专属技能'
        self.assertEqual(dota_constants_zh.get_ability_zh("antimage_nonexistent_future_skill_xyz"), "")

        # Static JS must not fallback to '专属技能'
        app_js = (REPO_ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("专属技能", app_js)

        # Offline --check mode passes and validates abilities localization
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "tools" / "refresh_constants.py"), "--check"],
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(proc.returncode, 0, f"STDOUT: {proc.stdout}\nSTDERR: {proc.stderr}")

    def test_3_no_paste_gemini_api_key_prompt(self):
        """ai_coach_engine.py 与前端不再出现'粘贴 Gemini API Key'或'请填入 Gemini API Key'"""
        engine_src = (REPO_ROOT / "ai_coach_engine.py").read_text(encoding="utf-8")
        self.assertNotIn("粘贴 Gemini API Key", engine_src)
        self.assertNotIn("请填入 Gemini API Key", engine_src)

        raw = json.loads((REPO_ROOT / "reports" / "raw_8774383260.json").read_text(encoding="utf-8"))
        rep = dota_analyst.analyze_match_data(raw, dota_analyst.load_roster())
        with patch.object(
            ai_coach_engine,
            "load_env_llm_config",
            return_value={"gemini_api_key": "", "xai_api_key": "", "base_url": "https://api.x.ai/v1"},
        ):
            res_strict = ai_coach_engine.call_nano_banana_poster_art(
                report=rep,
                engine_pref="nano_banana_strict",
                force=True,
            )
            self.assertFalse(res_strict["ok"])
            self.assertNotIn("粘贴", res_strict.get("error", ""))
            self.assertNotIn("输入框", res_strict.get("error", ""))

            res_auto = ai_coach_engine.call_nano_banana_poster_art(
                report=rep,
                engine_pref="auto",
                force=True,
            )
            self.assertFalse(res_auto["ok"])
            self.assertNotIn("填入", res_auto.get("error", ""))
            self.assertNotIn("粘贴", res_auto.get("error", ""))


if __name__ == "__main__":
    unittest.main()
