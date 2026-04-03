# 需求文档：搜索增强 (search-enhance)

## 简介

本需求文档定义了 NAS 影视媒体库管理工具的搜索增强功能。当前系统仅支持通过 Prowlarr 搜索 BT/磁力资源并由 qBittorrent 下载，本功能将搜索能力扩展为双通道：网盘搜索（rrdynb + ddys + PanSou → Alist 转存）和 BT/磁力直搜补充（磁力熊）。搜索弹窗改造为 Tab 切换模式，网盘 Tab 展示按网盘类型分组的资源卡片并支持一键转存，BT/磁力 Tab 在现有 Prowlarr 基础上补充磁力熊直搜源。同时新增爬虫基础设施、Alist 挂载状态检查与转存链路、搜索源与网盘优先级配置等能力。

## 术语表

- **系统 (System)**：NAS 影视媒体库管理工具的后端服务（Python FastAPI）
- **搜索弹窗 (Search_Modal)**：前端搜索资源弹窗组件（SearchModal.tsx）
- **爬虫基础设施 (Scraper_Base)**：后端 scraper_base.py，提供请求间隔控制、指数退避重试、UA 轮换、结果缓存、代理池等通用爬虫能力
- **网盘爬虫 (Pan_Scraper)**：基于 Scraper_Base 的网盘资源爬虫，包括 rrdynb、ddys、PanSou 三个源
- **人人电影网爬虫 (Rrdynb_Scraper)**：针对 rrdynb.com（帝国 CMS）的爬虫，反爬较弱，使用 requests + BeautifulSoup
- **低端影视爬虫 (Ddys_Scraper)**：针对 ddys.io 的爬虫，反爬较强，可能需要 cloudscraper 或 playwright
- **PanSou 客户端 (PanSou_Client)**：对接 PanSou API 的客户端，作为网盘搜索兜底源
- **磁力熊爬虫 (Cilixiong_Scraper)**：针对 cilixiong.org 的磁力链接爬虫
- **网盘搜索结果 (Pan_Result)**：统一的网盘搜索结果数据结构，包含 title、pan_type、share_url、password、source 字段
- **Alist 管理器 (Alist_Manager)**：后端 downloader.py 中已有的 Alist 对接模块，本功能扩展其挂载检查和转存能力
- **挂载状态 (Mount_Status)**：Alist 中各网盘的挂载状态信息，包含网盘类型、驱动名称、挂载路径
- **转存任务 (Transfer_Task)**：通过 Alist 将网盘分享链接转存到指定路径的任务
- **下载管理器 (Download_Manager)**：后端 download_manager.py，管理下载/转存任务队列
- **敏感词过滤器 (Content_Filter)**：后端过滤不合适搜索结果的组件
- **网盘类型 (Pan_Type)**：支持的网盘类型枚举：quark（夸克）、aliyun（阿里）、baidu（百度）、pan115（115）、pikpak（PikPak）
- **Alist**：网盘管理服务（localhost:5244），已挂载夸克/阿里/百度/115/PikPak
- **Prowlarr**：BT 索引器聚合搜索服务（localhost:9696）
- **qBittorrent**：BT 下载客户端（localhost:8080）

## 需求

### 需求 1：爬虫基础设施

**用户故事：** 作为媒体库用户，我希望系统具备通用的爬虫基础设施，以便各网盘爬虫和磁力爬虫能安全、稳定地抓取资源信息。

#### 验收标准

