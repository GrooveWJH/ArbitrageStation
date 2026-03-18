import React from 'react';
import {
  Card,
  Col,
  Row,
  Space,
  Tag,
} from 'antd';

export default function MarginCards({ items }) {
  if (!items || items.length === 0) return null;

  return (
    <Card
      size="small"
      title="各交易所合约账户保证金利用率（含费率+价差套利，5s 刷新）"
      style={{ marginBottom: 16 }}
    >
      <Row gutter={[16, 16]}>
        {items.map((ex) => {
          const over = ex.used_pct >= ex.cap_pct;
          const warn = ex.used_pct >= ex.cap_pct * 0.85;
          const color = over ? '#cf1322' : warn ? '#fa8c16' : '#52c41a';
          const strokeColor = over ? '#ff4d4f' : warn ? '#fa8c16' : '#52c41a';

          return (
            <Col key={ex.exchange_id} xs={24} sm={12} lg={8}>
              <div
                style={{
                  border: `1px solid ${over ? '#ffadd2' : warn ? '#ffd591' : '#d9d9d9'}`,
                  borderRadius: 8,
                  padding: '12px 16px',
                  background: over ? '#fff0f6' : warn ? '#fffbe6' : '#fff',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <Space size={6}>
                    <Tag color={over ? 'red' : 'default'} style={{ fontWeight: 700, fontSize: 12 }}>
                      {ex.exchange_name?.toUpperCase()}
                    </Tag>
                    {over && <Tag color="red" style={{ fontSize: 10 }}>超上限</Tag>}
                  </Space>
                  <span style={{ fontWeight: 700, color, fontSize: 15 }}>
                    {ex.used_pct?.toFixed(1)}
                    %
                  </span>
                </div>

                <div style={{ position: 'relative', height: 10, borderRadius: 5, background: '#f0f0f0', marginBottom: 6 }}>
                  <div
                    style={{
                      height: '100%',
                      borderRadius: 5,
                      width: `${Math.min(ex.used_pct ?? 0, 100)}%`,
                      background: strokeColor,
                      transition: 'width 0.4s',
                    }}
                  />
                  <div
                    style={{
                      position: 'absolute',
                      top: -2,
                      bottom: -2,
                      left: `${ex.cap_pct ?? 80}%`,
                      width: 2,
                      background: '#ff4d4f',
                      borderRadius: 1,
                    }}
                  />
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
                  <span style={{ color: '#888' }}>
                    上限
                    {' '}
                    <b style={{ color: '#262626' }}>${(ex.max_notional ?? 0).toFixed(2)}</b>
                  </span>
                  <span style={{ color: '#888' }}>
                    已开
                    {' '}
                    <b style={{ color }}>${(ex.current_notional ?? 0).toFixed(2)}</b>
                  </span>
                  <span style={{ color: '#888' }}>
                    余
                    {' '}
                    <b style={{ color: '#3f8600' }}>${(ex.remaining_notional ?? 0).toFixed(2)}</b>
                  </span>
                </div>

                <div style={{ fontSize: 11, color: '#aaa' }}>
                  余额 ${(ex.total ?? 0).toFixed(2)} · 杠杆 {ex.user_leverage ?? 1}x · 上限 {ex.cap_pct ?? 80}%
                  {(ex.funding_notional > 0 || ex.spread_notional > 0) && (
                    <span style={{ marginLeft: 8 }}>
                      (费率 ${(ex.funding_notional ?? 0).toFixed(0)} / 价差 ${(ex.spread_notional ?? 0).toFixed(0)})
                    </span>
                  )}
                </div>

                {ex.error && <div style={{ fontSize: 11, color: '#cf1322', marginTop: 4 }}>错误: {ex.error}</div>}
              </div>
            </Col>
          );
        })}
      </Row>
    </Card>
  );
}
