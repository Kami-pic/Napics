"""Provider 契约 DTO。

本模块只定义 Core 与 Provider 之间的结构化数据边界，不绑定任何具体实现。
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
    cn: str = ""
    en: str = ""
    original: str = ""
    shadow: str = ""
    clean: str = ""
    fallbacks: List[str] = Field(default_factory=list)


class SearchRequest(BaseModel):
    query: str
    media_type: str = ""
    year: Optional[int] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    keywords: SearchKeywordSet = Field(default_factory=SearchKeywordSet)
    limit: int = 50
    timeout_sec: float = Field(default=15.0, alias="timeoutSec")


class SearchCandidate(BaseModel):
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
    subscription_id: str = Field(default="", alias="subscriptionId")
    title: str = ""
    media_type: str = Field(default="", alias="mediaType")
    keywords: SearchKeywordSet = Field(default_factory=SearchKeywordSet)
    limit: int = 50
    since: Optional[datetime] = None


class RSSCandidate(BaseModel):
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
    query: str
    media_type: str = Field(default="", alias="mediaType")
    year: Optional[int] = None
    limit: int = 20


class MetadataCandidate(BaseModel):
    provider_id: str = Field(alias="providerId")
    external_id: str = Field(alias="externalId")
    title: str
    original_title: str = Field(default="", alias="originalTitle")
    year: Optional[int] = None
    media_type: str = Field(default="", alias="mediaType")
    overview: str = ""
    poster_url: str = Field(default="", alias="posterUrl")
    rating: Optional[float] = None


class EpisodeInfo(BaseModel):
    season: int
    episode: int
    title: str = ""
    air_date: str = Field(default="", alias="airDate")


class ArtworkInfo(BaseModel):
    kind: str
    url: str
    language: str = ""


class AliasSet(BaseModel):
    cn: str = ""
    en: str = ""
    original: str = ""
    aliases: List[str] = Field(default_factory=list)


class MetadataDetail(BaseModel):
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


class DownloadRequest(BaseModel):
    url: str
    save_path: str = Field(alias="savePath")
    category: str = ""
    metadata: ProviderMetadata | None = None


class DownloadSubmitResult(BaseModel):
    success: bool
    external_task_id: str = Field(default="", alias="externalTaskId")
    error_code: str = Field(default="", alias="errorCode")
    message: str = ""


class DownloadProgress(BaseModel):
    external_task_id: str = Field(alias="externalTaskId")
    progress: float = 0.0
    speed: str = ""
    eta: str = ""
    status: str = ""
    files: List[str] = Field(default_factory=list)


class StorageEntry(BaseModel):
    path: str
    name: str
    is_dir: bool = Field(default=False, alias="isDir")
    size: int = 0
    updated_at: Optional[datetime] = Field(default=None, alias="updatedAt")


class ProviderCatalog(BaseModel):
    search: List[ProviderMetadata] = Field(default_factory=list)
    pan_search: List[ProviderMetadata] = Field(default_factory=list, alias="panSearch")
    metadata: List[ProviderMetadata] = Field(default_factory=list)
    rss: List[ProviderMetadata] = Field(default_factory=list)
    download: List[ProviderMetadata] = Field(default_factory=list)
    storage: List[ProviderMetadata] = Field(default_factory=list)
    notification: List[ProviderMetadata] = Field(default_factory=list)


JsonValue = Any
