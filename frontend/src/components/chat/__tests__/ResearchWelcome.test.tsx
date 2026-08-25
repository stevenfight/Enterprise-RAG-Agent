// -*- coding: utf-8 -*-
/** 研究工作台欢迎区测试。 */
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import ResearchWelcome from '@/components/chat/ResearchWelcome';

vi.mock('@/hooks/useTheme', () => ({ useTheme: () => ({ isDark: false }) }));

describe('ResearchWelcome', () => {
  it('RW-R02-02: 展示工作台欢迎信息和快捷问题入口', () => {
    const onSend = vi.fn();
    render(<ResearchWelcome quickCommands={['中芯国际2024年营收是多少？']} onSend={onSend} />);

    expect(screen.getByRole('heading', { name: '从一个问题开始，完成可核验的财务研究' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /中芯国际2024年营收是多少/ }));
    expect(onSend).toHaveBeenCalledWith('中芯国际2024年营收是多少？');
  });

  it('CP-R16: 以真实研究范围和可核验能力组织空会话启动页', () => {
    render(
      <ResearchWelcome
        companyName="中国移动"
        mode="agent"
        quickCommands={['对比三大运营商2024年的营业收入']}
        onSend={vi.fn()}
      />,
    );

    expect(screen.getByRole('region', { name: '研究启动页' })).toBeInTheDocument();
    expect(screen.getByText('当前研究范围')).toBeInTheDocument();
    expect(screen.getByText('中国移动')).toBeInTheDocument();
    expect(screen.getByText('Agent 深度分析')).toBeInTheDocument();
    expect(screen.getByText('证据核验')).toBeInTheDocument();
    expect(screen.getByText('分析过程')).toBeInTheDocument();
  });
});
