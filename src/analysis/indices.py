"""
Vegetation and land-surface spectral indices.

All index functions take numpy arrays (float32, values in [0, 1] reflectance)
and return a 2D float32 array.

Implemented indices:
  NDVI   — Tucker (1979)
  EVI    — Huete et al. (2002)
  EVI2   — Jiang et al. (2008) — no blue band required
  NDRE   — Gitelson & Merzlyak (1994)  [Sentinel-2 only]
  SAVI   — Huete (1988)
  MSAVI2 — Qi et al. (1994)
  NDWI   — McFeeters (1996)   — water detection
  MNDWI  — Xu (2006)          — modified water index
  NDBI   — Zha et al. (2003)  — built-up index
  NBR    — Key & Benson (2006) — normalised burn ratio
  LAI    — LAI estimation from NDVI (Baret & Guyot 1991)
"""

from __future__ import annotations

import numpy as np


def _safe_divide(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    """Division safe against zeros; returns NaN where denominator == 0."""
    with np.errstate(invalid="ignore", divide="ignore"):
        result = np.where(denominator != 0, numerator / denominator, np.nan)
    return result.astype(np.float32)


# ── Primary Vegetation Indices ────────────────────────────────────────────────

def ndvi(nir: np.ndarray, red: np.ndarray) -> np.ndarray:
    """Normalised Difference Vegetation Index.

    Reference: Tucker, C.J. (1979). Remote Sensing of Environment, 8(2), 127-150.

    NDVI = (NIR - Red) / (NIR + Red)

    Interpretation:
      < 0.1  : Water, rock, bare soil, cloud
      0.1–0.2: Sparse vegetation, senescent/dry grass
      0.2–0.3: Shrubs, grassland
      0.3–0.5: Moderate canopy, degraded forest
      0.5–0.7: Healthy forest, dense crops
      0.7–0.9: Tropical rainforest, peak growing season

    Args:
        nir: Near-infrared reflectance array [0, 1]
        red: Red reflectance array [0, 1]

    Returns:
        NDVI array [-1, 1]
    """
    return _safe_divide(nir - red, nir + red)


def evi(
    nir: np.ndarray,
    red: np.ndarray,
    blue: np.ndarray,
    G: float = 2.5,
    C1: float = 6.0,
    C2: float = 7.5,
    L: float = 1.0,
) -> np.ndarray:
    """Enhanced Vegetation Index.

    Reference: Huete, A. et al. (2002). Remote Sensing of Environment,
    83(1-2), 195-213.

    EVI = G × (NIR - Red) / (NIR + C1 × Red - C2 × Blue + L)

    Advantages over NDVI:
      - Less sensitive to atmospheric effects (uses blue band)
      - Does not saturate in high-biomass dense forests
      - Better sensitivity to canopy structural variation

    Returns:
        EVI array, typically in [-1, 1] but can exceed this in noisy data
    """
    denominator = nir + C1 * red - C2 * blue + L
    return (G * _safe_divide(nir - red, denominator)).astype(np.float32)


def evi2(
    nir: np.ndarray,
    red: np.ndarray,
    G: float = 2.5,
    C: float = 2.4,
    L: float = 1.0,
) -> np.ndarray:
    """Enhanced Vegetation Index 2 — two-band EVI (no blue required).

    Reference: Jiang, Z. et al. (2008). Remote Sensing of Environment,
    112(10), 4521-4529.

    EVI2 = G × (NIR - Red) / (NIR + C × Red + L)

    Use when: LISS-III/LISS-IV (no blue band), or when blue band is noisy.
    """
    return (G * _safe_divide(nir - red, nir + C * red + L)).astype(np.float32)


def ndre(nir: np.ndarray, red_edge: np.ndarray) -> np.ndarray:
    """Red-Edge Normalised Difference Vegetation Index.

    Reference: Gitelson, A.A. & Merzlyak, M.N. (1994). Journal of
    Photochemistry and Photobiology B, 22(3), 247-244.

    NDRE = (NIR - RedEdge) / (NIR + RedEdge)

    Available only on sensors with a red-edge band:
      Sentinel-2: B5 (705 nm), B6 (740 nm), B7 (783 nm)
      Planet SuperDove: has red-edge band

    Advantages:
      - More sensitive to chlorophyll content than NDVI
      - Does not saturate as quickly in dense vegetation
      - Better indicator of plant stress, nitrogen content

    Args:
        nir:      NIR band (Sentinel-2 B8 or B8A)
        red_edge: Red-edge band (Sentinel-2 B5 at 705 nm recommended)
    """
    return _safe_divide(nir - red_edge, nir + red_edge)


def savi(
    nir: np.ndarray,
    red: np.ndarray,
    L: float = 0.5,
) -> np.ndarray:
    """Soil-Adjusted Vegetation Index.

    Reference: Huete, A.R. (1988). Remote Sensing of Environment, 25(3), 295-309.

    SAVI = ((NIR - Red) / (NIR + Red + L)) × (1 + L)

    Use when: canopy cover < 40%, sparse vegetation, arid regions.
    L=0.5 is optimal for intermediate cover; L=0 ≈ NDVI, L=1 for very sparse.
    """
    return (_safe_divide(nir - red, nir + red + L) * (1 + L)).astype(np.float32)


def msavi2(nir: np.ndarray, red: np.ndarray) -> np.ndarray:
    """Modified Soil-Adjusted Vegetation Index 2.

    Reference: Qi, J. et al. (1994). Remote Sensing of Environment, 48(2), 119-126.

    MSAVI2 = (2×NIR + 1 - sqrt((2×NIR + 1)² - 8×(NIR - Red))) / 2

    Self-adjusting L factor — no need to set L manually.
    """
    term = (2 * nir + 1) ** 2 - 8 * (nir - red)
    result = (2 * nir + 1 - np.sqrt(np.maximum(term, 0))) / 2
    return result.astype(np.float32)


# ── Water & Urban Indices ─────────────────────────────────────────────────────

def ndwi(green: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """Normalised Difference Water Index — detects open water bodies.

    Reference: McFeeters, S.K. (1996). International Journal of Remote
    Sensing, 17(7), 1425-1432.

    NDWI = (Green - NIR) / (Green + NIR)

    Use for: water body extraction, flood mapping.
    Positive values indicate water; negative values indicate land.
    """
    return _safe_divide(green - nir, green + nir)


def mndwi(green: np.ndarray, swir: np.ndarray) -> np.ndarray:
    """Modified Normalised Difference Water Index.

    Reference: Xu, H. (2006). International Journal of Remote Sensing,
    27(14), 3025-3033.

    MNDWI = (Green - SWIR) / (Green + SWIR)

    Better than NDWI for: suppressing built-up land noise in water maps.
    Uses SWIR band (Landsat B6, Sentinel-2 B11) instead of NIR.
    """
    return _safe_divide(green - swir, green + swir)


def nbr(nir: np.ndarray, swir2: np.ndarray) -> np.ndarray:
    """Normalised Burn Ratio — fire severity and forest disturbance.

    Reference: Key, C.H. & Benson, N.C. (2006). FIREMON: Fire Effects
    Monitoring and Inventory System.

    NBR = (NIR - SWIR2) / (NIR + SWIR2)
    dNBR = pre_fire_NBR - post_fire_NBR  (change map)

    Negative dNBR → regrowth; Positive dNBR → burn severity.
    Also useful for detecting logging, land clearing events.
    """
    return _safe_divide(nir - swir2, nir + swir2)


# ── LAI Estimation ────────────────────────────────────────────────────────────

def lai_from_ndvi(
    ndvi_arr: np.ndarray,
    method: str = "baret1991",
) -> np.ndarray:
    """Estimate Leaf Area Index from NDVI.

    Available methods:

    "baret1991":
        LAI = -ln((0.69 - NDVI) / 0.59) / 0.91
        Reference: Baret, F. & Guyot, G. (1991). Remote Sensing of
        Environment, 35(2-3), 161-173.
        Valid range: NDVI 0.08 – 0.92

    "chen1996":
        LAI = 4.9 × NDVI - 0.46    (empirical, temperate forests)
        Reference: Chen, J.M. & Cihlar, J. (1996). Remote Sensing of
        Environment, 58(1), 1-6.

    Returns:
        LAI array in m²/m² (typically 0–8 for forests)
    """
    ndvi_arr = np.clip(ndvi_arr, 0.0, 1.0)
    if method == "baret1991":
        inner = np.maximum((0.69 - ndvi_arr) / 0.59, 1e-6)
        lai = -np.log(inner) / 0.91
    elif method == "chen1996":
        lai = 4.9 * ndvi_arr - 0.46
    else:
        raise ValueError(f"Unknown LAI method '{method}'")
    return np.maximum(lai, 0.0).astype(np.float32)


# ── Batch computation ─────────────────────────────────────────────────────────

def compute_all_indices(bands: dict) -> dict:
    """Compute all applicable indices from a bands dictionary.

    Args:
        bands: dict mapping band name to 2D reflectance array.
               Expected keys (use any subset):
                 "blue", "green", "red", "nir", "red_edge", "swir1", "swir2"

    Returns:
        dict of {index_name: 2D array}
    """
    results = {}
    b = bands  # shorthand

    if "nir" in b and "red" in b:
        results["ndvi"]  = ndvi(b["nir"], b["red"])
        results["savi"]  = savi(b["nir"], b["red"])
        results["msavi2"]= msavi2(b["nir"], b["red"])
        results["evi2"]  = evi2(b["nir"], b["red"])

    if "nir" in b and "red" in b and "blue" in b:
        results["evi"] = evi(b["nir"], b["red"], b["blue"])

    if "nir" in b and "red_edge" in b:
        results["ndre"] = ndre(b["nir"], b["red_edge"])

    if "green" in b and "nir" in b:
        results["ndwi"] = ndwi(b["green"], b["nir"])

    if "green" in b and "swir1" in b:
        results["mndwi"] = mndwi(b["green"], b["swir1"])

    if "nir" in b and "swir2" in b:
        results["nbr"] = nbr(b["nir"], b["swir2"])

    if "ndvi" in results:
        results["lai"] = lai_from_ndvi(results["ndvi"])

    return results
