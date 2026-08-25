// -*- coding: utf-8 -*-
/**
 * 研究上下文状态测试
 * 上下文仅服务当前应用运行期，不进入浏览器持久化。
 */

import { beforeEach, describe, expect, it } from 'vitest';
import { appStore } from '@/stores/appStore';

describe('研究上下文状态', () => {
  beforeEach(() => {
    appStore.setState({ researchContext: {} });
  });

  it('RW-R01-01 保存当前公司与提问模式', () => {
    appStore.getState().setResearchContext({ companyName: '中芯国际', mode: 'agent' });

    expect(appStore.getState().researchContext).toEqual({
      companyName: '中芯国际',
      mode: 'agent',
    });
  });

  it('RW-R01-02 更新模式时保留当前公司', () => {
    appStore.getState().setResearchContext({ companyName: '中芯国际' });
    appStore.getState().setResearchContext({ mode: 'rag' });

    expect(appStore.getState().researchContext).toEqual({
      companyName: '中芯国际',
      mode: 'rag',
    });
  });

  it('RW-R01-03 清除公司后不保留空字段', () => {
    appStore.getState().setResearchContext({ companyName: '中芯国际', mode: 'rag' });
    appStore.getState().setResearchContext({ companyName: undefined });

    expect(appStore.getState().researchContext).toStrictEqual({ mode: 'rag' });
  });
});
