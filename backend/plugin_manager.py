"""插件管理器 — 插件加载/注册/卸载逻辑。

职责：
- 扫描 plugins/ 目录读取 manifest.json
- 根据 config.installed_plugins 决定哪些插件处于已安装状态
- 提供安装/卸载 API（修改 config + 注册/注销 provider）
- 支持第三方插件：插件目录下的 __init__.py 导出 register(ctx) 函数
"""

import importlib
import importlib.util
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# plugins/ 目录位于 backend/ 下
PLUGINS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugins")


class PluginManifest(BaseModel):
    """插件清单定义"""
    id: str
    name: str
    version: str = "1.0.0"
    description: str = ""
    category: str = ""  # metadata / search / rss / download / storage / feature
    icon: str = ""
    requires_config: List[str] = Field(default_factory=list)
    depends_on: List[str] = Field(default_factory=list)
    provides: List[str] = Field(default_factory=list)
    risk_level: str = "low"  # low / medium / high


class PluginInfo(BaseModel):
    """插件信息（含安装状态）"""
    id: str
    name: str
    version: str = "1.0.0"
    description: str = ""
    category: str = ""
    icon: str = ""
    requires_config: List[str] = Field(default_factory=list)
    depends_on: List[str] = Field(default_factory=list)
    provides: List[str] = Field(default_factory=list)
    risk_level: str = "low"
    installed: bool = False


