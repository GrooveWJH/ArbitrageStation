/**
 * Format a UTC timestamp as UTC+8 (Asia/Shanghai) local time.
 * @param {string|Date|number} v  - ISO string, Date, or epoch ms
 * @param {boolean} showSeconds   - include seconds (default true)
 * @returns {string}
 */
export function fmtTime(v, showSeconds = true) {
  if (!v) return '-';
  try {
    // Strings without timezone info (no Z / +HH:MM) are stored as UTC — append Z so
    // the browser parses them as UTC instead of local time.
    const raw = typeof v === 'string' && !/Z$|[+-]\d{2}:?\d{2}$/.test(v)
      ? v.replace(' ', 'T') + 'Z'
      : v;
    const d = new Date(raw);
    if (isNaN(d.getTime())) return String(v);
    return d.toLocaleString('zh-CN', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: showSeconds ? '2-digit' : undefined,
      hour12: false,
    });
  } catch {
    return String(v);
  }
}
