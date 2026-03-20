import { useQuery } from "@tanstack/react-query";
import api from "../httpClient";

async function fetchAnalyticsPnlSummary(params) {
  const res = await api.get("/pnl/v2/summary", { params });
  return res.data || {};
}

async function fetchAnalyticsPnlStrategies(params) {
  const res = await api.get("/pnl/v2/strategies", { params });
  return res.data || { rows: [], total_count: 0 };
}

async function fetchAnalyticsReconcileLatest(limit) {
  const res = await api.get("/pnl/v2/reconcile/latest", { params: { limit } });
  return res.data || { rows: [] };
}

async function fetchAnalyticsEquityCurve(days) {
  const res = await api.get("/analytics/equity", { params: { days } });
  return res.data || { points: [] };
}

export function useAnalyticsPnlSummaryQuery(params) {
  return useQuery({
    queryKey: ["analytics", "pnl-summary", params],
    queryFn: () => fetchAnalyticsPnlSummary(params),
  });
}

export function useAnalyticsPnlStrategiesQuery(params) {
  return useQuery({
    queryKey: ["analytics", "pnl-strategies", params],
    queryFn: () => fetchAnalyticsPnlStrategies(params),
  });
}

export function useAnalyticsPnlReconcileLatestQuery(limit = 1) {
  return useQuery({
    queryKey: ["analytics", "reconcile-latest", limit],
    queryFn: () => fetchAnalyticsReconcileLatest(limit),
  });
}

export function useAnalyticsEquityCurveQuery(days) {
  return useQuery({
    queryKey: ["analytics", "equity-curve", days],
    queryFn: () => fetchAnalyticsEquityCurve(days),
  });
}
