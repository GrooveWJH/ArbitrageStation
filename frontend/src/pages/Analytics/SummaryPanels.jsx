import React from 'react';
import {
  Card,
  Col,
  Row,
  Space,
  Tag,
  Tooltip,
} from 'antd';
import { ExclamationCircleOutlined } from '@ant-design/icons';
import { TermLabel } from '../../components/TermHint';
import { fmtTime } from '../../utils/time';
import { PnlText, QualityTag } from './renderers';

export function SummaryMetaCard({
  scope,
  summary,
  coveragePct,
  dailyReconcile,
  anomalyStrategyCount,
}) {
  return (
    <Card size="small" style={{ marginBottom: 12 }}>
      <Space wrap size={12}>
        <span style={{ color: '#666' }}>scope:</span>
        <Tag color={scope === 'active' ? 'blue' : 'default'}>{scope}</Tag>
        <span style={{ color: '#666' }}>as_of:</span>
        <Tag>{fmtTime(summary?.as_of) || '-'}</Tag>
        <span style={{ color: '#666' }}>timezone:</span>
        <Tag>{summary?.timezone || 'UTC+8'}</Tag>
        <span style={{ color: '#666' }}>
          <TermLabel label="funding_quality" term="funding_quality" />
          :
        </span>
        <QualityTag value={summary?.funding_quality || summary?.quality} />
        <span style={{ color: '#666' }}>funding_coverage:</span>
        <Tag color={coveragePct == null ? 'default' : coveragePct >= 98 ? 'green' : coveragePct > 0 ? 'orange' : 'red'}>
          {coveragePct == null ? 'n/a' : `${coveragePct.toFixed(1)}%`}
        </Tag>
        <span style={{ color: '#666' }}>daily_reconcile:</span>
        <Tag color={dailyReconcile?.passed ? 'green' : dailyReconcile ? 'red' : 'default'}>
          {dailyReconcile ? `${dailyReconcile.trade_date_cn} ${dailyReconcile.passed ? 'pass' : 'fail'}` : 'n/a'}
        </Tag>
        <span style={{ color: '#666' }}>anomaly_strategies:</span>
        <Tag color={anomalyStrategyCount > 0 ? 'red' : 'green'}>{anomalyStrategyCount}</Tag>
      </Space>
    </Card>
  );
}

export function WarningsCard({ warnings }) {
  if (warnings.length === 0) return null;
  return (
    <Card
      size="small"
      style={{ marginBottom: 12, borderColor: '#ffccc7', background: '#fff2f0' }}
      title={(
        <Space>
          <ExclamationCircleOutlined style={{ color: '#cf1322' }} />
          <span>Warnings</span>
          <Tag color="red">{warnings.length}</Tag>
        </Space>
      )}
    >
      <Space wrap>
        {warnings.map((w) => (
          <Tag key={w} color="red">
            {w}
          </Tag>
        ))}
      </Space>
    </Card>
  );
}

export function PnlOverviewRow({ summary }) {
  return (
    <Row gutter={12} style={{ marginBottom: 12 }}>
      <Col span={6}>
        <Card size="small">
          <div style={{ color: '#888', fontSize: 12 }}>
            <TermLabel label="Total PnL" term="total_pnl" />
          </div>
          <div style={{ fontSize: 22, fontWeight: 700 }}>
            <PnlText value={summary?.total_pnl_usdt} />
          </div>
        </Card>
      </Col>
      <Col span={6}>
        <Card size="small">
          <div style={{ color: '#888', fontSize: 12 }}>
            <TermLabel label="Spread PnL" term="spread_pnl" />
          </div>
          <div style={{ fontSize: 22, fontWeight: 700 }}>
            <PnlText value={summary?.spread_pnl_usdt} />
          </div>
        </Card>
      </Col>
      <Col span={6}>
        <Card size="small">
          <div style={{ color: '#888', fontSize: 12 }}>
            <TermLabel label="Funding PnL" term="funding_pnl" />
          </div>
          <div style={{ fontSize: 22, fontWeight: 700 }}>
            {summary?.funding_pnl_usdt == null ? <Tag color="red">missing</Tag> : <PnlText value={summary?.funding_pnl_usdt} />}
          </div>
        </Card>
      </Col>
      <Col span={6}>
        <Card size="small">
          <div style={{ color: '#888', fontSize: 12 }}>
            <TermLabel label="Fee" term="fee_usdt" />
          </div>
          <div style={{ fontSize: 22, fontWeight: 700, color: '#cf1322' }}>
            -
            {Number(summary?.fee_usdt || 0).toFixed(4)}
            {' '}
            U
          </div>
        </Card>
      </Col>
    </Row>
  );
}

