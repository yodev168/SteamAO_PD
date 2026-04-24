"""
pages/4_Price_Bands.py — 價格區間分析
市場結構 / 評價表現 / 商業表現 / 交叉洞察，共 10 張 Altair 圖表
"""
import altair as alt
import numpy as np
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
    page_title="價格區間分析 | Steam AO 分析",
    page_icon="💰",
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
# Price bin constants (全頁統一)
# ---------------------------------------------------------------------------
PRICE_BINS = [0, 50, 100, 150, 200, 250, 300, 350, 400, 450, 500, 800, 1500, float("inf")]
PRICE_LABELS = [
    "0-50", "50-100", "100-150", "150-200", "200-250",
    "250-300", "300-350", "350-400", "400-450", "450-500",
    "500-800", "800-1500", "1500+",
]

# ---------------------------------------------------------------------------
# Colour scheme — rating label → hex (mirrors 3_Reviews.py)
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

RATING_ORDER = RATING_DISPLAY_ORDER + ["少量評論"]

# Canonical stacked order (bottom → top): positive → mixed → negative → no review
STACKED_ORDER = [
    "壓倒性好評", "極度好評", "大多好評", "好評",
    "褒貶不一",
    "大多負評", "負評", "極度負評",
    "少量評論", "尚無評論",
]

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
st.title("價格區間分析")
st.markdown(f"篩選結果：**{len(df):,}** 款遊戲")

if len(df) == 0:
    st.warning("沒有符合條件的遊戲，請調整篩選條件。")
    st.stop()

# ---------------------------------------------------------------------------
# Data preparation — price bins + derived columns
# ---------------------------------------------------------------------------
df = df[df["price_twd_original"].notna() & (df["price_twd_original"] > 0)].copy()

df["price_bin"] = pd.cut(
    df["price_twd_original"],
    bins=PRICE_BINS,
    labels=PRICE_LABELS,
    right=False,
)
df["price_bin"] = pd.Categorical(df["price_bin"], categories=PRICE_LABELS, ordered=True)
df["est_revenue"] = df["price_twd_original"] * df["est_sales_low"]

# Review-quality subset (review_count >= 10)
df_rev = df[df["review_count"] >= 10].copy()

# KPI row
kc1, kc2, kc3, kc4 = st.columns(4)
kc1.metric("分析遊戲數", f"{len(df):,}")
kc2.metric("有效評論遊戲", f"{len(df_rev):,}")
avg_pr = df_rev["positive_ratio"].mean()
kc3.metric("平均好評率", f"{avg_pr * 100:.1f}%" if pd.notna(avg_pr) else "—")
total_rev = df["est_revenue"].sum()
rev_unit = "億" if total_rev >= 1e8 else "萬"
rev_divisor = 1e8 if total_rev >= 1e8 else 1e4
kc4.metric("總估算營收", f"NT$ {total_rev / rev_divisor:,.1f} {rev_unit}（估算）")

st.markdown("---")

# ---------------------------------------------------------------------------
# Helper: build Altair color scale from a list of rating labels
# ---------------------------------------------------------------------------
def _rating_scale(present_labels: list[str]):
    domain = [r for r in RATING_ORDER if r in present_labels]
    color_range = [RATING_COLORS.get(r, "#888888") for r in domain]
    return domain, color_range


