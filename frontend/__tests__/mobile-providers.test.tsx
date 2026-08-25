// 锁定应用级缓存真的生效：插件列表和配置在一次会话里各只请求一次。
//
// 移动端切 Tab 会重挂载页面组件，如果每个页面自己请求一次，
// 在手机 + NAS 这种链路上就是每次切换都多等几百毫秒。
import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

import MobileProviders, { useMobileConfig, useMobilePlugins } from "@/components/mobile/MobileProviders";

const { mockApi } = vi.hoisted(() => ({
  mockApi: { getConfig: vi.fn() },
}));
vi.mock("@/lib/api", () => ({ api: mockApi }));

const { mockFetchPlugins } = vi.hoisted(() => ({
  mockFetchPlugins: vi.fn(),
}));
vi.mock("@/lib/api/plugins", () => ({ fetchPlugins: mockFetchPlugins }));

/** 两个互不相干的消费者，各自都读插件和配置 */
function ConsumerA() {
  const { hasDiscover, ready } = useMobilePlugins();
  const { defaultSavePath } = useMobileConfig();
  return <div data-testid="a">{ready ? String(hasDiscover) : "..."}|{defaultSavePath}</div>;
}

function ConsumerB() {
  const { hasPlayer } = useMobilePlugins();
  const { config } = useMobileConfig();
  return <div data-testid="b">{String(hasPlayer)}|{config?.scan_paths?.length ?? -1}</div>;
}

beforeEach(() => {
  mockApi.getConfig.mockReset();
  mockFetchPlugins.mockReset();
  mockApi.getConfig.mockResolvedValue({
    scan_paths: [String.raw`\\NAS\share\视频`, "/volume1/media"],
  });
  mockFetchPlugins.mockResolvedValue([
    { id: "feature-discover", installed: true, available: true, provides: [] },
    { id: "feature-player", installed: true, available: true, provides: [] },
  ]);
});

describe("MobileProviders", () => {
  it("两个消费者共享同一份数据，插件与配置各只请求一次", async () => {
    render(
      <MobileProviders>
        <ConsumerA />
        <ConsumerB />
      </MobileProviders>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("a")).toHaveTextContent("true");
      expect(screen.getByTestId("b")).toHaveTextContent("true|2");
    });

    expect(mockFetchPlugins).toHaveBeenCalledTimes(1);
    expect(mockApi.getConfig).toHaveBeenCalledTimes(1);
  });

  it("默认保存路径取第一个扫描路径", async () => {
    render(
      <MobileProviders>
        <ConsumerA />
      </MobileProviders>,
    );
    await waitFor(() => {
      expect(screen.getByTestId("a")).toHaveTextContent(String.raw`\\NAS\share\视频`);
    });
  });

  it("配置请求失败时标记 loadFailed，不卡在加载态", async () => {
    mockApi.getConfig.mockRejectedValue(new Error("后端没起来"));

    function FailProbe() {
      const { ready, loadFailed, defaultSavePath } = useMobileConfig();
      return <div data-testid="probe">{String(ready)}|{String(loadFailed)}|{defaultSavePath || "空"}</div>;
    }

    render(
      <MobileProviders>
        <FailProbe />
      </MobileProviders>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("probe")).toHaveTextContent("true|true|空");
    });
  });

  it("在 Provider 外使用会明确报错，而不是静默拿到空值", () => {
    function Outside() {
      useMobileConfig();
      return null;
    }
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<Outside />)).toThrow(/MobileProviders/);
    consoleError.mockRestore();
  });
});
