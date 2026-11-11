# -*- coding: utf-8 -*-
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS_PATH = ROOT / "static" / "styles.css"


def _hex_to_rel_luminance(hex_str: str) -> float:
    h = hex_str.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    r, g, b = (int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))

    def _lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def _contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    l1 = _hex_to_rel_luminance(fg_hex)
    l2 = _hex_to_rel_luminance(bg_hex)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _parse_root_vars(css_text: str) -> dict:
    m = re.search(r":root\s*\{([^}]*)\}", css_text)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        vm = re.match(r"\s*(--[a-zA-Z0-9_-]+)\s*:\s*([^;]+);", line)
        if vm:
            out[vm.group(1)] = vm.group(2).strip()
    return out


class TestR42WarmPaletteContrast(unittest.TestCase):
    def test_1_grep_zero_ws_vars_and_cold_brand_colors(self):
        """R4-2: grep -rn '\\-\\-ws-\\|#7b87cf\\|123, 135, 207' static/ 必须无结果。"""
        proc = subprocess.run(
            ["grep", "-rn", r"\-\-ws-\|#7b87cf\|123, 135, 207", "static/"],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
        )
        self.assertEqual(
            proc.returncode,
            1,
            f"发现未清除的冷色变量或紫色品牌色:\n{proc.stdout}",
        )
        self.assertEqual(proc.stdout.strip(), "")

    def test_2_root_warm_palette_and_in_place_edit_not_appended(self):
        """R4-2: :root 新增 --line-soft: #2c2d2a 且移除全部 --ws-*；直接在原处替换而非末尾叠层。"""
        css_text = CSS_PATH.read_text(encoding="utf-8")
        root_vars = _parse_root_vars(css_text)
        self.assertEqual(root_vars.get("--line-soft"), "#2c2d2a")
        ws_keys = [k for k in root_vars if k.startswith("--ws-")]
        self.assertEqual(ws_keys, [], f":root 中仍残留 --ws-* 定义: {ws_keys}")

        cold_hex_leftovers = (
            "#5b67b2",
            "#8c98dc",
            "#8995db",
            "#e4e7ff",
            "#d2d8ff",
            "#d5dcfa",
            "#d6dcff",
        )
        for ch in cold_hex_leftovers:
            self.assertNotIn(
                ch,
                css_text.lower(),
                f"styles.css 中仍残留冷紫/蓝字面量颜色 {ch}",
            )

        # 删除 15 行 --ws-* 定义并原处替换，文件总行数应少于修改前的 10103 行
        self.assertLess(len(css_text.splitlines()), 10103)

    def test_3_wcag_contrast_text_and_muted_at_least_4_5(self):
        """R4-2: 正文文字 (--text, --muted) 与各层背景 (--bg, --panel, --panel-2, --panel-3) 对比度 >= 4.5:1。"""
        css_text = CSS_PATH.read_text(encoding="utf-8")
        root_vars = _parse_root_vars(css_text)
        fg_keys = ("--text", "--muted")
        bg_keys = ("--bg", "--panel", "--panel-2", "--panel-3")
        for fk in fg_keys:
            self.assertIn(fk, root_vars, f"缺少文字颜色变量 {fk}")
            for bk in bg_keys:
                self.assertIn(bk, root_vars, f"缺少背景颜色变量 {bk}")
                ratio = _contrast_ratio(root_vars[fk], root_vars[bk])
                self.assertGreaterEqual(
                    ratio,
                    4.5,
                    f"{fk} ({root_vars[fk]}) vs {bk} ({root_vars[bk]}) 对比度 {ratio:.2f}:1 < 4.5:1",
                )


if __name__ == "__main__":
    unittest.main()
