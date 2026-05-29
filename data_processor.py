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
ORG_INDEX_PATH = Path(__file__).parent / "org_participation.pkl"
TOPIC_INDEX_PATH = Path(__file__).parent / "topic_participation.pkl"
PERSON_INDEX_PATH = Path(__file__).parent / "person_participation.pkl"

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


def build_org_participation_index() -> pd.DataFrame:
    """Walk every project JSON and extract organisation-level participation.

    Returns one row per (project, organisation) with columns:
      project_ref, org_id, org_name, region, roles (comma-sep), offer_grant, project_cost.
    """
    json_root = JSON_DIR / "ukri" if (JSON_DIR / "ukri").exists() else JSON_DIR
    files = [f for f in json_root.iterdir() if f.suffix == ".json"]
    print(f"Indexing organisation participation across {len(files)} JSON files...")
    rows = []
    for i, f in enumerate(files):
        try:
            with open(f, encoding="utf-8") as fp:
                data = json.load(fp)
            pc = data.get("projectOverview", {}).get("projectComposition", {})
            proj = pc.get("project", {}) or {}
            ref = proj.get("grantReference") or f.stem
            for r in pc.get("organisationRoles", []) or []:
                addr = r.get("address") or {}
                rows.append({
                    "project_ref": str(ref),
                    "org_id": r.get("id"),
                    "org_name": (r.get("name") or "").strip(),
                    "region": addr.get("region") or "Unknown",
                    "roles": ",".join((x.get("name") or "") for x in (r.get("roles") or [])),
                    "offer_grant": r.get("offerGrant"),
                    "project_cost": r.get("projectCost"),
                })
        except Exception:
            continue
        if (i + 1) % 2000 == 0:
            print(f"  {i + 1}/{len(files)} files processed...")
    return pd.DataFrame(rows)


def get_or_build_org_index(force_rebuild: bool = False) -> pd.DataFrame:
    if ORG_INDEX_PATH.exists() and not force_rebuild:
        with open(ORG_INDEX_PATH, "rb") as f:
            return pickle.load(f)
    df = build_org_participation_index()
    with open(ORG_INDEX_PATH, "wb") as f:
        pickle.dump(df, f)
    print(f"Cached org participation index to {ORG_INDEX_PATH} ({len(df)} rows)")
    return df


# Placeholder tags used by UKRI when topic classification is deferred or
# absent. These are taxonomy artifacts, not real research topics, and badly
# distort topic-level funding analysis if left in. The 'See subject area'
# tag alone covers 280 projects with a mean award of £7.76M (mostly EPSRC
# fellowships and large strategic-priority awards).
TOPIC_PLACEHOLDERS = {
    "unclassified",
    "see subject area",
    "see research areas",
    "not yet classified",
    "other",
}


def build_topic_index() -> pd.DataFrame:
    """Walk every project JSON and extract research topic / subject tags.

    Returns one row per (project, tag) with columns:
      project_ref, tag, kind ('topic' | 'subject'), percentage.
    Drops placeholder tags (see TOPIC_PLACEHOLDERS) that represent deferred
    or absent classification rather than real topics.
    """
    json_root = JSON_DIR / "ukri" if (JSON_DIR / "ukri").exists() else JSON_DIR
    files = [f for f in json_root.iterdir() if f.suffix == ".json"]
    print(f"Indexing research topics/subjects across {len(files)} JSON files...")
    rows = []
    for i, f in enumerate(files):
        try:
            with open(f, encoding="utf-8") as fp:
                data = json.load(fp)
            proj = (
                data.get("projectOverview", {})
                    .get("projectComposition", {})
                    .get("project", {}) or {}
            )
            ref = proj.get("grantReference") or f.stem
            for t in proj.get("researchTopics", []) or []:
                tag = (t.get("text") or "").strip()
                if tag and tag.lower() not in TOPIC_PLACEHOLDERS:
                    rows.append({
                        "project_ref": str(ref),
                        "tag": tag,
                        "kind": "topic",
                        "percentage": t.get("percentage"),
                    })
            for s in proj.get("researchSubjects", []) or []:
                tag = (s.get("text") or "").strip()
                if tag and tag.lower() not in TOPIC_PLACEHOLDERS:
                    rows.append({
                        "project_ref": str(ref),
                        "tag": tag,
                        "kind": "subject",
                        "percentage": s.get("percentage"),
                    })
        except Exception:
            continue
        if (i + 1) % 2000 == 0:
            print(f"  {i + 1}/{len(files)} files processed...")
    return pd.DataFrame(rows)


def get_or_build_topic_index(force_rebuild: bool = False) -> pd.DataFrame:
    if TOPIC_INDEX_PATH.exists() and not force_rebuild:
        with open(TOPIC_INDEX_PATH, "rb") as f:
            return pickle.load(f)
    df = build_topic_index()
    with open(TOPIC_INDEX_PATH, "wb") as f:
        pickle.dump(df, f)
    print(f"Cached topic index to {TOPIC_INDEX_PATH} ({len(df)} rows)")
    return df


def build_person_index() -> pd.DataFrame:
    """Walk every project JSON and extract people + their roles per project.

    Returns one row per (project, person) with columns:
      project_ref, person_id, full_name, role, org_name.
    role ∈ {PRINCIPAL_INVESTIGATOR, CO_INVESTIGATOR, FELLOW, RESEARCHER, ...}.
    A person may appear multiple times if they hold multiple roles.
    """
    json_root = JSON_DIR / "ukri" if (JSON_DIR / "ukri").exists() else JSON_DIR
    files = [f for f in json_root.iterdir() if f.suffix == ".json"]
    print(f"Indexing person participation across {len(files)} JSON files...")
    rows = []
    for i, f in enumerate(files):
        try:
            with open(f, encoding="utf-8") as fp:
                data = json.load(fp)
            pc = data.get("projectOverview", {}).get("projectComposition", {}) or {}
            proj = pc.get("project", {}) or {}
            ref = str(proj.get("grantReference") or f.stem)
            lead_org = (pc.get("leadResearchOrganisation") or {}).get("name") or ""
            for r in pc.get("personRoles", []) or []:
                full = (r.get("fullName") or
                        f"{r.get('firstName','')} {r.get('surname','')}".strip())
                if not full or full == " ":
                    continue
                pid = r.get("id")
                for role in (r.get("roles") or []):
                    rname = role.get("name") or ""
                    if not rname:
                        continue
                    rows.append({
                        "project_ref": ref,
                        "person_id": pid,
                        "full_name": full.strip(),
                        "role": rname,
                        "org_name": lead_org.strip(),
                    })
        except Exception:
            continue
        if (i + 1) % 2000 == 0:
            print(f"  {i + 1}/{len(files)} files processed...")
    return pd.DataFrame(rows)


def get_or_build_person_index(force_rebuild: bool = False) -> pd.DataFrame:
    if PERSON_INDEX_PATH.exists() and not force_rebuild:
        with open(PERSON_INDEX_PATH, "rb") as f:
            return pickle.load(f)
    df = build_person_index()
    with open(PERSON_INDEX_PATH, "wb") as f:
        pickle.dump(df, f)
    print(f"Cached person index to {PERSON_INDEX_PATH} ({len(df)} rows)")
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
