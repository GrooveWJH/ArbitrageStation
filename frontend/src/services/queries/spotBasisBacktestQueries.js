import { useQuery } from "@tanstack/react-query";
import api from "../httpClient";

function isTerminalStatus(status) {
  const s = String(status || "").toLowerCase();
  return s === "succeeded" || s === "failed";
}

async function fetchSpotBasisDataJob(jobId) {
  const res = await api.get(`/spot-basis-data/jobs/${jobId}`);
  return res?.data?.job || null;
}

export function useSpotBasisDataJobQuery(jobId, enabled = true) {
  return useQuery({
    queryKey: ["spot-basis-data", "jobs", jobId],
    queryFn: () => fetchSpotBasisDataJob(jobId),
    enabled: Boolean(jobId) && enabled,
    refetchInterval: (query) => (isTerminalStatus(query.state.data?.status) ? false : 2000),
    refetchIntervalInBackground: true,
    retry: false,
  });
}
