# [TODO] provider-rss-phase4-todo.md

## 范围

Phase 4：迁移 RSS 源为 `RSSProvider`。

本清单只跟踪 RSS 源适配，不包含 Prowlarr 搜索迁移、BT 直搜、网盘、下载器迁移。

## 当前子任务

- [x] 新增 `backend/rss_provider_adapter.py`，用通用 adapter 包装已有 `RSSSourceBase.fetch()`。
- [x] 新增 `backend/test_rss_provider_adapter.py`，验证 adapter 满足 `RSSProvider` 协议并输出 `RSSCandidate`。
- [x] 新增 `backend/rss_provider_factory.py`，集中现有 RSS source 构造函数，作为后续替换 `routes/subscribe.py` 注册逻辑的兼容桥。
- [x] 新增 `backend/test_rss_provider_factory.py`，验证 RSS provider 清单与静态 metadata 一致。
- [x] `routes/subscribe.py` 的 RSS 源注册链路改为从 `rss_provider_factory.py` 获取 source factory，注册到旧 `RSSSourceManager` 的行为保持兼容。

## 暂不做

- 不修改 `rss_source_*` 内部 parser。
- 不改订阅轮询策略。
- 不改订阅匹配逻辑。
- 不改自动下载逻辑。
- 不改 `RSSSourceManager` 的数据结构和调用协议。

## 验证

- `cd backend && python -X utf8 -m pytest test_subscribe_rss_provider_bridge.py test_rss_provider_adapter.py test_rss_provider_factory.py test_rss_engine.py test_rss_engine_phase2a.py`
