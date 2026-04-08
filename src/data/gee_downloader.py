"""
Google Earth Engine (GEE) data downloader.

Supports Sentinel-2, Landsat 8/9, GEDI, and Hansen Global Forest Change
imagery. Uses server-side GEE processing — no large downloads needed for
index computation; full raster export goes to Google Drive or GCS.

Reference datasets:
  - Sentinel-2 SR:   COPERNICUS/S2_SR_HARMONIZED
  - Landsat 8 SR:    LANDSAT/LC08/C02/T1_L2
  - Landsat 9 SR:    LANDSAT/LC09/C02/T1_L2
  - GEDI canopy:     LARSE/GEDI/GEDI02_A_002_MONTHLY
  - Hansen GFC:      UMD/hansen/global_forest_change_2023_v1_11
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import ee
    _GEE_AVAILABLE = True
except ImportError:
    _GEE_AVAILABLE = False

import yaml


def _require_gee() -> None:
    if not _GEE_AVAILABLE:
        raise ImportError(
            "earthengine-api is not installed. Run: pip install earthengine-api"
        )


def initialize_gee(project: Optional[str] = None) -> None:
    """Authenticate and initialise the GEE Python API.

    Call once per session before any GEE operation.
    Run `earthengine authenticate` on first use to store credentials.
    """
    _require_gee()
    try:
        ee.Initialize(project=project)
    except Exception:
        ee.Authenticate()
        ee.Initialize(project=project)


def bbox_to_geometry(bbox: List[float]) -> "ee.Geometry.Rectangle":
    """Convert [min_lon, min_lat, max_lon, max_lat] to a GEE geometry."""
    _require_gee()
    min_lon, min_lat, max_lon, max_lat = bbox
    return ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])


# ── Sentinel-2 ────────────────────────────────────────────────────────────────

def get_sentinel2_collection(
    bbox: List[float],
    start_date: str,
    end_date: str,
    cloud_cover_max: int = 10,
) -> "ee.ImageCollection":
    """Return a cloud-filtered, cloud-masked Sentinel-2 SR image collection.

    Uses the s2cloudless probability mask (Sentinel-2 Cloud Probability dataset)
    following the recommended workflow from the GEE documentation.

    Args:
        bbox:             [min_lon, min_lat, max_lon, max_lat]
        start_date:       ISO date string e.g. "2024-01-01"
        end_date:         ISO date string e.g. "2024-12-31"
        cloud_cover_max:  Maximum scene cloud cover percentage

    Returns:
        ee.ImageCollection with cloud-masked, scaled reflectance values
    """
    _require_gee()
    aoi = bbox_to_geometry(bbox)

    s2 = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(aoi)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", cloud_cover_max))
    )

    # Cloud probability collection for masking
    s2_cloudless = (
        ee.ImageCollection("COPERNICUS/S2_CLOUD_PROBABILITY")
        .filterBounds(aoi)
        .filterDate(start_date, end_date)
    )

    joined = ee.ImageCollection(
        ee.Join.saveFirst("cloud_mask").apply(
            primary=s2,
            secondary=s2_cloudless,
            condition=ee.Filter.equals(
                leftField="system:index", rightField="system:index"
            ),
        )
    )

    def mask_clouds(img: "ee.Image") -> "ee.Image":
        cloud_prob = ee.Image(img.get("cloud_mask")).select("probability")
        cloud_mask = cloud_prob.lt(35)
        return (
            img.updateMask(cloud_mask)
            .divide(10000)                  # scale to [0, 1] reflectance
            .copyProperties(img, img.propertyNames())
        )

    return joined.map(mask_clouds)


def get_sentinel2_median(
    bbox: List[float],
    start_date: str,
    end_date: str,
    cloud_cover_max: int = 10,
) -> "ee.Image":
    """Return median-composite Sentinel-2 image for a date range.

    The median composite reduces cloud remnants and seasonal variation,
    giving a representative "typical" surface reflectance for the period.
    """
    col = get_sentinel2_collection(bbox, start_date, end_date, cloud_cover_max)
    return col.median().clip(bbox_to_geometry(bbox))


# ── Landsat ───────────────────────────────────────────────────────────────────

def _apply_landsat_scale(img: "ee.Image") -> "ee.Image":
    """Apply Landsat Collection 2 scaling factors.

    Scale factor: 0.0000275, offset: -0.2  (USGS Collection 2 specification)
    """
    optical = img.select("SR_B.").multiply(0.0000275).add(-0.2)
    thermal = img.select("ST_B.*").multiply(0.00341802).add(149.0)
    return img.addBands(optical, overwrite=True).addBands(thermal, overwrite=True)


def _mask_landsat_clouds(img: "ee.Image") -> "ee.Image":
    """Mask clouds and cloud shadows using the QA_PIXEL band."""
    qa = img.select("QA_PIXEL")
    cloud_bit = 1 << 3
    shadow_bit = 1 << 4
    cloud_mask = qa.bitwiseAnd(cloud_bit).eq(0)
    shadow_mask = qa.bitwiseAnd(shadow_bit).eq(0)
    return img.updateMask(cloud_mask.And(shadow_mask))


def get_landsat_collection(
    bbox: List[float],
    start_date: str,
    end_date: str,
    satellite: str = "L8",
    cloud_cover_max: int = 20,
) -> "ee.ImageCollection":
    """Return a cloud-masked, scaled Landsat image collection.

    Args:
        satellite: "L8" for Landsat 8, "L9" for Landsat 9, "L7" for Landsat 7,
                   "L5" for Landsat 5 (historical back to 1984)
    """
    _require_gee()
    collections = {
        "L9": "LANDSAT/LC09/C02/T1_L2",
        "L8": "LANDSAT/LC08/C02/T1_L2",
        "L7": "LANDSAT/LE07/C02/T1_L2",
        "L5": "LANDSAT/LT05/C02/T1_L2",
    }
    if satellite not in collections:
        raise ValueError(f"satellite must be one of {list(collections.keys())}")

    aoi = bbox_to_geometry(bbox)
    col = (
        ee.ImageCollection(collections[satellite])
        .filterBounds(aoi)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lt("CLOUD_COVER", cloud_cover_max))
        .map(_mask_landsat_clouds)
        .map(_apply_landsat_scale)
    )
    return col


def get_landsat_median(
    bbox: List[float],
    start_date: str,
    end_date: str,
    satellite: str = "L8",
    cloud_cover_max: int = 20,
) -> "ee.Image":
    """Return median-composite Landsat image for a date range."""
    col = get_landsat_collection(bbox, start_date, end_date, satellite, cloud_cover_max)
    return col.median().clip(bbox_to_geometry(bbox))


# ── GEDI LiDAR ────────────────────────────────────────────────────────────────

def get_gedi_canopy_height(
    bbox: List[float],
    start_date: str = "2019-04-01",
    end_date: str = "2023-12-31",
) -> "ee.Image":
    """Return mean GEDI relative height (rh98) as a canopy height proxy.

    rh98 = height below which 98% of returned energy lies ≈ canopy top height.
    Reference: Dubayah et al. 2020, Remote Sensing of Environment.

    Note: GEDI coverage is limited to latitudes 51.6°N – 51.6°S.
    """
    _require_gee()
    aoi = bbox_to_geometry(bbox)
    gedi = (
        ee.ImageCollection("LARSE/GEDI/GEDI02_A_002_MONTHLY")
        .filterBounds(aoi)
        .filterDate(start_date, end_date)
        .select("rh98")
        .filter(ee.Filter.gt("rh98", 0))
    )
    return gedi.mean().clip(aoi)


# ── Hansen Global Forest Change ───────────────────────────────────────────────

def get_hansen_forest_change(bbox: List[float]) -> Dict[str, "ee.Image"]:
    """Return Hansen GFC layers for loss year, gain, and tree cover (year 2000).

    Reference: Hansen, M.C. et al. (2013). Science, 342(6160), 850-853.

    Returns dict with keys:
      "treecover2000"  — % canopy cover in year 2000 (0–100)
      "loss"          — binary mask of any loss 2001-2023
      "lossyear"      — year of first loss (1=2001, 23=2023, 0=no loss)
      "gain"          — binary mask of gain 2000-2012
    """
    _require_gee()
    aoi = bbox_to_geometry(bbox)
    gfc = ee.Image("UMD/hansen/global_forest_change_2023_v1_11").clip(aoi)
    return {
        "treecover2000": gfc.select("treecover2000"),
        "loss":          gfc.select("loss"),
        "lossyear":      gfc.select("lossyear"),
        "gain":          gfc.select("gain"),
    }


# ── Export helpers ─────────────────────────────────────────────────────────────

def export_image_to_drive(
    image: "ee.Image",
    description: str,
    folder: str = "MillionTwigs",
    scale: int = 10,
    bbox: Optional[List[float]] = None,
    crs: str = "EPSG:4326",
) -> "ee.batch.Task":
    """Start a GEE export task to Google Drive.

    Args:
        image:       ee.Image to export
        description: Task name (also becomes the filename)
        folder:      Google Drive folder name
        scale:       Output resolution in metres (10 for S2, 30 for Landsat)
        bbox:        Export region; uses image footprint if None
        crs:         Output coordinate reference system

    Returns:
        ee.batch.Task — call .start() to begin and .status() to monitor
    """
    _require_gee()
    region = bbox_to_geometry(bbox) if bbox else image.geometry()
    task = ee.batch.Export.image.toDrive(
        image=image,
        description=description,
        folder=folder,
        scale=scale,
        region=region,
        crs=crs,
        maxPixels=1e13,
        fileFormat="GeoTIFF",
    )
    task.start()
    return task


def wait_for_tasks(tasks: List["ee.batch.Task"], poll_interval: int = 30) -> None:
    """Block until all GEE export tasks complete or fail."""
    import sys
    pending = list(tasks)
    while pending:
        done = []
        for task in pending:
            status = task.status()
            state = status["state"]
            if state in ("COMPLETED", "FAILED", "CANCELLED"):
                print(f"  Task '{status['description']}': {state}")
                done.append(task)
        pending = [t for t in pending if t not in done]
        if pending:
            print(f"  Waiting for {len(pending)} task(s)…", end="\r", flush=True)
            time.sleep(poll_interval)


# ── Config-driven convenience function ────────────────────────────────────────

def download_from_config(config_path: str = "config.yaml") -> Dict:
    """Download imagery based on config.yaml settings.

    Returns a dict with keys "baseline" and "current", each containing
    the respective ee.Image objects.
    """
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    initialize_gee(project=cfg["credentials"].get("gee_project"))

    bbox = cfg["aoi"]["bbox"]
    source = cfg["source"]["primary"]
    max_cloud = cfg["source"]["cloud_cover_max"]

    def _fetch(period: str) -> "ee.Image":
        d = cfg["dates"][period]
        start, end = d["start"], d["end"]
        if source == "sentinel2":
            return get_sentinel2_median(bbox, start, end, max_cloud)
        elif source in ("landsat8", "landsat9"):
            sat = "L8" if source == "landsat8" else "L9"
            return get_landsat_median(bbox, start, end, sat)
        else:
            raise ValueError(f"GEE download not supported for source '{source}'")

    return {
        "baseline": _fetch("baseline"),
        "current":  _fetch("current"),
    }
