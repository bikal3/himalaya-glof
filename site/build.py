#!/usr/bin/env python3
"""Build the static Nepal GLOF Explorer site into dist/.

Every hazard score, projection, ML probability and change figure is computed here by the
utils modules and written out as JSON. The browser only renders — it never recomputes a
number — so the published page cannot drift from what the Python produced.

Usage:
    python site/build.py              # build into dist/
    python site/build.py --out other  # build elsewhere
    python site/build.py --serve      # build, then serve dist/ on :8000
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).parent.parent
SITE = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from utils.change_detection import compute_changes, get_cache_last_updated, get_cache_source
from utils.climate_projections import fractional_growth_rate, project_lake_area
from utils.exposure import load_buffered_corridors, load_exposure
from utils.ml_model import FEATURES, load_model, predict_proba
from utils.risk_score import classify
from utils.provenance_text import (
    CACHE_SOURCE_LABELS,
    CLIMATE_NOTICE,
    DOWNLOADS_NOTICE,
    HOME_NOTICE,
    MAP_NOTICE,
    METHODOLOGY_NOTICE,
    ML_NOTICE,
    POPULATION_NOTICE,
    PROVENANCE_ROWS,
    TRENDS_NOTICE,
)

SITE_URL = "https://himalayaglof.bikal3.com.np"
REPO_URL = "https://github.com/bikal3/himalaya-glof"

# file, nav label, icon, sidebar group, page title, meta description.
PAGES = [
    ("index.html", "Home", "🏔️", "", "🏔️ Nepal GLOF Explorer",
     "Overview metrics and a map of all 25 monitored glacial lakes."),
    ("map.html", "Risk Map", "🗺️", "Explore Data", "Interactive GLOF Hazard Map",
     "Filter 25 Nepal glacial lakes by basin, risk class and area."),
    ("trends.html", "Lake Trends", "📈", "Explore Data", "Glacial Lake Trends 2000–2024",
     "Lake area 2000–2024, basin totals and risk score spread."),
    ("climate.html", "Climate Projections", "🌡️", "Analysis", "Climate Projections",
     "Lake area projected to 2100 under RCP 4.5 and 8.5."),
    ("ml.html", "ML Risk Scoring", "🤖", "Analysis", "ML-Based Risk Scoring",
     "Random Forest GLOF probability against the formula score."),
    ("change.html", "Change Detection", "🛰️", "Analysis", "Change Detection",
     "Baseline vs latest lake area, with a 15% alert threshold."),
    ("population.html", "Population Exposure", "👥", "Analysis", "Population Exposure Analysis",
     "WorldPop and OpenStreetMap counts per flood corridor."),
    ("methodology.html", "Methodology", "📋", "Reference", "Methodology",
     "Spectral indices, hazard scoring, data sources and provenance."),
    ("downloads.html", "Downloads", "⬇️", "Reference", "Data Downloads",
     "Every dataset behind the app, free to download."),
]

ASSETS: dict[str, str] = {}   # {"style.css": "style.4f2a1c9e.css"}, filled by copy_static

DESCRIPTIONS = {f: desc for f, _, _, _, _, desc in PAGES}
TITLES = {f: title for f, _, _, _, title, _ in PAGES}

RISK_ORDER = ["Very High", "High", "Moderate", "Low"]
TIER_COLOR = {"High": "#E63946", "Medium": "#F4A261", "Low": "#1D9E75"}


def url_for(filename: str) -> str:
    """Clean URL for a page.

    Cloudflare Pages serves map.html at /map and 308-redirects /map.html to it, so
    linking to the extensionless form avoids a redirect on every navigation.
    """
    if filename == "index.html":
        return "/"
    return "/" + filename.removesuffix(".html")


# ══════════════════════════════════════════════════════════════════════════════
# Tiny markdown → HTML (the notice text uses **bold**, *italic*, `code`, [x](y))
# ══════════════════════════════════════════════════════════════════════════════
def md(text: str) -> str:
    """Render the restricted markdown used in provenance notices."""
    out = esc(text.strip())
    out = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", out)
    out = re.sub(r"`([^`]+)`", r'<code class="inline">\1</code>', out)
    paragraphs = [p.strip().replace("\n", " ") for p in out.split("\n\n") if p.strip()]
    return "".join(f"<p>{p}</p>" for p in paragraphs)


def esc(text) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def callout(text: str, kind: str = "") -> str:
    return f'<div class="callout {kind}">{md(text)}</div>'


def notice(detail: str) -> str:
    return f'<p class="note">⚠️ Demonstration data — {md(detail)[3:-4]}</p>'


def metric(label: str, value: str, small: bool = False) -> str:
    cls = "value sm" if small else "value"
    return (
        f'<div class="metric"><div class="label">{esc(label)}</div>'
        f'<div class="{cls}">{esc(value)}</div></div>'
    )


def table(headers: list, rows: list[list], numeric: set[int] | None = None,
          caption: str = "") -> str:
    numeric = numeric or set()
    head = "".join(
        f'<th{" class=\"num\"" if i in numeric else ""}>{esc(h)}</th>'
        for i, h in enumerate(headers)
    )
    body = []
    for row in rows:
        cells = "".join(
            f'<td{" class=\"num\"" if i in numeric else ""}>{c}</td>'
            for i, c in enumerate(row)
        )
        body.append(f"<tr>{cells}</tr>")
    cap = f"<caption>{esc(caption)}</caption>" if caption else ""
    return (
        f'<div class="table-wrap"><table>{cap}<thead><tr>{head}</tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table></div>'
    )


def risk_pill(risk_class: str) -> str:
    slug = risk_class.lower().replace(" ", "")
    return f'<span class="pill {slug}">{esc(risk_class)}</span>'


# ══════════════════════════════════════════════════════════════════════════════
# Page shell
# ══════════════════════════════════════════════════════════════════════════════
def sidebar(filename: str) -> str:
    """Grouped navigation, rendered into every page."""
    out = []
    current_group = None
    for f, label, icon, group, _, _ in PAGES:
        if group != current_group:
            if group:
                out.append(f'<div class="group-label">{esc(group)}</div>')
            current_group = group
        active = ' aria-current="page"' if f == filename else ""
        out.append(
            f'<a class="nav-item" href="{url_for(f)}"{active}>'
            f'<span class="icon" aria-hidden="true">{icon}</span>{esc(label)}</a>'
        )
    return f"""<aside class="sidebar" id="sidebar">
  <nav aria-label="Pages">{"".join(out)}</nav>
  <hr>
  <p class="warn">⚠️ Demonstration data — not for operational or emergency use</p>
  <p class="caption">25 glacial lakes · Nepal Himalaya · 2000–2024</p>
  <a class="badge" href="{REPO_URL}"><span class="left">GitHub</span><span
     class="right">bikal3/himalaya-glof</span></a>
