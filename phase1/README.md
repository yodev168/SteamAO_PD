# Phase 1a: Steam AO AppID Crawler

使用 Steam Search endpoint 抓取所有已發售 AO 遊戲的 appid（約 5476 筆）。

---

## 環境需求

- Python 3.9+
- 在專案根目錄安裝依賴：

```powershell
cd ..
pip install -r requirements.txt
```

---

## Step 1：匯出 Steam Cookie（必做，只做一次）

1. 開啟 Chrome 或 Edge，**用乾淨的小帳**登入 Steam
   - 建議不要用主帳號（保護隱私）
   - 免費帳號即可，不需要購買遊戲

2. 進入 `https://store.steampowered.com/adultonly`
   - 如果出現年齡確認彈窗，點「Continue」確認

3. 按 F12 開啟 DevTools → 選 **Application** 頁籤
   → 左側展開 **Cookies** → 點 `https://store.steampowered.com`

4. 找到並複製以下 5 個 cookie 的值：

   | Cookie 名稱 | 說明 |
   |------------|------|
   | `sessionid` | session 識別碼 |
   | `steamLoginSecure` | 登入驗證 token（重要） |
   | `birthtime` | 年齡驗證，填 `631152001`（1990-01-01）即可 |
   | `wants_mature_content` | 必須為 `1` |
   | `lastagecheckage` | 填 `1-0-1990` 即可 |

5. 在 `phase1/` 資料夾下建立 `cookies.json`（**不要** commit 這個檔案）：

   ```json
   {
     "sessionid": "你複製的值",
     "steamLoginSecure": "你複製的值",
     "birthtime": "631152001",
     "wants_mature_content": "1",
     "lastagecheckage": "1-0-1990"
   }
   ```

   > 範例檔：`cookies.example.json`

---

## Step 2：執行爬蟲

在 `phase1/` 資料夾下執行（順序固定）：

```powershell
cd phase1

# 1. 爬取（約 3~5 分鐘，支援中斷後重跑）
python crawl_search.py

# 2. 合併輸出 CSV
python merge_export.py

# 3. 驗證結果
python sanity_check.py
```

---

## 產出檔案

| 檔案 | 說明 |
|------|------|
| `raw/search_start_N.json` | 每頁的原始 API response（用於重新 parse） |
| `crawl_log.jsonl` | 每頁的爬取 log（JSON Lines 格式） |
| `ao_apps_raw.csv` | 完整原始清單（含重複） |
| `ao_apps_deduped.csv` | 去重後的最終 appid 清單 |

---

## 斷點續跑

`crawl_search.py` 在重跑時會自動跳過 `raw/` 裡已存在的檔案。
直接重跑即可，不會浪費 API 呼叫：

```powershell
python crawl_search.py  # 自動從中斷點繼續
```

---

## 常見問題

**Q: 跑到一半顯示「cookie 失效」？**
回到 Step 1 重新複製 cookie 更新 `cookies.json`，然後重跑。

**Q: 出現 HTTP 429？**
程式會自動等待 5 分鐘後重試，不需要手動處理。

**Q: `ao_apps_deduped.csv` 筆數和 Steam 顯示的不完全一樣？**
Steam 頁面上的數字和 API 回傳偶爾有 ±10 的差距，屬正常現象。
執行 `python sanity_check.py` 查看詳細比對結果。

---

## Cookie 有效期

Steam cookie 約 30 天過期。如果 30 天後要重新爬取，
只需更新 `cookies.json`，然後清除 `raw/` 資料夾後重跑。

---

## GUI 啟動方式（推薦）

不需要開 terminal，直接雙擊使用。

### 方法一：雙擊 .bat 啟動（最簡單）

在專案根目錄 `SteamPD/` 找到 `run_gui.bat`，雙擊執行。
視窗會直接打開，不會出現黑色 console。

### 方法二：從 terminal 啟動

```powershell
cd phase1
python gui.py
```

### GUI 功能說明

| 區域 | 功能 |
|------|------|
| 頂部 Cookie 狀態 | 自動檢查 `cookies.json` 是否存在且完整，顯示綠/橙/紅 |
| `1. Crawl` 按鈕 | 執行 `crawl_search.py`（約 3-5 分鐘） |
| `2. Merge` 按鈕 | 執行 `merge_export.py`，輸出 CSV |
| `3. Sanity Check` 按鈕 | 執行 `sanity_check.py`，驗證結果 |
| 進度條 | 即時顯示 `X / 5476` 筆進度 |
| Log 視窗 | 彩色即時 log（綠=成功 / 橙=警告 / 紅=錯誤 / 灰=快取） |
| CSV Preview | 完成後自動顯示 `ao_apps_deduped.csv` 前 200 筆 |
| `Stop` 按鈕 | 中止目前執行中的腳本（重跑會從斷點繼續） |
| `Open raw/` | 直接開啟 raw 資料夾（檔案總管） |
| `Open CSV` | 用預設程式開啟 CSV（通常是 Excel） |

### 執行順序（和 terminal 版相同）

1. 確認 Cookie 狀態顯示綠色
2. 點「1. Crawl」→ 等進度條跑完
3. 點「2. Merge」→ CSV Preview 自動刷新
4. 點「3. Sanity Check」→ 確認 Log 出現 ALL CHECKS PASSED
