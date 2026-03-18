import React from 'react';
import { Tag } from 'antd';
import { READINESS_REASON_LABELS } from './constants';

export const num = (v, d = 0) => {
  const x = Number(v);
  return Number.isFinite(x) ? x : d;
};

export const parseNumberList = (raw, asInt = false) => {
  const text = String(raw ?? '').trim();
  if (!text) return [];
  const out = text.split(/[\s,，;；]+/).map((x) => Number(x)).filter((x) => Number.isFinite(x));
  if (!out.length) return [];
  if (asInt) return [...new Set(out.map((x) => Math.trunc(x)))];
  return [...new Set(out.map((x) => Number(x.toFixed(8))))];
};

export const fmtReasonCodes = (codes) => {
  if (!Array.isArray(codes) || !codes.length) return '无';
  return codes.map((x) => READINESS_REASON_LABELS[x] || String(x)).join('、');
};

export const isSameValue = (a, b) => {
  const na = Number(a);
  const nb = Number(b);
  if (Number.isFinite(na) && Number.isFinite(nb)) return Math.abs(na - nb) < 1e-10;
  return String(a ?? '') === String(b ?? '');
};

export const fmtPreviewValue = (v) => {
  if (v == null) return '--';
  const n = Number(v);
  if (Number.isFinite(n)) {
    if (Math.abs(n - Math.trunc(n)) < 1e-10) return String(Math.trunc(n));
    return n.toFixed(6).replace(/0+$/g, '').replace(/\.$/, '');
  }
  return String(v);
};

export const statusTag = (status) => {
  const s = String(status || '').toLowerCase();
  if (s === 'succeeded') return <Tag color="success">已完成</Tag>;
  if (s === 'failed') return <Tag color="error">失败</Tag>;
  if (s === 'running') return <Tag color="processing">运行中</Tag>;
  if (s === 'pending') return <Tag color="default">排队中</Tag>;
  return <Tag>未知</Tag>;
};
