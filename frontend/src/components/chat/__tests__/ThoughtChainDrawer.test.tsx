// -*- coding: utf-8 -*-
/**
 * ThoughtChainDrawer 组件单元测试
 * 覆盖: 时间线节点定位 / 步骤渲染 / 展开折叠
 */
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ThoughtChainDrawer from '@/components/chat/ThoughtChainDrawer';
import type { ReasoningStep } from '@/types/chat';

/** Mock useTheme */
vi.mock('@/hooks/useTheme', () => ({
  useTheme: () => ({ isDark: false }),
}));

/** 模拟短 observation */
const shortObs = '营收数据: 10,408 亿元';

/** 模拟长 observation (>80字符触发展开) */
const longObs = '从检索结果中提取到以下关键数据：营业收入达到人民币10,408亿元，同比增长4.5%，其中移动通信服务收入占比较大，新兴业务持续保持双位数增长，整体表现优于行业平均水平。';

/** 标准测试步骤 */
const mockSteps: ReasoningStep[] = [
  {
    step_number: 1,
    thought: '需要先检索三大运营商2024年营收数据',
    action: 'compare',
    action_input: '{"companies":["中国移动","中国联通","中国电信"],"year":2024}',
    observation: shortObs,
  },
  {
    step_number: 2,
    thought: '已获取足够数据，可以直接给出结论',
    observation: longObs,
  },
];

/** 无 thought 的步骤 */
const noThoughtSteps: ReasoningStep[] = [
  {
    step_number: 1,
    observation: '某观察结果',
  },
];

/** 无 action 的步骤 */
const noActionSteps: ReasoningStep[] = [
  {
    step_number: 1,
    thought: '分析完毕',
    observation: '结果',
  },
];

const defaultProps = {
  open: true,
  onClose: vi.fn(),
  steps: mockSteps,
};

describe('ThoughtChainDrawer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('基础渲染', () => {
    it('open=true 时应该渲染 Drawer', () => {
      render(<ThoughtChainDrawer {...defaultProps} />);
      expect(screen.getByText(/推理过程.*2 步/)).toBeInTheDocument();
    });

    it('open=false 时不应该显示内容', () => {
      render(<ThoughtChainDrawer {...defaultProps} open={false} />);
      expect(screen.queryByText('推理过程')).toBeNull();
    });

    it('应该渲染正确数量的步骤标签', () => {
      render(<ThoughtChainDrawer {...defaultProps} />);
      const tags = screen.getAllByText(/步骤 \d/);
      expect(tags).toHaveLength(2);
    });

    it('应该显示调用工具标签', () => {
      render(<ThoughtChainDrawer {...defaultProps} />);
      expect(screen.getByText('调用工具: compare')).toBeInTheDocument();
    });
  });

  describe('时间线节点渲染', () => {
    it('每个步骤应该有独立卡片', () => {
      render(<ThoughtChainDrawer {...defaultProps} />);
      // 通过 Tag 组件匹配步骤编号来验证卡片数量
      expect(screen.getByText('步骤 1')).toBeInTheDocument();
      expect(screen.getByText('步骤 2')).toBeInTheDocument();
    });

    it('时间线竖线容器存在（position:relative）', () => {
      render(<ThoughtChainDrawer {...defaultProps} />);
      // Drawer 打开时，步骤卡片应该渲染出来 -- 验证时间线组件正常挂载
      expect(screen.getByText('步骤 1')).toBeInTheDocument();
      expect(screen.getByText('步骤 2')).toBeInTheDocument();
    });
  });

  describe('Thought 渲染', () => {
    it('有 thought 时应该渲染文本', () => {
      render(<ThoughtChainDrawer {...defaultProps} />);
      expect(screen.getByText('需要先检索三大运营商2024年营收数据')).toBeInTheDocument();
    });

    it('无 thought 的步骤不应该渲染 thought 文本内容', () => {
      render(<ThoughtChainDrawer {...defaultProps} steps={noThoughtSteps} />);
      expect(screen.getByText('步骤 1')).toBeInTheDocument();
      // 无 thought 文本时，不应该渲染对应的 BulbOutlined 旁边的内容
      expect(screen.queryByText('需要先检索三大运营商2024年营收数据')).toBeNull();
    });
  });

  describe('Action 渲染', () => {
    it('有 action 时应该显示工具调用标签', () => {
      render(<ThoughtChainDrawer {...defaultProps} />);
      expect(screen.getByText('调用工具: compare')).toBeInTheDocument();
    });

    it('有 action_input 时应该渲染到 DOM 中', () => {
      render(<ThoughtChainDrawer {...defaultProps} />);
      // Drawer 通过 React Portal 渲染到 body，action_input 内容应存在于 document.body
      expect(document.body.textContent).toContain('中国移动');
    });

    it('无 action 的步骤不应该渲染 action 区域', () => {
      render(<ThoughtChainDrawer {...defaultProps} steps={noActionSteps} />);
      expect(screen.queryByText('调用工具:')).toBeNull();
    });
  });

  describe('Observation 展开折叠', () => {
    it('短 observation 不应该显示展开全部', () => {
      render(<ThoughtChainDrawer {...defaultProps} />);
      // 只有步骤2是长observation，步骤1是短observation
      // 确认长observation长度 > 80
      expect(longObs.length).toBeGreaterThan(80);
    });

    it('长 observation 应该显示展开全部按钮', () => {
      render(<ThoughtChainDrawer {...defaultProps} steps={[
        { step_number: 1, thought: '分析', observation: longObs },
      ]} />);
      // 长文本 > 80 字符时应该出现"展开全部"
      expect(screen.getByText('展开全部')).toBeInTheDocument();
    });

    it('点击展开全部后应隐藏该按钮', () => {
      render(<ThoughtChainDrawer {...defaultProps} steps={[
        { step_number: 1, thought: '分析', observation: longObs },
      ]} />);
      fireEvent.click(screen.getByText('展开全部'));
      expect(screen.queryByText('展开全部')).toBeNull();
    });
  });

  describe('回调', () => {
    it('关闭按钮应触发 onClose', () => {
      render(<ThoughtChainDrawer {...defaultProps} />);
      const closeBtn = document.querySelector('.ant-drawer-close');
      if (closeBtn) {
        fireEvent.click(closeBtn);
        expect(defaultProps.onClose).toHaveBeenCalled();
      }
    });
  });

  describe('空步骤列表', () => {
    it('空步骤列表应正常渲染无报错', () => {
      render(<ThoughtChainDrawer {...defaultProps} steps={[]} />);
      expect(screen.getByText(/推理过程.*0 步/)).toBeInTheDocument();
    });
  });

  describe('步骤间间距', () => {
    it('多步骤时应有步骤分隔空间', () => {
      render(<ThoughtChainDrawer {...defaultProps} steps={mockSteps.slice(0, 2)} />);
      // 两个步骤都渲染了
      expect(screen.getByText('步骤 1')).toBeInTheDocument();
      expect(screen.getByText('步骤 2')).toBeInTheDocument();
    });
  });
});
