/** C2.5 研究任务的带鉴权 fetch streaming 封装。 */

export interface ResearchTaskStreamEvent {
  event_id: number;
  event_type: string;
  [key: string]: unknown;
}

export interface ResearchTaskStreamOptions {
  afterEventId?: number;
  onEvent: (event: ResearchTaskStreamEvent) => void;
  signal?: AbortSignal;
}

/**
 * 读取研究任务事件流。
 *
 * 新任务流必须使用 fetch，才能在 Authorization 请求头中携带密钥；
 * 密钥不得出现在 URL 或查询参数中。
 */
export async function streamResearchTaskEvents(
  taskId: string,
  options: ResearchTaskStreamOptions,
): Promise<void> {
  const apiKey = import.meta.env.VITE_API_KEY;
  if (!apiKey) {
    throw new Error('未配置 VITE_API_KEY，不能建立受认证的任务事件流');
  }

  const baseUrl = import.meta.env.VITE_API_BASE_URL || '';
  const params = new URLSearchParams();
  if (options.afterEventId !== undefined) {
    params.set('after_event_id', String(options.afterEventId));
  }
  const query = params.toString();
  const url = `${baseUrl}/api/research/tasks/${encodeURIComponent(taskId)}/events${query ? `?${query}` : ''}`;
  const response = await fetch(url, {
    headers: {
      Authorization: `Bearer ${apiKey}`,
      Accept: 'text/event-stream',
    },
    signal: options.signal,
  });
  if (!response.ok) {
    throw new Error(`任务事件流请求失败: HTTP ${response.status}`);
  }
  if (!response.body) {
    throw new Error('任务事件流响应缺少正文');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    let boundary = buffer.indexOf('\n\n');
    while (boundary >= 0) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const data = frame
        .split('\n')
        .filter((line) => line.startsWith('data:'))
        .map((line) => line.slice('data:'.length).trim())
        .join('\n');
      if (data) {
        options.onEvent(JSON.parse(data) as ResearchTaskStreamEvent);
      }
      boundary = buffer.indexOf('\n\n');
    }
    if (done) {
      return;
    }
  }
}
