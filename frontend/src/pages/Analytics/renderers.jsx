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
  return <Tag color={qualityColor[q] || 'default'}>{q}</Tag>;
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
    active: ['blue', 'active'],
    closed: ['green', 'closed'],
    closing: ['orange', 'closing'],
    error: ['red', 'error'],
  };
  const one = map[value] || ['default', String(value || '-')];
  return <Tag color={one[0]}>{one[1]}</Tag>;
}
