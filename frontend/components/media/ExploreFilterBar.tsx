// 探索页筛选栏（铺开式设计，完全对齐 MoviePilot 筛选维度）
"use client";
import { useCallback, useState } from "react";

export interface ExploreFilters {
  sort: string;
  tags: string;         // 豆瓣=风格标签, TMDB=genre ID
  language: string;     // TMDB 语言
  year: string;         // 豆瓣年代 / Bangumi 年份
  voteAverage: number;  // 最低评分（豆瓣+TMDB 双滑块）
  voteMax: number;      // 最高评分（豆瓣+TMDB 双滑块）
  area: string;         // 豆瓣地区
  bangumiType: string;  // Bangumi cat 类别
}

export const DEFAULT_FILTERS: ExploreFilters = {
  sort: "", tags: "", language: "", year: "", voteAverage: 0, voteMax: 10, area: "", bangumiType: "",
};

export interface ExploreFilterBarProps {
  provider: string;
  type: string;
  filters: ExploreFilters;
  onChange: (filters: ExploreFilters) => void;
}

// ── 豆瓣 ──
// sort: T=近期热度（默认第一个） U=综合排序 S=高分优先 R=首播时间
// TOP250 作为豆瓣电影的特殊排序标签
const DOUBAN_MOVIE_SORTS = [
  { value: "T", label: "近期热度" },
  { value: "U", label: "综合排序" },
  { value: "S", label: "高分优先" },
  { value: "R", label: "首播时间" },
  { value: "TOP250", label: "TOP250" },
];
const DOUBAN_TV_SORTS = [
  { value: "T", label: "近期热度" },
  { value: "U", label: "综合排序" },
  { value: "S", label: "高分优先" },
  { value: "R", label: "首播时间" },
];
// 电影和剧集共用同一套风格标签（剧集额外包含综艺）
const DOUBAN_MOVIE_TAGS = [
  "喜剧", "爱情", "动作", "科幻", "动画", "悬疑", "犯罪", "惊悚",
  "冒险", "音乐", "历史", "奇幻", "恐怖", "战争", "传记", "歌舞",
  "武侠", "情色", "灾难", "西部", "纪录片", "短片",
];
const DOUBAN_TV_TAGS = [
  "喜剧", "爱情", "动作", "科幻", "动画", "悬疑", "犯罪", "惊悚",
  "冒险", "音乐", "历史", "奇幻", "恐怖", "战争", "传记", "歌舞",
  "武侠", "情色", "灾难", "西部", "纪录片", "短片", "综艺",
];
// 常用地区（"其他"代表所有不在列表中的冷门地区）
const DOUBAN_AREAS = [
  "华语", "欧美", "韩国", "日本", "中国大陆", "美国", "中国香港", "中国台湾",
  "英国", "法国", "德国", "意大利", "西班牙", "印度", "泰国",
];
// 被收进"其他"的冷门地区
const DOUBAN_OTHER_AREAS = [
  "俄罗斯", "加拿大", "澳大利亚", "爱尔兰", "瑞典", "巴西", "丹麦",
  "波兰", "荷兰", "比利时", "土耳其", "伊朗", "墨西哥", "阿根廷",
  "挪威", "芬兰", "新西兰", "以色列", "奥地利", "瑞士", "捷克",
  "南非", "马来西亚", "新加坡", "菲律宾", "印度尼西亚", "越南",
];
// 年代：固定年代段 + 动态最近6年
const DOUBAN_YEARS = (() => {
  const now = new Date().getFullYear();
  const dynamic = Array.from({ length: 6 }, (_, i) => String(now - i));
  return [
    "2020年代", "2010年代", "2000年代", "90年代", "80年代", "70年代", "60年代",
    ...dynamic,
  ];
})();

