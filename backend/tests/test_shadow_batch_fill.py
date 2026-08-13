"""影子名批量填充：验证 apply_auto_fill 与 auto_fill 的优先级规则完全等价"""
import json
import os
import shutil
import tempfile

import pytest

from shadow_name_manager import ShadowNameManager, apply_auto_fill


@pytest.fixture
def workdir():
    d = tempfile.mkdtemp(prefix="napics_shadow_")
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _mgr_with(workdir, library):
    path = os.path.join(workdir, "media_library.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(library, f, ensure_ascii=False)
    return ShadowNameManager(library_path=path), path


# ── 优先级等价性：逐个来源组合对比两条实现 ──

_SOURCES = ["manual", "nfo", "tmdb", "douban", "bangumi", "scrape", "parsed", ""]


@pytest.mark.parametrize("existing", _SOURCES)
@pytest.mark.parametrize("incoming", _SOURCES)
def test_apply_auto_fill_matches_auto_fill(workdir, existing, incoming):
    """内存版与落盘版必须给出相同的接受/拒绝判定和相同的字段结果"""
    fp = "/media/电影/a.mkv"

    # 落盘版
    lib_item = {"file_path": fp, "shadow_name": "旧名", "shadow_name_source": existing}
    mgr, path = _mgr_with(workdir, [lib_item])
    disk_result = mgr.auto_fill(fp, "新名", source=incoming, tmdb_id=123)
    with open(path, encoding="utf-8") as f:
        disk_item = json.load(f)[0]

    # 内存版
    mem_item = {"file_path": fp, "shadow_name": "旧名", "shadow_name_source": existing}
    mem_result = apply_auto_fill(mem_item, "新名", source=incoming, tmdb_id=123)

    assert disk_result == mem_result, f"判定不一致: existing={existing} incoming={incoming}"
    assert disk_item.get("shadow_name") == mem_item.get("shadow_name")
    assert disk_item.get("shadow_name_source") == mem_item.get("shadow_name_source")
    assert disk_item.get("shadow_tmdb_id") == mem_item.get("shadow_tmdb_id")


def test_apply_auto_fill_fills_empty_item():
    """全新条目（无任何影子名字段）应被填充"""
    item = {"file_path": "/media/x.mkv"}
    assert apply_auto_fill(item, "权力的游戏 (2011)", source="parsed") is True
    assert item["shadow_name"] == "权力的游戏 (2011)"
    assert item["shadow_name_source"] == "parsed"
    assert item["organize_status"] == "ok"


def test_manual_not_overwritten_by_parsed():
    """手动设置的影子名不能被解析结果覆盖"""
    item = {"file_path": "/media/x.mkv", "shadow_name": "我的命名", "shadow_name_source": "manual"}
    assert apply_auto_fill(item, "自动解析名", source="parsed") is False
    assert item["shadow_name"] == "我的命名"


def test_same_priority_overwrites():
    """同优先级允许覆盖（与原 auto_fill 的 > 判定一致）"""
    item = {"file_path": "/media/x.mkv", "shadow_name": "旧", "shadow_name_source": "tmdb"}
    assert apply_auto_fill(item, "新", source="nfo") is True
    assert item["shadow_name"] == "新"


def test_batch_does_not_touch_disk(workdir):
    """批量应用不应产生任何文件写入"""
    _, path = _mgr_with(workdir, [{"file_path": "/media/a.mkv"}])
    before = os.path.getmtime(path)

    items = [{"file_path": f"/media/{i}.mkv"} for i in range(100)]
    filled = sum(1 for it in items if apply_auto_fill(it, "名字", source="parsed"))

    assert filled == 100
    assert os.path.getmtime(path) == before
