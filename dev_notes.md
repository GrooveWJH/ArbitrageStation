# 濂楀埄浜ゆ槗宸ュ叿 - 寮€鍙戣繘搴﹁褰?
## 椤圭洰姒傝堪

鏈湴杩愯鐨勫姞瀵嗚揣甯佽祫閲戣垂鐜囧鍒╁伐鍏凤紝鏀寔澶氫氦鏄撴墍鐩戞帶銆佸叏鑷姩寮€骞充粨銆侀鎺х鐞嗗拰閭欢閫氱煡銆?
---

## 褰撳墠杩涘害锛氬姛鑳藉畬鏁达紝鍙甯镐娇鐢?
---

## 宸插畬鎴愭ā鍧?
### 鍚庣 (Python + FastAPI)

| 鏂囦欢 | 璇存槑 |
|------|------|
| `main.py` | 搴旂敤鍏ュ彛锛孉PScheduler 璋冨害锛堟暟鎹噰闆?0s銆侀鎺?0s銆佽嚜鍔ㄤ氦鏄?0s锛?|
| `models/database.py` | 鏁版嵁搴撴ā鍨嬶細Exchange銆丼trategy銆丳osition銆丗undingRate銆乀radeLog銆丷iskRule銆丒mailConfig銆丄ppConfig銆?*AutoTradeConfig**銆?*EquitySnapshot** |
| `core/exchange_manager.py` | CCXT 灏佽锛屾敮鎸?100+ 浜ゆ槗鎵€锛孉PI Key 绠＄悊 |
| `core/data_collector.py` | 瀹氭椂閲囬泦璧勯噾璐圭巼 + 鏇存柊鎸佷粨浠锋牸锛屽唴瀛樼紦瀛橈紙funding_rate_cache銆乿olume_cache銆乫ast_price_cache锛?|
| `core/equity_collector.py` | **鏂?*锛氭瘡4灏忔椂閲囬泦鎵€鏈変氦鏄撴墍USDT璧勪骇鎬婚噺锛屽瓨鍏?EquitySnapshot 琛?|
| `core/arbitrage_engine.py` | 濂楀埄鏈轰細鎵弿锛氳法鎵€濂楀埄锛坒ind_opportunities锛? 鐜拌揣瀵瑰啿锛坒ind_spot_hedge_opportunities锛?|
| `core/risk_manager.py` | 椋庢帶寮曟搸锛屾敮鎸?5 绉嶈鍒欑被鍨嬶紝鍏ㄩ儴宸插疄鐜?|
| `core/auto_trade_engine.py` | **鍏ㄨ嚜鍔ㄤ氦鏄撳紩鎿?*锛堟柊锛夛紝姣?30 绉掓壂鎻忥紝鍚叆鍦?鍑哄満閫昏緫 |
| `strategies/cross_exchange.py` | 璺ㄦ墍濂楀埄绛栫暐锛欰 鎵€鍋氬 + B 鎵€鍋氱┖ |
| `strategies/spot_hedge.py` | 鐜拌揣瀵瑰啿绛栫暐锛氱幇璐т拱鍏?+ 姘哥画鍋氱┖ |
| `services/email_service.py` | SMTP 閭欢閫氱煡锛圚TML 鏍煎紡锛?|
| `api/exchanges.py` | 浜ゆ槗鎵€澧炲垹鏀规煡 |
| `api/dashboard.py` | 鐪嬫澘鏁版嵁锛堟眹鎬汇€佽垂鐜囥€佹満浼氥€佺瓥鐣ャ€佹棩蹇楋級 |
| `api/trading.py` | 鎵嬪姩寮€浠?骞充粨鎺ュ彛 |
| `api/settings.py` | 椋庢帶瑙勫垯 CRUD銆侀偖浠堕厤缃€佸簲鐢ㄩ厤缃€?*鑷姩浜ゆ槗閰嶇疆** CRUD |
| `api/websocket.py` | WebSocket 瀹炴椂鎺ㄩ€侊紙璐圭巼+鏈轰細姣?绉掞紝浠峰樊姣?绉掞級 |

### 鍓嶇 (React + Ant Design)

| 椤甸潰 | 璇存槑 |
|------|------|
| `pages/Dashboard` | 鎬昏鐪嬫澘锛? 椤圭粺璁?+ 濂楀埄鏈轰細琛?+ 鐜拌揣瀵瑰啿鏈轰細琛?+ 浜ゆ槗鏃ュ織 |
| `pages/FundingRates` | 璧勯噾璐圭巼鐩戞帶锛氭寜浜ゆ槗瀵?鏈€灏忚垂鐜?24h鎴愪氦閲?浜ゆ槗鎵€绛涢€夛紝WebSocket 瀹炴椂鍒锋柊 |
| `pages/Positions` | 绛栫暐绠＄悊锛氬紑绛栫暐锛堝姩鎬佽〃鍗曞尯鍒嗚法鎵€/鐜拌揣瀵瑰啿锛夈€佸揩閫熷～鍏ユ満浼氥€佹墜鍔ㄥ钩浠撱€佽鎯?|
| `pages/Settings` | 閰嶇疆涓績锛?涓瓙妯″潡 |

Settings 瀛愭ā鍧楋細
- **鑷姩浜ゆ槗绛栫暐**锛堟柊锛岀涓€涓?tab锛夛細鍏ュ満/鍑哄満/浠撲綅鍏ㄩ儴鍙傛暟閰嶇疆锛屼氦鏄撴墍绛涢€?- **椋庢帶瑙勫垯**锛氬彲瑙嗗寲澧炲垹鏀癸紝5 绉嶈鍒欑被鍨嬪叏閮ㄦ湁鏁?- **浜ゆ槗鎵€绠＄悊**锛氫粠 100+ 鏀寔涓坊鍔?鍒犻櫎/閰嶇疆 API Key
- **閭欢閫氱煡**锛歋MTP 閰嶇疆 + 娴嬭瘯鍙戦€?- **搴旂敤閰嶇疆**锛氬埛鏂伴棿闅斻€侀鎺ч棿闅斻€佽嚜鍔ㄤ氦鏄撴€诲紑鍏?
### 閮ㄧ讲
- `start.bat` 鈥?Windows 涓€閿惎鍔紙鑷姩瀹夎渚濊禆锛屽垎鍒惎鍔ㄥ墠鍚庣锛?
---

## 鑷姩浜ゆ槗寮曟搸璁捐

### 鍏ュ満閫昏緫锛堟瘡 30 绉掓鏌ワ級
鍚屾椂婊¤冻浠ヤ笅鍏ㄩ儴鏉′欢鎵嶅紑浠擄細

