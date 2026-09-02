// 取名证据有矛盾时的提示条。
//
// 名字仍然会填一个最优候选（留空会让搜索和 UI 一起失去可用值），但必须让用户看得见
// 这条数据没通过自检，否则错值就悄悄沉淀下去了 —— 库里那 1992 条 source=nfo
// 就是这么来的。
"use client";

/** 冲突类型 → 人话。后端常量见 backend/name_conflicts.py */
const CONFLICT_LABELS: Record<string, string> = {
  nfo_season_vs_folder: "刮削信息写的季号和目录名对不上",
  nfo_episode_vs_filename: "刮削信息写的集号和文件名里的序号对不上",
  nfo_year_vs_name: "刮削信息的年份和文件名里的年份对不上",
  sibling_name_mismatch: "同一目录下各集算出的作品名互不相同，取到的多半是分集标题",
};

export interface NameConflictHintProps {
  conflicts?: string[];
}

export default function NameConflictHint({ conflicts }: NameConflictHintProps) {
  if (!conflicts || conflicts.length === 0) return null;

  return (
    <div className="px-1">
      <div className="flex items-start gap-1.5 rounded-lg border border-amber-500/20 bg-amber-500/[0.07] px-2 py-1.5">
        <span className="text-[10px] leading-4 text-amber-400 shrink-0">⚠</span>
        <div className="min-w-0 flex-1">
          <p className="text-[11px] text-amber-300/90">名字没通过自检，下面显示的是候选值</p>
          <ul className="mt-0.5 space-y-0.5">
            {conflicts.map(c => (
              <li key={c} className="text-[10px] leading-4 text-amber-200/70">
                · {CONFLICT_LABELS[c] || c}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
