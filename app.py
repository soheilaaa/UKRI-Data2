"""
UKRI Sustainability Research Funding Dashboard
For Nature Sustainability paper: mapping UK public R&D investment in sustainability science.
Run: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from collections import Counter
import re
import sys
from pathlib import Path
import networkx as nx

sys.path.insert(0, str(Path(__file__).parent))
from data_processor import get_or_build_dataset, SUSTAINABILITY_THEMES

# ── Page configuration ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="UKRI Sustainability Research Dashboard",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.metric-card {
    background: #f0f7f4;
    border-left: 4px solid #2e7d5e;
    padding: 1rem;
    border-radius: 6px;
    margin-bottom: 0.5rem;
}
.metric-value { font-size: 1.8rem; font-weight: 700; color: #1a5438; }
.metric-label { font-size: 0.85rem; color: #555; }
.section-header {
    font-size: 1.1rem; font-weight: 600; color: #2e7d5e;
    border-bottom: 2px solid #2e7d5e; padding-bottom: 4px; margin-bottom: 1rem;
}
</style>
""", unsafe_allow_html=True)


# ── Download helper ───────────────────────────────────────────────────────────
def _chart(fig, filename):
    """Render a Plotly figure with a 3× PNG download button."""
    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "toImageButtonOptions": {
                "format": "png",
                "filename": filename,
                "scale": 3,
            },
            "displayModeBar": True,
        },
    )

# ── Colour palette ────────────────────────────────────────────────────────────
COUNCIL_COLORS = {
    "EPSRC": "#1f77b4", "MRC": "#d62728", "ESRC": "#ff7f0e",
    "NERC": "#2ca02c", "BBSRC": "#9467bd", "AHRC": "#8c564b",
    "STFC": "#e377c2", "GCRF": "#7f7f7f", "Innovate UK": "#17becf",
    "UKRI": "#bcbd22", "UKRI FLF": "#bcbd22", "ISCF": "#aec7e8",
    "Horizon Europe Guarantee": "#ffbb78", "SPF": "#98df8a",
}
THEME_COLORS = px.colors.qualitative.Set2

# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Loading UKRI project data…")
def load_data():
    return get_or_build_dataset(force_rebuild=False)


df_all = load_data()

# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.image(
        "https://www.ukri.org/wp-content/themes/ukri/assets/images/ukri-logo-transparent.png"
        if False else "",  # no external URL fetch
    ) if False else None
    st.markdown("## 🔍 Filters")

    year_min = int(df_all["start_year"].dropna().min())
    year_max = int(df_all["start_year"].dropna().max())
    year_range = st.slider("Start year range", year_min, year_max, (year_min, year_max))

    all_funders = sorted(df_all["funder"].dropna().unique())
    selected_funders = st.multiselect("Funding councils", all_funders, default=all_funders)

    all_regions = sorted(df_all["region"].dropna().unique())
    selected_regions = st.multiselect("Regions", all_regions, default=all_regions)

    sus_filter = st.radio(
        "Project scope",
        ["All projects", "Sustainability-related only", "Non-sustainability only"],
        index=0,
    )

    st.markdown("---")
    st.markdown("**Data sources**")
    st.markdown("UKRI Gateway to Research API  \nExcel: 1,383 curated projects  \nJSON: 16,128 project records")

# ── Apply filters ─────────────────────────────────────────────────────────────
df = df_all.copy()
df = df[(df["start_year"] >= year_range[0]) & (df["start_year"] <= year_range[1])]
if selected_funders:
    df = df[df["funder"].isin(selected_funders)]
if selected_regions:
    df = df[df["region"].isin(selected_regions)]
if sus_filter == "Sustainability-related only":
    df = df[df["is_sustainability"]]
elif sus_filter == "Non-sustainability only":
    df = df[~df["is_sustainability"]]

# ── Header ────────────────────────────────────────────────────────────────────
st.title("🌿 UKRI Sustainability Research Funding")
st.markdown(
    "**Mapping public R&D investment in sustainability science across the UK (2016–2025)**  \n"
    "Analysis prepared for *Nature Sustainability*"
)
st.markdown("---")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Overview",
    "🗺️ Geographic Distribution",
    "🏛️ Institutions",
    "🌱 Sustainability Themes",
    "🤝 Collaboration Networks",
    "📚 Research Impact",
])

# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 – OVERVIEW
# ═════════════════════════════════════════════════════════════════════════════
with tab1:
    total_projects = len(df)
    total_funding = df["fund_value"].sum()
    sus_projects = df["is_sustainability"].sum()
    sus_funding = df[df["is_sustainability"]]["fund_value"].sum()
    active_projects = (df["status"] == "Active").sum()
    avg_funding = df["fund_value"].mean()
    total_pubs = df["publication_count"].sum()
    avg_collabs = df["collab_count"].mean()

    # KPI row
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Projects", f"{total_projects:,}")
        st.metric("Active Projects", f"{active_projects:,}")
    with c2:
        st.metric("Total Funding", f"£{total_funding/1e9:.2f}B")
        st.metric("Avg. Grant Size", f"£{avg_funding/1e6:.1f}M")
    with c3:
        st.metric("Sustainability Projects", f"{sus_projects:,}")
        st.metric("Sustainability Share", f"{100*sus_projects/max(total_projects,1):.0f}%")
    with c4:
        st.metric("Sustainability Funding", f"£{sus_funding/1e9:.2f}B")
        st.metric("Total Publications", f"{int(total_pubs):,}")

    st.markdown("---")

    col_left, col_right = st.columns([3, 2])

    with col_left:
        # Funding by year stacked by council
        st.markdown('<div class="section-header">Annual UKRI Funding (£B) by Research Council</div>', unsafe_allow_html=True)
        yr_df = (
            df.groupby(["start_year", "funder"])["fund_value"]
            .sum()
            .reset_index()
            .rename(columns={"fund_value": "funding", "start_year": "year", "funder": "council"})
        )
        yr_df["funding_B"] = yr_df["funding"] / 1e9
        fig_yr = px.bar(
            yr_df,
            x="year",
            y="funding_B",
            color="council",
            color_discrete_map=COUNCIL_COLORS,
            labels={"funding_B": "Funding (£B)", "year": "Start Year", "council": "Council"},
            template="plotly_white",
        )
        fig_yr.update_layout(legend_title_text="Council", height=380, margin=dict(t=10))
        _chart(fig_yr, "ukri_annual_funding_by_council")

    with col_right:
        # Council share donut
        st.markdown('<div class="section-header">Funding Share by Council</div>', unsafe_allow_html=True)
        council_df = (
            df.groupby("funder")["fund_value"]
            .sum()
            .reset_index()
            .rename(columns={"fund_value": "funding", "funder": "council"})
            .sort_values("funding", ascending=False)
        )
        fig_donut = px.pie(
            council_df,
            names="council",
            values="funding",
            hole=0.45,
            color="council",
            color_discrete_map=COUNCIL_COLORS,
            template="plotly_white",
        )
        fig_donut.update_traces(textposition="inside", textinfo="percent+label")
        fig_donut.update_layout(showlegend=False, height=380, margin=dict(t=10))
        _chart(fig_donut, "ukri_funding_share_by_council")

    col_a, col_b = st.columns(2)

    with col_a:
        # Sustainability vs non-sustainability funding over time
        st.markdown('<div class="section-header">Sustainability Funding Trend</div>', unsafe_allow_html=True)
        sus_yr = (
            df.groupby(["start_year", "is_sustainability"])["fund_value"]
            .sum()
            .reset_index()
        )
        sus_yr["type"] = sus_yr["is_sustainability"].map({True: "Sustainability", False: "Other UKRI"})
        sus_yr["funding_M"] = sus_yr["fund_value"] / 1e6
        fig_sus_trend = px.area(
            sus_yr,
            x="start_year",
            y="funding_M",
            color="type",
            color_discrete_map={"Sustainability": "#2ca02c", "Other UKRI": "#aec7e8"},
            labels={"funding_M": "Funding (£M)", "start_year": "Start Year", "type": "Category"},
            template="plotly_white",
        )
        fig_sus_trend.update_layout(height=320, margin=dict(t=10), legend_title_text="")
        _chart(fig_sus_trend, "ukri_sustainability_funding_trend")

    with col_b:
        # Project count by year and status
        st.markdown('<div class="section-header">Project Count by Year & Status</div>', unsafe_allow_html=True)
        cnt_df = (
            df.groupby(["start_year", "status"])
            .size()
            .reset_index(name="count")
        )
        fig_cnt = px.bar(
            cnt_df,
            x="start_year",
            y="count",
            color="status",
            color_discrete_map={"Active": "#2ca02c", "Closed": "#888"},
            labels={"count": "Projects", "start_year": "Start Year", "status": "Status"},
            template="plotly_white",
            barmode="stack",
        )
        fig_cnt.update_layout(height=320, margin=dict(t=10), legend_title_text="")
        _chart(fig_cnt, "ukri_project_count_by_year")

    # Grant size distribution
    st.markdown('<div class="section-header">Grant Size Distribution by Council</div>', unsafe_allow_html=True)
    box_df = df[df["fund_value"].notna() & (df["fund_value"] > 0)].copy()
    box_df["funding_M"] = box_df["fund_value"] / 1e6
    fig_box = px.box(
        box_df,
        x="funder",
        y="funding_M",
        color="funder",
        color_discrete_map=COUNCIL_COLORS,
        points=False,
        labels={"funding_M": "Grant Size (£M)", "funder": "Council"},
        template="plotly_white",
        log_y=True,
    )
    fig_box.update_layout(showlegend=False, height=340, margin=dict(t=10))
    _chart(fig_box, "ukri_grant_size_by_council")


