# [TODO] 下一步工作清单

---

## 订阅系统重设计

> 设计方案：`docs/subscribe-redesign.md`，交给独立对话按 Phase 推进。

---

## 技术债务

- [ ] `pan_models.py` 的 4 个 `@validator` → Pydantic V2 `@field_validator`
- [ ] `routes/search.py` 拆分 → 订阅重设计 Phase 1b 会一并解决
- [ ] `routes/discover.py`（729 行）拆分
- [ ] 后端 `print()` → `logging` 模块
