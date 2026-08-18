import json
import os
from pydantic import BaseModel
from typing import Optional, List

from core.json_store import atomic_write_json

class IndexerPriorityConfig(BaseModel):
    """索引器优先级配置（用于 AppConfig 序列化）"""
    indexer_id: int = 0
    name: str = ""
    priority: int = 50
    enabled: bool = True
    preferred_types: List[str] = []
    supports_chinese: bool = False

class SortWeightsConfig(BaseModel):
    """种子排序权重配置（用户可自定义）"""
    title_match: float = 0.30
    resolution_upgrade: float = 0.25
    codec_match: float = 0.15
    seeder_health: float = 0.15
    chinese_sub: float = 0.10
    size_reasonable: float = 0.05

class AIFeaturesConfig(BaseModel):
    """AI 场景开关配置"""
    extract_episode: bool = True       # 文件名智能解析
    scrape_candidate: bool = True      # 刮削候选匹配
    library_diagnosis: bool = True     # 媒体库健康诊断
    search_recommend: bool = True     # 搜索结果推荐
    natural_search: bool = False       # 自然语言搜索（二期）
    subscribe_recommend: bool = False  # 订阅推荐（二期）

class SearchFilterConfig(BaseModel):
    """搜索过滤规则配置"""
    must_include: List[str] = []                                          # 必须包含的关键词
    must_exclude: List[str] = ["TS", "CAM", "HDTC", "TC", "TELECINE", "HDTS"]  # 严格排除的关键词

class MediaLibraryConfig(BaseModel):
    """虚拟媒体库配置（分类添加文件夹）"""
    name: str = ""                    # 显示名称（默认取根目录名）
    category_tag: str = "movie"       # 标签：movie/tv/anime_tv/anime_movie/variety/other
    paths: List[str] = []             # 一个或多个真实路径
    exclude_dirs: List[str] = []      # 该库独立的排除规则


class PluginSourceConfig(BaseModel):
    """外部插件源配置"""
    name: str = ""                    # 源名称
    url: str = ""                     # 源 index.json 的 URL
    requires_license: bool = False    # 是否需要授权验证


