import api from "../httpClient";

export const getSpotBasisOpportunities = (params) =>
  api.get("/spot-basis/opportunities", { timeout: 30000, params: params || {} });
export const getSpotBasisAutoDecisionPreview = (params) =>
  api.get("/spot-basis/auto-decision-preview", { timeout: 30000, params: params || {} });
export const getSpotBasisHistory = (params) => api.get("/spot-basis/history", { params });
export const getSpotBasisAutoConfig = () => api.get("/spot-basis/auto-config");
export const updateSpotBasisAutoConfig = (data) => api.put("/spot-basis/auto-config", data);
export const getSpotBasisAutoStatus = () => api.get("/spot-basis/auto-status");
export const setSpotBasisAutoStatus = (data) => api.put("/spot-basis/auto-status", data);
export const getSpotBasisAutoCycleLast = () => api.get("/spot-basis/auto-cycle-last");
export const getSpotBasisAutoCycleLogs = (params) => api.get("/spot-basis/auto-cycle-logs", { params: params || {} });
export const runSpotBasisAutoCycleOnce = () => api.post("/spot-basis/auto-cycle-run-once");
export const getSpotBasisDrawdownWatermark = () => api.get("/spot-basis/drawdown-watermark");
export const resetSpotBasisDrawdownWatermark = (data) => api.post("/spot-basis/drawdown-watermark/reset", data || {});
