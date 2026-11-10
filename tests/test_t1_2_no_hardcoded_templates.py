# -*- coding: utf-8 -*-
"""
T1-2 验收测试：
1. 泄漏测试：对每份固定样本，取出不在本场 10 个英雄里的全部英雄中文名（长度 2 个字以上），
   断言它们不出现在玩家评语、阶段点评、团战点评的任何字符串里。
2. 模板时间字面量扫描：tools/lint_templates.py 扫描 .py 和 .js 里同时含中文和 \\d{1,2}:\\d{2} 字面量的字符串，发现即失败。
"""

import unittest
from dota_constants_zh import HEROES_ZH
from tests.helpers import build_all_sample_reports, iter_report_strings
from tools.lint_templates import scan_repo


# 静态物品名中包含英雄同名词汇的最小白名单（先知钟摆/先知钱袋为 Dota 2 中立道具/衍生品名称，主宰比赛/主宰后期为动词用法但我们也尽量避免）
ALLOWED_ITEM_SUBSTRINGS = {
    "先知": ("先知钟摆", "先知钱袋"),
}

# 排除非评语类的原始 BP 列表、玩家昵称、历史缓存 LLM 文本字段
EXCLUDED_PATH_KEYWORDS = (
    "picks_bans",
    "picks_order",
    "draft_order",
    "personaname",
    "grok_coaching",
)

EXTRA_HERO_ALIASES = {
    93: "小鱼人",
    97: "猛犸",
    14: "屠夫",
    68: "冰魂",
}


class TestT12NoHardcodedTemplates(unittest.TestCase):
    def test_no_11th_hero_leaks_in_reports(self):
        all_hero_names = set()
        for hid, (zh_name, _zh_short, _) in HEROES_ZH.items():
            if len(zh_name) >= 2:
                all_hero_names.add((hid, zh_name))
            if hid in EXTRA_HERO_ALIASES:
                all_hero_names.add((hid, EXTRA_HERO_ALIASES[hid]))

        reports = build_all_sample_reports()
        leaks = []

        for mid, rep in reports.items():
            match_hids = set()
            for side_key in ("radiant_pos_1_to_5", "dire_pos_1_to_5"):
                for p in rep.get(side_key, []):
                    if p.get("hero_id"):
                        match_hids.add(int(p["hero_id"]))
            if not match_hids:
                continue

            present_names = {name for hid, name in all_hero_names if hid in match_hids}
            absent_names = {
                name
                for hid, name in all_hero_names
                if hid not in match_hids and not any(name in pn for pn in present_names)
            }

            for path, val in iter_report_strings(rep):
                if any(kw in path for kw in EXCLUDED_PATH_KEYWORDS):
                    continue
                for name in absent_names:
                    if name not in val:
                        continue
                    cleaned = val
                    for allowed_sub in ALLOWED_ITEM_SUBSTRINGS.get(name, ()):
                        cleaned = cleaned.replace(allowed_sub, "")
                    if name in cleaned:
                        leaks.append(f"match={mid} path={path} leaked_hero={name!r} text={val[:120]!r}")

        self.assertEqual(
            leaks,
            [],
            f"Found {len(leaks)} 11th-hero name leaks across sample reports:\n" + "\n".join(leaks[:30]),
        )

    def test_lint_templates_no_hardcoded_timestamps(self):
        violations = scan_repo()
        self.assertEqual(
            violations,
            [],
            "Found hardcoded Chinese + MM:SS template literals:\n"
            + "\n".join(f"{r}:{ln}: {s}" for r, ln, s in violations[:30]),
        )


if __name__ == "__main__":
    unittest.main()
