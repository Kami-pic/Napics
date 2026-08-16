"""插件中心 API 端点"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from plugin_manager import PluginInfo, PluginManager, RemotePluginInfo
from shared import config_m

logger = logging.getLogger(__name__)


def _reset_services_on_plugin_change():
    """插件变更后刷新依赖插件状态的服务单例"""
    try:
        from shared import reset_pan_search_service
        reset_pan_search_service()
    except Exception:
        pass
    try:
        from routes.subscribe import refresh_rss_sources
        if not refresh_rss_sources():
            logger.warning("[Plugins] RSS 源刷新失败，已保留原运行时源")
    except Exception as e:
        logger.warning(f"[Plugins] RSS 源刷新异常，已保留原运行时源: {e}")
    try:
        from shared import refresh_download_backends
        if not refresh_download_backends():
            logger.warning("[Plugins] 下载后端刷新失败，已保留原运行时后端")
    except Exception as e:
        logger.warning(f"[Plugins] 下载后端刷新异常，已保留原运行时后端: {e}")


router = APIRouter(prefix="/api/plugins", tags=["plugins"])

# 单例
_plugin_manager: Optional[PluginManager] = None


def _get_plugin_manager() -> PluginManager:
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager


class InstallRequest(BaseModel):
    id: str


class UninstallRequest(BaseModel):
    id: str
    remove_files: bool = False  # 是否删除插件文件（远程插件）


class PluginConfigUpdate(BaseModel):
    config: dict = {}


class AddSourceRequest(BaseModel):
    name: str
    url: str


class RemoveSourceRequest(BaseModel):
    url: str


class InstallRemoteRequest(BaseModel):
    """远程插件安装请求"""
    source_url: str  # 插件源 URL
    plugin_id: str   # 要安装的插件 ID


class InstallFromUrlRequest(BaseModel):
    """从 GitHub URL 直接安装插件"""
    url: str  # GitHub 仓库 URL


# ── 插件列表与安装/卸载 ──


@router.get("", response_model=List[PluginInfo])
def list_plugins():
    """获取所有可用插件列表（含安装状态）"""
    pm = _get_plugin_manager()
    installed = config_m.config.installed_plugins
    plugins = pm.list_all(installed)
    result = []
    for plugin in plugins:
        missing = [
            key for key in plugin.requires_config
            if not str(getattr(config_m.config, key, "") or "").strip()
        ]
        if plugin.installed and missing:
            result.append(plugin.model_copy(update={
                "available": False,
                "load_error": f"缺少配置: {', '.join(missing)}",
            }))
        else:
            result.append(plugin)
    return result


@router.post("/install")
def install_plugin(req: InstallRequest):
    """安装本地插件"""
    pm = _get_plugin_manager()
    installed = list(config_m.config.installed_plugins)

    result = pm.install(req.id, installed)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result)

    # 更新配置
    installed.append(req.id)
    conf = config_m.config.model_copy()
    conf.installed_plugins = installed
    config_m.save(conf)

    logger.info(f"[Plugins] 已安装插件: {req.id}")
    _reset_services_on_plugin_change()
    return {"success": True, "installed_plugins": installed}


@router.post("/uninstall")
def uninstall_plugin(req: UninstallRequest):
    """卸载插件"""
    pm = _get_plugin_manager()
    installed = list(config_m.config.installed_plugins)

    if req.remove_files:
        result = pm.uninstall_remote_plugin(req.id, installed)
    else:
        result = pm.uninstall(req.id, installed)

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result)

    # 更新配置
    if req.id in installed:
        installed.remove(req.id)
    conf = config_m.config.model_copy()
    conf.installed_plugins = installed
    config_m.save(conf)

    logger.info(f"[Plugins] 已卸载插件: {req.id}")
    _reset_services_on_plugin_change()
    return {"success": True, "installed_plugins": installed}


# ── 插件配置 ──


@router.get("/{plugin_id}/config")
def get_plugin_config(plugin_id: str):
    """获取插件配置项"""
    pm = _get_plugin_manager()
    manifest = pm.get_manifest(plugin_id)
    if not manifest:
        raise HTTPException(status_code=404, detail={"error": "plugin_not_found"})
    if plugin_id not in config_m.config.installed_plugins:
        raise HTTPException(status_code=409, detail={"error": "plugin_not_installed"})

    # 从全局 config 中提取插件需要的配置字段
    conf = config_m.config
    plugin_config = {}
    for key in manifest.requires_config:
        plugin_config[key] = getattr(conf, key, "")

    schema = [field.model_dump() for field in manifest.config_schema]
    if not schema:
        schema = [
            {"key": key, "label": key, "type": "text", "description": "", "placeholder": "", "required": False}
            for key in manifest.requires_config
        ]
    return {"plugin_id": plugin_id, "config": plugin_config, "schema": schema}


@router.put("/{plugin_id}/config")
def update_plugin_config(plugin_id: str, req: PluginConfigUpdate):
    """保存插件配置"""
    pm = _get_plugin_manager()
    manifest = pm.get_manifest(plugin_id)
    if not manifest:
        raise HTTPException(status_code=404, detail={"error": "plugin_not_found"})
    if plugin_id not in config_m.config.installed_plugins:
        raise HTTPException(status_code=409, detail={"error": "plugin_not_installed"})

    # 只允许更新 manifest 中声明的配置字段
    conf = config_m.config.model_copy()
    updated_keys = []
    for key, value in req.config.items():
        if key in manifest.requires_config and hasattr(conf, key):
            setattr(conf, key, value)
            updated_keys.append(key)

    if updated_keys:
        config_m.save(conf)
        logger.info(f"[Plugins] 更新插件 {plugin_id} 配置: {updated_keys}")
        _reset_services_on_plugin_change()

    return {"success": True, "updated_keys": updated_keys}


@router.post("/{plugin_id}/test")
def test_plugin_connection(plugin_id: str):
    """测试插件连通性（检查配置的服务是否可达）"""
    import requests as _requests

    pm = _get_plugin_manager()
    manifest = pm.get_manifest(plugin_id)
    if not manifest:
        raise HTTPException(status_code=404, detail={"error": "plugin_not_found"})

    conf = config_m.config
    results = {}

    # 根据插件 ID 执行不同的连通性检测
    try:
        if plugin_id == "search-prowlarr":
            url = (getattr(conf, "prowlarr_url", "") or "").rstrip("/")
            key = getattr(conf, "prowlarr_api_key", "") or ""
            if not url or not key:
                return {"success": False, "error": "地址或 API Key 未配置"}
            resp = _requests.get(
                f"{url}/api/v1/health", params={"apikey": key}, timeout=5,
                proxies={"http": None, "https": None},
            )
            results["status_code"] = resp.status_code
            results["success"] = resp.status_code == 200

        elif plugin_id == "download-qbittorrent":
            url = (getattr(conf, "qb_url", "") or "").rstrip("/")
            if not url:
                return {"success": False, "error": "地址未配置"}
            resp = _requests.get(
                f"{url}/api/v2/app/version", timeout=5,
                proxies={"http": None, "https": None},
            )
            results["status_code"] = resp.status_code
            results["version"] = resp.text.strip() if resp.status_code == 200 else ""
            results["success"] = resp.status_code == 200

        elif plugin_id in ("storage-openlist", "download-openlist"):
            url = (getattr(conf, "alist_url", "") or "").rstrip("/")
            token = getattr(conf, "alist_token", "") or ""
            if not url:
                return {"success": False, "error": "地址未配置"}
            resp = _requests.post(
                f"{url}/api/me", headers={"Authorization": token}, timeout=5,
                proxies={"http": None, "https": None},
            )
            results["status_code"] = resp.status_code
            data = resp.json() if resp.status_code == 200 else {}
            results["success"] = data.get("code") == 200
            results["username"] = data.get("data", {}).get("username", "")

        elif plugin_id == "metadata-tmdb":
            key = getattr(conf, "tmdb_api_key", "") or ""
            proxy = getattr(conf, "http_proxy", "") or ""
            if not key:
                return {"success": False, "error": "API Key 未配置"}
            proxies = {"http": proxy, "https": proxy} if proxy else None
            resp = _requests.get(
                "https://api.themoviedb.org/3/configuration",
                params={"api_key": key}, timeout=8, proxies=proxies,
            )
            results["status_code"] = resp.status_code
            results["success"] = resp.status_code == 200

        else:
            return {"success": True, "message": "该插件无需连通性测试"}

    except _requests.exceptions.Timeout:
        return {"success": False, "error": "连接超时"}
    except _requests.exceptions.ConnectionError as e:
        return {"success": False, "error": f"连接失败: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

    if results.get("success"):
        return {"success": True, **results}
    return {"success": False, "error": f"HTTP {results.get('status_code', '?')}", **results}


# ── 外部插件源管理 ──


@router.get("/sources")
def list_plugin_sources():
    """获取已添加的外部插件源列表"""
    sources = config_m.config.plugin_sources
    return {"sources": [s.model_dump() for s in sources]}


@router.post("/sources")
def add_plugin_source(req: AddSourceRequest):
    """添加外部插件源"""
    conf = config_m.config.model_copy()

    # 检查是否已存在
    for s in conf.plugin_sources:
        if s.url == req.url:
            raise HTTPException(status_code=400, detail={"error": "source_exists", "message": "该插件源已添加"})

    # 验证源可访问
    pm = _get_plugin_manager()
    proxy = config_m.config.http_proxy or ""
    result = pm.fetch_remote_index(req.url, proxy=proxy)
    if not result["success"]:
        raise HTTPException(status_code=400, detail={
            "error": "source_unreachable",
            "message": f"无法访问插件源: {result['error']}",
        })

    # 保存
    from config_manager import PluginSourceConfig
    source = PluginSourceConfig(name=req.name or result["index"].name, url=req.url)
    conf.plugin_sources.append(source)
    config_m.save(conf)

    logger.info(f"[Plugins] 添加插件源: {source.name} ({source.url})")
    return {"success": True, "source": source.model_dump()}


@router.delete("/sources")
def remove_plugin_source(req: RemoveSourceRequest):
    """移除外部插件源"""
    conf = config_m.config.model_copy()
    original_count = len(conf.plugin_sources)
    conf.plugin_sources = [s for s in conf.plugin_sources if s.url != req.url]

    if len(conf.plugin_sources) == original_count:
        raise HTTPException(status_code=404, detail={"error": "source_not_found", "message": "未找到该插件源"})

    config_m.save(conf)
    logger.info(f"[Plugins] 移除插件源: {req.url}")
    return {"success": True}


@router.get("/sources/plugins")
def list_remote_plugins(source_url: str = ""):
    """拉取指定插件源的可用插件列表。

    如果不传 source_url，则拉取所有已添加源的插件。
    """
    pm = _get_plugin_manager()
    proxy = config_m.config.http_proxy or ""
    installed = config_m.config.installed_plugins

    sources_to_fetch = []
    if source_url:
        sources_to_fetch = [(source_url, False)]
    else:
        sources_to_fetch = [(s.url, s.requires_license) for s in config_m.config.plugin_sources]

    all_plugins = []
    errors = []
    license_key = config_m.config.license_key or ""

    for url, requires_license in sources_to_fetch:
        key = license_key if requires_license else ""
        result = pm.fetch_remote_index(url, proxy=proxy, license_key=key)
        if result["success"]:
            index = result["index"]
            for p in index.plugins:
                all_plugins.append({
                    "id": p.id,
                    "name": p.name,
                    "version": p.version,
                    "description": p.description,
                    "category": p.category,
                    "icon": p.icon,
                    "risk_level": p.risk_level,
                    "depends_on": p.depends_on,
                    "download_url": p.download_url,
                    "installed": p.id in installed,
                    "source": url,
                    "source_name": index.name,
                })
        else:
            errors.append({"url": url, "error": result["error"]})

    return {"plugins": all_plugins, "errors": errors}


@router.post("/install-remote")
def install_remote_plugin(req: InstallRemoteRequest):
    """从远程插件源下载并安装插件"""
    pm = _get_plugin_manager()
    proxy = config_m.config.http_proxy or ""
    installed = list(config_m.config.installed_plugins)

    # 拉取源获取插件信息
    result = pm.fetch_remote_index(req.source_url, proxy=proxy)
    if not result["success"]:
        raise HTTPException(status_code=400, detail={
            "error": "source_unreachable",
            "message": f"无法访问插件源: {result['error']}",
        })

    # 找到目标插件
    index = result["index"]
    target_plugin = None
    for p in index.plugins:
        if p.id == req.plugin_id:
            target_plugin = p
            break

    if not target_plugin:
        raise HTTPException(status_code=404, detail={
            "error": "plugin_not_found",
            "message": f"插件源中未找到插件: {req.plugin_id}",
        })

    # 下载并安装
    install_result = pm.install_remote_plugin(target_plugin, installed, proxy=proxy, source_url=req.source_url)
    if not install_result["success"]:
        raise HTTPException(status_code=400, detail=install_result)

    # 更新配置
    installed.append(req.plugin_id)
    conf = config_m.config.model_copy()
    conf.installed_plugins = installed
    config_m.save(conf)

    logger.info(f"[Plugins] 已安装远程插件: {req.plugin_id} (来源: {req.source_url})")
    _reset_services_on_plugin_change()
    return {"success": True, "installed_plugins": installed}


@router.post("/install-from-url")
def install_from_url(req: InstallFromUrlRequest):
    """从 GitHub 仓库 URL 直接安装插件"""
    pm = _get_plugin_manager()
    proxy = config_m.config.http_proxy or ""
    installed = list(config_m.config.installed_plugins)

    result = pm.install_from_github_url(req.url, installed, proxy=proxy)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result)

    # 更新配置
    plugin_id = result["plugin_id"]
    installed.append(plugin_id)
    conf = config_m.config.model_copy()
    conf.installed_plugins = installed
    config_m.save(conf)

    logger.info(f"[Plugins] 从 URL 安装插件: {plugin_id} ({req.url})")
    _reset_services_on_plugin_change()
    return {"success": True, "plugin_id": plugin_id, "name": result.get("name", ""), "installed_plugins": installed}
