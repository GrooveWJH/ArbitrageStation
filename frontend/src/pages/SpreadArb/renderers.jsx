import React from 'react';
import {
  ArrowDownOutlined,
  ArrowUpOutlined,
} from '@ant-design/icons';
import {
  Badge,
  Tag,
} from 'antd';

export function PnlCell({ value }) {
  if (value == null) return <span style={{ color: '#aaa' }}>—</span>;
  const pos = value >= 0;
  return (
    <span style={{ color: pos ? '#3f8600' : '#cf1322', fontWeight: 700 }}>
      {pos ? <ArrowUpOutlined style={{ fontSize: 11 }} /> : <ArrowDownOutlined style={{ fontSize: 11 }} />}
      {' '}
      {pos ? '+' : ''}
      {value.toFixed(4)}
      {' '}
      U
    </span>
  );
}

export function statusTag(s) {
  const map = {
    open: ['processing', 'blue', '持仓中'],
    closing: ['processing', 'orange', '平仓中'],
    closed: ['success', 'green', '已平仓'],
    error: ['error', 'red', '错误'],
  };
  const [dot, color, label] = map[s] || ['default', 'default', s];
  return <Badge status={dot} text={<Tag color={color} style={{ margin: 0 }}>{label}</Tag>} />;
}
