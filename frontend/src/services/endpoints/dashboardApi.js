import api from "../httpClient";

export const getSummary = () => api.get("/dashboard/summary");
export const getFundingRates = (params) => api.get("/dashboard/funding-rates", { params });
export const getOpportunities = (params) => api.get("/dashboard/opportunities", { params });
export const getSpotOpportunities = (params) => api.get("/dashboard/spot-opportunities", { params });
export const getTradeLogs = (params) => api.get("/dashboard/trade-logs", { params });
export const getAccountOverview = () => api.get("/dashboard/account-overview");
export const getMarginStatus = () => api.get("/dashboard/margin-status");
