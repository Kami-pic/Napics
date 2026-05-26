// 首次扫描完成摘要弹窗 — 展示媒体库统计 + 引导下一步
"use client";
import { useMemo } from "react";
import type { FolderNode } from "@/types";

interface ScanSummaryModalProps {
  open: boolean;
  onClose: () => void;
  tree: FolderNode | null;
  totalVideos: number;
  hasMetadataPlugin: boolean;
  onOpenSettings: () => void;
}

interface TreeStats {
  movies: number;
  tvShows: number;
  unidentified: number;
  totalFolders: number;
}

function countTree(node: FolderNode): TreeStats {
  const stats: TreeStats = { movies: 0, tvShows: 0, unidentified: 0, totalFolders: 0 };
  const walk = (n: FolderNode) => {
    if (!n.path || n.is_top_category || n.is_virtual_library) {
      for (const child of n.children || []) walk(child);
      return;
    }
    stats.totalFolders++;
    const ft = n.folder_type;
    if (ft === "movie") stats.movies++;
    else if (ft === "tv" || ft === "season") stats.tvShows++;
    else if (!ft || ft === "mixed") stats.unidentified++;
    for (const child of n.children || []) walk(child);
  };
  walk(node);
  return stats;
}

export default function ScanSummaryModal({ open, onClose, tree, totalVideos, hasMetadataPlugin, onOpenSettings }: ScanSummaryModalProps) {
  const stats = useMemo(() => tree ? countTree(tree) : null, [tree]);

  if (!open || !stats) return null;

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-[#1a1a1a] border border-white/[0.08] rounded-2xl p-6 w-[380px] shadow-2xl" onClick={e => e.stopPropagation()}>
        <div className="text-center mb-5">
          <span className="text-4xl">🎉</span>
          <h2 className="text-lg font-medium text-white mt-2">扫描完成</h2>
        </div>

        <div className="grid grid-cols-2 gap-3 mb-5">
          <StatCard icon="🎬" label="电影" value={stats.movies} />
          <StatCard icon="📺" label="剧集" value={stats.tvShows} />
          <StatCard icon="📁" label="视频文件" value={totalVideos} />
          <StatCard icon="❓" label="待识别" value={stats.unidentified} />
        </div>

        {stats.unidentified > 0 && (
          <div className="text-xs text-slate-400 bg-white/[0.03] rounded-lg p-3 mb-4">
            {hasMetadataPlugin
              ? "💡 点击待识别的文件夹，可以手动匹配或自动刮削"
              : "💡 安装元数据插件后可自动刮削影片信息"}
          </div>
        )}

        {!hasMetadataPlugin && (
          <button onClick={() => { onClose(); onOpenSettings(); }}
            className="w-full py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-sm text-white font-medium transition-colors mb-2">
            配置 TMDB API Key
          </button>
        )}

        <button onClick={onClose}
          className="w-full py-2.5 rounded-lg bg-white/[0.06] hover:bg-white/[0.1] text-sm text-slate-300 transition-colors">
          开始使用
        </button>
      </div>
    </div>
  );
}

function StatCard({ icon, label, value }: { icon: string; label: string; value: number }) {
  return (
    <div className="flex items-center gap-2.5 bg-white/[0.03] rounded-lg px-3 py-2.5">
      <span className="text-lg">{icon}</span>
      <div>
        <div className="text-lg font-semibold text-white leading-tight">{value}</div>
        <div className="text-[10px] text-slate-500">{label}</div>
      </div>
    </div>
  );
}
