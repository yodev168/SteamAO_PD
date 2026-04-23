import csv
import json
import os
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk

BASE = Path(__file__).parent
PHASE2 = BASE.parent / "phase2"
PHASE3 = BASE.parent / "phase3"

P1_COOKIES = BASE / "cookies.json"
P1_DEDUPED = BASE / "ao_apps_deduped.csv"
P1_RAW_DIR = BASE / "raw"

P2_MASTER = PHASE2 / "ao_games_master.csv"
P2_RAW_DIR = PHASE2 / "raw"
P2_MISSING = PHASE2 / "missing_report.csv"

P3_CLEANED = PHASE3 / "ao_games_cleaned.csv"

REQUIRED_COOKIE_KEYS = {
    "sessionid",
    "steamLoginSecure",
    "birthtime",
    "wants_mature_content",
    "lastagecheckage",
}

P1_PROGRESS_RE = re.compile(r"total=(\d+)/(\d+)")
P2_PROGRESS_RE = re.compile(r"\]\s+(\d+)/(\d+)\s+appid=")
PREVIEW_MAX_ROWS = 200

BG = "#1e1e2e"
FG = "#cdd6f4"
ACCENT = "#89b4fa"
GREEN = "#a6e3a1"
ORANGE = "#fab387"
RED = "#f38ba8"
GRAY = "#585b70"
BTN_BG = "#313244"
BTN_ACTIVE = "#45475a"
HEADER_BG = "#181825"


def _open_path(path: Path) -> None:
    target = path if path.exists() else path.parent
    if os.name == "nt":
        os.startfile(str(target))
    else:
        subprocess.run(["xdg-open", str(target)], check=False)


def make_btn(parent, text: str, command, side: str = "left", padx: int = 2, fg: str = FG) -> tk.Button:
    b = tk.Button(
        parent,
        text=text,
        command=command,
        bg=BTN_BG,
        fg=fg,
        activebackground=BTN_ACTIVE,
        activeforeground=FG,
        relief="flat",
        font=("Microsoft JhengHei UI", 9),
        padx=8,
        pady=3,
        cursor="hand2",
    )
    b.pack(side=side, padx=padx)
    return b


