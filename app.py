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

# ── Sub-themes ────────────────────────────────────────────────────────────────
# Each theme's keyword list (from data_processor.SUSTAINABILITY_THEMES) is
# partitioned into coherent sub-themes. The union of a theme's sub-theme
# keywords equals that theme's full keyword list, so the two tiers are
# consistent (theme funding = sum of its sub-theme funding).
SUB_THEMES = {
    "Climate & Carbon": {
        "Climate Change & Warming": [
            "climate change", "climate crisis", "global warming",
            "greenhouse gas", "co2", "methane", "paris agreement",
        ],
        "Net Zero & Decarbonisation": [
            "net zero", "net-zero", "decarbonisation", "decarbonization",
        ],
        "Carbon Capture & Removal": [
            "carbon", "carbon capture", "carbon sequestration",
        ],
        "Adaptation & Mitigation": [
            "climate adaptation", "climate mitigation",
        ],
    },
    "Clean Energy": {
        "Solar": ["solar energy", "solar cell", "solar panel", "photovoltaic"],
        "Wind": ["wind energy", "wind turbine", "offshore wind"],
        "Storage & Hydrogen": [
            "hydrogen energy", "energy storage", "battery storage", "fuel cell",
        ],
        "Other Renewables & Transition": [
            "renewable energy", "energy transition", "clean energy",
            "low carbon energy", "nuclear fusion", "tidal energy", "geothermal",
        ],
    },
    "Environment & Ecology": {
        "Biodiversity & Wildlife": [
            "biodiversity", "wildlife", "species extinction",
            "ecosystem", "ecological",
        ],
        "Conservation & Restoration": [
            "conservation", "nature-based", "rewilding", "habitat loss",
            "deforestation", "land degradation",
        ],
        "Pollution & Air Quality": [
            "pollution", "air quality", "microplastic", "environmental impact",
        ],
    },
    "Water & Oceans": {
        "Freshwater & Supply": [
            "water quality", "water security", "water resource",
            "freshwater", "hydrological", "wastewater",
        ],
        "Oceans & Marine": [
            "ocean", "marine ecosystem", "coastal", "blue carbon",
            "coral reef", "sea level", "ocean acidification",
        ],
        "Flood & Drought": ["flood risk", "drought"],
    },
    "Food & Agriculture": {
        "Food Security & Systems": [
            "food security", "food system", "food production", "food waste",
        ],
        "Sustainable Farming": [
            "sustainable agriculture", "agroecology", "precision agriculture",
            "agri-environment", "sustainable farming", "agricultural sustainability",
        ],
        "Soil & Crops": [
            "crop resilience", "soil health", "soil carbon", "land use",
        ],
    },
    "Circular Economy": {
        "Recycling & Waste": [
            "recycling", "waste reduction", "plastic pollution", "reuse",
            "upcycling", "material recovery", "end of life",
        ],
        "Sustainable Materials": ["sustainable materials", "bioplastic"],
        "Resource Efficiency & Manufacturing": [
            "circular economy", "resource efficiency", "industrial ecology",
            "cradle to cradle", "sustainable manufacturing",
        ],
    },
    "Sustainable Cities": {
        "Urban Planning & Built Environment": [
            "sustainable city", "urban sustainability", "smart city",
            "urban planning", "built environment", "green infrastructure",
            "urban heat",
        ],
        "Sustainable Transport": [
            "transport decarbonisation", "sustainable transport",
            "active travel", "electric vehicle", "zero emission",
        ],
    },
    "Social Sustainability": {
        "Justice & Equity": [
            "environmental justice", "climate justice", "health inequality",
            "low income", "vulnerable communities",
        ],
        "Development & SDGs": [
            "sustainable development", "sdg", "community resilience",
        ],
        "Policy & Just Transition": [
            "just transition", "green jobs", "sustainability governance",
            "sustainability policy",
        ],
    },
}

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
    st.markdown("UKRI Gateway to Research API  \n16,128 project records (all JSON files)")

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
header_col, export_col = st.columns([4, 1.4])
with header_col:
    st.title("🌿 UKRI Sustainability Research Funding")
    st.markdown(
        "**Mapping public R&D investment in sustainability science across the UK (2016–2025)**  \n"
        "Analysis prepared for *Nature Sustainability*"
    )