1. 璺濅笅娆¤祫閲戣垂鐜囩粨绠?鈮?N 鍒嗛挓锛堥粯璁?10 鍒嗛挓锛?2. 骞村寲鏀剁泭 鈮?鏈€浣庨槇鍊硷紙榛樿 20%锛?3. 浠峰樊鏉′欢锛?   - 璺ㄦ墍锛?绌哄ご鎵€浠锋牸 - 澶氬ご鎵€浠锋牸) / 澶氬ご鎵€浠锋牸 鈮?max_entry_spread_pct锛堥粯璁?-0.1%锛?   - 鐜拌揣瀵瑰啿锛?鍚堢害浠锋牸 - 鐜拌揣浠锋牸) / 鐜拌揣浠锋牸 鈮?min_entry_basis_pct锛堥粯璁?0%锛?4. 鍚屼竴浜ゆ槗瀵?浜ゆ槗鎵€缁勫悎鏃犻噸澶嶈繍琛屼腑绛栫暐
5. 璇ュ涓婃鍏抽棴鍚?10 鍒嗛挓鍐峰嵈鏈熷凡杩?
### 鍑哄満閫昏緫
- **绛夊緟鏀惰垂**锛氬紑浠撴椂闂?> 鍏ュ満鍒嗛挓鏁?+ 2 鍒嗛挓缂撳啿鍚庡紑濮嬫娴?- **姝ｅ父鍑哄満**锛殀褰撳墠浠峰樊| 鈮?exit_spread_threshold_pct锛堥粯璁?0.05%锛?- **寮哄埗鍑哄満**锛氭敹璐瑰悗鎸佷粨瓒呰繃 max_hold_minutes锛堥粯璁?60 鍒嗛挓锛?
### 璇嗗埆瑙勫垯
- 鑷姩寮€浠撶殑绛栫暐鍚嶇О浠?`[AUTO] ` 寮€澶?- 鍑哄満閫昏緫鍙鐞?`[AUTO]` 绛栫暐锛涙墜鍔ㄥ紑浠撶殑浠撲綅涓嶅彈褰卞搷

### 浠撲綅鏂规鍙傝€?
| 椋庢牸 | 妯″紡 | 鍩哄噯閲戦 | 鍗曠瑪涓婇檺 | 鏈€澶氭寔浠?| 鏈€浣庡勾鍖?|
|------|------|---------|---------|---------|---------|
| 淇濆畧 | 鍥哄畾 | $200 | $200 | 3 | 30% |
| 鍧囪　 | 鍔ㄦ€?| $300 | $1500 | 5 | 30% |
| 婵€杩?| 鍔ㄦ€?| $500 | $3000 | 8 | 20% |

鍔ㄦ€佹ā寮忚绠楀叕寮忥細
- scale = clamp(骞村寲 / 50%, 0.5x, 3x)
- vol_cap = 24h鎴愪氦閲?脳 volume_cap_pct%
- 鏈€缁堜粨浣?= min(鍩哄噯 脳 scale, vol_cap, 鍗曠瑪涓婇檺)

---

## 椋庢帶瑙勫垯锛堝叏閮?5 绉嶇被鍨嬪潎宸插疄鐜帮級

| 瑙勫垯绫诲瀷 | 瑙﹀彂鏉′欢 | 鍔ㄤ綔 |
|---------|---------|------|
| `loss_pct` | 绛栫暐浜忔崯 鈮?闃堝€? | close_position / alert_only |
| `max_position_usd` | 鍗曚粨浣嶅競鍊?鈮?闃堝€?USD | close_position / alert_only |
| `max_exposure_usd` | 鎵€鏈変粨浣嶆€绘暈鍙?鈮?闃堝€?USD | close_position / alert_only |
| `min_rate_diff` | 褰撳墠璐圭巼宸?< 闃堝€?锛堝鍒╂満浼氭秷澶憋級 | close_position / alert_only |
| `max_leverage` | 鏈夋晥鏉犳潌鍊嶆暟 鈮?闃堝€?| close_position / alert_only |

榛樿棰勭疆锛?*浜忔崯 鈮?80% 鈫?绔嬪嵆鍏ㄥ钩 + 鍙戦偖浠?*

---

## 鏈湴杩愯鍦板潃

| 鏈嶅姟 | 鍦板潃 |
|------|------|
| 鍓嶇鐣岄潰 | http://localhost:3000 |
| 鍚庣 API 鏂囨。 | http://localhost:8000/docs |

---

## 鎶€鏈爤

| 灞傜骇 | 鎶€鏈?|
|------|------|
| 鍚庣妗嗘灦 | Python 3.11 + FastAPI |
| 浜ゆ槗鎵€ SDK | CCXT锛堟敮鎸?100+ 浜ゆ槗鎵€锛?|
| 鏁版嵁搴?| SQLite锛坉ata/arbitrage.db锛?|
| 瀹氭椂浠诲姟 | APScheduler |
| 鍓嶇妗嗘灦 | React 18 + Ant Design 5 |
| 瀹炴椂閫氫俊 | WebSocket |
| 閮ㄧ讲 | start.bat 鏈湴鍚姩 |

---

## 浠峰樊濂楀埄妯″潡锛堟柊锛?
### 鏍稿績鏂囦欢
| 鏂囦欢 | 璇存槑 |
|------|------|
| `core/spread_stats.py` | 姣?5鍒嗛挓璁＄畻鍚勪氦鏄撳浠峰樊缁熻锛坢ean/std/p90锛夛紝瀛樺叆 spread_stats_cache |
| `core/spread_arb_engine.py` | 浠峰樊濂楀埄涓诲紩鎿庯細鍏ュ満/鍑哄満/瀵瑰啿妯″紡/鎸佷粨鏇存柊 |
| `api/spread_arb.py` | REST API锛氫粨浣?缁熻/閰嶇疆/鎵嬪姩骞充粨/瀵瑰啿妯″紡鍒濆鍖?淇濊瘉閲戠姸鎬?|
| `pages/SpreadArb` | 鍓嶇椤甸潰锛氬紑鍏?淇濊瘉閲戝崱鐗?鍙傛暟閰嶇疆/鎸佷粨琛?鍘嗗彶琛?瀵瑰啿妯″紡Modal |

### 鍏变韩涓婇檺鏈哄埗
- `AutoTradeConfig.max_open_strategies` 鍚屾椂闄愬埗璐圭巼濂楀埄锛圓UTO绛栫暐锛? 浠峰樊濂楀埄锛圫preadPosition锛夌殑鎬绘暟
- 璐圭巼濂楀埄寮曟搸鍦?`_enter_primary_strategies` 涓悓鏃惰鍏?SpreadPosition 鏁伴噺
- 浠峰樊濂楀埄寮曟搸鍦?`_count_active` 涓悓鏃惰鍏?Strategy 鏁伴噺

