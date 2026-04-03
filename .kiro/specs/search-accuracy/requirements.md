# 需求文档：搜索匹配准确性提升 (search-accuracy)

## 简介

本需求文档定义了 NAS 影视媒体库管理工具在搜索匹配准确性方面的功能需求。系统当前以中文影片为主，但 TMDB 和 Prowlarr 以英文为主要搜索源，导致中文标题与 TMDB 翻译名不一致时匹配失败率偏高。本功能通过引入影子名机制、增强 TMDB 匹配算法、优化 Prowlarr 搜索策略、建立匹配置信度体系四个维度进行改进，全面提升刮削匹配、发现页识别和 BT 资源搜索的准确性。

## 术语表

- **系统 (System)**：NAS 影视媒体库管理工具的后端服务
- **影子名 (Shadow_Name)**：存储在媒体库 JSON 中的隐藏标准化名称，不修改实际文件名，所有搜索/刮削/匹配优先使用该名称
- **影子名管理器 (Shadow_Name_Manager)**：负责影子名读写、批量生成和搜索名称获取的后端组件
- **别名解析器 (Alias_Resolver)**：从豆瓣、Bangumi、NFO 等多数据源收集影片所有已知名称变体的组件
- **别名集合 (Alias_Set)**：包含中文名、英文名、日文名变体的数据结构
- **增强评分器 (Enhanced_Scorer)**：对 TMDB 候选结果进行多维度评分并输出置信度等级的组件
- **匹配置信度 (Match_Confidence)**：反映匹配质量的三级体系，包含高（high）、中（medium）、低（low）三个等级
- **索引器优先级管理器 (Indexer_Priority_Manager)**：管理 Prowlarr 索引器优先级配置的组件
- **搜索词构造器 (Search_Query_Builder)**：根据影片信息和别名构造多个搜索词变体的组件
- **TMDB**：The Movie Database，影视元数据 API 服务
- **Prowlarr**：BT 索引器聚合搜索服务
- **NFO**：Kodi/Jellyfin/Emby 兼容的影视元数据 XML 文件
- **文本标准化 (Normalize_Text)**：将字符串进行全角转半角、去标点空格、转小写的处理函数

## 需求

### 需求 1：影子名存储与管理

**用户故事：** 作为媒体库用户，我希望系统为每个媒体项维护一个隐藏的标准化名称（影子名），以便在不修改实际文件名的情况下提升搜索和匹配的准确性。

#### 验收标准

1. WHEN 用户通过 API 为指定媒体项设置影子名 THEN Shadow_Name_Manager SHALL 将影子名、来源标记和关联 TMDB ID 持久化到 media_library.json 对应条目中
2. WHEN 用户设置影子名且来源为 "manual" THEN Shadow_Name_Manager SHALL 将该影子名标记为手动设置，后续自动填充操作不覆盖该值
3. WHEN 系统自动填充影子名且该媒体项已有来源为 "manual" 的影子名 THEN Shadow_Name_Manager SHALL 跳过填充并返回 False
4. WHEN 系统自动填充影子名且该媒体项没有手动设置的影子名 THEN Shadow_Name_Manager SHALL 写入影子名并返回 True
5. WHEN 用户清除指定媒体项的影子名 THEN Shadow_Name_Manager SHALL 移除该条目的 shadow_name、shadow_name_source 和 shadow_tmdb_id 字段
6. WHEN 调用 get_search_name 且该媒体项有影子名 THEN Shadow_Name_Manager SHALL 返回影子名
7. WHEN 调用 get_search_name 且该媒体项没有影子名 THEN Shadow_Name_Manager SHALL 返回原始文件名

### 需求 2：影子名自动填充

**用户故事：** 作为媒体库用户，我希望系统在刮削成功、扫描发现 NFO、或发现页入库时自动生成影子名，以便减少手动操作。

#### 验收标准

1. WHEN TMDB 刮削成功且匹配置信度为 "high" 或 "medium" THEN 系统 SHALL 使用 TMDB 返回的 original_title 加年份格式自动填充影子名，来源标记为 "tmdb"
2. WHEN 扫描媒体库时发现文件夹下存在 NFO 文件且 NFO 包含 originaltitle 字段 THEN 系统 SHALL 从 NFO 提取 originaltitle 自动填充影子名，来源标记为 "nfo"
3. WHEN 用户触发批量生成影子名操作 THEN Shadow_Name_Manager SHALL 遍历所有已刮削的媒体项，为每个没有手动影子名的条目生成影子名，并返回生成数、跳过数和失败数的统计

### 需求 3：影子名前端交互

**用户故事：** 作为媒体库用户，我希望在详情面板中查看和编辑影子名，以便在自动匹配不准确时手动干预。

#### 验收标准

