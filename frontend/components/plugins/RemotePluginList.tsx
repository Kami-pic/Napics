// 远程插件列表 — 按插件源分组嵌套展示 + 从 URL 安装/添加源
"use client";
import React, { useState, useEffect, useCallback } from "react";
import {
  fetchPluginSources,
  fetchRemotePlugins,
  addPluginSource,
  removePluginSource,
  installRemotePlugin,
  uninstallPlugin,
  installFromUrl,
  type PluginSource,
  type RemotePluginItem,
} from "@/lib/api/plugins";

interface RemotePluginListProps {
  onInstalled: () => void;
}

// 社区插件源
const PARTNER_SOURCE = {
  name: "Napics 社区插件源",
  url: "https://github.com/icatmiumiu/plugins-of-napics",
};

interface SourceGroup {
  name: string;
  url: string;
  plugins: RemotePluginItem[];
}

export default function RemotePluginList({ onInstalled }: RemotePluginListProps) {
  const [sources, setSources] = useState<PluginSource[]>([]);
  const [remotePlugins, setRemotePlugins] = useState<RemotePluginItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [fetchingPartner, setFetchingPartner] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [errors, setErrors] = useState<Array<{ url: string; error: string }>>([]);
  const [collapsedSources, setCollapsedSources] = useState<Set<string>>(new Set());
  // URL 输入（统一入口：自动判断是插件源还是单插件）
  const [urlInput, setUrlInput] = useState("");
  const [urlLoading, setUrlLoading] = useState(false);
  const [urlSuccess, setUrlSuccess] = useState("");

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [sourcesData, remoteData] = await Promise.all([
        fetchPluginSources(),
        fetchRemotePlugins(),
      ]);
      setSources(sourcesData);
      setRemotePlugins(remoteData.plugins);
      setErrors(remoteData.errors);
    } catch (e) {
      console.error("加载远程插件失败", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // 获取合作插件
  const handleFetchPartner = async () => {
    const alreadyAdded = sources.some(s => s.url === PARTNER_SOURCE.url);
    if (alreadyAdded) {
      await loadData();
      return;
    }
    setFetchingPartner(true);
    setError("");
    try {
      await addPluginSource(PARTNER_SOURCE.name, PARTNER_SOURCE.url);
      await loadData();
    } catch (e: any) {
      const msg = e?.message || e?.error || "获取失败";
      if (typeof msg === "string" && msg.includes("已添加")) {
        await loadData();
      } else {
        setError(typeof msg === "string" ? msg : JSON.stringify(msg));
      }
    } finally {
      setFetchingPartner(false);
    }
  };

  const handleRemoveSource = async (url: string) => {
    try {
      await removePluginSource(url);
      await loadData();
    } catch (e: any) {
      setError(e?.message || "移除失败");
    }
  };

  const handleInstallRemote = async (plugin: RemotePluginItem) => {
    setActionLoading(plugin.id);
    setError("");
    try {
      await installRemotePlugin(plugin.source, plugin.id);
      await loadData();
      onInstalled();
    } catch (e: any) {
      const msg = e?.message || e?.error || "安装失败";
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setActionLoading(null);
    }
  };

  const handleUninstallRemote = async (pluginId: string) => {
    setActionLoading(pluginId);
    setError("");
    try {
      await uninstallPlugin(pluginId);
      await loadData();
      onInstalled();
    } catch (e: any) {
      const msg = e?.message || e?.error || "卸载失败";
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setActionLoading(null);
    }
  };

  // 统一 URL 安装：先尝试当作插件源添加，失败则当作单插件安装
  const handleUrlInstall = async () => {
    const url = urlInput.trim();
    if (!url) return;
    setUrlLoading(true);
    setError("");
    setUrlSuccess("");
    try {
      // 先尝试当作插件源
      await addPluginSource("", url);
      setUrlSuccess("插件源添加成功");
      setUrlInput("");
      await loadData();
    } catch {
      // 插件源失败，尝试当作单插件仓库安装
      try {
        const result = await installFromUrl(url);
        setUrlSuccess(`"${result.name || result.plugin_id}" 安装成功`);
        setUrlInput("");
        onInstalled();
        await loadData();
      } catch (e2: any) {
        const msg = e2?.message || e2?.error || "安装失败";
        setError(typeof msg === "string" ? msg : JSON.stringify(msg));
      }
    } finally {
      setUrlLoading(false);
    }
  };

  const toggleSource = (url: string) => {
    setCollapsedSources(prev => {
      const next = new Set(prev);
      if (next.has(url)) next.delete(url);
      else next.add(url);
      return next;
    });
  };

  // 按源分组
  const sourceGroups: SourceGroup[] = [];
  const groupMap = new Map<string, SourceGroup>();
  for (const plugin of remotePlugins) {
    let group = groupMap.get(plugin.source);
    if (!group) {
      group = { name: plugin.source_name, url: plugin.source, plugins: [] };
      groupMap.set(plugin.source, group);
      sourceGroups.push(group);
    }
    group.plugins.push(plugin);
  }

  if (sources.length === 0 && !loading) {
    return (
      <div className="space-y-6">
        <div className="text-center py-10">
          <p className="text-sm text-slate-500 mb-4">暂无外部插件源</p>
          <button onClick={handleFetchPartner} disabled={fetchingPartner}
            className="px-4 py-2 rounded-lg text-xs bg-emerald-500/15 text-emerald-400 hover:bg-emerald-500/25 disabled:opacity-50">
            {fetchingPartner ? "获取中..." : "🤝 获取合作插件"}
          </button>
        </div>
        <UrlInstallSection
          url={urlInput} setUrl={setUrlInput}
          loading={urlLoading} onInstall={handleUrlInstall}
          success={urlSuccess}
        />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* 操作栏 */}
      <div className="flex items-center justify-between">
        <span className="text-xs text-slate-500">插件源</span>
        <button onClick={handleFetchPartner} disabled={fetchingPartner}
          className="text-xs text-emerald-400 hover:text-emerald-300 disabled:opacity-50">
          {fetchingPartner ? "获取中..." : "🤝 获取合作插件"}
        </button>
      </div>

      {/* 错误提示 */}
      {errors.length > 0 && (
        <div className="space-y-1.5">
          {errors.map((e, i) => (
            <div key={i} className="px-3 py-2 bg-red-500/5 border border-red-500/10 rounded-lg text-[11px] text-red-400">
              {e.url}: {e.error}
            </div>
          ))}
        </div>
      )}

      {error && (
        <div className="px-3 py-2 bg-red-500/10 border border-red-500/20 rounded-lg text-xs text-red-400">
          {error}
          <button onClick={() => setError("")} className="ml-2 text-red-500 hover:text-red-300">✕</button>
        </div>
      )}

      {/* 按源分组的嵌套列表 */}
      {loading ? (
        <div className="flex items-center justify-center py-10">
          <div className="w-5 h-5 border-2 border-slate-700 border-t-blue-500 rounded-full animate-spin" />
        </div>
      ) : sourceGroups.length > 0 ? (
        <div className="space-y-4">
          {sourceGroups.map(group => {
            const isCollapsed = collapsedSources.has(group.url);
            return (
              <div key={group.url} className="border border-white/[0.06] rounded-xl overflow-hidden">
                {/* 源头部 */}
                <div className="flex items-center justify-between px-4 py-3 bg-white/[0.03] cursor-pointer hover:bg-white/[0.05] transition-colors"
                  onClick={() => toggleSource(group.url)}>
                  <div className="flex items-center gap-2.5 min-w-0">
                    <svg className={`w-3.5 h-3.5 text-slate-500 transition-transform ${isCollapsed ? "" : "rotate-90"}`}
                      fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                    </svg>
                    <span className="text-xs font-medium text-slate-300 truncate">{group.name}</span>
                    <span className="text-[10px] text-slate-600">{group.plugins.length} 个插件</span>
                  </div>
                  <button
                    onClick={e => { e.stopPropagation(); handleRemoveSource(group.url); }}
                    className="text-[10px] text-red-400/50 hover:text-red-400 flex-shrink-0 px-2 py-1 rounded hover:bg-red-500/10"
                  >
                    移除源
                  </button>
                </div>

                {/* 插件列表 */}
                {!isCollapsed && (
                  <div className="divide-y divide-white/[0.04]">
                    {group.plugins.map(plugin => (
                      <div key={plugin.id} className="flex items-center gap-3 px-4 py-3 pl-10 hover:bg-white/[0.02] transition-colors">
                        <span className="text-lg flex-shrink-0">{plugin.icon || "🧩"}</span>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-sm text-slate-200">{plugin.name}</span>
                            {plugin.installed && (
                              <span className="px-1.5 py-0.5 rounded text-[10px] text-green-400 bg-green-500/10">已安装</span>
                            )}
                          </div>
                          <p className="text-[11px] text-slate-500 mt-1">{plugin.description}</p>
                        </div>
                        <div className="flex-shrink-0">
                          {plugin.installed ? (
                            <button
                              onClick={() => handleUninstallRemote(plugin.id)}
                              disabled={actionLoading === plugin.id}
                              className="px-3 py-1.5 rounded-lg text-xs text-red-400/70 hover:text-red-400 hover:bg-red-500/10 disabled:opacity-50"
                            >
                              {actionLoading === plugin.id ? "..." : "卸载"}
                            </button>
                          ) : (
                            <button
                              onClick={() => handleInstallRemote(plugin)}
                              disabled={actionLoading === plugin.id}
                              className="px-3 py-1.5 rounded-lg text-xs bg-blue-500/15 text-blue-400 hover:bg-blue-500/25 disabled:opacity-50"
                            >
                              {actionLoading === plugin.id ? "..." : "安装"}
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <div className="text-center py-8 text-xs text-slate-600">
          插件源中暂无可用插件
        </div>
      )}

      {/* 从 URL 安装/添加源 */}
      <UrlInstallSection
        url={urlInput} setUrl={setUrlInput}
        loading={urlLoading} onInstall={handleUrlInstall}
        success={urlSuccess}
      />
    </div>
  );
}

// 从 URL 安装/添加源 — 统一入口
function UrlInstallSection({ url, setUrl, loading, onInstall, success }: {
  url: string; setUrl: (v: string) => void;
  loading: boolean; onInstall: () => void;
  success: string;
}) {
  return (
    <div className="border-t border-white/[0.06] pt-5">
      <p className="text-xs text-slate-500 mb-3">从 URL 添加</p>
      <div className="flex gap-2">
        <input
          value={url}
          onChange={e => setUrl(e.target.value)}
          placeholder="输入 GitHub 仓库地址（插件源或单个插件）"
          className="flex-1 px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-blue-500/50"
          onKeyDown={e => { if (e.key === "Enter" && !loading) onInstall(); }}
        />
        <button
          onClick={onInstall}
          disabled={loading || !url.trim()}
          className="px-3 py-2 rounded-lg text-xs bg-blue-500/15 text-blue-400 hover:bg-blue-500/25 disabled:opacity-50 flex-shrink-0"
        >
          {loading ? "..." : "添加"}
        </button>
      </div>
      {success && (
        <div className="mt-2 px-3 py-1.5 bg-green-500/10 border border-green-500/20 rounded-lg text-[11px] text-green-400">
          {success}
        </div>
      )}
    </div>
  );
}
