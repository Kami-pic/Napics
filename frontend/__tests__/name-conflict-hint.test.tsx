// 名字没通过自检时必须看得见：候选值照常显示，但要说清它是候选。
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import NameConflictHint from "@/components/detail/NameConflictHint";

describe("NameConflictHint", () => {
  it("没有冲突时什么都不渲染", () => {
    const { container } = render(<NameConflictHint />);
    expect(container.firstChild).toBeNull();
    const empty = render(<NameConflictHint conflicts={[]} />);
    expect(empty.container.firstChild).toBeNull();
  });

  it("把冲突类型翻成人话", () => {
    render(<NameConflictHint conflicts={["nfo_season_vs_folder"]} />);
    expect(screen.getByText(/季号和目录名对不上/)).toBeTruthy();
    expect(screen.getByText(/候选值/)).toBeTruthy();
  });

  it("多条冲突都列出来", () => {
    render(<NameConflictHint conflicts={["nfo_season_vs_folder", "sibling_name_mismatch"]} />);
    expect(screen.getByText(/季号和目录名对不上/)).toBeTruthy();
    expect(screen.getByText(/分集标题/)).toBeTruthy();
  });

  it("认不出的类型原样显示，不吞掉", () => {
    render(<NameConflictHint conflicts={["some_new_check"]} />);
    expect(screen.getByText(/some_new_check/)).toBeTruthy();
  });
});
