// 播放页外壳：页头（返回 + 片名 + 季集号）+ 播放器。
//
// 播放页在底栏黑名单里（`ROUTES_WITHOUT_BOTTOM_NAV`），所以页头是页内**唯一**出口。
// 之前不给页头是为了让播放器占满视口，但代价是没有任何文字说明正在播什么，
// 加到主屏（standalone）后连系统返回键都没有，等于死路。
//
// 播放器本身仍然贴边（`padded={false}`），只有页头和它下面的说明区有留白。
"use client";
import { useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";

import { useMobileLibraryTree } from "./MobileLibraryTreeProvider";
import type { VideoInfo } from "@/types";
import {
  findVideoByPath,
  findEpisodeNeighbors,
  videoDisplayName,
  episodeSeasonNumber,
  episodeNumber,
} from "@/lib/mobile/libraryNav";
import { libraryDetailUrl, playUrl } from "@/lib/mobile/mobileRouteUtils";
import MobileShell from "./MobileShell";
import MobileNativePlayer from "./MobileNativePlayer";
import MobileEpisodeSwitcher from "./MobileEpisodeSwitcher";

export interface MobilePlayClientProps {
  path: string;
}

export default function MobilePlayClient({ path }: MobilePlayClientProps) {
  const router = useRouter();
  // 片名要从树里取。树没加载完就先显示文件名，不阻塞播放 ——
  // 播放本身只依赖 path，等一棵整树才起播是本末倒置。
  const { tree, ensureLoaded } = useMobileLibraryTree();
  useEffect(() => { ensureLoaded(); }, [ensureLoaded]);

  const video = findVideoByPath(tree, path);
  const fileName = path.split(/[\\/]/).pop() || "播放";
  const title = video ? videoDisplayName(video) : fileName;

  const seasonNo = episodeSeasonNumber(fileName);
  const episodeNo = episodeNumber(fileName);
  const episodeLabel = seasonNo !== null && episodeNo !== null
    ? `S${String(seasonNo).padStart(2, "0")}E${String(episodeNo).padStart(2, "0")}`
    : "";

  // 从详情页进来的居多，返回回详情；没有 path 时退回媒体库由播放器内部处理
  const onBack = useCallback(() => {
    router.push(libraryDetailUrl(path));
  }, [router, path]);

  const neighbors = findEpisodeNeighbors(tree, path);

  // 切集用 replace 而不是 push：连着看五集不该在历史栈里堆五层，
  // 返回键的语义应该始终是"回到进来时的那个列表/详情"。
  const goTo = useCallback((target: VideoInfo | null) => {
    if (target) router.replace(playUrl(target.file_path));
  }, [router]);

  return (
    <MobileShell
      title={path ? title : "播放"}
      subtitle={episodeLabel || undefined}
      onBack={path ? onBack : undefined}
      padded={false}
    >
      <MobileNativePlayer path={path} />
      {path && neighbors.total > 1 && (
        <div className="px-[var(--m-page-px)] pt-3">
          <MobileEpisodeSwitcher
            index={neighbors.index}
            total={neighbors.total}
            hasPrev={!!neighbors.prev}
            hasNext={!!neighbors.next}
            onPrev={() => goTo(neighbors.prev)}
            onNext={() => goTo(neighbors.next)}
          />
        </div>
      )}
    </MobileShell>
  );
}
