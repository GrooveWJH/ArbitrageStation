import React, { useEffect, useState } from 'react';
import {
  Card,
  Table,
  Tag,
  Button,
  Space,
  Modal,
  Form,
  Select,
  InputNumber,
  Popconfirm,
  Drawer,
  Descriptions,
  Row,
  Col,
  message,
  Tooltip,
} from 'antd';
import {
  PlusOutlined,
  CloseCircleOutlined,
  EyeOutlined,
  ThunderboltOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import {
  getPnlV2StrategyDetail,
} from '../../services/endpoints/analyticsApi';
import {
  openStrategy,
  closeStrategy,
} from '../../services/endpoints/tradingApi';
import { usePositionsOverviewQuery } from '../../services/queries/positionsQueries';
import { fmtTime } from '../../utils/time';
import { TermLabel } from '../../components/TermHint';

export default function Positions() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(15);
  const [openModal, setOpenModal] = useState(false);
  const [detailDrawer, setDetailDrawer] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailEventFilter, setDetailEventFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('active');
  const [strategyType, setStrategyType] = useState('cross_exchange');
  const [form] = Form.useForm();
  const positionsOverviewQuery = usePositionsOverviewQuery({
    status: statusFilter,
    page,
    pageSize,
  });
  const overview = positionsOverviewQuery.data || {};
  const strategies = overview.strategies || [];
  const exchanges = overview.exchanges || [];
  const opportunities = overview.opportunities || [];
  const spotOpportunities = overview.spotOpportunities || [];
  const totalCount = overview.totalCount || 0;
  const loading = positionsOverviewQuery.isPending || positionsOverviewQuery.isFetching;

  useEffect(() => {
    setPage(1);
  }, [statusFilter]);

  const handleOpenStrategy = async (values) => {
    try {
      await openStrategy(values);
      message.success('Strategy opened');
      setOpenModal(false);
      form.resetFields();
      await positionsOverviewQuery.refetch();
    } catch (e) {
      message.error(`Open failed: ${e.response?.data?.detail || e.message}`);
    }
  };

  const handleClose = async (id) => {
    try {
      await closeStrategy(id, { reason: 'manual_close' });
      message.success('Close request sent');
      await positionsOverviewQuery.refetch();
    } catch (e) {
      message.error(`Close failed: ${e.message}`);
    }
  };

  const openDetail = async (record) => {
    setDetailEventFilter('all');
    setDetailDrawer({ ...record, v2: null });
    setDetailLoading(true);
    try {
      const res = await getPnlV2StrategyDetail(record.id, { window_mode: 'lifecycle', event_limit: 200 });
      const payload = res?.data || null;
      setDetailDrawer((prev) => (prev && prev.id === record.id ? { ...prev, v2: payload } : prev));
    } catch (e) {
      message.warning(`Load detail failed: ${e?.response?.data?.detail || e.message}`);
    } finally {
      setDetailLoading(false);
    }
  };

  const fillFromOpportunity = (opp) => {
    form.setFieldsValue({
      symbol: opp.symbol,
      long_exchange_id: opp.long_exchange_id,
      short_exchange_id: opp.short_exchange_id,
    });
  };

  const fillFromSpotOpportunity = (opp) => {
    form.setFieldsValue({
      symbol: opp.symbol,
      long_exchange_id: opp.long_exchange_id ?? opp.spot_exchange_id ?? opp.exchange_id,
      short_exchange_id: opp.short_exchange_id ?? opp.perp_exchange_id ?? opp.exchange_id,
    });
  };

  const statusTag = (status) => {
    const map = {
      active: ['green', 'Active'],
      closed: ['default', 'Closed'],
      closing: ['orange', 'Closing'],
      error: ['red', 'Error'],
    };
    const [color, label] = map[status] || ['default', status];
    return <Tag color={color}>{label}</Tag>;
  };

  const qualityTag = (quality) => {
    const q = quality || 'unknown';
    const colorMap = {
      ok: 'green',
      na: 'blue',
      partial: 'orange',
      stale: 'volcano',
      missing: 'red',
    };
    return <Tag color={colorMap[q] || 'default'}>{q}</Tag>;
  };

  const pnlRender = (v, precision = 2) => {
    if (v == null) return <span style={{ color: '#999' }}>--</span>;
    const n = Number(v);
    return (
      <span style={{ color: n >= 0 ? '#3f8600' : '#cf1322', fontWeight: 600 }}>
        {n >= 0 ? '+' : ''}
        {n.toFixed(precision)} USDT
      </span>
    );
  };

  const pnlPctRender = (v) => {
    if (v == null) return <span style={{ color: '#999' }}>--</span>;
    const n = Number(v);
    return (
      <span style={{ color: n >= 0 ? '#3f8600' : '#cf1322' }}>
        {n >= 0 ? '+' : ''}
        {n.toFixed(2)}%
      </span>
    );
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    { title: 'Strategy', dataIndex: 'name', key: 'name', ellipsis: true },
    {
      title: 'Type',
      dataIndex: 'strategy_type',
      key: 'strategy_type',
      width: 130,
      render: (v) => <Tag color={v === 'cross_exchange' ? 'purple' : 'cyan'}>{v === 'cross_exchange' ? 'Cross Exchange' : 'Spot Hedge'}</Tag>,
    },
    { title: 'Symbol', dataIndex: 'symbol', key: 'symbol', render: (v) => <Tag color="blue">{v}</Tag> },
    { title: 'Long Ex', dataIndex: 'long_exchange', key: 'long_exchange' },
    { title: 'Short Ex', dataIndex: 'short_exchange', key: 'short_exchange' },
    {
      title: <TermLabel label="当前年化" term="current_annualized" />,
      dataIndex: 'current_annualized',
      key: 'current_annualized',
      width: 120,
      render: (v) => (v == null ? <span style={{ color: '#999' }}>--</span> : `${Number(v).toFixed(2)}%`),
      sorter: (a, b) => Number(a.current_annualized ?? -1e18) - Number(b.current_annualized ?? -1e18),
    },
    { title: <TermLabel label="Margin (U)" term="capital_base" />, dataIndex: 'initial_margin_usd', key: 'initial_margin_usd', render: (v) => `$${v?.toFixed(0)}` },
    {
      title: <TermLabel label="Spread PnL" term="spread_pnl" />,
      dataIndex: 'unrealized_pnl',
      key: 'unrealized_pnl',
      render: (v) => <Tooltip title="Price-move PnL during holding">{pnlRender(v)}</Tooltip>,
    },
    {
      title: <TermLabel label="Funding PnL" term="funding_pnl" />,
      dataIndex: 'funding_pnl_usd',
      key: 'funding_pnl_usd',
      render: (v) => (v == null ? <Tag color="red">missing</Tag> : <Tooltip title="Funding fee PnL from ledger attribution">{pnlRender(v, 4)}</Tooltip>),
    },
    {
      title: <TermLabel label="Total PnL" term="total_pnl" />,
      dataIndex: 'total_pnl_usd',
      key: 'total_pnl_usd',
      render: (v, r) => {
        if (v == null) return <Tag color="orange">partial</Tag>;
        const n = Number(v);
        const pct = r.initial_margin_usd > 0 ? (n / r.initial_margin_usd) * 100 : 0;
        return (
          <span style={{ fontWeight: 700, color: n >= 0 ? '#3f8600' : '#cf1322' }}>
            {n >= 0 ? '+' : ''}
            {n.toFixed(4)}U
            <span style={{ fontSize: 11, marginLeft: 4, color: pct >= 0 ? '#3f8600' : '#cf1322' }}>
              ({pct >= 0 ? '+' : ''}
              {pct.toFixed(2)}%)
            </span>
          </span>
        );
      },
      sorter: (a, b) => Number(a.total_pnl_usd ?? -1e18) - Number(b.total_pnl_usd ?? -1e18),
    },
    {
      title: <TermLabel label="Quality" term="quality" />,
      dataIndex: 'quality',
      key: 'quality',
      width: 92,
      render: (v) => qualityTag(v),
    },
    { title: 'Status', dataIndex: 'status', key: 'status', render: statusTag },
    { title: 'Opened At', dataIndex: 'created_at', key: 'created_at', render: (v) => fmtTime(v), width: 160 },
    {
      title: 'Close Reason',
      dataIndex: 'close_reason',
      key: 'close_reason',
      ellipsis: true,
      width: 220,
      render: (v, record) =>
        v ? (
          <Tooltip title={v}>
            <span style={{ color: record.status === 'error' ? '#ff4d4f' : '#888', fontSize: 12 }}>{v}</span>
          </Tooltip>
        ) : null,
    },
    { title: 'Closed At', dataIndex: 'closed_at', key: 'closed_at', render: (v) => fmtTime(v), width: 160 },
    {
      title: 'Action',
      key: 'action',
      fixed: 'right',
      width: 150,
      render: (_, record) => (
        <Space>
          <Button size="small" icon={<EyeOutlined />} onClick={() => openDetail(record)}>
            Detail
          </Button>
          {record.status === 'active' && (
            <Popconfirm title="Confirm close?" onConfirm={() => handleClose(record.id)}>
              <Button size="small" danger icon={<CloseCircleOutlined />}>
                Close
              </Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];

  return (
    <>
      <Card
        title="Strategy Management"
        extra={
          <Space>
            <Select
              value={statusFilter}
              onChange={setStatusFilter}
              style={{ width: 140 }}
              options={[
                { label: 'Active', value: 'active' },
                { label: 'Closed', value: 'closed' },
                { label: 'All', value: undefined },
              ]}
            />
            <Button
              icon={<ReloadOutlined />}
              onClick={() => { void positionsOverviewQuery.refetch(); }}
              loading={loading}
            >
              Refresh
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpenModal(true)}>
              Open Strategy
            </Button>
          </Space>
        }
      >
        <Table
          dataSource={strategies}
          columns={columns}
          rowKey="id"
          loading={loading}
          size="small"
          scroll={{ x: 1400 }}
          pagination={{
            current: page,
            pageSize,
            total: totalCount,
            showSizeChanger: true,
            pageSizeOptions: [15, 30, 50, 100],
            showTotal: (t, range) => `${range[0]}-${range[1]} / ${t}`,
            onChange: (nextPage, nextPageSize) => {
              setPage(nextPage);
              if (nextPageSize !== pageSize) setPageSize(nextPageSize);
            },
          }}
          rowClassName={(r) => {
            if (r.quality === 'missing') return 'missing-row';
            if (r.total_pnl_usd == null) return 'partial-row';
            return '';
          }}
        />
      </Card>

      <Modal title="Open Strategy" open={openModal} onCancel={() => setOpenModal(false)} footer={null} width={700}>
        {strategyType === 'cross_exchange' && opportunities.length > 0 && (
          <Card size="small" title={<><ThunderboltOutlined /> Top Cross Opportunities</>} style={{ marginBottom: 16 }}>
            <Table
              dataSource={opportunities.slice(0, 5)}
              size="small"
              pagination={false}
              rowKey="symbol"
              columns={[
                { title: 'Symbol', dataIndex: 'symbol' },
                { title: 'Long Ex', dataIndex: 'long_exchange' },
                { title: 'Short Ex', dataIndex: 'short_exchange' },
                { title: 'Annualized', dataIndex: 'annualized_pct', render: (v) => `${v.toFixed(1)}%` },
                {
                  title: '',
                  key: 'fill',
                  render: (_, r) => (
                    <Button size="small" onClick={() => fillFromOpportunity(r)}>
                      Fill
                    </Button>
                  ),
                },
              ]}
            />
          </Card>
        )}

        {strategyType === 'spot_hedge' && spotOpportunities.length > 0 && (
          <Card size="small" title={<><ThunderboltOutlined /> Top Spot-Perp Opportunities</>} style={{ marginBottom: 16 }}>
            <Table
              dataSource={spotOpportunities.slice(0, 5)}
              size="small"
              pagination={false}
              rowKey={(r) =>
                `${r.symbol}-${r.long_exchange_id ?? r.spot_exchange_id ?? r.exchange_id}-${r.short_exchange_id ?? r.perp_exchange_id ?? r.exchange_id}`
              }
              columns={[
                { title: 'Symbol', dataIndex: 'symbol' },
                { title: 'Spot Ex', dataIndex: 'long_exchange' },
                { title: 'Perp Ex', dataIndex: 'short_exchange' },
                { title: 'Rate', dataIndex: 'rate_pct', render: (v) => `${v > 0 ? '+' : ''}${v.toFixed(4)}%` },
                { title: 'Annualized', dataIndex: 'annualized_pct', render: (v) => `${v.toFixed(1)}%` },
                {
                  title: '',
                  key: 'fill',
                  render: (_, r) => (
                    <Button size="small" onClick={() => fillFromSpotOpportunity(r)}>
                      Fill
                    </Button>
                  ),
                },
              ]}
            />
          </Card>
        )}

        <Form
          form={form}
          layout="vertical"
          onFinish={handleOpenStrategy}
          onValuesChange={(changed) => {
            if (changed.strategy_type) setStrategyType(changed.strategy_type);
          }}
          initialValues={{ strategy_type: 'cross_exchange', leverage: 1 }}
        >
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="strategy_type" label="Strategy Type" rules={[{ required: true }]}>
                <Select
                  options={[
                    { label: 'Cross Exchange - long low funding / short high funding', value: 'cross_exchange' },
                    { label: 'Spot Hedge - buy spot + short perp', value: 'spot_hedge' },
                  ]}
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="symbol"
                label={strategyType === 'spot_hedge' ? 'Perp Symbol' : 'Symbol'}
                rules={[{ required: true }]}
              >
                <Select
                  showSearch
                  placeholder="e.g. BTC/USDT:USDT"
                  options={[
                    'BTC/USDT:USDT',
                    'ETH/USDT:USDT',
                    'SOL/USDT:USDT',
                    'BNB/USDT:USDT',
                    'XRP/USDT:USDT',
                    'DOGE/USDT:USDT',
                    'AVAX/USDT:USDT',
                    'LINK/USDT:USDT',
                    'DOT/USDT:USDT',
                    'ADA/USDT:USDT',
                    'MATIC/USDT:USDT',
                    'LTC/USDT:USDT',
                  ].map((s) => ({ label: s, value: s }))}
                  allowClear
                />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="long_exchange_id"
                label={strategyType === 'spot_hedge' ? 'Spot Exchange (buy spot)' : 'Long Exchange'}
                rules={[{ required: true }]}
              >
                <Select options={exchanges.map((e) => ({ label: e.display_name, value: e.id }))} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="short_exchange_id"
                label={strategyType === 'spot_hedge' ? 'Perp Exchange (short perp)' : 'Short Exchange'}
                rules={[{ required: true }]}
              >
                <Select options={exchanges.map((e) => ({ label: e.display_name, value: e.id }))} />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="size_usd" label="Margin (USDT)" rules={[{ required: true }]}>
                <InputNumber style={{ width: '100%' }} min={0} step={100} prefix="$" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="leverage" label="Leverage">
                <InputNumber style={{ width: '100%' }} min={1} max={20} step={1} suffix="x" />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item>
            <Button type="primary" htmlType="submit" block>
              Confirm Open
            </Button>
          </Form.Item>
        </Form>
      </Modal>

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
                      ({totalPnl != null && margin > 0 ? `${(totalPnl / margin * 100).toFixed(2)}%` : '-'})
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

      <style>{`
        .missing-row { background: #fff1f0 !important; }
        .partial-row { background: #fff7e6 !important; }
      `}</style>
    </>
  );
}
