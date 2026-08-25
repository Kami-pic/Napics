import MobileShell from "@/components/mobile/MobileShell";
import MobileStateView from "@/components/mobile/MobileStateView";
import { parseSearchQuery } from "@/lib/mobile/mobileRouteUtils";

export default async function MobileSearchPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  // URL 是搜索页的唯一状态来源，规范化后再交给客户端组件
  const query = parseSearchQuery(await searchParams);

  return (
    <MobileShell title="搜索" subtitle={query.q || undefined}>
      <MobileStateView
        state="empty"
        emptyText={query.q ? `搜索功能正在开发中（${query.q}）` : "搜索功能正在开发中"}
      />
    </MobileShell>
  );
}
