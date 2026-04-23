"""
pages/2_Release_Heatmap.py — 發售熱度分析
KPI 列 + 年份長條圖 + 年×月 熱力圖
"""
import datetime

import altair as alt
import pandas as pd
import streamlit as st

from data import (
    load_games,
    RATING_DISPLAY_ORDER,
    SORT_OPTIONS,
    fmt_num,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="發售熱度 | Steam AO 分析",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    [data-testid="stSidebar"] { min-width: 280px; max-width: 320px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar (mirrors other pages)
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
# Filter
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
    return df.reset_index(drop=True)


df = apply_filters(df_all)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("發售熱度分析")
st.markdown(f"篩選結果：**{len(df):,}** 款遊戲")

if len(df) == 0:
    st.warning("沒有符合條件的遊戲，請調整篩選條件。")
    st.stop()

# ---------------------------------------------------------------------------
# KPI row
# ---------------------------------------------------------------------------
now = datetime.date.today()
this_month_mask = (
    df["release_date"].dt.year  == now.year
) & (
    df["release_date"].dt.month == now.month
)
this_month_count = int(this_month_mask.sum())

has_reviews_count = int(df["has_reviews"].astype(str).str.strip().eq("True").sum())
avg_price = df["price_twd_original"].mean()
total_est = int(df["est_sales_low"].sum())

kc1, kc2, kc3, kc4 = st.columns(4)
kc1.metric("符合條件遊戲", f"{len(df):,}")
kc2.metric("有評論遊戲",    f"{has_reviews_count:,}")
kc3.metric("本月新作",      f"{this_month_count:,}")
kc4.metric("平均台幣售價",  f"NT$ {avg_price:,.0f}" if pd.notna(avg_price) else "—")

st.markdown("---")

# ---------------------------------------------------------------------------
# Section: 年份發售數量
# ---------------------------------------------------------------------------
st.subheader("年份發售數量")

yearly = (
    df.dropna(subset=["release_year"])
    .groupby("release_year", as_index=False)
    .agg(
        count=("appid", "count"),
        total_est_sales=("est_sales_low", "sum"),
    )
)
yearly["release_year"] = yearly["release_year"].astype(int)
yearly["year_str"] = yearly["release_year"].astype(str)

bar_chart = (
    alt.Chart(yearly)
    .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
    .encode(
        x=alt.X("year_str:N", title="年份",
                sort=alt.SortField("release_year", order="ascending"),
                axis=alt.Axis(labelAngle=0)),
        y=alt.Y("count:Q", title="發售數量"),
        color=alt.Color("count:Q", scale=alt.Scale(scheme="blues"), legend=None),
        tooltip=[
            alt.Tooltip("year_str:N",         title="年份"),
            alt.Tooltip("count:Q",            title="發售數量",     format=","),
            alt.Tooltip("total_est_sales:Q",  title="預測銷售合計（套）", format=","),
        ],
    )
    .properties(height=300)
    .configure_axis(labelFontSize=13, titleFontSize=13)
    .configure_view(strokeWidth=0)
)

st.altair_chart(bar_chart, use_container_width=True)

st.markdown("---")

# ---------------------------------------------------------------------------
# Section: 年 × 月 熱力圖
# ---------------------------------------------------------------------------
st.subheader("年 × 月 發售熱力圖")

metric_opt = st.radio(
    "顏色指標",
    options=["發售數量", "預測銷售合計"],
    horizontal=True,
    key="heatmap_metric",
)

month_labels = {
    1: "1月", 2: "2月", 3: "3月", 4: "4月",
    5: "5月", 6: "6月", 7: "7月", 8: "8月",
    9: "9月", 10: "10月", 11: "11月", 12: "12月",
}

hm_df = (
    df.dropna(subset=["release_year", "release_month"])
    .groupby(["release_year", "release_month"], as_index=False)
    .agg(
        count=("appid", "count"),
        total_est_sales=("est_sales_low", "sum"),
    )
)
hm_df["release_year"]  = hm_df["release_year"].astype(int)
hm_df["release_month"] = hm_df["release_month"].astype(int)
hm_df["year_str"]      = hm_df["release_year"].astype(str)
hm_df["month_label"]   = hm_df["release_month"].map(month_labels)

# Ensure all 12 months exist for every year present (fill with 0)
years_in = hm_df["release_year"].unique()
full_grid = pd.DataFrame(
    [(y, m) for y in years_in for m in range(1, 13)],
    columns=["release_year", "release_month"],
)
hm_df = full_grid.merge(hm_df, on=["release_year", "release_month"], how="left")
hm_df["count"]           = hm_df["count"].fillna(0).astype(int)
hm_df["total_est_sales"] = hm_df["total_est_sales"].fillna(0).astype(int)
hm_df["year_str"]        = hm_df["release_year"].astype(str)
hm_df["month_label"]     = hm_df["release_month"].map(month_labels)

color_field    = "count:Q"         if metric_opt == "發售數量" else "total_est_sales:Q"
color_title    = "發售數量"          if metric_opt == "發售數量" else "預測銷售合計"
tooltip_fields = [
    alt.Tooltip("year_str:N",        title="年份"),
    alt.Tooltip("month_label:N",     title="月份"),
    alt.Tooltip("count:Q",           title="發售數量",         format=","),
    alt.Tooltip("total_est_sales:Q", title="預測銷售合計（套）", format=","),
]

heatmap = (
    alt.Chart(hm_df)
    .mark_rect()
    .encode(
        x=alt.X(
            "release_month:O",
            title="月份",
            axis=alt.Axis(
                values=list(range(1, 13)),
                labelExpr="{'1':'1月','2':'2月','3':'3月','4':'4月','5':'5月','6':'6月',"
                          "'7':'7月','8':'8月','9':'9月','10':'10月','11':'11月','12':'12月'}[datum.value]",
                labelAngle=0,
            ),
        ),
        y=alt.Y(
            "release_year:O",
            title="年份",
            sort="descending",
        ),
        color=alt.Color(
            color_field,
            scale=alt.Scale(scheme="orangered"),
            legend=alt.Legend(title=color_title),
        ),
        tooltip=tooltip_fields,
    )
    .properties(height=max(200, len(years_in) * 36))
    .configure_axis(labelFontSize=13, titleFontSize=13)
    .configure_view(strokeWidth=0)
)

st.altair_chart(heatmap, use_container_width=True)

st.markdown("---")

# ---------------------------------------------------------------------------
# Section: 月份發售趨勢（折線，跨年比較）
# ---------------------------------------------------------------------------
st.subheader("各月份發售趨勢（跨年比較）")

monthly_trend = (
    df.dropna(subset=["release_year", "release_month"])
    .groupby(["release_year", "release_month"], as_index=False)
    .agg(count=("appid", "count"))
)
monthly_trend["release_year"]  = monthly_trend["release_year"].astype(int)
monthly_trend["release_month"] = monthly_trend["release_month"].astype(int)
monthly_trend["year_str"]      = monthly_trend["release_year"].astype(str)
monthly_trend["month_label"]   = monthly_trend["release_month"].map(month_labels)

line_chart = (
    alt.Chart(monthly_trend)
    .mark_line(point=True)
    .encode(
        x=alt.X(
            "release_month:O",
            title="月份",
            axis=alt.Axis(
                values=list(range(1, 13)),
                labelExpr="{'1':'1月','2':'2月','3':'3月','4':'4月','5':'5月','6':'6月',"
                          "'7':'7月','8':'8月','9':'9月','10':'10月','11':'11月','12':'12月'}[datum.value]",
                labelAngle=0,
            ),
        ),
        y=alt.Y("count:Q", title="發售數量"),
        color=alt.Color("year_str:N", title="年份"),
        tooltip=[
            alt.Tooltip("year_str:N",    title="年份"),
            alt.Tooltip("month_label:N", title="月份"),
            alt.Tooltip("count:Q",       title="發售數量", format=","),
        ],
    )
    .properties(height=300)
    .configure_axis(labelFontSize=13, titleFontSize=13)
    .configure_view(strokeWidth=0)
)

st.altair_chart(line_chart, use_container_width=True)
