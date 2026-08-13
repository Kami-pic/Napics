"""JSON 落盘工具：原子写入，避免 NAS 断电或并发写导致文件截断损坏。

先写同目录临时文件并 fsync，再用 os.replace 原子替换目标文件。
os.replace 在同一文件系统上是原子操作（Windows / Linux 均成立），
因此读方永远看到的是完整的旧内容或完整的新内容，不会读到半截 JSON。
"""
import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def atomic_write_json(path: str, data: Any, *, compact: bool = False, indent: int = 4) -> None:
    """原子写入 JSON 文件。

    compact=True 时用紧凑分隔符（省体积、序列化更快），用于大数据文件；
    否则按 indent 缩进，用于需要人工查看的配置文件。
    """
    tmp_path = f"{path}.tmp"
    dump_kwargs = {"ensure_ascii": False}
    if compact:
        dump_kwargs["separators"] = (",", ":")
    else:
        dump_kwargs["indent"] = indent

    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, **dump_kwargs)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        # 清理残留临时文件，避免下次写入被半成品干扰
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        raise
