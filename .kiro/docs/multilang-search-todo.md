# [TODO] 多语言搜索词构造 — 业务 Skill 设计

> 这是一个需要单独对话深入设计的业务 skill。
> 核心问题：不同搜索源需要不同语言的搜索词，当前实现有缺陷。

---

## 问题描述

### 现状
- SSE 搜索接口新增了 `cn_name`/`en_name` 参数，按源分配搜索词
- 但前端用户手动输入关键词后，所有源会用同一个输入框的值搜索
- 发现页卡片点击搜索时，cnName/enName 传递链路不完整
- 665 个媒体库条目只有中文名，没有英文名

### 核心矛盾
- 用户在搜索框输入的是一个词（可能是中文或英文）
- 但不同源需要不同语言的搜索词：
  - Prowlarr/Bitsearch → 英文名（BT 站英文为主）
  - 磁力熊/XL720 → 中文名（国产片源）
  - Nyaa/蜜柑 → 日文原名或英文名（动画站）
  - 网盘搜索 → 中文名（国内网盘）

### 前端交互冲突
- 搜索标签（searchTags）已经有中文/英文/混合多个选项
- 但点击搜索按钮后，所有源用同一个 keyword
- 需要的是：前端传递 cn/en/original 三个维度，后端按源自动选择
- 用户手动修改搜索词时，应该只影响当前选中的标签对应的语言维度

---

## 设计要点

### 数据模型：每个媒体的三个名称维度
```
{
  cn_name: "进击的巨人",      // 中文名（豆瓣/本地）
  en_name: "Attack on Titan", // 英文名（TMDB/shadow_name）
  original_name: "進撃の巨人", // 原名（日/韩/法等，Bangumi）
}
```

### 搜索词来源优先级
1. 用户手动输入 → 覆盖对应语言维度
2. shadow_name → 英文名
3. clean_name → 中英文分离
4. TMDB/豆瓣/Bangumi 详情 → 补全缺失维度

### 各源搜索词分配
| 源 | 优先搜索词 | 回退 |
|---|---|---|
| Prowlarr | en_name | cn_name |
| Bitsearch | en_name | query |
| 磁力熊 | cn_name | query |
| XL720 | cn_name | query |
| Nyaa | original_name > en_name | query |
| 蜜柑 | cn_name > original_name | query |
| 网盘(全部) | cn_name | query |

### 前端交互方案
- 搜索标签保持现有设计（中文/英文/混合）
- 新增：搜索时自动传递 cn_name + en_name + original_name 三个参数
- 用户手动修改搜索框 → 作为 query 传递，后端用 L1 split_by_language 自动分离
- 搜索标签点击 → 更新 query，同时保持 cn_name/en_name 不变

### 回退链（后端）
1. 用指定语言搜索词搜索
2. 无结果 → 用 query 原文搜索
3. 仍无结果 → 用另一种语言搜索

---

## 关联问题

### 发现页英文名补全
- 发现页卡片的 `original_title` 需要从 TMDB 获取
- 详情页打开时请求 TMDB 详情，同时获取英文名和评分
- 英文名存入缓存，供后续搜索使用

### 媒体库英文名补全
- 665 个只有中文名的条目需要批量 TMDB 搜索补全
- 需要限频（TMDB API 限制 ~40 req/10s）
- 补全后写入 shadow_name + shadow_name_source

### 前端清洗名显示
- 前端 FolderDetail/VideoDetail 的 cnName 来自 splitByLanguage(clean_name)
- 如果 clean_name 只有中文，enName 为空
- 需要 fallback 到 shadow_name 的英文部分

---

## 待决策
- [ ] 用户手动输入搜索词时，是否自动分离中英文分别发给不同源？
- [ ] 搜索标签是否需要显示"英文搜索"/"中文搜索"/"全语言"三种模式？
- [ ] 回退链是否在 SSE 中实现（一个源无结果时自动换词重搜）？