### 淇濊瘉閲戝埄鐢ㄧ巼
- `/api/spread-arb/margin-status`锛氬惈璐圭巼濂楀埄 + 浠峰樊濂楀埄涓ょ浠撲綅鐨勪繚璇侀噾鍗犵敤
- 璐圭巼濂楀埄鑷姩浜ゆ槗椤靛拰浠峰樊濂楀埄椤靛潎浣跨敤姝ゆ帴鍙?
## 宸茬煡闂 / 鏆傛湭瀹炵幇

- 寮€浠撲环鏍肩敤鍙傝€冧环鑰岄潪瀹為檯鎴愪氦浠凤紙cross_exchange.py銆乻pot_hedge.py 閮芥湁姝ら棶棰橈紝褰卞搷鐩堜簭璁＄畻鍑嗙‘鎬э級
- API Key 鏄庢枃瀛樺偍锛堟棤鍔犲瘑锛?- 鏃犵櫥褰曢壌鏉冿紙鎵€鏈夋帴鍙ｅ叕寮€锛?- 鑷姩浜ゆ槗鍑哄満渚濊禆鏃堕棿鎺ㄧ畻鏀惰垂锛岃嫢缁撶畻鏃堕棿涓嶅噯浼氭湁鍋忓樊
- fast_price_cache 鍙湁鍚堢害浠凤紝鐜拌揣瀵瑰啿鍑哄満鐢?position.current_price锛?0s 鏇存柊锛変唬鏇垮疄鏃剁幇璐т环
- `compute_opportunities` 纭紪鐮?z鈮?.5 鏈€浣庨槇鍊硷紙閫氬父鍚堢悊锛夛紝鐢ㄦ埛閰嶇疆 spread_entry_z 濡傛灉 < 1.5 涓嶄細鐢熸晥
- ~~`_serialize_pos` 鏈繑鍥?`take_profit_z`~~ 宸蹭慨澶嶏紙2026-03-11锛?
---

## 鍙樻洿鏃ュ織

### 2026-03-11锛堢鍗佷節娆★紝褰撳墠锛?- **Bug 淇锛欱ULLA/Binance 鏉犳潌瓒呴檺鍙嶅澶辫触**
  - 鏍瑰洜锛欱inance BULLA/USDT:USDT 鏈€澶ф潬鏉?1x锛岀郴缁熶互 cfg.leverage=2x 璁＄畻鍚堢害鏁伴噺锛坰ize_usd脳2/price锛夛紝瓒呭嚭1x涓嬫渶澶ф寔浠撻搴?鈫?Binance -2027 鎶ラ敊
  - Gate 澶氳吙鍏堟垚鍔燂紝Binance 绌鸿吙澶辫触锛岃Е鍙戠揣鎬ュ钩浠擄紝寰€杩旀墜缁垂鐧界櫧娑堣€楋紝鍏卞彂鐢?娆?  - 淇锛歚auto_trade_engine.py _enter_primary_strategies` 鍦?cooldown 妫€鏌ュ悗銆佸紑浠撳墠锛岃皟鐢?`fetch_max_leverage` 妫€鏌ヤ袱鑵挎渶澶ф潬鏉嗭紝浠讳竴鑵?max_lev < cfg.leverage 鍒欒烦杩囷紙璁?sym_skips 鏃ュ織锛?  - 缁撴灉锛欱ULLA 鍜屾墍鏈?x闄愬埗鍚堢害鍦ㄥ綋鍓?x鏉犳潌閰嶇疆涓嬩笉鍐嶈灏濊瘯寮€浠?- **鏂板鍒嗘瀽鏂囦欢**锛歚C:\Claudeworkplace\ai-trader\logs\analysis_20260311_081500.json`锛堝惈 BULLA 鏍瑰洜鍒嗘瀽 + pre_settle_exit_threshold_pct 寤鸿锛?
### 2026-03-11锛堢鍗佸叓娆★級
- **璁板繂琛ュ叏**锛氶€氳繃閬嶅巻椤圭洰鏂囦欢锛岃ˉ褰?3鏈?0~11鏃ヤ涪澶辩殑鍙樻洿璁板綍鑷虫鏂囦欢鍜?arbitrage-tool.md

