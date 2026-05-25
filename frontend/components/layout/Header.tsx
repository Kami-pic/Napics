// 顶部栏：标题+统计 | 下载管理、扫描、表单管理、设置
"use client";
import { useState } from "react";
import Link from "next/link";
import type { LibraryStats } from "@/types";
import { api } from "@/lib/api";

interface HeaderProps {
  stats: LibraryStats;
  onOpenSettings?: () => void;  // 已移至 Sidebar，保留兼容
  scanning?: boolean;
  onStartScan: () => void;
  onStopScan: () => void;
  onNavigateHome?: () => void;
  onOpenDownloads: () => void;
  onOpenSubscriptions?: () => void;
  subscriptionCount?: number;
  syncMsg?: string;
  syncing?: boolean;
  onRefresh?: () => void;
}

export default function Header({ stats, onOpenSettings, scanning, onStartScan, onStopScan, onNavigateHome, onOpenDownloads, onOpenSubscriptions, subscriptionCount = 0, syncMsg, syncing, onRefresh }: HeaderProps) {
  const [refreshing, setRefreshing] = useState(false);
  const handleRefreshQuality = async () => {
    setRefreshing(true);
    try {
      const res = await api.refreshQuality();
      if (onRefresh && res.updated > 0) onRefresh();
    } catch {}
    setRefreshing(false);
  };
  return (
    <header className="flex justify-between items-center py-5 px-1">
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight cursor-pointer hover:opacity-80 transition-opacity"
          onClick={onNavigateHome}>Napics Media Manager</h1>
        <div className="flex items-center gap-3 mt-1">
          {syncing && syncMsg && (
            <span className="flex items-center gap-1.5 text-xs text-green-400">
              <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse" />
              {syncMsg}
            </span>
          )}
          {scanning && !syncing && <span className="flex items-center gap-1.5 text-xs text-blue-400"><span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-pulse" />扫描中...</span>}
          {stats.total > 0 && !scanning && !syncing && (
            <span className="text-xs text-slate-500">
              {stats.total} 个资源 · {stats.lowRes} 待升级 · {stats.missingSub} 缺字幕
              <button onClick={handleRefreshQuality} disabled={refreshing}
                className="ml-2 text-slate-600 hover:text-blue-400 transition-colors disabled:opacity-50"
                title="全局重新检测质量分">
                {refreshing ? "检测中..." : "检测质量"}
              </button>
            </span>
          )}
        </div>
      </div>
      <div className="flex items-center gap-2">
        {scanning ? (
          <button onClick={onStopScan} className="px-4 py-2 text-sm text-red-400 hover:bg-red-500/10 rounded-lg transition-all">停止</button>
        ) : (
          <button onClick={onStartScan} className="px-4 py-2 text-sm text-blue-400 hover:bg-blue-500/10 rounded-lg transition-all">扫描媒体库</button>
        )}
        <button onClick={onOpenDownloads} className="px-4 py-2 text-sm text-slate-400 hover:bg-white/5 rounded-lg transition-all">下载管理</button>
        {onOpenSubscriptions && (
          <button onClick={onOpenSubscriptions} className="relative px-4 py-2 text-sm text-slate-400 hover:bg-white/5 rounded-lg transition-all">
            订阅
            {subscriptionCount > 0 && (
              <span className="absolute -top-1 -right-1 w-4 h-4 bg-violet-600 text-white text-[9px] font-bold rounded-full flex items-center justify-center">{subscriptionCount}</span>
            )}
          </button>
        )}
        <Link href="/manage" className="px-4 py-2 text-sm text-slate-400 hover:bg-white/5 rounded-lg transition-all">表单管理</Link>
      </div>
    </header>
  );
}
