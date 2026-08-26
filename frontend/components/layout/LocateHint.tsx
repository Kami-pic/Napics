// 「查看 / 定位到目录」失败时的提示条
//
// 为什么需要它：下载面板的「📂 查看」和发现详情的「查看本地」都是把一个路径
// 交给 findLibraryNodeByPath 去树里找节点，找不到时原来**什么都不做** ——
// 用户看到的就是"点了没反应"，既不知道是没同步、还是路径对不上。
// 移动端一直有这句提示（useMobileLibrary），桌面端漏了。
"use client";
import { useEffect } from "react";

export interface LocateHintProps {
  message: string;
  onDismiss: () => void;
  /** 毫秒；<=0 表示不自动消失 */
  duration?: number;
}

export default function LocateHint({ message, onDismiss, duration = 5000 }: LocateHintProps) {
  useEffect(() => {
    if (!message || duration <= 0) return;
    const timer = setTimeout(onDismiss, duration);
    return () => clearTimeout(timer);
  }, [message, duration, onDismiss]);

  if (!message) return null;

  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[70] max-w-[min(90vw,32rem)]">
      <div className="flex items-start gap-3 rounded-lg border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-xs text-amber-300 shadow-2xl backdrop-blur">
        <span aria-hidden="true">📂</span>
        <p className="flex-1 leading-relaxed">{message}</p>
        <button onClick={onDismiss} aria-label="关闭提示"
          className="-mr-1 -mt-0.5 rounded px-1 text-amber-400/70 hover:text-amber-200">
          ✕
        </button>
      </div>
    </div>
  );
}