# ═════════════════════════════════════════════════════════════════════════════
# TAB 2 – GEOGRAPHIC DISTRIBUTION
# ═════════════════════════════════════════════════════════════════════════════
with tab2:
    col_l, col_r = st.columns([3, 2])

    with col_l:
        st.markdown('<div class="section-header">Total Funding by UK Region (£M)</div>', unsafe_allow_html=True)
        reg_df = (
            df.groupby("region")
            .agg(
                funding=("fund_value", "sum"),
                projects=("project_ref", "count"),
                sus_projects=("is_sustainability", "sum"),
            )
            .reset_index()
            .sort_values("funding", ascending=True)
        )
        reg_df["funding_M"] = reg_df["funding"] / 1e6
        reg_df["sus_pct"] = (100 * reg_df["sus_projects"] / reg_df["projects"]).round(1)

        fig_reg = go.Figure()
        fig_reg.add_trace(go.Bar(
            y=reg_df["region"],
            x=reg_df["funding_M"],
            orientation="h",
            marker_color="#1f77b4",
            name="Total Funding",
            text=[f"£{v:.0f}M" for v in reg_df["funding_M"]],
            textposition="outside",
        ))
        fig_reg.update_layout(
            xaxis_title="Funding (£M)",
            yaxis_title="",
            template="plotly_white",
            height=500,
            margin=dict(t=10, r=80),
        )
        _chart(fig_reg, "ukri_funding_by_region")

    with col_r:
        st.markdown('<div class="section-header">Projects by Region</div>', unsafe_allow_html=True)
        fig_reg_cnt = px.bar(
            reg_df.sort_values("projects"),
            y="region",
            x="projects",
            orientation="h",
            color="sus_pct",
            color_continuous_scale="Greens",
            labels={"projects": "Projects", "region": "", "sus_pct": "% Sustainability"},
            template="plotly_white",
        )
        fig_reg_cnt.update_layout(height=500, margin=dict(t=10), coloraxis_colorbar_title="% Sust.")
        _chart(fig_reg_cnt, "ukri_projects_by_region")

    # Nation-level summary
    st.markdown('<div class="section-header">Funding by UK Nation</div>', unsafe_allow_html=True)
    nation_df = (
        df.groupby("nation")
        .agg(funding=("fund_value", "sum"), projects=("project_ref", "count"))
        .reset_index()
    )
    sus_nation = (
        df[df["is_sustainability"]].groupby("nation")["fund_value"]
        .sum()
        .reset_index()
        .rename(columns={"fund_value": "sus_funding"})
    )
    nation_df = nation_df.merge(sus_nation, on="nation", how="left").fillna(0)
    nation_df["funding_M"] = nation_df["funding"] / 1e6
    nation_df["sus_M"] = nation_df["sus_funding"] / 1e6
    nation_df["other_M"] = nation_df["funding_M"] - nation_df["sus_M"]

    fig_nation = go.Figure()
    fig_nation.add_trace(go.Bar(
        name="Sustainability",
        x=nation_df["nation"],
        y=nation_df["sus_M"],
        marker_color="#2ca02c",
    ))
    fig_nation.add_trace(go.Bar(
        name="Other UKRI",
        x=nation_df["nation"],
        y=nation_df["other_M"],
        marker_color="#aec7e8",
    ))
    fig_nation.update_layout(
        barmode="stack",
        yaxis_title="Funding (£M)",
        template="plotly_white",
        height=340,
        margin=dict(t=10),
        legend_title_text="",
    )
    _chart(fig_nation, "ukri_funding_by_nation")

    # Regional funding over time heatmap
    st.markdown('<div class="section-header">Regional Funding Over Time (£M) – Heatmap</div>', unsafe_allow_html=True)
    heat_df = (
        df.groupby(["region", "start_year"])["fund_value"]
        .sum()
        .reset_index()
    )
    heat_pivot = heat_df.pivot(index="region", columns="start_year", values="fund_value").fillna(0) / 1e6

    fig_heat = px.imshow(
        heat_pivot,
        aspect="auto",
        color_continuous_scale="YlGn",
        labels=dict(color="£M"),
        template="plotly_white",
    )
    fig_heat.update_layout(height=400, margin=dict(t=10))
    _chart(fig_heat, "ukri_regional_funding_heatmap")


