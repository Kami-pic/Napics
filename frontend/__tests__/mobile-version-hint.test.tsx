// 窄屏提示条：不做 UA 跳转，用户自己决定；关掉之后不再出现。
import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

import MobileVersionHint from "@/components/layout/MobileVersionHint";

const { mockPath } = vi.hoisted(() => ({ mockPath: { value: "/" } }));
vi.mock("next/navigation", () => ({ usePathname: () => mockPath.value }));

async function mount() {
  render(<MobileVersionHint />);
  await act(async () => { await Promise.resolve(); });
}

beforeEach(() => {
  localStorage.clear();
  mockPath.value = "/";
});

describe("窄屏提示条", () => {
  it("桌面页显示，链接指向 /m 且不发生跳转", async () => {
    await mount();
    const link = screen.getByRole("link", { name: "打开移动版" });
    expect(link.getAttribute("href")).toBe("/m");
  });

  it("靠 CSS 断点隐藏，不靠 JS 测宽度（转屏要立刻生效）", async () => {
    await mount();
    expect(screen.getByRole("link", { name: "打开移动版" }).closest("div")!.className)
      .toContain("md:hidden");
  });

  it("点「不再提示」后立刻消失，并且下次进来不再出现", async () => {
    await mount();
    fireEvent.click(screen.getByRole("button", { name: "不再提示" }));
    expect(screen.queryByRole("link", { name: "打开移动版" })).toBeNull();

    await mount();
    expect(screen.queryByRole("link", { name: "打开移动版" })).toBeNull();
  });

  it("移动版和登录页自己不显示这条提示", async () => {
    mockPath.value = "/m/library";
    await mount();
    expect(screen.queryByRole("link", { name: "打开移动版" })).toBeNull();

    mockPath.value = "/login";
    await mount();
    expect(screen.queryByRole("link", { name: "打开移动版" })).toBeNull();
  });
});
