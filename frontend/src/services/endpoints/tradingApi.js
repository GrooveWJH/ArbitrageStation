import api from "../httpClient";

export const openStrategy = (data) => api.post("/trading/open", data);
export const closeStrategy = (id, data) => api.post(`/trading/close/${id}`, data);
export const getAutoTrade = () => api.get("/trading/auto-trade");
export const setAutoTrade = (enabled) => api.post(`/trading/auto-trade?enabled=${enabled}`);
