// 插件中心面板 — 侧边栏抽屉式展示
"use client";
import React, { useState, useEffect, useCallback } from "react";
import { fetchPlugins, installPlugin, uninstallPlugin, type PluginInfo } from "@/lib/api/plugins";
import PluginCard from "./PluginCard";
import PluginConfigModal from "./PluginConfigModal";
import RemotePluginList from "./RemotePluginList";
import AddSourceModal from "./AddSourceModal";

interface PluginCenterProps {
  open: boolean;
  onClose: () => void;
}

const CATEGORIES = [
  { key: "all", label: "全部" },
  { key: "installed", label: "已安装" },
  { key: "metadata", label: "元数据" },
  { key: "search", label: "搜索" },
  { key: "rss", label: "订阅" },
  { key: "download", label: "下载" },
  { key: "storage", label: "存储" },
  { key: "feature", label: "增强" },
];

export default function PluginCenter({ open, onClose }: PluginCenterProps) {
  const [plugins, setPlugins] = useState<PluginInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeCategory, setActiveCategory] = useState("all");
  const [configPlugin, setConfigPlugin] = useState<PluginInfo | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [showRemote, setShowRemote] = useState(false);
  const [showAddSource, setShowAddSource] = useState(false);

  const loadPlugins = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchPlugins();
      setPlugins(data);
    } catch (e) {
      console.error("加载插件列表失败", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) loadPlugins();
  }, [open, loadPlugins]);

  const handleInstall = async (id: string) => {
    setActionLoading(id);
    setError("");
    try {
      await installPlugin(id);
      await loadPlugins();
      window.dispatchEvent(new Event("plugins-changed"));
    } catch (e: any) {
      const msg = e?.message || e?.error || "安装失败";
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setActionLoading(null);
    }
  };

  const handleUninstall = async (id: string) => {
    setActionLoading(id);
    setError("");
    try {
      await uninstallPlugin(id);
      await loadPlugins();
      window.dispatchEvent(new Event("plugins-changed"));
    } catch (e: any) {
      const msg = e?.message || e?.error || "卸载失败";
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setActionLoading(null);
    }
  };

  // 已迁出到社区源的插件，不在内置 Tab 中显示
  const COMMUNITY_ONLY_PLUGINS = new Set([
    "search-bt-direct", "search-pan", "search-example",
    "search-prowlarr", "search-nyaa", "search-yts", "search-eztv",
    "rss-anime", "rss-tv-movie",
    "metadata-douban",
    "download-openlist", "storage-openlist",
    "feature-subscribe",
  ]);

  const filtered = activeCategory === "all"
    ? plugins.filter(p => !p.id.includes("deprecated") && !COMMUNITY_ONLY_PLUGINS.has(p.id))
    : activeCategory === "installed"
    ? plugins.filter(p => p.installed)
    : plugins.filter(p => p.category === activeCategory && !p.id.includes("deprecated") && !COMMUNITY_ONLY_PLUGINS.has(p.id));

  // 排序：已安装在前，同组内按 category → name 排序
  const sorted = [...filtered].sort((a, b) => {
    if (a.installed !== b.installed) return a.installed ? -1 : 1;
    if (a.category !== b.category) return a.category.localeCompare(b.category);
    return a.name.localeCompare(b.name);
  });

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* 遮罩 */}
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />

      {/* 面板 */}
      <div className="relative ml-auto w-full max-w-lg h-full bg-[#141414] border-l border-white/[0.06] flex flex-col animate-in slide-in-from-right duration-300">
        {/* 头部 */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06]">
          <div className="flex items-center gap-2">
            <span className="text-lg">🧩</span>
            <h2 className="text-base font-semibold text-slate-200">插件中心</h2>
            <span className="text-xs text-slate-500">
              {plugins.filter(p => p.installed).length}/{plugins.length} 已安装
            </span>
          </div>
          <button onClick={onClose} className="w-8 h-8 rounded-lg flex items-center justify-center text-slate-500 hover:text-slate-300 hover:bg-white/5">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* 内置/第三方 切换 */}
        <div className="flex items-center gap-1 px-6 py-2 border-b border-white/[0.06]">
          <button onClick={() => setShowRemote(false)}
            className={`px-3 py-1.5 rounded-lg text-xs transition-all ${
              !showRemote ? "bg-white/[0.08] text-slate-200 font-medium" : "text-slate-500 hover:text-slate-300"
            }`}>
            内置插件
          </button>
          <button onClick={() => setShowRemote(true)}
            className={`px-3 py-1.5 rounded-lg text-xs transition-all ${
              showRemote ? "bg-white/[0.08] text-slate-200 font-medium" : "text-slate-500 hover:text-slate-300"
            }`}>
            第三方插件源
          </button>
        </div>

        {!showRemote && (
          <>
            {/* 分类 Tab */}
            <div className="flex gap-1 px-6 py-3 border-b border-white/[0.06] overflow-x-auto no-scrollbar">
              {CATEGORIES.map(cat => (
                <button key={cat.key} onClick={() => setActiveCategory(cat.key)}
                  className={`px-3 py-1.5 rounded-lg text-xs whitespace-nowrap transition-all ${
                    activeCategory === cat.key
                      ? "bg-blue-500/15 text-blue-400 font-medium"
                      : "text-slate-500 hover:text-slate-300 hover:bg-white/5"
                  }`}>
                  {cat.label}
                </button>
              ))}
            </div>

            {/* 错误提示 */}
            {error && (
              <div className="mx-6 mt-3 px-3 py-2 bg-red-500/10 border border-red-500/20 rounded-lg text-xs text-red-400">
                {error}
                <button onClick={() => setError("")} className="ml-2 text-red-500 hover:text-red-300">✕</button>
              </div>
            )}

            {/* 插件列表 */}
            <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
              {loading ? (
                <div className="flex items-center justify-center py-12">
                  <div className="w-6 h-6 border-2 border-slate-700 border-t-blue-500 rounded-full animate-spin" />
                </div>
              ) : filtered.length === 0 ? (
                <div className="text-center py-12 text-slate-600 text-sm">暂无插件</div>
              ) : (
                sorted.map(plugin => (
                  <PluginCard
                    key={plugin.id}
                    plugin={plugin}
                    loading={actionLoading === plugin.id}
                    onInstall={() => handleInstall(plugin.id)}
                    onUninstall={() => handleUninstall(plugin.id)}
                    onConfig={() => setConfigPlugin(plugin)}
                  />
                ))
              )}
            </div>
          </>
        )}

        {showRemote && (
          <div className="flex-1 overflow-y-auto px-6 py-4">
            <RemotePluginList
              onAddSource={() => setShowAddSource(true)}
              onInstalled={() => { loadPlugins(); window.dispatchEvent(new Event("plugins-changed")); }}
            />
          </div>
        )}
      </div>

      {/* 配置弹窗 */}
      {configPlugin && (
        <PluginConfigModal
          plugin={configPlugin}
          onClose={() => setConfigPlugin(null)}
          onSaved={() => { setConfigPlugin(null); loadPlugins(); }}
        />
      )}

      {/* 添加插件源弹窗 */}
      {showAddSource && (
        <AddSourceModal
          onClose={() => setShowAddSource(false)}
          onAdded={() => { setShowAddSource(false); }}
        />
      )}
    </div>
  );
}
