// 锁定：流式接口返回 HTTP 错误时，必须把原因暴露出来，不能静默跳过
//
// 背景：fetch 对 4xx/5xx 不抛异常。之前 useLibrary.startScan 直接去读
// response.body 当 SSE 解析，错误响应体的每一行都不以 "data: " 开头，
// 于是全部被跳过 —— 表现为「进度条一闪而过、什么都没扫、也没有任何报错」，
// 用户无法得知真实原因（路径在容器内不存在）。
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { iterSseEvents } from "@/lib/sse/framer";

/** 构造一个 HTTP 错误响应（带 FastAPI 风格的 detail） */
function errorResponse(status: number, detail: string): Response {
  return {
    ok: false,
    status,
    json: async () => ({ detail }),
    body: {
      getReader: () => ({
        read: async () => ({ done: true, value: undefined }),
        cancel: async () => {},
      }),
    },
  } as unknown as Response;
}

/** 构造一个正常的 SSE 响应 */
function sseResponse(events: object[]): Response {
  const encoder = new TextEncoder();
  const chunks = events.map(e => encoder.encode(`data: ${JSON.stringify(e)}\n\n`));
  let i = 0;
  return {
    ok: true,
    status: 200,
    body: {
      getReader: () => ({
        read: async () =>
          i < chunks.length
            ? { done: false, value: chunks[i++] }
            : { done: true, value: undefined },
        cancel: async () => {},
      }),
    },
  } as unknown as Response;
}

/**
 * 复刻 startScan 里读取流的核心逻辑，用于验证错误处理契约。
 * 与 useLibrary.startScan 保持一致：先判 response.ok，再读流。
 */
async function consumeScanStream(response: Response, path: string) {
  if (!response.ok) {
    let detail = "";
    try {
      const err = await response.json();
      detail = typeof err?.detail === "string" ? err.detail : "";
    } catch { /* 非 JSON */ }
    const reason = detail === "Path does not exist"
      ? `路径不存在：${path}\n\n服务端访问不到这个目录。如果用 Docker 部署，请确认该目录已挂载进容器，并且容器内路径与这里填写的完全一致。`
      : (detail || `HTTP ${response.status}`);
    throw new Error(reason);
  }

  if (!response.body) return [];
  const received: any[] = [];
  for await (const part of iterSseEvents(response.body)) {
    if (!part.startsWith("data: ")) continue;
    try { received.push(JSON.parse(part.replace("data: ", ""))); } catch { /* skip */ }
  }
  return received;
}

describe("扫描流式接口的错误可见性", () => {
  it("路径不存在时必须抛出带说明的错误，而不是静默结束", async () => {
    const resp = errorResponse(400, "Path does not exist");
    await expect(consumeScanStream(resp, "/vol2/1000/video")).rejects.toThrow(/路径不存在/);
  });

  it("错误提示要包含 Docker 挂载的排查方向", async () => {
    const resp = errorResponse(400, "Path does not exist");
    await expect(consumeScanStream(resp, "/vol2/1000/video")).rejects.toThrow(/挂载/);
  });

  it("错误提示里要带上用户填的具体路径", async () => {
    const resp = errorResponse(400, "Path does not exist");
    await expect(consumeScanStream(resp, "/vol2/1000/video")).rejects.toThrow(/\/vol2\/1000\/video/);
  });

  it("其他后端错误也要把 detail 透出来", async () => {
    const resp = errorResponse(500, "内部错误：磁盘不可用");
    await expect(consumeScanStream(resp, "/media")).rejects.toThrow(/磁盘不可用/);
  });

  it("没有 detail 字段时退化为显示状态码", async () => {
    const resp = {
      ok: false,
      status: 502,
      json: async () => { throw new Error("not json"); },
    } as unknown as Response;
    await expect(consumeScanStream(resp, "/media")).rejects.toThrow(/502/);
  });

  it("正常 SSE 响应应能解析出全部事件", async () => {
    const resp = sseResponse([
      { type: "start", total: 2 },
      { type: "progress", current: 1 },
      { type: "done", total: 2 },
    ]);
    const events = await consumeScanStream(resp, "/media");
    expect(events).toHaveLength(3);
    expect(events[0].type).toBe("start");
    expect(events[2].type).toBe("done");
  });

  it("回归：错误响应体不能被当作 SSE 静默消费掉", async () => {
    // 这正是修复前的行为 —— 不抛错、返回空数组、界面毫无反应
    const resp = errorResponse(400, "Path does not exist");
    let threw = false;
    try {
      await consumeScanStream(resp, "/media");
    } catch {
      threw = true;
    }
    expect(threw).toBe(true);
  });
});
