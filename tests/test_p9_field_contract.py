import json
import subprocess
import unittest
from pathlib import Path

from dota_analyst import analyze_match_data, load_roster
from tests.helpers import load_all_raw_matches

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "schema" / "report.schema.json"


def _validate_against_schema(instance, schema, path="$"):
    expected_type = schema.get("type")
    if expected_type:
        types = expected_type if isinstance(expected_type, list) else [expected_type]
        type_ok = False
        for t in types:
            if t == "null" and instance is None:
                type_ok = True
            elif t == "boolean" and isinstance(instance, bool):
                type_ok = True
            elif t == "integer" and isinstance(instance, int) and not isinstance(instance, bool):
                type_ok = True
            elif t == "number" and isinstance(instance, (int, float)) and not isinstance(instance, bool):
                type_ok = True
            elif t == "string" and isinstance(instance, str):
                type_ok = True
            elif t == "array" and isinstance(instance, list):
                type_ok = True
            elif t == "object" and isinstance(instance, dict):
                type_ok = True
        if not type_ok:
            raise AssertionError(f"{path}: expected type {expected_type}, got {type(instance).__name__} ({instance!r})")

    if "enum" in schema and instance not in schema["enum"]:
        raise AssertionError(f"{path}: value {instance!r} not in enum {schema['enum']}")

    if isinstance(instance, dict):
        for req_key in schema.get("required", []):
            if req_key not in instance:
                raise AssertionError(f"{path}: missing required key '{req_key}'")
        props = schema.get("properties", {})
        for k, sub_schema in props.items():
            if k in instance:
                _validate_against_schema(instance[k], sub_schema, f"{path}.{k}")

    if isinstance(instance, list) and "items" in schema:
        item_schema = schema["items"]
        for idx, item in enumerate(instance):
            _validate_against_schema(item, item_schema, f"{path}[{idx}]")


