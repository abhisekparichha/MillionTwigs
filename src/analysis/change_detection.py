"""
Temporal change detection between two satellite images.

Methods implemented:
  1. Change Vector Analysis (CVA) — Malila 1980
     Computes magnitude and direction of change in feature space.
     Identifies where vegetation has been gained or lost and by how much.

  2. Post-Classification Comparison (PCC)
     Classifies both images independently and computes a confusion matrix.
     Simple but accumulates classification errors from two independent steps.

  3. Image Differencing on NDVI
     Simplest approach: ΔV = NDVI_t2 - NDVI_t1
     Threshold ΔV to identify significant change.

  4. Vegetation Change Summary
     Summarises gain/loss in area, percentage, and estimated tree delta.

References:
  Malila, W.A. (1980). Change vector analysis: An approach for detecting
  forest changes with Landsat. LARS Symposia, 385.

  Singh, A. (1989). Review Article: Digital change detection techniques
  using remotely-sensed data. International Journal of Remote Sensing,
  10(6), 989-1003.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import numpy as np


# ── Image Differencing ────────────────────────────────────────────────────────

def ndvi_difference(
    ndvi_t1: np.ndarray,
    ndvi_t2: np.ndarray,
    threshold_std: float = 1.5,
) -> Dict[str, np.ndarray]:
    """Compute NDVI difference map and classify change type.

    delta = NDVI_t2 - NDVI_t1

    Positive delta → vegetation gain (regrowth, afforestation)
    Negative delta → vegetation loss (deforestation, crop harvest, die-off)

    Significant change defined as |delta| > threshold_std × std(delta).

    Args:
        ndvi_t1:        NDVI array at time 1 (past)
        ndvi_t2:        NDVI array at time 2 (present)
        threshold_std:  number of standard deviations to define significant change

    Returns:
        dict with keys:
          "delta"     — raw NDVI difference
          "gain_mask" — boolean mask of significant vegetation gain
          "loss_mask" — boolean mask of significant vegetation loss
          "no_change" — boolean mask of stable pixels
    """
    delta = (ndvi_t2 - ndvi_t1).astype(np.float32)
    valid = ~(np.isnan(ndvi_t1) | np.isnan(ndvi_t2))

    std_delta = float(np.nanstd(delta[valid]))
    threshold = threshold_std * std_delta

    gain_mask = valid & (delta > threshold)
    loss_mask = valid & (delta < -threshold)
    no_change = valid & ~gain_mask & ~loss_mask

    return {
        "delta":     delta,
        "gain_mask": gain_mask,
        "loss_mask": loss_mask,
        "no_change": no_change,
        "threshold": threshold,
        "std_delta": std_delta,
    }


# ── Change Vector Analysis (CVA) ──────────────────────────────────────────────

def change_vector_analysis(
    features_t1: np.ndarray,
    features_t2: np.ndarray,
    magnitude_threshold_std: float = 1.5,
) -> Dict[str, np.ndarray]:
    """Change Vector Analysis (CVA) in multi-dimensional feature space.

    CVA computes a change vector ΔV = f_t2 - f_t1 for each pixel, where
    features can include multiple indices (NDVI, EVI, NIR, SWIR, etc.).

    The magnitude ||ΔV|| indicates the amount of change.
    The direction (angle in feature space) indicates the type of change.

    For 2D feature space [ΔNDVI, ΔSWIR]:
      NW quadrant (ΔNDVI > 0, ΔSWIR < 0): Vegetation gain
      SE quadrant (ΔNDVI < 0, ΔSWIR > 0): Vegetation loss / deforestation
      NE quadrant (ΔNDVI > 0, ΔSWIR > 0): Soil exposure + regrowth
      SW quadrant (ΔNDVI < 0, ΔSWIR < 0): Water increase / flooding

    Reference: Malila, W.A. (1980). LARS Symposia, Paper 385.

    Args:
        features_t1:             Array shape (n_features, H, W) for time 1
        features_t2:             Array shape (n_features, H, W) for time 2
        magnitude_threshold_std: Std deviations above mean for significant change

    Returns:
        dict with keys:
          "magnitude"      — per-pixel change magnitude (L2 norm of ΔV)
          "direction_deg"  — per-pixel change direction in degrees (2D case only)
          "change_mask"    — boolean mask of significant change pixels
          "change_type"    — integer class: 0=no change, 1=gain, 2=loss, 3=other
    """
    assert features_t1.shape == features_t2.shape, "Feature arrays must have same shape"

    delta = (features_t2 - features_t1).astype(np.float32)   # (n_features, H, W)
    # L2 magnitude: sqrt(sum of squared differences across all features)
    magnitude = np.sqrt(np.nansum(delta ** 2, axis=0))       # (H, W)

    # Threshold for significant change
    valid_mag = magnitude[~np.isnan(magnitude)]
    threshold = float(np.mean(valid_mag) + magnitude_threshold_std * np.std(valid_mag))
    change_mask = magnitude > threshold

    # Direction (only meaningful for 2D CVA — NDVI + SWIR)
    direction_deg = None
    change_type = np.zeros(magnitude.shape, dtype=np.uint8)

    if delta.shape[0] == 2:
        d_ndvi = delta[0]
        d_swir = delta[1]
        direction_deg = np.degrees(np.arctan2(d_ndvi, d_swir))   # (H, W)

        # Classify change type where magnitude is significant
        change_type = np.where(
            change_mask & (d_ndvi > 0) & (d_swir <= 0), 1,   # vegetation gain
            np.where(
                change_mask & (d_ndvi < 0) & (d_swir >= 0), 2,   # vegetation loss
                np.where(change_mask, 3, 0)                       # other change
            )
        ).astype(np.uint8)

    return {
        "magnitude":     magnitude,
        "direction_deg": direction_deg,
        "change_mask":   change_mask,
        "change_type":   change_type,
        "threshold":     threshold,
    }


# ── Post-Classification Comparison ────────────────────────────────────────────

def classify_vegetation(
    ndvi_array: np.ndarray,
    thresholds: Optional[Dict[str, float]] = None,
) -> np.ndarray:
    """Classify pixels into vegetation cover classes using NDVI thresholds.

    Class codes:
      0 — Non-vegetation (water, bare soil, urban)
      1 — Sparse vegetation (NDVI 0.1–0.25)
      2 — Moderate vegetation (NDVI 0.25–0.45)
      3 — Dense vegetation / forest (NDVI > 0.45)

    Adapted from: Xiao, X. et al. (2002), based on NDVI ranges validated
    for Indian tropical and subtropical vegetation types.

    Args:
        ndvi_array: 2D NDVI float array
        thresholds: optional override dict with keys "sparse", "moderate", "dense"

    Returns:
        2D uint8 class array (0–3)
    """
    t = {"sparse": 0.10, "moderate": 0.25, "dense": 0.45}
    if thresholds:
        t.update(thresholds)

    classes = np.zeros(ndvi_array.shape, dtype=np.uint8)
    classes[ndvi_array >= t["sparse"]]   = 1
    classes[ndvi_array >= t["moderate"]] = 2
    classes[ndvi_array >= t["dense"]]    = 3
    classes[np.isnan(ndvi_array)]        = 255  # nodata

    return classes


def post_classification_comparison(
    classes_t1: np.ndarray,
    classes_t2: np.ndarray,
    pixel_area_m2: float = 100.0,
) -> Dict:
    """Compare two classified maps and summarise land cover change.

    Args:
        classes_t1:    Classification from time 1 (uint8 class array)
        classes_t2:    Classification from time 2 (uint8 class array)
        pixel_area_m2: Area of one pixel in m²

    Returns:
        dict with:
          "from_to_matrix"   — 4×4 confusion matrix (class transitions)
          "net_change_ha"    — dict of {class: net change in hectares}
          "forest_gain_ha"   — hectares of new forest (class 3)
          "forest_loss_ha"   — hectares of forest converted to lower class
          "summary_text"     — human-readable summary string
    """
    CLASS_NAMES = {0: "Non-veg", 1: "Sparse", 2: "Moderate", 3: "Dense/Forest"}
    n_classes = 4
    matrix = np.zeros((n_classes, n_classes), dtype=np.int64)

    valid = (classes_t1 != 255) & (classes_t2 != 255)
    for i in range(n_classes):
        for j in range(n_classes):
            matrix[i, j] = int(((classes_t1 == i) & (classes_t2 == j) & valid).sum())

    # Net change per class (positive = gain, negative = loss)
    net_change_ha = {}
    for cls in range(n_classes):
        gain_px = matrix[:, cls].sum() - matrix[cls, cls]
        loss_px = matrix[cls, :].sum() - matrix[cls, cls]
        net_px = gain_px - loss_px
        net_change_ha[CLASS_NAMES[cls]] = (net_px * pixel_area_m2) / 10000.0

    # Forest specifically (class 3)
    forest_gain_px = matrix[:3, 3].sum()  # anything → forest
    forest_loss_px = matrix[3, :3].sum()  # forest → anything
    forest_gain_ha = (forest_gain_px * pixel_area_m2) / 10000.0
    forest_loss_ha = (forest_loss_px * pixel_area_m2) / 10000.0

    summary = (
        f"Dense vegetation GAIN: {forest_gain_ha:,.1f} ha\n"
        f"Dense vegetation LOSS: {forest_loss_ha:,.1f} ha\n"
        f"Net dense vegetation:  {forest_gain_ha - forest_loss_ha:+,.1f} ha\n"
    )
    for name, ha in net_change_ha.items():
        summary += f"  {name:12s}: {ha:+,.1f} ha\n"

    return {
        "from_to_matrix": matrix,
        "class_names":    CLASS_NAMES,
        "net_change_ha":  net_change_ha,
        "forest_gain_ha": forest_gain_ha,
        "forest_loss_ha": forest_loss_ha,
        "summary_text":   summary,
    }


# ── Vegetation Change Summary ─────────────────────────────────────────────────

def vegetation_change_summary(
    ndvi_t1: np.ndarray,
    ndvi_t2: np.ndarray,
    pixel_area_m2: float,
    ndvi_threshold: float = 0.35,
    mean_crown_area_m2: float = 25.0,
) -> Dict:
    """Compute a complete vegetation change summary between two dates.

    Produces the headline numbers: vegetation area, estimated tree count,
    and change metrics for a report.

    Args:
        ndvi_t1:             Past NDVI array
        ndvi_t2:             Current NDVI array
        pixel_area_m2:       m² per pixel
        ndvi_threshold:      NDVI value above which a pixel counts as vegetation
        mean_crown_area_m2:  Mean tree crown area in m² for the biome

    Returns:
        dict with full change statistics
    """
    valid = ~(np.isnan(ndvi_t1) | np.isnan(ndvi_t2))
    total_area_ha = (valid.sum() * pixel_area_m2) / 10_000.0

    veg_t1 = valid & (ndvi_t1 > ndvi_threshold)
    veg_t2 = valid & (ndvi_t2 > ndvi_threshold)

    veg_area_t1_ha = (veg_t1.sum() * pixel_area_m2) / 10_000.0
    veg_area_t2_ha = (veg_t2.sum() * pixel_area_m2) / 10_000.0
    change_ha = veg_area_t2_ha - veg_area_t1_ha
    pct_change = (change_ha / (veg_area_t1_ha + 1e-6)) * 100.0

    # Estimated tree counts (allometric)
    n_trees_t1 = round(veg_t1.sum() * pixel_area_m2 / mean_crown_area_m2)
    n_trees_t2 = round(veg_t2.sum() * pixel_area_m2 / mean_crown_area_m2)
    n_trees_delta = n_trees_t2 - n_trees_t1

    mean_ndvi_t1 = float(np.nanmean(ndvi_t1[valid]))
    mean_ndvi_t2 = float(np.nanmean(ndvi_t2[valid]))

    return {
        "total_area_ha":       round(total_area_ha, 2),
        "veg_area_t1_ha":      round(veg_area_t1_ha, 2),
        "veg_area_t2_ha":      round(veg_area_t2_ha, 2),
        "veg_change_ha":       round(change_ha, 2),
        "veg_change_pct":      round(pct_change, 1),
        "estimated_trees_t1":  n_trees_t1,
        "estimated_trees_t2":  n_trees_t2,
        "estimated_trees_delta": n_trees_delta,
        "mean_ndvi_t1":        round(mean_ndvi_t1, 4),
        "mean_ndvi_t2":        round(mean_ndvi_t2, 4),
        "ndvi_threshold":      ndvi_threshold,
        "mean_crown_area_m2":  mean_crown_area_m2,
    }
