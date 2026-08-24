// SSE 分帧器：把 fetch 流的字节 chunk 还原成按 `\n\n` 分隔的事件文本。
// 只做分帧，不解析 `data:` 前缀、不 JSON.parse、不管状态机、不处理业务错误。

/**
 * 按 SSE 事件边界（`\n\n`）迭代 fetch 响应流。
 *
 * - 跨 chunk 缓冲：一个事件被切成多个 chunk 时会拼回完整事件才吐出。
 * - 流结束时若缓冲区还有不以 `\n\n` 结尾的残留，照原样吐出最后一段。
 *   因此调用方解析 `data:` 时必须用 try/catch 兜住可能的半截 JSON。
 * - 调用方 `break` 出循环时会自动 cancel reader，不需要自己持有 reader。
 *
 * @param body fetch 响应体流
 * @param signal 可选取消信号，aborted 后停止读取
 */
export async function* iterSseEvents(
  body: ReadableStream<Uint8Array>,
  signal?: AbortSignal,
): AsyncGenerator<string> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      if (signal?.aborted) return;
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value as Uint8Array, { stream: true });
      const parts = buffer.split("\n\n");
      // 最后一段可能是被截断的半个事件，留到下一轮
      buffer = parts.pop() || "";
      for (const part of parts) yield part;
    }
    // flush 解码器里可能残留的多字节字符，再吐出尾部未闭合的那一段
    buffer += decoder.decode();
    if (buffer.length > 0) yield buffer;
  } finally {
    // 提前 break 时靠这里释放上游连接；正常读完时 cancel 是无害的空操作
    try {
      await reader.cancel();
    } catch {
      /* 流已关闭 */
    }
  }
}
