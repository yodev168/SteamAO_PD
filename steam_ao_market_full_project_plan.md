# Steam AO 市場資料平台完整企劃

## 專案定位
建立一套針對 Steam「僅限成人（Adult Only / AO）」市場的資料蒐集、分析與預測系統。

---

## 目前進度總覽（更新日期：2026-04-23）

### Phase 完成度

| Phase | 狀態 | 備註 |
|-------|------|------|
| Phase 0：資料定義 | ✅ 完成 | 見本文件 §四 核心資料表 |
| Phase 1：AO Universe | ✅ 完成 | 產出 `phase1/ao_apps_deduped.csv`（5367 筆） |
| Phase 2：Master Data | ✅ **完成** | 產出 `phase2/ao_games_master.csv`（5367 筆），`sanity_check` 全數通過 |
| Phase 3：Market Proxy | ⬜ 未開始 | 下一步 |
| Phase 4：Daily Snapshot | ⬜ 未開始 | 建議與 Phase 3 並行啟動 |
| Phase 5：Dashboard | ⬜ 未開始 | |
| Phase 6：Intelligence | ⬜ 未開始 | 需 30+ 天 snapshot 後才有意義 |
| Phase 7：預測模型 | ⬜ 未開始 | 需 30+ 天 snapshot 後才有意義 |

### Phase 1 交付物

- `phase1/ao_apps_deduped.csv`：**5367 筆**（AO all + AO upcoming 去重後）
- `phase1/ao_apps_raw.csv`：原始清單（含 source_tab）
- 爬蟲、合併、sanity_check 腳本已完成並能重跑
- GUI 工具：`phase1/gui.py`、`phase1/gui_phase12.py`（Tkinter，選用）

### Phase 2 交付物

- `phase2/ao_games_master.csv`：**5367 筆** Master 資料
- `phase2/missing_report.csv`：877 筆缺欄位清單（主要為 upcoming / 無評論遊戲）
- `phase2/crawl_log.jsonl`：完整爬取日誌
- 原始資料：
  - `phase2/raw/appdetails/`：**5367 / 5367（100%）**
  - `phase2/raw/reviews/`：**5367 / 5367（100%）**
  - `phase2/raw/html/`：0（因 appdetails 已全數成功，不需要 fallback）
  - `phase2/raw/errors/`：0

### Phase 2 `sanity_check.py` 實測結果

| 指標 | 覆蓋率 | 狀態 |
|------|-------|------|
| Row count | 5367 / 5367 | ✅ PASS |
| name coverage | 100.0% | ✅ PASS |
| price_twd_original（paid non-upcoming） | 100.0% | ✅ PASS |
| price_usd_original（paid non-upcoming） | 26.8% | ⚠ WARN（多數遊戲 appdetails 只回傳 TWD 價格，屬已知限制） |
| release_date coverage | 97.1% | ✅ PASS |
| review_count coverage | 83.7% | ⚠ WARN（upcoming / 零評論遊戲本身就無 review summary，屬正常） |
| appids from phase1 in master | 100.0% | ✅ PASS |
| Source breakdown：appdetails only | 100.0% | — |
| Source breakdown：HTML fallback | 0.0% | — |
| Source breakdown：no source data | 0.0% | ✅ |

> 所有硬性門檻已通過，可以正式進入 Phase 3。

### 目前待辦 / 已知坑

| 項目 | 優先級 | 說明 |
|------|-------|------|
| `price_usd_original` 覆蓋率偏低（26.8%） | 🟢 低 | Steam appdetails 以 TWD 為主，USD 常缺。Phase 3 ranking 先以 TWD 為準，USD 可留待未來補 cc=us 的第二次請求 |
| `developer` / `publisher` 尚未輸出到 master | 🟡 中 | 原 appdetails JSON 已有，`parse_appdetails.py` 可於進入 Phase 3 前擴欄位 |
| `tags` / `genres` 尚未輸出 | 🟡 中 | Phase 6 題材熱度需要，建議 Phase 3 前補上 |
| `lowest_discount_percent` / `lowest_price_*` 全為 null | 🟢 低 | 無直接來源，待 Phase 4 daily snapshot 累積後可回算 |
| HANDOFF 文件 | ✅ 已建立 | 見 `HANDOFF.md`，包含接手 agent 的 1 分鐘 checklist |

