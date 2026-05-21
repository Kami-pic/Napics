# [TODO] 插件生态与商业化

> 插件分发体系 + 社区贡献机制 + 付费插件商业化。

---

## 产品架构

```
┌─────────────────────────────────────────────────────┐
│  napics（主仓库，开源 MIT，主账号）                    │
│  Core + 插件框架 + SDK + 免费内置插件                 │
└─────────────────────────────────────────────────────┘
         │                          │
         ▼                          ▼
┌─────────────────────┐   ┌─────────────────────────┐
│ napics-community-   │   │ napics-pro（私有仓库，   │
│ plugins             │   │ 闭源，主账号）            │
│ （另一个账号，开源） │   │ 付费插件源代码           │
│ 灰色插件（BT/网盘/  │   │ AI 增强 / 自动化 /      │
│ RSS 源）            │   │ 智能订阅 / 分析报告      │
└─────────────────────┘   └─────────────────────────┘
```

### 三层仓库

| 仓库 | 账号 | 开源 | 内容 | 风险 |
|------|------|------|------|------|
| `napics` | 主账号 | MIT | Core + 框架 + 低风险插件 | 🟢 无 |
| `napics-community-plugins` | 小号 | MIT | BT 直搜/网盘搜/RSS 源 | 🔴 隔离 |
| `napics-pro` | 主账号 | 闭源 | 付费插件 | 🟢 合法商业软件 |

---

## 主仓库预装插件（免费）

| 插件 ID | 说明 | 理由 |
|---------|------|------|
| metadata-tmdb | TMDB 元数据 | 合法 API，核心体验 |
| metadata-bangumi | Bangumi 元数据 | 合法 API，动画用户需要 |
| feature-completeness | 季集完整性检测 | 纯本地计算 |
| feature-discover | 发现推荐 | 合法数据源 |
| feature-local-match | 本地媒体感知 | 纯本地 |
| download-qbittorrent | qB 对接 | 工具本身合法 |

### 外部社区插件（灰色，另一个账号）

| 插件 ID | 说明 |
|---------|------|
| search-bt-direct | 12 个 BT 直搜源 |
| search-pan | 网盘搜索聚合 |
| search-prowlarr | Prowlarr 对接 |
| metadata-douban | 豆瓣元数据（逆向） |
| rss-anime | 动画 RSS 源包 |
| rss-tv-movie | 影视 RSS 源包 |
| download-openlist | OpenList/Alist 对接 |
| feature-subscribe | 订阅追更 |
| storage-openlist | 网盘挂载浏览 |

### 付费插件（闭源）

| 插件 ID | 名称 | 卖点 |
|---------|------|------|
| napics-pro-ai | AI 智能整理 | 方案生成+自动执行+学习偏好 |
| napics-pro-automation | 全链路自动化 | 监控→整理→归位→通知 |
| napics-pro-subscribe | 智能订阅 | 洗版决策+质量升级+日历 |
| napics-pro-analytics | 媒体库分析 | 健康报告+存储优化建议 |

---

## 付费机制

### License Key 验证

- 用户购买 → 获得 License Key → 设置中填入 → 解锁付费插件源
- 下载时验证 Key，下载后本地运行不再验证（离线友好）
- 验证服务：LemonSqueezy / Gumroad / 自建（初期用第三方，零运维）

### 定价（参考）

- 一次性买断 ¥99-199（含 1 年更新）
- 或年订阅 ¥49-99
- 早鸟/赞助者终身授权

---

## 执行计划

### Phase 1：外部插件源加载（核心能力）

- [x] 定义插件源 `index.json` 规范
- [x] 后端：`config.json` 新增 `plugin_sources: [{name, url}]` 字段
- [x] 后端：新增 API
  - `GET /api/plugins/sources` — 已添加的插件源列表
  - `POST /api/plugins/sources` — 添加插件源
  - `DELETE /api/plugins/sources` — 移除插件源
  - `GET /api/plugins/sources/plugins` — 拉取远程插件列表
  - `POST /api/plugins/install-remote` — 下载并安装远程插件
- [x] 后端：插件下载逻辑（下载 zip → 解压到 plugins/ → 校验 manifest → 注册）
- [x] 前端：插件中心"内置/第三方"Tab 切换
- [x] 前端：插件中心"添加插件源"按钮 + 输入 URL 弹窗
- [x] 前端：远程插件在列表中显示（区分来源标签）
- [x] 安装第三方插件时弹安全警告

