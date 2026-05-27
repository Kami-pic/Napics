# 贡献指南

感谢你对 Napics 的关注！欢迎提交 Issue 和 Pull Request。

---

## 报告 Bug

请使用 [Bug Report 模板](https://github.com/Kami-pic/napics/issues/new?template=bug_report.md) 提交，包含：

- 复现步骤
- 期望行为 vs 实际行为
- 运行环境（OS、Python 版本、Node 版本）
- 相关日志或截图

---

## 功能建议

请使用 [Feature Request 模板](https://github.com/Kami-pic/napics/issues/new?template=feature_request.md) 提交。

---

## 提交 Pull Request

### 开发环境

```bash
# 后端
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8000

# 前端
cd frontend
npm install
npm run dev

# 测试
cd backend && python -X utf8 -m pytest tests/
cd frontend && npx vitest --run
```

### 代码规范

- Python：snake_case，类型注解，中文注释
- 前端：PascalCase 组件，Tailwind CSS，TypeScript
- 前端单文件不超过 300 行，后端路由不超过 400 行
- 所有外部服务凭据走 `backend/config.json`，不允许硬编码

### Commit 规范

中文多行格式：

```
类型: 简要描述

- 变更要点 1
- 变更要点 2
```

类型包括：`feat` / `fix` / `refactor` / `docs` / `chore` / `test`

### PR 要求

- 一个 PR 只做一件事
- 后端改动需附带测试或说明测试方式
- 前端改动需确认无 TypeScript 报错
- 不要提交 `node_modules`、`__pycache__`、`.next`、`venv` 等

---

## 插件开发

如果你想开发第三方插件，请参考 [插件开发指南](backend/plugins/PLUGIN_DEV_GUIDE.md)。

---

## 行为准则

- 友善沟通，尊重他人
- 聚焦技术讨论，避免无关争论
- 不提交包含恶意代码或侵权内容的 PR
