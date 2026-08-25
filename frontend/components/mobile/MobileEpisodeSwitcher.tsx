// 上一集 / 下一集。只在同一目录（同季）内切。
//
// **和原生播放器的关系要说清楚**：
// - 这排按钮在**页面里**，不在播放器里。iOS 上只要还是内联播放（`playsInline`）就能点到；
//   用户一旦按了播放器的全屏按钮，iOS 会接管成系统全屏播放器，那时页面被完全遮住，
//   切集必须先退出全屏（系统播放器左上角的「完成」）。这是 iOS 的既定行为，
//   不做 hack 去拦全屏 —— 全屏观看体验比就地切集重要。
// - 换集后**不会自动播放**：换 src 相当于新的媒体加载，iOS 要求新的用户手势。
//   所以按钮文案是"下一集"而不是"播下一集"，用户按完还要点一次播放键。
"use client";

export interface MobileEpisodeSwitcherProps {
  /** 当前位置，从 1 开始 */
  index: number;
  total: number;
  hasPrev: boolean;
  hasNext: boolean;
  onPrev: () => void;
  onNext: () => void;
}

export default function MobileEpisodeSwitcher({
  index,
  total,
  hasPrev,
  hasNext,
  onPrev,
  onNext,
}: MobileEpisodeSwitcherProps) {
  // 目录里只有一个视频（电影、单文件目录）时没有可切的对象
  if (total <= 1) return null;

  return (
    <div className="flex items-center gap-2" aria-label="切换集数">
      <button
        type="button"
        onClick={onPrev}
        disabled={!hasPrev}
        className="flex flex-1 items-center justify-center gap-1.5 rounded-[var(--m-radius-sm)] text-[13px] text-[var(--m-text)] disabled:opacity-40"
        style={{
          minHeight: "var(--m-touch-min)",
          background: "var(--m-surface)",
          border: "1px solid var(--m-border)",
        }}
      >
        <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" aria-hidden="true">
          <path d="m15 18-6-6 6-6" />
        </svg>
        上一集
      </button>

      <span className="shrink-0 text-[12px] tabular-nums text-[var(--m-text-dim)]">
        {index} / {total}
      </span>

      <button
        type="button"
        onClick={onNext}
        disabled={!hasNext}
        className="flex flex-1 items-center justify-center gap-1.5 rounded-[var(--m-radius-sm)] text-[13px] text-[var(--m-text)] disabled:opacity-40"
        style={{
          minHeight: "var(--m-touch-min)",
          background: "var(--m-surface)",
          border: "1px solid var(--m-border)",
        }}
      >
        下一集
        <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" aria-hidden="true">
          <path d="m9 18 6-6-6-6" />
        </svg>
      </button>
    </div>
  );
}
