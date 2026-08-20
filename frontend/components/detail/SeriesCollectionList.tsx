"use client";
import { useState } from "react";
import type { FolderNode, VideoInfo } from "@/types";
import { api } from "@/lib/api";
import { formatDuration } from "@/lib/utils";

interface SeriesCollectionListProps {
  node: FolderNode;
  onSelectItem: (child: FolderNode | VideoInfo) => void;
  selectedPath: string | null;
}

export default function SeriesCollectionList({ node, onSelectItem, selectedPath }: SeriesCollectionListProps) {
  // 子项来源：优先子文件夹，没有则用直接视频
  const items = node.children.length > 0
    ? node.children.map(c => ({ type: "folder" as const, name: c.name, path: c.path, node: c, video: c.videos[0] }))
    : node.videos.map(v => ({ type: "video" as const, name: v.file_name, path: v.file_path, node: null, video: v }));

  return (
    <div className="space-y-1.5">
      {items.map(item => (
        <button
          key={item.path}
          onClick={() => onSelectItem(item.type === "folder" ? item.node! : item.video)}
          className={`w-full flex gap-3 p-2.5 rounded-lg text-left transition-all ${
            selectedPath === item.path
              ? "bg-blue-500/10 border border-blue-500/20"
              : "bg-white/[0.03] hover:bg-white/[0.06] border border-transparent"
          }`}
        >
          <ItemPoster path={item.path} name={item.name} />
          <div className="flex-1 min-w-0">
            <p className="text-sm text-white truncate">{item.name}</p>
            {item.video && (
              <div className="flex items-center gap-2 mt-1">
                {item.video.resolution && <span className="text-[10px] text-slate-500">{item.video.resolution}</span>}
                {(item.video.duration_min ?? item.video.duration ?? 0) > 0 && <span className="text-[10px] text-slate-600">{formatDuration(item.video.duration_min ?? item.video.duration)}</span>}
                {item.video.size_gb > 0 && <span className="text-[10px] text-slate-600">{item.video.size_gb.toFixed(1)}GB</span>}
              </div>
            )}
          </div>
        </button>
      ))}
      {items.length === 0 && <p className="text-xs text-slate-600 py-4 text-center">暂无内容</p>}
    </div>
  );
}

function ItemPoster({ path, name }: { path: string; name: string }) {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);
  const src = api.getLocalPoster(path);

  return (
    <div className="w-[60px] h-[84px] rounded-md overflow-hidden bg-[#222] flex-shrink-0 relative">
      {!loaded && !error && <div className="absolute inset-0 flex items-center justify-center"><span className="text-slate-700 text-lg">🎬</span></div>}
      {error && <div className="absolute inset-0 flex items-center justify-center"><span className="text-slate-700 text-lg">🎬</span></div>}
      <img
        src={src}
        alt={name}
        className={`w-full h-full object-cover transition-opacity ${loaded ? "opacity-100" : "opacity-0"}`}
        onLoad={() => setLoaded(true)}
        onError={() => setError(true)}
      />
    </div>
  );
}
