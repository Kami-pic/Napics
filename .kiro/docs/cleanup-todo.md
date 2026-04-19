# [TODO] 查漏补缺 — 遗留清理

> 从 2026-04-17 检查中提取的遗留工作，交给独立对话处理。
> 不阻塞搜索匹配优化，但应在下一个里程碑前完成。

---

## 1. 浏览器校验（来自 polish-todo "待新对话校验"）

> 需要用户在浏览器中实际操作验证，确认后勾掉。

- [ ] 1.1 发现页 SearchModal 搜索是否能返回结果（含直搜源）
- [ ] 1.2 订阅/探索/搜索模式的 sticky header 高度是否一致
- [ ] 1.3 探索二级 tab 刷新按钮是否正常
- [ ] 1.4 切换一级 tab 是否稳定回顶部
- [ ] 1.5 订阅日历是否显示播出时间（新订阅的剧集）
- [ ] 1.6 保存路径 placeholder 是否显示默认 NAS 路径
- [ ] 1.7 订阅配置面板是否正常弹出（质量/模式/洗版/源选择）
- [ ] 1.8 SearchModal ⚙️ 搜索源设置是否正常

## 2. 技术债务（来自 polish-todo）

- [ ] 2.1 `pan_models.py` 的 `@validator` → Pydantic V2 `@field_validator`
- [ ] 2.2 `routes/search.py`（507 行）超 400 行限制 — `_merge_bt_extra_sources` 和 SSE `_generate` 下沉到业务层
- [ ] 2.3 `routes/discover.py`（700+ 行）超 400 行限制 — `_async_enrich_tmdb_ids`、`douban_hot` 等下沉到业务层
- [ ] 2.4 后端日志从 `print()` 迁移到 `logging` 模块（统一日志级别和格式）

## 3. 匹配算法遗留（来自 discover-recommend-todo 1.10）

- [ ] 3.1 Bangumi calendar API 的 bgm_id 和卡片标题偶尔错位 — 需专项排查根因
- [ ] 3.2 中文搜 TMDB 覆盖率有限，部分冷门片搜不到 — 评估是否需要增加搜索策略

## 4. 完成后收尾

- [ ] 4.1 验证通过的项目回 polish-todo 勾掉对应条目
- [ ] 4.2 更新 devlog.md 归档
