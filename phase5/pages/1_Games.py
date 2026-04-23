"""
pages/1_Games.py — 遊戲清單（卡片 / 清單 雙模式）
"""
import streamlit as st
import pandas as pd

from data import (
    load_games,
    steam_url,
    fmt_twd,
    fmt_usd,
    fmt_num,
    display_value,
    RATING_DISPLAY_ORDER,
    SORT_OPTIONS,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="遊戲清單 | Steam AO 分析",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    [data-testid="stSidebar"] { min-width: 280px; max-width: 320px; }
    .game-title { font-size: 0.95rem; font-weight: 700; line-height: 1.3; margin-bottom: 4px; }
    .muted { color: #888; font-size: 0.80rem; }
    .badge {
        display: inline-block;
        padding: 1px 7px;
        border-radius: 3px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-bottom: 4px;
    }
    .badge-pos  { background: #1a9441; color: #fff; }
    .badge-mix  { background: #b5a200; color: #fff; }
    .badge-neg  { background: #c0392b; color: #fff; }
    .badge-none { background: #555;    color: #ccc; }
    .steam-link a {
        display: inline-block;
        padding: 3px 10px;
        background: #1b2838;
        color: #c6d4df !important;
        border-radius: 4px;
        text-decoration: none;
        font-size: 0.80rem;
    }
    .steam-link a:hover { background: #2a475e; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
df_all = load_games()

st.sidebar.title("🎮 Steam AO 分析")
st.sidebar.markdown("---")

search_query = st.sidebar.text_input(
    "搜尋遊戲名稱 / 開發商 / 發行商",
    placeholder="輸入關鍵字…",
    key="search_query",
)

price_min_data = int(df_all["price_twd_original"].min(skipna=True))
price_max_data = int(df_all["price_twd_original"].max(skipna=True))
st.sidebar.markdown("**台幣售價區間（NT$）**")
pc1, pc2 = st.sidebar.columns(2)
price_low_text = pc1.text_input("最低", value=str(price_min_data), key="price_low_text")
price_high_text = pc2.text_input("最高", value=str(price_max_data), key="price_high_text")
try:
    price_low = int(price_low_text.strip()) if price_low_text.strip() else price_min_data
except ValueError:
    price_low = price_min_data
    st.sidebar.caption("最低價格式錯誤，已套用資料最小值。")
try:
    price_high = int(price_high_text.strip()) if price_high_text.strip() else price_max_data
except ValueError:
    price_high = price_max_data
    st.sidebar.caption("最高價格式錯誤，已套用資料最大值。")
price_low = max(0, min(price_low, price_max_data))
price_high = max(0, min(price_high, price_max_data))
if price_low > price_high:
    price_low, price_high = price_high, price_low
price_range = (price_low, price_high)

all_zh_ratings = RATING_DISPLAY_ORDER + ["少量評論"]
if "selected_ratings" not in st.session_state:
    st.session_state["selected_ratings"] = list(all_zh_ratings)
with st.sidebar.popover(
    f"評價等級（已選 {len(st.session_state['selected_ratings'])}/{len(all_zh_ratings)}）",
    use_container_width=True,
):
    rb1, rb2 = st.columns(2)
    if rb1.button("全選", key="rating_all", use_container_width=True):
        st.session_state["selected_ratings"] = list(all_zh_ratings)
        st.rerun()
    if rb2.button("清除", key="rating_none", use_container_width=True):
        st.session_state["selected_ratings"] = []
        st.rerun()
    new_ratings = []
    for r in all_zh_ratings:
        checked = st.checkbox(
            r,
            value=r in st.session_state["selected_ratings"],
            key=f"rating_chk_{r}",
        )
        if checked:
            new_ratings.append(r)
    st.session_state["selected_ratings"] = new_ratings
selected_ratings = st.session_state["selected_ratings"]

only_reviewed = st.sidebar.checkbox("僅顯示有評論的遊戲", value=False, key="only_reviewed")

all_years = sorted([int(y) for y in df_all["release_year"].dropna().unique()], reverse=True)
if "selected_years" not in st.session_state:
    st.session_state["selected_years"] = list(all_years[:5])
with st.sidebar.popover(
    f"發售年份（已選 {len(st.session_state['selected_years'])}/{len(all_years)}）",
    use_container_width=True,
):
    yb1, yb2 = st.columns(2)
    if yb1.button("全選", key="year_all", use_container_width=True):
        st.session_state["selected_years"] = list(all_years)
        st.rerun()
    if yb2.button("清除", key="year_none", use_container_width=True):
        st.session_state["selected_years"] = []
        st.rerun()
    new_years = []
    for y in all_years:
        checked = st.checkbox(
            str(y),
            value=y in st.session_state["selected_years"],
            key=f"year_chk_{y}",
        )
        if checked:
            new_years.append(y)
    st.session_state["selected_years"] = new_years
selected_years = st.session_state["selected_years"]

sort_label = st.sidebar.selectbox(
    "排序方式",
    options=list(SORT_OPTIONS.keys()),
    index=0,
    key="sort_label",
)

st.sidebar.markdown("---")
st.sidebar.caption("Phase 5 MVP · 資料日期：2026-04-23")


# ---------------------------------------------------------------------------
# Apply filters
# ---------------------------------------------------------------------------
def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    q = search_query.strip().lower()
    if q:
        mask = (
            df["name"].str.lower().str.contains(q, na=False)
            | df["developer"].astype(str).str.lower().str.contains(q, na=False)
            | df["publisher"].astype(str).str.lower().str.contains(q, na=False)
        )
        df = df[mask]
    df = df[
        df["price_twd_original"].between(price_range[0], price_range[1], inclusive="both")
    ]
    if selected_ratings:
        df = df[df["review_score_desc_zh"].isin(selected_ratings)]
    if only_reviewed:
        df = df[df["has_reviews"].astype(str).str.strip() == "True"]
    if selected_years:
        df = df[df["release_year"].isin(selected_years)]
    sort_col, ascending = SORT_OPTIONS[sort_label]
    return df.sort_values(sort_col, ascending=ascending, na_position="last").reset_index(drop=True)


df = apply_filters(df_all)

# ---------------------------------------------------------------------------
# Header + 模式切換
# ---------------------------------------------------------------------------
st.title("遊戲清單")

hcol1, hcol2 = st.columns([6, 2])
with hcol1:
    st.markdown(f"篩選結果：**{len(df):,}** 款遊戲")
with hcol2:
    view_mode = st.radio(
        "顯示模式",
        options=["🃏 卡片", "📋 清單"],
        horizontal=True,
        key="view_mode",
        label_visibility="collapsed",
    )

total = len(df)
if total == 0:
    st.warning("沒有符合條件的遊戲，請調整篩選條件。")
    st.stop()

# ---------------------------------------------------------------------------
# Pagination（卡片 30 筆 / 清單 50 筆）
# ---------------------------------------------------------------------------
PER_PAGE = 30 if view_mode == "🃏 卡片" else 50
total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)

if "games_page" not in st.session_state:
    st.session_state["games_page"] = 1

prev_total = st.session_state.get("games_prev_total", -1)
if prev_total != total:
    st.session_state["games_page"] = 1
    st.session_state["games_prev_total"] = total

current_page = st.session_state["games_page"]

start = (current_page - 1) * PER_PAGE
end   = min(start + PER_PAGE, total)
page_df = df.iloc[start:end]

# ===========================================================================
# 卡片模式
# ===========================================================================
POSITIVE_LABELS = {"壓倒性好評", "極度好評", "大多好評", "好評"}
NEGATIVE_LABELS = {"大多負評", "負評", "極度負評"}


def rating_badge(zh_label: str) -> str:
    if zh_label in POSITIVE_LABELS:
        cls = "badge-pos"
    elif zh_label in NEGATIVE_LABELS:
        cls = "badge-neg"
    elif zh_label == "褒貶不一":
        cls = "badge-mix"
    else:
        cls = "badge-none"
    return f'<span class="badge {cls}">{zh_label}</span>'


if view_mode == "🃏 卡片":
    COLS = 3
    for row_start in range(0, len(page_df), COLS):
        cols = st.columns(COLS)
        for ci, col in enumerate(cols):
            idx = row_start + ci
            if idx >= len(page_df):
                break
            row = page_df.iloc[idx]

            with col:
                # 縮圖
                img_url = str(row.get("header_image", "") or "").strip()
                if img_url and img_url != "nan":
                    st.image(img_url, use_container_width=True)
                else:
                    st.html(
                        '<div style="height:120px;background:#1a1a2e;border-radius:6px;'
                        'display:flex;align-items:center;justify-content:center;'
                        'color:#555;font-size:0.8rem;">無宣傳圖</div>'
                    )

                # 評論資料
                rc        = fmt_num(row.get("review_count"))
                rp        = fmt_num(row.get("review_positive"))
                rn        = fmt_num(row.get("review_negative"))
                ratio_raw = row.get("positive_ratio")
                try:
                    ratio_str = f"{float(ratio_raw) * 100:.1f}%"
                except (TypeError, ValueError):
                    ratio_str = "—"

                url      = steam_url(str(row["appid"]))
                name     = str(row.get("name") or "—")
                zh_rating = str(row.get("review_score_desc_zh") or "—")
                badge_html = rating_badge(zh_rating)
                twd      = fmt_twd(row.get("price_twd_original"))
                usd_raw  = row.get("price_usd_original")
                try:
                    usd_str = f"US$ {float(usd_raw):.2f}"
                except (TypeError, ValueError):
                    usd_str = ""
                rd       = row.get("release_date")
                rd_str   = pd.Timestamp(rd).strftime("%Y-%m-%d") if pd.notna(rd) else "—"
                dev      = display_value(row.get("developer"))
                pub      = display_value(row.get("publisher"))
                est      = fmt_num(row.get("est_sales_low"))

                usd_part = f'&nbsp;&nbsp;<span style="color:#888;font-size:0.80rem;">{usd_str}</span>' if usd_str else ""

                st.html(f"""
                <div style="padding:2px 0 8px 0;">
                  <div style="font-size:0.95rem;font-weight:700;line-height:1.4;margin-bottom:4px;">
                    <a href="{url}" target="_blank"
                       style="color:#c6d4df;text-decoration:none;">{name}</a>
                  </div>
                  <div style="margin-bottom:6px;display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
                    {badge_html}
                    <span style="color:#aaa;font-size:0.80rem;">
                      {rc} 則 &nbsp;
                      <span style="color:#5cb85c;">▲ {rp}</span>&nbsp;
                      <span style="color:#d9534f;">▼ {rn}</span>&nbsp;
                      好評率 {ratio_str}
                    </span>
                  </div>
                  <div style="font-size:0.95rem;font-weight:600;margin-bottom:2px;">
                    {twd}{usd_part}
                  </div>
                  <div style="color:#888;font-size:0.80rem;margin-bottom:2px;">發售日：{rd_str}</div>
                  <div style="color:#888;font-size:0.80rem;margin-bottom:2px;">開發：{dev}</div>
                  <div style="color:#888;font-size:0.80rem;margin-bottom:6px;">發行：{pub}</div>
                  <div style="font-size:0.82rem;margin-bottom:6px;">
                    <span style="color:#888;">預測銷售：</span>
                    <span style="font-weight:600;">{est} 套</span>
                  </div>
                  <a href="{url}" target="_blank"
                     style="display:inline-block;padding:3px 10px;background:#1b2838;
                            color:#c6d4df;border-radius:4px;text-decoration:none;
                            font-size:0.80rem;">在 Steam 開啟 ↗</a>
                  <hr style="margin:12px 0;border:none;border-top:1px solid #333;">
                </div>
                """)

# ===========================================================================
# 清單模式（HTML table，支援評論等級字體顏色）
# ===========================================================================
else:
    # Steam 配色：參考 Steam 評論顏色體系
    RATING_COLOR: dict[str, str] = {
        "壓倒性好評": "#4ade80",   # 亮綠（Overwhelmingly Positive）
        "極度好評":   "#4db366",   # 中綠（Very Positive）
        "大多好評":   "#66c0f4",   # Steam 藍綠（Mostly Positive）
        "好評":       "#66c0f4",   # Steam 藍綠（Positive）
        "褒貶不一":   "#b9a074",   # 黃褐（Mixed）
        "大多負評":   "#c0392b",   # 紅（Mostly Negative）
        "負評":       "#c0392b",   # 紅（Negative）
        "極度負評":   "#8b1a1a",   # 深紅（Overwhelmingly Negative）
        "少量評論":   "#888888",   # 灰
        "尚無評論":   "#888888",   # 灰
    }

    def _rating_text(r) -> tuple[str, str]:
        """Return (display_text, css_color)."""
        rating = str(r.get("review_score_desc_zh") or "—")
        color  = RATING_COLOR.get(rating, "#888888")
        count  = r.get("review_count")
        ratio  = r.get("positive_ratio")
        try:
            if pd.isna(count) or int(count) == 0:
                return rating, color
        except (TypeError, ValueError):
            return rating, color
        ratio_s = f"{float(ratio) * 100:.1f}%" if pd.notna(ratio) else "—"
        text = f"{rating} · {int(count):,} 則 ({ratio_s})"
        return text, color

    def _fmt_price(val) -> str:
        try:
            v = int(val)
            return f"NT$ {v:,}"
        except (TypeError, ValueError):
            return "—"

    def _fmt_sales(val) -> str:
        try:
            return f"{int(val):,} 套"
        except (TypeError, ValueError):
            return "—"

    def _fmt_date(val) -> str:
        try:
            return pd.Timestamp(val).strftime("%Y-%m-%d") if pd.notna(val) else "—"
        except Exception:
            return "—"

    # Build HTML table
    rows_html = []
    for _, r in page_df.iterrows():
        img_url  = str(r.get("header_image") or "").strip()
        img_tag  = (
            f'<img src="{img_url}" style="height:48px;width:auto;border-radius:3px;'
            f'vertical-align:middle;">'
            if img_url and img_url != "nan"
            else '<span style="color:#555;font-size:0.75rem;">無圖</span>'
        )
        url      = steam_url(str(r["appid"]))
        name     = str(r.get("name") or "—")
        r_text, r_color = _rating_text(r)
        price    = _fmt_price(r.get("price_twd_original"))
        date_s   = _fmt_date(r.get("release_date"))
        sales    = _fmt_sales(r.get("est_sales_low"))

        rows_html.append(f"""
        <tr>
          <td style="width:80px;text-align:center;padding:6px 8px;vertical-align:middle;">
            <a href="{url}" target="_blank">{img_tag}</a>
          </td>
          <td style="padding:6px 8px;vertical-align:middle;font-size:0.88rem;font-weight:600;max-width:220px;">
            <a href="{url}" target="_blank"
               style="color:#c6d4df;text-decoration:none;"
               onmouseover="this.style.textDecoration='underline'"
               onmouseout="this.style.textDecoration='none'">{name}</a>
          </td>
          <td style="padding:6px 8px;vertical-align:middle;font-size:0.82rem;
                     color:{r_color};font-weight:600;max-width:280px;">{r_text}</td>
          <td style="padding:6px 8px;vertical-align:middle;font-size:0.85rem;
                     white-space:nowrap;">{price}</td>
          <td style="padding:6px 8px;vertical-align:middle;font-size:0.82rem;
                     color:#aaa;white-space:nowrap;">{date_s}</td>
          <td style="padding:6px 8px;vertical-align:middle;font-size:0.82rem;
                     white-space:nowrap;">{sales}</td>
        </tr>""")

    table_html = f"""
    <style>
    .game-list-table {{
        width: 100%;
        border-collapse: collapse;
        font-family: inherit;
    }}
    .game-list-table th {{
        background: #1e2a3a;
        color: #8ba3bc;
        font-size: 0.78rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        padding: 8px 8px;
        text-align: left;
        border-bottom: 1px solid #2a3f55;
    }}
    .game-list-table td {{
        border-bottom: 1px solid #1e2a3a;
    }}
    .game-list-table tr:hover td {{
        background: #1a2535;
    }}
    </style>
    <table class="game-list-table">
      <thead>
        <tr>
          <th>縮圖</th>
          <th>名稱</th>
          <th>評論等級 / 評論數</th>
          <th>台幣售價</th>
          <th>發售日</th>
          <th>預測銷售</th>
        </tr>
      </thead>
      <tbody>
        {"".join(rows_html)}
      </tbody>
    </table>
    """

    st.html(table_html)

# ---------------------------------------------------------------------------
# Pagination controls
# ---------------------------------------------------------------------------
st.markdown("---")
pcol1, pcol2, pcol3 = st.columns([1, 3, 1])

with pcol1:
    if st.button("← 上一頁", disabled=(current_page <= 1), key="prev_page"):
        st.session_state["games_page"] -= 1
        st.rerun()

with pcol2:
    st.markdown(
        f'<div style="text-align:center;padding-top:6px;">第 {current_page} / {total_pages} 頁'
        f'&nbsp;&nbsp;（共 {total:,} 款，每頁 {PER_PAGE} 款）</div>',
        unsafe_allow_html=True,
    )

with pcol3:
    if st.button("下一頁 →", disabled=(current_page >= total_pages), key="next_page"):
        st.session_state["games_page"] += 1
        st.rerun()
