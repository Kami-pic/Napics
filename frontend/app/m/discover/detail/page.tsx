import MobileDiscoverDetailClient from "@/components/mobile/MobileDiscoverDetailClient";
import { parseDiscoverDetailQuery } from "@/lib/mobile/mobileRouteUtils";

export default async function MobileDiscoverDetailPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  // URL 是这一页的唯一状态来源，规范化后交给客户端组件
  const query = parseDiscoverDetailQuery(await searchParams);

  return <MobileDiscoverDetailClient query={query} />;
}
