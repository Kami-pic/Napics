// 移动端底部主导航：四个 Tab
"use client";
import { usePathname, useRouter } from "next/navigation";

import {
  MOBILE_NAV_ITEMS,
  activeNavKey,
  type MobileNavKey,
} from "@/lib/mobile/mobileRouteUtils";

/** 每个 Tab 的图标。单独放这里，避免路由常量文件被迫依赖 JSX */
const NAV_ICONS: Record<MobileNavKey, string> = {
  library: "M4 6h16M4 12h16M4 18h10",
  discover: "M12 3l2.6 6.1L21 10l-5 4.2L17.5 21 12 17.6 6.5 21 8 14.2 3 10l6.4-.9z",
  search: "M11 4a7 7 0 100 14 7 7 0 000-14zM20 20l-4.2-4.2",
  downloads: "M12 4v10m0 0l-3.5-3.5M12 14l3.5-3.5M5 19h14",
};

export default function MobileBottomNav() {
  const pathname = usePathname();
  const router = useRouter();
  const active = activeNavKey(pathname);

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-30 flex border-t bg-[var(--m-bg)]/95 backdrop-blur"
      style={{
        height: "calc(var(--m-nav-h) + var(--m-safe-bottom))",
        paddingBottom: "var(--m-safe-bottom)",
        borderColor: "var(--m-border)",
      }}
      aria-label="主导航"
    >
      {MOBILE_NAV_ITEMS.map(item => {
        const isActive = active === item.key;
        return (
          <button
            key={item.key}
            type="button"
            // 主 Tab 用 replace：push 会让返回键在四个 Tab 之间来回循环，退不出去。
            // 目标是不带任何 query 的根路由，所以从下钻页点它就回到该 Tab 的首屏。
            //
            // 已经在这个 Tab 的首屏时 replace 到同一个 URL 不会有任何变化，
            // 这时按 iOS tab bar 的惯例回到顶部 —— 否则用户点了完全没有反馈。
            onClick={() => {
              if (isActive) window.scrollTo({ top: 0, behavior: "smooth" });
              router.replace(item.route);
            }}
            aria-current={isActive ? "page" : undefined}
            className="flex flex-1 flex-col items-center justify-center gap-0.5 active:bg-[var(--m-surface-raised)]"
            style={{
              minHeight: "var(--m-touch-min)",
              color: isActive ? "var(--m-accent)" : "var(--m-text-dim)",
            }}
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
              <path d={NAV_ICONS[item.key]} strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <span className="text-[11px] leading-none">{item.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
