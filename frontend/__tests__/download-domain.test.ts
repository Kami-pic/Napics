// 锁定下载域的三件事：状态映射穷举、对账态不算失败、progress 只能合并不能替换。
import { describe, it, expect } from "vitest";

import {
  DOWNLOAD_POLL_INTERVAL_MS,
  DOWNLOAD_STATUS_META,
  collectClearableTaskIds,
  collectFailedTaskIds,
  describeDownloadStatus,
  describeRelocateResult,
  mergeProgressIntoTasks,
  needsPolling,
  type DownloadStatus,
} from "@/lib/domain/download";

/** 后端 download_manager 实际会赋的九个取值 */
const BACKEND_STATUSES: DownloadStatus[] = [
  "pending", "downloading", "completed", "failed",
  "lost", "unknown", "archived", "awaiting_confirm", "cancelled",
];

describe("下载状态映射", () => {
  it("穷举后端九个取值，一个不少", () => {
    expect(Object.keys(DOWNLOAD_STATUS_META).sort()).toEqual([...BACKEND_STATUSES].sort());
  });

  it("每个取值都有非空标签，不会出现空白标签", () => {
    for (const status of BACKEND_STATUSES) {
      expect(describeDownloadStatus(status).label).not.toBe("");
    }
  });

  it("lost / unknown 是对账态，不能映射成失败", () => {
    for (const status of ["lost", "unknown"] as const) {
      const meta = describeDownloadStatus(status);
      expect(meta.reconciling).toBe(true);
      expect(meta.tone).not.toBe("danger");
      expect(meta.terminal).toBe(false);
    }
    // 对照：真正的失败才是 danger
    expect(describeDownloadStatus("failed").tone).toBe("danger");
  });

  it("死配置 relocating / cloud_done 不在映射里", () => {
    expect(Object.keys(DOWNLOAD_STATUS_META)).not.toContain("relocating");
    expect(Object.keys(DOWNLOAD_STATUS_META)).not.toContain("cloud_done");
  });

  it("后端将来新增取值时兜底显示原始值，不是空白", () => {
    const meta = describeDownloadStatus("some_new_status");
    expect(meta.label).toBe("some_new_status");
    expect(meta.reconciling).toBe(true);
  });

  it("空状态也给得出人能看懂的标签", () => {
    expect(describeDownloadStatus("").label).toBe("未知状态");
  });

  it("终态判定：只有 completed / archived / failed / cancelled 是终态", () => {
    const terminal = BACKEND_STATUSES.filter(s => DOWNLOAD_STATUS_META[s].terminal);
    expect(terminal.sort()).toEqual(["archived", "cancelled", "completed", "failed"]);
  });

  it("全是终态时不需要继续轮询，有一个活跃就要轮询", () => {
    expect(needsPolling([{ status: "completed" }, { status: "archived" }])).toBe(false);
    expect(needsPolling([{ status: "completed" }, { status: "downloading" }])).toBe(true);
    // 对账态没确定，必须继续轮询（轮询停了对账和归位也就停了）
    expect(needsPolling([{ status: "unknown" }])).toBe(true);
    expect(needsPolling([])).toBe(false);
  });
});

describe("progress 合并", () => {
  const tasks = [
    { id: "t1", status: "downloading", progress: 0.1, speed: "" },
    { id: "t2", status: "completed", progress: 1, speed: "" },
    { id: "t3", status: "failed", progress: 0, speed: "" },
  ];

  it("progress 只含子集时，未提及的任务原样保留", () => {
    const merged = mergeProgressIntoTasks(tasks, [
      { id: "t1", progress: 0.7, speed: "12.5 MB/s" },
    ]);
    expect(merged).toHaveLength(3);
    expect(merged[0]).toMatchObject({ id: "t1", progress: 0.7, speed: "12.5 MB/s", status: "downloading" });
    expect(merged[1]).toMatchObject({ id: "t2", status: "completed" });
    expect(merged[2]).toMatchObject({ id: "t3", status: "failed" });
  });

  it("回归：绝不能把已完成任务抹掉（progress 里没有它们）", () => {
    const merged = mergeProgressIntoTasks(tasks, [{ id: "t1", progress: 0.9 }]);
    expect(merged.map(t => t.id)).toEqual(["t1", "t2", "t3"]);
  });

  it("progress 为空数组时列表不变", () => {
    expect(mergeProgressIntoTasks(tasks, [])).toEqual(tasks);
  });

  it("progress 里出现列表中没有的 id 时忽略，不凭空插入", () => {
    const merged = mergeProgressIntoTasks(tasks, [{ id: "t9", progress: 0.5 }]);
    expect(merged.map(t => t.id)).toEqual(["t1", "t2", "t3"]);
  });

  it("缺 id 的脏数据不会污染合并", () => {
    const merged = mergeProgressIntoTasks(tasks, [{ progress: 0.5 } as { id?: string }] as never);
    expect(merged).toEqual(tasks);
  });
});

describe("归位结果描述", () => {
  it("搬成功时给出文件数，且不需要用户介入", () => {
    const hint = describeRelocateResult({ relocate_status: "moved", relocated_count: 3 });
    expect(hint).toEqual({ label: "已归位 3 个文件", tone: "success", actionable: false });
  });

  it("同名跳过和沙盒为空是两种不同提示，都需要用户介入", () => {
    const skipped = describeRelocateResult({ relocate_status: "skipped_existing", relocated_count: 0 });
    const empty = describeRelocateResult({ relocate_status: "empty", relocated_count: 0 });
    expect(skipped?.actionable).toBe(true);
    expect(empty?.actionable).toBe(true);
    expect(skipped?.label).not.toBe(empty?.label);
  });

  it("归位失败是 danger", () => {
    expect(describeRelocateResult({ relocate_status: "failed", relocated_count: 0 })?.tone).toBe("danger");
  });

  it("还没归位时返回 null，界面不显示任何归位提示", () => {
    expect(describeRelocateResult({ relocate_status: "", relocated_count: 0 })).toBeNull();
  });
});

describe("轮询间隔", () => {
  it("与桌面面板保持同一个值（4s）", () => {
    expect(DOWNLOAD_POLL_INTERVAL_MS).toBe(4000);
  });
});


describe("批量清理的任务筛选", () => {
  const tasks = BACKEND_STATUSES.map(status => ({ id: `id-${status}`, status }));

  it("只把真正失败的算进「清理失败」", () => {
    expect(collectFailedTaskIds(tasks)).toEqual(["id-failed"]);
  });

  it("lost / unknown 不算失败 —— 它们是对账态，下一轮可能就恢复了", () => {
    const ids = collectFailedTaskIds(tasks);
    expect(ids).not.toContain("id-lost");
    expect(ids).not.toContain("id-unknown");
  });

  it("「清除已完成」只清终态，不碰对账中的任务", () => {
    const ids = collectClearableTaskIds(tasks);
    expect(ids.sort()).toEqual(
      ["id-completed", "id-archived", "id-failed", "id-cancelled"].sort(),
    );
    // 这两个原来会被一起删掉 —— 等于把正在核对的任务记录抹了
    expect(ids).not.toContain("id-lost");
    expect(ids).not.toContain("id-unknown");
    // 还没结束的也不能清
    expect(ids).not.toContain("id-downloading");
    expect(ids).not.toContain("id-pending");
    expect(ids).not.toContain("id-awaiting_confirm");
  });

  it("空列表返回空数组，调用方据此禁用按钮", () => {
    expect(collectFailedTaskIds([])).toEqual([]);
    expect(collectClearableTaskIds([])).toEqual([]);
  });
});
