# Steam AO 市場資料專案 — Agent 交接文件

> 最後更新：2026-04-22
> 交接對象：接手本專案的下一位 agent
> 前置閱讀：`steam_ao_market_full_project_plan.md`、`phase1/README.md`、`phase2/README.md`

---

## 1. 專案一句話

為 Steam「僅限成人（Adult Only / AO）」遊戲建立資料庫，目標終局是 dashboard + 市場 intelligence + 銷量預測。當前在資料採集層（Phase 1~2），**尚未開始分析層（Phase 3+）**。

---

## 2. 目前完成度總覽

| Phase | 狀態 | 備註 |
|-------|------|------|
| Phase 0：資料定義 | ✅ 完成 | 見 `steam_ao_market_full_project_plan.md` |
| Phase 1：AO Universe | ✅ 完成 | 產出 `phase1/ao_apps_deduped.csv`，**5360 筆** |
| Phase 2：Master Data | 🟡 **部分完成，需補跑** | 已產出 `phase2/ao_games_master.csv`（5367 筆），但 reviews 和 html fallback 未跑完 |
| Phase 3：Market Proxy | ⬜ 未開始 | |
| Phase 4：Daily Snapshot | ⬜ 未開始 | |
| Phase 5：Dashboard | ⬜ 未開始 | |
| Phase 6：Intelligence | ⬜ 未開始 | |
| Phase 7：預測模型 | ⬜ 未開始 | |

---

## 3. Phase 2 目前真實狀態（重要）

雖然 `ao_games_master.csv` 已產出，但實際資料覆蓋率還沒到位。交接時的實測數字：

```
phase2/raw/appdetails/*.json   : 4503 / 5360  (~84%)
phase2/raw/reviews/*.json      : 2116 / 5360  (~39%)   ← 明顯不足
phase2/raw/html/*.html         :    0          ← 從未跑過 fallback
phase2/raw/errors/             :    0 檔
phase2/ao_games_master.csv     : 5367 列
phase2/missing_report.csv      : 5367 列       ← 幾乎每一筆都缺 review_count
```

### 解讀

1. **appdetails 仍有約 857 筆未抓**：這些是還沒執行完 `fetch_appdetails.py` 的 appid，或是被 API 退件的。
2. **reviews 只有 39%**：`fetch_reviews.py` 顯然中途被中斷過，需要重跑（有 checkpoint，會自動跳過已抓的）。
3. **HTML fallback 從未執行**：`fetch_store_html.py` 還沒跑。對於 appdetails 抓不到的那 ~857 筆（很多 AO 遊戲因為年齡牆會讓 appdetails 回空），需要這步補。
4. **master CSV 有 5367 列 vs phase1 5360 筆**：差 7 筆，合理推測是執行期間有重複或 extra，需要由 `sanity_check.py` 的 output 來確認。
5. **missing_report 5367 筆全有缺欄位**：主要因素是 reviews 只跑 39%，補完 reviews 後此數字應該降到 500 以下。

---

## 4. 下一個 agent 的 **立刻要做的 3 件事**

**順序很重要，請嚴格按順序執行。**

### Step A：補齊 Phase 2 資料（0.5~1 天內完成）

```powershell
cd phase2

# 1. 補完 appdetails（已抓會跳過，只會補剩下的 ~857 筆，約 1~1.5 小時）
python fetch_appdetails.py

# 2. 補完 reviews（已抓會跳過，還有 ~3244 筆要跑，約 3~5 小時）
python fetch_reviews.py

# 3. 對 appdetails 失敗的遊戲補抓 HTML（第一次全量，約 1~2 小時）
#    執行前請先確認 phase1/cookies.json 還沒過期（若過期，依 phase1/README.md 重新匯出）
python fetch_store_html.py

# 4. 重新合併
python merge_master.py

# 5. 檢查
python sanity_check.py
```

### Step B：sanity_check 必須達到的門檻

跑完 Step A 後，`sanity_check.py` 的輸出必須滿足：

| 指標 | 合格門檻 |
|------|---------|
| Row count | = 5360（若出現 extra，要回去修 `merge_master.py` 或 `load_appids.py` 的去重邏輯） |
| name coverage | ≥ 99% |
| price_twd_original | ≥ 90%（paid non-upcoming） |
| release_date | ≥ 95% |
| review_count | ≥ 99% |
| no source data | ≤ 1%（理想是 0） |

**不達門檻不要進 Phase 3。** 缺的那批先去 `missing_report.csv` 抽樣排查是 API 問題還是解析問題，優先改 `parse_store_html.py` / `parse_appdetails.py`，而不是硬上 Phase 3。

### Step C：Git commit + 打 tag（避免資料遺失）

