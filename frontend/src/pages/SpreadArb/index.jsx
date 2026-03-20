import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  Card, Row, Col, Table, Tag, Button, Switch, InputNumber, Select,
  Space, Statistic, Tooltip, Badge, Tabs, Popconfirm, Alert, Modal,
  Progress, List,
} from 'antd';
import {
  ReloadOutlined, SettingOutlined, CloseCircleOutlined,
  ArrowUpOutlined, ArrowDownOutlined, ThunderboltOutlined,
  CheckCircleOutlined, CloseCircleFilled,
} from '@ant-design/icons';
import api from '../../services/httpClient';
import {
  useSpreadArbConfigQuery,
  useSpreadArbHistoryPositionsQuery,
  useSpreadArbMarginStatusQuery,
  useSpreadArbOpenPositionsQuery,
  useSpreadArbStatsQuery,
} from '../../services/queries/spreadArbQueries';
import { fmtTime } from '../../utils/time';

function fmtPrice(v) {
  if (!v) return '—';
  if (v >= 1000) return `$${v.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
  if (v >= 1)    return `$${v.toFixed(4)}`;
  return `$${v.toFixed(8)}`;
}

function PnlCell({ value }) {
  if (value == null) return <span style={{ color: '#aaa' }}>—</span>;
  const pos = value >= 0;
  return (
    <span style={{ color: pos ? '#3f8600' : '#cf1322', fontWeight: 700 }}>
      {pos ? <ArrowUpOutlined style={{ fontSize: 11 }} /> : <ArrowDownOutlined style={{ fontSize: 11 }} />}
      {' '}{pos ? '+' : ''}{value.toFixed(4)} U
    </span>
  );
}

function statusTag(s) {
  const map = {
    open:    ['processing', 'blue',   '持仓中'],
    closing: ['processing', 'orange', '平仓中'],
    closed:  ['success',    'green',  '已平仓'],
    error:   ['error',      'red',    '错误'],
  };
  const [dot, color, label] = map[s] || ['default', 'default', s];
  return <Badge status={dot} text={<Tag color={color} style={{ margin: 0 }}>{label}</Tag>} />;
}

function fmtVol(v) {
  if (!v) return '0';
  if (v >= 1e9) return `${(v/1e9).toFixed(1)}B`;
  if (v >= 1e6) return `${(v/1e6).toFixed(0)}M`;
  if (v >= 1e3) return `${(v/1e3).toFixed(0)}K`;
  return String(v);
}

// ── Margin Cards ──────────────────────────────────────────────────────────────
function MarginCards({ items }) {
  if (!items || items.length === 0) return null;
  return (
    <Card
      size="small"
      title="各交易所合约账户保证金利用率（含费率+价差套利，5s 刷新）"
      style={{ marginBottom: 16 }}
    >
      <Row gutter={[16, 16]}>
        {items.map(ex => {
          const over = ex.used_pct >= ex.cap_pct;
          const warn = ex.used_pct >= ex.cap_pct * 0.85;
          const color = over ? '#cf1322' : warn ? '#fa8c16' : '#52c41a';
          const strokeColor = over ? '#ff4d4f' : warn ? '#fa8c16' : '#52c41a';
          return (
            <Col key={ex.exchange_id} xs={24} sm={12} lg={8}>
              <div style={{
                border: `1px solid ${over ? '#ffadd2' : warn ? '#ffd591' : '#d9d9d9'}`,
                borderRadius: 8,
                padding: '12px 16px',
                background: over ? '#fff0f6' : warn ? '#fffbe6' : '#fff',
              }}>
                {/* Header */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <Space size={6}>
                    <Tag color={over ? 'red' : 'default'} style={{ fontWeight: 700, fontSize: 12 }}>
                      {ex.exchange_name?.toUpperCase()}
                    </Tag>
                    {over && <Tag color="red" style={{ fontSize: 10 }}>超上限</Tag>}
                  </Space>
                  <span style={{ fontWeight: 700, color, fontSize: 15 }}>
                    {ex.used_pct?.toFixed(1)}%
                  </span>
                </div>

                {/* Progress bar */}
                <div style={{ position: 'relative', height: 10, borderRadius: 5, background: '#f0f0f0', marginBottom: 6 }}>
                  <div style={{
                    height: '100%', borderRadius: 5,
                    width: `${Math.min(ex.used_pct ?? 0, 100)}%`,
                    background: strokeColor,
                    transition: 'width 0.4s',
                  }} />
                  {/* cap_pct marker */}
                  <div style={{
                    position: 'absolute', top: -2, bottom: -2,
                    left: `${ex.cap_pct ?? 80}%`,
                    width: 2, background: '#ff4d4f', borderRadius: 1,
                  }} />
                </div>

                {/* Notional row */}
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
                  <span style={{ color: '#888' }}>上限 <b style={{ color: '#262626' }}>${(ex.max_notional ?? 0).toFixed(2)}</b></span>
                  <span style={{ color: '#888' }}>已开 <b style={{ color }}>${(ex.current_notional ?? 0).toFixed(2)}</b></span>
                  <span style={{ color: '#888' }}>余 <b style={{ color: '#3f8600' }}>${(ex.remaining_notional ?? 0).toFixed(2)}</b></span>
                </div>

                {/* Detail row */}
                <div style={{ fontSize: 11, color: '#aaa' }}>
                  余额 ${(ex.total ?? 0).toFixed(2)} · 杠杆 {ex.user_leverage ?? 1}x · 上限 {ex.cap_pct ?? 80}%
                  {(ex.funding_notional > 0 || ex.spread_notional > 0) && (
                    <span style={{ marginLeft: 8 }}>
                      (费率 ${(ex.funding_notional ?? 0).toFixed(0)} / 价差 ${(ex.spread_notional ?? 0).toFixed(0)})
                    </span>
                  )}
                </div>

                {ex.error && <div style={{ fontSize: 11, color: '#cf1322', marginTop: 4 }}>错误: {ex.error}</div>}
              </div>
            </Col>
          );
        })}
      </Row>
    </Card>
  );
}

// ── Config Panel ──────────────────────────────────────────────────────────────
function ConfigPanel({ cfg, onSave, saving }) {
  const [local, setLocal] = useState(null);
  // Only initialize once when cfg first arrives; don't reset on background polls
  const didInit = useRef(false);
  useEffect(() => {
    if (cfg && !didInit.current) {
      setLocal(cfg);
      didInit.current = true;
    }
  }, [cfg]);
  const set = (k, v) => setLocal(p => ({ ...p, [k]: v }));
  if (!local) return null;

  return (
    <Card size="small" title={<><SettingOutlined /> 价差套利配置</>} style={{ marginBottom: 16 }}>
      <Row gutter={[16, 12]}>
        {/* ── z 阈值 ── */}
        <Col span={6}>
          <div style={{ color: '#888', fontSize: 12, marginBottom: 4 }}>
            <Tooltip title="当前价差 z分数 ≥ 此值时入场">入场 z 阈值 ℹ</Tooltip>
          </div>
          <InputNumber value={local.spread_entry_z} onChange={v => set('spread_entry_z', v)}
            min={0.5} max={5} step={0.1} precision={1} style={{ width: '100%' }} />
        </Col>
        <Col span={6}>
          <div style={{ color: '#888', fontSize: 12, marginBottom: 4 }}>
            <Tooltip title="z分数回落至此值时平仓（价差回归均值）">出场 z 阈值 ℹ</Tooltip>
          </div>
          <InputNumber value={local.spread_exit_z} onChange={v => set('spread_exit_z', v)}
            min={-1} max={2} step={0.1} precision={1} style={{ width: '100%' }} />
        </Col>
        <Col span={6}>
          <div style={{ color: '#888', fontSize: 12, marginBottom: 4 }}>
            <Tooltip title={`止损 z = 入场时z + δ。入场z越高止损线自动上移，避免高z入场时倒挂。示例：入场z=3.4，δ=1.5 → 止损z=4.9`}>
              止损偏移 δ ℹ
            </Tooltip>
          </div>
          <InputNumber value={local.spread_stop_z_delta} onChange={v => set('spread_stop_z_delta', v)}
            min={0.1} max={5} step={0.1} precision={1} style={{ width: '100%' }}
            addonAfter="σ" />
        </Col>
        <Col span={6}>
          <div style={{ color: '#888', fontSize: 12, marginBottom: 4 }}>
            <Tooltip title={`浮动止盈 z = 入场时z - δ。价差收敛到此z即止盈，早于完全均值回归。默认3.0，即入场z=7时在z=4止盈。`}>
              止盈偏移 δ ℹ
            </Tooltip>
          </div>
          <InputNumber value={local.spread_tp_z_delta} onChange={v => set('spread_tp_z_delta', v)}
            min={0.5} max={10} step={0.5} precision={1} style={{ width: '100%' }}
            addonAfter="σ" />
        </Col>
        <Col span={6}>
          <div style={{ color: '#888', fontSize: 12, marginBottom: 4 }}>
            <Tooltip title="结算前N分钟平仓，避免价格波动风险">结算前平仓(分钟) ℹ</Tooltip>
          </div>
          <InputNumber value={local.spread_pre_settle_mins} onChange={v => set('spread_pre_settle_mins', v)}
            min={1} max={60} step={1} style={{ width: '100%' }} />
        </Col>

        {/* ── 仓位 & 成交量 ── */}
        <Col span={6}>
          <div style={{ color: '#888', fontSize: 12, marginBottom: 4 }}>
            <Tooltip title="每笔仓位使用「可用余额」的百分比（可用=总余额-费率套利占用）">仓位占比(%) ℹ</Tooltip>
          </div>
          <InputNumber value={local.spread_position_pct} onChange={v => set('spread_position_pct', v)}
            min={1} max={100} step={1} precision={1} suffix="%" style={{ width: '100%' }} />
        </Col>
        <Col span={6}>
          <div style={{ color: '#888', fontSize: 12, marginBottom: 4 }}>
            <Tooltip title="价差套利专属上限（两种策略共用「总上限」）">价差仓位上限 ℹ</Tooltip>
          </div>
          <InputNumber value={local.spread_max_positions} onChange={v => set('spread_max_positions', v)}
            min={1} max={20} step={1} style={{ width: '100%' }} />
        </Col>
        <Col span={6}>
          <div style={{ color: '#888', fontSize: 12, marginBottom: 4 }}>
            <Tooltip title="两腿中较小成交量须达到此值才入场（0=不限制）">最小24h成交量 ℹ</Tooltip>
          </div>
          <InputNumber
            value={local.spread_min_volume_usd}
            onChange={v => set('spread_min_volume_usd', v || 0)}
            min={0} step={100000}
            formatter={v => v ? `$${Number(v).toLocaleString()}` : '$0'}
            parser={v => Number((v || '0').replace(/[^0-9]/g, ''))}
            style={{ width: '100%' }}
          />
        </Col>
        <Col span={6}>
          <div style={{ color: '#888', fontSize: 12, marginBottom: 4 }}>
            <Tooltip title="止损平仓后，该对子在N分钟内不再入场（冷静期）">止损冷静期(分钟) ℹ</Tooltip>
          </div>
          <InputNumber value={local.spread_cooldown_mins} onChange={v => set('spread_cooldown_mins', v)}
            min={0} max={1440} step={5} style={{ width: '100%' }} />
        </Col>

        {/* ── 共用总上限 & 下单类型 ── */}
        <Col span={6}>
          <div style={{ color: '#888', fontSize: 12, marginBottom: 4 }}>
            <Tooltip title="费率套利 + 价差套利 合计最多同时持有的「策略个数」上限（不是 USD，与费率套利自动交易页面互通）">
              总策略数上限（共用）ℹ
            </Tooltip>
          </div>
          <InputNumber value={local.max_open_strategies} onChange={v => set('max_open_strategies', v)}
            min={1} max={50} step={1} style={{ width: '100%' }} addonAfter="个" />
        </Col>
        <Col span={6}>
          <div style={{ color: '#888', fontSize: 12, marginBottom: 4 }}>下单类型</div>
          <Select value={local.spread_order_type} onChange={v => set('spread_order_type', v)} style={{ width: '100%' }}>
            <Select.Option value="market">市价单 (立即成交)</Select.Option>
            <Select.Option value="limit">限价单 (当前价)</Select.Option>
          </Select>
        </Col>
        <Col span={6}>
          <div style={{ color: '#888', fontSize: 12, marginBottom: 4 }}>
            <Tooltip title="关闭后，若价差套利方向与同交易所同币种的费率套利方向相反，则跳过该机会（无需交易所开启双向持仓模式）">
              双向持仓模式 ℹ
            </Tooltip>
          </div>
          <Switch
            checked={local.spread_use_hedge_mode ?? true}
            onChange={v => set('spread_use_hedge_mode', v)}
            checkedChildren="开启"
            unCheckedChildren="关闭"
          />
          <div style={{ fontSize: 11, color: '#aaa', marginTop: 4 }}>
            {local.spread_use_hedge_mode ?? true
              ? '独立建仓，与费率套利方向无关'
              : '跳过与费率套利方向冲突的机会'}
          </div>
        </Col>
        <Col span={6} style={{ display: 'flex', alignItems: 'flex-end' }}>
          <Button type="primary" loading={saving} onClick={() => onSave(local)} block>
            保存配置
          </Button>
        </Col>
      </Row>
    </Card>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function SpreadArb() {
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

  const loading = isMainInitialLoading;
  const [saving, setSaving]       = useState(false);
  const [toggling, setToggling]   = useState(false);
  const [hedgeModal, setHedgeModal] = useState(null); // null | {results, loading}
  const [hedgeLoading, setHedgeLoading] = useState(false);

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
      await api.put('/spread-arb/config', { spread_arb_enabled: enabled });
      await refreshMain();
    } finally {
      setToggling(false);
    }
  };

  const handleSaveCfg = async (newCfg) => {
    setSaving(true);
    try {
      await api.put('/spread-arb/config', newCfg);
      await refreshMain();
    } finally {
      setSaving(false);
    }
  };

  const handleClose = async (id) => {
    await api.post(`/spread-arb/close/${id}`);
    await refreshMain();
  };

  const handleSetupHedge = async () => {
    setHedgeLoading(true);
    setHedgeModal({ results: null, loading: true });
    try {
      const res = await api.post('/spread-arb/setup-hedge-mode');
      setHedgeModal({ results: res.data.results || {}, loading: false });
    } catch (e) {
      setHedgeModal({ results: {}, loading: false, error: '请求失败，请检查交易所连接' });
    } finally {
      setHedgeLoading(false);
    }
  };

  const enabled   = stats?.enabled ?? false;
  const totalActive = stats?.total_active ?? 0;
  const maxTotal    = stats?.max_open_strategies ?? (cfg?.max_open_strategies ?? 5);
  const fundingCnt  = stats?.funding_count ?? 0;
  const spreadCnt   = stats?.open_count ?? 0;
  const usedPct     = maxTotal > 0 ? Math.round(totalActive / maxTotal * 100) : 0;

  // ── Open positions columns ─────────────────────────────────────────────────
  const openCols = [
    {
      title: '交易对',
      dataIndex: 'symbol',
      width: 140,
      render: (sym, row) => (
        <div>
          <div style={{ fontWeight: 700 }}>{sym}</div>
          <Tag color="purple" style={{ fontSize: 10, marginTop: 2 }}>{row.order_type}</Tag>
        </div>
      ),
    },
    {
      title: '做空（高价）',
      width: 150,
      render: (_, row) => (
        <div>
          <div style={{ fontWeight: 600 }}>{row.short_exchange_name}</div>
          <div style={{ fontSize: 11, color: '#888' }}>入场 {fmtPrice(row.short_entry_price)}</div>
          <div style={{ fontSize: 11, color: '#1677ff' }}>现价 {fmtPrice(row.short_current_price)}</div>
        </div>
      ),
    },
    {
      title: '做多（低价）',
      width: 150,
      render: (_, row) => (
        <div>
          <div style={{ fontWeight: 600 }}>{row.long_exchange_name}</div>
          <div style={{ fontSize: 11, color: '#888' }}>入场 {fmtPrice(row.long_entry_price)}</div>
          <div style={{ fontSize: 11, color: '#1677ff' }}>现价 {fmtPrice(row.long_current_price)}</div>
        </div>
      ),
    },
    {
      title: '入场价差 → 当前价差',
      width: 180,
      render: (_, row) => {
        const narrowed = row.current_spread_pct < row.entry_spread_pct;
        return (
          <div>
            <div style={{ fontSize: 13 }}>
              <span style={{ color: '#888' }}>{row.entry_spread_pct?.toFixed(4)}%</span>
              <span style={{ margin: '0 6px' }}>→</span>
              <span style={{ fontWeight: 700, color: narrowed ? '#3f8600' : '#cf1322' }}>
                {row.current_spread_pct?.toFixed(4)}%
              </span>
            </div>
            <div style={{ fontSize: 11, color: '#aaa' }}>
              入场 z={row.entry_z_score?.toFixed(2)}
              {row.entry_z_score > 0 && (
                <>
                  <Tooltip title={`浮动止盈 = 入场z(${row.entry_z_score?.toFixed(2)}) - δ(${(cfg?.spread_tp_z_delta ?? 3.0).toFixed(1)})，价差收敛时提前锁利`}>
                    <span style={{ marginLeft: 6, color: '#52c41a' }}>
                      TP≤{row.take_profit_z != null ? row.take_profit_z.toFixed(2) : (row.entry_z_score - (cfg?.spread_tp_z_delta ?? 3.0)).toFixed(2)}
                    </span>
                  </Tooltip>
                  <Tooltip title={`动态止损线 = 入场z(${row.entry_z_score?.toFixed(2)}) + δ(${(cfg?.spread_stop_z_delta ?? 1.5).toFixed(1)})`}>
                    <span style={{ marginLeft: 6, color: '#ff7875' }}>
                      SL≥{(row.entry_z_score + (cfg?.spread_stop_z_delta ?? 1.5)).toFixed(1)}
                    </span>
                  </Tooltip>
                </>
              )}
            </div>
          </div>
        );
      },
    },
    {
      title: '仓位规模',
      dataIndex: 'position_size_usd',
      width: 90,
      align: 'right',
      render: v => <span style={{ color: '#666' }}>${v?.toFixed(2)}</span>,
    },
    {
      title: '浮动盈亏',
      dataIndex: 'unrealized_pnl_usd',
      width: 120,
      align: 'right',
      render: v => <PnlCell value={v} />,
      sorter: (a, b) => (a.unrealized_pnl_usd || 0) - (b.unrealized_pnl_usd || 0),
    },
    {
      title: '操作',
      width: 90,
      align: 'center',
      render: (_, row) => (
        <Popconfirm
          title="确认立即平仓？"
          description="将以市价单平掉两腿持仓"
          onConfirm={() => handleClose(row.id)}
          okText="确认平仓"
          cancelText="取消"
          okButtonProps={{ danger: true }}
        >
          <Button danger size="small" icon={<CloseCircleOutlined />}>平仓</Button>
        </Popconfirm>
      ),
    },
  ];

  // ── History columns ────────────────────────────────────────────────────────
  const histCols = [
    { title: '交易对', dataIndex: 'symbol', width: 130, render: s => <Tag color="blue">{s}</Tag> },
    { title: '做空', dataIndex: 'short_exchange_name', width: 100 },
    { title: '做多', dataIndex: 'long_exchange_name', width: 100 },
    {
      title: '入场价差',
      dataIndex: 'entry_spread_pct',
      width: 100,
      render: v => <span style={{ color: '#cf1322' }}>{v?.toFixed(4)}%</span>,
    },
    {
      title: '入场 z',
      dataIndex: 'entry_z_score',
      width: 80,
      render: v => <Tag color={v >= 2 ? 'red' : 'orange'}>z={v?.toFixed(2)}</Tag>,
    },
    {
      title: '已实现盈亏',
      dataIndex: 'realized_pnl_usd',
      width: 120,
      align: 'right',
      render: v => <PnlCell value={v} />,
      sorter: (a, b) => (a.realized_pnl_usd || 0) - (b.realized_pnl_usd || 0),
      defaultSortOrder: 'descend',
    },
    { title: '状态', dataIndex: 'status', width: 90, render: statusTag },
    {
      title: '平仓原因',
      dataIndex: 'close_reason',
      ellipsis: true,
      render: v => <span style={{ fontSize: 11, color: '#888' }}>{v}</span>,
    },
    {
      title: '开仓时间',
      dataIndex: 'created_at',
      width: 140,
      render: v => v ? fmtTime(v) : '—',
    },
  ];

  const s = stats || {};

  return (
    <div>
      {/* ── Header row ──────────────────────────────────────────────────────── */}
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
              <Badge status="processing" text={
                <span style={{ color: '#1677ff', fontSize: 12 }}>运行中（每30秒扫描）</span>
              } />
            )}
          </Space>
        </Col>
        <Col>
          <Space>
            <Tooltip title="在所有已连接交易所上开启双向持仓模式（开始交易前必须执行）">
              <Button
                icon={<ThunderboltOutlined />}
                onClick={handleSetupHedge}
                loading={hedgeLoading}
              >
                初始化对冲模式
              </Button>
            </Tooltip>
            <Button
              icon={<ReloadOutlined />}
              onClick={() => { void handleRefresh(); }}
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

      {/* ── Stats cards ─────────────────────────────────────────────────────── */}
      <Row gutter={12} style={{ marginBottom: 16 }}>
        <Col span={4}>
          <Card size="small">
            <Statistic title="价差持仓中" value={s.open_count ?? 0}
              valueStyle={{ color: (s.open_count ?? 0) > 0 ? '#1677ff' : '#999' }} />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic title="浮动盈亏" value={s.total_unrealized ?? 0} precision={4} suffix="U"
              valueStyle={{ color: (s.total_unrealized ?? 0) >= 0 ? '#3f8600' : '#cf1322' }} />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic title="已实现盈亏" value={s.total_realized ?? 0} precision={4} suffix="U"
              valueStyle={{ color: (s.total_realized ?? 0) >= 0 ? '#3f8600' : '#cf1322' }} />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic title="综合盈亏" value={s.combined_pnl ?? 0} precision={4} suffix="U"
              valueStyle={{ color: (s.combined_pnl ?? 0) >= 0 ? '#3f8600' : '#cf1322' }} />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic title={`胜率 (${s.closed_count ?? 0}笔)`}
              value={s.win_rate ?? 0} precision={1} suffix="%"
              valueStyle={{ color: (s.win_rate ?? 0) >= 50 ? '#3f8600' : '#cf1322' }} />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small" title={
            <span style={{ fontSize: 12, color: '#888' }}>
              仓位占用 {totalActive}/{maxTotal}
            </span>
          } bodyStyle={{ paddingTop: 8 }}>
            <Progress
              percent={usedPct}
              size="small"
              status={usedPct >= 100 ? 'exception' : usedPct >= 80 ? 'active' : 'normal'}
              format={() => `${totalActive}/${maxTotal}`}
            />
            <div style={{ fontSize: 11, color: '#888', marginTop: 4, display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#1677ff' }}>费率 {fundingCnt}</span>
              <span style={{ color: '#722ed1' }}>价差 {spreadCnt}</span>
            </div>
          </Card>
        </Col>
      </Row>

      {/* ── Margin utilization ──────────────────────────────────────────────── */}
      <MarginCards items={marginData} />

      {/* ── Config panel ────────────────────────────────────────────────────── */}
      <ConfigPanel cfg={cfg} onSave={handleSaveCfg} saving={saving} />

      {/* ── Positions & History tabs ────────────────────────────────────────── */}
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
                  loading={loading}
                  pagination={false}
                  size="small"
                  scroll={{ x: 900 }}
                  locale={{ emptyText: '暂无持仓，价差机会出现时将自动开仓' }}
                  rowClassName={row => (row.unrealized_pnl_usd ?? 0) >= 0 ? 'win-row' : 'loss-row'}
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
                  loading={loading}
                  pagination={{ pageSize: 20, showTotal: t => `共 ${t} 条` }}
                  size="small"
                  scroll={{ x: 900 }}
                  rowClassName={row => (row.realized_pnl_usd ?? 0) >= 0 ? 'win-row' : 'loss-row'}
                />
              ),
            },
          ]}
        />
      </Card>

      {/* ── Hedge mode result modal ──────────────────────────────────────────── */}
      <Modal
        title={
          <Space>
            <ThunderboltOutlined style={{ color: '#faad14' }} />
            对冲模式初始化结果
          </Space>
        }
        open={hedgeModal !== null}
        onCancel={() => setHedgeModal(null)}
        footer={[
          <Button key="ok" type="primary" onClick={() => setHedgeModal(null)}>确定</Button>,
        ]}
      >
        {hedgeModal?.loading ? (
          <div style={{ textAlign: 'center', padding: '24px 0', color: '#888' }}>
            正在初始化各交易所对冲模式，请稍候…
          </div>
        ) : hedgeModal?.error ? (
          <Alert type="error" message={hedgeModal.error} showIcon />
        ) : hedgeModal?.results && Object.keys(hedgeModal.results).length === 0 ? (
          <Alert type="warning" message="未找到已连接的活跃交易所，请先在「交易所」页面添加并启用交易所。" showIcon />
        ) : (
          <List
            dataSource={Object.entries(hedgeModal?.results || {})}
            renderItem={([name, ok]) => (
              <List.Item>
                <List.Item.Meta
                  avatar={
                    ok
                      ? <CheckCircleOutlined style={{ fontSize: 20, color: '#3f8600' }} />
                      : <CloseCircleFilled style={{ fontSize: 20, color: '#cf1322' }} />
                  }
                  title={<span style={{ fontWeight: 600 }}>{name}</span>}
                  description={
                    ok
                      ? <span style={{ color: '#3f8600' }}>双向持仓模式已开启</span>
                      : <span style={{ color: '#cf1322' }}>初始化失败，请检查 API 权限或手动设置</span>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Modal>

      <style>{`
        .win-row td  { background: #f6ffed !important; }
        .loss-row td { background: #fff1f0 !important; }
      `}</style>
    </div>
  );
}
