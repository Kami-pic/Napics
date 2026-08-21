"""钉住 .dockerignore 插件白名单与 CORE_BUILTIN_PLUGIN_IDS 的一致性。

踩过的坑：plugin_manager 把 subtitle-search / feature-player 列为核心内置插件，
但 .dockerignore 的白名单忘了同步放行，镜像里就没有这两个插件的代码。
本地跑得好好的，部署到 NAS 后插件中心里插件直接消失，排查成本很高。
"""
import os
import re

from plugin_manager import CORE_BUILTIN_PLUGIN_IDS

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DOCKERIGNORE = os.path.join(_REPO_ROOT, ".dockerignore")


def _whitelisted_plugin_ids() -> set:
    """从 .dockerignore 里解析被放行的插件目录 id"""
    with open(_DOCKERIGNORE, encoding="utf-8") as f:
        content = f.read()
    # 只认 "!backend/plugins/<id>/" 这种目录级放行，忽略 "**" 那行和 *.md 通配
    return set(re.findall(r"^!backend/plugins/([^/*]+)/$", content, flags=re.M))


def test_core_plugins_are_whitelisted_in_dockerignore():
    """每个核心内置插件都必须在 .dockerignore 里放行，否则不进镜像"""
    missing = CORE_BUILTIN_PLUGIN_IDS - _whitelisted_plugin_ids()
    assert not missing, (
        f".dockerignore 少放行了核心插件 {sorted(missing)}，"
        f"重建镜像后这些插件的代码不会进镜像"
    )


def test_whitelist_has_no_stale_entries():
    """反向检查：白名单里不该留已经不是核心插件的条目"""
    stale = _whitelisted_plugin_ids() - CORE_BUILTIN_PLUGIN_IDS
    assert not stale, f".dockerignore 白名单里有已非核心插件的残留 {sorted(stale)}"


def test_whitelisted_plugin_dirs_exist():
    """放行的插件目录必须真实存在，且带 manifest.json"""
    plugins_dir = os.path.join(_REPO_ROOT, "backend", "plugins")
    for pid in sorted(_whitelisted_plugin_ids()):
        manifest = os.path.join(plugins_dir, pid, "manifest.json")
        assert os.path.isfile(manifest), f"{pid} 缺 manifest.json：{manifest}"
