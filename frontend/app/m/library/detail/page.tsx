import MobileLibraryDetailClient from "@/components/mobile/MobileLibraryDetailClient";
import { parsePathParam } from "@/lib/mobile/mobileRouteUtils";

export default async function MobileLibraryDetailPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const path = parsePathParam(await searchParams);

  return <MobileLibraryDetailClient path={path} />;
}
