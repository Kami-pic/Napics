// AI 相关 API
import type { AISuggestion, OrganizeSnapshot } from "@/types";
import { request, BASE_URL } from "./base";

export const aiApi = {
  getAISuggestions: () => request<AISuggestion[]>(`${BASE_URL}/ai/suggest`),

  executeAISuggestions: (suggestions: AISuggestion[]) => request<any>(`${BASE_URL}/ai/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(suggestions),
  }),

  getAIHistory: () => request<OrganizeSnapshot[]>(`${BASE_URL}/ai/history`),

  rollbackAI: (snapshotId: number) => request<any>(`${BASE_URL}/ai/rollback?snapshot_id=${snapshotId}`, {
    method: "POST",
  }),

  // ── AI 集成 ──
  testAIConnection: () => request<{ success: boolean; response?: string; error?: string }>(`${BASE_URL}/ai/test`, { method: "POST" }),
  getAIStatus: () => request<any>(`${BASE_URL}/ai/status`),
  aiDiagnosis: () => request<any>(`${BASE_URL}/ai/diagnosis`, { method: "POST" }),
  aiSearchRecommend: (query: string, results: any[], localInfo?: any, signal?: AbortSignal) =>
    request<{ recommended: { index: number; reason: string }[] }>(`${BASE_URL}/ai/search-recommend`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, results, local_info: localInfo }),
      signal,
    }),

  // 影子名管理
  setShadowName: (path: string, shadowName: string, source: string = "manual") =>
    request<any>(`${BASE_URL}/media/shadow-name`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, shadow_name: shadowName, source }),
    }),

  clearShadowName: (path: string) =>
    request<any>(`${BASE_URL}/media/shadow-name`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    }),

  batchGenerateShadowNames: () =>
    request<any>(`${BASE_URL}/media/shadow-name/batch`, { method: "POST" }),
};
