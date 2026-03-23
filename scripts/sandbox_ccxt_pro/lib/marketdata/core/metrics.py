from __future__ import annotations

import time
from dataclasses import dataclass

from lib.marketdata.types import EventRow


@dataclass
class ChannelMetrics:
    first_event_at: float | None = None
    last_event_at: float | None = None
    first_complete_at: float | None = None
    last_report_at: float = 0.0
    total_events: int = 0
    total_complete: int = 0
    total_bytes: int = 0
    total_complete_bytes: int = 0
    window_events: int = 0
    window_complete: int = 0
    window_bytes: int = 0
    window_complete_bytes: int = 0


class MetricsRegistry:
    def __init__(self):
        self._data: dict[str, ChannelMetrics] = {}

    def get(self, key: str) -> ChannelMetrics:
        if key not in self._data:
            self._data[key] = ChannelMetrics()
        return self._data[key]

    @property
    def data(self) -> dict[str, ChannelMetrics]:
        return self._data


def on_event(
    metrics: ChannelMetrics,
    *,
    complete: bool,
    payload_bytes: int,
    exchange: str,
    mkt: str,
    ch: str,
    interval_sec: float = 10,
) -> list[EventRow]:
    out: list[EventRow] = []
    now = time.time()
    if metrics.first_event_at is None:
        metrics.first_event_at = now
    metrics.last_event_at = now

    metrics.total_events += 1
    metrics.window_events += 1
    metrics.total_bytes += max(payload_bytes, 0)
    metrics.window_bytes += max(payload_bytes, 0)

    if complete:
        metrics.total_complete += 1
        metrics.window_complete += 1
        metrics.total_complete_bytes += max(payload_bytes, 0)
        metrics.window_complete_bytes += max(payload_bytes, 0)
        if metrics.first_complete_at is None:
            metrics.first_complete_at = now
            metrics.last_report_at = now
            out.append(
                EventRow(
                    tone="ok",
                    code="METRIC_START",
                    exchange=exchange,
                    mkt=mkt,
                    ch=ch,
                    note="首次完整数据 complete=1，开始测速 rate",
                )
            )
            return out

    if metrics.first_complete_at is None:
        return out

    if now - metrics.last_report_at < interval_sec:
        return out

    elapsed = max(1e-6, now - metrics.first_complete_at)
    win_elapsed = max(1e-6, now - metrics.last_report_at)
    rate_win_all = metrics.window_events / win_elapsed
    rate_win_ok = metrics.window_complete / win_elapsed
    rate_avg_all = metrics.total_events / elapsed
    rate_avg_ok = metrics.total_complete / elapsed
    bw_win_all_mbps = (metrics.window_bytes * 8) / win_elapsed / 1_000_000
    bw_win_ok_mbps = (metrics.window_complete_bytes * 8) / win_elapsed / 1_000_000
    bw_avg_all_mbps = (metrics.total_bytes * 8) / elapsed / 1_000_000
    bw_avg_ok_mbps = (metrics.total_complete_bytes * 8) / elapsed / 1_000_000

    out.append(
        EventRow(
            tone="metric",
            code="METRIC_WINDOW",
            exchange=exchange,
            mkt=mkt,
            ch=ch,
            rate=f"Hz:{rate_win_all:.2f}/{rate_win_ok:.2f}",
            note=(
                f"速率(rate) 近10s(all/ok): {rate_win_all:.2f}/{rate_win_ok:.2f}, "
                f"累计(avg): {rate_avg_all:.2f}/{rate_avg_ok:.2f}; "
                f"带宽(bw) Mbps 近10s(all/ok): {bw_win_all_mbps:.3f}/{bw_win_ok_mbps:.3f}, "
                f"累计(avg): {bw_avg_all_mbps:.3f}/{bw_avg_ok_mbps:.3f}"
            ),
        )
    )

    metrics.last_report_at = now
    metrics.window_events = 0
    metrics.window_complete = 0
    metrics.window_bytes = 0
    metrics.window_complete_bytes = 0
    return out


def build_final_summary_rows(registry: MetricsRegistry) -> list[EventRow]:
    rows = [
        EventRow(
            tone="metric",
            code="SUMMARY",
            exchange="summary",
            ch="metric",
            note="退出汇总：ticker vs orderbook 全程频率(从首次读取到结束)",
        )
    ]
    if not registry.data:
        rows.append(EventRow(tone="warn", code="SUMMARY_EMPTY", exchange="summary", ch="metric", note="无可用统计数据"))
        return rows

    for key in sorted(registry.data.keys()):
        parts = key.split("|", 3)
        if len(parts) == 4:
            ex, mkt, ch, symbol = parts
        else:
            ex, mkt, ch = parts
            symbol = ""
        m = registry.data[key]
        if m.first_event_at is None or m.last_event_at is None:
            rows.append(EventRow(tone="warn", code="SUMMARY_NODATA", exchange=ex, mkt=mkt, ch=ch, note="通道未收到数据"))
            continue

        elapsed = max(1e-6, m.last_event_at - m.first_event_at)
        hz_all = m.total_events / elapsed
        hz_ok = m.total_complete / elapsed
        rows.append(
            EventRow(
                tone="metric",
                code="SUMMARY",
                exchange=ex,
                mkt=mkt,
                ch=ch,
                rate=f"avg:{hz_all:.2f}/{hz_ok:.2f}",
                note=(
                    f"symbol={symbol or '--'}; 频率Hz all/ok={hz_all:.2f}/{hz_ok:.2f}; "
                    f"带宽Mbps all/ok={(m.total_bytes * 8) / elapsed / 1_000_000:.3f}/"
                    f"{(m.total_complete_bytes * 8) / elapsed / 1_000_000:.3f}; "
                    f"事件={m.total_events}/{m.total_complete}; 时长={elapsed:.1f}s"
                ),
            )
        )

    return rows


@dataclass(frozen=True)
class SummaryStat:
    exchange: str
    market: str
    channel: str
    symbol: str
    hz_all: float
    hz_ok: float
    total_events: int
    total_complete: int
    mbps_all: float
    mbps_ok: float
    elapsed_sec: float


def collect_summary_stats(registry: MetricsRegistry) -> list[SummaryStat]:
    out: list[SummaryStat] = []
    for key in sorted(registry.data.keys()):
        ex, mkt, ch, symbol = key.split("|", 3)
        m = registry.data[key]
        if m.first_event_at is None or m.last_event_at is None:
            continue
        elapsed = max(1e-6, m.last_event_at - m.first_event_at)
        out.append(
            SummaryStat(
                exchange=ex,
                market=mkt,
                channel=ch,
                symbol=symbol,
                hz_all=m.total_events / elapsed,
                hz_ok=m.total_complete / elapsed,
                total_events=m.total_events,
                total_complete=m.total_complete,
                mbps_all=(m.total_bytes * 8) / elapsed / 1_000_000,
                mbps_ok=(m.total_complete_bytes * 8) / elapsed / 1_000_000,
                elapsed_sec=elapsed,
            )
        )
    return out
