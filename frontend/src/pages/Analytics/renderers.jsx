import React from 'react';
import { ArrowDownOutlined, ArrowUpOutlined } from '@ant-design/icons';
import { Tag } from 'antd';

const qualityColor = {
  ok: 'green',
  na: 'blue',
  partial: 'orange',
  stale: 'volcano',
  missing: 'red',
};

export function QualityTag({ value }) {
  const q = value || 'unknown';
  const labelMap = {
    ok: '正常',
    na: '无数据',
    partial: '部分',
    stale: '过期',
    missing: '缺失',
    unknown: '未知',
  };
  return <Tag color={qualityColor[q] || 'default'}>{labelMap[q] || q}</Tag>;
}

export function PnlText({ value, precision = 4, suffix = 'U' }) {
  if (value == null) return <span style={{ color: '#999' }}>--</span>;
  const pos = value >= 0;
  return (
    <span style={{ color: pos ? '#3f8600' : '#cf1322', fontWeight: 600 }}>
      {pos ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
      {' '}
      {pos ? '+' : ''}
      {Number(value).toFixed(precision)}
      {' '}
      {suffix}
    </span>
  );
}

export function StatusTag({ value }) {
  const map = {
    active: ['blue', '运行中'],
    closed: ['green', '已结束'],
    closing: ['orange', '平仓中'],
    error: ['red', '异常'],
  };
  const one = map[value] || ['default', String(value || '-')];
  return <Tag color={one[0]}>{one[1]}</Tag>;
}