### 2026-03-10锛堢鍗佷竷娆★級
- **鏂板銆屼环宸満浼氥€嶉〉闈?*锛坄pages/SpreadOpportunities/index.jsx`锛?  - 姣?s杞 `/api/spread-monitor/opportunities`
  - 鏄剧ず z鍒嗘暟銆佽垂鐜囨柟鍚戯紙`funding_aligned`锛夈€佸綋鍓嶄环宸?鍧囧€?蟽/+1.5蟽闂ㄦ銆侀璁″噣鍒╂鼎銆佸線杩旀墜缁垂銆佹垚浜ら噺
  - 鍑€鍒╂鼎鐢?`effective_exit_z = max(exit_z, z_score - tp_delta)` 璁＄畻棰勬湡鍑哄満浠峰樊锛堟瘮鍧囧€间繚瀹堬級
  - 缁胯壊琛岄珮浜垂鐜囨柟鍚戜竴鑷寸殑鏈轰細
- **鏂板 `/api/spread-monitor/opportunities` 鎺ュ彛**锛坰pread_monitor.py锛?  - 杩囨护鏉′欢锛歾 鈮?1.5 涓?current_spread > round_trip_fee + 0.1%
  - 杩斿洖鎺掑簭锛歾_score 闄嶅簭
- **鏂板 `/api/spread-monitor/kline` 鎺ュ彛**锛坰pread_monitor.py锛?  - 鏀寔浠绘剰鏃堕棿妗嗘灦锛?m/5m/15m/1h/4h/1d锛夊拰 limit锛?0-500锛?  - 鍙屾墍 OHLCV 鎸夋椂闂存埑鍐呰繛鎺ワ紝璁＄畻浠峰樊 OHLC
  - 杩斿洖缁熻鍩虹嚎锛坢ean/std/p90/upper_1.5/upper_2锛?- **SpreadMonitor 椤垫柊澧?K 绾垮浘**锛坄pages/SpreadMonitor/index.jsx`锛?  - 鑷畾涔?SVG 铚＄儧鍥撅紙`SpreadKlineChart` 缁勪欢锛屾棤绗笁鏂瑰浘琛ㄥ簱锛?  - 鍙犲姞 mean/+1.5蟽/+2蟽 姘村钩绾?  - 鏀寔 hover 鏌ョ湅 OHLC 鍊?- **ai-trader 鈫?arbitrage-tool 妗ユ帴**锛坄api/ai_analyst.py`锛?  - 璇诲彇 `C:\Claudeworkplace\ai-trader\logs\analysis_*.json`
  - GET /latest銆丟ET /history銆丳OST /apply銆丳OST /reject
  - apply 鍙皢 AI 鍒嗘瀽寤鸿鐩存帴鍐欏叆 arbitrage.db锛堢櫧鍚嶅崟 20 涓瓧娈碉級
  - 宸叉寕杞借嚦 main.py
- **瀵艰埅鑿滃崟鏇存柊**锛氭柊澧炪€屼环宸満浼氥€嶏紙RiseOutlined锛夛紝鍏?9 涓彍鍗曢」
- **`run_spread_arb` 璋冨害浠?30s 鏀逛负 1s**锛坢ain.py锛?
### 2026-03-10锛堢鍗佸叚娆★紝褰撳墠锛?- **AI 鑷富浜ゆ槗 Agent 瀹屾暣瀹炵幇**锛坄C:\Claudeworkplace\ai-trader\`锛?  - 涓夊眰鏋舵瀯锛氫俊鍙烽浄杈?鈫?AI 澶ц剳锛圕laude API锛夆啋 鎵ц鍣?+ 椋庢帶
  - `config/settings.py`锛氬叏灞€閰嶇疆锛堣祫閲戠鐞嗐€侀鎺у弬鏁般€佷俊鍙烽槇鍊笺€丄I 妯″瀷锛?  - `models/database.py`锛氱嫭绔?SQLite 鏁版嵁搴擄紝5 寮犺〃锛坮ounds/decisions/trades/learnings/signals锛?  - `core/radar.py`锛氫俊鍙烽浄杈撅紝姣?0绉掓壂鎻忓競鍦猴紝妫€娴?绫诲紓甯镐俊鍙?    - 璐圭巼寮傚姩锛? 0.1%/8h锛夈€佷环鏍肩獊鍙橈紙5min > 2%锛夈€佹垚浜ら噺寮傚父锛? 3x 鍧囧€硷級銆佽法鎵€浠峰樊锛? 0.5%锛?    - 浠?arbitrage-tool 鏁版嵁搴撹鍙?Exchange 琛ㄧ殑 API Key
  - `core/brain.py`锛欳laude API 鍐崇瓥寮曟搸锛坈laude-sonnet-4-6锛?    - 缁撴瀯鍖?JSON 杈撳嚭锛坅ction/positions/reasoning/confidence锛?    - 纭害鏉熷啓鍦?system prompt锛堝垵鏈熷彧鍋氬鍐层€佸繀椤昏姝㈡崯銆佷笉纭畾灏?skip锛?    - 杞缁撴潫鍚庤嚜鍔ㄥ鐩樻€荤粨锛屽啓鍏?learnings 琛?  - `core/executor.py`锛氳鍗曟墽琛岋紙澶嶇敤 ccxt锛岀嫭绔嬩笅鍗曢€昏緫锛?    - 寮€浠擄細绮惧害澶勭悊 + 鏉犳潌璁剧疆 + 瀹為檯鎴愪氦浠疯褰?    - 骞充粨锛歳educeOnly + 鐩堜簭璁＄畻 + 杞浣欓鏇存柊
  - `core/risk.py`锛氱‖鎬ч鎺э紙AI 涓嶅彲瑕嗙洊锛?    - 绛栫暐绫诲瀷鐧藉悕鍗曘€佺疆淇″害涓嬮檺銆佹寔浠撴暟閲忎笂闄?    - 鍗曚粨澶у皬闄愬埗锛?0% 棰勭畻锛夈€佹鎹熻寖鍥撮檺鍒讹紙1-10%锛?    - 杞鐔旀柇锛堜簭瀹?20U 鑷姩鍋滄鏈疆锛屽己鍒跺钩鎵€鏈変粨浣嶏級
  - `core/memory.py`锛欰I 璁板繂绯荤粺锛堝喅绛栧巻鍙?+ 澶嶇洏瀛︿範锛?  - `main.py`锛氬叆鍙ｏ紝鏀寔 `--live`锛堝疄鐩橈級鍜?`--summary`锛堟煡鐪嬭〃鐜帮級
  - 榛樿妯℃嫙杩愯锛坉ry_run锛夛紝涓嶇湡瀹炰笅鍗?  - 200U 鍒?10 杞?脳 20U锛屾瘡杞嫭绔嬮绠楀拰椋庢帶

### 2026-03-09锛堢鍗佷簲娆★級
- **浠峰樊濂楀埄鍏ュ満鏀逛负瀹炴椂瑙﹀彂锛堜环鏍兼洿鏂板嵆瑙﹀彂锛?*
  - 鍘熼€昏緫锛歚run_spread_arb()` 姣?0s鎵竴娆★紝鏈轰細鍙兘绛?0s鎵嶈鎹曟崏
  - 鏂伴€昏緫锛歚update_fast_prices()`锛堟瘡1s鎵ц锛夊畬鎴愬悗绔嬪嵆璋冪敤 `trigger_spread_entries()`
  - `trigger_spread_entries()` 鐗规€э細
    - `threading.Lock` non-blocking acquire 鈥?涓婁竴绗斿紑浠撹繕鍦ㄦ墽琛屾椂鑷姩璺宠繃锛屼笉鍫嗙Н
    - 鍏堝仛绾紦瀛樿锛坄compute_opportunities`锛夛紝鑻ユ棤鏈轰細鐩存帴杩斿洖锛屼笉鍗犻攣
    - 鍙礋璐ｅ叆鍦猴紱閫€鍑烘鏌ヤ繚鐣欏湪30s璋冨害鐨?`run_spread_arb()`
  - `run_spread_arb()` 鐜板湪鍙皟 `_check_exits()`锛屼笉鍐?`_scan_opportunities()`
  - `data_collector.update_fast_prices`锛氭湯灏炬柊澧?`trigger_spread_entries()` 璋冪敤

