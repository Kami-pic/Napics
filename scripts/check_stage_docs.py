from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TODO_PATH = ".kiro/docs/optimization-stabilization-todo.md"


def git_diff_cached() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def is_code_change(path: str) -> bool:
    return path.startswith("backend/") or path.startswith("frontend/")


def is_doc_change(path: str) -> bool:
    return (
        path == TODO_PATH
        or path.startswith(".kiro/knowledge/")
        or path.startswith(".kiro/docs/_one-off/")
    )


def main() -> int:
    staged = git_diff_cached()
    code_changes = [path for path in staged if is_code_change(path)]
    if not code_changes:
        print("阶段文档检查跳过：本次提交没有 backend/frontend 代码变更。")
        return 0

    if TODO_PATH not in staged:
        print(f"阶段文档检查失败：检测到代码变更，但未同时更新 `{TODO_PATH}`。")
        return 1

    doc_changes = [path for path in staged if is_doc_change(path) and path != TODO_PATH]
    if not doc_changes:
        print("阶段文档检查失败：检测到代码变更，但未同时更新 knowledge 或 worklog。")
        print("至少补一个：`.kiro/knowledge/*.md` 或 `.kiro/docs/_one-off/*.md`。")
        return 1

    print("阶段文档检查通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
