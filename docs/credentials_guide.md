# Data Source Credentials & Access Guide

Step-by-step registration for every satellite data source used in MillionTwigs.

---

## Quick Setup (do this first)

```bash
# 1. Copy the template
cp .env.example .env

# 2. Open .env and fill in your credentials
nano .env          # or use VS Code: code .env

# 3. Verify all credentials are detected
python -m src.config.credentials

# 4. Install python-dotenv so .env loads automatically
pip install python-dotenv
```

The checker will show exactly which credentials are set and which are missing:
```
MillionTwigs — Credential Status Check
=============================================
📄 .env file found

  GEE_PROJECT              ✅ set
  COPERNICUS_USER          ✅ set
  COPERNICUS_PASSWORD      ✅ set
  LANDSATXPLORE_USERNAME   ❌ missing
  LANDSATXPLORE_PASSWORD   ❌ missing
  EARTHDATA_USERNAME       ✅ set
  EARTHDATA_PASSWORD       ✅ set
  BHUVAN_USER              ❌ missing
  BHUVAN_PASSWORD          ❌ missing
```

---

## Where Each Credential Is Used in the Code

| Environment Variable | Used in file | Purpose |
|---|---|---|
| `GEE_PROJECT` | `src/data/gee_downloader.py` → `initialize_gee()` | Sentinel-2, Landsat, GEDI, Hansen via GEE |
| `COPERNICUS_USER` | `src/data/sentinel_downloader.py` → `_get_credentials()` | Direct Sentinel-2 download |
| `COPERNICUS_PASSWORD` | `src/data/sentinel_downloader.py` → `_get_credentials()` | Direct Sentinel-2 download |
| `LANDSATXPLORE_USERNAME` | `src/data/landsat_downloader.py` → `_get_credentials()` | Landsat search & download |
| `LANDSATXPLORE_PASSWORD` | `src/data/landsat_downloader.py` → `_get_credentials()` | Landsat search & download |
| `EARTHDATA_USERNAME` | `src/config/credentials.py` → `get_nasa()` | GEDI direct download |
| `EARTHDATA_PASSWORD` | `src/config/credentials.py` → `get_nasa()` | GEDI direct download |
| `BHUVAN_USER` | `src/data/bhuvan_downloader.py` → `_get_bhuvan_credentials()` | ISRO Bhuvan data |
| `BHUVAN_PASSWORD` | `src/data/bhuvan_downloader.py` → `_get_bhuvan_credentials()` | ISRO Bhuvan data |

All credentials flow through `src/config/credentials.py` which:
- Loads `.env` automatically via python-dotenv
- Validates each credential before use
- Raises a `CredentialError` with the exact registration URL if anything is missing

---

---

## 1. ISRO Bhuvan / NRSC (India)

ISRO data is spread across **three separate portals** — each requires its own account.

---

### 1A. Bhuvan Satellite Data Download (LISS-III, LISS-IV, AWiFS — Free)

**URL**: https://bhuvan-app1.nrsc.gov.in/mda/

**What you get**: Resourcesat-2/2A LISS-III (23.5 m), LISS-IV (5.8 m), AWiFS (56 m)
Free for Indian citizens and researchers. Archives from ~2009.

**Registration steps**:
```
1. Go to: https://bhuvan-app1.nrsc.gov.in/mda/
2. Click "New User Registration"
3. Fill in:
     - Name (your full name)
     - Organisation (university / company / individual)
     - Designation
     - Email address (use institutional email if possible — faster approval)
     - Purpose of use: "Research / Vegetation Analysis"
     - Country: India
4. Submit → you receive an activation email within 1–3 working days
5. Activate via email link → set your password
6. Login at: https://bhuvan-app1.nrsc.gov.in/mda/
```

**After login — download data**:
```
1. Go to: https://bhuvan.nrsc.gov.in → top menu → "Data Download"
2. Click "Satellite Data"
3. Choose sensor from the tree:
     RESOURCESAT-2A → LISS-IV-MX  (for trees/canopy, 5.8 m)
     RESOURCESAT-2A → LISS-III    (for regional NDVI, 23.5 m)
4. Draw your AOI bounding box on the map
5. Set date range (tip: pick Jan–May to avoid monsoon cloud cover)
6. Select "L2 — Standard Geocoded" (ortho-corrected, free)
7. Click "Search" → select scenes → "Add to Cart"
8. Cart → "Place Order" → receive download link by email (usually within 24 hrs)
```

**File format**: GeoTIFF, separate file per band. Band naming:
```
Band 2 = Green (0.52–0.59 µm)
Band 3 = Red   (0.62–0.68 µm)
Band 4 = NIR   (0.77–0.86 µm)
```

---

### 1B. NRSC Open Data Archive (LULC maps, pre-processed products)

**URL**: https://bhuvan.nrsc.gov.in/bhuvan_links.php#

Free land-use / land-cover maps at 1:50,000 scale, vegetation health maps, NDVI
products. No download registration needed — use Bhuvan login from 1A.

