import { useQuery } from "@tanstack/react-query";
import api from "../httpClient";

function normalizeStrategyRows(rows) {
  return rows.map((r) => ({
    id: r.strategy_id,
    name: r.name,
    strategy_type: r.strategy_type,
    symbol: r.symbol,
    long_exchange: r.long_exchange,
    short_exchange: r.short_exchange,
    current_annualized: r.current_annualized,
    initial_margin_usd: r.initial_margin_usd,
    unrealized_pnl: r.spread_pnl_usdt,
    funding_pnl_usd: r.funding_pnl_usdt,
    total_pnl_usd: r.total_pnl_usdt,
    quality: r.quality,
    funding_expected_event_count: r.funding_expected_event_count,
    funding_captured_event_count: r.funding_captured_event_count,
    status: r.status,
    close_reason: r.close_reason,
    created_at: r.created_at,
    closed_at: r.closed_at,
  }));
}

async function fetchPositionsOverview(status, page, pageSize) {
  const [strategiesRes, exchangesRes, opportunitiesRes, spotOpportunitiesRes] = await Promise.all([
    api.get("/pnl/v2/strategies", {
      params: {
        days: 0,
        status,
        page,
        page_size: pageSize,
      },
    }),
    api.get("/exchanges/"),
    api.get("/dashboard/opportunities", { params: { min_diff: 0.01 } }),
    api.get("/dashboard/spot-opportunities", { params: { min_rate: 0.01 } }),
  ]);

  const strategyRows = Array.isArray(strategiesRes?.data?.rows) ? strategiesRes.data.rows : [];
  const exchanges = Array.isArray(exchangesRes?.data) ? exchangesRes.data : [];
  const opportunities = Array.isArray(opportunitiesRes?.data) ? opportunitiesRes.data : [];
  const spotOpportunities = Array.isArray(spotOpportunitiesRes?.data) ? spotOpportunitiesRes.data : [];

  return {
    strategies: normalizeStrategyRows(strategyRows),
    totalCount: Number(strategiesRes?.data?.total_count || 0),
    exchanges: exchanges.filter((ex) => ex.is_active),
    opportunities,
    spotOpportunities,
  };
}

export function usePositionsOverviewQuery({ status, page, pageSize }) {
  return useQuery({
    queryKey: ["positions", "overview", status || "all", page, pageSize],
    queryFn: () => fetchPositionsOverview(status, page, pageSize),
    refetchInterval: 15000,
    refetchIntervalInBackground: true,
  });
}