### 2026-03-09锛堢鍗佸洓娆★級
- **浠峰樊濂楀埄姝㈡崯鏀逛负娴姩闃堝€?*
  - 闂锛氬浐瀹?`spread_stop_z=3.0`锛岃嫢鍏ュ満 z=4 鍒欏紑浠撳嵆瑙︽鎹?  - 鏂伴€昏緫锛氭鎹?z = `entry_z_score + spread_stop_z_delta`锛埼?鍙厤缃紝榛樿 1.5锛?  - 鍏滃簳锛氳嫢 `entry_z_score` 涓?0锛堣€佷粨浣嶏級锛岄€€鍥炰娇鐢?`spread_stop_z` 缁濆鍊?  - `models/database.py`锛氭柊澧?`spread_stop_z_delta REAL DEFAULT 1.5` + migration
  - `spread_arb_engine.py _check_exits`锛欵xit 鈶?鏀逛负 `z >= pos.entry_z_score + delta`
  - `api/spread_arb.py`锛歋preadArbConfig + get_config 鏂板 `spread_stop_z_delta`
  - `pages/SpreadArb ConfigPanel`锛氥€屾鎹?z 闃堝€笺€嶁啋銆屾鎹熷亸绉?未銆嶏紙鍚叕寮?Tooltip锛?  - `pages/SpreadArb 鎸佷粨琛╜锛氬叆鍦轰环宸鏂板鍔ㄦ€佹鎹熺嚎鏄剧ず锛堢孩鑹插皬瀛?"姝㈡崯鈮.X"锛?
### 2026-03-09锛堢鍗佷笁娆★級
- **鎸佷粨鏈熼棿璧勯噾璐规敹鐩婅鍏ョ泩浜?*锛圥ositions绛栫暐琛級
  - `models/database.py`锛歚Strategy` 鏂板 `funding_pnl_usd REAL DEFAULT 0.0` 瀛楁 + migration
  - `core/exchange_manager.py fetch_funding_income`锛氭柊澧?`symbol` 鍙傛暟锛屾敮鎸佹寜甯佸杩囨护
    - 浼樺厛璋冪敤 CCXT 缁熶竴 `fetchFundingHistory(symbol)`
    - Binance 鍏滃簳锛歚/fapi/v1/income?symbol=BTCUSDT`
    - OKX 鍏滃簳锛歚/account/bills?instId=BTC-USDT-SWAP`
    - Bybit 鍏滃簳锛歚/v5/account/transaction-log?symbol=BTCUSDT`
  - `auto_trade_engine.py _check_exits`锛氳Е鍙戝嚭鍦哄墠璋冪敤鐪熷疄 API 瀛樺叆 `strategy.funding_pnl_usd`
    - 绌哄ご鑵匡細`fetch_funding_income(short_ex, since_ms=created_at, symbol=symbol)`
    - 澶氬ご鑵匡細鍚屼笂锛堣法鎵€濂楀埄涓斾笉鍚屼氦鏄撴墍鏃讹級
    - 鏌ヨ澶辫触鏃惰 warning 浣嗕笉闃绘柇骞充粨
  - `api/dashboard.py get_strategies`锛?    - 宸插叧闂瓥鐣ヨ繑鍥炲瓨鍌ㄧ殑 `funding_pnl_usd`锛堝钩浠撴椂鍐欏叆鐨勭湡瀹炲€硷級
    - 杩愯涓瓥鐣ヨ皟鐢?`_get_cached_funding_income`锛?鍒嗛挓缂撳瓨锛岄伩鍏嶆瘡娆¤姹傞兘鎵?API锛?    - 鏂板杩斿洖瀛楁 `funding_pnl_usd`銆乣total_pnl_usd`锛堜环宸?璧勯噾璐癸級
  - `pages/Positions/index.jsx`锛?    - 鍘熴€屾湭瀹炵幇鐩堜簭銆嶅垪閲嶅懡鍚嶄负銆屼环宸泩浜忋€?    - 鏂板銆岃祫閲戣垂銆嶅垪锛圱ooltip 璇存槑锛?    - 鍘熴€岀泩浜?銆嶅垪鏇挎崲涓恒€屾€荤泩浜忋€嶅垪锛圲SD + % 鍚堝苟锛屽彲鎺掑簭锛?    - 璇︽儏 Drawer 鍚屾灞曠ず涓夐」鎷嗗垎

### 2026-03-09锛堢鍗佷簩娆★級
- **鏂板浠峰樊鐩戞帶椤甸潰**锛坄api/spread_monitor.py` + `pages/SpreadMonitor/index.jsx`锛?  - 鍚庣锛歚GET /api/spread-monitor/groups`锛屼粠 funding_rate_cache 鑱氬悎鎵€鏈夋湁 鈮? 浜ゆ槗鎵€鐨勫竵瀵?  - 姣忔潯鏁版嵁鍚細鏍囪浠锋牸銆佺浉瀵逛环宸?銆佽祫閲戣垂鐜囥€佷笅娆＄粨绠楀€掕鏃躲€佺粨绠楀懆鏈燂紙hours + 娆?澶╋級銆佹墜缁垂鐜?  - 楂樹寒锛氱粍鍐呯粨绠楅鐜囨渶楂樼殑浜ゆ槗鎵€锛堟鑹茶鑳屾櫙 + 楂橀 Tag锛?  - 鍓嶇锛氭寜鏈€澶т环宸檷搴忔帓鍒楋紝鏀寔鎼滅储杩囨护 + 鏈€灏忎环宸繃婊わ紝30s 鑷姩鍒锋柊
  - 瀵艰埅锛氳祫閲戣垂鐜囦笅鏂规柊澧炪€屼环宸洃鎺с€嶈彍鍗曢」锛圫wapOutlined 鍥炬爣锛?
### 2026-03-09锛堢鍗佷竴娆★級
- **淇鍏ュ満鏃舵満閫昏緫锛氭敼涓轰互浣庨鎵€缁撶畻涓哄噯**
  - 淇鍓嶏細`min(secs_l, secs_s)`锛屼换鎰忎竴鏂圭粨绠楃獥鍙ｅ唴灏卞叆鍦猴紙楂橀鎵€鍦ㄧ獥鍙ｅ氨杩涳級
  - 淇鍚庯細姣旇緝 `long_periods_per_day` vs `short_periods_per_day`锛屼互棰戠巼鏇翠綆鐨勪竴鏂圭殑 `next_funding_time` 涓哄噯
  - 閬撶悊锛氫綆棰戞墍鍐冲畾濂楀埄鑺傚锛岄珮棰戞墍姣忎釜灏忓懆鏈熶篃浼氱粨绠楋紱鍙湪浣庨鎵€绐楀彛鍐呮墠鍏ュ満鑳戒繚璇佷袱鑵块兘鍦ㄧ獥鍙ｉ檮杩?  - `_enter_primary_strategies` cross_exchange 鍏ュ満鏃舵満宸蹭慨澶?  - TRIGGER 鈶?鐩爣鏈轰細鏃堕棿绐楀彛妫€鏌ュ悓姝ヤ慨澶嶏紙鍚屾牱鏀逛负浣庨鎵€鏃堕棿锛?
