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
};
