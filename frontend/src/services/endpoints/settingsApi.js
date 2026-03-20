import api from "../httpClient";

export const getRiskRules = () => api.get("/settings/risk-rules");
export const createRiskRule = (data) => api.post("/settings/risk-rules", data);
export const updateRiskRule = (id, data) => api.put(`/settings/risk-rules/${id}`, data);
export const deleteRiskRule = (id) => api.delete(`/settings/risk-rules/${id}`);
export const getEmailConfig = () => api.get("/settings/email");
export const updateEmailConfig = (data) => api.put("/settings/email", data);
export const testEmail = () => api.post("/settings/email/test");
export const getAppConfig = () => api.get("/settings/app");
export const updateAppConfig = (data) => api.put("/settings/app", data);
export const getAutoTradeConfig = () => api.get("/settings/auto-trade-config");
export const updateAutoTradeConfig = (data) => api.put("/settings/auto-trade-config", data);
