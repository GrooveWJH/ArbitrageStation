import React, { useEffect, useMemo, useState } from 'react';
import {
  Button,
  Card,
  Col,
  Empty,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Tooltip,
  message,
} from 'antd';
import {
  ArrowDownOutlined,
  ArrowUpOutlined,
  DownloadOutlined,
  ExclamationCircleOutlined,
  LineChartOutlined,
  ReloadOutlined,
  SyncOutlined,
} from '@ant-design/icons';
import { Line } from '@ant-design/charts';
import {
  getEquityCurve,
  getPnlV2Export,
  getPnlV2ReconcileLatest,
  getPnlV2Strategies,
  getPnlV2Summary,
  runPnlV2FundingIngest,
} from '../../services/api';
import { fmtTime } from '../../utils/time';
import { TermLabel } from '../../components/TermHint';

const qualityColor = {
  ok: 'green',
  na: 'blue',
  partial: 'orange',
  stale: 'volcano',
  missing: 'red',
};

function QualityTag({ value }) {
  const q = value || 'unknown';
  return <Tag color={qualityColor[q] || 'default'}>{q}</Tag>;
}

function PnlText({ value, precision = 4, suffix = 'U' }) {
  if (value == null) return <span style={{ color: '#999' }}>--</span>;
  const pos = value >= 0;
  return (
    <span style={{ color: pos ? '#3f8600' : '#cf1322', fontWeight: 600 }}>
      {pos ? <ArrowUpOutlined /> : <ArrowDownOutlined />} {pos ? '+' : ''}
      {Number(value).toFixed(precision)} {suffix}
    </span>
  );
}

function StatusTag({ value }) {
  const map = {
    active: ['blue', 'active'],
    closed: ['green', 'closed'],
    closing: ['orange', 'closing'],
    error: ['red', 'error'],
  };
  const one = map[value] || ['default', String(value || '-')];
  return <Tag color={one[0]}>{one[1]}</Tag>;
}

