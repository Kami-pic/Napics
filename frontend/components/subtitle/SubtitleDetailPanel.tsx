// 字幕详情面板 — 显示文件列表和下载按钮
"use client";
import { useState } from "react";
import type { SubtitleDetail } from "@/lib/api/subtitle";

export interface SubtitleDetailPanelProps {
  detail: SubtitleDetail;
  loading: boolean;
  downloading: boolean;
  downloadMsg: string;
  videoPath: string;
  onDownload: (subtitleId: number, videoPath: string, fileUrl?: string, langSuffix?: string) => Promise<void>;
  onClose: () => void;
}

/** 从语言描述推测语言后缀 */
function guessLangSuffix(desc: string): string {
  if (desc.includes("简") || desc.includes("chs")) return "chs";
  if (desc.includes("繁") || desc.includes("cht")) return "cht";
  if (desc.includes("英") || desc.includes("eng")) return "eng";
  if (desc.includes("日")) return "jpn";
  if (desc.includes("韩")) return "kor";
  if (desc.includes("双")) return "chs";
  return "";
}

export default function SubtitleDetailPanel({
  detail, loading, downloading, downloadMsg, videoPath, onDownload, onClose,
}: SubtitleDetailPanelProps) {
  const [langSuffix, setLangSuffix] = useState(() => guessLangSuffix(detail.lang?.desc || ""));

  if (loading) {
    return (
      <div className="w-[300px] border-l border-white/[0.06] flex items-center justify-center">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500" />
      </div>
    );
  }

  return (
    <div className="w-[300px] border-l border-white/[0.06] flex flex-col overflow-hidden">
      {/* 头部 */}
      <div className="flex items-center justify-between px-4 pt-4 pb-2">
        <span className="text-xs text-slate-400 font-medium">字幕详情</span>
        <button className="text-slate-600 hover:text-slate-400 text-sm" onClick={onClose}>✕</button>
      </div>

      {/* 信息 */}
      <div className="px-4 pb-3 space-y-2 border-b border-white/[0.06]">
        <p className="text-[12px] text-slate-300 leading-relaxed">{detail.native_name || detail.title}</p>
        <div className="flex flex-wrap gap-1.5">
          {detail.subtype && (
            <span className="text-[10px] px-2 py-0.5 rounded bg-blue-500/15 text-blue-400">{detail.subtype}</span>
          )}
          {detail.lang?.desc && (
            <span className="text-[10px] px-2 py-0.5 rounded bg-green-500/15 text-green-400">{detail.lang.desc}</span>
          )}
          {detail.release_site && (
            <span className="text-[10px] px-2 py-0.5 rounded bg-white/[0.06] text-slate-400">{detail.release_site}</span>
          )}
        </div>
        <div className="flex gap-3 text-[10px] text-slate-600">
          <span>下载 {detail.down_count}</span>
          <span>浏览 {detail.view_count}</span>
          {detail.upload_time && <span>{detail.upload_time.split(" ")[0]}</span>}
        </div>
      </div>

      {/* 文件列表 */}
      {detail.filelist.length > 0 && (
        <div className="flex-1 overflow-y-auto px-4 py-3">
          <p className="text-[10px] text-slate-500 mb-2">包含 {detail.filelist.length} 个文件</p>
          <div className="space-y-1.5">
            {detail.filelist.map((file, idx) => (
              <div
                key={idx}
                className="flex items-center gap-2 px-2.5 py-2 rounded-lg bg-white/[0.03] hover:bg-white/[0.06] transition-colors group"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-[11px] text-slate-300 truncate" title={file.f}>{file.f}</p>
                  <p className="text-[10px] text-slate-600">{file.s}</p>
                </div>
                <button
                  className="text-[10px] px-2 py-1 rounded bg-blue-500/20 text-blue-400 hover:bg-blue-500/30 opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
                  onClick={() => onDownload(detail.id, videoPath, file.url, langSuffix)}
                  disabled={downloading}
                >
                  下载
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 底部操作 */}
      <div className="px-4 py-3 border-t border-white/[0.06] space-y-2">
        {/* 语言后缀选择 */}
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-slate-500">后缀</span>
          <div className="flex gap-1">
            {["chs", "cht", "eng", "jpn", "kor", ""].map((suf) => (
              <button
                key={suf}
                className={`text-[10px] px-1.5 py-0.5 rounded transition-colors ${
                  langSuffix === suf
                    ? "bg-blue-500/20 text-blue-400"
                    : "bg-white/[0.04] text-slate-500 hover:text-slate-300"
                }`}
                onClick={() => setLangSuffix(suf)}
              >
                {suf || "无"}
              </button>
            ))}
          </div>
        </div>

        {/* 下载整包按钮 */}
        <button
          className="w-full text-xs py-2 rounded-lg bg-blue-500/20 text-blue-400 hover:bg-blue-500/30 transition-colors disabled:opacity-50"
          onClick={() => onDownload(detail.id, videoPath, undefined, langSuffix)}
          disabled={downloading}
        >
          {downloading ? "下载中..." : "下载字幕"}
        </button>

        {/* 下载状态 */}
        {downloadMsg && (
          <p className={`text-[10px] text-center ${downloadMsg.includes("失败") ? "text-red-400" : "text-green-400"}`}>
            {downloadMsg}
          </p>
        )}
      </div>
    </div>
  );
}
