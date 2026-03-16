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
      title={`Strategy Detail #${detailDrawer?.id}`}
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
                <Descriptions.Item label="Status">{statusTag(detailDrawer.status)}</Descriptions.Item>
                <Descriptions.Item label="Type">{detailDrawer.strategy_type}</Descriptions.Item>
                <Descriptions.Item label="Symbol">{detailDrawer.symbol}</Descriptions.Item>
                <Descriptions.Item label={<TermLabel label="Margin" term="capital_base" />}>${margin}</Descriptions.Item>
                <Descriptions.Item label={<TermLabel label="Spread PnL" term="spread_pnl" />}>{pnlRender(spreadPnl)}</Descriptions.Item>
                <Descriptions.Item label={<TermLabel label="Funding PnL" term="funding_pnl" />}>
                  {fundingPnl == null ? <Tag color="red">missing</Tag> : pnlRender(fundingPnl, 4)}
                </Descriptions.Item>
                <Descriptions.Item label={<TermLabel label="Total PnL" term="total_pnl" />} span={2}>
                  {totalPnl == null ? <Tag color="orange">partial</Tag> : pnlRender(totalPnl, 4)}
                  <span style={{ marginLeft: 8, fontSize: 12, color: '#888' }}>
                    ({totalPnl != null && margin > 0 ? `${((totalPnl / margin) * 100).toFixed(2)}%` : '-'})
                  </span>
                </Descriptions.Item>
                <Descriptions.Item label={<TermLabel label="Quality" term="quality" />}>{qualityTag(quality)}</Descriptions.Item>
                <Descriptions.Item label={<TermLabel label="Coverage" term="funding_coverage" />}>
                  {expected <= 0
                    ? <span style={{ color: '#999' }}>n/a</span>
                    : `${captured}/${expected} (${coverage == null ? '--' : `${(Number(coverage) * 100).toFixed(1)}%`})`}
                </Descriptions.Item>
                <Descriptions.Item label={<TermLabel label="Reason" term="quality_reason" />} span={2}>
                  {q.quality_reason || '-'}
                </Descriptions.Item>
                <Descriptions.Item label="As Of" span={2}>
                  {fmtTime(detailDrawer?.v2?.as_of)}
                </Descriptions.Item>
                <Descriptions.Item label="Window" span={2}>
                  {detailDrawer?.v2?.window_mode === 'lifecycle' ? 'strategy_lifecycle' : 'custom_window'}
                  {' | '}
                  {fmtTime(detailDrawer?.v2?.window_start_utc)} ~ {fmtTime(detailDrawer?.v2?.window_end_utc)}
                </Descriptions.Item>
                <Descriptions.Item label="Close Reason" span={2}>
                  {detailDrawer.close_reason || '-'}
                </Descriptions.Item>
              </Descriptions>
            );
          })()}

          <Card title="Funding Events (v2)" size="small" style={{ marginBottom: 16 }}>
            <div style={{ marginBottom: 8 }}>
              <Space>
                <span style={{ color: '#888' }}>Filter:</span>
                <Select
                  size="small"
                  style={{ width: 180 }}
                  value={detailEventFilter}
                  onChange={setDetailEventFilter}
                  options={[
                    { label: 'All Events', value: 'all' },
                    { label: 'Assigned Only', value: 'assigned' },
                    { label: 'Unassigned Only', value: 'unassigned' },
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
                { title: 'Funding Time', dataIndex: 'funding_time', width: 170, render: (v) => fmtTime(v) },
                { title: 'Exchange', dataIndex: 'exchange', width: 100 },
                { title: 'Symbol', dataIndex: 'symbol', width: 140 },
                { title: 'Amount', dataIndex: 'amount_usdt', width: 110, render: (v) => pnlRender(v, 6) },
                {
                  title: 'Assigned',
                  dataIndex: 'assigned_amount_usdt',
                  width: 110,
                  render: (v, r) => (r.is_unassigned ? <Tag color="red">unassigned</Tag> : pnlRender(v, 6)),
                },
                { title: 'Ratio', dataIndex: 'assigned_ratio', width: 90, render: (v) => `${(Number(v || 0) * 100).toFixed(2)}%` },
                { title: 'Source', dataIndex: 'source', width: 130 },
                { title: 'Source Ref', dataIndex: 'source_ref', width: 180, ellipsis: true },
                { title: 'Rule', dataIndex: 'assignment_rule', width: 90 },
              ]}
            />
          </Card>

          <Card title="Leg Positions" size="small">
            <Table
              dataSource={detailDrawer?.v2?.positions || detailDrawer?.positions || []}
              rowKey="id"
              size="small"
              pagination={false}
              columns={[
                { title: 'Exchange ID', dataIndex: 'exchange_id' },
                {
                  title: 'Side',
                  dataIndex: 'side',
                  render: (v) => <Tag color={v === 'long' ? 'green' : 'red'}>{v}</Tag>,
                },
                { title: 'Type', dataIndex: 'position_type' },
                { title: 'Size', dataIndex: 'size', render: (v) => v?.toFixed(4) },
                { title: <TermLabel label="Entry Local" term="entry_local" />, dataIndex: 'entry_local', render: (v) => (v == null ? '-' : v.toFixed(6)) },
                { title: <TermLabel label="Entry Exch" term="entry_exchange" />, dataIndex: 'entry_exchange', render: (v) => (v == null ? '-' : v.toFixed(6)) },
                {
                  title: 'Entry Δ',
                  dataIndex: 'entry_deviation_pct',
                  render: (v, r) => {
                    if (v == null) return <span style={{ color: '#999' }}>n/a</span>;
                    const txt = `${Number(v).toFixed(4)}%`;
                    if (r.entry_deviation_warn) {
                      return (
                        <Tooltip title={`entry deviation >= ${r.entry_deviation_warn_threshold_pct || 0.05}%`}>
                          <Tag color="orange">{txt}</Tag>
                        </Tooltip>
                      );
                    }
                    return <span>{txt}</span>;
                  },
                },
                { title: 'Current', dataIndex: 'current_price', render: (v) => v?.toFixed(4) },
                { title: <TermLabel label="Unrealized PnL %" term="unrealized_pnl" />, dataIndex: 'unrealized_pnl_pct', render: pnlPctRender },
                { title: 'Status', dataIndex: 'status' },
              ]}
            />
          </Card>
        </>
      )}
    </Drawer>
  );
}
