// -*- coding: utf-8 -*-
/**
 * 财务格式化工具
 * - Markdown -> HTML 转换（含表格美化）
 * - 财务 KPI 自动提取
 */

import { monoFont } from '@/styles/theme';

/** KPI 数据项 */
export interface KPIItem {
  name: string;
  value: string;
  unit: string;
  type: 'revenue' | 'profit' | 'growth' | 'roe' | 'margin' | 'other';
  isPositive?: boolean;
}

/** 从文本中提取财务 KPI */
export function extractFinancialKPIs(text: string): KPIItem[] {
  const kpis: KPIItem[] = [];
  const seen = new Set<string>();

  const add = (key: string, item: KPIItem) => {
    if (!seen.has(key)) {
      seen.add(key);
      kpis.push(item);
    }
  };

  // 营业收入 / 营收 / 收入
  const revenueRe = /营收[收入]?[：:\s]*([\d,.]+)\s*亿元/g;
  let m: RegExpExecArray | null;
  while ((m = revenueRe.exec(text)) !== null) {
    add(`revenue-${m[1]}`, {
      name: '营业收入',
      value: m[1],
      unit: '亿元',
      type: 'revenue',
    });
  }

  // 净利润
  const profitRe = /净利润[：:\s]*([\d,.]+)\s*亿元/g;
  while ((m = profitRe.exec(text)) !== null) {
    add(`profit-${m[1]}`, {
      name: '净利润',
      value: m[1],
      unit: '亿元',
      type: 'profit',
    });
  }

  // 同比增长（正值）
  const growthPosRe = /同比(?:增长|上升|提升)[：:\s]*\+?([\d,.]+)\s*%/g;
  while ((m = growthPosRe.exec(text)) !== null) {
    add(`growth-pos-${m[1]}`, {
      name: '同比增长',
      value: `+${m[1]}`,
      unit: '%',
      type: 'growth',
      isPositive: true,
    });
  }

  // 同比增长（负值）
  const growthNegRe = /同比(?:下降|减少|降低)[：:\s]*([\d,.]+)\s*%/g;
  while ((m = growthNegRe.exec(text)) !== null) {
    add(`growth-neg-${m[1]}`, {
      name: '同比下降',
      value: `-${m[1]}`,
      unit: '%',
      type: 'growth',
      isPositive: false,
    });
  }

  // ROE
  const roeRe = /ROE[：:\s]*([\d,.]+)\s*%/gi;
  while ((m = roeRe.exec(text)) !== null) {
    add(`roe-${m[1]}`, {
      name: 'ROE',
      value: m[1],
      unit: '%',
      type: 'roe',
    });
  }

  // 毛利率
  const marginRe = /毛利率[：:\s]*([\d,.]+)\s*%/g;
  while ((m = marginRe.exec(text)) !== null) {
    add(`margin-${m[1]}`, {
      name: '毛利率',
      value: m[1],
      unit: '%',
      type: 'margin',
    });
  }

  return kpis.slice(0, 6); // 最多 6 个
}

/** 检测单元格是否为纯数字/百分比/货币 */
export function isNumericCell(text: string): boolean {
  const t = text.trim();
  if (!t) return false;
  // 匹配纯数字、千分位、小数、百分比、正负号、货币符号
  return /^[+-]?[\d\s,.+%¥$€£]+$/.test(t) && /\d/.test(t);
}

