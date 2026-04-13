// 订阅日历：时间线展示即将更新的剧集
"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";

interface CalendarEntry {
  subscription_id: string;
  title: string;
  season: number;
  episode: number;
  episode_title: string;
  air_date: string;
  downloaded: boolean;
  poster: string;
}

export default function SubscribeCalendar() {
  const [entries, setEntries] = useState<CalendarEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getSubscriptionCalendar()
      .then(data => setEntries(data || []))
      .catch(() => setEntries([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <p className="text-center py-8 text-xs text-slate-600">加载日历...</p>;
  }
  if (entries.length === 0) {
    return <p className="text-center py-8 text-xs text-slate-600">暂无剧集播出计划</p>;
  }

  // 按日期分组
  const grouped: Record<string, CalendarEntry[]> = {};
  for (const e of entries) {
    const key = e.air_date;
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(e);
  }

  const today = new Date().toISOString().slice(0, 10);
  const dates = Object.keys(grouped).sort();

  return (
    <div className="space-y-4">
      {dates.map(date => {
        const isToday = date === today;
        const isPast = date < today;
        return (
          <div key={date}>
            <div className="flex items-center gap-2 mb-2">
              <span className={`text-xs font-medium ${isToday ? "text-blue-400" : isPast ? "text-slate-600" : "text-slate-400"}`}>
                {isToday ? "今天" : date.slice(5)}
              </span>
              {isToday && <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-pulse" />}
            </div>
            <div className="space-y-1.5 pl-3 border-l border-white/[0.06]">
              {grouped[date].map(e => (
                <div key={`${e.subscription_id}-${e.episode}`}
                  className={`flex items-center gap-2 px-3 py-2 rounded-lg ${
                    e.downloaded ? "bg-emerald-500/5" : isPast ? "bg-white/[0.02]" : "bg-white/[0.03]"
                  }`}>
                  <span className={`text-[11px] font-medium ${e.downloaded ? "text-emerald-400" : "text-slate-300"}`}>
                    {e.title}
                  </span>
                  <span className="text-[10px] text-slate-500">S{String(e.season).padStart(2, "0")}E{String(e.episode).padStart(2, "0")}</span>
                  {e.episode_title && <span className="text-[10px] text-slate-600 truncate">{e.episode_title}</span>}
                  {e.downloaded && <span className="text-[10px] text-emerald-400 ml-auto flex-shrink-0">✓</span>}
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
