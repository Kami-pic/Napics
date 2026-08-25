import type { Metadata } from "next";

import MobileProviders from "@/components/mobile/MobileProviders";

export const metadata: Metadata = {
  title: "Napics 移动版",
};

// 保持 Server Component：Provider 自己带 "use client"，
// 这样根 app/layout.tsx 不需要任何改动，桌面 / 与 /manage 不受影响。
export default function MobileLayout({ children }: { children: React.ReactNode }) {
  return <MobileProviders>{children}</MobileProviders>;
}
