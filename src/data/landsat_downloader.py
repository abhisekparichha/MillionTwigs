"""
USGS Landsat downloader via the landsatxplore library.

Supports programmatic search and download of:
  - Landsat 9 OLI/TIRS Collection 2 Level-2  (2021–present)
  - Landsat 8 OLI/TIRS Collection 2 Level-2  (2013–2021)
  - Landsat 7 ETM+ Collection 2 Level-2       (1999–2022)
  - Landsat 5 TM Collection 2 Level-2         (1984–2013) ← historical baseline

Landsat Collection 2 Level-2 products are surface-reflectance corrected
and cloud-masked using the QA_PIXEL band.

Credentials:
  Set in .env (copy from .env.example):
    LANDSATXPLORE_USERNAME=your_usgs_username
    LANDSATXPLORE_PASSWORD=your_usgs_password

  Register free (instant) at: https://ers.cr.usgs.gov/register
  See: docs/credentials_guide.md §4

Band reference (Landsat 8/9):
  SR_B2 = Blue  (0.45–0.51 µm)
  SR_B3 = Green (0.53–0.59 µm)
  SR_B4 = Red   (0.64–0.67 µm)  ← NDVI denominator
  SR_B5 = NIR   (0.85–0.88 µm)  ← NDVI numerator
  SR_B6 = SWIR1 (1.57–1.65 µm)
  SR_B7 = SWIR2 (2.11–2.29 µm)
  Scale: reflectance = DN × 0.0000275 + (−0.2)

Band reference (Landsat 5 TM):
  SR_B1 = Blue, SR_B2 = Green, SR_B3 = Red, SR_B4 = NIR,
  SR_B5 = SWIR1, SR_B7 = SWIR2
  NDVI = (SR_B4 - SR_B3) / (SR_B4 + SR_B3)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

try:
    from landsatxplore.api import API
    from landsatxplore.earthexplorer import EarthExplorer
    _LANDSATXPLORE_OK = True
except ImportError:
    _LANDSATXPLORE_OK = False


# USGS dataset IDs used with landsatxplore
DATASET_IDS = {
    "L9": "landsat_ot_c2_l2",   # Landsat 9 Collection 2 Level-2
    "L8": "landsat_ot_c2_l2",   # Landsat 8 Collection 2 Level-2
    "L7": "landsat_etm_c2_l2",  # Landsat 7 ETM+ C2 L2
    "L5": "landsat_tm_c2_l2",   # Landsat 5 TM C2 L2
}

# Scaling factors for Collection 2 Level-2
SCALE_FACTOR = 0.0000275
SCALE_OFFSET = -0.2


def _require_landsatxplore() -> None:
    if not _LANDSATXPLORE_OK:
        raise ImportError(
            "landsatxplore is not installed.\n"
            "Run: pip install landsatxplore"
        )


def _get_credentials() -> tuple:
    """Load USGS EarthExplorer credentials from environment / .env file.

    Set these in .env:
        LANDSATXPLORE_USERNAME=your_usgs_username
        LANDSATXPLORE_PASSWORD=your_usgs_password

    Register (free, instant): https://ers.cr.usgs.gov/register
    See: docs/credentials_guide.md §4
    """
    try:
        from src.config.credentials import get_usgs
        creds = get_usgs()
        return creds.username, creds.password
    except ImportError:
        username = os.environ.get("LANDSATXPLORE_USERNAME")
        password = os.environ.get("LANDSATXPLORE_PASSWORD")
        if not username or not password:
            raise EnvironmentError(
                "Set LANDSATXPLORE_USERNAME and LANDSATXPLORE_PASSWORD in .env.\n"
                "Register free at: https://ers.cr.usgs.gov/register\n"
                "See: docs/credentials_guide.md §4"
            )
        return username, password


def search_landsat(
    bbox: List[float],
    start_date: str,
    end_date: str,
    satellite: str = "L8",
    cloud_cover_max: int = 20,
    max_results: int = 20,
) -> List[dict]:
    """Search USGS EarthExplorer for Landsat scenes.

    Args:
        bbox:             [min_lon, min_lat, max_lon, max_lat]
        start_date:       "YYYY-MM-DD"
        end_date:         "YYYY-MM-DD"
        satellite:        "L9", "L8", "L7", or "L5"
        cloud_cover_max:  maximum cloud cover %
        max_results:      maximum number of scenes to return

    Returns:
        List of scene metadata dicts with keys:
          display_id, acquisition_date, cloud_cover, spatial_bounds
    """
    _require_landsatxplore()
    if satellite not in DATASET_IDS:
        raise ValueError(f"satellite must be one of {list(DATASET_IDS)}")

    username, password = _get_credentials()
    min_lon, min_lat, max_lon, max_lat = bbox

    api = API(username, password)
    try:
        scenes = api.search(
            dataset=DATASET_IDS[satellite],
            bbox=(min_lon, min_lat, max_lon, max_lat),
            start_date=start_date,
            end_date=end_date,
            max_cloud_cover=cloud_cover_max,
            max_results=max_results,
        )
    finally:
        api.logout()

    print(f"Found {len(scenes)} Landsat {satellite} scenes.")
    return scenes


def download_landsat(
    bbox: List[float],
    start_date: str,
    end_date: str,
    output_dir: str = "data/raw/landsat",
    satellite: str = "L8",
    cloud_cover_max: int = 20,
    max_scenes: int = 3,
) -> List[Path]:
    """Search and download Landsat scenes to disk.

    Downloads the full product bundle (all bands + QA_PIXEL).
    Saved as .tar files — extract with: tar -xf scene.tar -C output_dir/

    Args:
        max_scenes: download at most this many scenes (sorted by cloud cover)

    Returns:
        List of paths to downloaded .tar files
    """
    _require_landsatxplore()
    scenes = search_landsat(bbox, start_date, end_date, satellite, cloud_cover_max)
    if not scenes:
        print("No scenes found.")
        return []

    # Sort by cloud cover, take top N
    scenes = sorted(scenes, key=lambda s: s.get("cloud_cover", 100))[:max_scenes]

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    username, password = _get_credentials()

    ee = EarthExplorer(username, password)
    downloaded = []
    try:
        for scene in scenes:
            scene_id = scene["display_id"]
            print(f"  Downloading {scene_id} (cloud: {scene['cloud_cover']:.1f}%)…")
            ee.download(scene_id, output_dir=str(out))
            tar_path = out / f"{scene_id}.tar"
            if tar_path.exists():
                downloaded.append(tar_path)
                print(f"  Saved: {tar_path}")
    finally:
        ee.logout()

    print(f"Downloaded {len(downloaded)} Landsat scenes to {out}/")
    return downloaded


def get_band_paths(scene_dir: Path, satellite: str = "L8") -> dict:
    """Return a dict mapping band name → file path for an extracted scene.

    Args:
        scene_dir: directory containing extracted Landsat GeoTIFF files
        satellite: "L8"/"L9" or "L5"/"L7"

    Returns:
        dict with keys: blue, green, red, nir, swir1, swir2, qa
    """
    tifs = list(scene_dir.glob("*.TIF")) + list(scene_dir.glob("*.tif"))
    band_map = {}

    if satellite in ("L8", "L9"):
        mapping = {
            "blue":  "SR_B2", "green": "SR_B3", "red":   "SR_B4",
            "nir":   "SR_B5", "swir1": "SR_B6", "swir2": "SR_B7",
            "qa":    "QA_PIXEL",
        }
    else:  # L5, L7
        mapping = {
            "blue":  "SR_B1", "green": "SR_B2", "red":   "SR_B3",
            "nir":   "SR_B4", "swir1": "SR_B5", "swir2": "SR_B7",
            "qa":    "QA_PIXEL",
        }

    for name, band_code in mapping.items():
        matches = [f for f in tifs if band_code in f.stem]
        if matches:
            band_map[name] = matches[0]

    return band_map
