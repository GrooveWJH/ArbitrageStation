import api from "../httpClient";

export const freezeSpotBasisDataUniverse = (data) => api.post("/spot-basis-data/universe/freeze", data);
export const freezeSpotBasisDataUniverseToday = () => api.post("/spot-basis-data/universe/freeze-today");
export const listSpotBasisDataUniverse = (params) => api.get("/spot-basis-data/universe", { params });
export const createSpotBasisDataBackfillJob = (data) => api.post("/spot-basis-data/backfill", data);
export const getSpotBasisBacktestReadiness = (params) => api.get("/spot-basis-data/backtest-readiness", { params });
export const getSpotBasisDataAvailableRange = (params) => api.get("/spot-basis-data/available-range", { params });
export const importSpotBasisSnapshots = (data) => api.post("/spot-basis-data/import-snapshots", data);
export const importSpotBasisFunding = (data) => api.post("/spot-basis-data/import-funding", data);
export const createSpotBasisDataBacktestJob = (data) => api.post("/spot-basis-data/backtest", data);
export const createSpotBasisDataBacktestSearchJob = (data) => api.post("/spot-basis-data/backtest-search", data);
export const createSpotBasisDataExportJob = (data) => api.post("/spot-basis-data/export", data);
export const getSpotBasisDataJob = (jobId) => api.get(`/spot-basis-data/jobs/${jobId}`);
export const collectSpotBasisDataNow = (params) => api.post("/spot-basis-data/collect-now", null, { params });
