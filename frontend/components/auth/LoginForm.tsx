// 访问密码登录表单。桌面与移动端共用。
"use client";
import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { api } from "@/lib/api";

/** 登录后跳回的地址。只接受站内相对路径 —— 直接用 next 参数跳转等于开了个跳转中转站 */
function safeNext(raw: string | null): string {
  if (!raw) return "/";
  // 必须以单个 / 开头：// 开头会被浏览器当成协议相对 URL 跳到外站
  if (!raw.startsWith("/") || raw.startsWith("//")) return "/";
  return raw;
}

export default function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = safeNext(searchParams.get("next"));

  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [checking, setChecking] = useState(true);

  // 没启用访问密码、或者本来就已登录时，别把人卡在登录页上
  useEffect(() => {
    let cancelled = false;
    api.getAuthStatus()
      .then(status => {
        if (cancelled) return;
        if (!status.enabled || status.authenticated) router.replace(next);
        else setChecking(false);
      })
      .catch(() => { if (!cancelled) setChecking(false); });
    return () => { cancelled = true; };
  }, [router, next]);

  const submit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!password || submitting) return;
    setSubmitting(true);
    setError("");
    const res = await api.login(password);
    setSubmitting(false);
    if (res.ok) {
      // replace 而不是 push：不让返回键退回登录页
      router.replace(next);
    } else {
      setError(res.error || "登录失败");
      setPassword("");
    }
  }, [password, submitting, router, next]);

  if (checking) return null;

  return (
    <div
      className="flex min-h-dvh items-center justify-center bg-[var(--m-bg)] px-6"
      style={{ paddingTop: "var(--m-safe-top)", paddingBottom: "var(--m-safe-bottom)" }}
    >
      <form onSubmit={submit} className="flex w-full max-w-sm flex-col gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-lg font-semibold text-[var(--m-text)]">Napics</h1>
          <p className="text-xs text-[var(--m-text-dim)]">请输入访问密码</p>
        </div>

        <input
          type="password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          autoComplete="current-password"
          autoFocus
          aria-label="访问密码"
          className="rounded-[var(--m-radius)] border px-3 text-sm outline-none"
          style={{
            minHeight: "var(--m-touch-min)",
            background: "var(--m-surface)",
            borderColor: "var(--m-border)",
            color: "var(--m-text)",
          }}
        />

        {error && (
          <p role="alert" className="text-xs" style={{ color: "var(--m-danger)" }}>
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={!password || submitting}
          className="rounded-[var(--m-radius)] text-sm font-medium disabled:opacity-40"
          style={{
            minHeight: "var(--m-touch-min)",
            background: "var(--m-accent)",
            color: "var(--m-on-accent)",
          }}
        >
          {submitting ? "验证中…" : "进入"}
        </button>

        <p className="text-[11px] leading-relaxed text-[var(--m-text-dim)]">
          访问密码只用于阻止同一局域网内的其他设备误入，不足以把 Napics 暴露到公网。
          需要在外网访问请配置 Tailscale / WireGuard 这类私有网络。
        </p>
      </form>
    </div>
  );
}