**Useful pre-processed NRSC products** (no processing needed):
- National LULC (2019–20) — district-level tree cover
- Wasteland Atlas — degraded land identification
- Forest cover maps — cross-validate your NDVI analysis

---

### 1C. Cartosat-3 (0.25 m — Academic access via RESPOND Programme)

Cartosat-3 at sub-metre resolution is **not freely available** but accessible to
Indian researchers under the RESPOND programme.

**Eligibility**: Faculty / researchers at Indian universities (IITs, IISc, NIT, etc.)

**Application process**:
```
Email: nrsc-respond@nrsc.gov.in
Subject: "Data Request — Cartosat-3 for Vegetation Research"

Include in the email:
  - Your name, designation, institution
  - PI (Principal Investigator) details if applicable
  - Project title and brief abstract (2–3 lines)
  - AOI description (district, state, approx. coordinates)
  - Date range required
  - Justification: why Cartosat-3 resolution is needed
  - Whether you have an active DST/DBT/ISRO-sponsored project

Typical turnaround: 2–4 weeks
Data delivered: via secure download link or physical media
```

**Commercial alternative** (Antrix Corporation):
```
URL: https://www.antrix.gov.in/staticPages/satimage.jsp
Email: sales@antrix.gov.in
Pricing: Negotiated per-scene, generally ₹3,000–₹15,000 per scene
```

---

### 1D. MOSDAC — Meteorological & Oceanographic Data (SAC, Ahmedabad)

**URL**: https://mosdac.gov.in

Useful for: INSAT-3D cloud masks, Kalpana-1 data, vegetation drought indices.

```
1. Go to: https://mosdac.gov.in
2. Click "Register" (top right)
3. Fill form: name, email, organisation, purpose
4. Activate via email
5. Login → Catalogue → search your AOI and date range
6. Products relevant to vegetation:
     - INSAT-3D VIS/NIR (1 km)
     - Vegetation Health Index (VHI)
     - Soil Moisture
```

---

### 1E. VEDAS — Pre-computed NDVI & Vegetation Products (SAC)

**URL**: https://vedas.sac.gov.in/vedas/

**No account needed** for viewing. Registration required for bulk data download.

Provides ready-to-use:
- Monthly NDVI composites (Resourcesat AWiFS)
- Vegetation Condition Index (VCI)
- Normalised Difference Drought Index (NDDI)
- Crop health monitoring layers

```
1. Go to: https://vedas.sac.gov.in/vedas/
2. Select "Vegetation" from the left panel
3. Choose product, date, and state
4. Download CSV / GeoTIFF directly (no login for small areas)
5. For bulk access: email vedas@sac.gov.in
```

---

## 2. Google Earth Engine (GEE)

Provides Sentinel-2, Landsat, GEDI, Hansen GFC and more — **processed server-side,
no large downloads needed**.

**URL**: https://code.earthengine.google.com/register

**Cost**: Free for non-commercial use (research, education, NGO).
Commercial use requires a paid Google Cloud project.

**Registration steps**:
```
1. Go to: https://code.earthengine.google.com/register
2. Sign in with your Google account
3. Select "Use with a noncommercial Cloud project"
4. Create a new Google Cloud project (or use an existing one):
     - Project name: milliontwigs-analysis (or anything)
     - Organisation: leave empty for personal use
5. Fill the GEE registration form:
     - Affiliation: university / research institution / NGO
     - Use case: "Forest and vegetation monitoring research"
     - Description: brief 2–3 sentence project description
6. Submit — approval typically takes minutes to 24 hours
   (institutional emails get faster approval)
```

**Authenticate in Python** (one-time, run in terminal):
```bash
pip install earthengine-api
earthengine authenticate
# Opens a browser → sign in with your Google account → copy the token
# Paste the token back into the terminal
```

**Verify it works**:
```python
import ee
ee.Initialize()
print(ee.Image("COPERNICUS/S2_SR_HARMONIZED").bandNames().getInfo())
```

**Note on project ID**: GEE now requires a Cloud project ID.
```python
ee.Initialize(project="your-cloud-project-id")
# Or set env var: GOOGLE_CLOUD_PROJECT=your-cloud-project-id
```

---

## 3. Copernicus Dataspace — Sentinel-2 (ESA)

**URL**: https://dataspace.copernicus.eu

Free Sentinel-2 L2A (atmospherically corrected) data globally from 2015.

**Registration steps**:
```
1. Go to: https://dataspace.copernicus.eu
2. Click "Register" (top right)
3. Fill in: name, email, country, organisation
4. Verify email
5. Login at: https://browser.dataspace.copernicus.eu
```

**Manual download** (browser):
```
1. Open: https://browser.dataspace.copernicus.eu
2. Search your location on the map
3. Left panel: Select "Sentinel-2" → "L2A"
4. Set date range, cloud cover filter (< 10%)
5. Click on a scene → "Download" → select bands:
     For NDVI: B04 (Red), B08 (NIR)
     For EVI:  B02 (Blue), B04, B08
     For NDRE: B05 (Red-Edge), B08A
     For NBR:  B08, B12 (SWIR2)
```

