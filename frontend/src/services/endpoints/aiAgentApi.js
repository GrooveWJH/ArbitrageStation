import api from "../httpClient";

export const getAiAgentOverview = () => api.get("/ai-agent/overview");
export const getAiAgentRounds = () => api.get("/ai-agent/rounds");
export const getAiAgentDecisions = (limit = 50, round_num) => api.get("/ai-agent/decisions", { params: { limit, round_num } });
export const getAiAgentTrades = (status, round_num, limit = 50) =>
  api.get("/ai-agent/trades", { params: { status, round_num, limit } });
export const getAiAgentSignals = (limit = 100) => api.get("/ai-agent/signals", { params: { limit } });
export const getAiAgentLearnings = () => api.get("/ai-agent/learnings");
export const getAiAgentExchanges = () => api.get("/ai-agent/exchanges");
export const addAiAgentExchange = (data) => api.post("/ai-agent/exchanges", data);
export const updateAiAgentExchange = (id, data) => api.put(`/ai-agent/exchanges/${id}`, data);
export const deleteAiAgentExchange = (id) => api.delete(`/ai-agent/exchanges/${id}`);
export const getAiAgentBalances = () => api.get("/ai-agent/balances");
export const getAiAgentPnlAnalysis = () => api.get("/ai-agent/pnl-analysis");
export const getAiAgentComboStats = () => api.get("/ai-agent/combo-stats");
export const getAiAgentStatus = () => api.get("/ai-agent/status");
export const startAiAgent = (data) => api.post("/ai-agent/start", data || {});
export const stopAiAgent = () => api.post("/ai-agent/stop");
export const gracefulStopAiAgent = () => api.post("/ai-agent/graceful-stop");
export const endAiAgentRound = () => api.post("/ai-agent/end-round");
export const getAiAgentLogs = (lines = 200) => api.get("/ai-agent/logs", { params: { lines } });
