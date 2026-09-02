"""源元数据只能有一处登记。

## 背景

源的实现早就插件化了，但元数据曾经散落硬编码在六处：`BT_SOURCE_DEFAULTS`、
`PAN_SOURCE_DEFAULTS`、`DIRECT_BT_SOURCE_ORDER`、
`LEGACY_SKIP_FILTER_DIRECT_BT_SOURCES`、`SOURCE_LANG_PRIORITY`、
`CN_SEASON_SOURCES`/`EN_SEASON_SOURCES`、以及 `compute_junk_flags` 里的
`_no_seeder_info`。加一个源要改六处，漏一处就是**静默的**错误行为：

- 漏 `SOURCE_LANG_PRIORITY` → 拿默认的英文优先去搜一个中文站，永远 0 条
- 漏 `_no_seeder_info` → 只给磁力链接的源，全部结果被判成死种

这个文件钉住「只有一处登记」这件事。
"""
import io
import os

import pytest

from core.source_registry import (
    DEFAULT_TRAITS, SOURCE_TRAITS, SourceTraits,
    direct_bt_source_ids, focus_for, lang_priority_for,
    legacy_skip_filter_source_ids, season_format_for, source_defaults,
    sources_without_seeders, traits_for,
)

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

VALID_LANGS = {"en", "cn", "original", "query"}
VALID_SEASON_FORMATS = {"cn", "en", ""}
VALID_KINDS = {"bt", "pan"}
VALID_FOCUS = {"anime", "movie", "tv"}


# ── 登记表自身的完整性 ──

def test_every_source_has_a_label():
    """label 是用户在设置页看到的名字，空的话开关列表里会出现一个裸 id。"""
    missing = [name for name, t in SOURCE_TRAITS.items() if not t.label]
    assert missing == [], f"这些源没有 label: {missing}"


def test_every_source_has_valid_lang_priority():
    for name, t in SOURCE_TRAITS.items():
        assert t.lang_priority, f"{name} 没有语言优先级 —— 会拿默认英文优先去搜"
        bad = set(t.lang_priority) - VALID_LANGS
        assert not bad, f"{name} 的语言优先级含未知取值 {bad}"


def test_every_source_has_valid_season_format():
    for name, t in SOURCE_TRAITS.items():
        assert t.season_format in VALID_SEASON_FORMATS, \
            f"{name} 的季号格式 {t.season_format!r} 不合法"


def test_every_source_has_valid_kind_and_focus():
    for name, t in SOURCE_TRAITS.items():
        assert t.kind in VALID_KINDS, f"{name} 的 kind {t.kind!r} 不合法"
        bad = set(t.focus) - VALID_FOCUS
        assert not bad, f"{name} 的 focus 含未知取值 {bad}"


def test_pan_sources_all_use_chinese_season_format():
    """网盘源都是中文站，季号一律「第N季」。"""
    for name, t in SOURCE_TRAITS.items():
        if t.kind == "pan":
            assert t.season_format == "cn", f"网盘源 {name} 的季号格式应该是 cn"


# ── 未知源不能炸 ──

def test_unknown_source_falls_back_to_defaults():
    """源来自插件，运行时出现主仓库不认识的名字是**正常情况**，不是异常。"""
    assert traits_for("某个第三方插件带来的源") is DEFAULT_TRAITS
    assert lang_priority_for("完全不存在") == DEFAULT_TRAITS.lang_priority
    assert season_format_for("完全不存在") == DEFAULT_TRAITS.season_format
    assert focus_for("完全不存在") == ()


def test_traits_for_tolerates_empty_name():
    assert traits_for("") is DEFAULT_TRAITS


# ── 派生视图必须和登记表一致 ──

def test_direct_bt_excludes_prowlarr():
    """Prowlarr 是聚合器，不是直搜源。"""
    ids = direct_bt_source_ids()
    assert "prowlarr" not in ids
    assert "bitsearch" in ids


def test_direct_bt_only_contains_bt_kind():
    pan = {name for name, t in SOURCE_TRAITS.items() if t.kind == "pan"}
    assert not (set(direct_bt_source_ids()) & pan), "网盘源不该出现在 BT 直搜清单里"


def test_derived_views_stay_in_sync_with_the_table():
    assert set(sources_without_seeders()) == {
        name for name, t in SOURCE_TRAITS.items() if not t.reports_seeders
    }
    assert set(legacy_skip_filter_source_ids()) == {
        name for name, t in SOURCE_TRAITS.items() if t.legacy_skip_filter
    }


