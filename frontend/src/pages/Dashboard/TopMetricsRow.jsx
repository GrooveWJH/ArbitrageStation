import React from 'react';
import { Card, Col, Row } from 'antd';
import { ArrowDownOutlined, ArrowUpOutlined } from '@ant-design/icons';

function fmtCurrency(v) {
  if (v == null || Number.isNaN(Number(v))) return '--';
  return `$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

export default function TopMetricsRow({ pnlSummary, accountSummary, emergencyCount = 0 }) {
  const totalEquity = accountSummary?.totalUsdt ?? 0;
  const openExposure = accountSummary?.knownFuturesUsdt ?? 0;
  const riskWarnings = Number(accountSummary?.warningExchangeCount || 0) + emergencyCount;
  const riskLabel = riskWarnings > 0 ? '关注' : '正常';
  const riskTone = riskWarnings > 0 ? 'warning' : 'healthy';
  const pnlDelta = pnlSummary?.total_pnl_usdt;
  const pnlPct = pnlSummary?.total_pnl_pct;

  return (
    <Row gutter={[16, 16]} className="kinetic-dashboard-metrics">
      <Col xs={24} md={12} xl={8}>
        <Card className="kinetic-overview-metric">
          <div className="metric-label">总权益 (USDT)</div>
          <div className="metric-value">{fmtCurrency(totalEquity)}</div>
          <div className="metric-foot">
            <span className="metric-up">{Number(accountSummary?.exchangeCount || 0)} 个交易所</span>
            <span>实时资金汇总</span>
          </div>
        </Card>
      </Col>
      <Col xs={24} md={12} xl={8}>
        <Card className="kinetic-overview-metric">
          <div className="metric-label">在仓敞口</div>
          <div className="metric-value">{fmtCurrency(openExposure)}</div>
          <div className="metric-foot">
            <span className="metric-up">{Number(pnlSummary?.open_positions || 0)} 条在仓腿</span>
            <span>
              {pnlDelta == null ? '--' : (
                <>
                  {Number(pnlDelta) >= 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
                  {' '}
                  {Number(pnlDelta) >= 0 ? '+' : ''}
                  {Number(pnlDelta).toFixed(2)}U
                  {' / '}
                  {pnlPct == null ? '--' : `${Number(pnlPct).toFixed(2)}%`}
                </>
              )}
            </span>
          </div>
        </Card>
      </Col>
      <Col xs={24} md={24} xl={8}>
        <Card className={`kinetic-overview-metric ${riskTone === 'warning' ? 'warning' : 'healthy'}`}>
          <div className="metric-label">系统状态 / 风险</div>
          <div className="metric-value">{riskLabel}</div>
          <div className="metric-foot">
            <span>{riskWarnings > 0 ? `${riskWarnings} 条风险信号` : '无关键告警'}</span>
            <span>{Number(pnlSummary?.active_strategies || 0)} 个策略运行中</span>
          </div>
        </Card>
      </Col>
    </Row>
  );
}
