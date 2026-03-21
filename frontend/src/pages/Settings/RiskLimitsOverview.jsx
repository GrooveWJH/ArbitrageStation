import React, { useMemo } from 'react';
import { SafetyOutlined } from '@ant-design/icons';

export default function RiskLimitsOverview({ rules }) {
  const visual = useMemo(() => {
    const activeRules = rules.filter((item) => item.is_enabled);
    const findRule = (type) => activeRules.find((item) => item.rule_type === type);
    const lossRule = findRule('loss_pct');
    const leverageRule = findRule('max_leverage');
    const spreadRule = findRule('min_rate_diff');
    const panicEnabled = activeRules.some((item) => item.action === 'close_position');
    const drawdownPct = Number(lossRule?.threshold || 0);
    const drawdownBar = Math.max(0, Math.min(100, drawdownPct));
    const leverageValue = Number(leverageRule?.threshold || 0);
    const leverageBar = Math.max(0, Math.min(100, (leverageValue / 20) * 100));
    return {
      activeCount: activeRules.length,
      drawdownPct,
      drawdownBar,
      leverageValue,
      leverageBar,
      spreadValue: Number(spreadRule?.threshold || 0),
      panicEnabled,
    };
  }, [rules]);

  return (
    <section className="kinetic-risk-visual">
      <div className="kinetic-risk-visual-head">
        <h4>
          <SafetyOutlined />
          全局风控阈值
        </h4>
        <span>当前策略: 严格模式</span>
      </div>
      <div className="kinetic-risk-visual-body">
        <div className="risk-track">
          <div className="risk-track-label">
            <span>最大回撤</span>
            <strong>{visual.drawdownPct.toFixed(2)}%</strong>
          </div>
          <div className="risk-track-bar"><span style={{ width: `${visual.drawdownBar}%` }} /></div>
        </div>
        <div className="risk-track">
          <div className="risk-track-label">
            <span>最大杠杆</span>
            <strong>{visual.leverageValue.toFixed(1)}x</strong>
          </div>
          <div className="risk-track-bar"><span style={{ width: `${visual.leverageBar}%` }} /></div>
        </div>
        <div className="risk-mini-grid">
          <div className="risk-mini-card">
            <div className="k">滑点容忍度</div>
            <div className="v">{visual.spreadValue.toFixed(3)}%</div>
            <div className="m">{visual.activeCount} 条规则已启用</div>
          </div>
          <div className="risk-mini-card">
            <div className="k">最小价差门槛</div>
            <div className="v">{(visual.spreadValue * 100).toFixed(1)} bps</div>
            <div className="m">套利触发下限</div>
          </div>
          <div className={`risk-mini-card ${visual.panicEnabled ? 'danger' : ''}`}>
            <div className="k">紧急平仓规则</div>
            <div className="v">{visual.panicEnabled ? '已启用' : '已禁用'}</div>
            <div className="m">{visual.panicEnabled ? '波动触发' : '仅告警模式'}</div>
          </div>
        </div>
      </div>
    </section>
  );
}
