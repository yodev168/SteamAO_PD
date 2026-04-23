"""
pages/3_Reviews.py — 評論分析
KPI 列 + 圓餅圖 + 水平長條圖 + 好評率直方圖 + 評論數直方圖
+ 散佈圖 + 售價分組長條圖 + 年度堆疊長條圖
"""
import altair as alt
import pandas as pd
import streamlit as st

from data import (
    load_games,
    RATING_DISPLAY_ORDER,
    SORT_OPTIONS,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="評論分析 | Steam AO 分析",
    page_icon="📊",
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
# Colour scheme — rating label → hex
# ---------------------------------------------------------------------------
RATING_COLORS: dict[str, str] = {
    "壓倒性好評": "#22c55e",
    "極度好評":   "#4ade80",
    "大多好評":   "#86efac",
    "好評":       "#66c0f4",
    "褒貶不一":   "#fbbf24",
    "大多負評":   "#f97316",
    "負評":       "#ef4444",
    "極度負評":   "#991b1b",
    "少量評論":   "#9ca3af",
    "尚無評論":   "#6b7280",
}

# Canonical display order (best → worst)
RATING_ORDER = RATING_DISPLAY_ORDER + ["少量評論"]

# ---------------------------------------------------------------------------
# Sidebar — mirrors other pages
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
price_low_text  = pc1.text_input("最低", value=str(price_min_data), key="price_low_text")
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
price_low  = max(0, min(price_low,  price_max_data))
price_high = max(0, min(price_high, price_max_data))
if price_low > price_high:
    price_low, price_high = price_high, price_low
price_range = (price_low, price_high)

all_zh_ratings = RATING_ORDER
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
st.title("評論分析")
st.markdown(f"篩選結果：**{len(df):,}** 款遊戲")

if len(df) == 0:
    st.warning("沒有符合條件的遊戲，請調整篩選條件。")
    st.stop()

# Subset with actual reviews
df_rev = df[df["has_reviews"].astype(str).str.strip() == "True"].copy()

# ---------------------------------------------------------------------------
# 1. KPI 列
# ---------------------------------------------------------------------------
kc1, kc2, kc3, kc4 = st.columns(4)
kc1.metric("有評論遊戲",   f"{len(df_rev):,} / {len(df):,}")
avg_rc = df_rev["review_count"].mean()
kc2.metric("平均評論數",   f"{avg_rc:,.0f}" if pd.notna(avg_rc) else "—")
med_rc = df_rev["review_count"].median()
kc3.metric("中位數評論數", f"{med_rc:,.0f}" if pd.notna(med_rc) else "—")
avg_pr = df_rev["positive_ratio"].mean()
kc4.metric("平均好評率",   f"{avg_pr * 100:.1f}%" if pd.notna(avg_pr) else "—")

st.markdown("---")

# ---------------------------------------------------------------------------
# Helper: build rating domain/range for Altair scale
# ---------------------------------------------------------------------------
def _rating_scale(present_labels: list[str]):
    domain = [r for r in RATING_ORDER if r in present_labels]
    color_range = [RATING_COLORS.get(r, "#888888") for r in domain]
    return domain, color_range


# ---------------------------------------------------------------------------
# 2. 評論等級圓餅圖 + 3. 水平長條圖  (side by side)
# ---------------------------------------------------------------------------
st.subheader("評論等級分布")

pie_df = (
    df.groupby("review_score_desc_zh", as_index=False)
    .agg(
        count=("appid", "count"),
        avg_reviews=("review_count", "mean"),
    )
)
pie_df["pct"] = pie_df["count"] / pie_df["count"].sum()
pie_df["pct_label"] = (pie_df["pct"] * 100).round(1).astype(str) + "%"

present_labels = pie_df["review_score_desc_zh"].tolist()
domain, color_range = _rating_scale(present_labels)

color_scale = alt.Scale(domain=domain, range=color_range)

# Numeric sort key so Altair arc segments follow rating order
pie_df["sort_order"] = pie_df["review_score_desc_zh"].apply(
    lambda x: domain.index(x) if x in domain else 999
)

col_pie, col_bar = st.columns([1, 1])

with col_pie:
    st.caption("圓餅圖（各等級遊戲佔比）")
    pie_chart = (
        alt.Chart(pie_df)
        .mark_arc(outerRadius=130, innerRadius=50)
        .encode(
            theta=alt.Theta("count:Q"),
            color=alt.Color(
                "review_score_desc_zh:N",
                scale=color_scale,
                sort=domain,
                legend=alt.Legend(
                    title="評論等級",
                    orient="bottom",
                    columns=2,
                    labelFontSize=11,
                ),
            ),
            order=alt.Order("sort_order:Q", sort="ascending"),
            tooltip=[
                alt.Tooltip("review_score_desc_zh:N", title="評論等級"),
                alt.Tooltip("count:Q",               title="遊戲數",   format=","),
                alt.Tooltip("pct_label:N",            title="佔比"),
                alt.Tooltip("avg_reviews:Q",          title="平均評論數", format=",.0f"),
            ],
        )
        .properties(height=360)
    )
    st.altair_chart(pie_chart, use_container_width=True)

with col_bar:
    st.caption("水平長條圖（各等級遊戲數量 / 平均評論數）")

    bar_df = pie_df.copy()
    bar_df["rating_sort"] = bar_df["review_score_desc_zh"].apply(
        lambda x: domain.index(x) if x in domain else 999
    )
    bar_df = bar_df.sort_values("rating_sort")

    base = alt.Chart(bar_df)

    bar_count = (
        base.mark_bar(cornerRadiusTopRight=3, cornerRadiusBottomRight=3)
        .encode(
            y=alt.Y(
                "review_score_desc_zh:N",
                sort=domain,
                title=None,
                axis=alt.Axis(labelFontSize=12),
            ),
            x=alt.X("count:Q", title="遊戲數量"),
            color=alt.Color(
                "review_score_desc_zh:N",
                scale=color_scale,
                sort=domain,
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("review_score_desc_zh:N", title="評論等級"),
                alt.Tooltip("count:Q",               title="遊戲數",   format=","),
                alt.Tooltip("avg_reviews:Q",          title="平均評論數", format=",.0f"),
            ],
        )
        .properties(height=320)
    )

    text_count = (
        base.mark_text(align="left", dx=4, fontSize=11, color="#555")
        .encode(
            y=alt.Y("review_score_desc_zh:N", sort=domain),
            x=alt.X("count:Q"),
            text=alt.Text("count:Q", format=","),
        )
    )

    st.altair_chart(
        (bar_count + text_count)
        .configure_axis(labelFontSize=12, titleFontSize=12)
        .configure_view(strokeWidth=0),
        use_container_width=True,
    )

st.markdown("---")

# ---------------------------------------------------------------------------
# 4. 好評率分布直方圖
# ---------------------------------------------------------------------------
st.subheader("好評率分布")
st.caption("僅含有評論的遊戲（positive_ratio 每 5% 一格）")

if len(df_rev) == 0:
    st.info("篩選結果中沒有有評論的遊戲。")
else:
    hist_ratio_df = df_rev[["positive_ratio"]].dropna().copy()
    hist_ratio_df["pct"] = (hist_ratio_df["positive_ratio"] * 100).round(0)

    hist_ratio = (
        alt.Chart(hist_ratio_df)
        .mark_bar(
            cornerRadiusTopLeft=2,
            cornerRadiusTopRight=2,
            binSpacing=1,
        )
        .encode(
            x=alt.X(
                "positive_ratio:Q",
                bin=alt.Bin(step=0.05),
                title="好評率",
                axis=alt.Axis(format=".0%", labelAngle=0),
            ),
            y=alt.Y("count():Q", title="遊戲數量"),
            color=alt.Color(
                "positive_ratio:Q",
                bin=alt.Bin(step=0.05),
                scale=alt.Scale(scheme="redyellowgreen"),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("positive_ratio:Q", bin=alt.Bin(step=0.05), title="好評率區間", format=".0%"),
                alt.Tooltip("count():Q", title="遊戲數量", format=","),
            ],
        )
        .properties(height=280)
        .configure_axis(labelFontSize=13, titleFontSize=13)
        .configure_view(strokeWidth=0)
    )
    st.altair_chart(hist_ratio, use_container_width=True)

st.markdown("---")

# ---------------------------------------------------------------------------
# 5. 評論數量分布（log bins 手動分組）
# ---------------------------------------------------------------------------
st.subheader("評論數量分布")
st.caption("有評論遊戲的評論數分布（對數區間）")

if len(df_rev) > 0:
    import numpy as np

    rc_data = df_rev["review_count"].dropna()
    rc_data = rc_data[rc_data > 0]

    bins = [1, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 100000]
    labels = [
        "1–4", "5–9", "10–19", "20–49", "50–99",
        "100–199", "200–499", "500–999",
        "1K–1.9K", "2K–4.9K", "5K–9.9K", "10K+",
    ]
    counts_per_bin = []
    for i in range(len(bins) - 1):
        lo, hi = bins[i], bins[i + 1]
        cnt = int(((rc_data >= lo) & (rc_data < hi)).sum())
        counts_per_bin.append({"區間": labels[i], "遊戲數量": cnt, "sort_idx": i})

    bin_df = pd.DataFrame(counts_per_bin)

    log_hist = (
        alt.Chart(bin_df)
        .mark_bar(
            cornerRadiusTopLeft=3,
            cornerRadiusTopRight=3,
        )
        .encode(
            x=alt.X(
                "區間:N",
                sort=[r["區間"] for r in counts_per_bin],
                title="評論數區間",
                axis=alt.Axis(labelAngle=-30),
            ),
            y=alt.Y("遊戲數量:Q", title="遊戲數量"),
            color=alt.Color(
                "sort_idx:Q",
                scale=alt.Scale(scheme="blues"),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("區間:N",    title="評論數區間"),
                alt.Tooltip("遊戲數量:Q", title="遊戲數量", format=","),
            ],
        )
        .properties(height=280)
        .configure_axis(labelFontSize=12, titleFontSize=12)
        .configure_view(strokeWidth=0)
    )
    st.altair_chart(log_hist, use_container_width=True)

st.markdown("---")

# ---------------------------------------------------------------------------
# 6. 好評率 vs 評論數量 散佈圖
# ---------------------------------------------------------------------------
st.subheader("好評率 vs 評論數量")
st.caption("每個點為一款遊戲；X 軸使用對數刻度；顏色對應評論等級")

if len(df_rev) > 0:
    scatter_df = df_rev[
        df_rev["review_count"] > 0
    ][["name", "review_count", "positive_ratio",
       "review_score_desc_zh", "est_sales_low",
       "price_twd_original"]].dropna(subset=["review_count", "positive_ratio"]).copy()

    sc_domain, sc_range = _rating_scale(scatter_df["review_score_desc_zh"].unique().tolist())

    scatter = (
        alt.Chart(scatter_df)
        .mark_circle(opacity=0.65, size=50)
        .encode(
            x=alt.X(
                "review_count:Q",
                scale=alt.Scale(type="log"),
                title="評論數量（對數刻度）",
                axis=alt.Axis(format=","),
            ),
            y=alt.Y(
                "positive_ratio:Q",
                title="好評率",
                axis=alt.Axis(format=".0%"),
                scale=alt.Scale(domain=[0, 1]),
            ),
            color=alt.Color(
                "review_score_desc_zh:N",
                scale=alt.Scale(domain=sc_domain, range=sc_range),
                sort=sc_domain,
                legend=alt.Legend(
                    title="評論等級",
                    orient="right",
                    labelFontSize=11,
                ),
            ),
            tooltip=[
                alt.Tooltip("name:N",                 title="遊戲名稱"),
                alt.Tooltip("review_count:Q",         title="評論數",   format=","),
                alt.Tooltip("positive_ratio:Q",       title="好評率",   format=".1%"),
                alt.Tooltip("review_score_desc_zh:N", title="評論等級"),
                alt.Tooltip("est_sales_low:Q",        title="預測銷售", format=","),
                alt.Tooltip("price_twd_original:Q",   title="台幣售價", format=","),
            ],
        )
        .properties(height=380)
        .configure_axis(labelFontSize=12, titleFontSize=12)
        .configure_view(strokeWidth=0)
    )
    st.altair_chart(scatter, use_container_width=True)

st.markdown("---")

# ---------------------------------------------------------------------------
# 7. 評論等級 vs 平均售價
# ---------------------------------------------------------------------------
st.subheader("各評論等級的平均售價")
st.caption("觀察好評 / 差評遊戲是否有定價差異（僅限付費遊戲）")

price_df = (
    df[df["price_twd_original"] > 0]
    .groupby("review_score_desc_zh", as_index=False)
    .agg(
        avg_price=("price_twd_original", "mean"),
        count=("appid", "count"),
    )
)
price_df = price_df[price_df["review_score_desc_zh"].isin(domain)]

if len(price_df) == 0:
    st.info("篩選結果中沒有足夠資料。")
else:
    pv_domain, pv_range = _rating_scale(price_df["review_score_desc_zh"].tolist())

    price_bar = (
        alt.Chart(price_df)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=alt.X(
                "review_score_desc_zh:N",
                sort=pv_domain,
                title="評論等級",
                axis=alt.Axis(labelAngle=-20, labelFontSize=12),
            ),
            y=alt.Y("avg_price:Q", title="平均台幣售價（NT$）"),
            color=alt.Color(
                "review_score_desc_zh:N",
                scale=alt.Scale(domain=pv_domain, range=pv_range),
                sort=pv_domain,
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("review_score_desc_zh:N", title="評論等級"),
                alt.Tooltip("avg_price:Q",            title="平均售價（NT$）", format=",.0f"),
                alt.Tooltip("count:Q",                title="遊戲數",        format=","),
            ],
        )
        .properties(height=300)
        .configure_axis(labelFontSize=12, titleFontSize=12)
        .configure_view(strokeWidth=0)
    )
    st.altair_chart(price_bar, use_container_width=True)