class RunnerTab:
    def __init__(self) -> None:
        self.proc: subprocess.Popen | None = None
        self.log_queue: queue.Queue = queue.Queue()

    def _run_script(self, script_name: str, extra_args: list[str] | None = None) -> None:
        if self.proc and self.proc.poll() is None:
            messagebox.showwarning("執行中", "已有任務執行中，請先停止或等待完成。")
            return

        self._reset_progress()
        self._append_log(f"\n{'=' * 60}\n", None)
        self._append_log(f"[開始] {script_name}\n", "start")
        self._append_log(f"{'=' * 60}\n", None)
        display_cmd = script_name if not extra_args else f"{script_name} {' '.join(extra_args)}"
        self.status_label.config(text=f"執行中：{display_cmd}")

        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        cmd = [sys.executable, "-u", script_name]
        if extra_args:
            cmd.extend(extra_args)
        self.proc = subprocess.Popen(
            cmd,
            cwd=self.script_cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=flags,
        )
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self) -> None:
        for line in self.proc.stdout:
            self.log_queue.put(line)
        self.log_queue.put(("__done__", self.proc.wait()))

    def _pump_output(self) -> None:
        try:
            while True:
                item = self.log_queue.get_nowait()
                if isinstance(item, tuple) and item[0] == "__done__":
                    code = item[1]
                    self.status_label.config(text=f"完成（結束碼 {code}）" if code == 0 else f"發生錯誤（結束碼 {code}）")
                    self._append_log(f"\n[完成] 結束碼={code}\n{'=' * 60}\n", "done" if code == 0 else "error")
                    self.refresh_preview()
                    continue

                line = item
                self._append_log(line)
                m = self.progress_re.search(line)
                if m:
                    current, total = int(m.group(1)), int(m.group(2))
                    self.progress["maximum"] = total
                    self.progress["value"] = current
                    self.progress_label.config(text=f"{current:,} / {total:,}")
        except queue.Empty:
            pass
        self.frame.after(100, self._pump_output)

    def _append_log(self, line: str, forced_tag: str | None = None) -> None:
        tag = forced_tag
        if tag is None:
            if "[ERROR]" in line or "[FAIL]" in line or "FAIL" in line:
                tag = "error"
            elif "[WARN]" in line or "[NO_DATA]" in line:
                tag = "warn"
            elif "[CACHE]" in line:
                tag = "cache"
            elif "[START]" in line:
                tag = "start"
            elif "[DONE]" in line or "[PASS]" in line or "[END]" in line or "[OK" in line:
                tag = "done"

        self.log.configure(state="normal")
        self.log.insert("end", line, tag if tag else "")
        self.log.configure(state="disabled")
        self.log.see("end")

    def _stop_current(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self._append_log("\n[已停止] 使用者手動終止。\n", "warn")
            self.status_label.config(text="已由使用者停止")
        else:
            self._append_log("[提示] 目前沒有正在執行的任務。\n", None)

    def _clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self._reset_progress()
        self.status_label.config(text="")

    def _reset_progress(self) -> None:
        self.progress["value"] = 0
        self.progress["maximum"] = 100
        self.progress_label.config(text="— / —")

    def _build_progress(self) -> None:
        frame = tk.Frame(self.frame, bg=BG, padx=10, pady=2)
        frame.pack(fill="x")
        tk.Label(frame, text="進度：", bg=BG, fg=GRAY, font=("Microsoft JhengHei UI", 9)).pack(side="left", padx=(0, 6))
        self.progress = ttk.Progressbar(frame, style="AO.Horizontal.TProgressbar", orient="horizontal", length=500, mode="determinate")
        self.progress.pack(side="left", padx=(0, 10))
        self.progress_label = tk.Label(frame, text="— / —", bg=BG, fg=FG, font=("Microsoft JhengHei UI", 9))
        self.progress_label.pack(side="left")
        self.status_label = tk.Label(frame, text="", bg=BG, fg=GRAY, font=("Microsoft JhengHei UI", 9))
        self.status_label.pack(side="left", padx=10)

    def _build_log(self) -> None:
        lframe = tk.LabelFrame(self.frame, text="執行紀錄", bg=BG, fg=GRAY, font=("Microsoft JhengHei UI", 9), padx=4, pady=4)
        lframe.pack(fill="both", expand=True, padx=10, pady=(4, 2))
        self.log = scrolledtext.ScrolledText(
            lframe,
            bg="#11111b",
            fg=FG,
            insertbackground=FG,
            font=("Consolas", 9),
            wrap="word",
            state="disabled",
        )
        self.log.pack(fill="both", expand=True)
        self.log.tag_config("warn", foreground=ORANGE)
        self.log.tag_config("error", foreground=RED)
        self.log.tag_config("cache", foreground=GRAY)
        self.log.tag_config("start", foreground=ACCENT)
        self.log.tag_config("done", foreground=GREEN)

    def refresh_preview(self) -> None:
        self.tree.delete(*self.tree.get_children())
        if not self.preview_csv.exists():
            self.preview_status.config(text=self.preview_empty_text)
            return
        try:
            with open(self.preview_csv, encoding="utf-8-sig", newline="") as f:
                reader = csv.reader(f)
                headers = next(reader, None)
                rows = list(reader)
        except Exception as exc:
            self.preview_status.config(text=f"讀取 CSV 失敗：{exc}")
            return
        if not headers:
            self.preview_status.config(text=f"{self.preview_csv.name} 是空的")
            return

        self.tree["columns"] = headers
        for col in headers:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=self.get_col_width(col), minwidth=60, anchor="w")
        for row in rows[:PREVIEW_MAX_ROWS]:
            self.tree.insert("", "end", values=row)
        shown = min(PREVIEW_MAX_ROWS, len(rows))
        self.preview_status.config(text=f"共 {len(rows):,} 筆（顯示前 {shown} 筆）")

    def get_col_width(self, col: str) -> int:
        return 100


