"""
UKRI Sustainability Research Data Processor
Merges Excel project metadata with JSON rich project data.
Classifies projects by sustainability theme via keyword matching.
Run directly to regenerate processed_data.pkl cache.
"""

import pandas as pd
import json
import os
import urllib.parse
import pickle
from pathlib import Path
from datetime import datetime

EXCEL_PATH = Path(__file__).parent / "UKRI_Projects_Partially_Cleaned.xlsx"
JSON_DIR = Path(__file__).parent / "ukri"
CACHE_PATH = Path(__file__).parent / "processed_data.pkl"

SUSTAINABILITY_THEMES = {
    "Climate & Carbon": [
        "climate change", "climate crisis", "global warming", "carbon",
        "greenhouse gas", "co2", "net zero", "net-zero", "decarbonisation",
        "decarbonization", "carbon capture", "carbon sequestration", "methane",
        "climate adaptation", "climate mitigation", "paris agreement",
    ],
    "Clean Energy": [
        "renewable energy", "solar energy", "solar cell", "solar panel",
        "wind energy", "wind turbine", "offshore wind", "hydrogen energy",
        "energy storage", "battery storage", "fuel cell", "photovoltaic",
        "energy transition", "clean energy", "low carbon energy",
        "nuclear fusion", "tidal energy", "geothermal",
    ],
    "Environment & Ecology": [
        "biodiversity", "ecosystem", "ecological", "conservation",
        "habitat loss", "species extinction", "wildlife", "nature-based",
        "rewilding", "deforestation", "land degradation", "pollution",
        "air quality", "microplastic", "environmental impact",
    ],
    "Water & Oceans": [
        "water quality", "water security", "water resource", "ocean",
        "marine ecosystem", "coastal", "freshwater", "flood risk",
        "drought", "hydrological", "wastewater", "blue carbon",
        "coral reef", "sea level", "ocean acidification",
    ],
    "Food & Agriculture": [
        "food security", "food system", "sustainable agriculture",
        "agroecology", "crop resilience", "soil health", "soil carbon",
        "land use", "food waste", "precision agriculture", "agri-environment",
        "sustainable farming", "food production", "agricultural sustainability",
    ],
    "Circular Economy": [
        "circular economy", "recycling", "waste reduction", "plastic pollution",
        "sustainable materials", "resource efficiency", "reuse", "bioplastic",
        "industrial ecology", "cradle to cradle", "end of life", "upcycling",
        "sustainable manufacturing", "material recovery",
    ],
    "Sustainable Cities": [
        "sustainable city", "urban sustainability", "smart city",
        "urban planning", "transport decarbonisation", "built environment",
        "green infrastructure", "urban heat", "sustainable transport",
        "active travel", "electric vehicle", "zero emission",
    ],
    "Social Sustainability": [
        "environmental justice", "sustainable development", "sdg",
        "just transition", "community resilience", "health inequality",
        "climate justice", "green jobs", "low income", "vulnerable communities",
        "sustainability governance", "sustainability policy",
    ],
}


def classify_sustainability(text: str) -> list[str]:
    """Return list of sustainability themes found in text."""
    if not text:
        return []
    text_lower = text.lower()
    themes = []
    for theme, keywords in SUSTAINABILITY_THEMES.items():
        if any(kw in text_lower for kw in keywords):
            themes.append(theme)
    return themes


def load_json_project(ref: str) -> dict:
    """Load JSON file for a project reference. Returns empty dict if not found."""
    encoded = urllib.parse.quote(str(ref), safe="") + ".json"
    path = JSON_DIR / encoded
    if not path.exists():
        path = JSON_DIR / (str(ref) + ".json")
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("projectOverview", {}).get("projectComposition", {}).get("project", {})
    except Exception:
        return {}