### 2026-03-09锛堢鍗佹锛?- **Bug 淇锛歍RIGGER 鈶?铏氬亣瑙﹀彂锛圔ABY/USDT:USDT 妗堜緥锛?*
  - 鏍瑰洜鈶狅細`fast_price_cache` 鐢辨壒閲?`fetch_tickers()` 濉厖锛屼綆娴佸姩鎬у竵锛圔ABY 鍦?OKX锛夌殑 `last` 浠锋牸鍙兘鏄暟灏忔椂鍓嶇殑鏃у€硷紝瀵艰嚧 `spread_pnl_pct` 涓ラ噸铏氶珮锛?.381% 瀹為檯搴斾负 0.003%锛?  - 鏍瑰洜鈶★細`pos.current_price` 鐢变笓鐢?`fetch_ticker(exchange, symbol)` 鍗曠嫭鎷夊彇锛屾洿鍑嗙‘锛屼絾 cross_exchange 鍑哄満妫€鏌ュ嵈缁曡繃瀹冪敤浜?`fast_price_cache`
  - 淇鈶狅細`_check_exits` 浠锋牸鏉ユ簮鏀逛负浼樺厛鐢?`pos.current_price`锛宖allback 鎵嶇敤 `fast_price_cache`
  - 淇鈶★細TRIGGER 鈶?鍦?%姣旇緝閫氳繃鍚庡姞 USD 缁濆鍊奸獙璇侊細`spread_pnl_usd > close_fee_usd` 鎵嶇湡姝ｈЕ鍙戯紝鍚﹀垯璁?debug 鏃ュ織璺宠繃

### 2026-03-09锛堢涔濇锛?- **Bug 淇锛氬钩浠撳け璐ヤ笁澶ф牴鍥狅紙WET/USDT 妗堜緥锛?*
  - 鏍瑰洜鈶狅細`close_position` 鐩存帴璋?`place_order` 娌℃湁 `reduceOnly=True`锛孊inance 浼氭牎楠屾柟鍚?鏁伴噺锛岀簿搴︿笉绗︾洿鎺ユ嫆鍗?  - 鏍瑰洜鈶★細鏁伴噺鏈仛绮惧害鑸嶅叆锛坄amount_to_precision`锛夛紝娴偣鏁板 4987.654321 瑙﹀彂 Binance `LOT_SIZE` filter 鎶ラ敊
  - 鏍瑰洜鈶細骞充粨鏃朵粛璋?`set_leverage_for_symbol`锛屽宸叉湁浠撲綅璁炬潬鏉嗗彲鑳借 Binance 鎷掔粷
  - 淇锛歚close_position` 鐙珛瀹炵幇锛屽姞 `reduceOnly=True` + `amount_to_precision`锛屽け璐ュ悗鑷姩 `fetch_positions` 鎷夊彇瀹為檯鎸佷粨閲忛噸璇曚竴娆?  - `close_spot_position` 鍚屾牱鍔?`amount_to_precision`
  - `place_order` 涔熷姞 `amount_to_precision`锛堝悓鏃朵繚鎶ゅ紑浠撶簿搴︼級

### 2026-03-09锛堢鍏锛?- **Bug 淇锛氬钩浠撻儴鍒嗗け璐ユ椂瑁镐粨鏃犲憡璀?*
  - 鍦烘櫙锛歐ET #238 鑷姩姝㈡崯鏃?OKX 骞充粨鎴愬姛锛屼絾 Binance 骞充粨澶辫触锛孊N 瑁镐粨鑴辩鎵€鏈夌洃鎺э紙pos.status="error" 鑰岄潪 "open"锛岄鎺у紩鎿庣湅涓嶅埌锛?  - `cross_exchange.py` / `spot_hedge.py` close()锛氬钩浠撳け璐ユ椂**淇濇寔 pos.status="open"**锛堜笉鏀逛负 error锛夛紝骞剁珛鍗冲彂閭欢鍛婅
  - 淇鍓嶏細澶辫触鑵挎爣 error 鈫?椋庢帶涓嶇锛岀敤鎴锋棤鎰熺煡
  - 淇鍚庯細澶辫触鑵跨暀 open 鈫?椋庢帶缁х画鐩戞帶锛岄偖浠剁珛鍗抽€氱煡鎵嬪姩澶勭悊

### 2026-03-09锛堢涓冩锛?- **鏂板 TRIGGER 鈶燽锛氳垂鐜囧弽杞珛鍗冲嚭鍦?*
  - `auto_trade_engine.py _check_exits`锛氬湪 TRIGGER 鈶?涔嬪悗銆乀RIGGER 鈶?涔嬪墠鏂板瑙﹀彂鍣?  - 鏉′欢锛歚current_annualized < -(cfg.min_annualized_pct)`锛?*浠绘剰鏃跺埢**鍧囧彲瑙﹀彂锛堜笉闄愪簬缁撶畻绐楀彛锛?  - 瑙ｅ喅闂锛氳垂鐜囧湪鎸佷粨鏈熼棿鍙嶈浆鍚庯紝TRIGGER 鈶?鍙湪缁撶畻绐楀彛鍓?N 鍒嗛挓鎵嶆鏌ワ紝涓棿鏈€闀垮彲鑳芥寔缁嚑鍗佸垎閽熸寔缁簭鎹燂紙濡?RIVER/USDT:USDT 妗堜緥锛氬勾鍖?-262%锛屼笅娆＄粨绠楄繕鏈?68 鍒嗛挓锛?  - 鍓嶇 AutoTrade 椤靛嚭鍦鸿Е鍙戝櫒璇存槑鏂板 `鈶燽 璐圭巼鍙嶈浆` 鏍囩

### 2026-03-09锛堢鍏锛?- **Bug 淇锛氬钩浠撹璐︿环鏍奸敊璇?*
  - `cross_exchange.py` / `spot_hedge.py` close()锛歍radeLog 鐨?price 鏀圭敤 `result.get("average") or result.get("price") or pos.current_price`锛屼娇鐢ㄥ疄闄呮垚浜ゅ潎浠疯€岄潪缂撳瓨浠?- **Bug 淇锛氱揣鎬ュ钩浠撴棤 TradeLog**
  - 涓や釜绛栫暐 open() 鐨勭揣鎬ュ钩浠撳垎鏀潎琛ュ叏 `TradeLog(action="emergency_close")`锛岃褰曞疄闄呭钩浠撲环
- **Bug 淇锛氭崲浠撲笉妫€鏌ョ洰鏍囨満浼氱獥鍙?*
  - `auto_trade_engine.py` TRIGGER 鈶細瀵规瘡涓€欓€夋満浼氳绠?`opp_secs`锛屼笉鍦ㄥ叆鍦虹獥鍙ｅ唴锛坥pp_secs > window_sec锛夌殑璺宠繃
- **Bug 淇锛氭崲浠撲笉浜忔鏌ュ熀鍑嗕笉涓€鑷?*
  - 鏃э細`spread_pnl_pct + est_funding_pct - close_fee_pct`锛堜环鏍?涓庡悕涔?娣风畻锛?  - 鏂帮細鍏ㄩ儴鎹㈢畻涓?USD 缁濆鍊硷細`net_at_close = actual_spread_pnl_usd + est_funding_usd - close_fee_usd`
- **鐩堜簭鍒嗘瀽鍏ㄩ潰瀹屽杽**锛坄api/analytics.py` + `pages/Analytics/index.jsx`锛?  - 鍚庣鏂板 `_calc_fees_from_logs(logs, fee_rate)`锛氫及绠楁墜缁垂 = 危(price 脳 size 脳 fee_rate)
  - 杩斿洖瀛楁鎷嗗垎锛歚total_spread_pnl_gross`锛堜环宸瘺鍒╋級/ `total_fees_usd`锛堟墜缁垂锛? `total_funding_income`锛堣祫閲戣垂锛? `combined_pnl`锛堝噣缁煎悎鐩堜簭 = spread - fees + funding锛?  - `total_realized_pnl` 鏀逛负鍑€鍊硷紙鎵ｆ墜缁垂锛夛紝鑳滅巼鍩轰簬鍑€鐩堜簭璁＄畻
  - 绛栫暐琛屾柊澧?`spread_pnl`锛堜环宸瘺鍒╋級/ `est_fees`锛堜及绠楁墜缁垂锛? `pnl`锛堝噣鐩堜簭锛?  - 鍓嶇锛? 寮犻《閮ㄥ崱锛堢患鍚堝噣鐩堜簭 / 浠峰樊姣涘埄 / 璧勯噾璐?/ 鎵嬬画璐癸級+ 鍏紡灞曠ず琛?+ 绛栫暐琛?3 鍒楋紙姣涘埄/鎵嬬画璐?鍑€鐩堜簭锛?
### 2026-03-08锛堢浜旀锛?- 鏂板鐩堜簭鍒嗘瀽椤甸潰锛坄api/analytics.py` + `pages/Analytics/index.jsx`锛?  - 鎸夋椂闂磋寖鍥达紙7/30/90澶?鍏ㄩ儴锛夌瓫閫?  - 姹囨€伙細鎬荤泩浜忋€佸凡瀹炵幇銆佹湭瀹炵幇銆佽儨鐜囥€佸钩鍧囨瘡绗?  - 鎸変氦鏄撴墍 + 鎸変氦鏄撳鍒嗙粍缁熻
  - 绛栫暐鏄庣粏琛紙鐩?浜忚棰滆壊鍖哄垎锛?- 鍚堢害鏁伴噺鎹㈢畻淇锛坄_base_to_contracts`锛夛細place_order 鏃堕櫎浠?contractSize锛屾秷闄?OKX 10x 浠撲綅闂
- Bug 淇锛歚_has_cooldown` 鏀圭敤 Python timedelta锛堜笉鍐嶄緷璧?SQLite func.datetime锛?- Bug 淇锛氬仠鐢ㄤ氦鏄撴墍鏃跺悓姝ユ竻鐞?`_crypto_symbol_cache`

