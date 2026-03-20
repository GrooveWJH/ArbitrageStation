import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Input,
  InputNumber,
  Modal,
  Progress,
  Row,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import { LineChartOutlined, PlayCircleOutlined, ReloadOutlined, SearchOutlined, UploadOutlined } from '@ant-design/icons';
import {
  createSpotBasisDataBacktestJob,
  createSpotBasisDataBacktestSearchJob,
  getSpotBasisBacktestReadiness,
  getSpotBasisDataAvailableRange,
  importSpotBasisFunding,
  importSpotBasisSnapshots,
} from '../../services/endpoints/spotBasisDataApi';
import {
  getSpotBasisAutoConfig,
  setSpotBasisAutoStatus,
  updateSpotBasisAutoConfig,
} from '../../services/endpoints/spotBasisApi';
import { useSpotBasisDataJobQuery } from '../../services/queries/spotBasisBacktestQueries';
import { getApiErrorMessage } from '../../utils/error';

const { Title, Text } = Typography;

const num = (v, d = 0) => {
  const x = Number(v);
  return Number.isFinite(x) ? x : d;
};

const parseNumberList = (raw, asInt = false) => {
  const text = String(raw ?? '').trim();
  if (!text) return [];
  const out = text
    .split(/[\s,，;；]+/)
    .map((x) => Number(x))
    .filter((x) => Number.isFinite(x));
  if (!out.length) return [];
  if (asInt) {
    return [...new Set(out.map((x) => Math.trunc(x)))];
  }
  return [...new Set(out.map((x) => Number(x.toFixed(8))))];
};

const AUTO_CFG_FIELD_LABELS = {
  enter_score_threshold: '入场评分阈值',
  entry_conf_min: '入场置信度下限',
  max_open_pairs: '最大持仓对数',
  target_utilization_pct: '目标资金利用率(%)',
  min_pair_notional_usd: '单对最小本金(USDT)',
  max_impact_pct: '最大冲击成本(%)',
  switch_confirm_rounds: '换仓确认轮数',
  rebalance_min_relative_adv_pct: '换仓相对增益门槛(%)',
  rebalance_min_absolute_adv_usd_day: '换仓绝对增益门槛(USDT/天)',
  hold_conf_min: '持有置信度下限',
  switch_min_advantage: '换仓最小优势(%)',
  max_exchange_utilization_pct: '单交易所利用率上限(%)',
  max_symbol_utilization_pct: '单币种利用率上限(%)',
  min_capacity_pct: '容量下限(%)',
  portfolio_dd_hard_pct: '组合硬回撤阈值(%)',
};

const READINESS_REASON_LABELS = {
  universe_empty: '候选池为空',
  universe_missing_dates: '部分日期缺少机会池',
  snapshot_empty: '15m快照为空',
  snapshot_coverage_low: '15m快照覆盖率偏低',
  previous_run_deadband_blocked: '上次回测被死区阈值阻断',
  previous_run_universe_empty: '上次回测因候选池为空未执行',
};

const DELTA_REASON_LABELS = {
  adv_below_abs_deadband: '绝对增益未达阈值',
  adv_below_rel_deadband: '相对增益未达阈值',
  no_delta_plan: '当前无调仓差额',
};

const IMPORT_JOB_TYPE_LABELS = {
  import_snapshots: '快照导入',
  import_funding: 'Funding导入',
};

const fmtReasonCodes = (codes) => {
  if (!Array.isArray(codes) || !codes.length) return '无';
  return codes.map((x) => READINESS_REASON_LABELS[x] || String(x)).join('、');
};

const isSameValue = (a, b) => {
  const na = Number(a);
  const nb = Number(b);
  if (Number.isFinite(na) && Number.isFinite(nb)) {
    return Math.abs(na - nb) < 1e-10;
  }
  return String(a ?? '') === String(b ?? '');
};

const fmtPreviewValue = (v) => {
  if (v == null) return '--';
  const n = Number(v);
  if (Number.isFinite(n)) {
    if (Math.abs(n - Math.trunc(n)) < 1e-10) return String(Math.trunc(n));
    return n.toFixed(6).replace(/0+$/g, '').replace(/\.$/, '');
  }
  return String(v);
};

const defaultParams = {
  days: 15,
  top_n: 120,
  initial_nav_usd: 10000,
  min_rate_pct: 0.01,
  min_perp_volume: 1000000,
  min_spot_volume: 1000000,
  min_basis_pct: 0,
  require_cross_exchange: false,
  enter_score_threshold: 0,
  entry_conf_min: 0.55,
  hold_conf_min: 0.45,
  max_open_pairs: 5,
  target_utilization_pct: 60,
  min_pair_notional_usd: 300,
  max_exchange_utilization_pct: 35,
  max_symbol_utilization_pct: 10,
  min_capacity_pct: 12,
  max_impact_pct: 0.3,
  switch_min_advantage: 5,
  switch_confirm_rounds: 3,
  rebalance_min_relative_adv_pct: 5,
  rebalance_min_absolute_adv_usd_day: 0.5,
  portfolio_dd_hard_pct: -4,
  data_stale_max_buckets: 3,
};

const defaultSearchParams = {
  days: 30,
  top_n: 120,
  initial_nav_usd: 10000,
  min_rate_pct: 0.01,
  min_perp_volume: 1000000,
  min_spot_volume: 1000000,
  min_basis_pct: 0,
  require_cross_exchange: false,
  hold_conf_min: 0.45,
  max_exchange_utilization_pct: 35,
  max_symbol_utilization_pct: 10,
  min_capacity_pct: 12,
  switch_min_advantage: 5,
  portfolio_dd_hard_pct: -4,
  data_stale_max_buckets: 3,
  train_days: 7,
  test_days: 3,
  step_days: 3,
  train_top_k: 3,
  max_trials: 24,
  random_seed: 42,
  enter_score_threshold_values: '0,5,10,15',
  entry_conf_min_values: '0.5,0.55,0.6',
  max_open_pairs_values: '3,5,7',
  target_utilization_pct_values: '50,60,70',
  min_pair_notional_usd_values: '200,300,500',
  max_impact_pct_values: '0.2,0.3,0.4',
  switch_confirm_rounds_values: '2,3,4',
  rebalance_min_relative_adv_pct_values: '3,5,8',
  rebalance_min_absolute_adv_usd_day_values: '0.3,0.5,1.0',
};

