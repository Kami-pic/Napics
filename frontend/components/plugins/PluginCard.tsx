// 单个插件卡片
"use client";
import React, { useState } from "react";
import type { PluginInfo } from "@/lib/api/plugins";

interface PluginCardProps {
  plugin: PluginInfo;
  loading: boolean;
  onInstall: () => void;
  onUninstall: () => void;
  onConfig: () => void;
}

export default function PluginCard({ plugin, loading, onInstall, onUninstall, onConfig }: PluginCardProps) {
  const [confirmUninstall, setConfirmUninstall] = useState(false);

  const categoryColors: Record<string, string> = {
    metadata: "text-purple-400 bg-purple-500/10",
    search: "text-blue-400 bg-blue-500/10",
    rss: "text-orange-400 bg-orange-500/10",
    download: "text-green-400 bg-green-500/10",
    storage: "text-cyan-400 bg-cyan-500/10",
    feature: "text-yellow-400 bg-yellow-500/10",
  };

  const catStyle = categoryColors[plugin.category] || "text-slate-400 bg-white/5";

  return (
    <div className={`p-4 rounded-xl border transition-all ${
      plugin.installed
        ? "bg-white/[0.03] border-white/[0.08]"
        : "bg-white/[0.02] border-white/[0.04] hover:border-white/[0.08]"
    }`}>
      <div className="flex items-start gap-3">
        {/* 图标 */}
        <span className="text-2xl flex-shrink-0 mt-0.5">{plugin.icon || "🧩"}</span>

        {/* 信息 */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-slate-200">{plugin.name}</span>
            <span className={`px-1.5 py-0.5 rounded text-[10px] ${catStyle}`}>
              {plugin.category}
            </span>
            {plugin.installed && (
              <span className="px-1.5 py-0.5 rounded text-[10px] text-green-400 bg-green-500/10">已安装</span>
            )}
          </div>
          <p className="text-xs text-slate-500 mt-1 line-clamp-2">{plugin.description}</p>

          {/* 依赖提示 */}
          {plugin.depends_on.length > 0 && (
            <p className="text-[10px] text-slate-600 mt-1">
              依赖: {plugin.depends_on.join(", ")}
            </p>
          )}
        </div>

        {/* 操作按钮 */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {plugin.installed ? (
            <>
              {plugin.requires_config.length > 0 && (
                <button onClick={onConfig}
                  className="px-2.5 py-1.5 rounded-lg text-xs text-slate-400 hover:text-slate-200 hover:bg-white/5 transition-all">
                  配置
                </button>
              )}
              {confirmUninstall ? (
                <div className="flex items-center gap-1">
                  <button onClick={() => { onUninstall(); setConfirmUninstall(false); }}
                    disabled={loading}
                    className="px-2.5 py-1.5 rounded-lg text-xs text-red-400 bg-red-500/10 hover:bg-red-500/20 transition-all disabled:opacity-50">
                    {loading ? "..." : "确认"}
                  </button>
                  <button onClick={() => setConfirmUninstall(false)}
                    className="px-2 py-1.5 rounded-lg text-xs text-slate-500 hover:text-slate-300">
                    取消
                  </button>
                </div>
              ) : (
                <button onClick={() => setConfirmUninstall(true)}
                  className="px-2.5 py-1.5 rounded-lg text-xs text-red-400/70 hover:text-red-400 hover:bg-red-500/10 transition-all">
                  卸载
                </button>
              )}
            </>
          ) : (
            <button onClick={onInstall} disabled={loading}
              className="px-3 py-1.5 rounded-lg text-xs text-blue-400 bg-blue-500/10 hover:bg-blue-500/20 transition-all disabled:opacity-50">
              {loading ? "安装中..." : "安装"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
