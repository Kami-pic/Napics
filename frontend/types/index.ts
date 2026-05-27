// 全局类型定义

export interface VideoInfo {
  file_name: string;
  file_path: string;
  folder_name: string;
  size_gb: number;
  resolution: string;
  width: number;
  height: number;
  duration: number;
  audio_codec: string;
  video_codec: string;
  subtitle_count: number;
  hdr_type: string;
  is_low_res: boolean;
  has_poster?: boolean;
  has_nfo?: boolean;
  shadow_name?: string;
  shadow_name_source?: string;
  shadow_tmdb_id?: number;
  organize_status?: string; // "ok" | "scrape_failed" | undefined(未整理)
  clean_name?: string; // 清洗后的文件名（去广告/标签/编码）
  clean_name_cn?: string; // 中文清洗名
  clean_name_en?: string; // 英文清洗名
  clean_name_original?: string; // 原始语言清洗名（日文/韩文等）
  clean_name_source?: string; // 清洗名来源
  quality_score?: number; // 100 分制综合质量评分
}

export interface FolderNode {
  name: string;
  path: string;
  children: FolderNode[];
  videos: VideoInfo[];
  video_count: number;
  has_cover: boolean;
  is_category?: boolean;
  is_top_category?: boolean;
  is_virtual_library?: boolean;
  parent_category_tag?: string;
  folder_type?: string;
  shadow_name?: string;
  clean_name?: string;
  clean_name_cn?: string;
  clean_name_en?: string;
  clean_name_original?: string;
  category_tag?: string;
}

// 季集完整度
export interface SeasonCompleteness {
  season_number: number;
  episode_count: number;
  local_count: number;
  missing_episodes: { episode: number; title: string; air_date: string; aired: boolean }[];
  status: "complete" | "partial" | "missing";
}

export interface CompletenessResult {
  tmdb_id?: number;
  title?: string;
  english_title?: string;
  total_seasons?: number;
  seasons?: SeasonCompleteness[];
  total_episodes?: number;
  local_total?: number;
  completeness_pct?: number;
  status: "ok" | "no_tmdb_id" | "no_tmdb_client" | "tmdb_error" | "plugin_not_installed";
  message?: string;
}

/** 虚拟媒体库配置 */
export interface MediaLibraryConfig {
  name: string;
  category_tag: string;
  paths: string[];
  exclude_dirs: string[];
}

export interface AppConfig {
  prowlarr_url: string;
  prowlarr_api_key: string;
  tmdb_api_key: string;
  qb_url: string;
  qb_username?: string;
  qb_password?: string;
  alist_url: string;
  alist_token: string;
  scan_paths: string[];
  exclude_dirs: string;
  media_libraries?: MediaLibraryConfig[];
  http_proxy?: string;
  player_path?: string;
  openai_api_key?: string;
  openai_base_url?: string;
  openai_model?: string;
  ai_enabled?: boolean;
  ai_features?: AIFeaturesConfig;
  indexer_priorities?: IndexerPriority[];
  search_confidence_threshold?: "high" | "medium" | "low";
  category_tags?: Record<string, string>;
  // 搜索下载优化新增
  search_filter?: SearchFilterConfig;
  preferred_codec?: string;
  download_channel_auto?: boolean;
  recycle_bin_path?: string;
  recycle_bin_retention_days?: number;
  default_scrape_source?: string;
}

export interface SearchFilterConfig {
  must_include: string[];
  must_exclude: string[];
}

export interface ScanProgress {
  current: number;
  total: number;
  lastFile: string;
}

export type FilterType = "all" | "upgrade" | "nosub" | "dolby" | "hdr" | "large" | "small";
export type ViewMode = "card" | "list";

export interface SearchResult {
  title: string;
  size_gb: number;
  indexer: string;
  seeders: number;
  leechers: number;
  download_url: string;
  info_url?: string;
  quality_tag: string;
}

export interface LibraryStats {
  total: number;
  lowRes: number;
  missingSub: number;
}

export interface AISuggestion {
  original_path: string;
  suggested_rel_path: string;
  reason: string;
}

export interface OrganizeSnapshot {
  id: number;
  time: string;
  label?: string;
  ops: { old_path: string; new_path: string; is_dir?: boolean }[];
}

export interface ScrapeResult {
  tmdb_id: number;
  media_type: string;
  title: string;
  original_title: string;
  english_title?: string;
  year: string;
  poster_url: string | null;
  backdrop_url: string | null;
  overview: string;
  rating: number;
  genres: string[];
  director: string;
  cast: string[];
  runtime: number;
  imdb_id: string;
  total_seasons: number;
  status: string;
  season_number: number;
  episode_count: number;
  air_date: string;
  episode_number: number;
  episode_title: string;
  still_url: string | null;
}

// ===== 搜索升级 & 新增影片 类型定义 =====

export interface QualityTag {
  resolution: string;
  source: string;
  video_codec: string;
  audio_codec: string;
  has_chinese_sub: boolean;
  release_group: string;
  is_surround: boolean;   // 环绕声 5.0+
  display: string;
}

