import React from 'react';
import {
  Card,
  Col,
  Empty,
  Modal,
  Row,
  Segmented,
  Spin,
  Tag,
} from 'antd';
import { LineChartOutlined } from '@ant-design/icons';
import SpreadKlineChart from './SpreadKlineChart';

export default function KlineModal({
  klineModal,
  klineTf,
  onTfChange,
  klineLoading,
  klineError,
  klineData,
  onClose,
}) {
  return (
    <Modal
      className="kinetic-spread-kline-modal"
      open={!!klineModal}
      onCancel={onClose}
      footer={null}
      width={1000}
      title={klineModal && (
        <div className="kinetic-spread-kline-title">
          <span className="kinetic-spread-kline-title-main">
            <LineChartOutlined />
            <span>{klineModal.symbol} 价差走势</span>
          </span>
          {klineData && (
            <span className="kinetic-spread-kline-title-sub">
              {klineData.exchange_a} − {klineData.exchange_b}
            </span>
          )}
          {klineData?.stats && (() => {
            const latest = klineData.candles[klineData.candles.length - 1]?.close;
            const z = latest && klineData.stats.std > 0
              ? ((latest - klineData.stats.mean) / klineData.stats.std).toFixed(1)
              : null;
            if (!z) return null;
            return (
              <Tag className={`kinetic-spread-kline-ztag ${z >= 1.5 ? 'is-hot' : z >= 1 ? 'is-warn' : 'is-cool'}`}>
                z={z}
              </Tag>
            );
          })()}
        </div>
      )}
      destroyOnClose
    >
      <div style={{ marginBottom: 12 }}>
        <Segmented
          value={klineTf}
          onChange={onTfChange}
          options={[
            { label: '15m', value: '15m' },
            { label: '1h', value: '1h' },
            { label: '4h', value: '4h' },
            { label: '1d', value: '1d' },
          ]}
        />
      </div>

      {klineLoading && (
        <div style={{ textAlign: 'center', padding: '60px 0' }}>
          <Spin size="large" />
        </div>
      )}

      {!klineLoading && klineError && (
        <Empty
          description={(
            <div style={{ textAlign: 'left', color: '#cf1322' }}>
              {klineError.map((msg, i) => <div key={i}>• {msg}</div>)}
            </div>
          )}
        />
      )}

      {!klineLoading && klineData && klineData.candles.length > 0 && (() => {
        const cs = klineData.candles;
        const latest = cs[cs.length - 1].close;
        const closes = cs.map((c) => c.close);
        const highs = cs.map((c) => c.high);
        const lows = cs.map((c) => c.low);
        const maxS = Math.max(...highs);
        const minS = Math.min(...lows);
        const avg = closes.reduce((a, b) => a + b, 0) / closes.length;
        const st = klineData.stats;
        const currentZ = st && st.std > 0 ? (latest - st.mean) / st.std : null;

        return (
          <>
            <Row gutter={8} style={{ marginBottom: 8 }}>
              {[
                { label: '最新价差', value: latest, color: latest >= 0 ? '#ef5350' : '#26a69a' },
                { label: '均值', value: avg, color: avg >= 0 ? '#ef5350' : '#26a69a' },
                { label: '区间最高', value: maxS, color: '#ef5350' },
                { label: '区间最低', value: minS, color: '#26a69a' },
              ].map(({ label, value, color }) => (
                <Col span={6} key={label}>
                  <Card size="small" bodyStyle={{ padding: '6px 10px' }}>
                    <div style={{ fontSize: 10, color: '#aaa' }}>{label}</div>
                    <div style={{ fontWeight: 700, fontSize: 14, color }}>
                      {value >= 0 ? '+' : ''}
                      {value.toFixed(4)}
                      %
                    </div>
                  </Card>
                </Col>
              ))}
            </Row>

            {st && (
              <Row gutter={8} style={{ marginBottom: 8 }}>
                <Col span={6}>
                  <Card size="small" bodyStyle={{ padding: '6px 10px' }}>
                    <div style={{ fontSize: 10, color: '#aaa' }}>历史均值</div>
                    <div style={{ fontWeight: 700, fontSize: 14, color: '#1677ff' }}>
                      {st.mean >= 0 ? '+' : ''}
                      {st.mean.toFixed(4)}
                      %
                    </div>
                  </Card>
                </Col>
                <Col span={6}>
                  <Card size="small" bodyStyle={{ padding: '6px 10px' }}>
                    <div style={{ fontSize: 10, color: '#aaa' }}>+1.5σ门槛</div>
                    <div style={{ fontWeight: 700, fontSize: 14, color: '#fa8c16' }}>
                      {st.upper_1_5 >= 0 ? '+' : ''}
                      {st.upper_1_5.toFixed(4)}
                      %
                    </div>
                  </Card>
                </Col>
                <Col span={6}>
                  <Card size="small" bodyStyle={{ padding: '6px 10px' }}>
                    <div style={{ fontSize: 10, color: '#aaa' }}>当前z分数</div>
                    <div
                      style={{
                        fontWeight: 700,
                        fontSize: 14,
                        color: currentZ >= 1.5 ? '#cf1322' : currentZ >= 1 ? '#fa8c16' : '#52c41a',
                      }}
                    >
                      {currentZ != null ? currentZ.toFixed(2) : '—'}
                    </div>
                  </Card>
                </Col>
                <Col span={6}>
                  <Card size="small" bodyStyle={{ padding: '6px 10px' }}>
                    <div style={{ fontSize: 10, color: '#aaa' }}>数据样本</div>
                    <div style={{ fontWeight: 700, fontSize: 14, color: '#666' }}>
                      {st.n} 根
                    </div>
                  </Card>
                </Col>
              </Row>
            )}

            <div style={{ fontSize: 11, color: '#aaa', marginBottom: 6, display: 'flex', gap: 16 }}>
              <span><span style={{ display: 'inline-block', width: 10, height: 10, background: '#ef5350', marginRight: 4 }} />价差扩大</span>
              <span><span style={{ display: 'inline-block', width: 10, height: 10, background: '#26a69a', marginRight: 4 }} />价差收窄</span>
              {st && (
                <>
                  <span><span style={{ display: 'inline-block', width: 16, height: 2, background: '#1677ff', marginRight: 4, verticalAlign: 'middle' }} />均值</span>
                  <span><span style={{ display: 'inline-block', width: 16, height: 2, background: '#fa8c16', marginRight: 4, verticalAlign: 'middle' }} />+1.5σ</span>
                  <span><span style={{ display: 'inline-block', width: 16, height: 2, background: '#cf1322', marginRight: 4, verticalAlign: 'middle' }} />+2σ</span>
                </>
              )}
              <span style={{ marginLeft: 'auto' }}>{cs.length} 根K线</span>
            </div>

            <SpreadKlineChart candles={cs} timeframe={klineTf} stats={klineData.stats} />
          </>
        );
      })()}
    </Modal>
  );
}
