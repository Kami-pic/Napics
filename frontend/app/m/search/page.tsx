import MobileShell from "@/components/mobile/MobileShell";
import MobileDiscoverSearchClient from "@/components/mobile/MobileDiscoverSearchClient";
import { parseDiscoverSearchQuery } from "@/lib/mobile/mobileRouteUtils";

// 底栏「搜索」= 按片名找片子（豆瓣搜索）。
// 资源搜索（BT / 网盘）在 /m/resource，只从详情页的「搜索资源」进。
export default async function MobileSearchPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const q = parseDiscoverSearchQuery(await searchParams);

  return (
    <MobileShell title="搜索" subtitle={q || undefined}>
      <MobileDiscoverSearchClient q={q} />
    </MobileShell>
  );
}