### Phase 2：高风险插件迁出主仓库

#### Phase 2a：BT 直搜 + 网盘搜索（最高风险）

- [x] 创建社区插件仓库目录结构（search-bt-direct / search-pan）
- [x] BT 直搜源：12 个 scraper 打包 + __init__.py 自注册
- [x] 网盘搜索源：9 个 scraper 打包 + __init__.py 自注册
- [x] 生成 index.json（插件源清单）
- [x] 生成 zip 包并通过端到端测试
- [x] 推送到 `icatmiumiu/plugins-of-napics` 仓库
- [x] 创建 GitHub Release v1.0.0 并上传 zip 包
- [x] 验证：主仓库添加社区源 → 拉取 index.json → 解析成功
- [x] 验证：下载 zip → 解压 → manifest 加载 → 12 个源文件就位
- [x] 验证：插件注册 → 12 个 BT provider 注册成功
- [x] 验证：卸载插件 → provider 注销 → Core 降级正常
- [ ] 主仓库删除 bt_scraper_*.py 和 pan_scraper_*.py（git 历史可回溯）

#### Phase 2b：Prowlarr + RSS + 豆瓣 + OpenList + subscribe

- [ ] 迁出 search-prowlarr
- [ ] 迁出 rss-anime / rss-tv-movie
- [ ] 迁出 metadata-douban
- [ ] 迁出 download-openlist / storage-openlist
- [ ] 迁出 feature-subscribe
- [ ] 更新 index.json
- [ ] 验证全流程

### Phase 3：插件 SDK 发布

- [ ] 将 `provider_contracts.py` + `provider_models.py` + `provider_context.py` 打包为 `napics-plugin-sdk`
- [ ] 发布到 PyPI
- [ ] 创建 `napics-plugin-template` 模板仓库（GitHub Template）
- [ ] 完善 PLUGIN_DEV_GUIDE.md：补充 Metadata / RSS / Download 类型示例
- [ ] README 中添加"开发你自己的插件"引导

### Phase 4：付费插件基础设施

- [ ] 后端：支持带 License Key 的插件源（请求 index.json 时带 auth header）
- [ ] 后端：License Key 配置项（设置页）
- [ ] 前端：设置页 License Key 输入 + 验证状态显示
- [ ] 创建 `napics-pro` 私有仓库
- [ ] 接入支付平台（LemonSqueezy / Gumroad）
- [ ] 第一个付费插件上线（napics-pro-ai 或 napics-pro-automation）

### Phase 5：生态完善（后续）

- [ ] 插件版本管理（检测更新 + 一键升级）
- [ ] 插件评分/评论（如果用户量够）
- [ ] 插件权限声明（manifest 中声明网络/文件系统访问）
- [ ] 官方推荐插件列表（主仓库 README 中引导）

---

## 插件源 index.json 规范（草案）

```json
{
  "name": "napics-community-plugins",
  "version": "1.0.0",
  "description": "Napics 社区插件源",
  "homepage": "https://github.com/xxx/napics-community-plugins",
  "plugins": [
    {
      "id": "search-bt-direct",
      "name": "BT 直搜源包",
      "version": "1.0.0",
      "description": "12 个 BT 直搜源（Bitsearch/Nyaa/蜜柑等）",
      "category": "search",
      "icon": "🔍",
      "risk_level": "high",
      "depends_on": [],
      "download_url": "https://github.com/xxx/napics-community-plugins/releases/download/v1.0.0/search-bt-direct.zip",
      "sha256": "abc123...",
      "min_napics_version": "1.0.0"
    }
  ]
}
```

---

## 约束

- Phase 1 完成前不做 Phase 2（先有加载能力，再迁出代码）
- 付费插件的接口和免费插件完全一致，不做特殊 API
- 不做运行时 License 验证（离线友好）
- 不做 Python 沙箱（不现实），靠安全警告 + 社区信任
- 插件源 URL 支持 GitHub raw / Releases / 任意 HTTPS 地址

---

## 验收标准

- [ ] 用户首次启动：Core + 预装插件可用，无灰色代码
- [ ] 用户添加社区源后：能看到并安装 BT 搜索等插件
- [ ] 社区开发者：pip install napics-plugin-sdk → 按模板开发 → 发布到自己的源 → 用户能安装
- [ ] 付费用户：填入 License Key → 解锁付费插件源 → 安装 Pro 插件
