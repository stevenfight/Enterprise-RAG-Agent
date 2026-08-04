// -*- coding: utf-8 -*-
/**
 * 占位页面模板
 * Phase 2/3 功能开发前的占位提示
 */

import { Result, Button } from 'antd';
import { createLogger } from '@/utils/logger';

const logger = createLogger('PlaceholderPage');

interface PlaceholderPageProps {
  /** 功能名称 */
  title: string;
  /** 功能描述 */
  description?: string;
  /** 图标 */
  icon?: React.ReactNode;
  /** 预计上线阶段 */
  phase?: string;
}

export default function PlaceholderPage({ title, description, icon, phase }: PlaceholderPageProps) {
  logger.renderStart({ title, phase });

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        minHeight: 400,
      }}
    >
      <Result
        icon={icon}
        title={title}
        subTitle={description || `功能开发中，敬请期待${phase ? `（${phase}）` : ''}`}
        extra={
          <Button type="primary" onClick={() => window.location.href = '/'}>
            返回首页
          </Button>
        }
      />
    </div>
  );
}
