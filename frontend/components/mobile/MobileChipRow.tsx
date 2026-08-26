// 横向滚动的胶囊单选条。榜单 Tab 与下载任务筛选共用一份。
//
// 两处原本各写了一遍同样的胶囊样式、同样的横向滚动容器和同样的 36px 触控高度，
// 差别只有无障碍语义（tab vs radio）。
//
// 注意：横向滚动容器**不能**加 touch-action 限制，它会按祖先链求交，
// 把整棵子树的拖动一起锁死（Phase 2 踩过）。
"use client";
import { useEffect, useRef } from "react";

export interface MobileChipItem {
  key: string;
  label: string;
  /** 未选中时也要引起注意（如"需处理"有内容）。为 false 时用次要文字色 */
  emphasize?: boolean;
}

export interface MobileChipRowProps {
  items: readonly MobileChipItem[];
  activeKey: string;
  onChange: (key: string) => void;
  /** 读屏要能说出这一组是什么 */
  ariaLabel: string;
  /**
   * `tab` = 切换的是"看哪一批内容"（tablist/tab + aria-selected）；
   * `radio` = 在同一批内容上做互斥筛选（radiogroup/radio + aria-checked）。
   */
  semantics: "tab" | "radio";
}

export default function MobileChipRow({
  items, activeKey, onChange, ariaLabel, semantics,
}: MobileChipRowProps) {
  const activeRef = useRef<HTMLButtonElement>(null);
  const isTab = semantics === "tab";

  // 从详情返回时选中项可能在屏幕外，滚进可视区，否则用户以为选择被重置了。
  // jsdom 没有 scrollIntoView，可选调用避免测试环境炸掉。
  useEffect(() => {
    activeRef.current?.scrollIntoView?.({ block: "nearest", inline: "center" });
  }, [activeKey]);

  return (
    <div
      role={isTab ? "tablist" : "radiogroup"}
      aria-label={ariaLabel}
      className="-mx-[var(--m-page-px)] flex gap-2 overflow-x-auto px-[var(--m-page-px)]"
      style={{ scrollbarWidth: "none" }}
    >
      {items.map(item => {
        const active = item.key === activeKey;
        return (
          <button
            key={item.key}
            ref={active ? activeRef : undefined}
            type="button"
            role={isTab ? "tab" : "radio"}
            aria-selected={isTab ? active : undefined}
            aria-checked={isTab ? undefined : active}
            onClick={() => onChange(item.key)}
            className="shrink-0 whitespace-nowrap rounded-[var(--m-radius-pill)] px-3 text-[13px]"
            style={{
              minHeight: "var(--m-chip-h)",
              background: active ? "var(--m-accent-weak)" : "var(--m-surface)",
              border: `1px solid ${active ? "var(--m-accent)" : "var(--m-border)"}`,
              color: active
                ? "var(--m-text)"
                : item.emphasize ? "var(--m-warning)" : "var(--m-text-dim)",
            }}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}
