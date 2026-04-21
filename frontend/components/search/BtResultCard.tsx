// BT 搜索结果单条卡片
"use client";
import type { EnhancedSearchResult } from "@/types";
import { INDEXER_TAG_STYLE, INDEXER_DOT_COLOR } from "./FilterBar";

// 已知直搜源名称
const DIRECT_SOURCE_NAMES = new Set(["bitsearch", "cilixiong", "xl720", "nyaa", "mikan", "yts", "limetorrents", "acgrip", "bangumi_moe"]);

const RES_RANK: Record<string, number> = { "": 0, SD: 0, "720p": 1, "1080p": 2, "2160p": 3 };

function isSeasonPack(title: string) {
  return /S\d{2}/i.test(title) && !/E\d{2}/i.test(title);
}

export interface BtResultCardProps {
  res: EnhancedSearchResult;
  index: number;
  currentResolution: string;
  qbConfigured: boolean;
  downloadingUrl: string | null;
  onDownload: (res: EnhancedSearchResult, channel: "qb" | "alist") => void;
}

export default function BtResultCard({ res, index, currentResolution, qbConfigured, downloadingUrl, onDownload }: BtResultCardProps) {
  const curRes = currentResolution;
  const isHigher = (() => {
    const resScore = (res as any).quality_score ?? 0;
    if (resScore > 0 && curRes) {
      const curScore = RES_RANK[curRes] ?? 0;
      const curEstimate = curScore === 3 ? 80 : curScore === 2 ? 50 : curScore === 1 ? 25 : 0;
      return resScore > curEstimate + 5;
    }
    const rr = RES_RANK[res.quality?.resolution ?? ""] ?? 0;
    const cr = RES_RANK[curRes] ?? 0;
    return cr > 0 && rr > cr;
  })();

  const isDownloading = downloadingUrl === res.download_url;
  const q = res.quality;
  const surround = q?.is_surround ?? false;
  const is4k = q?.resolution === "2160p";
  const is1080 = q?.resolution === "1080p";
  const seasonPack = isSeasonPack(res.title);

  return (
    <div className="bg-[#0f0f0f] rounded-xl border border-white/[0.06] hover:border-white/[0.10] transition-colors overflow-hidden">
      <div className="flex items-center gap-4 px-4 py-3">
        <div className="flex-1 min-w-0">
          <p className="text-[13px] text-slate-200 truncate leading-snug" title={res.title}>{res.title}</p>
          <div className="flex items-center gap-1.5 mt-2 flex-wrap">
            {q?.resolution && (
              <span className={`text-[10px] px-2 py-0.5 rounded font-bold ${
                is4k ? "bg-yellow-500/20 text-yellow-400" :
                is1080 ? "bg-blue-500/15 text-blue-400" :
                "bg-white/[0.06] text-slate-500"
              }`}>{q.resolution}</span>
            )}
            {isHigher && <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/15 text-green-400 font-bold">↑ 更高</span>}
            {q?.source && <span className="text-[10px] px-2 py-0.5 rounded bg-white/[0.04] text-slate-400">{q.source}</span>}
            {q?.video_codec && <span className="text-[10px] px-2 py-0.5 rounded bg-white/[0.04] text-slate-500">{q.video_codec}</span>}
            {q?.audio_codec && (
              <span className={`text-[10px] px-2 py-0.5 rounded ${surround ? "bg-purple-500/15 text-purple-400 font-medium" : "bg-white/[0.04] text-slate-500"}`}>
                {q.audio_codec}
              </span>
            )}
            {/* 索引器标签：直搜源用各自颜色，Prowlarr 索引器加 "p:" 前缀 + 统一灰色 */}
            {(() => {
              const source = (res as any)._source || "";
              const indexer = res.indexer || "";
              const isDirectSource = DIRECT_SOURCE_NAMES.has(source);
              if (isDirectSource) {
                // 直搜源：用各自品牌色
                return <span className={`text-[10px] px-2 py-0.5 rounded ${INDEXER_TAG_STYLE[source] || "bg-white/[0.04] text-slate-500"}`}>{indexer}</span>;
              }
              // Prowlarr 索引器：两段式标签（橙色 p + 灰色索引器名）
              return (
                <span className="text-[10px] rounded overflow-hidden inline-flex">
                  <span className="bg-orange-500/20 text-orange-400 px-1 py-0.5 font-bold">p</span>
                  <span className="bg-white/[0.04] text-slate-500 px-1.5 py-0.5">{indexer}</span>
                </span>
              );
            })()}
            {q?.has_chinese_sub && <span className="text-[10px] px-2 py-0.5 rounded bg-blue-500/15 text-blue-400 font-medium">中字</span>}
            {seasonPack && <span className="text-[10px] px-2 py-0.5 rounded bg-yellow-500/15 text-yellow-400 font-medium">整季</span>}
            {q?.release_group && <span className="text-[10px] px-2 py-0.5 rounded bg-white/[0.04] text-slate-500">{q.release_group}</span>}
            {(res as any).quality_score > 0 && (
              <span className="text-[10px] px-2 py-0.5 rounded bg-white/[0.04] text-slate-500 font-mono">{(res as any).quality_score}分</span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-4 flex-shrink-0">
          <div className="text-right min-w-[65px]">
            <p className="text-[13px] font-bold text-slate-200">{res.size_gb > 0 ? `${res.size_gb} GB` : "—"}</p>
            <p className="text-[11px] text-slate-500">
              {res.seeders === 0 && res.size_gb === 0
                ? <span className="text-slate-500">磁力</span>
                : <>做种 <span className={res.seeders > 10 ? "text-green-400" : res.seeders > 0 ? "text-yellow-400" : "text-red-400"}>{res.seeders}</span></>
              }
            </p>
          </div>
          <div className="flex gap-1.5">
            <button onClick={() => onDownload(res, "qb")} disabled={!qbConfigured || isDownloading}
              className={`px-4 py-1.5 rounded-lg text-[12px] font-bold transition-colors ${qbConfigured ? "bg-blue-600 hover:bg-blue-500 text-white" : "bg-white/[0.04] text-slate-600 cursor-not-allowed"} disabled:opacity-40`}>
              {isDownloading ? "..." : "下载"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