1. WHEN 用户打开媒体项的详情面板 THEN 系统 SHALL 显示影子名编辑入口，包含当前影子名文本和来源标签（如 "TMDB"、"手动"）
2. WHEN 用户在详情面板中编辑并保存影子名 THEN 系统 SHALL 调用后端 API 将影子名以 "manual" 来源保存
3. WHEN 媒体项有影子名且用户打开搜索升级弹窗 THEN 系统 SHALL 在搜索框中默认填入影子名而非原始文件名

### 需求 4：多源别名解析

**用户故事：** 作为媒体库用户，我希望系统从豆瓣、Bangumi、NFO 等多个数据源收集影片的所有已知名称变体，以便为搜索提供更丰富的关键词。

#### 验收标准

1. WHEN Alias_Resolver 接收到非空标题进行别名解析 THEN Alias_Resolver SHALL 返回的 Alias_Set 中 cn_names 列表至少包含原始标题
2. WHEN Alias_Resolver 从豆瓣搜索建议中获取到 subtitle（外文名/别名）THEN Alias_Resolver SHALL 将这些名称添加到 Alias_Set 的对应语言列表中
3. WHEN Alias_Resolver 从 Bangumi 搜索中获取到 original_title THEN Alias_Resolver SHALL 将该名称添加到 Alias_Set 的 jp_names 列表中
4. WHEN Alias_Resolver 对同一标题进行重复解析 THEN Alias_Resolver SHALL 从缓存返回结果，不发起新的外部 API 请求
5. IF 豆瓣或 Bangumi API 不可用 THEN Alias_Resolver SHALL 跳过该数据源并使用其余可用数据源的结果继续解析

### 需求 5：增强 TMDB 匹配评分

**用户故事：** 作为媒体库用户，我希望系统使用多维度评分算法对 TMDB 候选结果进行匹配，以便提高刮削匹配的准确率。

#### 验收标准

1. WHEN Enhanced_Scorer 对候选项进行评分 THEN Enhanced_Scorer SHALL 从精确匹配（最高 100 分）、模糊匹配、前缀匹配、包含匹配、别名交叉验证（+15~25 分）、年份匹配（+20 分）和热度（最高 +10 分）多个维度计算综合分数
2. WHEN 候选项的标准化标题与查询词完全相同 THEN Enhanced_Scorer SHALL 给予该维度 100 分（精确匹配）
3. WHEN 候选项的标准化标题与查询词的模糊相似度 >= 0.85 THEN Enhanced_Scorer SHALL 给予模糊匹配加分
4. WHEN 候选项的年份与目标年份相同 THEN Enhanced_Scorer SHALL 加 20 分；WHEN 年份差值超过 1 年 THEN Enhanced_Scorer SHALL 减 30 分
5. WHEN 综合分数 >= 80 THEN Enhanced_Scorer SHALL 将置信度设为 "high"；WHEN 分数在 50 到 79 之间 THEN Enhanced_Scorer SHALL 将置信度设为 "medium"；WHEN 分数 < 50 THEN Enhanced_Scorer SHALL 将置信度设为 "low"

### 需求 6：模糊匹配算法

**用户故事：** 作为媒体库用户，我希望系统能够处理标题中的细微差异（如拼写变体、标点差异），以便在标题不完全一致时仍能匹配成功。

#### 验收标准

1. THE Enhanced_Scorer SHALL 使用基于 Levenshtein 编辑距离的模糊匹配算法，返回 0.0 到 1.0 之间的相似度分数
2. WHEN 两个字符串完全相同 THEN Enhanced_Scorer 的模糊匹配 SHALL 返回 1.0
3. WHEN 两个字符串的长度差异超过较长字符串长度的 50% THEN Enhanced_Scorer 的模糊匹配 SHALL 返回 0.0
4. WHEN 计算两个字符串的模糊匹配分数 THEN Enhanced_Scorer SHALL 保证 fuzzy_score(a, b) 等于 fuzzy_score(b, a)

### 需求 7：文本标准化

**用户故事：** 作为媒体库用户，我希望系统在匹配前对文本进行标准化处理，以便消除全角/半角、大小写、标点等差异对匹配结果的影响。

#### 验收标准

1. THE Normalize_Text 函数 SHALL 将全角字符转换为对应的半角字符
2. THE Normalize_Text 函数 SHALL 移除所有标点符号、空格和特殊符号
3. THE Normalize_Text 函数 SHALL 将所有字母转换为小写
4. WHEN 对同一字符串连续执行两次标准化 THEN Normalize_Text 函数 SHALL 产生与执行一次相同的结果（幂等性）

### 需求 8：搜索词构造

**用户故事：** 作为媒体库用户，我希望系统根据影片信息和别名自动构造多个搜索词变体，以便提高 TMDB 和 BT 搜索的命中率。

#### 验收标准