# ═════════════════════════════════════════════════════════════════════════════
# TAB 3 – INSTITUTIONS
# ═════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown('<div class="section-header">Top 20 Institutions by Total Funding</div>', unsafe_allow_html=True)

    inst_df = (
        df.groupby("institution")
        .agg(
            funding=("fund_value", "sum"),
            projects=("project_ref", "count"),
            sus_projects=("is_sustainability", "sum"),
            avg_funding=("fund_value", "mean"),
            total_pubs=("publication_count", "sum"),
            avg_collabs=("collab_count", "mean"),
        )
        .reset_index()
        .sort_values("funding", ascending=False)
    )
    inst_df["funding_M"] = inst_df["funding"] / 1e6
    inst_df["avg_funding_M"] = inst_df["avg_funding"] / 1e6
    inst_df["sus_pct"] = (100 * inst_df["sus_projects"] / inst_df["projects"]).round(1)
    top20 = inst_df.head(20).sort_values("funding_M")

    fig_inst = go.Figure()
    fig_inst.add_trace(go.Bar(
        y=top20["institution"],
        x=top20["funding_M"],
        orientation="h",
        marker=dict(
            color=top20["sus_pct"],
            colorscale="Greens",
            colorbar=dict(title="% Sustainability"),
        ),
        text=[f"£{v:.0f}M" for v in top20["funding_M"]],
        textposition="outside",
    ))
    fig_inst.update_layout(
        xaxis_title="Total Funding (£M)",
        yaxis_title="",
        template="plotly_white",
        height=560,
        margin=dict(t=10, r=80),
    )
    _chart(fig_inst, "ukri_top_institutions_funding")

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown('<div class="section-header">Institution: Funding vs. Projects vs. Publications</div>', unsafe_allow_html=True)
        top50 = inst_df[inst_df["projects"] >= 3].head(50)
        fig_bubble = px.scatter(
            top50,
            x="projects",
            y="funding_M",
            size="total_pubs",
            color="sus_pct",
            color_continuous_scale="Greens",
            hover_name="institution",
            labels={
                "projects": "Number of Projects",
                "funding_M": "Total Funding (£M)",
                "total_pubs": "Publications",
                "sus_pct": "% Sustainability",
            },
            template="plotly_white",
            size_max=40,
        )
        fig_bubble.update_layout(height=420, margin=dict(t=10))
        _chart(fig_bubble, "ukri_institution_funding_vs_projects")

    with col_b:
        st.markdown('<div class="section-header">Department-Level Funding (Top 15)</div>', unsafe_allow_html=True)
        dept_df = (
            df[df["department"].notna() & (df["department"].str.upper() != "UNLISTED")]
            .groupby("department")["fund_value"]
            .sum()
            .reset_index()
            .sort_values("fund_value", ascending=False)
            .head(15)
        )
        dept_df["funding_M"] = dept_df["fund_value"] / 1e6
        fig_dept = px.bar(
            dept_df.sort_values("funding_M"),
            y="department",
            x="funding_M",
            orientation="h",
            color="funding_M",
            color_continuous_scale="Blues",
            labels={"funding_M": "Funding (£M)", "department": ""},
            template="plotly_white",
        )
        fig_dept.update_layout(showlegend=False, height=420, margin=dict(t=10), coloraxis_showscale=False)
        _chart(fig_dept, "ukri_department_funding")

    # Institution × Council heatmap
    st.markdown('<div class="section-header">Institution × Funding Council Matrix (£M)</div>', unsafe_allow_html=True)
    inst_council = (
        df.groupby(["institution", "funder"])["fund_value"]
        .sum()
        .reset_index()
    )
    top15_inst = inst_df.head(15)["institution"].tolist()
    ic_pivot = (
        inst_council[inst_council["institution"].isin(top15_inst)]
        .pivot(index="institution", columns="funder", values="fund_value")
        .fillna(0)
    ) / 1e6

    fig_ic = px.imshow(
        ic_pivot,
        aspect="auto",
        color_continuous_scale="Blues",
        labels=dict(color="£M"),
        template="plotly_white",
        text_auto=".0f",
    )
    fig_ic.update_layout(height=420, margin=dict(t=10))
    _chart(fig_ic, "ukri_institution_council_matrix")