</aside>"""


def layout(filename: str, title: str, description: str, body: str,
           scripts: list[str] | None = None, needs_leaflet: bool = False,
           needs_plotly: bool = False) -> str:
    head_extra = ""
    if needs_leaflet:
        head_extra += '<link rel="stylesheet" href="/vendor/leaflet.css">'
    tail = ""
    if needs_leaflet:
        tail += '<script src="/vendor/leaflet.js"></script>'
    if needs_plotly:
        tail += '<script src="/vendor/plotly-basic.min.js"></script>'
    tail += f'<script src="/assets/{ASSETS.get("common.js", "common.js")}"></script>'
    for s in scripts or []:
        tail += f'<script src="/assets/{ASSETS.get(s, s)}"></script>'

    canonical = f"{SITE_URL}{url_for(filename)}"
    full_title = "Nepal GLOF Explorer" if filename == "index.html" \
        else f"{title} — Nepal GLOF Explorer"

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full_title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Nepal GLOF Explorer">
<meta property="og:title" content="{esc(full_title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{canonical}">
<meta name="twitter:card" content="summary">
<meta name="theme-color" content="#F1EFE8">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="/assets/{ASSETS.get("style.css", "style.css")}">
{head_extra}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<button class="sidebar-toggle" id="sidebar-toggle" aria-label="Toggle navigation"
        aria-controls="sidebar" aria-expanded="false">☰</button>
<div class="app">
{sidebar(filename)}
<main id="main">
<h1 class="page-title">{esc(TITLES.get(filename, title))}</h1>
{body}
<footer>
  <p><strong>Demonstration data — not for operational or emergency use.</strong>
     Lake attributes are simulated; see <a href="/methodology#provenance">Data
     Provenance</a>.</p>
  <p>Population: WorldPop Nepal 2020 (© WorldPop, CC BY 4.0). Buildings: ©
     OpenStreetMap contributors (ODbL). Basemap tiles: © OpenStreetMap contributors, Esri.
     Source code: <a href="{REPO_URL}">github.com/bikal3/himalaya-glof</a>.</p>
  <p>Built {date.today().isoformat()}.</p>
</footer>
</main>
</div>
{tail}
</body>
</html>
"""


# ══════════════════════════════════════════════════════════════════════════════
# Data preparation
# ══════════════════════════════════════════════════════════════════════════════
RISK_BIN_WIDTH = 5      # 35 / 55 / 75 are all multiples, so no bin straddles a class boundary


