// 锁定测试环境里 EventSource 替身可用。
// 这是搜索生命周期测试的前置：jsdom 本身不实现 EventSource，
// 一旦这个替身失效，所有"旧连接被 close"的断言会以 ReferenceError 形式炸掉，
// 报错方向完全指不到真正的原因。
import { describe, it, expect, vi, beforeEach } from "vitest";
import { mockEventSourceInstances, resetMockEventSource } from "./helpers/mockEventSource";

beforeEach(() => resetMockEventSource());

describe("EventSource 测试替身", () => {
  it("实例化不抛错，且记录了 url", () => {
    const es = new EventSource("/backend/api/search/stream?query=x");
    expect(es.url).toContain("/api/search/stream");
    expect(mockEventSourceInstances).toHaveLength(1);
  });

  it("close 可以被 spy，调用后 readyState 变 CLOSED", () => {
    const es = new EventSource("/x");
    const spy = vi.spyOn(es, "close");
    es.close();
    expect(spy).toHaveBeenCalledOnce();
    expect(es.readyState).toBe(2);
  });

  it("能驱动 onmessage 推送 JSON 事件", () => {
    const es = new EventSource("/x");
    const received: unknown[] = [];
    es.onmessage = e => received.push(JSON.parse((e as MessageEvent).data));
    mockEventSourceInstances[0].emitMessage({ type: "done", added: 1 });
    expect(received).toEqual([{ type: "done", added: 1 }]);
  });

  it("能驱动 onerror", () => {
    const es = new EventSource("/x");
    const onError = vi.fn();
    es.onerror = onError;
    mockEventSourceInstances[0].emitError();
    expect(onError).toHaveBeenCalledOnce();
  });
});
