import React from 'react';
import {
  Card,
  Col,
  Progress,
  Row,
  Statistic,
} from 'antd';

export default function StatsCards({
  stats,
  totalActive,
  maxTotal,
  fundingCnt,
  spreadCnt,
  usedPct,
}) {
  const s = stats || {};

  return (
    <Row gutter={12} style={{ marginBottom: 16 }}>
      <Col span={4}>
        <Card size="small">
          <Statistic
            title="价差持仓中"
            value={s.open_count ?? 0}
            valueStyle={{ color: (s.open_count ?? 0) > 0 ? '#1677ff' : '#999' }}
          />
        </Card>
      </Col>
      <Col span={4}>
        <Card size="small">
          <Statistic
            title="浮动盈亏"
            value={s.total_unrealized ?? 0}
            precision={4}
            suffix="U"
            valueStyle={{ color: (s.total_unrealized ?? 0) >= 0 ? '#3f8600' : '#cf1322' }}
          />
        </Card>
      </Col>
      <Col span={4}>
        <Card size="small">
          <Statistic
            title="已实现盈亏"
            value={s.total_realized ?? 0}
            precision={4}
            suffix="U"
            valueStyle={{ color: (s.total_realized ?? 0) >= 0 ? '#3f8600' : '#cf1322' }}
          />
        </Card>
      </Col>
      <Col span={4}>
        <Card size="small">
          <Statistic
            title="综合盈亏"
            value={s.combined_pnl ?? 0}
            precision={4}
            suffix="U"
            valueStyle={{ color: (s.combined_pnl ?? 0) >= 0 ? '#3f8600' : '#cf1322' }}
          />
        </Card>
      </Col>
      <Col span={4}>
        <Card size="small">
          <Statistic
            title={`胜率 (${s.closed_count ?? 0}笔)`}
            value={s.win_rate ?? 0}
            precision={1}
            suffix="%"
            valueStyle={{ color: (s.win_rate ?? 0) >= 50 ? '#3f8600' : '#cf1322' }}
          />
        </Card>
      </Col>
      <Col span={4}>
        <Card
          size="small"
          title={<span style={{ fontSize: 12, color: '#888' }}>仓位占用 {totalActive}/{maxTotal}</span>}
          bodyStyle={{ paddingTop: 8 }}
        >
          <Progress
            percent={usedPct}
            size="small"
            status={usedPct >= 100 ? 'exception' : usedPct >= 80 ? 'active' : 'normal'}
            format={() => `${totalActive}/${maxTotal}`}
          />
          <div style={{ fontSize: 11, color: '#888', marginTop: 4, display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: '#1677ff' }}>费率 {fundingCnt}</span>
            <span style={{ color: '#722ed1' }}>价差 {spreadCnt}</span>
          </div>
        </Card>
      </Col>
    </Row>
  );
}
