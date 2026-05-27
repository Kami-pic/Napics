"""插件管理器 — 插件加载/注册/卸载逻辑。

职责：
- 扫描 plugins/ 目录读取 manifest.json
- 根据 config.installed_plugins 决定哪些插件处于已安装状态
- 提供安装/卸载 API（修改 config + 注册/注销 provider）
- 支持第三方插件：插件目录下的 __init__.py 导出 register(ctx) 函数
"""

import importlib
import importlib.util
import io
import json
import logging
import os
import shutil
import sys
import zipfile
from typing import Any, Dict, List, Optional

import requests
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
    source: str = "builtin"  # builtin / remote


class RemotePluginInfo(BaseModel):
    """远程插件源中的插件信息"""
    id: str
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    category: str = ""
    icon: str = ""
    risk_level: str = "low"
    depends_on: List[str] = Field(default_factory=list)
    download_url: str = ""
    sha256: str = ""
    min_napics_version: str = ""


class PluginSourceIndex(BaseModel):
    """远程插件源 index.json 结构"""
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    homepage: str = ""
    plugins: List[RemotePluginInfo] = Field(default_factory=list)


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
                source="builtin",
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

    # ── 远程插件源管理 ──

    def fetch_remote_index(self, source_url: str, proxy: str = "", license_key: str = "") -> Dict[str, Any]:
        """拉取远程插件源的 index.json。

        返回 {"success": True, "index": PluginSourceIndex} 或 {"success": False, "error": ...}
        license_key: 需要授权的插件源带 License Key 作为 auth header
        """
        try:
            proxies = {"http": proxy, "https": proxy} if proxy else None
            # 支持 GitHub 仓库 URL 自动转换为 raw index.json
            url = self._normalize_source_url(source_url)
            headers = {}
            if license_key:
                headers["Authorization"] = f"Bearer {license_key}"
            resp = requests.get(url, timeout=15, proxies=proxies, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            index = PluginSourceIndex(**data)
            return {"success": True, "index": index}
        except requests.RequestException as e:
            logger.error(f"[PluginManager] 拉取远程插件源失败 {source_url}: {e}")
            return {"success": False, "error": f"网络请求失败: {str(e)}"}
        except Exception as e:
            logger.error(f"[PluginManager] 解析远程插件源失败 {source_url}: {e}")
            return {"success": False, "error": f"解析失败: {str(e)}"}

    def install_remote_plugin(
        self,
        plugin_info: RemotePluginInfo,
        installed_plugins: List[str],
        proxy: str = "",
        source_url: str = "",
    ) -> Dict[str, Any]:
        """从远程源下载并安装插件。

        流程：下载 zip → 解压到 plugins/ → 校验 manifest → 注册
        如果 download_url 下载失败（如 release 未发布），回退到从源仓库下载整个 zip 并提取子目录。
        """
        plugin_id = plugin_info.id

        if plugin_id in self._manifests and plugin_id in installed_plugins:
            return {"success": False, "error": "already_installed", "message": f"插件 {plugin_id} 已安装"}

        if not plugin_info.download_url and not source_url:
            return {"success": False, "error": "no_download_url", "message": "插件缺少下载地址"}

        proxies = {"http": proxy, "https": proxy} if proxy else None
        zip_content = None

        # 尝试从 download_url 下载 zip
        if plugin_info.download_url:
            try:
                resp = requests.get(plugin_info.download_url, timeout=60, proxies=proxies)
                resp.raise_for_status()
                zip_content = resp.content
            except requests.RequestException as e:
                logger.warning(f"[PluginManager] download_url 下载失败，尝试回退: {e}")

        # 回退：从源仓库下载整个 zip 并提取子目录
        if zip_content is None and source_url:
            fallback_result = self._fallback_install_from_repo(plugin_id, source_url, installed_plugins, proxies)
            if fallback_result is not None:
                return fallback_result
            # fallback_result 为 None 表示回退也失败了
            return {"success": False, "error": "download_failed", "message": f"下载失败，release 和仓库源码均不可用"}

        if zip_content is None:
            return {"success": False, "error": "download_failed", "message": "下载失败"}

        # SHA256 校验（如果提供了）
        if plugin_info.sha256:
            import hashlib
            actual_hash = hashlib.sha256(zip_content).hexdigest()
            if actual_hash != plugin_info.sha256:
                return {
                    "success": False,
                    "error": "hash_mismatch",
                    "message": f"文件校验失败（期望 {plugin_info.sha256[:16]}...，实际 {actual_hash[:16]}...）",
                }

        # 解压到 plugins/ 目录
        plugin_dir = os.path.join(PLUGINS_DIR, plugin_id)
        try:
            # 如果已存在旧版本，先备份
            if os.path.isdir(plugin_dir):
                backup_dir = plugin_dir + ".bak"
                if os.path.isdir(backup_dir):
                    shutil.rmtree(backup_dir)
                os.rename(plugin_dir, backup_dir)

            # 解压
            zip_buffer = io.BytesIO(zip_content)
            with zipfile.ZipFile(zip_buffer, "r") as zf:
                # 检测 zip 内是否有单层根目录
                top_dirs = set()
                for name in zf.namelist():
                    parts = name.split("/")
                    if len(parts) > 1:
                        top_dirs.add(parts[0])
                    else:
                        top_dirs.add("")

                if len(top_dirs) == 1 and "" not in top_dirs:
                    # zip 内有单层根目录，解压后重命名
                    zf.extractall(PLUGINS_DIR)
                    extracted_dir = os.path.join(PLUGINS_DIR, top_dirs.pop())
                    if extracted_dir != plugin_dir:
                        if os.path.isdir(plugin_dir):
                            shutil.rmtree(plugin_dir)
                        os.rename(extracted_dir, plugin_dir)
                else:
                    # zip 内无根目录，直接解压到目标目录
                    os.makedirs(plugin_dir, exist_ok=True)
                    zf.extractall(plugin_dir)

            # 清理备份
            backup_dir = plugin_dir + ".bak"
            if os.path.isdir(backup_dir):
                shutil.rmtree(backup_dir)

        except Exception as e:
            # 恢复备份
            backup_dir = plugin_dir + ".bak"
            if os.path.isdir(backup_dir):
                if os.path.isdir(plugin_dir):
                    shutil.rmtree(plugin_dir)
                os.rename(backup_dir, plugin_dir)
            return {"success": False, "error": "extract_failed", "message": f"解压失败: {str(e)}"}

        # 校验 manifest.json 存在
        manifest_path = os.path.join(plugin_dir, "manifest.json")
        if not os.path.isfile(manifest_path):
            shutil.rmtree(plugin_dir)
            return {"success": False, "error": "no_manifest", "message": "插件包中缺少 manifest.json"}

        # 重新加载 manifest
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            manifest = PluginManifest(**data)
            self._manifests[manifest.id] = manifest
        except Exception as e:
            shutil.rmtree(plugin_dir)
            return {"success": False, "error": "invalid_manifest", "message": f"manifest.json 无效: {str(e)}"}

        # 加载插件模块
        load_err = self._load_plugin_module(plugin_id)
        if load_err:
            logger.warning(f"[PluginManager] 远程插件 {plugin_id} 模块加载失败（可能是纯声明式）: {load_err}")

        logger.info(f"[PluginManager] 远程插件 {plugin_id} 安装成功")
        return {"success": True, "plugin_id": plugin_id}

    def _fallback_install_from_repo(
        self,
        plugin_id: str,
        source_url: str,
        installed_plugins: List[str],
        proxies: Optional[Dict[str, str]],
    ) -> Optional[Dict[str, Any]]:
        """回退方案：从源仓库下载整个 zip，提取对应插件子目录。

        返回安装结果 dict，或 None 表示回退失败。
        """
        import re
        # 从 source_url 解析 GitHub user/repo
        clean_url = source_url.strip().rstrip("/")
        match = re.match(r"https?://github\.com/([^/]+)/([^/]+)", clean_url)
        if not match:
            return None

        user, repo = match.group(1), match.group(2)
        repo = repo.rstrip(".git")
        branch = "main"

        # 下载仓库 zip
        zip_url = f"https://github.com/{user}/{repo}/archive/refs/heads/{branch}.zip"
        try:
            resp = requests.get(zip_url, timeout=60, proxies=proxies)
            resp.raise_for_status()
        except requests.RequestException:
            return None

        # 解压并提取子目录
        plugin_dir = os.path.join(PLUGINS_DIR, plugin_id)
        try:
            if os.path.isdir(plugin_dir):
                backup_dir = plugin_dir + ".bak"
                if os.path.isdir(backup_dir):
                    shutil.rmtree(backup_dir)
                os.rename(plugin_dir, backup_dir)

            zip_buffer = io.BytesIO(resp.content)
            with zipfile.ZipFile(zip_buffer, "r") as zf:
                # GitHub zip 内有 repo-branch/ 根目录，子目录为 repo-branch/plugin_id/
                prefix = f"{repo}-{branch}/{plugin_id}/"
                members = [m for m in zf.namelist() if m.startswith(prefix)]
                if not members:
                    # 尝试不带 branch 的前缀（有些仓库用不同命名）
                    for name in zf.namelist():
                        if f"/{plugin_id}/" in name:
                            prefix = name[:name.index(f"/{plugin_id}/") + len(f"/{plugin_id}/")]
                            members = [m for m in zf.namelist() if m.startswith(prefix)]
                            break

                if not members:
                    # 恢复备份
                    backup_dir = plugin_dir + ".bak"
                    if os.path.isdir(backup_dir):
                        os.rename(backup_dir, plugin_dir)
                    return None

                # 提取子目录内容到 plugin_dir
                os.makedirs(plugin_dir, exist_ok=True)
                for member in members:
                    rel_path = member[len(prefix):]
                    if not rel_path:
                        continue
                    target_path = os.path.join(plugin_dir, rel_path)
                    if member.endswith("/"):
                        os.makedirs(target_path, exist_ok=True)
                    else:
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        with zf.open(member) as src, open(target_path, "wb") as dst:
                            dst.write(src.read())

            # 清理备份
            backup_dir = plugin_dir + ".bak"
            if os.path.isdir(backup_dir):
                shutil.rmtree(backup_dir)

        except Exception as e:
            backup_dir = plugin_dir + ".bak"
            if os.path.isdir(backup_dir):
                if os.path.isdir(plugin_dir):
                    shutil.rmtree(plugin_dir)
                os.rename(backup_dir, plugin_dir)
            logger.error(f"[PluginManager] 回退安装失败: {e}")
            return None

        # 校验 manifest
        manifest_path = os.path.join(plugin_dir, "manifest.json")
        if not os.path.isfile(manifest_path):
            shutil.rmtree(plugin_dir)
            return None

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            manifest = PluginManifest(**data)
            self._manifests[manifest.id] = manifest
        except Exception as e:
            shutil.rmtree(plugin_dir)
            return None

        load_err = self._load_plugin_module(plugin_id)
        if load_err:
            logger.warning(f"[PluginManager] 回退安装插件 {plugin_id} 模块加载失败: {load_err}")

        logger.info(f"[PluginManager] 回退从仓库源码安装插件成功: {plugin_id}")
        return {"success": True, "plugin_id": plugin_id}

    def uninstall_remote_plugin(self, plugin_id: str, installed_plugins: List[str]) -> Dict[str, Any]:
        """卸载远程插件（卸载 + 删除文件）"""
        result = self.uninstall(plugin_id, installed_plugins)
        if not result["success"]:
            return result

        # 删除插件目录
        plugin_dir = os.path.join(PLUGINS_DIR, plugin_id)
        if os.path.isdir(plugin_dir):
            try:
                shutil.rmtree(plugin_dir)
                self._manifests.pop(plugin_id, None)
                logger.info(f"[PluginManager] 已删除远程插件目录: {plugin_dir}")
            except Exception as e:
                logger.warning(f"[PluginManager] 删除插件目录失败: {e}")

        return result

    @staticmethod
    def _normalize_source_url(url: str) -> str:
        """将 GitHub 仓库 URL 转换为 raw index.json URL"""
        url = url.strip().rstrip("/")
        # 已经是直接指向 json 文件的 URL
        if url.endswith(".json"):
            return url
        # GitHub 仓库 URL → raw index.json
        if "github.com" in url and "/raw/" not in url and "/releases/" not in url:
            # https://github.com/user/repo → https://raw.githubusercontent.com/user/repo/main/index.json
            url = url.replace("github.com", "raw.githubusercontent.com")
            url += "/main/index.json"
        return url

    def install_from_github_url(
        self,
        github_url: str,
        installed_plugins: List[str],
        proxy: str = "",
    ) -> Dict[str, Any]:
        """从 GitHub 仓库 URL 直接安装插件。

        流程：解析 URL → 下载仓库 zip → 解压 → 校验 manifest → 注册
        支持格式：
        - https://github.com/user/repo（默认 main 分支）
        - https://github.com/user/repo/tree/branch
        """
        url = github_url.strip().rstrip("/")

        # 解析 GitHub URL
        if "github.com" not in url:
            return {"success": False, "error": "invalid_url", "message": "仅支持 GitHub 仓库 URL"}

        # 提取 user/repo 和 branch
        import re
        match = re.match(r"https?://github\.com/([^/]+)/([^/]+)(?:/tree/([^/]+))?", url)
        if not match:
            return {"success": False, "error": "invalid_url", "message": "无法解析 GitHub 仓库地址"}

        user, repo, branch = match.group(1), match.group(2), match.group(3) or "main"
        repo = repo.rstrip(".git")

        # 先尝试获取 manifest.json 确认是有效插件
        manifest_url = f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/manifest.json"
        try:
            proxies = {"http": proxy, "https": proxy} if proxy else None
            resp = requests.get(manifest_url, timeout=15, proxies=proxies)
            if resp.status_code == 404:
                return {"success": False, "error": "no_manifest", "message": "仓库中未找到 manifest.json（确认仓库根目录有此文件）"}
            resp.raise_for_status()
            manifest_data = resp.json()
            plugin_id = manifest_data.get("id", "")
            if not plugin_id:
                return {"success": False, "error": "invalid_manifest", "message": "manifest.json 缺少 id 字段"}
        except requests.RequestException as e:
            return {"success": False, "error": "network_error", "message": f"获取 manifest.json 失败: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": "parse_error", "message": f"解析 manifest.json 失败: {str(e)}"}

        # 检查是否已安装
        if plugin_id in installed_plugins:
            return {"success": False, "error": "already_installed", "message": f"插件 {plugin_id} 已安装"}

        # 下载仓库 zip
        zip_url = f"https://github.com/{user}/{repo}/archive/refs/heads/{branch}.zip"
        try:
            resp = requests.get(zip_url, timeout=60, proxies=proxies)
            resp.raise_for_status()
        except requests.RequestException as e:
            return {"success": False, "error": "download_failed", "message": f"下载仓库失败: {str(e)}"}

        # 解压到 plugins/ 目录
        plugin_dir = os.path.join(PLUGINS_DIR, plugin_id)
        try:
            if os.path.isdir(plugin_dir):
                backup_dir = plugin_dir + ".bak"
                if os.path.isdir(backup_dir):
                    shutil.rmtree(backup_dir)
                os.rename(plugin_dir, backup_dir)

            zip_buffer = io.BytesIO(resp.content)
            with zipfile.ZipFile(zip_buffer, "r") as zf:
                # GitHub zip 内有 repo-branch/ 根目录
                top_dirs = set()
                for name in zf.namelist():
                    parts = name.split("/")
                    if len(parts) > 1:
                        top_dirs.add(parts[0])

                if len(top_dirs) == 1:
                    zf.extractall(PLUGINS_DIR)
                    extracted_dir = os.path.join(PLUGINS_DIR, top_dirs.pop())
                    if extracted_dir != plugin_dir:
                        if os.path.isdir(plugin_dir):
                            shutil.rmtree(plugin_dir)
                        os.rename(extracted_dir, plugin_dir)
                else:
                    os.makedirs(plugin_dir, exist_ok=True)
                    zf.extractall(plugin_dir)

            # 清理备份
            backup_dir = plugin_dir + ".bak"
            if os.path.isdir(backup_dir):
                shutil.rmtree(backup_dir)

        except Exception as e:
            backup_dir = plugin_dir + ".bak"
            if os.path.isdir(backup_dir):
                if os.path.isdir(plugin_dir):
                    shutil.rmtree(plugin_dir)
                os.rename(backup_dir, plugin_dir)
            return {"success": False, "error": "extract_failed", "message": f"解压失败: {str(e)}"}

        # 校验并加载
        manifest_path = os.path.join(plugin_dir, "manifest.json")
        if not os.path.isfile(manifest_path):
            shutil.rmtree(plugin_dir)
            return {"success": False, "error": "no_manifest", "message": "解压后未找到 manifest.json"}

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            manifest = PluginManifest(**data)
            self._manifests[manifest.id] = manifest
        except Exception as e:
            shutil.rmtree(plugin_dir)
            return {"success": False, "error": "invalid_manifest", "message": f"manifest.json 无效: {str(e)}"}

        load_err = self._load_plugin_module(plugin_id)
        if load_err:
            logger.warning(f"[PluginManager] GitHub 插件 {plugin_id} 模块加载失败: {load_err}")

        logger.info(f"[PluginManager] 从 GitHub 安装插件成功: {plugin_id} ({github_url})")
        return {"success": True, "plugin_id": plugin_id, "name": manifest.name}
