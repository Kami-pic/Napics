// 网盘搜索结果面板 — 从 SearchModal.tsx 拆分
"use client";

import { useState, useMemo } from "react";
import type { PanResult, PanSourceStatus } from "@/types";
import { PanFilterState, applyPanFilters, PAN_TYPE_COLORS, PAN_TYPE_LABELS } from "./PanFilterBar";

// ── 网盘搜索结果视图（纯展示，筛选器已提到外层）──
export default function PanResultsView({
  searching, groups, total, sourceStatuses, keyword, filters, onRetry, onTransfer,
}: {
  searching: boolean;
  groups: Record<string, PanResult[]>;
  total: number;
  sourceStatuses: PanSourceStatus[];
  keyword: string;
  filters: PanFilterState;
  onRetry: () => void;
  onTransfer: (r: PanResult) => void;
}) {
  // 展平 + 筛选 + 重新分组
  const allResults = useMemo(() => {
    const all: PanResult[] = [];
    for (const items of Object.values(groups)) all.push(...items);
    return all;
  }, [groups]);

  const filteredResults = useMemo(() => applyPanFilters(allResults, filters), [allResults, filters]);

  const filteredGroups = useMemo(() => {
    const g: Record<string, PanResult[]> = {};
    for (const r of filteredResults) {
      if (!g[r.pan_type]) g[r.pan_type] = [];
      g[r.pan_type].push(r);
    }
    const order = ["quark", "aliyun", "pan115", "pikpak", "baidu"];
    const ordered: Record<string, PanResult[]> = {};
    for (const pt of order) { if (g[pt]) ordered[pt] = g[pt]; }
    for (const pt of Object.keys(g)) { if (!ordered[pt]) ordered[pt] = g[pt]; }
    return ordered;
  }, [filteredResults]);

  const isFiltered = filters.panType || filters.source || filters.resolution || filters.completeOnly;

  if (searching) {
    return (
      <div className="flex flex-col items-center py-16">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-500 mb-3" />
        <p className="text-[13px] text-slate-500">搜索网盘资源...</p>
      </div>
    );
  }

  if (total === 0) {
    return (
      <div className="text-center py-10">
        <p className="text-xs text-slate-600 mb-3">未搜到网盘资源</p>
        <button onClick={onRetry} className="text-xs text-emerald-400 hover:text-emerald-300">重试</button>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between mb-2">
        <p className="text-[11px] text-slate-500">
          共 {filteredResults.length} 条{isFiltered ? `（筛选自 ${total} 条）` : ""}
        </p>
      </div>

      {Object.entries(filteredGroups).map(([panType, items]) => (
        <div key={panType} className="border border-white/[0.04] rounded-xl overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-2.5 bg-white/[0.02]">
            <span className={`text-[11px] px-2 py-0.5 rounded font-bold ${PAN_TYPE_COLORS[panType] || PAN_TYPE_COLORS.unknown}`}>
              {PAN_TYPE_LABELS[panType] || panType}
            </span>
            <span className="text-[10px] text-slate-500">{items.length} 条</span>
          </div>
          <div className="p-2 space-y-1.5">
            {items.map((r, i) => (
              <PanResultCard key={i} result={r} onTransfer={onTransfer} />
            ))}
          </div>
        </div>
      ))}

      {filteredResults.length === 0 && isFiltered && (
        <div className="text-center py-8">
          <p className="text-xs text-slate-600 mb-2">当前筛选条件无匹配结果</p>
        </div>
      )}
    </div>
  );
}

// ── 单条网盘结果卡片（内嵌子组件，仅本文件使用）──
function PanResultCard({ result: r, onTransfer }: { result: PanResult; onTransfer: (r: PanResult) => void }) {
  const [copied, setCopied] = useState(false);
  const [transferring, setTransferring] = useState(false);

  const handleTransfer = async () => {
    if (r.pan_type === "quark") {
      // 夸克 → 调用后端自动转存
      setTransferring(true);
      onTransfer(r);
      setTransferring(false);
    } else {
      // 其他网盘 → 打开分享页 + 复制提取码
      if (r.password) {
        navigator.clipboard.writeText(r.password).then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 2000);
        }).catch(() => {});
      }
      window.open(r.share_url, "_blank");
    }
  };

  const btnLabel = r.pan_type === "quark"
    ? (transferring ? "转存中..." : "转存")
    : (r.password ? "打开(复制码)" : "打开");

  return (
    <div className="bg-[#0f0f0f] rounded-lg border border-white/[0.04] px-4 py-2.5 flex items-center gap-3 hover:border-white/[0.08] transition-colors">
      <div className="flex-1 min-w-0">
        <p className="text-[12px] text-slate-200 truncate" title={r.title}>
          {r.clean_title || r.title}
        </p>
        <div className="flex items-center gap-1.5 mt-1.5">
          <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold ${PAN_TYPE_COLORS[r.pan_type] || PAN_TYPE_COLORS.unknown}`}>
            {PAN_TYPE_LABELS[r.pan_type] || r.pan_type}
          </span>
          {r.resolution && r.resolution !== "unknown" && (
            <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold ${
              r.resolution === "2160p" ? "bg-yellow-500/20 text-yellow-400" :
              r.resolution === "1080p" ? "bg-blue-500/15 text-blue-400" :
              "bg-white/[0.06] text-slate-500"
            }`}>{r.resolution}</span>
          )}
          {!r.is_complete && <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/10 text-red-400">碎片</span>}
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/[0.06] text-slate-400">{r.source}</span>
          {r.password && (
            <span className="text-[10px] text-slate-500">
              码: {r.password} {copied && <span className="text-green-400">✓已复制</span>}
            </span>
          )}
        </div>
      </div>
      <div className="flex gap-1.5 flex-shrink-0">
        {r.pan_type === "quark" && (
          <button onClick={handleTransfer} disabled={transferring}
            className="px-3 py-1.5 rounded-lg text-[11px] font-bold bg-emerald-600 hover:bg-emerald-500 text-white transition-colors disabled:opacity-50">
            {transferring ? "..." : "转存"}
          </button>
        )}
        <button onClick={() => {
          if (r.password) {
            navigator.clipboard.writeText(r.password).then(() => {
              setCopied(true);
              setTimeout(() => setCopied(false), 2000);
            }).catch(() => {});
          }
          window.open(r.share_url, "_blank");
        }}
          className="px-3 py-1.5 rounded-lg text-[11px] font-bold bg-white/[0.06] text-slate-400 hover:text-white hover:bg-white/[0.10] transition-colors">
          打开
        </button>
      </div>
    </div>
  );
}
