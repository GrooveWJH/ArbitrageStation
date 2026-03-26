function normalizeGroupKey(value) {
  return String(value || '');
}

export function isWithinSpreadGroup(groupKey, relatedTarget) {
  if (!groupKey || !(relatedTarget instanceof Element)) return false;
  const row = relatedTarget.closest('tr[data-group-key]');
  if (!row) return false;
  return row.getAttribute('data-group-key') === normalizeGroupKey(groupKey);
}

export function composeSpreadRowClass(row, hoveredGroupKey) {
  const classes = [];
  if (row?.is_highest_freq) classes.push('kinetic-spread-row-highfreq');
  if (row?._groupKey && hoveredGroupKey && row._groupKey === hoveredGroupKey) {
    classes.push('kinetic-spread-row-group-hover');
  }
  return classes.join(' ');
}
