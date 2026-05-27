// 无媒体库时的引导区域
"use client";

interface EmptyLibraryGuideProps {
  onAddScanPath: () => void;
  onAddLibrary: () => void;
}

export default function EmptyLibraryGuide({ onAddScanPath, onAddLibrary }: EmptyLibraryGuideProps) {
  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="grid grid-cols-2 gap-5 max-w-xl w-full">
        <div className="p-6 rounded-2xl bg-white/[0.02] border border-white/[0.04] flex flex-col">
          <div className="w-11 h-11 rounded-xl bg-blue-500/10 flex items-center justify-center mb-4">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-blue-400">
              <path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
            </svg>
          </div>
          <p className="text-sm font-medium text-slate-200 mb-1.5">添加媒体库</p>
          <p className="text-xs text-slate-500 mb-5 flex-1">自动识别全部文件夹和媒体类型，适合已整理好的目录</p>
          <button onClick={onAddScanPath}
            className="w-full py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-sm font-medium text-white transition-all">
            添加
          </button>
        </div>
        <div className="p-6 rounded-2xl bg-white/[0.02] border border-white/[0.04] flex flex-col">
          <div className="w-11 h-11 rounded-xl bg-white/[0.04] flex items-center justify-center mb-4">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-slate-400">
              <path d="M12 5v14M5 12h14" />
            </svg>
          </div>
          <p className="text-sm font-medium text-slate-200 mb-1.5">添加分类文件夹</p>
          <p className="text-xs text-slate-500 mb-5 flex-1">按电影、电视剧等类型添加，支持多路径合并到一个文件夹</p>
          <button onClick={onAddLibrary}
            className="w-full py-2.5 rounded-xl bg-white/[0.06] hover:bg-white/[0.08] text-sm font-medium text-slate-300 border border-white/[0.06] transition-all">
            添加
          </button>
        </div>
      </div>
    </div>
  );
}
