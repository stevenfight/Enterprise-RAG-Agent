// -*- coding: utf-8 -*-
/**
 * 对话首页
 * 集成 ChatContainer + 侧边栏配置 + 示例问题
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { Typography, Select, Slider, Switch, Space, Card, Divider, Radio } from 'antd';
import {
  SearchOutlined,
  BulbOutlined,
  RobotOutlined,
  SettingOutlined,
  DownOutlined,
} from '@ant-design/icons';
import { chatStore, selectCurrentMessages } from '@/stores/chatStore';
import { useTheme } from '@/hooks/useTheme';
import { queryQuestion, getCompanies, streamAgentQuery } from '@/services/chatService';
import ChatContainer from '@/components/chat/ChatContainer';
import ThoughtChainDrawer from '@/components/chat/ThoughtChainDrawer';
import type { CompanyInfo, SSEEvent, AgentStepInfo, ReasoningStep, MultiAgentRunState } from '@/types/chat';
import { createLogger } from '@/utils/logger';
import { createEmptyAccumulator, applyAgentEvent } from '@/utils/agentEvent';

const logger = createLogger('ChatPage');
const { Text, Title } = Typography;

/** 示例问题 */
const EXAMPLE_QUESTIONS = [
  '中芯国际2024年营收是多少？',
  '对比三大运营商2024年的营业收入',
  '中芯国际的研发费用趋势如何？',
  '中国移动的收入结构是怎样的？',
];

