"""评审用临时测试：_extract_json 边界情况 + _validate_schema 边界"""
import json
import re
from ai_client import _extract_json, _validate_schema


def test_markdown_regex_nongreedy():
    """markdown 正则非贪婪匹配 vs 嵌套花括号"""
    bt = "```"
    # 嵌套对象: {"a": {"b": 1}}
    inner = json.dumps({"a": {"b": 1}})
    text = f"{bt}json\n{inner}\n{bt}"
    
    # 检查正则匹配的是什么
    pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
    m = re.search(pattern, text, re.DOTALL)
    if m:
        print(f"regex captured: {m.group(1)!r}")
    else:
        print("no regex match")
    
    result = _extract_json(text)
    print(f"_extract_json result: {result}")
    # 非贪婪 .*? 会在第一个 } 停下，匹配 '{"a": {"b": 1}'
    # 这会导致 JSON 解析失败，然后 fallback 到策略 4（first { to last }）
    # 策略 4 会成功，因为整个文本中 first { 到 last } 就是完整的 JSON
    assert result is not None, "Should still parse via fallback"


def test_validate_schema_required_null():
    """required=True 的字段值为 None 时应该校验失败"""
    schema = {"name": {"type": str, "required": True}}
    result = _validate_schema({"name": None}, schema)
    print(f"required field is None: {result}")
    # 当前实现: value is None and not required → continue
    # 但 required=True 时 value=None 也会走到 isinstance 检查
    # None is not str → 应该返回 False
    # 实际上代码逻辑是:
    # if value is None and not required: continue  ← required=True 时不走这个分支
    # if value is not None and not isinstance(value, expected_type): return False
    # ← value IS None, 所以这个条件也不满足
    # 结果: 返回 True（通过校验）
    # 这是一个 BUG: required=True 的字段值为 None 应该校验失败


def test_two_json_objects_in_text():
    """文本中有两个独立 JSON 对象"""
    text = "first: " + json.dumps({"a": 1}) + " second: " + json.dumps({"b": 2})
    result = _extract_json(text)
    print(f"two objects: {result}")
    # 策略 4: first { to last } → '{"a": 1} second: {"b": 2}' → 无效 JSON → None


def test_extract_json_with_none():
    """None 输入"""
    result = _extract_json(None)
    print(f"None input: {result}")
    assert result is None


if __name__ == "__main__":
    test_markdown_regex_nongreedy()
    test_validate_schema_required_null()
    test_two_json_objects_in_text()
    test_extract_json_with_none()
    print("\nAll edge case tests completed")
