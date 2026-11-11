#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R1-4 · 静态文件哈希自动生成与校验工具
计算 static/app.js 与 static/styles.css 的 SHA-256 前 8 位内容哈希，
并同步更新或检查 static/index.html 与 vercel.json。
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parent.parent


def compute_asset_hashes(root_dir: Path) -> tuple[str, str]:
    app_js = root_dir / "static" / "app.js"
    styles_css = root_dir / "static" / "styles.css"
    if not app_js.is_file():
        raise FileNotFoundError(f"Missing {app_js}")
    if not styles_css.is_file():
        raise FileNotFoundError(f"Missing {styles_css}")
    js_hash = hashlib.sha256(app_js.read_bytes()).hexdigest()[:8]
    css_hash = hashlib.sha256(styles_css.read_bytes()).hexdigest()[:8]
    return js_hash, css_hash


def build_updated_index_html(html_text: str, js_hash: str, css_hash: str) -> str:
    new_html, n_css = re.subn(
        r'href="/styles(?:\.[0-9a-f]+)?\.css"',
        f'href="/styles.{css_hash}.css"',
        html_text,
    )
    new_html, n_js = re.subn(
        r'src="/app(?:\.[0-9a-f]+)?\.js"',
        f'src="/app.{js_hash}.js"',
        new_html,
    )
    if n_css == 0 or n_js == 0:
        raise ValueError("static/index.html missing styles.css or app.js asset tag")
    return new_html


def build_updated_vercel_json(vercel_text: str, js_hash: str, css_hash: str) -> str:
    cfg = json.loads(vercel_text)
    expected_hdr_source = rf"/(app\.{js_hash}\.js|styles\.{css_hash}\.css)"
    for hdr_entry in cfg.get("headers") or []:
        vals = [h.get("value", "") for h in (hdr_entry.get("headers") or []) if h.get("key", "").lower() == "cache-control"]
        if any("immutable" in v for v in vals):
            hdr_entry["source"] = expected_hdr_source

    new_rewrites = []
    replaced_js = False
    replaced_css = False
    for rw in cfg.get("rewrites") or []:
        src = rw.get("source", "")
        dst = rw.get("destination", "")
        if dst == "/static/app.js" and src != "/app.js":
            if not replaced_js:
                new_rewrites.append({"source": f"/app.{js_hash}.js", "destination": "/static/app.js"})
                replaced_js = True
            continue
        if dst == "/static/styles.css" and src != "/styles.css":
            if not replaced_css:
                new_rewrites.append({"source": f"/styles.{css_hash}.css", "destination": "/static/styles.css"})
                replaced_css = True
            continue
        new_rewrites.append(rw)

    if not replaced_js:
        new_rewrites.insert(1, {"source": f"/app.{js_hash}.js", "destination": "/static/app.js"})
    if not replaced_css:
        new_rewrites.insert(2, {"source": f"/styles.{css_hash}.css", "destination": "/static/styles.css"})
    cfg["rewrites"] = new_rewrites
    return json.dumps(cfg, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or verify content hashes for static/app.js and static/styles.css.")
    parser.add_argument("--check", action="store_true", help="Verify hashes without writing any files.")
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="Project root directory.")
    args = parser.parse_args()

    root_dir = Path(args.root).resolve()
    js_hash, css_hash = compute_asset_hashes(root_dir)

    index_path = root_dir / "static" / "index.html"
    orig_html = index_path.read_text(encoding="utf-8")
    expected_html = build_updated_index_html(orig_html, js_hash, css_hash)

    vercel_path = root_dir / "vercel.json"
    has_vercel = vercel_path.is_file()
    orig_vercel = vercel_path.read_text(encoding="utf-8") if has_vercel else ""
    expected_vercel = build_updated_vercel_json(orig_vercel, js_hash, css_hash) if has_vercel else ""

    if args.check:
        errors = []
        if orig_html != expected_html:
            errors.append(
                f"static/index.html asset hashes out of sync (expected app.{js_hash}.js and styles.{css_hash}.css)."
            )
        if has_vercel and orig_vercel != expected_vercel:
            errors.append(
                f"vercel.json asset hashes out of sync (expected /app.{js_hash}.js and /styles.{css_hash}.css)."
            )
        if errors:
            for err in errors:
                sys.stderr.write(f"ERROR: {err}\n")
            sys.stderr.write("Run `python3 tools/build_static_hashes.py` to update static hashes.\n")
            return 1
        print(f"OK: Static hashes verified (app.{js_hash}.js, styles.{css_hash}.css).")
        return 0

    if orig_html != expected_html:
        index_path.write_text(expected_html, encoding="utf-8")
    if has_vercel and orig_vercel != expected_vercel:
        vercel_path.write_text(expected_vercel, encoding="utf-8")
    print(f"Updated static hashes: app.{js_hash}.js, styles.{css_hash}.css")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
