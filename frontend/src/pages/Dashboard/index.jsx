import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert } from 'antd';
import {
  useDashboardAccountOverviewQuery,
  useDashboardOpportunitiesQuery,
  useDashboardPnlSummaryQuery,
  useDashboardSpotOpportunitiesQuery,
  useDashboardTradeLogsQuery,
} from '../../services/queries/dashboardQueries';
import AccountSection from './AccountSection';
import { buildLogColumns, buildOppColumns, buildSpotOppColumns } from './columns';
import OpportunitiesSection from './OpportunitiesSection';
import PnlQualityBar from './PnlQualityBar';
import { updatePriceStore } from './priceDiffStore';
import RecentTradesCard from './RecentTradesCard';
import TopMetricsRow from './TopMetricsRow';
import { calcExchangeTotalUsdt, formatUsdt, toNumber } from './utils';

export default function Dashboard({ wsData }) {
  const [opportunities, setOpportunities] = useState([]);
  const [minVolume, setMinVolume] = useState(() => Number(localStorage.getItem('dashboard_min_volume') || 0));
  const [minSpotVolume, setMinSpotVolume] = useState(() => Number(localStorage.getItem('dashboard_min_spot_volume') || 0));
  const [accountTrend, setAccountTrend] = useState([]);
  const [accountRefreshLoading, setAccountRefreshLoading] = useState(false);

  const pnlSummaryQuery = useDashboardPnlSummaryQuery();
  const opportunitiesQuery = useDashboardOpportunitiesQuery(minVolume);
  const spotOpportunitiesQuery = useDashboardSpotOpportunitiesQuery(minVolume, minSpotVolume);
  const tradeLogsQuery = useDashboardTradeLogsQuery(20);
  const accountOverviewQuery = useDashboardAccountOverviewQuery();

  const pnlSummary = pnlSummaryQuery.data || {};
  const baseOpportunities = opportunitiesQuery.data || [];
  const spotOpportunities = spotOpportunitiesQuery.data || [];
  const logs = tradeLogsQuery.data || [];
  const accountData = accountOverviewQuery.data || [];
  const accountLoading = (!accountOverviewQuery.isFetched && accountOverviewQuery.isLoading) || accountRefreshLoading;

  const handleMinVolumeChange = (v) => {
    const val = v || 0;
    setMinVolume(val);
    localStorage.setItem('dashboard_min_volume', val);
  };

  const handleMinSpotVolumeChange = (v) => {
    const val = v || 0;
    setMinSpotVolume(val);
    localStorage.setItem('dashboard_min_spot_volume', val);
  };

  const handleRefreshAccount = useCallback(async () => {
    setAccountRefreshLoading(true);
    try {
      await accountOverviewQuery.refetch();
    } finally {
      setAccountRefreshLoading(false);
    }
  }, [accountOverviewQuery]);

  useEffect(() => {
    setOpportunities(Array.isArray(baseOpportunities) ? baseOpportunities : []);
  }, [baseOpportunities]);

  useEffect(() => {
    if (!accountOverviewQuery.dataUpdatedAt) return;

    const normalized = Array.isArray(accountData) ? accountData : [];
    const totalUsdt = normalized.reduce((sum, ex) => sum + calcExchangeTotalUsdt(ex), 0);
    const totalUnrealized = normalized.reduce(
      (sum, ex) => sum + (Array.isArray(ex.positions) ? ex.positions.reduce((s, p) => s + toNumber(p.unrealized_pnl), 0) : 0),
      0,
    );
    const now = new Date();
    const point = {
      ts: now.toISOString(),
      time: now.toLocaleTimeString([], { hour12: false }),
      total_usdt: Number(totalUsdt.toFixed(4)),
      unrealized_pnl: Number(totalUnrealized.toFixed(4)),
    };
    setAccountTrend((prev) => {
      if (prev.length === 0) return [point];
      const last = prev[prev.length - 1];
      const lastTs = new Date(last.ts).getTime();
      if (now.getTime() - lastTs < 4000) {
        return [...prev.slice(0, -1), point];
      }
      const next = [...prev, point];
      return next.slice(-180);
    });
  }, [accountOverviewQuery.dataUpdatedAt, accountData]);

  useEffect(() => {
    if (wsData?.type !== 'price_diffs') return;
    const payload = wsData?.payload ?? wsData?.data;
    if (payload) updatePriceStore(payload);
  }, [wsData]);

  useEffect(() => {
    if (wsData?.type !== 'opportunities') return;
    const payload = wsData?.payload ?? wsData?.data;
    const incoming = Array.isArray(payload?.opportunities) ? payload.opportunities : [];
    const newData = incoming.filter((o) => !minVolume || (o.min_volume_24h || 0) >= minVolume);
    setOpportunities((prev) => {
      if (prev.length === newData.length && JSON.stringify(prev) === JSON.stringify(newData)) return prev;
      return newData;
    });
  }, [wsData, minVolume]);

  const accountSummary = useMemo(() => {
    const out = {
      totalUsdt: 0,
      knownSpotUsdt: 0,
      knownFuturesUsdt: 0,
      altEquivalentUsdt: 0,
      unifiedUsdt: 0,
      positionCount: 0,
      unrealizedPnlUsdt: 0,
      exchangeCount: accountData.length,
      healthyExchangeCount: 0,
      warningExchangeCount: 0,
      errorExchangeCount: 0,
    };
    const mergedAssets = {};

    accountData.forEach((ex) => {
      const totalUsdt = calcExchangeTotalUsdt(ex);
      out.totalUsdt += totalUsdt;
      if (ex.unified_account) out.unifiedUsdt += toNumber(ex.total_usdt);
      else {
        const spotUsdt = toNumber(ex.spot_usdt);
        const futuresUsdt = toNumber(ex.futures_usdt);
        out.knownSpotUsdt += spotUsdt;
        out.knownFuturesUsdt += futuresUsdt;
        out.altEquivalentUsdt += Math.max(0, totalUsdt - spotUsdt - futuresUsdt);
      }

      if (ex.error) out.errorExchangeCount += 1;
      else out.healthyExchangeCount += 1;
      if (ex.warning) out.warningExchangeCount += 1;

      const positions = Array.isArray(ex.positions) ? ex.positions : [];
      out.positionCount += positions.length;
      out.unrealizedPnlUsdt += positions.reduce((s, p) => s + toNumber(p.unrealized_pnl), 0);

      const assets = Array.isArray(ex.spot_assets) ? ex.spot_assets : [];
      assets.forEach((a) => {
        if (!a?.asset) return;
        mergedAssets[a.asset] = (mergedAssets[a.asset] || 0) + toNumber(a.total);
      });
    });

    out.topAssets = Object.entries(mergedAssets)
      .map(([asset, total]) => ({ asset, total }))
      .sort((a, b) => b.total - a.total)
      .slice(0, 8);
    return out;
  }, [accountData]);

  const accountTrendStart = accountTrend.length > 0 ? toNumber(accountTrend[0].total_usdt) : null;
  const accountTrendEnd = accountTrend.length > 0 ? toNumber(accountTrend[accountTrend.length - 1].total_usdt) : null;
  const accountTrendDelta = accountTrendStart == null || accountTrendEnd == null ? null : accountTrendEnd - accountTrendStart;
  const accountTrendData = useMemo(() => accountTrend.map((p) => ({ time: p.time, total_usdt: p.total_usdt })), [accountTrend]);
  const accountTrendConfig = {
    data: accountTrendData,
    encode: { x: 'time', y: 'total_usdt' },
    smooth: true,
    animation: false,
    style: { stroke: '#1677ff', lineWidth: 2.6 },
    point: accountTrendData.length <= 48 ? { size: 2.5, style: { fill: '#1677ff' } } : false,
    axis: { x: { labelAutoRotate: true }, y: { labelAutoHide: true } },
  };

  const oppColumns = useMemo(() => buildOppColumns(), []);
  const spotOppColumns = useMemo(() => buildSpotOppColumns(), []);
  const logColumns = useMemo(() => buildLogColumns(), []);
  const emergencyLogs = logs.filter((l) => l.action === 'emergency_close');

  return (
    <div style={{ padding: 0 }}>
      {emergencyLogs.length > 0 && (
        <Alert
          message={`有 ${emergencyLogs.length} 笔风控平仓记录`}
          description="请检查策略状态和风险规则配置"
          type="error"
          showIcon
          closable
          style={{ marginBottom: 24 }}
        />
      )}

      <TopMetricsRow pnlSummary={pnlSummary} />
      <PnlQualityBar pnlSummary={pnlSummary} />

      <AccountSection
        accountLoading={accountLoading}
        accountData={accountData}
        accountSummary={accountSummary}
        accountTrendData={accountTrendData}
        accountTrendConfig={accountTrendConfig}
        accountTrendStart={accountTrendStart}
        accountTrendEnd={accountTrendEnd}
        accountTrendDelta={accountTrendDelta}
        onRefresh={handleRefreshAccount}
        formatUsdt={formatUsdt}
        calcExchangeTotalUsdt={calcExchangeTotalUsdt}
        toNumber={toNumber}
      />

      <OpportunitiesSection
        opportunities={opportunities}
        spotOpportunities={spotOpportunities}
        minVolume={minVolume}
        minSpotVolume={minSpotVolume}
        onMinVolumeChange={handleMinVolumeChange}
        onMinSpotVolumeChange={handleMinSpotVolumeChange}
        oppColumns={oppColumns}
        spotOppColumns={spotOppColumns}
      />

      <RecentTradesCard logs={logs} columns={logColumns} />
      <style>{`.risk-row { background: #fff1f0 !important; } .row-no-spot td { color: #bbb !important; }`}</style>
    </div>
  );
}
