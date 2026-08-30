// -*- coding: utf-8 -*-
/**
 * C2.8 研究任务状态 store (Zustand)。
 * 仅持有按 revision 合并后的事件状态，多任务相互隔离；
 * 合并规则全部来自 researchTaskState 纯逻辑，store 不复制规则。
 */
import { create } from 'zustand';

import {
  applyResearchTaskEvent,
  createResearchTaskState,
  type ResearchTaskState,
  type ResearchTaskStreamStateEvent,
} from '@/services/researchTaskState';

interface ResearchTaskStoreState {
  /** task_id 到本地合并状态的映射 */
  tasks: Record<string, ResearchTaskState>;
  /** 将事件帧合并进指定任务的本地状态 */
  applyEvent: (taskId: string, event: ResearchTaskStreamStateEvent) => void;
  /** 移除任务，恢复初始 */
  resetTask: (taskId: string) => void;
}

export const researchTaskStore = create<ResearchTaskStoreState>((set) => ({
  tasks: {},
  applyEvent: (taskId, event) =>
    set((state) => {
      const current = state.tasks[taskId] ?? createResearchTaskState(taskId);
      const merged = applyResearchTaskEvent(current, event);
      // 事件被忽略时保持原引用，避免触发多余渲染
      if (merged === current) {
        return state;
      }
      return { tasks: { ...state.tasks, [taskId]: merged } };
    }),
  resetTask: (taskId) =>
    set((state) => {
      if (!(taskId in state.tasks)) {
        return state;
      }
      const tasks = { ...state.tasks };
      delete tasks[taskId];
      return { tasks };
    }),
}));
