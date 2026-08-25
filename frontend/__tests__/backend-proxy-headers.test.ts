// @vitest-environment node
// `/backend` 代理的响应头策略。
//
// 断言对象是 handler 返回的 Headers 对象，不是网线上的实际字节 ——
// Node/Next 运行时对 body 与 header 的最终处理不在覆盖范围内。
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { GET, HEAD } from "@/app/backend/[[...path]]/route";

type Ctx = { params: Promise<{ path?: string[] }> };

const ctx = (...path: string[]): Ctx => ({ params: Promise.resolve({ path }) });

function stubUpstream(body: BodyInit | null, init: ResponseInit) {
  const fetchMock = vi.fn(async () => new Response(body, init));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

// route.ts 只 import type NextRequest，运行时用标准 Request 即可
const req = (headers: Record<string, string> = {}, method = "GET") =>
  new Request("http://localhost:3000/backend/playback/stream?path=x", { method, headers }) as never;

beforeEach(() => {
  vi.unstubAllGlobals();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("媒体响应保留长度头", () => {
  it("200 全量：Content-Length 透传", async () => {
    stubUpstream("0123456789", {
      status: 200,
      headers: { "content-type": "video/mp4", "content-length": "10", "accept-ranges": "bytes" },
    });
    const res = await GET(req(), ctx("playback", "stream"));
    expect(res.status).toBe(200);
    expect(res.headers.get("content-length")).toBe("10");
    expect(res.headers.get("accept-ranges")).toBe("bytes");
  });

  it("206 部分响应：Content-Length 与 Content-Range 都保留", async () => {
    stubUpstream("01", {
      status: 206,
      headers: {
        "content-type": "video/mp4",
        "content-length": "2",
        "content-range": "bytes 0-1/2048",
      },
    });
    const res = await GET(req({ range: "bytes=0-1" }), ctx("playback", "stream"));
    expect(res.status).toBe(206);
    expect(res.headers.get("content-length")).toBe("2");
    expect(res.headers.get("content-range")).toBe("bytes 0-1/2048");
  });

  it("HEAD：长度头保留，Safari 靠它拿到时长与 seek 能力", async () => {
    stubUpstream(null, {
      status: 200,
      headers: { "content-type": "video/mp4", "content-length": "2048", "accept-ranges": "bytes" },
    });
    const res = await HEAD(req({}, "HEAD"), ctx("playback", "stream"));
    expect(res.status).toBe(200);
    expect(res.headers.get("content-length")).toBe("2048");
  });

  it("416：非 200/206，不带长度头，但 Content-Range 仍透传", async () => {
    stubUpstream(null, {
      status: 416,
      headers: { "content-type": "video/mp4", "content-range": "bytes */2048" },
    });
    const res = await GET(req({ range: "bytes=99999-" }), ctx("playback", "stream"));
    expect(res.status).toBe(416);
    expect(res.headers.get("content-range")).toBe("bytes */2048");
    expect(res.headers.get("content-length")).toBeNull();
  });
});

describe("SSE 保持现状：不携带长度头", () => {
  it("text/event-stream 响应剥掉 Content-Length 并关闭缓冲", async () => {
    stubUpstream("data: hi\n\n", {
      status: 200,
      headers: { "content-type": "text/event-stream", "content-length": "10" },
    });
    const res = await GET(req(), ctx("sync"));
    expect(res.headers.get("content-length")).toBeNull();
    expect(res.headers.get("cache-control")).toBe("no-cache, no-transform");
    expect(res.headers.get("x-accel-buffering")).toBe("no");
  });
});

describe("压缩响应不保留长度头", () => {
  it("content-encoding 被剥掉时，长度头也必须一起剥掉", async () => {
    stubUpstream("compressed-bytes", {
      status: 200,
      headers: {
        "content-type": "application/json",
        "content-length": "16",
        "content-encoding": "gzip",
      },
    });
    const res = await GET(req(), ctx("library"));
    expect(res.headers.get("content-encoding")).toBeNull();
    expect(res.headers.get("content-length")).toBeNull();
  });
});
