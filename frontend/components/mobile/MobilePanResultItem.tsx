// 单条网盘结果。
//
// P0 只做展示 / 复制 / 外部打开，不承诺转存和任务跟踪。
// 复制必须**一次带上链接和提取码** —— 桌面实现只复制 password 再 window.open，
// 单独复制链接会把提取码丢掉，换个 App 打开就进不去了。
"use client";
import type { PanResult } from "@/types";

/** 网盘类型的中文名。只给语义文案，不给 Tailwind class */
const PAN_TYPE_LABEL: Record<PanResult["pan_type"], string> = {
  quark: "夸克",
  aliyun: "阿里云盘",
  baidu: "百度网盘",
  pan115: "115",
  pikpak: "PikPak",
  unknown: "网盘",
};

export interface MobilePanResultItemProps {
  result: PanResult;
  onCopy: (result: PanResult) => void;
  onOpen: (result: PanResult) => void;
}

export default function MobilePanResultItem({ result, onCopy, onOpen }: MobilePanResultItemProps) {
  return (
    <li
      className="flex flex-col gap-2 rounded-[var(--m-radius)] border p-3"
      style={{ background: "var(--m-surface)", borderColor: "var(--m-border)" }}
    >
      <p className="break-words text-sm text-[var(--m-text)]">
        {result.clean_title || result.title}
      </p>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-[var(--m-text-dim)]">
        <span style={{ color: "var(--m-text-muted)" }}>{PAN_TYPE_LABEL[result.pan_type]}</span>
        {result.resolution && <span>{result.resolution}</span>}
        {result.size_gb > 0 && <span>{result.size_gb.toFixed(2)} GB</span>}
        {result.file_count > 0 && <span>{result.file_count} 个文件</span>}
        {result.password && <span>提取码 {result.password}</span>}
        {!result.alive && <span style={{ color: "var(--m-warning)" }}>链接可能已失效</span>}
      </div>

      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => onCopy(result)}
          className="flex-1 rounded-[var(--m-radius)] text-sm"
          style={{
            minHeight: "var(--m-touch-min)",
            background: "var(--m-surface-raised)",
            color: "var(--m-text)",
          }}
        >
          {result.password ? "复制链接和提取码" : "复制链接"}
        </button>
        <button
          type="button"
          onClick={() => onOpen(result)}
          className="flex-1 rounded-[var(--m-radius)] text-sm"
          style={{
            minHeight: "var(--m-touch-min)",
            background: "var(--m-surface-raised)",
            color: "var(--m-text)",
          }}
        >
          用其他应用打开
        </button>
      </div>
    </li>
  );
}

/** 复制到剪贴板的文本：链接 + 提取码一次给全 */
export function panShareText(result: PanResult): string {
  return result.password
    ? `${result.share_url} 提取码：${result.password}`
    : result.share_url;
}
