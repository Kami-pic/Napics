// 搜索词回退链：BT 搜索按「中文名 → 英文名 → 原名 → 去季号」连着试好几个词，
// 这里把试过的词和最终命中的词摊开。
//
// 为什么必须显性化：用户看到「没有结果」时第一个要问的是"你到底拿什么词搜的"。
// 桌面弹窗一直有这个回显，移动端缺了它就只能靠猜。
"use client";
import { buildKeywordChain, type SourceKeywordInfo } from "@/lib/domain/searchKeywords";

export interface MobileKeywordChainProps {
  sourceKeywordInfo: SourceKeywordInfo;
  /** 搜索中不显示：这时候链是不完整的，会一直跳变 */
  searching: boolean;
}

export default function MobileKeywordChain({ sourceKeywordInfo, searching }: MobileKeywordChainProps) {
  if (searching) return null;
  const chain = buildKeywordChain(sourceKeywordInfo);
  if (chain.length === 0) return null;

  return (
    <div
      className="-mx-[var(--m-page-px)] flex items-center gap-1 overflow-x-auto px-[var(--m-page-px)] py-1"
      style={{ scrollbarWidth: "none" }}
      aria-label="搜索词回退链"
    >
      <span className="shrink-0 text-[10px] text-[var(--m-text-dim)]">回退匹配</span>
      {chain.map((item, index) => (
        <span key={item.keyword} className="flex shrink-0 items-center gap-1">
          {index > 0 && <span className="text-[10px] text-[var(--m-text-dim)]" aria-hidden="true">→</span>}
          <span
            className="whitespace-nowrap rounded-[var(--m-radius-sm)] px-1.5 py-0.5 text-[11px] leading-none"
            style={
              item.hit
                ? { background: "var(--m-accent-weak)", color: "var(--m-accent)" }
                : { background: "var(--m-surface)", color: "var(--m-text-dim)" }
            }
            // 命中/未命中不能只靠颜色区分
            title={item.hit ? "命中" : "没有结果"}
          >
            {item.keyword}
            {item.hit && <span className="ml-1" aria-label="命中">✓</span>}
          </span>
        </span>
      ))}
    </div>
  );
}
