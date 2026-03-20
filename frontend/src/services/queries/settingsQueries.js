import { useQuery } from "@tanstack/react-query";
import api from "../httpClient";

async function fetchRiskRules() {
  const res = await api.get("/settings/risk-rules");
  return Array.isArray(res.data) ? res.data : [];
}

async function fetchEmailConfig() {
  const res = await api.get("/settings/email");
  return res.data || {};
}

async function fetchAppConfig() {
  const res = await api.get("/settings/app");
  return res.data || {};
}

async function fetchSettingsExchanges() {
  const res = await api.get("/exchanges/");
  return Array.isArray(res.data) ? res.data : [];
}

async function fetchSupportedExchanges() {
  const res = await api.get("/exchanges/supported");
  return Array.isArray(res.data) ? res.data : [];
}

export function useRiskRulesQuery() {
  return useQuery({
    queryKey: ["settings", "risk-rules"],
    queryFn: fetchRiskRules,
  });
}

export function useEmailConfigQuery() {
  return useQuery({
    queryKey: ["settings", "email-config"],
    queryFn: fetchEmailConfig,
  });
}

export function useAppConfigQuery() {
  return useQuery({
    queryKey: ["settings", "app-config"],
    queryFn: fetchAppConfig,
  });
}

export function useSettingsExchangesQuery() {
  return useQuery({
    queryKey: ["settings", "exchanges"],
    queryFn: fetchSettingsExchanges,
  });
}

export function useSupportedExchangesQuery() {
  return useQuery({
    queryKey: ["settings", "supported-exchanges"],
    queryFn: fetchSupportedExchanges,
  });
}
