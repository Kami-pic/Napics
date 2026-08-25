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
import { subtitleApi } from "./subtitle";

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
  // subtitleApi 的 search / download 与 searchApi、downloadApi 撞名，
  // 展开进来会静默覆盖，所以挂成命名空间：api.subtitle.search(...)。
  subtitle: subtitleApi,
};
