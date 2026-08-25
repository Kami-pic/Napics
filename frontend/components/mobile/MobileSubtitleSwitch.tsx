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
    // 这是一组互斥单选（含"关闭"），不是一排独立开关：用 radiogroup/radio
    // 读屏才会念成"3 项中的第 2 项"，用 aria-pressed 会念成各自的按下状态。
    // 标签指向可见的那个"字幕"，不另写 aria-label，否则读屏念两遍。
    <div className="flex flex-wrap items-center gap-2" role="radiogroup" aria-labelledby="m-subtitle-label">
      <span id="m-subtitle-label" className="text-[12px] text-[var(--m-text-dim)]">字幕</span>
      {options.map(({ label, index }) => {
        const active = index === activeIndex;
        return (
          <button
            key={index}
            type="button"
            role="radio"
            onClick={() => onSelect(index)}
            aria-checked={active}
            className="max-w-[45%] truncate rounded-[var(--m-radius-pill)] px-3 text-[12px]"
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
