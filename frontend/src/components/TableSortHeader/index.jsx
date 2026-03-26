import React from 'react';
import { Tooltip } from 'antd';
import {
  CaretDownOutlined,
  CaretUpOutlined,
} from '@ant-design/icons';

export default function TableSortHeader({
  label,
  tooltip,
  field,
  sortField,
  sortDir,
  onSort,
}) {
  const active = sortField === field;
  const nextDir = active ? (sortDir === 'desc' ? 'asc' : 'desc') : 'desc';
  const orderLabel = sortDir === 'asc' ? '升序' : '降序';
  const ariaSort = active ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none';

  return (
    <Tooltip title={tooltip}>
      <button
        type="button"
        className={`kinetic-sort-header ${active ? `is-active dir-${sortDir}` : ''}`}
        aria-label={`${label}排序`}
        aria-sort={ariaSort}
        aria-pressed={active}
        onClick={() => {
          onSort(field, nextDir);
        }}
      >
        <span className="kinetic-sort-label">{label}</span>
        <span className={`kinetic-sort-order ${active ? `is-${sortDir} is-visible` : 'is-placeholder'}`}>
          {active ? orderLabel : '降序'}
        </span>
        <span className="kinetic-sort-icons" aria-hidden>
          <CaretUpOutlined className={`kinetic-sort-icon is-up ${active && sortDir === 'asc' ? 'is-on' : 'is-off'}`} />
          <CaretDownOutlined className={`kinetic-sort-icon is-down ${active && sortDir === 'desc' ? 'is-on' : 'is-off'}`} />
        </span>
      </button>
    </Tooltip>
  );
}
