/** C2.5 研究任务 fetch streaming 鉴权契约。 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { streamResearchTaskEvents } from '@/services/researchTaskStream';

describe('streamResearchTaskEvents', () => {
  beforeEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it('只通过 Authorization 头发送密钥，URL 不包含密钥', async () => {
    vi.stubEnv('VITE_API_KEY', 'task-stream-secret');
    const fetchMock = vi.fn().mockResolvedValue(
      new Response('data: {"event_id":7,"event_type":"run_created"}\n\n', { status: 200 }),
    );
    vi.stubGlobal('fetch', fetchMock);
    const onEvent = vi.fn();

    await streamResearchTaskEvents('research 011', { afterEventId: 5, onEvent });

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/research/tasks/research%20011/events?after_event_id=5',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer task-stream-secret',
          Accept: 'text/event-stream',
        }),
      }),
    );
    expect(fetchMock.mock.calls[0][0]).not.toContain('task-stream-secret');
    expect(onEvent).toHaveBeenCalledWith({ event_id: 7, event_type: 'run_created' });
  });
});