def test_keyword_mapper_views_are_derived_not_duplicated():
    """search_keyword_mapper 里那三个名字必须是派生视图，不能是第二份数据。"""
    from search_keyword_mapper import (
        CN_SEASON_SOURCES, EN_SEASON_SOURCES, SOURCE_LANG_PRIORITY,
    )

    assert set(SOURCE_LANG_PRIORITY) == set(SOURCE_TRAITS)
    for name, t in SOURCE_TRAITS.items():
        assert SOURCE_LANG_PRIORITY[name] == list(t.lang_priority)
    assert CN_SEASON_SOURCES == {
        n for n, t in SOURCE_TRAITS.items() if t.season_format == "cn"
    }
    assert EN_SEASON_SOURCES == {
        n for n, t in SOURCE_TRAITS.items() if t.season_format == "en"
    }
    # 一个源不能同时两种季号格式
    assert not (CN_SEASON_SOURCES & EN_SEASON_SOURCES)


def test_factory_constants_are_derived():
    import bt_search_provider_factory as factory

    assert factory.DIRECT_BT_SOURCE_ORDER == direct_bt_source_ids()
    assert factory.LEGACY_SKIP_FILTER_DIRECT_BT_SOURCES == legacy_skip_filter_source_ids()


# ── /search/sources 的响应形状不能变 ──

def test_bt_defaults_shape():
    """BT 条目必须是 label/enabled/type/needs_proxy 四个键 —— 前端按这个形状渲染开关。"""
    bt = source_defaults("bt")
    assert bt, "BT 默认表不能为空"
    for name, entry in bt.items():
        assert set(entry) == {"label", "enabled", "type", "needs_proxy"}, \
            f"{name} 的键集合变了: {sorted(entry)}"
        assert entry["type"] == "bt"
        assert isinstance(entry["enabled"], bool)


def test_pan_defaults_shape():
    """网盘条目历史上**没有** needs_proxy 键。凭空加上会改变接口响应形状。"""
    pan = source_defaults("pan")
    assert pan, "网盘默认表不能为空"
    for name, entry in pan.items():
        assert set(entry) == {"label", "enabled", "type"}, \
            f"{name} 的键集合变了: {sorted(entry)}"
        assert entry["type"] == "pan"


def test_search_service_tables_are_derived():
    import search_service

    assert search_service.BT_SOURCE_DEFAULTS == source_defaults("bt")
    assert search_service.PAN_SOURCE_DEFAULTS == source_defaults("pan")


def test_defaults_preserve_registration_order():
    """顺序即前端展示顺序，不能因为改成派生就乱掉。"""
    assert list(source_defaults("bt")) == [
        n for n, t in SOURCE_TRAITS.items() if t.kind == "bt"
    ]


# ── 别处不许再出现按源名写死的清单 ──

_SOURCE_NAME_SAMPLES = ("cilixiong", "bangumi_moe", "acgrip", "limetorrents")


@pytest.mark.parametrize("rel_path", [
    "search_keyword_mapper.py",
    "search_service.py",
    "bt_search_provider_factory.py",
    "search_helpers.py",
])
def test_no_hardcoded_source_names_outside_the_registry(rel_path):
    """这四个文件曾各自维护一份源名清单，现在都必须从登记表读。

    判据是「不出现具体源名字面量」。想加按源区分的行为，就在 SourceTraits
    里加一个字段，不要在这里写 `if source in {...}`。
    """
    path = os.path.join(_BACKEND, rel_path)
    src = io.open(path, encoding="utf-8").read()
    # 只看代码，注释里提源名是允许的（说明历史缘由需要举例）
    code = "\n".join(
        line.split("#", 1)[0] for line in src.splitlines()
    )
    found = [name for name in _SOURCE_NAME_SAMPLES if f'"{name}"' in code or f"'{name}'" in code]
    assert found == [], f"{rel_path} 里还有写死的源名 {found} —— 应该改成读 SourceTraits"


def test_scraper_declared_traits_win(monkeypatch):
    """插件里的 scraper 类可以自带元数据，不需要改主仓库。"""
    import core.source_registry as registry

    custom = SourceTraits(label="第三方源", lang_priority=("original",), season_format="cn")

    class FakeScraper:
        TRAITS = custom

    monkeypatch.setattr(
        registry, "_traits_from_plugin",
        lambda source: custom if source == "third_party" else None,
    )
    assert registry.traits_for("third_party") is custom
    assert registry.traits_for("bitsearch") is SOURCE_TRAITS["bitsearch"]