# ---------------------------------------------------------------------------
# Helper: build manual box-plot layers for a given value column
# Returns a layered Altair chart; data must have 'price_bin' and 'name' columns.
# ---------------------------------------------------------------------------
def _build_boxplot(
    data: pd.DataFrame,
    value_col: str,
    y_title: str,
    log_scale: bool = False,
    height: int = 380,
):
    """
    Manual box plot using pandas quantiles + Altair layers.
    Supports log Y scale and game name tooltips on outlier dots.
    """
    if data.empty or value_col not in data.columns:
        return None

    rows = []
    for bin_label in PRICE_LABELS:
        sub = data[data["price_bin"] == bin_label][value_col].dropna()
        n = len(sub)
        if n == 0:
            continue
        q1  = float(sub.quantile(0.25))
        med = float(sub.quantile(0.50))
        q3  = float(sub.quantile(0.75))
        iqr = q3 - q1
        lo_fence = q1 - 1.5 * iqr
        hi_fence = q3 + 1.5 * iqr
        # For log scale, fence cannot be <= 0
        if log_scale:
            lo_fence = max(lo_fence, 0.1)
        lo_whisk = float(sub[sub >= lo_fence].min()) if len(sub[sub >= lo_fence]) else q1
        hi_whisk = float(sub[sub <= hi_fence].max()) if len(sub[sub <= hi_fence]) else q3
        rows.append({
            "price_bin": bin_label,
            "q1": q1, "median": med, "q3": q3,
            "lo_whisker": lo_whisk, "hi_whisker": hi_whisk,
            "n": n,
        })

    if not rows:
        return None

    box_df = pd.DataFrame(rows)
    box_df["price_bin"] = pd.Categorical(box_df["price_bin"], categories=PRICE_LABELS, ordered=True)
    box_df["label"] = box_df.apply(
        lambda r: f"n={int(r['n'])}" if r["n"] < 30 else "", axis=1
    )

    y_scale = alt.Scale(type="log") if log_scale else alt.Scale()
    x_enc = alt.X("price_bin:O", sort=PRICE_LABELS, title="價格區間（NT$）",
                  axis=alt.Axis(labelAngle=-30, labelFontSize=11))

    base = alt.Chart(box_df)

    # Whisker rules
    whisker_lo = base.mark_rule(color="#555", strokeWidth=1.2).encode(
        x=x_enc,
        y=alt.Y("lo_whisker:Q", title=y_title, scale=y_scale),
        y2="q1:Q",
    )
    whisker_hi = base.mark_rule(color="#555", strokeWidth=1.2).encode(
        x=x_enc,
        y=alt.Y("q3:Q", scale=y_scale),
        y2="hi_whisker:Q",
    )

    # IQR box
    box = base.mark_bar(color="#4a90d9", opacity=0.75, cornerRadiusTopLeft=2,
                        cornerRadiusTopRight=2).encode(
        x=x_enc,
        y=alt.Y("q1:Q", title=y_title, scale=y_scale),
        y2="q3:Q",
        tooltip=[
            alt.Tooltip("price_bin:O",   title="區間"),
            alt.Tooltip("q1:Q",          title="Q1",   format=",.1f"),
            alt.Tooltip("median:Q",      title="中位數", format=",.1f"),
            alt.Tooltip("q3:Q",          title="Q3",   format=",.1f"),
            alt.Tooltip("n:Q",           title="樣本數", format=","),
        ],
    )

    # Median tick
    median_tick = base.mark_tick(color="#fff", thickness=2, size=18).encode(
        x=x_enc,
        y=alt.Y("median:Q", scale=y_scale),
    )

    # Low-sample annotation
    label_text = base.mark_text(
        align="center", dy=-8, fontSize=10, color="#888"
    ).encode(
        x=x_enc,
        y=alt.Y("hi_whisker:Q", scale=y_scale),
        text="label:N",
    )

    # Outliers
    outlier_rows = []
    for bin_label in PRICE_LABELS:
        sub = data[data["price_bin"] == bin_label][[value_col, "name"]].dropna()
        if sub.empty:
            continue
        box_row = box_df[box_df["price_bin"] == bin_label]
        if box_row.empty:
            continue
        lo_w = float(box_row["lo_whisker"].iloc[0])
        hi_w = float(box_row["hi_whisker"].iloc[0])
        outs = sub[(sub[value_col] < lo_w) | (sub[value_col] > hi_w)]
        for _, row in outs.iterrows():
            outlier_rows.append({
                "price_bin": bin_label,
                value_col: row[value_col],
                "name": row["name"],
            })

    layers = [whisker_lo, whisker_hi, box, median_tick, label_text]

    if outlier_rows:
        out_df = pd.DataFrame(outlier_rows)
        out_df["price_bin"] = pd.Categorical(out_df["price_bin"], categories=PRICE_LABELS, ordered=True)
        outlier_chart = (
            alt.Chart(out_df)
            .mark_circle(size=30, color="#e05252", opacity=0.6)
            .encode(
                x=alt.X("price_bin:O", sort=PRICE_LABELS),
                y=alt.Y(f"{value_col}:Q", scale=y_scale),
                tooltip=[
                    alt.Tooltip("price_bin:O", title="區間"),
                    alt.Tooltip("name:N",       title="遊戲名稱"),
                    alt.Tooltip(f"{value_col}:Q", title=y_title, format=",.2f"),
                ],
            )
        )
        layers.append(outlier_chart)

    chart = (
        alt.layer(*layers)
        .properties(height=height)
        .configure_axis(labelFontSize=11, titleFontSize=12)
        .configure_view(strokeWidth=0)
    )
    return chart


# ===========================================================================
# 區塊 1：市場結構
# ===========================================================================
st.header("區塊 1：市場結構")

# ---------------------------------------------------------------------------
# 圖 1：各價格區間遊戲數 Pareto 圖
# ---------------------------------------------------------------------------
st.subheader("圖 1 — 各價格區間遊戲數 Pareto 圖")
st.caption("長條：遊戲供給量；折線：累積百分比（觀察市場集中度）")

pareto_df = (
    df.groupby("price_bin", observed=True, as_index=False)
    .agg(count=("appid", "count"))
)
pareto_df["price_bin"] = pd.Categorical(pareto_df["price_bin"], categories=PRICE_LABELS, ordered=True)
pareto_df = pareto_df.sort_values("price_bin")
pareto_df["cumulative_pct"] = pareto_df["count"].cumsum() / pareto_df["count"].sum() * 100
pareto_df["pct_of_total"] = pareto_df["count"] / pareto_df["count"].sum() * 100
pareto_df["pct_label"] = pareto_df["pct_of_total"].round(1).astype(str) + "%"
pareto_df["cum_label"] = pareto_df["cumulative_pct"].round(1).astype(str) + "%"

