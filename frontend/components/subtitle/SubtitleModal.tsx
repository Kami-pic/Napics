// 字幕搜索弹窗
"use client";
import { useState, useEffect } from "react";
import SubtitleResultCard from "./SubtitleResultCard";
import SubtitleDetailPanel from "./SubtitleDetailPanel";
import { useSubtitleSearch, FORMAT_OPTIONS, LANG_OPTIONS, type FormatFilter, type LangFilter } from "./useSubtitleSearch";

export interface SubtitleModalProps {
  open: boolean;
  onClose: () => void;
  /** 默认搜索词（影片名） */
  query: string;
  /** 视频文件路径（下载时使用） */
  videoPath: string;
  /** 中文名 */
  cnName?: string;
  /** 英文名 */
  enName?: string;
  /** 原始语言名 */
  originalName?: string;
  /** 季号 */
  seasonNumber?: number;
  /** 集号 */
  episodeNumber?: number;
}

export default function SubtitleModal({ open, onClose, query, videoPath, cnName, enName, originalName, seasonNumber, episodeNumber }: SubtitleModalProps) {
  const s = useSubtitleSearch();
  const [inputValue, setInputValue] = useState(query);

  // 打开时用结构化名称自动搜索
  useEffect(() => {
    if (open && (cnName || enName || query)) {
      setInputValue(cnName || enName || query);
      s.doSearch(cnName || enName || query, {
        cn_name: cnName,
        en_name: enName,
        original_name: originalName,
        season_number: seasonNumber,
        episode_number: episodeNumber,
      });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, query]);

  if (!open) return null;

  const handleSearch = () => {
    if (inputValue.trim().length >= 3) {
      s.doSearch(inputValue.trim(), {
        cn_name: cnName,
        en_name: enName,
        original_name: originalName,
        season_number: seasonNumber,
        episode_number: episodeNumber,
      });
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSearch();
  };

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center p-8 z-50">
      <div className="bg-[var(--background)] border border-white/[0.06] rounded-2xl w-full max-w-[900px] h-[80vh] flex flex-col">

        {/* 头部：搜索栏 */}
        <div className="flex items-center gap-3 px-5 pt-5 pb-3 border-b border-white/[0.06]">
          <div className="flex-1 flex items-center gap-2 bg-white/[0.04] rounded-lg px-3 py-2">
            <span className="text-slate-500 text-sm">📝</span>
            <input
              className="flex-1 bg-transparent text-sm text-slate-200 outline-none placeholder:text-slate-600"
              placeholder="输入影片名称搜索字幕..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              autoFocus
            />
            <button
              className="text-xs px-3 py-1 rounded bg-blue-500/20 text-blue-400 hover:bg-blue-500/30 transition-colors"
              onClick={handleSearch}
              disabled={s.searching}
            >
              {s.searching ? "搜索中..." : "搜索"}
            </button>
          </div>
          <button
            className="text-slate-500 hover:text-slate-300 text-lg px-2"
            onClick={onClose}
          >
            ✕
          </button>
        </div>

        {/* 筛选栏 */}
        <div className="flex items-center gap-4 px-5 py-2.5 border-b border-white/[0.06]">
          {/* 格式筛选 */}
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-slate-500">格式</span>
            {FORMAT_OPTIONS.map((opt) => (
              <button
                key={opt}
                className={`text-[10px] px-2 py-0.5 rounded transition-colors ${
                  s.formatFilter === opt
                    ? "bg-blue-500/20 text-blue-400"
                    : "bg-white/[0.04] text-slate-500 hover:text-slate-300"
                }`}
                onClick={() => s.setFormatFilter(opt as FormatFilter)}
              >
                {opt}
              </button>
            ))}
          </div>

          {/* 语言筛选 */}
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-slate-500">语言</span>
            {LANG_OPTIONS.map((opt) => (
              <button
                key={opt}
                className={`text-[10px] px-2 py-0.5 rounded transition-colors ${
                  s.langFilter === opt
                    ? "bg-green-500/20 text-green-400"
                    : "bg-white/[0.04] text-slate-500 hover:text-slate-300"
                }`}
                onClick={() => s.setLangFilter(opt as LangFilter)}
              >
                {opt}
              </button>
            ))}
          </div>

          {/* 结果计数 */}
          {s.results.length > 0 && (
            <span className="text-[10px] text-slate-600 ml-auto">
              {s.filteredResults.length}/{s.results.length} 条
            </span>
          )}
        </div>

        {/* 主体 */}
        <div className="flex-1 flex overflow-hidden">
          {/* 左侧：搜索结果列表 */}
          <div className="flex-1 overflow-y-auto p-4 space-y-2">
            {s.searching && (
              <div className="flex flex-col items-center py-16">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mb-3" />
                <p className="text-[13px] text-slate-500">搜索中...</p>
              </div>
            )}

            {s.error && (
              <div className="text-center py-16">
                <p className="text-sm text-red-400">{s.error}</p>
              </div>
            )}

            {!s.searching && !s.error && s.filteredResults.length === 0 && s.results.length > 0 && (
              <div className="text-center py-16">
                <p className="text-sm text-slate-500">当前筛选无结果，试试调整筛选条件</p>
              </div>
            )}

            {!s.searching && !s.error && s.results.length === 0 && s.keyword && (
              <div className="text-center py-16">
                <p className="text-sm text-slate-500">未找到相关字幕</p>
                <p className="text-xs text-slate-600 mt-1">试试用英文名或缩短关键词</p>
              </div>
            )}

            {s.filteredResults.map((item) => (
              <SubtitleResultCard
                key={item.id}
                item={item}
                onSelect={s.fetchDetail}
                selected={s.selectedDetail?.id === item.id}
              />
            ))}
          </div>

          {/* 右侧：详情面板 */}
          {s.selectedDetail && (
            <SubtitleDetailPanel
              detail={s.selectedDetail}
              loading={s.loadingDetail}
              downloading={s.downloading}
              downloadMsg={s.downloadMsg}
              videoPath={videoPath}
              onDownload={s.doDownload}
              onClose={s.clearDetail}
            />
          )}
        </div>
      </div>
    </div>
  );
}
