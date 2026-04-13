// 订阅状态管理 hook：启动时拉取订阅列表，提供订阅/取消/检查方法
"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "@/lib/api";

export interface SubscriptionItem {
  id: string;
  title: string;
  year: string;
  type: string;
  tmdb_id?: number;
  douban_id?: string;
  season?: number;
  state: string;
  mode: string;
  quality: string;
  poster: string;
  total_episode: number;
  downloaded_episodes: Record<string, any>;
  found_resources: any[];
  created_at: string;
}

export function useSubscriptions() {
  const [subscriptions, setSubscriptions] = useState<SubscriptionItem[]>([]);
  const [loading, setLoading] = useState(false);
  const loadedRef = useRef(false);

  // 启动时拉取一次
  const refresh = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.getSubscriptions();
      setSubscriptions(data || []);
    } catch (e) {
      console.error("[useSubscriptions] 拉取失败:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!loadedRef.current) {
      loadedRef.current = true;
      refresh();
    }
  }, [refresh]);

  // 检查某个影片是否已订阅（本地缓存判断，不发请求）
  const isSubscribed = useCallback((tmdbId?: number, title?: string, year?: string, season?: number): boolean => {
    return subscriptions.some(s => {
      if (s.state === "completed") return false;
      if (tmdbId && s.tmdb_id === tmdbId && s.season === season) return true;
      if (title && s.title === title && s.year === (year || "") && s.season === season) return true;
      return false;
    });
  }, [subscriptions]);

  // 新增订阅
  const subscribe = useCallback(async (data: Record<string, any>): Promise<{ status: string; message?: string; warning?: string }> => {
    try {
      const result = await api.addSubscription(data);
      if (result.status === "ok") {
        // 刷新列表
        await refresh();
      }
      return result;
    } catch (e: any) {
      return { status: "error", message: e.message || "订阅失败" };
    }
  }, [refresh]);

  // 删除订阅
  const unsubscribe = useCallback(async (id: string) => {
    try {
      await api.deleteSubscription(id);
      await refresh();
    } catch (e) {
      console.error("[useSubscriptions] 删除失败:", e);
    }
  }, [refresh]);

  return { subscriptions, loading, refresh, isSubscribed, subscribe, unsubscribe };
}
