import React, {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { Row, message } from 'antd';
import {
  getSpotBasisAutoConfig,
  getSpotBasisAutoStatus,
  resetSpotBasisDrawdownWatermark,
  runSpotBasisAutoCycleOnce,
  setSpotBasisAutoStatus,
  updateSpotBasisAutoConfig,
} from '../../services/endpoints/spotBasisApi';
import {
  useSpotBasisAutoActiveExchangesQuery,
  useSpotBasisAutoCycleLastQuery,
  useSpotBasisAutoCycleLogsQuery,
  useSpotBasisAutoDecisionPreviewQuery,
  useSpotBasisAutoExchangeFundsQuery,
  useSpotBasisAutoOpportunitiesQuery,
  useSpotBasisDrawdownWatermarkQuery,
} from '../../services/queries/spotBasisAutoQueries';
import { getApiErrorMessage } from '../../utils/error';
import { CFG_FIELD_META, DEFAULT_CFG } from './configMeta';
import ControlSidebar from './ControlSidebar';
import {
  createCycleLogColumns,
  createExchangeFundsColumns,
  createOpportunityColumns,
} from './columns';
import {
  fmtUsd,
  normalizeRow,
  num,
} from './helpers';
import OpportunitySection from './OpportunitySection';

export default function SpotBasisAuto() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState([]);
  const [cfg, setCfg] = useState(null);
  const [saving, setSaving] = useState(false);
  const [savingStatus, setSavingStatus] = useState(false);
  const [decisionPreview, setDecisionPreview] = useState(null);
  const [cycleLogs, setCycleLogs] = useState([]);
  const [cycleLogsClearTs, setCycleLogsClearTs] = useState(0);

  const clearCycleLogs = useCallback(() => {
    setCycleLogsClearTs(Date.now());
    setCycleLogs([]);
  }, []);
  const [cycleRunning, setCycleRunning] = useState(false);
  const [drawdownWatermarkResetting, setDrawdownWatermarkResetting] = useState(false);
  const [exchangeFundsRefreshing, setExchangeFundsRefreshing] = useState(false);

  const cycleLastQuery = useSpotBasisAutoCycleLastQuery();
  const cycleLogsQuery = useSpotBasisAutoCycleLogsQuery(160);
  const drawdownWatermarkQuery = useSpotBasisDrawdownWatermarkQuery();
  const exchangeFundsQuery = useSpotBasisAutoExchangeFundsQuery();

  const cycleLast = cycleLastQuery.data || null;
  const drawdownWatermark = drawdownWatermarkQuery.data || null;
  const drawdownWatermarkLoading = drawdownWatermarkQuery.isPending;
  const exchangeFunds = exchangeFundsQuery.data || [];
  const exchangeFundsLoading = exchangeFundsQuery.isPending || exchangeFundsRefreshing;

  const [filters, setFilters] = useState({
    symbol: '',
    min_rate: 0.01,
    min_perp_volume: 1000000,
    min_spot_volume: 1000000,
    min_basis_pct: 0,
    perp_exchange_ids: [],
    spot_exchange_ids: [],
    require_cross_exchange: false,
    action_mode: 'open',
    sort_by: 'score_strict',
  });

  const exchangesQuery = useSpotBasisAutoActiveExchangesQuery();
  const exchanges = exchangesQuery.data || [];

  const opportunitiesQuery = useSpotBasisAutoOpportunitiesQuery(filters, expanded.length === 0);
  const decisionPreviewQuery = useSpotBasisAutoDecisionPreviewQuery(filters);
  const decisionLoading = decisionPreviewQuery.isPending;
  const rowsLoading = opportunitiesQuery.isPending || loading;

  const exchangeOptions = useMemo(
    () => exchanges.map((x) => ({ label: x.display_name || x.name || `EX#${x.id}`, value: x.id })),
    [exchanges],
  );

  const loadCfg = useCallback(async () => {
    const [cfgRes, statusRes] = await Promise.allSettled([
      getSpotBasisAutoConfig(),
      getSpotBasisAutoStatus(),
    ]);

    const c = cfgRes.status === 'fulfilled' ? cfgRes.value?.data || {} : {};
    const s = statusRes.status === 'fulfilled' ? statusRes.value?.data || {} : {};

    const merged = {
      ...DEFAULT_CFG,
      ...(c || {}),
      is_enabled: typeof s?.enabled === 'boolean' ? !!s.enabled : !!c?.is_enabled,
      dry_run: typeof s?.dry_run === 'boolean' ? !!s.dry_run : !!c?.dry_run,
    };
    setCfg(merged);

    if (cfgRes.status === 'rejected' && statusRes.status === 'rejected') {
      throw cfgRes.reason || statusRes.reason || new Error('配置接口不可用');
    }
  }, []);

  const refreshRows = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const res = await opportunitiesQuery.refetch();
      if (res.data) setRows(res.data.map(normalizeRow));
      if (res.error && !silent) message.error(getApiErrorMessage(res.error, '机会列表加载失败'));
    } finally {
      if (!silent) setLoading(false);
    }
  }, [opportunitiesQuery]);

  const refreshDecisionPreview = useCallback(async (silent = false) => {
    const res = await decisionPreviewQuery.refetch();
    if (res.data) setDecisionPreview(res.data);
    if (res.error && !silent) {
      message.error(getApiErrorMessage(res.error, '决策预览加载失败'));
      setDecisionPreview(null);
    }
  }, [decisionPreviewQuery]);

  useEffect(() => {
    void loadCfg().catch((e) => message.error(getApiErrorMessage(e, '自动策略配置加载失败')));
  }, [loadCfg]);

  useEffect(() => {
    if (cycleLogsQuery.data) {
      const filtered = cycleLogsQuery.data.filter((log) => {
        const ts = num(log.ts, 0);
        const ms = ts < 1e11 ? ts * 1000 : ts;
        return ms >= cycleLogsClearTs;
      });
      setCycleLogs(filtered);
    }
  }, [cycleLogsQuery.data, cycleLogsClearTs]);

  useEffect(() => {
    if (opportunitiesQuery.data) setRows(opportunitiesQuery.data.map(normalizeRow));
  }, [opportunitiesQuery.data]);

  useEffect(() => {
    if (decisionPreviewQuery.data) setDecisionPreview(decisionPreviewQuery.data);
  }, [decisionPreviewQuery.data]);

  const stats = useMemo(() => {
    if (!rows.length) return { c: 0, e: 0, s: 0 };
    return {
      c: rows.length,
      e: rows.reduce((a, b) => a + num(b.e24_net_pct, 0), 0) / rows.length,
      s: Math.max(...rows.map((x) => num(x.score_model, 0))),
    };
  }, [rows]);

  const fundsSummary = useMemo(() => {
    const totalUsdt = exchangeFunds.reduce((acc, x) => acc + num(x.total_usdt, 0), 0);
    const currentNotional = exchangeFunds.reduce((acc, x) => acc + num(x.current_notional, 0), 0);
    const maxNotional = exchangeFunds.reduce((acc, x) => acc + num(x.max_notional, 0), 0);
    const usedPct = maxNotional > 0 ? (currentNotional / maxNotional) * 100 : 0;
    return { totalUsdt, currentNotional, maxNotional, usedPct };
  }, [exchangeFunds]);

  const setCfgField = useCallback((key, value) => {
    const meta = CFG_FIELD_META[key] || {};
    setCfg((prev) => {
      const base = prev || DEFAULT_CFG;
      const fallback = num(base?.[key], 0);
      let next = num(value, fallback);
      if (meta.int) next = Math.trunc(next);
      if (Number.isFinite(meta.min)) next = Math.max(meta.min, next);
      if (Number.isFinite(meta.max)) next = Math.min(meta.max, next);
      return { ...base, [key]: next };
    });
  }, []);

  const saveCfg = async () => {
    if (!cfg) return;
    setSaving(true);
    try {
      const payload = {};
      Object.keys(DEFAULT_CFG).forEach((k) => {
        if (cfg[k] !== undefined) payload[k] = cfg[k];
      });
      await updateSpotBasisAutoConfig(payload);
      await loadCfg();
      message.success('参数已保存');
    } finally {
      setSaving(false);
    }
  };

  const setStatus = async (enabled, dryRun) => {
    setSavingStatus(true);
    try {
      await setSpotBasisAutoStatus({ enabled, dry_run: dryRun });
      setCfg((p) => ({ ...(p || DEFAULT_CFG), is_enabled: enabled, dry_run: dryRun }));
      if (enabled) message.success('自动程序已启用');
    } catch (e) {
      message.error(getApiErrorMessage(e, '状态更新失败'));
      await loadCfg();
    } finally {
      setSavingStatus(false);
    }
  };

  const runCycleOnce = async () => {
    setCycleRunning(true);
    try {
      await runSpotBasisAutoCycleOnce();
      await Promise.all([
        refreshRows(true),
        refreshDecisionPreview(true),
        cycleLastQuery.refetch(),
        cycleLogsQuery.refetch(),
        drawdownWatermarkQuery.refetch(),
        exchangeFundsQuery.refetch(),
      ]);
      message.success('周期执行完成');
    } catch (e) {
      message.error(getApiErrorMessage(e, '操作失败'));
    } finally {
      setCycleRunning(false);
    }
  };

  const resetDrawdownWatermark = async () => {
    setDrawdownWatermarkResetting(true);
    try {
      const { data } = await resetSpotBasisDrawdownWatermark();
      await Promise.all([drawdownWatermarkQuery.refetch(), cycleLastQuery.refetch()]);
      message.success(`高水位已重置到 ${fmtUsd(num(data?.peak_nav_usdt, 0), 2)}`);
    } catch (e) {
      message.error(getApiErrorMessage(e, '重置高水位失败'));
    } finally {
      setDrawdownWatermarkResetting(false);
    }
  };

  const refreshExchangeFunds = async () => {
    setExchangeFundsRefreshing(true);
    try {
      const res = await exchangeFundsQuery.refetch();
      if (res.error) message.error(getApiErrorMessage(res.error, '交易所资金加载失败'));
    } finally {
      setExchangeFundsRefreshing(false);
    }
  };

  const refreshCycleLogs = async () => {
    const res = await cycleLogsQuery.refetch();
    if (res.error) message.error(getApiErrorMessage(res.error, '日志加载失败'));
  };

  const columns = useMemo(() => createOpportunityColumns(), []);
  const exchangeFundsColumns = useMemo(() => createExchangeFundsColumns(), []);
  const cycleLogColumns = useMemo(() => createCycleLogColumns(), []);

  return (
    <div className="kinetic-spot-basis-auto-root">
      <OpportunitySection
        filters={filters}
        setFilters={setFilters}
        exchangeOptions={exchangeOptions}
        rows={rows}
        rowsLoading={rowsLoading}
        refreshRows={refreshRows}
        stats={stats}
        expanded={expanded}
        setExpanded={setExpanded}
        columns={columns}
      />

      <ControlSidebar
        cfg={cfg}
        savingStatus={savingStatus}
        setStatus={setStatus}
        setCfg={setCfg}
        drawdownWatermarkLoading={drawdownWatermarkLoading}
        drawdownWatermark={drawdownWatermark}
        drawdownWatermarkResetting={drawdownWatermarkResetting}
        resetDrawdownWatermark={resetDrawdownWatermark}
        setCfgField={setCfgField}
        saveCfg={saveCfg}
        saving={saving}
        runCycleOnce={runCycleOnce}
        cycleRunning={cycleRunning}
        exchangeFundsLoading={exchangeFundsLoading}
        refreshExchangeFunds={refreshExchangeFunds}
        fundsSummary={fundsSummary}
        exchangeFunds={exchangeFunds}
        exchangeFundsColumns={exchangeFundsColumns}
        cycleLast={cycleLast}
        refreshCycleLogs={refreshCycleLogs}
        clearCycleLogs={clearCycleLogs}
        cycleLogs={cycleLogs}
        cycleLogColumns={cycleLogColumns}
        decisionLoading={decisionLoading}
        decisionPreview={decisionPreview}
      />
    </div>
  );
}
