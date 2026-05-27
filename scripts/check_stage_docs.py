from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC_PREFIXES = (
    ".kiro/docs/",
    ".kiro/knowledge/",
)
RUNTIME_DOC_PREFIXES = (
    ".kiro/docs/_archived/",
)


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
    if any(path.startswith(prefix) for prefix in RUNTIME_DOC_PREFIXES):
        return False
    return any(path.startswith(prefix) for prefix in DOC_PREFIXES)


def main() -> int:
    staged = git_diff_cached()
    code_changes = [path for path in staged if is_code_change(path)]
    if not code_changes:
        print("阶段文档检查跳过：本次提交没有 backend/frontend 代码变更。")
        return 0

    doc_changes = [path for path in staged if is_doc_change(path)]
    if not doc_changes:
        print("阶段文档检查失败：检测到 backend/frontend 代码变更，但未同时更新相关项目文档。")
        print("至少补一个相关文档：`.kiro/docs/*.md`、`.kiro/docs/_one-off/*.md` 或 `.kiro/knowledge/*.md`。")
        print("不要为了通过检查固定修改 stabilization TODO；应更新本轮任务对应的文档。")
        return 1

    print("阶段文档检查通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
