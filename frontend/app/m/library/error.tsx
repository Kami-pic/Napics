"use client";
import MobileErrorFallback from "@/components/mobile/MobileErrorFallback";

// 媒体库段单独一层边界：树加载失败和路径解析失败最常发生在这里，
// 用段级边界能保住底部导航所在的外层不被一起卸掉。
export default function MobileLibraryError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return <MobileErrorFallback error={error} reset={reset} title="媒体库打不开" />;
}
