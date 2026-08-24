/** Phase 2 共享常量: 任务类型颜色映射 */
export const TYPE_COLORS = {
  retrieve: '#98D8C8',
  calculate: '#FAD4B8',
  compare: '#A8D8EA',
  chart: '#F4B8C8',
  verify: '#C8B8D8',
  report: '#B8A9C9',
};

export type DagNodeType = keyof typeof TYPE_COLORS;

export const TYPE_NAMES: Record<DagNodeType, string> = {
  retrieve: '数据检索',
  calculate: '指标计算',
  compare: '多公司对比',
  chart: '图表生成',
  verify: '结果验证',
  report: '汇总输出',
};
