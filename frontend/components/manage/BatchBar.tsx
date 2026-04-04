// 底部批量操作悬浮栏
"use client";

interface BatchBarProps {
  count: number;
  onMove: () => void;
  onDelete: () => void;
  onCancel: () => void;
}

export default function BatchBar({ count, onMove, onDelete, onCancel }: BatchBarProps) {
  if (count === 0) return null;
  return (
    <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-50">
      <div className="bg-blue-600 backdrop-blur-2xl border border-blue-400/30 px-6 py-3 rounded-2xl flex items-center gap-6 shadow-[0_15px_40px_rgba(37,99,235,0.4)]">
        <div className="flex flex-col">
          <span className="text-[9px] font-black uppercase tracking-widest text-blue-200 leading-none mb-0.5">已选中</span>
          <span className="text-xl font-black text-white leading-none">{count}</span>
        </div>
        <div className="w-px h-6 bg-blue-400/30"></div>
        <button onClick={onMove} className="bg-white/10 hover:bg-white/20 text-white px-4 py-2 rounded-xl text-xs font-black transition-all border border-white/20">批量移动</button>
        <button onClick={onDelete} className="bg-red-500/80 hover:bg-red-600 text-white px-4 py-2 rounded-xl text-xs font-black transition-all shadow-xl">物理删除</button>
        <button onClick={onCancel} className="text-white/60 hover:text-white px-3 py-1 text-xs font-bold">取消</button>
      </div>
    </div>
  );
}
