#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T1-2 模板字面量检查器：
扫描仓库内 .py 和 .js 文件中同时包含中文字符和 MM:SS (\\d{1,2}:\\d{2}) 时间字面量的字符串，发现即失败。
"""

import ast
import os
import re
import sys
from typing import List, Tuple

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZH_RE = re.compile(r"[\u4e00-\u9fff]")
TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\b")
# JS string literal or template literal chunk
JS_STRING_RE = re.compile(
    r"""(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`)""",
    re.DOTALL,
)


def scan_python_file(filepath: str, relpath: str) -> List[Tuple[str, int, str]]:
    violations: List[Tuple[str, int, str]] = []
    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()
    try:
        tree = ast.parse(source, filename=relpath)
    except SyntaxError as exc:
        violations.append((relpath, exc.lineno or 1, f"SyntaxError: {exc}"))
        return violations

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            val = node.value
            if ZH_RE.search(val) and TIME_RE.search(val):
                snippet = val.replace("\n", "\\n")[:120]
                violations.append((relpath, getattr(node, "lineno", 1), snippet))
    return violations


def scan_js_file(filepath: str, relpath: str) -> List[Tuple[str, int, str]]:
    violations: List[Tuple[str, int, str]] = []
    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()

    # Strip single-line and multi-line comments while preserving line numbers
    def _strip_comments(text: str) -> str:
        pattern = re.compile(
            r"""("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`)|(/\*[\s\S]*?\*/|//[^\n]*)"""
        )

        def _repl(m: re.Match) -> str:
            if m.group(1) is not None:
                return m.group(1)
            comment = m.group(2)
            return re.sub(r"[^\n]", " ", comment)

        return pattern.sub(_repl, text)

    clean = _strip_comments(source)
    for match in JS_STRING_RE.finditer(clean):
        lit = match.group(0)
        # For template literals, remove ${...} expressions before checking literal text
        if lit.startswith("`"):
            lit_check = re.sub(r"\$\{[^}]*\}", " ", lit)
        else:
            lit_check = lit
        if ZH_RE.search(lit_check) and TIME_RE.search(lit_check):
            lineno = clean.count("\n", 0, match.start()) + 1
            snippet = lit_check.replace("\n", "\\n")[:120]
            violations.append((relpath, lineno, snippet))
    return violations


def scan_repo(root_dir: str = ROOT_DIR) -> List[Tuple[str, int, str]]:
    violations: List[Tuple[str, int, str]] = []
    skip_dirs = {".git", ".cache", "__pycache__", "node_modules", "tests", "tools", "reports"}
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in sorted(dirnames) if d not in skip_dirs]
        for fname in sorted(filenames):
            fpath = os.path.join(dirpath, fname)
            relpath = os.path.relpath(fpath, root_dir)
            if fname.endswith(".py"):
                violations.extend(scan_python_file(fpath, relpath))
            elif fname.endswith(".js"):
                violations.extend(scan_js_file(fpath, relpath))
    return violations


def main() -> int:
    violations = scan_repo()
    if violations:
        print(f"Found {len(violations)} hardcoded Chinese + MM:SS template literals:", file=sys.stderr)
        for relpath, lineno, snippet in violations:
            print(f"  {relpath}:{lineno}: {snippet}", file=sys.stderr)
        return 1
    print("OK: 0 hardcoded Chinese + MM:SS template literals found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