# ═════════════════════════════════════════════════════════════════════════════
# TAB 4 – SUSTAINABILITY THEMES
# ═════════════════════════════════════════════════════════════════════════════
with tab4:
    sus_df = df[df["is_sustainability"]].copy()

    st.markdown(
        f"**{len(sus_df):,}** of **{len(df):,}** projects ({100*len(sus_df)/max(len(df),1):.1f}%) "
        "classified as sustainability-related via keyword analysis of titles and abstracts."
    )

    col_a, col_b = st.columns(2)

    with col_a:
        # Theme distribution
        st.markdown('<div class="section-header">Projects per Sustainability Theme</div>', unsafe_allow_html=True)
        theme_counts = {}
        theme_funding = {}
        for theme in SUSTAINABILITY_THEMES:
            col_key = "theme_" + theme.lower().replace(" ", "_").replace("&", "and")
            if col_key in df.columns:
                mask = df[col_key]
                theme_counts[theme] = mask.sum()
                theme_funding[theme] = df.loc[mask, "fund_value"].sum()

        th_df = pd.DataFrame({
            "theme": list(theme_counts.keys()),
            "projects": list(theme_counts.values()),
            "funding_M": [v / 1e6 for v in theme_funding.values()],
        }).sort_values("projects", ascending=True)

        fig_themes = px.bar(
            th_df,
            y="theme",
            x="projects",
            orientation="h",
            color="funding_M",
            color_continuous_scale="Greens",
            labels={"projects": "Projects", "theme": "", "funding_M": "Funding (£M)"},
            template="plotly_white",
        )
        fig_themes.update_layout(height=400, margin=dict(t=10), coloraxis_colorbar_title="£M")
        _chart(fig_themes, "ukri_sustainability_projects_by_theme")

    with col_b:
        # Theme funding donut
        st.markdown('<div class="section-header">Sustainability Funding by Theme (£M)</div>', unsafe_allow_html=True)
        fig_th_pie = px.pie(
            th_df.sort_values("funding_M", ascending=False),
            names="theme",
            values="funding_M",
            hole=0.4,
            color_discrete_sequence=THEME_COLORS,
            template="plotly_white",
        )
        fig_th_pie.update_traces(textposition="inside", textinfo="percent+label")
        fig_th_pie.update_layout(showlegend=False, height=400, margin=dict(t=10))
        _chart(fig_th_pie, "ukri_sustainability_funding_by_theme")

    # Theme evolution over time
    st.markdown('<div class="section-header">Sustainability Theme Evolution (Projects per Year)</div>', unsafe_allow_html=True)
    theme_yr_rows = []
    for theme in SUSTAINABILITY_THEMES:
        col_key = "theme_" + theme.lower().replace(" ", "_").replace("&", "and")
        if col_key in df.columns:
            sub = df[df[col_key]].groupby("start_year").size().reset_index(name="count")
            sub["theme"] = theme
            theme_yr_rows.append(sub)
    if theme_yr_rows:
        theme_yr_df = pd.concat(theme_yr_rows)
        fig_th_yr = px.line(
            theme_yr_df,
            x="start_year",
            y="count",
            color="theme",
            color_discrete_sequence=THEME_COLORS,
            markers=True,
            labels={"count": "Projects", "start_year": "Start Year", "theme": "Theme"},
            template="plotly_white",
        )
        fig_th_yr.update_layout(height=380, margin=dict(t=10), legend_title_text="")
        _chart(fig_th_yr, "ukri_theme_evolution_over_time")

    # Theme by council heatmap
    st.markdown('<div class="section-header">Sustainability Theme × Funding Council (Project Count)</div>', unsafe_allow_html=True)
    th_council_rows = []
    for theme in SUSTAINABILITY_THEMES:
        col_key = "theme_" + theme.lower().replace(" ", "_").replace("&", "and")
        if col_key in df.columns:
            sub = df[df[col_key]].groupby("funder").size().reset_index(name="count")
            sub["theme"] = theme
            th_council_rows.append(sub)
    if th_council_rows:
        tc_df = pd.concat(th_council_rows)
        tc_pivot = tc_df.pivot(index="theme", columns="funder", values="count").fillna(0)
        fig_tc = px.imshow(
            tc_pivot,
            aspect="auto",
            color_continuous_scale="YlGn",
            labels=dict(color="Projects"),
            template="plotly_white",
            text_auto="d",
        )
        fig_tc.update_layout(height=380, margin=dict(t=10))
        _chart(fig_tc, "ukri_theme_council_heatmap")

    # Theme × region
    st.markdown('<div class="section-header">Sustainability Theme × Region (Project Count)</div>', unsafe_allow_html=True)
    th_reg_rows = []
    for theme in SUSTAINABILITY_THEMES:
        col_key = "theme_" + theme.lower().replace(" ", "_").replace("&", "and")
        if col_key in df.columns:
            sub = df[df[col_key]].groupby("region").size().reset_index(name="count")
            sub["theme"] = theme
            th_reg_rows.append(sub)
    if th_reg_rows:
        tr_df = pd.concat(th_reg_rows)
        tr_pivot = tr_df.pivot(index="theme", columns="region", values="count").fillna(0)
        fig_tr = px.imshow(
            tr_pivot,
            aspect="auto",
            color_continuous_scale="Greens",
            labels=dict(color="Projects"),
            template="plotly_white",
            text_auto="d",
        )
        fig_tr.update_layout(height=380, margin=dict(t=10))
        _chart(fig_tr, "ukri_theme_region_heatmap")

    # Research topics word frequency
    st.markdown('<div class="section-header">Most Frequent Research Topics in Sustainability Projects</div>', unsafe_allow_html=True)
    topics_text = " ".join(sus_df["research_topics"].fillna("").tolist())
    topic_list = [t.strip() for t in topics_text.split(";") if t.strip() and t.strip() != "Unclassified"]
    topic_counts = Counter(topic_list).most_common(25)
    if topic_counts:
        td_df = pd.DataFrame(topic_counts, columns=["topic", "count"]).sort_values("count")
        fig_topics = px.bar(
            td_df,
            y="topic",
            x="count",
            orientation="h",
            color="count",
            color_continuous_scale="Greens",
            labels={"count": "Occurrences", "topic": ""},
            template="plotly_white",
        )
        fig_topics.update_layout(showlegend=False, height=500, margin=dict(t=10), coloraxis_showscale=False)
        _chart(fig_topics, "ukri_research_topics_frequency")
    else:
        st.info("Research topic metadata not available in this filtered dataset.")


