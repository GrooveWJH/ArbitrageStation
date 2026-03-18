import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  timeout: 20000,
});

api.interceptors.response.use(
  (res) => res,
  (error) => {
    if (!error?.response && error?.code === 'ECONNABORTED') {
      error.message = '请求超时，请检查后端或网络连接';
    }
    return Promise.reject(error);
  }
);

// Dashboard
export const getSummary = () => api.get('/dashboard/summary');
export const getFundingRates = (params) => api.get('/dashboard/funding-rates', { params });
export const getOpportunities = (params) => api.get('/dashboard/opportunities', { params });
export const getSpotOpportunities = (params) => api.get('/dashboard/spot-opportunities', { params });
export const getTradeLogs = (params) => api.get('/dashboard/trade-logs', { params });
export const getAccountOverview = () => api.get('/dashboard/account-overview');
export const getMarginStatus = () => api.get('/dashboard/margin-status');

// Exchanges
export const getSupportedExchanges = () => api.get('/exchanges/supported');
export const getExchanges = () => api.get('/exchanges/');
export const addExchange = (data) => api.post('/exchanges/', data);
export const updateExchange = (id, data) => api.put(`/exchanges/${id}`, data);
export const deleteExchange = (id) => api.delete(`/exchanges/${id}`);

// Trading
export const openStrategy = (data) => api.post('/trading/open', data);
export const closeStrategy = (id, data) => api.post(`/trading/close/${id}`, data);
export const getAutoTrade = () => api.get('/trading/auto-trade');
export const setAutoTrade = (enabled) => api.post(`/trading/auto-trade?enabled=${enabled}`);

// Settings - Risk Rules
export const getRiskRules = () => api.get('/settings/risk-rules');
export const createRiskRule = (data) => api.post('/settings/risk-rules', data);
export const updateRiskRule = (id, data) => api.put(`/settings/risk-rules/${id}`, data);
export const deleteRiskRule = (id) => api.delete(`/settings/risk-rules/${id}`);

// Settings - Email
export const getEmailConfig = () => api.get('/settings/email');
export const updateEmailConfig = (data) => api.put('/settings/email', data);
export const testEmail = () => api.post('/settings/email/test');

// Settings - App
export const getAppConfig = () => api.get('/settings/app');
export const updateAppConfig = (data) => api.put('/settings/app', data);

// Settings - Auto Trade Config
export const getAutoTradeConfig = () => api.get('/settings/auto-trade-config');
export const updateAutoTradeConfig = (data) => api.put('/settings/auto-trade-config', data);

// Analytics
export const getPnlAnalytics = (days) => api.get('/analytics/pnl', { params: { days } });
export const getEquityCurve = (days) => api.get('/analytics/equity', { params: { days } });
export const getPnlV2Summary = (daysOrParams) => {
  const params = (daysOrParams != null && typeof daysOrParams === 'object')
    ? daysOrParams
    : { days: daysOrParams };
  return api.get('/pnl/v2/summary', { params });
};
export const getPnlV2Strategies = (params) => api.get('/pnl/v2/strategies', { params: params || {} });
export const getPnlV2StrategyDetail = (id, params) => api.get(`/pnl/v2/strategies/${id}`, { params: params || {} });
export const getPnlV2Export = (params) => api.get('/pnl/v2/export', { params: params || {} });
export const getPnlV2ReconcileLatest = (limit = 7) => api.get('/pnl/v2/reconcile/latest', { params: { limit } });
export const runPnlV2FundingIngest = (params) => api.post('/pnl/v2/funding/ingest', null, { params: params || {} });

// AI Analyst
export const getAiAnalystLatest  = () => api.get('/ai-analyst/latest');
export const getAiAnalystHistory = (limit = 20) => api.get('/ai-analyst/history', { params: { limit } });
export const applyAiAdjustments  = (data) => api.post('/ai-analyst/apply', data);
export const getSpreadArbStats     = () => api.get('/spread-arb/stats');
export const getSpreadArbConfig    = () => api.get('/spread-arb/config');
export const updateSpreadArbConfig = (data) => api.put('/spread-arb/config', data);
export const getSpreadArbPositions = (status, limit) => api.get('/spread-arb/positions', { params: { status, limit } });
export const closeSpreadPosition   = (id) => api.post(`/spread-arb/close/${id}`);
export const setupHedgeMode        = () => api.post('/spread-arb/setup-hedge-mode');

// Spot-Basis Monitor (cross-exchange perp-short + spot-buy opportunities)
export const getSpotBasisOpportunities = (params) =>
  api.get('/spot-basis/opportunities', {
    timeout: 30000,
    params: params || {},
  });