class Phase1Tab(RunnerTab):
    def __init__(self, notebook: ttk.Notebook) -> None:
        super().__init__()
        self.frame = tk.Frame(notebook, bg=BG)
        notebook.add(self.frame, text="  Phase 1  ")

        self.script_cwd = BASE
        self.progress_re = P1_PROGRESS_RE
        self.preview_csv = P1_DEDUPED
        self.preview_empty_text = "尚未生成 ao_apps_deduped.csv — 請先執行「爬取資料」和「合併輸出」"

        self._build_topbar()
        self._build_buttons()
        self._build_progress()
        self._build_log()
        self._build_preview()
        self.frame.after(100, self._pump_output)
        self.check_cookies()

    def _build_topbar(self) -> None:
        frame = tk.Frame(self.frame, bg=HEADER_BG, pady=6, padx=10)
        frame.pack(fill="x")
        tk.Label(frame, text="Steam AO 爬蟲  //  第一階段", bg=HEADER_BG, fg=ACCENT, font=("Microsoft JhengHei UI", 13, "bold")).pack(side="left")
        right = tk.Frame(frame, bg=HEADER_BG)
        right.pack(side="right")
        self.cookie_label = tk.Label(right, text="Cookie：檢查中...", bg=HEADER_BG, fg=FG, font=("Microsoft JhengHei UI", 10), padx=8)
        self.cookie_label.pack(side="left")
        make_btn(right, "重新檢查 Cookie", self.check_cookies, side="left")
        make_btn(right, "開啟 phase1 資料夾", lambda: _open_path(BASE), side="left")

    def _build_buttons(self) -> None:
        frame = tk.Frame(self.frame, bg=BG, pady=8, padx=10)
        frame.pack(fill="x")
        tk.Label(frame, text="執行步驟：", bg=BG, fg=GRAY, font=("Microsoft JhengHei UI", 9)).pack(side="left", padx=(0, 6))
        make_btn(frame, "1. 爬取資料", lambda: self._run_script("crawl_search.py"), side="left", padx=4)
        make_btn(frame, "2. 合併輸出", lambda: self._run_script("merge_export.py"), side="left", padx=4)
        make_btn(frame, "3. 驗證結果", lambda: self._run_script("sanity_check.py"), side="left", padx=4)
        tk.Label(frame, text="  |  ", bg=BG, fg=GRAY).pack(side="left")
        make_btn(frame, "停止", self._stop_current, side="left", padx=4, fg=RED)
        make_btn(frame, "清除紀錄", self._clear_log, side="left", padx=4)

    def _build_preview(self) -> None:
        pframe = tk.LabelFrame(self.frame, text="資料預覽  (ao_apps_deduped.csv)", bg=BG, fg=GRAY, font=("Microsoft JhengHei UI", 9), padx=4, pady=4)
        pframe.pack(fill="x", padx=10, pady=(2, 6))
        tv_frame = tk.Frame(pframe, bg=BG)
        tv_frame.pack(fill="both", expand=True)
        xscroll = ttk.Scrollbar(tv_frame, orient="horizontal")
        yscroll = ttk.Scrollbar(tv_frame, orient="vertical")
        self.tree = ttk.Treeview(tv_frame, style="AO.Treeview", xscrollcommand=xscroll.set, yscrollcommand=yscroll.set, height=8, show="headings")
        xscroll.config(command=self.tree.xview)
        yscroll.config(command=self.tree.yview)
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        tv_frame.grid_columnconfigure(0, weight=1)
        tv_frame.grid_rowconfigure(0, weight=1)
        footer = tk.Frame(pframe, bg=BG)
        footer.pack(fill="x", pady=(4, 0))
        self.preview_status = tk.Label(footer, text="（尚未生成）", bg=BG, fg=GRAY, font=("Microsoft JhengHei UI", 8))
        self.preview_status.pack(side="left")
        make_btn(footer, "重新整理預覽", self.refresh_preview, side="right", padx=2)
        make_btn(footer, "開啟 CSV", lambda: _open_path(P1_DEDUPED), side="right", padx=2)
        make_btn(footer, "開啟 raw 資料夾", lambda: _open_path(P1_RAW_DIR), side="right", padx=2)
        self.refresh_preview()

    def get_col_width(self, col: str) -> int:
        if col == "name":
            return 240
        if col == "url":
            return 200
        return 100

    def check_cookies(self) -> bool:
        if not P1_COOKIES.exists():
            self.cookie_label.config(text="Cookie：找不到檔案", fg=RED)
            return False
        try:
            with open(P1_COOKIES, encoding="utf-8") as f:
                data = json.load(f)
            missing = REQUIRED_COOKIE_KEYS - data.keys()
            if missing:
                self.cookie_label.config(text=f"Cookie：缺少欄位 [{', '.join(sorted(missing))}]", fg=ORANGE)
                return False
            self.cookie_label.config(text=f"Cookie：正常（{len(data)} 個欄位）", fg=GREEN)
            return True
        except Exception as exc:
            self.cookie_label.config(text=f"Cookie：格式錯誤（{exc}）", fg=RED)
            return False


