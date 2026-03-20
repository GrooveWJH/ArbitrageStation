import { useQuery } from "@tanstack/react-query";
import api from "../httpClient";

async function fetchDashboardPnlSummary() {
  const res = await api.get("/pnl/v2/summary", { params: { days: 0 } });
  return res.data || {};
}

async function fetchDashboardOpportunities(minVolume) {
  const res = await api.get("/dashboard/opportunities", {
    params: { min_diff: 0.01, min_volume: minVolume || 0 },
  });
  return Array.isArray(res.data) ? res.data : [];
}

async function fetchDashboardSpotOpportunities(minVolume, minSpotVolume) {
  const res = await api.get("/dashboard/spot-opportunities", {
    params: {
      min_rate: 0.01,
      min_volume: minVolume || 0,
      min_spot_volume: minSpotVolume || 0,
    },
  });
  return Array.isArray(res.data) ? res.data : [];
}

async function fetchDashboardTradeLogs(limit) {
  const res = await api.get("/dashboard/trade-logs", { params: { limit } });
  return Array.isArray(res.data) ? res.data : [];
}

async function fetchDashboardAccountOverview() {
  const res = await api.get("/dashboard/account-overview");
  return Array.isArray(res.data) ? res.data : [];
}

export function useDashboardPnlSummaryQuery() {
  return useQuery({
    queryKey: ["dashboard", "pnl-summary"],
    queryFn: fetchDashboardPnlSummary,
    refetchInterval: 3000,
    refetchIntervalInBackground: true,
  });
}

export function useDashboardOpportunitiesQuery(minVolume) {
  return useQuery({
    queryKey: ["dashboard", "opportunities", minVolume || 0],
    queryFn: () => fetchDashboardOpportunities(minVolume || 0),
  });
}

export function useDashboardSpotOpportunitiesQuery(minVolume, minSpotVolume) {
  return useQuery({
    queryKey: ["dashboard", "spot-opportunities", minVolume || 0, minSpotVolume || 0],
    queryFn: () => fetchDashboardSpotOpportunities(minVolume || 0, minSpotVolume || 0),
  });
}

export function useDashboardTradeLogsQuery(limit = 20) {
  return useQuery({
    queryKey: ["dashboard", "trade-logs", limit],
    queryFn: () => fetchDashboardTradeLogs(limit),
  });
}

export function useDashboardAccountOverviewQuery() {
  return useQuery({
    queryKey: ["dashboard", "account-overview"],
    queryFn: fetchDashboardAccountOverview,
    refetchInterval: 5000,
    refetchIntervalInBackground: true,
  });
}
