"""
pages/2_Release_Heatmap.py — 發售熱度分析
KPI 列 + 年份長條圖 + 年×月 熱力圖
"""
import datetime
import json
import time
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as _components

from data import (
    load_games,
    RATING_DISPLAY_ORDER,
    SORT_OPTIONS,
    steam_url,
    fmt_twd,
)

DEBUG_LOG_PATH = Path(__file__).resolve().parents[2] / "debug-2ba0cd.log"
DEBUG_RUN_ID = "post-fix-1"


def _debug_log(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    payload = {
        "sessionId": "2ba0cd",
        "runId": DEBUG_RUN_ID,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    try:
        with DEBUG_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass

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
# 共用：可排序 HTML 表格（JS client-side sort，不改任何 td 樣式）
# ---------------------------------------------------------------------------
def _make_sortable_table(
    rows_html: list[str],
    table_id: str,
    columns: list[tuple[str, str]],
) -> str:
    th_parts = []
    for i, (label, stype) in enumerate(columns):
        if stype == "none":
            th_parts.append(f'<th data-sort="none" style="{_TH_BASE_STYLE}">{label}</th>')
        else:
            th_parts.append(
                f'<th data-sort="{stype}" data-col="{i}" data-dir="none" '
                f'style="{_TH_BASE_STYLE}cursor:pointer;user-select:none;" '
                f'onclick="sortTable(\'{table_id}\',{i},this)">'
                f'{label} <span class="sort-arrow" style="opacity:0.5;font-size:0.7em;">⇅</span></th>'
            )
    thead_html = "<tr>" + "".join(th_parts) + "</tr>"
    return f"""
<style>
#{table_id} {{ width:100%;border-collapse:collapse;font-family:inherit; }}
#{table_id} th {{ background:#1e2a3a;color:#8ba3bc;font-size:0.78rem;font-weight:600;
    text-transform:uppercase;letter-spacing:0.05em;padding:8px;text-align:left;
    border-bottom:1px solid #2a3f55; }}
#{table_id} td {{ border-bottom:1px solid #1e2a3a; }}
#{table_id} tr:hover td {{ background:#1a2535; }}
</style>
{_SORT_JS}
<table id="{table_id}">
  <thead>{thead_html}</thead>
  <tbody>{"".join(rows_html)}</tbody>
</table>
"""

_TH_BASE_STYLE = ""
_SORT_JS = """
<script>
function sortTable(tableId,colIdx,th){
  var table=document.getElementById(tableId);
  var tbody=table.querySelector('tbody');
  var rows=Array.from(tbody.querySelectorAll('tr'));
  var stype=th.getAttribute('data-sort');
  var dir=th.getAttribute('data-dir');
  var newDir=(dir==='desc')?'asc':'desc';
  th.setAttribute('data-dir',newDir);
  table.querySelectorAll('th[data-sort]').forEach(function(h){
    if(h.getAttribute('data-sort')==='none')return;
    var a=h.querySelector('.sort-arrow');
    if(a)a.textContent='⇅';
    if(h!==th)h.setAttribute('data-dir','none');
  });
  var arrow=th.querySelector('.sort-arrow');
  if(arrow)arrow.textContent=(newDir==='desc')?'▼':'▲';
  rows.sort(function(a,b){
    var ca=a.querySelectorAll('td')[colIdx];
    var cb=b.querySelectorAll('td')[colIdx];
    var va=ca?ca.innerText.trim():'';
    var vb=cb?cb.innerText.trim():'';
    if(stype==='num'){
      var na=parseFloat(va.replace(/[^0-9.-]/g,''))||0;
      var nb=parseFloat(vb.replace(/[^0-9.-]/g,''))||0;
      return(newDir==='desc')?nb-na:na-nb;
    }
    return(newDir==='desc')?vb.localeCompare(va,'zh'):va.localeCompare(vb,'zh');
  });
  rows.forEach(function(r){tbody.appendChild(r);});
}
</script>
"""


# ---------------------------------------------------------------------------
# Heatmap selection state
# ---------------------------------------------------------------------------
if "hm_selected_year" not in st.session_state:
    st.session_state["hm_selected_year"] = None
if "hm_selected_month" not in st.session_state:
    st.session_state["hm_selected_month"] = None
if "hm_show_dialog" not in st.session_state:
    st.session_state["hm_show_dialog"] = False


def _extract_year_month(payload):
    """Recursively extract release_year/release_month from selection payload."""
    if isinstance(payload, dict):
        if "release_year" in payload and "release_month" in payload:
            try:
                return int(payload["release_year"]), int(payload["release_month"])
            except (TypeError, ValueError):
                return None
        for v in payload.values():
            found = _extract_year_month(v)
            if found is not None:
                return found
    elif isinstance(payload, (list, tuple)):
        for v in payload:
            found = _extract_year_month(v)
            if found is not None:
                return found
    return None

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

color_mode = st.radio(
    "上色模式",
    options=["跨年份比較", "每年獨立"],
    horizontal=True,
    key="heatmap_color_mode",
)

display_mode = st.radio(
    "顯示模式",
    options=["單一指標", "並排對照"],
    horizontal=True,
    key="heatmap_display_mode",
)

metric_options = [
    "發售數量",
    "評論總數(換算遊戲套數指標)",
    "平均評論數(每款遊戲)",
]

if display_mode == "單一指標":
    metric_opt = st.radio(
        "顏色指標",
        options=metric_options,
        horizontal=True,
        key="heatmap_metric",
    )
    left_metric = metric_opt
    right_metric = None
else:
    sm_col1, sm_col2 = st.columns(2)
    left_metric = sm_col1.selectbox(
        "左圖指標",
        options=metric_options,
        index=0,
        key="heatmap_left_metric",
    )
    right_metric = sm_col2.selectbox(
        "右圖指標",
        options=metric_options,
        index=2,
        key="heatmap_right_metric",
    )
    metric_opt = left_metric
# region agent log
_debug_log(
    "H1",
    "2_Release_Heatmap.py:metric_opt",
    "Metric/color mode rendered",
    {
        "metric_opt": metric_opt,
        "color_mode": color_mode,
        "display_mode": display_mode,
        "left_metric": left_metric,
        "right_metric": right_metric,
        "prev_metric_opt": st.session_state.get("dbg_prev_metric_opt"),
        "prev_color_mode": st.session_state.get("dbg_prev_color_mode"),
        "hm_show_dialog": st.session_state.get("hm_show_dialog"),
        "hm_selected_year": st.session_state.get("hm_selected_year"),
        "hm_selected_month": st.session_state.get("hm_selected_month"),
    },
)
# endregion
st.session_state["dbg_prev_metric_opt"] = metric_opt
st.session_state["dbg_prev_color_mode"] = color_mode
st.session_state["dbg_prev_display_mode"] = display_mode

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
        total_reviews=("review_count", "sum"),
    )
)
hm_df["avg_reviews"] = (hm_df["total_reviews"] / hm_df["count"].replace(0, pd.NA)).fillna(0.0)
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
hm_df["total_reviews"] = hm_df["total_reviews"].fillna(0).astype(int)
hm_df["avg_reviews"] = hm_df["avg_reviews"].fillna(0.0)
hm_df["year_str"]        = hm_df["release_year"].astype(str)
hm_df["month_label"]     = hm_df["release_month"].map(month_labels)