if len(pareto_df) > 0:
    # Find how many bins reach 80% cumulative
    bins_to_80 = int((pareto_df["cumulative_pct"] <= 80).sum()) + 1
    bins_to_80 = min(bins_to_80, len(PRICE_LABELS))
    label_at_80 = PRICE_LABELS[bins_to_80 - 1] if bins_to_80 <= len(PRICE_LABELS) else "—"
    st.caption(f"💡 前 **{bins_to_80}** 個價位帶（至 NT${label_at_80}）累積了 80% 的遊戲供給")

    base_pareto = alt.Chart(pareto_df)

    bar_pareto = base_pareto.mark_bar(
        cornerRadiusTopLeft=3, cornerRadiusTopRight=3, color="#4a90d9"
    ).encode(
        x=alt.X("price_bin:O", sort=PRICE_LABELS, title="價格區間（NT$）",
                axis=alt.Axis(labelAngle=-30, labelFontSize=11)),
        y=alt.Y("count:Q", title="遊戲數量", axis=alt.Axis(titleColor="#4a90d9")),
        tooltip=[
            alt.Tooltip("price_bin:O",        title="價格區間"),
            alt.Tooltip("count:Q",            title="遊戲數",    format=","),
            alt.Tooltip("pct_label:N",        title="佔總數"),
            alt.Tooltip("cum_label:N",        title="累積百分比"),
        ],
    )

    line_pareto = base_pareto.mark_line(
        color="#e67e22", strokeWidth=2, point=alt.OverlayMarkDef(color="#e67e22", size=50)
    ).encode(
        x=alt.X("price_bin:O", sort=PRICE_LABELS),
        y=alt.Y("cumulative_pct:Q", title="累積百分比（%）",
                scale=alt.Scale(domain=[0, 100]),
                axis=alt.Axis(titleColor="#e67e22", format=".0f")),
        tooltip=[
            alt.Tooltip("price_bin:O",    title="價格區間"),
            alt.Tooltip("cum_label:N",    title="累積百分比"),
        ],
    )

    pareto_chart = (
        alt.layer(bar_pareto, line_pareto)
        .resolve_scale(y="independent")
        .properties(height=360)
        .configure_axis(labelFontSize=11, titleFontSize=12)
        .configure_view(strokeWidth=0)
    )
    st.altair_chart(pareto_chart, use_container_width=True)
else:
    st.info("資料不足，無法繪製圖表。")

st.markdown("---")

# ---------------------------------------------------------------------------
# 圖 2：各區間售價中位數 vs 銷量中位數（雙軸）
# ---------------------------------------------------------------------------
st.subheader("圖 2 — 各區間售價中位數 vs 銷量中位數")
st.caption("左軸（長條）：售價中位數；右軸（折線）：預測銷量中位數")

dual_df = (
    df.groupby("price_bin", observed=True, as_index=False)
    .agg(
        med_price=("price_twd_original", "median"),
        med_sales=("est_sales_low", "median"),
        n=("appid", "count"),
    )
)
dual_df["price_bin"] = pd.Categorical(dual_df["price_bin"], categories=PRICE_LABELS, ordered=True)
dual_df = dual_df.sort_values("price_bin")

if len(dual_df) > 0:
    base_dual = alt.Chart(dual_df)

    bar_dual = base_dual.mark_bar(
        cornerRadiusTopLeft=3, cornerRadiusTopRight=3, color="#5b9bd5", opacity=0.8
    ).encode(
        x=alt.X("price_bin:O", sort=PRICE_LABELS, title="價格區間（NT$）",
                axis=alt.Axis(labelAngle=-30, labelFontSize=11)),
        y=alt.Y("med_price:Q", title="售價中位數（NT$）",
                axis=alt.Axis(titleColor="#5b9bd5")),
        tooltip=[
            alt.Tooltip("price_bin:O",  title="價格區間"),
            alt.Tooltip("med_price:Q",  title="售價中位數（NT$）", format=",.0f"),
            alt.Tooltip("med_sales:Q",  title="銷量中位數",       format=","),
            alt.Tooltip("n:Q",          title="樣本數",           format=","),
        ],
    )

    line_dual = base_dual.mark_line(
        color="#e74c3c", strokeWidth=2.5,
        point=alt.OverlayMarkDef(color="#e74c3c", size=55)
    ).encode(
        x=alt.X("price_bin:O", sort=PRICE_LABELS),
        y=alt.Y("med_sales:Q", title="銷量中位數（套）",
                axis=alt.Axis(titleColor="#e74c3c", format=",")),
        tooltip=[
            alt.Tooltip("price_bin:O", title="價格區間"),
            alt.Tooltip("med_sales:Q", title="銷量中位數", format=","),
        ],
    )

    dual_chart = (
        alt.layer(bar_dual, line_dual)
        .resolve_scale(y="independent")
        .properties(height=360)
        .configure_axis(labelFontSize=11, titleFontSize=12)
        .configure_view(strokeWidth=0)
    )
    st.altair_chart(dual_chart, use_container_width=True)
else:
    st.info("資料不足，無法繪製圖表。")

st.markdown("---")

# ===========================================================================
# 區塊 2：評價表現
# ===========================================================================
st.header("區塊 2：評價表現")

col_box, col_high = st.columns([1, 1])

