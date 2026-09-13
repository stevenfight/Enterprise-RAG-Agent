// -*- coding: utf-8 -*-
/**
 * 顶部栏
 * 包含: 折叠按钮 + 页面标题 + 系统状态指示灯
 */

import { Alert, Button, Space, Typography, Badge, Tooltip, Divider, Popover, Drawer, Form, Input, Tag } from 'antd';
import {
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  SunOutlined,
  MoonOutlined,
  BgColorsOutlined,
} from '@ant-design/icons';
import { useLocation } from 'react-router-dom';
import { useEffect, useRef, useState } from 'react';
import { appStore } from '@/stores/appStore';
import { useTheme } from '@/hooks/useTheme';
import { accentThemes } from '@/styles/theme';
import { getCurrentResearchIdentity, loginResearch, logoutResearch, RESEARCH_IDENTITY_CHANGED_EVENT, type ResearchCurrentIdentity } from '@/services/researchAuthService';
const { Text } = Typography;

/** 路由到页面标题的映射 */
const pageTitleMap: Record<string, string> = {
  '/': '智能问答',
  '/dag': 'DAG 任务看板',
  '/charts': '数据图表',
  '/knowledge': '知识库管理',
  '/settings': '系统设置',
};

export type SystemStatus = 'checking' | 'ready' | 'unavailable';

interface HeaderBarProps {
  /** 系统健康状态 */
  systemStatus?: SystemStatus;
}

