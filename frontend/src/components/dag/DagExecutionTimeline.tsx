interface DagExecutionTimelineProps {
  batches: string[][];
  nodeLabels: Record<string, string>;
}

export default function DagExecutionTimeline({ batches, nodeLabels }: DagExecutionTimelineProps) {
  if (batches.length === 0) return null;

  return (
    <section className="dag-execution-timeline" aria-label="执行批次时间线">
      <div className="dag-execution-timeline__heading">
        <span>执行批次</span>
        <span className="dag-execution-timeline__count">{batches.length} 个阶段</span>
      </div>
      <div className="dag-execution-timeline__track">
        {batches.map((batch, index) => (
          <article key={index} className="dag-execution-step">
            <div className="dag-execution-step__marker">{index + 1}</div>
            <div className="dag-execution-step__body">
              <strong>第 {index + 1} 批</strong>
              <div className="dag-execution-step__nodes">
                {batch.map((nodeId) => (
                  <span key={nodeId} className="dag-execution-step__node">
                    {nodeLabels[nodeId] || nodeId}
                  </span>
                ))}
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
