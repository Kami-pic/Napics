// 移动端海报：本地文件优先，失败退远程（经后端代理），都没有就显示文字占位。
//
// 顺序不能反：本地 poster.jpg 在局域网内是最快的，远程 TMDB 图床要走后端 HTTP 代理。
"use client";
import { useState } from "react";
import { api } from "@/lib/api";

export interface MobilePosterProps {
  /** 视频或目录路径，用于取本地 poster */
  localPath: string;
  /** 刮削得到的远程海报地址，可空 */
  remoteUrl?: string | null;
  /** 都加载不出来时显示的文字 */
  fallbackText: string;
}

type Stage = "local" | "remote" | "placeholder";

function initialStage(localPath: string, remoteUrl?: string | null): Stage {
  if (localPath) return "local";
  return remoteUrl ? "remote" : "placeholder";
}

export default function MobilePoster({ localPath, remoteUrl, fallbackText }: MobilePosterProps) {
  // 换片子要重置回退链。用"渲染期比对上次 props"而不是 effect 里 setState ——
  // effect 里同步 setState 会多渲染一帧，也被 react-hooks 规则拦。
  const sourceKey = `${localPath}|${remoteUrl || ""}`;
  const [tracked, setTracked] = useState(() => ({
    key: sourceKey,
    stage: initialStage(localPath, remoteUrl),
  }));
  if (tracked.key !== sourceKey) {
    setTracked({ key: sourceKey, stage: initialStage(localPath, remoteUrl) });
  }
  const stage = tracked.key === sourceKey ? tracked.stage : initialStage(localPath, remoteUrl);
  const setStage = (next: Stage) => setTracked({ key: sourceKey, stage: next });

  const src =
    stage === "local" ? api.getLocalPoster(localPath)
      : stage === "remote" && remoteUrl ? api.getProxiedImage(remoteUrl)
        : "";

  return (
    <div
      className="flex w-24 shrink-0 items-center justify-center overflow-hidden rounded-[var(--m-radius)]"
      style={{ aspectRatio: "2 / 3", background: "var(--m-surface-raised)" }}
    >
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element -- 后端代理出来的图不走 next/image 优化
        <img
          src={src}
          alt=""
          className="h-full w-full object-cover"
          onError={() => setStage(stage === "local" && remoteUrl ? "remote" : "placeholder")}
        />
      ) : (
        <span className="px-2 text-center text-[11px] leading-tight text-[var(--m-text-dim)]">
          {fallbackText}
        </span>
      )}
    </div>
  );
}