```powershell
cd ..
# 確認 .gitignore 有把 raw/ 和 cookies.json 排除（已經有了，但還是要看一下）
git status
# Commit 設定檔和產出 CSV（raw/ 不進 repo，但 CSV 和 log 建議進）
git add phase2/ao_games_master.csv phase2/missing_report.csv phase2/crawl_log.jsonl
git commit -m "phase2: complete master data for 5360 AO games"
git tag phase2-done
```

> 備註：`raw/` 底下的 JSON/HTML 檔案總量約 300~500MB，**不要 commit**。CSV 才是最終交付物。

---

## 5. 完成 Phase 2 後的執行方向（Phase 3 開始）

### Phase 3：Market Proxy（建議下一步做）

**目標**：不靠 SteamSpy、不靠 SteamDB API，純用我們手上的 review_count + release_date 做「關注度 proxy」與排行。

**建議新增的檔案結構**：

```
phase3/
├── README.md
├── config.py
├── build_ranking.py          # 產出排行（follower proxy）
├── compute_attention.py      # 關注度分數
└── ao_games_ranked.csv       # 輸出
```

**attention score 初版公式建議**（可迭代）：

```python
# review_count 越高 → 越多人玩過
# review 越新（發售日越近）→ 相對關注越高
# review_positive / review_count → 口碑加權
attention = log(review_count + 1) * positive_ratio * age_decay(release_date)
```

**此階段不需要再爬新資料**，純用 `ao_games_master.csv` 做欄位計算與排序。做完可輸出：

- Top 100 by review_count
- Top 100 by positive_ratio（review_count ≥ 50 才入榜，避免少量評論的偏差）
- Top 100 by attention_score
- 發售月份分布、價格帶分布（給 Phase 5 的 dashboard 吃）

### Phase 4：Daily Snapshot（時間序列的起點，越早開始越值錢）

**這一步越早啟動越好**，因為每一天沒跑就永遠缺一天的資料，無法補。

**建議新增的檔案結構**：

```
phase4/
├── README.md
├── snapshot_daily.py         # 每天跑一次，只抓 reviews summary + price
├── raw/snapshots/YYYY-MM-DD/ # 每天一個資料夾
└── ao_daily_snapshots.csv    # 累積時間序列
```

**關鍵原則**：

- 每日 snapshot **只抓 appreviews + 價格**（不要重抓 appdetails；release_date、name 從 master 來）
- 每天跑的耗時：只有 5360 × 約 3s = ~5 小時（比 Phase 2 輕）
- 建議用 Windows Task Scheduler 每日凌晨自動執行
- 輸出欄位：`date, appid, review_count, review_positive, review_negative, price_twd, price_usd`
- **盡早啟動**，跑一個月後 Phase 6 的成長榜、熱度曲線才會有意義

### Phase 5：Dashboard（資料到位後才做）

建議技術棧選擇（二選一）：

- **輕量方案**：Streamlit 或 Gradio（Python，一週內可出 MVP）
- **正式方案**：Next.js + 一個 SQLite / DuckDB 當後端，前端用 shadcn/ui + recharts

先做 Streamlit MVP 驗證資料好不好看，再決定要不要上正式方案。

### Phase 6 / 7

Phase 6 和 7 需要至少 30 天的 daily snapshot 資料才有意義，**先不用花時間**，等 Phase 4 的資料累積起來再回頭做。

---

## 6. 重要技術守則（沿襲既有風格，不要違反）

這些是前面 agent 已經建立的專案慣例，**不要隨意改**：

### 爬蟲風險規避（避險 > 效率）

- ✅ **單線程 + 主動隨機節流**（不要改成多線程、不要改成 asyncio）
  - API 延遲區間 4.0~7.0s；HTML 2.3~3.8s
  - 遇 429 整個區間會自動上移，連續成功再逐步回到起點
- ✅ **只做讀取**：不發評論、不加好友、不加購物車
- ✅ **不爬個資**：只存 review summary，不存評論內容與作者名
- ✅ **本地存檔**：資料只在本機，不上傳、不對外 API 分享
- ✅ **Cookie 盡量少用**：只有 `fetch_store_html.py` 才用 cookie

### 程式結構慣例

- 每個 phase 獨立一個資料夾，獨立 `README.md` + `config.py`
- 所有爬蟲：**一筆一檔**（JSON 或 HTML），方便中斷續跑
- 解析邏輯和爬取邏輯分離：`fetch_*.py` 只負責下載，`parse_*.py` 只負責抽欄位
- 每個 phase 結尾都要有 `sanity_check.py`，不過門檻不進下一階段

### 編碼／環境

