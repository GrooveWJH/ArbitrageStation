import React from 'react';
import { Tag } from 'antd';

export function statusTag(status) {
  const map = {
    active: ['green', '运行中'],
    closed: ['default', '已结束'],
    closing: ['orange', '平仓中'],
    error: ['red', '异常'],
  };
  const [color, label] = map[status] || ['default', status];
  return <Tag color={color}>{label}</Tag>;
}

export function qualityTag(quality) {
  const q = quality || 'unknown';
  const colorMap = {
    ok: 'green',
    na: 'blue',
    partial: 'orange',
    stale: 'volcano',
    missing: 'red',
  };
  const labelMap = {
    ok: '正常',
    na: '无数据',
    partial: '部分',
    stale: '过期',
    missing: '缺失',
    unknown: '未知',
  };
  return <Tag color={colorMap[q] || 'default'}>{labelMap[q] || q}</Tag>;
}

export function pnlRender(v, precision = 2) {
  if (v == null) return <span style={{ color: '#999' }}>--</span>;
  const n = Number(v);
  return (
    <span style={{ color: n >= 0 ? '#3f8600' : '#cf1322', fontWeight: 600 }}>
      {n >= 0 ? '+' : ''}
      {n.toFixed(precision)} USDT
    </span>
  );
}

export function pnlPctRender(v) {
  if (v == null) return <span style={{ color: '#999' }}>--</span>;
  const n = Number(v);
  return (
    <span style={{ color: n >= 0 ? '#3f8600' : '#cf1322' }}>
      {n >= 0 ? '+' : ''}
      {n.toFixed(2)}%
    </span>
  );
}
