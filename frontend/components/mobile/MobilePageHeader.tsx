// 移动端页头：返回键 + 标题 + 右侧操作位
"use client";
import type { ReactNode } from "react";

export interface MobilePageHeaderProps {
  title: string;
  /** 副标题，如剧名下的季名；省略时不占位 */
  subtitle?: string;
  /** 传了才渲染返回键。调用方必须自带 fallback 目标，不能只调 router.back() */
  onBack?: () => void;
  right?: ReactNode;
}

export default function MobilePageHeader({ title, subtitle, onBack, right }: MobilePageHeaderProps) {
  return (
    <header
      className="sticky top-0 z-20 flex items-center gap-2 border-b bg-[var(--m-bg)]/95 backdrop-blur"
      style={{
        minHeight: "var(--m-header-h)",
        paddingTop: "var(--m-safe-top)",
        paddingLeft: "var(--m-page-px)",
        paddingRight: "var(--m-page-px)",
        borderColor: "var(--m-border)",
      }}
    >
      {onBack && (
        <button
          type="button"
          onClick={onBack}
          aria-label="返回"
          className="-ml-2 flex items-center justify-center rounded-lg text-[var(--m-text-muted)] active:bg-[var(--m-surface-raised)]"
          style={{ minWidth: "var(--m-touch-min)", minHeight: "var(--m-touch-min)" }}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="M15 18l-6-6 6-6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      )}
      <div className="min-w-0 flex-1 py-2">
        <h1 className="truncate text-[15px] font-semibold text-[var(--m-text)]">{title}</h1>
        {subtitle && (
          <p className="truncate text-xs text-[var(--m-text-dim)]">{subtitle}</p>
        )}
      </div>
      {right && <div className="flex flex-shrink-0 items-center gap-1">{right}</div>}
    </header>
  );
}
