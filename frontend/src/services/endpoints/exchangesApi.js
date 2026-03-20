import api from "../httpClient";

export const getSupportedExchanges = () => api.get("/exchanges/supported");
export const getExchanges = () => api.get("/exchanges/");
export const addExchange = (data) => api.post("/exchanges/", data);
export const updateExchange = (id, data) => api.put(`/exchanges/${id}`, data);
export const deleteExchange = (id) => api.delete(`/exchanges/${id}`);
