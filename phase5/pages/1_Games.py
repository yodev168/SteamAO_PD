"""
pages/1_Games.py — 遊戲清單（卡片網格 + 分頁）
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
# Sidebar (mirrors app.py — re-render to keep sidebar visible on this page)
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
price_range = st.sidebar.slider(
    "台幣售價區間（NT$）",
    min_value=price_min_data,
    max_value=price_max_data,
    value=(price_min_data, price_max_data),
    step=10,
    key="price_range",
)

all_zh_ratings = RATING_DISPLAY_ORDER + ["少量評論"]
selected_ratings = st.sidebar.multiselect(
    "評價等級",
    options=all_zh_ratings,
    default=all_zh_ratings,
    key="selected_ratings",
)

only_reviewed = st.sidebar.checkbox("僅顯示有評論的遊戲", value=False, key="only_reviewed")

all_years = sorted([y for y in df_all["release_year"].dropna().unique()], reverse=True)
selected_years = st.sidebar.multiselect(
    "發售年份",
    options=[int(y) for y in all_years],
    default=[int(y) for y in all_years],
    key="selected_years",
)

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
# Rating badge helper
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------
PER_PAGE = 30
total = len(df)
total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)

if "games_page" not in st.session_state:
    st.session_state["games_page"] = 1

# Reset to page 1 when filters change (detect via total count change)
prev_total = st.session_state.get("games_prev_total", -1)
if prev_total != total:
    st.session_state["games_page"] = 1
    st.session_state["games_prev_total"] = total

current_page = st.session_state["games_page"]

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("遊戲清單")
st.markdown(f"篩選結果：**{total:,}** 款遊戲")

if total == 0:
    st.warning("沒有符合條件的遊戲，請調整篩選條件。")
    st.stop()

# ---------------------------------------------------------------------------
# Page slice
# ---------------------------------------------------------------------------
start = (current_page - 1) * PER_PAGE
end   = min(start + PER_PAGE, total)
page_df = df.iloc[start:end]

# ---------------------------------------------------------------------------
# Card grid (3 columns)
# ---------------------------------------------------------------------------
COLS = 3

rows_iter = range(0, len(page_df), COLS)
for row_start in rows_iter:
    cols = st.columns(COLS)
    for ci, col in enumerate(cols):
        idx = row_start + ci
        if idx >= len(page_df):
            break
        row = page_df.iloc[idx]

        with col:
            # Promo image
            img_url = str(row.get("header_image", "") or "").strip()
            if img_url and img_url != "nan":
                st.image(img_url, use_container_width=True)
            else:
                st.markdown(
                    '<div style="height:120px;background:#1a1a2e;border-radius:6px;'
                    'display:flex;align-items:center;justify-content:center;'
                    'color:#555;font-size:0.8rem;">無宣傳圖</div>',
                    unsafe_allow_html=True,
                )

            # Name + Steam link
            url = steam_url(str(row["appid"]))
            name = str(row["name"])
            st.markdown(
                f'<div class="game-title">'
                f'<a href="{url}" target="_blank" style="text-decoration:none;">'
                f'{name}</a></div>',
                unsafe_allow_html=True,
            )

            # Rating badge
            zh_rating = str(row.get("review_score_desc_zh", "—"))
            st.markdown(rating_badge(zh_rating), unsafe_allow_html=True)

            # Price row
            twd = fmt_twd(row.get("price_twd_original"))
            usd = fmt_usd(row.get("price_usd_original"))
            st.markdown(
                f'<span style="font-size:0.95rem;font-weight:600;">{twd}</span>'
                f'&nbsp;&nbsp;<span class="muted">{usd}</span>',
                unsafe_allow_html=True,
            )

            # Release date
            rd = row.get("release_date")
            rd_str = pd.Timestamp(rd).strftime("%Y-%m-%d") if pd.notna(rd) else "—"
            st.markdown(f'<span class="muted">發售日：{rd_str}</span>', unsafe_allow_html=True)

            # Developer / Publisher
            dev = display_value(row.get("developer"))
            pub = display_value(row.get("publisher"))
            st.markdown(
                f'<span class="muted">開發：{dev}</span><br>'
                f'<span class="muted">發行：{pub}</span>',
                unsafe_allow_html=True,
            )

            # Reviews
            rc  = fmt_num(row.get("review_count"))
            rp  = fmt_num(row.get("review_positive"))
            rn  = fmt_num(row.get("review_negative"))
            ratio_raw = row.get("positive_ratio")
            try:
                ratio_str = f"{float(ratio_raw)*100:.1f}%"
            except (TypeError, ValueError):
                ratio_str = "—"

            st.markdown(
                f'<span class="muted">'
                f'評論：{rc} 則 &nbsp;|&nbsp; '
                f'<span style="color:#5cb85c;">▲ {rp}</span> &nbsp;'
                f'<span style="color:#d9534f;">▼ {rn}</span> &nbsp;'
                f'好評率 {ratio_str}</span>',
                unsafe_allow_html=True,
            )

            # Est. sales
            est = fmt_num(row.get("est_sales_low"))
            st.markdown(
                f'<span class="muted">預測銷售：</span>'
                f'<span style="font-weight:600;">{est} 套</span>',
                unsafe_allow_html=True,
            )

            # Steam open button
            st.markdown(
                f'<div class="steam-link"><a href="{url}" target="_blank">在 Steam 開啟 ↗</a></div>',
                unsafe_allow_html=True,
            )

            st.markdown("<hr style='margin:12px 0;border-color:#333;'>", unsafe_allow_html=True)

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
