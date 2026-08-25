// 复制到剪贴板，带降级路径。
//
// `navigator.clipboard` 只在安全上下文（https 或 localhost）可用。
// 而 Napics 的典型用法正是「局域网 http 访问 NAS 的 IP」—— 那是非安全上下文，
// iOS Safari 和 Android Chrome 上 navigator.clipboard 直接是 undefined。
// 只写 clipboard API 的话，手机上点复制毫无反应。

export type CopyResult = "ok" | "failed";

/** 老办法：隐藏 textarea + execCommand，非安全上下文下仍然可用 */
function copyViaTextarea(text: string): boolean {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  // 不能用 display:none / visibility:hidden —— 那样选不中内容
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.top = "-9999px";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  try {
    textarea.select();
    textarea.setSelectionRange(0, text.length);
    return document.execCommand("copy");
  } catch {
    return false;
  } finally {
    document.body.removeChild(textarea);
  }
}

export async function copyText(text: string): Promise<CopyResult> {
  if (!text) return "failed";

  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return "ok";
    } catch {
      // 权限被拒或非安全上下文，继续走降级
    }
  }

  return copyViaTextarea(text) ? "ok" : "failed";
}
