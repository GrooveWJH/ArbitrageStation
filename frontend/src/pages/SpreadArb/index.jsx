import React, {
  useCallback,
  useMemo,
  useState,
} from 'react';
import {
  Alert,
  Badge,
  Button,
  Card,
  Col,
  Space,
  Switch,
  Tabs,
  Tag,
  Table,
  Tooltip,
  Row,
} from 'antd';
import {
  ReloadOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  closeSpreadPosition,
  setupHedgeMode,
  updateSpreadArbConfig,
} from '../../services/endpoints/spreadArbApi';
import {
  useSpreadArbConfigQuery,
  useSpreadArbHistoryPositionsQuery,
  useSpreadArbMarginStatusQuery,
  useSpreadArbOpenPositionsQuery,
  useSpreadArbStatsQuery,
} from '../../services/queries/spreadArbQueries';
import ConfigPanel from './ConfigPanel';
import { buildHistoryColumns, buildOpenColumns } from './columns';
import HedgeSetupModal from './HedgeSetupModal';
import MarginCards from './MarginCards';
import StatsCards from './StatsCards';

export default function SpreadArb() {
  const queryClient = useQueryClient();
  const statsQuery = useSpreadArbStatsQuery();
  const cfgQuery = useSpreadArbConfigQuery();
  const openPositionsQuery = useSpreadArbOpenPositionsQuery();
  const historyPositionsQuery = useSpreadArbHistoryPositionsQuery();
  const marginStatusQuery = useSpreadArbMarginStatusQuery();

  const stats = statsQuery.data || null;
  const cfg = cfgQuery.data || null;
  const positions = openPositionsQuery.data?.positions || [];
  const history = historyPositionsQuery.data?.positions || [];
  const marginData = marginStatusQuery.data || [];

  const isMainInitialLoading = [
    statsQuery,
    cfgQuery,
    openPositionsQuery,
    historyPositionsQuery,
  ].some((q) => q.isLoading && !q.isFetched);
  const isMainFetching = [
    statsQuery,
    cfgQuery,
    openPositionsQuery,
    historyPositionsQuery,
  ].some((q) => q.isFetching);

  const [saving, setSaving] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [hedgeModal, setHedgeModal] = useState(null);
  const [hedgeLoading, setHedgeLoading] = useState(false);
  const updateConfigMutation = useMutation({
    mutationFn: updateSpreadArbConfig,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['spread-arb'] });
    },
  });
  const closePositionMutation = useMutation({
    mutationFn: closeSpreadPosition,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['spread-arb'] });
    },
  });
  const setupHedgeMutation = useMutation({
    mutationFn: setupHedgeMode,
  });

  const refreshMain = useCallback(async () => {
    await Promise.all([
      statsQuery.refetch(),
      cfgQuery.refetch(),
      openPositionsQuery.refetch(),
      historyPositionsQuery.refetch(),
    ]);
  }, [statsQuery, cfgQuery, openPositionsQuery, historyPositionsQuery]);

  const handleRefresh = useCallback(async () => {
    await Promise.all([refreshMain(), marginStatusQuery.refetch()]);
  }, [refreshMain, marginStatusQuery]);

  const handleToggle = async (enabled) => {
    setToggling(true);
    try {
      await updateConfigMutation.mutateAsync({ spread_arb_enabled: enabled });
      await refreshMain();
    } finally {
      setToggling(false);
    }
  };

  const handleSaveCfg = async (newCfg) => {
    setSaving(true);
    try {
      await updateConfigMutation.mutateAsync(newCfg);
      await refreshMain();
    } finally {
      setSaving(false);
    }
  };

  const handleClose = async (id) => {
    await closePositionMutation.mutateAsync(id);
    await refreshMain();
  };

  const handleSetupHedge = async () => {
    setHedgeLoading(true);
    setHedgeModal({ results: null, loading: true });
    try {
      const res = await setupHedgeMutation.mutateAsync();
      setHedgeModal({ results: res.data.results || {}, loading: false });
    } catch (e) {
      setHedgeModal({ results: {}, loading: false, error: '请求失败，请检查交易所连接' });
    } finally {
      setHedgeLoading(false);
    }
  };

  const enabled = stats?.enabled ?? false;
  const totalActive = stats?.total_active ?? 0;
  const maxTotal = stats?.max_open_strategies ?? (cfg?.max_open_strategies ?? 5);
  const fundingCnt = stats?.funding_count ?? 0;
  const spreadCnt = stats?.open_count ?? 0;
  const usedPct = maxTotal > 0 ? Math.round((totalActive / maxTotal) * 100) : 0;

  const openCols = useMemo(() => buildOpenColumns({ cfg, handleClose }), [cfg]);
  const histCols = useMemo(() => buildHistoryColumns(), []);

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Space size={16}>
            <span style={{ fontSize: 18, fontWeight: 700 }}>价差套利</span>
            <Space>
              <span style={{ color: '#888', fontSize: 13 }}>自动交易</span>
              <Switch
                checked={enabled}
                loading={toggling}
                onChange={handleToggle}
                checkedChildren="开启"
                unCheckedChildren="关闭"
              />
            </Space>
            {enabled && (
              <Badge status="processing" text={<span style={{ color: '#1677ff', fontSize: 12 }}>运行中（每30秒扫描）</span>} />
            )}
          </Space>
        </Col>
        <Col>
          <Space>
            <Tooltip title="在所有已连接交易所上开启双向持仓模式（开始交易前必须执行）">
              <Button icon={<ThunderboltOutlined />} onClick={handleSetupHedge} loading={hedgeLoading}>
                初始化对冲模式
              </Button>
            </Tooltip>
            <Button
              icon={<ReloadOutlined />}
              onClick={() => {
                void handleRefresh();
              }}
              loading={isMainFetching || marginStatusQuery.isFetching}
            >
              刷新
            </Button>
          </Space>
        </Col>
      </Row>

      {!enabled && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="价差套利自动交易未开启"
          description="开启前请先点击「初始化对冲模式」按钮，确保所有交易所已开启双向持仓模式，再开启自动交易。"
        />
      )}

      <StatsCards
        stats={stats}
        totalActive={totalActive}
        maxTotal={maxTotal}
        fundingCnt={fundingCnt}
        spreadCnt={spreadCnt}
        usedPct={usedPct}
      />

      <MarginCards items={marginData} />

      <ConfigPanel cfg={cfg} onSave={handleSaveCfg} saving={saving} />

      <Card size="small" bodyStyle={{ padding: 0 }}>
        <Tabs
          defaultActiveKey="open"
          style={{ padding: '0 16px' }}
          items={[
            {
              key: 'open',
              label: (
                <span>
                  持仓中
                  {positions.length > 0 && (
                    <Tag color="blue" style={{ marginLeft: 6, fontSize: 11 }}>{positions.length}</Tag>
                  )}
                </span>
              ),
              children: (
                <Table
                  rowKey="id"
                  dataSource={positions}
                  columns={openCols}
                  loading={isMainInitialLoading}
                  pagination={false}
                  size="small"
                  scroll={{ x: 900 }}
                  locale={{ emptyText: '暂无持仓，价差机会出现时将自动开仓' }}
                  rowClassName={(row) => ((row.unrealized_pnl_usd ?? 0) >= 0 ? 'win-row' : 'loss-row')}
                />
              ),
            },
            {
              key: 'history',
              label: `历史记录 (${history.length})`,
              children: (
                <Table
                  rowKey="id"
                  dataSource={history}
                  columns={histCols}
                  loading={isMainInitialLoading}
                  pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 条` }}
                  size="small"
                  scroll={{ x: 900 }}
                  rowClassName={(row) => ((row.realized_pnl_usd ?? 0) >= 0 ? 'win-row' : 'loss-row')}
                />
              ),
            },
          ]}
        />
      </Card>

      <HedgeSetupModal
        hedgeModal={hedgeModal}
        onClose={() => setHedgeModal(null)}
      />

      <style>{`
        .win-row td  { background: #f6ffed !important; }
        .loss-row td { background: #fff1f0 !important; }
      `}</style>
    </div>
  );
}
