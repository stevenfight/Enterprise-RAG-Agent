// -*- coding: utf-8 -*-
/** 研究任务入口的 TDD 契约。 */
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

const toggleSider = vi.hoisted(() => vi.fn());

vi.mock('@/stores/appStore', () => ({
  appStore: (selector: (state: { siderCollapsed: boolean; toggleSider: () => void }) => unknown) => selector({
    siderCollapsed: false,
    toggleSider,
  }),
}));

vi.mock('@/hooks/useTheme', () => ({
  useTheme: () => ({ isDark: false }),
}));

import Sidebar from '@/components/layout/Sidebar';

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location-path">{location.pathname}</output>;
}

describe('Sidebar', () => {
  it('E-RRD-1: 暴露研究任务入口', () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <Sidebar />
      </MemoryRouter>,
    );

    expect(screen.getByText('研究任务')).toBeInTheDocument();
  });

  it('E-RRD-1: 点击研究任务入口进入研究工作台', async () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <Sidebar />
        <LocationProbe />
      </MemoryRouter>,
    );

    await userEvent.click(screen.getByRole('menuitem', { name: /研究任务/ }));

    expect(screen.getByTestId('location-path')).toHaveTextContent('/research');
  });
});