# Exclude future months of current year from color calculations.
today = datetime.date.today()
future_month_mask = (
    (hm_df["release_year"] == today.year)
    & (hm_df["release_month"] > today.month)
)

hm_df["count_heat"] = hm_df["count"].where(~future_month_mask, pd.NA)
hm_df["reviews_heat"] = hm_df["total_reviews"].where(~future_month_mask, pd.NA)
hm_df["avg_reviews_heat"] = hm_df["avg_reviews"].where(~future_month_mask, pd.NA)

# Per-year normalization for relative heat mode (future months excluded).
count_year_max = hm_df.groupby("release_year")["count_heat"].transform("max")
reviews_year_max = hm_df.groupby("release_year")["reviews_heat"].transform("max")
avg_reviews_year_max = hm_df.groupby("release_year")["avg_reviews_heat"].transform("max")
hm_df["count_norm"] = (hm_df["count_heat"] / count_year_max.replace(0, pd.NA)).fillna(0.0)
hm_df["reviews_norm"] = (hm_df["reviews_heat"] / reviews_year_max.replace(0, pd.NA)).fillna(0.0)
hm_df["avg_reviews_norm"] = (hm_df["avg_reviews_heat"] / avg_reviews_year_max.replace(0, pd.NA)).fillna(0.0)

