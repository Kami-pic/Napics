import MobilePlayClient from "@/components/mobile/MobilePlayClient";
import { parsePathParam } from "@/lib/mobile/mobileRouteUtils";

export default async function MobilePlayPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const path = parsePathParam(await searchParams);

  return <MobilePlayClient path={path} />;
}
