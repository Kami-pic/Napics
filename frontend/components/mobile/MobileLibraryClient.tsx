// 媒体库分级浏览的客户端壳：状态分派 + 路由跳转。
// 显示什么由 libraryNav 的纯函数决定，这里不写矩阵逻辑。
"use client";
import { useCallback } from "react";
import { useRouter } from "next/navigation";

import type { FolderNode, VideoInfo } from "@/types";
import { useMobileLibrary } from "@/hooks/mobile/useMobileLibrary";
import { useMobileLibraryTree } from "./MobileLibraryTreeProvider";
import { folderTarget, videoTarget, findParentPath } from "@/lib/mobile/libraryNav";
import { libraryUrl, playUrl, searchUrl, MOBILE_ROUTES } from "@/lib/mobile/mobileRouteUtils";
import { folderCardMeta, seasonCardMeta, videoCardMeta } from "@/lib/mobile/mobileCardMeta";
import MobileShell from "./MobileShell";
import MobileStateView from "./MobileStateView";
import MobileCardGrid from "./MobileCardGrid";
import MobileMediaCard from "./MobileMediaCard";

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
        // 空态给下一步：目录空要么是还没下载，要么是下载了没入库
        emptyAction={
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => router.push(searchUrl({ q: view?.title || "", tab: "bt" }))}
              className="rounded-[var(--m-radius-sm)] px-4 text-sm text-[var(--m-on-accent)]"
              style={{ minHeight: "var(--m-touch-min)", background: "var(--m-accent)" }}
            >
              搜索资源
            </button>
            <button
              type="button"
              onClick={() => router.push(MOBILE_ROUTES.downloads)}
              className="rounded-[var(--m-radius-sm)] px-4 text-sm text-[var(--m-text)]"
              style={{ minHeight: "var(--m-touch-min)", background: "var(--m-surface-raised)" }}
            >
              去同步
            </button>
          </div>
        }
        errorText={errorText}
        onRetry={state === "error" ? () => void reload() : undefined}
      >
        <div className="flex flex-col gap-4 pt-3">
          {view && view.folders.length > 0 && (
            <MobileCardGrid ariaLabel={view.kind === "seasons" ? "季列表" : "目录列表"}>
              {view.folders.map(node => (
                <MobileMediaCard
                  key={node.path}
                  meta={view.kind === "seasons" ? seasonCardMeta(node) : folderCardMeta(node)}
                  onOpen={() => openFolder(node)}
                />
              ))}
            </MobileCardGrid>
          )}
          {view && view.videos.length > 0 && (
            <MobileCardGrid ariaLabel="视频列表">
              {view.videos.map(video => (
                <MobileMediaCard
                  key={video.file_path}
                  meta={videoCardMeta(video)}
                  onOpen={() => openDetail(video)}
                  onPlay={() => openPlay(video)}
                />
              ))}
            </MobileCardGrid>
          )}
          {/* 剧目录下的剧场版/SP：单独一段，不然会被当成正片的下一集 */}
          {view && view.extraVideos.length > 0 && (
            <MobileCardGrid title="其他视频（剧场版 / 特别篇）">
              {view.extraVideos.map(video => (
                <MobileMediaCard
                  key={video.file_path}
                  meta={videoCardMeta(video)}
                  onOpen={() => openDetail(video)}
                  onPlay={() => openPlay(video)}
                />
              ))}
            </MobileCardGrid>
          )}
        </div>
      </MobileStateView>
    </MobileShell>
  );
}
