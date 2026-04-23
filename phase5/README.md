# Phase 5 — Steam AO 市場分析 Dashboard（MVP）

本地可運行的 Streamlit dashboard，讀取 `phase3/ao_games_cleaned.csv`，提供兩個視圖：

| 頁面 | 說明 |
|------|------|
| **遊戲清單** | 卡片網格瀏覽全部遊戲，支援搜尋 / 篩選 / 排序 / 分頁，點標題或按鈕可直接開啟 Steam 商店頁 |
| **發售熱度** | KPI 總覽 + 年份長條圖 + 年×月熱力圖 + 跨年折線圖，可切換「發售數量」或「預測銷售合計」指標 |

---

## 安裝

```powershell
# 在專案根目錄（SteamPD/）執行
pip install -r requirements.txt
```

---

## 啟動

### 方法一：PowerShell

```powershell
cd phase5
streamlit run app.py
```

### 方法二：雙擊 run.bat

直接雙擊 `phase5\run.bat`，瀏覽器會自動開啟 `http://localhost:8501`。

---

## 資料來源

- `phase3/ao_games_cleaned.csv`（4,620 筆，更新日期：2026-04-23）
- 欄位說明見 `phase3/config.py` 與主專案文件 `steam_ao_market_full_project_plan.md`

---

## 側邊欄篩選器（所有頁面共用）

| 篩選器 | 說明 |
|--------|------|
| 搜尋 | 對遊戲名稱 / 開發商 / 發行商模糊比對 |
| 台幣售價區間 | NT$ slider |
| 評價等級 | 壓倒性好評 → 尚無評論（多選） |
| 僅顯示有評論 | 勾選後排除零評論遊戲 |
| 發售年份 | 2013–2026（多選） |
| 排序方式 | 預測銷售 / 評論數 / 發售日 / 台幣價 / 好評率 |

---

## 待補資料

- `price_usd_original`（美金售價）：顯示「—（資料補齊中）」，待重爬 cc=us 請求後補入
- `developer` / `publisher`：同上，已在 Phase 2.5 計畫中

---

## 下一步（Phase 5 完整版）

- 首頁市場總覽卡片（AO 總數 / 本月新作 / 平均價格 / Top 榜單）
- 價格帶分布分析
- Publisher 強度分析
- Phase 4 Daily Snapshot 接入後的成長榜單