# ---------------------------------------------------------------------------
# 圖 3：各價格區間好評率箱型圖
# ---------------------------------------------------------------------------
with col_box:
    st.subheader("圖 3 — 好評率箱型圖")
    st.caption("僅含 review_count ≥ 10 的遊戲；虛線為 70% 好評門檻")

    if len(df_rev) == 0:
        st.info("篩選結果中沒有足夠評論資料。")
    else:
        bp3 = _build_boxplot(df_rev, "positive_ratio", "好評率", log_scale=False, height=360)
        if bp3 is not None:
            # Add reference line at 0.7 — must rebuild without .configure_* for layering
            ref_data = pd.DataFrame({"y": [0.7]})
            ref_line = (
                alt.Chart(ref_data)
                .mark_rule(color="#27ae60", strokeDash=[6, 4], strokeWidth=1.5)
                .encode(y=alt.Y("y:Q"))
            )

            # Rebuild individual layers without final configure for overlay
            data_rev = df_rev.copy()
            rows_bp3 = []
            for bin_label in PRICE_LABELS:
                sub = data_rev[data_rev["price_bin"] == bin_label]["positive_ratio"].dropna()
                n = len(sub)
                if n == 0:
                    continue
                q1  = float(sub.quantile(0.25))
                med = float(sub.quantile(0.50))
                q3  = float(sub.quantile(0.75))
                iqr = q3 - q1
                lo_w = float(sub[sub >= q1 - 1.5 * iqr].min()) if len(sub[sub >= q1 - 1.5 * iqr]) else q1
                hi_w = float(sub[sub <= q3 + 1.5 * iqr].max()) if len(sub[sub <= q3 + 1.5 * iqr]) else q3
                rows_bp3.append({
                    "price_bin": bin_label, "q1": q1, "median": med, "q3": q3,
                    "lo_whisker": lo_w, "hi_whisker": hi_w, "n": n,
                    "label": f"n={n}" if n < 30 else "",
                })

            bp3_df = pd.DataFrame(rows_bp3)
            if not bp3_df.empty:
                bp3_df["price_bin"] = pd.Categorical(bp3_df["price_bin"], categories=PRICE_LABELS, ordered=True)

                x3 = alt.X("price_bin:O", sort=PRICE_LABELS, title="價格區間（NT$）",
                            axis=alt.Axis(labelAngle=-30, labelFontSize=10))
                y3 = alt.Y(scale=alt.Scale(domain=[0, 1]))

                wlo3 = alt.Chart(bp3_df).mark_rule(color="#555", strokeWidth=1.2).encode(
                    x=x3, y=alt.Y("lo_whisker:Q", title="好評率", scale=alt.Scale(domain=[0, 1])), y2="q1:Q")
                whi3 = alt.Chart(bp3_df).mark_rule(color="#555", strokeWidth=1.2).encode(
                    x=x3, y=alt.Y("q3:Q", scale=alt.Scale(domain=[0, 1])), y2="hi_whisker:Q")
                box3 = alt.Chart(bp3_df).mark_bar(color="#4a90d9", opacity=0.75).encode(
                    x=x3,
                    y=alt.Y("q1:Q", title="好評率", scale=alt.Scale(domain=[0, 1])),
                    y2="q3:Q",
                    tooltip=[
                        alt.Tooltip("price_bin:O", title="區間"),
                        alt.Tooltip("q1:Q",        title="Q1（25%）",   format=".1%"),
                        alt.Tooltip("median:Q",    title="中位數",      format=".1%"),
                        alt.Tooltip("q3:Q",        title="Q3（75%）",   format=".1%"),
                        alt.Tooltip("n:Q",         title="樣本數",      format=","),
                    ],
                )
                med3 = alt.Chart(bp3_df).mark_tick(color="#fff", thickness=2, size=18).encode(
                    x=x3, y=alt.Y("median:Q", scale=alt.Scale(domain=[0, 1])))
                lbl3 = alt.Chart(bp3_df).mark_text(align="center", dy=-8, fontSize=10, color="#888").encode(
                    x=x3, y=alt.Y("hi_whisker:Q", scale=alt.Scale(domain=[0, 1])), text="label:N")

                out_rows3 = []
                for bin_label in PRICE_LABELS:
                    sub = data_rev[data_rev["price_bin"] == bin_label][["positive_ratio", "name"]].dropna()
                    if sub.empty:
                        continue
                    row = bp3_df[bp3_df["price_bin"] == bin_label]
                    if row.empty:
                        continue
                    lo_w = float(row["lo_whisker"].iloc[0])
                    hi_w = float(row["hi_whisker"].iloc[0])
                    for _, r in sub[(sub["positive_ratio"] < lo_w) | (sub["positive_ratio"] > hi_w)].iterrows():
                        out_rows3.append({"price_bin": bin_label, "positive_ratio": r["positive_ratio"], "name": r["name"]})

                layers3 = [wlo3, whi3, box3, med3, lbl3, ref_line]
                if out_rows3:
                    out3_df = pd.DataFrame(out_rows3)
                    out3_df["price_bin"] = pd.Categorical(out3_df["price_bin"], categories=PRICE_LABELS, ordered=True)
                    out3 = alt.Chart(out3_df).mark_circle(size=30, color="#e05252", opacity=0.6).encode(
                        x=alt.X("price_bin:O", sort=PRICE_LABELS),
                        y=alt.Y("positive_ratio:Q", scale=alt.Scale(domain=[0, 1])),
                        tooltip=[
                            alt.Tooltip("price_bin:O",       title="區間"),
                            alt.Tooltip("name:N",            title="遊戲名稱"),
                            alt.Tooltip("positive_ratio:Q",  title="好評率", format=".1%"),
                        ],
                    )
                    layers3.append(out3)

                chart3 = (
                    alt.layer(*layers3)
                    .properties(height=360)
                    .configure_axis(labelFontSize=10, titleFontSize=11)
                    .configure_view(strokeWidth=0)
                )
                st.altair_chart(chart3, use_container_width=True)

