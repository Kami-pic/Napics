// 网盘结果视图。
// P0 只展示 + 复制（链接和提取码一起）+ 外部打开，界面上不出现任何
// 暗示"能转存 / 能跟踪任务"的文案 —— 那是 P1 的事。
"use client";
import type { PanResult } from "@/types";

import MobileStateView from "./MobileStateView";
import MobilePanResultItem from "./MobilePanResultItem";
import MobileSourceStatusRow, { type MobileSourceStatusItem } from "./MobileSourceStatusRow";

export interface MobilePanResultsProps {
  results: PanResult[];
  searching: boolean;
  error: string;
  hasQuery: boolean;
  sources: MobileSourceStatusItem[];
  onCopy: (result: PanResult) => void;
  onOpen: (result: PanResult) => void;
  onRetry: () => void;
}

export default function MobilePanResults({
  results, searching, error, hasQuery, sources, onCopy, onOpen, onRetry,
}: MobilePanResultsProps) {
  const state = error && results.length === 0
    ? "error"
    : searching && results.length === 0
      ? "loading"
      : results.length === 0
        ? "empty"
        : "ready";

  return (
    <div className="flex flex-col gap-3 pt-3">
      <MobileSourceStatusRow items={sources} />

      <MobileStateView
        state={state}
        loadingText="正在搜索网盘资源…"
        emptyText={hasQuery ? "没搜到网盘资源" : "输入关键词开始搜索"}
        errorText={error}
        onRetry={onRetry}
      >
        <>
          <p className="pb-1 text-[11px] text-[var(--m-text-dim)]">
            网盘资源复制链接后到网盘 App 里保存，Napics 暂不代为转存。
          </p>
          <ul className="flex flex-col gap-2">
            {results.map(result => (
              <MobilePanResultItem
                key={result.share_url || result.title}
                result={result}
                onCopy={onCopy}
                onOpen={onOpen}
              />
            ))}
          </ul>
        </>
      </MobileStateView>
    </div>
  );
}
