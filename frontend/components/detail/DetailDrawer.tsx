// 右侧详情面板（瘦壳入口，子组件已拆分到独立文件）
"use client";
import type { VideoInfo, FolderNode } from "@/types";
import { FolderDetail } from "./FolderDetail";
import { VideoDetail } from "./VideoDetail";
import { BatchPanel } from "./BatchPanel";
import { EditableTitle } from "./EditableTitle";

interface DetailDrawerProps {
  target: { type: "folder"; node: FolderNode } | { type: "video"; video: VideoInfo } | null;
  open: boolean;
  onClose: () => void;
  onPlay: (path: string) => void;
  onSearch: (query: string, ctx?: any) => void;
  onRefresh: () => void;
  onTreeRefresh: () => void;
  onRenamed: () => void;
  batchMode: boolean;
  selectedPaths: Set<string>;
  batchAction: (action: "delete" | "move" | "remove", targetDir?: string) => void;
  onClearSelection: () => void;
  currentVideos?: VideoInfo[];
  onSelectAll?: () => void;
  onInvertSelect?: () => void;
  currentCategoryTag?: string;
}

export default function DetailDrawer({ target, open, onClose, onPlay, onSearch, onRefresh, onTreeRefresh, onRenamed,
  batchMode, selectedPaths, batchAction, onClearSelection, currentVideos, onSelectAll, onInvertSelect, currentCategoryTag }: DetailDrawerProps) {
  if (!open) return null;
  if (batchMode && selectedPaths.size > 0) {
    return (
      <aside className="w-[380px] h-screen bg-[#141414] border-l border-white/[0.06] flex flex-col flex-shrink-0">
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.06]">
          <h3 className="text-base font-semibold text-slate-200">批处理</h3>
          <span className="text-xs text-slate-500">已选 {selectedPaths.size} 项</span>
        </div>
        <BatchPanel selectedPaths={selectedPaths} batchAction={batchAction} onClear={onClearSelection} onSearch={onSearch} onRefresh={onRefresh}
          currentVideos={currentVideos} onSelectAll={onSelectAll} onInvertSelect={onInvertSelect} />
      </aside>
    );
  }
  if (!target) return null;
  if (target.type === "folder" && target.node.path === "") return null;
  const currentName = target.type === "folder" ? (target.node.name || "媒体库") : target.video.file_name;
  const currentPath = target.type === "folder" ? target.node.path : target.video.file_path;

  return (
    <aside data-detail-drawer className="w-[380px] h-screen bg-[#141414] border-l border-white/[0.06] flex flex-col flex-shrink-0">
      <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.06] flex-shrink-0">
        <EditableTitle name={currentName} path={currentPath} onRenamed={onRenamed} />
        <button onClick={onClose} className="w-9 h-9 rounded-lg flex items-center justify-center text-slate-400 hover:text-white hover:bg-white/10 transition-all flex-shrink-0 text-lg">✕</button>
      </div>
      <div className="flex-1 overflow-y-auto">
        {target.type === "folder" ? (
          <FolderDetail key={target.node.path} node={target.node} onRefresh={onRefresh} onTreeRefresh={onTreeRefresh} onSearch={onSearch} currentCategoryTag={currentCategoryTag || ""} />
        ) : (
          <VideoDetail key={target.video.file_path} video={target.video} onPlay={onPlay} onSearch={onSearch} onRefresh={onRefresh} />
        )}
      </div>
    </aside>
  );
}
