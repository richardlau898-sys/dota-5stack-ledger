import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestR35BpSourceLabels(unittest.TestCase):
    def test_1_no_raw_json_fallback_in_draft_coach(self):
        """R3-5: draft_and_phase_coach.py 不得再回退读取已从 Vercel 包排除的 reports/raw_*.json。"""
        src = (ROOT / "draft_and_phase_coach.py").read_text(encoding="utf-8")
        self.assertNotIn("raw_*.json", src)

    def test_2_pregame_plan_attaches_explicit_source_labels_and_real_winrates(self):
        """R3-5: 手写评分标为「通用知识」，分段位胜率读取真实 .cache/hero_stats.json 并标注来源。"""
        import dota_analyst
        import draft_and_phase_coach

        roster = dota_analyst.load_roster()
        heroes_by_id, _ = dota_analyst.get_hero_constants_map()
        plan = draft_and_phase_coach.build_pregame_strategy_plan(
            own_picks=[
                {"pos": 1, "hero_id": 8},
                {"pos": 2, "hero_id": 17},
                {"pos": 3, "hero_id": 2},
                {"pos": 4, "hero_id": 86},
                {"pos": 5, "hero_id": 5},
            ],
            enemy_picks=[
                {"pos": 1, "hero_id": 93},
                {"pos": 2, "hero_id": 76},
            ],
            roster=roster,
            heroes_by_id=heroes_by_id,
        )
        self.assertEqual(plan.get("score_source"), "general_knowledge")
        self.assertEqual(plan.get("score_source_zh"), "通用知识")

        real_bp = plan["real_data_bp_stats"]
        self.assertEqual(len(real_bp["own_hero_real_stats"]), 5)
        for row in real_bp["own_hero_real_stats"]:
            self.assertIn(row.get("squad_source_zh"), ("车队全量对局", "已复盘对局"))
            self.assertEqual(row.get("bracket_source_zh"), "OpenDota 超凡/冠绝")
            self.assertIsNotNone(row.get("bracket_win_rate"))

        for erow in real_bp["enemy_against_stats"]:
            self.assertEqual(erow.get("against_source_zh"), "车队交手记录")
            self.assertEqual(erow.get("bracket_source_zh"), "OpenDota 超凡/冠绝")
            self.assertIsNotNone(erow.get("bracket_win_rate"))

    def test_3_rendered_bp_page_shows_source_beside_every_number_and_hides_empty_most_lost(self):
        """R3-5: 真实执行前端 renderPregameSlots + renderPregamePlanOutput，断言每个数字旁可见来源标签且无数据时不显示「最常输给谁」。"""
        import dota_analyst
        import draft_and_phase_coach

        roster = dota_analyst.load_roster()
        heroes_by_id, _ = dota_analyst.get_hero_constants_map()
        ledger = draft_and_phase_coach.build_squad_history_ledger(ROOT / "reports", roster, [])
        plan = draft_and_phase_coach.build_pregame_strategy_plan(
            own_picks=[
                {"pos": 1, "hero_id": 8},
                {"pos": 2, "hero_id": 17},
                {"pos": 3, "hero_id": 2},
                {"pos": 4, "hero_id": 86},
                {"pos": 5, "hero_id": 5},
            ],
            enemy_picks=[
                {"pos": 1, "hero_id": 93},
                {"pos": 2, "hero_id": 76},
            ],
            roster=roster,
            heroes_by_id=heroes_by_id,
        )

        node_script = r"""
const fs = require("fs");
const vm = require("vm");
const payload = JSON.parse(fs.readFileSync(0, "utf8"));
const appJs = fs.readFileSync("static/app.js", "utf8");
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
["pregame-own-slots", "pregame-enemy-slots", "pregame-active-slot-indicator", "pregame-plan-output"].forEach((id) => {
  els[id] = makeEl(id);
});
const sandbox = {
  window: {},
  document: {
    getElementById: (id) => els[id] || makeEl(id),
    querySelectorAll: () => [],
    querySelector: () => null,
    addEventListener: () => {},
    documentElement: { setAttribute() {}, style: {} },
    body: makeEl("body"),
  },
  localStorage: { getItem: () => null, setItem: () => {} },
  sessionStorage: { getItem: () => null, setItem: () => {} },
  navigator: { clipboard: { writeText: async () => {} } },
  location: { search: "", hash: "", pathname: "/", origin: "http://localhost" },
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
vm.runInContext(`
  state.roster = ${JSON.stringify(payload.roster)};
  state.squadLedger = ${JSON.stringify(payload.ledger)};
  state.heroesCatalog = ${JSON.stringify(payload.heroes)};
  state.pregameOwnPicks = ${JSON.stringify(payload.plan.own_players)};
  state.pregameEnemyPicks = ${JSON.stringify(payload.plan.enemy_players)};
  renderPregameSlots();
  renderPregamePlanOutput(${JSON.stringify(payload.plan)});
`, sandbox);
process.stdout.write(JSON.stringify({
  slotsHtml: els["pregame-own-slots"].innerHTML,
  planHtml: els["pregame-plan-output"].innerHTML,
}));
"""
        proc = subprocess.run(
            ["node", "-e", node_script],
            cwd=str(ROOT),
            input=json.dumps({
                "roster": roster,
                "ledger": ledger,
                "heroes": list(heroes_by_id.values()),
                "plan": plan,
            }),
            text=True,
            capture_output=True,
            check=True,
        )
        rendered = json.loads(proc.stdout)
        combined_html = rendered["slotsHtml"] + "\n" + rendered["planHtml"]

        self.assertIn("通用知识", combined_html)
        self.assertIn("OpenDota 超凡/冠绝", combined_html)
        self.assertTrue("已复盘对局" in combined_html or "车队全量对局" in combined_html)
        self.assertIn("bp-src-tag", combined_html)
        if not plan["real_data_bp_stats"]["most_lost_against_top"]:
            self.assertNotIn("最常输给谁", combined_html)

        # 再验证当 most_lost_against_top 非空时，渲染结果包含「车队最常输给谁」与「[车队交手记录]」
        plan_with_lost = json.loads(json.dumps(plan))
        plan_with_lost["real_data_bp_stats"]["most_lost_against_top"] = [
            {
                "hero_id": 76,
                "hero_short_zh": "殁境神蚀者",
                "against_games": 14,
                "against_win": 4,
                "against_losses": 10,
                "against_win_rate": 28.6,
                "loss_rate": 71.4,
                "insufficient_sample": False,
                "source_zh": "车队交手记录",
            }
        ]
        proc2 = subprocess.run(
            ["node", "-e", node_script],
            cwd=str(ROOT),
            input=json.dumps({
                "roster": roster,
                "ledger": ledger,
                "heroes": list(heroes_by_id.values()),
                "plan": plan_with_lost,
            }),
            text=True,
            capture_output=True,
            check=True,
        )
        rendered2 = json.loads(proc2.stdout)
        self.assertIn("车队最常输给谁", rendered2["planHtml"])
        self.assertIn("殁境神蚀者", rendered2["planHtml"])
        self.assertIn("[车队交手记录]", rendered2["planHtml"])

    def test_4_sync_player_heroes_against_writes_cache(self):
        """R3-5: sync_full_match_history.sync_player_heroes_against 能真实写出 player_heroes_against.json 格式。"""
        import tempfile
        from tools import sync_full_match_history

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "player_heroes_against.json"
            rows = sync_full_match_history.sync_player_heroes_against(
                account_id=86080912,
                fetcher=lambda _url: [
                    {"hero_id": 76, "games": 5, "win": 3, "against_games": 15, "against_win": 4},
                    {"hero_id": 8, "games": 16, "win": 11, "against_games": 8, "against_win": 5},
                ],
                cache_path=tmp_path,
            )
            self.assertEqual(len(rows), 2)
            self.assertTrue(tmp_path.exists())
            saved = json.loads(tmp_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["account_id"], 86080912)
            self.assertEqual(len(saved["heroes"]), 2)
            self.assertEqual(saved["heroes"][0]["against_games"], 15)


if __name__ == "__main__":
    unittest.main()
