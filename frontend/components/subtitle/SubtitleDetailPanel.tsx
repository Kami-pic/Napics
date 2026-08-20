// 字幕详情面板：assrt 展开压缩包文件列表，其他源直接下载
"use client";
import { useState, useEffect } from "react";
import type { SubtitleDetail, SubtitleSearchItem } from "@/lib/api/subtitle";

export interface SubtitleDetailPanelProps {
  item: SubtitleSearchItem;
  detail: SubtitleDetail | null;
  loading: boolean;
  downloading: boolean;
  downloadMsg: string;
  downloadOk: boolean;
  videoPath: string;
  onDownload: (item: SubtitleSearchItem, videoPath: string, fileUrl?: string, langSuffix?: string) => Promise<void>;
  onClose: () => void;
}

const SUFFIX_OPTIONS = ["chs", "cht", "eng", "jpn", "kor", ""] as const;

/** 从语言描述推测语言后缀 */
function guessLangSuffix(desc: string): string {
  const text = desc || "";
  if (text.includes("简") || text.includes("双语")) return "chs";
  if (text.includes("繁")) return "cht";
  if (text.includes("英")) return "eng";
  if (text.includes("日")) return "jpn";
  if (text.includes("韩")) return "kor";
  return "";
}

export default function SubtitleDetailPanel({
  item, detail, loading, downloading, downloadMsg, downloadOk,
  videoPath, onDownload, onClose,
}: SubtitleDetailPanelProps) {
  const [langSuffix, setLangSuffix] = useState(() => guessLangSuffix(item.lang?.desc || ""));

  // 切换选中项时重算默认后缀
  useEffect(() => {
    setLangSuffix(guessLangSuffix(item.lang?.desc || ""));
  }, [item.id, item.lang?.desc]);

  const title = detail?.native_name || detail?.title || item.native_name || item.videoname;

  return (
    <div className="w-[300px] border-l border-white/[0.06] flex flex-col overflow-hidden">
      <div className="flex items-center justify-between px-4 pt-4 pb-2">
        <span className="text-xs text-slate-400 font-medium">字幕详情</span>
        <button className="text-slate-600 hover:text-slate-400 text-sm" onClick={onClose}>✕</button>
      </div>

      <div className="px-4 pb-3 space-y-2 border-b border-white/[0.06]">
        <p className="text-[12px] text-slate-300 leading-relaxed">{title}</p>
        <div className="flex flex-wrap gap-1.5">
          {item.subtype && (
            <span className="text-[10px] px-2 py-0.5 rounded bg-blue-500/15 text-blue-400">{item.subtype}</span>
          )}
          {item.lang?.desc && (
            <span className="text-[10px] px-2 py-0.5 rounded bg-green-500/15 text-green-400">{item.lang.desc}</span>
          )}
          {item.release_site && (
            <span className="text-[10px] px-2 py-0.5 rounded bg-white/[0.06] text-slate-400">{item.release_site}</span>
          )}
        </div>
        {item.hit_keyword && (
          <p className="text-[10px] text-slate-600">命中搜索词：{item.hit_keyword}</p>
        )}
        {detail && (
          <div className="flex gap-3 text-[10px] text-slate-600">
            <span>下载 {detail.down_count}</span>
            <span>浏览 {detail.view_count}</span>
            {detail.upload_time && <span>{detail.upload_time.split(" ")[0]}</span>}
          </div>
        )}
      </div>

      {/* assrt 才有压缩包文件列表 */}
      <div className="flex-1 overflow-y-auto px-4 py-3">
        {loading ? (
          <div className="flex justify-center py-6">
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-500" />
          </div>
        ) : detail && detail.filelist.length > 0 ? (
          <>
            <p className="text-[10px] text-slate-500 mb-2">包含 {detail.filelist.length} 个文件</p>
            <div className="space-y-1.5">
              {detail.filelist.map((file, idx) => (
                <div
                  key={`${file.f}-${idx}`}
                  className="flex items-center gap-2 px-2.5 py-2 rounded-lg bg-white/[0.03] hover:bg-white/[0.06] transition-colors group"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-[11px] text-slate-300 truncate" title={file.f}>{file.f}</p>
                    <p className="text-[10px] text-slate-600">{file.s}</p>
                  </div>
                  <button
                    className="text-[10px] px-2 py-1 rounded bg-blue-500/20 text-blue-400 hover:bg-blue-500/30 opacity-0 group-hover:opacity-100 transition-opacity shrink-0 disabled:opacity-50"
                    onClick={() => onDownload(item, videoPath, file.url, langSuffix)}
                    disabled={downloading}
                  >
                    下载
                  </button>
                </div>
              ))}
            </div>
          </>
        ) : (
          <p className="text-[10px] text-slate-600">
            {item.source === "assrt" ? "该字幕无文件列表，可直接下载整包" : "该源直接下载字幕包"}
          </p>
        )}
      </div>

      <div className="px-4 py-3 border-t border-white/[0.06] space-y-2">
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-slate-500">后缀</span>
          <div className="flex gap-1">
            {SUFFIX_OPTIONS.map(suffix => (
              <button
                key={suffix || "none"}
                className={`text-[10px] px-1.5 py-0.5 rounded transition-colors ${
                  langSuffix === suffix
                    ? "bg-blue-500/20 text-blue-400"
                    : "bg-white/[0.04] text-slate-500 hover:text-slate-300"
                }`}
                onClick={() => setLangSuffix(suffix)}
              >
                {suffix || "无"}
              </button>
            ))}
          </div>
        </div>

        <button
          className="w-full text-xs py-2 rounded-lg bg-blue-500/20 text-blue-400 hover:bg-blue-500/30 transition-colors disabled:opacity-50"
          onClick={() => onDownload(item, videoPath, undefined, langSuffix)}
          disabled={downloading}
        >
          {downloading ? "下载中..." : "下载字幕"}
        </button>

        {downloadMsg && (
          <p className={`text-[10px] text-center ${downloadOk ? "text-green-400" : "text-red-400"}`}>
            {downloadMsg}
          </p>
        )}
      </div>
    </div>
  );
}
