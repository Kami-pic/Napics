// BT / 磁力结果视图：保存路径 + 源状态 + 结果列表。
// 和网盘结果从一开始就是两套视图，不做成一个组件里塞两种交互。
"use client";
import type { EnhancedSearchResult } from "@/types";

import MobileStateView from "./MobileStateView";
import MobileBtResultItem from "./MobileBtResultItem";
import MobileSavePathField from "./MobileSavePathField";
import MobileSourceStatusRow, { type MobileSourceStatusItem } from "./MobileSourceStatusRow";

export interface MobileBtResultsProps {
  results: EnhancedSearchResult[];
  searching: boolean;
  error: string;
  /** 有搜索词才谈得上"没搜到" */
  hasQuery: boolean;
  sources: MobileSourceStatusItem[];
  savePath: string;
  onSavePathChange: (path: string) => void;
  defaultSavePath: string;
  downloadingUrl: string | null;
  onDownload: (result: EnhancedSearchResult) => void;
  onRetry: () => void;
}

export default function MobileBtResults({
  results, searching, error, hasQuery, sources,
  savePath, onSavePathChange, defaultSavePath,
  downloadingUrl, onDownload, onRetry,
}: MobileBtResultsProps) {
  const state = error && results.length === 0
    ? "error"
    : searching && results.length === 0
      ? "loading"
      : results.length === 0
        ? "empty"
        : "ready";

  return (
    <div className="flex flex-col gap-3 pt-3">
      {/* 保存路径放在结果上方：提交前必须能看到会存到哪里 */}
      <MobileSavePathField
        value={savePath}
        onChange={onSavePathChange}
        defaultPath={defaultSavePath}
      />

      <MobileSourceStatusRow items={sources} />

      <MobileStateView
        state={state}
        loadingText="正在搜索各个源…"
        emptyText={hasQuery ? "没搜到结果，换个关键词试试" : "输入关键词开始搜索"}
        errorText={error}
        onRetry={onRetry}
      >
        <ul className="flex flex-col gap-2">
          {results.map(result => (
            <MobileBtResultItem
              key={result.download_url || result.title}
              result={result}
              submitting={downloadingUrl === result.download_url}
              disabled={downloadingUrl !== null}
              onDownload={onDownload}
            />
          ))}
        </ul>
      </MobileStateView>

      {/* 边搜边出结果时，列表下方要说明还没搜完 */}
      {searching && results.length > 0 && (
        <p className="py-2 text-center text-xs text-[var(--m-text-dim)]">还在搜其他源…</p>
      )}
    </div>
  );
}
