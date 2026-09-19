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
  /** 点某个回退词：用它直接重搜。让用户能一键跳到"作品名"那个更宽的词。 */
  onPick: (keyword: string) => void;
}

export default function MobileKeywordChain({ sourceKeywordInfo, searching, onPick }: MobileKeywordChainProps) {
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
          <button
            type="button"
            onClick={() => onPick(item.keyword)}
            className="whitespace-nowrap rounded-[var(--m-radius-sm)] px-1.5 py-0.5 text-[11px] leading-none"
            style={
              item.hit
                ? { background: "var(--m-accent-weak)", color: "var(--m-accent)" }
                : { background: "var(--m-surface)", color: "var(--m-text-dim)" }
            }
            // 命中/未命中不能只靠颜色区分；点击提示让用户知道这是可点的
            title={item.hit ? "命中，点击用这个词重搜" : "没有结果，点击用这个词重搜"}
          >
            {item.keyword}
            {item.hit && <span className="ml-1" aria-label="命中">✓</span>}
          </button>
        </span>
      ))}
    </div>
  );
}
