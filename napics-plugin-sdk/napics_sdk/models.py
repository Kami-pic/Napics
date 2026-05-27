"""Provider 契约 DTO — Napics 插件 SDK。

本模块定义 Core 与 Provider 之间的结构化数据边界。
插件开发者使用这些模型作为搜索/元数据/下载等函数的输入输出类型。
"""

from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProviderKind(str, Enum):
    SEARCH = "search"
    PAN_SEARCH = "pan_search"
    METADATA = "metadata"
    RSS = "rss"
    DOWNLOAD = "download"
    STORAGE = "storage"
    NOTIFICATION = "notification"


class ProviderRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    PRIVATE = "private"
    USER_CONFIGURED = "user_configured"


class ProviderHealthStatus(str, Enum):
    UNKNOWN = "unknown"
    OK = "ok"
    DEGRADED = "degraded"
    DISABLED = "disabled"
    ERROR = "error"


class ProviderMetadata(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    kind: ProviderKind
    type: str = ""
    enabled: bool = False
    default_enabled: bool = Field(default=False, alias="defaultEnabled")
    capabilities: List[str] = Field(default_factory=list)
    risk_level: ProviderRiskLevel = Field(
        default=ProviderRiskLevel.LOW,
        alias="riskLevel",
    )
    requires: List[str] = Field(default_factory=list)
    supports_proxy: bool = Field(default=False, alias="supportsProxy")
    description: str = ""

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("provider id 不能为空")
        if normalized != normalized.lower():
            raise ValueError("provider id 必须使用小写稳定机器名")
        return normalized

    @field_validator("capabilities", "requires")
    @classmethod
    def dedupe_text_list(cls, value: List[str]) -> List[str]:
        seen = set()
        result = []
        for item in value:
            normalized = item.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                result.append(normalized)
        return result


class ProviderHealth(BaseModel):
    status: ProviderHealthStatus = ProviderHealthStatus.UNKNOWN
    message: str = ""
    checked_at: Optional[datetime] = Field(default=None, alias="checkedAt")


class SearchKeywordSet(BaseModel):
    """搜索关键词集合 — 系统会自动填充多语言关键词"""
    cn: str = ""
    en: str = ""
    original: str = ""
    shadow: str = ""
    clean: str = ""
    fallbacks: List[str] = Field(default_factory=list)


class SearchRequest(BaseModel):
    """搜索请求"""
    query: str
    media_type: str = ""
    year: Optional[int] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    keywords: SearchKeywordSet = Field(default_factory=SearchKeywordSet)
    limit: int = 50
    timeout_sec: float = Field(default=15.0, alias="timeoutSec")


class SearchCandidate(BaseModel):
    """BT 搜索结果"""
    title: str
    download_url: str = Field(default="", alias="downloadUrl")
    info_url: str = Field(default="", alias="infoUrl")
    size_gb: float = Field(default=0.0, alias="sizeGb")
    seeders: int = 0
    leechers: int = 0
    published_at: Optional[datetime] = Field(default=None, alias="publishedAt")
    raw_quality: str = Field(default="", alias="rawQuality")
    provider_id: str = Field(alias="providerId")
    indexer: str = ""
    info_hash: str = Field(default="", alias="infoHash")


class PanSearchCandidate(BaseModel):
    """网盘搜索结果"""
    title: str
    clean_title: str = Field(default="", alias="cleanTitle")
    share_url: str = Field(alias="shareUrl")
    pan_type: str = Field(default="", alias="panType")
    password: str = ""
    source_provider_id: str = Field(alias="sourceProviderId")
    file_size: str = Field(default="", alias="fileSize")
    resolution: str = ""
    updated_at: Optional[datetime] = Field(default=None, alias="updatedAt")


class RSSFetchRequest(BaseModel):
    """RSS 拉取请求"""
    subscription_id: str = Field(default="", alias="subscriptionId")
    title: str = ""
    media_type: str = Field(default="", alias="mediaType")
    keywords: SearchKeywordSet = Field(default_factory=SearchKeywordSet)
    limit: int = 50
    since: Optional[datetime] = None


class RSSCandidate(BaseModel):
    """RSS 条目"""
    title: str = ""
    download_url: str = Field(default="", alias="downloadUrl")
    info_url: str = Field(default="", alias="infoUrl")
    published_at: Optional[datetime] = Field(default=None, alias="publishedAt")
    size_gb: float = Field(default=0.0, alias="sizeGb")
    info_hash: str = Field(default="", alias="infoHash")
    quality_tag: str = Field(default="", alias="qualityTag")
    resolution: str = ""
    episode: Optional[int] = None
    season: Optional[int] = None
    provider_id: str = Field(default="", alias="providerId")
    seeders: int = 0
    indexer: str = ""


class MetadataSearchRequest(BaseModel):
    """元数据搜索请求"""
    query: str
    media_type: str = Field(default="", alias="mediaType")
    year: Optional[int] = None
    limit: int = 20


class MetadataCandidate(BaseModel):
    """元数据搜索结果"""
    provider_id: str = Field(alias="providerId")
    external_id: str = Field(alias="externalId")
    title: str
    original_title: str = Field(default="", alias="originalTitle")
    year: Optional[int] = None
    media_type: str = Field(default="", alias="mediaType")
    overview: str = ""
    poster_url: str = Field(default="", alias="posterUrl")
    rating: Optional[float] = None
    extra: Any = Field(default_factory=dict)


class EpisodeInfo(BaseModel):
    """剧集信息"""
    season: int
    episode: int
    title: str = ""
    air_date: str = Field(default="", alias="airDate")


class ArtworkInfo(BaseModel):
    """图片资源"""
    kind: str
    url: str
    language: str = ""


class AliasSet(BaseModel):
    """多语言别名集合"""
    cn: str = ""
    en: str = ""
    original: str = ""
    aliases: List[str] = Field(default_factory=list)


class MetadataDetail(BaseModel):
    """元数据详情"""
    provider_id: str = Field(alias="providerId")
    external_id: str = Field(alias="externalId")
    title: str
    original_title: str = Field(default="", alias="originalTitle")
    media_type: str = Field(default="", alias="mediaType")
    year: Optional[int] = None
    overview: str = ""
    runtime: Optional[int] = None
    rating: Optional[float] = None
    aliases: AliasSet = Field(default_factory=AliasSet)
    episodes: List[EpisodeInfo] = Field(default_factory=list)
    artwork: List[ArtworkInfo] = Field(default_factory=list)
    extra: Any = Field(default_factory=dict)


class DownloadRequest(BaseModel):
    """下载请求"""
    url: str
    save_path: str = Field(alias="savePath")
    category: str = ""
    metadata: Optional[ProviderMetadata] = None


class DownloadSubmitResult(BaseModel):
    """下载提交结果"""
    success: bool
    external_task_id: str = Field(default="", alias="externalTaskId")
    error_code: str = Field(default="", alias="errorCode")
    message: str = ""


class DownloadProgress(BaseModel):
    """下载进度"""
    external_task_id: str = Field(alias="externalTaskId")
    progress: float = 0.0
    speed: str = ""
    eta: str = ""
    status: str = ""
    files: List[str] = Field(default_factory=list)
    extra: Any = Field(default_factory=dict)


class DownloadTaskInfo(BaseModel):
    """下载任务信息"""
    external_task_id: str = Field(alias="externalTaskId")
    name: str = ""
    save_path: str = Field(default="", alias="savePath")
    progress: float = 0.0
    speed: str = ""
    eta: str = ""
    status: str = ""
    extra: Any = Field(default_factory=dict)


class DownloadFileInfo(BaseModel):
    """下载文件信息"""
    name: str
    size_bytes: int = Field(default=0, alias="sizeBytes")


class StorageEntry(BaseModel):
    """存储目录条目"""
    path: str
    name: str
    is_dir: bool = Field(default=False, alias="isDir")
    size: int = 0
    updated_at: Optional[datetime] = Field(default=None, alias="updatedAt")


class StorageMountInfo(BaseModel):
    """存储挂载信息"""
    pan_type: str = Field(alias="panType")
    driver: str = ""
    mount_path: str = Field(default="", alias="mountPath")
    status: str = ""


class ProviderCatalog(BaseModel):
    """Provider 目录（按类型分组）"""
    search: List[ProviderMetadata] = Field(default_factory=list)
    pan_search: List[ProviderMetadata] = Field(default_factory=list, alias="panSearch")
    metadata: List[ProviderMetadata] = Field(default_factory=list)
    rss: List[ProviderMetadata] = Field(default_factory=list)
    download: List[ProviderMetadata] = Field(default_factory=list)
    storage: List[ProviderMetadata] = Field(default_factory=list)
    notification: List[ProviderMetadata] = Field(default_factory=list)
