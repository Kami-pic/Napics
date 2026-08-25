// 字幕开关。
//
// 必须由页面提供：iOS Safari **内联**播放没有字幕菜单（CC 只出现在原生全屏里），
// 只靠 <track default> 的话用户没有任何办法关掉字幕。
"use client";

export interface MobileSubtitleSwitchProps {
  names: string[];
  /** -1 表示关闭 */
  activeIndex: number;
  onSelect: (index: number) => void;
}

export default function MobileSubtitleSwitch({ names, activeIndex, onSelect }: MobileSubtitleSwitchProps) {
  if (names.length === 0) return null;

  const options: { label: string; index: number }[] = [
    { label: "关闭", index: -1 },
    ...names.map((name, index) => ({ label: name, index })),
  ];

  return (
    <div className="flex flex-wrap items-center gap-2" role="group" aria-label="字幕">
      <span className="text-[12px] text-[var(--m-text-dim)]">字幕</span>
      {options.map(({ label, index }) => {
        const active = index === activeIndex;
        return (
          <button
            key={index}
            type="button"
            onClick={() => onSelect(index)}
            aria-pressed={active}
            className="max-w-[45%] truncate rounded-lg px-3 text-[12px]"
            style={{
              minHeight: "var(--m-touch-min)",
              background: active ? "var(--m-accent-weak)" : "var(--m-surface)",
              color: active ? "var(--m-accent)" : "var(--m-text-muted)",
              border: "1px solid var(--m-border)",
            }}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}
