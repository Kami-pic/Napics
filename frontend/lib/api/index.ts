// API 聚合导出 — 保持 import { api } from "@/lib/api" 不变
import { searchApi } from "./search";
import { scrapeApi } from "./scrape";
import { organizeApi } from "./organize";
import { downloadApi } from "./download";
import { discoverApi } from "./discover";
import { subscribeApi } from "./subscribe";
import { configApi } from "./config";
import { systemApi } from "./system";
import { aiApi } from "./ai";
import { authApi } from "./auth";

export const api = {
  ...configApi,
  ...systemApi,
  ...searchApi,
  ...scrapeApi,
  ...organizeApi,
  ...downloadApi,
  ...discoverApi,
  ...subscribeApi,
  ...aiApi,
  ...authApi,
};
// subtitleApi 没有展开进来：它的 search / download 方法名与 searchApi、downloadApi
// 冲突，展开会静默覆盖。需要时直接 import { subtitleApi } from "@/lib/api/subtitle"。