# ═════════════════════════════════════════════════════════════════════════════
# TAB 5 – COLLABORATION NETWORKS
# ═════════════════════════════════════════════════════════════════════════════
with tab5:
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown('<div class="section-header">Collaboration Size Distribution</div>', unsafe_allow_html=True)
        collab_df = df[df["collab_count"] > 0].copy()
        fig_collab_hist = px.histogram(
            collab_df,
            x="collab_count",
            nbins=40,
            color_discrete_sequence=["#17becf"],
            labels={"collab_count": "Number of Partner Organisations", "count": "Projects"},
            template="plotly_white",
        )
        fig_collab_hist.update_layout(height=360, margin=dict(t=10), yaxis_title="Projects")
        _chart(fig_collab_hist, "ukri_collaboration_size_distribution")

    with col_b:
        st.markdown('<div class="section-header">Collaboration Size by Funding Council (Box Plot)</div>', unsafe_allow_html=True)
        fig_collab_box = px.box(
            df[df["collab_count"] > 0],
            x="funder",
            y="collab_count",
            color="funder",
            color_discrete_map=COUNCIL_COLORS,
            points=False,
            labels={"collab_count": "Partner Organisations", "funder": "Council"},
            template="plotly_white",
        )
        fig_collab_box.update_layout(showlegend=False, height=360, margin=dict(t=10))
        _chart(fig_collab_box, "ukri_collaboration_size_by_council")

    # Average collaboration by region
    st.markdown('<div class="section-header">Average Collaboration Size by Region & Sustainability Status</div>', unsafe_allow_html=True)
    collab_reg = (
        df.groupby(["region", "is_sustainability"])["collab_count"]
        .mean()
        .reset_index()
    )
    collab_reg["type"] = collab_reg["is_sustainability"].map({True: "Sustainability", False: "Other"})
    fig_collab_reg = px.bar(
        collab_reg,
        x="region",
        y="collab_count",
        color="type",
        barmode="group",
        color_discrete_map={"Sustainability": "#2ca02c", "Other": "#aec7e8"},
        labels={"collab_count": "Avg. Partner Organisations", "region": "Region", "type": ""},
        template="plotly_white",
    )
    fig_collab_reg.update_xaxes(tickangle=30)
    fig_collab_reg.update_layout(height=360, margin=dict(t=10, b=80), legend_title_text="")
    _chart(fig_collab_reg, "ukri_collaboration_by_region")

    # Collaboration vs funding scatter
    st.markdown('<div class="section-header">Collaboration Size vs. Grant Value</div>', unsafe_allow_html=True)
    scat_df = df[(df["collab_count"] > 0) & df["fund_value"].notna()].copy()
    scat_df["funding_M"] = scat_df["fund_value"] / 1e6
    fig_scat = px.scatter(
        scat_df,
        x="collab_count",
        y="funding_M",
        color="funder",
        color_discrete_map=COUNCIL_COLORS,
        opacity=0.6,
        hover_name="title",
        hover_data={"collab_count": True, "funding_M": ":.1f", "funder": True},
        labels={
            "collab_count": "Number of Collaborating Organisations",
            "funding_M": "Grant Size (£M)",
            "funder": "Council",
        },
        template="plotly_white",
        trendline="ols",
        trendline_scope="overall",
        trendline_color_override="red",
    )
    fig_scat.update_layout(height=420, margin=dict(t=10))
    _chart(fig_scat, "ukri_collaboration_vs_grant_size")

    # Top most collaborative institutions
    st.markdown('<div class="section-header">Top 20 Most Collaborative Lead Institutions (Avg. Partners)</div>', unsafe_allow_html=True)
    inst_collab = (
        df[df["collab_count"] > 0]
        .groupby("institution")
        .agg(avg_collab=("collab_count", "mean"), projects=("project_ref", "count"))
        .reset_index()
        .query("projects >= 3")
        .sort_values("avg_collab", ascending=False)
        .head(20)
        .sort_values("avg_collab")
    )
    fig_inst_collab = px.bar(
        inst_collab,
        y="institution",
        x="avg_collab",
        orientation="h",
        color="projects",
        color_continuous_scale="Blues",
        labels={"avg_collab": "Avg. Partner Organisations", "institution": "", "projects": "Projects"},
        template="plotly_white",
    )
    fig_inst_collab.update_layout(height=500, margin=dict(t=10), coloraxis_colorbar_title="Projects")
    _chart(fig_inst_collab, "ukri_top_collaborative_institutions")

    # ── Network graphs ────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Network Graphs")

    # ── Graph 1: Institution Co-Collaboration Network (static, paper-quality) ─
    st.markdown('<div class="section-header">Institution Co-Collaboration Network (Top 35 Hubs)</div>', unsafe_allow_html=True)
    st.caption(
        "Node size ∝ number of distinct partner organisations. "
        "Colour = research community (greedy modularity). "
        "Edge thickness ∝ shared projects. "
        "Use the **📷 camera** button (top-right) to download a high-resolution PNG for publication."
    )

    COMMUNITY_COLORS = [
        "#1f77b4", "#d62728", "#2ca02c", "#ff7f0e", "#9467bd",
        "#8c564b", "#e377c2", "#17becf", "#bcbd22", "#aec7e8",
    ]

    @st.cache_data(show_spinner="Building collaboration network…")
    def build_collab_network(data_key, top_n=35, min_edge_weight=3):
        from data_processor import get_or_build_dataset as _load
        _df = _load()

        G_full = nx.Graph()
        inst_region = {}
        for _, row in _df.iterrows():
            lead = str(row["institution"]).strip().lower()
            inst_region[lead] = str(row.get("region") or "Unknown")
            orgs_raw = str(row.get("corrected_additional_orgs", "") or "")
            if not orgs_raw or orgs_raw == "nan":
                continue
            for org in orgs_raw.split(";"):
                org = org.strip().lower()
                if org and org != lead:
                    if G_full.has_edge(lead, org):
                        G_full[lead][org]["weight"] += 1
                    else:
                        G_full.add_edge(lead, org, weight=1)

        for node in G_full.nodes():
            G_full.nodes[node]["region"] = inst_region.get(node, "Unknown")

        degree_map = dict(G_full.degree())
        top_nodes = sorted(degree_map, key=lambda x: -degree_map[x])[:top_n]
        sub = G_full.subgraph(top_nodes).copy()

        edges_to_remove = [(u, v) for u, v, d in sub.edges(data=True) if d["weight"] < min_edge_weight]
        sub.remove_edges_from(edges_to_remove)
        sub.remove_nodes_from(list(nx.isolates(sub)))

        communities = list(nx.algorithms.community.greedy_modularity_communities(sub))
        community_map = {}
        for i, comm in enumerate(communities):
            for node in comm:
                community_map[node] = i

        return sub, community_map

    G_collab, community_map = build_collab_network("collab_v3", top_n=22, min_edge_weight=3)

    @st.cache_data(show_spinner="Rendering network figure…")
    def render_collab_matplotlib(_G, _community_map):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        from matplotlib.lines import Line2D
        import io

        # ── Palette (colourblind-friendly, high contrast) ─────────────────────
        PALETTE = ["#2166ac", "#d6604d", "#4dac26", "#8073ac", "#f1a340", "#01665e"]

        # ── Institution name abbreviations ───────────────────────────────────
        ABBREV = {
            "university college london": "UCL",
            "king's college london": "King's College London",
            "imperial college london": "Imperial College London",
            "manchester academy": "Univ. Manchester",
            "heriot-watt university f.c.": "Heriot-Watt Univ.",
            "columbia university": "Columbia Univ.",
        }

        def short_name(raw):
            low = raw.lower()
            if low in ABBREV:
                return ABBREV[low]
            for prefix in ("the university of ", "university of ", "university college "):
                if low.startswith(prefix):
                    return raw[len(prefix):].title()
            return raw.title().replace("University", "Univ.")

        degree_map = dict(_G.degree())
        max_deg = max(degree_map.values(), default=1)
        sorted_degs = sorted(degree_map.values(), reverse=True)
        top5_threshold = sorted_degs[min(4, len(sorted_degs) - 1)]

        # ── Community-aware layout: centres on equilateral triangle ──────────
        communities = {}
        for node, cid in _community_map.items():
            communities.setdefault(cid, []).append(node)

        n_comm = len(communities)
        CLUSTER_R = 1.5          # radius of triangle
        INNER_R_BASE = 0.42      # radius within each cluster

        comm_centers = {}
        for i, cid in enumerate(sorted(communities.keys())):
            angle = -np.pi / 2 + 2 * np.pi * i / n_comm  # top vertex first
            comm_centers[cid] = (CLUSTER_R * np.cos(angle), CLUSTER_R * np.sin(angle))

        pos = {}
        for cid, members in communities.items():
            cx_c, cy_c = comm_centers[cid]
            ordered = sorted(members, key=lambda n: -degree_map.get(n, 0))
            n = len(ordered)
            inner_r = INNER_R_BASE + 0.05 * n
            # Most-connected node at the community centre
            pos[ordered[0]] = (cx_c, cy_c)
            for j, node in enumerate(ordered[1:]):
                a = 2 * np.pi * j / (n - 1) if n > 2 else np.pi * j
                pos[node] = (cx_c + inner_r * np.cos(a), cy_c + inner_r * np.sin(a))

        # Post-process: push overlapping nodes apart
        pa = {n: list(p) for n, p in pos.items()}
        nl = list(pa)
        for _ in range(80):
            for i in range(len(nl)):
                for j in range(i + 1, len(nl)):
                    a, b = nl[i], nl[j]
                    dx = pa[b][0] - pa[a][0]
                    dy = pa[b][1] - pa[a][1]
                    d = max((dx ** 2 + dy ** 2) ** 0.5, 1e-6)
                    if d < 0.22:
                        push = (0.22 - d) / 2
                        ux, uy = dx / d, dy / d
                        pa[a][0] -= push * ux; pa[a][1] -= push * uy
                        pa[b][0] += push * ux; pa[b][1] += push * uy
        pos = {n: tuple(p) for n, p in pa.items()}

        max_w = max((d["weight"] for _, _, d in _G.edges(data=True)), default=1)

        # ── Figure ────────────────────────────────────────────────────────────
        fig, ax = plt.subplots(figsize=(14, 11))
        fig.patch.set_facecolor("#ffffff")
        ax.set_facecolor("#f7f9f8")
        ax.set_aspect("equal")
        ax.axis("off")

        # ── Edges ─────────────────────────────────────────────────────────────
        for u, v, data in sorted(_G.edges(data=True), key=lambda e: e[2].get("weight", 1)):
            x0, y0 = pos[u]
            x1, y1 = pos[v]
            cu = _community_map.get(u, 0)
            cv = _community_map.get(v, 0)
            w = data["weight"]
            lw = 0.5 + 3.5 * (w / max_w)
            if cu == cv:
                color = PALETTE[cu % len(PALETTE)]
                alpha = 0.18 + 0.32 * (w / max_w)
            else:
                color = "#999999"
                alpha = 0.10 + 0.12 * (w / max_w)
            ax.plot([x0, x1], [y0, y1], "-",
                    color=color, lw=lw, alpha=alpha,
                    zorder=1, solid_capstyle="round")

        # ── Cluster halos (soft background per community) ──────────────────
        for cid, (cx_c, cy_c) in comm_centers.items():
            color = PALETTE[cid % len(PALETTE)]
            halo = plt.Circle((cx_c, cy_c), INNER_R_BASE + 0.28,
                               color=color, alpha=0.06, zorder=0, linewidth=0)
            ax.add_patch(halo)

        # ── Nodes ─────────────────────────────────────────────────────────────
        for node in _G.nodes():
            x, y = pos[node]
            deg = degree_map.get(node, 1)
            cid = _community_map.get(node, 0)
            color = PALETTE[cid % len(PALETTE)]
            size = 180 + 820 * (deg / max_deg)
            ax.scatter([x], [y], s=size, c=color, zorder=3,
                       edgecolors="white", linewidths=2.8, alpha=0.94)

        # ── Labels ────────────────────────────────────────────────────────────
        for node in _G.nodes():
            x, y = pos[node]
            deg = degree_map.get(node, 1)
            cid = _community_map.get(node, 0)
            cx_c, cy_c = comm_centers[cid]
            dx, dy = x - cx_c, y - cy_c
            d = max((dx ** 2 + dy ** 2) ** 0.5, 1e-4)
            offset = 0.30 + 0.10 * (deg / max_deg)
            lx = x + offset * dx / d
            ly = y + offset * dy / d

            label = short_name(node)
            bold = deg >= top5_threshold
            ax.text(
                lx, ly, label,
                fontsize=16, fontweight="bold" if bold else "normal",
                ha="center", va="center", zorder=5,
                bbox=dict(
                    boxstyle="round,pad=0.28",
                    facecolor="white",
                    edgecolor="#c0c0c0",
                    alpha=0.90,
                    linewidth=0.6,
                ),
            )

        # ── Legend ────────────────────────────────────────────────────────────
        comm_members_m = {}
        for node, cid in _community_map.items():
            comm_members_m.setdefault(cid, []).append(node)

        legend_elems = []
        for cid in sorted(comm_members_m.keys()):
            color = PALETTE[cid % len(PALETTE)]
            n_m = len(comm_members_m[cid])
            legend_elems.append(
                mpatches.Patch(facecolor=color, alpha=0.85, edgecolor="white",
                               linewidth=1.5,
                               label=f"Community {cid + 1}  ({n_m} institutions)")
            )

        # Node size reference
        for ref_deg, ref_label in [
            (int(max_deg * 0.35), "Moderate connectivity"),
            (max_deg, "High connectivity"),
        ]:
            ms = np.sqrt((180 + 820 * (ref_deg / max_deg)) / np.pi) * 0.55
            legend_elems.append(
                Line2D([0], [0], marker="o", color="w",
                       markerfacecolor="#888", markeredgecolor="white",
                       markeredgewidth=1.5, markersize=ms,
                       label=ref_label)
            )

        ax.legend(
            handles=legend_elems,
            loc="lower left",
            framealpha=0.93,
            fontsize=15,
            title="Research communities",
            title_fontsize=16,
            edgecolor="#dddddd",
            borderpad=0.9,
            labelspacing=0.55,
        )

        # ── Caption ───────────────────────────────────────────────────────────
        ax.text(
            0.5, 0.01,
            "Node size ∝ partner organisations  ·  "
            "Edge width ∝ shared projects  ·  "
            "Coloured edges = intra-community  ·  Grey edges = inter-community",
            transform=ax.transAxes,
            ha="center", va="bottom", fontsize=13, color="#666",
        )

        plt.tight_layout(pad=0.4)

        buf_png = io.BytesIO()
        fig.savefig(buf_png, format="png", dpi=300, bbox_inches="tight",
                    facecolor="white")
        buf_png.seek(0)
        buf_svg = io.BytesIO()
        fig.savefig(buf_svg, format="svg", bbox_inches="tight", facecolor="white")
        buf_svg.seek(0)
        plt.close(fig)
        return buf_png.getvalue(), buf_svg.getvalue()

    png_bytes, svg_bytes = render_collab_matplotlib(G_collab, community_map)
    st.image(png_bytes, use_container_width=True)

    dl_col1, dl_col2 = st.columns(2)
    with dl_col1:
        st.download_button(
            "📥 Download PNG (300 DPI)",
            data=png_bytes,
            file_name="ukri_institution_collaboration_network.png",
            mime="image/png",
        )
    with dl_col2:
        st.download_button(
            "📥 Download SVG (vector)",
            data=svg_bytes,
            file_name="ukri_institution_collaboration_network.svg",
            mime="image/svg+xml",
        )

    # Community membership summary
    comm_members: dict[int, list[str]] = {}
    for node, cid in community_map.items():
        comm_members.setdefault(cid, []).append(node.title())
    legend_cols = st.columns(min(len(comm_members), 5))
    for cid, members in sorted(comm_members.items()):
        with legend_cols[cid % len(legend_cols)]:
            color = COMMUNITY_COLORS[cid % len(COMMUNITY_COLORS)]
            preview = ", ".join(sorted(members)[:3]) + ("…" if len(members) > 3 else "")
            st.markdown(
                f'<span style="background:{color};padding:2px 8px;border-radius:3px;'
                f'color:#fff;font-size:0.78rem"><b>Community {cid + 1}</b></span> '
                f'<span style="font-size:0.8rem">{preview}</span>',
                unsafe_allow_html=True,
            )

    # ── Graph 2: Sustainability Theme Co-occurrence Network ───────────────────
    st.markdown('<div class="section-header">Sustainability Theme Co-occurrence Network</div>', unsafe_allow_html=True)
    st.caption(
        "Nodes = sustainability research themes. "
        "Edge width ∝ number of projects where both themes appear together. "
        "Node size ∝ total projects classified under that theme."
    )

    @st.cache_data(show_spinner="Building theme network…")
    def build_theme_network(_df_themes_col, _df_sus_themes_col):
        theme_list = list(SUSTAINABILITY_THEMES.keys())
        G_t = nx.Graph()
        for theme in theme_list:
            G_t.add_node(theme)
        for themes_str in _df_sus_themes_col:
            themes = [t.strip() for t in str(themes_str).split(";") if t.strip()]
            for i in range(len(themes)):
                for j in range(i + 1, len(themes)):
                    u, v = themes[i], themes[j]
                    if u in G_t and v in G_t:
                        if G_t.has_edge(u, v):
                            G_t[u][v]["weight"] += 1
                        else:
                            G_t.add_edge(u, v, weight=1)
        # Node attribute: total projects
        for theme, col_key in zip(
            theme_list,
            [f"theme_{t.lower().replace(' ','_').replace('&','and')}" for t in theme_list],
        ):
            G_t.nodes[theme]["count"] = int(_df_themes_col.get(col_key, pd.Series([False])).sum())
        return G_t

    theme_col_series = {
        col: df_all[col] for col in df_all.columns if col.startswith("theme_") and col != "theme_count"
    }
    G_theme = build_theme_network(theme_col_series, df_all["sustainability_themes"])

    pos_theme = nx.circular_layout(G_theme)
    theme_counts = [G_theme.nodes[n].get("count", 10) for n in G_theme.nodes()]
    theme_sizes = [12 + tc * 0.3 for tc in theme_counts]
    theme_labels = [n for n in G_theme.nodes()]

    # Build a wider single edge trace with variable width by drawing edges individually
    theme_edge_traces = []
    max_w = max((d["weight"] for _, _, d in G_theme.edges(data=True)), default=1)
    for u, v, data in G_theme.edges(data=True):
        x0, y0 = pos_theme[u]
        x1, y1 = pos_theme[v]
        w = data["weight"]
        alpha = 0.3 + 0.6 * (w / max_w)
        theme_edge_traces.append(go.Scatter(
            x=[x0, x1, None], y=[y0, y1, None],
            mode="lines",
            line=dict(width=1.5 + 8 * (w / max_w), color=f"rgba(44,160,44,{alpha:.2f})"),
            hovertext=f"{u} ↔ {v}: {w} projects",
            hoverinfo="text",
            showlegend=False,
        ))

    theme_node_trace = go.Scatter(
        x=[pos_theme[n][0] for n in G_theme.nodes()],
        y=[pos_theme[n][1] for n in G_theme.nodes()],
        mode="markers+text",
        text=theme_labels,
        textposition="top center",
        textfont=dict(size=11, color="#1a5438"),
        hovertext=[
            f"<b>{n}</b><br>Projects: {G_theme.nodes[n].get('count', 0)}<br>Connections: {G_theme.degree(n)}"
            for n in G_theme.nodes()
        ],
        hoverinfo="text",
        marker=dict(
            size=theme_sizes,
            color=theme_counts,
            colorscale="Greens",
            showscale=True,
            colorbar=dict(title="Projects", thickness=12),
            line=dict(width=1.5, color="white"),
        ),
        showlegend=False,
    )

    fig_theme_net = go.Figure(data=theme_edge_traces + [theme_node_trace])
    fig_theme_net.update_layout(
        title=dict(text="Sustainability Theme Co-occurrence Network", font=dict(size=14)),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        template="plotly_white",
        height=560,
        margin=dict(t=40, b=10, l=10, r=10),
        plot_bgcolor="rgba(248,252,250,1)",
    )
    _chart(fig_theme_net, "ukri_theme_cooccurrence_network")

    # ── Graph 3: Funder–Institution Bipartite Network ─────────────────────────
    st.markdown('<div class="section-header">Funder–Institution Bipartite Network</div>', unsafe_allow_html=True)
    st.caption(
        "Left = funding councils (sorted by project count). "
        "Right = top 20 lead institutions. "
        "Edge colour = funding council · Edge width ∝ jointly funded projects."
    )

    # ── Prepare data ──────────────────────────────────────────────────────────
    bip_top_insts = (
        df_all.groupby("institution").size()
        .sort_values(ascending=False)
        .head(20)
        .index.tolist()
    )
    # Sort funders by total project count descending
    bip_top_funders = (
        df_all["funder"].dropna().value_counts().index.tolist()
    )
    bip_edge_df = (
        df_all[df_all["institution"].isin(bip_top_insts)]
        .groupby(["funder", "institution"])
        .size()
        .reset_index(name="count")
    )
    bip_funder_counts = df_all["funder"].value_counts().to_dict()
    bip_inst_counts = (
        df_all[df_all["institution"].isin(bip_top_insts)]
        .groupby("institution").size().to_dict()
    )

    @st.cache_data(show_spinner="Rendering bipartite network…")
    def render_bipartite_mpl(top_funders, top_insts, edge_df,
                             funder_counts, inst_counts, council_colors):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import io

        def abbrev_inst(raw):
            known = {
                "university college london": "UCL",
                "king's college london": "King's College London",
                "imperial college london": "Imperial College London",
                "manchester academy": "Univ. Manchester",
                "heriot-watt university f.c.": "Heriot-Watt Univ.",
                "columbia university": "Columbia Univ.",
            }
            low = raw.lower()
            if low in known:
                return known[low]
            for prefix in ("the university of ", "university of ",
                           "university college "):
                if low.startswith(prefix):
                    return raw[len(prefix):].title()
            return raw.title().replace("University", "Univ.")

        n_f = len(top_funders)
        n_i = len(top_insts)
        max_w = edge_df["count"].max() if len(edge_df) else 1
        max_fc = max(funder_counts.values(), default=1)
        max_ic = max(inst_counts.values(), default=1)

        # Y positions: evenly spaced, top = highest project count
        fy = {f: 1.0 - i / max(n_f - 1, 1) for i, f in enumerate(top_funders)}
        iy = {inst: 1.0 - i / max(n_i - 1, 1) for i, inst in enumerate(top_insts)}

        X_F = 0.0   # funder node column (data coords)
        X_I = 1.0   # institution node column

        fig, ax = plt.subplots(figsize=(18, 14))
        fig.patch.set_facecolor("#ffffff")
        ax.set_facecolor("#f7f9f8")
        ax.set_xlim(-0.62, 1.62)
        ax.set_ylim(-0.06, 1.10)
        ax.axis("off")

        # ── Edges ─────────────────────────────────────────────────────────
        for _, row in edge_df.sort_values("count").iterrows():
            f, inst, w = row["funder"], row["institution"], row["count"]
            if f not in fy or inst not in iy:
                continue
            color = council_colors.get(f, "#aaaaaa")
            lw = 0.5 + 5.5 * (w / max_w)
            alpha = 0.14 + 0.48 * (w / max_w)
            ax.plot([X_F, X_I], [fy[f], iy[inst]], "-",
                    color=color, lw=lw, alpha=alpha,
                    zorder=1, solid_capstyle="round")

        # ── Funder nodes + labels (left side) ─────────────────────────────
        for f in top_funders:
            y = fy[f]
            color = council_colors.get(f, "#aaaaaa")
            size = 80 + 320 * (funder_counts.get(f, 1) / max_fc)
            ax.scatter([X_F], [y], s=size, c=color, zorder=3,
                       edgecolors="white", linewidths=2, alpha=0.93)
            ax.text(X_F - 0.04, y, f,
                    ha="right", va="center", fontsize=20,
                    color="#1a2a3a", zorder=4)

        # ── Institution nodes + labels (right side) ────────────────────────
        for inst in top_insts:
            y = iy[inst]
            size = 80 + 320 * (inst_counts.get(inst, 1) / max_ic)
            ax.scatter([X_I], [y], s=size, c="#2ca02c", zorder=3,
                       edgecolors="white", linewidths=2, alpha=0.93)
            ax.text(X_I + 0.04, y, abbrev_inst(inst),
                    ha="left", va="center", fontsize=20,
                    color="#1a5438", zorder=4)

        # ── Column headers ─────────────────────────────────────────────────
        ax.text(X_F, 1.07, "Funding Councils",
                ha="center", va="bottom", fontsize=24,
                fontweight="bold", color="#1f4e79")
        ax.text(X_I, 1.07, "Lead Institutions (Top 20)",
                ha="center", va="bottom", fontsize=24,
                fontweight="bold", color="#1a5438")

        # ── Caption ───────────────────────────────────────────────────────
        ax.text(0.5, -0.04,
                "Edge colour = funding council  ·  "
                "Edge width ∝ shared projects  ·  "
                "Node size ∝ project count",
                ha="center", va="top", fontsize=16,
                color="#666", transform=ax.transAxes)

        plt.tight_layout(pad=0.3)

        buf_png = io.BytesIO()
        fig.savefig(buf_png, format="png", dpi=300,
                    bbox_inches="tight", facecolor="white")
        buf_png.seek(0)
        buf_svg = io.BytesIO()
        fig.savefig(buf_svg, format="svg",
                    bbox_inches="tight", facecolor="white")
        buf_svg.seek(0)
        plt.close(fig)
        return buf_png.getvalue(), buf_svg.getvalue()

    bip_png, bip_svg = render_bipartite_mpl(
        tuple(bip_top_funders), tuple(bip_top_insts),
        bip_edge_df, bip_funder_counts, bip_inst_counts,
        COUNCIL_COLORS,
    )
    st.image(bip_png, use_container_width=True)

    bip_dl1, bip_dl2 = st.columns(2)
    with bip_dl1:
        st.download_button(
            "📥 Download PNG (300 DPI)", data=bip_png,
            file_name="ukri_funder_institution_bipartite.png",
            mime="image/png",
        )
    with bip_dl2:
        st.download_button(
            "📥 Download SVG (vector)", data=bip_svg,
            file_name="ukri_funder_institution_bipartite.svg",
            mime="image/svg+xml",
        )


