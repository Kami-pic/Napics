---
inclusion: fileMatch
fileMatchPattern: "**/organizer.py,**/analyzer.py,**/scraper.py,**/file_relocator.py"
---

# 整理流水线规范

修改整理相关代码前，必须先阅读 `.kiro/knowledge/organize-pipeline-v3.md` 了解 V3 流水线的完整设计。

核心原则：
- 先问后做：物理结构与逻辑确权完全解耦，NFO 是唯一真理
- 执行顺序：Step 0 散装封装 → Step 1 旧刮削处理 → Step 2 分析判定 → Step 3 刮削确权 → Step 4 结构归位 → Step 5 影子名生成
- 没有 NFO 的文件完全不动
- folder_type 和 category_hint 只判定一次，全程传递