### 下一步（建議執行順序）

1. **Phase 3：Market Proxy**（不需再爬資料，直接用 master CSV 計算）
   - `build_ranking.py`：review_count、positive_ratio、attention_score Top 100
   - `compute_attention.py`：`attention = log(review_count+1) * positive_ratio * age_decay(release_date)`
   - 輸出發售月份分布、價格帶分布給 Phase 5 使用
2. **Phase 4：Daily Snapshot**（**越早啟動越值錢**，建議與 Phase 3 並行）
   - 每日只抓 appreviews summary + 價格（不重抓 appdetails）
   - 建議用 Windows Task Scheduler 每日凌晨自動跑
3. **Phase 2.5（可選補強）**：擴 `parse_appdetails.py` 加上 developer / publisher / tags / genres 後重跑 `merge_master.py`

### 沿襲的技術守則

- 單線程 + 主動隨機節流（API 4.0~7.0s、HTML 2.3~3.8s，遇 429 自動上移）
- 只讀取、不爬個資、不重分發；cookie 只在 HTML fallback 時使用
- 每個 phase 一個資料夾 + 獨立 `README.md` + `config.py` + `sanity_check.py`
- 爬取與解析分離（`fetch_*.py` 只下載、`parse_*.py` 只抽欄位）
- 一筆一檔（JSON/HTML），支援中斷續跑

---

## 一、目標

### 立即目標
建立 AO 遊戲資料庫，至少包含：
- appid
- title
- release_date
- review_count
- follower_count
- price
- developer / publisher

👉 用來：
- 排行
- 市場分布
- 銷量 proxy（review + follower）

---

### 中期目標
建立每日快照：
- review_count_daily
- follower_count_daily
- price_daily

👉 可做：
- 成長榜
- 新作動能
- 熱度曲線

---

### 終局目標（Dashboard）
首頁包含：

#### 市場總覽
- AO 總數
- upcoming 數量
- 本月新作
- 平均價格

#### 榜單
- follower 成長榜
- review 成長榜
- upcoming 熱度榜

#### 分析
- 題材熱度
- 發售月份分布
- 價格帶分析
- publisher 強度

#### Intelligence
- 題材過熱
- 檔期擁擠
- 爆款預警

---

## 二、資料來源策略

### 主來源（核心）
- Steam AO 入口頁（你現在抓的 8677）

### 次來源
- Steam 商店頁（reviews / metadata）
- SteamDB（followers）

### 不採用主來源
- ❌ SteamSpy（只做補充）

---

## 三、Phase Roadmap

---

## Phase 0：資料定義
定義：
- 資料表
- 欄位
- snapshot 規則

---

## Phase 1：AO Universe
👉 抓所有 appid

來源：
- AO all
- AO upcoming

輸出：
- ao_apps_raw
- ao_apps_deduped

---

## Phase 2：Master Data
👉 抓每個遊戲詳細資料

來源：
- Steam 商店頁
- SteamDB（followers）

---

## Phase 3：Market Proxy
👉 建立銷量代理

使用：
- review_count
- follower_count

輸出：
- attention score
- ranking

---

## Phase 4：Daily Snapshot
👉 建立時間序列

每天更新：
- reviews
- followers
- price

---

## Phase 5：Dashboard
👉 可視化

- 排行
- 分布
- 成長

---

## Phase 6：市場 Intelligence
👉 分析層

- 題材熱度
- 發行商分析
- 檔期分析

---

## Phase 7：預測模型
👉 進階分析

- 成長曲線
- 銷量區間
- 檔期建議

---

## 四、核心資料表

### ao_apps_raw
- appid
- name
- source_tab

### ao_games_master
- appid
- title
- review_count
- follower_count
- price

### ao_daily_snapshots
- date
- appid
- review_count
- follower_count

---

## 五、執行順序

1. Phase 1（抓 universe）
2. Phase 2（補 reviews + followers）
3. Phase 3（做 ranking）
4. Phase 4（開始 snapshot）
5. Phase 5（dashboard）

---

## 六、關鍵成功點

- 先抓全 appid（最重要）
- 盡早開始 snapshot（越早越值錢）
- 不追求一開始精準模型
- 先做 ranking > 再做 prediction
