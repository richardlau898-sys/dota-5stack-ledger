# -*- coding: utf-8 -*-
import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestR41RebrandDotaLedger(unittest.TestCase):
    def test_1_single_source_brand_constants_and_dao_mark(self):
        """R4-1: 站点名「刀塔账房」与副标题「五黑战后复盘与赛前作战室」在后端与前端各只定义在一处常量，保留「刀」字标记。"""
        import dota_analyst

        self.assertEqual(getattr(dota_analyst, "SITE_NAME", None), "刀塔账房")
        self.assertEqual(getattr(dota_analyst, "SITE_SUBTITLE", None), "五黑战后复盘与赛前作战室")

        # 后端 Python 代码中字面量 "刀塔账房" 只在 dota_analyst.py 定义一次
        py_files = list(ROOT.glob("*.py")) + list((ROOT / "tools").glob("*.py"))
        literal_defs = []
        for pf in py_files:
            txt = pf.read_text(encoding="utf-8")
            matches = re.findall(r'["\']刀塔账房["\']', txt)
            if matches:
                literal_defs.append((pf.name, len(matches)))
        self.assertEqual(literal_defs, [("dota_analyst.py", 1)])

        # 前端 JS 代码中字面量 "刀塔账房" 与 "五黑战后复盘与赛前作战室" 各只在 static/app.js 定义一次
        app_js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r'["\'`]刀塔账房["\'`]', app_js)), 1)
        self.assertEqual(len(re.findall(r'["\'`]五黑战后复盘与赛前作战室["\'`]', app_js)), 1)
        self.assertNotIn("战后算账", app_js)

        index_html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        self.assertIn(">刀<", index_html)
        self.assertIn("刀塔账房", index_html)
        self.assertIn("五黑战后复盘与赛前作战室", index_html)
        self.assertNotIn("战后算账", index_html)

    def test_2_grep_workstation_and_keen_zero_matches(self):
        """R4-1: grep -rni 'workstation\\|keen' static/ *.py tools/ 必须无结果，同时保留中立附魔运行时字典键。"""
        import dota_constants_zh

        self.assertEqual(
            dota_constants_zh.ITEMS_ZH.get("enhancement_k" + "een_eyed"),
            "敏锐附魔(+施法距离)",
        )

        proc = subprocess.run(
            "grep -rni 'workstation\\|keen' static/ *.py tools/",
            cwd=str(ROOT),
            shell=True,
            text=True,
            capture_output=True,
        )
        self.assertEqual(
            proc.returncode,
            1,
            f"发现残留的 workstation/keen 匹配:\n{proc.stdout}",
        )
        self.assertEqual(proc.stdout.strip(), "")

    def test_3_webhook_share_pdf_and_poster_use_site_name(self):
        """R4-1: 赛后推送、分享文案、全屏/PDF 报告页脚与海报页脚均引用新站点名「刀塔账房」。"""
        from tools import postgame_webhook_notifier

        sample_report = json.loads((ROOT / "reports" / "match_9043295657.json").read_text(encoding="utf-8"))
        webhook_payload = postgame_webhook_notifier.build_postgame_webhook_payload(
            sample_report,
            "https://dota-ai-analyst.vercel.app",
        )
        self.assertIn("刀塔账房", webhook_payload["content"])
        self.assertNotIn("战后算账", webhook_payload["content"])

        node_script = r"""
const fs = require("fs");
const vm = require("vm");
const report = JSON.parse(fs.readFileSync("reports/match_9043295657.json", "utf8"));
const appJs = fs.readFileSync("static/app.js", "utf8");
const filledTexts = [];
const els = {};
function makeEl(id) {
  return {
    id,
    innerHTML: "",
    textContent: "",
    value: "",
    width: 920,
    height: 790,
    hidden: false,
    open: false,
    style: {},
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
    addEventListener() {},
    querySelectorAll() { return []; },
    querySelector() { return null; },
    setAttribute() {},
    getAttribute() { return ""; },
    showModal() { this.open = true; },
    close() { this.open = false; },
    getContext() {
      return {
        fillStyle: "",
        strokeStyle: "",
        lineWidth: 1,
        font: "",
        textAlign: "left",
        createLinearGradient: () => ({ addColorStop() {} }),
        fillRect() {},
        strokeRect() {},
        clearRect() {},
        beginPath() {},
        moveTo() {},
        lineTo() {},
        stroke() {},
        save() {},
        restore() {},
        measureText: (t) => ({ width: String(t).length * 12 }),
        fillText: (t) => { filledTexts.push(String(t)); },
      };
    },
  };
}
["share-poster-dialog", "share-verdict-textarea", "share-poster-canvas"].forEach((id) => {
  els[id] = makeEl(id);
});
const sandbox = {
  window: {},
  document: {
    title: "",
    getElementById: (id) => els[id] || (els[id] = makeEl(id)),
    querySelectorAll: () => [],
    querySelector: () => null,
    addEventListener: () => {},
    documentElement: { setAttribute() {}, style: {} },
    body: makeEl("body"),
  },
  localStorage: { getItem: () => null, setItem: () => {} },
  sessionStorage: { getItem: () => null, setItem: () => {} },
  navigator: { clipboard: { writeText: async () => {} } },
  location: { search: "", hash: "", pathname: "/", origin: "https://dota-ai-analyst.vercel.app" },
  history: { replaceState() {}, pushState() {} },
  fetch: async () => ({ ok: true, json: async () => ({}) }),
  URLSearchParams,
  console,
  setTimeout: () => 1,
  clearTimeout: () => {},
  requestAnimationFrame: () => 1,
};
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(appJs, sandbox);
const out = vm.runInContext(`
  state.currentReport = ${JSON.stringify(report)};
  const pdfHtml = buildStructuredFullReportHtml(state.currentReport);
  openSharePosterDialog(state.currentReport);
  const teamShareCopy = document.getElementById("share-verdict-textarea").value;
  ({ pdfHtml, teamShareCopy })
`, sandbox);
process.stdout.write(JSON.stringify({ ...out, filledTexts }));
"""
        proc = subprocess.run(
            ["node", "-e", node_script],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            check=True,
        )
        res = json.loads(proc.stdout)
        self.assertIn("刀塔账房", res["pdfHtml"])
        self.assertIn("刀塔账房", res["teamShareCopy"])
        self.assertTrue(any("刀塔账房" in t for t in res["filledTexts"]))
        self.assertNotIn("战后算账", res["pdfHtml"])
        self.assertNotIn("战后算账", res["teamShareCopy"])


if __name__ == "__main__":
    unittest.main()
