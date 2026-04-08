# MillionTwigs — Satellite Vegetation & Tree Analysis Platform

A research-grade pipeline for detecting, counting, and tracking trees and
vegetation cover using satellite imagery from ISRO and open-source providers.
Implements peer-reviewed models for individual tree detection, canopy
segmentation, vegetation indices, and temporal change detection.

---

## Table of Contents

1. [Science Behind the Pipeline](#1-science-behind-the-pipeline)
2. [Data Sources — ISRO](#2-data-sources--isro)
3. [Data Sources — Open Source / International](#3-data-sources--open-source--international)
4. [How to Obtain Imagery Step-by-Step](#4-how-to-obtain-imagery-step-by-step)
5. [Models & Techniques Used](#5-models--techniques-used)
6. [Project Structure](#6-project-structure)
7. [Setup & Installation](#7-setup--installation)
8. [Quick Start](#8-quick-start)
9. [References](#9-references)

---

## 1. Science Behind the Pipeline

### The Core Problem
Counting individual trees from satellite imagery requires solving three distinct
problems:

| Problem | Technique | Sensor Resolution Needed |
|---|---|---|
| Is there vegetation here? | NDVI / EVI indices | ≥ 30 m |
| How much canopy? | Semantic segmentation (U-Net) | ≥ 5 m |
| How many individual trees? | Instance detection (DeepForest / Mask R-CNN) | ≤ 1 m |
| Has it changed? | Change Vector Analysis (CVA) | Same resolution over time |

You choose the right technique based on the resolution of imagery you can obtain
for your area of interest (AOI).

---

## 2. Data Sources — ISRO

India has an exceptional constellation of Earth-observation satellites operated
by ISRO/NRSC. The following are the most useful for vegetation analysis:

### 2.1 Resourcesat-2 / 2A (LISS-III, LISS-IV, AWiFS)

| Sensor | Resolution | Bands | Best Use |
|---|---|---|---|
| LISS-IV MX | **5.8 m** | Green, Red, NIR | Individual tree crowns in dense areas |
| LISS-III | 23.5 m | Blue, Green, Red, SWIR, NIR | Regional NDVI, canopy cover |
| AWiFS | 56 m | Blue, Green, Red, SWIR, NIR | District/state-level vegetation mapping |

LISS-IV's 5.8 m multispectral resolution is the **sweet spot** for canopy
segmentation with U-Net — individual tree crowns become distinguishable.

**Revisit**: 5 days (combined Resourcesat-2 and 2A)

### 2.2 Cartosat-3

| Product | Resolution | Use |
|---|---|---|
| Panchromatic | **0.25 m** | Individual tree counting by crown detection |
| Multispectral | 1 m | Tree crown segmentation with colour |

At 0.25 m Cartosat-3 is the sharpest civilian optical satellite data available
from India and enables per-tree counting in urban and semi-urban areas.

### 2.3 OceanSat-3 (OCM-3)

12-band ocean colour sensor. While designed for marine use, OCM-3's NIR and
SWIR bands can compute broad coastal vegetation indices.

### 2.4 SARAL / AltiKa

Altimetry satellite — useful for deriving canopy height models when combined
with ICESat-2 or GEDI LiDAR.

### 2.5 Where to Access ISRO Data

#### Bhuvan Portal (nrsc.gov.in / bhuvan.nrsc.gov.in)
- **URL**: https://bhuvan.nrsc.gov.in
- **Free tier**: LISS-III, AWiFS archives (up to 5 scenes/request)
- **Steps**:
  1. Register at https://bhuvan-app1.nrsc.gov.in/mda/
  2. Navigate to "Bhuvan Satellite Data Download"
  3. Draw your AOI polygon on the map
  4. Select sensor: RESOURCESAT-2 > LISS-IV or LISS-III
  5. Set date range (for historical comparison, select periods ≥ 1 year apart)
  6. Download GeoTIFF (Level 2 ortho-corrected product recommended)

#### MOSDAC (mosdac.gov.in)
- **URL**: https://mosdac.gov.in
- Operated by Space Applications Centre (SAC), Ahmedabad
- Best for INSAT-3D/3DR data and meteorological products
- Register and use the Catalogue Search

#### NRSC Open EO Data Archive
- **URL**: https://vedas.sac.gov.in/vedas/
- VEDAS (Visualisation of Earth observation Data and Archival System)
- Provides pre-computed NDVI, land-use change products directly

#### How to Get Cartosat-3 Data
Cartosat-3 data for specific sites can be requested through:
- **NRSC Data Dissemination unit**: nrsc-datadissemination@nrsc.gov.in
- Commercial distribution via Antrix Corporation (antrix.gov.in)
- Academic access via RESPOND programme for verified researchers

---

## 3. Data Sources — Open Source / International

These sources are free, easy to access programmatically, and ideal for
historical baselines:

### 3.1 Sentinel-2 (ESA / Copernicus) — RECOMMENDED STARTING POINT

| Property | Value |
|---|---|
| Resolution | **10 m** (RGB + NIR), 20 m (Red-edge, SWIR), 60 m (coastal) |
| Bands | 13 multispectral bands |
| Revisit | 5 days at equator |
| Archive | From 2015 to present |
| Cost | Free |

Sentinel-2's **Red-Edge bands (B5, B6, B7)** are uniquely powerful for
vegetation analysis — they detect chlorophyll content inaccessible to Landsat.

**Access**:
- Copernicus Browser: https://browser.dataspace.copernicus.eu/
- Python API: `sentinelsat` library or `openeo`
- Google Earth Engine: `ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")`

### 3.2 Landsat 8 / 9 (USGS / NASA)

| Property | Value |
|---|---|
| Resolution | 30 m (multispectral), 15 m (panchromatic) |
| Archive | Landsat 5 from **1984** — longest temporal record available |
| Cost | Free |

Use Landsat for long-term historical comparison (e.g., 1990 vs 2024).

**Access**:
- USGS EarthExplorer: https://earthexplorer.usgs.gov
- Python: `landsatxplore` library
- GEE: `ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")`

### 3.3 Google Earth Engine (GEE)

**The most powerful free platform** for time-series vegetation analysis.
Provides server-side processing of petabytes of satellite data — no downloads.

- **URL**: https://code.earthengine.google.com
- **Python API**: `earthengine-api` (`ee`)
- Access ISRO LISS data indirectly through the GEE community catalogue

### 3.4 Planet Labs (Paid, but free for research)

- 3 m resolution daily imagery
- Education & Research programme: https://www.planet.com/markets/education-and-research/
- Best for urban tree canopy work

### 3.5 GEDI (NASA) — Forest Height & Structure

- **Global Ecosystem Dynamics Investigation** — LiDAR from ISS
- 25 m footprint, provides **canopy height, cover fraction, above-ground biomass**
- Access via GEE: `ee.ImageCollection("LARSE/GEDI/GEDI02_A_002_MONTHLY")`
- Python: `gedi-subsetter` tool

### 3.6 Global Forest Watch (Hansen et al.)

- Annual tree cover loss/gain at 30 m since 2000
- **URL**: https://globalforestwatch.org
- GEE: `ee.Image("UMD/hansen/global_forest_change_2023_v1_11")`

### 3.7 OpenStreetMap (OSM)

- Tree positions from community mapping (urban areas, parks)
- Useful as ground truth validation layer
- Overpass API or `osmnx` Python library

---

## 4. How to Obtain Imagery Step-by-Step

### Path A: ISRO Bhuvan (Free, India-specific, higher resolution)

```
1. Go to: https://bhuvan.nrsc.gov.in
2. Click "Data Download" → "Satellite Data"
3. Register/Login
4. Under "2D Viewer", zoom to your AOI
5. Draw bounding box using the AOI tool
6. Select:
   - Satellite: RESOURCESAT-2A
   - Sensor: LISS-IV-MX (for trees) or LISS-III (for regional)
   - Date: Choose two periods separated by ≥ 1 year
   - Processing level: Standard (ortho-corrected)
7. Add to cart → Download ZIP
8. Unzip to data/raw/{year}/
```

### Path B: Sentinel-2 via Copernicus Browser (Easiest start)

```
1. Go to: https://browser.dataspace.copernicus.eu
2. Draw AOI polygon
3. Select "Sentinel-2 L2A" (atmospherically corrected)
4. Filter: Cloud cover < 10%, your date range
5. Download as GeoTIFF (select bands: B02,B03,B04,B08 for basic NDVI)
   For full analysis also download B05,B06,B07,B11,B12
6. Place in: data/raw/sentinel2/{date}/
```

### Path C: Google Earth Engine Python API (Programmatic, best for time series)

See `notebooks/01_data_acquisition.ipynb` for the full workflow. Requires
a Google account with GEE access (free at code.earthengine.google.com).

### Path D: USGS EarthExplorer for historical Landsat

```
1. Go to: https://earthexplorer.usgs.gov
2. Register (free)
3. Enter coordinates of your AOI in "Search Criteria"
4. "Data Sets" → Landsat → Landsat Collection 2 Level-2
5. Select dates from 2+ decades apart for change detection
6. Download: Band files (B4=Red, B5=NIR for Landsat 8)
```

---

## 5. Models & Techniques Used

### 5.1 Vegetation Indices

#### NDVI — Normalized Difference Vegetation Index
**Reference**: Tucker, C.J. (1979). *Remote Sensing of Environment*, 8(2), 127-150.

```
NDVI = (NIR - Red) / (NIR + Red)   range: [-1, 1]

  < 0.1  : Bare soil, rock, water
  0.1–0.3: Sparse vegetation, grassland
  0.3–0.5: Shrubland, degraded forest
  0.5–0.9: Dense forest, healthy canopy
```

#### EVI — Enhanced Vegetation Index
**Reference**: Huete et al. (2002). *Remote Sensing of Environment*, 83(1-2), 195-213.

```
EVI = 2.5 × (NIR - Red) / (NIR + 6×Red - 7.5×Blue + 1)

Better than NDVI in: high-biomass regions, atmospheric correction sensitivity
```

#### NDRE — Red-Edge NDVI (Sentinel-2 only)
**Reference**: Gitelson & Merzlyak (1994). *Journal of Photochemistry and Photobiology B*.

```
NDRE = (NIR - RedEdge) / (NIR + RedEdge)

Superior to NDVI for: stress detection, canopy nitrogen content
```

#### SAVI — Soil-Adjusted Vegetation Index
**Reference**: Huete (1988). *Remote Sensing of Environment*, 25(3), 295-309.

```
SAVI = ((NIR - Red) / (NIR + Red + L)) × (1 + L)    L = 0.5

Better than NDVI in areas with exposed soil (sparse canopy < 40%)
```

### 5.2 Individual Tree Detection (Instance-level)

#### DeepForest
**Reference**: Weinstein, B.G. et al. (2020). *Methods in Ecology and Evolution*, 11(12), 1743-1751.

- Retinanet-based object detector pretrained on 10,000+ labelled tree crowns
  from the NEON AOP dataset (1 m LiDAR-derived CHM + RGB)
- Works on RGB imagery at 0.1–1 m resolution
- Works directly on ISRO Cartosat-3 PAN or Planet 3m imagery
- Python package: `deepforest`

```python
from deepforest import main as df
model = df.deepforest()
model.use_release()   # loads pretrained NEON weights
boxes = model.predict_image(path="cartosat_scene.tif", return_plot=False)
# returns: xmin, ymin, xmax, ymax, score for each detected crown
```

**Accuracy**: 69–83% F1 on temperate forests (adapts with fine-tuning on local data)

#### Mask R-CNN (Instance Segmentation)
**Reference**: He et al. (2017). *ICCV 2017*.

Used when you need tree crown polygons (not just bounding boxes).
Requires labelled training data for the specific region/sensor.

#### Segment Anything Model (SAM) — Zero-shot
**Reference**: Kirillov et al. (2023). *ICCV 2023* — Meta AI Research.

SAM can segment individual tree crowns from high-resolution imagery without
any training data. Used as a fast labelling tool or in zero-shot mode.

```python
# Combine SAM + NDVI mask to isolate vegetation, then count segments
```

### 5.3 Canopy Cover Segmentation (Pixel-level)

#### U-Net
**Reference**: Ronneberger, O., Fischer, P., Bröker, T. (2015). *MICCAI 2015*.

Standard encoder-decoder architecture for binary canopy/non-canopy pixel
classification. Works at 5–10 m resolution (LISS-IV, Sentinel-2).

**Pre-trained weights available**: `segmentation-models-pytorch` library with
ImageNet-pretrained encoders (ResNet50, EfficientNet-B4).

#### Random Forest / XGBoost (Classical ML Baseline)
**Reference**: Breiman, L. (2001). *Machine Learning*, 45(1), 5-32.

Classify each pixel using spectral features (NDVI, EVI, NDWI, all band ratios)
+ texture features (GLCM entropy, contrast). Excellent interpretability and
works well when labelled data is limited.

### 5.4 Change Detection

#### Post-Classification Comparison (PCC)
Compare classified land-cover maps from two dates. Simple but error accumulation
from two independent classifications.

#### Change Vector Analysis (CVA)
**Reference**: Malila, W.A. (1980). *LARS Symposia*, 385.

Computes a change vector in spectral feature space between T1 and T2 imagery.
Magnitude = amount of change, Direction = type of change (deforestation vs
regrowth). Does not require intermediate classification.

```
ΔV = [ΔNDVI, ΔEVI, ΔNIR, ΔSWIR]
Magnitude = ||ΔV||
Direction = atan2(ΔNDVI, ΔSWIR)   # vegetation loss vs gain
```

#### LandTrendr (Temporal Segmentation)
**Reference**: Kennedy et al. (2010). *Remote Sensing of Environment*, 114(12), 2897-2910.

Fits temporal trajectories to Landsat time-series to detect abrupt and gradual
change events. Available in GEE.

```javascript
// Google Earth Engine
var lt = ee.Algorithms.TemporalSegmentation.LandTrendr(params);
```

### 5.5 Tree Count Estimation from Canopy Cover

When only medium-resolution imagery is available (10–30 m), individual trees
cannot be resolved. Use allometric extrapolation:

```
N_trees ≈ Canopy_Area(m²) / Mean_Crown_Area(m²)

Mean crown area varies by biome:
  Tropical forest: 25–60 m²/tree
  Dry deciduous:   15–35 m²/tree
  Urban trees:     10–25 m²/tree
  Agroforestry:    8–20 m²/tree

Source: Jucker et al. (2017), Global Change Biology — crown-diameter allometry
```

---

## 6. Project Structure

```
MillionTwigs/
├── README.md
├── requirements.txt
├── config.yaml                       # AOI, date ranges, sensor preferences
├── src/
│   ├── data/
│   │   ├── bhuvan_downloader.py      # ISRO Bhuvan / NRSC data client
│   │   ├── gee_downloader.py         # Google Earth Engine client
│   │   ├── sentinel_downloader.py    # Copernicus Sentinel-2 client
│   │   ├── landsat_downloader.py     # USGS Landsat client
│   │   └── gedi_downloader.py        # NASA GEDI LiDAR client
│   ├── preprocessing/
│   │   ├── atmospheric_correction.py # DOS1 / py6S correction
│   │   ├── cloud_masking.py          # Sen2Cor / s2cloudless
│   │   ├── harmonization.py          # Co-register multi-date images
│   │   └── image_utils.py            # Tile, reproject, band-stack
│   ├── analysis/
│   │   ├── indices.py                # NDVI, EVI, NDRE, SAVI, NDWI
│   │   ├── tree_detection.py         # DeepForest + SAM integration
│   │   ├── canopy_segmentation.py    # U-Net inference + postprocessing
│   │   ├── pixel_classification.py   # Random Forest / XGBoost
│   │   ├── change_detection.py       # CVA + PCC change maps
│   │   └── tree_count.py             # Crown → count, allometric estimate
│   ├── models/
│   │   ├── unet.py                   # U-Net architecture (PyTorch)
│   │   ├── deepforest_wrapper.py     # DeepForest inference wrapper
│   │   └── sam_wrapper.py            # SAM zero-shot segmentation
│   └── visualization/
│       ├── maps.py                   # Folium interactive maps
│       └── reports.py                # PDF/HTML summary report
├── notebooks/
│   ├── 01_data_acquisition.ipynb     # Download data from all sources
│   ├── 02_preprocessing.ipynb        # Cloud mask, correct, stack
│   ├── 03_vegetation_indices.ipynb   # Compute + visualize NDVI/EVI
│   ├── 04_tree_detection.ipynb       # Run DeepForest / U-Net
│   └── 05_change_analysis.ipynb      # Historical comparison
├── scripts/
│   ├── run_pipeline.py               # End-to-end CLI runner
│   └── validate_ground_truth.py      # Accuracy assessment
└── docs/
    └── sensor_band_reference.md      # Band numbers per satellite
```

---

## 7. Setup & Installation

### Prerequisites

- Python 3.10+
- GDAL system library: `sudo apt-get install gdal-bin libgdal-dev`
- Google Earth Engine account (free): https://code.earthengine.google.com/register

### Install

```bash
git clone https://github.com/abhisekparichha/milliontwigs
cd MillionTwigs

python -m venv .venv
source .venv/bin/activate          # Linux/Mac
# .venv\Scripts\activate           # Windows

pip install -r requirements.txt

# Authenticate GEE (one-time)
earthengine authenticate

# Verify
python -c "import ee; ee.Initialize(); print('GEE OK')"
```

---

## 8. Quick Start

### 8.1 Configure your AOI

Edit `config.yaml`:
```yaml
aoi:
  name: "My Study Area"
  bbox: [75.123, 12.456, 75.789, 12.890]   # [min_lon, min_lat, max_lon, max_lat]

dates:
  baseline:  "2015-01-01/2015-12-31"        # historical period
  current:   "2024-01-01/2024-12-31"        # recent period

cloud_cover_max: 10   # percent
```

### 8.2 Run Full Pipeline

```bash
python scripts/run_pipeline.py \
  --config config.yaml \
  --source sentinel2 \
  --method deepforest \
  --output results/
```

### 8.3 Jupyter Notebooks

```bash
jupyter lab notebooks/
# Start with 01_data_acquisition.ipynb
```

---

## 9. References

1. Tucker, C.J. (1979). Red and photographic infrared linear combinations for
   monitoring vegetation. *Remote Sensing of Environment*, 8(2), 127-150.

2. Huete, A. et al. (2002). Overview of the radiometric and biophysical
   performance of the MODIS vegetation indices. *Remote Sensing of Environment*,
   83(1-2), 195-213.

3. Weinstein, B.G. et al. (2020). DeepForest: A Python Package for RGB Deep
   Learning Tree Crown Detection. *Methods in Ecology and Evolution*, 11, 1743-1751.

4. Ronneberger, O., Fischer, P., Bröker, T. (2015). U-Net: Convolutional
   Networks for Biomedical Image Segmentation. *MICCAI 2015*, LNCS 9351, 234-241.

5. He, K. et al. (2017). Mask R-CNN. *ICCV 2017*, 2961-2969.

6. Kirillov, A. et al. (2023). Segment Anything. *ICCV 2023*, 4015-4026.
   Meta AI Research.

7. Kennedy, R.E. et al. (2010). Detecting trends in forest disturbance and
   recovery using yearly Landsat time series: LandTrendr. *Remote Sensing of
   Environment*, 114(12), 2897-2910.

8. Malila, W.A. (1980). Change vector analysis: An approach for detecting
   forest changes with Landsat. *LARS Symposia*, 385.

9. Breiman, L. (2001). Random Forests. *Machine Learning*, 45(1), 5-32.

10. Jucker, T. et al. (2017). Allometric equations for integrating remote
    sensing imagery into forest monitoring programmes. *Global Change Biology*,
    23(1), 177-190.

11. Hansen, M.C. et al. (2013). High-Resolution Global Maps of 21st-Century
    Forest Cover Change. *Science*, 342(6160), 850-853.

12. Huete, A.R. (1988). A soil-adjusted vegetation index (SAVI). *Remote
    Sensing of Environment*, 25(3), 295-309.

13. Gitelson, A.A. & Merzlyak, M.N. (1994). Spectral reflectance changes
    associated with autumn senescence of *Aesculus hippocastanum* L. and
    *Acer platanoides* L. leaves. *Journal of Photochemistry and Photobiology B*,
    22(3), 247-244.