// ── TMDB ──
const TMDB_MOVIE_SORTS = [
  { value: "popularity.desc", label: "热度降序" },
  { value: "popularity.asc", label: "热度升序" },
  { value: "release_date.desc", label: "上映日期降序" },
  { value: "release_date.asc", label: "上映日期升序" },
  { value: "vote_average.desc", label: "评分降序" },
  { value: "vote_average.asc", label: "评分升序" },
];
const TMDB_TV_SORTS = [
  { value: "popularity.desc", label: "热度降序" },
  { value: "popularity.asc", label: "热度升序" },
  { value: "first_air_date.desc", label: "首播日期降序" },
  { value: "first_air_date.asc", label: "首播日期升序" },
  { value: "vote_average.desc", label: "评分降序" },
  { value: "vote_average.asc", label: "评分升序" },
];
const TMDB_LANGUAGES = [
  { value: "", label: "全部" }, { value: "zh", label: "中文" }, { value: "en", label: "英语" },
  { value: "ja", label: "日语" }, { value: "ko", label: "韩语" },
  { value: "fr", label: "法语" }, { value: "de", label: "德语" },
  { value: "es", label: "西班牙语" }, { value: "it", label: "意大利语" },
  { value: "ru", label: "俄语" }, { value: "pt", label: "葡萄牙语" },
  { value: "ar", label: "阿拉伯语" }, { value: "hi", label: "印地语" },
  { value: "th", label: "泰语" },
];
const TMDB_GENRES_MOVIE = [
  { value: "28", label: "动作" }, { value: "12", label: "冒险" }, { value: "16", label: "动画" },
  { value: "35", label: "喜剧" }, { value: "80", label: "犯罪" }, { value: "99", label: "纪录片" },
  { value: "18", label: "剧情" }, { value: "10751", label: "家庭" }, { value: "14", label: "奇幻" },
  { value: "36", label: "历史" }, { value: "27", label: "恐怖" }, { value: "10402", label: "音乐" },
  { value: "9648", label: "悬疑" }, { value: "10749", label: "爱情" }, { value: "878", label: "科幻" },
  { value: "10770", label: "电视电影" }, { value: "53", label: "惊悚" }, { value: "10752", label: "战争" },
  { value: "37", label: "西部" },
];
const TMDB_GENRES_TV = [
  { value: "10759", label: "动作冒险" }, { value: "16", label: "动画" }, { value: "35", label: "喜剧" },
  { value: "80", label: "犯罪" }, { value: "99", label: "纪录片" }, { value: "18", label: "剧情" },
  { value: "10751", label: "家庭" }, { value: "10762", label: "儿童" }, { value: "9648", label: "悬疑" },
  { value: "10763", label: "新闻" }, { value: "10764", label: "真人秀" }, { value: "10765", label: "科幻奇幻" },
  { value: "10766", label: "肥皂剧" }, { value: "10767", label: "脱口秀" }, { value: "10768", label: "战争政治" },
  { value: "37", label: "西部" },
];

// ── Bangumi ──
const BGM_SORTS = [{ value: "rank", label: "排名" }, { value: "date", label: "日期" }];
const BGM_CATS = [
  { value: "0", label: "其他" }, { value: "1", label: "TV" },
  { value: "2", label: "OVA" }, { value: "3", label: "Movie" }, { value: "5", label: "WEB" },
];
const BGM_YEARS = (() => {
  const now = new Date().getFullYear();
  return Array.from({ length: 10 }, (_, i) => String(now - i));
})();

// ── UI 组件 ──
function Pill({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick}
      className={`px-2.5 py-1 rounded-md text-[13px] leading-5 transition-colors whitespace-nowrap ${
        active ? "bg-white/10 text-white font-medium" : "text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]"
      }`}>
      {label}
    </button>
  );
}

function FilterRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-1 flex-wrap min-h-[32px]">
      <span className="text-[13px] text-slate-500 w-10 flex-shrink-0">{label}</span>
      {children}
    </div>
  );
}

