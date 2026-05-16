import logging

import pytest

from provider_context import MappingConfigView, MemoryProviderCache, ProviderContext
from provider_models import (
    ProviderKind,
    ProviderMetadata,
    ProviderRiskLevel,
    DownloadRequest,
    DownloadSubmitResult,
    DownloadTaskInfo,
    SearchCandidate,
    SearchRequest,
)


def test_provider_metadata_uses_stable_aliases_and_dedupes_lists():
    metadata = ProviderMetadata(
        id="example",
        name="Example",
        kind=ProviderKind.SEARCH,
        enabled=True,
        defaultEnabled=True,
        capabilities=["search", "search", "magnet", ""],
        riskLevel=ProviderRiskLevel.USER_CONFIGURED,
        supportsProxy=True,
    )

    payload = metadata.model_dump(by_alias=True)

    assert payload["id"] == "example"
    assert payload["defaultEnabled"] is True
    assert payload["riskLevel"] == "user_configured"
    assert payload["supportsProxy"] is True
    assert payload["capabilities"] == ["search", "magnet"]


def test_provider_metadata_rejects_unstable_id():
    with pytest.raises(ValueError):
        ProviderMetadata(id="Example", name="Example", kind=ProviderKind.SEARCH)


def test_provider_context_injects_config_logger_and_cache():
    context = ProviderContext(
        config=MappingConfigView({"proxy": "http://127.0.0.1:7890"}),
        logger=logging.getLogger("test.providers"),
        cache=MemoryProviderCache(),
    )

    context.cache.set("provider:key", "value")

    assert context.config.get("proxy") == "http://127.0.0.1:7890"
    assert context.cache.get("provider:key") == "value"
    assert context.runtime_info.profile == "open-core"


def test_search_dto_round_trip_uses_structured_models():
    request = SearchRequest(query="test", timeoutSec=3)
    candidate = SearchCandidate(
        title="Result",
        providerId="example",
        downloadUrl="magnet:?xt=urn:btih:abc",
        sizeGb=1.5,
        infoHash="ABC",
    )

    assert request.timeout_sec == 3
    assert candidate.model_dump(by_alias=True)["providerId"] == "example"
    assert candidate.model_dump(by_alias=True)["sizeGb"] == 1.5


def test_download_dto_round_trip_uses_structured_models():
    request = DownloadRequest(
        url="magnet:?xt=urn:btih:abc",
        savePath="/downloads",
    )
    result = DownloadSubmitResult(success=True, externalTaskId="task-1")

    assert request.save_path == "/downloads"
    assert result.model_dump(by_alias=True)["externalTaskId"] == "task-1"


def test_download_task_info_round_trip_uses_structured_models():
    task = DownloadTaskInfo(
        externalTaskId="hash-1",
        name="Show S01",
        savePath="/downloads",
        progress=0.5,
        status="downloading",
    )

    payload = task.model_dump(by_alias=True)

    assert task.external_task_id == "hash-1"
    assert payload["savePath"] == "/downloads"
