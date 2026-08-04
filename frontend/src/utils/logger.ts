// -*- coding: utf-8 -*-
/**
 * 前端统一日志工具
 * 格式: [时间] [组件名] [级别] 消息
 */

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

const LEVEL_COLORS: Record<LogLevel, string> = {
  debug: '#8c8c8c',
  info: '#1890ff',
  warn: '#faad14',
  error: '#ff4d4f',
};

function timestamp(): string {
  const d = new Date();
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}.${d.getMilliseconds().toString().padStart(3, '0')}`;
}

/** 创建组件级 logger */
export function createLogger(componentName: string) {
  const prefix = `[${componentName}]`;

  const log = (level: LogLevel, ...args: unknown[]) => {
    const ts = timestamp();
    const color = LEVEL_COLORS[level];
    const style = `color:${color};font-weight:bold;`;

    switch (level) {
      case 'error':
        console.error(`%c${ts} ${prefix}`, style, ...args);
        break;
      case 'warn':
        console.warn(`%c${ts} ${prefix}`, style, ...args);
        break;
      case 'debug':
        console.debug(`%c${ts} ${prefix}`, style, ...args);
        break;
      default:
        console.log(`%c${ts} ${prefix}`, style, ...args);
    }
  };

  return {
    debug: (...args: unknown[]) => log('debug', ...args),
    info: (...args: unknown[]) => log('info', ...args),
    warn: (...args: unknown[]) => log('warn', ...args),
    error: (...args: unknown[]) => log('error', ...args),

    /** 渲染开始日志 */
    renderStart: (props?: Record<string, unknown>) => {
      log('info', '渲染开始', props || '');
    },

    /** 渲染结束日志 */
    renderEnd: (extra?: string) => {
      log('info', '渲染结束', extra || '');
    },

    /** 渲染错误日志 */
    renderError: (err: unknown) => {
      log('error', '渲染异常:', err);
    },
  };
}
