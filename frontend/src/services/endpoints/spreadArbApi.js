import api from "../httpClient";

export const getSpreadArbStats = () => api.get("/spread-arb/stats");
export const getSpreadArbConfig = () => api.get("/spread-arb/config");
export const updateSpreadArbConfig = (data) => api.put("/spread-arb/config", data);
export const getSpreadArbPositions = (status, limit) => api.get("/spread-arb/positions", { params: { status, limit } });
export const closeSpreadPosition = (id) => api.post(`/spread-arb/close/${id}`);
export const setupHedgeMode = () => api.post("/spread-arb/setup-hedge-mode");