# ---------------------------------------------------------------------------
# 圖 5：各區間高分遊戲佔比
# ---------------------------------------------------------------------------
with col_high:
    st.subheader("圖 5 — 高分遊戲佔比（好評率 ≥ 80%）")
    st.caption("僅含 review_count ≥ 10 的遊戲")

    if len(df_rev) == 0:
        st.info("資料不足。")
    else:
        high_df = (
            df_rev.groupby("price_bin", observed=True, as_index=False)
            .apply(lambda g: pd.Series({
                "total": len(g),
                "high": (g["positive_ratio"] >= 0.8).sum(),
            }))
            .reset_index(drop=True)
        )
        high_df["pct"] = high_df["high"] / high_df["total"].replace(0, np.nan) * 100
        high_df["bar_label"] = high_df.apply(
            lambda r: f"{r['pct']:.1f}%\n(n={int(r['total'])})" if pd.notna(r["pct"]) else "",
            axis=1,
        )
        high_df["price_bin"] = pd.Categorical(high_df["price_bin"], categories=PRICE_LABELS, ordered=True)
        high_df = high_df.sort_values("price_bin").dropna(subset=["pct"])

        if len(high_df) > 0:
            bar5 = (
                alt.Chart(high_df)
                .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
                .encode(
                    x=alt.X("price_bin:O", sort=PRICE_LABELS, title="價格區間（NT$）",
                            axis=alt.Axis(labelAngle=-30, labelFontSize=10)),
                    y=alt.Y("pct:Q", title="高分遊戲佔比（%）", scale=alt.Scale(domain=[0, 100])),
                    color=alt.Color(
                        "pct:Q",
                        scale=alt.Scale(scheme="greens", domain=[0, 100]),
                        legend=None,
                    ),
                    tooltip=[
                        alt.Tooltip("price_bin:O", title="區間"),
                        alt.Tooltip("pct:Q",       title="高分佔比（%）", format=".1f"),
                        alt.Tooltip("high:Q",      title="高分遊戲數",   format=","),
                        alt.Tooltip("total:Q",     title="有效遊戲數",   format=","),
                    ],
                )
                .properties(height=360)
            )

            text5 = (
                alt.Chart(high_df)
                .mark_text(align="center", dy=-6, fontSize=10, color="#333")
                .encode(
                    x=alt.X("price_bin:O", sort=PRICE_LABELS),
                    y=alt.Y("pct:Q"),
                    text=alt.Text("bar_label:N"),
                )
            )

            chart5 = (
                alt.layer(bar5, text5)
                .properties(height=360)
                .configure_axis(labelFontSize=10, titleFontSize=11)
                .configure_view(strokeWidth=0)
            )
            st.altair_chart(chart5, use_container_width=True)
        else:
            st.info("資料不足。")

# ---------------------------------------------------------------------------
# 圖 4：各區間評論等級堆疊百分比圖（全寬）
# ---------------------------------------------------------------------------
st.subheader("圖 4 — 各區間評論等級組成（100% 堆疊）")
st.caption("含全部遊戲（含無評論）；消除樣本數差異，純粹比較品質結構")

stack_df = (
    df.groupby(["price_bin", "review_score_desc_zh"], observed=True, as_index=False)
    .agg(count=("appid", "count"))
)
stack_df["price_bin"] = pd.Categorical(stack_df["price_bin"], categories=PRICE_LABELS, ordered=True)

# Compute percentage within each price_bin
stack_totals = stack_df.groupby("price_bin", observed=True)["count"].transform("sum")
stack_df["pct"] = stack_df["count"] / stack_totals * 100
stack_df["pct_label"] = stack_df["pct"].round(1).astype(str) + "%"

# Sort order for stacking
stack_df["sort_order"] = stack_df["review_score_desc_zh"].apply(
    lambda x: STACKED_ORDER.index(x) if x in STACKED_ORDER else 999
)

present_ratings = stack_df["review_score_desc_zh"].unique().tolist()
s4_domain, s4_range = _rating_scale(present_ratings)

if len(stack_df) > 0:
    chart4 = (
        alt.Chart(stack_df)
        .mark_bar()
        .encode(
            x=alt.X("price_bin:O", sort=PRICE_LABELS, title="價格區間（NT$）",
                    axis=alt.Axis(labelAngle=-30, labelFontSize=11)),
            y=alt.Y("pct:Q", title="佔比（%）", stack="normalize",
                    axis=alt.Axis(format=".0%")),
            color=alt.Color(
                "review_score_desc_zh:N",
                scale=alt.Scale(domain=s4_domain, range=s4_range),
                sort=s4_domain,
                legend=alt.Legend(
                    title="評論等級",
                    orient="right",
                    labelFontSize=11,
                ),
            ),
            order=alt.Order("sort_order:Q", sort="ascending"),
            tooltip=[
                alt.Tooltip("price_bin:O",           title="價格區間"),
                alt.Tooltip("review_score_desc_zh:N", title="評論等級"),
                alt.Tooltip("count:Q",               title="遊戲數",   format=","),
                alt.Tooltip("pct_label:N",           title="佔比"),
            ],
        )
        .properties(height=380)
        .configure_axis(labelFontSize=11, titleFontSize=12)
        .configure_view(strokeWidth=0)
    )
    st.altair_chart(chart4, use_container_width=True)