### 2026-03-08锛堢鍥涙锛?- **Bug 淇锛氱幇璐у鍐茬敤閿欏疄渚嬶紙鑷村懡锛?*
  - `spot_hedge.py`锛氫拱鍏ョ幇璐ф敼鐢?`place_spot_order`锛屽崠鍑虹幇璐ф敼鐢?`close_spot_position`锛岃幏鍙栦环鏍兼敼鐢?`fetch_spot_ticker`
  - `risk_manager.py`锛氶鎺у钩浠撴椂鐜拌揣浠撲綅鐢?`close_spot_position`
  - `data_collector.py`锛氭洿鏂版寔浠撲环鏍兼椂鐜拌揣浠撲綅鐢?`fetch_spot_ticker`
  - `exchange_manager.py`锛氭柊澧?`fetch_spot_ticker` / `place_spot_order` / `close_spot_position` 涓変釜鐜拌揣涓撶敤鍑芥暟
- **TradFi 鍚堢害杩囨护**锛歚exchange_manager.fetch_funding_rates` 閫氳繃 `underlyingType == "COIN"` 杩囨护 Binance 鑲＄エ閫氳瘉锛圥LTR銆乀SLA 绛夛級
- **鍋滅敤浜ゆ槗鎵€缂撳瓨娓呯悊**锛歚collect_funding_rates` 鍏ュ彛澶勬竻闄ゅ凡鍋滅敤浜ゆ槗鎵€鐨勫叏閮ㄧ紦瀛?- **澶辫触寮€浠撲笉鐣欒剰鏁版嵁**锛歅osition status 鍦ㄨ鍗曞け璐ユ椂璁句负 `"error"`锛屼笉鍐嶆樉绀哄菇鐏垫寔浠?- **鎬昏鐪嬫澘鏂板銆岃处鎴疯祫閲戙€嶆澘鍧?*锛氬疄鏃舵媺鍙栧悇浜ゆ槗鎵€浣欓+鍚堢害鎸佷粨锛屾敮鎸佺粺涓€璐︽埛锛圤KX/Bybit绛夛級鍜屽垎璐︼紙Binance锛夎嚜鍔ㄨ瘑鍒?- **濂楀埄鏈轰細琛ㄦ柊澧炪€屼笅娆＄粨绠椼€嶅€掕鏃跺垪**锛堣法鎵€ + 鐜拌揣瀵瑰啿涓や釜琛級
- **Settings 椤靛垹闄?`_Removed` 姝讳唬鐮?*锛?16琛岋級

### 2026-03-08锛堢涓夋锛?- 鏂板缓 `pages/AutoTrade/index.jsx`锛堢嫭绔嬮〉闈級锛屽惈澶у彿鍚仠鎸夐挳 + 瀹炴椂鐘舵€佺粺璁?+ 鍏ㄩ儴閰嶇疆
- 渚ц竟瀵艰埅鏂板銆岃嚜鍔ㄤ氦鏄撱€嶈彍鍗曢」锛圧obotOutlined 鍥炬爣锛?- Settings 椤电Щ闄よ嚜鍔ㄤ氦鏄?tab锛屾仮澶嶄负 4 涓?tab锛堥鎺?浜ゆ槗鎵€/閭欢/搴旂敤锛?- AutoTradeConfig 鏂板 `min_cross_volume_usd` / `min_spot_volume_usd` 瀛楁
- 鑷姩浜ゆ槗寮曟搸鍏ュ満鏃跺皢浜ゆ槗閲忎笅闄愪紶鍏?find_opportunities/find_spot_hedge_opportunities
- Bug 淇锛?澶勪笁鍏冭繍绠楃浼樺厛绾с€乢mark_auto閫昏緫銆乷pen_count鏈崟鑾枫€乽nrealized_pnl None