**Set environment variables for sentinelsat** (used in sentinel_downloader.py):
```bash
export COPERNICUS_USER="your_email@example.com"
export COPERNICUS_PASSWORD="your_password"
```

Or add to a `.env` file (already in .gitignore):
```
COPERNICUS_USER=your_email@example.com
COPERNICUS_PASSWORD=your_password
```

---

## 4. USGS EarthExplorer — Landsat 8/9 (Historical from 1984)

**URL**: https://earthexplorer.usgs.gov

Free Landsat Collection 2 Level-2 (surface reflectance, cloud-masked). Archive
goes back to **Landsat 5 in 1984** — the only freely available 40-year record.

**Registration steps**:
```
1. Go to: https://ers.cr.usgs.gov/register
2. Fill form: name, email, username, password, address
3. Select affiliation: Research / Academic / Government
4. Verify email → account active immediately
```

**Search and download**:
```
1. Go to: https://earthexplorer.usgs.gov
2. Enter coordinates (or draw polygon) in "Search Criteria"
3. Set date range
4. "Data Sets" tab → Landsat → "Landsat Collection 2 Level-2"
   Select: Landsat 8-9 OLI/TIRS C2 L2  (for 2013–present)
   Select: Landsat 4-5 TM C2 L2         (for 1982–2012 history)
5. "Results" tab → click the download icon on each scene
6. Download: "Product Bundle" (all bands) or individual band files
```

**For landsatxplore (programmatic)**:
```bash
export LANDSATXPLORE_USERNAME="your_usgs_username"
export LANDSATXPLORE_PASSWORD="your_usgs_password"
```

---

## 5. NASA Earthdata — GEDI LiDAR & MODIS

**URL**: https://urs.earthdata.nasa.gov

Required for GEDI canopy height data, MODIS NDVI, and HLS (Harmonized Landsat Sentinel).

**Registration steps**:
```
1. Go to: https://urs.earthdata.nasa.gov/users/new
2. Fill in: username, password, email, country, affiliation
3. Verify email → account active immediately
4. Agree to EOSDIS Terms and GES-DISC Application
```

**GEDI download via Python**:
```bash
pip install gedi-subsetter
# or access directly via GEE: ee.ImageCollection("LARSE/GEDI/GEDI02_A_002_MONTHLY")
```

**MODIS NDVI via GEE** (no download needed):
```python
modis = ee.ImageCollection("MODIS/061/MOD13Q1").select("NDVI")
```

---

## 6. Environment Variables Summary

Add all credentials to a `.env` file in the project root
(already in `.gitignore` — will never be committed):

```bash
# .env — DO NOT COMMIT THIS FILE

# Google Earth Engine (set after running: earthengine authenticate)
GEE_PROJECT=your-google-cloud-project-id

# Copernicus Dataspace (Sentinel-2)
COPERNICUS_USER=your_email@example.com
COPERNICUS_PASSWORD=your_password

# USGS EarthExplorer (Landsat)
LANDSATXPLORE_USERNAME=your_usgs_username
LANDSATXPLORE_PASSWORD=your_usgs_password

# NASA Earthdata (GEDI, MODIS)
EARTHDATA_USERNAME=your_earthdata_username
EARTHDATA_PASSWORD=your_earthdata_password

# ISRO Bhuvan (used in future API integration)
BHUVAN_USER=your_bhuvan_email
BHUVAN_PASSWORD=your_bhuvan_password
```

**Load in Python**:
```python
from dotenv import load_dotenv
import os
load_dotenv()

gee_project   = os.environ["GEE_PROJECT"]
cop_user      = os.environ["COPERNICUS_USER"]
```

---

## 7. Approval Wait Times Summary

| Source | Registration | Approval Time | Cost |
|---|---|---|---|
| ISRO Bhuvan (LISS-IV, LISS-III) | Online form | 1–3 working days | Free |
| ISRO MOSDAC | Online form | 1–2 days | Free |
| ISRO VEDAS | None needed | Instant | Free |
| Cartosat-3 (RESPOND) | Email to NRSC | 2–4 weeks | Free (academic) |
| Google Earth Engine | Online form | Minutes–24 hrs | Free (non-commercial) |
| Copernicus Dataspace | Online form | Instant | Free |
| USGS EarthExplorer | Online form | Instant | Free |
| NASA Earthdata | Online form | Instant | Free |

---

## 8. Recommended Order of Registration

Register in this order — easiest first, most time-consuming last:

```
Day 1 (instant):
  ✅ Copernicus Dataspace   → sentinel-2, works in minutes
  ✅ USGS EarthExplorer     → landsat 40-year archive, works in minutes
  ✅ NASA Earthdata          → GEDI canopy height, works in minutes
  ✅ Google Earth Engine     → start registration (may take up to 24 hrs)

Day 1–2:
  ✅ ISRO Bhuvan / MDA       → submit registration, wait for email approval

When running code:
  ✅ earthengine authenticate → run once in terminal after GEE approval

Only if needed for < 1 m imagery (weeks later):
  📧 Cartosat-3 RESPOND email → nrsc-respond@nrsc.gov.in
```