def build_dataset() -> pd.DataFrame:
    """Build full merged dataset from Excel + JSON files."""
    print("Loading Excel file...")
    df = pd.read_excel(EXCEL_PATH, engine="openpyxl")

    # Standardise column names
    col_map = {}
    for c in df.columns:
        if "Fund value" in c:
            col_map[c] = "fund_value"
        elif "Offer grant" in c:
            col_map[c] = "offer_grant"
        elif "Project cost" in c:
            col_map[c] = "project_cost"
        elif "Investigators" in c:
            col_map[c] = "investigators"
        elif "Additional organisations" in c and "Corrected" not in c:
            col_map[c] = "additional_orgs"
        elif "Corrected additional" in c:
            col_map[c] = "corrected_additional_orgs"
    df = df.rename(columns=col_map)
    df = df.rename(columns={
        "Project reference": "project_ref",
        "Project ID": "project_id",
        "GTR Project URL": "url",
        "Title": "title",
        "Start Date": "start_date",
        "End Date": "end_date",
        "Region": "region",
        "Status": "status",
        "Lead RO Name": "lead_ro",
        "Corrected Lead RO Name": "corrected_lead_ro",
        "Lead RO ID": "lead_ro_id",
        "Department": "department",
        "Funding Org ID": "funder_id",
        "Funding Org Name": "funder",
    })

    # Numeric funding
    for col in ["fund_value", "offer_grant", "project_cost"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Dates
    for col in ["start_date", "end_date"]:
        df[col] = pd.to_datetime(df[col], errors="coerce")
    df["start_year"] = df["start_date"].dt.year
    df["end_year"] = df["end_date"].dt.year
    df["duration_years"] = (
        (df["end_date"] - df["start_date"]).dt.days / 365.25
    ).round(1)

    # Institution name normalisation (use corrected if available)
    df["institution"] = df["corrected_lead_ro"].fillna(df["lead_ro"]).str.strip()

    # Collaboration count
    def count_orgs(val):
        if pd.isna(val) or str(val).strip() == "":
            return 0
        return len([x for x in str(val).split(";") if x.strip()])

    df["collab_count"] = df.get("corrected_additional_orgs", df.get("additional_orgs", pd.Series())).apply(count_orgs)

    # Enrich from JSON
    print(f"Loading JSON data for {len(df)} projects...")
    abstracts, subjects, topics, health_cats, publications, grant_cats, tech_summaries = (
        [], [], [], [], [], [], []
    )

    for i, row in df.iterrows():
        proj = load_json_project(row["project_ref"])
        abstracts.append(proj.get("abstractText") or "")
        subjects.append(
            "; ".join(s.get("text", "") for s in proj.get("researchSubjects", []))
        )
        topics.append(
            "; ".join(t.get("text", "") for t in proj.get("researchTopics", []) if t.get("text") != "Unclassified")
        )
        health_cats.append(
            "; ".join(h.get("text", "") for h in proj.get("healthCategories", []))
        )
        publications.append(len(proj.get("publications", [])))
        grant_cats.append(proj.get("grantCategory") or "")
        tech_summaries.append(proj.get("technicalSummary") or "")

        if (i + 1) % 200 == 0:
            print(f"  Processed {i + 1}/{len(df)}...")

    df["abstract"] = abstracts
    df["research_subjects"] = subjects
    df["research_topics"] = topics
    df["health_categories"] = health_cats
    df["publication_count"] = publications
    df["grant_category"] = grant_cats
    df["technical_summary"] = tech_summaries

    # Sustainability classification
    print("Classifying sustainability themes...")
    combined_text = df["title"].fillna("") + " " + df["abstract"].fillna("")

    theme_cols = {}
    all_themes = []
    for theme in SUSTAINABILITY_THEMES:
        mask = combined_text.apply(lambda t, th=theme: th in classify_sustainability(t))
        theme_cols[f"theme_{theme.lower().replace(' ', '_').replace('&', 'and')}"] = mask
        all_themes.append(mask)

    for col, mask in theme_cols.items():
        df[col] = mask

    df["is_sustainability"] = pd.concat(all_themes, axis=1).any(axis=1)
    df["sustainability_themes"] = combined_text.apply(
        lambda t: "; ".join(classify_sustainability(t))
    )
    df["theme_count"] = df["sustainability_themes"].apply(
        lambda t: len([x for x in t.split(";") if x.strip()]) if t else 0
    )

    # UK nation derived from region
    nation_map = {
        "Scotland": "Scotland",
        "Wales": "Wales",
        "Northern Ireland": "Northern Ireland",
    }
    english_regions = {
        "London", "South East", "South West", "East of England",
        "East Midlands", "West Midlands", "Yorkshire and The Humber",
        "North West", "North East",
    }

    def get_nation(region):
        if region in nation_map:
            return nation_map[region]
        if region in english_regions:
            return "England"
        return "Unknown"

    df["nation"] = df["region"].apply(get_nation)

    print(f"Dataset complete: {len(df)} projects, {df['is_sustainability'].sum()} sustainability-related")
    return df


def get_or_build_dataset(force_rebuild: bool = False) -> pd.DataFrame:
    if CACHE_PATH.exists() and not force_rebuild:
        print("Loading cached dataset...")
        with open(CACHE_PATH, "rb") as f:
            return pickle.load(f)
    df = build_dataset()
    with open(CACHE_PATH, "wb") as f:
        pickle.dump(df, f)
    print(f"Cached to {CACHE_PATH}")
    return df


if __name__ == "__main__":
    df = get_or_build_dataset(force_rebuild=True)
    print("\nDataset summary:")
    print(df[["project_ref", "title", "funder", "fund_value", "start_year",
              "region", "is_sustainability", "sustainability_themes",
              "publication_count"]].head(10).to_string())
    print(f"\nTotal funding: £{df['fund_value'].sum():,.0f}")
    print(f"Sustainability projects: {df['is_sustainability'].sum()} / {len(df)}")
    print(f"Funders: {df['funder'].value_counts().to_dict()}")
