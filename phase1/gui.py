"""
gui.py

Tkinter Dashboard for Phase 1a: Steam AO AppID Crawler.

Sections:
  - TopBar   : cookie status indicator + open-folder button
  - Buttons  : Crawl / Merge / Sanity / Stop / Clear
  - Progress : ttk.Progressbar + X/total label
  - Log      : live stdout from subprocess, colour-coded by tag
  - Preview  : first 200 rows of ao_apps_deduped.csv in a Treeview

Launch:
  python phase1/gui.py        (shows console)
  pythonw phase1/gui.py       (no console, for run_gui.bat)
  or double-click run_gui.bat
"""

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

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE = Path(__file__).parent
COOKIES = BASE / "cookies.json"
DEDUPED = BASE / "ao_apps_deduped.csv"
RAW_CSV = BASE / "ao_apps_raw.csv"
RAW_DIR = BASE / "raw"
LOG_FILE = BASE / "crawl_log.jsonl"

REQUIRED_COOKIE_KEYS = {
    "sessionid",
    "steamLoginSecure",
    "birthtime",
    "wants_mature_content",
    "lastagecheckage",
}

PROGRESS_RE = re.compile(r"total=(\d+)/(\d+)")
PREVIEW_MAX_ROWS = 200

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Main GUI class
# ---------------------------------------------------------------------------

class CrawlerGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Steam AO 爬蟲 — 第一階段")
        self.root.configure(bg=BG)
        self.root.minsize(900, 700)
        self.root.geometry("1100x780")

        self.proc: subprocess.Popen | None = None
        self.log_queue: queue.Queue = queue.Queue()

        self._build_topbar()
        self._build_buttons()
        self._build_progress()
        self._build_log()
        self._build_preview()

        # Start queue pump
        self.root.after(100, self._pump_output)

        # Initial cookie check
        self.check_cookies()

    # -----------------------------------------------------------------------
    # UI builders
    # -----------------------------------------------------------------------

    def _build_topbar(self) -> None:
        frame = tk.Frame(self.root, bg=HEADER_BG, pady=6, padx=10)
        frame.pack(fill="x")

        title = tk.Label(
            frame,
            text="Steam AO 爬蟲  //  第一階段",
            bg=HEADER_BG,
            fg=ACCENT,
            font=("微軟正黑體", 13, "bold"),
        )
        title.pack(side="left")

        # Right-side controls
        right = tk.Frame(frame, bg=HEADER_BG)
        right.pack(side="right")

        self.cookie_label = tk.Label(
            right,
            text="Cookie：檢查中...",
            bg=HEADER_BG,
            fg=FG,
            font=("微軟正黑體", 10),
            padx=8,
        )
        self.cookie_label.pack(side="left")

        self._btn(right, "重新檢查 Cookie", self.check_cookies, side="left")
        self._btn(right, "開啟 phase1 資料夾", lambda: self._open_path(BASE), side="left")

    def _build_buttons(self) -> None:
        frame = tk.Frame(self.root, bg=BG, pady=8, padx=10)
        frame.pack(fill="x")

        tk.Label(frame, text="執行步驟：", bg=BG, fg=GRAY,
                 font=("微軟正黑體", 9)).pack(side="left", padx=(0, 6))

        self._btn(frame, "1. 爬取資料",
                  lambda: self._run_script("crawl_search.py"), side="left", padx=4)
        self._btn(frame, "2. 合併輸出",
                  lambda: self._run_script("merge_export.py"), side="left", padx=4)
        self._btn(frame, "3. 驗證結果",
                  lambda: self._run_script("sanity_check.py"), side="left", padx=4)

        # Separator
        tk.Label(frame, text="  |  ", bg=BG, fg=GRAY).pack(side="left")

        self.stop_btn = self._btn(frame, "停止", self._stop_current,
                                  side="left", padx=4, fg=RED)
        self._btn(frame, "清除紀錄", self._clear_log, side="left", padx=4)

    def _build_progress(self) -> None:
        frame = tk.Frame(self.root, bg=BG, padx=10, pady=2)
        frame.pack(fill="x")

        tk.Label(frame, text="進度：", bg=BG, fg=GRAY,
                 font=("微軟正黑體", 9)).pack(side="left", padx=(0, 6))

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

        self.progress = ttk.Progressbar(
            frame,
            style="AO.Horizontal.TProgressbar",
            orient="horizontal",
            length=500,
            mode="determinate",
        )
        self.progress.pack(side="left", padx=(0, 10))

        self.progress_label = tk.Label(
            frame, text="— / —", bg=BG, fg=FG, font=("微軟正黑體", 9)
        )
        self.progress_label.pack(side="left")

        self.status_label = tk.Label(
            frame, text="", bg=BG, fg=GRAY, font=("微軟正黑體", 9)
        )
        self.status_label.pack(side="left", padx=10)

    def _build_log(self) -> None:
        lframe = tk.LabelFrame(
            self.root, text="執行紀錄", bg=BG, fg=GRAY,
            font=("微軟正黑體", 9), padx=4, pady=4,
        )
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

        # Colour tags
        self.log.tag_config("ok", foreground=GREEN)
        self.log.tag_config("warn", foreground=ORANGE)
        self.log.tag_config("error", foreground=RED)
        self.log.tag_config("cache", foreground=GRAY)
        self.log.tag_config("start", foreground=ACCENT)
        self.log.tag_config("done", foreground=GREEN)

    def _build_preview(self) -> None:
        pframe = tk.LabelFrame(
            self.root, text="資料預覽  (ao_apps_deduped.csv)",
            bg=BG, fg=GRAY, font=("微軟正黑體", 9), padx=4, pady=4,
        )
        pframe.pack(fill="x", padx=10, pady=(2, 6))

        # Treeview with scrollbars
        tv_frame = tk.Frame(pframe, bg=BG)
        tv_frame.pack(fill="both", expand=True)

        xscroll = ttk.Scrollbar(tv_frame, orient="horizontal")
        yscroll = ttk.Scrollbar(tv_frame, orient="vertical")

        style = ttk.Style()
        style.configure(
            "AO.Treeview",
            background="#11111b",
            foreground=FG,
            fieldbackground="#11111b",
            rowheight=20,
            font=("Consolas", 8),
        )
        style.configure("AO.Treeview.Heading",
                         background=BTN_BG, foreground=ACCENT,
                         font=("Segoe UI", 9, "bold"))
        style.map("AO.Treeview", background=[("selected", BTN_ACTIVE)])

        self.tree = ttk.Treeview(
            tv_frame,
            style="AO.Treeview",
            xscrollcommand=xscroll.set,
            yscrollcommand=yscroll.set,
            height=8,
            show="headings",
        )
        xscroll.config(command=self.tree.xview)
        yscroll.config(command=self.tree.yview)

        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        tv_frame.grid_columnconfigure(0, weight=1)
        tv_frame.grid_rowconfigure(0, weight=1)

        # Footer bar
        footer = tk.Frame(pframe, bg=BG)
        footer.pack(fill="x", pady=(4, 0))

        self.preview_status = tk.Label(
            footer, text="（尚未生成）", bg=BG, fg=GRAY,
            font=("微軟正黑體", 8)
        )
        self.preview_status.pack(side="left")

        self._btn(footer, "重新整理預覽", self.refresh_preview, side="right", padx=2)
        self._btn(footer, "開啟 CSV", lambda: self._open_path(DEDUPED), side="right", padx=2)
        self._btn(footer, "開啟 raw 資料夾", lambda: self._open_path(RAW_DIR), side="right", padx=2)

        # Load initial data if CSV already exists
        self.refresh_preview()

    # -----------------------------------------------------------------------
    # Cookie check
    # -----------------------------------------------------------------------

    def check_cookies(self) -> bool:
        if not COOKIES.exists():
            self.cookie_label.config(text="Cookie：找不到檔案", fg=RED)
            return False
        try:
            with open(COOKIES, encoding="utf-8") as f:
                data = json.load(f)
            missing = REQUIRED_COOKIE_KEYS - data.keys()
            if missing:
                short = ", ".join(sorted(missing))
                self.cookie_label.config(
                    text=f"Cookie：缺少欄位 [{short}]", fg=ORANGE
                )
                return False
            self.cookie_label.config(
                text=f"Cookie：正常  （{len(data)} 個欄位）", fg=GREEN
            )
            return True
        except Exception as exc:
            self.cookie_label.config(text=f"Cookie：格式錯誤  ({exc})", fg=RED)
            return False

    # -----------------------------------------------------------------------
    # Script runner
    # -----------------------------------------------------------------------

    def _run_script(self, script_name: str) -> None:
        if self.proc and self.proc.poll() is None:
            messagebox.showwarning(
                "執行中",
                "已有一個任務正在執行。\n請等待完成或按「停止」後再試。",
            )
            return

        # Guard: warn if no cookie before crawl
        if script_name == "crawl_search.py" and not self.check_cookies():
            if not messagebox.askyesno(
                "Cookie 缺失",
                "cookies.json 不存在或欄位不完整。\n\n"
                "請先參考 README.md 的步驟匯出 Steam Cookie。\n\n"
                "確定要繼續嗎？",
            ):
                return

        self._reset_progress()
        self._append_log(f"\n{'='*60}\n")
        self._append_log(f"[開始] {script_name}\n", "start")
        self._append_log(f"{'='*60}\n")
        self.status_label.config(text=f"執行中：{script_name}")

        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self.proc = subprocess.Popen(
            [sys.executable, "-u", script_name],
            cwd=BASE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=flags,
        )
        t = threading.Thread(target=self._reader, daemon=True)
        t.start()

    def _reader(self) -> None:
        """Background thread: read subprocess stdout line by line."""
        for line in self.proc.stdout:
            self.log_queue.put(line)
        exit_code = self.proc.wait()
        self.log_queue.put(("__done__", exit_code))

    # -----------------------------------------------------------------------
    # Output pump (runs on UI thread via after())
    # -----------------------------------------------------------------------

    def _pump_output(self) -> None:
        try:
            while True:
                item = self.log_queue.get_nowait()

                # Sentinel from _reader when process exits
                if isinstance(item, tuple) and item[0] == "__done__":
                    exit_code = item[1]
                    tag = "done" if exit_code == 0 else "error"
                    self.status_label.config(
                        text=f"完成（結束碼 {exit_code}）"
                        if exit_code == 0
                        else f"發生錯誤（結束碼 {exit_code}）"
                    )
                    self._append_log(
                        f"\n[完成] 結束碼={exit_code}\n{'='*60}\n", tag
                    )
                    # Auto-refresh preview after merge or sanity
                    self.refresh_preview()
                    continue

                line = item
                self._append_log(line)

                # Parse progress: total=X/Y
                m = PROGRESS_RE.search(line)
                if m:
                    current = int(m.group(1))
                    total = int(m.group(2))
                    self.progress["maximum"] = total
                    self.progress["value"] = current
                    self.progress_label.config(text=f"{current:,} / {total:,}")

        except queue.Empty:
            pass

        self.root.after(100, self._pump_output)

    # -----------------------------------------------------------------------
    # Log helpers
    # -----------------------------------------------------------------------

    def _append_log(self, line: str, forced_tag: str | None = None) -> None:
        tag = forced_tag
        if tag is None:
            if "[ERROR]" in line:
                tag = "error"
            elif "[WARN]" in line:
                tag = "warn"
            elif "[CACHE]" in line:
                tag = "cache"
            elif "[START]" in line:
                tag = "start"
            elif "[DONE]" in line or "DONE" in line or "[PASS]" in line:
                tag = "done"
            elif "[FAIL]" in line or "FAIL" in line:
                tag = "error"

        self.log.configure(state="normal")
        if tag:
            self.log.insert("end", line, tag)
        else:
            self.log.insert("end", line)
        self.log.configure(state="disabled")
        self.log.see("end")

    def _clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self._reset_progress()
        self.status_label.config(text="")

    # -----------------------------------------------------------------------
    # Progress helpers
    # -----------------------------------------------------------------------

    def _reset_progress(self) -> None:
        self.progress["value"] = 0
        self.progress["maximum"] = 100
        self.progress_label.config(text="— / —")

    # -----------------------------------------------------------------------
    # Stop
    # -----------------------------------------------------------------------

    def _stop_current(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self._append_log("\n[已停止] 使用者手動終止。\n", "warn")
            self.status_label.config(text="已由使用者停止")
        else:
            self._append_log("[提示] 目前沒有正在執行的任務。\n")

    # -----------------------------------------------------------------------
    # CSV Preview
    # -----------------------------------------------------------------------

    def refresh_preview(self) -> None:
        self.tree.delete(*self.tree.get_children())

        if not DEDUPED.exists():
            self.preview_status.config(
                text="尚未生成 ao_apps_deduped.csv — 請先執行「爬取資料」和「合併輸出」"
            )
            return

        try:
            with open(DEDUPED, encoding="utf-8-sig", newline="") as f:
                reader = csv.reader(f)
                try:
                    headers = next(reader)
                except StopIteration:
                    self.preview_status.config(text="ao_apps_deduped.csv 是空的")
                    return
                rows = list(reader)
        except Exception as exc:
            self.preview_status.config(text=f"讀取 CSV 失敗：{exc}")
            return

        # Configure columns dynamically from CSV headers
        self.tree["columns"] = headers
        for col in headers:
            width = 200 if col in ("name", "url") else 90
            self.tree.heading(col, text=col)
            self.tree.column(col, width=width, minwidth=50, anchor="w")

        for row in rows[:PREVIEW_MAX_ROWS]:
            self.tree.insert("", "end", values=row)

        shown = min(len(rows), PREVIEW_MAX_ROWS)
        self.preview_status.config(
            text=f"共 {len(rows):,} 筆  （顯示前 {shown} 筆）"
        )

    # -----------------------------------------------------------------------
    # Open path helper
    # -----------------------------------------------------------------------

    def _open_path(self, path: Path) -> None:
        target = path if path.exists() else path.parent
        if os.name == "nt":
            os.startfile(str(target))
        else:
            subprocess.run(["xdg-open", str(target)], check=False)

    # -----------------------------------------------------------------------
    # Widget factory
    # -----------------------------------------------------------------------

    def _btn(
        self,
        parent,
        text: str,
        command,
        side: str = "left",
        padx: int = 2,
        fg: str = FG,
    ) -> tk.Button:
        b = tk.Button(
            parent,
            text=text,
            command=command,
            bg=BTN_BG,
            fg=fg,
            activebackground=BTN_ACTIVE,
            activeforeground=FG,
            relief="flat",
            font=("微軟正黑體", 9),
            padx=8,
            pady=3,
            cursor="hand2",
        )
        b.pack(side=side, padx=padx)
        return b


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    root = tk.Tk()
    app = CrawlerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