else:
    st.info("資料不足，無法繪製圖表。")

st.markdown("---")

# ===========================================================================
# 區塊 3：商業表現
# ===========================================================================
st.header("區塊 3：商業表現")

col_rev, col_sales = st.columns([1, 1])

# ---------------------------------------------------------------------------
# 圖 6：各區間總估計營收貢獻
# ---------------------------------------------------------------------------
with col_rev:
    st.subheader("圖 6 — 總估算營收貢獻")
    st.caption("估算值 = price_twd_original × est_sales_low，未計入折扣")

    rev_df = (
        df.groupby("price_bin", observed=True, as_index=False)
        .agg(
            total_revenue=("est_revenue", "sum"),
            n=("appid", "count"),
        )
    )
    rev_df["price_bin"] = pd.Categorical(rev_df["price_bin"], categories=PRICE_LABELS, ordered=True)
    rev_df = rev_df.sort_values("price_bin")
    total_all = rev_df["total_revenue"].sum()
    rev_df["pct_revenue"] = rev_df["total_revenue"] / total_all * 100 if total_all > 0 else 0
    rev_df["avg_revenue"] = rev_df["total_revenue"] / rev_df["n"].replace(0, np.nan)

    # Choose unit
    use_yi = total_all >= 1e8
    divisor_r = 1e8 if use_yi else 1e4
    unit_label = "億台幣" if use_yi else "萬台幣"
    rev_df["revenue_display"] = rev_df["total_revenue"] / divisor_r
    rev_df["avg_display"] = rev_df["avg_revenue"] / divisor_r
    rev_df["pct_label"] = rev_df["pct_revenue"].round(1).astype(str) + "%"

    if len(rev_df) > 0 and total_all > 0:
        bar6 = (
            alt.Chart(rev_df)
            .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
            .encode(
                x=alt.X("price_bin:O", sort=PRICE_LABELS, title="價格區間（NT$）",
                        axis=alt.Axis(labelAngle=-30, labelFontSize=10)),
                y=alt.Y("revenue_display:Q", title=f"估算營收（{unit_label}）"),
                color=alt.Color(
                    "revenue_display:Q",
                    scale=alt.Scale(scheme="oranges"),
                    legend=None,
                ),
                tooltip=[
                    alt.Tooltip("price_bin:O",       title="價格區間"),
                    alt.Tooltip("revenue_display:Q", title=f"總營收（{unit_label}）", format=",.2f"),
                    alt.Tooltip("pct_label:N",       title="佔總營收"),
                    alt.Tooltip("n:Q",               title="遊戲數",               format=","),
                    alt.Tooltip("avg_display:Q",     title=f"平均單款（{unit_label}）", format=",.3f"),
                ],
            )
            .properties(height=380)
        )

        text6 = (
            alt.Chart(rev_df)
            .mark_text(align="center", dy=-6, fontSize=10, color="#7d6000")
            .encode(
                x=alt.X("price_bin:O", sort=PRICE_LABELS),
                y=alt.Y("revenue_display:Q"),
                text=alt.Text("pct_label:N"),
            )
        )

        chart6 = (
            alt.layer(bar6, text6)
            .properties(height=380)
            .configure_axis(labelFontSize=10, titleFontSize=11)
            .configure_view(strokeWidth=0)
        )
        st.altair_chart(chart6, use_container_width=True)
    else:
        st.info("資料不足，無法繪製圖表。")

