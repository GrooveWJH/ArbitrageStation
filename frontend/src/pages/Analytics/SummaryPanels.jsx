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
        <span style={{ color: '#9eb8d9' }}>范围:</span>
        <Tag color={scope === 'active' ? 'blue' : 'default'}>{scope === 'active' ? '运行中' : '全部'}</Tag>
        <span style={{ color: '#9eb8d9' }}>统计时间:</span>
        <Tag>{fmtTime(summary?.as_of) || '-'}</Tag>
        <span style={{ color: '#9eb8d9' }}>时区:</span>
        <Tag>{summary?.timezone || 'UTC+8'}</Tag>
        <span style={{ color: '#9eb8d9' }}>
          <TermLabel label="资金费质量" term="funding_quality" />
          :
        </span>
        <QualityTag value={summary?.funding_quality || summary?.quality} />
        <span style={{ color: '#9eb8d9' }}>资金费覆盖率:</span>
        <Tag color={coveragePct == null ? 'default' : coveragePct >= 98 ? 'green' : coveragePct > 0 ? 'orange' : 'red'}>
          {coveragePct == null ? '无' : `${coveragePct.toFixed(1)}%`}
        </Tag>
        <span style={{ color: '#9eb8d9' }}>日对账:</span>
        <Tag color={dailyReconcile?.passed ? 'green' : dailyReconcile ? 'red' : 'default'}>
          {dailyReconcile ? `${dailyReconcile.trade_date_cn} ${dailyReconcile.passed ? '通过' : '失败'}` : '无'}
        </Tag>
        <span style={{ color: '#9eb8d9' }}>异常策略数:</span>
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
          <span>告警</span>
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
            <TermLabel label="总盈亏" term="total_pnl" />
          </div>
          <div style={{ fontSize: 22, fontWeight: 700 }}>
            <PnlText value={summary?.total_pnl_usdt} />
          </div>
        </Card>
      </Col>
      <Col span={6}>
        <Card size="small">
          <div style={{ color: '#888', fontSize: 12 }}>
            <TermLabel label="价差盈亏" term="spread_pnl" />
          </div>
          <div style={{ fontSize: 22, fontWeight: 700 }}>
            <PnlText value={summary?.spread_pnl_usdt} />
          </div>
        </Card>
      </Col>
      <Col span={6}>
        <Card size="small">
          <div style={{ color: '#888', fontSize: 12 }}>
            <TermLabel label="资金费盈亏" term="funding_pnl" />
          </div>
          <div style={{ fontSize: 22, fontWeight: 700 }}>
            {summary?.funding_pnl_usdt == null ? <Tag color="red">缺失</Tag> : <PnlText value={summary?.funding_pnl_usdt} />}
          </div>
        </Card>
      </Col>
      <Col span={6}>
        <Card size="small">
          <div style={{ color: '#888', fontSize: 12 }}>
            <TermLabel label="手续费" term="fee_usdt" />
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
  const slippagePolicyLabelMap = {
    excluded_from_total: '不计入总盈亏',
    included_in_total: '计入总盈亏',
  };
  return (
    <Row gutter={12} style={{ marginBottom: 16 }}>
      <Col span={12}>
        <Card size="small" title={<TermLabel label="数据质量" term="quality" />}>
          <Space wrap>
            <span>质量:</span>
            <QualityTag value={summary?.quality} />
            <span>覆盖率:</span>
            {coveragePct == null ? <span style={{ color: '#999' }}>无</span> : <span>{coveragePct.toFixed(1)}%</span>}
            <span>事件:</span>
            <span>
              {captured}
              /
              {expected}
            </span>
            <span>滑点策略:</span>
            <Tag>{slippagePolicyLabelMap[summary?.slippage_policy] || '不计入总盈亏'}</Tag>
          </Space>
        </Card>
      </Col>
      <Col span={12}>
        <Card size="small" title="平仓胜率">
          <Space>
            <span>
              {winCount}
              /
              {closedWithTotalCount}
            </span>
            <Tag color={winRate >= 60 ? 'green' : winRate >= 40 ? 'orange' : 'red'}>{winRate.toFixed(1)}%</Tag>
            <span style={{ color: '#888' }}>对账:</span>
            <Tag color={summary?.reconciliation?.passed ? 'green' : 'red'}>
              {summary?.reconciliation?.passed ? '通过' : '失败'}
            </Tag>
            <span style={{ color: '#888' }}>日:</span>
            <Tag color={dailyReconcile?.passed ? 'green' : dailyReconcile ? 'red' : 'default'}>
              {dailyReconcile ? `${dailyReconcile.trade_date_cn} ${dailyReconcile.passed ? '通过' : '失败'}` : '无'}
            </Tag>
            {dailyReconcile ? (
              <Tooltip title={`abs=${Number(dailyReconcile.abs_diff || 0).toFixed(6)}, pct=${(Number(dailyReconcile.pct_diff || 0) * 100).toFixed(4)}%`}>
                <Tag>{`差值 ${Number(dailyReconcile.abs_diff || 0).toFixed(4)}U`}</Tag>
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
            <TermLabel label="新启动" term="started_count" />
          </div>
          <div style={{ fontSize: 22, fontWeight: 700, color: '#1677ff' }}>{Number(statusOverview.started_count || 0)}</div>
        </Card>
      </Col>
      <Col span={8}>
        <Card size="small">
          <div style={{ color: '#888', fontSize: 12 }}>
            <TermLabel label="已结束" term="closed_count" />
          </div>
          <div style={{ fontSize: 22, fontWeight: 700, color: '#52c41a' }}>{Number(statusOverview.closed_count || 0)}</div>
        </Card>
      </Col>
      <Col span={8}>
        <Card size="small">
          <div style={{ color: '#888', fontSize: 12 }}>
            <TermLabel label="持续中" term="continued_count" />
          </div>
          <div style={{ fontSize: 22, fontWeight: 700, color: '#fa8c16' }}>{Number(statusOverview.continued_count || 0)}</div>
        </Card>
      </Col>
    </Row>
  );
}
