// 封面组件 — 优先本地海报，fallback 到远程 poster_url
"use client";
import { useState, useRef, useEffect } from "react";
import { api } from "@/lib/api";
import { BASE_URL } from "@/lib/api/base";

export default function CardPoster({ name, path, cacheKey = 0, cover = false }: { name: string; path?: string; cacheKey?: number; cover?: boolean }) {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);
  const [remoteSrc, setRemoteSrc] = useState<string | null>(null);
  const [stage, setStage] = useState<"local" | "remote" | "done">("local");
  const everLoadedRef = useRef(false); // 曾经加载成功过就不再显示 spinner
  const bust = cacheKey ? `&_t=${cacheKey}` : "";
  const coverParam = cover ? "&cover=true" : "";
  const API_BASE = BASE_URL;
  const localSrc = path ? `${API_BASE}/scrape/poster?path=${encodeURIComponent(path)}${coverParam}${bust}` : null;

  // cacheKey 变化时重置状态（刮削/删除后刷新）
  useEffect(() => {
    setLoaded(false); setError(false); setRemoteSrc(null); setStage("local");
  }, [cacheKey, path]);

  const src = stage === "local" ? localSrc : stage === "remote" ? remoteSrc : null;

  return (
    <>
      {!loaded && !everLoadedRef.current && !error && stage !== "done" && src && <div className="absolute inset-0 flex items-center justify-center bg-[#111]"><div className="w-6 h-6 border-2 border-slate-800 border-t-slate-500 rounded-full animate-spin" /></div>}
      {(error || stage === "done" || !src) && <div className="absolute inset-0 bg-[#111] flex items-center justify-center"><span className="text-slate-700 text-3xl">🎬</span></div>}
      {/* lazy + async 解码：一屏几十张卡片时，eager/sync 会强制同时发起全部请求
          并阻塞渲染，NAS 上尤其明显。改为只加载进入视口的封面。 */}
      {src && stage !== "done" && <img src={src} alt="" loading="lazy" decoding="async"
        className={`absolute inset-0 w-full h-full object-cover transition-opacity duration-300 ${(loaded || everLoadedRef.current) ? "opacity-100" : "opacity-0"}`}
        onLoad={() => { setLoaded(true); everLoadedRef.current = true; }}
        onError={() => {
          if (stage === "local" && path && !cover) {
            // 本地没有，尝试读 NFO 拿远程 URL（仅刮削单元，聚合容器不读 NFO）
            setStage("done");
            api.readScrape(path, true).then(r => {
              if (r.status === "ok" && r.data?.poster_url) {
                const proxyUrl = `${API_BASE}/proxy/image?url=${encodeURIComponent(r.data.poster_url)}`;
                setRemoteSrc(proxyUrl);
                setStage("remote");
                setLoaded(false);
                setError(false);
              }
            }).catch(() => {});
          } else {
            setStage("done");
          }
        }} />}
    </>
  );
}
