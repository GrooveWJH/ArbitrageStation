const readString = (value) => {
  if (typeof value !== "string") return "";
  const text = value.trim();
  return text;
};

export function getApiErrorMessage(error, fallback = "Request failed") {
  const detail = error?.response?.data?.detail;
  if (detail && typeof detail === "object") {
    const detailMessage = readString(detail.message);
    if (detailMessage) return detailMessage;
  }

  const detailText = readString(detail);
  if (detailText) return detailText;

  const data = error?.response?.data;
  const dataMessage = readString(data?.message);
  if (dataMessage) return dataMessage;

  const dataError = readString(data?.error);
  if (dataError) return dataError;

  const rawData = readString(data);
  if (rawData) return rawData;

  const message = readString(error?.message);
  if (message) return message;

  return fallback;
}