metric_field_map = {
    "發售數量": {
        "raw_col": "count",
        "heat_col": "count_heat",
        "norm_col": "count_norm",
        "title": "發售數量",
    },
    "評論總數(換算遊戲套數指標)": {
        "raw_col": "total_reviews",
        "heat_col": "reviews_heat",
        "norm_col": "reviews_norm",
        "title": "評論總數(換算遊戲套數指標)",
    },
    "平均評論數(每款遊戲)": {
        "raw_col": "avg_reviews",
        "heat_col": "avg_reviews_heat",
        "norm_col": "avg_reviews_norm",
        "title": "平均評論數(每款遊戲)",
    },
}

base_tooltip_fields = [
    alt.Tooltip("year_str:N", title="年份"),
    alt.Tooltip("month_label:N", title="月份"),
    alt.Tooltip("count:Q", title="發售數量", format=","),
    alt.Tooltip("total_reviews:Q", title="評論總數(換算遊戲套數指標)", format=","),
    alt.Tooltip("avg_reviews:Q", title="平均評論數(每款遊戲)", format=",.1f"),
]


def _build_color_spec(metric_name: str):
    metric_info = metric_field_map[metric_name]
    is_per_year_mode = color_mode == "每年獨立"
    if is_per_year_mode:
        color_field = f"{metric_info['norm_col']}:Q"
        relative_tooltip = alt.Tooltip(
            f"{metric_info['norm_col']}:Q",
            title="相對該年最大",
            format=".0%",
        )
        color_title = f"{metric_info['title']}（相對該年最大）"
        color_scale = alt.Scale(scheme="orangered", domain=[0, 1])
        color_legend = alt.Legend(title=color_title, format=".0%")
        tooltip_fields = base_tooltip_fields + [relative_tooltip]
    else:
        color_field = f"{metric_info['heat_col']}:Q"
        color_title = metric_info["title"]
        non_future_metric = hm_df.loc[~future_month_mask, metric_info["raw_col"]]
        if len(non_future_metric) > 0:
            metric_min = float(non_future_metric.min())
            metric_max = float(non_future_metric.max())
            if metric_max > metric_min:
                color_scale = alt.Scale(scheme="orangered", domain=[metric_min, metric_max])
            else:
                color_scale = alt.Scale(scheme="orangered")
        else:
            color_scale = alt.Scale(scheme="orangered")
        color_legend = alt.Legend(title=color_title)
        tooltip_fields = base_tooltip_fields
    return color_field, color_scale, color_legend, tooltip_fields

# Define a point selection so Streamlit can capture click events.
heatmap_pick = alt.selection_point(
    name="hm_pick",
    fields=["release_year", "release_month"],
    on="click",
)

def _build_heatmap_chart(metric_name: str):
    color_field, color_scale, color_legend, tooltip_fields = _build_color_spec(metric_name)
    return (
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
                scale=color_scale,
                legend=color_legend,
            ),
            tooltip=tooltip_fields,
        )
        .add_params(heatmap_pick)
        .properties(height=max(200, len(years_in) * 36))
        .configure_axis(labelFontSize=13, titleFontSize=13)
        .configure_view(strokeWidth=0)
    )


if display_mode == "單一指標":
    heatmap_event_candidates = [
        st.altair_chart(
            _build_heatmap_chart(left_metric),
            use_container_width=True,
            on_select="rerun",
            selection_mode="hm_pick",
        )
    ]
else:
    left_col, right_col = st.columns(2)
    left_col.caption(f"左圖：{left_metric}")
    right_col.caption(f"右圖：{right_metric}")
    left_event = left_col.altair_chart(
        _build_heatmap_chart(left_metric),
        use_container_width=True,
        on_select="rerun",
        selection_mode="hm_pick",
    )
    right_event = right_col.altair_chart(
        _build_heatmap_chart(right_metric),
        use_container_width=True,
        on_select="rerun",
        selection_mode="hm_pick",
    )
    heatmap_event_candidates = [left_event, right_event]

# Persist clicked heatmap cell (year + month)
picked_year_month = None
for heatmap_event in heatmap_event_candidates:
    if heatmap_event is None:
        continue
    event_selection = getattr(heatmap_event, "selection", heatmap_event)
    picked_year_month = _extract_year_month(event_selection)
    if picked_year_month is not None:
        break
