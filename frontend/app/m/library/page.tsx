import MobileLibraryClient from "@/components/mobile/MobileLibraryClient";
import { parsePathParam } from "@/lib/mobile/mobileRouteUtils";

// Server Component：只负责读异步 searchParams 并规范化，具体交互在客户端组件里。
export default async function MobileLibraryPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const path = parsePathParam(await searchParams);

  return <MobileLibraryClient path={path} />;
}
