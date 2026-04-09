"""
MillionTwigs — Interactive Streamlit Demo

Deployable to:
  - Hugging Face Spaces (free, recommended)
  - Streamlit Cloud (free)
  - Render / Railway (free tier, custom domain)
  - Google Cloud Run (free tier)

Run locally:
    pip install streamlit numpy scipy scikit-image matplotlib plotly
    streamlit run app.py
"""

import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from scipy.ndimage import gaussian_filter
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from src.analysis.change_detection import (
    ndvi_difference,
    classify_vegetation,
    post_classification_comparison,
    vegetation_change_summary,
)
from src.analysis.tree_detection import (
    detect_trees_watershed,
    estimate_tree_count_from_canopy,
)
from src.analysis.indices import compute_all_indices

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MillionTwigs — Satellite Tree Analysis",
    page_icon="🌳",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Styles ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .metric-card {
        background: #f0f7f0;
        border-left: 4px solid #2d7d46;
        padding: 12px 16px;
        border-radius: 6px;
        margin: 6px 0;
    }
    .loss-card {
        background: #fff0f0;
        border-left: 4px solid #c0392b;
    }
    .gain-card {
        background: #f0fff4;
        border-left: 4px solid #27ae60;
    }
    h1 { color: #1a5c2a; }
    .stMetric label { font-size: 0.85rem !important; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar controls ──────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/color/96/forest.png", width=64)
    st.title("MillionTwigs")
    st.caption("Satellite Vegetation & Tree Analysis")
    st.divider()

    st.subheader("Simulation Settings")
    n_trees_past = st.slider("Trees in baseline period", 50, 300, 160, step=10)
    n_trees_now  = st.slider("Trees in current period",  50, 300, 120, step=10)
    pixel_size   = st.select_slider(
        "Pixel resolution",
        options=[1.0, 5.8, 10.0, 23.5, 30.0],
        value=10.0,
        format_func=lambda v: f"{v} m  ({'Cartosat-3' if v==1 else 'LISS-IV' if v==5.8 else 'Sentinel-2' if v==10 else 'LISS-III' if v==23.5 else 'Landsat'})",
    )
    ndvi_thresh = st.slider("NDVI vegetation threshold", 0.15, 0.55, 0.30, step=0.05)
    biome = st.selectbox(
        "Biome (for allometric estimate)",
        ["tropical_dry", "tropical_wet", "subtropical", "temperate", "urban"],
        index=0,
    )

    st.divider()
    deforestation = st.checkbox("Add deforestation zone", value=True)
    plantation    = st.checkbox("Add plantation / regrowth zone", value=True)
    seed = st.number_input("Random seed", value=42, step=1)

    st.divider()
    st.caption("Data sources: ISRO Bhuvan, Sentinel-2, Landsat")
    st.caption("Models: Tucker 1979 · Weinstein 2020 · Jucker 2017")

# ── Data generation ───────────────────────────────────────────────────────────
@st.cache_data
def generate_scenes(n_past, n_now, px, thresh, biome_key, defor, plant, rseed):
    np.random.seed(rseed)
    H = W = max(150, int(600 / px))  # scale grid to resolution

    def place_crowns(n, base=0.09):
        arr = np.ones((H, W), dtype=np.float32) * base
        y, x = np.mgrid[0:H, 0:W]
        for _ in range(n):
            r = np.random.randint(8, H - 8)
            c = np.random.randint(8, W - 8)
            peak  = np.random.uniform(0.50, 0.88)
            sigma = np.random.uniform(1.2, max(1.5, 6.0 / px))
            arr  += np.exp(-((y - r)**2 + (x - c)**2) / (2 * sigma**2)) * peak
        return np.clip(arr + np.random.normal(0, 0.012, (H, W)), 0, 1)

    ndvi_p = place_crowns(n_past)
    ndvi_n = place_crowns(n_now)

    if defor:
        r0, c0 = int(H * 0.55), int(W * 0.55)
        rr, cc = int(H * 0.22), int(W * 0.22)
        ndvi_n[r0:r0+rr, c0:c0+cc] = np.random.uniform(0.04, 0.13, (rr, cc))

    if plant:
        r0, c0 = int(H * 0.05), int(W * 0.05)
        rr, cc = int(H * 0.18), int(W * 0.18)
        patch = place_crowns(int(n_now * 0.25), base=0.35)[r0:r0+rr, c0:c0+cc]
        ndvi_n[r0:r0+rr, c0:c0+cc] = patch

    ndvi_n = np.clip(ndvi_n, 0, 1)

    labels_p, n_detect_p = detect_trees_watershed(ndvi_p, pixel_size_m=px, ndvi_threshold=thresh)
    labels_n, n_detect_n = detect_trees_watershed(ndvi_n, pixel_size_m=px, ndvi_threshold=thresh)
    diff    = ndvi_difference(ndvi_p, ndvi_n)
    summary = vegetation_change_summary(ndvi_p, ndvi_n, px**2, thresh, 25.0)
    allom_p = estimate_tree_count_from_canopy(summary["veg_area_t1_ha"] * 10_000, biome=biome_key)
    allom_n = estimate_tree_count_from_canopy(summary["veg_area_t2_ha"] * 10_000, biome=biome_key)

    return {
        "ndvi_p": ndvi_p, "ndvi_n": ndvi_n,
        "labels_p": labels_p, "labels_n": labels_n,
        "n_detect_p": n_detect_p, "n_detect_n": n_detect_n,
        "diff": diff, "summary": summary,
        "allom_p": allom_p, "allom_n": allom_n,
        "H": H, "W": W,
    }

data = generate_scenes(
    n_trees_past, n_trees_now, pixel_size,
    ndvi_thresh, biome, deforestation, plantation, int(seed)
)
s = data["summary"]
pixel_area_ha = pixel_size**2 / 10_000

# ── Header ────────────────────────────────────────────────────────────────────
st.title("🌳 MillionTwigs — Satellite Vegetation & Tree Analysis")
st.markdown(
    "Simulates ISRO / Sentinel-2 satellite image analysis to estimate **tree counts** "
    "and detect **vegetation change** between two time periods."
)
st.info(
    "**This demo uses synthetic NDVI data.** Connect real Sentinel-2 or ISRO LISS-IV "
    "imagery via `config.yaml` to run on actual satellite images.",
    icon="ℹ️",
)

# ── Top KPI metrics ───────────────────────────────────────────────────────────
st.subheader("Key Metrics")
c1, c2, c3, c4, c5 = st.columns(5)
delta_veg = s["veg_change_ha"]
delta_trees = data["allom_n"]["estimate"] - data["allom_p"]["estimate"]

c1.metric("Vegetation — Past",  f"{s['veg_area_t1_ha']:.1f} ha")
c2.metric("Vegetation — Now",   f"{s['veg_area_t2_ha']:.1f} ha",
          delta=f"{delta_veg:+.1f} ha",
          delta_color="normal" if delta_veg >= 0 else "inverse")
c3.metric("Est. Trees — Past",  f"{data['allom_p']['estimate']:,}")
c4.metric("Est. Trees — Now",   f"{data['allom_n']['estimate']:,}",
          delta=f"{delta_trees:+,}",
          delta_color="normal" if delta_trees >= 0 else "inverse")
c5.metric("Detected Crowns (watershed)",
          f"{data['n_detect_n']:,}",
          delta=f"{data['n_detect_n'] - data['n_detect_p']:+,}",
          delta_color="normal" if data["n_detect_n"] >= data["n_detect_p"] else "inverse")

st.divider()

# ── NDVI Maps ─────────────────────────────────────────────────────────────────
st.subheader("NDVI Maps")
tab1, tab2, tab3 = st.tabs(["Baseline vs Current", "Change Map", "Crown Detection"])

with tab1:
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for ax, arr, title in [
        (axes[0], data["ndvi_p"], "NDVI — Baseline (Past)"),
        (axes[1], data["ndvi_n"], "NDVI — Current"),
    ]:
        im = ax.imshow(arr, cmap="RdYlGn", vmin=0, vmax=0.9)
        ax.set_title(title, fontsize=12)
        ax.axis("off")
        plt.colorbar(im, ax=ax, label="NDVI", shrink=0.8)
    plt.tight_layout()
    st.pyplot(fig)
    plt.close()

with tab2:
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    im = axes[0].imshow(data["diff"]["delta"], cmap="RdBu", vmin=-0.5, vmax=0.5)
    axes[0].set_title("ΔNDVI (blue=gain, red=loss)", fontsize=12)
    axes[0].axis("off")
    plt.colorbar(im, ax=axes[0], label="ΔNDVI", shrink=0.8)

    chg = np.zeros((data["H"], data["W"], 3), dtype=np.uint8)
    chg[data["diff"]["gain_mask"]] = [0, 180, 0]
    chg[data["diff"]["loss_mask"]] = [210, 30, 30]
    axes[1].imshow(chg)
    g_ha = data["diff"]["gain_mask"].sum() * pixel_area_ha
    l_ha = data["diff"]["loss_mask"].sum() * pixel_area_ha
    axes[1].set_title(
        f"Vegetation Change  |  Gain: {g_ha:.2f} ha  |  Loss: {l_ha:.2f} ha",
        fontsize=11,
    )
    axes[1].axis("off")
    plt.tight_layout()
    st.pyplot(fig)
    plt.close()

    col_g, col_l = st.columns(2)
    col_g.success(f"**Gain area:** {g_ha:.2f} ha ({g_ha/s['total_area_ha']*100:.1f}% of AOI)")
    col_l.error(f"**Loss area:** {l_ha:.2f} ha ({l_ha/s['total_area_ha']*100:.1f}% of AOI)")

with tab3:
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for ax, labels, n, title in [
        (axes[0], data["labels_p"], data["n_detect_p"], "Detected Crowns — Past"),
        (axes[1], data["labels_n"], data["n_detect_n"], "Detected Crowns — Now"),
    ]:
        display = labels.astype(float)
        display[labels == 0] = np.nan
        ax.imshow(display, cmap="nipy_spectral", interpolation="nearest")
        ax.set_title(f"{title}\n{n} crowns (watershed, {pixel_size} m)", fontsize=11)
        ax.axis("off")
    plt.tight_layout()
    st.pyplot(fig)
    plt.close()
    st.caption(
        "Watershed segmentation (Vincent & Soille 1991). Each colour = one detected crown. "
        "At coarse resolution (≥10 m), use allometric estimate instead."
    )

st.divider()

# ── Allometric Tree Count ─────────────────────────────────────────────────────
st.subheader("Allometric Tree Count Estimate")
st.caption(
    "Canopy area → tree count via crown-diameter allometry. "
    "Reference: Jucker et al. (2017), *Global Change Biology*, 23(1), 177-190."
)

col1, col2 = st.columns(2)
for col, period, allom in [
    (col1, "Baseline (Past)", data["allom_p"]),
    (col2, "Current",         data["allom_n"]),
]:
    with col:
        st.markdown(f"**{period}**")
        st.metric("Point estimate", f"{allom['estimate']:,} trees")
        st.progress(
            min(allom["estimate"] / max(data["allom_p"]["estimate"], 1), 1.0),
            text=f"95% CI: {allom['lower_95ci']:,} – {allom['upper_95ci']:,}",
        )
        st.caption(f"Canopy area: {allom['canopy_area_m2']/10_000:.2f} ha  |  "
                   f"Mean crown: {allom['mean_crown_area_m2']} m²  |  Biome: {allom['biome']}")

st.divider()

# ── Method comparison table ───────────────────────────────────────────────────
st.subheader("Method Comparison")
import pandas as pd
methods_df = pd.DataFrame([
    {
        "Method": "Watershed segmentation",
        "Resolution needed": "5–30 m",
        "Past count": f"{data['n_detect_p']:,}",
        "Now count": f"{data['n_detect_n']:,}",
        "Delta": f"{data['n_detect_n'] - data['n_detect_p']:+,}",
        "Reference": "Vincent & Soille 1991",
    },
    {
        "Method": f"Allometric estimate ({biome})",
        "Resolution needed": "Any",
        "Past count": f"{data['allom_p']['estimate']:,}",
        "Now count": f"{data['allom_n']['estimate']:,}",
        "Delta": f"{data['allom_n']['estimate'] - data['allom_p']['estimate']:+,}",
        "Reference": "Jucker et al. 2017",
    },
    {
        "Method": "DeepForest CNN",
        "Resolution needed": "≤ 1 m",
        "Past count": "— (needs Cartosat-3)",
        "Now count": "— (needs Cartosat-3)",
        "Delta": "—",
        "Reference": "Weinstein et al. 2020",
    },
])
st.dataframe(methods_df, use_container_width=True, hide_index=True)

st.divider()

# ── Data source guide ─────────────────────────────────────────────────────────
with st.expander("How to connect real satellite data"):
    st.markdown("""
**Option 1 — ISRO Bhuvan (India, free)**
1. Register at [bhuvan.nrsc.gov.in](https://bhuvan.nrsc.gov.in)
2. Draw AOI → RESOURCESAT-2A → LISS-IV (5.8 m, best for trees)
3. Download GeoTIFF → place in `data/raw/bhuvan/liss4/{year}/`

**Option 2 — Sentinel-2 via Copernicus (global, free)**
1. [browser.dataspace.copernicus.eu](https://browser.dataspace.copernicus.eu)
2. Select L2A, cloud cover < 10%, two dates (past + present)
3. Download bands B2,B3,B4,B8,B11 → `data/raw/sentinel2/{year}/`

**Option 3 — Google Earth Engine (programmatic)**
```bash
earthengine authenticate
python scripts/run_pipeline.py --config config.yaml --source gee
```

**Edit `config.yaml`** to set your bounding box and date ranges.
    """)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "MillionTwigs · Satellite Vegetation Analysis · "
    "Models: NDVI (Tucker 1979) · EVI (Huete 2002) · "
    "DeepForest (Weinstein 2020) · U-Net (Ronneberger 2015) · "
    "Allometry (Jucker 2017)"
)
