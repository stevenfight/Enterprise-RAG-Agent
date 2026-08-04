// -*- coding: utf-8 -*-
/**
 * DAG 有向无环图组件
 * Phase 2 - 使用 @antv/g6 v5 渲染 Agent 任务规划的子任务依赖关系图
 *
 * 后端 /api/agent/plan 返回:
 *   - nodes: [{id, label, type, description, tool_name, status}]
 *   - edges: [{source, target}]
 *   - execution_order: [[task_id, ...], ...]
 */

import React, { useEffect, useRef, useMemo, useState, useCallback } from 'react';
import { Graph } from '@antv/g6';
import { TYPE_COLORS } from '@/constants/dag';

interface DagNode {
  id: string;
  label: string;
  type: string;
  description: string;
  tool_name: string;
  status: string;
}

interface DagEdge {
  source: string;
  target: string;
}

interface DagFlowProps {
  nodes: DagNode[];
  edges: DagEdge[];
  height?: number;
}

// ========== 日志工具 ==========

let _dagMountId = 0;

function dagLogger(fnName: string, msg: string, extra?: Record<string, unknown>) {
  const payload = extra ? ` ${JSON.stringify(extra)}` : '';
  console.debug(`[DagFlow][${fnName}] ${msg}${payload}`);
}

// ========== 组件 ==========

export default function DagFlow({ nodes, edges, height = 420 }: DagFlowProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);
  const [containerWidth, setContainerWidth] = useState(0);

  const mountId = useMemo(() => { _dagMountId += 1; return _dagMountId; }, []);

  // 用 JSON 序列化做浅层稳定比较，避免数组/对象引用变化导致 G6 实例频繁重建
  const dataKey = useMemo(
    () => JSON.stringify({ ids: nodes.map(n => n.id), edges: edges.map(e => `${e.source}->${e.target}`), height, w: containerWidth }),
    [nodes, edges, height, containerWidth]
  );

  // 监听容器宽度变化，兜底 offsetWidth 为 0 的边界情况
  const measureWidth = useCallback(() => {
    if (containerRef.current) {
      const w = containerRef.current.offsetWidth;
      if (w !== containerWidth) {
        dagLogger(`mount#${mountId}`, `measureWidth: offsetWidth=${w} (之前=${containerWidth})`);
        setContainerWidth(w);
      }
    }
  }, [containerWidth, mountId]);

  // ---- ResizeObserver 生命周期 ----
  useEffect(() => {
    dagLogger(`mount#${mountId}`, 'ResizeObserver setup 开始');
    measureWidth();

    if (typeof ResizeObserver !== 'undefined') {
      const ro = new ResizeObserver(measureWidth);
      if (containerRef.current) {
        ro.observe(containerRef.current);
        dagLogger(`mount#${mountId}`, 'ResizeObserver 已绑定容器');
      }
      return () => {
        ro.disconnect();
        dagLogger(`mount#${mountId}`, 'ResizeObserver 已清理');
      };
    } else {
      dagLogger(`mount#${mountId}`, 'ResizeObserver 不可用，静默回退');
    }
  }, [measureWidth, mountId]);

  // ---- G6 实例生命周期 ----
  useEffect(() => {
    dagLogger(`mount#${mountId}`, `dataKey 变更, nodes=${nodes.length} edges=${edges.length} containerWidth=${containerWidth} hasRef=${!!containerRef.current}`);

    if (!containerRef.current || nodes.length === 0) {
      dagLogger(`mount#${mountId}`, `跳过G6创建: hasRef=${!!containerRef.current} nodesLen=${nodes.length}`);
      return;
    }

    // 销毁旧实例
    if (graphRef.current) {
      dagLogger(`mount#${mountId}`, '销毁旧G6实例');
      graphRef.current.destroy();
      graphRef.current = null;
    }

    // 兜底: offsetWidth 为 0 时使用容器实际可用宽度 (至少 200)
    const offsetW = containerRef.current.offsetWidth;
    const widthSource =
      offsetW > 0 ? 'offsetWidth' :
      containerWidth > 0 ? 'stateWidth' :
      'fallback200';

    const width = offsetW || containerWidth || 200;

    dagLogger(`mount#${mountId}`, `构建G6实例: width=${width} (${widthSource}) height=${height} typeMap=${JSON.stringify(nodes.map(n => n.type))}`);

    const g6Nodes = nodes.map(n => ({
      id: n.id,
      data: {
        label: `${n.id} - ${n.type}`,
        description: n.description,
        type: n.type,
        tool_name: n.tool_name,
        color: TYPE_COLORS[n.type] || '#B8A9C9',
      },
    }));

    const g6Edges = edges.map(e => ({
      source: e.source,
      target: e.target,
      style: {
        stroke: '#d9cfe8',
        endArrow: true,
      },
    }));

    const graph = new Graph({
      container: containerRef.current,
      width,
      height,
      data: { nodes: g6Nodes, edges: g6Edges },
      layout: {
        type: 'dagre',
        rankdir: 'TB',
        nodesep: 50,
        ranksep: 70,
      },
      node: {
        style: {
          size: [180, 56],
          labelText: '',
          labelFill: '#3D3554',
          labelFontSize: 12,
          labelFontWeight: 600,
          labelPlacement: 'center',
          labelOffsetY: 4,
          fill: '#ffffff',
          stroke: '#B8A9C9',
          lineWidth: 2,
          radius: 10,
          shadowColor: 'rgba(0,0,0,0.06)',
          shadowBlur: 8,
        },
      },
      edge: {
        style: {
          stroke: '#d9cfe8',
          lineWidth: 2,
          endArrow: true,
        },
      },
      behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element'],
      autoFit: 'view',
    });

    graph.render();
    graphRef.current = graph;
    dagLogger(`mount#${mountId}`, 'G6实例创建并渲染完成');

    return () => {
      if (graphRef.current) {
        dagLogger(`mount#${mountId}`, 'cleanup: 销毁G6实例');
        graphRef.current.destroy();
        graphRef.current = null;
      }
    };
  }, [dataKey, mountId]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---- 空状态 ----
  if (nodes.length === 0) {
    dagLogger(`mount#${mountId}`, '渲染空状态: nodes=0');
    return (
      <div style={{
        width: '100%',
        height,
        borderRadius: 12,
        background: '#faf8fd',
        border: '1px solid #e8e3ef',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        color: '#bbb',
        fontSize: 14,
      }}>
        <div style={{ fontSize: 48, marginBottom: 12, opacity: 0.3 }}>
          &#9679;&#9472;&#9679;&#9472;&#9679;
        </div>
        <div>暂无任务规划数据</div>
        <div style={{ fontSize: 12, marginTop: 4 }}>
          输入查询后，Agent 会自动生成任务 DAG
        </div>
      </div>
    );
  }

  dagLogger(`mount#${mountId}`, `渲染canvas容器, height=${height}`);

  return (
    <div
      ref={containerRef}
      style={{
        width: '100%',
        height,
        borderRadius: 12,
        background: '#faf8fd',
        border: '1px solid #e8e3ef',
        overflow: 'hidden',
      }}
    />
  );
}
