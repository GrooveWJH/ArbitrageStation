import { useEffect, useState } from 'react';

const priceStore = { data: {} };
const priceListeners = new Set();

export function updatePriceStore(data) {
  priceStore.data = data;
  priceListeners.forEach((fn) => fn());
}

export function usePriceDiff(symbol, longId, shortId) {
  const key = `${symbol}|${longId}|${shortId}`;
  const [data, setData] = useState(() => priceStore.data[key] || null);

  useEffect(() => {
    const handler = () => {
      const one = priceStore.data[key];
      if (one !== undefined) setData(one || null);
    };
    priceListeners.add(handler);
    return () => priceListeners.delete(handler);
  }, [key]);

  return data;
}
