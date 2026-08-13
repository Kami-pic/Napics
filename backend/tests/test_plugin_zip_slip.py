"""插件包解压安全：Zip Slip 防护

恶意插件包可以在压缩包里放 ../../ 路径，解压时覆盖后端源码，
等于远程代码执行。这里锁定四类攻击载荷都被拒绝，同时确认正常插件包不受影响。
"""
import io
import os
import shutil
import tempfile
import zipfile

import pytest

from core.path_guard import (
    UnsafeArchiveError,
    assert_safe_archive_members,
    is_within,
    normalize,
    safe_extract_all,
)


@pytest.fixture
def dest():
    d = tempfile.mkdtemp(prefix="napics_zip_")
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _zip_with(names_and_data):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in names_and_data:
            zf.writestr(name, data)
    buf.seek(0)
    return buf


# ── 恶意载荷必须被拒绝 ──

def test_rejects_parent_traversal(dest):
    with pytest.raises(UnsafeArchiveError):
        assert_safe_archive_members(["../../evil.py"], dest)


def test_rejects_backslash_traversal(dest):
    """Windows 分隔符形式的逃逸"""
    with pytest.raises(UnsafeArchiveError):
        assert_safe_archive_members(["..\\..\\evil.py"], dest)


def test_rejects_absolute_posix_path(dest):
    with pytest.raises(UnsafeArchiveError):
        assert_safe_archive_members(["/etc/cron.d/evil"], dest)


def test_rejects_windows_drive_path(dest):
    with pytest.raises(UnsafeArchiveError):
        assert_safe_archive_members(["C:\\Windows\\System32\\evil.dll"], dest)


def test_rejects_nested_traversal(dest):
    """看似正常的前缀后接逃逸"""
    with pytest.raises(UnsafeArchiveError):
        assert_safe_archive_members(["plugin/sub/../../../../evil.py"], dest)


def test_rejects_when_any_member_unsafe(dest):
    """只要有一个成员越界，整包拒绝（不能部分解压）"""
    with pytest.raises(UnsafeArchiveError):
        assert_safe_archive_members(["manifest.json", "__init__.py", "../evil.py"], dest)


# ── 正常插件包必须放行 ──

def test_allows_normal_plugin_members(dest):
    assert_safe_archive_members(
        ["manifest.json", "__init__.py", "sources/", "sources/scraper.py", "README.md"],
        dest,
    )


def test_allows_internal_relative_navigation(dest):
    """内部 a/../b 折叠后仍在目标内，应放行"""
    assert_safe_archive_members(["sources/../manifest.json"], dest)


# ── 端到端解压 ──

def test_safe_extract_writes_normal_package(dest):
    buf = _zip_with([
        ("manifest.json", '{"id":"test-plugin","name":"测试插件"}'),
        ("__init__.py", "def register(ctx): pass\n"),
    ])
    with zipfile.ZipFile(buf) as zf:
        safe_extract_all(zf, dest)

    assert os.path.isfile(os.path.join(dest, "manifest.json"))
    assert os.path.isfile(os.path.join(dest, "__init__.py"))


def test_safe_extract_blocks_malicious_package(dest):
    """恶意包不能写出任何文件"""
    outside = os.path.join(os.path.dirname(dest), "PWNED_should_not_exist.py")
    buf = _zip_with([
        ("manifest.json", '{"id":"evil","name":"evil"}'),
        ("../PWNED_should_not_exist.py", "import os; os.system('rm -rf /')\n"),
    ])
    with zipfile.ZipFile(buf) as zf:
        with pytest.raises(UnsafeArchiveError):
            safe_extract_all(zf, dest)

    assert not os.path.exists(outside), "恶意成员被写到了目标目录之外"
    assert not os.path.exists(os.path.join(dest, "manifest.json")), "校验失败时不应写入任何文件"


# ── 路径包含判断 ──

def test_is_within_basic(dest):
    assert is_within(os.path.join(dest, "a", "b.txt"), dest) is True
    assert is_within(dest, dest) is True


def test_is_within_rejects_sibling_prefix():
    """/media/video 不能把 /media/video2 当成自己的子目录"""
    assert is_within(os.path.join("/media", "video2", "x.mkv"), os.path.join("/media", "video")) is False


def test_is_within_rejects_outside(dest):
    assert is_within(os.path.join(os.path.dirname(dest), "other", "x.txt"), dest) is False


def test_is_within_handles_trailing_separator(dest):
    """配置里的路径常带尾部分隔符（如 \\\\NAS\\share\\视频\\）"""
    assert is_within(os.path.join(dest, "a.mkv"), dest + os.sep) is True


def test_normalize_is_case_insensitive_on_windows():
    import sys
    if sys.platform != "win32":
        pytest.skip("仅 Windows 大小写不敏感")
    assert normalize("C:\\Temp\\A") == normalize("c:\\temp\\a")


def test_empty_inputs_are_safe():
    assert is_within("", "/media") is False
    assert is_within("/media/x", "") is False
