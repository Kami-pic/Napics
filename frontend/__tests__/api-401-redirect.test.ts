// 锁定：任何接口返回 401 都统一跳登录页，且 promise 仍然 reject。
//
// 放在 request 里而不是让每个调用点自己判断 —— 后端一旦启用访问密码，
// 所有接口都会 401，逐个处理必然漏掉几个，表现成"页面一片空白且没有任何提示"。
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

import { request, LOGIN_PATH } from "@/lib/api/base";

const originalLocation = window.location;

function stubLocation(pathname: string, search = "") {
  Object.defineProperty(window, "location", {
    configurable: true,
    value: { pathname, search, href: "" } as unknown as Location,
  });
}

beforeEach(() => {
  vi.restoreAllMocks();
});

afterEach(() => {
  Object.defineProperty(window, "location", { configurable: true, value: originalLocation });
});

describe("request 的 401 处理", () => {
  it("401 时跳登录页并带上原地址", async () => {
    stubLocation("/m/search", "?q=%E6%95%99%E7%88%B6");
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response("", { status: 401 }),
    );

    await expect(request("/backend/library")).rejects.toThrow(/未授权/);
    expect(window.location.href).toBe(
      `${LOGIN_PATH}?next=${encodeURIComponent("/m/search?q=%E6%95%99%E7%88%B6")}`,
    );
  });

  it("已经在登录页时不再跳转（否则会自跳成循环）", async () => {
    stubLocation(LOGIN_PATH);
    vi.spyOn(global, "fetch").mockResolvedValue(new Response("", { status: 401 }));

    await expect(request("/backend/library")).rejects.toThrow(/未授权/);
    expect(window.location.href).toBe("");
  });

  it("401 一定 reject，不能让调用方拿着 undefined 继续走", async () => {
    stubLocation("/");
    vi.spyOn(global, "fetch").mockResolvedValue(new Response("", { status: 401 }));

    let resolved = false;
    await request("/backend/library").then(() => { resolved = true; }).catch(() => {});
    expect(resolved).toBe(false);
  });

  it("其他错误码照旧抛出，带上响应体便于排查", async () => {
    stubLocation("/");
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response("路径不存在", { status: 400 }),
    );

    await expect(request("/backend/library")).rejects.toThrow(/400.*路径不存在/);
    // 不是 401，不该跳转
    expect(window.location.href).toBe("");
  });

  it("正常响应原样返回", async () => {
    stubLocation("/");
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: 1 }), {
        status: 200, headers: { "content-type": "application/json" },
      }),
    );

    await expect(request<{ ok: number }>("/backend/library")).resolves.toEqual({ ok: 1 });
    expect(window.location.href).toBe("");
  });
});
