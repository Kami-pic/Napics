"""路由响应快照测试辅助模型。"""

from typing import Any

from pydantic import BaseModel, Field


class RouteResponseSnapshot(BaseModel):
    """记录路由响应的稳定字段形状，不保存完整业务数据。"""

    status_code: int
    body_type: str
    field_paths: tuple[str, ...] = Field(default_factory=tuple)
    field_types: dict[str, str] = Field(default_factory=dict)
    list_lengths: dict[str, int] = Field(default_factory=dict)

    @classmethod
    def from_body(cls, status_code: int, body: Any) -> "RouteResponseSnapshot":
        field_types: dict[str, str] = {}
        list_lengths: dict[str, int] = {}

        def walk(value: Any, path: str) -> None:
            if path:
                field_types[path] = _type_name(value)

            if isinstance(value, dict):
                for key in sorted(value):
                    child_path = f"{path}.{key}" if path else str(key)
                    walk(value[key], child_path)
                return

            if isinstance(value, list):
                if path:
                    list_lengths[path] = len(value)
                if value:
                    walk(value[0], f"{path}[]" if path else "[]")

        walk(body, "")
        return cls(
            status_code=status_code,
            body_type=_type_name(body),
            field_paths=tuple(sorted(field_types)),
            field_types=field_types,
            list_lengths=list_lengths,
        )


def _type_name(value: Any) -> str:
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int) and not isinstance(value, bool):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    return type(value).__name__
