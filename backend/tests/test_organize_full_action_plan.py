"""organize_full 显式 action_plan 执行入口测试。"""

import asyncio
from types import SimpleNamespace

from routes import organize
from test_support.fake_library_store import LibraryMutationContract


class ExplodingRequest:
    async def json(self):
        raise AssertionError("显式 action_plan 场景不应再读取 request body")


class _FakeConfigManager(LibraryMutationContract):
    """空媒体库；整理后的对账走 mutate_library，所以必须带上写入契约"""

    def __init__(self):
        self.saved = None

    def load_library(self):
        return []

    def save_library(self, data):
        self.saved = list(data)


def test_organize_full_uses_explicit_action_plan_without_request_body(monkeypatch):
    monkeypatch.setattr(organize, "_get_category_from_path", lambda path: "tv")
    monkeypatch.setattr(organize, "_tmdb_client", lambda: None)
    monkeypatch.setattr(organize, "config_m", _FakeConfigManager())
    monkeypatch.setattr(organize, "shadow_m", SimpleNamespace(auto_fill=lambda *args, **kwargs: False))

    action_plan = {
        "tmdb_match": {},
        "plan": [],
        "folder_type": "",
        "wrap_plan": [],
        "archive_plan": [],
    }

    result = asyncio.run(
        organize.organize_full(
            path=".",
            dry_run=False,
            use_ai=False,
            request=ExplodingRequest(),
            action_plan=action_plan,
        )
    )

    assert result["status"] == "ok"
    assert result["dry_run"] is False
    assert result["steps"]["shadow"] == 0
