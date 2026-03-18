export function buildSearchPayload(searchParams, parseNumberList) {
  return {
    start_date: searchParams.start_date,
    end_date: searchParams.end_date,
    days: searchParams.days,
    top_n: searchParams.top_n,
    initial_nav_usd: searchParams.initial_nav_usd,
    min_rate_pct: searchParams.min_rate_pct,
    min_perp_volume: searchParams.min_perp_volume,
    min_spot_volume: searchParams.min_spot_volume,
    min_basis_pct: searchParams.min_basis_pct,
    require_cross_exchange: !!searchParams.require_cross_exchange,
    hold_conf_min: searchParams.hold_conf_min,
    max_exchange_utilization_pct: searchParams.max_exchange_utilization_pct,
    max_symbol_utilization_pct: searchParams.max_symbol_utilization_pct,
    min_capacity_pct: searchParams.min_capacity_pct,
    switch_min_advantage: searchParams.switch_min_advantage,
    portfolio_dd_hard_pct: searchParams.portfolio_dd_hard_pct,
    data_stale_max_buckets: searchParams.data_stale_max_buckets,
    train_days: searchParams.train_days,
    test_days: searchParams.test_days,
    step_days: searchParams.step_days,
    train_top_k: searchParams.train_top_k,
    max_trials: searchParams.max_trials,
    random_seed: searchParams.random_seed,
    enter_score_threshold_values: parseNumberList(searchParams.enter_score_threshold_values, false),
    entry_conf_min_values: parseNumberList(searchParams.entry_conf_min_values, false),
    max_open_pairs_values: parseNumberList(searchParams.max_open_pairs_values, true),
    target_utilization_pct_values: parseNumberList(searchParams.target_utilization_pct_values, false),
    min_pair_notional_usd_values: parseNumberList(searchParams.min_pair_notional_usd_values, false),
    max_impact_pct_values: parseNumberList(searchParams.max_impact_pct_values, false),
    switch_confirm_rounds_values: parseNumberList(searchParams.switch_confirm_rounds_values, true),
    rebalance_min_relative_adv_pct_values: parseNumberList(searchParams.rebalance_min_relative_adv_pct_values, false),
    rebalance_min_absolute_adv_usd_day_values: parseNumberList(searchParams.rebalance_min_absolute_adv_usd_day_values, false),
  };
}

export function buildAutoConfigPatch(recommended, searchParams, num) {
  const rec = recommended?.params;
  if (!rec) return null;
  return {
    enter_score_threshold: num(rec.enter_score_threshold, 0),
    entry_conf_min: num(rec.entry_conf_min, 0.55),
    max_open_pairs: Math.max(1, Math.trunc(num(rec.max_open_pairs, 5))),
    target_utilization_pct: Math.max(1, num(rec.target_utilization_pct, 60)),
    min_pair_notional_usd: Math.max(1, num(rec.min_pair_notional_usd, 300)),
    max_impact_pct: Math.max(0.01, num(rec.max_impact_pct, 0.3)),
    switch_confirm_rounds: Math.max(1, Math.trunc(num(rec.switch_confirm_rounds, 3))),
    rebalance_min_relative_adv_pct: Math.max(0, num(rec.rebalance_min_relative_adv_pct, 5)),
    rebalance_min_absolute_adv_usd_day: Math.max(0, num(rec.rebalance_min_absolute_adv_usd_day, 0.5)),
    hold_conf_min: Math.max(0, Math.min(1, num(searchParams.hold_conf_min, 0.45))),
    switch_min_advantage: Math.max(0, num(searchParams.switch_min_advantage, 5)),
    max_exchange_utilization_pct: Math.max(1, num(searchParams.max_exchange_utilization_pct, 35)),
    max_symbol_utilization_pct: Math.max(1, num(searchParams.max_symbol_utilization_pct, 10)),
    min_capacity_pct: Math.max(0, num(searchParams.min_capacity_pct, 12)),
    portfolio_dd_hard_pct: num(searchParams.portfolio_dd_hard_pct, -4),
  };
}
