import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import MobileVersionHint from "@/components/layout/MobileVersionHint";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Napics Media Manager",
  description: "Napics 影视媒体库管理工具",
  icons: {
    icon: "/favicon.svg",
  },
};

// 移动端需要显式声明：Next 默认只给 width/initial-scale，
// viewportFit 是刘海屏安全区（配合 env(safe-area-inset-*)）所必需
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};


export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <body className="min-h-full flex flex-col">
        {children}
        {/* 窄屏提示条。它自己判断路由（/m 与 /login 不显示），
            所以放在这里不会影响移动版和登录页 */}
        <MobileVersionHint />
      </body>
    </html>
  );
}
