# [当前] pluginization-audit.md

> Phase 1 边界审计交付文档（索引）。
> V2 方案要求本阶段输出完整模块清单和归类，实际审计内容分散在以下四份文档中。

---

## 审计文档索引

| 文档 | 内容 | 路径 |
|---|---|---|
| PUBLIC_CORE.md | 可公开核心能力清单（低/中/高风险分级） | `.kiro/docs/PUBLIC_CORE.md` |
| PLUGIN_BOUNDARY.md | Provider 契约与依赖边界设计 | `.kiro/docs/PLUGIN_BOUNDARY.md` |
| PRIVATE_PROVIDERS.md | 私有 provider 清单（BT/RSS/网盘/下载/元数据） | `.kiro/docs/PRIVATE_PROVIDERS.md` |
| FRONTEND_PROVIDER_HARDCODE.md | 前端硬编码 provider 清单与改造建议 | `.kiro/docs/FRONTEND_PROVIDER_HARDCODE.md` |

## 审计覆盖范围

- ✅ 当前搜索源清单（BT 13 源 + Prowlarr）
- ✅ 当前网盘搜索源清单（9 源）
- ✅ 当前 RSS 源清单（8 源）
- ✅ 当前元数据源清单（TMDB / 豆瓣 / Bangumi）
- ✅ 当前下载器清单（qBittorrent / OpenList）
- ✅ 当前云盘/存储源清单（OpenList Storage / 夸克转存）
- ✅ 当前 `shared.py` 依赖清单（见 PLUGIN_BOUNDARY.md 耦合点表）
- ✅ 当前前端硬编码 provider 清单（见 FRONTEND_PROVIDER_HARDCODE.md）
- ✅ 当前可验证测试命令（各 Phase TODO 中记录）
- ✅ 当前 PC 自用环境启动方式（start.bat / stop.bat）

## 验收状态

Phase 1 审计交付完成。所有模块已归类为 Core / Plugin / Private 三层，每个源都有风险等级和建议去向。
