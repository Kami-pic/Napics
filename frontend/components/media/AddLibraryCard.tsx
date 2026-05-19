// 常驻添加媒体文件夹卡片（一级目录第一张）
"use client";

interface AddLibraryCardProps {
  onClick: () => void;
}

export default function AddLibraryCard({ onClick }: AddLibraryCardProps) {
  return (
    <button onClick={onClick}
      className="group w-full aspect-[2/3] rounded-xl border-2 border-dashed border-white/[0.08] hover:border-blue-500/30 bg-white/[0.02] hover:bg-blue-500/[0.03] flex flex-col items-center justify-center gap-3 transition-all cursor-pointer">
      <div className="w-10 h-10 rounded-full bg-white/[0.04] group-hover:bg-blue-500/10 flex items-center justify-center transition-all">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-slate-500 group-hover:text-blue-400 transition-colors">
          <path d="M12 5v14M5 12h14" />
        </svg>
      </div>
      <span className="text-xs text-slate-500 group-hover:text-slate-300 transition-colors">添加媒体文件夹</span>
    </button>
  );
}