class AppConfig(BaseModel):
    prowlarr_url: str = "http://127.0.0.1:9696"
    prowlarr_api_key: str = ""
    tmdb_api_key: str = ""
    qb_url: str = "http://127.0.0.1:8080"
    qb_username: str = "admin"
    qb_password: str = ""
    alist_url: str = "http://127.0.0.1:5244"
    alist_token: str = ""
    scan_paths: List[str] = []        # 扫描路径（自动识别模式，忽略根目录平铺内容）
    exclude_dirs: str = ""
    media_libraries: List[MediaLibraryConfig] = []  # 虚拟媒体库（分类添加模式）
    # 兼容旧配置字段已在 load() 中迁移，不再作为模型字段
    # nas_paths / nas_path 读取时自动合并到 scan_paths
    openai_api_key: Optional[str] = ""
    openai_base_url: Optional[str] = ""
    openai_model: Optional[str] = ""
    ai_enabled: bool = False                      # AI 全局总开关
    ai_features: AIFeaturesConfig = AIFeaturesConfig()  # AI 场景开关
    http_proxy: Optional[str] = ""
    # 代理分流：以下域名（后缀匹配）始终直连，不走 http_proxy。
    # 内置已包含豆瓣 / Bangumi / 常见国内 CDN 与网盘，这里是额外追加。
    # 用途：http_proxy 只有一个，全部请求都走它会把国内站点绕出国反而失败。
    direct_domains: List[str] = []
    indexer_priorities: List[IndexerPriorityConfig] = []
    search_confidence_threshold: str = "medium"  # "high" | "medium" | "low"
    category_tags: dict = {}  # 一级分类目录路径 → 标签 {"\\\\NAS\\电影": "movie", ...}
    # 搜索下载优化新增配置
    search_filter: SearchFilterConfig = SearchFilterConfig()
    preferred_codec: str = "x265"                # 编码偏好
    download_channel_auto: bool = True            # 下载通道自动推荐
    recycle_bin_path: str = ""                    # 回收站目录路径
    recycle_bin_retention_days: int = 30           # 回收站保留天数
    # 本地播放器路径（仅在后端跑在桌面系统上时有意义；
    # Docker / NAS 部署时后端没有桌面环境，无法拉起播放器，留空即可）
    player_path: str = ""
    # 是否使用本地播放器（开启则走后端 /play 调起本地/系统默认播放器，关闭则走浏览器内 Web Player）
    use_local_player: bool = False
    # 二期新增
    sort_weights: SortWeightsConfig = SortWeightsConfig()  # 种子排序权重
    torrent_blacklist: List[str] = []             # 无效种子黑名单（download_url）
    torrent_blacklist_updated: str = ""           # 黑名单最后更新时间
    subscribe_interval_hours: float = 4.0         # 订阅搜索基础间隔（小时）
    # 搜索源开关
    bt_search_sources: dict = {}                  # BT 源开关 {"bitsearch": true, "cilixiong": true, ...}
    pan_search_sources: dict = {}                 # 网盘源开关 {"pansearch": true, "rrdynb": true, ...}
    # 刮削配置
    default_scrape_source: str = "douban"          # 默认刮削源 "tmdb" | "douban"
    # 插件系统
    # 新安装默认预装 6 个低风险核心插件；社区插件只从外部源按需安装。
    # 已有配置不会被该默认值覆盖，用户主动卸载状态会被保留。
    installed_plugins: List[str] = [
        "metadata-tmdb",
        "metadata-bangumi",
        "download-qbittorrent",
        "feature-completeness",
        "feature-discover",
        "feature-local-match",
    ]
    plugin_sources: List[PluginSourceConfig] = [  # 外部插件源列表（预置官方社区源）
        PluginSourceConfig(
            name="Napics 社区插件源",
            url="https://github.com/icatmiumiu/plugins-of-napics",
        ),
    ]
    # 授权
    license_key: str = ""                         # License Key
    license_status: str = ""                      # 验证状态：valid / expired / invalid / ""
    license_email: str = ""                       # 授权邮箱
    license_plan: str = ""                        # 授权计划
    license_validated_at: str = ""                # 最后验证时间（ISO 格式）
    # 下载监控目录（无下载器插件时的兜底方案）
    download_watch_dirs: List[str] = []           # 监控目录列表，新文件自动触发整理
    # 插件代理覆盖：{"metadata-bangumi": "proxy", "metadata-douban": "direct"}
    # 可选值：auto（默认分流）、direct（强制直连）、proxy（强制走 http_proxy）
    plugin_proxy_overrides: dict = {}
    # GitHub 镜像：国内直连 raw.githubusercontent.com / github.com 常超时，
    # 官方地址优先、失败时按此列表回退。设为 {"raw": [], "repo": []} 可关闭回退。
    # 为 None（默认）时使用 core/github_access.py 内置的镜像列表。
    github_mirrors: Optional[dict] = None
    # 已执行过的一次性配置迁移标记。落盘后不再重复执行，
    # 保证补齐类迁移不会覆盖用户后续的主动卸载。
    config_migrations: List[str] = []

