// 远程插件列表 — 展示外部插件源中的可用插件
"use client";
import React, { useState, useEffect, useCallback } from "react";
import {
  fetchPluginSources,
  fetchRemotePlugins,
  removePluginSource,
  installRemotePlugin,
  type PluginSource,
  type RemotePluginItem,
} from "@/lib/api/plugins";

interface RemotePluginListProps {
  onAddSource: () => void;
  onInstalled: () => void;
}

export default function RemotePluginList({ onAddSource, onInstalled }: RemotePluginListProps) {
  const [sources, setSources] = useState<PluginSource[]>([]);
  const [remotePlugins, setRemotePlugins] = useState<RemotePluginItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [errors, setErrors] = useState<Array<{ url: string; error: string }>>([]);

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

  const riskColors: Record<string, string> = {
    low: "text-green-400 bg-green-500/10",
    medium: "text-amber-400 bg-amber-500/10",
    high: "text-red-400 bg-red-500/10",
  };

  if (sources.length === 0 && !loading) {
    return (
      <div className="text-center py-8">
        <p className="text-sm text-slate-500 mb-3">暂无外部插件源</p>
        <button onClick={onAddSource}
          className="px-4 py-2 rounded-lg text-xs bg-blue-500/15 text-blue-400 hover:bg-blue-500/25">
          添加插件源
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* 已添加的源 */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs text-slate-500">已添加的插件源</span>
          <button onClick={onAddSource}
            className="text-[10px] text-blue-400 hover:text-blue-300">
            + 添加
          </button>
        </div>
        {sources.map(s => (
          <div key={s.url} className="flex items-center justify-between px-3 py-2 bg-white/[0.02] border border-white/[0.06] rounded-lg">
            <div className="min-w-0">
              <span className="text-xs text-slate-300 block truncate">{s.name || s.url}</span>
              <span className="text-[10px] text-slate-600 block truncate">{s.url}</span>
            </div>
            <button onClick={() => handleRemoveSource(s.url)}
              className="text-[10px] text-red-400/60 hover:text-red-400 ml-2 flex-shrink-0">
              移除
            </button>
          </div>
        ))}
      </div>

      {/* 错误提示 */}
      {errors.length > 0 && (
        <div className="space-y-1">
          {errors.map((e, i) => (
            <div key={i} className="px-3 py-1.5 bg-red-500/5 border border-red-500/10 rounded text-[10px] text-red-400">
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

      {/* 远程插件列表 */}
      {loading ? (
        <div className="flex items-center justify-center py-8">
          <div className="w-5 h-5 border-2 border-slate-700 border-t-blue-500 rounded-full animate-spin" />
        </div>
      ) : remotePlugins.length > 0 ? (
        <div className="space-y-2">
          <span className="text-xs text-slate-500">可安装的插件</span>
          {remotePlugins.map(plugin => (
            <div key={plugin.id} className="p-3 bg-white/[0.02] border border-white/[0.04] rounded-xl hover:border-white/[0.08] transition-all">
              <div className="flex items-start gap-3">
                <span className="text-xl flex-shrink-0">{plugin.icon || "🧩"}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-slate-200">{plugin.name}</span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] ${riskColors[plugin.risk_level] || "text-slate-400 bg-white/5"}`}>
                      {plugin.risk_level === "high" ? "⚠️ 高风险" : plugin.category}
                    </span>
                    {plugin.installed && (
                      <span className="px-1.5 py-0.5 rounded text-[10px] text-green-400 bg-green-500/10">已安装</span>
                    )}
                  </div>
                  <p className="text-xs text-slate-500 mt-1 line-clamp-2">{plugin.description}</p>
                  <p className="text-[10px] text-slate-600 mt-0.5">来源: {plugin.source_name}</p>
                </div>
                <div className="flex-shrink-0">
                  {plugin.installed ? (
                    <span className="text-[10px] text-green-400/60">✓</span>
                  ) : (
                    <button
                      onClick={() => handleInstallRemote(plugin)}
                      disabled={actionLoading === plugin.id}
                      className="px-3 py-1.5 rounded-lg text-xs bg-blue-500/15 text-blue-400 hover:bg-blue-500/25 disabled:opacity-50"
                    >
                      {actionLoading === plugin.id ? "安装中..." : "安装"}
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-6 text-xs text-slate-600">
          插件源中暂无可用插件
        </div>
      )}
    </div>
  );
}
