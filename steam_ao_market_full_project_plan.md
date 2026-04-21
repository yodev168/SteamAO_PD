# Steam AO 市場資料平台完整企劃

## 專案定位
建立一套針對 Steam「僅限成人（Adult Only / AO）」市場的資料蒐集、分析與預測系統。

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