1. WHEN Search_Query_Builder 为非空标题构造 TMDB 搜索词列表 THEN Search_Query_Builder SHALL 返回非空列表，至少包含原始标题
2. WHEN Search_Query_Builder 构造 TMDB 搜索词列表 THEN Search_Query_Builder SHALL 按搜索成功概率降序排列，列表长度不超过 6 个，且无重复项
3. WHEN Search_Query_Builder 构造 BT 搜索词列表 THEN Search_Query_Builder SHALL 优先使用英文名加年份的组合，并包含原始标题作为备选
4. WHEN 标题包含副标题（如冒号分隔的内容）THEN Search_Query_Builder SHALL 生成去除副标题的简化版本作为额外搜索词

### 需求 9：增强 TMDB 刮削流程

**用户故事：** 作为媒体库用户，我希望系统在刮削时优先使用影子名、收集多源别名、使用增强评分，以便显著提升中文影片的刮削成功率。

#### 验收标准

1. WHEN 触发文件名刮削且该媒体项有影子名 THEN 系统 SHALL 优先使用影子名作为搜索关键词
2. WHEN 触发文件名刮削 THEN 系统 SHALL 通过 Alias_Resolver 收集别名，通过 Search_Query_Builder 构造搜索词列表，对每个搜索词执行 TMDB 搜索并收集所有候选项
3. WHEN 收集到 TMDB 候选项 THEN 系统 SHALL 使用 Enhanced_Scorer 对所有候选项进行评分，选出最佳匹配
4. WHEN 多个搜索词返回相同 TMDB ID 的候选项 THEN 系统 SHALL 对候选项按 TMDB ID 去重，每个 ID 只保留一个条目
5. IF 所有搜索词均无匹配结果 THEN 系统 SHALL 返回置信度为 "low" 的空结果

### 需求 10：匹配置信度前端展示

**用户故事：** 作为媒体库用户，我希望在刮削结果中看到匹配置信度，以便在低置信度时手动选择正确的匹配。

#### 验收标准

1. WHEN 刮削结果的置信度为 "low" THEN 系统 SHALL 在前端显示候选列表供用户手动选择
2. WHEN 刮削结果的置信度为 "medium" THEN 系统 SHALL 在前端显示匹配结果和确认按钮，附带评分依据说明
3. WHEN 刮削结果的置信度为 "high" THEN 系统 SHALL 自动采用匹配结果，无需用户确认

### 需求 11：Prowlarr 索引器优先级管理

**用户故事：** 作为媒体库用户，我希望配置 Prowlarr 索引器的优先级，以便按内容类型调整搜索策略。

#### 验收标准

1. WHEN 用户通过设置页配置索引器优先级 THEN Indexer_Priority_Manager SHALL 将优先级（0-100）、启用状态和偏好类型持久化到 config.json
2. WHEN 请求按优先级排序的索引器列表 THEN Indexer_Priority_Manager SHALL 返回按 priority 字段降序排列的列表
3. WHEN 请求特定媒体类型的索引器列表 THEN Indexer_Priority_Manager SHALL 过滤出 preferred_types 包含该类型或 preferred_types 为空的索引器

### 需求 12：Prowlarr 增强搜索

**用户故事：** 作为媒体库用户，我希望系统使用多关键词搜索和综合排序来优化 Prowlarr BT 资源搜索，以便找到更相关、更高质量的资源。

#### 验收标准

1. WHEN 执行增强搜索 THEN 系统 SHALL 使用 Search_Query_Builder 构造的搜索词列表（最多 3 个）依次搜索 Prowlarr
2. WHEN 多个搜索词返回相同 download_url 的结果 THEN 系统 SHALL 按 download_url 去重，每个 URL 只保留一个条目
3. WHEN 对搜索结果进行排序 THEN 系统 SHALL 按综合评分降序排列，综合评分由质量等级（权重 0.4）、做种数（权重 0.3）、索引器权重（权重 0.15）和标题匹配度（权重 0.15）组成
4. IF 部分索引器超时或返回错误 THEN 系统 SHALL 跳过失败的索引器，使用其余索引器的结果继续搜索

### 需求 13：错误处理与降级

**用户故事：** 作为媒体库用户，我希望系统在外部 API 不可用时能够优雅降级，以便核心功能不完全中断。

#### 验收标准

1. IF TMDB API 请求超时或返回错误 THEN 系统 SHALL 降级使用豆瓣和 Bangumi 数据源及已有缓存
2. IF 豆瓣别名解析失败 THEN 系统 SHALL 跳过豆瓣别名，使用 Bangumi 和 NFO 数据继续处理
3. IF 所有搜索词在 TMDB 均返回空结果 THEN 系统 SHALL 返回置信度为 "low" 的空结果，前端提示用户手动搜索