with export_col:
    st.markdown("&nbsp;", unsafe_allow_html=True)
    if st.button("📊 Build PowerPoint", help="Generate a slide deck with all headline figures, tables, and network graphs — descriptive captions go into the speaker notes.", use_container_width=True):
        with st.spinner("Building PowerPoint deck (figures, tables, networks)…"):
            from pptx_export import build_pptx_bytes
            st.session_state["pptx_bytes"] = build_pptx_bytes(df)
    if "pptx_bytes" in st.session_state:
        from datetime import date as _d
        st.download_button(
            "⬇️ Download .pptx",
            data=st.session_state["pptx_bytes"],
            file_name=f"ukri_sustainability_dashboard_{_d.today().isoformat()}.pptx",
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            use_container_width=True,
        )
    if st.button(
        "📄 Generate Scientific Paper (Nature Sustainability Format)",
        help="Generate a complete Nature Sustainability-style manuscript as a .docx file, with every figure embedded, captioned, and discussed in the main text. Includes Abstract, Introduction, Results, Discussion, Methods, References.",
        use_container_width=True,
    ):
        with st.spinner("Generating manuscript (figures, narrative, tables, references)…"):
            from paper_export import build_paper_docx
            st.session_state["paper_bytes"] = build_paper_docx(df)
    if "paper_bytes" in st.session_state:
        from datetime import date as _d2
        st.download_button(
            "⬇️ Download .docx",
            data=st.session_state["paper_bytes"],
            file_name=f"ukri_sustainability_manuscript_{_d2.today().isoformat()}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
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
    st.markdown('<div class="section-header">Grant Size Distribution: Top 10 Councils by Sustainability Funding</div>', unsafe_allow_html=True)
    # Rank councils by total sustainability funding, keep the top 10
    top10_councils = (
        df[df["is_sustainability"] & df["fund_value"].notna()]
        .groupby("funder")["fund_value"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
        .index
        .tolist()
    )
    box_df = df[
        df["fund_value"].notna()
        & (df["fund_value"] > 0)
        & df["funder"].isin(top10_councils)
    ].copy()
    box_df["funding_M"] = box_df["fund_value"] / 1e6
    fig_box = px.box(
        box_df,
        x="funder",
        y="funding_M",
        color="funder",
        color_discrete_map=COUNCIL_COLORS,
        points="all",
        labels={"funding_M": "Grant Size (£M)", "funder": "Council"},
        template="plotly_white",
        log_y=True,
        category_orders={"funder": top10_councils},
    )
    fig_box.update_traces(
        marker=dict(size=3, opacity=0.35),
        jitter=0.4,
        pointpos=0,
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
    st.caption(
        "Bar length = total funding. **Colour = interdisciplinarity index** — the Shannon "
        "diversity of an institution's declared research subjects across its portfolio "
        "(0 = all projects in a single discipline; higher = funding spread more evenly "
        "across many disciplines). Sustainability share (keyword classification of titles "
        "and abstracts across 8 themes) is shown on hover."
    )

    # ── Interdisciplinarity index: Shannon diversity of research subjects ───────
    @st.cache_data(show_spinner=False)
    def _institution_interdisciplinarity(data_key):
        import math
        from collections import Counter
        rows = []
        for inst, grp in df.groupby("institution"):
            counter = Counter()
            for s in grp["research_subjects"]:
                for subj in str(s).split(";"):
                    subj = subj.strip()
                    if subj:
                        counter[subj] += 1
            total = sum(counter.values())
            if total > 0:
                shannon = -sum((c / total) * math.log(c / total) for c in counter.values())
            else:
                shannon = 0.0
            rows.append({
                "institution": inst,
                "interdisc": round(shannon, 2),
                "n_subjects": len(counter),
            })
        return pd.DataFrame(rows)

    interdisc_df = _institution_interdisciplinarity(f"interdisc_{len(df)}_{df['fund_value'].sum():.0f}")

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
        .merge(interdisc_df, on="institution", how="left")
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
            color=top20["interdisc"],
            colorscale="Viridis",
            colorbar=dict(title="Interdisciplinarity<br>(subject diversity)"),
        ),
        text=[f"£{v:.0f}M" for v in top20["funding_M"]],
        textposition="outside",
        customdata=np.stack([
            top20["interdisc"],
            top20["n_subjects"],
            top20["projects"],
            top20["sus_pct"],
        ], axis=-1),
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Total funding: £%{x:.0f}M<br>"
            "Interdisciplinarity index: %{customdata[0]:.2f}<br>"
            "Distinct research subjects: %{customdata[1]}<br>"
            "Projects: %{customdata[2]}<br>"
            "Sustainability share: %{customdata[3]:.0f}%"
            "<extra></extra>"
        ),
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
        st.caption(
            "Bubble size = publications. **Colour = interdisciplinarity index** (Shannon "
            "diversity of declared research subjects). Sustainability share — keyword "
            "classification of titles and abstracts across 8 themes — is shown on hover."
        )
        top50 = inst_df[inst_df["projects"] >= 3].head(50)
        fig_bubble = px.scatter(
            top50,
            x="projects",
            y="funding_M",
            size="total_pubs",
            color="interdisc",
            color_continuous_scale="Viridis",
            hover_name="institution",
            hover_data={
                "interdisc": ":.2f",
                "n_subjects": True,
                "sus_pct": ":.0f",
                "total_pubs": True,
            },
            labels={
                "projects": "Number of Projects",
                "funding_M": "Total Funding (£M)",
                "total_pubs": "Publications",
                "interdisc": "Interdisciplinarity",
                "n_subjects": "Distinct subjects",
                "sus_pct": "% Sustainability",
            },
            template="plotly_white",
            size_max=40,
        )
        fig_bubble.update_layout(
            height=420,
            margin=dict(t=10),
            coloraxis_colorbar_title="Interdiscip.<br>(subj. diversity)",
        )
        _chart(fig_bubble, "ukri_institution_funding_vs_projects")

    with col_b:
        st.markdown('<div class="section-header">Department-Level Funding (Top 15)</div>', unsafe_allow_html=True)
        st.caption(
            "Lead departments recorded in project metadata — a subject-level view of where "
            "funding concentrates. Projects with no department recorded "
            f"({(df['department'].fillna('').str.strip() == '').sum():,} of {len(df):,}) are excluded."
        )
        dept_clean = df["department"].fillna("").str.strip()
        dept_mask = (
            (dept_clean != "")
            & (dept_clean.str.upper() != "UNLISTED")
        )
        dept_df = (
            df[dept_mask]
            .groupby(dept_clean[dept_mask])
            .agg(
                fund_value=("fund_value", "sum"),
                projects=("project_ref", "count"),
                insts=("institution", "nunique"),
            )
            .reset_index()
            .rename(columns={"department": "department"})
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
            color_continuous_scale="Tealgrn",
            labels={"funding_M": "Funding (£M)", "department": ""},
            custom_data=["projects", "insts"],
            template="plotly_white",
        )
        fig_dept.update_traces(
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Funding: £%{x:.0f}M<br>"
                "Projects: %{customdata[0]}<br>"
                "Institutions: %{customdata[1]}"
                "<extra></extra>"
            )
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
            color_continuous_scale="Tealgrn",
            labels={"projects": "Projects", "theme": "", "funding_M": "Funding (£M)"},
            template="plotly_white",
        )
        fig_themes.update_layout(height=400, margin=dict(t=10), coloraxis_colorbar_title="£M")
        _chart(fig_themes, "ukri_sustainability_projects_by_theme")

    with col_b:
        # Theme funding donut
        st.markdown('<div class="section-header">Sustainability Funding: Theme → Sub-theme (£M)</div>', unsafe_allow_html=True)
        st.caption(
            "Inner ring = theme, outer ring = sub-theme. Each project's funding is "
            "attributed to the sub-theme whose keywords it matches most strongly, so "
            "every theme total equals the sum of its sub-themes."
        )

        @st.cache_data(show_spinner=False)
        def _theme_subtheme_funding(data_key):
            texts = (df["title"].fillna("") + " " + df["abstract"].fillna("")).str.lower()
            funds = df["fund_value"].fillna(0)
            records = {}
            for theme, subs in SUB_THEMES.items():
                col_key = "theme_" + theme.lower().replace(" ", "_").replace("&", "and")
                if col_key not in df.columns:
                    continue
                matched = df[col_key].values
                for txt, fund, m in zip(texts, funds, matched):
                    if not m:
                        continue
                    best_sub, best_hits = None, -1
                    for sub_name, kws in subs.items():
                        hits = sum(1 for kw in kws if kw in txt)
                        if hits > best_hits:
                            best_hits, best_sub = hits, sub_name
                    if best_sub is not None:
                        key = (theme, best_sub)
                        records[key] = records.get(key, 0.0) + fund
            return pd.DataFrame(
                [{"theme": t, "subtheme": s, "funding_M": v / 1e6}
                 for (t, s), v in records.items()]
            )

        sub_funding_df = _theme_subtheme_funding(
            f"subtheme_{len(df)}_{df['fund_value'].sum():.0f}"
        )
        fig_th_sun = px.sunburst(
            sub_funding_df,
            path=["theme", "subtheme"],
            values="funding_M",
            color="theme",
            color_discrete_sequence=THEME_COLORS,
            template="plotly_white",
        )
        fig_th_sun.update_traces(
            textinfo="label+percent parent",
            insidetextorientation="radial",
            hovertemplate="<b>%{label}</b><br>£%{value:.0f}M<br>%{percentRoot:.1%} of total<extra></extra>",
        )
        fig_th_sun.update_layout(height=420, margin=dict(t=10, l=0, r=0, b=0))
        _chart(fig_th_sun, "ukri_sustainability_funding_by_theme")

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

    # Theme × council — funding size
    st.markdown('<div class="section-header">Sustainability Theme × Funding Council (Total Funding £M)</div>', unsafe_allow_html=True)
    th_council_fund_rows = []
    for theme in SUSTAINABILITY_THEMES:
        col_key = "theme_" + theme.lower().replace(" ", "_").replace("&", "and")
        if col_key in df.columns:
            sub = (
                df[df[col_key]]
                .groupby("funder")["fund_value"]
                .sum()
                .reset_index(name="funding")
            )
            sub["theme"] = theme
            th_council_fund_rows.append(sub)
    if th_council_fund_rows:
        tcf_df = pd.concat(th_council_fund_rows)
        tcf_df["funding_M"] = tcf_df["funding"] / 1e6
        tcf_pivot = tcf_df.pivot(index="theme", columns="funder", values="funding_M").fillna(0)
        fig_tcf = px.imshow(
            tcf_pivot,
            aspect="auto",
            color_continuous_scale="YlOrRd",
            labels=dict(color="£M"),
            template="plotly_white",
            text_auto=".0f",
        )
        fig_tcf.update_layout(height=380, margin=dict(t=10))
        _chart(fig_tcf, "ukri_theme_council_funding_heatmap")

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

    # Theme × region — funding size
    st.markdown('<div class="section-header">Sustainability Theme × Region (Total Funding £M)</div>', unsafe_allow_html=True)
    th_reg_fund_rows = []
    for theme in SUSTAINABILITY_THEMES:
        col_key = "theme_" + theme.lower().replace(" ", "_").replace("&", "and")
        if col_key in df.columns:
            sub = (
                df[df[col_key]]
                .groupby("region")["fund_value"]
                .sum()
                .reset_index(name="funding")
            )
            sub["theme"] = theme
            th_reg_fund_rows.append(sub)
    if th_reg_fund_rows:
        trf_df = pd.concat(th_reg_fund_rows)
        trf_df["funding_M"] = trf_df["funding"] / 1e6
        trf_pivot = trf_df.pivot(index="theme", columns="region", values="funding_M").fillna(0)
        fig_trf = px.imshow(
            trf_pivot,
            aspect="auto",
            color_continuous_scale="YlOrRd",
            labels=dict(color="£M"),
            template="plotly_white",
            text_auto=".0f",
        )
        fig_trf.update_layout(height=380, margin=dict(t=10))
        _chart(fig_trf, "ukri_theme_region_funding_heatmap")

    # Research topics — frequency coloured by interdisciplinarity
    st.markdown('<div class="section-header">Most Frequent Research Topics in Sustainability Projects</div>', unsafe_allow_html=True)
    st.caption(
        "Bar length = how often the topic is declared. **Colour = interdisciplinarity "
        "index** — the Shannon diversity of research subjects across the projects that "
        "feature the topic (higher = the topic spans more disciplines, i.e. an "
        "interdisciplinary connector; lower = concentrated in one field)."
    )

    PLACEHOLDER_TOPICS = {"unclassified", "see subject area"}

    @st.cache_data(show_spinner=False)
    def _topic_frequency_interdisc(data_key):
        import math
        topic_count = Counter()
        topic_subj = {}
        for topics_str, subjects_str in zip(
            sus_df["research_topics"].fillna(""), sus_df["research_subjects"].fillna("")
        ):
            topics = [
                t.strip() for t in topics_str.split(";")
                if t.strip() and t.strip().lower() not in PLACEHOLDER_TOPICS
            ]
            subjects = [s.strip() for s in subjects_str.split(";") if s.strip()]
            for t in topics:
                topic_count[t] += 1
                topic_subj.setdefault(t, Counter()).update(subjects)
        rows = []
        for topic, cnt in topic_count.items():
            c = topic_subj[topic]
            total = sum(c.values())
            shannon = (
                -sum((v / total) * math.log(v / total) for v in c.values())
                if total else 0.0
            )
            rows.append({
                "topic": topic,
                "count": cnt,
                "interdisc": round(shannon, 2),
                "n_subjects": len(c),
            })
        return pd.DataFrame(rows)

    topic_metrics = _topic_frequency_interdisc(
        f"topicidx_{len(sus_df)}_{sus_df['fund_value'].sum():.0f}"
    )
    if not topic_metrics.empty:
        td_df = topic_metrics.sort_values("count", ascending=False).head(25).sort_values("count")
        fig_topics = px.bar(
            td_df,
            y="topic",
            x="count",
            orientation="h",
            color="interdisc",
            color_continuous_scale="Viridis",
            custom_data=["interdisc", "n_subjects"],
            labels={"count": "Occurrences", "topic": "", "interdisc": "Interdisciplinarity"},
            template="plotly_white",
        )
        fig_topics.update_traces(
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Occurrences: %{x}<br>"
                "Interdisciplinarity index: %{customdata[0]:.2f}<br>"
                "Distinct research subjects: %{customdata[1]}"
                "<extra></extra>"
            )
        )
        fig_topics.update_layout(
            height=500,
            margin=dict(t=10),
            coloraxis_colorbar_title="Interdiscip.<br>(subj. diversity)",
        )
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
        st.markdown('<div class="section-header">Collaboration Size by Funding Council — Standard Projects</div>', unsafe_allow_html=True)
        net_threshold = st.slider(
            "Large-consortium threshold (partner organisations)",
            min_value=10, max_value=60, value=20, step=5,
            help="Projects with more partners than this are treated as large consortia / "
                 "network projects and shown separately below, so they don't compress the "
                 "box plot for typical projects.",
        )
        standard_collab = df[(df["collab_count"] > 0) & (df["collab_count"] <= net_threshold)]
        fig_collab_box = px.box(
            standard_collab,
            x="funder",
            y="collab_count",
            color="funder",
            color_discrete_map=COUNCIL_COLORS,
            points="outliers",
            labels={"collab_count": "Partner Organisations", "funder": "Council"},
            template="plotly_white",
        )
        fig_collab_box.update_layout(showlegend=False, height=360, margin=dict(t=10))
        _chart(fig_collab_box, "ukri_collaboration_size_by_council_standard")

    # Large consortia / network projects — plotted separately
    large_collab = df[df["collab_count"] > net_threshold]
    st.markdown(
        f'<div class="section-header">Large Consortia / Network Projects '
        f'(&gt; {net_threshold} partners) by Council</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        f"{len(large_collab):,} projects exceed {net_threshold} partner organisations — "
        "typically network grants, consortia and large programme awards. Each dot is one "
        "project; these are the outliers removed from the box plot above."
    )
    if len(large_collab):
        fig_large = px.box(
            large_collab,
            x="funder",
            y="collab_count",
            color="funder",
            color_discrete_map=COUNCIL_COLORS,
            points="all",
            hover_name="title",
            labels={"collab_count": "Partner Organisations", "funder": "Council"},
            template="plotly_white",
        )
        fig_large.update_traces(marker=dict(size=5, opacity=0.6), jitter=0.3, pointpos=0)
        fig_large.update_layout(showlegend=False, height=360, margin=dict(t=10))
        _chart(fig_large, "ukri_collaboration_large_consortia")
    else:
        st.info(f"No projects exceed {net_threshold} partner organisations in the current selection.")

    # Average collaboration by region
    st.markdown('<div class="section-header">Collaboration Size by Funding Tier & Sustainability Status</div>', unsafe_allow_html=True)
    st.caption(
        "Grant funding spans more than three orders of magnitude and is approximately "
        "log-normal, so projects are grouped into order-of-magnitude (log-spaced) tiers "
        "rather than equal-width bins. Box = median and interquartile range per tier; "
        "collaboration size grows steeply with grant size."
    )
    FUND_TIER_EDGES = [100_000, 500_000, 1_000_000, 5_000_000, 10_000_000, np.inf]
    FUND_TIER_LABELS = ["£100k–500k", "£500k–1M", "£1M–5M", "£5M–10M", ">£10M"]
    collab_fund = df[df["fund_value"].notna() & (df["fund_value"] >= FUND_TIER_EDGES[0])].copy()
    collab_fund["fund_tier"] = pd.cut(
        collab_fund["fund_value"],
        bins=FUND_TIER_EDGES,
        labels=FUND_TIER_LABELS,
        right=False,
    )
    collab_fund["type"] = collab_fund["is_sustainability"].map(
        {True: "Sustainability", False: "Other UKRI"}
    )
    fig_collab_fund = px.box(
        collab_fund,
        x="fund_tier",
        y="collab_count",
        color="type",
        points=False,
        category_orders={"fund_tier": FUND_TIER_LABELS,
                         "type": ["Sustainability", "Other UKRI"]},
        color_discrete_map={"Sustainability": "#2ca02c", "Other UKRI": "#aec7e8"},
        labels={"collab_count": "Partner Organisations", "fund_tier": "Grant Funding Tier", "type": ""},
        template="plotly_white",
    )
    fig_collab_fund.update_layout(
        height=380, margin=dict(t=10), legend_title_text="", boxmode="group"
    )
    _chart(fig_collab_fund, "ukri_collaboration_by_funding_tier")

    # Companion: mean collaboration size per tier (robust summary with sample sizes)
    tier_summary = (
        collab_fund.groupby("fund_tier", observed=True)["collab_count"]
        .agg(mean_collab="mean", median_collab="median", projects="size")
        .reset_index()
    )
    tier_summary["mean_collab"] = tier_summary["mean_collab"].round(1)
    tier_summary["fund_tier"] = pd.Categorical(
        tier_summary["fund_tier"], categories=FUND_TIER_LABELS, ordered=True
    )
    tier_summary = tier_summary.sort_values("fund_tier")
    fig_tier_mean = px.bar(
        tier_summary,
        x="fund_tier",
        y="mean_collab",
        color="mean_collab",
        color_continuous_scale="Tealgrn",
        custom_data=["median_collab", "projects"],
        labels={"mean_collab": "Mean Partner Organisations", "fund_tier": "Grant Funding Tier"},
        template="plotly_white",
        text="mean_collab",
    )
    fig_tier_mean.update_traces(
        textposition="outside",
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Mean partners: %{y}<br>"
            "Median partners: %{customdata[0]}<br>"
            "Projects: %{customdata[1]}"
            "<extra></extra>"
        ),
    )
    fig_tier_mean.update_layout(
        height=320, margin=dict(t=10), coloraxis_showscale=False
    )
    _chart(fig_tier_mean, "ukri_mean_collaboration_by_funding_tier")

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
        "Coloured edges are intra-community; grey edges are inter-community. "
        "Use the download buttons below the figure for a publication-quality PNG or SVG."
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
            orgs_raw = str(row.get("collab_orgs", "") or "")
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

    G_collab, community_map = build_collab_network("collab_v4_full16k", top_n=22, min_edge_weight=3)

    @st.cache_data(show_spinner="Rendering network figure…")
    def render_collab_matplotlib(_G, _community_map, legend_unit="institutions",
                                 abbreviate=True, label_fontsize=16, wrap_width=0,
                                 min_sep=0.22, offset_base=0.30, iterations=80,
                                 fig_w=14, fig_h=11, cache_key=""):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        from matplotlib.lines import Line2D
        import textwrap
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
            if abbreviate:
                low = raw.lower()
                if low in ABBREV:
                    disp = ABBREV[low]
                else:
                    disp = None
                    for prefix in ("the university of ", "university of ", "university college "):
                        if low.startswith(prefix):
                            disp = raw[len(prefix):].title()
                            break
                    if disp is None:
                        disp = raw.title().replace("University", "Univ.")
            else:
                disp = raw  # subjects etc. are already concise, keep verbatim
            if wrap_width and wrap_width > 0:
                disp = "\n".join(textwrap.wrap(disp, wrap_width))
            return disp

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
        for _ in range(iterations):
            for i in range(len(nl)):
                for j in range(i + 1, len(nl)):
                    a, b = nl[i], nl[j]
                    dx = pa[b][0] - pa[a][0]
                    dy = pa[b][1] - pa[a][1]
                    d = max((dx ** 2 + dy ** 2) ** 0.5, 1e-6)
                    if d < min_sep:
                        push = (min_sep - d) / 2
                        ux, uy = dx / d, dy / d
                        pa[a][0] -= push * ux; pa[a][1] -= push * uy
                        pa[b][0] += push * ux; pa[b][1] += push * uy
        pos = {n: tuple(p) for n, p in pa.items()}

        max_w = max((d["weight"] for _, _, d in _G.edges(data=True)), default=1)

        # ── Figure ────────────────────────────────────────────────────────────
        fig, ax = plt.subplots(figsize=(fig_w, fig_h))
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
            offset = offset_base + 0.10 * (deg / max_deg)
            lx = x + offset * dx / d
            ly = y + offset * dy / d

            label = short_name(node)
            bold = deg >= top5_threshold
            ax.text(
                lx, ly, label,
                fontsize=label_fontsize, fontweight="bold" if bold else "normal",
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
                               label=f"Community {cid + 1}  ({n_m} {legend_unit})")
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
            loc="center left",
            bbox_to_anchor=(1.02, 0.5),
            framealpha=0.93,
            fontsize=15,
            title="Research communities",
            title_fontsize=16,
            edgecolor="#dddddd",
            borderpad=0.9,
            labelspacing=0.55,
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

    # ── Graph 1b: Research Subject Co-occurrence Network (static, paper-quality) ─
    st.markdown('<div class="section-header">Research Subject Co-occurrence Network (Top Hubs)</div>', unsafe_allow_html=True)
    st.caption(
        "Companion to the institution network, built the same way but over research "
        "subjects. Nodes = research subjects; an edge links two subjects declared together "
        "on the same project. Node size ∝ number of distinct subjects it co-occurs with "
        "(disciplinary breadth). Colour = subject community (greedy modularity); edge "
        "thickness ∝ projects sharing both subjects. Coloured edges are intra-community, "
        "grey edges inter-community. Use the download buttons below for a publication-quality "
        "PNG or SVG."
    )

    @st.cache_data(show_spinner="Building subject co-occurrence network…")
    def build_subject_network(data_key, top_n=22, min_edge_weight=12):
        import itertools
        from collections import Counter
        from data_processor import get_or_build_dataset as _load
        _df = _load()
        placeholders = {"unclassified", "see subject area", "see research areas",
                        "not yet classified", "other", ""}

        freq = Counter()
        n_projects = 0
        G_full = nx.Graph()
        for s in _df["research_subjects"].fillna(""):
            subs = [x.strip() for x in str(s).split(";")
                    if x.strip().lower() not in placeholders]
            subs = list(dict.fromkeys(subs))  # unique within a project
            if subs:
                n_projects += 1
            for x in subs:
                freq[x] += 1
            for u, v in itertools.combinations(subs, 2):
                if G_full.has_edge(u, v):
                    G_full[u][v]["weight"] += 1
                else:
                    G_full.add_edge(u, v, weight=1)

        degree_map = dict(G_full.degree())
        top_nodes = sorted(degree_map, key=lambda x: -degree_map[x])[:top_n]
        sub = G_full.subgraph(top_nodes).copy()

        edges_to_remove = [(u, v) for u, v, d in sub.edges(data=True) if d["weight"] < min_edge_weight]
        sub.remove_edges_from(edges_to_remove)
        sub.remove_nodes_from(list(nx.isolates(sub)))

        # Chance-corrected tie strengths on the displayed edges
        for u, v, d in sub.edges(data=True):
            w = d["weight"]
            d["assoc"] = w * n_projects / (freq[u] * freq[v]) if freq[u] and freq[v] else 0.0
            d["jaccard"] = w / (freq[u] + freq[v] - w) if (freq[u] + freq[v] - w) else 0.0

        communities = list(nx.algorithms.community.greedy_modularity_communities(sub))
        community_map = {}
        for i, comm in enumerate(communities):
            for node in comm:
                community_map[node] = i

        # Missing-link prediction among the displayed hubs (non-edges in full graph)
        nodes = list(sub.nodes())
        non_edges = [(a, b) for a, b in itertools.combinations(nodes, 2)
                     if not G_full.has_edge(a, b)]
        miss_rows = []
        if non_edges:
            aa = dict(((a, b), s) for a, b, s in nx.adamic_adar_index(G_full, non_edges))
            ra = dict(((a, b), s) for a, b, s in nx.resource_allocation_index(G_full, non_edges))
            for a, b in non_edges:
                cn = len(list(nx.common_neighbors(G_full, a, b)))
                miss_rows.append({
                    "Subject A": a,
                    "Subject B": b,
                    "Shared neighbours": cn,
                    "Adamic–Adar": round(aa.get((a, b), 0.0), 2),
                    "Resource allocation": round(ra.get((a, b), 0.0), 3),
                })
        missing_df = (
            pd.DataFrame(miss_rows)
            .sort_values("Adamic–Adar", ascending=False)
            .reset_index(drop=True)
            if miss_rows else pd.DataFrame()
        )
        return sub, community_map, missing_df

    G_subject, subject_comm_map, subject_missing_df = build_subject_network(
        "subject_v2_full16k", top_n=22, min_edge_weight=12
    )

    TIE_METRICS = {
        "Co-occurrence count": "weight",
        "Association strength (chance-corrected)": "assoc",
        "Jaccard index": "jaccard",
    }
    tie_label = st.radio(
        "Edge weighting (tie strength)",
        list(TIE_METRICS.keys()), index=0, horizontal=True, key="subj_tie_metric",
    )
    tie_attr = TIE_METRICS[tie_label]

    # Re-weight a display copy so edge thickness reflects the chosen tie strength
    G_subject_disp = G_subject.copy()
    for u, v, d in G_subject_disp.edges(data=True):
        d["weight"] = d.get(tie_attr, 0.0)

    subj_png, subj_svg = render_collab_matplotlib(
        G_subject_disp, subject_comm_map, legend_unit="subjects", abbreviate=False,
        label_fontsize=13, wrap_width=16, min_sep=0.32, offset_base=0.40,
        iterations=120, fig_w=16, fig_h=12.5, cache_key=f"subj_{tie_attr}",
    )
    st.image(subj_png, use_container_width=True)
    st.caption(
        f"Edge thickness now reflects **{tie_label.lower()}**. Co-occurrence count = raw "
        "shared projects; association strength = shared projects relative to what chance "
        "would predict from each subject's frequency (>1 = stronger than chance); Jaccard = "
        "shared / combined project sets. Node selection (top 22 by degree) and communities "
        "are unchanged — only edge weighting differs."
    )

    sdl1, sdl2 = st.columns(2)
    with sdl1:
        st.download_button(
            "📥 Download PNG (300 DPI)", data=subj_png,
            file_name=f"ukri_subject_cooccurrence_network_{tie_attr}.png",
            mime="image/png", key="subj_png_dl",
        )
    with sdl2:
        st.download_button(
            "📥 Download SVG (vector)", data=subj_svg,
            file_name=f"ukri_subject_cooccurrence_network_{tie_attr}.svg",
            mime="image/svg+xml", key="subj_svg_dl",
        )

    # Edge tie-strength table (the numbers behind the edge thickness)
    tie_rows = [
        {"Subject A": u, "Subject B": v,
         "Shared projects": int(d.get("weight", 0)),
         "Association strength": round(d.get("assoc", 0.0), 2),
         "Jaccard": round(d.get("jaccard", 0.0), 3)}
        for u, v, d in G_subject.edges(data=True)
    ]
    if tie_rows:
        sort_col = {
            "weight": "Shared projects",
            "assoc": "Association strength",
            "jaccard": "Jaccard",
        }[tie_attr]
        tie_tbl = (
            pd.DataFrame(tie_rows)
            .sort_values(sort_col, ascending=False)
            .reset_index(drop=True)
        )
        st.markdown(
            '<div style="font-weight:600;color:#2e7d5e;margin-top:0.4rem">'
            f"Edge tie strengths — sorted by {tie_label.lower()}</div>",
            unsafe_allow_html=True,
        )
        st.caption(
            "The numbers behind the edge thickness. Association strength > 1 = stronger "
            "than chance; < 1 = weaker than chance."
        )
        st.dataframe(tie_tbl.head(15), use_container_width=True, hide_index=True)

    # Subject community membership summary
    subj_members: dict[int, list[str]] = {}
    for node, cid in subject_comm_map.items():
        subj_members.setdefault(cid, []).append(node)
    subj_cols = st.columns(min(len(subj_members), 5))
    for cid, members in sorted(subj_members.items()):
        with subj_cols[cid % len(subj_cols)]:
            color = COMMUNITY_COLORS[cid % len(COMMUNITY_COLORS)]
            preview = ", ".join(sorted(members)[:3]) + ("…" if len(members) > 3 else "")
            st.markdown(
                f'<span style="background:{color};padding:2px 8px;border-radius:3px;'
                f'color:#fff;font-size:0.78rem"><b>Community {cid + 1}</b></span> '
                f'<span style="font-size:0.8rem">{preview}</span>',
                unsafe_allow_html=True,
            )

    # Predicted missing links (interdisciplinary white space)
    st.markdown(
        '<div style="font-weight:600;color:#2e7d5e;margin-top:0.6rem">'
        "Predicted missing links — interdisciplinary white space</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Pairs of leading subjects that **never co-occur** on a project yet share many "
        "common neighbours, ranked by the Adamic–Adar link-prediction score (higher = more "
        "structurally expected, i.e. a stronger candidate interdisciplinary gap). "
        "Resource allocation is a second, stricter predictor shown for comparison."
    )
    if subject_missing_df is not None and not subject_missing_df.empty:
        st.dataframe(
            subject_missing_df.head(10),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("All leading subjects are already directly connected — no missing links to predict.")

    # ── Graph 1c: Organisation–Project Bipartite Network (from JSON files) ────
    st.markdown('<div class="section-header">Organisation–Project Network (Sustainability Collaborations)</div>', unsafe_allow_html=True)
    st.caption(
        "Bipartite view extracted directly from the per-project JSON files. "
        "Left column = organisations; right column = sustainability projects with ≥2 participants. "
        "Edges show participation. Project colour = funding council; organisation size ∝ number of joint projects shown. "
        "This complements the co-collaboration network above by exposing the specific projects that connect the hubs."
    )

    op_top_orgs = st.slider("Top organisations", 8, 25, 14, key="op_top_orgs")
    op_top_projects = st.slider("Top joint projects", 15, 60, 30, key="op_top_projects")

    @st.cache_data(show_spinner="Indexing organisation participation from JSON files…")
    def load_org_participation_cached():
        from data_processor import get_or_build_org_index
        return get_or_build_org_index()

    @st.cache_data(show_spinner="Building organisation–project bipartite network…")
    def build_org_project_bipartite(top_orgs_n: int, top_projects_n: int):
        from data_processor import get_or_build_dataset as _load
        df_full = _load()
        op = load_org_participation_cached()
        if op.empty:
            return None, [], {}

        df_full = df_full.assign(project_ref=df_full["project_ref"].astype(str))
        op = op.assign(project_ref=op["project_ref"].astype(str))

        sus_refs = set(df_full.loc[df_full["is_sustainability"], "project_ref"])
        op_s = op[op["project_ref"].isin(sus_refs)].copy()

        # Drop solo-org projects
        per_proj = op_s.groupby("project_ref")["org_name"].nunique()
        multi_refs = per_proj[per_proj >= 2].index
        op_s = op_s[op_s["project_ref"].isin(multi_refs)]
        if op_s.empty:
            return None, [], {}

        # Rank organisations by number of multi-org sustainability projects
        ranked_orgs = (
            op_s.groupby("org_name")["project_ref"].nunique().sort_values(ascending=False)
        )
        top_orgs = ranked_orgs.head(top_orgs_n).index.tolist()
        op_focus = op_s[op_s["org_name"].isin(top_orgs)]

        # Rank projects by how many of the top orgs they contain, then by funding value
        proj_meta = (
            df_full.loc[df_full["project_ref"].isin(op_focus["project_ref"].unique()),
                        ["project_ref", "title", "funder", "fund_value"]]
            .drop_duplicates("project_ref")
            .set_index("project_ref")
        )
        proj_score = op_focus.groupby("project_ref")["org_name"].nunique().rename("top_org_count")
        proj_rank = (
            proj_score.to_frame()
            .join(proj_meta[["fund_value"]], how="left")
            .fillna({"fund_value": 0})
            .sort_values(["top_org_count", "fund_value"], ascending=[False, False])
        )
        top_proj_refs = proj_rank.head(top_projects_n).index.tolist()
        op_final = op_focus[op_focus["project_ref"].isin(top_proj_refs)]

        G = nx.Graph()
        for org in top_orgs:
            G.add_node(("org", org), kind="org", label=org)
        for ref in top_proj_refs:
            meta = proj_meta.loc[ref] if ref in proj_meta.index else None
            title = str(meta["title"]) if meta is not None and pd.notna(meta["title"]) else ref
            funder = str(meta["funder"]) if meta is not None and pd.notna(meta["funder"]) else "Unknown"
            fv = float(meta["fund_value"]) if meta is not None and pd.notna(meta["fund_value"]) else 0.0
            G.add_node(("proj", ref), kind="proj", label=title, funder=funder, fund_value=fv, ref=ref)
        for _, row in op_final.iterrows():
            G.add_edge(("org", row["org_name"]), ("proj", row["project_ref"]))

        # Keep only orgs with at least one displayed project (some top orgs may drop out after project filter)
        for org in list(top_orgs):
            if G.degree(("org", org)) == 0:
                G.remove_node(("org", org))
        top_orgs = [o for o in top_orgs if ("org", o) in G]
        return G, top_orgs, {ref: proj_meta.loc[ref].to_dict() for ref in top_proj_refs if ref in proj_meta.index}

    G_bp, top_orgs_kept, _bp_meta = build_org_project_bipartite(op_top_orgs, op_top_projects)

    if G_bp is None or len(G_bp) == 0:
        st.info("No multi-organisation sustainability projects found in the JSON index. "
                "If this is the first run, the index is built lazily and may take ~30s.")
    else:
        @st.cache_data(show_spinner="Rendering bipartite figure…")
        def render_org_project_bipartite(_G, _top_orgs, sig: str,
                                         left_title="Organisations",
                                         right_title="Sustainability Projects",
                                         left_color="#0b3d91"):
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            from matplotlib.lines import Line2D
            import io

            FUNDER_PALETTE = [
                "#1f77b4", "#d62728", "#2ca02c", "#ff7f0e", "#9467bd",
                "#8c564b", "#e377c2", "#17becf", "#bcbd22", "#7f7f7f",
            ]

            org_nodes = [n for n in _G.nodes if _G.nodes[n].get("kind") == "org"]
            proj_nodes = [n for n in _G.nodes if _G.nodes[n].get("kind") == "proj"]

            funders = sorted({_G.nodes[n].get("funder", "Unknown") for n in proj_nodes})
            funder_color = {f: FUNDER_PALETTE[i % len(FUNDER_PALETTE)] for i, f in enumerate(funders)}

            # Organisations sorted by degree desc (most-connected at top)
            org_sorted = sorted(org_nodes, key=lambda n: -_G.degree(n))
            # Projects grouped by funder for visual banding
            proj_sorted = sorted(
                proj_nodes,
                key=lambda n: (_G.nodes[n].get("funder", "zzz"), -_G.degree(n)),
            )

            def col_positions(nodes, x):
                m = len(nodes)
                if m == 1:
                    return {nodes[0]: (x, 0)}
                return {n: (x, 1.0 - 2.0 * i / (m - 1)) for i, n in enumerate(nodes)}

            pos = {}
            pos.update(col_positions(org_sorted, -1.0))
            pos.update(col_positions(proj_sorted, 1.0))

            n_rows = max(len(org_sorted), len(proj_sorted))
            fig_h = max(8.0, 0.36 * n_rows)
            fig, ax = plt.subplots(figsize=(16, fig_h))
            fig.patch.set_facecolor("#ffffff")
            ax.set_facecolor("#f7f9f8")
            ax.axis("off")

            # Edges (coloured by project funder)
            for u, v in _G.edges():
                proj_node = u if _G.nodes[u].get("kind") == "proj" else v
                funder = _G.nodes[proj_node].get("funder", "Unknown")
                c = funder_color.get(funder, "#888")
                x0, y0 = pos[u]; x1, y1 = pos[v]
                ax.plot([x0, x1], [y0, y1], "-", color=c, alpha=0.22, lw=0.9, zorder=1)

            # Organisation nodes
            max_org_deg = max((_G.degree(n) for n in org_sorted), default=1)
            for n in org_sorted:
                x, y = pos[n]
                deg = _G.degree(n)
                size = 240 + 700 * (deg / max_org_deg)
                ax.scatter([x], [y], s=size, c=left_color, edgecolors="white", linewidths=2.2, zorder=3)
                label = _G.nodes[n]["label"].title()
                if len(label) > 38:
                    label = label[:36] + "…"
                ax.text(x - 0.08, y, label, ha="right", va="center",
                        fontsize=11, fontweight="bold", zorder=5)

            # Project nodes
            for n in proj_sorted:
                x, y = pos[n]
                meta = _G.nodes[n]
                c = funder_color.get(meta.get("funder", "Unknown"), "#888")
                ax.scatter([x], [y], s=110, c=c, edgecolors="white", linewidths=1.2,
                           zorder=3, marker="s")
                title = meta.get("label", "")
                short = title if len(title) <= 60 else title[:57] + "…"
                ax.text(x + 0.06, y, short, ha="left", va="center", fontsize=9, zorder=5)

            # Column headers
            ax.text(-1.0, 1.07, left_title, ha="center", va="bottom",
                    fontsize=15, fontweight="bold", color=left_color)
            ax.text(1.0, 1.07, right_title, ha="center", va="bottom",
                    fontsize=15, fontweight="bold", color="#333")

            legend_elems = [
                Line2D([0], [0], marker="s", color="w", markerfacecolor=funder_color[f],
                       markeredgecolor="white", markersize=11, label=f)
                for f in funders
            ]
            ax.legend(handles=legend_elems, loc="center left", bbox_to_anchor=(1.02, 0.5),
                      framealpha=0.95, fontsize=11, title="Funding council",
                      title_fontsize=12, edgecolor="#dddddd")

            ax.set_xlim(-2.6, 2.6)
            ax.set_ylim(-1.18, 1.18)
            plt.tight_layout(pad=0.4)

            buf_png = io.BytesIO()
            fig.savefig(buf_png, format="png", dpi=220, bbox_inches="tight", facecolor="white")
            buf_png.seek(0)
            buf_svg = io.BytesIO()
            fig.savefig(buf_svg, format="svg", bbox_inches="tight", facecolor="white")
            buf_svg.seek(0)
            plt.close(fig)
            return buf_png.getvalue(), buf_svg.getvalue()

        bp_sig = f"orgs={op_top_orgs}|projs={op_top_projects}|n={G_bp.number_of_nodes()}|e={G_bp.number_of_edges()}"
        bp_png, bp_svg = render_org_project_bipartite(G_bp, top_orgs_kept, bp_sig)
        st.image(bp_png, use_container_width=True)

        bp_dl1, bp_dl2 = st.columns(2)
        with bp_dl1:
            st.download_button(
                "📥 Download PNG (220 DPI)",
                data=bp_png,
                file_name="ukri_org_project_bipartite.png",
                mime="image/png",
            )
        with bp_dl2:
            st.download_button(
                "📥 Download SVG (vector)",
                data=bp_svg,
                file_name="ukri_org_project_bipartite.svg",
                mime="image/svg+xml",
            )

        n_orgs = sum(1 for n in G_bp.nodes if G_bp.nodes[n].get("kind") == "org")
        n_projs = sum(1 for n in G_bp.nodes if G_bp.nodes[n].get("kind") == "proj")
        st.caption(
            f"Showing {n_orgs} organisations and {n_projs} projects "
            f"({G_bp.number_of_edges()} participation edges). "
            f"Data source: per-project JSON files in `ukri/` — `organisationRoles` field."
        )

    # ── Graph 1c-bis: Theme–Project Bipartite Network (interdisciplinarity) ───
    st.markdown('<div class="section-header">Theme–Project Network (Interdisciplinary Sustainability Projects)</div>', unsafe_allow_html=True)
    st.caption(
        "Companion to the organisation–project network, but with sustainability **themes** "
        "on the left instead of organisations. Right column = projects classified under ≥2 "
        "themes (i.e. interdisciplinary). Edges link a project to every theme it addresses; "
        "a project fanning out to many themes is highly interdisciplinary, and each theme's "
        "node size ∝ the number of these cross-cutting projects it shares. "
        "Project colour = funding council."
    )

    tp_top_projects = st.slider("Top interdisciplinary projects", 15, 60, 30, key="tp_top_projects")

    @st.cache_data(show_spinner="Building theme–project bipartite network…")
    def build_theme_project_bipartite(top_projects_n: int):
        from data_processor import get_or_build_dataset as _load
        df_full = _load().assign(project_ref=lambda d: d["project_ref"].astype(str))
        inter = df_full[df_full["is_sustainability"] & (df_full["theme_count"] >= 2)].copy()
        if inter.empty:
            return None, [], {}
        inter = inter.sort_values(["theme_count", "fund_value"], ascending=[False, False])
        top = inter.head(top_projects_n)

        G = nx.Graph()
        themes_present = set()
        for _, row in top.iterrows():
            ref = row["project_ref"]
            themes = [t.strip() for t in str(row["sustainability_themes"]).split(";") if t.strip()]
            if len(themes) < 2:
                continue
            title = str(row["title"]) if pd.notna(row["title"]) else ref
            funder = str(row["funder"]) if pd.notna(row["funder"]) else "Unknown"
            fv = float(row["fund_value"]) if pd.notna(row["fund_value"]) else 0.0
            G.add_node(("proj", ref), kind="proj", label=title, funder=funder, fund_value=fv, ref=ref)
            for th in themes:
                if ("org", th) not in G:
                    G.add_node(("org", th), kind="org", label=th)
                G.add_edge(("org", th), ("proj", ref))
                themes_present.add(th)
        return G, sorted(themes_present), {}

    G_tp, theme_nodes_kept, _tp_meta = build_theme_project_bipartite(tp_top_projects)

    if G_tp is None or len(G_tp) == 0:
        st.info("No multi-theme sustainability projects found in the current data.")
    else:
        tp_sig = f"themes|projs={tp_top_projects}|n={G_tp.number_of_nodes()}|e={G_tp.number_of_edges()}"
        tp_png, tp_svg = render_org_project_bipartite(
            G_tp, theme_nodes_kept, tp_sig,
            left_title="Sustainability Themes",
            right_title="Interdisciplinary Projects",
            left_color="#1a5438",
        )
        st.image(tp_png, use_container_width=True)

        tpdl1, tpdl2 = st.columns(2)
        with tpdl1:
            st.download_button(
                "📥 Download PNG (220 DPI)", data=tp_png,
                file_name="ukri_theme_project_bipartite.png",
                mime="image/png", key="tp_png_dl",
            )
        with tpdl2:
            st.download_button(
                "📥 Download SVG (vector)", data=tp_svg,
                file_name="ukri_theme_project_bipartite.svg",
                mime="image/svg+xml", key="tp_svg_dl",
            )

        n_th = sum(1 for n in G_tp.nodes if G_tp.nodes[n].get("kind") == "org")
        n_pr = sum(1 for n in G_tp.nodes if G_tp.nodes[n].get("kind") == "proj")
        st.caption(
            f"Showing {n_th} themes and {n_pr} interdisciplinary projects "
            f"({G_tp.number_of_edges()} theme–project edges). Every project shown spans ≥2 "
            "themes; those fanning out to the most themes are the most interdisciplinary."
        )

    # ── Graph 1d: Research Topic Co-occurrence Network (from JSON files) ──────
    st.markdown('<div class="section-header">Research Topic Co-occurrence Network</div>', unsafe_allow_html=True)
    st.caption(
        "Built from the `researchTopics` and `researchSubjects` classifications in "
        "every project's JSON file, with placeholder labels "
        "(`See subject area`, `Unclassified`, etc.) filtered out. Two tags are connected "
        "if they appear together on the same project; edge weight = number of shared "
        "projects. **Node size ∝ fractionally attributed funding** — each project's "
        "funding is split equally among all its declared tags before summing, so a "
        "multi-discipline £10M consortium grant carrying 5 tags contributes £2M to each "
        "tag rather than £10M each. This correction removes the bibliometric inflation "
        "that previously made broad social-science tags look richer per project than "
        "narrower engineering tags. Communities (colours) are detected by greedy "
        "modularity."
    )

    tc1, tc2, tc3 = st.columns(3)
    with tc1:
        topic_kind = st.selectbox(
            "Tag type", ["Topics + Subjects", "Topics only", "Subjects only"],
            index=0, key="topic_kind",
        )
    with tc2:
        topic_top_n = st.slider("Top tags", 20, 60, 35, key="topic_top_n")
    with tc3:
        topic_min_w = st.slider("Min shared projects", 2, 15, 4, key="topic_min_w")
    topic_sustain_only = st.checkbox(
        "Restrict to sustainability-classified projects", value=False, key="topic_sustain"
    )

    @st.cache_data(show_spinner="Loading topic index from JSON files…")
    def load_topic_index_cached():
        from data_processor import get_or_build_topic_index
        return get_or_build_topic_index()

    @st.cache_data(show_spinner="Building topic co-occurrence graph…")
    def build_topic_cooccurrence(kind_filter: str, top_n: int, min_w: int, sus_only: bool):
        from data_processor import get_or_build_dataset as _load
        df_full = _load().assign(project_ref=lambda d: d["project_ref"].astype(str))
        ti = load_topic_index_cached().assign(project_ref=lambda d: d["project_ref"].astype(str)).copy()
        if kind_filter == "Topics only":
            ti = ti[ti["kind"] == "topic"]
        elif kind_filter == "Subjects only":
            ti = ti[ti["kind"] == "subject"]
        if sus_only:
            sus_refs = set(df_full.loc[df_full["is_sustainability"], "project_ref"])
            ti = ti[ti["project_ref"].isin(sus_refs)]
        if ti.empty:
            return None
        tag_counts = ti.groupby("tag")["project_ref"].nunique().sort_values(ascending=False)
        top_tags = set(tag_counts.head(top_n).index)
        ti_f = ti[ti["tag"].isin(top_tags)]
        # FRACTIONAL funding attribution. Each project's funding is divided
        # equally among ALL its declared tags (across the full taxonomy, not
        # just the top-N displayed). So a £10M consortium grant carrying 5
        # topic tags contributes £2M to each tag, not £10M to each. This
        # removes the bibliometric inflation where heavy-tagged multi-
        # discipline grants over-credit every tag they carry — which was
        # making broad social-science tags look richer per project than
        # narrow engineering tags.
        tags_per_project = ti.groupby("project_ref").size().to_dict()
        fund_lookup = df_full.set_index("project_ref")["fund_value"].to_dict()
        tag_funding: dict[str, float] = {}
        for tag, ref in (
            ti_f.drop_duplicates(["tag", "project_ref"])[["tag", "project_ref"]].itertuples(index=False)
        ):
            n_tags = max(tags_per_project.get(ref, 1), 1)
            proj_fund = float(fund_lookup.get(ref, 0) or 0)
            tag_funding[tag] = tag_funding.get(tag, 0.0) + proj_fund / n_tags
        G = nx.Graph()
        for tag in top_tags:
            G.add_node(tag,
                       count=int(tag_counts[tag]),
                       funding=tag_funding.get(tag, 0.0))
        proj_tags = ti_f.groupby("project_ref")["tag"].apply(lambda s: list(set(s)))
        for tags in proj_tags:
            if len(tags) < 2:
                continue
            for i in range(len(tags)):
                for j in range(i + 1, len(tags)):
                    u, v = tags[i], tags[j]
                    if G.has_edge(u, v):
                        G[u][v]["weight"] += 1
                    else:
                        G.add_edge(u, v, weight=1)
        G.remove_edges_from([(u, v) for u, v, d in G.edges(data=True) if d["weight"] < min_w])
        G.remove_nodes_from(list(nx.isolates(G)))
        if G.number_of_nodes() == 0:
            return None
        try:
            communities = list(nx.algorithms.community.greedy_modularity_communities(G))
        except Exception:
            communities = [set(G.nodes())]
        cmap = {n: i for i, comm in enumerate(communities) for n in comm}
        return G, cmap

    topic_result = build_topic_cooccurrence(topic_kind, topic_top_n, topic_min_w, topic_sustain_only)
    if topic_result is None:
        st.info(
            "No co-occurrences at the current threshold. "
            "Lower **Min shared projects** or include more tags."
        )
    else:
        G_topic, topic_cmap = topic_result

        @st.cache_data(show_spinner="Rendering topic network…")
        def render_topic_network(_G, _cmap, sig: str):
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import matplotlib.patches as mpatches
            import io
            PALETTE = [
                "#2166ac", "#d6604d", "#4dac26", "#8073ac", "#f1a340",
                "#01665e", "#c51b7d", "#5aae61", "#8c510a", "#7570b3",
            ]
            try:
                pos = nx.spring_layout(
                    _G, seed=42, k=1.4 / (max(len(_G), 1) ** 0.5),
                    iterations=140, weight="weight",
                )
            except Exception:
                pos = nx.circular_layout(_G)
            max_w = max((d["weight"] for _, _, d in _G.edges(data=True)), default=1)
            counts = {n: _G.nodes[n].get("count", 1) for n in _G.nodes}
            max_c = max(counts.values(), default=1)
            fundings = {n: _G.nodes[n].get("funding", 0.0) for n in _G.nodes}
            max_f = max(fundings.values(), default=1) or 1
            fig, ax = plt.subplots(figsize=(15, 11))
            fig.patch.set_facecolor("#ffffff")
            ax.set_facecolor("#f7f9f8")
            ax.set_aspect("equal")
            ax.axis("off")
            for u, v, d in sorted(_G.edges(data=True), key=lambda e: e[2]["weight"]):
                w = d["weight"]
                x0, y0 = pos[u]; x1, y1 = pos[v]
                cu = _cmap.get(u, 0); cv = _cmap.get(v, 0)
                if cu == cv:
                    color = PALETTE[cu % len(PALETTE)]
                    alpha = 0.40 + 0.45 * (w / max_w)
                else:
                    color = "#888888"
                    alpha = 0.25 + 0.35 * (w / max_w)
                # sqrt-style scaling makes mid-range weight differences more
                # visible than a linear ramp; baseline 2.0 px so even the
                # lightest edges read at a glance.
                lw = 2.0 + 11.0 * (w / max_w) ** 0.6
                ax.plot([x0, x1], [y0, y1], "-", color=color,
                        lw=lw, alpha=alpha, zorder=1, solid_capstyle="round")
            for n in _G.nodes:
                x, y = pos[n]
                color = PALETTE[_cmap.get(n, 0) % len(PALETTE)]
                # Node size ∝ total funding (sqrt-scaled so the largest topic
                # doesn't crowd the canvas while small ones stay legible).
                f_norm = (fundings[n] / max_f) ** 0.5 if max_f else 0
                size = 220 + 2400 * f_norm
                ax.scatter([x], [y], s=size, c=color,
                           edgecolors="white", linewidths=2.4, zorder=3)
            for n in _G.nodes:
                x, y = pos[n]
                short = n if len(n) <= 28 else n[:26] + "…"
                f_m = fundings[n] / 1e6
                if f_m >= 100:
                    f_str = f"£{f_m:.0f}M"
                elif f_m >= 1:
                    f_str = f"£{f_m:.1f}M"
                else:
                    f_str = f"£{f_m * 1000:.0f}k"
                label = f"{short}\n{f_str} · {counts[n]} proj"
                ax.text(x, y, label, fontsize=9, ha="center", va="center",
                        fontweight="bold", zorder=5,
                        bbox=dict(boxstyle="round,pad=0.24", facecolor="white",
                                  edgecolor="#c0c0c0", alpha=0.92, linewidth=0.6))
            comm_groups: dict[int, list[str]] = {}
            for n, cid in _cmap.items():
                comm_groups.setdefault(cid, []).append(n)
            legend_elems = [
                mpatches.Patch(facecolor=PALETTE[cid % len(PALETTE)], alpha=0.85,
                               edgecolor="white", linewidth=1.5,
                               label=f"Community {cid + 1}  ({len(members)} tags)")
                for cid, members in sorted(comm_groups.items())
            ]
            ax.legend(handles=legend_elems, loc="center left",
                      bbox_to_anchor=(1.02, 0.5), framealpha=0.95,
                      fontsize=11, title="Topic communities",
                      title_fontsize=12, edgecolor="#dddddd")
            plt.tight_layout(pad=0.4)
            buf_png = io.BytesIO()
            fig.savefig(buf_png, format="png", dpi=220, bbox_inches="tight", facecolor="white")
            buf_png.seek(0)
            buf_svg = io.BytesIO()
            fig.savefig(buf_svg, format="svg", bbox_inches="tight", facecolor="white")
            buf_svg.seek(0)
            plt.close(fig)
            return buf_png.getvalue(), buf_svg.getvalue()

        topic_sig = (
            f"kind={topic_kind}|n={topic_top_n}|w={topic_min_w}|sus={topic_sustain_only}"
            f"|nodes={G_topic.number_of_nodes()}|edges={G_topic.number_of_edges()}|fund=v3frac"
        )
        tpng, tsvg = render_topic_network(G_topic, topic_cmap, topic_sig)
        st.image(tpng, use_container_width=True)
        td1, td2 = st.columns(2)
        with td1:
            st.download_button("📥 Download PNG (220 DPI)", data=tpng,
                               file_name="ukri_topic_cooccurrence.png", mime="image/png")
        with td2:
            st.download_button("📥 Download SVG (vector)", data=tsvg,
                               file_name="ukri_topic_cooccurrence.svg", mime="image/svg+xml")
        st.caption(
            f"{G_topic.number_of_nodes()} tags, {G_topic.number_of_edges()} co-occurrence edges "
            f"(weight ≥ {topic_min_w}). Source: `researchTopics` & `researchSubjects` JSON fields."
        )

        # Tag-level funding table — reports ALL tags (not just the network's
        # top-N), using fractional attribution. The "In network" column marks
        # the tags that made the cut into the figure above.
        st.markdown(
            '<div class="section-header" style="margin-top:1.2rem">'
            'Tag-level fractional funding — all subjects'
            '</div>',
            unsafe_allow_html=True,
        )
        st.caption(
            "Every research topic / subject tag in the JSON corpus (after the "
            "current Tag-type and sustainability filters), with project funding "
            "divided equally among each project's declared tags before summing — "
            "so a £10M consortium grant carrying 6 tags contributes £1.67M to "
            "each. Placeholder labels (`See subject area`, `Unclassified`, etc.) "
            "are excluded. The **In network** column flags the top "
            f"{topic_top_n} tags that the figure above displays. "
            "Sort any column by clicking its header."
        )

        @st.cache_data(show_spinner="Computing all-tag funding table…")
        def build_full_topic_table(kind_filter: str, sus_only: bool, top_n_in_net: int):
            from data_processor import get_or_build_dataset as _load
            df_full = _load().assign(project_ref=lambda d: d["project_ref"].astype(str))
            ti_all = load_topic_index_cached().assign(project_ref=lambda d: d["project_ref"].astype(str)).copy()
            if kind_filter == "Topics only":
                ti_all = ti_all[ti_all["kind"] == "topic"]
            elif kind_filter == "Subjects only":
                ti_all = ti_all[ti_all["kind"] == "subject"]
            if sus_only:
                sus_refs = set(df_full.loc[df_full["is_sustainability"], "project_ref"])
                ti_all = ti_all[ti_all["project_ref"].isin(sus_refs)]
            if ti_all.empty:
                return pd.DataFrame()

            tag_counts_all = ti_all.groupby("tag")["project_ref"].nunique()
            tags_per_project_all = ti_all.groupby("project_ref").size().to_dict()
            fund_lookup_all = df_full.set_index("project_ref")["fund_value"].to_dict()
            tag_funding_all: dict[str, float] = {}
            for tag, ref in (
                ti_all.drop_duplicates(["tag", "project_ref"])[["tag", "project_ref"]].itertuples(index=False)
            ):
                n_t = max(tags_per_project_all.get(ref, 1), 1)
                pf = float(fund_lookup_all.get(ref, 0) or 0)
                tag_funding_all[tag] = tag_funding_all.get(tag, 0.0) + pf / n_t
            top_tags_in_net = set(tag_counts_all.sort_values(ascending=False).head(top_n_in_net).index)
            kinds_per_tag = ti_all.groupby("tag")["kind"].agg(
                lambda s: "both" if set(s) == {"topic", "subject"} else list(set(s))[0]
            ).to_dict()

            rows = []
            for tag, cnt in tag_counts_all.items():
                f = tag_funding_all.get(tag, 0.0)
                rows.append({
                    "Tag": tag,
                    "Kind": kinds_per_tag.get(tag, ""),
                    "Projects": int(cnt),
                    "Fractional funding (£M)": round(f / 1e6, 3),
                    "Avg/project (£M)": round(f / cnt / 1e6, 4) if cnt else 0.0,
                    "In network": "✓" if tag in top_tags_in_net else "",
                })
            return (
                pd.DataFrame(rows)
                  .sort_values("Fractional funding (£M)", ascending=False)
                  .reset_index(drop=True)
            )

        topic_table = build_full_topic_table(topic_kind, topic_sustain_only, topic_top_n)
        topic_table.index += 1
        st.dataframe(topic_table, use_container_width=True,
                     height=min(640, 40 + 36 * min(len(topic_table), 16)))

        in_net = int((topic_table["In network"] == "✓").sum())
        total_frac = topic_table["Fractional funding (£M)"].sum()
        st.caption(
            f"{len(topic_table)} unique tags ({in_net} shown in the network above) · "
            f"total fractional funding **£{total_frac:.0f} M** · "
            f"top tag by total fractional funding: **{topic_table.iloc[0]['Tag']}** "
            f"(£{topic_table.iloc[0]['Fractional funding (£M)']:.1f} M, "
            f"{topic_table.iloc[0]['Projects']} projects, "
            f"£{topic_table.iloc[0]['Avg/project (£M)']:.3f} M/project)."
        )

    # ── Graph 1e: Principal Investigator Collaboration Network ───────────────
    st.markdown('<div class="section-header">Principal Investigator Collaboration Network</div>', unsafe_allow_html=True)
    st.caption(
        "Connects researchers who appear together on the same UKRI project. "
        "Built from `personRoles` in the JSON files. By default, both Principal "
        "Investigators and Co-Investigators are included (most projects have a "
        "single PI, so PI-only edges are sparse — adding Co-Is reveals the "
        "richer collaboration structure). Edge weight = shared projects; "
        "node size ∝ total projects led or co-led."
    )

    pc1, pc2 = st.columns(2)
    with pc1:
        pi_top_n = st.slider("Top investigators", 20, 80, 40, key="pi_top_n")
    with pc2:
        pi_min_w = st.slider("Min shared projects", 1, 8, 1, key="pi_min_w")
    pc3, pc4 = st.columns(2)
    with pc3:
        pi_sustain_only = st.checkbox(
            "Restrict to sustainability projects", value=False, key="pi_sustain"
        )
    with pc4:
        pi_include_coi = st.checkbox(
            "Include Co-Investigators", value=True, key="pi_coi"
        )

    @st.cache_data(show_spinner="Loading person index from JSON files…")
    def load_person_index_cached():
        from data_processor import get_or_build_person_index
        return get_or_build_person_index()

    @st.cache_data(show_spinner="Building investigator collaboration graph…")
    def build_pi_collab(top_n: int, min_w: int, sus_only: bool, include_coi: bool):
        from data_processor import get_or_build_dataset as _load
        df_full = _load().assign(project_ref=lambda d: d["project_ref"].astype(str))
        pp = load_person_index_cached().assign(project_ref=lambda d: d["project_ref"].astype(str)).copy()
        roles = {"PRINCIPAL_INVESTIGATOR", "CO_INVESTIGATOR"} if include_coi else {"PRINCIPAL_INVESTIGATOR"}
        pp = pp[pp["role"].isin(roles)]
        if sus_only:
            sus_refs = set(df_full.loc[df_full["is_sustainability"], "project_ref"])
            pp = pp[pp["project_ref"].isin(sus_refs)]
        if pp.empty:
            return None

        person_proj_count = pp.groupby("full_name")["project_ref"].nunique()
        person_org = (
            pp.groupby(["full_name", "org_name"]).size().reset_index(name="n")
            .sort_values("n", ascending=False)
            .drop_duplicates("full_name").set_index("full_name")["org_name"].to_dict()
        )

        # Build the FULL co-investigation graph first, then pick the top-N most
        # connected people. Ranking by raw project count surfaces solo PIs with
        # no edges; ranking by weighted degree surfaces the actual collaborators.
        G_full = nx.Graph()
        proj_ppl = pp.groupby("project_ref")["full_name"].apply(lambda s: list(set(s)))
        for ppl in proj_ppl:
            if len(ppl) < 2:
                continue
            for i in range(len(ppl)):
                for j in range(i + 1, len(ppl)):
                    u, v = ppl[i], ppl[j]
                    if G_full.has_edge(u, v):
                        G_full[u][v]["weight"] += 1
                    else:
                        G_full.add_edge(u, v, weight=1)

        G_full.remove_edges_from(
            [(u, v) for u, v, d in G_full.edges(data=True) if d["weight"] < min_w]
        )
        if G_full.number_of_edges() == 0:
            return None

        weighted_deg = dict(G_full.degree(weight="weight"))
        top_people = [n for n, _ in sorted(weighted_deg.items(), key=lambda kv: -kv[1])[:top_n]]
        G = G_full.subgraph(top_people).copy()
        G.remove_nodes_from(list(nx.isolates(G)))
        if G.number_of_nodes() == 0:
            return None

        for n in G.nodes:
            G.nodes[n]["count"] = int(person_proj_count.get(n, 0))
            G.nodes[n]["org"] = person_org.get(n, "")

        try:
            communities = list(nx.algorithms.community.greedy_modularity_communities(G))
        except Exception:
            communities = [set(G.nodes)]
        cmap = {n: i for i, comm in enumerate(communities) for n in comm}
        return G, cmap

    pi_result = build_pi_collab(pi_top_n, pi_min_w, pi_sustain_only, pi_include_coi)
    if pi_result is None:
        st.info(
            "No co-investigator edges at the current threshold. "
            "Try lowering **Min shared projects**, increasing **Top investigators**, "
            "or enabling **Include Co-Investigators**."
        )
    else:
        G_pi, pi_cmap = pi_result

        @st.cache_data(show_spinner="Rendering PI network…")
        def render_pi_network(_G, _cmap, sig: str):
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import matplotlib.patches as mpatches
            import io
            PALETTE = [
                "#2166ac", "#d6604d", "#4dac26", "#8073ac", "#f1a340",
                "#01665e", "#c51b7d", "#5aae61", "#8c510a", "#7570b3",
            ]
            n_nodes = max(len(_G), 1)
            try:
                pos = nx.spring_layout(
                    _G, seed=7, k=2.6 / (n_nodes ** 0.5),
                    iterations=240, weight="weight",
                )
            except Exception:
                pos = nx.circular_layout(_G)

            # Post-process: push overlapping nodes apart so labels don't collide
            min_sep = max(0.18, 1.3 / (n_nodes ** 0.5))
            pa = {n: list(p) for n, p in pos.items()}
            nl = list(pa)
            for _ in range(120):
                moved = False
                for i in range(len(nl)):
                    for j in range(i + 1, len(nl)):
                        a, b = nl[i], nl[j]
                        dx = pa[b][0] - pa[a][0]
                        dy = pa[b][1] - pa[a][1]
                        d = max((dx ** 2 + dy ** 2) ** 0.5, 1e-6)
                        if d < min_sep:
                            push = (min_sep - d) / 2
                            ux, uy = dx / d, dy / d
                            pa[a][0] -= push * ux; pa[a][1] -= push * uy
                            pa[b][0] += push * ux; pa[b][1] += push * uy
                            moved = True
                if not moved:
                    break
            pos = {n: tuple(p) for n, p in pa.items()}

            max_w = max((d["weight"] for _, _, d in _G.edges(data=True)), default=1)
            counts = {n: _G.nodes[n].get("count", 1) for n in _G.nodes}
            max_c = max(counts.values(), default=1)

            # Community centroids (for label offsets)
            comm_members: dict[int, list[str]] = {}
            for n, cid in _cmap.items():
                comm_members.setdefault(cid, []).append(n)
            comm_centers = {
                cid: (
                    sum(pos[m][0] for m in members) / len(members),
                    sum(pos[m][1] for m in members) / len(members),
                )
                for cid, members in comm_members.items()
            }

            fig, ax = plt.subplots(figsize=(17, 13))
            fig.patch.set_facecolor("#ffffff")
            ax.set_facecolor("#f7f9f8")
            ax.set_aspect("equal")
            ax.axis("off")

            for u, v, d in sorted(_G.edges(data=True), key=lambda e: e[2]["weight"]):
                w = d["weight"]
                x0, y0 = pos[u]; x1, y1 = pos[v]
                cu = _cmap.get(u, 0); cv = _cmap.get(v, 0)
                if cu == cv:
                    color = PALETTE[cu % len(PALETTE)]
                    alpha = 0.55 + 0.35 * (w / max_w)
                else:
                    color = "#7a7a7a"
                    alpha = 0.40 + 0.30 * (w / max_w)
                ax.plot([x0, x1], [y0, y1], "-", color=color,
                        lw=1.0 + 3.0 * (w / max_w), alpha=alpha, zorder=1,
                        solid_capstyle="round")

            for n in _G.nodes:
                x, y = pos[n]
                color = PALETTE[_cmap.get(n, 0) % len(PALETTE)]
                size = 180 + 620 * (counts[n] / max_c)
                ax.scatter([x], [y], s=size, c=color,
                           edgecolors="white", linewidths=2.2, zorder=3)

            sorted_counts = sorted(counts.values(), reverse=True)
            top10 = sorted_counts[min(9, len(sorted_counts) - 1)] if sorted_counts else 1

            # Label placement: offset outward from community centroid so the
            # label sits beside (not on top of) its node and away from interior edges.
            for n in _G.nodes:
                x, y = pos[n]
                cid = _cmap.get(n, 0)
                cx_c, cy_c = comm_centers.get(cid, (0.0, 0.0))
                dx, dy = x - cx_c, y - cy_c
                dist = (dx ** 2 + dy ** 2) ** 0.5
                deg_n = _G.degree(n)
                # Smaller offset for the top-degree (central) nodes so they keep
                # the labelled position; larger for periphery.
                offset = max(0.06, 0.13 - 0.04 * (deg_n / max(max((_G.degree(m) for m in _G.nodes), default=1), 1)))
                if dist < 1e-3:
                    lx, ly = x, y - offset
                else:
                    lx = x + offset * dx / dist
                    ly = y + offset * dy / dist
                label = n if len(n) <= 24 else n[:22] + "…"
                bold = counts[n] >= top10
                ax.text(lx, ly, label, fontsize=9 if bold else 8,
                        fontweight="bold" if bold else "normal",
                        ha="center", va="center", zorder=5,
                        bbox=dict(boxstyle="round,pad=0.18", facecolor="white",
                                  edgecolor="#c8c8c8", alpha=0.93, linewidth=0.5))
            comm_groups: dict[int, list[str]] = {}
            for n, cid in _cmap.items():
                comm_groups.setdefault(cid, []).append(n)
            legend_elems = [
                mpatches.Patch(facecolor=PALETTE[cid % len(PALETTE)], alpha=0.85,
                               edgecolor="white", linewidth=1.5,
                               label=f"Community {cid + 1}  ({len(members)} researchers)")
                for cid, members in sorted(comm_groups.items())
            ]
            ax.legend(handles=legend_elems, loc="center left",
                      bbox_to_anchor=(1.02, 0.5), framealpha=0.95,
                      fontsize=11, title="Research clusters",
                      title_fontsize=12, edgecolor="#dddddd")
            plt.tight_layout(pad=0.4)
            buf_png = io.BytesIO()
            fig.savefig(buf_png, format="png", dpi=220, bbox_inches="tight", facecolor="white")
            buf_png.seek(0)
            buf_svg = io.BytesIO()
            fig.savefig(buf_svg, format="svg", bbox_inches="tight", facecolor="white")
            buf_svg.seek(0)
            plt.close(fig)
            return buf_png.getvalue(), buf_svg.getvalue()

        pi_sig = (
            f"n={pi_top_n}|w={pi_min_w}|sus={pi_sustain_only}|coi={pi_include_coi}"
            f"|nodes={G_pi.number_of_nodes()}|edges={G_pi.number_of_edges()}"
        )
        pi_png, pi_svg = render_pi_network(G_pi, pi_cmap, pi_sig)
        st.image(pi_png, use_container_width=True)
        pid1, pid2 = st.columns(2)
        with pid1:
            st.download_button("📥 Download PNG (220 DPI)", data=pi_png,
                               file_name="ukri_pi_collaboration.png", mime="image/png")
        with pid2:
            st.download_button("📥 Download SVG (vector)", data=pi_svg,
                               file_name="ukri_pi_collaboration.svg", mime="image/svg+xml")
        st.caption(
            f"{G_pi.number_of_nodes()} investigators, {G_pi.number_of_edges()} co-investigation edges "
            f"(weight ≥ {pi_min_w}). Source: `personRoles` JSON field."
        )

    # ── Graph 2: Sustainability Theme Co-occurrence Network ───────────────────
    st.markdown('<div class="section-header">Sustainability Theme Co-occurrence Network</div>', unsafe_allow_html=True)
    st.caption(
        "How the eight sustainability themes co-occur within projects. The **chord network** "
        "follows the **Weight by** toggle (project counts or total funding £): node size ∝ "
        "projects/funding under the theme, edge width ∝ shared projects or jointly-funded £. "
        "The **co-occurrence matrix** is shown both ways — by project count and by funding "
        "size (£M) — so you can compare them directly. Communities (colours, halos) are "
        "detected by greedy modularity on the weighted graph."
    )

    @st.cache_data(show_spinner="Building theme network…")
    def build_theme_network(_df_themes_col, _df_sus_themes_col, _fund_series):
        theme_list = list(SUSTAINABILITY_THEMES.keys())
        G_t = nx.Graph()
        for theme in theme_list:
            G_t.add_node(theme)
        for themes_str, fund in zip(_df_sus_themes_col, _fund_series.fillna(0)):
            themes = [t.strip() for t in str(themes_str).split(";") if t.strip()]
            for i in range(len(themes)):
                for j in range(i + 1, len(themes)):
                    u, v = themes[i], themes[j]
                    if u in G_t and v in G_t:
                        if G_t.has_edge(u, v):
                            G_t[u][v]["weight"] += 1
                            G_t[u][v]["funding"] += float(fund)
                        else:
                            G_t.add_edge(u, v, weight=1, funding=float(fund))
        for theme, col_key in zip(
            theme_list,
            [f"theme_{t.lower().replace(' ','_').replace('&','and')}" for t in theme_list],
        ):
            mask = _df_themes_col.get(col_key)
            if mask is not None:
                G_t.nodes[theme]["count"] = int(mask.sum())
                G_t.nodes[theme]["funding"] = float(_fund_series[mask].sum())
            else:
                G_t.nodes[theme]["count"] = 0
                G_t.nodes[theme]["funding"] = 0.0
        return G_t

    theme_col_series = {
        col: df_all[col] for col in df_all.columns if col.startswith("theme_") and col != "theme_count"
    }
    G_theme = build_theme_network(theme_col_series, df_all["sustainability_themes"], df_all["fund_value"])

    @st.cache_data(show_spinner="Rendering theme network…")
    def render_theme_network(_G, metric="projects"):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        from matplotlib.patches import FancyArrowPatch
        import io
        import math

        use_funding = metric == "funding"
        edge_key = "funding" if use_funding else "weight"

        def edge_val(d):
            return d.get(edge_key, 0)

        def fmt_edge(v):
            return f"£{v/1e6:.0f}M" if use_funding else f"{int(v)}"

        def node_val(n):
            return _G.nodes[n].get("funding" if use_funding else "count", 0)

        def fmt_node(v):
            return f"£{v/1e6:.0f}M" if use_funding else f"{int(v)} projects"

        PALETTE = [
            "#1b7837", "#5aae61", "#762a83", "#9970ab",
            "#d6604d", "#f1a340", "#4393c3", "#2166ac",
        ]

        try:
            communities = list(nx.algorithms.community.greedy_modularity_communities(_G))
        except Exception:
            communities = [set(_G.nodes())]
        cmap = {n: i for i, comm in enumerate(communities) for n in comm}
        comm_groups: dict[int, list[str]] = {}
        for n, cid in cmap.items():
            comm_groups.setdefault(cid, []).append(n)

        # Circular layout ordered by community (so same-community nodes are
        # adjacent on the ring — much cleaner for a small dense graph than
        # spring layout, which clumps everything to the centre).
        node_order = []
        for cid in sorted(comm_groups):
            node_order.extend(sorted(comm_groups[cid], key=lambda n: -_G.nodes[n].get("count", 0)))
        n_nodes = len(node_order)
        R = 1.0
        pos = {}
        for i, n in enumerate(node_order):
            theta = math.pi / 2 - 2 * math.pi * i / n_nodes  # start at top, go clockwise
            pos[n] = (R * math.cos(theta), R * math.sin(theta))

        max_w = max((edge_val(d) for _, _, d in _G.edges(data=True)), default=1) or 1
        counts = {n: node_val(n) for n in _G.nodes}
        max_c = max(counts.values(), default=1) or 1

        fig, ax = plt.subplots(figsize=(14, 11))
        fig.patch.set_facecolor("#ffffff")
        ax.set_facecolor("#fbfcfa")
        ax.set_aspect("equal")
        ax.axis("off")

        # Curved bezier edges — chord-diagram aesthetic. Curvature is
        # consistent so parallel chords don't visually pile.
        edges_sorted = sorted(_G.edges(data=True), key=lambda e: edge_val(e[2]))
        for u, v, d in edges_sorted:
            w = edge_val(d)
            cu = cmap.get(u, 0); cv = cmap.get(v, 0)
            if cu == cv:
                color = PALETTE[cu % len(PALETTE)]
                alpha = 0.55 + 0.35 * (w / max_w)
            else:
                color = "#888888"
                alpha = 0.30 + 0.40 * (w / max_w)
            lw = 1.0 + 8.5 * (w / max_w)
            arrow = FancyArrowPatch(
                pos[u], pos[v],
                connectionstyle="arc3,rad=0.18",
                arrowstyle="-",
                linewidth=lw, color=color, alpha=alpha,
                zorder=1, capstyle="round",
            )
            ax.add_patch(arrow)

        # Edge weight labels — show all edges, but smaller text for weak ones.
        # Bezier midpoint approximation for curved edges.
        median_edge = sorted([edge_val(e[2]) for e in edges_sorted])[len(edges_sorted) // 2]
        for u, v, d in edges_sorted:
            w = edge_val(d)
            x0, y0 = pos[u]; x1, y1 = pos[v]
            mx, my = (x0 + x1) / 2, (y0 + y1) / 2
            # Perpendicular offset matching the bezier curvature (rad=0.18)
            dx, dy = x1 - x0, y1 - y0
            length = (dx ** 2 + dy ** 2) ** 0.5 or 1e-6
            nx_, ny_ = -dy / length, dx / length
            curve_offset = 0.18 * length * 0.5
            lx, ly = mx + nx_ * curve_offset, my + ny_ * curve_offset
            # Bigger font + opaque bg for the top half of edges
            is_strong = w >= median_edge
            ax.text(lx, ly, fmt_edge(w),
                    fontsize=10 if is_strong else 8,
                    fontweight="bold" if is_strong else "normal",
                    ha="center", va="center",
                    color="#222" if is_strong else "#555", zorder=4,
                    bbox=dict(boxstyle="round,pad=0.18",
                              facecolor="#ffffff",
                              edgecolor="#bbb" if is_strong else "#dcdcdc",
                              alpha=0.93 if is_strong else 0.80,
                              linewidth=0.5))

        # Nodes
        for n in _G.nodes:
            x, y = pos[n]
            color = PALETTE[cmap.get(n, 0) % len(PALETTE)]
            size = 800 + 2200 * (counts[n] / max_c)
            ax.scatter([x], [y], s=size, c=color,
                       edgecolors="white", linewidths=3.4,
                       zorder=3, alpha=0.95)

        # Labels — pushed radially outward, rotated to align with the circle
        # tangent for that "around-a-clock-face" feel.
        for n in _G.nodes:
            x, y = pos[n]
            theta = math.atan2(y, x)
            label_r = 1.32
            lx, ly = label_r * math.cos(theta), label_r * math.sin(theta)
            # Decide ha based on which half of the circle the label sits on
            if math.cos(theta) > 0:
                ha = "left"
                rot = math.degrees(theta)
            else:
                ha = "right"
                rot = math.degrees(theta) + 180
            # Keep text upright for the top/bottom-most labels
            if abs(math.cos(theta)) < 0.15:
                rot = 0
                ha = "center"
            label = f"{n}\n({fmt_node(counts[n])})"
            ax.text(lx, ly, label, fontsize=11, ha=ha, va="center",
                    fontweight="bold", color="#1a3d2b",
                    rotation=rot, rotation_mode="anchor", zorder=5,
                    bbox=dict(boxstyle="round,pad=0.32", facecolor="white",
                              edgecolor="#b8b8b8", alpha=0.94, linewidth=0.7))

        # Generous margins so rotated labels don't clip
        ax.set_xlim(-2.3, 2.3)
        ax.set_ylim(-1.7, 1.7)

        legend_elems = [
            mpatches.Patch(facecolor=PALETTE[cid % len(PALETTE)], alpha=0.88,
                           edgecolor="white", linewidth=1.5,
                           label=f"Community {cid + 1}  ({len(members)} themes)")
            for cid, members in sorted(comm_groups.items())
        ]
        ax.legend(handles=legend_elems, loc="center left",
                  bbox_to_anchor=(1.02, 0.5), framealpha=0.95,
                  fontsize=12, title="Theme communities",
                  title_fontsize=13, edgecolor="#dddddd")

        plt.tight_layout(pad=0.4)
        buf_png = io.BytesIO()
        fig.savefig(buf_png, format="png", dpi=240, bbox_inches="tight", facecolor="white")
        buf_png.seek(0)
        buf_svg = io.BytesIO()
        fig.savefig(buf_svg, format="svg", bbox_inches="tight", facecolor="white")
        buf_svg.seek(0)
        plt.close(fig)
        return buf_png.getvalue(), buf_svg.getvalue()

    @st.cache_data(show_spinner="Rendering theme co-occurrence matrix…")
    def render_theme_matrix(_G, metric="projects"):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
        import io

        use_funding = metric == "funding"
        node_key = "funding" if use_funding else "count"
        edge_key = "funding" if use_funding else "weight"
        scale = 1e6 if use_funding else 1

        def fmt(v):
            return f"{v/1e6:.0f}" if use_funding else f"{int(v)}"

        nodes = sorted(_G.nodes(), key=lambda n: -_G.nodes[n].get(node_key, 0))
        N = len(nodes)
        M = np.zeros((N, N), dtype=float)
        for i, u in enumerate(nodes):
            for j, v in enumerate(nodes):
                if i == j:
                    M[i, j] = _G.nodes[u].get(node_key, 0)
                elif _G.has_edge(u, v):
                    M[i, j] = _G[u][v].get(edge_key, 0)

        fig, ax = plt.subplots(figsize=(10, 8.5))
        fig.patch.set_facecolor("#ffffff")
        cmap_obj = plt.cm.YlGn
        im = ax.imshow(M, cmap=cmap_obj, aspect="equal")
        # Diagonal styled distinctly (those are theme totals, not co-occurrences)
        for i in range(N):
            ax.add_patch(plt.Rectangle((i - 0.5, i - 0.5), 1, 1,
                                       fill=False, edgecolor="#333", linewidth=1.4, zorder=4))
        # Numeric annotations
        vmax = M.max() if M.max() > 0 else 1
        for i in range(N):
            for j in range(N):
                val = M[i, j]
                if val == 0:
                    continue
                color = "white" if val / vmax > 0.55 else "#1a3d2b"
                ax.text(j, i, fmt(val), ha="center", va="center",
                        fontsize=10, fontweight="bold" if i == j else "normal",
                        color=color, zorder=5)
        ax.set_xticks(range(N))
        ax.set_yticks(range(N))
        ax.set_xticklabels(nodes, rotation=40, ha="right", fontsize=10)
        ax.set_yticklabels(nodes, fontsize=10)
        ax.set_xlabel("")
        ax.set_ylabel("")
        diag_label = "total funding £M per theme" if use_funding else "total projects per theme"
        ax.set_title(f"Theme co-occurrence matrix  ·  diagonal = {diag_label}",
                     fontsize=12, color="#333", pad=12)
        cbar = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
        cbar.set_label("Shared funding (£M)" if use_funding else "Shared projects", fontsize=10)
        plt.tight_layout(pad=0.4)
        buf_png = io.BytesIO()
        fig.savefig(buf_png, format="png", dpi=220, bbox_inches="tight", facecolor="white")
        buf_png.seek(0)
        buf_svg = io.BytesIO()
        fig.savefig(buf_svg, format="svg", bbox_inches="tight", facecolor="white")
        buf_svg.seek(0)
        plt.close(fig)
        return buf_png.getvalue(), buf_svg.getvalue()

    if G_theme.number_of_edges() == 0:
        st.info("No theme co-occurrences in the current filter — projects classified under a single theme only.")
    else:
        tv_col, tm_col = st.columns(2)
        with tv_col:
            theme_view = st.radio(
                "View",
                ["Chord network", "Co-occurrence matrix", "Both"],
                index=2, horizontal=True, key="theme_view",
            )
        with tm_col:
            theme_metric_label = st.radio(
                "Weight by",
                ["Projects", "Funding (£)"],
                index=0, horizontal=True, key="theme_metric",
            )
        theme_metric = "funding" if theme_metric_label.startswith("Funding") else "projects"

        if theme_view in ("Chord network", "Both"):
            theme_png, theme_svg = render_theme_network(G_theme, theme_metric)
            st.image(theme_png, use_container_width=True)
            thd1, thd2 = st.columns(2)
            with thd1:
                st.download_button("📥 Download network PNG", data=theme_png,
                                   file_name="ukri_theme_cooccurrence_network.png", mime="image/png")
            with thd2:
                st.download_button("📥 Download network SVG", data=theme_svg,
                                   file_name="ukri_theme_cooccurrence_network.svg", mime="image/svg+xml")

        if theme_view in ("Co-occurrence matrix", "Both"):
            # Project-count matrix
            st.markdown('<div style="font-weight:600;color:#2e7d5e;margin-top:0.3rem">By project count</div>', unsafe_allow_html=True)
            mat_png, mat_svg = render_theme_matrix(G_theme, "projects")
            st.image(mat_png, use_container_width=True)
            mthd1, mthd2 = st.columns(2)
            with mthd1:
                st.download_button("📥 Download matrix PNG", data=mat_png,
                                   file_name="ukri_theme_cooccurrence_matrix.png", mime="image/png",
                                   key="theme_mat_png")
            with mthd2:
                st.download_button("📥 Download matrix SVG", data=mat_svg,
                                   file_name="ukri_theme_cooccurrence_matrix.svg", mime="image/svg+xml",
                                   key="theme_mat_svg")

            # Funding matrix (companion)
            st.markdown('<div style="font-weight:600;color:#2e7d5e;margin-top:0.6rem">By funding size (£M)</div>', unsafe_allow_html=True)
            matf_png, matf_svg = render_theme_matrix(G_theme, "funding")
            st.image(matf_png, use_container_width=True)
            mfhd1, mfhd2 = st.columns(2)
            with mfhd1:
                st.download_button("📥 Download funding matrix PNG", data=matf_png,
                                   file_name="ukri_theme_cooccurrence_matrix_funding.png", mime="image/png",
                                   key="theme_matf_png")
            with mfhd2:
                st.download_button("📥 Download funding matrix SVG", data=matf_svg,
                                   file_name="ukri_theme_cooccurrence_matrix_funding.svg", mime="image/svg+xml",
                                   key="theme_matf_svg")

        pair_col1, pair_col2 = st.columns(2)
        with pair_col1:
            edge_rows = [
                {"Theme A": u, "Theme B": v, "Shared projects": d["weight"]}
                for u, v, d in sorted(G_theme.edges(data=True), key=lambda e: -e[2]["weight"])[:8]
            ]
            if edge_rows:
                st.markdown(
                    '<div style="font-size:0.85rem;color:#666;margin-top:0.4rem">Top theme pairings — by shared projects</div>',
                    unsafe_allow_html=True,
                )
                st.dataframe(pd.DataFrame(edge_rows), use_container_width=True, hide_index=True)
        with pair_col2:
            edge_rows_fund = [
                {"Theme A": u, "Theme B": v, "Shared funding (£M)": round(d.get("funding", 0) / 1e6, 1)}
                for u, v, d in sorted(G_theme.edges(data=True), key=lambda e: -e[2].get("funding", 0))[:8]
            ]
            if edge_rows_fund:
                st.markdown(
                    '<div style="font-size:0.85rem;color:#666;margin-top:0.4rem">Top theme pairings — by shared funding</div>',
                    unsafe_allow_html=True,
                )
                st.dataframe(pd.DataFrame(edge_rows_fund), use_container_width=True, hide_index=True)

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

    # ── Graph 3b: Funder Group × Sustainability Theme funding map ──────────────
    st.markdown('<div class="section-header">Funder Group × Sustainability Theme (Funding £M)</div>', unsafe_allow_html=True)
    st.caption(
        "Funders categorised into families — UKRI Research Councils (AHRC, BBSRC, EPSRC, "
        "ESRC, MRC, NERC, STFC); Innovate UK (incl. ATI, APC); UKRI strategic & "
        "infrastructure funds (ISCF, SPF, UKRI FLF, Infrastructure Fund, COVID …); EU & "
        "international/ODA funds (Horizon Europe Guarantee, GCRF, Newton, ISPF, Ayrton …); "
        "and UK government departments (DBT, DEFRA). Cells show total funding (£M) each "
        "group commits to each sustainability theme — which funder families drive which themes."
    )

    FUNDER_GROUP_MAP = {
        "AHRC": "UKRI Research Councils", "BBSRC": "UKRI Research Councils",
        "EPSRC": "UKRI Research Councils", "ESRC": "UKRI Research Councils",
        "MRC": "UKRI Research Councils", "NERC": "UKRI Research Councils",
        "STFC": "UKRI Research Councils",
        "Innovate UK": "Innovate UK", "ATI": "Innovate UK", "APC": "Innovate UK",
        "Other NPIF": "Innovate UK",
        "ISCF": "UKRI Strategic & Infrastructure", "SPF": "UKRI Strategic & Infrastructure",
        "UKRI": "UKRI Strategic & Infrastructure", "UKRI FLF": "UKRI Strategic & Infrastructure",
        "Infrastructure Fund": "UKRI Strategic & Infrastructure",
        "UKRI CRCRM": "UKRI Strategic & Infrastructure",
        "UKRI Inn.Scholar": "UKRI Strategic & Infrastructure",
        "DRI": "UKRI Strategic & Infrastructure", "TMF": "UKRI Strategic & Infrastructure",
        "COVID": "UKRI Strategic & Infrastructure", "NC3Rs": "UKRI Strategic & Infrastructure",
        "Horizon Europe Guarantee": "EU & International", "EU": "EU & International",
        "GCRF": "EU & International", "Newton Fund": "EU & International",
        "ISPF": "EU & International", "Ayrton Fund": "EU & International",
        "FIC": "EU & International", "UUI": "EU & International", "SiPF": "EU & International",
        "DBT": "UK Government Depts", "DEFRA": "UK Government Depts",
    }
    GROUP_ORDER = [
        "UKRI Research Councils", "Innovate UK", "UKRI Strategic & Infrastructure",
        "EU & International", "UK Government Depts", "Other",
    ]

    fg_df = df.copy()
    fg_df["funder_group"] = fg_df["funder"].map(FUNDER_GROUP_MAP).fillna("Other")
    fg_rows = []
    for theme in SUSTAINABILITY_THEMES:
        col_key = "theme_" + theme.lower().replace(" ", "_").replace("&", "and")
        if col_key not in fg_df.columns:
            continue
        sub = fg_df[fg_df[col_key]].groupby("funder_group")["fund_value"].sum() / 1e6
        for grp, val in sub.items():
            fg_rows.append({"group": grp, "theme": theme, "funding_M": val})

    if fg_rows:
        fg_long = pd.DataFrame(fg_rows)
        fg_pivot = fg_long.pivot(index="group", columns="theme", values="funding_M").fillna(0)
        fg_pivot = fg_pivot.reindex([g for g in GROUP_ORDER if g in fg_pivot.index])

        fig_fg = px.imshow(
            fg_pivot, aspect="auto", color_continuous_scale="YlOrRd",
            labels=dict(color="£M"), template="plotly_white", text_auto=".0f",
        )
        fig_fg.update_layout(height=320, margin=dict(t=10))
        _chart(fig_fg, "ukri_funder_group_theme_funding")

        # Row-normalised: each group's thematic emphasis (% of its theme-attributed funding)
        st.markdown(
            '<div style="font-weight:600;color:#2e7d5e;margin-top:0.4rem">'
            "Thematic emphasis — share of each group's funding (%)</div>",
            unsafe_allow_html=True,
        )
        fg_pct = fg_pivot.div(fg_pivot.sum(axis=1).replace(0, 1), axis=0) * 100
        fig_fg_pct = px.imshow(
            fg_pct, aspect="auto", color_continuous_scale="Greens",
            labels=dict(color="%"), template="plotly_white", text_auto=".0f",
        )
        fig_fg_pct.update_layout(height=320, margin=dict(t=10))
        _chart(fig_fg_pct, "ukri_funder_group_theme_share")


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
            color_continuous_scale="Tealgrn",
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
    pub_scat = df[(df["publication_count"] > 0) & df["fund_value"].notna() & (df["fund_value"] > 0)].copy()
    if pub_scat.empty:
        st.info("No projects with both publication counts and grant values in the current filter.")
    else:
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
    "Projects: 16,128 · "
    "Analysis: keyword classification across 8 sustainability themes · "
    "Dashboard built for *Nature Sustainability* submission</small>",
    unsafe_allow_html=True,
)
