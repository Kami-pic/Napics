// 媒体库分级浏览的客户端壳：状态分派 + 路由跳转。
// 显示什么由 libraryNav 的纯函数决定，这里不写矩阵逻辑。
"use client";
import { useCallback } from "react";
import { useRouter } from "next/navigation";

import type { FolderNode, VideoInfo } from "@/types";
import { useMobileLibrary } from "@/hooks/useMobileLibrary";
import { useMobileLibraryTree } from "./MobileLibraryTreeProvider";
import { folderTarget, videoTarget, findParentPath } from "@/lib/mobile/libraryNav";
import { libraryUrl, playUrl } from "@/lib/mobile/mobileRouteUtils";
import MobileShell from "./MobileShell";
import MobileStateView from "./MobileStateView";
import MobileFolderList from "./MobileFolderList";
import MobileSeasonList from "./MobileSeasonList";
import MobileEpisodeList from "./MobileEpisodeList";

export interface MobileLibraryClientProps {
  /** 空串表示库根 */
  path: string;
}

export default function MobileLibraryClient({ path }: MobileLibraryClientProps) {
  const router = useRouter();
  const { tree } = useMobileLibraryTree();
  const { state, view, errorText, reload } = useMobileLibrary(path);

  // 下钻与详情都是 push：返回键要能逐级退回来
  const openFolder = useCallback((node: FolderNode) => {
    router.push(folderTarget(node).url);
  }, [router]);

  const openDetail = useCallback((video: VideoInfo) => {
    router.push(videoTarget(video).url);
  }, [router]);

  const openPlay = useCallback((video: VideoInfo) => {
    router.push(playUrl(video.file_path));
  }, [router]);

  // 返回键必须自带 fallback：直达链接进来时历史栈里没有上一级，
  // 只调 router.back() 会退出应用。父路径从树里算，算不出就不渲染返回键。
  const parentPath = findParentPath(tree, path);
  const onBack = parentPath === null ? undefined : () => router.push(libraryUrl(parentPath));

  return (
    <MobileShell
      title={view?.title || (path ? "目录" : "媒体库")}
      subtitle={view?.subtitle || undefined}
      onBack={onBack}
    >
      <MobileStateView
        state={state}
        loadingText="正在读取媒体库…"
        emptyText="这个目录里还没有已入库的视频"
        errorText={errorText}
        onRetry={state === "error" ? () => void reload() : undefined}
      >
        <div className="flex flex-col gap-4 pt-3">
          {view?.kind === "seasons" ? (
            <MobileSeasonList seasons={view.folders} onOpen={openFolder} />
          ) : (
            view && view.folders.length > 0 && (
              <MobileFolderList folders={view.folders} onOpen={openFolder} />
            )
          )}
          {view && view.videos.length > 0 && (
            <MobileEpisodeList videos={view.videos} onOpenDetail={openDetail} onPlay={openPlay} />
          )}
        </div>
      </MobileStateView>
    </MobileShell>
  );
}