export default function ChatPage() {
  const { isDark } = useTheme();

  // 侧边栏配置状态
  const [companies, setCompanies] = useState<CompanyInfo[]>([]);
  const [selectedCompany, setSelectedCompany] = useState<string | undefined>(undefined);
  const [topN, setTopN] = useState(5);
  const [agentMode, setAgentMode] = useState<boolean>(() => {
    // Phase 2: 从 localStorage 恢复 Agent 开关状态
    try {
      return localStorage.getItem('agent-mode') === 'true';
    } catch {
      return false;
    }
  });
  const [agentMaxSteps, setAgentMaxSteps] = useState<number>(() => {
    // Phase 2: 从 localStorage 恢复 Agent 推理步数
    try {
      const saved = localStorage.getItem('agent-max-steps');
      return saved ? parseInt(saved, 10) : 5;
    } catch {
      return 5;
    }
  });
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [companiesLoaded, setCompaniesLoaded] = useState(false);

  // SSE 连接引用 (Phase 2)
  const sseRef = useRef<EventSource | null>(null);

  // 示例问题填入输入框 (Phase 2)
  const [fillInputText, setFillInputText] = useState<string | undefined>(undefined);

  // Phase 2: 思维链侧边抽屉
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerSteps, setDrawerSteps] = useState<ReasoningStep[]>([]);

  const handleViewReasoning = useCallback((steps: ReasoningStep[]) => {
    setDrawerSteps(steps);
    setDrawerOpen(true);
  }, []);

  // chatStore
  const isLoading = chatStore((s) => s.isLoading);
  const setLoading = chatStore((s) => s.setLoading);
  const addUserMessage = chatStore((s) => s.addUserMessage);
  const addAssistantMessage = chatStore((s) => s.addAssistantMessage);
  const addErrorMessage = chatStore((s) => s.addErrorMessage);
  const updateLastAssistantMessage = chatStore((s) => s.updateLastAssistantMessage);
  const currentSessionId = chatStore((s) => s.currentSessionId);
  const currentMessages = chatStore(selectCurrentMessages);

  logger.renderStart({
    isLoading,
    companiesCount: companies.length,
    selectedCompany,
    topN,
    agentMode,
    currentSessionId,
    messagesCount: currentMessages.length,
  });

  // 加载公司列表
  useEffect(() => {
    const loadCompanies = async () => {
      try {
        logger.info('加载公司列表: GET /api/companies');
        const res = await getCompanies();
        setCompanies(res.companies);
        setCompaniesLoaded(true);
        logger.info('公司列表加载成功:', { count: res.companies.length, companies: res.companies.map(c => c.name) });
      } catch (err) {
        setCompaniesLoaded(false);
        logger.error('公司列表加载失败:', err);
      }
    };
    loadCompanies();
  }, []);

  // 清理 SSE 连接 (Phase 2)
  useEffect(() => {
    return () => {
      if (sseRef.current) {
        sseRef.current.close();
      }
    };
  }, []);

  // 持久化 Agent 开关状态 (Phase 2)
  useEffect(() => {
    try {
      localStorage.setItem('agent-mode', String(agentMode));
    } catch {
      // localStorage 不可用时忽略
    }
  }, [agentMode]);

  // 持久化 Agent 推理步数
  useEffect(() => {
    try {
      localStorage.setItem('agent-max-steps', String(agentMaxSteps));
    } catch {
      // localStorage 不可用时忽略
    }
  }, [agentMaxSteps]);

  // 发送消息 (Phase 2: 支持 Agent SSE 流式模式)
  const handleSend = useCallback(
    async (content: string) => {
      logger.info('发送消息:', {
        content: content.slice(0, 50),
        company: selectedCompany,
        topN,
        agentMode,
        sessionId: currentSessionId,
      });

      addUserMessage(content);
      setLoading(true);

      if (agentMode) {
        // Phase 2: Agent SSE 流式模式
        const agentStartTime = Date.now();
        logger.info('Agent SSE 模式启用', { query: content.slice(0, 80), timestamp: new Date().toISOString() });

        let acc = createEmptyAccumulator();
        let fullAnswer = '';
        let wasForcedStop = false; // 是否因步数上限强制终止
        let assistantMessageCreated = false; // 是否已创建 assistant 占位消息

        // 先关闭之前的 SSE 连接
        if (sseRef.current) {
          logger.debug('关闭之前的 SSE 连接');
          sseRef.current.close();
        }

        const es = streamAgentQuery(
          content,
          {
            company_name: selectedCompany || undefined,
            max_steps: agentMaxSteps,
            conversation_id: currentSessionId,
          },
          (event: SSEEvent) => {
            acc = applyAgentEvent(acc, event);

            // 首次出现推理步或多 Agent 状态时创建 assistant 占位消息
            if (!assistantMessageCreated && (acc.reasoningChain.length > 0 || acc.agentRun !== null)) {
              if (acc.agentRun) {
                addAssistantMessage('正在编排多 Agent 任务...', [], undefined, acc.agentRun);
              } else {
                addAssistantMessage('推理中...', [], [...acc.reasoningChain]);
              }
              assistantMessageCreated = true;
              return;
            }

            // 同步事件到 store
            const partial: { content?: string; reasoningChain?: AgentStepInfo[]; agentRun?: MultiAgentRunState } = {};
            if (acc.agentRun) partial.agentRun = acc.agentRun;
            if (acc.reasoningChain.length > 0) partial.reasoningChain = acc.reasoningChain;

            if (event.type === 'answer_chunk') {
              partial.content = acc.answer;
            } else if (event.type === 'answer') {
              partial.content = acc.answer;
              fullAnswer = acc.answer;
              logger.info('ON ANSWER 最终答案到达', { contentLen: acc.answer.length, elapsedMs: Date.now() - agentStartTime });
            }

            if (Object.keys(partial).length > 0) {
              updateLastAssistantMessage(partial);
            }

            if (event.type === 'error') {
              logger.error('SSE 错误事件:', event.content);
            } else if (event.type === 'done') {
              wasForcedStop = event.forced_stop === true;
              logger.info('SSE 流完成', {
                totalSteps: event.total_steps,
                elapsedMs: event.total_elapsed_ms,
                reasoningStepsCount: acc.reasoningChain.length,
                forcedStop: event.forced_stop,
              });
            }
          },
          (error: Event) => {
            console.error(
              '%c[ChatPage] SSE ERROR %cEventSource 连接错误',
              'color: #ff4d4f; font-weight: bold;',
              'color: #333;',
              { eventPhase: error.eventPhase, type: error.type },
            );
            logger.error('SSE 连接错误:', error);
            addErrorMessage('Agent 推理服务连接失败，请稍后重试。');
            setLoading(false);
          },
        );

        sseRef.current = es;
        console.log('%c[ChatPage] SSE INIT %cEventSource 已创建，等待事件...', 'color: #1890ff; font-weight: bold;', 'color: #333;', { query: content.slice(0, 30) });

        // 等待 SSE 流结束 (answer 事件到达)
        const checkDone = setInterval(() => {
          if (fullAnswer) {
            logger.info('SSE 收到完整答案', { answerLen: fullAnswer.length, reasoningSteps: acc.reasoningChain.length, totalElapsedMs: Date.now() - agentStartTime, forcedStop: wasForcedStop });
            clearInterval(checkDone);
            if (sseRef.current) {
              sseRef.current.close();
              sseRef.current = null;
            }
            // answer 事件已通过 updateLastAssistantMessage 设置内容和推理链路
            // 推理步数达上限时，注入系统警告提示
            if (wasForcedStop) {
              chatStore.getState().addErrorMessage(
                `推理达到步数上限（${acc.reasoningChain.length} 步），部分数据可能未检索到。建议细化查询条件后重试。`
              );
            }
            setLoading(false);
          }
        }, 200);

        // 超时保护 (120s)
        setTimeout(() => {
          clearInterval(checkDone);
          if (sseRef.current) {
            sseRef.current.close();
            sseRef.current = null;
          }
          if (!fullAnswer) {
            addErrorMessage('Agent 推理超时，请尝试简化问题或关闭 Agent 模式。');
          }
          setLoading(false);
        }, 120000);
      } else {
        // 普通 RAG 模式 (enable_rewrite 固定为 true)
        try {
          logger.debug('调用 queryQuestion API (普通RAG模式)...');
          const res = await queryQuestion({
            query: content,
            company_name: selectedCompany || undefined,
            top_n: topN,
            conversation_id: currentSessionId,
            enable_rewrite: true, // 固定开启，不再由用户控制
          });
          logger.info('API 响应成功:', {
            answerLength: res.answer.length,
            sourcesCount: res.sources.length,
            processingTime: res.processing_time,
            conversationId: res.conversation_id,
          });
          addAssistantMessage(res.answer, res.sources);
        } catch (err: unknown) {
          const errorMsg =
            err instanceof Error ? err.message : '未知错误';
          logger.error('API 请求失败:', { error: errorMsg, query: content.slice(0, 30) });
          if (errorMsg.includes('timeout') || errorMsg.includes('ECONNABORTED')) {
            addErrorMessage('请求超时，请检查网络连接或稍后重试。');
          } else {
            addErrorMessage(`服务暂时不可用，请稍后重试。（${errorMsg}）`);
          }
        } finally {
          setLoading(false);
          logger.debug('请求流程结束');
        }
      }
    },
    [selectedCompany, topN, agentMode, agentMaxSteps, currentSessionId, addUserMessage, setLoading, addAssistantMessage, updateLastAssistantMessage, addErrorMessage],
  );

  logger.renderEnd();

  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* 左侧: 配置面板 */}
      <div
        style={{
          width: 260,
          borderRight: `1px solid ${isDark ? '#303030' : '#f0f0f0'}`,
          padding: '16px',
          overflow: 'auto',
          background: isDark ? '#1a1a1a' : '#fafafa',
          flexShrink: 0,
        }}
      >
        <Title level={5} style={{ marginBottom: 16, color: isDark ? '#e8e8e8' : '#262626' }}>
          <SearchOutlined style={{ marginRight: 8 }} />
          检索配置
        </Title>

        {/* 公司选择 */}
        <div style={{ marginBottom: 20 }}>
          <Text style={{ fontSize: 13, display: 'block', marginBottom: 6, color: isDark ? '#8c8c8c' : '#595959' }}>
            选择公司
          </Text>
          <Select
            value={selectedCompany}
            onChange={(val: string | undefined) => setSelectedCompany(val)}
            placeholder="全部公司"
            allowClear
            style={{ width: '100%' }}
            options={companies.map((c) => ({
              value: c.name,
              label: c.display_name,
            }))}
            notFoundContent={companiesLoaded ? '暂无数据' : '加载中...'}
          />
        </div>

        {/* 检索返回条数 - Phase 2: 移入高级选项折叠面板 */}
        <div style={{ marginBottom: 12 }}>
          <div
            onClick={() => setShowAdvanced(!showAdvanced)}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              cursor: 'pointer',
              padding: '8px 0',
              userSelect: 'none',
            }}
          >
            <Space size={6}>
              <SettingOutlined style={{ color: isDark ? '#8c8c8c' : '#595959' }} />
              <Text style={{ fontSize: 13, color: isDark ? '#8c8c8c' : '#595959' }}>
                高级选项
              </Text>
            </Space>
            <DownOutlined
              style={{
                fontSize: 10,
                color: isDark ? '#8c8c8c' : '#595959',
                transform: showAdvanced ? 'rotate(180deg)' : 'rotate(0deg)',
                transition: 'transform 0.3s',
              }}
            />
          </div>
          <div
            style={{
              maxHeight: showAdvanced ? 200 : 0,
              overflow: 'hidden',
              opacity: showAdvanced ? 1 : 0,
              transition: 'max-height 0.3s ease, opacity 0.3s ease',
            }}
          >
            <div style={{ marginBottom: 16 }}>
              <Text style={{ fontSize: 13, display: 'block', marginBottom: 6, color: isDark ? '#8c8c8c' : '#595959' }}>
                检索返回条数: {topN}
              </Text>
              <Slider
                min={1}
                max={10}
                value={topN}
                onChange={setTopN}
              />
            </div>
          </div>
        </div>

        {/* Agent 深度推理开关 (Phase 2) */}
        <div style={{ marginBottom: 16 }}>
          <Space>
            <Switch
              checked={agentMode}
              onChange={setAgentMode}
              size="small"
            />
            <Text style={{ fontSize: 13, color: isDark ? '#8c8c8c' : '#595959' }}>
              <RobotOutlined style={{ marginRight: 4 }} />
              Agent 深度推理
            </Text>
          </Space>
          {agentMode && (
            <>
              <Text
                style={{
                  display: 'block',
                  marginTop: 4,
                  fontSize: 11,
                  color: '#B8A9C9',
                }}
              >
                开启后将实时展示 AI 推理过程
              </Text>
              {/* 推理步数选择 (Phase 2) */}
              <div style={{ marginTop: 10 }}>
                <Text style={{ fontSize: 12, color: isDark ? '#8c8c8c' : '#595959' }}>
                  推理步数上限
                </Text>
                <Radio.Group
                  value={agentMaxSteps}
                  onChange={(e) => setAgentMaxSteps(e.target.value)}
                  size="small"
                  style={{ marginTop: 6, display: 'flex', gap: 8 }}
                >
                  <Radio.Button value={5}>5 步</Radio.Button>
                  <Radio.Button value={10}>10 步</Radio.Button>
                </Radio.Group>
                <Text
                  style={{
                    display: 'block',
                    marginTop: 4,
                    fontSize: 11,
                    color: isDark ? '#6b6b6b' : '#b0b0b0',
                  }}
                >
                  步数越多检索越充分，但耗时更长
                </Text>
              </div>
            </>
          )}
        </div>

        <Divider style={{ margin: '16px 0' }} />

        {/* 示例问题 */}
        <Title level={5} style={{ marginBottom: 12, color: isDark ? '#e8e8e8' : '#262626' }}>
          <BulbOutlined style={{ marginRight: 8 }} />
          示例问题
        </Title>
        <Space orientation="vertical" size={8} style={{ width: '100%' }}>
          {EXAMPLE_QUESTIONS.map((q, i) => (
            <Card
              key={i}
              size="small"
              hoverable
              onClick={() => {
                logger.info('示例问题点击，填入输入框:', q);
                setFillInputText(q);
              }}
              style={{
                borderRadius: 8,
                fontSize: 13,
                cursor: 'pointer',
                border: `1px solid ${isDark ? '#303030' : '#e8e8e8'}`,
              }}
              styles={{ body: { padding: '8px 12px' } }}
            >
              <Text style={{ fontSize: 13 }}>{q}</Text>
            </Card>
          ))}
        </Space>
      </div>

      {/* 右侧: 对话区域 */}
      <div style={{ flex: 1, overflow: 'hidden' }}>
        <ChatContainer
          onSend={handleSend}
          isLoading={isLoading}
          isAgentMode={agentMode}
          fillInputText={fillInputText}
          onFillInputTextConsumed={() => setFillInputText(undefined)}
          onViewReasoning={handleViewReasoning}
        />
      </div>

      {/* Phase 2: 思维链侧边抽屉 */}
      <ThoughtChainDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        steps={drawerSteps}
      />
    </div>
  );
}