export function QualityAndWinRateRow({
  summary,
  coveragePct,
  captured,
  expected,
  winCount,
  closedWithTotalCount,
  winRate,
  dailyReconcile,
}) {
  return (
    <Row gutter={12} style={{ marginBottom: 16 }}>
      <Col span={12}>
        <Card size="small" title={<TermLabel label="Data Quality" term="quality" />}>
          <Space wrap>
            <span>quality:</span>
            <QualityTag value={summary?.quality} />
            <span>coverage:</span>
            {coveragePct == null ? <span style={{ color: '#999' }}>n/a</span> : <span>{coveragePct.toFixed(1)}%</span>}
            <span>events:</span>
            <span>
              {captured}
              /
              {expected}
            </span>
            <span>slippage policy:</span>
            <Tag>{summary?.slippage_policy || 'excluded_from_total'}</Tag>
          </Space>
        </Card>
      </Col>
      <Col span={12}>
        <Card size="small" title="Closed Win Rate">
          <Space>
            <span>
              {winCount}
              /
              {closedWithTotalCount}
            </span>
            <Tag color={winRate >= 60 ? 'green' : winRate >= 40 ? 'orange' : 'red'}>{winRate.toFixed(1)}%</Tag>
            <span style={{ color: '#888' }}>reconcile:</span>
            <Tag color={summary?.reconciliation?.passed ? 'green' : 'red'}>
              {summary?.reconciliation?.passed ? 'pass' : 'fail'}
            </Tag>
            <span style={{ color: '#888' }}>daily:</span>
            <Tag color={dailyReconcile?.passed ? 'green' : dailyReconcile ? 'red' : 'default'}>
              {dailyReconcile ? `${dailyReconcile.trade_date_cn} ${dailyReconcile.passed ? 'pass' : 'fail'}` : 'n/a'}
            </Tag>
            {dailyReconcile ? (
              <Tooltip title={`abs=${Number(dailyReconcile.abs_diff || 0).toFixed(6)}, pct=${(Number(dailyReconcile.pct_diff || 0) * 100).toFixed(4)}%`}>
                <Tag>{`diff ${Number(dailyReconcile.abs_diff || 0).toFixed(4)}U`}</Tag>
              </Tooltip>
            ) : null}
          </Space>
        </Card>
      </Col>
    </Row>
  );
}

export function StatusOverviewRow({ statusOverview }) {
  return (
    <Row gutter={12} style={{ marginBottom: 12 }}>
      <Col span={8}>
        <Card size="small">
          <div style={{ color: '#888', fontSize: 12 }}>
            <TermLabel label="Started" term="started_count" />
          </div>
          <div style={{ fontSize: 22, fontWeight: 700, color: '#1677ff' }}>{Number(statusOverview.started_count || 0)}</div>
        </Card>
      </Col>
      <Col span={8}>
        <Card size="small">
          <div style={{ color: '#888', fontSize: 12 }}>
            <TermLabel label="Closed" term="closed_count" />
          </div>
          <div style={{ fontSize: 22, fontWeight: 700, color: '#52c41a' }}>{Number(statusOverview.closed_count || 0)}</div>
        </Card>
      </Col>
      <Col span={8}>
        <Card size="small">
          <div style={{ color: '#888', fontSize: 12 }}>
            <TermLabel label="Continued" term="continued_count" />
          </div>
          <div style={{ fontSize: 22, fontWeight: 700, color: '#fa8c16' }}>{Number(statusOverview.continued_count || 0)}</div>
        </Card>
      </Col>
    </Row>
  );
}
