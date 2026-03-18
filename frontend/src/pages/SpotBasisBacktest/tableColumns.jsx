import React from 'react';
import { Space, Tag } from 'antd';
import { num } from './utils';

export const createEventCols = () => [
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

export const createLeaderboardCols = () => [
  { title: '参数组', dataIndex: 'combo_id', width: 90 },
  { title: '稳定评分', dataIndex: 'stability_score', width: 100, render: (v) => num(v).toFixed(4) },
  { title: '窗口数', dataIndex: 'windows_covered', width: 80, render: (v) => num(v, 0) },
  { title: '平均收益(%)', dataIndex: 'avg_test_return_pct', width: 110, render: (v) => num(v).toFixed(4) },
  { title: '收益波动(%)', dataIndex: 'std_test_return_pct', width: 110, render: (v) => num(v).toFixed(4) },
  { title: '平均回撤(%)', dataIndex: 'avg_test_drawdown_pct', width: 110, render: (v) => num(v).toFixed(4) },
  { title: '正收益窗口占比', dataIndex: 'positive_window_ratio', width: 120, render: (v) => `${(num(v) * 100).toFixed(1)}%` },
  { title: '触发硬风控窗口', dataIndex: 'risk_halt_windows', width: 120, render: (v) => num(v, 0) },
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

export const createWindowCols = () => [
  { title: '窗口', dataIndex: 'window_index', width: 80 },
  { title: '训练区间', key: 'train', width: 220, render: (_, r) => `${r.train_start || '--'} ~ ${r.train_end || '--'}` },
  { title: '测试区间', key: 'test', width: 220, render: (_, r) => `${r.test_start || '--'} ~ ${r.test_end || '--'}` },
  { title: '最佳参数组', dataIndex: 'best_test_combo_id', width: 100, render: (v) => v || '--' },
  { title: '最佳测试收益(%)', dataIndex: 'best_test_return_pct', width: 130, render: (v) => num(v).toFixed(4) },
  { title: '最佳测试回撤(%)', dataIndex: 'best_test_drawdown_pct', width: 130, render: (v) => num(v).toFixed(4) },
  { title: '入围参数组', dataIndex: 'selected_combo_ids', render: (v) => (Array.isArray(v) && v.length ? v.join(', ') : '--') },
];

export const createAutoDiffCols = (fmtPreviewValue) => [
  { title: '参数', dataIndex: 'label', width: 260 },
  { title: '当前值', dataIndex: 'before', width: 170, render: (v) => fmtPreviewValue(v) },
  { title: '建议值', dataIndex: 'after', width: 170, render: (v) => fmtPreviewValue(v) },
  { title: '变化', dataIndex: 'changed', width: 90, render: (v) => (v ? <Tag color="processing">变更</Tag> : <Tag>不变</Tag>) },
];
