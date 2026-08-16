// 已安装插件状态 hook — 控制前端功能区域显隐
"use client";
import { useState, useEffect, useCallback } from "react";
import { fetchPlugins, type PluginInfo } from "@/lib/api/plugins";

export interface InstalledPluginsState {
  /** 已安装的插件 ID 集合 */
  installed: Set<string>;
  /** 是否加载完成 */
  ready: boolean;
  /** 插件状态是否加载失败 */
  loadFailed: boolean;
  /** 刷新插件状态 */
  refresh: () => void;
  /** 快捷判断 */
  hasSearch: boolean;
  hasPanSearch: boolean;
  hasDiscover: boolean;
  hasSubscribe: boolean;
  hasDownload: boolean;
  hasCompleteness: boolean;
  hasProwlarr: boolean;
}

export interface PluginCapabilities {
  hasSearch: boolean;
  hasPanSearch: boolean;
}

export function derivePluginCapabilities(plugins: PluginInfo[]): PluginCapabilities {
  const available = plugins.filter(plugin => plugin.installed && plugin.available);
  return {
    hasSearch: available.some(plugin =>
      plugin.id === "search-prowlarr"
      || plugin.id === "search-bt-direct"
      || plugin.provides.some(capability => capability.startsWith("SearchProvider:"))
    ),
    hasPanSearch: available.some(plugin =>
      plugin.id === "search-pan"
      || plugin.provides.some(capability => capability.startsWith("PanSearchProvider:"))
    ),
  };
}

export function useInstalledPlugins(): InstalledPluginsState {
  const [plugins, setPlugins] = useState<PluginInfo[]>([]);
  const [ready, setReady] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setPlugins(await fetchPlugins());
      setLoadFailed(false);
    } catch {
      setLoadFailed(true);
    } finally {
      setReady(true);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  // 监听插件安装/卸载事件（PluginCenter 操作后触发）
  useEffect(() => {
    const handler = () => refresh();
    window.addEventListener("plugins-changed", handler);
    return () => window.removeEventListener("plugins-changed", handler);
  }, [refresh]);

  const installed = new Set(plugins.filter(plugin => plugin.installed).map(plugin => plugin.id));
  const available = new Set(
    plugins.filter(plugin => plugin.installed && plugin.available).map(plugin => plugin.id),
  );
  const capabilities = derivePluginCapabilities(plugins);

  return {
    installed,
    ready,
    loadFailed,
    refresh,
    ...capabilities,
    hasDiscover: available.has("feature-discover"),
    hasSubscribe: available.has("feature-subscribe"),
    hasCompleteness: available.has("feature-completeness"),
    hasDownload: available.has("download-qbittorrent") || available.has("download-openlist"),
    hasProwlarr: available.has("search-prowlarr"),
  };
}
