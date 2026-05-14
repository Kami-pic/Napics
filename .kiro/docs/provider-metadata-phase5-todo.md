# [TODO] provider-metadata-phase5-todo.md

## 范围

Phase 5：迁移 MetadataProvider。

本清单只跟踪 TMDB / 豆瓣 / Bangumi 元数据源适配，不包含 Prowlarr、BT、RSS、网盘、下载器迁移。

## 当前子任务

- [x] 新增 `backend/metadata_provider_adapter.py`，用通用 adapter 包装已有元数据客户端搜索与详情能力。
- [x] 新增 `backend/test_metadata_provider_adapter.py`，验证 adapter 满足 `MetadataProvider` 协议并输出 `MetadataCandidate` / `MetadataDetail`。
- [x] 新增 `backend/metadata_provider_factory.py`，集中现有 TMDB / 豆瓣 / Bangumi 元数据源构造函数，作为后续替换刮削调用链的兼容桥。
- [x] 新增 `backend/test_metadata_provider_factory.py`，验证 Metadata provider 清单与静态 metadata 一致。
- [x] `/api/providers` 的 metadata 分类补充 TMDB / 豆瓣 / Bangumi 静态清单。

## 暂不做

- 不修改 TMDB / 豆瓣 / Bangumi client 内部请求与 parser。
- 不改现有刮削决策逻辑。
- 不改发现推荐与探索接口。
- 不新增元数据源。
- 不改前端 provider 感知逻辑。

## 验证

- `cd backend && python -X utf8 -m pytest test_metadata_provider_adapter.py test_metadata_provider_factory.py test_provider_api.py test_provider_contracts.py`