def risk_histogram(scores: list[float]) -> list[dict]:
    """Bin hazard scores for the distribution chart.

    Binned here rather than in the browser because plotly-basic — the bundle this site
    vendors — ships only bar, pie and scatter. A `histogram` trace silently degrades to a
    scatter, which is what turned this chart into a zigzag line.

    Width 5 divides every class threshold, so each bar sits wholly inside one risk class
    and can be coloured by it. 25 lakes over 20 bins (the old setting) left most bars at a
    count of 1 and seven bins empty, which read as noise.
    """
    if not scores:
        return []
    lo = int(min(scores) // RISK_BIN_WIDTH) * RISK_BIN_WIDTH
    hi = int(max(scores) // RISK_BIN_WIDTH + 1) * RISK_BIN_WIDTH

    bins = []
    for start in range(lo, hi, RISK_BIN_WIDTH):
        end = start + RISK_BIN_WIDTH
        # Upper edge is inclusive only for the final bin, so no score is counted twice.
        in_bin = [s for s in scores if start <= s < end or (end == hi and s == end)]
        bins.append({
            "start": start,
            "end": end,
            "mid": start + RISK_BIN_WIDTH / 2,
            "count": len(in_bin),
            "risk_class": classify(start),
        })
    return bins


def prepare_data() -> dict:
    """Load every input and precompute everything the pages display."""
    lakes = gpd.read_file(ROOT / "data" / "lakes_risk.geojson")
    ts = pd.read_csv(ROOT / "data" / "lakes_timeseries.csv")
    corridors = gpd.read_file(ROOT / "data" / "flood_corridors.geojson")
    buffered = load_buffered_corridors(str(ROOT / "data" / "flood_corridors_buffered.geojson"))
    exposure = load_exposure(str(ROOT / "data" / "population_exposure.json"))
    events = pd.read_csv(ROOT / "data" / "glof_events.csv")

    cache_dir = ROOT / "data" / "sentinel_cache"
    change = compute_changes(str(cache_dir))
    change_source = get_cache_source(str(cache_dir))
    change_updated = get_cache_last_updated(str(cache_dir))

    lake_records = []
    for _, r in lakes.iterrows():
        lake_records.append({
            "lake_id": r["lake_id"],
            "lake_name": r["lake_name"],
            "lat": round(float(r.geometry.y), 6),
            "lon": round(float(r.geometry.x), 6),
            "area_km2": float(r["area_km2"]),
            "area_growth_rate": float(r["area_growth_rate"]),
            "dam_type": r["dam_type"],
            "slope_downstream": float(r["slope_downstream"]),
            "distance_to_settlement_km": float(r["distance_to_settlement_km"]),
            "risk_score": float(r["risk_score"]),
            "risk_class": r["risk_class"],
            "basin": r["basin"],
            "district": r["district"],
            "elevation_m": int(r["elevation_m"]),
        })

    # Climate projections, precomputed per lake by the same model the app uses.
    climate = {}
    for rec in lake_records:
        a0 = rec["area_km2"]
        rate = fractional_growth_rate(rec["area_growth_rate"], a0)
        proj = project_lake_area(area_0=a0, growth_rate=rate)
        area_2100 = float(proj.loc[proj["year"] == 2100, "area_rcp85"].iloc[0])
        climate[rec["lake_id"]] = {
            "growth_rate_pct": round(rate * 100, 2),
            "years": [int(y) for y in proj["year"]],
            "rcp45": [round(v, 4) for v in proj["area_rcp45"]],
            "rcp45_low": [round(v, 4) for v in proj["area_rcp45_low"]],
            "rcp45_high": [round(v, 4) for v in proj["area_rcp45_high"]],
            "rcp85": [round(v, 4) for v in proj["area_rcp85"]],
            "rcp85_low": [round(v, 4) for v in proj["area_rcp85_low"]],
            "rcp85_high": [round(v, 4) for v in proj["area_rcp85_high"]],
            "out_of_range": bool(a0 > 0 and area_2100 > 10 * a0),
            "multiple_2100": round(area_2100 / a0, 1) if a0 > 0 else 0,
        }

    # ML probabilities, from the committed model.
    ml = {"available": False, "features": FEATURES, "importances": [], "probs": {}}
    model_path = ROOT / "models" / "glof_risk_model.pkl"
    if model_path.exists():
        model = load_model(str(model_path))
        lakes_df = pd.DataFrame(lakes.drop(columns="geometry"))
        probs = predict_proba(model, lakes_df)
        ml = {
            "available": True,
            "features": FEATURES,
            "importances": [round(float(v), 4) for v in model.feature_importances_],
            "probs": {lid: round(float(p), 3) for lid, p in zip(lakes_df["lake_id"], probs)},
        }

    return {
        "lakes": lake_records,
        "risk_bins": risk_histogram([r["risk_score"] for r in lake_records]),
        "timeseries": ts,
        "corridors": corridors,
        "buffered": buffered,
        "exposure": exposure,
        "events": events,
        "change": change,
        "change_source": change_source,
        "change_updated": change_updated,
        "climate": climate,
        "ml": ml,
    }


def write_site_data(d: dict, out: Path) -> None:
    """Write the JSON payloads the browser fetches."""
    sd = out / "site-data"
    sd.mkdir(parents=True, exist_ok=True)

    (sd / "lakes.json").write_text(json.dumps(d["lakes"], separators=(",", ":")))
    (sd / "climate.json").write_text(json.dumps(d["climate"], separators=(",", ":")))
    (sd / "ml.json").write_text(json.dumps(d["ml"], separators=(",", ":")))
    (sd / "risk-bins.json").write_text(json.dumps(d["risk_bins"], separators=(",", ":")))

    ts_out = {}
    for lake_id, grp in d["timeseries"].groupby("lake_id"):
        g = grp.sort_values("year")
        ts_out[lake_id] = {
            "lake_name": g["lake_name"].iloc[0],
            "basin": g["basin"].iloc[0],
            "years": [int(y) for y in g["year"]],
            "areas": [round(float(a), 4) for a in g["area_km2"]],
        }
    (sd / "timeseries.json").write_text(json.dumps(ts_out, separators=(",", ":")))

    (sd / "change.json").write_text(
        d["change"].to_json(orient="records", double_precision=4)
    )
    (sd / "exposure.json").write_text(
        d["exposure"].to_json(orient="records", double_precision=4)
    )
    (sd / "corridors.geojson").write_text(d["corridors"].to_json())
    (sd / "corridors_buffered.geojson").write_text(d["buffered"].to_json())


# ══════════════════════════════════════════════════════════════════════════════
# Pages
# ══════════════════════════════════════════════════════════════════════════════
def page_home(d: dict) -> str:
    lakes = d["lakes"]
    ts = d["timeseries"]
    area_2000 = ts[ts["year"] == 2000]["area_km2"].sum()
    area_2024 = ts[ts["year"] == 2024]["area_km2"].sum()
    high = sum(1 for l in lakes if l["risk_class"] in ("High", "Very High"))

    body = f"""
<p class="lede">
  <strong>Glacial Lake Outburst Floods (GLOFs)</strong> are among the most destructive hazards
  in the Nepal Himalaya — triggered when a moraine or ice dam holding a glacial lake fails
  catastrophically. This site demonstrates a GLOF hazard-screening workflow over 25
  high-elevation lakes across Nepal: annual lake area from 2000 to 2024, a hazard score
  weighing dam type, lake growth rate, downstream slope and proximity to settlements, and a
  four-tier risk classification. The <a href="/methodology">Methodology</a> page documents
  the intended satellite pipeline and what each number is actually derived from.
</p>

{callout(HOME_NOTICE)}

<div class="metrics">
  {metric("Lakes Monitored", str(len(lakes)))}
  {metric("High / Very High Risk", str(high))}
  {metric("Total Area 2024 (km²)", f"{area_2024:.1f}")}
  {metric("Area Change since 2000", f"{area_2024 - area_2000:+.1f} km²")}
</div>

<hr>

<h2>Overview Map</h2>
<p class="muted">All 25 lakes, sized by area and coloured by risk class, with the eight
digitised downstream flood corridors. Click a lake for detail.</p>
<div id="map" class="map" role="application" aria-label="Map of 25 monitored glacial lakes"></div>

<h2>Explore</h2>
<div class="cards">
  <div class="card"><h3>🗺️ Risk Map</h3>
    <p>Filter the inventory by basin, risk class and minimum area.</p>
    <a class="dl" href="/map">Open Risk Map</a></div>
  <div class="card"><h3>📈 Lake Trends</h3>
    <p>Area time-series, basin totals and the spread of hazard scores.</p>
    <a class="dl" href="/trends">Open Trends</a></div>
  <div class="card"><h3>👥 Population Exposure</h3>
    <p>Real WorldPop and OpenStreetMap counts inside each flood corridor.</p>
    <a class="dl" href="/population">Open Exposure</a></div>
</div>
"""
    return layout("index.html", "Home", DESCRIPTIONS[PAGES[0][0]], body,
                  scripts=["home-page.js"], needs_leaflet=True)


def page_map(d: dict) -> str:
    basins = sorted({l["basin"] for l in d["lakes"]})
    basin_checks = "".join(
        f'<label><input type="checkbox" name="basin" value="{esc(b)}" checked> {esc(b)}</label>'
        for b in basins
    )
    class_checks = "".join(
        f'<label><input type="checkbox" name="risk" value="{esc(c)}" checked> {esc(c)}</label>'
        for c in RISK_ORDER
    )
    areas = [l["area_km2"] for l in d["lakes"]]
    lo, hi = min(areas), max(areas)

    body = f"""
{notice(MAP_NOTICE)}

<div class="controls">
  <div class="control">
    <span class="legend-label">Basin</span>
    <div class="checks" id="basin-filter">{basin_checks}</div>
  </div>
  <div class="control">
    <span class="legend-label">Risk class</span>
    <div class="checks" id="risk-filter">{class_checks}</div>
  </div>
  <div class="control">
    <label for="area-filter">Minimum area — <output id="area-out">{lo:.2f}</output> km²</label>
    <input type="range" id="area-filter" min="{lo:.2f}" max="{hi:.2f}" step="0.05" value="{lo:.2f}">
    <button class="reset" id="reset" type="button">Reset filters</button>
  </div>
</div>

<div class="metrics">
  <div class="metric"><div class="label">Lakes shown</div><div class="value" id="m-count">–</div></div>
  <div class="metric"><div class="label">High / Very High risk</div><div class="value" id="m-high">–</div></div>
  <div class="metric"><div class="label">Total area (km²)</div><div class="value" id="m-area">–</div></div>
  <div class="metric"><div class="label">Largest lake</div><div class="value sm" id="m-largest">–</div></div>
</div>

<div id="map" class="map tall" role="application" aria-label="Filtered map of glacial lakes"></div>

<h2>Filtered Lakes</h2>
<div class="table-wrap">
  <table>
    <thead><tr>
      <th>Lake</th><th class="num">Area (km²)</th><th>Risk class</th>
      <th class="num">Score</th><th>District</th><th>Basin</th><th>Dam type</th>
    </tr></thead>
    <tbody id="lake-rows"></tbody>
  </table>
</div>
<p class="muted" id="empty-msg" hidden>No lakes match these filters.</p>
"""
    return layout("map.html", "Risk Map", DESCRIPTIONS[PAGES[1][0]], body,
                  scripts=["map-page.js"], needs_leaflet=True)


def page_trends(d: dict) -> str:
    ts = d["timeseries"]
    area_2005 = ts[ts["year"] == 2005]["area_km2"].sum()
    area_2024 = ts[ts["year"] == 2024]["area_km2"].sum()
    delta = area_2024 - area_2005
    fields = int(delta * 1_000_000 / 7140)

    body = f"""
{notice(TRENDS_NOTICE)}

<h3>Area time-series — top 8 lakes by current area</h3>
<div id="chart-series" class="chart"></div>

<h3>Total lake area by basin (2024)</h3>
<div id="chart-basin" class="chart"></div>

<h3>Hazard score distribution</h3>
<div id="chart-hist" class="chart"></div>

{callout(f"**From 2005 to 2024**, total monitored lake area grew by **{delta:.2f} km²** — "
          f"equivalent to approximately **{fields:,} football fields**.", "info")}
"""
    return layout("trends.html", "Lake Trends", DESCRIPTIONS[PAGES[2][0]], body,
                  scripts=["trends-page.js"], needs_plotly=True)


def page_climate(d: dict) -> str:
    options = "".join(
        f'<option value="{esc(l["lake_id"])}">{esc(l["lake_name"])}</option>'
        for l in sorted(d["lakes"], key=lambda x: x["lake_name"])
    )
    body = f"""
<p class="lede">As temperatures rise, glaciers retreat and meltwater accumulates — causing
glacial lakes to expand and their moraine dams to weaken. This page projects lake area to 2100
under two IPCC emissions pathways: <strong>RCP 4.5</strong> (strong mitigation, peak warming
~2°C) and <strong>RCP 8.5</strong> (high emissions, peak warming ~4°C). Larger lakes exert
greater hydrostatic pressure on their dams, directly raising outburst flood probability.</p>

<div class="controls">
  <div class="control">
    <label for="lake-select">Select lake</label>
    <select id="lake-select">{options}</select>
  </div>
</div>

<div id="range-warning"></div>
<div id="chart-climate" class="chart"></div>

<div class="cards">
  <div class="card"><h3>2050 projections</h3><div id="table-2050"></div></div>
  <div class="card"><h3>2100 projections</h3><div id="table-2100"></div></div>
</div>

{callout("**Source:** Kraaijenbrink et al. (2017) — Impact of a global temperature rise of "
          "1.5 degrees Celsius on Asia's glaciers. *Nature*, 549, 257-260. RCP 4.5 increment: "
          "+0.008/yr; RCP 8.5 increment: +0.014/yr above observed growth rate. Uncertainty "
          "bands represent ±1σ from the published variance.", "info")}
{notice(CLIMATE_NOTICE)}
"""
    return layout("climate.html", "Climate Projections", DESCRIPTIONS[PAGES[3][0]], body,
                  scripts=["climate-page.js"], needs_plotly=True)


def page_ml(d: dict) -> str:
    ml = d["ml"]
    if not ml["available"]:
        body = "<h2>ML Risk Scoring</h2>" + callout(
            "Model file not found. Run `python data/train_model.py`, then rebuild.", "alert")
        return layout("ml.html", "ML Risk Scoring", DESCRIPTIONS[PAGES[4][0]], body)

    model_card = f"""
<h3>Model card</h3>
<p><strong>Model:</strong> RandomForestClassifier (scikit-learn),
<code class="inline">n_estimators=100</code>, <code class="inline">random_state=42</code>,
<code class="inline">class_weight='balanced'</code>.</p>
<p><strong>Training data:</strong> positive examples from the GLOF event catalogue
(<code class="inline">data/glof_events.csv</code>) — real events across the wider Hindu Kush
Himalaya (Nepal, Bhutan, Tibet, Sikkim), with unverified attribute values. Negative examples
are inventory lakes with no documented event, matched by normalised name so that
e.g. 'Lower Barun Lake' and 'Lower Barun' are recognised as the same lake.</p>
<p><strong>Features:</strong> {esc(", ".join(ml["features"]))}.
<strong>Dam type encoding:</strong> moraine=2, ice=1, bedrock=0.</p>
<p><strong>Known limitation:</strong> the positive and negative rows come from separately
authored files whose numeric formatting differs, which leaks class membership. Any accuracy
figure from this setup overstates real predictive skill.</p>
<p><strong>Retrain:</strong> <code class="inline">python data/train_model.py</code>.</p>
"""

    body = f"""
<p class="lede">The formula-based hazard score weights factors by fixed rules. This page adds a
<strong>Random Forest classifier</strong> trained on confirmed GLOF events, letting the data
determine which factors matter most. Where the two scores diverge, the scatter plot below
highlights lakes the formula may be over- or under-rating.</p>

{callout(ML_NOTICE, "alert")}

<h3>Feature importance</h3>
<div id="chart-importance" class="chart"></div>

<h3>Formula score vs ML probability</h3>
<div id="chart-scatter" class="chart"></div>

<h3>Lake comparison</h3>
<div class="table-wrap">
  <table>
    <thead><tr>
      <th>ID</th><th>Lake</th><th class="num">Formula score</th>
      <th class="num">ML probability</th><th>Risk class</th><th>Dam type</th>
    </tr></thead>
    <tbody id="ml-rows"></tbody>
  </table>
</div>

{model_card}
"""
    return layout("ml.html", "ML Risk Scoring", DESCRIPTIONS[PAGES[4][0]], body,
                  scripts=["ml-page.js"], needs_plotly=True)


def page_change(d: dict) -> str:
    change = d["change"]
    alerts = change[change["alert"].astype(bool)]["lake_name"].tolist()
    source_label = CACHE_SOURCE_LABELS.get(d["change_source"], CACHE_SOURCE_LABELS["unknown"])

    if alerts:
        alert_block = callout(
            f"**Area change alert (>15%):** {', '.join(alerts)}", "")
    else:
        alert_block = callout("No lakes exceed the 15% area change threshold since baseline.",
                              "info")

    rows = []
    for _, r in change.iterrows():
        pct = float(r["pct_change"])
        arrow = "↑" if pct > 5 else ("↓" if pct < -5 else "→")
        rows.append([
            esc(r["lake_name"]), int(r["baseline_year"]), f'{r["baseline_area"]:.3f}',
            int(r["latest_year"]), f'{r["latest_area"]:.3f}', f'{r["delta_area"]:+.3f}',
            f"{pct:+.2f}", arrow,
        ])

    body = f"""
<p class="lede">Rapid lake expansion is one of the strongest early-warning signals for GLOF
risk — a growing lake exerts increasing pressure on its dam. This page compares each lake's
earliest cached observation (baseline) against the most recent, flagging any lake that has
grown more than 15% as a potential concern.</p>

{callout(source_label, "alert" if d["change_source"] != "sentinel_hub_mndwi" else "info")}
{alert_block}
<p class="muted">Cache last updated: {esc(d["change_updated"] or "unknown")}</p>

<div id="chart-change" class="chart"></div>

<h3>All lakes</h3>
{table(["Lake", "Baseline year", "Baseline area (km²)", "Latest year", "Latest area (km²)",
        "Delta (km²)", "Change (%)", "Trend"], rows, numeric={1, 2, 3, 4, 5, 6})}
"""
    return layout("change.html", "Change Detection", DESCRIPTIONS[PAGES[5][0]], body,
                  scripts=["change-page.js"], needs_plotly=True)


def page_population(d: dict) -> str:
    exp = d["exposure"].sort_values("population_at_risk", ascending=False).reset_index(drop=True)
    options = "".join(
        f'<option value="{esc(r["lake_id"])}">{esc(r["lake_name"])}</option>'
        for _, r in exp.iterrows()
    )
    rows = []
    for i, (_, r) in enumerate(exp.iterrows(), 1):
        badge = "🟢 real" if r["data_source"] == "real" else "⚪ synthetic"
        rows.append([
            i, esc(r["lake_name"]), f'{int(r["population_at_risk"]):,}',
            f'{int(r["buildings_at_risk"]):,}', f'{r["corridor_area_km2"]:.1f}', badge,
        ])

    body = f"""
<p class="lede">Hazard alone does not determine impact — a high-risk lake above an uninhabited
valley poses far less threat than a moderate-risk lake above a densely settled floodplain. This
page estimates the population and buildings within each lake's downstream flood corridor,
combining <a href="https://www.worldpop.org/">WorldPop Nepal 2020</a> (100 m resolution) with
OpenStreetMap building footprints.</p>

{callout(POPULATION_NOTICE, "info")}

<div class="controls">
  <div class="control">
    <label for="lake-select">Select lake</label>
    <select id="lake-select">{options}</select>
  </div>
</div>

<div class="metrics">
  <div class="metric"><div class="label">Population at risk</div><div class="value" id="m-pop">–</div></div>
  <div class="metric"><div class="label">Buildings at risk</div><div class="value" id="m-bld">–</div></div>
  <div class="metric"><div class="label">Corridor area (km²)</div><div class="value" id="m-area">–</div></div>
</div>

<div id="map" class="map" role="application" aria-label="Flood corridors by exposure tier"></div>

<h2>All lakes — population exposure ranking</h2>
{table(["Rank", "Lake", "Population at risk", "Buildings at risk", "Corridor area (km²)",
        "Data source"], rows, numeric={0, 2, 3, 4})}

<p class="muted">Population: WorldPop Nepal 2020 (100 m resolution, © WorldPop).
Buildings: OpenStreetMap contributors. Corridors marked <strong>synthetic</strong> use
buffered centroid paths — treat as indicative only.</p>
"""
    return layout("population.html", "Population Exposure", DESCRIPTIONS[PAGES[6][0]], body,
                  scripts=["population-page.js"], needs_leaflet=True)


def page_methodology(d: dict) -> str:
    scoring = table(
        ["Factor", "Max score", "Notes"],
        [["Dam type", 40, "Moraine=40, Ice=30, Bedrock=10"],
         ["Area growth rate", 25, "Capped at 0.05 km²/yr = 25 pts"],
         ["Downstream slope", 20, "Capped at 35° = 20 pts"],
         ["Distance to settlement", 15, "Inverse linear; 0 km = 15 pts, ≥80 km = 0 pts"]],
        numeric={1},
    )
    sources = table(
        ["Dataset", "Provider", "Resolution", "Use", "In shipped data?"],
        [["Landsat 5/7/8/9 SR", "USGS / NASA", "30 m", "Lake delineation (MNDWI)",
          "No — pipeline only"],
         ["Sentinel-2 MSI", "ESA", "10 m", "Recent area measurements",
          "No — needs <code class=\"inline\">fetch_sentinel.py</code>"],
         ["Copernicus DEM GLO-30", "ESA / Copernicus", "30 m", "Downstream slope",
          "No — slopes are simulated"],
         ["ICIMOD GLOF Database", "ICIMOD", "—", "Event catalogue for ML training",
          "Events yes, attributes unverified"],
         ["WorldPop Nepal 2020", "WorldPop / Univ. of Southampton", "100 m",
          "Population exposure", "<strong>Yes</strong>"],
         ["OpenStreetMap", "OSM contributors", "—", "Building footprints",
          "<strong>Yes</strong>"]],
    )
    provenance = table(["Value", "Source"], [[esc(v), esc(s)] for v, s in PROVENANCE_ROWS])

    gee_path = ROOT / "gee_scripts" / "lake_detection.js"
    gee = (f'<pre class="code">{esc(gee_path.read_text())}</pre>' if gee_path.exists()
           else '<p class="muted">GEE script not found at gee_scripts/lake_detection.js</p>')

    body = f"""
{callout(METHODOLOGY_NOTICE, "alert")}

<h3>1. Lake detection</h3>
<p>Glacial lakes are delineated from Landsat Surface Reflectance imagery using the
<strong>Modified Normalized Difference Water Index (MNDWI)</strong>. A 2000–2024 record spans
three sensors: Landsat 5 TM and 7 ETM+ for 2000–2012, Landsat 8 OLI from 2013, and Landsat 9
from late 2021. Sentinel-2 MSI (10 m) is used from 2016 onward on the Change Detection page.</p>

<div class="formula">
  <span>NDWI =</span>
  <span class="frac"><span class="num">Green − NIR</span><span class="den">Green + NIR</span></span>
</div>
<div class="formula">
  <span>MNDWI =</span>
  <span class="frac"><span class="num">Green − SWIR</span><span class="den">Green + SWIR</span></span>
</div>
<p><strong>Threshold:</strong> pixels with MNDWI &gt; 0.2 are classified as water.</p>

<h3>2. Hazard scoring</h3>
{scoring}
<p class="muted">Every non-dam component floors at 0: a shrinking lake or a negative slope
contributes no hazard points, it never subtracts from the dam-type baseline.</p>

<h3>3. Data sources</h3>
{sources}

<h3 id="provenance">4. Data provenance</h3>
<p>Which numbers on this site are measured, and which are generated for demonstration:</p>
{provenance}
{callout("Because the hazard inputs are simulated, this site carries **no validation against "
          "observed GLOF events** — a scoring method built on generated slopes and dam types "
          "cannot be tested against real outcomes. Validation becomes meaningful once a real "
          "inventory is loaded via `data/fetch_icimod.py`.", "info")}

<h3>5. Google Earth Engine script</h3>
{gee}
"""
    return layout("methodology.html", "Methodology", DESCRIPTIONS[PAGES[7][0]], body)


def page_downloads(d: dict, out: Path) -> str:
    def size_of(rel: str) -> str:
        p = out / rel.lstrip("/")
        if not p.exists():
            return ""
        kb = p.stat().st_size / 1024
        return f"{kb / 1024:.1f} MB" if kb >= 1024 else f"{kb:.0f} KB"

    def card(title, desc, schema, href) -> str:
        size = size_of(href)
        size_html = f' <span class="size">({size})</span>' if size else ""
        return f"""<div class="card">
  <h3>{esc(title)}</h3>
  <p>{desc}</p>
  <div class="schema">{esc(schema)}</div>
  <a class="dl" href="{href}" download>Download{size_html}</a>
</div>"""

    cards = "".join([
        card("Lake risk GeoJSON",
             "One Point feature per lake (WGS84 / EPSG:4326) with hazard score, risk class, "
             "dam type, elevation and basin.",
             "lake_id · lake_name · area_km2 · area_growth_rate · dam_type · slope_downstream · "
             "distance_to_settlement_km · risk_score · risk_class · basin · district · "
             "elevation_m · last_updated",
             "/data/lakes_risk.geojson"),
        card("Lake time-series CSV",
             "Annual area values for all 25 lakes from 2000 to 2024 (625 rows).",
             "lake_id · lake_name · year · area_km2 · centroid_lat · centroid_lon · basin · district",
             "/data/lakes_timeseries.csv"),
        card("Flood corridors GeoJSON",
             "8 downstream LineString corridors for the highest-risk lakes, digitised from "
             "valley topography.",
             "lake_id · lake_name · risk_class · geometry (LineString)",
             "/data/flood_corridors.geojson"),
        card("Buffered corridors GeoJSON",
             "All 25 lakes with ±2 km Polygon corridors (8 real LineStrings buffered, "
             "17 synthetic from lake centroids).",
             "lake_id · lake_name · data_source · geometry (Polygon)",
             "/data/flood_corridors_buffered.geojson"),
        card("Population exposure JSON",
             "Pre-computed population and building counts within each lake's flood corridor, "
             "derived from WorldPop Nepal 2020 and OpenStreetMap. <strong>Real data.</strong>",
             "lake_id · lake_name · corridor_area_km2 · population_at_risk · buildings_at_risk · "
             "data_source",
             "/data/population_exposure.json"),
        card("Lake area cache (2016–2024)",
             "One JSON file per lake, bundled as a zip. Each file records its own "
             "<code class=\"inline\">source</code>: the cache shipped here is generated from "
             "the simulated area series, not from Sentinel-2.",
             "lake_id · lake_name · last_updated · source · scenes[ year · date · area_km2 · "
             "cloud_pct ]",
             "/data/sentinel_cache.zip"),
        card("GLOF event catalogue",
             "Confirmed GLOF events used to train the classifier, curated from the ICIMOD GLOF "
             "database. Coverage is the wider Hindu Kush Himalaya — Nepal, Bhutan, Tibet and "
             "Sikkim — not Nepal alone. The events are real; the per-event attributes are "
             "unverified estimates.",
             "lake_name · year · area_km2 · area_growth_rate · dam_type · slope_downstream · "
             "distance_to_settlement_km · elevation_m · glof_occurred",
             "/data/glof_events.csv"),
        card("Trained ML model",
             "Random Forest classifier (scikit-learn, joblib). Cross-validation scores are "
             "omitted deliberately: the classes come from separately authored files, so any "
             "score reflects that split rather than predictive skill.",
             "joblib pickle — loading a pickle executes code; only load if you trust the source",
             "/data/glof_risk_model.pkl"),
        card("PDF summary report",
             "Auto-generated report with key statistics and a risk table for the top 10 lakes.",
             "PDF", "/data/nepal_glof_report.pdf"),
    ])

    body = f"""
<p class="lede">Every dataset behind this site is available below.</p>
{callout(DOWNLOADS_NOTICE, "alert")}

<div class="cards">{cards}</div>

<h2>WorldPop Nepal 2020 raster (~100 MB)</h2>
<p>The WorldPop 2020 population raster is used to compute population counts within flood
corridors. It is too large to bundle here — fetch it directly, or let the offline script do it:</p>
<pre class="code">https://data.worldpop.org/GIS/Population/Global_2000_2020/2020/NPL/npl_ppp_2020.tif

pip install -r requirements-offline.txt
python data/compute_exposure.py</pre>
<p class="muted">Source: WorldPop (www.worldpop.org) — School of Geography and Environmental
Science, University of Southampton. Licence: CC BY 4.0.</p>
"""
    return layout("downloads.html", "Downloads", DESCRIPTIONS[PAGES[8][0]], body)


# ══════════════════════════════════════════════════════════════════════════════
# Static file copying
# ══════════════════════════════════════════════════════════════════════════════
def copy_static(out: Path) -> dict[str, str]:
    """Copy assets, fingerprinting each with a content hash.

    style.css becomes style.4f2a1c9e.css, so a redeploy publishes a new URL and a
    browser holding the previous file cannot show stale styling against new markup.
    Returns {original name: hashed name} for the page templates to link against.
    """
    shutil.copytree(SITE / "assets", out / "assets", dirs_exist_ok=True)
    shutil.copytree(SITE / "vendor", out / "vendor", dirs_exist_ok=True)

    data_out = out / "data"
    data_out.mkdir(parents=True, exist_ok=True)
    for name in ["lakes_risk.geojson", "lakes_timeseries.csv", "flood_corridors.geojson",
                 "flood_corridors_buffered.geojson", "population_exposure.json",
                 "glof_events.csv"]:
        shutil.copy2(ROOT / "data" / name, data_out / name)
    model = ROOT / "models" / "glof_risk_model.pkl"
    if model.exists():
        shutil.copy2(model, data_out / "glof_risk_model.pkl")

    # Bundle the per-lake area cache as a single download.
    cache_dir = ROOT / "data" / "sentinel_cache"
    if cache_dir.exists():
        import zipfile
        with zipfile.ZipFile(data_out / "sentinel_cache.zip", "w", zipfile.ZIP_DEFLATED) as zf:
            for f in sorted(cache_dir.glob("*.json")):
                zf.write(f, arcname=f"sentinel_cache/{f.name}")

    fingerprints: dict[str, str] = {}
    for f in sorted((out / "assets").iterdir()):
        if not f.is_file():
            continue
        digest = hashlib.md5(f.read_bytes()).hexdigest()[:8]
        hashed = f"{f.stem}.{digest}{f.suffix}"
        f.rename(f.with_name(hashed))
        fingerprints[f.name] = hashed
    return fingerprints


def write_pdf(out: Path, lakes: gpd.GeoDataFrame, ts: pd.DataFrame) -> None:
    """Pre-generate the PDF summary report served from the Downloads page."""
    try:
        from fpdf import FPDF
    except ImportError:
        print("  fpdf2 not installed — skipping PDF")
        return

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Nepal GLOF Explorer - Summary Report",
             new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 8, f"Generated: {date.today().isoformat()}",
             new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 9)
    pdf.multi_cell(0, 5, "DEMONSTRATION DATA - lake areas, growth rates, dam types, slopes and "
                         "settlement distances are simulated. Not for operational use.")
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Key Statistics", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    stats = [
        ("Total lakes monitored", len(lakes)),
        ("High / Very High risk lakes",
         int(lakes["risk_class"].isin(["High", "Very High"]).sum())),
        ("Total lake area 2024 (km2)", round(float(lakes["area_km2"].sum()), 2)),
        ("Earliest record year", int(ts["year"].min())),
        ("Latest record year", int(ts["year"].max())),
    ]
    for label, value in stats:
        pdf.cell(0, 7, f"  {label}: {value}", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Top 10 Lakes by Risk Score", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 9)
    headers = ["Lake Name", "Area km2", "Risk Score", "Risk Class", "Dam Type"]
    widths = [50, 25, 25, 30, 30]
    for h, w in zip(headers, widths):
        pdf.cell(w, 7, h, border=1)
    pdf.ln()
    pdf.set_font("Helvetica", "", 9)
    for _, row in lakes.nlargest(10, "risk_score").iterrows():
        values = [row["lake_name"], f'{row["area_km2"]:.2f}', f'{row["risk_score"]:.1f}',
                  row["risk_class"], row["dam_type"]]
        for val, w in zip(values, widths):
            pdf.cell(w, 7, str(val), border=1)
        pdf.ln()

    (out / "data" / "nepal_glof_report.pdf").write_bytes(bytes(pdf.output()))


def write_meta(out: Path) -> None:
    """Cloudflare Pages headers, robots.txt, sitemap and favicon."""
    (out / "_headers").write_text("""/*
  X-Content-Type-Options: nosniff
  X-Frame-Options: SAMEORIGIN
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: geolocation=(), microphone=(), camera=()
  Content-Security-Policy: default-src 'self'; img-src 'self' data: https://*.tile.openstreetmap.org https://server.arcgisonline.com https://*.basemaps.cartocdn.com; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; base-uri 'self'; form-action 'none'; frame-ancestors 'self'

/assets/*
  Cache-Control: public, max-age=31536000, immutable

/vendor/*
  Cache-Control: public, max-age=31536000, immutable

/site-data/*
  Cache-Control: public, max-age=3600

/data/*
  Cache-Control: public, max-age=86400
""")

    (out / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}/sitemap.xml\n")

    urls = "".join(
        f"  <url><loc>{SITE_URL}{url_for(f)}</loc>"
        f"<lastmod>{date.today().isoformat()}</lastmod></url>\n"
        for f, *_ in PAGES
    )
    (out / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}</urlset>\n"
    )

    (out / "favicon.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        '<rect width="64" height="64" rx="12" fill="#157A5C"/>'
        '<path d="M10 46 L26 20 L36 36 L42 27 L54 46 Z" fill="#fff"/>'
        '<path d="M26 20 L33 31 L30 33 L20 30 Z" fill="#BFE3D4"/>'
        "</svg>\n"
    )

    (out / "404.html").write_text(layout(
        "404.html", "Page not found", "That page does not exist.",
        '<h2>Page not found</h2><p class="lede">That page does not exist. '
        'Try the <a href="/">home page</a>.</p>',
    ))


