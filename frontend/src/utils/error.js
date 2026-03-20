const readString = (value) => {
  if (typeof value !== "string") return "";
  const text = value.trim();
  return text;
};

const readMessageLike = (value) => {
  const direct = readString(value);
  if (direct) return direct;
  if (value && typeof value === "object") {
    const nested = readString(value.message);
    if (nested) return nested;
  }
  return "";
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

export function getApiErrorMessages(error, fallback = "Request failed") {
  const detailErrors = error?.response?.data?.detail?.errors;
  if (Array.isArray(detailErrors)) {
    const messages = detailErrors
      .map((item) => readMessageLike(item))
      .filter(Boolean);
    if (messages.length) return messages;
  }

  return [getApiErrorMessage(error, fallback)];
}
