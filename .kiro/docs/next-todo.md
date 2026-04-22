# [废弃] 下一步工作清单

> 技术债务已于 2026-04-22 清理完成，详见 devlog.md。
> `routes/search.py` 拆分留待订阅重设计 Phase 1b 一并解决。

---

## 订阅系统重设计

> 设计方案：`docs/subscribe-redesign.md`，交给独立对话按 Phase 推进。

---

## 技术债务

- [x] `pan_models.py` 的 4 个 `@validator` → Pydantic V2 `@field_validator`
- [ ] `routes/search.py` 拆分 → 订阅重设计 Phase 1b 会一并解决
- [x] `routes/discover.py`（729 行）拆分 → enrich 逻辑下沉到 `discover_enrich.py`
- [x] 后端 `print()` → `logging` 模块（38 个核心文件，shared.py 统一配置 basicConfig）
