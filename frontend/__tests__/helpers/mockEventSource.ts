// jsdom 完全不实现 EventSource（接口表里 0 处引用），
// 而 BT 主搜索就是靠 EventSource 收流的。测试要断言"新搜索开始时旧连接被 close"，
// 没有这个替身连 new EventSource() 都会 ReferenceError。
//
// 由 vitest.setup.ts 全局安装。测试里通过 mockEventSourceInstances 拿到实例，
// 用 emitMessage / emitError 驱动流。

type Listener = (event: MessageEvent | Event) => void;

/** 已创建的全部实例，按创建顺序排列（每个测试自行判断该看第几个） */
export const mockEventSourceInstances: MockEventSource[] = [];

export class MockEventSource {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 2;
  readonly CONNECTING = 0;
  readonly OPEN = 1;
  readonly CLOSED = 2;

  url: string;
  readyState = 0;
  withCredentials = false;
  onopen: Listener | null = null;
  onmessage: Listener | null = null;
  onerror: Listener | null = null;

  private listeners = new Map<string, Set<Listener>>();

  constructor(url: string | URL) {
    this.url = String(url);
    this.readyState = MockEventSource.OPEN;
    mockEventSourceInstances.push(this);
  }

  // 原型方法，测试可以 vi.spyOn(instance, "close")
  close() {
    this.readyState = MockEventSource.CLOSED;
  }

  addEventListener(type: string, listener: Listener) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type)!.add(listener);
  }

  removeEventListener(type: string, listener: Listener) {
    this.listeners.get(type)?.delete(listener);
  }

  dispatchEvent(event: Event) {
    this.listeners.get(event.type)?.forEach(l => l(event));
    return true;
  }

  /** 让这个连接推一条 message（data 会被 JSON.stringify） */
  emitMessage(data: unknown) {
    const event = { data: JSON.stringify(data), type: "message" } as MessageEvent;
    this.onmessage?.(event);
    this.listeners.get("message")?.forEach(l => l(event));
  }

  /** 让这个连接报错（对应 es.onerror） */
  emitError() {
    const event = { type: "error" } as Event;
    this.onerror?.(event);
    this.listeners.get("error")?.forEach(l => l(event));
  }
}

/** 把替身装到 globalThis 上，并清空上一轮的实例记录 */
export function installMockEventSource() {
  mockEventSourceInstances.length = 0;
  (globalThis as { EventSource?: unknown }).EventSource = MockEventSource;
}

/** 只清实例记录，保留已安装的构造函数（用在 beforeEach 里） */
export function resetMockEventSource() {
  mockEventSourceInstances.length = 0;
}
