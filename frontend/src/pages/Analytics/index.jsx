import React, {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react';
import {
  Button,
  Card,
  Col,
  Row,
  Select,
  Space,
  Table,
  Tag,
  message,
} from 'antd';
import {
  DownloadOutlined,
  ReloadOutlined,
  SyncOutlined,
} from '@ant-design/icons';
import {
  getPnlV2Export,
  runPnlV2FundingIngest,
} from '../../services/endpoints/analyticsApi';
import {
  useAnalyticsPnlReconcileLatestQuery,
  useAnalyticsPnlStrategiesQuery,
  useAnalyticsPnlSummaryQuery,
} from '../../services/queries/analyticsQueries';
import { getApiErrorMessage } from '../../utils/error';
import AttributionTables from './AttributionTables';
import EquityCurveCard from './EquityCurveCard';
import {
  PnlOverviewRow,
  QualityAndWinRateRow,
  StatusOverviewRow,
  SummaryMetaCard,
  WarningsCard,
} from './SummaryPanels';
import { buildStrategyColumns } from './strategyColumns';

export default function Analytics() {
  const [days, setDays] = useState(30);
  const [scope, setScope] = useState('active');
  const [syncing, setSyncing] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const statusFilter = scope === 'all' ? undefined : scope;

  const summaryQuery = useAnalyticsPnlSummaryQuery({ days, status: statusFilter });
  const strategiesQuery = useAnalyticsPnlStrategiesQuery({
    days,
    status: statusFilter,
    page,
    page_size: pageSize,
  });
  const reconcileQuery = useAnalyticsPnlReconcileLatestQuery(1);

  const summary = summaryQuery.data || {};
  const rows = strategiesQuery.data?.rows || [];
  const totalCount = Number(strategiesQuery.data?.total_count || 0);
  const recRows = reconcileQuery.data?.rows || [];
  const dailyReconcile = recRows.length > 0 ? recRows[0] : null;

  const loading = [summaryQuery, strategiesQuery, reconcileQuery].some((q) => q.isLoading && !q.isFetched);
  const refreshing = [summaryQuery, strategiesQuery, reconcileQuery].some((q) => q.isFetching);

  const refreshAnalytics = useCallback(async () => {
    await Promise.all([
      summaryQuery.refetch(),
      strategiesQuery.refetch(),
      reconcileQuery.refetch(),
    ]);
  }, [summaryQuery, strategiesQuery, reconcileQuery]);

  useEffect(() => {
    setPage(1);
  }, [days, scope]);

  const onSyncFunding = useCallback(async () => {
    setSyncing(true);
    try {
      const res = await runPnlV2FundingIngest({ lookback_hours: 72 });
      const cnt = res.data?.count || 0;
      message.success(`funding ingest done (${cnt} exchanges)`);
      await refreshAnalytics();
    } catch (e) {
      message.error(`ingest failed: ${getApiErrorMessage(e)}`);
    } finally {
      setSyncing(false);
    }
  }, [refreshAnalytics]);

  const expected = Number(summary?.funding_expected_event_count || 0);
  const captured = Number(summary?.funding_captured_event_count || 0);
  const coveragePct = expected > 0 ? (captured / expected) * 100 : null;
  const anomalyStrategyCount = Number.isFinite(Number(summary?.anomaly_strategy_count))
    ? Number(summary?.anomaly_strategy_count)
    : rows.filter((r) => !['ok', 'na'].includes(r.quality) || r.total_pnl_usdt == null).length;
  const statusOverview = summary?.status_overview || {
    started_count: Number(summary?.started_count || 0),
    closed_count: Number(summary?.closed_count || 0),
    continued_count: Number(summary?.continued_count || 0),
  };
  const profitAttribution = summary?.attribution?.profit || [];
  const lossAttribution = summary?.attribution?.loss || [];
  const warnings = useMemo(() => {
    const out = [];
    (summary?.warnings || []).forEach((w) => {
      if (w && !out.includes(w)) out.push(w);
    });
    return out;
  }, [summary]);

  const closedWithTotalCount = Number(summary?.closed_with_total_count || 0);
  const winCount = Number(summary?.closed_win_count || 0);
  const winRate = summary?.closed_win_rate == null
    ? closedWithTotalCount > 0
      ? (winCount / closedWithTotalCount) * 100
      : 0
    : Number(summary.closed_win_rate) * 100;

  const columns = useMemo(() => buildStrategyColumns(), []);

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
      message.error(`export failed: ${getApiErrorMessage(e)}`);
    }
  };

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <span style={{ fontSize: 18, fontWeight: 700 }}>P&amp;L Analytics (v2)</span>
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
            <Button
              icon={<ReloadOutlined />}
              onClick={() => {
                void refreshAnalytics();
              }}
              loading={refreshing}
            >
              Refresh
            </Button>
            <Button icon={<SyncOutlined />} onClick={onSyncFunding} loading={syncing}>
              Sync Funding
            </Button>
            <Button icon={<DownloadOutlined />} onClick={onExportCsv}>
              Export CSV
            </Button>
          </Space>
        </Col>
      </Row>

      <SummaryMetaCard
        scope={scope}
        summary={summary}
        coveragePct={coveragePct}
        dailyReconcile={dailyReconcile}
        anomalyStrategyCount={anomalyStrategyCount}
      />
      <WarningsCard warnings={warnings} />

      <EquityCurveCard days={days} />

      <PnlOverviewRow summary={summary} />

      <QualityAndWinRateRow
        summary={summary}
        coveragePct={coveragePct}
        captured={captured}
        expected={expected}
        winCount={winCount}
        closedWithTotalCount={closedWithTotalCount}
        winRate={winRate}
        dailyReconcile={dailyReconcile}
      />

      <StatusOverviewRow statusOverview={statusOverview} />

      <AttributionTables
        profitRows={profitAttribution}
        lossRows={lossAttribution}
      />

      <Card
        size="small"
        title={(
          <Space>
            Strategy Rows
            <Tag color="blue">{totalCount}</Tag>
          </Space>
        )}
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
