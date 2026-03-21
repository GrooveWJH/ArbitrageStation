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
const QUALITY_LABEL = {
  ok: '正常',
  na: '无数据',
  partial: '部分',
  stale: '过期',
  missing: '缺失',
};

export default function PnlQualityBar({ pnlSummary }) {
  const fundingCoveragePct = pnlSummary?.funding_coverage == null ? null : Number(pnlSummary.funding_coverage) * 100.0;
  const barValues = [
    Number(pnlSummary?.funding_coverage ?? 0.45),
    Number(pnlSummary?.quality === 'ok' ? 0.82 : 0.56),
    Number(pnlSummary?.funding_quality === 'ok' ? 0.78 : 0.52),
    Number(pnlSummary?.total_pnl_pct ?? 0) > 0 ? 0.9 : 0.6,
    Number(pnlSummary?.anomaly_strategy_count || 0) > 0 ? 0.45 : 0.82,
    Number(pnlSummary?.active_strategies || 1) > 0 ? 0.88 : 0.36,
    Number(pnlSummary?.open_positions || 1) > 0 ? 0.8 : 0.34,
    1,
  ].map((v) => Math.max(0.18, Math.min(1, v)));

  return (
    <Card className="kinetic-pnl-quality-panel" size="small">
      <div className="kinetic-pnl-panel-head">
        <h3>盈亏质量表现</h3>
        <Tag color="blue">v2</Tag>
      </div>

      <div className="kinetic-pnl-bars">
        {barValues.map((value, idx) => (
          <div key={`${idx}`} className={`kinetic-pnl-bar ${idx === barValues.length - 1 ? 'is-highlight' : ''}`}>
            <span style={{ height: `${Math.round(value * 100)}%` }} />
          </div>
        ))}
      </div>

      <div className="kinetic-pnl-stats">
        <div>
          <div className="stat-label">统计时间</div>
          <div className="stat-value">{fmtTime(pnlSummary?.as_of) || '-'}</div>
        </div>
        <div>
          <div className="stat-label"><TermLabel label="质量" term="quality" /></div>
          <div className="stat-value">
            <Tag color={QUALITY_COLOR[pnlSummary?.quality] || 'default'}>{QUALITY_LABEL[pnlSummary?.quality] || pnlSummary?.quality || '-'}</Tag>
          </div>
        </div>
        <div>
          <div className="stat-label"><TermLabel label="资金费质量" term="funding_quality" /></div>
          <div className="stat-value">
            <Tag color={QUALITY_COLOR[pnlSummary?.funding_quality] || 'default'}>{QUALITY_LABEL[pnlSummary?.funding_quality] || pnlSummary?.funding_quality || '-'}</Tag>
          </div>
        </div>
        <div>
          <div className="stat-label"><TermLabel label="覆盖率" term="funding_coverage" /></div>
          <div className="stat-value">
            <Tag color={fundingCoveragePct == null ? 'default' : fundingCoveragePct >= 98 ? 'green' : fundingCoveragePct > 0 ? 'orange' : 'red'}>
              {fundingCoveragePct == null ? '无' : `${fundingCoveragePct.toFixed(1)}%`}
            </Tag>
          </div>
        </div>
      </div>

      <Space wrap size={8}>
        <span className="kinetic-mini-note"><TermLabel label="资金费盈亏" term="funding_pnl" />:</span>
        {pnlSummary?.funding_pnl_usdt == null ? (
          <Tag color="red">缺失</Tag>
        ) : (
          <Tag color={Number(pnlSummary.funding_pnl_usdt) >= 0 ? 'green' : 'red'}>
            {Number(pnlSummary.funding_pnl_usdt).toFixed(4)}U
          </Tag>
        )}
        <span className="kinetic-mini-note"><TermLabel label="异常" term="quality" />:</span>
        <Tag color={Number(pnlSummary?.anomaly_strategy_count || 0) > 0 ? 'red' : 'green'}>
          {Number(pnlSummary?.anomaly_strategy_count || 0)}
        </Tag>
      </Space>
    </Card>
  );
}
