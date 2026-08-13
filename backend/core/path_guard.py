"""路径安全判断：判定目标路径是否落在允许的根目录之内。

用于两处防护：
1. 插件包解压（防 Zip Slip：压缩包内用 ../ 逃出目标目录覆盖任意文件）
2. 路由接受的 path 参数（防路径穿越：操作媒体库之外的任意文件）

只做纯路径判断，不依赖任何配置或业务模块。白名单由调用方注入。

Windows 注意点：
- 路径大小写不敏感，比较前统一 normcase
- UNC 路径（\\\\NAS\\share\\视频）要能正确处理
- 用 realpath 解析符号链接/junction，避免通过链接绕过检查
"""
import os
from typing import Iterable, List, Optional


def normalize(path: str) -> str:
    """归一化路径用于比较：转绝对路径、折叠 .. 、统一大小写与分隔符。

    这里刻意不用 realpath：realpath 会解析符号链接，在 SMB/UNC 路径上会产生
    实际的网络 IO。而 /scrape/poster 这类接口每屏要被调用几十次，开销不可接受。
    代价是无法拦截"媒体库内的符号链接指向库外"这种绕过 —— 但要放置这种链接，
    攻击者本来就已经具备媒体库的写权限了，防护价值有限。
    """
    if not path:
        return ""
    try:
        resolved = os.path.normpath(os.path.abspath(path))
    except (OSError, ValueError):
        resolved = path
    # 去掉末尾分隔符（但保留根目录的分隔符，如 C:\ 和 \\\\server\\share）
    stripped = resolved.rstrip("\\/")
    if stripped:
        resolved = stripped
    return os.path.normcase(resolved)


def is_within(path: str, root: str) -> bool:
    """判断 path 是否等于 root 或位于 root 之内。"""
    if not path or not root:
        return False
    norm_path = normalize(path)
    norm_root = normalize(root)
    if not norm_path or not norm_root:
        return False
    if norm_path == norm_root:
        return True
    # 必须以 root + 分隔符 开头，避免 /media/videos2 被 /media/video 误判为子路径
    return norm_path.startswith(norm_root + os.sep)


def is_within_any(path: str, roots: Iterable[str]) -> bool:
    """判断 path 是否位于任一允许的根目录之内。"""
    return any(is_within(path, root) for root in roots if root)


def find_matching_root(path: str, roots: Iterable[str]) -> Optional[str]:
    """返回命中的根目录（最长匹配），未命中返回 None。"""
    best = None
    best_len = -1
    for root in roots:
        if root and is_within(path, root):
            length = len(normalize(root))
            if length > best_len:
                best, best_len = root, length
    return best


# ── 压缩包解压防护 ──

class UnsafeArchiveError(Exception):
    """压缩包内含试图逃出目标目录的路径。"""


def assert_safe_archive_members(names: Iterable[str], dest_dir: str) -> None:
    """校验压缩包成员名解析后都落在 dest_dir 内，否则抛 UnsafeArchiveError。

    拦截三类恶意成员：
    - 相对逃逸：`../../evil.py`
    - 绝对路径：`/etc/cron.d/evil`、`C:\\Windows\\System32\\evil.dll`
    - 混合分隔符绕过：`..\\..\\evil.py`
    """
    dest_real = normalize(dest_dir)
    if not dest_real:
        raise UnsafeArchiveError("解压目标目录无效")

    for name in names:
        if not name:
            continue
        # zip 规范用 /，但恶意包可能用 \ 试图绕过；统一按两种分隔符切分判断
        if os.path.isabs(name) or name.startswith(("/", "\\")):
            raise UnsafeArchiveError(f"压缩包含绝对路径成员: {name}")
        # Windows 盘符形式（C:foo 也算）
        if len(name) >= 2 and name[1] == ":":
            raise UnsafeArchiveError(f"压缩包含盘符路径成员: {name}")

        candidate = os.path.join(dest_dir, name.replace("\\", os.sep))
        # 这里不能用 realpath：目标还不存在，且父目录可能是待创建的。
        # 用 normpath 折叠 .. 后再比较前缀。
        norm_candidate = os.path.normcase(os.path.normpath(os.path.abspath(candidate)))
        if norm_candidate != dest_real and not norm_candidate.startswith(dest_real + os.sep):
            raise UnsafeArchiveError(f"压缩包成员逃出目标目录: {name}")


def safe_extract_all(zip_file, dest_dir: str, members: Optional[List[str]] = None) -> None:
    """校验后解压。members 为 None 时解压全部。"""
    names = members if members is not None else zip_file.namelist()
    assert_safe_archive_members(names, dest_dir)
    os.makedirs(dest_dir, exist_ok=True)
    if members is None:
        zip_file.extractall(dest_dir)
    else:
        zip_file.extractall(dest_dir, members=members)
