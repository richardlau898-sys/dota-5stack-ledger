# -*- coding: utf-8 -*-
import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS_PATH = ROOT / "static" / "styles.css"
HTML_PATH = ROOT / "static" / "index.html"
JS_PATH = ROOT / "static" / "app.js"
BASELINE_STYLES_LINES = 10090

# Emoji Unicode ranges (excluding geometric shapes like ◆ ▸ ◀ ● ■ ✕ ↗)
EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002705"
    "\U000026A0"
    "\U00002694"
    "\U00002696"
    "\U00002699"
    "\U000023F1"
    "\U000023E9"
    "\U000023EA"
    "]"
)


class TestR43DotaVisualLanguage(unittest.TestCase):
    def test_1_faction_colors_and_winloss_separation(self):
        """R4-3: :root 定义 --radiant: #92a525 与 --dire: #c23c2a；阵营一律绿/红，胜负一律金色/砖红不与阵营混用。"""
        css = CSS_PATH.read_text(encoding="utf-8")
        root_m = re.search(r":root\s*\{([^}]*)\}", css)
        self.assertIsNotNone(root_m)
        root_txt = root_m.group(1)
        self.assertIn("--radiant: #92a525;", root_txt)
        self.assertIn("--dire: #c23c2a;", root_txt)

        # Win classes must use gold, not green
        for win_sel in (
            r"\.result-pill\.win\s*\{([^}]*)\}",
            r"\.ws-match-wl\.win,\s*\.ws-match-wl-badge\.win\s*\{([^}]*)\}",
            r"\.match-headline\s+\.win-tag\s*\{([^}]*)\}",
            r"\.home-match-card\.win-card\s*\{([^}]*)\}",
            r"\.hmc-verdict-preview\.win\s*\{([^}]*)\}",
            r"\.pregame-wl-card\.win\s*\{([^}]*)\}",
        ):
            m = re.search(win_sel, css)
            self.assertIsNotNone(m, f"未找到胜局样式选择器: {win_sel}")
            block = m.group(1)
            self.assertNotIn("--green", block, f"胜局样式不应混用阵营绿色: {win_sel}")
            self.assertNotIn("120, 191, 150", block, f"胜局样式不应混用绿色背景: {win_sel}")
            self.assertTrue(
                "--gold" in block or "#c6a468" in block or "198, 164, 104" in block,
                f"胜局样式应使用金色: {win_sel} -> {block}",
            )

        # Faction classes must use --radiant / --dire
        self.assertRegex(css, r"\.legend-dot\.rad::before\s*\{[^}]*var\(--radiant\)")
        self.assertRegex(css, r"\.legend-dot\.dire::before\s*\{[^}]*var\(--dire\)")
        self.assertRegex(css, r"\.scrub-tug-rad\s*\{[^}]*var\(--radiant\)")
        self.assertRegex(css, r"\.scrub-tug-dire\s*\{[^}]*var\(--dire\)")

    def test_2_match_header_dota_scoreboard_with_5v5_avatars_and_winner_border(self):
        """R4-3: 比赛头部做成 Dota 计分板（左天辉 5 英雄头像 | 中衬线金色大比分 | 右夜魇 5 英雄头像，胜方加金色描边）。"""
        node_script = r"""
const fs = require("fs");
const vm = require("vm");
const appJs = fs.readFileSync("static/app.js", "utf8");
const repDireWin = JSON.parse(fs.readFileSync("reports/match_9043295657.json", "utf8"));
const repRadWin = Object.assign({}, repDireWin, { radiant_win: true, winner: "天辉 (Radiant)" });

const els = {};
function makeEl(id) {
  return {
    id,
    innerHTML: "",
    textContent: "",
    hidden: false,
    style: {},
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
    addEventListener() {},
    querySelectorAll() { return []; },
    querySelector() { return null; },
    setAttribute() {},
    getAttribute() { return ""; },
  };
}
const sandbox = {
  console,
  window: { location: { origin: "https://dota-ai-analyst.vercel.app", pathname: "/", search: "" } },
  location: { origin: "https://dota-ai-analyst.vercel.app", pathname: "/", search: "" },
  localStorage: { getItem() { return null; }, setItem() {}, removeItem() {} },
  sessionStorage: { getItem() { return null; }, setItem() {}, removeItem() {} },
  navigator: {},
  document: {
    title: "",
    body: { dataset: {} },
    getElementById(id) {
      if (!els[id]) els[id] = makeEl(id);
      return els[id];
    },
    querySelector() { return null; },
    querySelectorAll() { return []; },
    createElement(tag) { return makeEl(tag); },
    addEventListener() {},
  },
  fetch: async () => ({ ok: true, json: async () => ({}) }),
  setTimeout: () => 1,
  clearTimeout() {},
  requestAnimationFrame: () => 1,
  URLSearchParams,
};
vm.createContext(sandbox);
vm.runInContext(appJs, sandbox);

sandbox.renderMatchOverview(repDireWin);
const htmlDireWin = els["match-kpi-strip"].innerHTML;

sandbox.renderMatchOverview(repRadWin);
const htmlRadWin = els["match-kpi-strip"].innerHTML;

console.log(JSON.stringify({ htmlDireWin, htmlRadWin, radScore: repDireWin.radiant_score, direScore: repDireWin.dire_score }));
"""
        proc = subprocess.run(
            ["node", "-e", node_script],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            check=True,
        )
        out = json.loads(proc.stdout.strip().splitlines()[-1])
        for key, winner_cls, loser_cls in (
            ("htmlDireWin", "dota-sb-side is-dire is-winner", "dota-sb-side is-radiant"),
            ("htmlRadWin", "dota-sb-side is-radiant is-winner", "dota-sb-side is-dire"),
        ):
            html = out[key]
            self.assertIn("dota-scoreboard", html)
            self.assertIn("dota-sb-score", html)
            self.assertIn(f"{out['radScore']}", html)
            self.assertIn(f"{out['direScore']}", html)
            self.assertIn(winner_cls, html)
            self.assertIn(loser_cls, html)
            self.assertNotIn(f"{loser_cls} is-winner", html)
            avatar_imgs = re.findall(r'class="dota-sb-hero-img"', html)
            self.assertEqual(len(avatar_imgs), 10, f"计分板应展示左右各 5 个共 10 个英雄头像，实际 {len(avatar_imgs)}")

    def test_3_serif_headings_tabular_nums_and_no_webfonts(self):
        """R4-3: 站点名、每节标题、大比分用系统衬线体，不加载网络字体，数字等宽。"""
        css = CSS_PATH.read_text(encoding="utf-8")
        html = HTML_PATH.read_text(encoding="utf-8")
        self.assertIn(
            '--serif: "Songti SC", "Noto Serif SC", "STSong", Georgia, serif;',
            css,
        )
        self.assertNotIn("fonts.googleapis.com", css)
        self.assertNotIn("fonts.googleapis.com", html)
        self.assertNotIn("@import", css)
        self.assertNotIn("@font-face", css)

        for sel in (
            r"\.ws-brand-name\s*\{([^}]*)\}",
            r"\.section-heading\s+h2\s*\{([^}]*)\}",
            r"\.dota-sb-score\s*\{([^}]*)\}",
        ):
            m = re.search(sel, css)
            self.assertIsNotNone(m, f"缺少衬线标题规则: {sel}")
            self.assertIn("var(--serif)", m.group(1), f"{sel} 未使用 var(--serif)")

        self.assertIn("font-variant-numeric: tabular-nums;", css)

    def test_4_slate_gold_panels_buttons_diamond_dividers_vignette_and_line_budget(self):
        """R4-3: 石板加金线面板（圆角 2-3px、无 999px 药丸、顶部微高光）、旧版按钮、节标题细金线+◆、径向暗角且零图片素材、CSS 行数不超基线。"""
        css = CSS_PATH.read_text(encoding="utf-8")
        lines = css.splitlines()
        self.assertLessEqual(
            len(lines),
            BASELINE_STYLES_LINES,
            f"styles.css 行数 ({len(lines)}) 不得超过修改前基线 ({BASELINE_STYLES_LINES})",
        )
        self.assertNotIn("border-radius: 999px", css)
        self.assertNotIn("border-radius: 10px", css)
        self.assertNotIn("border-radius: 8px", css)
        self.assertEqual(re.findall(r"url\(", css), [], "CSS 中不得引用背景图片素材 url(...)")
        self.assertIn("radial-gradient(", css, "缺少纯 CSS 径向渐变暗角层次")
        self.assertIn("inset 0 1px 0", css, "面板缺少顶部内侧极淡高光")
        self.assertIn('"◆"', css, "每节标题下缺少细金线上的小菱形 ◆ 装饰")

        # 普通按钮深色底加金色细边；主按钮砖红底 (--red)
        cmd_btn_m = re.search(r"\.ws-cmd-btn\s*\{([^}]*)\}", css)
        self.assertIsNotNone(cmd_btn_m)
        self.assertTrue(
            "#565343" in cmd_btn_m.group(1) or "198, 164, 104" in cmd_btn_m.group(1),
            f".ws-cmd-btn 未采用深色底+金色细边: {cmd_btn_m.group(1)}",
        )
        cmd_pri_m = re.search(r"\.ws-cmd-btn\.primary\s*\{([^}]*)\}", css)
        self.assertIsNotNone(cmd_pri_m)
        self.assertTrue(
            "var(--red)" in cmd_pri_m.group(1) or "#954338" in cmd_pri_m.group(1),
            f".ws-cmd-btn.primary 未采用砖红底: {cmd_pri_m.group(1)}",
        )

    def test_5_no_english_kickers_no_task_codes_reduced_emojis_and_valve_footer(self):
        """R4-3: 去掉英文小标题与任务编号 (F3/F7)，去掉导航/节标题/按钮里的表情符号，页脚可见且含 Valve 商标声明。"""
        html = HTML_PATH.read_text(encoding="utf-8")
        js = JS_PATH.read_text(encoding="utf-8")

        forbidden_ui_tokens = (
            "NEXT GAME TOP 3 FIXES",
            "TEAM METRICS",
            "TOP 3 REPLAY MOMENTS",
            "REPLAY FACT-CHECK",
            "DOTA 2 5-STACK FORENSICS HUB",
            "PRE-GAME 5-STACK LIVE TACTICAL ROOM",
            "STRUCTURED DOSSIER",
            "(F3)",
            "(F7)",
            "F3 ·",
        )
        for tok in forbidden_ui_tokens:
            self.assertNotIn(tok, html, f"index.html 仍残留英文小标题或任务编号: {tok}")
            self.assertNotIn(tok, js, f"app.js 仍残留英文小标题或任务编号: {tok}")

        # 导航、节标题、按钮里的表情符号去掉（排除弹窗内的自定义创作提示 select option）
        nav_and_btn_blocks = re.findall(
            r"<(?:button|h1|h2|h3)\b[^>]*>.*?</(?:button|h1|h2|h3)>",
            html,
            flags=re.DOTALL,
        )
        offending = []
        for blk in nav_and_btn_blocks:
            text_only = re.sub(r"<[^>]+>", "", blk).strip()
            if EMOJI_RE.search(text_only):
                offending.append(text_only)
        self.assertEqual(
            offending,
            [],
            f"index.html 的导航/标题/按钮中仍含表情符号: {offending[:10]}",
        )

        # 页脚包含精确 Valve 商标声明，且位于 .main-container 内部可滚动阅读区域中
        valve_disclaimer = "Dota 2 是 Valve 公司的商标，本站为玩家自用工具，与 Valve 无关。"
        self.assertIn(valve_disclaimer, html)
        main_m = re.search(r'<main class="main-container">(.*)</main>', html, flags=re.DOTALL)
        self.assertIsNotNone(main_m)
        self.assertIn(valve_disclaimer, main_m.group(1), "页脚必须位于 .main-container 滚动区内以便用户可见")


if __name__ == "__main__":
    unittest.main()