st.markdown("---")

# ---------------------------------------------------------------------------
# 8. 年度評論等級堆疊長條圖
# ---------------------------------------------------------------------------
st.subheader("各年度評論等級組成")
st.caption("觀察每年 AO 遊戲的評論等級分布變化")

yearly_df = (
    df.dropna(subset=["release_year"])
    .groupby(["release_year", "review_score_desc_zh"], as_index=False)
    .agg(count=("appid", "count"))
)
yearly_df["release_year"] = yearly_df["release_year"].astype(int)
yearly_df["year_str"] = yearly_df["release_year"].astype(str)

yr_present = yearly_df["review_score_desc_zh"].unique().tolist()
yr_domain, yr_range = _rating_scale(yr_present)

# Numeric sort key for stacked segment order
yearly_df["sort_order"] = yearly_df["review_score_desc_zh"].apply(
    lambda x: yr_domain.index(x) if x in yr_domain else 999
)

stacked_bar = (
    alt.Chart(yearly_df)
    .mark_bar()
    .encode(
        x=alt.X(
            "year_str:N",
            sort=alt.SortField("release_year", order="ascending"),
            title="年份",
            axis=alt.Axis(labelAngle=0),
        ),
        y=alt.Y("count:Q", title="遊戲數量（堆疊）"),
        color=alt.Color(
            "review_score_desc_zh:N",
            scale=alt.Scale(domain=yr_domain, range=yr_range),
            sort=yr_domain,
            legend=alt.Legend(
                title="評論等級",
                orient="right",
                labelFontSize=11,
            ),
        ),
        order=alt.Order("sort_order:Q", sort="ascending"),
        tooltip=[
            alt.Tooltip("year_str:N",             title="年份"),
            alt.Tooltip("review_score_desc_zh:N", title="評論等級"),
            alt.Tooltip("count:Q",                title="遊戲數", format=","),
        ],
    )
    .properties(height=340)
    .configure_axis(labelFontSize=13, titleFontSize=13)
    .configure_view(strokeWidth=0)
)

st.altair_chart(stacked_bar, use_container_width=True)
