// -*- coding: utf-8 -*-
/**
 * TDD 测试: HeaderBar 唯一外观入口
 */

import { beforeEach, describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, within, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import HeaderBar from '../HeaderBar';
import { appStore } from '@/stores/appStore';

const getCurrentResearchIdentity = vi.hoisted(() => vi.fn());
const loginResearch = vi.hoisted(() => vi.fn());
const logoutResearch = vi.hoisted(() => vi.fn());

vi.mock('@/services/researchAuthService', () => ({
  getCurrentResearchIdentity,
  loginResearch,
  logoutResearch,
  RESEARCH_IDENTITY_CHANGED_EVENT: 'research-identity-changed',
}));

const mockToggle = vi.fn();
const mockSetTheme = vi.fn();
const mockSetAccentTheme = vi.fn();

// mock useTheme
vi.mock('@/hooks/useTheme', () => ({
  useTheme: () => ({
    isDark: false,
    themeMode: 'light',
    accentTheme: 'financialTeal',
    toggleTheme: mockToggle,
    setTheme: mockSetTheme,
    setAccentTheme: mockSetAccentTheme,
  }),
}));

describe('HeaderBar 外观面板', () => {
  beforeEach(() => {
    appStore.setState({ researchContext: {} });
    getCurrentResearchIdentity.mockRejectedValue({ response: { status: 401 } });
    loginResearch.mockReset();
    logoutResearch.mockReset();
  });
  it('DS-R05-03: 渲染唯一外观入口', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <HeaderBar systemStatus="ready" />
      </MemoryRouter>,
    );
    const btn = screen.getByRole('button', { name: '外观' });
    expect(btn).toBeInTheDocument();
  });

  it('DS-R05-04: 可在面板中保留亮暗主题切换', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <HeaderBar systemStatus="ready" />
      </MemoryRouter>,
    );
    const btn = screen.getByRole('button', { name: '外观' });
    fireEvent.click(btn);
    fireEvent.click(screen.getByRole('button', { name: '暗色模式' }));
    expect(mockSetTheme).toHaveBeenCalledWith('dark');
  });

  it('DS-R08-01: 主体色按钮具有文字标签和选中语义', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <HeaderBar systemStatus="ready" />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole('button', { name: '外观' }));
    const tealButton = screen.getByRole('button', { name: '金融青绿主体色' });
    const blueButton = screen.getByRole('button', { name: '深蓝主体色' });

    expect(tealButton).toHaveAttribute('aria-pressed', 'true');
    expect(blueButton).toHaveAttribute('aria-pressed', 'false');
    fireEvent.click(blueButton);
    expect(mockSetAccentTheme).toHaveBeenCalledWith('deepBlue');
  });

  it('RW-R07-01: 顶栏只读展示下次提问的研究范围', () => {
    appStore.setState({
      researchContext: { companyName: '中芯国际', mode: 'agent' },
    });
    render(
      <MemoryRouter initialEntries={['/']}>
        <HeaderBar systemStatus="ready" />
      </MemoryRouter>,
    );

    expect(screen.getByText('下次提问：中芯国际 · Agent 模式')).toBeInTheDocument();
  });

  it('CP-R14-01: 直接进入辅助路由仍展示 Store 初始化后的 Agent 模式', () => {
    appStore.setState({ researchContext: { mode: 'agent' } });
    render(
      <MemoryRouter initialEntries={['/charts']}>
        <HeaderBar systemStatus="ready" />
      </MemoryRouter>,
    );

    expect(screen.getByText('下次提问：全部公司 · Agent 模式')).toBeInTheDocument();
  });

  it('RW-R10-01: 可从只读研究范围按钮打开摘要', () => {
    appStore.setState({ researchContext: { companyName: '中芯国际', mode: 'rag' } });
    render(
      <MemoryRouter initialEntries={['/']}>
        <HeaderBar systemStatus="ready" />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole('button', { name: '查看研究范围' }));
    const drawer = screen.getByRole('dialog');
    expect(within(drawer).getByText('下次提问：中芯国际 · RAG 模式')).toBeInTheDocument();
  });

  it('CP-R17: 顶栏为窄屏外观和健康状态提供可收缩钩子', () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/']}>
        <HeaderBar systemStatus="ready" />
      </MemoryRouter>,
    );

    expect(container.querySelector('.app-header-bar')).toBeInTheDocument();
    expect(container.querySelector('.header-appearance-label')).toBeInTheDocument();
    expect(container.querySelector('.header-health-label')).toBeInTheDocument();
  });
  it('DS-R04-01: 健康检查完成前显示检查中', () => {
    render(<MemoryRouter><HeaderBar systemStatus="checking" /></MemoryRouter>);
    expect(screen.getByText('检查中')).toBeInTheDocument();
  });

  it('DS-R04-02: 健康检查失败显示暂不可用', () => {
    render(<MemoryRouter><HeaderBar systemStatus="unavailable" /></MemoryRouter>);
    expect(screen.getByText('暂不可用')).toBeInTheDocument();
  });

  it('FWC-T02: 研究任务路由显示准确标题', () => {
    render(<MemoryRouter initialEntries={['/research']}><HeaderBar systemStatus="ready" /></MemoryRouter>);
    expect(screen.getByText('研究任务')).toBeInTheDocument();
  });

  it('E-T22-03: 未登录时提供登录入口，登录后显示当前用户名和角色', async () => {
    getCurrentResearchIdentity.mockRejectedValueOnce({ response: { status: 401 } });
    loginResearch.mockResolvedValueOnce({ username: 'alice', roles: ['approver'] });
    render(<MemoryRouter><HeaderBar systemStatus="ready" /></MemoryRouter>);

    const loginButton = await screen.findByRole('button', { name: '登录' });
    await waitFor(() => expect(loginButton).not.toHaveClass('ant-btn-loading'));
    fireEvent.click(loginButton);
    fireEvent.change(screen.getByLabelText('用户名'), { target: { value: 'alice' } });
    fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'secret' } });
    fireEvent.click(screen.getByRole('button', { name: '登录提交' }));

    expect(await screen.findByText('alice')).toBeInTheDocument();
    expect(screen.getByText('审批人')).toBeInTheDocument();
    expect(loginResearch).toHaveBeenCalledWith({ username: 'alice', password: 'secret' });
  });

  it('E-T22-04: 登出后回到明确未登录状态', async () => {
    getCurrentResearchIdentity.mockResolvedValueOnce({ user_id: 'user-1', username: 'alice', roles: ['approver'] });
    logoutResearch.mockResolvedValueOnce(undefined);
    render(<MemoryRouter><HeaderBar systemStatus="ready" /></MemoryRouter>);

    expect(await screen.findByText('alice')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '登出' }));

    expect(await screen.findByRole('button', { name: '登录' })).toBeInTheDocument();
    expect(logoutResearch).toHaveBeenCalledOnce();
  });

  it('E-T26: 键盘可提交登录，失败信息会被辅助技术明确通知', async () => {
    const user = userEvent.setup();
    getCurrentResearchIdentity.mockRejectedValueOnce({ response: { status: 401 } });
    loginResearch.mockRejectedValueOnce(new Error('invalid credentials'));
    render(<MemoryRouter><HeaderBar systemStatus="ready" /></MemoryRouter>);

    const loginButton = await screen.findByRole('button', { name: '登录' });
    await waitFor(() => expect(loginButton).not.toHaveClass('ant-btn-loading'));
    await user.click(loginButton);
    await user.type(screen.getByLabelText('用户名'), 'alice');
    await user.type(screen.getByLabelText('密码'), 'wrong-password{enter}');

    expect(await screen.findByRole('alert')).toHaveTextContent('登录失败，请检查用户名和密码。');
    expect(loginResearch).toHaveBeenCalledWith({ username: 'alice', password: 'wrong-password' });
  });
});