function EquityCurve({ days }) {
  const [eq, setEq] = useState(null);
  const [loading, setLoading] = useState(false);
  const [view, setView] = useState('equity');

  const load = async () => {
    setLoading(true);
    try {
      const res = await getEquityCurve(days);
      setEq(res.data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [days]);

  const chartData = useMemo(() => {
    if (!eq?.points?.length) return [];
    if (view === 'equity') {
      return eq.points.map((p) => ({ time: p.time, value: p.total, type: 'equity' }));
    }
    return eq.points.map((p) => ({ time: p.time, value: p.profit, type: 'profit' }));
  }, [eq, view]);

  const color = view === 'equity' ? '#1677ff' : '#52c41a';
  const config = {
    data: chartData,
    encode: { x: 'time', y: 'value', color: 'type' },
    smooth: true,
    animation: false,
    style: { stroke: color, lineWidth: 2 },
    point: chartData.length <= 30 ? { size: 3 } : false,
  };

  return (
    <Card
      size="small"
      style={{ marginBottom: 16 }}
      title={
        <Space>
          <LineChartOutlined style={{ color: '#1677ff' }} />
          <span>Equity Curve</span>
        </Space>
      }
      extra={
        <Space>
          <Select
            size="small"
            value={view}
            style={{ width: 120 }}
            onChange={setView}
            options={[
              { label: 'Equity', value: 'equity' },
              { label: 'Profit', value: 'profit' },
            ]}
          />
          <Button size="small" icon={<ReloadOutlined />} onClick={load} loading={loading} />
        </Space>
      }
    >
      {!loading && (!eq?.points || eq.points.length === 0) ? (
        <Empty description="No equity snapshots yet" />
      ) : (
        <div style={{ height: 260 }}>
          <Line {...config} />
        </div>
      )}
    </Card>
  );
}

export default function Analytics() {
  const [days, setDays] = useState(30);
  const [scope, setScope] = useState('active');
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [summary, setSummary] = useState(null);
  const [rows, setRows] = useState([]);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [totalCount, setTotalCount] = useState(0);
  const [dailyReconcile, setDailyReconcile] = useState(null);
  const statusFilter = scope === 'all' ? undefined : scope;

  const load = async () => {
    setLoading(true);
    try {
      const [s, r, rec] = await Promise.all([
        getPnlV2Summary({ days, status: statusFilter }),
        getPnlV2Strategies({ days, status: statusFilter, page, page_size: pageSize }),
        getPnlV2ReconcileLatest(1),
      ]);
      setSummary(s.data || {});
      setRows((r.data && r.data.rows) || []);
      setTotalCount(Number(r?.data?.total_count || 0));
      const recRows = (rec.data && rec.data.rows) || [];
      setDailyReconcile(recRows.length > 0 ? recRows[0] : null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [days, scope, page, pageSize]);

  useEffect(() => {
    setPage(1);
  }, [days, scope]);

  const onSyncFunding = async () => {
    setSyncing(true);
    try {
      const res = await runPnlV2FundingIngest({ lookback_hours: 72 });
      const cnt = (res.data && res.data.count) || 0;
      message.success(`funding ingest done (${cnt} exchanges)`);
      await load();
    } catch (e) {
      message.error(`ingest failed: ${e?.response?.data?.detail || e.message}`);
    } finally {
      setSyncing(false);
    }
  };

  const expected = Number(summary?.funding_expected_event_count || 0);
  const captured = Number(summary?.funding_captured_event_count || 0);
  const coveragePct = expected > 0 ? (captured / expected) * 100 : null;
  const anomalyStrategyCount =
    Number.isFinite(Number(summary?.anomaly_strategy_count))
      ? Number(summary?.anomaly_strategy_count)
      : rows.filter((r) => !['ok', 'na'].includes(r.quality) || r.total_pnl_usdt == null).length;
  const statusOverview = summary?.status_overview || {
    started_count: Number(summary?.started_count || 0),
    closed_count: Number(summary?.closed_count || 0),
    continued_count: Number(summary?.continued_count || 0),
  };
  const profitAttribution = (summary?.attribution && summary.attribution.profit) || [];
  const lossAttribution = (summary?.attribution && summary.attribution.loss) || [];
  const warnings = useMemo(() => {
    const out = [];
    (summary?.warnings || []).forEach((w) => {
      if (w && !out.includes(w)) out.push(w);
    });
    return out;
  }, [summary]);

  const closedWithTotalCount = Number(summary?.closed_with_total_count || 0);
  const winCount = Number(summary?.closed_win_count || 0);
  const winRate =
    summary?.closed_win_rate == null
      ? (closedWithTotalCount > 0 ? (winCount / closedWithTotalCount) * 100 : 0)
      : Number(summary.closed_win_rate) * 100;

  const columns = [
    { title: 'ID', dataIndex: 'strategy_id', width: 72 },
    { title: 'Type', dataIndex: 'strategy_type', width: 120 },
    { title: 'Symbol', dataIndex: 'symbol', width: 150, render: (v) => <Tag color="blue">{v}</Tag> },
    { title: 'Long', dataIndex: 'long_exchange', width: 110 },
    { title: 'Short', dataIndex: 'short_exchange', width: 110 },
    { title: <TermLabel label="Margin" term="capital_base" />, dataIndex: 'initial_margin_usd', width: 95, render: (v) => `$${Number(v || 0).toFixed(2)}` },
    {
      title: <TermLabel label="Spread" term="spread_pnl" />,
      dataIndex: 'spread_pnl_usdt',
      width: 120,
      render: (v) => <PnlText value={v} />,
      sorter: (a, b) => Number(a.spread_pnl_usdt || -1e18) - Number(b.spread_pnl_usdt || -1e18),
    },
    {
      title: <TermLabel label="Funding" term="funding_pnl" />,
      dataIndex: 'funding_pnl_usdt',
      width: 130,
      render: (v, r) => {
        if (v == null) return <Tag color="red">missing</Tag>;
        return (
          <Space size={4}>
            <PnlText value={v} />
            {r.quality !== 'ok' ? <QualityTag value={r.quality} /> : null}
          </Space>
        );
      },
    },
    {
      title: <TermLabel label="Fee" term="fee_usdt" />,
      dataIndex: 'fee_usdt',
      width: 100,
      render: (v) => <span style={{ color: '#cf1322', fontWeight: 600 }}>-{Number(v || 0).toFixed(4)} U</span>,
    },
    {
      title: <TermLabel label="Total" term="total_pnl" />,
      dataIndex: 'total_pnl_usdt',
      width: 120,
      render: (v, r) => {
        if (v == null) return <Tag color="orange">partial</Tag>;
        return <PnlText value={v} />;
      },
      sorter: (a, b) => Number(a.total_pnl_usdt || -1e18) - Number(b.total_pnl_usdt || -1e18),
    },
    {
      title: <TermLabel label="Quality" term="quality" />,
      dataIndex: 'quality',
      width: 90,
      render: (v) => <QualityTag value={v} />,
    },
    {
      title: <TermLabel label="Reason" term="quality_reason" />,
      dataIndex: 'quality_reason',
      width: 180,
      ellipsis: true,
      render: (v) => (v ? <Tag>{v}</Tag> : <span style={{ color: '#999' }}>-</span>),
    },
    {
      title: <TermLabel label="Funding Coverage" term="funding_coverage" />,
      key: 'coverage',
      width: 130,
      render: (_, r) => {
        const e = Number(r.funding_expected_event_count || 0);
        const c = Number(r.funding_captured_event_count || 0);
        if (e <= 0) return <span style={{ color: '#999' }}>n/a</span>;
        const pct = (c / e) * 100;
        return (
          <Tooltip title={`${c}/${e}`}>
            <span>{pct.toFixed(1)}%</span>
          </Tooltip>
        );
      },
    },
    { title: 'Status', dataIndex: 'status', width: 90, render: (v) => <StatusTag value={v} /> },
    { title: 'Created', dataIndex: 'created_at', width: 160, render: (v) => fmtTime(v) },
    { title: 'Closed', dataIndex: 'closed_at', width: 160, render: (v) => fmtTime(v) },
  ];

  const onExportCsv = async () => {
    try {
      const res = await getPnlV2Export({ days, status: statusFilter, format: 'csv' });
      const csv = String(res?.data || '');
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      const ts = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
      a.href = url;
      a.download = `pnl_v2_${ts}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      message.error(`export failed: ${e?.response?.data?.detail || e.message}`);
    }
  };

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <span style={{ fontSize: 18, fontWeight: 700 }}>P&L Analytics (v2)</span>
        </Col>
        <Col>
          <Space>
            <Select
              value={scope}
              onChange={setScope}
              style={{ width: 130 }}
              options={[
                { label: 'Active', value: 'active' },
                { label: 'All', value: 'all' },
              ]}
            />
            <Select
              value={days}
              onChange={setDays}
              style={{ width: 130 }}
              options={[
                { label: 'Last 7d', value: 7 },
                { label: 'Last 30d', value: 30 },
                { label: 'Last 90d', value: 90 },
                { label: 'All', value: 0 },
              ]}
            />
            <Button icon={<ReloadOutlined />} onClick={load} loading={loading}>Refresh</Button>
            <Button icon={<SyncOutlined />} onClick={onSyncFunding} loading={syncing}>Sync Funding</Button>
            <Button icon={<DownloadOutlined />} onClick={onExportCsv}>Export CSV</Button>
          </Space>
        </Col>
      </Row>

      <Card size="small" style={{ marginBottom: 12 }}>
        <Space wrap size={12}>
          <span style={{ color: '#666' }}>scope:</span>
          <Tag color={scope === 'active' ? 'blue' : 'default'}>{scope}</Tag>
          <span style={{ color: '#666' }}>as_of:</span>
          <Tag>{fmtTime(summary?.as_of) || '-'}</Tag>
          <span style={{ color: '#666' }}>timezone:</span>
          <Tag>{summary?.timezone || 'UTC+8'}</Tag>
          <span style={{ color: '#666' }}><TermLabel label="funding_quality" term="funding_quality" />:</span>
          <QualityTag value={summary?.funding_quality || summary?.quality} />
          <span style={{ color: '#666' }}>funding_coverage:</span>
          <Tag color={coveragePct == null ? 'default' : coveragePct >= 98 ? 'green' : coveragePct > 0 ? 'orange' : 'red'}>
            {coveragePct == null ? 'n/a' : `${coveragePct.toFixed(1)}%`}
          </Tag>
          <span style={{ color: '#666' }}>daily_reconcile:</span>
          <Tag color={dailyReconcile?.passed ? 'green' : (dailyReconcile ? 'red' : 'default')}>
            {dailyReconcile ? `${dailyReconcile.trade_date_cn} ${dailyReconcile.passed ? 'pass' : 'fail'}` : 'n/a'}
          </Tag>
          <span style={{ color: '#666' }}>anomaly_strategies:</span>
          <Tag color={anomalyStrategyCount > 0 ? 'red' : 'green'}>{anomalyStrategyCount}</Tag>
        </Space>
      </Card>

      {warnings.length > 0 ? (
        <Card
          size="small"
          style={{ marginBottom: 12, borderColor: '#ffccc7', background: '#fff2f0' }}
          title={
            <Space>
              <ExclamationCircleOutlined style={{ color: '#cf1322' }} />
              <span>Warnings</span>
              <Tag color="red">{warnings.length}</Tag>
            </Space>
          }
        >
          <Space wrap>
            {warnings.map((w) => (
              <Tag key={w} color="red">{w}</Tag>
            ))}
          </Space>
        </Card>
      ) : null}

      <EquityCurve days={days} />

      <Row gutter={12} style={{ marginBottom: 12 }}>
        <Col span={6}>
          <Card size="small">
            <div style={{ color: '#888', fontSize: 12 }}><TermLabel label="Total PnL" term="total_pnl" /></div>
            <div style={{ fontSize: 22, fontWeight: 700 }}>
              <PnlText value={summary?.total_pnl_usdt} />
            </div>
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <div style={{ color: '#888', fontSize: 12 }}><TermLabel label="Spread PnL" term="spread_pnl" /></div>
            <div style={{ fontSize: 22, fontWeight: 700 }}>
              <PnlText value={summary?.spread_pnl_usdt} />
            </div>
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <div style={{ color: '#888', fontSize: 12 }}><TermLabel label="Funding PnL" term="funding_pnl" /></div>
            <div style={{ fontSize: 22, fontWeight: 700 }}>
              {summary?.funding_pnl_usdt == null ? <Tag color="red">missing</Tag> : <PnlText value={summary?.funding_pnl_usdt} />}
            </div>
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <div style={{ color: '#888', fontSize: 12 }}><TermLabel label="Fee" term="fee_usdt" /></div>
            <div style={{ fontSize: 22, fontWeight: 700, color: '#cf1322' }}>
              -{Number(summary?.fee_usdt || 0).toFixed(4)} U
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={12} style={{ marginBottom: 16 }}>
        <Col span={12}>
          <Card size="small" title={<TermLabel label="Data Quality" term="quality" />}>
            <Space wrap>
              <span>quality:</span>
              <QualityTag value={summary?.quality} />
              <span>coverage:</span>
              {coveragePct == null ? <span style={{ color: '#999' }}>n/a</span> : <span>{coveragePct.toFixed(1)}%</span>}
              <span>events:</span>
              <span>{captured}/{expected}</span>
              <span>slippage policy:</span>
              <Tag>{summary?.slippage_policy || 'excluded_from_total'}</Tag>
            </Space>
          </Card>
        </Col>
        <Col span={12}>
          <Card size="small" title="Closed Win Rate">
            <Space>
              <span>{winCount}/{closedWithTotalCount}</span>
              <Tag color={winRate >= 60 ? 'green' : winRate >= 40 ? 'orange' : 'red'}>
                {winRate.toFixed(1)}%
              </Tag>
              <span style={{ color: '#888' }}>reconcile:</span>
              <Tag color={summary?.reconciliation?.passed ? 'green' : 'red'}>
                {summary?.reconciliation?.passed ? 'pass' : 'fail'}
              </Tag>
              <span style={{ color: '#888' }}>daily:</span>
              <Tag color={dailyReconcile?.passed ? 'green' : (dailyReconcile ? 'red' : 'default')}>
                {dailyReconcile ? `${dailyReconcile.trade_date_cn} ${dailyReconcile.passed ? 'pass' : 'fail'}` : 'n/a'}
              </Tag>
              {dailyReconcile ? (
                <Tooltip title={`abs=${Number(dailyReconcile.abs_diff || 0).toFixed(6)}, pct=${(Number(dailyReconcile.pct_diff || 0) * 100).toFixed(4)}%`}>
                  <Tag>{`diff ${Number(dailyReconcile.abs_diff || 0).toFixed(4)}U`}</Tag>
                </Tooltip>
              ) : null}
            </Space>
          </Card>
        </Col>
      </Row>

      <Row gutter={12} style={{ marginBottom: 12 }}>
        <Col span={8}>
          <Card size="small">
            <div style={{ color: '#888', fontSize: 12 }}><TermLabel label="Started" term="started_count" /></div>
            <div style={{ fontSize: 22, fontWeight: 700, color: '#1677ff' }}>{Number(statusOverview.started_count || 0)}</div>
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <div style={{ color: '#888', fontSize: 12 }}><TermLabel label="Closed" term="closed_count" /></div>
            <div style={{ fontSize: 22, fontWeight: 700, color: '#52c41a' }}>{Number(statusOverview.closed_count || 0)}</div>
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <div style={{ color: '#888', fontSize: 12 }}><TermLabel label="Continued" term="continued_count" /></div>
            <div style={{ fontSize: 22, fontWeight: 700, color: '#fa8c16' }}>{Number(statusOverview.continued_count || 0)}</div>
          </Card>
        </Col>
      </Row>

      <Row gutter={12} style={{ marginBottom: 16 }}>
        <Col span={12}>
          <Card size="small" title={<TermLabel label="Profit Attribution" term="attribution" />}>
            <Table
              size="small"
              pagination={false}
              rowKey={(r) => `p-${r.strategy_type}`}
              dataSource={profitAttribution}
              columns={[
                { title: 'Type', dataIndex: 'strategy_type', width: 120 },
                { title: 'Strategies', dataIndex: 'strategy_count', width: 90 },
                {
                  title: 'PnL',
                  dataIndex: 'pnl_usdt',
                  render: (v) => <PnlText value={v} />,
                },
                {
                  title: 'Ratio',
                  dataIndex: 'pnl_ratio',
                  render: (v) => (v == null ? '--' : `${(Number(v) * 100).toFixed(2)}%`),
                },
              ]}
              expandable={{
                rowExpandable: (r) => Array.isArray(r?.strategies) && r.strategies.length > 0,
                expandedRowRender: (r) => (
                  <Table
                    size="small"
                    pagination={false}
                    rowKey={(s) => `p-${r.strategy_type}-${s.strategy_id}`}
                    dataSource={r.strategies || []}
                    columns={[
                      { title: 'Strategy ID', dataIndex: 'strategy_id', width: 110 },
                      { title: 'Name', dataIndex: 'name', ellipsis: true },
                      { title: 'PnL', dataIndex: 'pnl_usdt', width: 150, render: (v) => <PnlText value={v} /> },
                    ]}
                  />
                ),
              }}
              locale={{ emptyText: 'No profit attribution' }}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card size="small" title={<TermLabel label="Loss Attribution" term="attribution" />}>
            <Table
              size="small"
              pagination={false}
              rowKey={(r) => `l-${r.strategy_type}`}
              dataSource={lossAttribution}
              columns={[
                { title: 'Type', dataIndex: 'strategy_type', width: 120 },
                { title: 'Strategies', dataIndex: 'strategy_count', width: 90 },
                {
                  title: 'PnL',
                  dataIndex: 'pnl_usdt',
                  render: (v) => <PnlText value={v} />,
                },
                {
                  title: 'Ratio',
                  dataIndex: 'pnl_ratio',
                  render: (v) => (v == null ? '--' : `${(Number(v) * 100).toFixed(2)}%`),
                },
              ]}
              expandable={{
                rowExpandable: (r) => Array.isArray(r?.strategies) && r.strategies.length > 0,
                expandedRowRender: (r) => (
                  <Table
                    size="small"
                    pagination={false}
                    rowKey={(s) => `l-${r.strategy_type}-${s.strategy_id}`}
                    dataSource={r.strategies || []}
                    columns={[
                      { title: 'Strategy ID', dataIndex: 'strategy_id', width: 110 },
                      { title: 'Name', dataIndex: 'name', ellipsis: true },
                      { title: 'PnL', dataIndex: 'pnl_usdt', width: 150, render: (v) => <PnlText value={v} /> },
                    ]}
                  />
                ),
              }}
              locale={{ emptyText: 'No loss attribution' }}
            />
          </Card>
        </Col>
      </Row>

      <Card
        size="small"
        title={
          <Space>
            Strategy Rows
            <Tag color="blue">{totalCount}</Tag>
          </Space>
        }
      >
        <Table
          dataSource={rows}
          columns={columns}
          rowKey="strategy_id"
          size="small"
          loading={loading}
          scroll={{ x: 2050 }}
          pagination={{
            current: page,
            pageSize,
            total: totalCount,
            showSizeChanger: true,
            pageSizeOptions: [20, 50, 100, 200],
            showTotal: (t, range) => `${range[0]}-${range[1]} / ${t}`,
            onChange: (nextPage, nextPageSize) => {
              setPage(nextPage);
              if (nextPageSize !== pageSize) setPageSize(nextPageSize);
            },
          }}
          rowClassName={(r) => {
            if (r.quality === 'missing') return 'missing-row';
            if (r.total_pnl_usdt == null) return 'partial-row';
            if (Number(r.total_pnl_usdt) < 0) return 'loss-row';
            return '';
          }}
        />
      </Card>

      <style>{`
        .missing-row { background: #fff1f0 !important; }
        .partial-row { background: #fff7e6 !important; }
        .loss-row { background: #fffafb !important; }
      `}</style>
    </div>
  );
}