class ConfigManager:
    def __init__(self, config_path: str = None):
        # 数据目录：优先环境变量 NAPICS_DATA_DIR，否则回退到 backend/ 目录
        data_dir = os.environ.get("NAPICS_DATA_DIR") or os.path.dirname(os.path.abspath(__file__))
        self.data_dir = os.path.abspath(data_dir)
        os.makedirs(self.data_dir, exist_ok=True)
        self.config_path = config_path or os.path.join(self.data_dir, "config.json")
        self.lib_path = os.path.join(self.data_dir, "media_library.json")
        self._config = self.load()
        self._on_library_save_callbacks = []  # save_library 后的回调列表

    def load(self) -> AppConfig:
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 迁移逻辑：nas_path / nas_paths → scan_paths
                if "scan_paths" not in data:
                    migrated = []
                    if "nas_paths" in data and data["nas_paths"]:
                        migrated = [p for p in data["nas_paths"] if p]
                    elif "nas_path" in data and data["nas_path"]:
                        migrated = [data["nas_path"]]
                    data["scan_paths"] = migrated
                # 迁移逻辑：预装插件（旧配置 installed_plugins 为空时注入默认值）
                if not data.get("installed_plugins") and not data.get("_plugins_migrated"):
                    data["installed_plugins"] = AppConfig.model_fields["installed_plugins"].default
                    data["_plugins_migrated"] = True
                # 清理旧字段避免 Pydantic 校验问题
                data.pop("nas_path", None)
                data.pop("nas_paths", None)
                data.pop("_plugins_migrated", None)
                migrated = self._apply_migrations(data)
                config = AppConfig(**data)
            # 落盘必须在读句柄关闭之后：Windows 下目标文件仍被占用时 os.replace 会失败
            if migrated:
                # 迁移结果必须落盘，否则每次启动都会重复补齐，
                # 用户主动卸载的插件会被反复装回来
                self.save(config)
            return config
        return AppConfig()

    @staticmethod
    def _apply_migrations(data: dict) -> bool:
        """对已落盘的配置执行一次性迁移。返回是否发生了改动。

        每个迁移只执行一次（记录在 config_migrations 里），
        之后用户对相关配置的修改不会被覆盖。
        """
        done = list(data.get("config_migrations") or [])
        changed = False

        # 补齐 Bangumi 元数据源：早期默认列表遗漏了它，
        # 导致 /api/providers 过滤后前端完全看不到 Bangumi，相关功能整体不可用。
        if "add_bangumi_metadata" not in done:
            plugins = list(data.get("installed_plugins") or [])
            if plugins and "metadata-bangumi" not in plugins:
                plugins.append("metadata-bangumi")
                data["installed_plugins"] = plugins
            done.append("add_bangumi_metadata")
            changed = True

        if changed:
            data["config_migrations"] = done
        return changed

    def save(self, config: AppConfig):
        # config.json 需要人工可读，保留缩进；原子写避免损坏
        atomic_write_json(self.config_path, config.dict(), indent=4)
        self._config = config

    @property
    def config(self) -> AppConfig:
        return self._config

    def load_library(self) -> List[dict]:
        if os.path.exists(self.lib_path):
            try:
                with open(self.lib_path, "r", encoding="utf-8", errors="replace") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                # JSON 损坏，尝试备份
                bak = self.lib_path + ".bak"
                if os.path.exists(bak):
                    with open(bak, "r", encoding="utf-8") as f:
                        return json.load(f)
        return []

    def save_library(self, data: List[dict]):
        # 按 file_path 去重，保留最后一条
        seen = {}
        for v in data:
            fp = v.get("file_path", "")
            if fp:
                seen[fp] = v
        deduped = list(seen.values())
        # 注入 quality_score（100 分制综合评分）
        try:
            from quality_parser import compute_quality_score_from_video
            for v in deduped:
                if "quality_score" not in v or v.get("quality_score", 0) == 0:
                    v["quality_score"] = compute_quality_score_from_video(v)
        except Exception:
            pass
        # 原子写入 + 紧凑序列化：大媒体库下显著减少序列化耗时与落盘体积，
        # 且避免写入过程中断电导致 media_library.json 截断损坏
        atomic_write_json(self.lib_path, deduped, compact=True)
        # 通知媒体库索引刷新
        for cb in self._on_library_save_callbacks:
            try:
                cb(deduped)
            except Exception:
                pass

    # 排除列表：移除的文件/文件夹路径，同步时跳过
    def _excluded_path(self):
        return os.path.join(self.data_dir, "excluded_paths.json")

    def load_excluded(self) -> set:
        p = self._excluded_path()
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return set(json.load(f))
        return set()

    def add_excluded_paths(self, paths: List[str]):
        excluded = self.load_excluded()
        excluded.update(paths)
        with open(self._excluded_path(), "w", encoding="utf-8") as f:
            json.dump(list(excluded), f, indent=2, ensure_ascii=False)

    def remove_excluded_paths(self, paths: List[str]):
        excluded = self.load_excluded()
        excluded -= set(paths)
        with open(self._excluded_path(), "w", encoding="utf-8") as f:
            json.dump(list(excluded), f, indent=2, ensure_ascii=False)

    # 禁止刮削列表
    def _no_scrape_path(self):
        return os.path.join(self.data_dir, "no_scrape.json")

    def load_no_scrape(self) -> set:
        p = self._no_scrape_path()
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return set(json.load(f))
        return set()

    def set_no_scrape(self, path: str, enabled: bool):
        items = self.load_no_scrape()
        if enabled:
            items.add(path)
        else:
            items.discard(path)
        with open(self._no_scrape_path(), "w", encoding="utf-8") as f:
            json.dump(list(items), f, indent=2, ensure_ascii=False)
