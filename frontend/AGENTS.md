# NAS Video Upgrader - Development Rules

## 代码结构规则
1. **单文件不超过 200 行**：超过必须拆分为独立组件
2. **前端组件化**：按功能域拆分到 `components/` 下的子目录（layout/media/manage/ai/search/settings）
3. **TypeScript 接口集中管理**：所有 interface 定义在 `types/index.ts`
4. **API 调用统一封装**：所有 `fetch` 调用通过 `lib/api.ts` 代理
5. **后端模块化**：每个功能域一个 Python 文件（scanner/searcher/downloader/ai_organizer/organize_history）

## 编码风格
- 前端：React 函数组件 + Hooks，使用 Tailwind CSS
- 后端：FastAPI + Pydantic Model
- 状态管理：优先使用 `useMemo` / `useCallback` 处理大列表性能
- 配置管理：走 `config.json` 持久化，填入即保存

## AI 友好
- 组件命名必须语义化（如 `CardGrid` 而非 `View1`）
- 每个组件文件顶部写一行注释说明用途
- Props 接口单独命名导出（如 `CardGridProps`）
