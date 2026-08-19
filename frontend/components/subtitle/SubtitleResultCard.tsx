// 字幕搜索结果单条卡片
"use client";
import type { SubtitleSearchItem } from "@/lib/api/subtitle";

export interface SubtitleResultCardProps {
  item: SubtitleSearchItem;
  onSelect: (id: number) => void;
  selected: boolean;
}

/** 解析格式标签颜色 */
function formatTagStyle(subtype: string): string {
  const lower = subtype.toLowerCase();
  if (lower.includes("srt") || lower.includes("subrip")) return "bg-blue-500/15 text-blue-400";
  if (lower.includes("ass")) return "bg-purple-500/15 text-purple-400";
  if (lower.includes("ssa")) return "bg-purple-500/15 text-purple-300";
  if (lower.includes("sup") || lower.includes("pgs")) return "bg-orange-500/15 text-orange-400";
  if (lower.includes("vobsub") || lower.includes("sub")) return "bg-yellow-500/15 text-yellow-400";
  return "bg-white/[0.06] text-slate-500";
}

/** 简化格式显示名 */
function formatLabel(subtype: string): string {
  const lower = subtype.toLowerCase();
  if (lower.includes("srt") || lower.includes("subrip")) return "SRT";
  if (lower.includes("ass")) return "ASS";
  if (lower.includes("ssa")) return "SSA";
  if (lower.includes("vobsub")) return "SUB";
  if (lower.includes("sup") || lower.includes("pgs")) return "SUP";
  return subtype || "未知";
}

export default function SubtitleResultCard({ item, onSelect, selected }: SubtitleResultCardProps) {
  return (
    <div
      className={`bg-[#0f0f0f] rounded-xl border transition-colors cursor-pointer ${
        selected ? "border-blue-500/40 bg-blue-500/5" : "border-white/[0.06] hover:border-white/[0.10]"
      }`}
      onClick={() => onSelect(item.id)}
    >
      <div className="px-4 py-3">
        {/* 第一行：标题 */}
        <p className="text-[13px] text-slate-200 leading-snug truncate" title={item.native_name}>
          {item.native_name || item.videoname}
        </p>

        {/* 第二行：标签 */}
        <div className="flex items-center gap-1.5 mt-2 flex-wrap">
          {/* 格式 */}
          <span className={`text-[10px] px-2 py-0.5 rounded font-medium ${formatTagStyle(item.subtype)}`}>
            {formatLabel(item.subtype)}
          </span>

          {/* 语言 */}
          {item.lang?.desc && (
            <span className="text-[10px] px-2 py-0.5 rounded bg-green-500/15 text-green-400">
              {item.lang.desc}
            </span>
          )}

          {/* 字幕组 */}
          {item.release_site && (
            <span className="text-[10px] px-2 py-0.5 rounded bg-white/[0.06] text-slate-400">
              {item.release_site}
            </span>
          )}

          {/* 评分 */}
          {item.vote_score > 0 && (
            <span className="text-[10px] px-2 py-0.5 rounded bg-amber-500/10 text-amber-400">
              ★ {item.vote_score}
            </span>
          )}
        </div>

        {/* 第三行：匹配视频名 + 上传时间 */}
        <div className="flex items-center gap-3 mt-1.5">
          {item.videoname && (
            <span className="text-[10px] text-slate-500 truncate flex-1" title={item.videoname}>
              {item.videoname}
            </span>
          )}
          {item.upload_time && (
            <span className="text-[10px] text-slate-600 shrink-0">
              {item.upload_time.split(" ")[0]}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
