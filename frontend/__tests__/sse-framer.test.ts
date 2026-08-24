// 锁定共享 SSE 分帧器的四种边界行为。
//
// 背景：分帧逻辑原先在 useLibrary(/scan)、Toolbar(/sync)、
// OrganizeProgress(/organize/full-stream) 和本目录的测试副本里各写了一份。
// 抽成 iterSseEvents 后，跨 chunk 拼接和尾部残留的处理必须由测试钉住。
import { describe, it, expect, vi } from "vitest";
import { iterSseEvents } from "@/lib/sse/framer";

/** 用给定的字节 chunk 序列构造一个最小 ReadableStream 替身 */
function streamOf(chunks: string[], onCancel?: () => void): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  const encoded = chunks.map(c => encoder.encode(c));
  let i = 0;
  return {
    getReader: () => ({
      read: async () =>
        i < encoded.length
          ? { done: false, value: encoded[i++] }
          : { done: true, value: undefined },
      cancel: async () => { onCancel?.(); },
    }),
  } as unknown as ReadableStream<Uint8Array>;
}

async function collect(stream: ReadableStream<Uint8Array>, signal?: AbortSignal) {
  const out: string[] = [];
  for await (const evt of iterSseEvents(stream, signal)) out.push(evt);
  return out;
}

describe("iterSseEvents", () => {
  it("单个 chunk 里的多个事件要逐个吐出", async () => {
    const events = await collect(streamOf(["data: a\n\ndata: b\n\ndata: c\n\n"]));
    expect(events).toEqual(["data: a", "data: b", "data: c"]);
  });

  it("一个事件被切成多个 chunk 时要拼回完整事件", async () => {
    const events = await collect(streamOf(['data: {"typ', 'e":"prog', 'ress"}\n\n']));
    expect(events).toEqual(['data: {"type":"progress"}']);
  });

  it("`\\n\\n` 恰好跨 chunk 边界时不能丢事件也不能切错", async () => {
    // 第一个 chunk 以 "\n" 结尾，第二个 chunk 以 "\n" 开头，边界正好劈开分隔符
    const events = await collect(streamOf(["data: a\n", "\ndata: b\n\n"]));
    expect(events).toEqual(["data: a", "data: b"]);
  });

  it("流结束时尾部没有 `\\n\\n` 的残留仍要吐出", async () => {
    const events = await collect(streamOf(["data: a\n\ndata: tail-no-terminator"]));
    expect(events).toEqual(["data: a", "data: tail-no-terminator"]);
  });

  it("尾部只剩空串时不吐出多余事件", async () => {
    const events = await collect(streamOf(["data: a\n\n"]));
    expect(events).toEqual(["data: a"]);
  });

  it("调用方提前 break 时要 cancel reader", async () => {
    const onCancel = vi.fn();
    const stream = streamOf(["data: a\n\ndata: b\n\n"], onCancel);
    for await (const evt of iterSseEvents(stream)) {
      expect(evt).toBe("data: a");
      break;
    }
    expect(onCancel).toHaveBeenCalled();
  });

  it("signal 已 abort 时不产出任何事件", async () => {
    const controller = new AbortController();
    controller.abort();
    const events = await collect(streamOf(["data: a\n\n"]), controller.signal);
    expect(events).toEqual([]);
  });
});
