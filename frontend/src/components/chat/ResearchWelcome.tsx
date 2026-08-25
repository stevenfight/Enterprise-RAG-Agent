// -*- coding: utf-8 -*-
/** 研究工作台空会话启动页。 */
import {
  BulbOutlined,
  FileSearchOutlined,
  MessageOutlined,
  NodeIndexOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons';

interface ResearchWelcomeProps {
  quickCommands?: string[];
  companyName?: string;
  mode?: 'rag' | 'agent';
  onSend: (content: string) => void;
}

const CAPABILITIES = [
  { icon: <MessageOutlined />, title: '回答与数据', description: '从已接入年报中生成结构化回答' },
  { icon: <FileSearchOutlined />, title: '证据核验', description: '回答完成后查看对应来源与页码' },
  { icon: <NodeIndexOutlined />, title: '分析过程', description: '深度分析时查看已脱敏的执行摘要' },
];

export default function ResearchWelcome({ quickCommands, companyName, mode = 'rag', onSend }: ResearchWelcomeProps) {
  const scope = companyName ?? '全部公司';
  const modeLabel = mode === 'agent' ? 'Agent 深度分析' : 'RAG 问答';

  return (
    <section className="research-welcome" aria-label="研究启动页">
      <div className="research-welcome__hero">
        <div className="research-welcome__emblem" aria-hidden="true">
          <SafetyCertificateOutlined />
        </div>
        <span className="research-welcome__eyebrow">证据驱动研究</span>
        <h1>从一个问题开始，<br />完成可核验的财务研究</h1>
        <p>基于已接入的年报资料生成回答，并在研究过程中保留可回看的来源和分析摘要。</p>
      </div>

      <div className="research-welcome__scope" aria-label="当前研究范围">
        <span>当前研究范围</span>
        <strong>{scope}</strong>
        <i aria-hidden="true" />
        <span>{modeLabel}</span>
      </div>

      <div className="research-welcome__launchpad">
        <div className="research-welcome__section-heading">
          <div>
            <span>开始研究</span>
            <h2>选择一个示例问题，或在下方直接提问</h2>
          </div>
          <BulbOutlined aria-hidden="true" />
        </div>
        {quickCommands && quickCommands.length > 0 && (
          <div className="research-welcome__questions">
            {quickCommands.map((command) => (
              <button key={command} type="button" className="research-welcome__question quick-command-chip" onClick={() => onSend(command)}>
                <span>{command}</span>
                <span aria-hidden="true">↗</span>
              </button>
            ))}
          </div>
        )}
      </div>

      <ul className="research-welcome__capabilities" aria-label="研究能力">
        {CAPABILITIES.map((capability) => (
          <li key={capability.title}>
            <span className="research-welcome__capability-icon" aria-hidden="true">{capability.icon}</span>
            <div>
              <strong>{capability.title}</strong>
              <span>{capability.description}</span>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
