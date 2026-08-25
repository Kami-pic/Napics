import MobileShell from "@/components/mobile/MobileShell";
import MobileStateView from "@/components/mobile/MobileStateView";
import { parsePathParam } from "@/lib/mobile/mobileRouteUtils";

// Server Component：只负责读异步 searchParams 并规范化，
// 具体交互交给 Client Component（Phase 2 落地 useMobileLibrary 后接上）。
export default async function MobileLibraryPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const path = parsePathParam(await searchParams);

  return (
    <MobileShell title={path ? "目录" : "媒体库"} subtitle={path || undefined}>
      <MobileStateView state="empty" emptyText="媒体库浏览正在开发中" />
    </MobileShell>
  );
}
