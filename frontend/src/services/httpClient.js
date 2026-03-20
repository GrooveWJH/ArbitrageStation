import axios from "axios";

const httpClient = axios.create({
  baseURL: "/api",
  timeout: 20000,
});

httpClient.interceptors.response.use(
  (res) => res,
  (error) => {
    if (!error?.response && error?.code === "ECONNABORTED") {
      error.message = "请求超时，请检查后端或网络连接";
    }
    return Promise.reject(error);
  },
);

export default httpClient;