- Python 3.9+
- Windows PowerShell 環境下開發，所有腳本要能處理 UTF-8 中文名稱（`safe_console_text()` 可參考）
- 依賴統一放專案根目錄 `requirements.txt`

---

## 7. 已知的坑與待辦

| 項目 | 優先級 | 說明 |
|------|-------|------|
| `master 有 5367 列 vs phase1 5360 列`，差 7 筆 | 🔴 高 | `merge_master.py` 或 `load_appids.py` 可能有重複 appid，`sanity_check.py` 會列出 extra appids，建議查清楚再往下做 |
| `fetch_reviews.py` 只跑完 39% | 🔴 高 | 必須重跑補齊，否則整個 Phase 3 的 ranking 會失真 |
| `fetch_store_html.py` 未執行 | 🟡 中 | 大約 800+ 筆只能靠 HTML 補，AO 遊戲的 appdetails 常因年齡牆回空 |
| `lowest_discount_percent` / `lowest_price_*` 都是 null | 🟢 低 | 目前 schema 預留但無來源，Phase 4 時可從 daily snapshot 累積的每日價格算出 |
| 沒有 developer / publisher 欄位 | 🟡 中 | `steam_ao_market_full_project_plan.md` 提到但目前 master 沒有。解析 appdetails 的 `developers` / `publishers` 即可補，建議 Phase 2.5 就加上 |
| 沒有 tags / genres | 🟡 中 | Phase 6 的「題材熱度」需要。要擴 `APPDETAILS_PARAMS` 的 filters 或用 storesearch API 補 |
| cookies.json 過期偵測 | 🟢 低 | `fetch_store_html.py` 在開跑前有 validate，但建議改成每次跑前都 validate 並提示 |

---

## 8. 檔案地圖（給不熟悉專案的 agent）

```
SteamPD/
├── steam_ao_market_full_project_plan.md   # 專案總體企劃（必讀）
├── phase1_steam_ao_appid_spec.md          # Phase 1 規格
├── requirements.txt                        # Python 依賴
├── run_gui.bat                             # 啟動 GUI
├── HANDOFF.md                              # ← 本文件
│
├── phase1/                                 # ✅ 已完成
│   ├── README.md
│   ├── ao_apps_deduped.csv                 # 5360 筆，Phase 2 的輸入
│   ├── cookies.json                        # Steam 登入 cookie（勿上傳）
│   ├── crawl_search.py                     # AO universe 爬蟲
│   ├── merge_export.py
│   ├── sanity_check.py
│   ├── gui.py / gui_phase12.py             # Tkinter GUI（可選工具）
│   └── raw/
│
└── phase2/                                 # 🟡 需補跑
    ├── README.md                           # 詳細執行指引
    ├── config.py                           # endpoints / 節流參數 / 路徑
    ├── load_appids.py                      # 讀 phase1 deduped
    ├── fetch_appdetails.py                 # 公開 API（主來源）
    ├── fetch_reviews.py                    # 公開 API（review summary）
    ├── fetch_store_html.py                 # HTML fallback（需 cookie）
    ├── parse_appdetails.py
    ├── parse_reviews.py
    ├── parse_store_html.py
    ├── merge_master.py                     # 三來源合併
    ├── sanity_check.py
    ├── crawl_log.jsonl                     # 逐筆爬取日誌
    ├── ao_games_master.csv                 # 最終輸出（交付物）
    ├── missing_report.csv                  # 缺欄位清單
    └── raw/                                # 原始檔（勿進 git）
        ├── appdetails/*.json               # 4503 / 5360
        ├── reviews/*.json                  # 2116 / 5360
        ├── html/*.html                     # 0（未跑）
        └── errors/
```

---

## 9. 一分鐘上手 checklist（給接手 agent）

- [ ] 讀 `steam_ao_market_full_project_plan.md`（5 分鐘）
- [ ] 讀 `phase2/README.md`（3 分鐘）
- [ ] 讀本文件 Section 3 的「目前真實狀態」
- [ ] `cd phase2` 跑 Step A 的 5 個指令（總計約 5~8 小時，可跨夜執行）
- [ ] 看 `sanity_check.py` 輸出是否全 PASS
- [ ] 若全 PASS → 建立 `phase3/` 開始 ranking
- [ ] 若有 FAIL → 先查 `missing_report.csv`，補哪個來源、改哪個 parser
- [ ] **不要跳過 Phase 4**，daily snapshot 越早啟動越值錢

---

## 10. 一句話總結

> **把 Phase 2 補完 → 開 Phase 3 ranking → 同步啟動 Phase 4 每日 snapshot。Dashboard 和預測都是後話。**

資料先有、資料對、資料每天長。其他都是後續迭代。