class TestP9FieldContract(unittest.TestCase):
    def test_1_all_sample_reports_conform_to_json_schema(self):
        self.assertTrue(SCHEMA_PATH.exists(), "schema/report.schema.json must exist")
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        roster = load_roster()
        raw_matches = load_all_raw_matches()
        self.assertGreaterEqual(len(raw_matches), 10)
        for mid, raw in raw_matches.items():
            rep = analyze_match_data(raw, roster)
            _validate_against_schema(rep, schema, path=f"report[{mid}]")

    def test_2_frontend_no_longer_reads_nonexistent_fields(self):
        app_js = (REPO_ROOT / "static" / "app.js").read_text(encoding="utf-8")
        forbidden_snippets = [
            "unpressedBlock?.events",
            "df.item_audit_by_side",
            'p.side === "天辉"',
            "is_focus_player",
            "report.draft_and_combo",
            "report.mvp?.hero_short_zh",
            ".avg_score",
        ]
        for snippet in forbidden_snippets:
            self.assertNotIn(snippet, app_js, f"Forbidden nonexistent field reference still in app.js: {snippet}")
        self.assertIn("validateReportContract", app_js, "Frontend must include validateReportContract reader check")

    def test_3_weakness_radar_and_headless_contract_validation(self):
        roster = load_roster()
        raw_matches = load_all_raw_matches()
        parsed_reports = []
        for mid, raw in list(raw_matches.items())[:6]:
            if raw.get("version"):
                parsed_reports.append(analyze_match_data(raw, roster))

        script = r"""
const fs = require("fs");
const vm = require("vm");

let code = fs.readFileSync("static/app.js", "utf8");
code = code.replace(/document\.addEventListener\(\s*["']DOMContentLoaded["'][\s\S]*$/, "");
code += "\nglobalThis.state = state;\n";

const contractErrors = [];
const elements = {};
function getEl(id) {
  if (!elements[id]) {
    elements[id] = {
      id,
      innerHTML: "",
      textContent: "",
      value: "",
      hidden: false,
      disabled: false,
      open: false,
      style: {},
      dataset: {},
      classList: {
        _set: new Set(),
        add(...cls) { cls.forEach((c) => this._set.add(c)); },
        remove(...cls) { cls.forEach((c) => this._set.delete(c)); },
        toggle(c, force) { return Boolean(force); },
        contains(c) { return this._set.has(c); }
      },
      setAttribute() {},
      getAttribute() { return null; },
      addEventListener() {},
      removeEventListener() {},
      querySelector() { return null; },
      querySelectorAll() { return []; },
      scrollTo() {},
    };
  }
  return elements[id];
}

const sandbox = {
  window: {
    location: { search: "", pathname: "/", href: "http://localhost/" },
    history: { pushState() {}, replaceState() {} },
    addEventListener() {},
    removeEventListener() {},
    scrollTo() {},
  },
  document: {
    getElementById: (id) => getEl(id),
    querySelector: () => null,
    querySelectorAll: () => [],
    createElement: (tag) => getEl("created_" + tag + "_" + Math.random()),
    body: getEl("body"),
  },
  localStorage: { _s: {}, getItem(k) { return this._s[k] || null; }, setItem(k, v) { this._s[k] = String(v); }, removeItem(k) { delete this._s[k]; } },
  sessionStorage: { _s: {}, getItem(k) { return this._s[k] || null; }, setItem(k, v) { this._s[k] = String(v); }, removeItem(k) { delete this._s[k]; } },
  Intl, Date, Math, Number, String, Boolean, Array, Object, Set, Map, RegExp, Error, Promise, JSON, URIError,
  encodeURIComponent, decodeURIComponent, parseInt, parseFloat, isNaN, isFinite,
  console: {
    log() {},
    warn() {},
    error(...args) {
      const msg = args.map(String).join(" ");
      if (msg.includes("[FieldContract]")) contractErrors.push(msg);
    }
  },
  fetch: async () => ({ status: 200, json: async () => ({ ok: true }), text: async () => "{}" }),
  setTimeout: () => 1,
  clearTimeout: () => {},
  setInterval: () => 1,
  clearInterval: () => {},
  requestAnimationFrame: (fn) => fn(),
};
sandbox.window.document = sandbox.document;
sandbox.globalThis = sandbox;

vm.createContext(sandbox);
vm.runInContext(code, sandbox);

const reports = JSON.parse(fs.readFileSync(process.env.REPORTS_FILE, "utf8"));
let radarTriggeredDimensions = new Set();

for (const rep of reports) {
  if (typeof sandbox.validateReportContract !== "function") {
    throw new Error("validateReportContract is not defined");
  }
  sandbox.validateReportContract(rep);
  sandbox.renderFullMatchReport(rep);
  const audit = sandbox.auditAllMicroDimensions(rep, rep.deep_forensics || {}, rep.focus_side || "radiant", "天辉");
  for (const [k, v] of Object.entries(audit)) {
    if (v && v.level !== "good") {
      radarTriggeredDimensions.add(k);
    }
  }
}

if (contractErrors.length > 0) {
  throw new Error("Contract errors found: " + contractErrors.join(" | "));
}

// Across sample parsed matches, previously-dead dimensions (hero_ult, itemization, vision, damage_received) must trigger warn/critical
for (const mustTrigger of ["hero_ult", "itemization", "vision", "damage_received"]) {
  if (!radarTriggeredDimensions.has(mustTrigger)) {
    throw new Error("Expected radar dimension '" + mustTrigger + "' to trigger non-green on problematic matches, got only: " + Array.from(radarTriggeredDimensions).join(","));
  }
}

console.log("P9_OK:" + Array.from(radarTriggeredDimensions).join(","));
"""
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tmp:
            json.dump(parsed_reports, tmp, ensure_ascii=False)
            tmp_path = tmp.name
        try:
            env = dict(**subprocess.os.environ, REPORTS_FILE=tmp_path)
            proc = subprocess.run(
                ["node", "-e", script],
                cwd=str(REPO_ROOT),
                env=env,
                capture_output=True,
                text=True,
                timeout=20,
            )
            self.assertEqual(proc.returncode, 0, f"Node test failed:\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}")
            self.assertIn("P9_OK", proc.stdout)
        finally:
            Path(tmp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
