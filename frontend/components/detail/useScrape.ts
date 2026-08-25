// 刮削数据加载 hook：读取/执行刮削并管理缓存状态
import { useState, useEffect, useCallback } from "react";
import type { ScrapeResult, MatchConfidence } from "@/types";
import { api } from "@/lib/api";
import { getCached, setCached } from "./detailCache";

export function useScrape(name: string, path: string, autoScrape: boolean = false, noFallback: boolean = false) {
  const cacheKey = path || name;
  const cached = getCached(cacheKey);
  const [data, setData] = useState<ScrapeResult | null>(cached.scrapeData || null);
  // 首次读取是否还在路上。status 区分不了"还没读"和"读完了没有数据"
  // （两者都是 idle），调用方据此会把加载中误显示成"没有刮削信息"。
  const [reading, setReading] = useState(false);
  const [scrapeLoading, setScrapeLoading] = useState(cached.scrapeLoading || false);
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "failed" | "not_found">(
    (cached.scrapeStatus as any) || "idle"
  );
  const [confidence, setConfidence] = useState<MatchConfidence | null>(null);
  const [pendingConfirm, setPendingConfirm] = useState(false);

  // 同步刮削状态到缓存
  useEffect(() => {
    if (cacheKey) {
      setCached(cacheKey, { scrapeLoading, scrapeStatus: status, scrapeData: data });
    }
  }, [cacheKey, scrapeLoading, status, data]);

  // 恢复时：如果缓存显示 loading 但实际请求已丢失，重置
  useEffect(() => {
    if (cached.scrapeLoading && !scrapeLoading) {
      // 缓存说在 loading 但当前 hook 不是 loading → 可能是恢复后的状态
      // 保持 loading 状态，等请求自然完成或超时
    }
  }, [cacheKey]);

  const reload = useCallback((): Promise<void> => {
    if (!path) return Promise.resolve();
    return api.readScrape(path, noFallback).then(r => {
      if (r.status === "ok" && (r.data?.tmdb_id || r.data?.title)) { setData(r.data); setStatus("success"); }
      else { setData(null); setStatus("not_found"); }
    }).catch(() => { setData(null); setStatus("failed"); });
  }, [path]);

  useEffect(() => {
    if (!name && !path) return;
    let cancelled = false;
    // 如果缓存中有有效数据，直接用缓存
    const c = getCached(path || name);
    if (c.scrapeData?.tmdb_id || c.scrapeData?.title) {
      setData(c.scrapeData); setStatus("success");
      return;
    }
    if (c.scrapeLoading) {
      // 缓存说正在刮削，保持 loading 状态
      setScrapeLoading(true); setStatus("loading");
      return;
    }
    // 重置状态（path 变化时清除旧数据）
    setData(null); setStatus("idle"); setConfidence(null); setPendingConfirm(false);
    setReading(!!path);

    (async () => {
      try {
        if (path) {
          const r = await api.readScrape(path, noFallback);
          if (cancelled) return;
          if (r.status === "ok" && (r.data?.tmdb_id || r.data?.title)) {
            setData(r.data); setStatus("success");
            return;
          }
        }
        if (!cancelled) { setStatus("idle"); }
      } catch {
        if (!cancelled) setStatus("failed");
      } finally {
        if (!cancelled) setReading(false);
      }
    })();

    return () => { cancelled = true; };
  }, [name, path]);

  const rescrape = (): Promise<void> => {
    if (!path && !name) return Promise.resolve();
    setScrapeLoading(true); setStatus("loading"); setConfidence(null); setPendingConfirm(false);
    return api.executeScrape(path || name).then(r => {
      const d = r.self?.data || r.data;
      const conf = r.self?.confidence || r.confidence;
      if (conf) setConfidence(conf);
      if (d?.tmdb_id) {
        if (conf?.level === "medium") {
          setData(d); setStatus("success"); setPendingConfirm(true);
        } else if (conf?.level === "low") {
          setData(d); setStatus("success"); setPendingConfirm(true);
        } else {
          setData(d); setStatus("success");
        }
      } else {
        setStatus("not_found");
        // 刮削失败时保留已有数据，但提示用户
        alert("自动刮削未匹配到结果，请尝试「重新匹配」手动选择");
      }
    }).catch(() => { setStatus("failed"); alert("刮削请求失败"); }).finally(() => setScrapeLoading(false));
  };

  return { data, loading: scrapeLoading, reading, status, rescrape, reload, setData, confidence, pendingConfirm, setPendingConfirm };
}
