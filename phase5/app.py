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

# -- Price range (manual number inputs) --
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

# -- Rating filter (compact dropdown with checkboxes) --
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

# -- Has reviews toggle --
only_reviewed = st.sidebar.checkbox("僅顯示有評論的遊戲", value=False, key="only_reviewed")

# -- Release year (compact dropdown with checkboxes) --
all_years = sorted(
    [int(y) for y in df_all["release_year"].dropna().unique()],
    reverse=True,
)
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
st.info("請使用左側導覽選擇頁面：\n- **1 Games** — 遊戲清單\n- **2 Release Heatmap** — 發售熱度分析\n- **3 Reviews** — 評論分析\n- **4 Price Bands** — 價格區間分析")

# Quick summary metrics
c1, c2, c3, c4 = st.columns(4)
c1.metric("符合條件遊戲", f"{len(df_filtered):,}")
c2.metric("有評論遊戲",
          f"{int(df_filtered['has_reviews'].astype(str).str.strip().eq('True').sum()):,}")
avg_price = df_filtered["price_twd_original"].mean()
c3.metric("平均台幣售價", f"NT$ {avg_price:,.0f}" if pd.notna(avg_price) else "—")
total_est = df_filtered["est_sales_low"].sum()
c4.metric("預測銷售合計", f"{total_est:,} 套")
