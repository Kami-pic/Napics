import json
import os
from pydantic import BaseModel
from typing import Optional, List

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

class AppConfig(BaseModel):
    prowlarr_url: str = "http://127.0.0.1:9696"
    prowlarr_api_key: str = ""
    tmdb_api_key: str = ""
    qb_url: str = "http://127.0.0.1:8080"
    qb_username: str = "admin"
    qb_password: str = ""
    alist_url: str = "http://127.0.0.1:5244"
    alist_token: str = ""
    nas_paths: List[str] = ["C:\\Users\\shenq\\Videos"]
    exclude_dirs: str = ""
    nas_path: Optional[str] = "" # 兼容旧配置
    openai_api_key: Optional[str] = ""
    openai_base_url: Optional[str] = ""
    openai_model: Optional[str] = ""
    ai_enabled: bool = False                      # AI 全局总开关
    ai_features: AIFeaturesConfig = AIFeaturesConfig()  # AI 场景开关
    http_proxy: Optional[str] = ""
    indexer_priorities: List[IndexerPriorityConfig] = []
    search_confidence_threshold: str = "medium"  # "high" | "medium" | "low"
    category_tags: dict = {}  # 一级分类目录路径 → 标签 {"\\\\NAS\\电影": "movie", ...}
    # 搜索下载优化新增配置
    search_filter: SearchFilterConfig = SearchFilterConfig()
    preferred_codec: str = "x265"                # 编码偏好
    download_channel_auto: bool = True            # 下载通道自动推荐
    recycle_bin_path: str = ""                    # 回收站目录路径
    recycle_bin_retention_days: int = 30           # 回收站保留天数
    player_path: str = "C:\\Program Files\\DAUM\\PotPlayer\\PotPlayerMini64.exe"  # 本地播放器路径
    # 二期新增
    sort_weights: SortWeightsConfig = SortWeightsConfig()  # 种子排序权重
    torrent_blacklist: List[str] = []             # 无效种子黑名单（download_url）
    torrent_blacklist_updated: str = ""           # 黑名单最后更新时间
    subscribe_interval_hours: float = 4.0         # 订阅搜索基础间隔（小时）
    # 搜索源开关
    bt_search_sources: dict = {}                  # BT 源开关 {"bitsearch": true, "cilixiong": true, ...}
    pan_search_sources: dict = {}                 # 网盘源开关 {"pansearch": true, "rrdynb": true, ...}
    # 刮削配置
    default_scrape_source: str = "tmdb"           # 默认刮削源 "tmdb" | "douban"

class ConfigManager:
    def __init__(self, config_path: str = None):
        # 强制使用绝对路径锁定 backend 目录
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_path = config_path or os.path.join(base_dir, "config.json")
        self.lib_path = os.path.join(base_dir, "media_library.json")
        self._config = self.load()
        self._on_library_save_callbacks = []  # save_library 后的回调列表

    def load(self) -> AppConfig:
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 迁移逻辑：如果旧的单路径存在且新的多路径不存在，则自动合并
                if "nas_path" in data and ("nas_paths" not in data or data["nas_paths"] == ["C:\\Users\\shenq\\Videos"]):
                   data["nas_paths"] = [data["nas_path"]]
                return AppConfig(**data)
        return AppConfig()

    def save(self, config: AppConfig):
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config.dict(), f, indent=4)
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
                bak = lib_path + ".bak"
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
        lib_path = "media_library.json"
        with open(lib_path, "w", encoding="utf-8") as f:
            json.dump(deduped, f, indent=4, ensure_ascii=False)
        # 通知媒体库索引刷新
        for cb in self._on_library_save_callbacks:
            try:
                cb(deduped)
            except Exception:
                pass

    # 排除列表：移除的文件/文件夹路径，同步时跳过
    def _excluded_path(self):
        return "excluded_paths.json"

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
        return "no_scrape.json"

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
