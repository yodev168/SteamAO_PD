# Phase 1：Steam AO AppID 抓取規格書

## 目標
從 Steam AO 入口頁抓出 **完整 appid universe**

---

## 成功標準

完成後可以回答：

- AO 總共有幾款
- upcoming 有幾款
- 去重後 universe 幾款

---

## 輸入

- AO ALL 頁
- AO UPCOMING 頁
- 已登入 Steam（必要）

---

## 輸出

### ao_apps_raw.csv

- appid
- name
- url
- source_tab
- discovered_at

---

### ao_apps_deduped.csv

- appid
- name
- source_all
- source_upcoming

---

## 核心流程

### Step 1：進入 AO 頁

開啟：
- all
- upcoming

---

### Step 2：找載入方式

判斷：

#### A. 有 page 參數
→ 用 page loop

#### B. 有 API / XHR
→ replay request

#### C. 沒有
→ 用 scroll

---

## Scroll Strategy（最重要）

流程：

1. 讀 DOM → 抽 appid
2. scroll 到底
3. 等待載入
4. 再抽 appid
5. 重複

---

### 停止條件

```txt
連續 3 次沒有新增 appid → STOP
```

---

## appid 抽取規則

從以下 pattern 抓：

```
/app/<appid>/
```

轉成：

```
https://store.steampowered.com/app/<appid>/
```

---

## 去重策略

使用 Set：

```ts
Set<string> appids
```

---

## 資料結構

```ts
type RawApp = {
  appid: string
  name: string
  url: string
  source_tab: "all" | "upcoming"
  discovered_at: string
}
```

---

## 任務拆分

### Task 1：extract_appid
輸入 HTML / DOM  
輸出 appid list

---

### Task 2：crawl_all
抓 AO all

---

### Task 3：crawl_upcoming
抓 AO upcoming

---

### Task 4：merge
合併 + 去重

---

### Task 5：export
輸出 CSV

---

## Log 格式

```txt
[AO-ALL] cycle=12 new=48 total=1832
[AO-ALL] cycle=13 new=37 total=1869
[AO-ALL] cycle=14 new=0 idle=1
[AO-ALL] cycle=15 new=0 idle=2
[AO-ALL] cycle=16 new=0 idle=3 STOP
```

---

## 錯誤處理

### 可忽略
- 單頁抓不到
- timeout

### 必須停止
- 登入失效
- AO 頁打不開

---

## 最重要原則

1. 只抓 appid，不抓細節
2. 不要一開始做複雜分析
3. 先抓全 → 再優化
4. 能重跑比優雅更重要

---

## 完成條件

✔ 抓完 AO ALL  
✔ 抓完 AO UPCOMING  
✔ 成功去重  
✔ 輸出 CSV  
✔ 可重跑  

---

## 一句話總結

👉 Phase 1 的唯一任務：

**「把 Steam AO 全部 appid 抓乾淨」**
