"""
ISRO Bhuvan / NRSC data downloader guide and helpers.

Bhuvan does not expose a public REST API for bulk programmatic downloads.
Data access is via:
  1. Web portal manual download: https://bhuvan.nrsc.gov.in
  2. Bhuvan WMS/WCS services (view-only, not full-resolution download)
  3. VEDAS portal for pre-processed products: https://vedas.sac.gov.in
  4. NRSC Direct Data Products (DDP) — formal request via email/portal

This module provides:
  - WMS access to Bhuvan layers for quick previews
  - Helper functions for working with downloaded ISRO GeoTIFF products
  - Metadata parsing for RESOURCESAT and CARTOSAT products
  - Band stacking utilities specific to LISS-III, LISS-IV, AWiFS band ordering

ISRO sensor band order reference (Resourcesat-2):
  LISS-III:  B2=Green(0.52-0.59µm), B3=Red(0.62-0.68µm),
             B4=NIR(0.77-0.86µm),   B5=SWIR(1.55-1.70µm)
  LISS-IV MX: B2=Green, B3=Red, B4=NIR  (3-band multispectral)
  AWiFS:     B2=Green, B3=Red, B4=NIR, B5=SWIR

Data Access Procedure (Manual):
  1. Register at: https://bhuvan-app1.nrsc.gov.in/mda/
  2. Log in to Bhuvan portal: https://bhuvan.nrsc.gov.in
  3. Navigate: Data Download → Satellite Data → RESOURCESAT-2 or CARTOSAT-3
  4. Draw AOI using the bounding box tool
  5. Select sensor, date range, processing level (L2 ortho-corrected)
  6. Submit request → receive notification email with download link
  7. Download ZIP → extract to data/raw/bhuvan/{sensor}/{date}/
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np


def _get_bhuvan_credentials() -> tuple:
    """Load ISRO Bhuvan credentials from environment / .env file.

    Set these in your .env file (copy from .env.example):
        BHUVAN_USER=your_registered_email
        BHUVAN_PASSWORD=your_password

    Registration (free, 1–3 working days): https://bhuvan-app1.nrsc.gov.in/mda/
    See docs/credentials_guide.md §1A for full registration steps.

    NOTE: Bhuvan does not provide a public REST API for bulk downloads.
    These credentials are used for:
      - WMS authenticated layer access
      - Future API integration if NRSC opens programmatic access
    For now, data download remains a manual portal workflow.
    """
    try:
        from src.config.credentials import get_bhuvan
        creds = get_bhuvan()
        return creds.user, creds.password
    except ImportError:
        user = os.environ.get("BHUVAN_USER")
        password = os.environ.get("BHUVAN_PASSWORD")
        if not user or not password:
            raise EnvironmentError(
                "Set BHUVAN_USER and BHUVAN_PASSWORD in your .env file.\n"
                "Register at: https://bhuvan-app1.nrsc.gov.in/mda/\n"
                "Approval takes 1–3 working days.\n"
                "See: docs/credentials_guide.md §1A"
            )
        return user, password

try:
    import rasterio
    from rasterio.crs import CRS
    from rasterio.merge import merge
    from rasterio.warp import calculate_default_transform, reproject, Resampling
    _RASTERIO_AVAILABLE = True
except ImportError:
    _RASTERIO_AVAILABLE = False


# ── ISRO Sensor Metadata ───────────────────────────────────────────────────────

ISRO_SENSORS: Dict[str, Dict] = {
    "LISS-III": {
        "satellite": "Resourcesat-2/2A",
        "resolution_m": 23.5,
        "bands": {
            "B2": {"name": "Green",  "wavelength": (0.52, 0.59)},
            "B3": {"name": "Red",    "wavelength": (0.62, 0.68)},
            "B4": {"name": "NIR",    "wavelength": (0.77, 0.86)},
            "B5": {"name": "SWIR",   "wavelength": (1.55, 1.70)},
        },
        "ndvi_bands": ("B4", "B3"),   # (NIR, Red)
        "revisit_days": 24,
        "swath_km": 141,
    },
    "LISS-IV-MX": {
        "satellite": "Resourcesat-2/2A",
        "resolution_m": 5.8,
        "bands": {
            "B2": {"name": "Green", "wavelength": (0.52, 0.59)},
            "B3": {"name": "Red",   "wavelength": (0.62, 0.68)},
            "B4": {"name": "NIR",   "wavelength": (0.77, 0.86)},
        },
        "ndvi_bands": ("B4", "B3"),
        "revisit_days": 5,
        "swath_km": 70,
        "note": "Best for canopy segmentation — resolves individual tree crowns in open areas",
    },
    "LISS-IV-PAN": {
        "satellite": "Resourcesat-2/2A",
        "resolution_m": 5.8,
        "bands": {
            "PAN": {"name": "Panchromatic", "wavelength": (0.50, 0.75)},
        },
        "revisit_days": 5,
        "swath_km": 23,
    },
    "AWiFS": {
        "satellite": "Resourcesat-2/2A",
        "resolution_m": 56,
        "bands": {
            "B2": {"name": "Green", "wavelength": (0.52, 0.59)},
            "B3": {"name": "Red",   "wavelength": (0.62, 0.68)},
            "B4": {"name": "NIR",   "wavelength": (0.77, 0.86)},
            "B5": {"name": "SWIR",  "wavelength": (1.55, 1.70)},
        },
        "ndvi_bands": ("B4", "B3"),
        "revisit_days": 5,
        "swath_km": 740,
        "note": "Best for district/state scale vegetation mapping",
    },
    "CARTOSAT-3-PAN": {
        "satellite": "Cartosat-3",
        "resolution_m": 0.25,
        "bands": {
            "PAN": {"name": "Panchromatic", "wavelength": (0.45, 0.90)},
        },
        "revisit_days": 4,
        "swath_km": 16,
        "note": "Highest resolution — enables per-tree counting via DeepForest",
    },
    "CARTOSAT-3-MX": {
        "satellite": "Cartosat-3",
        "resolution_m": 1.0,
        "bands": {
            "B1": {"name": "Blue",  "wavelength": (0.45, 0.52)},
            "B2": {"name": "Green", "wavelength": (0.52, 0.60)},
            "B3": {"name": "Red",   "wavelength": (0.63, 0.69)},
            "B4": {"name": "NIR",   "wavelength": (0.77, 0.89)},
        },
        "ndvi_bands": ("B4", "B3"),
        "revisit_days": 4,
        "swath_km": 16,
    },
}


def get_sensor_info(sensor_name: str) -> Dict:
    """Return metadata dict for a given ISRO sensor name."""
    if sensor_name not in ISRO_SENSORS:
        raise ValueError(
            f"Unknown sensor '{sensor_name}'. "
            f"Available: {list(ISRO_SENSORS.keys())}"
        )
    return ISRO_SENSORS[sensor_name]


def recommend_sensor(
    resolution_needed_m: float,
    requires_nir: bool = True,
    aoi_size_km2: float = 100,
) -> List[str]:
    """Recommend ISRO sensors based on analysis requirements.

    Args:
        resolution_needed_m: target pixel size (e.g. 5 for canopy, 25 for regional)
        requires_nir:        True if NDVI/EVI computation is needed
        aoi_size_km2:        area of interest in km²

    Returns:
        Sorted list of recommended sensor names
    """
    recommendations = []
    for name, info in ISRO_SENSORS.items():
        if info["resolution_m"] > resolution_needed_m * 5:
            continue
        if requires_nir and "NIR" not in [b["name"] for b in info["bands"].values()]:
            continue
        recommendations.append((name, info["resolution_m"]))
    recommendations.sort(key=lambda x: x[1])
    return [r[0] for r in recommendations]


# ── File utilities for downloaded ISRO products ────────────────────────────────

def stack_liss_bands(band_files: Dict[str, Path], output_path: Path) -> Path:
    """Stack individual LISS band GeoTIFFs into a single multi-band file.

    ISRO products are distributed as separate single-band GeoTIFFs.
    This function stacks them in the correct order for analysis.

    Args:
        band_files:  Dict mapping band name (e.g. "B2") to file Path
        output_path: Output path for the stacked GeoTIFF

    Returns:
        Path to the stacked output file
    """
    if not _RASTERIO_AVAILABLE:
        raise ImportError("rasterio is required. Run: pip install rasterio")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    ordered_bands = sorted(band_files.keys())
    src_files = [rasterio.open(band_files[b]) for b in ordered_bands]

    meta = src_files[0].meta.copy()
    meta.update(count=len(src_files), driver="GTiff", compress="deflate")

    with rasterio.open(output_path, "w", **meta) as dst:
        for i, src in enumerate(src_files, start=1):
            dst.write(src.read(1), i)
            dst.update_tags(i, band_name=ordered_bands[i - 1])

    for src in src_files:
        src.close()

    print(f"Stacked {len(ordered_bands)} bands → {output_path}")
    return output_path


def reproject_to_wgs84(input_path: Path, output_path: Path) -> Path:
    """Reproject a raster to WGS-84 geographic coordinates (EPSG:4326).

    ISRO products are often delivered in UTM or a local Indian TM projection.
    Reprojecting to WGS-84 enables direct comparison with Sentinel-2/Landsat.
    """
    if not _RASTERIO_AVAILABLE:
        raise ImportError("rasterio is required.")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dst_crs = CRS.from_epsg(4326)

    with rasterio.open(input_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, dst_crs, src.width, src.height, *src.bounds
        )
        meta = src.meta.copy()
        meta.update(
            crs=dst_crs,
            transform=transform,
            width=width,
            height=height,
            compress="deflate",
        )
        with rasterio.open(output_path, "w", **meta) as dst:
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=dst_crs,
                    resampling=Resampling.bilinear,
                )
    print(f"Reprojected → {output_path}")
    return output_path


def normalise_dn_to_reflectance(
    array: np.ndarray,
    sensor: str = "LISS-IV-MX",
    gain: float = 1.0,
    offset: float = 0.0,
) -> np.ndarray:
    """Convert raw digital numbers (DN) to surface reflectance [0, 1].

    ISRO L1 products contain DN values. L2 products are already in reflectance
    units. Always prefer L2 (ortho-corrected + reflectance calibrated) data.

    For L1 DN conversion the formula is:
        Reflectance = (DN × gain + offset) / π × (d² / E₀ × cos(θ))

    In practice, for most vegetation analysis the simpler linear scaling:
        Reflectance ≈ DN / DN_max
    is used as a first approximation when calibration coefficients are unknown.

    Args:
        array:  Input array of DN values (float)
        sensor: ISRO sensor name (for reference only)
        gain:   Radiometric gain coefficient from product metadata
        offset: Radiometric offset coefficient from product metadata

    Returns:
        Reflectance array in range [0, 1]
    """
    reflectance = (array.astype(np.float32) * gain + offset)
    reflectance = np.clip(reflectance / 10000.0, 0.0, 1.0)
    return reflectance


# ── Bhuvan WMS helper (preview tiles only) ────────────────────────────────────

BHUVAN_WMS_BASE = "https://bhuvan-vec2.nrsc.gov.in/bhuvan/gwc/service/wms"

BHUVAN_WMS_LAYERS = {
    "liss3_india": "bhuvan:liss3_india",
    "liss4_india": "bhuvan:liss4_india",
    "ndvi_india":  "bhuvan:ndvi_india",
    "lulc_india":  "bhuvan:lulc_india",
}

def get_bhuvan_wms_url(layer: str, bbox: List[float], width: int = 512, height: int = 512) -> str:
    """Build a Bhuvan WMS GetMap URL for preview purposes.

    NOTE: WMS returns a rendered PNG image at screen resolution — it is NOT
    suitable for analysis. Use this only for visual inspection and planning.
    For actual analysis data, use the Bhuvan download portal.

    Args:
        layer: One of the keys in BHUVAN_WMS_LAYERS
        bbox:  [min_lon, min_lat, max_lon, max_lat]

    Returns:
        WMS GetMap URL string
    """
    if layer not in BHUVAN_WMS_LAYERS:
        raise ValueError(f"layer must be one of {list(BHUVAN_WMS_LAYERS.keys())}")
    layer_name = BHUVAN_WMS_LAYERS[layer]
    min_lon, min_lat, max_lon, max_lat = bbox
    return (
        f"{BHUVAN_WMS_BASE}?"
        f"SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap"
        f"&LAYERS={layer_name}"
        f"&BBOX={min_lon},{min_lat},{max_lon},{max_lat}"
        f"&WIDTH={width}&HEIGHT={height}"
        f"&FORMAT=image/png&SRS=EPSG:4326"
    )


def print_access_guide() -> None:
    """Print a step-by-step guide for accessing ISRO data."""
    guide = """
    ┌─────────────────────────────────────────────────────────────────┐
    │          ISRO Satellite Data Access — Step-by-Step Guide        │
    └─────────────────────────────────────────────────────────────────┘

    FREE DATA (Resourcesat-2 LISS-III, LISS-IV, AWiFS):
    ─────────────────────────────────────────────────────
    1. Register:  https://bhuvan-app1.nrsc.gov.in/mda/
    2. Portal:    https://bhuvan.nrsc.gov.in → "Data Download"
    3. Draw your AOI on the map using the Rectangle/Polygon tool
    4. Choose sensor: RESOURCESAT-2A → LISS-IV-MX (for trees)
    5. Date range: pick dry season (Jan–May) to avoid cloud cover
    6. Processing: select "L2 Ortho-corrected" (standard, free)
    7. Submit → get email notification → download ZIP

    HIGH RESOLUTION (Cartosat-3 at 0.25m):
    ─────────────────────────────────────────
    Academic access via RESPOND Programme:
      Email: nrsc-respond@nrsc.gov.in
      Include: institution, PI name, project summary, AOI, date range

    Commercial access via Antrix Corporation:
      URL: https://www.antrix.gov.in/staticPages/satimage.jsp

    VEDAS (Pre-processed products — NDVI, LULC):
    ──────────────────────────────────────────────
    URL: https://vedas.sac.gov.in/vedas/
    No download required — interactive analysis in browser
    Provides: NDVI time series, vegetation health maps, fire alerts

    MOSDAC (Meteorological + Oceansat data):
    ─────────────────────────────────────────
    URL: https://mosdac.gov.in
    Best for: INSAT-3D cloud masks, Oceansat vegetation indices

    NRSC Open Data:
    ───────────────
    URL: https://nrsc.gov.in → "Data Products"
    Annual LULC maps (1:50,000 scale) available free for India
    """
    print(guide)