class Phase2Tab(RunnerTab):
    def __init__(self, notebook: ttk.Notebook) -> None:
        super().__init__()
        self.frame = tk.Frame(notebook, bg=BG)
        notebook.add(self.frame, text="  Phase 2  ")

        self.script_cwd = PHASE2
        self.progress_re = P2_PROGRESS_RE
        self.preview_csv = P2_MASTER
        self.preview_empty_text = "尚未生成 ao_games_master.csv — 請先執行 1a/1b/2/3"

        self._build_topbar()
        self._build_buttons()
        self._build_progress()
        self._build_log()
        self._build_preview()
        self.frame.after(100, self._pump_output)
        self.check_preconditions()

    def _build_topbar(self) -> None:
        frame = tk.Frame(self.frame, bg=HEADER_BG, pady=6, padx=10)
        frame.pack(fill="x")
        tk.Label(frame, text="Steam AO 爬蟲  //  第二階段 Master Data", bg=HEADER_BG, fg=ACCENT, font=("Microsoft JhengHei UI", 13, "bold")).pack(side="left")
        right = tk.Frame(frame, bg=HEADER_BG)
        right.pack(side="right")
        self.precond_label = tk.Label(right, text="前置條件：檢查中...", bg=HEADER_BG, fg=FG, font=("Microsoft JhengHei UI", 10), padx=8)
        self.precond_label.pack(side="left")
        make_btn(right, "重新檢查", self.check_preconditions, side="left")
        make_btn(right, "開啟 phase2 資料夾", lambda: _open_path(PHASE2), side="left")

    def _build_buttons(self) -> None:
        frame = tk.Frame(self.frame, bg=BG, pady=6, padx=10)
        frame.pack(fill="x")
        row1 = tk.Frame(frame, bg=BG)
        row1.pack(fill="x", pady=(0, 4))
        tk.Label(row1, text="抓取步驟：", bg=BG, fg=GRAY, font=("Microsoft JhengHei UI", 9)).pack(side="left", padx=(0, 6))
        make_btn(row1, "1a. AppDetails", lambda: self._run_script("fetch_appdetails.py"), side="left", padx=4)
        make_btn(row1, "1b. Reviews", self._run_reviews, side="left", padx=4)
        tk.Label(row1, text="並行數", bg=BG, fg=GRAY, font=("Microsoft JhengHei UI", 9)).pack(side="left", padx=(8, 4))
        self.reviews_workers_var = tk.StringVar(value="3")
        self.reviews_workers_spin = tk.Spinbox(
            row1,
            from_=1,
            to=8,
            width=4,
            textvariable=self.reviews_workers_var,
            bg=BTN_BG,
            fg=FG,
            insertbackground=FG,
            relief="flat",
            font=("Consolas", 9),
            justify="center",
        )
        self.reviews_workers_spin.pack(side="left", padx=(0, 6))
        make_btn(row1, "2. HTML Fallback(需Cookie)", lambda: self._run_script("fetch_store_html.py"), side="left", padx=4)

        row2 = tk.Frame(frame, bg=BG)
        row2.pack(fill="x")
        tk.Label(row2, text="後處理：    ", bg=BG, fg=GRAY, font=("Microsoft JhengHei UI", 9)).pack(side="left", padx=(0, 6))
        make_btn(row2, "3. 合併 Master CSV", lambda: self._run_script("merge_master.py"), side="left", padx=4)
        make_btn(row2, "4. 驗證結果", lambda: self._run_script("sanity_check.py"), side="left", padx=4)
        tk.Label(row2, text="  |  ", bg=BG, fg=GRAY).pack(side="left")
        make_btn(row2, "停止", self._stop_current, side="left", padx=4, fg=RED)
        make_btn(row2, "清除紀錄", self._clear_log, side="left", padx=4)

    def _run_reviews(self) -> None:
        try:
            workers = int(self.reviews_workers_var.get().strip())
        except ValueError:
            messagebox.showwarning("參數錯誤", "並行數請輸入 1~8 的整數。")
            return
        if workers < 1 or workers > 8:
            messagebox.showwarning("參數錯誤", "並行數請輸入 1~8。")
            return
        self._run_script("fetch_reviews.py", ["--workers", str(workers)])

    def _build_preview(self) -> None:
        pframe = tk.LabelFrame(self.frame, text="資料預覽  (ao_games_master.csv)", bg=BG, fg=GRAY, font=("Microsoft JhengHei UI", 9), padx=4, pady=4)
        pframe.pack(fill="x", padx=10, pady=(2, 6))
        tv_frame = tk.Frame(pframe, bg=BG)
        tv_frame.pack(fill="both", expand=True)
        xscroll = ttk.Scrollbar(tv_frame, orient="horizontal")
        yscroll = ttk.Scrollbar(tv_frame, orient="vertical")
        self.tree = ttk.Treeview(tv_frame, style="AO.Treeview", xscrollcommand=xscroll.set, yscrollcommand=yscroll.set, height=8, show="headings")
        xscroll.config(command=self.tree.xview)
        yscroll.config(command=self.tree.yview)
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        tv_frame.grid_columnconfigure(0, weight=1)
        tv_frame.grid_rowconfigure(0, weight=1)
        footer = tk.Frame(pframe, bg=BG)
        footer.pack(fill="x", pady=(4, 0))
        self.preview_status = tk.Label(footer, text="（尚未生成）", bg=BG, fg=GRAY, font=("Microsoft JhengHei UI", 8))
        self.preview_status.pack(side="left")
        make_btn(footer, "重新整理預覽", self.refresh_preview, side="right", padx=2)
        make_btn(footer, "開啟 Master CSV", lambda: _open_path(P2_MASTER), side="right", padx=2)
        make_btn(footer, "開啟 missing_report", lambda: _open_path(P2_MISSING), side="right", padx=2)
        make_btn(footer, "開啟 raw 資料夾", lambda: _open_path(P2_RAW_DIR), side="right", padx=2)
        self.refresh_preview()

    def get_col_width(self, col: str) -> int:
        if col == "name":
            return 220
        if col in ("release_date", "review_score_desc", "fetched_at"):
            return 160
        if col in ("developer", "publisher"):
            return 180
        if col == "header_image":
            return 300
        if col in ("genres", "categories"):
            return 200
        if col == "recommendations_total":
            return 130
        if col == "appid":
            return 80
        if col in ("positive_ratio", "has_reviews"):
            return 100
        return 115

    def check_preconditions(self) -> bool:
        issues = []
        if not P1_DEDUPED.exists():
            issues.append("缺 ao_apps_deduped.csv")
        if not P1_COOKIES.exists():
            issues.append("缺 cookies.json")
        if issues:
            self.precond_label.config(text=f"前置條件：⚠ {'；'.join(issues)}", fg=ORANGE)
            return False
        self.precond_label.config(text="前置條件：正常", fg=GREEN)
        return True


