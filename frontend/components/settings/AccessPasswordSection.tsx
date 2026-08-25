// 访问密码设置。默认不启用，用户主动设了才生效。
"use client";
import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api";

export default function AccessPasswordSection() {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.getAuthStatus()
      .then(status => { if (!cancelled) setEnabled(status.enabled); })
      .catch(() => { if (!cancelled) setEnabled(false); });
    return () => { cancelled = true; };
  }, []);

  const apply = useCallback(async (targetPassword: string) => {
    setBusy(true);
    setMessage(null);
    const res = await api.setAccessPassword(targetPassword, oldPassword);
    setBusy(false);
    if (res.ok) {
      setEnabled(!!res.enabled);
      setOldPassword("");
      setNewPassword("");
      setMessage({
        text: res.enabled
          ? "已启用。其他设备需要重新输入密码"
          : "已关闭，任何人都能访问",
        ok: true,
      });
    } else {
      setMessage({ text: res.error || "操作失败", ok: false });
    }
  }, [oldPassword]);

  if (enabled === null) return null;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <label className="text-sm font-medium text-slate-300">访问密码</label>
        {enabled
          ? <span className="text-[10px] px-1.5 py-0.5 bg-green-500/10 text-green-400 rounded">已启用</span>
          : <span className="text-[10px] px-1.5 py-0.5 bg-amber-500/10 text-amber-400 rounded">未启用</span>}
      </div>
      <p className="text-xs text-slate-600 leading-relaxed">
        不设密码时，同一局域网内任何设备打开 Napics 都能浏览服务端目录、播放和删除文件。
        设了密码后浏览器会记住 30 天。
        <br />
        这只能阻止误入，不足以把 Napics 暴露到公网 —— 外网访问请用 Tailscale / WireGuard。
      </p>

      {enabled && (
        <input
          type="password"
          value={oldPassword}
          onChange={e => setOldPassword(e.target.value)}
          placeholder="当前密码"
          aria-label="当前访问密码"
          autoComplete="current-password"
          className="w-full bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-slate-300 outline-none focus:border-blue-500/30"
        />
      )}

      <input
        type="password"
        value={newPassword}
        onChange={e => setNewPassword(e.target.value)}
        placeholder={enabled ? "新密码（至少 4 位）" : "设置密码（至少 4 位）"}
        aria-label="新访问密码"
        autoComplete="new-password"
        className="w-full bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-slate-300 outline-none focus:border-blue-500/30"
      />

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => void apply(newPassword)}
          disabled={busy || newPassword.length < 4}
          className="px-3 py-1.5 rounded-lg text-xs bg-blue-500/20 text-blue-300 border border-blue-500/30 hover:bg-blue-500/30 disabled:opacity-40"
        >
          {enabled ? "修改密码" : "启用"}
        </button>
        {enabled && (
          <button
            type="button"
            onClick={() => void apply("")}
            disabled={busy || !oldPassword}
            className="px-3 py-1.5 rounded-lg text-xs text-slate-400 hover:bg-white/[0.06] disabled:opacity-40"
          >
            关闭访问密码
          </button>
        )}
      </div>

      {message && (
        <p className={`text-xs ${message.ok ? "text-green-400" : "text-red-400"}`}>{message.text}</p>
      )}
    </div>
  );
}
