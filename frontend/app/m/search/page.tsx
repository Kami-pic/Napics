import MobileShell from "@/components/mobile/MobileShell";
import MobileSearchClient from "@/components/mobile/MobileSearchClient";
import { parseSearchQuery } from "@/lib/mobile/mobileRouteUtils";

export default async function MobileSearchPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  // URL 是搜索页的唯一状态来源，规范化后交给客户端组件
  const query = parseSearchQuery(await searchParams);

  return (
    <MobileShell title="搜索" subtitle={query.q || undefined}>
      <MobileSearchClient query={query} />
    </MobileShell>
  );
}
