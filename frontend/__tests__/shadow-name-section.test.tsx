import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ShadowNameSection } from "@/components/detail/ShadowNameSection";

describe("ShadowNameSection", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));
  });

  it("文件夹模式保存标准名后只触发树刷新", async () => {
    const onRefresh = vi.fn();
    const onTreeRefresh = vi.fn();

    render(
      <ShadowNameSection
        path="\\\\NAS\\视频\\动画番\\军火女王"
        folderName="军火女王"
        folderShadowName="Jormungand"
        folderCleanName="军火女王 Jormungand"
        onRefresh={onRefresh}
        onTreeRefresh={onTreeRefresh}
      />,
    );

    fireEvent.click(screen.getByText("Jormungand"));
    fireEvent.click(screen.getByText("保存"));

    await waitFor(() => {
      expect(onTreeRefresh).toHaveBeenCalledTimes(1);
    });

    expect(onRefresh).not.toHaveBeenCalled();
  });

  it("文件夹模式保存英文名后只触发树刷新", async () => {
    const onRefresh = vi.fn();
    const onTreeRefresh = vi.fn();

    render(
      <ShadowNameSection
        path="\\\\NAS\\视频\\动画番\\军火女王"
        folderName="军火女王"
        folderShadowName="Jormungand"
        folderCleanName="军火女王"
        onRefresh={onRefresh}
        onTreeRefresh={onTreeRefresh}
      />,
    );

    fireEvent.click(screen.getByText("+ en"));
    fireEvent.click(screen.getByText("保存"));

    await waitFor(() => {
      expect(onTreeRefresh).toHaveBeenCalledTimes(1);
    });

    expect(onRefresh).not.toHaveBeenCalled();
  });
});
