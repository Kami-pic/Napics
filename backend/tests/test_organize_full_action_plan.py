"""organize_full 显式 action_plan 执行入口测试。"""

import asyncio
from types import SimpleNamespace

from routes import organize


class ExplodingRequest:
    async def json(self):
        raise AssertionError("显式 action_plan 场景不应再读取 request body")


def test_organize_full_uses_explicit_action_plan_without_request_body(monkeypatch):
    monkeypatch.setattr(organize, "_get_category_from_path", lambda path: "tv")
    monkeypatch.setattr(organize, "_tmdb_client", lambda: None)
    monkeypatch.setattr(organize, "config_m", SimpleNamespace(load_library=lambda: []))
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
