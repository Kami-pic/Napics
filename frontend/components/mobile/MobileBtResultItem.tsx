// 单条 BT / 磁力结果。桌面 BtResultCard 的 JSX 不搬，只共用数据形状。
"use client";
import type { EnhancedSearchResult } from "@/types";

export interface MobileBtResultItemProps {
  result: EnhancedSearchResult;
  /** 该结果正在提交中 */
  submitting: boolean;
  /** 任意一条正在提交时禁用其余按钮，避免连点提交多次 */
  disabled: boolean;
  onDownload: (result: EnhancedSearchResult) => void;
}

/** 没有做种数信息的源（直搜站）显示 0 会让人误判成死种，这里区别对待 */
function seedersText(result: EnhancedSearchResult): string {
  const noSeederInfo = result.seeders === 0 && result.size_gb === 0;
  if (noSeederInfo) return "磁力链接";
  return `${result.seeders} 做种`;
}

export default function MobileBtResultItem({
  result, submitting, disabled, onDownload,
}: MobileBtResultItemProps) {
  const quality = result.quality?.display || result.quality_tag || "";

  return (
    <li
      className="flex flex-col gap-2 rounded-[var(--m-radius)] border p-3"
      style={{ background: "var(--m-surface)", borderColor: "var(--m-border)" }}
    >
      <p className="break-words text-sm text-[var(--m-text)]">{result.title}</p>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-[var(--m-text-dim)]">
        {result.size_gb > 0 && <span>{result.size_gb.toFixed(2)} GB</span>}
        <span>{seedersText(result)}</span>
        {result.indexer && <span className="truncate">{result.indexer}</span>}
        {quality && <span style={{ color: "var(--m-text-muted)" }}>{quality}</span>}
        {result.quality?.has_chinese_sub && (
          <span style={{ color: "var(--m-success)" }}>中字</span>
        )}
      </div>

      <button
        type="button"
        onClick={() => onDownload(result)}
        disabled={disabled}
        className="rounded-[var(--m-radius)] text-sm disabled:opacity-50"
        style={{
          minHeight: "var(--m-touch-min)",
          background: "var(--m-accent)",
          color: "var(--m-on-accent)",
        }}
      >
        {submitting ? "提交中…" : "下载到本地"}
      </button>
    </li>
  );
}
