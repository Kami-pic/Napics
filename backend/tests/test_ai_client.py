"""ai_client.py 单元测试"""
import json
import pytest
from unittest.mock import patch, MagicMock
from ai_client import (
    AIClient, _extract_json, _validate_schema,
    get_usage_stats, reset_usage_stats, _record_usage,
)


# ── _extract_json 测试 ──

class TestExtractJson:
    def test_direct_json(self):
        assert _extract_json('{"a": 1}') == {"a": 1}

    def test_markdown_code_block(self):
        text = '这是结果：\n```json\n{"a": 1}\n```\n完毕'
        assert _extract_json(text) == {"a": 1}

    def test_markdown_no_lang(self):
        text = '```\n{"a": 1}\n```'
        assert _extract_json(text) == {"a": 1}

    def test_json_with_surrounding_text(self):
        text = '好的，结果如下：\n{"a": 1}\n希望对你有帮助'
        assert _extract_json(text) == {"a": 1}

    def test_array_response(self):
        text = '[{"a": 1}, {"b": 2}]'
        result = _extract_json(text)
        assert result == {"items": [{"a": 1}, {"b": 2}]}

    def test_empty_input(self):
        assert _extract_json("") is None
        assert _extract_json(None) is None

    def test_invalid_json(self):
        assert _extract_json("这不是 JSON") is None

    def test_nested_json(self):
        text = '{"results": [{"index": 1, "title": "test"}]}'
        result = _extract_json(text)
        assert result["results"][0]["title"] == "test"


# ── _validate_schema 测试 ──

class TestValidateSchema:
    def test_valid(self):
        data = {"name": "test", "age": 25}
        schema = {
            "name": {"type": str, "required": True},
            "age": {"type": int, "required": True},
        }
        assert _validate_schema(data, schema) is True

    def test_missing_required(self):
        data = {"name": "test"}
        schema = {"name": {"type": str, "required": True}, "age": {"type": int, "required": True}}
        assert _validate_schema(data, schema) is False

    def test_wrong_type(self):
        data = {"name": 123}
        schema = {"name": {"type": str, "required": True}}
        assert _validate_schema(data, schema) is False

    def test_optional_null(self):
        data = {"name": "test", "year": None}
        schema = {
            "name": {"type": str, "required": True},
            "year": {"type": str, "required": False},
        }
        assert _validate_schema(data, schema) is True

    def test_optional_missing(self):
        data = {"name": "test"}
        schema = {
            "name": {"type": str, "required": True},
            "year": {"type": str, "required": False},
        }
        assert _validate_schema(data, schema) is True


# ── AIClient 测试 ──

class TestAIClient:
    def test_disabled_when_no_key(self):
        client = AIClient({"openai_api_key": "", "openai_base_url": "http://x", "openai_model": "m", "ai_enabled": True})
        assert client.enabled is False

    def test_disabled_when_master_off(self):
        client = AIClient({"openai_api_key": "sk-x", "openai_base_url": "http://x", "openai_model": "m", "ai_enabled": False})
        assert client.enabled is False

    def test_enabled_when_all_set(self):
        client = AIClient({
            "openai_api_key": "sk-x", "openai_base_url": "http://x",
            "openai_model": "m", "ai_enabled": True,
        })
        assert client.enabled is True

    def test_feature_check(self):
        client = AIClient({
            "openai_api_key": "sk-x", "openai_base_url": "http://x",
            "openai_model": "m", "ai_enabled": True,
            "ai_features": {"extract_episode": True, "search_recommend": False},
        })
        assert client.is_feature_enabled("extract_episode") is True
        assert client.is_feature_enabled("search_recommend") is False
        assert client.is_feature_enabled("nonexistent") is False

    def test_chat_returns_none_when_disabled(self):
        client = AIClient({"ai_enabled": False})
        assert client.chat([{"role": "user", "content": "hi"}]) is None

    @patch("ai_client.requests.post")
    def test_chat_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"total_tokens": 10},
        }
        mock_post.return_value = mock_resp

        reset_usage_stats()
        client = AIClient({
            "openai_api_key": "sk-x", "openai_base_url": "http://test.com",
            "openai_model": "m", "ai_enabled": True,
        })
        result = client.chat([{"role": "user", "content": "hi"}], scene="test_scene")
        assert result == "ok"
        stats = get_usage_stats()
        assert stats["test_scene"]["calls"] == 1
        assert stats["test_scene"]["tokens"] == 10

    @patch("ai_client.requests.post")
    def test_chat_json_with_schema(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": '{"clean_title": "测试", "year": null}'}}],
            "usage": {"total_tokens": 15},
        }
        mock_post.return_value = mock_resp

        client = AIClient({
            "openai_api_key": "sk-x", "openai_base_url": "http://test.com",
            "openai_model": "m", "ai_enabled": True,
        })
        schema = {"clean_title": {"type": str, "required": True}}
        result = client.chat_json(
            [{"role": "user", "content": "test"}],
            scene="test", schema=schema,
        )
        assert result["clean_title"] == "测试"

    @patch("ai_client.requests.post")
    def test_chat_json_schema_fail(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": '{"wrong_field": 1}'}}],
            "usage": {"total_tokens": 5},
        }
        mock_post.return_value = mock_resp

        client = AIClient({
            "openai_api_key": "sk-x", "openai_base_url": "http://test.com",
            "openai_model": "m", "ai_enabled": True,
        })
        schema = {"clean_title": {"type": str, "required": True}}
        result = client.chat_json(
            [{"role": "user", "content": "test"}],
            scene="test", schema=schema,
        )
        assert result is None  # schema 校验失败


# ── 计量测试 ──

class TestUsageStats:
    def test_record_and_get(self):
        reset_usage_stats()
        _record_usage("test_scene", tokens=100)
        _record_usage("test_scene", tokens=50)
        _record_usage("test_scene", error=True)
        stats = get_usage_stats()
        assert stats["test_scene"]["calls"] == 3
        assert stats["test_scene"]["tokens"] == 150
        assert stats["test_scene"]["errors"] == 1

    def test_reset(self):
        _record_usage("x", tokens=1)
        reset_usage_stats()
        assert get_usage_stats() == {}
