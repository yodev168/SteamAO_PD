# Phase 2：Steam AO Master Data 抓取

對 phase1 的 5360 款 AO 遊戲，補齊 Master 層級資料，產出 `ao_games_master.csv`。

---

## 環境需求

- Python 3.9+
- 在專案根目錄安裝依賴（如果 phase1 裝過可跳過）：

```powershell
cd ..
pip install -r requirements.txt
```

---

## 依賴 Phase 1 的輸出

執行前確認以下檔案已存在：

| 檔案 | 說明 |
|------|------|
| `phase1/ao_apps_deduped.csv` | 5360 筆去重後的 appid 清單 |
| `phase1/cookies.json` | Steam 登入 cookie（HTML fallback 用） |

---

## 執行順序

在 `phase2/` 資料夾下依序執行：

```powershell
cd phase2

# 1. 抓 appdetails（公開 API，約 2.5 小時，可中斷續跑）
python fetch_appdetails.py

# 2. 抓 reviews summary（公開 API，約 2.5 小時，可中斷續跑）
python fetch_reviews.py

# 3. 對 appdetails 失敗的遊戲補抓 HTML（需 cookie，約 1~2 小時）
python fetch_store_html.py

# 4. 合併三個來源 → ao_games_master.csv
python merge_master.py

# 5. 驗證結果
python sanity_check.py
```

> **步驟 1 和 2 可以同時在兩個 terminal 跑**（各自是不同 endpoint，互不影響）。
> 如果想保守一點，依序跑也完全 OK。

---

## 中斷續跑

每支腳本都會把每筆結果存成獨立檔案：

- `raw/appdetails/<appid>.json`
- `raw/reviews/<appid>.json`
- `raw/html/<appid>.html`

重跑時，已存在的檔案會自動跳過（`[CACHE]` 顯示），不會浪費 API 呼叫。

---

## 產出檔案

| 檔案 | 說明 |
|------|------|
| `raw/appdetails/<appid>.json` | appdetails API 原始回應 |
| `raw/reviews/<appid>.json` | appreviews API 的 query_summary |
| `raw/html/<appid>.html` | 商店頁 HTML（只有 fallback 才產生） |
| `raw/errors/<appid>_*.txt` | 失敗記錄 |
| `crawl_log.jsonl` | 每筆的爬取 log |
| `ao_games_master.csv` | 最終輸出（5360 筆） |
| `missing_report.csv` | 缺欄位的 appid 清單 |

---

## ao_games_master.csv 欄位說明

| 欄位 | 型別 | 說明 |
|------|------|------|
| `appid` | int | 主鍵 |
| `name` | str | 遊戲標題 |
| `price_twd_original` | int / null | 原價（TWD，整數。NT$289 = 289） |
| `price_usd_original` | float / null | 原價（USD，小數。US$9.99 = 9.99） |
| `lowest_discount_percent` | int / null | 史低折扣百分比（目前預留欄位，預設 null） |
| `lowest_price_twd` | int / null | 史低價格（TWD，預留欄位，預設 null） |
| `lowest_price_usd` | float / null | 史低價格（USD，預留欄位，預設 null） |
| `is_free` | bool | 是否免費 |
| `release_date` | str / null | 發售日（原始字串，可能是中文日期或 "Coming Soon"） |
| `coming_soon` | bool | 是否尚未發售 |
| `review_count` | int | 總評論數 |
| `review_positive` | int | 正評數 |
| `review_negative` | int | 負評數 |
| `review_score` | int | Steam 評分（0~9） |
| `review_score_desc` | str | 評分說明（如 "Very Positive"） |
| `source_appdetails` | bool | 資料來源：公開 appdetails API |
| `source_html_fallback` | bool | 資料來源：商店 HTML 解析 |
| `fetched_at` | ISO8601 | 合併時間戳 |

---

## 預期耗時

| 步驟 | 預期時間 |
|------|---------|
| fetch_appdetails | 約 2.5 小時 |
| fetch_reviews | 約 2.5 小時 |
| fetch_store_html | 約 1~2 小時（視 fallback 數量） |
| merge_master | < 1 分鐘 |
| sanity_check | < 1 分鐘 |

---

## 預期磁碟用量

| 目錄 | 預估大小 |
|------|---------|
| `raw/appdetails/` | ~20 MB（5360 個 JSON） |
| `raw/reviews/` | ~10 MB（5360 個 JSON） |
| `raw/html/` | ~300~500 MB（1500~2700 個 HTML） |
| `ao_games_master.csv` | ~1~2 MB |

---

## 常見問題

**Q: fetch_store_html 顯示「Cookie validation failed」？**
回到 phase1/README.md 重新匯出 cookie，更新 `phase1/cookies.json` 後重跑。

**Q: 出現 HTTP 429？**
程式會自動等待 5 分鐘後重試，不需要手動處理。
另外腳本使用「主動式隨機節流」：平常每次請求就會在區間內隨機延遲（API 約 4.0~7.0s、HTML 約 2.3~3.8s）。
若遇到 429，整個延遲區間會再上移（例如 API 變成 2.6~4.0s），連續成功後才會逐步回到起始區間。

**Q: 一開始就出現 `ao_apps_deduped.csv has no valid rows`？**
先確認 `phase1/ao_apps_deduped.csv` 不是空檔，且 header 至少包含 `appid,name`。
如果你是手動編輯過 CSV，請保留原始欄位名稱，避免改到 `appid` 欄位。

**Q: sanity_check 顯示 price_twd_original 覆蓋率偏低？**
這通常是免費遊戲或 coming_soon 遊戲，不是錯誤。檢視 `missing_report.csv` 確認細節。

---

## 避險原則（風險規避）

- **單線程 + 主動隨機節流**：API 每次隨機延遲約 4.0~7.0s、HTML 約 2.3~3.8s；遇 429 區間會整體上移
- **只做讀取**：不發評論、不加好友、不加購物車
- **不爬個資**：只存 review summary，完全不存評論內容與作者
- **Cookie 只用在必要處**：只有 `fetch_store_html.py` 才用，且只打 appdetails 失敗的那些
- **本地存檔**：資料只存在本機，不上傳、不重分發
