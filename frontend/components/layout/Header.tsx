// 顶部栏：标题+统计 | 下载管理、扫描、表单管理、设置
"use client";
import Link from "next/link";
import type { LibraryStats } from "@/types";

interface HeaderProps {
  stats: LibraryStats;
  onOpenSettings: () => void;
  scanning?: boolean;
  onStartScan: () => void;
  onStopScan: () => void;
  onNavigateHome?: () => void;
  onOpenDownloads: () => void;
  syncMsg?: string;
  syncing?: boolean;
}

export default function Header({ stats, onOpenSettings, scanning, onStartScan, onStopScan, onNavigateHome, onOpenDownloads, syncMsg, syncing }: HeaderProps) {
  return (
    <header className="flex justify-between items-center py-5 px-1">
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight cursor-pointer hover:opacity-80 transition-opacity"
          onClick={onNavigateHome}>NAS Media Manager</h1>
        <div className="flex items-center gap-3 mt-1">
          {syncing && syncMsg && (
            <span className="flex items-center gap-1.5 text-xs text-green-400">
              <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse" />
              {syncMsg}
            </span>
          )}
          {scanning && !syncing && <span className="flex items-center gap-1.5 text-xs text-blue-400"><span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-pulse" />扫描中...</span>}
          {stats.total > 0 && !scanning && !syncing && (
            <span className="text-xs text-slate-500">{stats.total} 个资源 · {stats.lowRes} 待升级 · {stats.missingSub} 缺字幕</span>
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
        <Link href="/manage" className="px-4 py-2 text-sm text-slate-400 hover:bg-white/5 rounded-lg transition-all">表单管理</Link>
        <button onClick={onOpenSettings} className="w-9 h-9 rounded-lg flex items-center justify-center text-slate-500 hover:bg-white/5 hover:text-slate-300 transition-all">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 010 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 010-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28z" /><circle cx="12" cy="12" r="3" /></svg>
        </button>
      </div>
    </header>
  );
}
