import api from "../httpClient";

export const getPnlAnalytics = (days) => api.get("/analytics/pnl", { params: { days } });
export const getEquityCurve = (days) => api.get("/analytics/equity", { params: { days } });
export const getPnlV2Summary = (daysOrParams) => {
  const params = daysOrParams != null && typeof daysOrParams === "object" ? daysOrParams : { days: daysOrParams };
  return api.get("/pnl/v2/summary", { params });
};
export const getPnlV2Strategies = (params) => api.get("/pnl/v2/strategies", { params: params || {} });
export const getPnlV2StrategyDetail = (id, params) => api.get(`/pnl/v2/strategies/${id}`, { params: params || {} });
export const getPnlV2Export = (params) => api.get("/pnl/v2/export", { params: params || {} });
export const getPnlV2ReconcileLatest = (limit = 7) => api.get("/pnl/v2/reconcile/latest", { params: { limit } });
export const runPnlV2FundingIngest = (params) => api.post("/pnl/v2/funding/ingest", null, { params: params || {} });
