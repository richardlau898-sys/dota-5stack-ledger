import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS_PATH = ROOT / "static" / "styles.css"
JS_PATH = ROOT / "static" / "app.js"
HTML_PATH = ROOT / "static" / "index.html"


class TestP11MobileResponsive(unittest.TestCase):
    def test_vh_before_dvh_fallback_order(self):
        """100vh must precede 100dvh in every CSS declaration block that specifies both."""
        css = CSS_PATH.read_text(encoding="utf-8")
        blocks_with_dvh = [
            m.group(0)
            for m in re.finditer(r"[^{}]+\{[^{}]*100dvh[^{}]*\}", css)
        ]
        self.assertGreaterEqual(len(blocks_with_dvh), 2)
        for block in blocks_with_dvh:
            idx_vh = block.find("100vh")
            idx_dvh = block.find("100dvh")
            self.assertNotEqual(
                idx_vh, -1, f"Block with 100dvh missing 100vh fallback:\n{block}"
            )
            self.assertLess(
                idx_vh,
                idx_dvh,
                f"100vh fallback must appear BEFORE 100dvh:\n{block}",
            )

    def test_no_inline_wide_minmax_in_app_js(self):
        """Inline minmax(420px, 1fr) or >350px in app.js must be removed."""
        js = JS_PATH.read_text(encoding="utf-8")
        self.assertNotIn("minmax(420px, 1fr)", js)
        wide_inline = re.findall(r"minmax\(\s*([4-9]\d\d)px", js)
        self.assertEqual(
            wide_inline,
            [],
            f"Found wide inline minmax in static/app.js: {wide_inline}",
        )

    def test_prose_font_size_at_least_12px(self):
        """Body and prose selectors must have font-size >= 12px."""
        css = CSS_PATH.read_text(encoding="utf-8")
        prose_selectors = [
            r"body\s*\{",
            r"\.phase-p-prose\s*\{",
            r"\.roadmap-stage-list\s*\{",
            r"\.stage-rank-desc\s*\{",
            r"\.micro-radar-desc\s*\{",
            r"\.phase-mid-pillar\s+p\s*\{",
            r"\.ward-summary-table\s*\{",
            r"\.verdict-item-timeline-row\s*\{",
            r"\.tf-p-spotlight-banner\s*\{",
            r"\.tf-p-kda-line\s*\{",
            r"\.sf-caster-line\s*\{",
            r"\.f-target-line\s*\{",
        ]
        for pat in prose_selectors:
            m = re.search(pat + r"([^{}]*)\}", css)
            self.assertIsNotNone(m, f"Selector {pat} not found in styles.css")
            body_text = m.group(1)
            fs_match = re.search(r"font-size:\s*(\d+(?:\.\d+)?)px", body_text)
            self.assertIsNotNone(fs_match, f"No font-size in {pat}")
            px = float(fs_match.group(1))
            self.assertGreaterEqual(
                px, 12.0, f"Selector {pat} has font-size {px}px < 12px"
            )

    def test_mobile_view_bar_actions_menu(self):
        """Grok, Share, and PDF buttons in the view bar are grouped inside a collapsible mobile menu."""
        html = HTML_PATH.read_text(encoding="utf-8")
        css = CSS_PATH.read_text(encoding="utf-8")

        self.assertIn('id="ws-mobile-actions-menu"', html)
        self.assertIn('id="btn-mobile-actions-toggle"', html)
        self.assertIn('id="ws-mobile-actions-drawer"', html)

        m = re.search(
            r'id="ws-mobile-actions-drawer"[^>]*>(.*?)</div>',
            html,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(m, "#ws-mobile-actions-drawer not found in index.html")
        drawer_html = m.group(1)
        for btn_id in ("btn-export-pdf", "btn-hero-share-link", "btn-trigger-grok"):
            self.assertIn(
                f'id="{btn_id}"',
                drawer_html,
                f"{btn_id} must be inside #ws-mobile-actions-drawer",
            )

        self.assertIn(".ws-mobile-actions-drawer", css)
        self.assertIn(".ws-mobile-actions-toggle", css)


if __name__ == "__main__":
    unittest.main()
