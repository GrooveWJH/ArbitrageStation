import { useQuery } from "@tanstack/react-query";
import api from "../httpClient";

function buildFundingRateParams(filters) {
  const params = {};
  if (filters?.symbol) params.symbol = filters.symbol;
  if (filters?.min_rate != null) params.min_rate = filters.min_rate;
  if (filters?.min_volume != null) params.min_volume = filters.min_volume;
  if (Array.isArray(filters?.exchange_ids) && filters.exchange_ids.length) {
    params.exchange_ids = filters.exchange_ids.join(",");
  }
  return params;
}

async function fetchFundingRates(filters) {
  const res = await api.get("/dashboard/funding-rates", {
    params: buildFundingRateParams(filters),
  });
  return Array.isArray(res.data) ? res.data : [];
}

async function fetchFundingRateExchanges() {
  const res = await api.get("/exchanges/");
  return Array.isArray(res.data) ? res.data : [];
}

export function useFundingRatesQuery(filters) {
  return useQuery({
    queryKey: ["funding-rates", "list", filters],
    queryFn: () => fetchFundingRates(filters),
  });
}

export function useFundingRateExchangesQuery() {
  return useQuery({
    queryKey: ["funding-rates", "exchanges"],
    queryFn: fetchFundingRateExchanges,
  });
}
