import MobileShell from "@/components/mobile/MobileShell";
import MobileStateView from "@/components/mobile/MobileStateView";
import { parsePathParam } from "@/lib/mobile/mobileRouteUtils";

// 播放页不传 title、不加左右留白：播放器要占满整个视口。
// 底栏由 MobileShell 按路由自动隐藏，这里不需要额外处理。
export default async function MobilePlayPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const path = parsePathParam(await searchParams);

  return (
    <MobileShell padded={false}>
      <MobileStateView
        state={path ? "empty" : "error"}
        emptyText="原生播放正在开发中"
        errorText="缺少视频路径，无法播放"
      />
    </MobileShell>
  );
}