1. THE Scraper_Base SHALL 在每次 HTTP 请求之间插入 1 到 2 秒的随机延迟，避免触发目标站点的频率限制
2. WHEN 目标站点返回 429（Too Many Requests）、503（Service Unavailable）或请求超时 THEN Scraper_Base SHALL 执行指数退避重试，最多重试 3 次，退避间隔依次为 2 秒、4 秒、8 秒
3. THE Scraper_Base SHALL 维护一个包含 10 个以上常见浏览器 User-Agent 字符串的轮换池，每次请求随机选取一个 UA
4. THE Scraper_Base SHALL 提供按搜索关键词缓存结果的能力，缓存 TTL 为 5 分钟，TTL 内相同关键词直接返回缓存结果
5. WHERE 用户配置了代理池地址 THEN Scraper_Base SHALL 通过配置的代理发送请求
6. WHERE 用户未配置代理池 THEN Scraper_Base SHALL 直接发送请求，不使用代理
7. THE Content_Filter SHALL 根据敏感词列表过滤搜索结果，命中敏感词的结果不返回给前端

### 需求 2：人人电影网爬虫

**用户故事：** 作为媒体库用户，我希望系统能从人人电影网（rrdynb.com）搜索并提取网盘分享链接，以便获取网盘资源。

#### 验收标准

1. WHEN 用户输入搜索关键词 THEN Rrdynb_Scraper SHALL 通过帝国 CMS POST 表单接口向 rrdynb.com 发起搜索请求
2. WHEN rrdynb.com 返回搜索结果页 THEN Rrdynb_Scraper SHALL 解析出每条结果的标题、详情页 URL 和年份信息
3. WHEN Rrdynb_Scraper 访问详情页 THEN Rrdynb_Scraper SHALL 通过正则匹配提取网盘分享链接（share_url）和提取码（password），share_url 和 password 必须配对提取
4. WHEN Rrdynb_Scraper 提取完成 THEN Rrdynb_Scraper SHALL 输出统一格式的 Pan_Result 列表，每条包含 title、pan_type、share_url、password、source 字段
5. WHEN 详情页中包含多个不同网盘类型的链接 THEN Rrdynb_Scraper SHALL 分别提取每个链接并生成独立的 Pan_Result 条目
6. IF 详情页中未找到任何网盘链接 THEN Rrdynb_Scraper SHALL 跳过该条目并继续处理下一条搜索结果

### 需求 3：低端影视爬虫

**用户故事：** 作为媒体库用户，我希望系统能从低端影视（ddys.io）搜索并提取网盘分享链接，以便获取更多网盘资源来源。

#### 验收标准

1. WHEN 用户输入搜索关键词 THEN Ddys_Scraper SHALL 向 ddys.io 发起搜索请求，处理可能存在的 Cookie 验证或 JS 挑战
2. WHEN ddys.io 返回搜索结果页 THEN Ddys_Scraper SHALL 解析出每条结果的标题和详情页 URL
3. WHEN Ddys_Scraper 访问详情页 THEN Ddys_Scraper SHALL 还原混淆的网盘 URL 并提取分享链接和提取码
4. WHEN Ddys_Scraper 提取完成 THEN Ddys_Scraper SHALL 输出统一格式的 Pan_Result 列表
5. IF requests 库无法绕过 ddys.io 的反爬机制 THEN Ddys_Scraper SHALL 降级使用 cloudscraper 或 playwright 进行请求
6. IF ddys.io 完全不可访问 THEN Ddys_Scraper SHALL 返回空结果并记录错误日志，不影响其他搜索源的正常运行

### 需求 4：PanSou API 集成

**用户故事：** 作为媒体库用户，我希望系统能对接 PanSou API 作为网盘搜索的兜底源，以便在其他爬虫源无结果时仍有资源可用。

#### 验收标准

1. WHEN 用户输入搜索关键词 THEN PanSou_Client SHALL 调用 PanSou 的 `/api/search` 接口进行搜索
2. WHEN PanSou 返回搜索结果 THEN PanSou_Client SHALL 按目标网盘类型（quark/aliyun/baidu/pan115/pikpak）过滤结果
3. WHEN PanSou_Client 处理完成 THEN PanSou_Client SHALL 输出统一格式的 Pan_Result 列表
4. THE Content_Filter SHALL 对 PanSou 返回的结果执行敏感词过滤
5. IF PanSou API 地址未配置 THEN PanSou_Client SHALL 跳过搜索并返回空结果

