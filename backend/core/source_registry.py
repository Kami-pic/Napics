"""搜索源元数据的**唯一**登记处。

## 为什么需要它

源的**实现**早就插件化了（scraper 类由插件注册进 plugin registry），但源的
**元数据**散落硬编码在六处，每处都是一份按源名写死的清单：

| 位置 | 内容 |
|---|---|
| `search_service.BT_SOURCE_DEFAULTS / PAN_SOURCE_DEFAULTS` | 显示名、默认启用、是否需要代理 |
| `bt_search_provider_factory.DIRECT_BT_SOURCE_ORDER` | 有哪些直搜源、什么顺序 |
| `bt_search_provider_factory.LEGACY_SKIP_FILTER_DIRECT_BT_SOURCES` | 哪些源跳过智能过滤 |
| `search_keyword_mapper.SOURCE_LANG_PRIORITY` | 每个源用什么语言的搜索词 |
| `search_keyword_mapper.CN_SEASON_SOURCES / EN_SEASON_SOURCES` | 季号拼「第N季」还是「S0N」 |
| `search_helpers.compute_junk_flags` 里的 `_no_seeder_info` | 哪些源不上报做种数 |

后果是加一个源要改六处、删一个源同样六处，漏一处就是**静默的**错误行为 ——
漏 `SOURCE_LANG_PRIORITY` 会拿默认的英文优先去搜一个中文站，永远 0 条；
漏 `_no_seeder_info` 会让一个只给磁力链接的源全部结果被判成死种。

## 约定

- 所有「按源不同而不同」的行为参数都进 `SourceTraits`，不再新增按源名判断的集合。
- 插件里的 scraper 类可以自己声明 `TRAITS` 覆盖默认值 —— 第三方源自带元数据，
  不需要改主仓库任何一行。
- 查不到的源一律拿 `DEFAULT_TRAITS`，绝不 KeyError：源来自插件，运行时出现
  主仓库不认识的名字是正常情况。

## 本表的数据来源

`label` / `default_enabled` / `needs_proxy` / 登记顺序全部照搬迁移前
`search_service` 里两份表的**实际运行值**（逐条 dump 核对过），
不是凭印象填的 —— 这几个字段直接决定用户看到的源开关状态。
"""

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class SourceTraits:
    """一个搜索源的行为元数据。"""

    # 给人看的名字
    label: str = ""

    # 源类型："bt"（含 Prowlarr 聚合）/ "pan"
    kind: str = "bt"

    # 默认是否启用
    default_enabled: bool = True

    # 是否需要 HTTP 代理才能访问。网盘源一律 None（历史上这个字段只对 BT 源有意义）
    needs_proxy: bool = False

    # 搜索词语言优先级。("en","cn") = 先用英文名，没有再用中文名。
    # 取值：en / cn / original / query
    lang_priority: Tuple[str, ...] = ("en", "cn", "query")

    # 季号拼接格式："cn" → 「进击的巨人 第3季」，"en" → 「Attack on Titan S03」，
    # "" → 不拼季号
    season_format: str = ""

    # 是否上报做种数。不上报的源（只给磁力链接的站）不能按「死种」过滤，
    # 否则它的全部结果都会被判成垃圾。
    reports_seeders: bool = True

    # 走 Prowlarr 聚合而非直搜
    via_prowlarr: bool = False

    # 历史遗留：这批源默认跳过智能过滤
    legacy_skip_filter: bool = False

    # 这个源专注的内容类型，空 tuple 表示通用。取值：anime / movie / tv
    # 用途：番剧专门站拿电影名去搜必然 0 条 —— 那不是源坏了，是不该查它。
    focus: Tuple[str, ...] = ()


DEFAULT_TRAITS = SourceTraits()


