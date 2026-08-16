import { describe, expect, it } from "vitest";
import { derivePluginCapabilities } from "@/hooks/useInstalledPlugins";
import type { PluginInfo } from "@/lib/api/plugins";

function plugin(id: string, provides: string[]): PluginInfo {
  return {
    id,
    name: id,
    version: "1.0.0",
    description: "",
    category: "search",
    icon: "",
    requires_config: [],
    config_schema: [],
    depends_on: [],
    provides,
    risk_level: "high",
    installed: true,
    source: "external",
    registered: true,
    available: true,
    load_error: "",
  };
}

describe("derivePluginCapabilities", () => {
  it("识别当前分组 BT 搜索插件", () => {
    const capabilities = derivePluginCapabilities([
      plugin("search-bt-movie-tv", ["SearchProvider:yts", "SearchProvider:eztv"]),
    ]);

    expect(capabilities.hasSearch).toBe(true);
    expect(capabilities.hasPanSearch).toBe(false);
  });

  it("识别当前分组网盘搜索插件", () => {
    const capabilities = derivePluginCapabilities([
      plugin("search-pan-github", ["PanSearchProvider:gogopanso", "PanSearchProvider:github"]),
    ]);

    expect(capabilities.hasSearch).toBe(false);
    expect(capabilities.hasPanSearch).toBe(true);
  });

  it("忽略未安装插件声明的能力", () => {
    const item = plugin("search-yts", ["SearchProvider:yts"]);
    item.installed = false;

    expect(derivePluginCapabilities([item])).toEqual({
      hasSearch: false,
      hasPanSearch: false,
    });
  });
});


describe("插件运行状态", () => {
  it("忽略已安装但加载失败的插件", () => {
    const item = plugin("search-broken", ["SearchProvider:broken"]);
    item.available = false;
    item.load_error = "register failed";

    expect(derivePluginCapabilities([item])).toEqual({
      hasSearch: false,
      hasPanSearch: false,
    });
  });
});