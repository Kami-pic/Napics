// API 基础设施：request 函数 + BASE_URL

export const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
  return res.json();
}
