from .leverage_margin import Any, Exchange, Optional, Session, _ASSET_USDT_PRICE_CACHE, _ASSET_USDT_PRICE_TTL_SECS, _STABLE_USD_ASSETS, _VIP0_TAKER_FEES, _balance_to_usdt_value, _binance_native_symbol, _build_ccxt_balance_from_binance_account, _check_and_mark_ban, _credential_signature, _crypto_symbol_cache, _ensure_cross_margin_mode, _exchange_ban_until, _exchange_cred_sig, _exchange_instances, _extract_balance_totals, _fee_cache, _fetch_ticker_last_price_cached, _is_binance_spot_451_error, _is_crypto_market, _is_missing_credential_error, _is_timestamp_error, _max_leverage_cache, _resolve_asset_usdt_price, _spot_cred_sig, _spot_instances, _time, _to_float, build_ccxt_instance, ccxt, extract_usdt_balance, fetch_exchange_total_equity_usdt, fetch_funding_income, fetch_max_leverage, fetch_spot_balance_safe, fetch_spot_volumes, fetch_taker_fee, get_instance, get_spot_instance, get_supported_exchanges, get_vip0_taker_fee, invalidate_instance, is_exchange_banned, logger, logging, mark_exchange_banned, re, resync_time_differences, set_leverage_for_symbol



