// 本地状态角标的优先级。桌面 DiscoverCard 与移动端 MobileDiscoverCard 共用这一份判定，
// 判定漂了就会出现"同一批数据两端显示不一致"。
import { describe, it, expect } from "vitest";

import { resolveLocalStatusTag } from "@/lib/discoverStatus";

describe("resolveLocalStatusTag", () => {
  it("已有 + 订阅合并成一个标，不叠两个", () => {
    expect(resolveLocalStatusTag("owned_high", true)).toEqual({
      key: "owned_sub", text: "✓ 已有·订阅", tone: "owned",
    });
  });

  it("画质低 + 订阅是升级态", () => {
    expect(resolveLocalStatusTag("owned_low", true)).toEqual({
      key: "upgrade_sub", text: "↑ 升级·订阅", tone: "upgrade",
    });
  });

  it("只有本地时按画质分已有 / 可升级", () => {
    expect(resolveLocalStatusTag("owned_high", false)).toEqual({
      key: "owned", text: "✓ 已有", tone: "owned",
    });
    expect(resolveLocalStatusTag("owned_low", false)).toEqual({
      key: "upgrade", text: "↑ 可升级", tone: "upgrade",
    });
  });

  it("只有订阅时是订阅态", () => {
    expect(resolveLocalStatusTag("none", true)?.key).toBe("subscribed");
    expect(resolveLocalStatusTag(undefined, true)?.key).toBe("subscribed");
  });

  it("两者都没有就不给角标，不写「未拥有」这种噪音", () => {
    expect(resolveLocalStatusTag("none", false)).toBeNull();
    expect(resolveLocalStatusTag(undefined, undefined)).toBeNull();
    expect(resolveLocalStatusTag("")).toBeNull();
  });

  it("后端给了没见过的取值时按「没有」处理，不误报已有", () => {
    expect(resolveLocalStatusTag("owned_medium", false)).toBeNull();
  });
});
