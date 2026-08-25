import Link from "next/link";

import MobileShell from "@/components/mobile/MobileShell";
import { MOBILE_ROUTES } from "@/lib/mobile/mobileRouteUtils";

// /m 直接渲染发现首页，不做重定向 —— 重定向会多压一条历史记录，
// 返回键的行为立刻变得难以预料。发现功能本身在 Phase 3 落地，
// 在那之前这里渲染真正可用的入口，而不是一句"未实现"。
const ENTRIES = [
  { href: MOBILE_ROUTES.library, title: "媒体库", desc: "浏览已入库的电影和剧集" },
  { href: MOBILE_ROUTES.search, title: "搜索资源", desc: "搜 BT / 磁力与网盘资源" },
  { href: MOBILE_ROUTES.downloads, title: "下载任务", desc: "查看进度与入库状态" },
];

export default function MobileDiscoverPage() {
  return (
    <MobileShell title="Napics">
      <div className="flex flex-col gap-3 pt-4">
        {ENTRIES.map(entry => (
          <Link
            key={entry.href}
            href={entry.href}
            className="flex flex-col gap-1 rounded-[var(--m-radius)] border p-4 active:bg-[var(--m-surface-raised)]"
            style={{
              minHeight: "var(--m-touch-min)",
              background: "var(--m-surface)",
              borderColor: "var(--m-border)",
            }}
          >
            <span className="text-sm font-medium text-[var(--m-text)]">{entry.title}</span>
            <span className="text-xs text-[var(--m-text-dim)]">{entry.desc}</span>
          </Link>
        ))}
        <p className="px-1 pt-2 text-xs text-[var(--m-text-dim)]">
          发现推荐正在开发中，稍后这里会显示榜单。
        </p>
      </div>
    </MobileShell>
  );
}
