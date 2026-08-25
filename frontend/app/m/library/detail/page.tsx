import MobileShell from "@/components/mobile/MobileShell";
import MobileStateView from "@/components/mobile/MobileStateView";
import { parsePathParam } from "@/lib/mobile/mobileRouteUtils";

export default async function MobileLibraryDetailPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const path = parsePathParam(await searchParams);

  return (
    <MobileShell title="详情" subtitle={path || undefined}>
      <MobileStateView
        state={path ? "empty" : "error"}
        emptyText="视频详情正在开发中"
        errorText="缺少视频路径，无法打开详情"
      />
    </MobileShell>
  );
}
