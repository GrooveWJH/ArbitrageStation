import React, { useMemo, useState } from 'react';
import {
  Button,
  Card,
  Empty,
  Select,
  Space,
} from 'antd';
import {
  LineChartOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { Line } from '@ant-design/charts';
import { useAnalyticsEquityCurveQuery } from '../../services/queries/analyticsQueries';

export default function EquityCurveCard({ days }) {
  const {
    data: eq,
    isLoading,
    isFetching,
    isFetched,
    refetch,
  } = useAnalyticsEquityCurveQuery(days);
  const isInitialLoading = isLoading && !isFetched;
  const [view, setView] = useState('equity');

  const chartData = useMemo(() => {
    if (!eq?.points?.length) return [];
    if (view === 'equity') {
      return eq.points.map((p) => ({ time: p.time, value: p.total, type: '权益' }));
    }
    return eq.points.map((p) => ({ time: p.time, value: p.profit, type: '收益' }));
  }, [eq, view]);

  const color = view === 'equity' ? '#1677ff' : '#52c41a';
  const config = {
    data: chartData,
    encode: { x: 'time', y: 'value', color: 'type' },
    smooth: true,
    animation: false,
    style: { stroke: color, lineWidth: 2 },
    point: chartData.length <= 30 ? { size: 3 } : false,
    legend: {
      color: {
        itemLabelFill: '#c8d8f0',
      },
    },
  };

  return (
    <Card
      size="small"
      style={{ marginBottom: 16 }}
      title={(
        <Space>
          <LineChartOutlined style={{ color: '#1677ff' }} />
          <span>权益曲线</span>
        </Space>
      )}
      extra={(
        <Space>
          <Select
            size="small"
            value={view}
            style={{ width: 120 }}
            onChange={setView}
            options={[
              { label: '权益', value: 'equity' },
              { label: '收益', value: 'profit' },
            ]}
          />
          <Button
            size="small"
            icon={<ReloadOutlined />}
            onClick={() => {
              void refetch();
            }}
            loading={isFetching && !isInitialLoading}
          />
        </Space>
      )}
    >
      {!isInitialLoading && (!eq?.points || eq.points.length === 0) ? (
        <Empty description={<span style={{ color: '#8ba3c7' }}>暂无权益快照</span>} />
      ) : (
        <div style={{ height: 260 }}>
          <Line {...config} />
        </div>
      )}
    </Card>
  );
}
