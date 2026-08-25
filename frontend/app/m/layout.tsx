import type { Metadata, Viewport } from "next";

import MobileProviders from "@/components/mobile/MobileProviders";
import MobileGestureLock from "@/components/mobile/MobileGestureLock";

export const metadata: Metadata = {
  title: "Napics 移动版",
};

// 只覆盖 /m 段的 viewport，桌面继承根 layout 的那份。
//
// maximumScale=1 + userScalable=false 是给 Android 和 PWA standalone 用的；
// **iOS Safari 会故意忽略这两个值**（无障碍考虑），所以那边还要靠
// MobileGestureLock 拦 gesturestart，两者缺一不可。
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: "cover",
  themeColor: "#0f0f0f",
};

// 保持 Server Component：Provider 自己带 "use client"，
// 这样根 app/layout.tsx 不需要任何改动，桌面 / 与 /manage 不受影响。
export default function MobileLayout({ children }: { children: React.ReactNode }) {
  return (
    <MobileProviders>
      <MobileGestureLock />
      <div className="m-app">{children}</div>
    </MobileProviders>
  );
}
