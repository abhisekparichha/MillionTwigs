"""
Sentinel-2 data downloader via the Copernicus Dataspace API.

Uses the `sentinelsat` library to search and download Sentinel-2 L2A products
(atmospherically corrected) directly to disk — useful when working offline
or when GEE export quotas are exhausted.

Set credentials via environment variables:
    COPERNICUS_USER=your_email
    COPERNICUS_PASSWORD=your_password

Register free at: https://dataspace.copernicus.eu/
"""

from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional, Tuple

try:
    from sentinelsat import SentinelAPI, read_geojson, geojson_to_wkt
    _SENTINELSAT_AVAILABLE = True
except ImportError:
    _SENTINELSAT_AVAILABLE = False


# Copernicus Dataspace OData API endpoint
_DATASPACE_API_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1"
# Legacy Scihub (still works for older scenes)
_SCIHUB_URL = "https://apihub.copernicus.eu/apihub"


def _require_sentinelsat() -> None:
    if not _SENTINELSAT_AVAILABLE:
        raise ImportError(
            "sentinelsat is not installed. Run: pip install sentinelsat"
        )


def _get_credentials() -> Tuple[str, str]:
    user = os.environ.get("COPERNICUS_USER")
    password = os.environ.get("COPERNICUS_PASSWORD")
    if not user or not password:
        raise EnvironmentError(
            "Set COPERNICUS_USER and COPERNICUS_PASSWORD environment variables.\n"
            "Register free at: https://dataspace.copernicus.eu/"
        )
    return user, password


def connect_api() -> "SentinelAPI":
    """Return an authenticated SentinelAPI client."""
    _require_sentinelsat()
    user, password = _get_credentials()
    return SentinelAPI(user, password, api_url=_SCIHUB_URL)


def search_sentinel2(
    bbox: List[float],
    start_date: str,
    end_date: str,
    cloud_cover_max: int = 10,
    product_type: str = "S2MSI2A",   # L2A = surface reflectance
) -> "pandas.DataFrame":
    """Search for Sentinel-2 scenes intersecting the AOI.

    Args:
        bbox:             [min_lon, min_lat, max_lon, max_lat]
        start_date:       "YYYY-MM-DD"
        end_date:         "YYYY-MM-DD"
        cloud_cover_max:  maximum cloud cover %
        product_type:     "S2MSI2A" (L2A, recommended) or "S2MSI1C" (L1C)

    Returns:
        GeoDataFrame of matching products with metadata
    """
    _require_sentinelsat()
    api = connect_api()

    min_lon, min_lat, max_lon, max_lat = bbox
    footprint = (
        f"POLYGON(({min_lon} {min_lat}, {max_lon} {min_lat}, "
        f"{max_lon} {max_lat}, {min_lon} {max_lat}, {min_lon} {min_lat}))"
    )

    products = api.query(
        area=footprint,
        date=(start_date.replace("-", ""), end_date.replace("-", "")),
        platformname="Sentinel-2",
        producttype=product_type,
        cloudcoverpercentage=(0, cloud_cover_max),
    )
    gdf = api.to_geodataframe(products)
    print(f"Found {len(gdf)} Sentinel-2 scenes.")
    return gdf


def download_sentinel2(
    bbox: List[float],
    start_date: str,
    end_date: str,
    output_dir: str = "data/raw/sentinel2",
    cloud_cover_max: int = 10,
    max_scenes: int = 5,
) -> List[Path]:
    """Search and download Sentinel-2 L2A scenes to disk.

    Downloads are saved as .SAFE directories (standard ESA format).
    Each .SAFE directory contains individual band GeoTIFF files.

    Args:
        max_scenes: download at most this many scenes (sorted by cloud cover)

    Returns:
        List of paths to downloaded .SAFE directories
    """
    _require_sentinelsat()
    api = connect_api()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    products = search_sentinel2(bbox, start_date, end_date, cloud_cover_max)
    if products.empty:
        print("No scenes found matching criteria.")
        return []

    # Sort by cloud cover and take top N
    products = products.sort_values("cloudcoverpercentage").head(max_scenes)
    print(f"Downloading {len(products)} scenes to {out}…")

    downloaded = api.download_all(list(products.index), directory_path=str(out))
    return [Path(str(out)) / p["title"] + ".SAFE" for p in downloaded.values()]


def list_safe_bands(safe_dir: Path) -> dict:
    """Return a dict mapping band name → file path for a .SAFE directory.

    Only includes 10m and 20m resolution bands (excludes 60m).
    """
    band_map = {}
    for jp2 in safe_dir.rglob("*.jp2"):
        name = jp2.stem
        # Sentinel-2 band file naming: T30UXB_20240101T102021_B04_10m
        for band in ["B02", "B03", "B04", "B05", "B06", "B07",
                     "B08", "B8A", "B11", "B12"]:
            if f"_{band}_" in name or name.endswith(f"_{band}"):
                band_map[band] = jp2
    return band_map
