"""
app.py — Phase 5 Dashboard entry point
Run: streamlit run app.py  (from the phase5/ directory)
"""
import streamlit as st
import pandas as pd

from data import (
    load_games,
    RATING_DISPLAY_ORDER,
    SORT_OPTIONS,
)

# ---------------------------------------------------------------------------
# Page config (must be first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Steam AO 市場分析",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Global CSS tweaks
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* Narrower sidebar */
    [data-testid="stSidebar"] { min-width: 280px; max-width: 320px; }
    /* Card image full width */
    .game-card img { width: 100% !important; border-radius: 6px; }
    /* Muted secondary text */
    .muted { color: #888; font-size: 0.82rem; }
    /* Steam link button */
    .steam-link a {
        display: inline-block;
        padding: 3px 10px;
        background: #1b2838;
        color: #c6d4df !important;
        border-radius: 4px;
        text-decoration: none;
        font-size: 0.82rem;
    }
    .steam-link a:hover { background: #2a475e; }
    /* Divider between cards */
    hr.card-sep { margin: 6px 0; border-color: #333; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Load data once (cached)
# ---------------------------------------------------------------------------
df_all = load_games()

# ---------------------------------------------------------------------------
# Sidebar — shared filters
# ---------------------------------------------------------------------------
st.sidebar.title("🎮 Steam AO 分析")
st.sidebar.markdown("---")

# -- Text search --
search_query = st.sidebar.text_input(
    "搜尋遊戲名稱 / 開發商 / 發行商",
    placeholder="輸入關鍵字…",
    key="search_query",
)

# -- Price range --
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

# -- Rating filter --
all_zh_ratings = RATING_DISPLAY_ORDER + ["少量評論"]
selected_ratings = st.sidebar.multiselect(
    "評價等級",
    options=all_zh_ratings,
    default=all_zh_ratings,
    key="selected_ratings",
)

# -- Has reviews toggle --
only_reviewed = st.sidebar.checkbox("僅顯示有評論的遊戲", value=False, key="only_reviewed")

# -- Release year --
all_years = sorted(
    [y for y in df_all["release_year"].dropna().unique()],
    reverse=True,
)
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
# Apply filters → shared filtered DataFrame stored in session_state
# ---------------------------------------------------------------------------
def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    # Text search
    q = search_query.strip().lower()
    if q:
        mask = (
            df["name"].str.lower().str.contains(q, na=False)
            | df["developer"].astype(str).str.lower().str.contains(q, na=False)
            | df["publisher"].astype(str).str.lower().str.contains(q, na=False)
        )
        df = df[mask]

    # Price
    df = df[
        df["price_twd_original"].between(price_range[0], price_range[1], inclusive="both")
    ]

    # Rating
    if selected_ratings:
        df = df[df["review_score_desc_zh"].isin(selected_ratings)]

    # Has reviews
    if only_reviewed:
        df = df[df["has_reviews"].astype(str).str.strip() == "True"]

    # Year
    if selected_years:
        df = df[df["release_year"].isin(selected_years)]

    # Sort
    sort_col, ascending = SORT_OPTIONS[sort_label]
    df = df.sort_values(sort_col, ascending=ascending, na_position="last")

    return df.reset_index(drop=True)


df_filtered = apply_filters(df_all)
st.session_state["df_filtered"] = df_filtered

# ---------------------------------------------------------------------------
# Home page: just redirect note when opened directly
# ---------------------------------------------------------------------------
st.title("Steam AO 市場分析 Dashboard")
st.markdown(
    f"目前篩選結果：**{len(df_filtered):,}** 款遊戲（共 {len(df_all):,} 款）"
)
st.info("請使用左側導覽選擇頁面：\n- **1 Games** — 遊戲清單\n- **2 Release Heatmap** — 發售熱度分析")

# Quick summary metrics
c1, c2, c3, c4 = st.columns(4)
c1.metric("符合條件遊戲", f"{len(df_filtered):,}")
c2.metric("有評論遊戲",
          f"{int(df_filtered['has_reviews'].astype(str).str.strip().eq('True').sum()):,}")
avg_price = df_filtered["price_twd_original"].mean()
c3.metric("平均台幣售價", f"NT$ {avg_price:,.0f}" if pd.notna(avg_price) else "—")
total_est = df_filtered["est_sales_low"].sum()
c4.metric("預測銷售合計", f"{total_est:,} 套")
