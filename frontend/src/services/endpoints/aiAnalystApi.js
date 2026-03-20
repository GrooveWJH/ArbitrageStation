import api from "../httpClient";

export const getAiAnalystLatest = () => api.get("/ai-analyst/latest");
export const getAiAnalystHistory = (limit = 20) => api.get("/ai-analyst/history", { params: { limit } });
export const applyAiAdjustments = (data) => api.post("/ai-analyst/apply", data);
