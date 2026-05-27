"""统一 AI 客户端，封装 OpenAI 兼容 API 调用。
支持火山引擎豆包 / DeepSeek / 任意 OpenAI 兼容服务。
"""
import json
import logging
import re
import time
import requests
from typing import Optional

logger = logging.getLogger(__name__)

# ── 调用计量（内存，重启清零） ──

_usage_stats: dict = {}


def _record_usage(scene: str, tokens: int = 0, error: bool = False):
    """记录一次 AI 调用的统计信息"""
    if scene not in _usage_stats:
        _usage_stats[scene] = {"calls": 0, "tokens": 0, "errors": 0}
    _usage_stats[scene]["calls"] += 1
    _usage_stats[scene]["tokens"] += tokens
    if error:
        _usage_stats[scene]["errors"] += 1


def get_usage_stats() -> dict:
    """返回各场景的调用统计"""
    return dict(_usage_stats)


def reset_usage_stats():
    """重置统计（测试用）"""
    _usage_stats.clear()


# ── JSON 提取与校验 ──

def _extract_json(text: str) -> Optional[dict]:
    """从 AI 响应文本中提取 JSON 对象。
    兼容：直接 JSON / markdown 代码块包裹 / 前后有废话。"""
    if not text:
        return None
    text = text.strip()
    # 尝试 1：直接解析
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
        if isinstance(result, list):
            return {"items": result}
    except json.JSONDecodeError:
        pass

    # 尝试 2：从 markdown 代码块提取
    md_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if md_match:
        try:
            return json.loads(md_match.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试 3：从 markdown 代码块提取数组
    md_arr = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', text, re.DOTALL)
    if md_arr:
        try:
            arr = json.loads(md_arr.group(1))
            return {"items": arr}
        except json.JSONDecodeError:
            pass

    # 尝试 4：找第一个 { 到最后一个 }
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        try:
            return json.loads(text[first_brace:last_brace + 1])
        except json.JSONDecodeError:
            pass

    return None


def _validate_schema(data: dict, schema: dict) -> bool:
    """轻量 schema 校验：检查必填字段是否存在、值类型是否匹配。
    schema 格式：{"field": {"type": str/int/float/list/dict/bool, "required": True/False}}
    type 为 None 表示不校验类型。"""
    for field, rules in schema.items():
        required = rules.get("required", False)
        expected_type = rules.get("type")
        if required and field not in data:
            logger.warning(f"[AI Schema] 缺少必填字段: {field}")
            return False
        if field in data and expected_type is not None:
            value = data[field]
            # null 值对非必填字段是合法的
            if value is None and not required:
                continue
            if value is not None and not isinstance(value, expected_type):
                logger.warning(f"[AI Schema] 字段 {field} 类型不匹配: 期望 {expected_type.__name__}, 实际 {type(value).__name__}")
                return False
    return True


# ── AI 客户端 ──

class AIClient:
    """无状态客户端，每次从 config 构造。"""

    def __init__(self, config: dict):
        self.api_key = config.get("openai_api_key", "") or ""
        self.base_url = (config.get("openai_base_url", "") or "").rstrip("/")
        self.model = config.get("openai_model", "") or ""
        self.master_enabled = config.get("ai_enabled", False)
        self.features = config.get("ai_features", {})
        self.enabled = bool(self.master_enabled and self.api_key and self.base_url and self.model)

    def is_feature_enabled(self, feature_name: str) -> bool:
        """检查某个 AI 场景是否生效：master ON + 场景 ON + 凭据完整"""
        return self.enabled and self.features.get(feature_name, False)

    def chat(self, messages: list, temperature: float = 0,
             timeout: int = 20, scene: str = "unknown") -> Optional[str]:
        """发送 chat completion 请求，返回文本内容。失败返回 None。"""
        if not self.enabled:
            return None

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }

        start = time.time()
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
            resp.raise_for_status()
            result = resp.json()
            content = result["choices"][0]["message"]["content"]
            # 记录 token 用量
            usage = result.get("usage", {})
            total_tokens = usage.get("total_tokens", 0)
            elapsed = round(time.time() - start, 2)
            logger.info(f"[AI] scene={scene} tokens={total_tokens} time={elapsed}s")
            _record_usage(scene, tokens=total_tokens)
            return content
        except requests.exceptions.Timeout:
            logger.warning(f"[AI] scene={scene} 超时 ({timeout}s)")
            _record_usage(scene, error=True)
            return None
        except Exception as e:
            logger.error(f"[AI] scene={scene} 调用失败: {e}")
            _record_usage(scene, error=True)
            return None

    def chat_json(self, messages: list, temperature: float = 0,
                  timeout: int = 20, scene: str = "unknown",
                  schema: Optional[dict] = None) -> Optional[dict]:
        """发送请求并解析 JSON 响应。支持可选 schema 校验。失败返回 None。"""
        content = self.chat(messages, temperature=temperature,
                            timeout=timeout, scene=scene)
        if content is None:
            return None

        data = _extract_json(content)
        if data is None:
            logger.warning(f"[AI] scene={scene} JSON 提取失败，原始响应: {content[:200]}")
            return None

        if schema and not _validate_schema(data, schema):
            logger.warning(f"[AI] scene={scene} schema 校验失败")
            return None

        return data


def get_ai_client() -> AIClient:
    """从 shared.config_m 获取配置，构造客户端实例。"""
    from shared import config_m
    conf = config_m.config
    config_dict = conf.dict() if hasattr(conf, "dict") else {}
    return AIClient(config_dict)