### 需求 5：网盘搜索 API

**用户故事：** 作为媒体库用户，我希望系统提供统一的网盘搜索 API，以便前端通过一个接口获取所有网盘源的聚合搜索结果。

#### 验收标准

1. WHEN 前端调用 `/search/pan` 接口 THEN 系统 SHALL 并发调用所有已启用的网盘搜索源（rrdynb、ddys、pansou）
2. WHEN 多个搜索源返回结果 THEN 系统 SHALL 按 share_url 对结果进行去重，相同 share_url 只保留一条
3. WHEN 去重完成后 THEN 系统 SHALL 按网盘类型对结果分组，分组顺序为：夸克 > 阿里 > 115 > PikPak > 百度
4. WHEN 某个网盘类型在 Alist 中未挂载 THEN 系统 SHALL 在该类型的结果中标记 `mounted: false`
5. IF 某个搜索源超时或返回错误 THEN 系统 SHALL 跳过该源并使用其余源的结果继续聚合，不阻塞整体搜索
6. WHEN `/search/pan` 返回结果 THEN 系统 SHALL 在响应中包含每个搜索源的状态（成功/失败/禁用）和结果数量

### 需求 6：Alist 挂载状态检查

**用户故事：** 作为媒体库用户，我希望系统能自动检测 Alist 中已挂载的网盘列表，以便在搜索结果中区分可转存和不可转存的资源。

#### 验收标准

1. WHEN 后端服务启动时 THEN Alist_Manager SHALL 查询 Alist 已挂载的存储列表并缓存结果
2. THE Alist_Manager SHALL 每 5 分钟定时刷新已挂载存储列表的缓存
3. THE Alist_Manager SHALL 建立 pan_type 到 Alist 驱动的映射关系（quark→Quark/夸克、aliyun→AliyundriveOpen/阿里、baidu→BaiduNetdisk/百度、pan115→115 Cloud/115、pikpak→PikPak）
4. WHEN 前端调用 `/alist/mounts` 接口 THEN 系统 SHALL 返回当前已挂载的网盘类型列表及其挂载路径
5. WHEN 搜索结果中某条资源的 pan_type 对应的网盘在 Alist 中未挂载 THEN 系统 SHALL 在该结果中标记 `mounted: false`

### 需求 7：Alist 转存链路

**用户故事：** 作为媒体库用户，我希望能将搜索到的网盘分享链接通过 Alist 一键转存到 NAS，以便快速获取网盘资源。

#### 验收标准

1. WHEN 用户点击转存按钮 THEN 系统 SHALL 将 share_url 和 password 提交给 Alist 执行离线下载/转存操作
2. WHEN 转存的目标网盘与分享链接的网盘类型相同（同盘转存）THEN 系统 SHALL 标记该任务为"秒传"类型，预期快速完成
3. WHEN 转存的目标网盘与分享链接的网盘类型不同（跨盘转存）THEN 系统 SHALL 标记该任务为"异步离线"类型，通过 Alist 离线下载通道处理
4. WHEN Alist 返回转存错误 THEN 系统 SHALL 将错误码映射为用户可理解的提示信息：空间不足、同名文件冲突、分享链接失效、提取码错误
5. WHEN 转存任务创建成功 THEN 系统 SHALL 将该任务纳入 Download_Manager 的任务队列，复用现有的任务状态管理和进度监控能力
6. WHEN 转存任务完成 THEN 系统 SHALL 将文件归位到用户指定的 save_path 目标路径
7. IF Alist 服务不可达 THEN 系统 SHALL 返回明确的错误提示"Alist 服务不可用"，不创建转存任务

### 需求 8：搜索弹窗 Tab 切换

**用户故事：** 作为媒体库用户，我希望搜索弹窗支持 BT/磁力和网盘两个 Tab 切换，以便在同一弹窗中查看不同来源的搜索结果。

