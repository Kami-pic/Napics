// 移动端页面外壳：页头 + 滚动内容区 + 底部导航。
// 底栏是否显示由路由决定（播放页隐藏），页面不用自己判断。
"use client";
import type { ReactNode } from "react";
import { usePathname } from "next/navigation";

import { shouldShowBottomNav } from "@/lib/mobile/mobileRouteUtils";
import MobileBottomNav from "./MobileBottomNav";
import MobilePageHeader from "./MobilePageHeader";

export interface MobileShellProps {
  children: ReactNode;
  /** 省略时不渲染页头（播放页要全屏） */
  title?: string;
  subtitle?: string;
  onBack?: () => void;
  headerRight?: ReactNode;
  /** 内容区左右留白。播放页这类要贴边的传 false */
  padded?: boolean;
}

export default function MobileShell({
  children,
  title,
  subtitle,
  onBack,
  headerRight,
  padded = true,
}: MobileShellProps) {
  const pathname = usePathname();
  const withNav = shouldShowBottomNav(pathname);

  return (
    <div className="flex min-h-dvh flex-col bg-[var(--m-bg)] text-[var(--m-text)]">
      {title !== undefined && (
        <MobilePageHeader title={title} subtitle={subtitle} onBack={onBack} right={headerRight} />
      )}
      <main
        className="flex-1"
        style={{
          paddingLeft: padded ? "var(--m-page-px)" : undefined,
          paddingRight: padded ? "var(--m-page-px)" : undefined,
          // 有底栏时必须留出高度，否则列表最后一项被压在底栏下面点不到
          paddingBottom: withNav ? "var(--m-page-pb)" : "var(--m-safe-bottom)",
        }}
      >
        {children}
      </main>
      {withNav && <MobileBottomNav />}
    </div>
  );
}
