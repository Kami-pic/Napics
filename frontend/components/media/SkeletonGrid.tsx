// 发现页骨骼屏加载占位
"use client";

export interface SkeletonGridProps {
  colCount: number;
  rows: number;
}

export default function SkeletonGrid({ colCount, rows }: SkeletonGridProps) {
  const count = colCount * rows;
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-5">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="rounded-xl overflow-hidden bg-[#1a1a1a] border border-white/[0.06] animate-pulse">
          <div className="aspect-[2/3] bg-[#222]" />
        </div>
      ))}
    </div>
  );
}
