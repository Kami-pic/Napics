// 已安装插件状态 hook — 控制前端功能区域显隐
"use client";
import { useState, useEffect, useCallback } from "react";
import { fetchPlugins, type PluginInfo } from "@/lib/api/plugins";

export interface InstalledPluginsState {
  /** 已安装的插件 ID 集合 */
  installed: Set<string>;
  /** 是否加载完成 */
  ready: boolean;
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

export function useInstalledPlugins(): InstalledPluginsState {
  const [installed, setInstalled] = useState<Set<string>>(new Set());
  const [ready, setReady] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const plugins = await fetchPlugins();
      const ids = new Set(plugins.filter(p => p.installed).map(p => p.id));
      setInstalled(ids);
    } catch {
      // 后端不可用时默认空
      setInstalled(new Set());
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

  return {
    installed,
    ready,
    refresh,
    hasSearch: installed.has("search-prowlarr") || installed.has("search-bt-direct"),
    hasPanSearch: installed.has("search-pan"),
    hasDiscover: installed.has("feature-discover"),
    hasSubscribe: installed.has("feature-subscribe"),
    hasCompleteness: installed.has("feature-completeness"),
    hasDownload: installed.has("download-qbittorrent") || installed.has("download-openlist"),
    hasProwlarr: installed.has("search-prowlarr"),
  };
}
