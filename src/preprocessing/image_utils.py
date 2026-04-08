"""
Image utility functions for satellite raster data.

Handles: band reading, tiling, reprojection, co-registration,
normalisation, and writing results.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Generator, List, Optional, Tuple

import numpy as np

try:
    import rasterio
    from rasterio.transform import from_bounds
    from rasterio.enums import Resampling
    from rasterio.warp import reproject, calculate_default_transform
    from rasterio.windows import Window
    from rasterio.merge import merge as rasterio_merge
    _RASTERIO_OK = True
except ImportError:
    _RASTERIO_OK = False

try:
    from skimage.transform import match_histograms
    _SKIMAGE_OK = True
except ImportError:
    _SKIMAGE_OK = False


def read_bands(
    path: Path,
    band_indices: Optional[List[int]] = None,
    as_float: bool = True,
) -> Tuple[np.ndarray, dict]:
    """Read one or more bands from a GeoTIFF into a numpy array.

    Args:
        path:         Path to input GeoTIFF
        band_indices: 1-based list of bands to read (None = all bands)
        as_float:     if True, convert to float32 and scale nodata to NaN

    Returns:
        (array, profile) where array has shape (bands, height, width)
    """
    if not _RASTERIO_OK:
        raise ImportError("rasterio is required.")
    with rasterio.open(path) as src:
        indices = band_indices or list(range(1, src.count + 1))
        arr = src.read(indices).astype(np.float32 if as_float else src.dtypes[0])
        profile = src.profile.copy()
        nodata = src.nodata
    if as_float and nodata is not None:
        arr[arr == nodata] = np.nan
    return arr, profile


def write_raster(
    array: np.ndarray,
    profile: dict,
    output_path: Path,
    nodata: float = np.nan,
    compress: str = "deflate",
) -> Path:
    """Write a numpy array to GeoTIFF.

    Args:
        array:       Shape (bands, H, W) or (H, W) for single band
        profile:     rasterio profile from source raster (updated automatically)
        output_path: destination file path
        nodata:      nodata fill value
        compress:    GDAL compression driver

    Returns:
        Path to written file
    """
    if not _RASTERIO_OK:
        raise ImportError("rasterio is required.")
    if array.ndim == 2:
        array = array[np.newaxis, ...]
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    profile.update(
        dtype=str(array.dtype),
        count=array.shape[0],
        compress=compress,
        nodata=nodata,
        driver="GTiff",
    )
    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(array)
    return output_path


def tile_raster(
    path: Path,
    tile_size: int = 256,
    overlap: int = 64,
) -> Generator[Tuple[np.ndarray, Window, dict], None, None]:
    """Yield (array, window, profile) tiles from a raster.

    Used to feed large satellite images into deep learning models in patches.

    Args:
        tile_size:  spatial size of each tile in pixels
        overlap:    overlap between adjacent tiles (avoids boundary artefacts)

    Yields:
        (array[bands, tile_size, tile_size], rasterio.Window, profile)
    """
    if not _RASTERIO_OK:
        raise ImportError("rasterio is required.")
    stride = tile_size - overlap
    with rasterio.open(path) as src:
        profile = src.profile.copy()
        h, w = src.height, src.width
        for row_off in range(0, h, stride):
            for col_off in range(0, w, stride):
                win_h = min(tile_size, h - row_off)
                win_w = min(tile_size, w - col_off)
                win = Window(col_off, row_off, win_w, win_h)
                arr = src.read(window=win).astype(np.float32)
                # Zero-pad if edge tile is smaller than tile_size
                if arr.shape[1] < tile_size or arr.shape[2] < tile_size:
                    padded = np.zeros(
                        (arr.shape[0], tile_size, tile_size), dtype=arr.dtype
                    )
                    padded[:, :arr.shape[1], :arr.shape[2]] = arr
                    arr = padded
                yield arr, win, profile


def coregister(
    target_path: Path,
    reference_path: Path,
    output_path: Path,
    resampling: str = "bilinear",
) -> Path:
    """Reproject and resample target raster to match the reference raster's
    grid (extent, resolution, CRS).

    Essential for multi-date change detection — both images must be on
    exactly the same pixel grid.

    Args:
        target_path:    raster to be reprojected
        reference_path: raster whose grid to match
        output_path:    output path
        resampling:     one of "nearest", "bilinear", "cubic", "lanczos"

    Returns:
        Path to the co-registered output
    """
    if not _RASTERIO_OK:
        raise ImportError("rasterio is required.")
    resamp_map = {
        "nearest": Resampling.nearest,
        "bilinear": Resampling.bilinear,
        "cubic": Resampling.cubic,
        "lanczos": Resampling.lanczos,
    }
    resamp = resamp_map.get(resampling, Resampling.bilinear)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(reference_path) as ref:
        dst_crs = ref.crs
        dst_transform = ref.transform
        dst_width = ref.width
        dst_height = ref.height

    with rasterio.open(target_path) as src:
        meta = src.meta.copy()
        meta.update(
            crs=dst_crs,
            transform=dst_transform,
            width=dst_width,
            height=dst_height,
            compress="deflate",
        )
        with rasterio.open(output_path, "w", **meta) as dst:
            for band_idx in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, band_idx),
                    destination=rasterio.band(dst, band_idx),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=dst_transform,
                    dst_crs=dst_crs,
                    resampling=resamp,
                )
    return output_path


def histogram_match(
    source_array: np.ndarray,
    reference_array: np.ndarray,
) -> np.ndarray:
    """Match histogram of source image to reference image.

    Used in change detection pre-processing to normalise radiometric
    differences between images from different dates or sensors.
    Implements the CDF-based histogram matching (Gonzalez & Woods, 2018).

    Args:
        source_array:    array to adjust, shape (bands, H, W) or (H, W)
        reference_array: reference array to match, same shape

    Returns:
        Adjusted array with same shape as source_array
    """
    if not _SKIMAGE_OK:
        raise ImportError("scikit-image is required. Run: pip install scikit-image")
    # match_histograms expects (H, W, C) or (H, W)
    if source_array.ndim == 3:
        src_hwc = np.moveaxis(source_array, 0, -1)
        ref_hwc = np.moveaxis(reference_array, 0, -1)
        matched_hwc = match_histograms(src_hwc, ref_hwc, channel_axis=-1)
        return np.moveaxis(matched_hwc, -1, 0)
    return match_histograms(source_array, reference_array)


def clip_to_percentile(
    array: np.ndarray,
    low: float = 2.0,
    high: float = 98.0,
) -> np.ndarray:
    """Clip array values to percentile range and scale to [0, 1].

    Used for visualisation pre-processing (not for index calculation).
    """
    lo = np.nanpercentile(array, low)
    hi = np.nanpercentile(array, high)
    clipped = np.clip(array, lo, hi)
    return (clipped - lo) / (hi - lo + 1e-9)


def compute_stats(array: np.ndarray) -> Dict[str, float]:
    """Return basic descriptive statistics for an array (ignores NaN)."""
    valid = array[~np.isnan(array)]
    return {
        "min":    float(np.min(valid)),
        "max":    float(np.max(valid)),
        "mean":   float(np.mean(valid)),
        "std":    float(np.std(valid)),
        "median": float(np.median(valid)),
        "count":  int(valid.size),
    }
