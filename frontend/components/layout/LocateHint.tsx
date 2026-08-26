// 桌面端「操作失败了，但界面上看不出来」这类情况的底部提示条
//
// 两个用处，成因是同一个：后端/前端把失败吞掉了，用户只看到"点了没反应"。
//   1. 「查看 / 定位到目录」—— findLibraryNodeByPath 找不到节点时原来什么都不做，
//      既不知道是没同步、还是路径对不上。移动端一直有这句提示，桌面端漏了。
//   2. 「检测质量」—— 后端不管成功失败都返回 {"status":"ok"}，前端 catch {}。
//
// 为什么不塞在按钮旁边：那里放不下一整句话，而只写"失败"等于没说。
"use client";
import { useEffect } from "react";

export interface LocateHintProps {
  message: string;
  onDismiss: () => void;
  /** 毫秒；<=0 表示不自动消失 */
  duration?: number;
  icon?: string;
}

export default function LocateHint({ message, onDismiss, duration = 5000, icon = "📂" }: LocateHintProps) {
  useEffect(() => {
    if (!message || duration <= 0) return;
    const timer = setTimeout(onDismiss, duration);
    return () => clearTimeout(timer);
  }, [message, duration, onDismiss]);

  if (!message) return null;

  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[70] max-w-[min(90vw,32rem)]">
      <div className="flex items-start gap-3 rounded-lg border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-xs text-amber-300 shadow-2xl backdrop-blur">
        <span aria-hidden="true">{icon}</span>
        <p className="flex-1 leading-relaxed">{message}</p>
        <button onClick={onDismiss} aria-label="关闭提示"
          className="-mr-1 -mt-0.5 rounded px-1 text-amber-400/70 hover:text-amber-200">
          ✕
        </button>
      </div>
    </div>
  );
}