# region agent log
_debug_log(
    "H2",
    "2_Release_Heatmap.py:heatmap_event",
    "Heatmap event parsed",
    {
        "event_type": type(heatmap_event).__name__ if heatmap_event is not None else "NoneType",
        "picked_year_month": picked_year_month,
        "hm_show_dialog_before_pick": st.session_state.get("hm_show_dialog"),
    },
)
# endregion
if picked_year_month is not None:
    selected_year, selected_month = picked_year_month
    is_new_pick = (
        st.session_state["hm_selected_year"] != selected_year
        or st.session_state["hm_selected_month"] != selected_month
    )
    # region agent log
    _debug_log(
        "H3",
        "2_Release_Heatmap.py:pick_compare",
        "Picked year/month comparison",
        {
            "selected_year": selected_year,
            "selected_month": selected_month,
            "prev_year": st.session_state.get("hm_selected_year"),
            "prev_month": st.session_state.get("hm_selected_month"),
            "is_new_pick": is_new_pick,
        },
    )
    # endregion
    st.session_state["hm_selected_year"] = selected_year
    st.session_state["hm_selected_month"] = selected_month
    if is_new_pick:
        st.session_state["hm_show_dialog"] = True
        # region agent log
        _debug_log(
            "H4",
            "2_Release_Heatmap.py:set_show_dialog",
            "Dialog toggled on by new heatmap pick",
            {
                "hm_show_dialog": st.session_state.get("hm_show_dialog"),
                "picked_year": selected_year,
                "picked_month": selected_month,
            },
        )
        # endregion

# Selection action row
picked_year = st.session_state["hm_selected_year"]
picked_month = st.session_state["hm_selected_month"]
if picked_year is not None and picked_month is not None:
    info_col, clear_col = st.columns([5, 1])
    info_col.caption(f"目前選取：{picked_year} 年 {picked_month} 月")
    if clear_col.button("清除選取", key="clear_hm_pick", use_container_width=True):
        st.session_state["hm_selected_year"] = None
        st.session_state["hm_selected_month"] = None
        st.session_state["hm_show_dialog"] = False
        st.rerun()

# If current filters no longer include selected cell, clear it automatically.
valid_pairs = set(zip(hm_df["release_year"].astype(int), hm_df["release_month"].astype(int)))
if (
    picked_year is not None
    and picked_month is not None
    and (picked_year, picked_month) not in valid_pairs
):
    st.session_state["hm_selected_year"] = None
    st.session_state["hm_selected_month"] = None
    st.session_state["hm_show_dialog"] = False
    st.info("所選年月已不在目前篩選結果中，已自動清除。")
    picked_year, picked_month = None, None

