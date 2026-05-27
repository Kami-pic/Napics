# Search Providers

本目录用于搜索类 Provider 示例。

- `example_provider.py`：公开 SDK 示例，不访问真实资源站。
- `private_pan/`：私有网盘搜索 provider，本仓库不提交。
- `private_bt/`：私有 BT 搜索 provider，本仓库不提交。

Provider 只负责获取原始候选；评分、过滤、排序、下载决策仍属于 Core。
