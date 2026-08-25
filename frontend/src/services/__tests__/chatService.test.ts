// -*- coding: utf-8 -*-
/** SSE 日志安全回归测试。 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

const logger = vi.hoisted(() => ({
  info: vi.fn(),
  debug: vi.fn(),
  warn: vi.fn(),
  error: vi.fn(),
}));

vi.mock('@/utils/logger', () => ({ createLogger: () => logger }));

import { streamAgentQuery } from '@/services/chatService';

class EventSourceMock {
  static latest: EventSourceMock | undefined;
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  readyState = 1;
  close = vi.fn();

  constructor(_url: string) {
    EventSourceMock.latest = this;
  }
}

describe('streamAgentQuery', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    EventSourceMock.latest = undefined;
    vi.stubGlobal('EventSource', EventSourceMock);
    vi.spyOn(console, 'log').mockImplementation(() => {});
  });

  it('RW-R08-06: 不将原始 SSE 内容或工具输入写入浏览器日志', () => {
    streamAgentQuery('公开问题', {}, vi.fn());
    EventSourceMock.latest?.onmessage?.({
      data: JSON.stringify({
        type: 'action',
        step: 1,
        content: '内部执行细节',
        action_input: { token: 'secret-value' },
      }),
    } as MessageEvent);

    const logOutput = JSON.stringify([
      logger.info.mock.calls,
      logger.debug.mock.calls,
      logger.warn.mock.calls,
      logger.error.mock.calls,
      (console.log as ReturnType<typeof vi.fn>).mock.calls,
    ]);
    expect(logOutput).not.toContain('内部执行细节');
    expect(logOutput).not.toContain('secret-value');
  });
});
