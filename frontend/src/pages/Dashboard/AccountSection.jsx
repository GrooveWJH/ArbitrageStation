import React from 'react';
import { ReloadOutlined, WalletOutlined } from '@ant-design/icons';
import { Line } from '@ant-design/charts';
import { Button, Card, Col, Progress, Row, Space, Spin, Tag, Tooltip } from 'antd';

export default function AccountSection({
  accountLoading,
  accountData,
  accountSummary,
  accountTrendData,
  accountTrendConfig,
  accountTrendStart,
  accountTrendEnd,
  accountTrendDelta,
  onRefresh,
  formatUsdt,
  calcExchangeTotalUsdt,
  toNumber,
}) {
  const accountDistributionRows = accountData
    .map((ex) => {
      const totalUsdt = calcExchangeTotalUsdt(ex);
      return {
        key: ex.exchange_id,
        name: ex.exchange_name,
        totalUsdt,
        ratio: accountSummary.totalUsdt > 0 ? (totalUsdt / accountSummary.totalUsdt) * 100 : 0,
        hasError: Boolean(ex.error),
      };
    })
    .sort((a, b) => b.totalUsdt - a.totalUsdt);

  return (
    <Card
      title={<Space><WalletOutlined style={{ color: '#1677ff' }} /><span>账户资金 (实时)</span></Space>}
      style={{ marginBottom: 24 }}
      extra={(
        <Button icon={<ReloadOutlined />} size="small" loading={accountLoading} onClick={() => { void onRefresh(); }}>
          刷新
        </Button>
      )}
    >
      <Spin spinning={accountLoading}>
        {accountData.length === 0 && !accountLoading ? (
          <span style={{ color: '#aaa' }}>暂无数据，请点击刷新</span>
        ) : (
          <>
            <Row gutter={[12, 12]} style={{ marginBottom: 12 }}>
              <Col xs={24} sm={12} lg={6}>
                <Card
                  size="small"
                  bodyStyle={{ padding: 14 }}
                  style={{ background: 'linear-gradient(135deg, #e6f4ff 0%, #f7fbff 100%)', borderColor: '#bae0ff' }}
                >
                  <div style={{ color: '#666', fontSize: 12 }}>账户总资产 (USDT)</div>
                  <div style={{ fontSize: 24, fontWeight: 700, color: '#0958d9', lineHeight: 1.3 }}>
                    ${formatUsdt(accountSummary.totalUsdt, 2)}
                  </div>
                  <div style={{ color: '#777', fontSize: 12 }}>
                    {accountSummary.exchangeCount} 个交易所
                  </div>
                </Card>
              </Col>
              <Col xs={24} sm={12} lg={6}>
                <Card
                  size="small"
                  bodyStyle={{ padding: 14 }}
                  style={{ background: 'linear-gradient(135deg, #f6ffed 0%, #fcfff5 100%)', borderColor: '#d9f7be' }}
                >
                  <div style={{ color: '#666', fontSize: 12 }}>未实现盈亏</div>
                  <div style={{ fontSize: 24, fontWeight: 700, color: accountSummary.unrealizedPnlUsdt >= 0 ? '#389e0d' : '#cf1322', lineHeight: 1.3 }}>
                    {accountSummary.unrealizedPnlUsdt >= 0 ? '+' : ''}{formatUsdt(accountSummary.unrealizedPnlUsdt, 2)}U
                  </div>
                  <div style={{ color: '#777', fontSize: 12 }}>
                    在仓头寸 {accountSummary.positionCount} 笔
                  </div>
                </Card>
              </Col>
              <Col xs={24} sm={12} lg={6}>
                <Card
                  size="small"
                  bodyStyle={{ padding: 14 }}
                  style={{ background: 'linear-gradient(135deg, #f0f5ff 0%, #fafcff 100%)', borderColor: '#d6e4ff' }}
                >
                  <div style={{ color: '#666', fontSize: 12 }}>资金构成</div>
                  <div style={{ fontWeight: 600, color: '#1d39c4', marginTop: 2 }}>
                    统一账户 ${formatUsdt(accountSummary.unifiedUsdt, 2)}
                  </div>
                  <div style={{ color: '#777', fontSize: 12, marginTop: 2 }}>
                    现货 ${formatUsdt(accountSummary.knownSpotUsdt, 2)} / 合约 ${formatUsdt(accountSummary.knownFuturesUsdt, 2)}
                  </div>
                  <div style={{ color: '#777', fontSize: 12, marginTop: 2 }}>
                    山寨币折算 ${formatUsdt(accountSummary.altEquivalentUsdt, 2)}
                  </div>
                </Card>
              </Col>
              <Col xs={24} sm={12} lg={6}>
                <Card
                  size="small"
                  bodyStyle={{ padding: 14 }}
                  style={{ background: 'linear-gradient(135deg, #fff7e6 0%, #fffdf7 100%)', borderColor: '#ffe7ba' }}
                >
                  <div style={{ color: '#666', fontSize: 12 }}>连接状态</div>
                  <div style={{ marginTop: 4 }}>
                    <Tag color="green" style={{ marginBottom: 4 }}>正常 {accountSummary.healthyExchangeCount}</Tag>
                    <Tag color="orange" style={{ marginBottom: 4 }}>告警 {accountSummary.warningExchangeCount}</Tag>
                    <Tag color="red" style={{ marginBottom: 4 }}>异常 {accountSummary.errorExchangeCount}</Tag>
                  </div>
                </Card>
              </Col>
            </Row>

            <Row gutter={[16, 16]} style={{ marginBottom: 12 }}>
              <Col xs={24} xl={15}>
                <Card
                  size="small"
                  title="资金趋势 (当前会话)"
                  extra={<Tag color="blue">{accountTrendData.length} 点</Tag>}
                  bodyStyle={{ paddingBottom: 8 }}
                >
                  {accountTrendData.length < 2 ? (
                    <div style={{ height: 216, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#999' }}>
                      趋势数据采集中，等待更多刷新点
                    </div>
                  ) : (
                    <div style={{ height: 216 }}>
                      <Line {...accountTrendConfig} />
                    </div>
                  )}
                  <Row gutter={12} style={{ marginTop: 4, marginBottom: 2 }}>
                    <Col xs={24} sm={8}>
                      <div style={{ fontSize: 12, color: '#888' }}>起点</div>
                      <div style={{ fontWeight: 600 }}>${accountTrendStart == null ? '--' : formatUsdt(accountTrendStart, 2)}</div>
                    </Col>
                    <Col xs={24} sm={8}>
                      <div style={{ fontSize: 12, color: '#888' }}>当前</div>
                      <div style={{ fontWeight: 600 }}>${accountTrendEnd == null ? '--' : formatUsdt(accountTrendEnd, 2)}</div>
                    </Col>
                    <Col xs={24} sm={8}>
                      <div style={{ fontSize: 12, color: '#888' }}>会话变化</div>
                      <div style={{ fontWeight: 600, color: accountTrendDelta == null ? '#333' : accountTrendDelta >= 0 ? '#389e0d' : '#cf1322' }}>
                        {accountTrendDelta == null ? '--' : `${accountTrendDelta >= 0 ? '+' : ''}${formatUsdt(accountTrendDelta, 2)}U`}
                      </div>
                    </Col>
                  </Row>
                </Card>
              </Col>
              <Col xs={24} xl={9}>
                <Card size="small" title="交易所资产占比" bodyStyle={{ paddingBottom: 8 }}>
                  {accountDistributionRows.length === 0 ? (
                    <div style={{ color: '#999', minHeight: 216, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      暂无可分配数据
                    </div>
                  ) : (
                    accountDistributionRows.map((row) => (
                      <div key={row.key} style={{ marginBottom: 10 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                          <div style={{ color: row.hasError ? '#cf1322' : '#333' }}>{row.name}</div>
                          <div style={{ color: '#666' }}>${formatUsdt(row.totalUsdt, 2)}</div>
                        </div>
                        <Progress
                          percent={Number(row.ratio.toFixed(1))}
                          showInfo={false}
                          size="small"
                          strokeWidth={7}
                          strokeColor={row.hasError ? '#ff7875' : '#69b1ff'}
                          trailColor="#f0f0f0"
                        />
                        <div style={{ textAlign: 'right', color: '#888', fontSize: 12 }}>{row.ratio.toFixed(1)}%</div>
                      </div>
                    ))
                  )}
                </Card>
              </Col>
            </Row>

            {accountSummary.topAssets?.length > 0 && (
              <Card size="small" style={{ marginBottom: 12 }} title="资产分布 (按币种汇总)">
                <Space wrap size={[6, 6]}>
                  {accountSummary.topAssets.map((a) => (
                    <Tag key={a.asset} color="blue">
                      {a.asset}: {formatUsdt(a.total, 4)}
                    </Tag>
                  ))}
                </Space>
              </Card>
            )}

            <Row gutter={[16, 16]}>
              {accountData.map((ex) => {
                const totalUsdt = calcExchangeTotalUsdt(ex);
                const spotUsdt = toNumber(ex.spot_usdt);
                const futuresUsdt = toNumber(ex.futures_usdt);
                const altEquivalentUsdt = ex.unified_account ? 0 : Math.max(0, totalUsdt - spotUsdt - futuresUsdt);
                const posCount = Array.isArray(ex.positions) ? ex.positions.length : 0;
                const totalPnl = Array.isArray(ex.positions) ? ex.positions.reduce((s, p) => s + toNumber(p.unrealized_pnl), 0) : 0;
                const spotPct = totalUsdt > 0 ? Math.min(100, (spotUsdt / totalUsdt) * 100) : 0;
                const futuresPctRaw = totalUsdt > 0 ? (futuresUsdt / totalUsdt) * 100 : 0;
                const futuresPct = Math.min(Math.max(0, 100 - spotPct), Math.max(0, futuresPctRaw));
                const altPct = Math.max(0, 100 - spotPct - futuresPct);

                return (
                  <Col key={ex.exchange_id} xs={24} sm={12} xl={8}>
                    <Card
                      size="small"
                      title={(
                        <Space size={6} wrap>
                          <Tag color="geekblue">{ex.exchange_name}</Tag>
                          {ex.unified_account && <Tag color="blue">统一账户</Tag>}
                          {ex.warning && (
                            <Tooltip title={ex.warning}>
                              <Tag color="orange">部分可用</Tag>
                            </Tooltip>
                          )}
                          {ex.error && (
                            <Tooltip title={ex.error}>
                              <Tag color="red">连接异常</Tag>
                            </Tooltip>
                          )}
                        </Space>
                      )}
                      style={{ borderColor: ex.error ? '#ffccc7' : '#e6f4ff' }}
                      bodyStyle={{ paddingTop: 10, paddingBottom: 10 }}
                    >
                      <div style={{ marginBottom: 8 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                          <span style={{ color: '#888', fontSize: 12 }}>总资产</span>
                          <span style={{ fontSize: 18, fontWeight: 700, color: '#0958d9' }}>${formatUsdt(totalUsdt, 2)}</span>
                        </div>
                        <div style={{ height: 8, width: '100%', background: '#f2f3f5', borderRadius: 999, overflow: 'hidden', display: 'flex' }}>
                          {ex.unified_account ? (
                            <div style={{ width: '100%', background: '#91caff' }} />
                          ) : (
                            <>
                              <div style={{ width: `${spotPct}%`, background: '#73d13d' }} />
                              <div style={{ width: `${futuresPct}%`, background: '#69b1ff' }} />
                              <div style={{ width: `${altPct}%`, background: '#95de64' }} />
                            </>
                          )}
                        </div>
                        <div style={{ marginTop: 4, display: 'flex', justifyContent: 'space-between', color: '#888', fontSize: 12 }}>
                          {ex.unified_account ? (
                            <span>统一账户余额: ${formatUsdt(ex.total_usdt || 0, 2)}</span>
                          ) : (
                            <>
                              <span>现货 ${formatUsdt(spotUsdt, 2)} ({spotPct.toFixed(1)}%)</span>
                              <span>合约 ${formatUsdt(futuresUsdt, 2)} ({futuresPct.toFixed(1)}%)</span>
                            </>
                          )}
                        </div>
                        {!ex.unified_account && (
                          <div style={{ marginTop: 2, color: '#888', fontSize: 12 }}>
                            山寨币折算 ${formatUsdt(altEquivalentUsdt, 2)} ({altPct.toFixed(1)}%)
                          </div>
                        )}
                      </div>

                      <Row gutter={8} style={{ marginBottom: 6 }}>
                        <Col span={12}>
                          <div style={{ color: '#888', fontSize: 12 }}>持仓数量</div>
                          <div style={{ fontWeight: 600 }}>{posCount} 笔</div>
                        </Col>
                        <Col span={12}>
                          <div style={{ color: '#888', fontSize: 12 }}>浮动盈亏</div>
                          <div style={{ fontWeight: 600, color: totalPnl >= 0 ? '#389e0d' : '#cf1322' }}>
                            {totalPnl >= 0 ? '+' : ''}{formatUsdt(totalPnl, 4)}U
                          </div>
                        </Col>
                      </Row>

                      {ex.spot_assets?.length > 0 && (
                        <div style={{ marginTop: 4 }}>
                          <div style={{ color: '#888', fontSize: 12, marginBottom: 3 }}>主要现货资产</div>
                          <Space size={[4, 4]} wrap>
                            {ex.spot_assets.slice(0, 6).map((a) => (
                              <Tag key={a.asset}>
                                {a.asset}: {formatUsdt(a.total, 4)}
                              </Tag>
                            ))}
                          </Space>
                        </div>
                      )}

                      {ex.positions?.length > 0 && (
                        <div style={{ marginTop: 8 }}>
                          <div style={{ color: '#888', fontSize: 12, marginBottom: 4 }}>持仓明细</div>
                          {ex.positions.slice(0, 5).map((p, i) => (
                            <div key={`${p.symbol}-${i}`} style={{ fontSize: 12, display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                              <span style={{ maxWidth: '62%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                <Tag color={p.side === 'long' ? 'green' : 'red'} style={{ fontSize: 11, marginRight: 4 }}>
                                  {p.side}
                                </Tag>
                                <Tag color={(p.position_type || '').toLowerCase() === 'spot' ? 'cyan' : 'purple'} style={{ fontSize: 11, marginRight: 4 }}>
                                  {(p.position_type || 'swap').toLowerCase()}
                                </Tag>
                                {p.symbol}
                              </span>
                              <span style={{ color: toNumber(p.unrealized_pnl) >= 0 ? '#3f8600' : '#cf1322', fontWeight: 600 }}>
                                {toNumber(p.unrealized_pnl) >= 0 ? '+' : ''}{formatUsdt(p.unrealized_pnl || 0, 4)}U
                              </span>
                            </div>
                          ))}
                          {ex.positions.length > 5 && (
                            <div style={{ color: '#999', fontSize: 12 }}>还有 {ex.positions.length - 5} 笔未展开</div>
                          )}
                        </div>
                      )}
                    </Card>
                  </Col>
                );
              })}
            </Row>
          </>
        )}
      </Spin>
    </Card>
  );
}
