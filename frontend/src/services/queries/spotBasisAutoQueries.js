import { useQuery } from "@tanstack/react-query";
import api from "../httpClient";

const num = (v, d = 0) => {
  const x = Number(v);
  return Number.isFinite(x) ? x : d;
};

async function fetchSpotBasisAutoCycleLast() {
  const res = await api.get("/spot-basis/auto-cycle-last");
  return res.data || null;
}

function buildOpportunityParams(filters) {
  return {
    symbol: filters?.symbol || "",
    min_rate: filters?.min_rate ?? 0,
    min_perp_volume: filters?.min_perp_volume ?? 0,
    min_spot_volume: filters?.min_spot_volume ?? 0,
    min_basis_pct: filters?.min_basis_pct ?? 0,
    perp_exchange_ids: (filters?.perp_exchange_ids || []).join(","),
    spot_exchange_ids: (filters?.spot_exchange_ids || []).join(","),
    require_cross_exchange: !!filters?.require_cross_exchange,
    action_mode: filters?.action_mode || "open",
    sort_by: filters?.sort_by || "score_strict",
    limit: 120,
  };
}

function buildDecisionPreviewParams(filters) {
  return {
    symbol: filters?.symbol || "",
    min_rate: filters?.min_rate ?? 0,
    min_perp_volume: filters?.min_perp_volume ?? 0,
    min_spot_volume: filters?.min_spot_volume ?? 0,
    min_basis_pct: filters?.min_basis_pct ?? 0,
    perp_exchange_ids: (filters?.perp_exchange_ids || []).join(","),
    spot_exchange_ids: (filters?.spot_exchange_ids || []).join(","),
    require_cross_exchange: !!filters?.require_cross_exchange,
    sort_by: filters?.sort_by || "score_strict",
    limit: 120,
  };
}

async function fetchSpotBasisAutoOpportunities(filters) {
  const res = await api.get("/spot-basis/opportunities", {
    timeout: 30000,
    params: buildOpportunityParams(filters),
  });
  return Array.isArray(res?.data?.rows) ? res.data.rows : [];
}

async function fetchSpotBasisAutoDecisionPreview(filters) {
  const res = await api.get("/spot-basis/auto-decision-preview", {
    timeout: 30000,
    params: buildDecisionPreviewParams(filters),
  });
  return res.data || null;
}

async function fetchSpotBasisAutoCycleLogs(limit = 160) {
  const res = await api.get("/spot-basis/auto-cycle-logs", { params: { limit } });
  const items = Array.isArray(res?.data?.items) ? res.data.items : [];
  return items.map((x, idx) => ({
    ...(x || {}),
    __key: `${num(x?.ts, 0)}-${idx}`,
  }));
}

async function fetchSpotBasisDrawdownWatermark() {
  const res = await api.get("/spot-basis/drawdown-watermark");
  return res.data || null;
}

async function fetchSpotBasisAutoExchangeFunds() {
  const [overviewRes, marginRes] = await Promise.allSettled([
    api.get("/dashboard/account-overview"),
    api.get("/spread-arb/margin-status"),
  ]);

  const overviewRows = overviewRes.status === "fulfilled" ? overviewRes.value?.data || [] : [];
  const marginRows = marginRes.status === "fulfilled" ? marginRes.value?.data || [] : [];
  const marginMap = new Map((marginRows || []).map((x) => [num(x.exchange_id, 0), x || {}]));

  const rows = (overviewRows || []).map((x) => {
    const exchangeId = num(x.exchange_id, 0);
    const margin = marginMap.get(exchangeId) || {};
    const unified = !!x.unified_account;
    const totalUnified = num(x.total_usdt, 0);
    const spotUsdt = num(x.spot_usdt, 0);
    const futuresUsdt = num(x.futures_usdt, 0);
    const totalUsdt = unified
      ? totalUnified
      : totalUnified > 0
        ? totalUnified
        : spotUsdt + futuresUsdt;
    return {
      exchange_id: exchangeId,
      exchange_name: x.exchange_name || `EX#${exchangeId}`,
      unified_account: unified,
      total_usdt: totalUsdt,
      spot_usdt: spotUsdt,
      futures_usdt: futuresUsdt,
      positions_count: (x.positions || []).length,
      used_pct: num(margin.used_pct, 0),
      current_notional: num(margin.current_notional, 0),
      remaining_notional: num(margin.remaining_notional, 0),
      max_notional: num(margin.max_notional, 0),
      error: x.error || margin.error || "",
      warning: x.warning || "",
    };
  });

  rows.sort((a, b) => num(b.total_usdt, 0) - num(a.total_usdt, 0));
  return rows;
}

export function useSpotBasisAutoCycleLastQuery() {
  return useQuery({
    queryKey: ["spot-basis-auto", "cycle-last"],
    queryFn: fetchSpotBasisAutoCycleLast,
    refetchInterval: 5000,
    refetchIntervalInBackground: true,
    retry: false,
  });
}

export function useSpotBasisAutoOpportunitiesQuery(filters, pollingEnabled = true) {
  return useQuery({
    queryKey: ["spot-basis-auto", "opportunities", filters],
    queryFn: () => fetchSpotBasisAutoOpportunities(filters),
    refetchInterval: pollingEnabled ? 60000 : false,
    refetchIntervalInBackground: true,
    retry: false,
  });
}

export function useSpotBasisAutoDecisionPreviewQuery(filters) {
  return useQuery({
    queryKey: ["spot-basis-auto", "decision-preview", filters],
    queryFn: () => fetchSpotBasisAutoDecisionPreview(filters),
    refetchInterval: 60000,
    refetchIntervalInBackground: true,
    retry: false,
  });
}

export function useSpotBasisAutoCycleLogsQuery(limit = 160) {
  return useQuery({
    queryKey: ["spot-basis-auto", "cycle-logs", limit],
    queryFn: () => fetchSpotBasisAutoCycleLogs(limit),
    refetchInterval: 5000,
    refetchIntervalInBackground: true,
    retry: false,
  });
}

export function useSpotBasisDrawdownWatermarkQuery() {
  return useQuery({
    queryKey: ["spot-basis-auto", "drawdown-watermark"],
    queryFn: fetchSpotBasisDrawdownWatermark,
    refetchInterval: 10000,
    refetchIntervalInBackground: true,
    retry: false,
  });
}

export function useSpotBasisAutoExchangeFundsQuery() {
  return useQuery({
    queryKey: ["spot-basis-auto", "exchange-funds"],
    queryFn: fetchSpotBasisAutoExchangeFunds,
    refetchInterval: 10000,
    refetchIntervalInBackground: true,
    retry: false,
  });
}
