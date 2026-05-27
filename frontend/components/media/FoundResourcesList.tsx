// 订阅找到的资源列表：展示 found_resources，用户手动选择下载
"use client";
import { useState, useCallback } from "react";
import { api } from "@/lib/api";

interface RSSItemData {
  title: string;
  download_url: string;
  info_url: string;
  size_gb: number;
  quality_tag: string;
  resolution: string;
  episode: number | null;
  seeders: number;
  indexer: string;
  source_name: string;
  info_hash: string;
}

export interface FoundResourcesListProps {
  resources: RSSItemData[];
  subscriptionId: string;
  subscriptionTitle: string;
  savePath: string;
  mediaType: string;
  onDownloaded: () => void;
}

export default function FoundResourcesList({
  resources, subscriptionId, subscriptionTitle, savePath, mediaType, onDownloaded,
}: FoundResourcesListProps) {
  const [downloading, setDownloading] = useState<string>("");
  const [expanded, setExpanded] = useState(false);

  const handleDownload = useCallback(async (item: RSSItemData) => {
    if (!item.download_url) return;
    setDownloading(item.info_hash || item.title);
    try {
      // 提交下载任务
      await api.submitDownload({
        media_name: `${subscriptionTitle}${item.episode ? ` E${String(item.episode).padStart(2, "0")}` : ""}`,
        download_url: item.download_url,
        save_path: savePath,
        channel: "qb",
        category_hint: mediaType === "tv" ? "tv" : "movie",
        subscription_id: subscriptionId,
        subscription_episode: item.episode,
      });
      // 从 found_resources 中移除已下载的
      const remaining = resources.filter(r => (r.info_hash || r.title) !== (item.info_hash || item.title));
      await api.updateSubscription(subscriptionId, { found_resources: remaining });
      onDownloaded();
    } catch (e) {
      console.error("[FoundResources] 下载失败:", e);
    } finally {
      setDownloading("");
    }
  }, [resources, subscriptionId, subscriptionTitle, savePath, mediaType, onDownloaded]);

  if (!resources.length) return null;

  const shown = expanded ? resources : resources.slice(0, 3);

  return (
    <div className="mt-2 space-y-1.5">
      <p className="text-[10px] text-amber-400 font-medium">🔔 找到 {resources.length} 条资源</p>
      {shown.map((item, i) => (
        <div key={item.info_hash || `res-${i}`}
          className={`flex items-center gap-2 px-2 py-1.5 rounded bg-white/[0.03] border border-white/[0.04] ${
            downloading === (item.info_hash || item.title) ? "opacity-50" : ""
          }`}>
          <div className="flex-1 min-w-0">
            <p className="text-[10px] text-slate-300 truncate" title={item.title}>{item.title}</p>
            <div className="flex items-center gap-1.5 mt-0.5">
              {item.resolution && <span className="text-[9px] text-blue-400 bg-blue-500/10 px-1 rounded">{item.resolution}</span>}
              {item.quality_tag && item.quality_tag !== "Unknown" && (
                <span className="text-[9px] text-slate-500">{item.quality_tag}</span>
              )}
              {item.size_gb > 0 && <span className="text-[9px] text-slate-600">{item.size_gb}GB</span>}
              {item.seeders > 0 && <span className="text-[9px] text-slate-600">↑{item.seeders}</span>}
              {item.episode !== null && <span className="text-[9px] text-emerald-400">E{String(item.episode).padStart(2, "0")}</span>}
            </div>
          </div>
          <button
            onClick={() => handleDownload(item)}
            disabled={!!downloading}
            className="px-2 py-1 text-[10px] text-blue-400 bg-blue-500/10 hover:bg-blue-500/20 rounded transition-all disabled:opacity-30 flex-shrink-0">
            下载
          </button>
        </div>
      ))}
      {resources.length > 3 && !expanded && (
        <button onClick={() => setExpanded(true)}
          className="text-[10px] text-slate-500 hover:text-slate-300 transition-colors">
          展开全部 ({resources.length} 条)
        </button>
      )}
      {expanded && resources.length > 3 && (
        <button onClick={() => setExpanded(false)}
          className="text-[10px] text-slate-500 hover:text-slate-300 transition-colors">
          收起
        </button>
      )}
    </div>
  );
}
