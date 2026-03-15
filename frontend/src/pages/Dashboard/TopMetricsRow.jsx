import React from 'react';
import { ArrowDownOutlined, ArrowUpOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { Card, Col, Row, Statistic } from 'antd';
import { TermLabel } from '../../components/TermHint';

export default function TopMetricsRow({ pnlSummary }) {
  const displayPnl = pnlSummary?.total_pnl_usdt;
  const pnlPct = pnlSummary?.total_pnl_pct;
  const pnlColor = displayPnl == null ? '#999' : displayPnl >= 0 ? '#3f8600' : '#cf1322';
  const pnlIcon = displayPnl == null ? null : displayPnl >= 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />;

  return (
    <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
      <Col span={4}>
        <Card>
          <Statistic title="活跃策略" value={pnlSummary.active_strategies ?? 0} prefix={<ThunderboltOutlined />} />
        </Card>
      </Col>
      <Col span={4}>
        <Card>
          <Statistic title="持仓数量" value={pnlSummary.open_positions ?? 0} />
        </Card>
      </Col>
      <Col span={5}>
        <Card>
          <Statistic
            title={<TermLabel label="策略总盈亏 (v2, USDT)" term="total_pnl" />}
            value={displayPnl == null ? '--' : Number(displayPnl)}
            precision={displayPnl == null ? undefined : 2}
            valueStyle={{ color: pnlColor }}
            prefix={pnlIcon}
          />
        </Card>
      </Col>
      <Col span={4}>
        <Card>
          <Statistic
            title={<TermLabel label="收益率 (v2)" term="total_pnl_pct" />}
            value={pnlPct == null ? '--' : Number(pnlPct)}
            precision={pnlPct == null ? undefined : 2}
            suffix="%"
            valueStyle={{ color: pnlPct == null ? '#999' : Number(pnlPct) >= 0 ? '#3f8600' : '#cf1322' }}
          />
        </Card>
      </Col>
      <Col span={4}>
        <Card>
          <Statistic title="今日成交" value={pnlSummary.today_trades ?? 0} suffix="笔" />
        </Card>
      </Col>
      <Col span={3}>
        <Card>
          <Statistic title="在线交易所" value={pnlSummary.active_exchanges ?? 0} />
        </Card>
      </Col>
    </Row>
  );
}
