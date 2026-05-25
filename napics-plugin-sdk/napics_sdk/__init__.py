"""Napics Plugin SDK — 插件开发所需的协议、模型和上下文。

使用方式：
    from napics_sdk import SearchCandidate, PanSearchCandidate, RSSCandidate
    from napics_sdk import ProviderKind, ProviderMetadata
    from napics_sdk import ScraperBase  # 爬虫基类（仅在 napics 运行时可用）
"""

from napics_sdk.models import (
    AliasSet,
    ArtworkInfo,
    DownloadFileInfo,
    DownloadProgress,
    DownloadRequest,
    DownloadSubmitResult,
    DownloadTaskInfo,
    EpisodeInfo,
    MetadataCandidate,
    MetadataDetail,
    MetadataSearchRequest,
    PanSearchCandidate,
    ProviderCatalog,
    ProviderHealth,
    ProviderHealthStatus,
    ProviderKind,
    ProviderMetadata,
    ProviderRiskLevel,
    RSSCandidate,
    RSSFetchRequest,
    SearchCandidate,
    SearchKeywordSet,
    SearchRequest,
    StorageEntry,
    StorageMountInfo,
)

from napics_sdk.context import ProviderContext, ProviderConfigView, ProviderRuntimeInfo

__version__ = "0.1.0"

__all__ = [
    # 模型
    "AliasSet",
    "ArtworkInfo",
    "DownloadFileInfo",
    "DownloadProgress",
    "DownloadRequest",
    "DownloadSubmitResult",
    "DownloadTaskInfo",
    "EpisodeInfo",
    "MetadataCandidate",
    "MetadataDetail",
    "MetadataSearchRequest",
    "PanSearchCandidate",
    "ProviderCatalog",
    "ProviderHealth",
    "ProviderHealthStatus",
    "ProviderKind",
    "ProviderMetadata",
    "ProviderRiskLevel",
    "RSSCandidate",
    "RSSFetchRequest",
    "SearchCandidate",
    "SearchKeywordSet",
    "SearchRequest",
    "StorageEntry",
    "StorageMountInfo",
    # 上下文
    "ProviderContext",
    "ProviderConfigView",
    "ProviderRuntimeInfo",
]