# ══════════════════════════════════════════════════════════════════════════════
def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Build the static GLOF Explorer site")
    parser.add_argument("--out", default=str(ROOT / "dist"), help="Output directory")
    parser.add_argument("--serve", action="store_true", help="Serve the result on :8000")
    args = parser.parse_args(argv)

    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    print("Step 1: Loading data and precomputing…")
    d = prepare_data()
    print(f"  {len(d['lakes'])} lakes, {len(d['change'])} change rows, "
          f"{len(d['climate'])} projections, ML {'ready' if d['ml']['available'] else 'missing'}")

    print("Step 2: Copying static assets and datasets…")
    ASSETS.update(copy_static(out))
    print(f"  fingerprinted {len(ASSETS)} assets")
    write_site_data(d, out)
    write_pdf(out, gpd.read_file(ROOT / "data" / "lakes_risk.geojson"), d["timeseries"])

    print("Step 3: Rendering pages…")
    rendered = {
        "index.html": page_home(d),
        "map.html": page_map(d),
        "trends.html": page_trends(d),
        "climate.html": page_climate(d),
        "ml.html": page_ml(d),
        "change.html": page_change(d),
        "population.html": page_population(d),
        "methodology.html": page_methodology(d),
        "downloads.html": page_downloads(d, out),
    }
    for name, html in rendered.items():
        (out / name).write_text(html)
        print(f"  {name:22s} {len(html) / 1024:6.1f} KB")

    write_meta(out)

    total = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    count = sum(1 for f in out.rglob("*") if f.is_file())
    print(f"\nBuilt {count} files, {total / 1024 / 1024:.1f} MB total → {out}")

    if args.serve:
        import http.server
        import socketserver
        import functools

        class CleanURLHandler(http.server.SimpleHTTPRequestHandler):
            """Serve /map from map.html, the way Cloudflare Pages does."""

            def translate_path(self, path):
                local = super().translate_path(path)
                if not Path(local).exists() and not path.endswith("/"):
                    candidate = Path(local + ".html")
                    if candidate.exists():
                        return str(candidate)
                return local

        handler = functools.partial(CleanURLHandler, directory=str(out))
        with socketserver.TCPServer(("", 8000), handler) as httpd:
            print("Serving on http://localhost:8000 — Ctrl-C to stop")
            httpd.serve_forever()


if __name__ == "__main__":
    main()
