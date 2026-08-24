// -*- coding: utf-8 -*-
/**
 * DagFlow 组件单元测试
 * (G6 Canvas 渲染层不做深入测试, 聚焦: 数据稳定比较 / 空状态 / 接口)
 */
import { render, screen, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

const { mockGraphInstance, MockGraph } = vi.hoisted(() => {
  const inst = { render: vi.fn(), destroy: vi.fn(), on: vi.fn() };
  return {
    mockGraphInstance: inst,
    MockGraph: vi.fn().mockImplementation(function () { return inst; }),
  };
});

vi.mock('@antv/g6', () => ({
  Graph: MockGraph,
}));

import DagFlow, { type DagNode } from '@/components/dag/DagFlow';

/** 标准 DAG 节点 */
const mockNodes: DagNode[] = [
  { id: 'T1', label: '检索营收', type: 'retrieve', description: '检索三家运营商营收', tool_name: 'retrieve', status: 'completed' },
  { id: 'T2', label: '计算对比', type: 'compare', description: '对比营收数据', tool_name: 'compare', status: 'completed' },
  { id: 'T3', label: '生成图表', type: 'chart', description: '生成柱状图', tool_name: 'chart', status: 'pending' },
];

/** 标准 DAG 边 */
const mockEdges = [
  { source: 'T1', target: 'T2' },
  { source: 'T2', target: 'T3' },
];

describe('DagFlow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('基础渲染', () => {
    it('空节点列表应该显示空状态提示', () => {
      render(<DagFlow nodes={[]} edges={[]} />);
      expect(screen.getByText('暂无任务规划数据')).toBeInTheDocument();
      expect(screen.getByText('输入查询后，Agent 会自动生成任务 DAG')).toBeInTheDocument();
    });

    it('有节点时应该渲染容器 div', () => {
      const { container } = render(<DagFlow nodes={mockNodes} edges={mockEdges} />);
      const divs = container.querySelectorAll('div[style]');
      const canvasContainer = Array.from(divs).find(
        d => d.getAttribute('style')?.includes('overflow: hidden')
      );
      expect(canvasContainer).toBeDefined();
    });

    it('应该传递正确的高度', () => {
      const { container } = render(<DagFlow nodes={mockNodes} edges={mockEdges} height={500} />);
      const divs = container.querySelectorAll('div[style]');
      const canvasContainer = Array.from(divs).find(
        d => d.getAttribute('style')?.includes('overflow: hidden')
      );
      expect(canvasContainer?.getAttribute('style')).toContain('height: 500px');
    });
  });

  describe('空节点状态', () => {
    it('空数组应显示占位 UI', () => {
      const { container } = render(<DagFlow nodes={[]} edges={[]} />);
      expect(screen.getByText('暂无任务规划数据')).toBeInTheDocument();
      expect(container.textContent).toContain('Agent 会自动生成任务 DAG');
    });
  });

  describe('G6 实例管理', () => {
    it('相同数据的节点引用变化不应导致重建（useMemo 稳定比较）', () => {
      const { rerender } = render(<DagFlow nodes={mockNodes} edges={mockEdges} />);
      expect(MockGraph).toHaveBeenCalledTimes(1);

      const sameNodes = [...mockNodes];
      const sameEdges = [...mockEdges];
      rerender(<DagFlow nodes={sameNodes} edges={sameEdges} />);
      expect(MockGraph).toHaveBeenCalledTimes(1);
    });

    it('内容真正变化时才重建 G6 实例', () => {
      const { rerender } = render(<DagFlow nodes={mockNodes} edges={mockEdges} />);
      expect(MockGraph).toHaveBeenCalledTimes(1);

      const changedNodes: DagNode[] = [
        ...mockNodes,
        { id: 'T4', label: '验证', type: 'verify', description: '验证结果', tool_name: 'verify', status: 'pending' },
      ];
      rerender(<DagFlow nodes={changedNodes} edges={mockEdges} />);
      expect(MockGraph).toHaveBeenCalledTimes(2);
    });
  });

  describe('卸载清理', () => {
    it('组件卸载时应销毁 G6 实例', () => {
      const { unmount } = render(<DagFlow nodes={mockNodes} edges={mockEdges} />);
      unmount();
      expect(mockGraphInstance.destroy).toHaveBeenCalled();
    });
  });

  describe('默认高度', () => {
    it('未传 height 时默认为 420px', () => {
      const { container } = render(<DagFlow nodes={mockNodes} edges={mockEdges} />);
      const divs = container.querySelectorAll('div[style]');
      const canvasContainer = Array.from(divs).find(
        d => d.getAttribute('style')?.includes('overflow: hidden')
      );
      expect(canvasContainer?.getAttribute('style')).toContain('height: 420px');
    });
  });

  describe('节点详情弹窗', () => {
    /** 获取注册的 node:click 回调 */
    function getClickHandler(): ((evt: unknown) => void) | undefined {
      return mockGraphInstance.on.mock.calls.find(c => c[0] === 'node:click')?.[1];
    }

    it('DD-01: 点击节点弹出任务详情', () => {
      render(<DagFlow nodes={mockNodes} edges={mockEdges} />);
      const handler = getClickHandler();
      expect(handler).toBeDefined();
      act(() => {
        handler?.({ target: { id: 'T1' } });
      });
      expect(screen.getByText('任务详情 - T1')).toBeInTheDocument();
      expect(screen.getByText('检索三家运营商营收')).toBeInTheDocument();
    });

    it('DD-02: 详情弹窗展示工具参数', () => {
      const nodesWithParams: DagNode[] = [
        ...mockNodes,
        { id: 'T5', label: '对比', type: 'compare', description: '对比参数', tool_name: 'compare', tool_params: { companies: ['中国移动'], metric: '营收', year: 2024 }, status: 'pending' },
      ];
      render(<DagFlow nodes={nodesWithParams} edges={mockEdges} />);
      const handler = getClickHandler();
      act(() => {
        handler?.({ target: { id: 'T5' } });
      });
      expect(screen.getByText('任务详情 - T5')).toBeInTheDocument();
      expect(screen.getByText(/中国移动/)).toBeInTheDocument();
      expect(screen.getByText(/营收/)).toBeInTheDocument();
    });
  });
});
