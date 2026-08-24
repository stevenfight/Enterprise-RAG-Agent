// -*- coding: utf-8 -*-
/**
 * 图表数据表格展示组件
 */

import { Table } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { ChartData } from '../../types/chart';

interface ChartTableProps {
  data: ChartData;
  pagination?: boolean;
}

type TableRecord = Record<string, string>;

export default function ChartTable({ data, pagination = false }: ChartTableProps) {
  const isTable = data.chart_type === 'table' && data.columns && data.rows;
  const dataSource: TableRecord[] = isTable
    ? data.rows!.map((row, index) => {
        const record: TableRecord = { _key: String(index) };
        data.columns!.forEach((column, columnIndex) => {
          record[column] = row[columnIndex] ?? '-';
        });
        return record;
      })
    : (data.labels || []).map((label, index) => ({
        key: String(index),
        label,
        value: String((data.values || [])[index] ?? '-'),
      }));

  const columns: ColumnsType<TableRecord> = isTable
    ? data.columns!.map((column) => ({
        title: column,
        dataIndex: column,
        key: column,
        render: (value: string) => <span style={{ fontSize: 13 }}>{value}</span>,
      }))
    : [
        { title: data.xlabel || '类别', dataIndex: 'label', key: 'label' },
        { title: data.ylabel || '数值', dataIndex: 'value', key: 'value', align: 'right' },
      ];

  return (
    <Table
      dataSource={dataSource}
      columns={columns}
      rowKey={isTable ? '_key' : 'key'}
      pagination={pagination ? (dataSource.length > 15 ? { pageSize: 15, size: 'small' } : false) : false}
      size="small"
      bordered
      style={{ borderRadius: 8 }}
    />
  );
}