export const getSpotBasisAutoDecisionPreview = (params) =>
  api.get('/spot-basis/auto-decision-preview', {
    timeout: 30000,
    params: params || {},
  });
export const getSpotBasisHistory = (params) => api.get('/spot-basis/history', { params });
export const getSpotBasisAutoConfig = () => api.get('/spot-basis/auto-config');
export const updateSpotBasisAutoConfig = (data) => api.put('/spot-basis/auto-config', data);
export const getSpotBasisAutoStatus = () => api.get('/spot-basis/auto-status');
export const setSpotBasisAutoStatus = (data) => api.put('/spot-basis/auto-status', data);
export const getSpotBasisAutoCycleLast = () => api.get('/spot-basis/auto-cycle-last');
export const getSpotBasisAutoCycleLogs = (params) => api.get('/spot-basis/auto-cycle-logs', { params: params || {} });
export const runSpotBasisAutoCycleOnce = () => api.post('/spot-basis/auto-cycle-run-once');
export const getSpotBasisDrawdownWatermark = () => api.get('/spot-basis/drawdown-watermark');
export const resetSpotBasisDrawdownWatermark = (data) => api.post('/spot-basis/drawdown-watermark/reset', data || {});

// Spot-Basis backtest data layer
export const freezeSpotBasisDataUniverse = (data) => api.post('/spot-basis-data/universe/freeze', data);
export const freezeSpotBasisDataUniverseToday = () => api.post('/spot-basis-data/universe/freeze-today');
export const listSpotBasisDataUniverse = (params) => api.get('/spot-basis-data/universe', { params });
export const createSpotBasisDataBackfillJob = (data) => api.post('/spot-basis-data/backfill', data);
export const getSpotBasisBacktestReadiness = (params) => api.get('/spot-basis-data/backtest-readiness', { params });
export const getSpotBasisDataAvailableRange = (params) => api.get('/spot-basis-data/available-range', { params });
export const importSpotBasisSnapshots = (data) => api.post('/spot-basis-data/import-snapshots', data);
export const importSpotBasisFunding = (data) => api.post('/spot-basis-data/import-funding', data);
export const createSpotBasisDataBacktestJob = (data) => api.post('/spot-basis-data/backtest', data);
export const createSpotBasisDataBacktestSearchJob = (data) => api.post('/spot-basis-data/backtest-search', data);
export const createSpotBasisDataExportJob = (data) => api.post('/spot-basis-data/export', data);
export const getSpotBasisDataJob = (jobId) => api.get(`/spot-basis-data/jobs/${jobId}`);
export const collectSpotBasisDataNow = (params) => api.post('/spot-basis-data/collect-now', null, { params });

// AI Agent
export const getAiAgentOverview   = () => api.get('/ai-agent/overview');
export const getAiAgentRounds     = () => api.get('/ai-agent/rounds');
export const getAiAgentDecisions  = (limit = 50, round_num) => api.get('/ai-agent/decisions', { params: { limit, round_num } });
export const getAiAgentTrades     = (status, round_num, limit = 50) => api.get('/ai-agent/trades', { params: { status, round_num, limit } });
export const getAiAgentSignals    = (limit = 100) => api.get('/ai-agent/signals', { params: { limit } });
export const getAiAgentLearnings  = () => api.get('/ai-agent/learnings');

// AI Agent - 子账号交易所
export const getAiAgentExchanges  = () => api.get('/ai-agent/exchanges');
export const addAiAgentExchange   = (data) => api.post('/ai-agent/exchanges', data);
export const updateAiAgentExchange = (id, data) => api.put(`/ai-agent/exchanges/${id}`, data);
export const deleteAiAgentExchange = (id) => api.delete(`/ai-agent/exchanges/${id}`);

// AI Agent - 资金 & 分析
export const getAiAgentBalances    = () => api.get('/ai-agent/balances');
export const getAiAgentPnlAnalysis = () => api.get('/ai-agent/pnl-analysis');
export const getAiAgentComboStats  = () => api.get('/ai-agent/combo-stats');

// AI Agent - 控制
export const getAiAgentStatus     = () => api.get('/ai-agent/status');
export const startAiAgent         = (data) => api.post('/ai-agent/start', data || {});
export const stopAiAgent          = () => api.post('/ai-agent/stop');
export const gracefulStopAiAgent  = () => api.post('/ai-agent/graceful-stop');
export const endAiAgentRound      = () => api.post('/ai-agent/end-round');
export const getAiAgentLogs       = (lines = 200) => api.get('/ai-agent/logs', { params: { lines } });