const statusTag = (status) => {
  const s = String(status || '').toLowerCase();
  if (s === 'succeeded') return <Tag color="success">已完成</Tag>;
  if (s === 'failed') return <Tag color="error">失败</Tag>;
  if (s === 'running') return <Tag color="processing">运行中</Tag>;
  if (s === 'pending') return <Tag color="default">排队中</Tag>;
  return <Tag>未知</Tag>;
};

function EquityCurveChart({ rows }) {
  const hostRef = useRef(null);
  const [width, setWidth] = useState(960);

  useEffect(() => {
    if (!hostRef.current) return undefined;
    const ro = new ResizeObserver(() => {
      const next = Math.floor(hostRef.current?.clientWidth || 960);
      setWidth((prev) => (Math.abs(prev - next) > 1 ? next : prev));
    });
    ro.observe(hostRef.current);
    return () => ro.disconnect();
  }, []);

  if (!rows?.length) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无权益曲线" />;
  }

  const data = rows.map((x) => num(x.equity_usd, NaN));
  const clean = data.filter((x) => Number.isFinite(x));
  if (!clean.length) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无有效权益数据" />;
  }

  const minV = Math.min(...clean);
  const maxV = Math.max(...clean);
  const span = Math.max(1e-9, maxV - minV);
  const pad = span * 0.12;
  const lo = minV - pad;
  const hi = maxV + pad;

  const PAD = { left: 58, right: 20, top: 12, bottom: 30 };
  const H = 260;
  const innerW = Math.max(20, width - PAD.left - PAD.right);
  const innerH = H - PAD.top - PAD.bottom;

  const toX = (i) => PAD.left + (innerW * i) / Math.max(1, data.length - 1);
  const toY = (v) => PAD.top + innerH * (1 - (v - lo) / Math.max(1e-9, hi - lo));

  let d = '';
  let open = false;
  data.forEach((v, i) => {
    if (!Number.isFinite(v)) {
      open = false;
      return;
    }
    d += `${open ? 'L' : 'M'} ${toX(i)} ${toY(v)} `;
    open = true;
  });

  const ticks = [0, 0.25, 0.5, 0.75, 1].map((p) => lo + (hi - lo) * p);

  return (
    <div ref={hostRef} style={{ width: '100%' }}>
      <svg width={width} height={H}>
        {ticks.map((v) => (
          <line
            key={`g-${v}`}
            x1={PAD.left}
            x2={PAD.left + innerW}
            y1={toY(v)}
            y2={toY(v)}
            stroke="#e2e8f0"
            strokeDasharray="3 3"
          />
        ))}

        <line x1={PAD.left} x2={PAD.left} y1={PAD.top} y2={PAD.top + innerH} stroke="#cbd5e1" />
        <line x1={PAD.left} x2={PAD.left + innerW} y1={PAD.top + innerH} y2={PAD.top + innerH} stroke="#cbd5e1" />
        <path d={d.trim()} fill="none" stroke="#1677ff" strokeWidth="2" />

        {ticks.map((v) => (
          <text key={`t-${v}`} x={PAD.left - 8} y={toY(v) + 4} textAnchor="end" fontSize={11} fill="#64748b">
            {v.toFixed(2)}
          </text>
        ))}

        <text x={PAD.left} y={H - 8} fill="#64748b" fontSize={11}>开始</text>
        <text x={PAD.left + innerW} y={H - 8} fill="#64748b" fontSize={11} textAnchor="end">结束</text>
      </svg>
    </div>
  );
}

