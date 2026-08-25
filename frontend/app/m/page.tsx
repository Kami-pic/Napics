import MobileShell from "@/components/mobile/MobileShell";
import MobileDiscoverClient from "@/components/mobile/MobileDiscoverClient";
import { parseDiscoverTab } from "@/lib/mobile/mobileRouteUtils";

// /m 就是发现首页，不做重定向 —— 重定向会多压一条历史记录，返回键立刻变得难以预料。
export default async function MobileDiscoverPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const tab = parseDiscoverTab(await searchParams);

  return (
    <MobileShell title="发现">
      <MobileDiscoverClient initialTab={tab || undefined} />
    </MobileShell>
  );
}
