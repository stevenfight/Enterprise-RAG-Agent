/** C2.8 研究任务事件按 revision 合并的纯逻辑。 */

export type ResearchTaskStatus =
  | 'pending'
  | 'running'
  | 'waiting_approval'
  | 'paused'
  | 'failed'
  | 'cancelled'
  | 'completed'
  | 'unknown';

/** 前端本地合并后的研究任务状态视图 */
export interface ResearchTaskState {
  taskId: string;
  status: ResearchTaskStatus;
  revision: number;
  lastEventId: number;
  resumed: boolean;
}

/** 与后端 SSE 契约对齐的事件帧，payload 字段展开在同一层 */
export interface ResearchTaskStreamStateEvent {
  event_id?: number;
  event_type: string;
  revision?: number;
  status?: string;
  [key: string]: unknown;
}

/** 创建任务初始状态；revision 为 -1 表示尚未收到任何事件 */
export function createResearchTaskState(taskId: string): ResearchTaskState {
  return { taskId, status: 'unknown', revision: -1, lastEventId: 0, resumed: false };
}

/**
 * 按 revision 合并事件：只有严格更新的 revision 才被应用，
 * 乱序或重放的旧事件不回退状态；window_end 等非状态事件原样忽略。
 */
export function applyResearchTaskEvent(
  state: ResearchTaskState,
  event: ResearchTaskStreamStateEvent,
): ResearchTaskState {
  if (event.event_type === 'run_created') {
    const revision = typeof event.revision === 'number' ? event.revision : 0;
    if (revision <= state.revision) {
      return state;
    }
    return {
      ...state,
      status: 'pending',
      revision,
      lastEventId: event.event_id ?? state.lastEventId,
    };
  }
  if (event.event_type === 'run_transitioned') {
    const { revision, status } = event;
    if (typeof revision !== 'number' || typeof status !== 'string') {
      return state;
    }
    if (revision <= state.revision) {
      return state;
    }
    return {
      ...state,
      status: status as ResearchTaskStatus,
      revision,
      lastEventId: event.event_id ?? state.lastEventId,
      resumed: state.status === 'paused' && status === 'running',
    };
  }
  // window_end 与其余未知事件不参与状态合并
  return state;
}
