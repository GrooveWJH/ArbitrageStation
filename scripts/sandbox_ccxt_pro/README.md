# CCXT Pro Sandbox

该目录用于手动验证交易所接口与 WS 行情，不接入正式业务链路。

## 目录结构

```text
scripts/sandbox_ccxt_pro/
├─ cli/        # 交互式入口脚本（薄入口）
├─ jobs/       # 定时任务
├─ lib/        # 公共逻辑（common / marketdata / reporting）
├─ data/       # 运行产物（json 等）
└─ tools/      # 工程辅助脚本
```

## 目录黄金法则

1. 入口薄：`cli/` 和 `jobs/` 只做参数解析与调度。
2. 逻辑聚合：核心实现统一放 `lib/`，避免重复实现。
3. 产物隔离：运行输出统一写 `data/`，不污染源码目录。
4. 命名一致：脚本使用 `<domain>_<action>.py` 风格。

## 依赖

```bash
python3 -m pip install ccxt ccxtpro
```

## 环境变量

脚本通过 `.env` 读取密钥（不要提交真实密钥）：

- `BINANCE_API_KEY`, `BINANCE_API_SECRET`
- `GATE_API_KEY`, `GATE_API_SECRET`, `GATE_PASSWORD`
- `OKX_API_KEY`, `OKX_API_SECRET`, `OKX_PASSWORD`
- `MEXC_API_KEY`, `MEXC_API_SECRET`, `MEXC_PASSWORD`

```bash
cp scripts/sandbox_ccxt_pro/.env.example scripts/sandbox_ccxt_pro/.env
```

## 常用命令

WS 烟雾测试（热键 k 支持 btc/eth/both 切换）：

```bash
python3 scripts/sandbox_ccxt_pro/cli/ws_smoke.py
```

多交易所交集（spot && futures）：

```bash
python3 scripts/sandbox_ccxt_pro/cli/symbol_intersection.py \
  --exchanges binance okx gate mexc \
  --json \
  --out scripts/sandbox_ccxt_pro/data/symbols_intersection.json

# 双交集分组（每组独立求交集）
python3 scripts/sandbox_ccxt_pro/cli/symbol_intersection.py \
  --pair "binance&&okx" \
  --pair "gate&&mexc" \
  --json \
  --out scripts/sandbox_ccxt_pro/data/symbols_intersection.json
```

`symbols_intersection.json` 已升级为扁平 `v3`：

```json
{
  "schema_version": 3,
  "generated_at": "...",
  "mode": "single_group|grouped",
  "groups": [
    {
      "id": "all_4|pair_xxx",
      "exchanges": ["binance", "okx"],
      "symbols": ["BTC/USDT", "ETH/USDT"]
    }
  ],
  "meta": {
    "group_count": 1,
    "symbol_counts": {"all_4": 160}
  }
}
```

每 10 分钟扫描一次交集（空闲期带进度条）：

```bash
python3 scripts/sandbox_ccxt_pro/jobs/scan_symbols_intersection.py
```

负载均衡 orderbook 采集（Supervisor + Worker，默认 `both` = spot + futures）：

```bash
python3 scripts/sandbox_ccxt_pro/cli/binance_book_bandwidth.py

# 四个交易所同时启动（基于 data/symbols_intersection.json）
python3 scripts/sandbox_ccxt_pro/cli/binance_book_bandwidth.py --all

# 常用基础参数：symbols 文件、运行时长、交易所/市场、目标频率、输出文件
python3 scripts/sandbox_ccxt_pro/cli/binance_book_bandwidth.py --all \
  --symbols-file scripts/sandbox_ccxt_pro/data/symbols_intersection.json \
  --duration 40 \
  --max-wait 60 \
  --market both \
  --target-hz 2.0 \
  --metrics-out scripts/sandbox_ccxt_pro/data/metrics_snapshot.json
```

24x7 常驻服务（SQLite + HTTP + WebSocket）：

```bash
# 默认四所、spot+futures、写入 sqlite、对外提供本地 API
python3 scripts/sandbox_ccxt_pro/cli/marketdata_service.py serve

# 常见参数示例
python3 scripts/sandbox_ccxt_pro/cli/marketdata_service.py serve \
  --all \
  --market both \
  --target-hz 2.0 \
  --db-path scripts/sandbox_ccxt_pro/data/marketdata.sqlite3 \
  --metrics-out scripts/sandbox_ccxt_pro/data/metrics_snapshot.json

# 仅运行压缩维护循环
python3 scripts/sandbox_ccxt_pro/cli/marketdata_service.py compact-only
```

本地 API（默认 `127.0.0.1:18777`）：

- `GET /v1/health`
- `GET /v1/stats`
- `GET /v1/latest?exchange=&market=&symbol=&limit=`
- `GET /v1/series?exchange=binance&market=spot&symbol=BTC/USDT&resolution=raw&from_ms=...&to_ms=...`
- `GET /v1/symbols`
- `WS /ws/quotes?exchange=&market=&symbol=`

运行中会持续写出实时健康快照：

- `scripts/sandbox_ccxt_pro/data/metrics_snapshot.json`
- 结构包含 per-worker 与 per-symbol 指标（`hz_p50/hz_p95/error_rate/reconnects/bw_mbps`）
- 每个 worker 额外包含 symbols 统计字段：
  - `symbol_count_total`
  - `symbol_count_with_data`
  - `symbol_count_no_data`
  - `no_data_symbols`（从启动到当前未收到任何数据的 symbol 列表）
- `snapshot-mode`:
  - `full`: 每次写全量
  - `delta`: 只写变化较大的 worker/symbol 增量
  - `hybrid`(默认): 增量高频 + 30 秒全量
- 进度显示默认是原地刷新（`--live-refresh`），刷新频率默认 `5Hz`（`--refresh-hz`）

行数守卫（所有 `.py` 必须 `<300` 行）：

```bash
python3 scripts/sandbox_ccxt_pro/tools/check_max_lines.py
```