class PluginManager:
    """插件管理器"""

    def __init__(self):
        self._manifests: Dict[str, PluginManifest] = {}
        self._loaded_modules: Dict[str, Any] = {}  # 已加载的插件模块
        self._load_manifests()

    def _load_manifests(self) -> None:
        """扫描 plugins/ 目录加载所有 manifest.json"""
        self._manifests.clear()
        if not os.path.isdir(PLUGINS_DIR):
            logger.warning(f"[PluginManager] plugins 目录不存在: {PLUGINS_DIR}")
            return

        for entry in os.listdir(PLUGINS_DIR):
            plugin_dir = os.path.join(PLUGINS_DIR, entry)
            manifest_path = os.path.join(plugin_dir, "manifest.json")
            if not os.path.isfile(manifest_path):
                continue
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                manifest = PluginManifest(**data)
                self._manifests[manifest.id] = manifest
            except Exception as e:
                logger.error(f"[PluginManager] 加载插件清单失败 {manifest_path}: {e}")

    def reload(self) -> None:
        """重新扫描插件目录"""
        self._load_manifests()

    def list_all(self, installed_plugins: List[str]) -> List[PluginInfo]:
        """返回所有可用插件列表（含安装状态）"""
        result = []
        for manifest in sorted(self._manifests.values(), key=lambda m: (m.category, m.name)):
            result.append(PluginInfo(
                id=manifest.id,
                name=manifest.name,
                version=manifest.version,
                description=manifest.description,
                category=manifest.category,
                icon=manifest.icon,
                requires_config=manifest.requires_config,
                depends_on=manifest.depends_on,
                provides=manifest.provides,
                risk_level=manifest.risk_level,
                installed=manifest.id in installed_plugins,
            ))
        return result

    def get_manifest(self, plugin_id: str) -> Optional[PluginManifest]:
        """获取单个插件的 manifest"""
        return self._manifests.get(plugin_id)

    def check_dependencies(self, plugin_id: str, installed_plugins: List[str]) -> List[str]:
        """检查插件依赖是否满足，返回缺失的依赖列表"""
        manifest = self._manifests.get(plugin_id)
        if not manifest:
            return []
        missing = []
        for dep in manifest.depends_on:
            if dep not in installed_plugins:
                missing.append(dep)
        return missing

    def get_dependents(self, plugin_id: str, installed_plugins: List[str]) -> List[str]:
        """获取依赖此插件的已安装插件列表"""
        dependents = []
        for pid in installed_plugins:
            manifest = self._manifests.get(pid)
            if manifest and plugin_id in manifest.depends_on:
                dependents.append(pid)
        return dependents

    def install(self, plugin_id: str, installed_plugins: List[str]) -> Dict[str, Any]:
        """安装插件，返回操作结果"""
        manifest = self._manifests.get(plugin_id)
        if not manifest:
            return {"success": False, "error": "plugin_not_found", "message": f"插件 {plugin_id} 不存在"}

        if plugin_id in installed_plugins:
            return {"success": False, "error": "already_installed", "message": f"插件 {plugin_id} 已安装"}

        # 检查依赖
        missing = self.check_dependencies(plugin_id, installed_plugins)
        if missing:
            return {
                "success": False,
                "error": "missing_dependencies",
                "message": f"缺少依赖: {', '.join(missing)}",
                "missing_dependencies": missing,
            }

        # 尝试加载插件模块
        load_err = self._load_plugin_module(plugin_id)
        if load_err:
            return {"success": False, "error": "load_failed", "message": load_err}

        return {"success": True, "plugin_id": plugin_id}

    def uninstall(self, plugin_id: str, installed_plugins: List[str]) -> Dict[str, Any]:
        """卸载插件，返回操作结果"""
        if plugin_id not in installed_plugins:
            return {"success": False, "error": "not_installed", "message": f"插件 {plugin_id} 未安装"}

        # 检查是否有其他插件依赖此插件
        dependents = self.get_dependents(plugin_id, installed_plugins)
        if dependents:
            return {
                "success": False,
                "error": "has_dependents",
                "message": f"以下插件依赖此插件: {', '.join(dependents)}",
                "dependents": dependents,
            }

        # 卸载插件模块
        self._unload_plugin_module(plugin_id)

        return {"success": True, "plugin_id": plugin_id}

    # ── 插件模块加载 ──

    def _get_plugin_dir(self, plugin_id: str) -> Optional[str]:
        """获取插件目录路径"""
        for entry in os.listdir(PLUGINS_DIR):
            plugin_dir = os.path.join(PLUGINS_DIR, entry)
            manifest_path = os.path.join(plugin_dir, "manifest.json")
            if not os.path.isfile(manifest_path):
                continue
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("id") == plugin_id:
                    return plugin_dir
            except Exception:
                continue
        return None

    def _load_plugin_module(self, plugin_id: str) -> Optional[str]:
        """加载插件的 Python 模块。返回错误信息或 None（成功）。

        插件目录下如果有 __init__.py，会被作为模块加载。
        模块必须导出 register(context) 函数。
        """
        if plugin_id in self._loaded_modules:
            return None  # 已加载

        plugin_dir = self._get_plugin_dir(plugin_id)
        if not plugin_dir:
            return None  # 无代码目录，纯声明式插件（内置功能开关）

        init_path = os.path.join(plugin_dir, "__init__.py")
        if not os.path.isfile(init_path):
            return None  # 无代码，纯声明式插件

        try:
            # 动态加载模块
            module_name = f"napics_plugin_{plugin_id.replace('-', '_')}"
            spec = importlib.util.spec_from_file_location(module_name, init_path)
            if spec is None or spec.loader is None:
                return f"无法加载插件模块: {init_path}"

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # 调用 register 函数
            register_fn = getattr(module, "register", None)
            if register_fn and callable(register_fn):
                from plugin_context import get_plugin_context
                ctx = get_plugin_context(plugin_id)
                register_fn(ctx)
                logger.info(f"[PluginManager] 插件 {plugin_id} 已加载并注册")

            self._loaded_modules[plugin_id] = module
            return None

        except Exception as e:
            logger.error(f"[PluginManager] 加载插件 {plugin_id} 失败: {e}")
            return f"加载失败: {str(e)}"

    def _unload_plugin_module(self, plugin_id: str) -> None:
        """卸载插件模块"""
        module_name = f"napics_plugin_{plugin_id.replace('-', '_')}"

        # 调用 unregister 如果存在
        module = self._loaded_modules.pop(plugin_id, None)
        if module:
            unregister_fn = getattr(module, "unregister", None)
            if unregister_fn and callable(unregister_fn):
                try:
                    unregister_fn()
                except Exception as e:
                    logger.warning(f"[PluginManager] 插件 {plugin_id} unregister 异常: {e}")

        # 从 sys.modules 移除
        sys.modules.pop(module_name, None)
        logger.info(f"[PluginManager] 插件 {plugin_id} 已卸载")

    def load_installed_plugins(self, installed_plugins: List[str]) -> None:
        """启动时加载所有已安装的插件模块"""
        for plugin_id in installed_plugins:
            if plugin_id in self._manifests:
                err = self._load_plugin_module(plugin_id)
                if err:
                    logger.error(f"[PluginManager] 启动加载插件 {plugin_id} 失败: {err}")
