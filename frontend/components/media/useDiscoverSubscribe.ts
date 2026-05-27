// 发现页订阅逻辑 hook：订阅/取消订阅/订阅配置弹窗
"use client";
import { useState, useCallback } from "react";
import type { DoubanHotItem } from "@/types";
import type { MediaDetail } from "./discoverUtils";
import { useSubscriptions } from "@/hooks/useSubscriptions";
import type { SubscribeConfig } from "./SubscribeConfigModal";

export interface UseDiscoverSubscribeParams {
  activeTabConfig: { mediaType?: string; [key: string]: any };
}

export function useDiscoverSubscribe({ activeTabConfig }: UseDiscoverSubscribeParams) {
  const { isSubscribed: _isSubscribed, subscribe: doSubscribe, unsubscribe: doUnsubscribe, subscriptions, refresh: refreshSubs } = useSubscriptions();

  // ── 订阅配置弹窗 ──
  const [subConfigOpen, setSubConfigOpen] = useState(false);
  const [subConfigItem, setSubConfigItem] = useState<DoubanHotItem | null>(null);
  const [subConfigDetail, setSubConfigDetail] = useState<MediaDetail | null>(null);
  const [subscribing, setSubscribing] = useState(false);
  const [justSubscribed, setJustSubscribed] = useState<Set<string>>(new Set());

  // 包装 isSubscribed：加入"刚订阅"的临时标记
  const isSubscribed = useCallback((tmdbId?: number, title?: string, year?: string, season?: number): boolean => {
    if (title && justSubscribed.has(`${title}|${year || ""}`)) return true;
    return _isSubscribed(tmdbId, title, year, season);
  }, [_isSubscribed, justSubscribed]);

  const handleSubscribe = useCallback(async (item: DoubanHotItem, d: MediaDetail | null) => {
    // 打开配置弹窗而非直接订阅
    setSubConfigItem(item);
    setSubConfigDetail(d);
    setSubConfigOpen(true);
  }, []);

  // 取消订阅：根据 title+year 找到订阅 ID 后删除
  const handleUnsubscribe = useCallback(async (item: DoubanHotItem) => {
    const sub = subscriptions.find(s =>
      s.title === item.title && s.year === (item.year || "") && s.state !== "completed"
    );
    if (!sub) return;
    await doUnsubscribe(sub.id);
    setJustSubscribed(prev => {
      const next = new Set(prev);
      next.delete(`${item.title}|${item.year || ""}`);
      return next;
    });
  }, [subscriptions, doUnsubscribe]);

  const handleSubscribeConfirm = useCallback(async (config: SubscribeConfig) => {
    if (!subConfigItem) return;
    setSubscribing(true);
    setSubConfigOpen(false);
    const item = subConfigItem;
    const d = subConfigDetail;
    try {
      // type 优先从 item.media_type 取（卡片级别），回退到 detail，最后用 tab 级别
      const mediaType = item.media_type || (d as any)?.media_type || (activeTabConfig.mediaType === "tv" ? "tv" : "movie");

      // 清洗名：优先 detail，回退 item
      const cnName = (d as any)?.clean_name_cn || item.clean_name_cn || item.title;
      const enName = (d as any)?.clean_name_en || item.clean_name_en || (d as any)?.english_title || item._tmdb_original_title || "";
      const originalName = (d as any)?.clean_name_original || item.clean_name_original || "";

      // 季号：从标题中提取（"第二季" → 2, "S02" → 2）
      let season: number | undefined;
      const seasonMatch = item.title.match(/第([一二三四五六七八九十\d]+)季|S(\d{1,2})/i);
      if (seasonMatch) {
        const cnNum = seasonMatch[1];
        const enNum = seasonMatch[2];
        if (enNum) {
          season = parseInt(enNum);
        } else if (cnNum) {
          const cnMap: Record<string, number> = { "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10 };
          season = cnMap[cnNum] || parseInt(cnNum) || undefined;
        }
      }

      const result = await doSubscribe({
        title: item.title,
        year: item.year || d?.year || "",
        type: mediaType,
        season,
        // 各平台 ID：从详情数据中尽可能获取
        tmdb_id: d?.tmdb_id || (d as any)?.external_ids?.tmdb_id || undefined,
        imdb_id: (d as any)?.external_ids?.imdb_id || "",
        douban_id: item.douban_id || undefined,
        poster: item.cover_url || d?.poster_url || "",
        // 订阅配置
        quality: config.quality,
        target_quality: config.target_quality,
        include: config.include,
        exclude: config.exclude,
        mode: config.mode,
        best_version: config.best_version,
        save_path: config.save_path,
        search_keyword: config.search_keyword,
        sources: config.sources,
        purpose: config.purpose,
        // 清洗名（后端用于构造 aliases 和搜索词）
        clean_name_cn: cnName,
        clean_name_en: enName,
        clean_name_original: originalName,
      });
      if (result.status === "ok") {
        setJustSubscribed(prev => new Set(prev).add(`${item.title}|${item.year || d?.year || ""}`));
      }
    } catch (e) {
      console.error("[Subscribe] 异常:", e);
    } finally {
      setSubscribing(false);
      setSubConfigItem(null);
      setSubConfigDetail(null);
    }
  }, [doSubscribe, activeTabConfig, subConfigItem, subConfigDetail]);

  return {
    // 订阅状态
    subscriptions, refreshSubs,
    subscribing,
    justSubscribed, setJustSubscribed,
    _isSubscribed,
    isSubscribed,
    handleSubscribe,
    handleUnsubscribe,
    handleSubscribeConfirm,
    // 订阅配置弹窗
    subConfigOpen, setSubConfigOpen,
    subConfigItem, setSubConfigItem,
    subConfigDetail, setSubConfigDetail,
  };
}
