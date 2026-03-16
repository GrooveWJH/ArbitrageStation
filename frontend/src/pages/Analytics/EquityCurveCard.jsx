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
      return eq.points.map((p) => ({ time: p.time, value: p.total, type: 'equity' }));
    }
    return eq.points.map((p) => ({ time: p.time, value: p.profit, type: 'profit' }));
  }, [eq, view]);

  const color = view === 'equity' ? '#1677ff' : '#52c41a';
  const config = {
    data: chartData,
    encode: { x: 'time', y: 'value', color: 'type' },
    smooth: true,
    animation: false,
    style: { stroke: color, lineWidth: 2 },
    point: chartData.length <= 30 ? { size: 3 } : false,
  };

  return (
    <Card
      size="small"
      style={{ marginBottom: 16 }}
      title={(
        <Space>
          <LineChartOutlined style={{ color: '#1677ff' }} />
          <span>Equity Curve</span>
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
              { label: 'Equity', value: 'equity' },
              { label: 'Profit', value: 'profit' },
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
        <Empty description="No equity snapshots yet" />
      ) : (
        <div style={{ height: 260 }}>
          <Line {...config} />
        </div>
      )}
    </Card>
  );
}
