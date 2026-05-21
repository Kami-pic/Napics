// BT 搜索结果弹窗 — V2：结构化三行布局 + 分组模式 + 命中关键词标注
"use client";
import type { SourceStatus } from "./FilterBar";
import PanResultsView from "./PanResultsView";
import BtResultCard from "./BtResultCard";
import SearchHeader from "./SearchHeader";
import { useSearchState } from "./useSearchState";
import { useInstalledPlugins } from "@/hooks/useInstalledPlugins";
import { api } from "@/lib/api";

interface SearchModalProps {
  open: boolean;
  query: string;
  onClose: () => void;
  defaultSavePath: string;
  currentResolution?: string;
  qbConfigured?: boolean;
  alistConfigured?: boolean;
  shadowName?: string;
  cleanName?: string;
  mediaType?: string;
  cnName?: string;       // 中文名
  enName?: string;       // 英文名
  originalName?: string; // 原始语言名（日文/韩文/法语等）
  folderType?: string;   // "tv" | "season" | "movie" 等
  seasonNumber?: number;  // 季号
  episodeTag?: string;    // 如 "S01E01"
}

export default function SearchModal({
  open, query, onClose, defaultSavePath,
  currentResolution, qbConfigured = true, mediaType,
  cnName, enName, originalName, folderType, seasonNumber, episodeTag,
}: SearchModalProps) {
  const s = useSearchState({
    open, query, defaultSavePath, currentResolution, mediaType,
    cnName, enName, originalName, folderType, seasonNumber, episodeTag,
  });
  const plugins = useInstalledPlugins();

  if (!open) return null;

  // 无搜索源插件时的引导
  const noSearchPlugin = !plugins.hasSearch && !plugins.hasPanSearch;

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center p-8 z-50">
      <div className="bg-[var(--background)] border border-white/[0.06] rounded-2xl w-full max-w-[1200px] h-[85vh] flex flex-col">
        <SearchHeader
          {...s}
          defaultSavePath={defaultSavePath}
          onClose={onClose}
        />

        {s.toast && (
          <div className={`mx-5 mt-3 px-4 py-2 rounded-lg text-xs ${s.toast.ok ? "bg-green-500/10 text-green-400 border border-green-500/20" : "bg-red-500/10 text-red-400 border border-red-500/20"}`}>{s.toast.msg}</div>
        )}

        {/* 结果列表 */}
        <div className="flex-1 overflow-y-auto p-5">
          {noSearchPlugin ? (
            <div className="flex flex-col items-center justify-center py-20">
              <span className="text-3xl mb-4">🔍</span>
              <p className="text-sm text-slate-300 mb-2">未安装搜索源插件</p>
              <p className="text-xs text-slate-500 mb-4">在插件中心安装 BT 搜索源或网盘搜索源后即可搜索资源</p>
              <p className="text-[10px] text-slate-600">插件中心入口：侧边栏底部 🧩</p>
            </div>
          ) : s.activeTab === "bt" ? (
            /* ── BT/磁力 Tab ── */
            <>
          {(s.btActiveSource === "all" ? s.searching : s.sourceTabStates[s.btActiveSource]?.searching) ? (
            <div className="flex flex-col items-center py-16">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mb-3" />
              <p className="text-[13px] text-slate-500 mb-3">
                {s.btActiveSource === "all"
                  ? (s.searchingStep || "搜罗全网资源...")
                  : `搜索 ${s.btActiveSource}...`}
              </p>
              {/* 各源实时状态（仅全部模式显示）*/}
              {s.btActiveSource === "all" && Object.keys(s.sourceStatuses).length > 0 && (
                <div className="flex flex-wrap gap-2 justify-center">
                  {Object.entries(s.sourceStatuses).map(([name, st]) => (
                    <span key={name} className={`text-[10px] px-2 py-0.5 rounded ${
                      st.status === "done" ? "bg-green-500/10 text-green-400" :
                      st.status === "failed" ? "bg-red-500/10 text-red-400" :
                      "bg-blue-500/10 text-blue-400 animate-pulse"
                    }`}>
                      {name} {st.status === "done" ? `✓ ${st.count}` : st.status === "failed" ? "✗" : "..."}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ) : s.error ? (
            <div className="text-center py-10">
              <p className="text-red-400 text-xs mb-3">{s.error}</p>
              <button onClick={() => s.doSearch(s.keyword)} className="text-xs text-blue-400 hover:text-blue-300">重试</button>
            </div>
          ) : (
            <div className="space-y-2">
              {s.filtered.length > 0 && (
                <div className="flex items-center justify-between mb-2">
                  <p className="text-[11px] text-slate-500">
                    共 {s.activeResults.length} 条{s.smartFilter ? `，过滤后 ${s.displayResults.length} 条` : ""}{s.filtered.length !== s.displayResults.length ? `，筛选后 ${s.filtered.length} 条` : ""}
                    {/* 单源模式下显示搜索词回显 */}
                    {s.btActiveSource !== "all" && s.sourceKeywordInfo[s.btActiveSource]?.searched?.length > 0 && (
                      <span className="ml-2">
                        {s.sourceKeywordInfo[s.btActiveSource].searched.map((kw, i) => (
                          <span key={i} className={`inline-block text-[10px] px-1.5 py-0 rounded mr-1 ${
                            kw === s.sourceKeywordInfo[s.btActiveSource].hit ? "bg-blue-500/15 text-blue-400" : "bg-white/[0.04] text-slate-600"
                          }`}>{kw}</span>
                        ))}
                      </span>
                    )}
                  </p>
                </div>
              )}
              {/* 结果呈现 */}
              {s.filtered.map((res, i) => {
                // AI 推荐标记：从原始 results 数组中找到该结果的原始索引
                const origIdx = s.results.indexOf(res);
                const aiReason = origIdx >= 0 ? s.aiRecommended.get(origIdx) : undefined;
                return (
                  <BtResultCard key={i} res={res} index={i} currentResolution={s.curRes} qbConfigured={qbConfigured} downloadingUrl={s.downloadingUrl} onDownload={s.handleDownload} noSeederInfoSources={s.noSeederInfoSources} indexerProviderSources={s.indexerProviderSources} aiReason={aiReason} />
                );
              })}
              {s.filtered.length === 0 && s.activeResults.length > 0 && (
                <p className="text-center py-10 text-xs text-slate-600">无匹配筛选条件的结果</p>
              )}
              {s.activeResults.length === 0 && !s.searching && !(s.sourceTabStates[s.btActiveSource]?.searching) && !s.error && (
                <p className="text-center py-10 text-xs text-slate-600">未搜到资源</p>
              )}
            </div>
          )}
            </>
          ) : (
            /* ── 网盘 Tab ── */
            <PanResultsView
              searching={s.panSearching}
              groups={s.panGroups}
              total={s.panTotal}
              sourceStatuses={s.panSourceStatuses}
              keyword={s.keyword}
              filters={s.panFilters}
              disabledSources={s.disabledSources}
              onRetry={() => s.doPanSearch(s.keyword)}
              onTransfer={async (r) => {
                s.setToast(null);
                try {
                  const result = await api.alistTransfer(r.share_url, r.pan_type, s.savePath);
                  if (result.success) {
                    s.setToast({ msg: "转存任务已提交", ok: true });
                  } else {
                    const errMap: Record<string, string> = {
                      disk_full: "网盘空间不足",
                      name_conflict: "同名文件已存在",
                      link_expired: "分享链接已失效",
                      wrong_password: "提取码错误",
                      alist_unavailable: "OpenList 服务不可达",
                    };
                    s.setToast({ msg: errMap[result.error_code] || result.error_message || "转存失败", ok: false });
                  }
                } catch {
                  s.setToast({ msg: "转存请求失败", ok: false });
                }
              }}
            />
          )}
        </div>

        {/* 底部已移到顶栏搜索框下方 */}
      </div>
    </div>
  );
}