export default function SpotBasisBacktest() {
  const [params, setParams] = useState(defaultParams);
  const [jobId, setJobId] = useState(null);
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(false);
  const [readiness, setReadiness] = useState(null);
  const [readinessLoading, setReadinessLoading] = useState(false);
  const [importJobId, setImportJobId] = useState(null);
  const [importJob, setImportJob] = useState(null);
  const [importLoading, setImportLoading] = useState(false);
  const [importPath, setImportPath] = useState('');
  const [fundingImportPath, setFundingImportPath] = useState('');
  const [availableRangeLoading, setAvailableRangeLoading] = useState(false);
  const [availableRange, setAvailableRange] = useState(null);

  const [searchParams, setSearchParams] = useState(defaultSearchParams);
  const [searchJobId, setSearchJobId] = useState(null);
  const [searchJob, setSearchJob] = useState(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [applyAutoLoading, setApplyAutoLoading] = useState(false);
  const [applyAutoAndStartLoading, setApplyAutoAndStartLoading] = useState(false);
  const [autoDiffVisible, setAutoDiffVisible] = useState(false);
  const [autoDiffLoading, setAutoDiffLoading] = useState(false);
  const [autoDiffStartAfterApply, setAutoDiffStartAfterApply] = useState(false);
  const [autoDiffCurrentCfg, setAutoDiffCurrentCfg] = useState(null);
  const [autoDiffPatch, setAutoDiffPatch] = useState(null);

  const result = useMemo(() => job?.result || {}, [job]);
  const summary = result?.summary || {};
  const curve = result?.equity_curve || [];
  const events = result?.events || [];

  const searchResult = useMemo(() => searchJob?.result || {}, [searchJob]);
  const searchSummary = searchResult?.summary || {};
  const recommended = searchResult?.recommended || null;
  const leaderboard = searchResult?.leaderboard || [];
  const windows = searchResult?.windows || [];
  const autoDiffRows = useMemo(() => {
    const patch = autoDiffPatch || {};
    const current = autoDiffCurrentCfg || {};
    return Object.keys(patch).map((key) => {
      const before = current[key];
      const after = patch[key];
      return {
        key,
        label: AUTO_CFG_FIELD_LABELS[key] || key,
        before,
        after,
        changed: !isSameValue(before, after),
      };
    });
  }, [autoDiffCurrentCfg, autoDiffPatch]);

  const backtestJobQuery = useSpotBasisDataJobQuery(jobId, Boolean(jobId));
  const importJobQuery = useSpotBasisDataJobQuery(importJobId, Boolean(importJobId));
  const searchJobQuery = useSpotBasisDataJobQuery(searchJobId, Boolean(searchJobId));

  useEffect(() => {
    if (backtestJobQuery.data) {
      setJob(backtestJobQuery.data);
    }
  }, [backtestJobQuery.data]);

  useEffect(() => {
    if (importJobQuery.data) {
      setImportJob(importJobQuery.data);
    }
  }, [importJobQuery.data]);

  useEffect(() => {
    if (searchJobQuery.data) {
      setSearchJob(searchJobQuery.data);
    }
  }, [searchJobQuery.data]);

  useEffect(() => {
    const status = String(importJob?.status || '').toLowerCase();
    if ((status === 'succeeded' || status === 'failed') && importJob?.id && importJob.id === importJobId) {
      void checkReadiness(true);
    }
  }, [importJob?.status, importJob?.id, importJobId]);

  const buildReadinessParams = () => ({
    start_date: params.start_date || undefined,
    end_date: params.end_date || undefined,
    days: Math.max(1, Math.trunc(num(params.days, 15))),
    top_n: Math.max(1, Math.trunc(num(params.top_n, 120))),
  });

  const checkReadiness = async (silent = false) => {
    setReadinessLoading(true);
    try {
      const { data } = await getSpotBasisBacktestReadiness(buildReadinessParams());
      const next = data?.result || null;
      setReadiness(next);
      return next;
    } catch (e) {
      if (!silent) {
        message.error(getApiErrorMessage(e, '读取回测覆盖检查失败'));
      }
      return null;
    } finally {
      setReadinessLoading(false);
    }
  };

  const startPathImport = async (kind = 'snapshots') => {
    const isFunding = String(kind || '').toLowerCase() === 'funding';
    const p = String(isFunding ? fundingImportPath : importPath || '').trim();
    if (!p) {
      message.warning('请先输入本地文件路径');
      return;
    }
    setImportLoading(true);
    try {
      const name = p.split('\\').pop().split('/').pop();
      const ext = name.includes('.') ? name.split('.').pop().toLowerCase() : '';
      const fmt = ext === 'parquet' ? 'parquet' : 'csv';
      const importer = isFunding ? importSpotBasisFunding : importSpotBasisSnapshots;
      const { data } = await importer({
        file_path: p,
        file_format: fmt,
      });
      const j = data?.job;
      if (!j?.id) throw new Error('导入任务创建失败');
      setImportJobId(j.id);
      setImportJob(j);
      message.success(`${isFunding ? 'Funding历史' : '快照'}导入任务已启动 #${j.id}`);
    } catch (e) {
      message.error(getApiErrorMessage(e, `启动${isFunding ? 'Funding历史' : '快照'}导入失败`));
    } finally {
      setImportLoading(false);
    }
  };

  const startSnapshotImport = () => startPathImport('snapshots');
  const startFundingImport = () => startPathImport('funding');

  const fillAvailableDates = async () => {
    setAvailableRangeLoading(true);
    try {
      const preferredDays = Math.max(1, Math.trunc(num(params.days, 15)));
      const { data } = await getSpotBasisDataAvailableRange({ preferred_days: preferredDays });
      const next = data?.result || null;
      setAvailableRange(next);
      const start = next?.recommended_start_date;
      const end = next?.recommended_end_date;
      if (!start || !end) {
        message.warning('当前暂无可用的连续日期区间，请先导入 funding 与 15m 快照');
        return;
      }
      setParams((p) => ({ ...p, start_date: start, end_date: end }));
      message.success(`已自动填充回测日期: ${start} ~ ${end}`);
      setReadiness(null);
    } catch (e) {
      message.error(getApiErrorMessage(e, '读取可用日期范围失败'));
    } finally {
      setAvailableRangeLoading(false);
    }
  };

  const startBacktest = async () => {
    setLoading(true);
    try {
      const rd = await checkReadiness(true);
      if (rd && rd.ready === false) {
        const reasonText = fmtReasonCodes(rd.reason_codes);
        message.error(`回测前检查未通过：${reasonText}`);
        return;
      }
      if (rd && Array.isArray(rd.reason_codes) && rd.reason_codes.includes('snapshot_coverage_low')) {
        message.warning('回测数据覆盖偏低，结果可能不稳定');
      }
      const { data } = await createSpotBasisDataBacktestJob(params);
      const j = data?.job;
      if (!j?.id) throw new Error('任务创建失败');
      setJobId(j.id);
      setJob(j);
      message.success(`回测任务已启动 #${j.id}`);
    } catch (e) {
      message.error(getApiErrorMessage(e, '启动回测失败'));
    } finally {
      setLoading(false);
    }
  };

  const buildSearchPayload = () => ({
    start_date: searchParams.start_date,
    end_date: searchParams.end_date,
    days: searchParams.days,
    top_n: searchParams.top_n,
    initial_nav_usd: searchParams.initial_nav_usd,
    min_rate_pct: searchParams.min_rate_pct,
    min_perp_volume: searchParams.min_perp_volume,
    min_spot_volume: searchParams.min_spot_volume,
    min_basis_pct: searchParams.min_basis_pct,
    require_cross_exchange: !!searchParams.require_cross_exchange,
    hold_conf_min: searchParams.hold_conf_min,
    max_exchange_utilization_pct: searchParams.max_exchange_utilization_pct,
    max_symbol_utilization_pct: searchParams.max_symbol_utilization_pct,
    min_capacity_pct: searchParams.min_capacity_pct,
    switch_min_advantage: searchParams.switch_min_advantage,
    portfolio_dd_hard_pct: searchParams.portfolio_dd_hard_pct,
    data_stale_max_buckets: searchParams.data_stale_max_buckets,
    train_days: searchParams.train_days,
    test_days: searchParams.test_days,
    step_days: searchParams.step_days,
    train_top_k: searchParams.train_top_k,
    max_trials: searchParams.max_trials,
    random_seed: searchParams.random_seed,
    enter_score_threshold_values: parseNumberList(searchParams.enter_score_threshold_values, false),
    entry_conf_min_values: parseNumberList(searchParams.entry_conf_min_values, false),
    max_open_pairs_values: parseNumberList(searchParams.max_open_pairs_values, true),
    target_utilization_pct_values: parseNumberList(searchParams.target_utilization_pct_values, false),
    min_pair_notional_usd_values: parseNumberList(searchParams.min_pair_notional_usd_values, false),
    max_impact_pct_values: parseNumberList(searchParams.max_impact_pct_values, false),
    switch_confirm_rounds_values: parseNumberList(searchParams.switch_confirm_rounds_values, true),
    rebalance_min_relative_adv_pct_values: parseNumberList(searchParams.rebalance_min_relative_adv_pct_values, false),
    rebalance_min_absolute_adv_usd_day_values: parseNumberList(searchParams.rebalance_min_absolute_adv_usd_day_values, false),
  });

  const startSearch = async () => {
    setSearchLoading(true);
    try {
      const payload = buildSearchPayload();
      const { data } = await createSpotBasisDataBacktestSearchJob(payload);
      const j = data?.job;
      if (!j?.id) throw new Error('参数搜索任务创建失败');
      setSearchJobId(j.id);
      setSearchJob(j);
      message.success(`参数搜索任务已启动 #${j.id}`);
    } catch (e) {
      message.error(getApiErrorMessage(e, '启动参数搜索失败'));
    } finally {
      setSearchLoading(false);
    }
  };

  const refreshBacktestJob = async () => {
    if (!jobId) return;
    const res = await backtestJobQuery.refetch();
    if (res.error) {
      message.error(getApiErrorMessage(res.error, '读取任务失败'));
    }
  };

  const refreshSearchJob = async () => {
    if (!searchJobId) return;
    const res = await searchJobQuery.refetch();
    if (res.error) {
      message.error(getApiErrorMessage(res.error, '读取搜索任务失败'));
    }
  };

  const applyRecommendedToBacktest = () => {
    const rec = recommended?.params;
    if (!rec) {
      message.warning('暂无可应用的推荐参数');
      return;
    }
    setParams((p) => ({ ...p, ...rec }));
    message.success('已将推荐参数写入回测参数');
  };

  const buildAutoConfigPatchFromRecommended = () => {
    const rec = recommended?.params;
    if (!rec) return null;
    return {
      enter_score_threshold: num(rec.enter_score_threshold, 0),
      entry_conf_min: num(rec.entry_conf_min, 0.55),
      max_open_pairs: Math.max(1, Math.trunc(num(rec.max_open_pairs, 5))),
      target_utilization_pct: Math.max(1, num(rec.target_utilization_pct, 60)),
      min_pair_notional_usd: Math.max(1, num(rec.min_pair_notional_usd, 300)),
      max_impact_pct: Math.max(0.01, num(rec.max_impact_pct, 0.3)),
      switch_confirm_rounds: Math.max(1, Math.trunc(num(rec.switch_confirm_rounds, 3))),
      rebalance_min_relative_adv_pct: Math.max(0, num(rec.rebalance_min_relative_adv_pct, 5)),
      rebalance_min_absolute_adv_usd_day: Math.max(0, num(rec.rebalance_min_absolute_adv_usd_day, 0.5)),
      hold_conf_min: Math.max(0, Math.min(1, num(searchParams.hold_conf_min, 0.45))),
      switch_min_advantage: Math.max(0, num(searchParams.switch_min_advantage, 5)),
      max_exchange_utilization_pct: Math.max(1, num(searchParams.max_exchange_utilization_pct, 35)),
      max_symbol_utilization_pct: Math.max(1, num(searchParams.max_symbol_utilization_pct, 10)),
      min_capacity_pct: Math.max(0, num(searchParams.min_capacity_pct, 12)),
      portfolio_dd_hard_pct: num(searchParams.portfolio_dd_hard_pct, -4),
    };
  };

  const applyRecommendedToAuto = async (startAfterApply = false, patchOverride = null) => {
    const patch = patchOverride || buildAutoConfigPatchFromRecommended();
    if (!patch) {
      message.warning('暂无可应用的推荐参数');
      return false;
    }
    if (startAfterApply) {
      setApplyAutoAndStartLoading(true);
    } else {
      setApplyAutoLoading(true);
    }
    try {
      await updateSpotBasisAutoConfig(patch);
      if (startAfterApply) {
        await setSpotBasisAutoStatus({ enabled: true, dry_run: true });
        message.success('已应用推荐参数并开启自动策略（模拟模式）');
      } else {
        message.success('已应用推荐参数到自动策略配置');
      }
      return true;
    } catch (e) {
      message.error(getApiErrorMessage(e, '应用自动策略参数失败'));
      return false;
    } finally {
      if (startAfterApply) {
        setApplyAutoAndStartLoading(false);
      } else {
        setApplyAutoLoading(false);
      }
    }
  };

  const openAutoDiffPreview = async (startAfterApply = false) => {
    const patch = buildAutoConfigPatchFromRecommended();
    if (!patch) {
      message.warning('暂无可应用的推荐参数');
      return;
    }
    setAutoDiffLoading(true);
    try {
      const { data } = await getSpotBasisAutoConfig();
      setAutoDiffCurrentCfg(data || {});
      setAutoDiffPatch(patch);
      setAutoDiffStartAfterApply(!!startAfterApply);
      setAutoDiffVisible(true);
    } catch (e) {
      message.error(getApiErrorMessage(e, '读取当前自动策略配置失败'));
    } finally {
      setAutoDiffLoading(false);
    }
  };

  const confirmApplyFromDiff = async () => {
    if (!autoDiffPatch) return;
    const ok = await applyRecommendedToAuto(autoDiffStartAfterApply, autoDiffPatch);
    if (ok) {
      setAutoDiffVisible(false);
    }
  };

  const onNumber = (key, setter) => (value) => {
    setter((p) => ({ ...p, [key]: value == null ? p[key] : value }));
  };

  const eventCols = [
    {
      title: '时间',
      dataIndex: 'ts',
      width: 180,
      render: (v) => {
        if (!v) return '--';
        try {
          return new Date(v).toLocaleString('zh-CN');
        } catch {
          return v;
        }
      },
    },
    { title: '动作', dataIndex: 'action', width: 150 },
    { title: '交易对', dataIndex: 'symbol', width: 150, render: (v) => v || '--' },
    { title: '策略ID', dataIndex: 'strategy_id', width: 90, render: (v) => (v == null ? '--' : v) },
    { title: '名义本金', dataIndex: 'size_usd', width: 110, render: (v) => (v == null ? '--' : `$${num(v).toFixed(2)}`) },
    { title: '手续费', dataIndex: 'fee_usd', width: 100, render: (v) => (v == null ? '--' : `$${num(v).toFixed(4)}`) },
  ];

  const leaderboardCols = [
    { title: '参数组', dataIndex: 'combo_id', width: 90 },
    {
      title: '稳定评分',
      dataIndex: 'stability_score',
      width: 100,
      render: (v) => num(v).toFixed(4),
    },
    {
      title: '窗口数',
      dataIndex: 'windows_covered',
      width: 80,
      render: (v) => num(v, 0),
    },
    {
      title: '平均收益(%)',
      dataIndex: 'avg_test_return_pct',
      width: 110,
      render: (v) => num(v).toFixed(4),
    },
    {
      title: '收益波动(%)',
      dataIndex: 'std_test_return_pct',
      width: 110,
      render: (v) => num(v).toFixed(4),
    },
    {
      title: '平均回撤(%)',
      dataIndex: 'avg_test_drawdown_pct',
      width: 110,
      render: (v) => num(v).toFixed(4),
    },
    {
      title: '正收益窗口占比',
      dataIndex: 'positive_window_ratio',
      width: 120,
      render: (v) => `${(num(v) * 100).toFixed(1)}%`,
    },
    {
      title: '触发硬风控窗口',
      dataIndex: 'risk_halt_windows',
      width: 120,
      render: (v) => num(v, 0),
    },
    {
      title: '参数',
      dataIndex: 'params',
      render: (v) => (
        <Space size={[4, 4]} wrap>
          {Object.entries(v || {}).map(([k, x]) => (
            <Tag key={k}>{`${k}:${x}`}</Tag>
          ))}
        </Space>
      ),
    },
  ];

  const windowCols = [
    { title: '窗口', dataIndex: 'window_index', width: 80 },
    {
      title: '训练区间',
      key: 'train',
      width: 220,
      render: (_, r) => `${r.train_start || '--'} ~ ${r.train_end || '--'}`,
    },
    {
      title: '测试区间',
      key: 'test',
      width: 220,
      render: (_, r) => `${r.test_start || '--'} ~ ${r.test_end || '--'}`,
    },
    { title: '最佳参数组', dataIndex: 'best_test_combo_id', width: 100, render: (v) => v || '--' },
    {
      title: '最佳测试收益(%)',
      dataIndex: 'best_test_return_pct',
      width: 130,
      render: (v) => num(v).toFixed(4),
    },
    {
      title: '最佳测试回撤(%)',
      dataIndex: 'best_test_drawdown_pct',
      width: 130,
      render: (v) => num(v).toFixed(4),
    },
    {
      title: '入围参数组',
      dataIndex: 'selected_combo_ids',
      render: (v) => (Array.isArray(v) && v.length ? v.join(', ') : '--'),
    },
  ];

  const autoDiffCols = [
    { title: '参数', dataIndex: 'label', width: 260 },
    {
      title: '当前值',
      dataIndex: 'before',
      width: 170,
      render: (v) => fmtPreviewValue(v),
    },
    {
      title: '建议值',
      dataIndex: 'after',
      width: 170,
      render: (v) => fmtPreviewValue(v),
    },
    {
      title: '变化',
      dataIndex: 'changed',
      width: 90,
      render: (v) => (v ? <Tag color="processing">变更</Tag> : <Tag>不变</Tag>),
    },
  ];

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card>
        <Space align="center" style={{ width: '100%', justifyContent: 'space-between' }}>
          <Space>
            <LineChartOutlined style={{ color: '#1677ff' }} />
            <Title level={5} style={{ margin: 0 }}>现货-合约费率套利回测</Title>
          </Space>
          <Space>
            <Button
              icon={<ReloadOutlined />}
              disabled={!jobId}
              onClick={() => { void refreshBacktestJob(); }}
            >
              刷新任务
            </Button>
            <Button icon={<UploadOutlined />} loading={importLoading} onClick={startSnapshotImport}>
              导入本地快照
            </Button>
            <Button icon={<UploadOutlined />} loading={importLoading} onClick={startFundingImport}>
              导入Funding历史
            </Button>
            <Button loading={readinessLoading} onClick={() => checkReadiness(false)}>
              覆盖检查
            </Button>
            <Button loading={availableRangeLoading} onClick={fillAvailableDates}>
              自动填充日期
            </Button>
            <Button type="primary" loading={loading} icon={<PlayCircleOutlined />} onClick={startBacktest}>
              启动回测
            </Button>
          </Space>
        </Space>

        <Row gutter={[12, 12]} style={{ marginTop: 14 }}>
          <Col span={8}>
            <Text>离线快照文件路径(CSV/Parquet)</Text>
            <Input
              value={importPath}
              onChange={(e) => setImportPath(e.target.value)}
              placeholder="例如 C:\\data\\snapshots_15m_2026-02-27_2026-03-13.csv"
            />
          </Col>
          <Col span={8}>
            <Text>Funding历史文件路径(CSV/Parquet)</Text>
            <Input
              value={fundingImportPath}
              onChange={(e) => setFundingImportPath(e.target.value)}
              placeholder="例如 C:\\data\\funding_2026-02-27_2026-03-13.csv"
            />
          </Col>
          <Col span={4}>
            <Text>开始日期(YYYY-MM-DD)</Text>
            <Input value={params.start_date} onChange={(e) => setParams((p) => ({ ...p, start_date: e.target.value }))} placeholder="留空按 days" />
          </Col>
          <Col span={4}>
            <Text>结束日期(YYYY-MM-DD)</Text>
            <Input value={params.end_date} onChange={(e) => setParams((p) => ({ ...p, end_date: e.target.value }))} placeholder="留空为今天" />
          </Col>
          <Col span={4}><Text>回放天数</Text><InputNumber min={1} max={180} value={params.days} onChange={onNumber('days', setParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Text>每日机会池TopN</Text><InputNumber min={1} max={2000} value={params.top_n} onChange={onNumber('top_n', setParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Text>初始资金(USDT)</Text><InputNumber min={100} value={params.initial_nav_usd} onChange={onNumber('initial_nav_usd', setParams)} style={{ width: '100%' }} /></Col>

          <Col span={4}><Text>最小费率(%)</Text><InputNumber min={0} step={0.001} value={params.min_rate_pct} onChange={onNumber('min_rate_pct', setParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Text>最小合约量</Text><InputNumber min={0} value={params.min_perp_volume} onChange={onNumber('min_perp_volume', setParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Text>最小现货量</Text><InputNumber min={0} value={params.min_spot_volume} onChange={onNumber('min_spot_volume', setParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Text>最小基差(%)</Text><InputNumber step={0.001} value={params.min_basis_pct} onChange={onNumber('min_basis_pct', setParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Text>最大持仓对数</Text><InputNumber min={1} max={50} value={params.max_open_pairs} onChange={onNumber('max_open_pairs', setParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Text>目标利用率(%)</Text><InputNumber min={1} max={95} value={params.target_utilization_pct} onChange={onNumber('target_utilization_pct', setParams)} style={{ width: '100%' }} /></Col>

          <Col span={4}><Text>入场置信度下限</Text><InputNumber min={0} max={1} step={0.01} value={params.entry_conf_min} onChange={onNumber('entry_conf_min', setParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Text>换仓确认轮数</Text><InputNumber min={1} max={20} value={params.switch_confirm_rounds} onChange={onNumber('switch_confirm_rounds', setParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Text>最小单对本金</Text><InputNumber min={1} value={params.min_pair_notional_usd} onChange={onNumber('min_pair_notional_usd', setParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Text>硬回撤阈值(%)</Text><InputNumber max={0} step={0.1} value={params.portfolio_dd_hard_pct} onChange={onNumber('portfolio_dd_hard_pct', setParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Text>数据陈旧桶数</Text><InputNumber min={0} max={50} value={params.data_stale_max_buckets} onChange={onNumber('data_stale_max_buckets', setParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Text>最大冲击(%)</Text><InputNumber min={0.01} max={10} step={0.01} value={params.max_impact_pct} onChange={onNumber('max_impact_pct', setParams)} style={{ width: '100%' }} /></Col>
        </Row>
      </Card>

      <Card>
        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <Text strong>回测前数据覆盖检查</Text>
          <Text type="secondary">
            范围: {readiness?.start_date || '--'} ~ {readiness?.end_date || '--'}
          </Text>
        </Space>
        {availableRange?.recommended_start_date && availableRange?.recommended_end_date ? (
          <Text type="secondary">
            建议区间: {availableRange.recommended_start_date} ~ {availableRange.recommended_end_date}
            {' '}（连续{num(availableRange.trailing_contiguous_days, 0)}天）
          </Text>
        ) : null}
        {!readiness ? (
          <Alert
            type="info"
            showIcon
            style={{ marginTop: 10 }}
            message="尚未检查覆盖"
            description="点击“覆盖检查”获取候选池与15m快照覆盖情况。"
          />
        ) : (
          <>
            <Alert
              type={readiness.ready ? 'success' : 'error'}
              showIcon
              style={{ marginTop: 10 }}
              message={readiness.ready ? '覆盖检查通过' : '覆盖检查未通过'}
              description={`原因: ${fmtReasonCodes(readiness.reason_codes)}`}
            />
            {Array.isArray(readiness.reason_codes) && readiness.reason_codes.includes('previous_run_deadband_blocked') ? (
              <Alert
                type="warning"
                showIcon
                style={{ marginTop: 10 }}
                message="上次回测被 deadband 阻断"
                description={`阻断桶数: ${num(readiness?.latest_backtest_hint?.delta_blocked_bucket_count, 0)}；请检查绝对/相对增益门槛与成本参数。`}
              />
            ) : null}
            <Row gutter={[12, 12]} style={{ marginTop: 10 }}>
              <Col span={6}><Statistic title="期望交易日" value={num(readiness.expected_trade_days, 0)} /></Col>
              <Col span={6}><Statistic title="有机会池的天数" value={num(readiness.universe_days_with_rows, 0)} /></Col>
              <Col span={6}><Statistic title="缺失机会池天数" value={num(readiness.missing_universe_date_count, 0)} /></Col>
              <Col span={6}><Statistic title="快照覆盖率" value={num(readiness.snapshot_bucket_coverage_pct)} precision={2} suffix="%" /></Col>
            </Row>
            {num(readiness.missing_universe_date_count, 0) > 0 ? (
              <Text type="warning">
                缺失日期(预览): {(readiness.missing_universe_dates_preview || []).join(', ') || '--'}
              </Text>
            ) : null}
          </>
        )}
      </Card>

      <Card>
        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <Space>
            <Text strong>
              离线导入任务ID: {importJobId || '--'}
              {importJob?.job_type ? ` (${IMPORT_JOB_TYPE_LABELS[importJob.job_type] || importJob.job_type})` : ''}
            </Text>
            {statusTag(importJob?.status)}
            <Text type="secondary">{importJob?.message || ''}</Text>
          </Space>
          <Text type="secondary">更新时间: {importJob?.updated_at ? new Date(importJob.updated_at).toLocaleString('zh-CN') : '--'}</Text>
        </Space>
        <Progress percent={Math.round(num(importJob?.progress, 0) * 100)} style={{ marginTop: 10 }} />
        {importJob?.error ? (
          <Alert type="error" showIcon style={{ marginTop: 10 }} message="导入任务失败" description={importJob.error} />
        ) : null}
        {importJob?.result ? (
          <Row gutter={[12, 12]} style={{ marginTop: 10 }}>
            <Col span={6}><Statistic title="总行数" value={num(importJob?.result?.total_rows, 0)} /></Col>
            <Col span={6}><Statistic title="导入行数" value={num(importJob?.result?.imported_rows, 0)} /></Col>
            <Col span={6}><Statistic title="跳过行数" value={num(importJob?.result?.skipped_rows, 0)} /></Col>
            <Col span={6}><Statistic title="错误数" value={num(importJob?.result?.error_count, 0)} /></Col>
          </Row>
        ) : null}
      </Card>

      <Card>
        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <Space>
            <Text strong>回测任务ID: {jobId || '--'}</Text>
            {statusTag(job?.status)}
            <Text type="secondary">{job?.message || ''}</Text>
          </Space>
          <Text type="secondary">更新时间: {job?.updated_at ? new Date(job.updated_at).toLocaleString('zh-CN') : '--'}</Text>
        </Space>
        <Progress percent={Math.round(num(job?.progress, 0) * 100)} style={{ marginTop: 10 }} />
        {job?.error ? (
          <Alert type="error" showIcon style={{ marginTop: 10 }} message="回测任务失败" description={job.error} />
        ) : null}
      </Card>

      <Card>
        <Title level={5}>回测摘要</Title>
        {summary?.reason ? <Alert type="warning" showIcon message={`回测结果: ${summary.reason}`} style={{ marginBottom: 12 }} /> : null}
        {!summary?.reason && num(summary?.trades_opened, 0) === 0 && num(summary?.delta_blocked_bucket_count, 0) > 0 ? (
          <Alert
            type="warning"
            showIcon
            style={{ marginBottom: 12 }}
            message="本次回测被 deadband 阻断，未触发执行"
            description={`阻断桶数: ${num(summary?.delta_blocked_bucket_count, 0)}；原因: ${(summary?.delta_block_reason_top || []).map((x) => `${DELTA_REASON_LABELS[x.code] || x.code}(${x.count})`).join('、') || '--'}`}
          />
        ) : null}
        <Row gutter={[12, 12]}>
          <Col span={6}><Statistic title="起始资金" value={num(summary.initial_nav_usd)} precision={2} prefix="$" /></Col>
          <Col span={6}><Statistic title="结束资金" value={num(summary.end_nav_usd)} precision={2} prefix="$" /></Col>
          <Col span={6}><Statistic title="总收益率" value={num(summary.total_return_pct)} precision={3} suffix="%" /></Col>
          <Col span={6}><Statistic title="最大回撤" value={num(summary.max_drawdown_pct)} precision={3} suffix="%" /></Col>
          <Col span={6}><Statistic title="Funding收益" value={num(summary.funding_pnl_usd)} precision={4} prefix="$" /></Col>
          <Col span={6}><Statistic title="Basis收益" value={num(summary.basis_pnl_usd)} precision={4} prefix="$" /></Col>
          <Col span={6}><Statistic title="手续费" value={num(summary.fee_paid_usd)} precision={4} prefix="$" /></Col>
          <Col span={6}><Statistic title="执行换仓次数" value={num(summary.rebalance_executed, 0)} /></Col>
        </Row>
      </Card>

      <Card title="权益曲线">
        <EquityCurveChart rows={curve} />
      </Card>

      <Card title={`事件明细 (${events.length})`}>
        <Table
          size="small"
          rowKey={(r, idx) => `${r.ts || ''}-${r.action || ''}-${idx}`}
          columns={eventCols}
          dataSource={events}
          pagination={{ pageSize: 15, showSizeChanger: false }}
          scroll={{ x: 900 }}
        />
      </Card>

      <Card>
        <Space align="center" style={{ width: '100%', justifyContent: 'space-between' }}>
          <Space>
            <SearchOutlined style={{ color: '#1677ff' }} />
            <Title level={5} style={{ margin: 0 }}>Walk-forward 参数搜索</Title>
          </Space>
          <Space>
            <Button icon={<ReloadOutlined />} disabled={!searchJobId} onClick={() => { void refreshSearchJob(); }}>
              刷新搜索
            </Button>
            <Button type="primary" loading={searchLoading} icon={<PlayCircleOutlined />} onClick={startSearch}>
              启动参数搜索
            </Button>
          </Space>
        </Space>

        <Text type="secondary">列表类参数使用逗号分隔，例如: 0,5,10,15</Text>

        <Row gutter={[12, 12]} style={{ marginTop: 14 }}>
          <Col span={6}>
            <Text>开始日期(YYYY-MM-DD)</Text>
            <Input value={searchParams.start_date} onChange={(e) => setSearchParams((p) => ({ ...p, start_date: e.target.value }))} placeholder="留空按 days" />
          </Col>
          <Col span={6}>
            <Text>结束日期(YYYY-MM-DD)</Text>
            <Input value={searchParams.end_date} onChange={(e) => setSearchParams((p) => ({ ...p, end_date: e.target.value }))} placeholder="留空为今天" />
          </Col>
          <Col span={4}><Text>搜索天数</Text><InputNumber min={10} max={365} value={searchParams.days} onChange={onNumber('days', setSearchParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Text>机会池TopN</Text><InputNumber min={1} max={2000} value={searchParams.top_n} onChange={onNumber('top_n', setSearchParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Text>初始资金</Text><InputNumber min={100} value={searchParams.initial_nav_usd} onChange={onNumber('initial_nav_usd', setSearchParams)} style={{ width: '100%' }} /></Col>

          <Col span={4}><Text>训练天数</Text><InputNumber min={1} max={90} value={searchParams.train_days} onChange={onNumber('train_days', setSearchParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Text>测试天数</Text><InputNumber min={1} max={30} value={searchParams.test_days} onChange={onNumber('test_days', setSearchParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Text>步长天数</Text><InputNumber min={1} max={30} value={searchParams.step_days} onChange={onNumber('step_days', setSearchParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Text>每窗入围K</Text><InputNumber min={1} max={20} value={searchParams.train_top_k} onChange={onNumber('train_top_k', setSearchParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Text>最大试验组</Text><InputNumber min={1} max={300} value={searchParams.max_trials} onChange={onNumber('max_trials', setSearchParams)} style={{ width: '100%' }} /></Col>
          <Col span={4}><Text>随机种子</Text><InputNumber min={1} value={searchParams.random_seed} onChange={onNumber('random_seed', setSearchParams)} style={{ width: '100%' }} /></Col>

          <Col span={8}><Text>入场评分候选</Text><Input value={searchParams.enter_score_threshold_values} onChange={(e) => setSearchParams((p) => ({ ...p, enter_score_threshold_values: e.target.value }))} /></Col>
          <Col span={8}><Text>入场置信度候选</Text><Input value={searchParams.entry_conf_min_values} onChange={(e) => setSearchParams((p) => ({ ...p, entry_conf_min_values: e.target.value }))} /></Col>
          <Col span={8}><Text>最大持仓对数候选</Text><Input value={searchParams.max_open_pairs_values} onChange={(e) => setSearchParams((p) => ({ ...p, max_open_pairs_values: e.target.value }))} /></Col>

          <Col span={8}><Text>利用率候选(%)</Text><Input value={searchParams.target_utilization_pct_values} onChange={(e) => setSearchParams((p) => ({ ...p, target_utilization_pct_values: e.target.value }))} /></Col>
          <Col span={8}><Text>最小单对本金候选</Text><Input value={searchParams.min_pair_notional_usd_values} onChange={(e) => setSearchParams((p) => ({ ...p, min_pair_notional_usd_values: e.target.value }))} /></Col>
          <Col span={8}><Text>冲击成本上限候选(%)</Text><Input value={searchParams.max_impact_pct_values} onChange={(e) => setSearchParams((p) => ({ ...p, max_impact_pct_values: e.target.value }))} /></Col>

          <Col span={8}><Text>换仓确认轮数候选</Text><Input value={searchParams.switch_confirm_rounds_values} onChange={(e) => setSearchParams((p) => ({ ...p, switch_confirm_rounds_values: e.target.value }))} /></Col>
          <Col span={8}><Text>相对增益门槛候选(%)</Text><Input value={searchParams.rebalance_min_relative_adv_pct_values} onChange={(e) => setSearchParams((p) => ({ ...p, rebalance_min_relative_adv_pct_values: e.target.value }))} /></Col>
          <Col span={8}><Text>绝对增益门槛候选(USD/天)</Text><Input value={searchParams.rebalance_min_absolute_adv_usd_day_values} onChange={(e) => setSearchParams((p) => ({ ...p, rebalance_min_absolute_adv_usd_day_values: e.target.value }))} /></Col>
        </Row>
      </Card>

      <Card>
        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <Space>
            <Text strong>搜索任务ID: {searchJobId || '--'}</Text>
            {statusTag(searchJob?.status)}
            <Text type="secondary">{searchJob?.message || ''}</Text>
          </Space>
          <Text type="secondary">更新时间: {searchJob?.updated_at ? new Date(searchJob.updated_at).toLocaleString('zh-CN') : '--'}</Text>
        </Space>
        <Progress percent={Math.round(num(searchJob?.progress, 0) * 100)} style={{ marginTop: 10 }} />
        {searchJob?.error ? (
          <Alert type="error" showIcon style={{ marginTop: 10 }} message="参数搜索任务失败" description={searchJob.error} />
        ) : null}
      </Card>

      <Card title="参数搜索结果">
        <Row gutter={[12, 12]}>
          <Col span={6}><Statistic title="时间范围" value={`${searchSummary.start_date || '--'} ~ ${searchSummary.end_date || '--'}`} /></Col>
          <Col span={6}><Statistic title="窗口数量" value={num(searchSummary.windows, 0)} /></Col>
          <Col span={6}><Statistic title="参数组数量" value={num(searchSummary.combos_evaluated, 0)} /></Col>
          <Col span={6}><Statistic title="每窗入围K" value={num(searchSummary.train_top_k, 0)} /></Col>
        </Row>

        <Card size="small" style={{ marginTop: 12 }} title="推荐参数组">
          {!recommended ? (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无推荐参数" />
          ) : (
            <Space direction="vertical" style={{ width: '100%' }}>
              <Space>
                <Tag color="blue">参数组 {recommended.combo_id}</Tag>
                <Tag color="green">稳定评分 {num(recommended.stability_score).toFixed(4)}</Tag>
                <Tag color="purple">均值收益 {num(recommended.avg_test_return_pct).toFixed(4)}%</Tag>
                <Tag color="gold">收益波动 {num(recommended.std_test_return_pct).toFixed(4)}%</Tag>
                <Tag color="red">平均回撤 {num(recommended.avg_test_drawdown_pct).toFixed(4)}%</Tag>
              </Space>
              <Space size={[4, 4]} wrap>
                {Object.entries(recommended.params || {}).map(([k, v]) => (
                  <Tag key={k}>{`${k}: ${v}`}</Tag>
                ))}
              </Space>
              <Space wrap>
                <Button onClick={applyRecommendedToBacktest}>应用到上方回测参数</Button>
                <Button loading={applyAutoLoading || autoDiffLoading} onClick={() => openAutoDiffPreview(false)}>
                  应用到自动策略配置
                </Button>
                <Button type="primary" loading={applyAutoAndStartLoading || autoDiffLoading} onClick={() => openAutoDiffPreview(true)}>
                  应用并开启自动策略(模拟)
                </Button>
              </Space>
            </Space>
          )}
        </Card>

        <Card size="small" style={{ marginTop: 12 }} title={`稳定性榜单 (${leaderboard.length})`}>
          <Table
            size="small"
            rowKey={(r) => String(r.combo_id || '')}
            columns={leaderboardCols}
            dataSource={leaderboard}
            pagination={{ pageSize: 8, showSizeChanger: false }}
            scroll={{ x: 1200 }}
          />
        </Card>

        <Card size="small" style={{ marginTop: 12 }} title={`窗口结果 (${windows.length})`}>
          <Table
            size="small"
            rowKey={(r) => `w-${r.window_index || ''}`}
            columns={windowCols}
            dataSource={windows}
            pagination={{ pageSize: 8, showSizeChanger: false }}
            scroll={{ x: 1100 }}
          />
        </Card>
      </Card>

      <Modal
        title={autoDiffStartAfterApply ? '确认应用参数并开启自动策略(模拟)' : '确认应用参数到自动策略'}
        open={autoDiffVisible}
        onCancel={() => setAutoDiffVisible(false)}
        onOk={confirmApplyFromDiff}
        okText={autoDiffStartAfterApply ? '确认并开启(模拟)' : '确认应用'}
        cancelText="取消"
        confirmLoading={applyAutoLoading || applyAutoAndStartLoading}
        width={980}
      >
        {autoDiffStartAfterApply ? (
          <Alert
            type="warning"
            showIcon
            style={{ marginBottom: 12 }}
            message="将同时开启自动策略，且默认以模拟模式运行（dry_run=true）。"
          />
        ) : null}
        <Table
          size="small"
          rowKey={(r) => String(r.key || '')}
          columns={autoDiffCols}
          dataSource={autoDiffRows}
          pagination={false}
          scroll={{ x: 760, y: 420 }}
        />
      </Modal>
    </Space>
  );
}
