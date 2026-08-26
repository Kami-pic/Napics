import MobileShell from "@/components/mobile/MobileShell";
import MobileSearchClient from "@/components/mobile/MobileSearchClient";
import { parseResourceSearchQuery } from "@/lib/mobile/mobileRouteUtils";

// 资源搜索（BT / 磁力 / 网盘）。只从详情页的「搜索资源」「搜索升级」进来 ——
// 它需要一个明确的目标片子，所以不进底栏。
export default async function MobileResourceSearchPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  // URL 是搜索页的唯一状态来源，规范化后交给客户端组件
  const query = parseResourceSearchQuery(await searchParams);

  return (
    <MobileShell title="搜索资源" subtitle={query.q || undefined}>
      <MobileSearchClient query={query} />
    </MobileShell>
  );
}
