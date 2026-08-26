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
  /**
   * 受这一组控制的内容区 id（`tab` 语义下必填才完整）。
   * `role="tab"` 不给 `aria-controls`，读屏就说不出这个 tab 管的是哪块内容。
   */
  controlsId?: string;
}

export default function MobileChipRow({
  items, activeKey, onChange, ariaLabel, semantics, controlsId,
}: MobileChipRowProps) {
  const activeRef = useRef<HTMLButtonElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const isTab = semantics === "tab";

  // 从详情返回时选中项可能在屏幕外，滚进可视区，否则用户以为选择被重置了。
  // jsdom 没有 scrollIntoView，可选调用避免测试环境炸掉。
  useEffect(() => {
    activeRef.current?.scrollIntoView?.({ block: "nearest", inline: "center" });
  }, [activeKey]);

  /** tablist 与 radiogroup 都要求方向键在组内移动选择（roving tabindex）。
   *  只有选中项可 Tab 聚焦，左右键换选中项 —— 否则键盘用户要按 8 次 Tab 才能走完榜单。 */
  const onKeyDown = (event: React.KeyboardEvent) => {
    const delta = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (!delta) return;
    event.preventDefault();
    const current = items.findIndex(item => item.key === activeKey);
    if (current < 0) return;
    // 环绕：到头再按一次回到另一端，和原生 tablist 一致
    const next = (current + delta + items.length) % items.length;
    onChange(items[next].key);
    // 焦点跟着选中项走，不然后续方向键会从旧位置继续
    requestAnimationFrame(() => {
      containerRef.current
        ?.querySelectorAll<HTMLButtonElement>("button")
        [next]?.focus();
    });
  };

  return (
    <div
      ref={containerRef}
      role={isTab ? "tablist" : "radiogroup"}
      aria-label={ariaLabel}
      onKeyDown={onKeyDown}
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
            aria-controls={isTab ? controlsId : undefined}
            // roving tabindex：组内只有一个可 Tab 落点
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(item.key)}
            // 视觉高度 36px，用负外边距的伪元素把命中区撑到 44px 的触控下限。
            // 只在纵向扩，不会盖住横向相邻的 chip。
            className="relative shrink-0 whitespace-nowrap rounded-[var(--m-radius-pill)] px-3 text-[13px] before:absolute before:inset-x-0 before:-inset-y-1 before:content-['']"
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
