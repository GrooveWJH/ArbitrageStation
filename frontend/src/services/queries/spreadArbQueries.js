import { useQuery } from "@tanstack/react-query";
import api from "../httpClient";

async function fetchSpreadArbStats() {
  const res = await api.get("/spread-arb/stats");
  return res.data || {};
}

async function fetchSpreadArbConfig() {
  const res = await api.get("/spread-arb/config");
  return res.data || {};
}

async function fetchSpreadArbPositions(status, limit) {
  const res = await api.get("/spread-arb/positions", { params: { status, limit } });
  return res.data || { positions: [] };
}

async function fetchSpreadArbMarginStatus() {
  const res = await api.get("/spread-arb/margin-status");
  return res.data || [];
}

export function useSpreadArbStatsQuery() {
  return useQuery({
    queryKey: ["spread-arb", "stats"],
    queryFn: fetchSpreadArbStats,
    refetchInterval: 2000,
    refetchIntervalInBackground: true,
  });
}

export function useSpreadArbConfigQuery() {
  return useQuery({
    queryKey: ["spread-arb", "config"],
    queryFn: fetchSpreadArbConfig,
    refetchInterval: 2000,
    refetchIntervalInBackground: true,
  });
}

export function useSpreadArbOpenPositionsQuery() {
  return useQuery({
    queryKey: ["spread-arb", "positions", "open", 100],
    queryFn: () => fetchSpreadArbPositions("open", 100),
    refetchInterval: 2000,
    refetchIntervalInBackground: true,
  });
}

export function useSpreadArbHistoryPositionsQuery() {
  return useQuery({
    queryKey: ["spread-arb", "positions", "closed", 50],
    queryFn: () => fetchSpreadArbPositions("closed", 50),
    refetchInterval: 2000,
    refetchIntervalInBackground: true,
  });
}

export function useSpreadArbMarginStatusQuery() {
  return useQuery({
    queryKey: ["spread-arb", "margin-status"],
    queryFn: fetchSpreadArbMarginStatus,
    refetchInterval: 5000,
    refetchIntervalInBackground: true,
  });
}
