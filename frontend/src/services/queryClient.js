import { QueryClient } from "@tanstack/react-query";

function shouldRetry(error) {
  if (!error || typeof error !== "object") return true;
  const status = error?.response?.status;
  if (typeof status === "number" && status >= 400 && status < 500) return false;
  return true;
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => failureCount < 2 && shouldRetry(error),
      staleTime: 2000,
      gcTime: 5 * 60 * 1000,
      refetchOnWindowFocus: false,
      refetchOnReconnect: true,
    },
    mutations: {
      retry: 0,
    },
  },
});
