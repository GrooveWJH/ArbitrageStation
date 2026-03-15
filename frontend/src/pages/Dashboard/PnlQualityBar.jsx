import React from 'react';
import { Card, Space, Tag } from 'antd';
import { fmtTime } from '../../utils/time';
import { TermLabel } from '../../components/TermHint';

const QUALITY_COLOR = {
  ok: 'green',
  na: 'blue',
  partial: 'orange',
  stale: 'volcano',
  missing: 'red',
};

export default function PnlQualityBar({ pnlSummary }) {
  const fundingCoveragePct = pnlSummary?.funding_coverage == null ? null : Number(pnlSummary.funding_coverage) * 100.0;

  return (
    <Card size="small" style={{ marginBottom: 16 }}>
      <Space wrap size={12}>
        <span style={{ color: '#666' }}>PnL口径:</span>
        <Tag color="blue">v2</Tag>
        <span style={{ color: '#666' }}>as_of:</span>
        <Tag>{fmtTime(pnlSummary?.as_of) || '-'}</Tag>
        <span style={{ color: '#666' }}><TermLabel label="quality" term="quality" />:</span>
        <Tag color={QUALITY_COLOR[pnlSummary?.quality] || 'default'}>{pnlSummary?.quality || '-'}</Tag>
        <span style={{ color: '#666' }}><TermLabel label="funding_quality" term="funding_quality" />:</span>
        <Tag color={QUALITY_COLOR[pnlSummary?.funding_quality] || 'default'}>{pnlSummary?.funding_quality || '-'}</Tag>
        <span style={{ color: '#666' }}><TermLabel label="funding_pnl" term="funding_pnl" />:</span>
        {pnlSummary?.funding_pnl_usdt == null ? (
          <Tag color="red">missing</Tag>
        ) : (
          <Tag color={Number(pnlSummary.funding_pnl_usdt) >= 0 ? 'green' : 'red'}>
            {Number(pnlSummary.funding_pnl_usdt).toFixed(4)}U
          </Tag>
        )}
        <span style={{ color: '#666' }}><TermLabel label="coverage" term="funding_coverage" />:</span>
        <Tag color={fundingCoveragePct == null ? 'default' : fundingCoveragePct >= 98 ? 'green' : fundingCoveragePct > 0 ? 'orange' : 'red'}>
          {fundingCoveragePct == null ? 'n/a' : `${fundingCoveragePct.toFixed(1)}%`}
        </Tag>
        <span style={{ color: '#666' }}><TermLabel label="anomaly" term="quality" />:</span>
        <Tag color={Number(pnlSummary?.anomaly_strategy_count || 0) > 0 ? 'red' : 'green'}>
          {Number(pnlSummary?.anomaly_strategy_count || 0)}
        </Tag>
      </Space>
    </Card>
  );
}