# ── 源登记表 ──
#
# 顺序即前端展示顺序与 provider 构建顺序，照搬迁移前的实际顺序。
# 加源在这里加一条就够；删源删这一条就够。
SOURCE_TRAITS: Dict[str, SourceTraits] = {
    # ── 聚合器 ──
    "prowlarr": SourceTraits(
        label="Prowlarr", needs_proxy=False, via_prowlarr=True,
        lang_priority=("en", "cn", "query"), season_format="en",
    ),

    # ── BT 直搜 ──
    "bitsearch": SourceTraits(
        label="Bitsearch", needs_proxy=True, legacy_skip_filter=True,
        lang_priority=("en", "cn"), season_format="en",
    ),
    "cilixiong": SourceTraits(
        label="磁力熊", needs_proxy=False, legacy_skip_filter=True,
        lang_priority=("cn", "en"), season_format="cn",
        reports_seeders=False,
    ),
    "xl720": SourceTraits(
        label="XL720", needs_proxy=False, legacy_skip_filter=True,
        lang_priority=("cn", "en"), season_format="cn",
        reports_seeders=False,
    ),
    "nyaa": SourceTraits(
        label="Nyaa", needs_proxy=True, legacy_skip_filter=True,
        lang_priority=("original", "en", "cn"), season_format="en",
        focus=("anime",),
    ),
    "mikan": SourceTraits(
        label="蜜柑计划", needs_proxy=True, legacy_skip_filter=True,
        lang_priority=("cn", "original", "en"), season_format="cn",
        reports_seeders=False, focus=("anime",),
    ),
    "yts": SourceTraits(
        label="YTS", needs_proxy=True, legacy_skip_filter=True,
        lang_priority=("en", "cn"), season_format="en",
        focus=("movie",),
    ),
    "limetorrents": SourceTraits(
        label="LimeTorrents", default_enabled=False, needs_proxy=True,
        legacy_skip_filter=True,
        lang_priority=("en", "cn"), season_format="en",
    ),
    "acgrip": SourceTraits(
        label="ACG.RIP", default_enabled=False, needs_proxy=True,
        legacy_skip_filter=True,
        lang_priority=("cn", "original", "en"), season_format="cn",
        reports_seeders=False, focus=("anime",),
    ),
    "bangumi_moe": SourceTraits(
        label="Bangumi Moe", needs_proxy=False, legacy_skip_filter=True,
        lang_priority=("cn", "original", "en"), season_format="cn",
        reports_seeders=False, focus=("anime",),
    ),
    "eztv": SourceTraits(
        label="EZTV", default_enabled=False, needs_proxy=True,
        lang_priority=("en", "cn"), season_format="en",
        focus=("tv",),
    ),
    "dmhy": SourceTraits(
        # 国内可直连；标 True 会把它推去走海外代理，用户实测配上代理后这个源反而挂了
        label="动漫花园", needs_proxy=False,
        lang_priority=("cn", "original", "en"), season_format="cn",
        reports_seeders=False, focus=("anime",),
    ),
    "1337x": SourceTraits(
        label="1337x", needs_proxy=True,
        lang_priority=("en", "cn"), season_format="en",
    ),

    # ── 网盘源（中文优先）──
    "pansearch": SourceTraits(
        label="PanSearch", kind="pan",
        lang_priority=("cn", "en"), season_format="cn",
    ),
    "gogopanso": SourceTraits(
        label="狗狗盘搜", kind="pan",
        lang_priority=("cn", "en"), season_format="cn",
    ),
    "github": SourceTraits(
        label="GitHub", kind="pan",
        lang_priority=("cn", "en"), season_format="cn",
    ),
    "rrdynb": SourceTraits(
        label="人人电影", kind="pan",
        lang_priority=("cn", "en"), season_format="cn",
    ),
    "ddys": SourceTraits(
        label="低端影视", kind="pan",
        lang_priority=("cn", "en"), season_format="cn",
    ),
    "sites": SourceTraits(
        label="Sites", kind="pan",
        lang_priority=("cn", "en"), season_format="cn",
    ),
    "slowread": SourceTraits(
        label="慢读", kind="pan",
        lang_priority=("cn", "en"), season_format="cn",
    ),
    "wnsearch": SourceTraits(
        label="万能搜索", kind="pan",
        lang_priority=("cn", "en"), season_format="cn",
    ),
    "pansou": SourceTraits(
        label="PanSou", kind="pan", default_enabled=False,
        lang_priority=("cn", "en"), season_format="cn",
    ),
}


def traits_for(source: str) -> SourceTraits:
    """取一个源的元数据。

    优先用插件里 scraper 类声明的 `TRAITS`（第三方源自带元数据，不必改主仓库），
    其次本文件的登记表，最后 `DEFAULT_TRAITS`。**永不抛异常**。
    """
    declared = _traits_from_plugin(source)
    if declared is not None:
        return declared
    return SOURCE_TRAITS.get(source, DEFAULT_TRAITS)


def _traits_from_plugin(source: str):
    """插件的 scraper 类是否自己声明了 TRAITS。"""
    try:
        from plugin_context import get_plugin_providers

        info = (get_plugin_providers() or {}).get(source) or {}
        declared = getattr(info.get("scraper_class"), "TRAITS", None)
        if isinstance(declared, SourceTraits):
            return declared
    except Exception:
        pass
    return None


# ── 派生视图：调用方一律用这些，不要自己再写按源名的清单 ──

def direct_bt_source_ids() -> Tuple[str, ...]:
    """BT 直搜源（排除走 Prowlarr 聚合的），保持登记顺序。"""
    return tuple(
        name for name, t in SOURCE_TRAITS.items()
        if t.kind == "bt" and not t.via_prowlarr
    )


def legacy_skip_filter_source_ids() -> Tuple[str, ...]:
    return tuple(
        name for name, t in SOURCE_TRAITS.items() if t.legacy_skip_filter
    )


def source_defaults(kind: str) -> Dict[str, dict]:
    """给 `/search/sources` 用的默认配置表。

    形状必须和迁移前 `search_service.BT_SOURCE_DEFAULTS` 完全一致：
    BT 源 `{"label", "enabled", "type", "needs_proxy"}`，
    网盘源 `{"label", "enabled", "type"}`（没有 needs_proxy 键）。
    """
    out: Dict[str, dict] = {}
    for name, t in SOURCE_TRAITS.items():
        if t.kind != kind:
            continue
        entry = {
            "label": t.label or name,
            "enabled": t.default_enabled,
            "type": t.kind,
        }
        # 网盘源的条目历史上**没有** needs_proxy 这个键（不是 None，是不存在）。
        # 凭空加上会改变 /search/sources 的响应形状。
        if kind == "bt":
            entry["needs_proxy"] = t.needs_proxy
        out[name] = entry
    return out


def sources_without_seeders() -> frozenset:
    """不上报做种数的源。它们的结果不能按「死种」判垃圾。"""
    return frozenset(
        name for name, t in SOURCE_TRAITS.items() if not t.reports_seeders
    )


def lang_priority_for(source: str) -> Tuple[str, ...]:
    return traits_for(source).lang_priority


def season_format_for(source: str) -> str:
    return traits_for(source).season_format


def focus_for(source: str) -> Tuple[str, ...]:
    return traits_for(source).focus