export interface EnhancedSearchResult extends SearchResult {
  quality: QualityTag;
  quality_rank: number;
  match_verdict?: "matched" | "unmatched";
  publish_date?: string;
}

export interface FilterState {
  resolution: string[];   // 多选：["720p", "1080p", "2160p"]
  source: string[];       // 多选：["Bluray", "WEB-DL", "Remux"]
  videoCodec: string[];   // 多选：["x265", "x264"]
  audioCodec: string[];   // 多选：["DTS", "DTS-HD", "TrueHD", "Atmos", "AAC", "surround"]
  chineseSubOnly: boolean;
  seasonPackOnly: boolean;
  minSizeGb: number | null;
  maxSizeGb: number | null;
  minSeeders: number;
  indexers: string[];     // Prowlarr 索引器多选
}

export interface BatchUpgradeTask {
  name: string;
  path: string;
  currentResolution: string;
  status: "pending" | "searching" | "found" | "not_found" | "error";
  bestMatch: EnhancedSearchResult | null;
  allResults: EnhancedSearchResult[];
  confirmed: boolean;
  matchScore: number;           // 0.0-1.0 匹配分数
  confidence: "high" | "medium" | "low" | "";
  isUpgrade: boolean;           // 分辨率是否有提升
}

export interface DoubanHotItem {
  douban_id: string;
  title: string;
  year: string;
  rating: number;
  cover_url: string;
  subtitle: string;
  episode: string;
  _tmdb_original_title?: string;
  // 豆瓣 API v2 扩展字段
  genres?: string[];
  overview?: string;
  directors?: string[];
  actors?: string[];
  countries?: string[];
  media_type?: string;
  episodes_info?: string;
  // 本地媒体库感知
  local_status?: "none" | "owned_low" | "owned_high";
  local_folder?: string;
  // 结构化清洗名（后端 _inject_clean_names 注入）
  clean_name_cn?: string;
  clean_name_en?: string;
  clean_name_original?: string;
  // TMDB 评分（enrich_cache 注入）
  tmdb_rating?: number;
}

export interface AddMediaInfo {
  title: string;
  original_title: string;
  year: string;
  douban_id: string;
  rating: number;
  overview: string;
  genres: string[];
  director: string;
  cast: string[];
  poster_url: string;
}

// ===== 搜索匹配准确性提升 类型定义 =====

/** 影子名信息 */
export interface ShadowName {
  name: string;
  source: "manual" | "tmdb" | "nfo" | "douban" | "bangumi" | "parsed";
  tmdb_id?: number;
}

/** 匹配置信度 */
export interface MatchConfidence {
  level: "high" | "medium" | "low";
  score: number;
  details: Record<string, number>;
}

/** 增强的刮削结果（含置信度） */
export interface EnhancedScrapeResult {
  status: string;
  data: Record<string, any>;
  confidence: MatchConfidence;
  tmdb_id: number;
  media_type: string;
}

/** 索引器优先级配置 */
export interface IndexerPriority {
  indexer_id?: number;
  name: string;
  priority: number;
  prowlarr_priority?: number;
  enabled: boolean;
  preferred_types: ("anime" | "movie" | "tv")[];
  supports_chinese?: boolean;
  status?: "ok" | "error" | "warning" | "disabled" | "unknown";
  status_error?: string;
}

/** 刮削候选项（含英文名） */
export interface ScrapeCandidate {
  tmdb_id: number;
  media_type: string;
  title: string;
  original_title: string;
  english_title: string;
  year: string;
  overview: string;
  poster_url: string | null;
  popularity: number;
}


// ===== 搜索下载优化 新增类型 =====

/** 增强搜索响应 */
export interface SearchResponse {
  results: EnhancedSearchResult[];
  hit_keyword: string;
  total_raw: number;
  total_filtered: number;
}

/** 整季包验证信息 */
export interface SeasonPackInfo {
  result: EnhancedSearchResult;
  verification: {
    verified: boolean;
    is_magnet: boolean;
    episode_count: number;
    episodes_found: number[];
    is_complete: boolean;
  };
}

/** 单集搜索结果 */
export interface EpisodeResult {
  episode: number;
  status: "found" | "not_found";
  recommended: EnhancedSearchResult | null;
  alternatives: EnhancedSearchResult[];
}

/** 同源匹配方案 */
export interface SameSourcePlan {
  primary_group: string;
  coverage: number;
  episodes: Record<number, EnhancedSearchResult>;
  missing_episodes: number[];
}

/** 季级搜索完整结果 */
export interface SeasonSearchResponse {
  season_packs: SeasonPackInfo[];
  episode_results: Record<number, EpisodeResult>;
  recommended_plan: "season_pack" | "per_episode";
  same_source_plan?: SameSourcePlan;
  total_size_pack_gb: number;
  total_size_episode_gb: number;
}