#### 验收标准

1. WHEN 用户打开 Search_Modal THEN Search_Modal SHALL 显示两个 Tab：「BT/磁力」和「网盘」，默认选中「BT/磁力」Tab
2. WHEN 用户切换到「网盘」Tab THEN Search_Modal SHALL 调用 `/search/pan` 接口搜索网盘资源，并按网盘类型分组展示结果
3. WHEN 用户切换到「BT/磁力」Tab THEN Search_Modal SHALL 展示现有的 Prowlarr 搜索结果（含磁力熊补充结果）
4. WHEN 用户在搜索框中修改关键词并触发搜索 THEN Search_Modal SHALL 仅搜索当前激活的 Tab 对应的数据源
5. WHEN 两个 Tab 之间切换时 THEN Search_Modal SHALL 保留各 Tab 已加载的搜索结果缓存，避免重复请求

### 需求 9：网盘搜索结果卡片展示

**用户故事：** 作为媒体库用户，我希望网盘搜索结果以卡片形式展示，包含网盘类型标签和转存操作，以便快速识别和操作。

#### 验收标准

1. WHEN Search_Modal 渲染网盘 Tab 的搜索结果 THEN Search_Modal SHALL 为每条结果显示卡片，包含：标题、网盘类型彩色标签、来源站点名称和转存按钮
2. WHEN 网盘类型标签渲染时 THEN Search_Modal SHALL 为不同网盘类型使用不同颜色：夸克（蓝色）、阿里（橙色）、百度（绿色）、115（紫色）、PikPak（红色）
3. WHEN 某条结果的 pan_type 对应的网盘在 Alist 中未挂载 THEN Search_Modal SHALL 将该卡片置灰并显示"未挂载"标签，转存按钮禁用
4. WHEN 用户点击转存按钮 THEN Search_Modal SHALL 使用当前 savePath 作为转存目标路径，调用后端转存接口
5. WHEN 转存操作完成 THEN Search_Modal SHALL 通过 toast 通知用户转存结果：成功、失败、空间不足或链接失效
6. WHEN 搜索结果按网盘类型分组展示时 THEN Search_Modal SHALL 按配置的网盘优先级顺序排列分组（默认：夸克 > 阿里 > 115 > PikPak > 百度）

### 需求 10：磁力熊直搜补充

**用户故事：** 作为媒体库用户，我希望系统能从磁力熊（cilixiong.org）直接搜索磁力链接，以便在 Prowlarr 索引器之外获取更多 BT/磁力资源。

#### 验收标准

1. WHEN 用户在 BT/磁力 Tab 触发搜索 THEN 系统 SHALL 同时调用 Prowlarr 搜索和 Cilixiong_Scraper 搜索
2. WHEN Cilixiong_Scraper 接收搜索关键词 THEN Cilixiong_Scraper SHALL 搜索 cilixiong.org 并从详情页提取磁力链接
3. WHEN Cilixiong_Scraper 和 Prowlarr 均返回结果 THEN 系统 SHALL 按 btih hash 对磁力链接进行去重，相同 hash 只保留一条
4. WHEN Cilixiong_Scraper 返回的结果包含"最后更新时间"信息 THEN 系统 SHALL 将更新时间作为排序权重因子，更新时间越近权重越高（静态做种数不可靠）
5. WHEN 磁力熊搜索结果合并到 BT/磁力 Tab THEN Search_Modal SHALL 在结果的索引器字段显示"磁力熊"标识
6. IF Cilixiong_Scraper 搜索失败或超时 THEN 系统 SHALL 仅展示 Prowlarr 的搜索结果，不影响 BT/磁力 Tab 的正常使用

### 需求 11：搜索源配置管理

**用户故事：** 作为媒体库用户，我希望能在设置页中管理搜索源的启用/禁用状态和相关配置，以便根据实际情况灵活控制搜索行为。

