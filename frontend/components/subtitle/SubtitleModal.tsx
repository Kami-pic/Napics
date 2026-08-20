// 字幕搜索弹窗（三源：射手网 / SubHD / SubDL）
"use client";
import { useState, useEffect } from "react";
import SubtitleResultCard from "./SubtitleResultCard";
import SubtitleDetailPanel from "./SubtitleDetailPanel";
import SubtitleFilterBar from "./SubtitleFilterBar";
import SubtitleKeywordTrail from "./SubtitleKeywordTrail";
import { useSubtitleSearch } from "./useSubtitleSearch";

export interface SubtitleModalProps {
  open: boolean;
  onClose: () => void;
  /** 视频文件路径（下载目标目录由它决定） */
  videoPath: string;
  /** 兜底搜索词 */
  query: string;
  /** 中文名 */
  cnName?: string;
  /** 英文名 */
  enName?: string;
  /** 原始语言名（日/韩等） */
  originalName?: string;
  /** 目录类型：movie / tv / season 等，决定搜索词变体 */
  folderType?: string;
  /** 季号 */
  seasonNumber?: number;
  /** 集号 */
  episodeNumber?: number;
  /** 集标签，如 S01E05 */
  episodeTag?: string;
  /** 下载成功后回调，供外部刷新字幕状态 */
  onDownloaded?: () => void;
}

export default function SubtitleModal({
  open, onClose, videoPath, query,
  cnName, enName, originalName, folderType, seasonNumber, episodeNumber, episodeTag,
  onDownloaded,
}: SubtitleModalProps) {
  const s = useSubtitleSearch();
  const [inputValue, setInputValue] = useState(query);

  const searchOptions = {
    cn_name: cnName,
    en_name: enName,
    original_name: originalName,
    folder_type: folderType,
    season_number: seasonNumber,
    episode_number: episodeNumber,
    episode_tag: episodeTag,
  };

  // 打开时用结构化名称自动搜索（与「搜索升级」同一套搜索词规则）
  useEffect(() => {
    if (!open) return;
    const initial = cnName || enName || query;
    setInputValue(initial);
    if (initial) s.doSearch(initial, searchOptions);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, query, cnName, enName]);

  if (!open) return null;

  // 手动输入时只按输入词搜，不再叠加结构化名称
  const handleSearch = () => {
    const value = inputValue.trim();
    if (!value) return;
    s.doSearch(value, {
      folder_type: folderType,
      season_number: seasonNumber,
      episode_number: episodeNumber,
    });
  };

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center p-8 z-50">
      <div className="bg-[var(--background)] border border-white/[0.06] rounded-2xl w-full max-w-[1000px] h-[82vh] flex flex-col">
        {/* 搜索栏 */}
        <div className="flex items-center gap-3 px-5 pt-5 pb-3 border-b border-white/[0.06]">
          <div className="flex-1 flex items-center gap-2 bg-white/[0.04] rounded-lg px-3 py-2">
            <span className="text-slate-500 text-sm">📝</span>
            <input
              className="flex-1 bg-transparent text-sm text-slate-200 outline-none placeholder:text-slate-600"
              placeholder="影片名称，回车搜索"
              value={inputValue}
              onChange={e => setInputValue(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter") handleSearch(); }}
              autoFocus
            />
            <button
              onClick={() => s.setSmartFilter(!s.smartFilter)}
              title={
                s.smartFilter
                  ? `智能过滤已开启：隐藏不相关结果${s.junkCount ? `（已隐藏 ${s.junkCount} 条）` : ""}`
                  : "智能过滤已关闭：显示全部结果"
              }
              className={`w-7 h-7 rounded flex items-center justify-center text-sm transition-colors ${
                s.smartFilter ? "text-green-400 hover:bg-green-600/20" : "text-slate-600 hover:text-slate-400"
              }`}
            >
              {s.smartFilter ? "🛡️" : "🔓"}
            </button>
            <button
              className="text-xs px-3 py-1 rounded bg-blue-500/20 text-blue-400 hover:bg-blue-500/30 transition-colors disabled:opacity-50"
              onClick={handleSearch}
              disabled={s.searching}
            >
              {s.searching ? "搜索中..." : "搜索"}
            </button>
          </div>
          <button className="text-slate-500 hover:text-slate-300 text-lg px-2" onClick={onClose}>✕</button>
        </div>

        <SubtitleFilterBar
          sourceFilter={s.sourceFilter}
          formatFilter={s.formatFilter}
          langFilter={s.langFilter}
          sources={s.sources}
          filteredCount={s.filteredResults.length}
          totalCount={s.results.length}
          onSourceChange={s.setSourceFilter}
          onFormatChange={s.setFormatFilter}
          onLangChange={s.setLangFilter}
        />

        {!s.searching && (
          <SubtitleKeywordTrail
            candidates={s.candidateKeywords}
            sources={s.sources}
            activeKeyword={inputValue}
            onPick={keyword => { setInputValue(keyword); s.doSearch(keyword, { folder_type: folderType }); }}
          />
        )}

        <div className="flex-1 flex overflow-hidden">
          {/* 结果列表 */}
          <div className="flex-1 overflow-y-auto p-4 space-y-2">
            {s.searching && (
              <div className="flex flex-col items-center py-16">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mb-3" />
                <p className="text-[13px] text-slate-500">三源并发搜索中...</p>
              </div>
            )}

            {!s.searching && s.error && (
              <div className="text-center py-16">
                <p className="text-sm text-red-400">{s.error}</p>
              </div>
            )}

            {!s.searching && !s.error && s.results.length === 0 && s.keyword && (
              <div className="text-center py-16">
                <p className="text-sm text-slate-500">未找到相关字幕</p>
                <p className="text-xs text-slate-600 mt-1">试试改用英文名，或检查插件配置中的源凭据</p>
              </div>
            )}

            {!s.searching && s.results.length > 0 && s.filteredResults.length === 0 && (
              <div className="text-center py-16">
                <p className="text-sm text-slate-500">当前筛选无结果</p>
                {s.smartFilter && s.junkCount > 0 && (
                  <p className="text-xs text-slate-600 mt-1">
                    智能过滤隐藏了 {s.junkCount} 条不相关结果，点 🛡️ 可关闭
                  </p>
                )}
              </div>
            )}

            {s.filteredResults.map(item => (
              <SubtitleResultCard
                key={`${item.source}-${item.id}`}
                item={item}
                selected={s.selected?.source === item.source && s.selected?.id === item.id}
                onSelect={s.selectItem}
              />
            ))}
          </div>

          {/* 详情面板 */}
          {s.selected && (
            <SubtitleDetailPanel
              item={s.selected}
              detail={s.selectedDetail}
              loading={s.loadingDetail}
              downloading={s.downloading}
              downloadMsg={s.downloadMsg}
              downloadOk={s.downloadOk}
              videoPath={videoPath}
              onDownload={async (item, path, fileUrl, langSuffix) => {
                await s.doDownload(item, path, fileUrl, langSuffix);
                onDownloaded?.();
              }}
              onClose={s.clearSelection}
            />
          )}
        </div>
      </div>
    </div>
  );
}
