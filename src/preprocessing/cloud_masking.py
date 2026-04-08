"""
Cloud masking for Sentinel-2 and Landsat imagery.

Methods:
  1. Sentinel-2 SCL (Scene Classification Layer) — recommended for L2A products
  2. s2cloudless (ML-based probability map) — more accurate, used via GEE
  3. Landsat QA_PIXEL bitmask — USGS Collection 2 standard
  4. Simple threshold mask (NDSI / B02 brightness) — quick fallback

References:
  - Zupanc, A. (2019). "Improving cloud detection with machine learning."
    Sentinel Hub blog. (s2cloudless methodology)
  - USGS (2021). Landsat Collection 2 Quality Assessment Bands.
    https://www.usgs.gov/landsat-missions/landsat-collection-2-quality-assessment-bands
"""

from __future__ import annotations

import numpy as np
from typing import Optional


# ── Sentinel-2 SCL mask ───────────────────────────────────────────────────────

# SCL class values for Sentinel-2 L2A (from ESA SNAP documentation)
SCL_CLASSES = {
    0:  "No data",
    1:  "Saturated / Defective",
    2:  "Dark Area Pixels",
    3:  "Cloud Shadows",
    4:  "Vegetation",
    5:  "Non-Vegetated",
    6:  "Water",
    7:  "Unclassified",
    8:  "Cloud (Medium Probability)",
    9:  "Cloud (High Probability)",
    10: "Thin Cirrus",
    11: "Snow / Ice",
}

# Classes to MASK OUT (True = pixel is invalid/cloudy)
_SCL_CLOUD_CLASSES = {0, 1, 3, 8, 9, 10, 11}


def mask_sentinel2_scl(scl_band: np.ndarray) -> np.ndarray:
    """Generate a binary cloud mask from the Sentinel-2 SCL band.

    Args:
        scl_band: 2D array of SCL integer values (band 12 in L2A product)

    Returns:
        Boolean mask array — True where pixel is VALID (cloud-free vegetation/land),
        False where cloudy, shadowed, or water.
    """
    valid_mask = np.ones(scl_band.shape, dtype=bool)
    for cls in _SCL_CLOUD_CLASSES:
        valid_mask &= (scl_band != cls)
    return valid_mask


def apply_cloud_mask(
    image: np.ndarray,
    mask: np.ndarray,
    fill_value: float = np.nan,
) -> np.ndarray:
    """Apply a boolean validity mask to a multi-band image.

    Args:
        image:      array shape (bands, H, W)
        mask:       boolean array shape (H, W) — True = valid pixel
        fill_value: value for masked-out pixels

    Returns:
        Masked array same shape as image
    """
    result = image.copy().astype(np.float32)
    result[:, ~mask] = fill_value
    return result


# ── Landsat QA_PIXEL bitmask ──────────────────────────────────────────────────

# Bit positions in Landsat Collection 2 QA_PIXEL band
_LANDSAT_QA_BITS = {
    "fill":           0,
    "dilated_cloud":  1,
    "cirrus":         2,
    "cloud":          3,
    "cloud_shadow":   4,
    "snow":           5,
    "clear":          6,
    "water":          7,
}


def mask_landsat_qa(
    qa_band: np.ndarray,
    mask_cirrus: bool = True,
    mask_shadow: bool = True,
    mask_snow: bool = True,
) -> np.ndarray:
    """Generate a validity mask from the Landsat Collection 2 QA_PIXEL band.

    Reference: USGS Landsat Collection 2 QA_PIXEL Band Explanation.

    Args:
        qa_band:      2D uint16 array of QA_PIXEL values
        mask_cirrus:  mask thin cirrus clouds
        mask_shadow:  mask cloud shadows
        mask_snow:    mask snow / ice

    Returns:
        Boolean mask — True = valid (cloud-free, non-shadow) land pixel
    """
    def _bit(band: np.ndarray, bit_pos: int) -> np.ndarray:
        return (band >> bit_pos) & 1

    # Start: pixels must be "clear"
    valid = _bit(qa_band, _LANDSAT_QA_BITS["clear"]).astype(bool)
    # Remove fill
    valid &= ~_bit(qa_band, _LANDSAT_QA_BITS["fill"]).astype(bool)
    # Remove clouds
    valid &= ~_bit(qa_band, _LANDSAT_QA_BITS["cloud"]).astype(bool)
    # Remove dilated clouds (safe margin around cloud edges)
    valid &= ~_bit(qa_band, _LANDSAT_QA_BITS["dilated_cloud"]).astype(bool)
    if mask_cirrus:
        valid &= ~_bit(qa_band, _LANDSAT_QA_BITS["cirrus"]).astype(bool)
    if mask_shadow:
        valid &= ~_bit(qa_band, _LANDSAT_QA_BITS["cloud_shadow"]).astype(bool)
    if mask_snow:
        valid &= ~_bit(qa_band, _LANDSAT_QA_BITS["snow"]).astype(bool)
    return valid


# ── Simple brightness / NDSI cloud detection ─────────────────────────────────

def mask_bright_clouds(
    blue_band: np.ndarray,
    brightness_threshold: float = 0.25,
) -> np.ndarray:
    """Simple cloud mask using blue band brightness threshold.

    Clouds are bright across all visible wavelengths, especially blue.
    This method is a fast fallback when no quality band is available.

    Limitation: may incorrectly flag bright sand, snow, urban surfaces.

    Args:
        blue_band:            2D reflectance array [0, 1] for blue wavelength
        brightness_threshold: pixels above this are flagged as cloud

    Returns:
        Boolean mask — True = valid (not bright cloud)
    """
    return blue_band < brightness_threshold


def compute_cloud_fraction(mask: np.ndarray) -> float:
    """Return the fraction of pixels that are cloud-contaminated (0–1)."""
    return float((~mask).sum() / mask.size)