# Build selected month game list and show dialog.
if picked_year is not None and picked_month is not None:
    month_df = df[
        (df["release_year"].astype("Int64") == picked_year)
        & (df["release_month"].astype("Int64") == picked_month)
    ].copy()
    sort_col, ascending = SORT_OPTIONS[sort_label]
    month_df = month_df.sort_values(sort_col, ascending=ascending, na_position="last")

    def _fmt_date(val) -> str:
        try:
            return pd.Timestamp(val).strftime("%Y-%m-%d") if pd.notna(val) else "—"
        except Exception:
            return "—"

    def _fmt_sales(val) -> str:
        try:
            return f"{int(val):,} 套"
        except (TypeError, ValueError):
            return "—"

    if st.session_state.get("hm_show_dialog", False):
        # Consume one-shot dialog flag so non-click reruns don't reopen it.
        st.session_state["hm_show_dialog"] = False
        # region agent log
        _debug_log(
            "H5",
            "2_Release_Heatmap.py:dialog_gate",
            "Dialog render gate entered",
            {
                "hm_show_dialog_after_consume": st.session_state.get("hm_show_dialog"),
                "picked_year": picked_year,
                "picked_month": picked_month,
                "month_df_len": int(len(month_df)),
                "metric_opt": metric_opt,
            },
        )
        # endregion
        @st.dialog(f"{picked_year} 年 {picked_month} 月遊戲清單", width="large")
        def show_month_games_dialog():
            st.markdown(f"共 **{len(month_df):,}** 款遊戲")
            if len(month_df) == 0:
                st.info("此月份沒有遊戲。")
            else:
                rating_color = {
                    "壓倒性好評": "#4ade80",
                    "極度好評": "#4db366",
                    "大多好評": "#66c0f4",
                    "好評": "#66c0f4",
                    "褒貶不一": "#b9a074",
                    "大多負評": "#c0392b",
                    "負評": "#c0392b",
                    "極度負評": "#8b1a1a",
                    "少量評論": "#888888",
                    "尚無評論": "#888888",
                }
                rows_html = []
                for _, r in month_df.iterrows():
                    appid = str(r.get("appid", "") or "").strip()
                    url = steam_url(appid) if appid else "#"
                    name = str(r.get("name") or "—")
                    img_url = str(r.get("header_image") or "").strip()
                    img_tag = (
                        f'<img src="{img_url}" style="height:48px;width:auto;border-radius:3px;display:block;margin:0 auto;">'
                        if img_url and img_url != "nan"
                        else '<span style="color:#555;font-size:0.75rem;">無圖</span>'
                    )
                    rating = str(r.get("review_score_desc_zh") or "—")
                    r_color = rating_color.get(rating, "#666666")
                    review_count = r.get("review_count")
                    positive_ratio = r.get("positive_ratio")
                    try:
                        if pd.isna(review_count) or int(review_count) == 0:
                            rating_text = rating
                        else:
                            ratio_s = f"{float(positive_ratio) * 100:.1f}%" if pd.notna(positive_ratio) else "—"
                            rating_text = f"{rating} · {int(review_count):,} 則 ({ratio_s})"
                    except (TypeError, ValueError):
                        rating_text = rating
                    price = fmt_twd(r.get("price_twd_original"))
                    date_s = _fmt_date(r.get("release_date"))
                    sales = _fmt_sales(r.get("est_sales_low"))

                    rows_html.append(f"""
                    <tr>
                      <td style="width:76px;text-align:center;padding:6px 8px;vertical-align:middle;">
                        <a href="{url}" target="_blank">{img_tag}</a>
                      </td>
                      <td style="padding:6px 8px;vertical-align:middle;font-size:0.88rem;font-weight:600;line-height:1.4;word-break:break-word;">
                        <a href="{url}" target="_blank" style="color:#e8eaf0;text-decoration:none;"
                           onmouseover="this.style.textDecoration='underline'"
                           onmouseout="this.style.textDecoration='none'">{name}</a>
                      </td>
                      <td style="padding:6px 8px;vertical-align:middle;font-size:0.82rem;color:{r_color};font-weight:600;">{rating_text}</td>
                      <td style="padding:6px 8px;vertical-align:middle;font-size:0.84rem;color:#e8eaf0;white-space:nowrap;">{price}</td>
                      <td style="padding:6px 8px;vertical-align:middle;font-size:0.82rem;color:#aaa;white-space:nowrap;">{date_s}</td>
                      <td style="padding:6px 8px;vertical-align:middle;font-size:0.82rem;color:#e8eaf0;white-space:nowrap;">{sales}</td>
                      <td style="padding:6px 8px;vertical-align:middle;white-space:nowrap;">
                        <a href="{url}" target="_blank"
                           style="display:inline-block;padding:4px 10px;background:#1b2838;color:#c6d4df;
                                  border-radius:4px;text-decoration:none;font-size:0.78rem;">商店頁面</a>
                      </td>
                    </tr>""")

                table_html = _make_sortable_table(rows_html, "month-games-table", [
                    ("縮圖",             "none"),
                    ("名稱",             "text"),
                    ("評論等級 / 評論數", "text"),
                    ("台幣售價",          "num"),
                    ("發售日",            "text"),
                    ("預測銷售",          "num"),
                    ("Steam",            "none"),
                ])
                _d_h = min(520, 80 + 56 * min(len(rows_html), 12))
                _components.html(table_html, height=_d_h, scrolling=True)
            if st.button("關閉", key="close_hm_dialog", use_container_width=True):
                st.session_state["hm_show_dialog"] = False
                st.rerun()

        show_month_games_dialog()

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
monthly_trend["release_year"] = monthly_trend["release_year"].astype(int)
monthly_trend["release_month"] = monthly_trend["release_month"].astype(int)

# Use full month grid so month positions match heatmap exactly.
trend_years = sorted(monthly_trend["release_year"].unique())
trend_full_grid = pd.DataFrame(
    [(y, m) for y in trend_years for m in range(1, 13)],
    columns=["release_year", "release_month"],
)
monthly_trend = trend_full_grid.merge(
    monthly_trend,
    on=["release_year", "release_month"],
    how="left",
)
monthly_trend["count"] = monthly_trend["count"].fillna(0).astype(int)
monthly_trend["year_str"] = monthly_trend["release_year"].astype(str)
monthly_trend["month_label"] = monthly_trend["release_month"].map(month_labels)

line_chart = (
    alt.Chart(monthly_trend)
    .mark_line(point=True)
    .encode(
        x=alt.X(
            "release_month:O",
            title="月份",
            sort=list(range(1, 13)),
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