export default function HeaderBar({ systemStatus = 'checking' }: HeaderBarProps) {
  const [contextDrawerOpen, setContextDrawerOpen] = useState(false);
  const [loginOpen, setLoginOpen] = useState(false);
  const [identity, setIdentity] = useState<ResearchCurrentIdentity | null>(null);
  const [identityLoading, setIdentityLoading] = useState(true);
  const [loginSubmitting, setLoginSubmitting] = useState(false);
  const [loginError, setLoginError] = useState('');
  const loginOpenRef = useRef(loginOpen);
  const location = useLocation();
  const siderCollapsed = appStore((s) => s.siderCollapsed);
  const toggleSider = appStore((s) => s.toggleSider);
  const researchContext = appStore((s) => s.researchContext);
  const { isDark, themeMode, accentTheme, setTheme, setAccentTheme } = useTheme();

  const title = pageTitleMap[location.pathname] || '企业知识库';
  const researchSummary = `下次提问：${researchContext.companyName || '全部公司'} · ${researchContext.mode === 'agent' ? 'Agent 模式' : 'RAG 模式'}`;
  const healthStatus = systemStatus === 'ready' ? 'success' : systemStatus === 'checking' ? 'processing' : 'error';
  const healthText = systemStatus === 'ready' ? '已就绪' : systemStatus === 'checking' ? '检查中' : '暂不可用';
  loginOpenRef.current = loginOpen;

  useEffect(() => {
    let active = true;
    void getCurrentResearchIdentity()
      .then((currentIdentity) => {
        if (active) setIdentity(currentIdentity);
      })
      .catch(() => {
        // 未登录和会话失效都保持明确的登录入口，不在客户端保留旧身份。
        if (active) setIdentity(null);
      })
      .finally(() => {
        if (active) setIdentityLoading(false);
      });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    const handleLoginEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && loginOpenRef.current) {
        event.preventDefault();
        setLoginOpen(false);
      }
    };

    document.addEventListener('keydown', handleLoginEscape);
    return () => document.removeEventListener('keydown', handleLoginEscape);
  }, []);

  const handleLogin = async (values: { username: string; password: string }) => {
    setLoginSubmitting(true);
    setLoginError('');
    try {
      const loggedIn = await loginResearch(values);
      setIdentity({ user_id: '', ...loggedIn });
      window.dispatchEvent(new Event(RESEARCH_IDENTITY_CHANGED_EVENT));
      setLoginOpen(false);
    } catch {
      setLoginError('登录失败，请检查用户名和密码。');
    } finally {
      setLoginSubmitting(false);
    }
  };

  const handleLogout = async () => {
    await logoutResearch();
    setIdentity(null);
    window.dispatchEvent(new Event(RESEARCH_IDENTITY_CHANGED_EVENT));
  };

  const loginContent = (
    <Form layout="vertical" style={{ width: 264 }} onFinish={handleLogin}>
      <Form.Item label="用户名" name="username" rules={[{ required: true, message: '请输入用户名' }]}>
        <Input autoComplete="username" />
      </Form.Item>
      <Form.Item label="密码" name="password" rules={[{ required: true, message: '请输入密码' }]}>
        <Input.Password autoComplete="current-password" />
      </Form.Item>
      {loginError && <Alert type="error" showIcon message={loginError} />}
      <Button type="primary" htmlType="submit" loading={loginSubmitting} aria-label="登录提交" style={{ marginTop: 8 }}>
        登录
      </Button>
    </Form>
  );
  const appearanceContent = (
    <div style={{ width: 232 }}>
      <Text type="secondary" style={{ fontSize: 12 }}>显示模式</Text>
      <Space size={8} style={{ display: 'flex', marginTop: 8 }}>
        <Button
          size="small"
          type={themeMode === 'light' ? 'primary' : 'default'}
          aria-pressed={themeMode === 'light'}
          aria-label="亮色模式"
          onClick={() => setTheme('light')}
        >
          <SunOutlined />亮色模式
        </Button>
        <Button
          size="small"
          type={themeMode === 'dark' ? 'primary' : 'default'}
          aria-pressed={themeMode === 'dark'}
          aria-label="暗色模式"
          onClick={() => setTheme('dark')}
        >
          <MoonOutlined />暗色模式
        </Button>
      </Space>
      <Divider style={{ margin: '12px 0' }} />
      <Text type="secondary" style={{ fontSize: 12 }}>主体色</Text>
      <Space size={8} style={{ display: 'flex', marginTop: 8 }}>
        {(Object.entries(accentThemes) as Array<[keyof typeof accentThemes, (typeof accentThemes)[keyof typeof accentThemes]]>).map(([key, option]) => (
          <Button
            key={key}
            size="small"
            type={accentTheme === key ? 'primary' : 'default'}
            aria-pressed={accentTheme === key}
            aria-label={`${option.label}主体色`}
            onClick={() => setAccentTheme(key)}
          >
            <span
              aria-hidden="true"
              style={{
                display: 'inline-block',
                width: 8,
                height: 8,
                marginRight: 6,
                borderRadius: '50%',
                background: option[themeMode],
              }}
            />
            {option.label}
          </Button>
        ))}
      </Space>
    </div>
  );

  return (
    <div
      className="app-header-bar"
      style={{
        height: 56,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 24px',
        borderBottom: `1px solid ${isDark ? '#303030' : '#f0f0f0'}`,
        background: isDark ? '#1f1f1f' : '#ffffff',
      }}
    >
      {/* 左侧: 折叠按钮 + 标题 */}
      <Space className="app-header-bar__left" size={12}>
        <Button
          type="text"
          icon={siderCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
          onClick={toggleSider}
          style={{ fontSize: 16 }}
        />
        <Text
          strong
          style={{ fontSize: 16, color: isDark ? '#e8e8e8' : '#262626' }}
        >
          {title}
        </Text>
      </Space>

      {/* 右侧: 唯一外观入口 + 系统状态 */}
      <Space className="app-header-bar__right" size={8}>
        <Text
          className="header-research-context"
          type="secondary"
          style={{ fontSize: 12, whiteSpace: 'nowrap' }}
        >
          {researchSummary}
        </Text>
        <Button
          className="header-research-context-trigger"
          type="text"
          aria-label="查看研究范围"
          onClick={() => setContextDrawerOpen(true)}
        >
          研究范围
        </Button>
        {identity ? (
          <Space size={4} className="header-research-identity">
            <Text aria-label="当前登录用户">{identity.username}</Text>
            {identity.roles.includes('approver') && <Tag color="blue">审批人</Tag>}
            <Button type="text" aria-label="登出" onClick={() => void handleLogout()}>登出</Button>
          </Space>
        ) : (
          <Popover content={loginContent} title="研究工作台登录" trigger="click" placement="bottomRight" open={loginOpen} onOpenChange={setLoginOpen} destroyOnHidden>
            <Button type="text" aria-label="登录" loading={identityLoading} disabled={identityLoading}>登录</Button>
          </Popover>
        )}
        <Popover content={appearanceContent} title="外观" trigger="click" placement="bottomRight">
          <Button
            type="text"
            icon={<BgColorsOutlined />}
            aria-label="外观"
            style={{
              fontSize: 16,
              color: isDark ? '#e8e8e8' : '#595959',
            }}
          >
            <span className="header-appearance-label">外观</span>
          </Button>
        </Popover>
        <Tooltip title={healthText}>
          <Badge
            status={healthStatus}
            text={
              <Text
                className="header-health-label"
                style={{
                  fontSize: 13,
                  color: isDark ? '#8c8c8c' : '#595959',
                }}
              >
                {healthText}
              </Text>
            }
          />
        </Tooltip>
      </Space>
      <Drawer
        title="研究范围"
        placement="bottom"
        size={180}
        open={contextDrawerOpen}
        onClose={() => setContextDrawerOpen(false)}
      >
        <Text>{researchSummary}</Text>
        <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
          此范围仅影响下次提问，不会修改历史消息。
        </Text>
      </Drawer>
    </div>
  );
}
