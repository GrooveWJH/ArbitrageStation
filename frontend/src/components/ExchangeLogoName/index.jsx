import React from 'react';
import binanceLogo from '../../assets/exchanges/binance.svg';
import gateLogo from '../../assets/exchanges/gate.svg';
import mexcLogo from '../../assets/exchanges/mexc.png';
import okxLogo from '../../assets/exchanges/okx.png';

const LOGO_MAP = {
  binance: binanceLogo,
  gate: gateLogo,
  mexc: mexcLogo,
  okx: okxLogo,
};

const EXCHANGE_ALIASES = {
  binance: 'binance',
  okx: 'okx',
  mexc: 'mexc',
  gate: 'gate',
  gateio: 'gate',
  'gate.io': 'gate',
};

function normalizeToken(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '')
    .replace(/_/g, '')
    .replace(/-/g, '');
}

export function resolveExchangeLogoKey(name, exchangeId) {
  const candidates = [exchangeId, name];
  for (const candidate of candidates) {
    if (candidate == null) continue;
    const raw = String(candidate).trim().toLowerCase();
    if (!raw) continue;
    const normalized = normalizeToken(raw);
    const aliasHit = EXCHANGE_ALIASES[raw] || EXCHANGE_ALIASES[normalized];
    if (aliasHit) return aliasHit;
    if (normalized in LOGO_MAP) return normalized;
  }
  return null;
}

export default function ExchangeLogoName({
  name,
  exchangeId = null,
  suffix = '',
  className = '',
}) {
  const displayName = String(name || exchangeId || 'UNKNOWN');
  const key = resolveExchangeLogoKey(displayName, exchangeId);
  const logo = key ? LOGO_MAP[key] : null;
  const fullLabel = suffix ? `${displayName} ${suffix}` : displayName;

  return (
    <span
      className={`kinetic-exchange-identity ${className}`.trim()}
      data-exchange-key={key || 'unknown'}
      data-has-logo={logo ? 'true' : 'false'}
      title={fullLabel}
    >
      {logo ? (
        <img className="kinetic-exchange-logo" src={logo} alt={`${displayName} logo`} />
      ) : (
        <span className="kinetic-exchange-logo-fallback" aria-hidden />
      )}
      <span className="kinetic-exchange-name">{displayName}</span>
      {suffix ? <span className="kinetic-exchange-suffix">{suffix}</span> : null}
    </span>
  );
}
