# Marketdata Service API 文档

适用程序：`scripts/sandbox_ccxt_pro/cli/marketdata_service.py serve`

- 默认地址：`http://127.0.0.1:18777`
- OpenAPI UI：`http://127.0.0.1:18777/docs`
- ReDoc：`http://127.0.0.1:18777/redoc`

## 1. 启动与基础检查

```bash
python scripts/sandbox_ccxt_pro/cli/marketdata_service.py serve --all --market both
curl -s http://127.0.0.1:18777/v1/health | jq
```

服务读取的 symbols 文件为 `schema_version=3` 扁平结构（`groups`）：

```json
{
  "schema_version": 3,
  "generated_at": "...",
  "mode": "single_group|grouped",
  "groups": [
    {"id": "all_4", "exchanges": ["binance", "okx", "gate", "mexc"], "symbols": ["BTC/USDT", "ETH/USDT"]}
  ],
  "meta": {"group_count": 1, "symbol_counts": {"all_4": 2}}
}
```

## 2. 接口总览

### `GET /v1/health`
服务健康与运行摘要（轻量）。

主要字段：
- `ok`：服务进程是否存活
- `collector_boot_state`：`idle/starting/ready/error/cancelled`
- `workers_view`：worker 启动/就绪概览
  - `expected_workers_total`
  - `reported_workers_total`
  - `up_workers_total`
  - `up_workers[]` / `down_workers[]`
  - `up_markets_by_exchange`
- `queue_size`：写入队列长度
- `writer`：写入统计（events/bytes/batches/dropped/coalesced）
- `db`：数据库体积与压缩状态
- `workers`：每个 worker 轻量指标（不含 symbols 明细）
  - `symbol_count_total`
  - `symbol_count_with_data`
  - `symbol_count_no_data`

示例：
```bash
curl -s http://127.0.0.1:18777/v1/health | jq '.workers_view'
```

判断“全部市场已启动”：
```bash
curl -s http://127.0.0.1:18777/v1/health | jq '.workers_view.up_workers_total == .workers_view.expected_workers_total'
```

判断“所有 worker 都有数据覆盖”：
```bash
curl -s http://127.0.0.1:18777/v1/health | jq '[.workers[] | select(.symbol_count_no_data == 0)] | length'
```

---

### `GET /v1/stats`
完整快照（比 health 更详细，含 `global` + `workers`）。

示例：
```bash
curl -s http://127.0.0.1:18777/v1/stats | jq '.global'
```

低频相关字段（`global`）：
- `funding_last_pull_ms / funding_pull_errors / funding_coverage_ratio`
- `volume_last_pull_ms / volume_pull_errors / volume_coverage_ratio`
- `opportunity_snapshot_last_ms / opportunity_items`
- `funding_stale / volume_stale / opportunity_stale`

---

### `GET /v1/latest`
读取最新行情快照（来自 `latest_quote`）。

查询参数：
- `exchange`（可选）
- `market`（可选，`spot` 或 `futures`）
- `symbol`（可选，如 `BTC/USDT`）
- `limit`（可选，默认 500，范围 1~5000）

示例：
```bash
curl -s "http://127.0.0.1:18777/v1/latest?exchange=binance&market=spot&symbol=BTC/USDT&limit=5" | jq
```

返回：
- `count`
- `rows[]`：
  - `exchange, market, symbol`
  - `ts_exchange_ms, ts_recv_ms`
  - `bid1, ask1, mid, spread_bps, payload_bytes`

---

### `GET /v1/series`
读取历史序列（分辨率层）。

必填参数：
- `exchange`
- `market`
- `symbol`
- `from_ms`
- `to_ms`

可选参数：
- `resolution`：`raw | 1s | 10s | 60s`（默认 `raw`）
- `limit`：默认 2000，范围 1~10000

示例（最近 10 分钟 raw）：
```bash
FROM=$(python - <<'PY'
import time
print(int((time.time()-600)*1000))
PY
)
TO=$(python - <<'PY'
import time
print(int(time.time()*1000))
PY
)
curl -s "http://127.0.0.1:18777/v1/series?exchange=binance&market=spot&symbol=BTC/USDT&resolution=raw&from_ms=$FROM&to_ms=$TO&limit=1000" | jq '.count'
```

