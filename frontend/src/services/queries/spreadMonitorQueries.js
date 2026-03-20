import { useQuery } from "@tanstack/react-query";
import api from "../httpClient";

async function fetchSpreadOpportunities() {
  const res = await api.get("/spread-monitor/opportunities");
  return res.data || { opportunities: [] };
}

export function useSpreadOpportunitiesQuery() {
  return useQuery({
    queryKey: ["spread-monitor", "opportunities"],
    queryFn: fetchSpreadOpportunities,
    refetchInterval: 1000,
    refetchIntervalInBackground: true,
  });
}