### 2026-03-08锛堢浜屾锛?- 鏂板鑷姩浜ゆ槗寮曟搸 `core/auto_trade_engine.py`
- 鏂板 `AutoTradeConfig` 鏁版嵁搴撴ā鍨?- Settings 鏂板"鑷姩浜ゆ槗绛栫暐"閰嶇疆 tab
- `api/settings.py` 鏂板 GET/PUT `/settings/auto-trade-config`

### 2026-03-08锛堢涓€娆★級
- FundingRates 椤甸潰 WS 鏇存柊琛ュ厖 min_volume 杩囨护
- Positions 寮€浠撹〃鍗曞姩鎬佸寲锛堣法鎵€/鐜拌揣瀵瑰啿鏍囩鍒囨崲銆佸揩閫熷～鍏ュ垎绫绘樉绀猴級
- 椋庢帶寮曟搸瀹炵幇鍏ㄩ儴 5 绉嶈鍒欑被鍨嬶紝鎻愬彇 `_alert_only` 杈呭姪鍑芥暟

### 2026-03-13锛圫pot-Basis Auto 閲嶆瀯锛氱粍鍚堢骇鍐嶅钩琛★級
- 鏂板鑷姩鐜拌揣-鍚堢害璐圭巼濂楀埄鐨勭粍鍚堢骇鎵ц閾捐矾锛坄core/spot_basis_auto_engine.py`锛夛細
  - 鐩爣缁勫悎 vs 褰撳墠缁勫悎锛岃绠楃粍鍚堢骇 `Adv_port`锛圲SD/澶╋級
  - 鍙屾鍖鸿Е鍙戯細`relative %` + `absolute USD/day`
  - 杩炵画纭杞鍚庢墽琛岋紙澶嶇敤 `switch_confirm_rounds`锛?  - 鎵ц椤哄簭锛氬厛骞冲悗寮€锛涜嫢骞充粨闃舵澶辫触锛岃烦杩囧紑浠撻樁娈碉紝閬垮厤棰勭畻瓒呭崰鐢?- 鏁版嵁闄堟棫妯″紡锛坄risk_reduce_only`锛夛細
  - 褰?NAV/鏁版嵁闄堟棫鏃讹紝绂佹寮€鏂颁粨
  - 浠呭厑璁搁闄╀笅闄嶅瀷骞充粨锛堝 unmatched 鎴栦綆缃俊璐熸湡鏈涳級
- 鏂板閰嶇疆瀛楁锛坄SpotBasisAutoConfig` + migration + API锛夛細
  - `rebalance_min_relative_adv_pct`
  - `rebalance_min_absolute_adv_usd_day`
- 鍓嶇 `SpotBasisAuto` 鍚屾锛?  - 鏂板鍐嶅钩琛″弻姝诲尯鍙傛暟杈撳叆
  - 鏈€杩戞墽琛屽崱鐗囧睍绀哄紑/骞宠鍒掋€佹墽琛岀粨鏋溿€乣Adv_port`銆佸垏鎹㈡垚鏈?
### 2026-03-13锛圫pot-Basis Auto 閲嶆瀯锛氬悓 row 宸鎵ц锛?- 浼樺寲 delta planner锛坄_build_rebalance_delta_plan`锛夛細
  - 鍚屼竴 `row_id` 涓嬩笉鍐嶉粯璁も€滅暀涓€骞冲叾浣欌€?  - 鏀逛负鈥滃敖閲忎繚鐣欏凡鏈夌瓥鐣ュ瓙闆?+ 瀵圭洰鏍囩己鍙ｈˉ寮€ + 瀵硅秴閰嶉儴鍒嗗钩浠撯€?  - 鏂板琛屽唴鍔ㄤ綔鍘熷洜锛?    - `excess_over_target_same_row`
    - `top_up_to_target_same_row`
    - `new_target_row`
    - `not_in_target_portfolio`
- 绉婚櫎寮€浠撻樁娈碘€滃悓 row_id 涓€寰嬭烦杩団€濈殑闄愬埗锛屽厑璁稿悓 row 鍋?top-up锛堟柊寮€琛ラ綈锛?- 璇存槑锛氬綋鍓嶆墽琛屽眰浠嶆槸鈥滄寜绛栫暐鏁村崟骞充粨鈥濓紙鏃犻儴鍒嗗钩浠?API锛夛紝鍥犳缂╀粨閫氳繃鈥滃钩鏃у崟 + 寮€琛ュ崟鈥濆疄鐜般€?
### 2026-03-13锛圫pot-Basis Auto锛氭墽琛屽啓鍥炰笌澶辫触鑵块噸璇曪級
- 鍚庣 core/spot_basis_auto_engine.py锛?  - 鎺ュ叆澶辫触椤归噸璇曢槦鍒楋紙close/open 澶辫触鑵垮垎鍒叆闃熴€佸幓閲嶃€侀€€閬裤€佹渶澶ц疆娆°€佸埌鏈熼噸璇曪級銆?  - 鑷姩鍛ㄦ湡鏀逛负鈥滀紭鍏堝鐞嗗埌鏈熼噸璇曗€濓紱瀛樺湪鍒版湡椤规椂杩斿洖 
etry_executed锛屼笉閲嶈窇鏁磋疆鎵弿銆?  - 鍦?executed / 
isk_reduce_executed / 
etry_executed 鍥炲啓 execution_writeback 涓?
etry_queue 鍙娴嬪瓧娈点€?- 鍚庣閰嶇疆鎵╁睍锛?  - SpotBasisAutoConfig 鏂板 execution_retry_max_rounds銆乪xecution_retry_backoff_secs锛堝惈杩佺Щ锛夈€?  - pi/spot_basis.py 鐨?auto-config update/dump/preview 宸插悓姝ヨ繖涓や釜瀛楁銆?- 鍓嶇 pages/SpotBasisAuto/index.jsx锛?  - 鑷姩绛栫暐鎺у埗鏂板鈥滈噸璇曡疆鏁?/ 閲嶈瘯閫€閬匡紙绉掞級鈥濆弬鏁拌緭鍏ャ€?  - 鏈€杩戞墽琛屽崱鏂板鎵ц鍐欏洖涓庨噸璇曢槦鍒楃姸鎬佸睍绀猴紝渚夸簬鎺掓煡鑷姩鎵ц鍋ュ悍搴︺€?### TODO锛堝緟鍔烇級
- SpotBasisAuto 椤甸潰鏂囨缁熶竴鎭㈠涓轰腑鏂囷紝骞跺仛涓€杞?UI 缁嗚妭鍥炲綊銆?- SpotBasisAuto 澧炲姞 
- SpotBasisAuto 增加 retry_only 轮次状态徽标（面板/最近执行可见）。

### TODO_NEXT
- SpotBasisAuto 页面文案统一恢复为中文，并做一轮 UI 细节回归。
- SpotBasisAuto 增加 retry_only 轮次状态徽标（面板/最近执行可见）。