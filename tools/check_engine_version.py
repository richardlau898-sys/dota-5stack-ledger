#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R1-9 · 引擎版本号检查工具
当分析相关源码文件发生改动但 dota_analyst.py 中的 ENGINE_VERSION 未同步更新时，
在 CI 中输出 GitHub Actions ::warning:: 提醒（加 --strict 时以非 0 退出码返回）。
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent

ANALYSIS_EXACT_FILES = {
    "dota_analyst.py",
    "ai_coach_engine.py",
    "draft_and_phase_coach.py",
    "hero_profiles_126.py",
    "squad_growth_metrics.py",
    "tactical_microscope_engine.py",
    "dota_constants_zh.py",
}

ANALYSIS_PREFIXES = (
    "microscope_sections/",
)


def _is_analysis_file(rel_path: str) -> bool:
    norm = rel_path.strip().replace("\\", "/")
    if norm in ANALYSIS_EXACT_FILES:
        return True
    return any(norm.startswith(p) and norm.endswith(".py") for p in ANALYSIS_PREFIXES)


def _git_output(repo: Path, args: List[str]) -> Optional[str]:
    res = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        return None
    return res.stdout


def _extract_engine_version_at_ref(repo: Path, ref: str) -> Optional[str]:
    content = _git_output(repo, ["show", f"{ref}:dota_analyst.py"])
    if not content:
        return None
    m = re.search(r'^\s*ENGINE_VERSION\s*=\s*["\']([^"\']+)["\']', content, flags=re.MULTILINE)
    return m.group(1) if m else None


def check_engine_version(
    repo: Path = REPO_ROOT,
    base_ref: Optional[str] = None,
    head_ref: str = "HEAD",
) -> Tuple[bool, str]:
    resolved_base = base_ref
    if not resolved_base:
        gh_base = os.environ.get("GITHUB_BASE_REF", "").strip()
        if gh_base and _git_output(repo, ["rev-parse", "--verify", f"origin/{gh_base}"]) is not None:
            mb = _git_output(repo, ["merge-base", f"origin/{gh_base}", head_ref])
            resolved_base = mb.strip() if mb and mb.strip() else f"origin/{gh_base}"
        elif _git_output(repo, ["rev-parse", "--verify", f"{head_ref}~1"]) is not None:
            resolved_base = f"{head_ref}~1"
        else:
            return True, "OK: Initial commit or shallow clone without base ref; skipping ENGINE_VERSION diff check."

    diff_names_out = _git_output(repo, ["diff", "--name-only", resolved_base, head_ref])
    if diff_names_out is None:
        return True, f"OK: Unable to diff {resolved_base}..{head_ref}; skipping check."

    changed_analysis = sorted(
        f.strip()
        for f in diff_names_out.splitlines()
        if f.strip() and _is_analysis_file(f.strip())
    )
    if not changed_analysis:
        return True, "OK: No analysis files modified."

    base_ver = _extract_engine_version_at_ref(repo, resolved_base)
    head_ver = _extract_engine_version_at_ref(repo, head_ref)
    if base_ver != head_ver and head_ver:
        return True, f"OK: Analysis files changed ({', '.join(changed_analysis)}) and ENGINE_VERSION updated ({base_ver} -> {head_ver})."

    msg = (
        f"::warning file=dota_analyst.py,line=55::Analysis files modified ({', '.join(changed_analysis)}) "
        f"without bumping ENGINE_VERSION (still {head_ver!r}). Remember Rule 18!"
    )
    return False, msg


def main() -> int:
    parser = argparse.ArgumentParser(description="Check ENGINE_VERSION bump when analysis files change.")
    parser.add_argument("--repo", default=str(REPO_ROOT), help="Git repository path")
    parser.add_argument("--base", default=None, help="Base git ref")
    parser.add_argument("--head", default="HEAD", help="Head git ref")
    parser.add_argument("--strict", action="store_true", help="Exit 1 instead of 0 on warning")
    args = parser.parse_args()

    ok, msg = check_engine_version(Path(args.repo), base_ref=args.base, head_ref=args.head)
    print(msg)
    if not ok and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
