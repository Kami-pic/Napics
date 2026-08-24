"""JSON 落盘工具：原子写入，避免 NAS 断电或并发写导致文件截断损坏。

先写同目录临时文件并 fsync，再用 os.replace 原子替换目标文件。
os.replace 在同一文件系统上是原子操作（Windows / Linux 均成立），
因此读方永远看到的是完整的旧内容或完整的新内容，不会读到半截 JSON。
"""
import json
import logging
import os
import tempfile
import time
from typing import Any

logger = logging.getLogger(__name__)


_REPLACE_ATTEMPTS = 6
_REPLACE_BACKOFF_SEC = 0.02


def _replace_with_retry(tmp_path: str, path: str) -> None:
    """os.replace + 短重试。

    Windows 上目标文件正被另一次替换或杀软 / 索引服务持有时会抛
    PermissionError(13)，而这只是瞬时占用，重试就能过去。
    首次成功时没有任何额外开销。
    """
    for attempt in range(_REPLACE_ATTEMPTS):
        try:
            os.replace(tmp_path, path)
            return
        except PermissionError:
            if attempt == _REPLACE_ATTEMPTS - 1:
                raise
            time.sleep(_REPLACE_BACKOFF_SEC * (attempt + 1))


def atomic_write_json(path: str, data: Any, *, compact: bool = False, indent: int = 4) -> None:
    """原子写入 JSON 文件。

    compact=True 时用紧凑分隔符（省体积、序列化更快），用于大数据文件；
    否则按 indent 缩进，用于需要人工查看的配置文件。
    """
    dump_kwargs = {"ensure_ascii": False}
    if compact:
        dump_kwargs["separators"] = (",", ":")
    else:
        dump_kwargs["indent"] = indent

    # 临时文件名必须唯一。用固定的 `<path>.tmp` 时两个并发写会争同一个文件：
    # Windows 上直接 PermissionError（两次写入全部失败、调用方却以为保存了），
    # POSIX 上则是内容交错写坏。
    target_dir = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp_path = tempfile.mkstemp(
        dir=target_dir, prefix=os.path.basename(path) + ".", suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, **dump_kwargs)
            f.flush()
            os.fsync(f.fileno())
        _replace_with_retry(tmp_path, path)
    except Exception:
        # 清理残留临时文件，避免下次写入被半成品干扰
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        raise
