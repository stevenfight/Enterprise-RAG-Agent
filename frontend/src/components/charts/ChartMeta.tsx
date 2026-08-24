import { ClockCircleOutlined, FileTextOutlined } from '@ant-design/icons';
import type { ChartData } from '../../types/chart';

interface ChartMetaProps {
  data: Pick<ChartData, 'file_name' | 'generated_at' | 'xlabel' | 'ylabel'>;
}

export default function ChartMeta({ data }: ChartMetaProps) {
  const items = [
    data.xlabel && `横轴：${data.xlabel}`,
    data.ylabel && `纵轴：${data.ylabel}`,
    data.file_name && `来源：${data.file_name}`,
    data.generated_at && `生成于：${data.generated_at.replace('T', ' ').slice(0, 19)}`,
  ].filter(Boolean) as string[];

  if (items.length === 0) return null;

  return (
    <div className="chart-meta" role="group" aria-label="图表信息">
      {items.map((item) => (
        <span key={item} className="chart-meta__item">
          {item.startsWith('来源') ? <FileTextOutlined /> : item.startsWith('生成于') ? <ClockCircleOutlined /> : null}
          {item}
        </span>
      ))}
    </div>
  );
}