/** Markdown -> HTML 转换（增强版，支持表格美化） */
export function formatMarkdown(text: string, isDark = false): string {
  const lines = text.split('\n');
  const result: string[] = [];
  let inTable = false;
  let tableBuffer: string[] = [];

  // 表格样式常量
  const tableWrapper = isDark
    ? 'border-collapse:separate;width:100%;margin:12px 0;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.2);border-spacing:0;background:#252236'
    : 'border-collapse:separate;width:100%;margin:12px 0;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.06);border-spacing:0;background:#FFFFFF';

  const headerStyle = isDark
    ? 'padding:10px 14px;color:#FFFFFF;font-size:13px;font-weight:600;text-align:left;background:linear-gradient(135deg,#7A6B9C 0%,#5A4B7C 100%)'
    : 'padding:10px 14px;color:#FFFFFF;font-size:13px;font-weight:600;text-align:left;background:linear-gradient(135deg,#B8A9C9 0%,#9B8EC4 100%)';

  const rowEven = isDark ? '#2A2740' : '#FAF8FC';
  const rowOdd = isDark ? '#252236' : '#FFFFFF';

  function flushTable() {
    if (tableBuffer.length === 0) return;

    // 解析表格数据
    const rows: string[][] = [];
    let headerCells: string[] | null = null;

    for (const line of tableBuffer) {
      const cells = line.trim().split('|').filter(c => c.trim() !== '');
      // 跳过分隔行
      if (cells.every(c => /^[-:]+$/.test(c.trim()))) continue;

      const trimmed = cells.map(c => c.trim());
      if (headerCells === null) {
        headerCells = trimmed;
      } else {
        rows.push(trimmed);
      }
    }

    if (!headerCells || rows.length === 0) {
      tableBuffer = [];
      return;
    }

    // 判断哪些列是数字列
    const colCount = headerCells.length;
    const numericCols = new Set<number>();
    for (let c = 0; c < colCount; c++) {
      let allNumeric = true;
      for (const row of rows) {
        if (row[c] && !isNumericCell(row[c])) {
          allNumeric = false;
          break;
        }
      }
      if (allNumeric) numericCols.add(c);
    }

    // 渲染表头
    const theadHtml = `<thead><tr>${headerCells.map((c, idx) => {
      const align = numericCols.has(idx) ? 'text-align:right' : 'text-align:left';
      const font = numericCols.has(idx) ? `font-family:${monoFont}` : '';
      return `<th style="${headerStyle};${align};${font}">${processInline(c)}</th>`;
    }).join('')}</tr></thead>`;

    // 渲染数据行（斑马纹）
    const tbodyHtml = `<tbody>${rows.map((row, rIdx) => {
      const bg = rIdx % 2 === 0 ? rowOdd : rowEven;
      return `<tr style="background:${bg};transition:background 0.2s" onmouseout="this.style.background='${bg}'" onmouseover="this.style.background='${isDark ? 'rgba(184,169,201,0.12)' : 'rgba(184,169,201,0.08)'}'">${row.map((c, cIdx) => {
        const align = numericCols.has(cIdx) ? 'text-align:right' : 'text-align:left';
        const font = numericCols.has(cIdx) ? `font-family:${monoFont}` : '';
        // 数字颜色：正值绿、负值红
        let color = '';
        if (numericCols.has(cIdx)) {
          const num = parseFloat(c.replace(/[,+%\s]/g, ''));
          if (!isNaN(num)) {
            if (c.includes('-') || num < 0) {
              color = `color:${isDark ? '#E88B8B' : '#CF4A4A'}`;
            } else if (num > 0) {
              color = `color:${isDark ? '#7ECB9A' : '#2E9A5E'}`;
            }
          }
        }
        return `<td style="padding:8px 14px;border:none;font-size:13px;${align};${font};${color}">${processInline(c)}</td>`;
      }).join('')}</tr>`;
    }).join('')}</tbody>`;

    result.push(`<table style="${tableWrapper}">${theadHtml}${tbodyHtml}</table>`);
    tableBuffer = [];
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // 检测表格行
    if (line.trim().startsWith('|') && line.trim().endsWith('|')) {
      // 检测"数据来源"等说明性行，结束表格
      const cells = line.trim().split('|').filter(c => c.trim() !== '');
      const rowText = cells.join('');
      if (/数据来源|资料来源|来源[:：]|注[:：]|说明[:：]/.test(rowText)) {
        flushTable();
        result.push(`<div style="font-size:12px;color:#999;margin-top:4px">${processInline(cells.map(c => c.trim()).join(' | '))}</div>`);
        inTable = false;
        continue;
      }

      inTable = true;
      tableBuffer.push(line);
      continue;
    }

    // 表格结束
    if (inTable) {
      flushTable();
      inTable = false;
    }

    if (line.trim() === '') {
      result.push('<br/>');
      continue;
    }

    result.push(processLine(line));
  }

  // 结尾处理未关闭的表格
  if (inTable) {
    flushTable();
  }

  return result.join('\n');
}

/** 处理单行（非表格行） */
function processLine(line: string): string {
  let html = line;

  // 图片语法 ![alt](url) -- 必须在链接之前处理
  html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_match, alt, url) => {
    return `<img src="${url}" alt="${alt}" style="max-width:100%;border-radius:8px;margin:8px 0;" />`;
  });

  // 链接语法 [text](url)
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, text, url) => {
    if (match.includes('<img')) return match;
    return `<a href="${url}" target="_blank" rel="noopener noreferrer" style="color:#5BAA98;text-decoration:underline;">${text}</a>`;
  });

  // 标题语法 ### / ## / #
  html = html.replace(/^### (.+)$/gm, '<h4 style="margin:8px 0 4px;font-size:14px;font-weight:600;">$1</h4>');
  html = html.replace(/^## (.+)$/gm, '<h3 style="margin:10px 0 6px;font-size:15px;font-weight:700;">$1</h3>');
  html = html.replace(/^# (.+)$/gm, '<h2 style="margin:12px 0 8px;font-size:16px;font-weight:700;">$1</h2>');

  html = processInline(html);

  return html;
}

/** 处理行内格式：粗体、斜体、代码 */
function processInline(html: string): string {
  // 粗体 **text**
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  // 斜体 *text*
  html = html.replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, '<em>$1</em>');
  // 行内代码 `code`
  html = html.replace(/`(.+?)`/g, `<code style="background:rgba(0,0,0,0.06);padding:2px 6px;border-radius:3px;font-family:${monoFont};font-size:13px">$1</code>`);
  return html;
}