# ═════════════════════════════════════════════════════════════════════════════
# TAB 6 – RESEARCH IMPACT
# ═════════════════════════════════════════════════════════════════════════════
with tab6:
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown('<div class="section-header">Publications per Project by Council</div>', unsafe_allow_html=True)
        pub_council = (
            df.groupby("funder")
            .agg(
                total_pubs=("publication_count", "sum"),
                projects=("project_ref", "count"),
            )
            .reset_index()
        )
        pub_council["pubs_per_project"] = pub_council["total_pubs"] / pub_council["projects"]
        pub_council = pub_council.sort_values("pubs_per_project", ascending=True)

        fig_pub_council = px.bar(
            pub_council,
            y="funder",
            x="pubs_per_project",
            orientation="h",
            color="total_pubs",
            color_continuous_scale="Blues",
            labels={"pubs_per_project": "Publications per Project", "funder": "", "total_pubs": "Total Pubs"},
            template="plotly_white",
        )
        fig_pub_council.update_layout(height=380, margin=dict(t=10), coloraxis_colorbar_title="Total Pubs")
        _chart(fig_pub_council, "ukri_publications_per_project_by_council")

    with col_b:
        st.markdown('<div class="section-header">Publications: Sustainability vs. Other Projects</div>', unsafe_allow_html=True)
        pub_sus = df.copy()
        pub_sus["type"] = pub_sus["is_sustainability"].map({True: "Sustainability", False: "Other UKRI"})
        fig_pub_sus = px.histogram(
            pub_sus[pub_sus["publication_count"] > 0],
            x="publication_count",
            color="type",
            nbins=50,
            barmode="overlay",
            opacity=0.7,
            color_discrete_map={"Sustainability": "#2ca02c", "Other UKRI": "#aec7e8"},
            labels={"publication_count": "Publications per Project", "count": "Projects"},
            template="plotly_white",
            log_y=True,
        )
        fig_pub_sus.update_layout(height=380, margin=dict(t=10), legend_title_text="", yaxis_title="Projects (log)")
        _chart(fig_pub_sus, "ukri_publications_sustainability_vs_other")

    # Top 20 projects by publications
    st.markdown('<div class="section-header">Top 20 Projects by Publication Output</div>', unsafe_allow_html=True)
    top_pubs = (
        df[df["publication_count"] > 0]
        .sort_values("publication_count", ascending=False)
        .head(20)[["title", "funder", "institution", "start_year", "fund_value", "publication_count", "is_sustainability"]]
        .copy()
    )
    top_pubs["fund_value_M"] = (top_pubs["fund_value"] / 1e6).round(1)
    top_pubs["sustainability"] = top_pubs["is_sustainability"].map({True: "✓", False: ""})
    top_pubs = top_pubs.drop(columns=["fund_value", "is_sustainability"])
    top_pubs.columns = ["Title", "Council", "Institution", "Year", "Publications", "Grant (£M)", "Sustainable"]
    top_pubs = top_pubs.reset_index(drop=True)
    top_pubs.index += 1
    st.dataframe(top_pubs, use_container_width=True)

    # Publication vs grant size
    st.markdown('<div class="section-header">Publications vs. Grant Size</div>', unsafe_allow_html=True)
    pub_scat = df[(df["publication_count"] > 0) & df["fund_value"].notna()].copy()
    pub_scat["funding_M"] = pub_scat["fund_value"] / 1e6
    fig_pub_scat = px.scatter(
        pub_scat,
        x="funding_M",
        y="publication_count",
        color="funder",
        color_discrete_map=COUNCIL_COLORS,
        opacity=0.6,
        hover_name="title",
        log_x=True,
        log_y=True,
        labels={
            "funding_M": "Grant Size (£M, log)",
            "publication_count": "Publications (log)",
            "funder": "Council",
        },
        template="plotly_white",
        trendline="ols",
        trendline_scope="overall",
        trendline_color_override="black",
    )
    fig_pub_scat.update_layout(height=420, margin=dict(t=10))
    _chart(fig_pub_scat, "ukri_publications_vs_grant_size")

    # Publications per region
    st.markdown('<div class="section-header">Publication Output by Region</div>', unsafe_allow_html=True)
    pub_reg = (
        df.groupby("region")
        .agg(
            total_pubs=("publication_count", "sum"),
            projects=("project_ref", "count"),
        )
        .reset_index()
    )
    pub_reg["pubs_per_project"] = (pub_reg["total_pubs"] / pub_reg["projects"]).round(1)
    pub_reg = pub_reg.sort_values("total_pubs", ascending=True)

    fig_pub_reg = go.Figure()
    fig_pub_reg.add_trace(go.Bar(
        y=pub_reg["region"],
        x=pub_reg["total_pubs"],
        orientation="h",
        name="Total Publications",
        marker_color="#1f77b4",
    ))
    fig_pub_reg.update_layout(
        xaxis_title="Total Publications",
        template="plotly_white",
        height=380,
        margin=dict(t=10),
    )
    _chart(fig_pub_reg, "ukri_publication_output_by_region")

# ── Footer ─────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<small>Data: UKRI Gateway to Research (GTR) API · "
    "Projects: 1,383 curated records · JSON: 16,128 project files · "
    "Analysis: keyword classification across 8 sustainability themes · "
    "Dashboard built for *Nature Sustainability* submission</small>",
    unsafe_allow_html=True,
)
