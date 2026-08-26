// 「检测质量」按钮 —— 带失败原因
//
// 为什么要单独一个组件：这个按钮原来是 `await api.refreshQuality(...); onRefresh()`
// 外面套一个 `catch {}`，而后端不管成功失败都返回 {"status":"ok"}。三种失败
// （文件已不在该路径 / ffprobe 读不了这个文件 / 记录不在库里）在界面上完全一样，
// 都是"点了没反应，编码还是空的"。用户只能靠"把文件挪一下再重扫"来碰运气。
"use client";
import { useCallback, useState } from "react";
import { api } from "@/lib/api";
import LocateHint from "@/components/layout/LocateHint";

/** 后端 failed[].reason → 给用户看的话 */
const REASON_TEXT: Record<string, string> = {
  missing: "文件不在记录的路径上了，可能已被移动或删除。点顶部「快速同步」重新对账。",
  probe_failed: "ffprobe 读不出这个文件的元数据，通常是文件损坏，或者后缀与实际格式不符。",
  not_in_library: "这条记录不在媒体库里，先扫描一次。",
};

export interface QualityProbeButtonProps {
  filePath: string;
  onDone: () => void;
}

export default function QualityProbeButton({ filePath, onDone }: QualityProbeButtonProps) {
  const [busy, setBusy] = useState(false);
  // 失败原因用底部提示条显示（和「定位不到目录」共用一个组件）：标题行右侧
  // 塞不下一整句话，而只写「检测失败」等于没说。
  const [failure, setFailure] = useState("");
  const [ok, setOk] = useState(false);

  const dismiss = useCallback(() => setFailure(""), []);

  const run = async () => {
    setBusy(true);
    setFailure("");
    setOk(false);
    try {
      const result = await api.refreshQuality([filePath]);
      const failed = result.failed || [];
      if (failed.length > 0) {
        const reason = failed[0].reason;
        setFailure(REASON_TEXT[reason] || `检测失败（${reason}）`);
      } else if (result.probed === 0) {
        // 兜底：没失败也没探到，说明后端压根没走到探测那一步
        setFailure("没有拿到新的元数据。");
      } else {
        setOk(true);
      }
      onDone();
    } catch {
      setFailure("请求失败，检查后端是否在运行。");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <button onClick={run} disabled={busy}
        className="text-[11px] text-slate-500 hover:text-blue-400 transition-colors disabled:opacity-50"
        title="重新检测质量分">
        {busy ? "检测中..." : "检测质量"}
      </button>
      {ok && <span className="text-[11px] text-green-400">已更新</span>}
      <LocateHint message={failure} onDismiss={dismiss} duration={8000} icon="🔍" />
    </>
  );
}