# ---------------------------------------------------------------------------
# 圖 7：各區間預測銷量箱型圖（log 軸）
# ---------------------------------------------------------------------------
with col_sales:
    st.subheader("圖 7 — 預測銷量箱型圖（log 軸）")
    st.caption("觀察同價位內銷量差距（長尾分布）")

    df_sales = df[df["est_sales_low"] > 0].copy()

    if len(df_sales) == 0:
        st.info("資料不足。")
    else:
        # Manual log box plot
        rows_bp7 = []
        for bin_label in PRICE_LABELS:
            sub = df_sales[df_sales["price_bin"] == bin_label]["est_sales_low"].dropna()
            n = len(sub)
            if n == 0:
                continue
            q1  = float(sub.quantile(0.25))
            med = float(sub.quantile(0.50))
            q3  = float(sub.quantile(0.75))
            iqr = q3 - q1
            lo_fence = max(q1 - 1.5 * iqr, 0.1)
            hi_fence = q3 + 1.5 * iqr
            lo_w = float(sub[sub >= lo_fence].min()) if len(sub[sub >= lo_fence]) else q1
            hi_w = float(sub[sub <= hi_fence].max()) if len(sub[sub <= hi_fence]) else q3
            rows_bp7.append({
                "price_bin": bin_label, "q1": max(q1, 1), "median": max(med, 1),
                "q3": max(q3, 1), "lo_whisker": max(lo_w, 1), "hi_whisker": max(hi_w, 1),
                "n": n, "label": f"n={n}" if n < 30 else "",
            })

        if rows_bp7:
            bp7_df = pd.DataFrame(rows_bp7)
            bp7_df["price_bin"] = pd.Categorical(bp7_df["price_bin"], categories=PRICE_LABELS, ordered=True)

            x7 = alt.X("price_bin:O", sort=PRICE_LABELS, title="價格區間（NT$）",
                        axis=alt.Axis(labelAngle=-30, labelFontSize=10))
            log_scale = alt.Scale(type="log")

            wlo7 = alt.Chart(bp7_df).mark_rule(color="#555", strokeWidth=1.2).encode(
                x=x7, y=alt.Y("lo_whisker:Q", title="預測銷量（log）", scale=log_scale), y2="q1:Q")
            whi7 = alt.Chart(bp7_df).mark_rule(color="#555", strokeWidth=1.2).encode(
                x=x7, y=alt.Y("q3:Q", scale=log_scale), y2="hi_whisker:Q")
            box7 = alt.Chart(bp7_df).mark_bar(color="#e67e22", opacity=0.75).encode(
                x=x7,
                y=alt.Y("q1:Q", title="預測銷量（套，log）", scale=log_scale),
                y2="q3:Q",
                tooltip=[
                    alt.Tooltip("price_bin:O", title="區間"),
                    alt.Tooltip("q1:Q",        title="Q1",   format=","),
                    alt.Tooltip("median:Q",    title="中位數", format=","),
                    alt.Tooltip("q3:Q",        title="Q3",   format=","),
                    alt.Tooltip("n:Q",         title="樣本數", format=","),
                ],
            )
            med7 = alt.Chart(bp7_df).mark_tick(color="#fff", thickness=2, size=18).encode(
                x=x7, y=alt.Y("median:Q", scale=log_scale))
            lbl7 = alt.Chart(bp7_df).mark_text(align="center", dy=-8, fontSize=10, color="#888").encode(
                x=x7, y=alt.Y("hi_whisker:Q", scale=log_scale), text="label:N")

            out_rows7 = []
            for bin_label in PRICE_LABELS:
                sub = df_sales[df_sales["price_bin"] == bin_label][["est_sales_low", "name"]].dropna()
                if sub.empty:
                    continue
                row = bp7_df[bp7_df["price_bin"] == bin_label]
                if row.empty:
                    continue
                lo_w = float(row["lo_whisker"].iloc[0])
                hi_w = float(row["hi_whisker"].iloc[0])
                for _, r in sub[(sub["est_sales_low"] < lo_w) | (sub["est_sales_low"] > hi_w)].iterrows():
                    out_rows7.append({"price_bin": bin_label, "est_sales_low": max(r["est_sales_low"], 1), "name": r["name"]})

            layers7 = [wlo7, whi7, box7, med7, lbl7]
            if out_rows7:
                out7_df = pd.DataFrame(out_rows7)
                out7_df["price_bin"] = pd.Categorical(out7_df["price_bin"], categories=PRICE_LABELS, ordered=True)
                out7 = alt.Chart(out7_df).mark_circle(size=30, color="#e05252", opacity=0.6).encode(
                    x=alt.X("price_bin:O", sort=PRICE_LABELS),
                    y=alt.Y("est_sales_low:Q", scale=log_scale),
                    tooltip=[
                        alt.Tooltip("price_bin:O",     title="區間"),
                        alt.Tooltip("name:N",          title="遊戲名稱"),
                        alt.Tooltip("est_sales_low:Q", title="預測銷量", format=","),
                    ],
                )
                layers7.append(out7)

            chart7 = (
                alt.layer(*layers7)
                .properties(height=380)
                .configure_axis(labelFontSize=10, titleFontSize=11)
                .configure_view(strokeWidth=0)
            )
            st.altair_chart(chart7, use_container_width=True)
        else:
            st.info("資料不足。")

# ---------------------------------------------------------------------------
# 圖 8：各區間平均折扣幅度（資料依賴）
# ---------------------------------------------------------------------------
st.subheader("圖 8 — 各區間平均歷史折扣幅度")

df_discount = df[df["lowest_discount_percent"].notna()].copy()
non_null_rate = len(df_discount) / len(df) if len(df) > 0 else 0

if non_null_rate < 0.30:
    st.info(
        f"⏳ 折扣資料爬取中（目前完成率 {non_null_rate * 100:.1f}%，低於 30%）。"
        "資料補齊後此圖將自動顯示。"
    )
