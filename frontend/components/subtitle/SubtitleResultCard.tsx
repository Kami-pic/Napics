// 字幕搜索结果单条卡片
"use client";
import type { SubtitleSearchItem } from "@/lib/api/subtitle";
import { normalizeFormat, normalizeLang } from "./useSubtitleSearch";

export interface SubtitleResultCardProps {
  item: SubtitleSearchItem;
  selected: boolean;
  onSelect: (item: SubtitleSearchItem) => void;
}

const SOURCE_STYLE: Record<string, { label: string; cls: string }> = {
  assrt: { label: "射手网", cls: "bg-sky-500/15 text-sky-400" },
  subhd: { label: "SubHD", cls: "bg-rose-500/15 text-rose-400" },
  subdl: { label: "SubDL", cls: "bg-amber-500/15 text-amber-400" },
};

const FORMAT_STYLE: Record<string, string> = {
  SRT: "bg-blue-500/15 text-blue-400",
  ASS: "bg-purple-500/15 text-purple-400",
  SSA: "bg-purple-500/15 text-purple-300",
  SUP: "bg-orange-500/15 text-orange-400",
  SUB: "bg-yellow-500/15 text-yellow-400",
};

export default function SubtitleResultCard({ item, selected, onSelect }: SubtitleResultCardProps) {
  const source = SOURCE_STYLE[item.source] ?? { label: item.source, cls: "bg-white/[0.06] text-slate-400" };
  const format = normalizeFormat(item.subtype);
  const lang = normalizeLang(item.lang?.desc || "");
  const title = item.native_name || item.videoname;

  return (
    <button
      type="button"
      onClick={() => onSelect(item)}
      className={`w-full text-left bg-[#0f0f0f] rounded-xl border transition-colors ${
        selected ? "border-blue-500/40 bg-blue-500/5" : "border-white/[0.06] hover:border-white/[0.10]"
      }`}
    >
      <div className="px-4 py-3">
        <p className="text-[13px] text-slate-200 leading-snug truncate" title={title}>
          {title}
        </p>

        <div className="flex items-center gap-1.5 mt-2 flex-wrap">
          <span className={`text-[10px] px-2 py-0.5 rounded font-medium ${source.cls}`}>
            {source.label}
          </span>

          {format !== "其他" && (
            <span className={`text-[10px] px-2 py-0.5 rounded font-medium ${FORMAT_STYLE[format] ?? "bg-white/[0.06] text-slate-500"}`}>
              {format}
            </span>
          )}

          {lang !== "其他" && (
            <span className="text-[10px] px-2 py-0.5 rounded bg-green-500/15 text-green-400">
              {lang}
            </span>
          )}

          {item.release_site && (
            <span className="text-[10px] px-2 py-0.5 rounded bg-white/[0.06] text-slate-400 max-w-[120px] truncate">
              {item.release_site}
            </span>
          )}

          {item.file_size && (
            <span className="text-[10px] px-2 py-0.5 rounded bg-white/[0.04] text-slate-500 font-mono">
              {item.file_size}
            </span>
          )}

          {item.vote_score > 0 && (
            <span className="text-[10px] px-2 py-0.5 rounded bg-amber-500/10 text-amber-400">
              ★ {item.vote_score}
            </span>
          )}

          {/* 相关性：低分标红，便于判断是否误匹配 */}
          {item.match_score > 0 && (
            <span
              className={`text-[10px] px-2 py-0.5 rounded font-mono ${
                item.match_score >= 70
                  ? "bg-emerald-500/10 text-emerald-400"
                  : item.match_score >= 40
                  ? "bg-white/[0.04] text-slate-500"
                  : "bg-red-500/10 text-red-400"
              }`}
              title={`相关性 ${item.match_score}`}
            >
              {item.match_score}
            </span>
          )}

          {item.is_junk && (
            <span
              className="text-[10px] px-2 py-0.5 rounded bg-red-500/10 text-red-400"
              title={item.junk_reasons.join(", ")}
            >
              可能不相关
            </span>
          )}
        </div>

        {(item.videoname || item.upload_time) && (
          <div className="flex items-center gap-3 mt-1.5">
            {item.videoname && item.videoname !== title && (
              <span className="text-[10px] text-slate-500 truncate flex-1" title={item.videoname}>
                {item.videoname}
              </span>
            )}
            {item.upload_time && (
              <span className="text-[10px] text-slate-600 shrink-0 ml-auto">
                {item.upload_time.split(" ")[0]}
              </span>
            )}
          </div>
        )}
      </div>
    </button>
  );
}