class Phase3Tab(RunnerTab):
    def __init__(self, notebook: ttk.Notebook) -> None:
        super().__init__()
        self.frame = tk.Frame(notebook, bg=BG)
        notebook.add(self.frame, text="  Phase 3  ")

        self.script_cwd = PHASE3
        self.progress_re = P2_PROGRESS_RE
        self.preview_csv = P3_CLEANED
        self.preview_empty_text = "尚未生成 ao_games_cleaned.csv — 請先執行「清洗資料」"

        self._build_topbar()
        self._build_buttons()
        self._build_progress()
        self._build_log()
        self._build_preview()
        self.frame.after(100, self._pump_output)
        self.check_preconditions()

    def _build_topbar(self) -> None:
        frame = tk.Frame(self.frame, bg=HEADER_BG, pady=6, padx=10)
        frame.pack(fill="x")
        tk.Label(frame, text="Steam AO 爬蟲  //  第三階段 Market Proxy", bg=HEADER_BG, fg=ACCENT, font=("Microsoft JhengHei UI", 13, "bold")).pack(side="left")
        right = tk.Frame(frame, bg=HEADER_BG)
        right.pack(side="right")
        self.precond_label = tk.Label(right, text="前置條件：檢查中...", bg=HEADER_BG, fg=FG, font=("Microsoft JhengHei UI", 10), padx=8)
        self.precond_label.pack(side="left")
        make_btn(right, "重新檢查", self.check_preconditions, side="left")
        make_btn(right, "開啟 phase3 資料夾", lambda: _open_path(PHASE3), side="left")

    def _build_buttons(self) -> None:
        frame = tk.Frame(self.frame, bg=BG, pady=8, padx=10)
        frame.pack(fill="x")
        tk.Label(frame, text="執行步驟：", bg=BG, fg=GRAY, font=("Microsoft JhengHei UI", 9)).pack(side="left", padx=(0, 6))
        make_btn(frame, "1. 清洗資料", lambda: self._run_script("clean_master.py"), side="left", padx=4)
        tk.Label(frame, text="  |  ", bg=BG, fg=GRAY).pack(side="left")
        make_btn(frame, "停止", self._stop_current, side="left", padx=4, fg=RED)
        make_btn(frame, "清除紀錄", self._clear_log, side="left", padx=4)

    def _build_preview(self) -> None:
        pframe = tk.LabelFrame(self.frame, text="資料預覽  (ao_games_cleaned.csv)", bg=BG, fg=GRAY, font=("Microsoft JhengHei UI", 9), padx=4, pady=4)
        pframe.pack(fill="x", padx=10, pady=(2, 6))
        tv_frame = tk.Frame(pframe, bg=BG)
        tv_frame.pack(fill="both", expand=True)
        xscroll = ttk.Scrollbar(tv_frame, orient="horizontal")
        yscroll = ttk.Scrollbar(tv_frame, orient="vertical")
        self.tree = ttk.Treeview(tv_frame, style="AO.Treeview", xscrollcommand=xscroll.set, yscrollcommand=yscroll.set, height=8, show="headings")
        xscroll.config(command=self.tree.xview)
        yscroll.config(command=self.tree.yview)
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        tv_frame.grid_columnconfigure(0, weight=1)
        tv_frame.grid_rowconfigure(0, weight=1)
        footer = tk.Frame(pframe, bg=BG)
        footer.pack(fill="x", pady=(4, 0))
        self.preview_status = tk.Label(footer, text="（尚未生成）", bg=BG, fg=GRAY, font=("Microsoft JhengHei UI", 8))
        self.preview_status.pack(side="left")
        make_btn(footer, "重新整理預覽", self.refresh_preview, side="right", padx=2)
        make_btn(footer, "開啟 Cleaned CSV", lambda: _open_path(P3_CLEANED), side="right", padx=2)
        make_btn(footer, "開啟 phase3 資料夾", lambda: _open_path(PHASE3), side="right", padx=2)
        self.refresh_preview()

    def get_col_width(self, col: str) -> int:
        if col == "name":
            return 220
        if col in ("developer", "publisher"):
            return 180
        if col in ("genres", "categories"):
            return 200
        if col == "header_image":
            return 300
        if col in ("release_date", "review_score_desc", "fetched_at"):
            return 160
        if col == "recommendations_total":
            return 130
        if col == "est_sales_low":
            return 120
        if col in ("positive_ratio", "has_reviews"):
            return 100
        if col == "appid":
            return 80
        return 115

    def check_preconditions(self) -> bool:
        if not P2_MASTER.exists():
            self.precond_label.config(text="前置條件：⚠ 缺 ao_games_master.csv（請先完成 Phase 2）", fg=ORANGE)
            return False
        self.precond_label.config(text="前置條件：正常", fg=GREEN)
        return True


class CrawlerGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Steam AO 爬蟲")
        self.root.configure(bg=BG)
        self.root.minsize(980, 760)
        self.root.geometry("1160x820")
        self._setup_style()
        self._build_tabs()

    def _setup_style(self) -> None:
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "AO.Horizontal.TProgressbar",
            troughcolor=BTN_BG,
            background=ACCENT,
            bordercolor=BG,
            lightcolor=ACCENT,
            darkcolor=ACCENT,
        )
        style.configure(
            "AO.Treeview",
            background="#11111b",
            foreground=FG,
            fieldbackground="#11111b",
            rowheight=22,
            font=("Microsoft JhengHei UI", 9),
        )
        style.configure("AO.Treeview.Heading", background=BTN_BG, foreground=ACCENT, font=("Segoe UI", 9, "bold"))
        style.map("AO.Treeview", background=[("selected", BTN_ACTIVE)])
        style.configure("AO.TNotebook.Tab", padding=[12, 6], font=("Microsoft JhengHei UI", 10, "bold"))

    def _build_tabs(self) -> None:
        notebook = ttk.Notebook(self.root, style="AO.TNotebook")
        notebook.pack(fill="both", expand=True)
        self.phase1 = Phase1Tab(notebook)
        self.phase2 = Phase2Tab(notebook)
        self.phase3 = Phase3Tab(notebook)


def main() -> None:
    root = tk.Tk()
    app = CrawlerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