`raw` 返回字段：
- `bucket_ms`（即接收时间）
- `bid1, ask1, mid, spread_bps, payload_bytes`

聚合层（`1s/10s/60s`）返回字段：
- `bucket_ms`
- `open_mid, high_mid, low_mid, close_mid`
- `avg_spread_bps, samples, bytes_sum`

---

### `GET /v1/symbols`
返回当前 `latest_quote` 中出现过的交易对。

示例：
```bash
curl -s http://127.0.0.1:18777/v1/symbols | jq
```

返回：
- `count`
- `symbols[]`

---

### `GET /v1/funding/latest`
读取最新 funding 快照（仅 futures 数据）。

查询参数：
- `exchange`（可选）
- `symbol`（可选，如 `BTC/USDT`）
- `limit`（默认 500，范围 1~5000）

示例：
```bash
curl -s "http://127.0.0.1:18777/v1/funding/latest?exchange=binance&limit=5" | jq
```

返回：
- `count`
- `rows[]`：`exchange, symbol, funding_rate, next_funding_ts_ms, updated_at_ms`

---

### `GET /v1/volume/latest`
读取最新 24h 成交额快照（spot + futures）。

查询参数：
- `exchange`（可选）
- `market`（可选，`spot` 或 `futures`）
- `symbol`（可选）
- `limit`（默认 500，范围 1~5000）

示例：
```bash
curl -s "http://127.0.0.1:18777/v1/volume/latest?exchange=okx&market=futures&limit=5" | jq
```

返回：
- `count`
- `rows[]`：`exchange, market, symbol, volume_24h_quote, updated_at_ms`

---

### `GET /v1/opportunity-inputs`
读取内存聚合的机会输入快照（`quote + funding + volume`）。

查询参数：
- `exchange`（可选）
- `market`（可选，`spot` 或 `futures`）
- `symbol`（可选）
- `limit`（默认 500，范围 1~5000）

示例：
```bash
curl -s "http://127.0.0.1:18777/v1/opportunity-inputs?exchange=binance&limit=10" | jq
```

返回：
- `count`
- `rows[]`：`exchange, market, symbol, bid1, ask1, mid, spread_bps, funding_rate, volume_24h_quote, freshness_sec, coverage, ts_recv_ms`
- `source=memory`

---

### `WS /ws/quotes`
实时推送最新 quote。

可选过滤 query：
- `exchange`
- `market`
- `symbol`

消息类型：
- `{"type":"quote","data":{...}}`
- `{"type":"heartbeat","ts":...}`（空闲心跳）

`quote.data` 字段：
- `exchange, market, symbol`
- `exchange_ts_ms, recv_ts_ms`
- `bid1, ask1, mid, spread_bps, payload_bytes`

测试（需要 `websocat`）：
```bash
websocat "ws://127.0.0.1:18777/ws/quotes?exchange=binance&market=spot&symbol=BTC/USDT"
```

## 3. 常见排查

1. `collector_boot_state` 长时间 `starting`
- 说明某些交易所 worker 还在冷启动或连接失败。
- 看 `workers_view.down_workers` 定位具体 `exchange:market`。

2. `workers` 中 `symbol_count_no_data` 很大
- 说明该 worker 的部分 symbol 尚未收到任何推送。
- 先验证网络连通和对应交易所限流情况。

3. `queue_size` 持续上升
- 写入速度跟不上采集速度。
- 可调大 `--write-batch-size`，或减小订阅规模。

4. `dropped_events/coalesced_events` 增长
- 队列发生背压，已启用降压策略。
- 若长期增长，建议降频/分片/减少 symbols。

5. 低频字段长期 stale
- `funding_stale=true`：通常是 futures 拉取失败或交易所限流。
- `volume_stale=true`：通常是 24h ticker 拉取失败。
- `opportunity_stale=true`：通常是上游 quote/funding/volume 任一链路卡住。
