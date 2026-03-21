import React from 'react';
import {
  Card,
  Descriptions,
  Drawer,
  Select,
  Space,
  Table,
  Tag,
  Tooltip,
} from 'antd';
import { fmtTime } from '../../utils/time';
import { TermLabel } from '../../components/TermHint';

export default function StrategyDetailDrawer({
  detailDrawer,
  detailLoading,
  detailEventFilter,
  setDetailEventFilter,
  setDetailDrawer,
  statusTag,
  qualityTag,
  pnlRender,
  pnlPctRender,
}) {
  return (
    <Drawer
      title={`策略详情 #${detailDrawer?.id}`}
      open={!!detailDrawer}
      onClose={() => setDetailDrawer(null)}
      width={680}
    >
      {detailDrawer && (
        <>
          {(() => {
            const o = detailDrawer?.v2?.overview || {};
            const q = detailDrawer?.v2?.quality || {};
            const spreadPnl = o.spread_pnl_usdt ?? detailDrawer.unrealized_pnl;
            const fundingPnl = o.funding_pnl_usdt ?? detailDrawer.funding_pnl_usd;
            const totalPnl = o.total_pnl_usdt ?? detailDrawer.total_pnl_usd;
            const margin = o.initial_margin_usd ?? detailDrawer.initial_margin_usd;
            const quality = q.quality || detailDrawer.quality;
            const expected = Number(q.funding_expected_event_count || detailDrawer.funding_expected_event_count || 0);
            const captured = Number(q.funding_captured_event_count || detailDrawer.funding_captured_event_count || 0);
            const coverage = q.funding_coverage;
            return (
              <Descriptions bordered size="small" column={2} style={{ marginBottom: 24 }}>
                <Descriptions.Item label="状态">{statusTag(detailDrawer.status)}</Descriptions.Item>
                <Descriptions.Item label="类型">{detailDrawer.strategy_type}</Descriptions.Item>
                <Descriptions.Item label="交易对">{detailDrawer.symbol}</Descriptions.Item>
                <Descriptions.Item label={<TermLabel label="保证金" term="capital_base" />}>${margin}</Descriptions.Item>
                <Descriptions.Item label={<TermLabel label="价差盈亏" term="spread_pnl" />}>{pnlRender(spreadPnl)}</Descriptions.Item>
                <Descriptions.Item label={<TermLabel label="资金费盈亏" term="funding_pnl" />}>
                  {fundingPnl == null ? <Tag color="red">缺失</Tag> : pnlRender(fundingPnl, 4)}
                </Descriptions.Item>
                <Descriptions.Item label={<TermLabel label="总盈亏" term="total_pnl" />} span={2}>
                  {totalPnl == null ? <Tag color="orange">部分</Tag> : pnlRender(totalPnl, 4)}
                  <span style={{ marginLeft: 8, fontSize: 12, color: '#888' }}>
                    ({totalPnl != null && margin > 0 ? `${((totalPnl / margin) * 100).toFixed(2)}%` : '-'})
                  </span>
                </Descriptions.Item>
                <Descriptions.Item label={<TermLabel label="质量" term="quality" />}>{qualityTag(quality)}</Descriptions.Item>
                <Descriptions.Item label={<TermLabel label="覆盖率" term="funding_coverage" />}>
                  {expected <= 0
                    ? <span style={{ color: '#999' }}>无</span>
                    : `${captured}/${expected} (${coverage == null ? '--' : `${(Number(coverage) * 100).toFixed(1)}%`})`}
                </Descriptions.Item>
                <Descriptions.Item label={<TermLabel label="原因" term="quality_reason" />} span={2}>
                  {q.quality_reason || '-'}
                </Descriptions.Item>
                <Descriptions.Item label="统计时间" span={2}>
                  {fmtTime(detailDrawer?.v2?.as_of)}
                </Descriptions.Item>
                <Descriptions.Item label="统计窗口" span={2}>
                  {detailDrawer?.v2?.window_mode === 'lifecycle' ? '策略生命周期' : '自定义窗口'}
                  {' | '}
                  {fmtTime(detailDrawer?.v2?.window_start_utc)} ~ {fmtTime(detailDrawer?.v2?.window_end_utc)}
                </Descriptions.Item>
                <Descriptions.Item label="平仓原因" span={2}>
                  {detailDrawer.close_reason || '-'}
                </Descriptions.Item>
              </Descriptions>
            );
          })()}

          <Card title="资金费事件 (v2)" size="small" style={{ marginBottom: 16 }}>
            <div style={{ marginBottom: 8 }}>
              <Space>
                <span style={{ color: '#888' }}>筛选:</span>
                <Select
                  size="small"
                  style={{ width: 180 }}
                  value={detailEventFilter}
                  onChange={setDetailEventFilter}
                  options={[
                    { label: '全部事件', value: 'all' },
                    { label: '仅已归因', value: 'assigned' },
                    { label: '仅未归因', value: 'unassigned' },
                  ]}
                />
              </Space>
            </div>
            <Table
              dataSource={(() => {
                const v2 = detailDrawer?.v2 || {};
                const allRows = v2.funding_events || [];
                const assignedRows = v2.funding_events_assigned || [];
                const unassignedRows = v2.funding_events_unassigned || [];
                if (detailEventFilter === 'assigned') return assignedRows;
                if (detailEventFilter === 'unassigned') return unassignedRows;
                return allRows;
              })()}
              rowKey={(r) => `${r.ledger_id}-${r.position_id || 0}-${r.funding_time}`}
              size="small"
              loading={detailLoading}
              pagination={{ pageSize: 8, showSizeChanger: false }}
              scroll={{ x: 980 }}
              columns={[
                { title: '结算时间', dataIndex: 'funding_time', width: 170, render: (v) => fmtTime(v) },
                { title: '交易所', dataIndex: 'exchange', width: 100 },
                { title: '交易对', dataIndex: 'symbol', width: 140 },
                { title: '金额', dataIndex: 'amount_usdt', width: 110, render: (v) => pnlRender(v, 6) },
                {
                  title: '归因金额',
                  dataIndex: 'assigned_amount_usdt',
                  width: 110,
                  render: (v, r) => (r.is_unassigned ? <Tag color="red">未归因</Tag> : pnlRender(v, 6)),
                },
                { title: '占比', dataIndex: 'assigned_ratio', width: 90, render: (v) => `${(Number(v || 0) * 100).toFixed(2)}%` },
                { title: '来源', dataIndex: 'source', width: 130 },
                { title: '来源引用', dataIndex: 'source_ref', width: 180, ellipsis: true },
                { title: '规则', dataIndex: 'assignment_rule', width: 90 },
              ]}
            />
          </Card>

          <Card title="腿信息" size="small">
            <Table
              dataSource={detailDrawer?.v2?.positions || detailDrawer?.positions || []}
              rowKey="id"
              size="small"
              pagination={false}
              columns={[
                { title: '交易所 ID', dataIndex: 'exchange_id' },
                {
                  title: '方向',
                  dataIndex: 'side',
                  render: (v) => <Tag color={v === 'long' ? 'green' : 'red'}>{v === 'long' ? '多' : '空'}</Tag>,
                },
                { title: '类型', dataIndex: 'position_type' },
                { title: '数量', dataIndex: 'size', render: (v) => v?.toFixed(4) },
                { title: <TermLabel label="本地入场价" term="entry_local" />, dataIndex: 'entry_local', render: (v) => (v == null ? '-' : v.toFixed(6)) },
                { title: <TermLabel label="交易所入场价" term="entry_exchange" />, dataIndex: 'entry_exchange', render: (v) => (v == null ? '-' : v.toFixed(6)) },
                {
                  title: '入场偏差',
                  dataIndex: 'entry_deviation_pct',
                  render: (v, r) => {
                    if (v == null) return <span style={{ color: '#999' }}>无</span>;
                    const txt = `${Number(v).toFixed(4)}%`;
                    if (r.entry_deviation_warn) {
                      return (
                        <Tooltip title={`入场偏差 >= ${r.entry_deviation_warn_threshold_pct || 0.05}%`}>
                          <Tag color="orange">{txt}</Tag>
                        </Tooltip>
                      );
                    }
                    return <span>{txt}</span>;
                  },
                },
                { title: '当前价', dataIndex: 'current_price', render: (v) => v?.toFixed(4) },
                { title: <TermLabel label="未实现盈亏 %" term="unrealized_pnl" />, dataIndex: 'unrealized_pnl_pct', render: pnlPctRender },
                { title: '状态', dataIndex: 'status' },
              ]}
            />
          </Card>
        </>
      )}
    </Drawer>
  );
}