def _ensure_gate_cross_margin_mode_strict(exchange: Exchange, inst, symbol: str, target_lev: int) -> bool:
    """Gate hard requirement: only allow order placement after cross margin is confirmed."""
    if not inst:
        return False

    def _iter_gate_dicts(payload: Any):
        stack = [payload]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                yield item
                for v in item.values():
                    if isinstance(v, (dict, list, tuple)):
                        stack.append(v)
            elif isinstance(item, (list, tuple)):
                for v in item:
                    if isinstance(v, (dict, list, tuple)):
                        stack.append(v)

    def _extract_cross_fields(payload: Any) -> tuple[Optional[str], Optional[str], Optional[str]]:
        leverage_raw = None
        cross_limit_raw = None
        margin_mode_raw = None
        for row in _iter_gate_dicts(payload):
            if leverage_raw is None and row.get("leverage") is not None:
                leverage_raw = str(row.get("leverage")).strip()
            if cross_limit_raw is None and row.get("cross_leverage_limit") is not None:
                cross_limit_raw = str(row.get("cross_leverage_limit")).strip()
            if margin_mode_raw is None:
                mm = row.get("marginMode")
                if mm is None:
                    mm = row.get("margin_mode")
                if mm is None:
                    mm = row.get("mode")
                if mm is None and row.get("cross_mode") is not None:
                    mm = "cross" if bool(row.get("cross_mode")) else "isolated"
                if mm is None and row.get("crossMode") is not None:
                    mm = "cross" if bool(row.get("crossMode")) else "isolated"
                if mm is not None:
                    margin_mode_raw = str(mm).strip().lower()
        return leverage_raw, cross_limit_raw, margin_mode_raw

    def _is_cross_signal(leverage_raw: Optional[str], cross_limit_raw: Optional[str], margin_mode_raw: Optional[str]) -> bool:
        def _to_num(v: Optional[str]) -> Optional[float]:
            if v is None:
                return None
            try:
                return float(str(v).strip())
            except Exception:
                return None

        if margin_mode_raw in ("cross", "crossed"):
            return True
        lev_num = _to_num(leverage_raw)
        if lev_num is not None and abs(lev_num) < 1e-9:
            return True
        lim_num = _to_num(cross_limit_raw)
        if lim_num is not None and abs(lim_num - float(lev)) < 1e-9:
            return True
        return False

    try:
        lev = int(target_lev) if int(target_lev) > 0 else 1
        resp = None
        set_errors: list[str] = []
        # Gate API v4 cross mode semantics:
        # leverage=0 means cross margin, cross_leverage_limit controls max leverage.
        # Try this path first (strict full-cross requirement).
        for params in (
            {"cross_leverage_limit": str(lev)},
            {"margin_mode": "cross", "cross_leverage_limit": str(lev)},
            {"marginMode": "cross", "cross_leverage_limit": str(lev)},
            {"mode": "cross", "cross_leverage_limit": str(lev)},
        ):
            try:
                resp = inst.set_leverage(0, symbol, params=params)
                break
            except Exception as se:
                set_errors.append(f"lev=0 {se}")
        # Legacy fallback for wrappers that still require positive leverage arg.
        for params in (
            {"cross_leverage_limit": str(lev)},
            {"marginMode": "cross", "cross_leverage_limit": str(lev)},
            {"margin_mode": "cross", "cross_leverage_limit": str(lev)},
        ):
            if resp is not None:
                break
            try:
                resp = inst.set_leverage(lev, symbol, params=params)
                break
            except Exception as se:
                set_errors.append(f"lev={lev} {se}")
        if resp is None and set_errors:
            raise RuntimeError(set_errors[-1])

        leverage_raw, cross_limit_raw, margin_mode_raw = _extract_cross_fields(resp)
        cross_ok = _is_cross_signal(leverage_raw, cross_limit_raw, margin_mode_raw)
        saw_non_cross = margin_mode_raw in ("isolated", "fixed")

        if (not cross_ok) and (inst.has or {}).get("fetchPosition"):
            try:
                pos = inst.fetch_position(symbol)
                pos_lev, pos_cross_lim, pos_margin_mode = _extract_cross_fields(pos)
                if pos_margin_mode in ("isolated", "fixed"):
                    saw_non_cross = True
                cross_ok = cross_ok or _is_cross_signal(pos_lev, pos_cross_lim, pos_margin_mode)
            except Exception as pe:
                logger.warning(f"[hedge_order] Gate {symbol}: cross verify by fetch_position failed: {pe}")

        if (not cross_ok) and (inst.has or {}).get("fetchPositions"):
            try:
                positions = inst.fetch_positions([symbol]) or []
                for pos in positions:
                    pos_lev, pos_cross_lim, pos_margin_mode = _extract_cross_fields(pos)
                    if pos_margin_mode in ("isolated", "fixed"):
                        saw_non_cross = True
                    if _is_cross_signal(pos_lev, pos_cross_lim, pos_margin_mode):
                        cross_ok = True
                        break
            except Exception as pe:
                logger.warning(f"[hedge_order] Gate {symbol}: cross verify by fetch_positions failed: {pe}")

        if (not cross_ok) and (not saw_non_cross):
            # Gate unified account can return sparse leverage payloads. If cross was requested
            # and no isolated signal is observed, allow order placement.
            logger.warning(
                f"[hedge_order] Gate {symbol}: cross verify unavailable, proceeding with strict cross params "
                f"(leverage={leverage_raw}, cross_leverage_limit={cross_limit_raw}, margin_mode={margin_mode_raw})"
            )
            cross_ok = True

        if not cross_ok:
            logger.error(
                f"[hedge_order] Gate {symbol}: hard-cross check failed "
                f"(leverage={leverage_raw}, cross_leverage_limit={cross_limit_raw}, margin_mode={margin_mode_raw})"
            )
            return False
        logger.info(f"[hedge_order] Gate {symbol}: cross-margin confirmed (limit={lev}x)")
        return True
    except Exception as e:
        logger.error(f"[hedge_order] Gate {symbol}: hard-cross setup failed: {e}")
        return False


def _extract_interval_hours(info: dict) -> float | None:
    """Extract funding interval (hours) from a CCXT funding-rate response dict."""
    # 1. CCXT normalized field (some exchanges)
    v = info.get("fundingInterval")
    if v:
        try: return float(v)
        except Exception: pass

    # 2. Binance raw info: fundingIntervalHours
    raw = info.get("info") or {}
    v = raw.get("fundingIntervalHours")
    if v:
        try: return float(v)
        except Exception: pass

    # 3. Derive from next - prev settlement timestamps (OKX, Bybit, etc.)
    # CCXT exposes nextFundingTimestamp (ms) = next settlement
    # OKX raw info.fundingTime (ms) = previous settlement
    nft_ms = info.get("fundingTimestamp") or info.get("nextFundingTimestamp")
    pft_ms = raw.get("fundingTime") or raw.get("prevFundingTimestamp")
    if nft_ms and pft_ms:
        try:
            hours = (float(nft_ms) - float(pft_ms)) / 3_600_000
            if 0.25 <= hours <= 24:
                return hours
        except Exception:
            pass

    return None