/** 下载任务 */
export interface DownloadTask {
  id: string;
  media_name: string;
  download_url: string;
  save_path: string;
  download_dir: string;
  channel: "qb" | "alist";
  downloader_hash: string;
  category_hint: string;
  status: "pending" | "downloading" | "cloud_done" | "completed" | "relocating" | "awaiting_confirm" | "archived" | "failed" | "lost" | "unknown" | "cancelled";
  progress: number;
  speed: string;
  eta: string;
  phase: "" | "cloud_download" | "local_sync";
  error: string;
  is_season_pack: boolean;
  season_number: number;
  created_at: string;
  updated_at: string;
  coexist_pairs?: CoexistPair[];
}

/** 新旧文件共存冲突对 */
export interface CoexistPair {
  new_file: string;
  old_file: string;
  new_size_gb: number;
  old_size_gb: number;
}

/** 回收站条目 */
export interface RecycleBinEntry {
  id: string;
  original_path: string;
  recycle_path: string;
  size_gb: number;
  moved_at: string;
  task_id: string;
  expires_at: string;
}

// ===== 二期功能 新增类型 =====

/** 种子排序权重配置 */
export interface SortWeightsConfig {
  title_match: number;
  resolution_upgrade: number;
  codec_match: number;
  seeder_health: number;
  chinese_sub: number;
  size_reasonable: number;
}

/** 全库分析报告 */
export interface AnalysisReport {
  results: AnalysisFolderResult[];
  summary: AnalysisSummary;
  cross_folder_issues: any[];
  updated_at: number;
  from_cache: boolean;
  cache_age_hours: number;
}

export interface AnalysisSummary {
  total_folders: number;
  structure_issues: number;
  rename_issues: number;
  scrape_issues: number;
  quality_issues: number;
  filename_issues: number;
  shadow_name_issues: number;
  cross_folder_issues: number;
}

export interface AnalysisFolderResult {
  path: string;
  folder_name: string;
  folder_type: string;
  video_count: number;
  structure_ops: any[];
  rename_ops: any[];
  scrape_issues: any[];
  quality_issues: any[];
  filename_issues: any[];
  shadow_name_issues: any[];
}

/** 整理进度事件 */
export interface OrganizeProgressEvent {
  step: number;
  total: number;
  label: string;
  status: "running" | "done" | "completed" | "error";
  count?: number;
  folder_type?: string;
  summary?: Record<string, any>;
  result?: Record<string, any>;
  error?: string;
}

/** 整理历史快照 */
export interface OrganizeHistorySnapshot {
  id: number;
  time: string;
  label?: string;
  ops: { old_path: string; new_path: string; is_dir?: boolean }[];
}

/** 种子黑名单条目 */
export interface BlacklistEntry {
  url: string;
  expires_at: number;
  ttl_hours: number;
}


// ===== 网盘搜索增强 类型定义 =====

/** 网盘搜索结果 */
export interface PanResult {
  title: string;
  clean_title: string;
  pan_type: "quark" | "aliyun" | "baidu" | "pan115" | "pikpak" | "unknown";
  share_url: string;
  password: string;
  source: string;
  mounted: boolean;
  resolution: string;
  size_gb: number;
  is_complete: boolean;
  file_count: number;
  alive: boolean;
}

/** 搜索源状态 */
export interface PanSourceStatus {
  name: string;
  status: "success" | "failed" | "disabled" | "timeout";
  count: number;
  error: string;
}

/** 网盘搜索聚合响应 */
export interface PanSearchResponse {
  results: PanResult[];
  groups: Record<string, PanResult[]>;
  source_statuses: PanSourceStatus[];
  total: number;
}

// ===== Provider metadata 类型定义 =====

export interface ProviderMetadata {
  id: string;
  name: string;
  kind: "search" | "pan_search" | "metadata" | "rss" | "download" | "storage" | "notification";
  type: string;
  enabled: boolean;
  defaultEnabled: boolean;
  capabilities: string[];
  riskLevel: "low" | "medium" | "high" | "private" | "user_configured";
  requires: string[];
  supportsProxy: boolean;
  description: string;
}

export interface ProviderCatalog {
  search: ProviderMetadata[];
  panSearch: ProviderMetadata[];
  metadata: ProviderMetadata[];
  rss: ProviderMetadata[];
  download: ProviderMetadata[];
  storage: ProviderMetadata[];
  notification: ProviderMetadata[];
}


// ===== AI 集成 类型定义 =====

/** AI 场景开关配置 */
export interface AIFeaturesConfig {
  extract_episode: boolean;
  scrape_candidate: boolean;
  library_diagnosis: boolean;
  search_recommend: boolean;
  natural_search: boolean;
  subscribe_recommend: boolean;
}

/** AI 状态响应 */
export interface AIStatus {
  enabled: boolean;
  master_switch: boolean;
  has_credentials: boolean;
  features: AIFeaturesConfig;
  usage: Record<string, { calls: number; tokens: number; errors: number }>;
}

/** AI 诊断结果 */
export interface AIDiagnosisResult {
  health_score: number;
  priorities: {
    category: string;
    severity: "high" | "medium" | "low";
    count: number;
    suggestion: string;
    action: string;
  }[];
  summary: string;
}
