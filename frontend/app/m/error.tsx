"use client";
import MobileErrorFallback from "@/components/mobile/MobileErrorFallback";

export default function MobileError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return <MobileErrorFallback error={error} reset={reset} />;
}
