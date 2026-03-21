import React from 'react';
import { Button, Card, Progress, Space, Tag } from 'antd';
import { FilterOutlined, FundProjectionScreenOutlined, PlusOutlined } from '@ant-design/icons';

export default function PositionIntelCard({
  selectedStrategy,
  selectedRisk,
  statusTag,
  qualityTag,
  onOpenDetail,
  onClosePosition,
  onOpenPosition,
}) {
  return (
    <Card className="kinetic-panel-card kinetic-position-intel-card">
      <div className="intel-head">
        <div>
          <div className="intel-kicker">策略表现分析</div>
          <h4>{selectedStrategy?.name || '未选择策略'}</h4>
        </div>
        <Button
          type="text"
          icon={<FundProjectionScreenOutlined />}
          onClick={onOpenDetail}
          disabled={!selectedStrategy}
        />
      </div>

      <Space wrap style={{ marginBottom: 12 }}>
        {selectedStrategy ? (
          <>
            <Tag color="blue">{selectedStrategy.symbol}</Tag>
            {statusTag(selectedStrategy.status)}
            {qualityTag(selectedStrategy.quality)}
          </>
        ) : (
          <Tag>--</Tag>
        )}
      </Space>

      <div className="intel-grid">
        <div>
          <div className="label">风险等级</div>
          <div className={`value tone-${selectedRisk.tone}`}>{selectedRisk.label}</div>
        </div>
        <div>
          <div className="label">预期年化</div>
          <div className="value">
            {selectedStrategy?.current_annualized == null ? '--' : `${Number(selectedStrategy.current_annualized).toFixed(2)}%`}
          </div>
        </div>
        <div>
          <div className="label">总盈亏</div>
          <div className={`value ${Number(selectedStrategy?.total_pnl_usd || 0) >= 0 ? 'positive' : 'negative'}`}>
            {selectedStrategy?.total_pnl_usd == null ? '--' : `${Number(selectedStrategy.total_pnl_usd) >= 0 ? '+' : ''}${Number(selectedStrategy.total_pnl_usd).toFixed(2)}U`}
          </div>
        </div>
        <div>
          <div className="label">保证金基数</div>
          <div className="value">
            {selectedStrategy?.initial_margin_usd == null ? '--' : `$${Number(selectedStrategy.initial_margin_usd).toFixed(2)}`}
          </div>
        </div>
      </div>

      <div style={{ marginBottom: 14 }}>
        <div className="label" style={{ marginBottom: 6 }}>风险压力</div>
        <Progress percent={selectedRisk.pct} showInfo={false} strokeColor={selectedRisk.tone === 'danger' ? '#ee7d77' : '#7bd0ff'} trailColor="rgba(43,70,128,0.35)" />
      </div>

      <div className="intel-actions">
        <Button
          danger
          block
          disabled={!selectedStrategy || selectedStrategy.status !== 'active'}
          onClick={onClosePosition}
        >
          平仓
        </Button>
        <Button
          block
          icon={<FilterOutlined />}
          disabled={!selectedStrategy}
          onClick={onOpenDetail}
        >
          查看详情
        </Button>
        <Button type="primary" block icon={<PlusOutlined />} onClick={onOpenPosition}>
          新建仓位
        </Button>
      </div>
    </Card>
  );
}
