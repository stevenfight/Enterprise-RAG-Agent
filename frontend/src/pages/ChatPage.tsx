// -*- coding: utf-8 -*-
/**
 * 对话首页
 * 集成 ChatContainer + 侧边栏配置 + 示例问题
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { Typography, Select, Slider, Switch, Radio, Tabs, Button } from 'antd';
import {
  RobotOutlined,
  SettingOutlined,
  DownOutlined,
  CloseOutlined,
} from '@ant-design/icons';
import { chatStore, selectCurrentMessages } from '@/stores/chatStore';
import { appStore } from '@/stores/appStore';
import { useTheme } from '@/hooks/useTheme';
import { colors } from '@/styles/theme';
import { queryQuestion, getCompanies, streamAgentQuery } from '@/services/chatService';
import ChatContainer from '@/components/chat/ChatContainer';
import ThoughtChainDrawer from '@/components/chat/ThoughtChainDrawer';
import ResearchContextBar from '@/components/chat/ResearchContextBar';
import EvidencePanel from '@/components/chat/EvidencePanel';
import EvidenceContent from '@/components/chat/EvidenceContent';
import AnalysisTraceContent from '@/components/chat/AnalysisTraceContent';
import type { CompanyInfo, SSEEvent, AnalysisTraceStep, SourceInfo } from '@/types/chat';
import { createLogger } from '@/utils/logger';
import { createEmptyAccumulator, applyAgentEvent } from '@/utils/agentEvent';

const logger = createLogger('ChatPage');
const { Text } = Typography;

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
  const [topN, setTopN] = useState(5);
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

  // Phase 2: 思维链侧边抽屉
  const [drawerSteps, setDrawerSteps] = useState<AnalysisTraceStep[]>([]);
  const [activeDrawer, setActiveDrawer] = useState<'sessions' | 'evidence' | 'reasoning' | null>(null);
  const [selectedEvidenceMessageId, setSelectedEvidenceMessageId] = useState<string | undefined>(undefined);
  const [highlightedEvidenceSourceIndex, setHighlightedEvidenceSourceIndex] = useState<number | undefined>(undefined);
  const [desktopEvidenceOpen, setDesktopEvidenceOpen] = useState(false);

  const handleViewReasoning = useCallback((steps: AnalysisTraceStep[]) => {
    setDrawerSteps(steps);
    setActiveDrawer('reasoning');
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
  const setResearchContext = appStore((s) => s.setResearchContext);
  const selectedCompany = appStore((s) => s.researchContext?.companyName);
  const agentMode = appStore((s) => s.researchContext?.mode === 'agent');
  const setAgentMode = (enabled: boolean) => {
    setResearchContext({ mode: enabled ? 'agent' : 'rag' });
  };
  const requestIdRef = useRef(0);
  const ragAbortRef = useRef<AbortController | null>(null);
  const requestCleanupRef = useRef<(() => void) | null>(null);
  const latestAssistantMessage = [...currentMessages].reverse().find(
    (message) => message.role === 'assistant',
  );
  const selectedEvidenceMessage = currentMessages.find(
    (message) => message.id === selectedEvidenceMessageId && message.role === 'assistant',
  ) ?? latestAssistantMessage;
  const latestSources = selectedEvidenceMessage?.sources ?? [];

  useEffect(() => {
    setSelectedEvidenceMessageId(undefined);
    setHighlightedEvidenceSourceIndex(undefined);
    setDesktopEvidenceOpen(false);
  }, [currentSessionId]);

  /** 1200px 以下延续既有 Drawer，桌面端才打开右侧证据工作栏。 */
  const openEvidenceWorkspace = useCallback((messageId?: string, sourceIndex?: number) => {
    const targetMessageId = messageId ?? latestAssistantMessage?.id;
    const targetMessage = currentMessages.find(
      (message) => message.id === targetMessageId && message.role === 'assistant',
    );
    if (sourceIndex !== undefined && !targetMessage?.sources?.some((source) => source.index === sourceIndex)) return;

    setSelectedEvidenceMessageId(targetMessageId);
    setHighlightedEvidenceSourceIndex(sourceIndex);
    const useDrawer = typeof window !== 'undefined'
      && typeof window.matchMedia === 'function'
      && window.matchMedia('(max-width: 1199px)').matches;
    if (useDrawer) {
      setDesktopEvidenceOpen(false);
      setActiveDrawer('evidence');
      return;
    }
    setActiveDrawer(null);
    setDesktopEvidenceOpen(true);
  }, [currentMessages, latestAssistantMessage?.id]);

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
      requestIdRef.current += 1;
      requestCleanupRef.current?.();
      requestCleanupRef.current = null;
      setLoading(false);
    };
  }, [setLoading]);

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
      const requestSessionId = currentSessionId;
      const requestId = ++requestIdRef.current;
      const isRequestActive = () => requestId === requestIdRef.current;
      requestCleanupRef.current?.();
      logger.info('发送消息:', {
        content: content.slice(0, 50),
        company: selectedCompany,
        topN,
        agentMode,
        sessionId: currentSessionId,
      });

      addUserMessage(content, requestSessionId);
      setLoading(true);

      if (agentMode) {
        // Phase 2: Agent SSE 流式模式
        const agentStartTime = Date.now();
        logger.info('Agent SSE 模式启用', { query: content.slice(0, 80), timestamp: new Date().toISOString() });

        let acc = createEmptyAccumulator();
        let fullAnswer = '';
        let answerReceived = false;
        let wasForcedStop = false; // 是否因步数上限强制终止
        let assistantMessageCreated = false; // 是否已创建 assistant 占位消息
        let checkDone: ReturnType<typeof setInterval> | undefined;
        let timeoutId: ReturnType<typeof setTimeout> | undefined;
        let es: ReturnType<typeof streamAgentQuery> | null = null;
        const cleanupStream = () => {
          if (checkDone) clearInterval(checkDone);
          if (timeoutId) clearTimeout(timeoutId);
          if (sseRef.current === es) sseRef.current = null;
          es?.close();
        };
        requestCleanupRef.current = cleanupStream;

        // 先关闭之前的 SSE 连接
        if (sseRef.current) {
          logger.debug('关闭之前的 SSE 连接');
          sseRef.current.close();
        }

        es = streamAgentQuery(
          content,
          {
            company_name: selectedCompany || undefined,
            max_steps: agentMaxSteps,
            conversation_id: currentSessionId,
          },
          (event: SSEEvent) => {
            if (!isRequestActive()) return;
            acc = applyAgentEvent(acc, event);

            // 首次出现安全分析步骤时创建 assistant 占位消息。
            if (!assistantMessageCreated && acc.analysisTrace.length > 0) {
              if (!isRequestActive()) return;
              addAssistantMessage('分析中...', [], [...acc.analysisTrace], requestSessionId, undefined, { mode: 'agent', companyName: selectedCompany ?? '全部公司' });
              assistantMessageCreated = true;
              return;
            }

            // 同步事件到 store
            const partial: { content?: string; analysisTrace?: AnalysisTraceStep[]; sources?: SourceInfo[]; researchMeta?: { mode: 'rag' | 'agent'; companyName: string; processingTimeMs?: number } } = {};
            if (acc.analysisTrace.length > 0) partial.analysisTrace = acc.analysisTrace;

            if (event.type === 'answer_chunk') {
              partial.content = acc.answer;
            } else if (event.type === 'answer') {
              partial.content = acc.answer;
              partial.sources = event.sources ?? [];
              partial.researchMeta = {
                mode: 'agent',
                companyName: selectedCompany ?? '全部公司',
                ...(event.total_elapsed_ms !== undefined ? { processingTimeMs: event.total_elapsed_ms } : {}),
              };
              fullAnswer = acc.answer;
              answerReceived = true;
              logger.info('ON ANSWER 最终答案到达', { contentLen: acc.answer.length, elapsedMs: Date.now() - agentStartTime });
            }

            if (!assistantMessageCreated && partial.content !== undefined) {
              if (!isRequestActive()) return;
              addAssistantMessage(
                partial.content,
                partial.sources ?? [],
                partial.analysisTrace ? [...partial.analysisTrace] : undefined,
                requestSessionId,
                undefined,
                partial.researchMeta,
              );
              assistantMessageCreated = true;
            } else if (Object.keys(partial).length > 0) {
              if (!isRequestActive()) return;
              updateLastAssistantMessage(partial, requestSessionId);
            }

            if (event.type === 'error') {
              logger.error('SSE 错误事件:', event.content);
            } else if (event.type === 'done') {
              wasForcedStop = event.forced_stop === true;
              logger.info('SSE 流完成', {
                totalSteps: event.total_steps,
                elapsedMs: event.total_elapsed_ms,
                reasoningStepsCount: acc.analysisTrace.length,
                forcedStop: event.forced_stop,
              });
              if (event.total_elapsed_ms !== undefined && assistantMessageCreated && isRequestActive()) {
                updateLastAssistantMessage({
                  researchMeta: { mode: 'agent', companyName: selectedCompany ?? '全部公司', processingTimeMs: event.total_elapsed_ms },
                }, requestSessionId);
              }
            }
          },
          (error: Event) => {
            if (checkDone) {
              clearInterval(checkDone);
            }
            if (timeoutId) {
              clearTimeout(timeoutId);
            }
            const activeEventSource = sseRef.current;
            if (activeEventSource && activeEventSource === es) {
              activeEventSource.close();
              sseRef.current = null;
            }
            console.error(
              '%c[ChatPage] SSE ERROR %cEventSource 连接错误',
              'color: #ff4d4f; font-weight: bold;',
              'color: #333;',
              { eventPhase: error.eventPhase, type: error.type },
            );
            logger.error('SSE 连接错误:', error);
            if (isRequestActive()) addErrorMessage('Agent 推理服务连接失败，请稍后重试。', requestSessionId);
            if (isRequestActive()) setLoading(false);
          },
        );

        sseRef.current = es;
        console.log('%c[ChatPage] SSE INIT %cEventSource 已创建，等待事件...', 'color: #1890ff; font-weight: bold;', 'color: #333;', { query: content.slice(0, 30) });

        // 等待 SSE 流结束 (answer 事件到达)
        checkDone = setInterval(() => {
          if (answerReceived) {
            if (!isRequestActive()) return;
            logger.info('SSE 收到完整答案', { answerLen: fullAnswer.length, reasoningSteps: acc.analysisTrace.length, totalElapsedMs: Date.now() - agentStartTime, forcedStop: wasForcedStop });
            clearInterval(checkDone);
            if (timeoutId) {
              clearTimeout(timeoutId);
            }
            const activeEventSource = sseRef.current;
            if (activeEventSource && activeEventSource === es) {
              activeEventSource.close();
              sseRef.current = null;
            }
            // answer 事件已通过 updateLastAssistantMessage 设置内容和安全分析摘要
            // 推理步数达上限时，注入系统警告提示
            if (wasForcedStop && isRequestActive()) {
              chatStore.getState().addErrorMessage(
                `分析达到步数上限（${acc.analysisTrace.length} 步），部分数据可能未检索到。建议细化查询条件后重试。`
                , requestSessionId
              );
            }
            setLoading(false);
            requestCleanupRef.current = null;
          }
        }, 200);

        // 超时保护 (120s)
        timeoutId = setTimeout(() => {
          if (!isRequestActive()) return;
          clearInterval(checkDone);
          const activeEventSource = sseRef.current;
          if (activeEventSource && activeEventSource === es) {
            activeEventSource.close();
            sseRef.current = null;
          }
          if (!answerReceived && isRequestActive()) {
            addErrorMessage('Agent 推理超时，请尝试简化问题或关闭 Agent 模式。', requestSessionId);
          }
          setLoading(false);
          requestCleanupRef.current = null;
        }, 120000);
      } else {
        // 普通 RAG 模式 (enable_rewrite 固定为 true)
        try {
          logger.debug('调用 queryQuestion API (普通RAG模式)...');
          const controller = new AbortController();
          ragAbortRef.current = controller;
          requestCleanupRef.current = () => {
            controller.abort();
            if (ragAbortRef.current === controller) ragAbortRef.current = null;
          };
          const res = await queryQuestion({
            query: content,
            company_name: selectedCompany || undefined,
            top_n: topN,
            conversation_id: currentSessionId,
            enable_rewrite: true, // 固定开启，不再由用户控制
          }, controller.signal);
          logger.info('API 响应成功:', {
            answerLength: res.answer.length,
            sourcesCount: res.sources.length,
            processingTime: res.processing_time,
            conversationId: res.conversation_id,
          });
            if (isRequestActive()) addAssistantMessage(
              res.answer,
              res.sources,
              undefined,
              requestSessionId,
              res.comparison ?? undefined,
              { mode: 'rag', companyName: selectedCompany ?? '全部公司', processingTimeMs: Math.round(res.processing_time * 1000) },
            );
        } catch (err: unknown) {
          const errorMsg =
            err instanceof Error ? err.message : '未知错误';
          logger.error('API 请求失败:', { error: errorMsg, query: content.slice(0, 30) });
          if (!isRequestActive() || errorMsg.includes('canceled') || errorMsg.includes('cancelled') || errorMsg.includes('ERR_CANCELED')) return;
          if (errorMsg.includes('timeout') || errorMsg.includes('ECONNABORTED')) {
            addErrorMessage('请求超时，请检查网络连接或稍后重试。', requestSessionId);
          } else {
            addErrorMessage(`服务暂时不可用，请稍后重试。（${errorMsg}）`, requestSessionId);
          }
        } finally {
          if (!ragAbortRef.current?.signal.aborted && isRequestActive()) {
            ragAbortRef.current = null;
            requestCleanupRef.current = null;
            setLoading(false);
            logger.debug('请求流程结束');
          }
        }
      }
    },
    [selectedCompany, topN, agentMode, agentMaxSteps, currentSessionId, addUserMessage, setLoading, addAssistantMessage, updateLastAssistantMessage, addErrorMessage],
  );

  logger.renderEnd();

  return (
    <div className="chat-page" style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      <div className="chat-page__workspace" style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <ResearchContextBar
          companyName={selectedCompany}
          mode={agentMode ? 'agent' : 'rag'}
          configuration={(
            <section aria-label="研究配置" className="research-context-bar__configuration">
              <div className="research-context-bar__company-field">
                <Text className="research-context-bar__config-label">选择公司</Text>
                <Select
                  aria-label="选择公司"
                  value={selectedCompany}
                  onChange={(val: string | undefined) => setResearchContext({ companyName: val })}
                  placeholder="全部公司"
                  allowClear
                  className="research-context-bar__company-select"
                  options={companies.map((c) => ({ value: c.name, label: c.display_name }))}
                  notFoundContent={companiesLoaded ? '暂无数据' : '加载中...'}
                />
              </div>
              <div className="research-context-bar__agent-field">
                <Switch checked={agentMode} onChange={setAgentMode} size="small" aria-label="启用 Agent 深度推理" />
                <Text className="research-context-bar__agent-label"><RobotOutlined /> Agent</Text>
              </div>
              <div className="research-context-bar__advanced-field">
                <Button
                  type="text"
                  size="small"
                  className="research-context-bar__advanced-trigger"
                  icon={<SettingOutlined />}
                  aria-label="高级选项"
                  aria-expanded={showAdvanced}
                  onClick={() => setShowAdvanced((open) => !open)}
                >
                  高级选项 <DownOutlined className={showAdvanced ? 'research-context-bar__arrow research-context-bar__arrow--open' : 'research-context-bar__arrow'} />
                </Button>
                {showAdvanced && (
                  <div className="research-context-bar__advanced-content">
                    <Text className="research-context-bar__config-label">检索返回条数: {topN}</Text>
                    <Slider min={1} max={10} value={topN} onChange={setTopN} />
                    {agentMode && (
                      <div className="research-context-bar__steps">
                        <Text className="research-context-bar__config-label">推理步数上限</Text>
                        <Radio.Group value={agentMaxSteps} onChange={(e) => setAgentMaxSteps(e.target.value)} size="small">
                          <Radio.Button value={5}>5 步</Radio.Button>
                          <Radio.Button value={10}>10 步</Radio.Button>
                        </Radio.Group>
                        <Text className="research-context-bar__help">步数越多检索越充分，但耗时更长</Text>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </section>
          )}
          onOpenEvidence={() => openEvidenceWorkspace()}
        />
        <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
          <ChatContainer
            onSend={handleSend}
            isLoading={isLoading}
            isAgentMode={agentMode}
            onViewReasoning={handleViewReasoning}
            onViewEvidence={openEvidenceWorkspace}
            onViewCharts={(criteria) => {
              const params = new URLSearchParams({
                metric: criteria.metric_key,
                year: String(criteria.fiscal_year),
                unit: criteria.unit,
              });
              window.history.pushState({}, '', `/charts?${params.toString()}`);
              window.dispatchEvent(new PopStateEvent('popstate'));
            }}
            quickCommands={EXAMPLE_QUESTIONS}
            companyName={selectedCompany}
            researchMode={agentMode ? 'agent' : 'rag'}
            mobileSessionsOpen={activeDrawer === 'sessions'}
            onMobileSessionsOpenChange={(open) => setActiveDrawer(open ? 'sessions' : null)}
          />
        </div>
      </div>

      {desktopEvidenceOpen && (
        <aside
          className="chat-evidence-aside"
          aria-label="回答级证据"
          style={{
            width: 340,
            flexShrink: 0,
            overflow: 'auto',
            padding: 16,
            background: isDark ? colors.bgDarkCard : colors.bgCard,
            borderLeft: `1px solid ${isDark ? colors.borderDark : colors.border}`,
          }}
        >
          <div className="chat-evidence-aside__header">
            <Text strong>证据工作栏</Text>
            <Button type="text" size="small" icon={<CloseOutlined />} aria-label="关闭证据栏" onClick={() => {
              setHighlightedEvidenceSourceIndex(undefined);
              setDesktopEvidenceOpen(false);
            }} />
          </div>
          <Tabs
            defaultActiveKey="evidence"
            items={[
              { key: 'evidence', label: '证据', children: <EvidenceContent sources={latestSources} highlightedSourceIndex={highlightedEvidenceSourceIndex} /> },
              { key: 'analysis', label: '分析过程', children: <AnalysisTraceContent steps={selectedEvidenceMessage?.analysisTrace ?? []} /> },
            ]}
          />
        </aside>
      )}

      {/* Phase 2: 思维链侧边抽屉 */}
      <ThoughtChainDrawer
        open={activeDrawer === 'reasoning'}
        onClose={() => setActiveDrawer(null)}
        steps={drawerSteps}
      />
      <EvidencePanel
        open={activeDrawer === 'evidence'}
        onClose={() => {
          setHighlightedEvidenceSourceIndex(undefined);
          setActiveDrawer(null);
        }}
        sources={latestSources}
        highlightedSourceIndex={highlightedEvidenceSourceIndex}
      />
    </div>
  );
}
