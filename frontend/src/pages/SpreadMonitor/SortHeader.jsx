import React from 'react';
import { Tooltip } from 'antd';
import {
  SortAscendingOutlined,
  SortDescendingOutlined,
} from '@ant-design/icons';

export default function SortHeader({
  label,
  tooltip,
  field,
  sortField,
  sortDir,
  onSort,
}) {
  const active = sortField === field;
  const Icon = active && sortDir === 'asc' ? SortAscendingOutlined : SortDescendingOutlined;

  return (
    <Tooltip title={tooltip}>
      <span
        style={{ cursor: 'pointer', userSelect: 'none' }}
        onClick={() => {
          if (active) onSort(field, sortDir === 'desc' ? 'asc' : 'desc');
          else onSort(field, 'desc');
        }}
      >
        {label}
        {' '}
        <Icon style={{ color: active ? '#1677ff' : '#bbb', fontSize: 13 }} />
      </span>
    </Tooltip>
  );
}