/** 评分双滑块（最低~最高） */
function RangeSlider({ min, max, onChange }: { min: number; max: number; onChange: (min: number, max: number) => void }) {
  return (
    <div className="flex items-center gap-2 flex-1 max-w-[360px]">
      <input type="range" min={0} max={10} step={1} value={min}
        onChange={(e) => { const v = parseFloat(e.target.value); onChange(Math.min(v, max), max); }}
        className="flex-1 h-1 bg-white/10 rounded-full appearance-none cursor-pointer
          [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3
          [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-blue-500 [&::-webkit-slider-thumb]:cursor-pointer" />
      <span className="text-[12px] text-slate-500">~</span>
      <input type="range" min={0} max={10} step={1} value={max}
        onChange={(e) => { const v = parseFloat(e.target.value); onChange(min, Math.max(v, min)); }}
        className="flex-1 h-1 bg-white/10 rounded-full appearance-none cursor-pointer
          [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3
          [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-blue-500 [&::-webkit-slider-thumb]:cursor-pointer" />
      <span className="text-[13px] text-slate-300 w-16 text-right tabular-nums">
        {min === 0 && max === 10 ? "不限" : `${min}~${max}`}
      </span>
    </div>
  );
}

export default function ExploreFilterBar({ provider, type, filters, onChange }: ExploreFilterBarProps) {
  const set = useCallback((key: keyof ExploreFilters, value: string | number) => {
    onChange({ ...filters, [key]: value });
  }, [filters, onChange]);

  const [showOtherAreas, setShowOtherAreas] = useState(false);

  const isDouban = provider === "douban";
  const isTmdb = provider === "tmdb";
  const isBangumi = provider === "bangumi";
  const isOtherArea = DOUBAN_OTHER_AREAS.includes(filters.area);

  return (
    <div className="flex flex-col gap-0.5 py-2">
      {/* 排序（豆瓣电影多一个 TOP250） */}
      <FilterRow label="排序">
        {(isDouban
          ? (type === "movie" ? DOUBAN_MOVIE_SORTS : DOUBAN_TV_SORTS)
          : isTmdb ? (type === "tv" ? TMDB_TV_SORTS : TMDB_MOVIE_SORTS) : BGM_SORTS
        ).map(s => (
          <Pill key={s.value} label={s.label} active={filters.sort === s.value} onClick={() => set("sort", s.value)} />
        ))}
      </FilterRow>

      {/* 豆瓣：风格（剧集额外包含综艺） */}
      {isDouban && (
        <FilterRow label="风格">
          <Pill label="全部" active={!filters.tags} onClick={() => set("tags", "")} />
          {(type === "tv" ? DOUBAN_TV_TAGS : DOUBAN_MOVIE_TAGS).map(t => (
            <Pill key={t} label={t} active={filters.tags === t} onClick={() => set("tags", t)} />
          ))}
        </FilterRow>
      )}
      {/* 豆瓣：地区（常用 + "其他"聚合冷门地区） */}
      {isDouban && (
        <FilterRow label="地区">
          <Pill label="全部" active={!filters.area && !isOtherArea} onClick={() => { set("area", ""); setShowOtherAreas(false); }} />
          {DOUBAN_AREAS.map(a => (
            <Pill key={a} label={a} active={filters.area === a} onClick={() => { set("area", a); setShowOtherAreas(false); }} />
          ))}
          <Pill label="其他" active={isOtherArea || showOtherAreas} onClick={() => setShowOtherAreas(!showOtherAreas)} />
        </FilterRow>
      )}
      {/* 展开的冷门地区 */}
      {isDouban && showOtherAreas && (
        <FilterRow label="">
          {DOUBAN_OTHER_AREAS.map(a => (
            <Pill key={a} label={a} active={filters.area === a} onClick={() => set("area", a)} />
          ))}
        </FilterRow>
      )}
      {/* 豆瓣：年代 */}
      {isDouban && (
        <FilterRow label="年代">
          <Pill label="全部" active={!filters.year} onClick={() => set("year", "")} />
          {DOUBAN_YEARS.map(y => (
            <Pill key={y} label={y} active={filters.year === y} onClick={() => set("year", y)} />
          ))}
        </FilterRow>
      )}
      {/* 豆瓣：评分双滑块 */}
      {isDouban && (
        <FilterRow label="评分">
          <RangeSlider min={filters.voteAverage} max={filters.voteMax}
            onChange={(min, max) => onChange({ ...filters, voteAverage: min, voteMax: max })} />
        </FilterRow>
      )}

      {/* TMDB：风格 */}
      {isTmdb && (
        <FilterRow label="风格">
          <Pill label="全部" active={!filters.tags} onClick={() => set("tags", "")} />
          {(type === "tv" ? TMDB_GENRES_TV : TMDB_GENRES_MOVIE).map(g => (
            <Pill key={g.value} label={g.label} active={filters.tags === g.value} onClick={() => set("tags", g.value)} />
          ))}
        </FilterRow>
      )}
      {/* TMDB：语言 */}
      {isTmdb && (
        <FilterRow label="语言">
          {TMDB_LANGUAGES.map(l => (
            <Pill key={l.value} label={l.label} active={filters.language === l.value} onClick={() => set("language", l.value)} />
          ))}
        </FilterRow>
      )}
      {/* TMDB：评分双滑块 */}
      {isTmdb && (
        <FilterRow label="评分">
          <RangeSlider min={filters.voteAverage} max={filters.voteMax}
            onChange={(min, max) => onChange({ ...filters, voteAverage: min, voteMax: max })} />
        </FilterRow>
      )}

      {/* Bangumi：类别 */}
      {isBangumi && (
        <FilterRow label="类别">
          <Pill label="全部" active={!filters.bangumiType} onClick={() => set("bangumiType", "")} />
          {BGM_CATS.map(t => (
            <Pill key={t.value} label={t.label} active={filters.bangumiType === t.value} onClick={() => set("bangumiType", t.value)} />
          ))}
        </FilterRow>
      )}
      {/* Bangumi：年份 */}
      {isBangumi && (
        <FilterRow label="年份">
          <Pill label="全部" active={!filters.year} onClick={() => set("year", "")} />
          {BGM_YEARS.map(y => (
            <Pill key={y} label={y} active={filters.year === y} onClick={() => set("year", y)} />
          ))}
        </FilterRow>
      )}
    </div>
  );
}
