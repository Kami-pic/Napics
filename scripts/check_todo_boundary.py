from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TODO_FILES = list((ROOT / ".kiro" / "docs").glob("optimization-*todo.md"))
MAX_TODO_LINES = 260
FORBIDDEN_PATTERNS = [
    "### 本轮交付检查",
    "【本轮目标】",
    "【涉及文件】",
    "【验证结果】",
    "【风险检查】",
    "【结论】",
]


def main() -> int:
    errors: list[str] = []
    for path in TODO_FILES:
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        if len(lines) > MAX_TODO_LINES:
            errors.append(f"{path}: 行数 {len(lines)} 超过上限 {MAX_TODO_LINES}")
        for pattern in FORBIDDEN_PATTERNS:
            if pattern in text:
                errors.append(f"{path}: 不允许包含 `{pattern}`，请迁移到 worklog/devlog")

    if errors:
        print("TODO 边界检查失败：")
        for error in errors:
            print(f"- {error}")
        return 1

    print("TODO 边界检查通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