#### 验收标准

1. THE 系统 SHALL 在设置页提供搜索源开关配置，支持独立启用/禁用以下搜索源：rrdynb、ddys、pansou、cilixiong
2. WHEN 用户禁用某个搜索源 THEN 系统 SHALL 在后续搜索中跳过该源，不发起请求
3. THE 系统 SHALL 在设置页提供 PanSou API 地址配置项，允许用户填写自部署的 PanSou 服务地址
4. THE 系统 SHALL 在设置页提供网盘类型优先级配置，允许用户调整网盘分组的排列顺序
5. WHERE 用户配置了代理池地址 THEN 系统 SHALL 将代理配置传递给 Scraper_Base 使用
6. THE 系统 SHALL 在设置页提供敏感词列表配置，允许用户自定义需要过滤的关键词
7. WHEN 用户修改搜索源配置并保存 THEN 系统 SHALL 立即生效，下次搜索使用新配置

### 需求 12：网盘搜索结果统一数据格式

**用户故事：** 作为媒体库用户，我希望所有网盘搜索源输出统一的数据格式，以便前端能一致地展示和操作不同来源的结果。

#### 验收标准

1. THE 系统 SHALL 定义统一的 Pan_Result 数据结构，包含以下必填字段：title（资源标题）、pan_type（网盘类型枚举）、share_url（分享链接）、password（提取码，可为空）、source（来源站点标识）
2. WHEN 任何 Pan_Scraper 输出搜索结果 THEN Pan_Scraper SHALL 将结果转换为 Pan_Result 格式
3. WHEN Pan_Result 的 share_url 为空或格式无效 THEN 系统 SHALL 丢弃该条结果
4. WHEN Pan_Result 的 pan_type 无法识别 THEN 系统 SHALL 将 pan_type 设为 "unknown" 并在前端以灰色标签展示
5. FOR ALL 有效的 Pan_Result 对象，将其序列化为 JSON 再反序列化 SHALL 产生与原对象等价的结果（序列化往返一致性）

### 需求 13：爬虫错误处理与降级

**用户故事：** 作为媒体库用户，我希望系统在爬虫源不可用时能优雅降级，以便搜索功能不完全中断。

#### 验收标准

1. IF Rrdynb_Scraper 请求超时或返回错误 THEN 系统 SHALL 跳过 rrdynb 源并使用 ddys 和 pansou 的结果继续聚合
2. IF Ddys_Scraper 的反爬机制无法绕过 THEN 系统 SHALL 跳过 ddys 源并记录警告日志，使用其余源的结果
3. IF 所有网盘搜索源均失败 THEN 系统 SHALL 在 `/search/pan` 响应中返回空结果列表，并附带各源的错误状态信息
4. IF Cilixiong_Scraper 搜索失败 THEN 系统 SHALL 仅返回 Prowlarr 的搜索结果，BT/磁力 Tab 正常展示
5. WHEN 某个爬虫源连续失败超过 3 次 THEN Scraper_Base SHALL 在日志中记录该源的健康状态为"不稳定"

## 未来迭代规划 (Phase 2)

以下功能在当前版本暂不实现，归档至二期规划：

### P2-1：网盘资源自动推荐

未来支持根据网盘类型优先级、剩余空间和转存速度自动推荐最佳网盘资源，减少用户手动选择。

### P2-2：网盘搜索结果质量评分

未来引入网盘资源质量评分机制，综合考虑分辨率（从标题解析）、来源站点可靠性、分享链接有效性等维度。

### P2-3：分享链接有效性预检

未来在展示搜索结果前，通过 Alist API 预检分享链接是否有效（未过期、未被取消），无效链接标记为"已失效"。

### P2-4：爬虫源健康监控面板

未来在设置页新增爬虫源健康监控面板，展示各源的成功率、平均响应时间、最近错误信息，支持手动测试连通性。
