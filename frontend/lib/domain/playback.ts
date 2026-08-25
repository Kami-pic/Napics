// 播放域：原生可播扩展名候选 + 播放/字幕 URL 构造。桌面与移动端共用。
//
// 存在的理由是**编码次数**。后端 `/playback/subtitles` 返回的 `url` 字段里
// 路径已经 `quote()` 过一次；调用方再 `encodeURIComponent` 一遍，`%` 会变成
// `%25`，后端 unquote 后拿到的是带字面 `%20` 的路径 → 文件不存在。
// 所以字幕 URL 的规则是「只补前缀，不再编码」，流 URL 的规则是「自己编码一次」。
import { BASE_URL } from "@/lib/api/base";

/**
 * 交给浏览器直接播放的扩展名候选。
 *
 * 只是**初筛**，不承诺同扩展名一定可播 —— 容器能认不等于里面的编码能解
 * （mp4 装 HEVC 在 Chrome 上就播不了）。真正的判定要配合 `canPlayType()`，
 * 播不动时还要靠 media `error` 事件兜底。
 */
export const NATIVE_VIDEO_EXTENSION_CANDIDATES = ["mp4", "m4v", "webm", "mov"] as const;

/** 扩展名 → MIME，喂给 `canPlayType()` */
const EXTENSION_MIME: Record<string, string> = {
  mp4: "video/mp4",
  m4v: "video/mp4",
  webm: "video/webm",
  mov: "video/quicktime",
};

/**
 * 后端是不是跨源的。
 *
 * 默认 `BASE_URL` 是相对路径 `/backend`（同源，走 Next 代理）；只有显式设了
 * `NEXT_PUBLIC_API_URL` 直连独立后端时才是绝对地址。
 *
 * 这个判断决定 `<video>` 要不要加 `crossOrigin` —— **两种情况必须区别对待**：
 * 同源下加了它会把媒体请求变成 CORS 模式，而 `anonymous` 的凭据策略不发 cookie，
 * 开了访问密码后 `/playback/*` 会直接 401（它不在鉴权白名单里，
 * 而访问密码走 cookie 正是因为 `<video src>` 带不了自定义头），
 * 视频从"能播"退回"整个播不了"。
 */
export function isCrossOriginBackend(): boolean {
  return /^https?:\/\//i.test(BASE_URL);
}

/** 取小写扩展名（不带点）。无扩展名返回空串 */
export function videoExtension(path: string): string {
  const name = path.split(/[\\/]/).pop() || "";
  const idx = name.lastIndexOf(".");
  if (idx <= 0) return "";
  return name.slice(idx + 1).toLowerCase();
}

/** 扩展名是否在原生候选集内 */
export function isNativeExtensionCandidate(path: string): boolean {
  return (NATIVE_VIDEO_EXTENSION_CANDIDATES as readonly string[]).includes(videoExtension(path));
}

/**
 * 结合扩展名候选与 `canPlayType()` 判断能否原生播放。
 *
 * `video` 传 null 时只做扩展名初筛。注意 jsdom 里 `canPlayType()` 恒返回 `""`，
 * 测试要走"可播"分支必须 stub 它。
 */
export function canPlayNatively(path: string, video: HTMLVideoElement | null): boolean {
  if (!isNativeExtensionCandidate(path)) return false;
  if (!video || typeof video.canPlayType !== "function") return true;
  const mime = EXTENSION_MIME[videoExtension(path)];
  if (!mime) return true;
  return video.canPlayType(mime) !== "";
}

/** `/playback/stream` 的 URL。path 在这里编码一次，调用方不要预先编码 */
export function buildStreamUrl(path: string, audioIndex = 0): string {
  const params = new URLSearchParams({ path });
  if (audioIndex > 0) params.set("audio_index", String(audioIndex));
  return `${BASE_URL}/playback/stream?${params.toString()}`;
}

/** `/playback/subtitles` 列表接口的 URL */
export function buildSubtitleListUrl(path: string): string {
  return `${BASE_URL}/playback/subtitles?${new URLSearchParams({ path }).toString()}`;
}

/**
 * 把后端返回的字幕 url 变成可直接请求的地址。
 *
 * 后端给的是 `/playback/subtitle/file?path=<已 quote>`，这里**只补 BASE_URL**。
 * 绝对地址（http/https 开头）原样返回。再编码一次就会双重编码，见文件头注释。
 */
export function resolveSubtitleUrl(backendUrl: string): string {
  if (!backendUrl) return "";
  if (/^https?:\/\//i.test(backendUrl)) return backendUrl;
  if (backendUrl.startsWith(BASE_URL)) return backendUrl;
  return `${BASE_URL}${backendUrl.startsWith("/") ? "" : "/"}${backendUrl}`;
}
