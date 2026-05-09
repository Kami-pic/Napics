# [一次性] 正式 test_*.py 脚本化治理记录

## 本轮目标

- 先处理 pytest 收集被 `test_bt_expand.py` / `test_code_split.py` 阻断的问题。
- 不改业务逻辑，不碰前端，不移动 `backend/_*.py` 历史脚本，不用 skip 掩盖真实失败。

## 已处理

- `backend/test_bt_expand.py`
  - 移除导入期自定义 test runner、计数输出和 `sys.exit`
  - 保留 23 个 pytest 原生 `test_*` 函数
  - 验证：`python -X utf8 -m pytest test_bt_expand.py -p no:cacheprovider`，23 passed

- `backend/test_code_split.py`
  - 移除导入期 stdout/stderr 重包
  - 移除导入期自定义 test runner、计数输出和汇总输出
  - 保留 33 个 pytest 原生 `test_*` 函数
  - 验证：`python -X utf8 -m pytest test_code_split.py -p no:cacheprovider`，33 passed

- `backend/test_detail_drawer_split.py`
  - 移除导入期 localhost API 执行和失败时 `sys.exit`
  - 改为 7 个 pytest 原生测试函数
  - 验证：`python -X utf8 -m pytest test_detail_drawer_split.py --collect-only -p no:cacheprovider`，7 collected

## 全量收集结果

- 命令：`python -X utf8 -m pytest . --collect-only -p no:cacheprovider`
- 当前结果：已收集到 467 items 后仍失败。
- 当前残留阻断：其它正式 `test_*.py` 中仍存在 stdout/stderr 重包或导入期 `sys.exit`。
- 下一轮建议：按 collect 暴露顺序继续处理 stdout/stderr 重包类文件，再处理导入期 `sys.exit` 类文件。
