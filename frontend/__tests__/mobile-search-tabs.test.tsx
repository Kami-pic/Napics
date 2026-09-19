// 资源搜索 BT/网盘 Tab：全名、可切换、带结果计数。
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

import MobileSearchTabs from "@/components/mobile/MobileSearchTabs";

describe("MobileSearchTabs", () => {
  it("用全名而非缩写", () => {
    render(<MobileSearchTabs tab="bt" onTabChange={() => {}} btCount={0} panCount={0} />);
    expect(screen.getByText("BT / 磁力")).toBeTruthy();
    expect(screen.getByText("网盘")).toBeTruthy();
  });

  it("有结果时显示各自计数", () => {
    render(<MobileSearchTabs tab="bt" onTabChange={() => {}} btCount={7} panCount={3} />);
    expect(screen.getByText("7")).toBeTruthy();
    expect(screen.getByText("3")).toBeTruthy();
  });

  it("点另一个 Tab 回调切换", () => {
    const onTabChange = vi.fn();
    render(<MobileSearchTabs tab="bt" onTabChange={onTabChange} btCount={0} panCount={0} />);
    fireEvent.click(screen.getByText("网盘"));
    expect(onTabChange).toHaveBeenCalledWith("pan");
  });

  it("当前 Tab 标记 aria-selected", () => {
    render(<MobileSearchTabs tab="pan" onTabChange={() => {}} btCount={0} panCount={0} />);
    const pan = screen.getByText("网盘").closest("button")!;
    expect(pan.getAttribute("aria-selected")).toBe("true");
  });
});
