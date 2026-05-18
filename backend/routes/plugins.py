"""插件中心 API 端点"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from plugin_manager import PluginInfo, PluginManager
from shared import config_m

logger = logging.getLogger(__name__)

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


class PluginConfigUpdate(BaseModel):
    config: dict = {}


@router.get("", response_model=List[PluginInfo])
def list_plugins():
    """获取所有可用插件列表（含安装状态）"""
    pm = _get_plugin_manager()
    installed = config_m.config.installed_plugins
    return pm.list_all(installed)


@router.post("/install")
def install_plugin(req: InstallRequest):
    """安装插件"""
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
    return {"success": True, "installed_plugins": installed}


@router.post("/uninstall")
def uninstall_plugin(req: UninstallRequest):
    """卸载插件"""
    pm = _get_plugin_manager()
    installed = list(config_m.config.installed_plugins)

    result = pm.uninstall(req.id, installed)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result)

    # 更新配置
    installed.remove(req.id)
    conf = config_m.config.model_copy()
    conf.installed_plugins = installed
    config_m.save(conf)

    logger.info(f"[Plugins] 已卸载插件: {req.id}")
    return {"success": True, "installed_plugins": installed}


@router.get("/{plugin_id}/config")
def get_plugin_config(plugin_id: str):
    """获取插件配置项"""
    pm = _get_plugin_manager()
    manifest = pm.get_manifest(plugin_id)
    if not manifest:
        raise HTTPException(status_code=404, detail={"error": "plugin_not_found"})

    # 从全局 config 中提取插件需要的配置字段
    conf = config_m.config
    plugin_config = {}
    for key in manifest.requires_config:
        plugin_config[key] = getattr(conf, key, "")

    return {"plugin_id": plugin_id, "config": plugin_config}


@router.put("/{plugin_id}/config")
def update_plugin_config(plugin_id: str, req: PluginConfigUpdate):
    """保存插件配置"""
    pm = _get_plugin_manager()
    manifest = pm.get_manifest(plugin_id)
    if not manifest:
        raise HTTPException(status_code=404, detail={"error": "plugin_not_found"})

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

    return {"success": True, "updated_keys": updated_keys}