else:
    st.caption(f"僅含 lowest_discount_percent 非空值（目前覆蓋率 {non_null_rate * 100:.1f}%）")

    disc_df = (
        df_discount.groupby("price_bin", observed=True, as_index=False)
        .agg(
            avg_discount=("lowest_discount_percent", "mean"),
            pct_discounted=("lowest_discount_percent", lambda x: (x > 0).sum() / len(x) * 100),
            n=("appid", "count"),
        )
    )
    disc_df["price_bin"] = pd.Categorical(disc_df["price_bin"], categories=PRICE_LABELS, ordered=True)
    disc_df = disc_df.sort_values("price_bin")

    if len(disc_df) > 0:
        base_disc = alt.Chart(disc_df)

        bar8 = base_disc.mark_bar(
            cornerRadiusTopLeft=3, cornerRadiusTopRight=3, color="#8e44ad", opacity=0.8
        ).encode(
            x=alt.X("price_bin:O", sort=PRICE_LABELS, title="價格區間（NT$）",
                    axis=alt.Axis(labelAngle=-30, labelFontSize=11)),
            y=alt.Y("avg_discount:Q", title="平均歷史折扣（%）",
                    axis=alt.Axis(titleColor="#8e44ad")),
            tooltip=[
                alt.Tooltip("price_bin:O",     title="區間"),
                alt.Tooltip("avg_discount:Q",  title="平均折扣（%）",   format=".1f"),
                alt.Tooltip("pct_discounted:Q", title="曾打折佔比（%）", format=".1f"),
                alt.Tooltip("n:Q",             title="樣本數",           format=","),
            ],
        )

        line8 = base_disc.mark_line(
            color="#27ae60", strokeWidth=2,
            point=alt.OverlayMarkDef(color="#27ae60", size=50)
        ).encode(
            x=alt.X("price_bin:O", sort=PRICE_LABELS),
            y=alt.Y("pct_discounted:Q", title="曾打折遊戲佔比（%）",
                    scale=alt.Scale(domain=[0, 100]),
                    axis=alt.Axis(titleColor="#27ae60", format=".0f")),
            tooltip=[
                alt.Tooltip("price_bin:O",      title="區間"),
                alt.Tooltip("pct_discounted:Q", title="曾打折佔比（%）", format=".1f"),
            ],
        )

        chart8 = (
            alt.layer(bar8, line8)
            .resolve_scale(y="independent")
            .properties(height=320)
            .configure_axis(labelFontSize=11, titleFontSize=12)
            .configure_view(strokeWidth=0)
        )
        st.altair_chart(chart8, use_container_width=True)
    else:
        st.info("資料不足。")

st.markdown("---")

# ===========================================================================
# 區塊 4：交叉洞察
# ===========================================================================
st.header("區塊 4：交叉洞察")

# ---------------------------------------------------------------------------
# 圖 9：價格區間 × 發行月份 熱力圖
# ---------------------------------------------------------------------------
st.subheader("圖 9 — 價格區間 × 發行月份 熱力圖")
st.caption("顏色：該組合累積發行遊戲數（跨所有年份）；觀察各價位偏好哪些月份上架")

MONTH_ZH = {1: "1月", 2: "2月", 3: "3月", 4: "4月", 5: "5月", 6: "6月",
             7: "7月", 8: "8月", 9: "9月", 10: "10月", 11: "11月", 12: "12月"}

df_hm10 = df[df["release_month"].notna()].copy()
df_hm10["month_int"] = df_hm10["release_month"].astype(int)
df_hm10["month_str"] = df_hm10["month_int"].map(MONTH_ZH)

if len(df_hm10) == 0:
    st.info("發行月份資料不足。")
else:
    hm10_agg = (
        df_hm10.groupby(["month_int", "month_str", "price_bin"], observed=True, as_index=False)
        .agg(count=("appid", "count"))
    )
    hm10_agg["price_bin"] = pd.Categorical(hm10_agg["price_bin"], categories=PRICE_LABELS, ordered=True)

    # Full grid
    all_months = list(range(1, 13))
    full_grid10 = pd.MultiIndex.from_product(
        [all_months, PRICE_LABELS], names=["month_int", "price_bin"]
    ).to_frame(index=False)
    full_grid10["month_str"] = full_grid10["month_int"].map(MONTH_ZH)
    full_grid10["price_bin"] = pd.Categorical(full_grid10["price_bin"], categories=PRICE_LABELS, ordered=True)
    hm10 = full_grid10.merge(hm10_agg[["month_int", "price_bin", "count"]], on=["month_int", "price_bin"], how="left")
    hm10["count"] = hm10["count"].fillna(0).astype(int)
    hm10["cell_label"] = hm10["count"].apply(lambda v: str(v) if v > 0 else "")

    base10 = alt.Chart(hm10)

    rect10 = base10.mark_rect().encode(
        x=alt.X("price_bin:O", sort=PRICE_LABELS, title="價格區間（NT$）",
                axis=alt.Axis(labelAngle=-30, labelFontSize=10)),
        y=alt.Y("month_int:O", sort=list(range(1, 13)), title="月份",
                axis=alt.Axis(
                    labelExpr="{'1':'1月','2':'2月','3':'3月','4':'4月','5':'5月','6':'6月',"
                              "'7':'7月','8':'8月','9':'9月','10':'10月','11':'11月','12':'12月'}[datum.value]",
                    labelAngle=0,
                )),
        color=alt.Color(
            "count:Q",
            scale=alt.Scale(scheme="yelloworangered"),
            legend=alt.Legend(title="發行數"),
        ),
        tooltip=[
            alt.Tooltip("month_str:N",  title="月份"),
            alt.Tooltip("price_bin:O",  title="區間"),
            alt.Tooltip("count:Q",      title="發行數", format=","),
        ],
    )

    text10 = base10.mark_text(fontSize=10, color="#222").encode(
        x=alt.X("price_bin:O", sort=PRICE_LABELS),
        y=alt.Y("month_int:O", sort=list(range(1, 13))),
        text="cell_label:N",
    )

    chart10 = (
        alt.layer(rect10, text10)
        .properties(height=420)
        .configure_axis(labelFontSize=10, titleFontSize=11)
        .configure_view(strokeWidth=0)
    )
    st.altair_chart(chart10, use_container_width=True)
