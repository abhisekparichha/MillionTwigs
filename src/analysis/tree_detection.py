"""
Individual tree crown detection.

Implements two approaches:
  1. DeepForest (Weinstein et al. 2020) — retinanet-based object detector
     pretrained on NEON airborne RGB data at ~0.1–1 m resolution.
     Works directly on Cartosat-3 PAN (0.25 m) or Planet (3 m) imagery.

  2. SAM (Segment Anything Model, Kirillov et al. 2023) — zero-shot
     prompted segmentation. Combined with NDVI masking to focus on
     vegetation pixels, then each segment is counted as a tree.

  3. Watershed segmentation on NDVI — classical morphological approach
     for medium-resolution (5–10 m) imagery where deep learning
     individual tree models underperform.

References:
  Weinstein et al. (2020). Methods in Ecology and Evolution, 11, 1743-1751.
  Kirillov et al. (2023). ICCV 2023, 4015-4026.
  Vincent & Soille (1991). IEEE TPAMI, 13(6), 583-598. [Watershed]
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np

try:
    import geopandas as gpd
    from shapely.geometry import box
    _GPDF_OK = True
except ImportError:
    _GPDF_OK = False

try:
    from scipy import ndimage
    from skimage.feature import peak_local_max
    from skimage.segmentation import watershed
    from skimage.morphology import binary_erosion, disk
    _SKIMAGE_OK = True
except ImportError:
    _SKIMAGE_OK = False


# ── DeepForest ────────────────────────────────────────────────────────────────

def detect_trees_deepforest(
    image_path: Union[str, Path],
    score_threshold: float = 0.4,
    patch_size: int = 400,
    patch_overlap: float = 0.05,
) -> "gpd.GeoDataFrame":
    """Detect individual tree crowns using DeepForest.

    DeepForest applies a RetinaNet model pretrained on 10,000+ manually
    annotated tree crowns from NEON Airborne Observation Platform imagery.

    Requires imagery at ≤ 1 m GSD. Works best at 0.1–0.5 m (Cartosat-3 PAN,
    Planet, drone imagery). At 1–3 m spatial resolution accuracy degrades.

    Reference: Weinstein, B.G. et al. (2020). Methods in Ecology and Evolution.

    Args:
        image_path:      Path to RGB GeoTIFF (3-band, uint8 or float [0,1])
        score_threshold: Minimum detection confidence (0–1)
        patch_size:      Tile size for inference (pixels); larger = more context
        patch_overlap:   Fractional overlap between patches (0–0.5)

    Returns:
        GeoDataFrame with columns: geometry (Polygon), score, label
        Coordinate reference system matches the input image.
    """
    try:
        from deepforest import main as df_main
    except ImportError:
        raise ImportError(
            "deepforest is not installed.\n"
            "Run: pip install deepforest\n"
            "Reference: Weinstein et al. 2020, Methods in Ecology and Evolution"
        )

    model = df_main.deepforest()
    model.use_release()  # loads NEON pretrained weights (downloaded automatically)

    boxes = model.predict_tile(
        raster_path=str(image_path),
        patch_size=patch_size,
        patch_overlap=patch_overlap,
        return_plot=False,
        thresh=score_threshold,
    )

    if boxes is None or boxes.empty:
        print("DeepForest: no trees detected.")
        return gpd.GeoDataFrame()

    # Convert pixel bounding boxes to spatial geometries
    import rasterio
    with rasterio.open(image_path) as src:
        transform = src.transform
        crs = src.crs

    geometries = []
    for _, row in boxes.iterrows():
        min_x, min_y = rasterio.transform.xy(
            transform, row["ymin"], row["xmin"], offset="ul"
        )
        max_x, max_y = rasterio.transform.xy(
            transform, row["ymax"], row["xmax"], offset="ul"
        )
        geometries.append(box(min_x, min_y, max_x, max_y))

    gdf = gpd.GeoDataFrame(
        {"score": boxes["score"].values, "label": boxes["label"].values},
        geometry=geometries,
        crs=crs,
    )
    print(f"DeepForest: detected {len(gdf)} tree crowns.")
    return gdf


# ── SAM — Segment Anything Model ─────────────────────────────────────────────

def detect_trees_sam(
    image_path: Union[str, Path],
    ndvi_threshold: float = 0.3,
    min_area_m2: float = 5.0,
    max_area_m2: float = 500.0,
    sam_checkpoint: Optional[str] = None,
    sam_model_type: str = "vit_h",
) -> "gpd.GeoDataFrame":
    """Detect tree crowns using the Segment Anything Model (SAM).

    Pipeline:
      1. Compute NDVI from NIR+Red bands (or use RGB if only RGB available)
      2. Create vegetation binary mask (NDVI > threshold)
      3. Run SAM automatic mask generator on the masked region
      4. Filter segments by area (remove tiny fragments, large non-tree segments)
      5. Return each segment as a potential tree crown polygon

    Reference: Kirillov, A. et al. (2023). ICCV 2023 — Meta AI Research.

    Args:
        image_path:      Path to GeoTIFF (RGB or multispectral)
        ndvi_threshold:  Minimum NDVI to consider a pixel as vegetation
        min_area_m2:     Minimum crown area in m² (removes noise)
        max_area_m2:     Maximum crown area in m² (removes large non-tree patches)
        sam_checkpoint:  Path to SAM model weights (.pth file).
                         Download from: https://github.com/facebookresearch/segment-anything
                         File: sam_vit_h_4b8939.pth (2.4 GB)
        sam_model_type:  "vit_h" (best), "vit_l", or "vit_b" (fastest)

    Returns:
        GeoDataFrame with tree crown polygons
    """
    try:
        from segment_anything import sam_model_registry, SamAutomaticMaskGenerator
    except ImportError:
        raise ImportError(
            "segment-anything is not installed.\n"
            "Run: pip install git+https://github.com/facebookresearch/segment-anything.git\n"
            "Then download weights from the SAM GitHub repository.\n"
            "Reference: Kirillov et al. 2023, ICCV"
        )
    import torch
    import rasterio
    import cv2
    from shapely.geometry import shape
    from rasterio.features import shapes

    with rasterio.open(image_path) as src:
        arr = src.read().astype(np.float32)
        transform = src.transform
        crs = src.crs
        pixel_area = abs(transform.a * transform.e)   # m² per pixel

    min_area_px = int(min_area_m2 / pixel_area)
    max_area_px = int(max_area_m2 / pixel_area)

    # Build RGB uint8 for SAM
    if arr.shape[0] >= 3:
        rgb = (np.clip(arr[:3], 0, 1) * 255).astype(np.uint8)
        rgb = np.moveaxis(rgb, 0, -1)   # (H, W, 3)
    else:
        raise ValueError("Image must have at least 3 bands (RGB).")

    # Load SAM model
    if sam_checkpoint is None:
        raise ValueError(
            "Provide the path to SAM weights via sam_checkpoint.\n"
            "Download: https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth"
        )
    device = "cuda" if torch.cuda.is_available() else "cpu"
    sam = sam_model_registry[sam_model_type](checkpoint=sam_checkpoint)
    sam.to(device)

    # Optional NDVI mask (if NIR band available at index 3)
    if arr.shape[0] >= 4:
        nir = arr[3]
        red = arr[2]
        ndvi_arr = np.where(
            (nir + red) > 0, (nir - red) / (nir + red + 1e-9), 0
        )
        veg_mask = ndvi_arr > ndvi_threshold
    else:
        veg_mask = np.ones(rgb.shape[:2], dtype=bool)

    generator = SamAutomaticMaskGenerator(
        model=sam,
        points_per_side=32,
        pred_iou_thresh=0.86,
        stability_score_thresh=0.92,
        min_mask_region_area=min_area_px,
    )
    masks = generator.generate(rgb)

    # Filter by area and NDVI overlap
    geometries = []
    for mask in masks:
        m = mask["mask"]
        area_px = m.sum()
        if area_px < min_area_px or area_px > max_area_px:
            continue
        veg_overlap = (m & veg_mask).sum() / (area_px + 1e-6)
        if veg_overlap < 0.6:
            continue
        # Convert mask to polygon
        for geom, _ in shapes(m.astype(np.uint8), transform=transform):
            geometries.append(shape(geom))

    gdf = gpd.GeoDataFrame(geometry=geometries, crs=crs)
    print(f"SAM: detected {len(gdf)} tree crowns.")
    return gdf


# ── Watershed Segmentation (medium resolution) ────────────────────────────────

def detect_trees_watershed(
    ndvi_array: np.ndarray,
    pixel_size_m: float = 5.8,
    min_crown_area_m2: float = 10.0,
    smoothing_sigma: float = 1.5,
    ndvi_threshold: float = 0.3,
) -> Tuple[np.ndarray, int]:
    """Detect tree canopy patches using watershed segmentation on NDVI.

    Suitable for LISS-IV (5.8 m) or Sentinel-2 (10 m) imagery where
    individual tree crowns are partially resolvable.

    Algorithm:
      1. Threshold NDVI to create vegetation binary mask
      2. Apply Gaussian smoothing to reduce noise
      3. Find local NDVI maxima (tree crown peaks)
      4. Run watershed from each peak to delineate individual crowns
      5. Filter segments by minimum crown area

    Reference: Vincent, L. & Soille, P. (1991). IEEE TPAMI, 13(6), 583-598.

    Args:
        ndvi_array:         2D NDVI float array
        pixel_size_m:       pixel resolution in metres (for area filtering)
        min_crown_area_m2:  minimum crown area to keep (removes noise)
        smoothing_sigma:    Gaussian blur sigma (pixels)
        ndvi_threshold:     minimum NDVI to be considered vegetation

    Returns:
        (label_array, n_trees) where label_array has an integer label per crown
    """
    if not _SKIMAGE_OK:
        raise ImportError(
            "scikit-image and scipy are required.\n"
            "Run: pip install scikit-image scipy"
        )

    veg_mask = ndvi_array > ndvi_threshold

    # Smooth to merge neighbouring peaks in same crown
    smoothed = ndimage.gaussian_filter(ndvi_array, sigma=smoothing_sigma)

    # Find local maxima (potential tree crown centres)
    min_distance_px = max(2, int(3.0 / pixel_size_m))   # ~3 m minimum crown radius
    coords = peak_local_max(
        smoothed,
        min_distance=min_distance_px,
        labels=veg_mask,
    )

    # Create markers for watershed
    markers = np.zeros_like(ndvi_array, dtype=np.int32)
    for i, (r, c) in enumerate(coords, start=1):
        markers[r, c] = i

    # Watershed on inverted NDVI (high NDVI = valley in the watershed space)
    labels = watershed(-smoothed, markers, mask=veg_mask)

    # Filter by minimum area
    min_area_px = int(min_crown_area_m2 / (pixel_size_m ** 2))
    unique, counts = np.unique(labels[labels > 0], return_counts=True)
    valid_labels = unique[counts >= min_area_px]

    filtered = np.where(np.isin(labels, valid_labels), labels, 0)
    n_trees = len(valid_labels)

    print(f"Watershed: detected {n_trees} tree crowns at {pixel_size_m} m resolution.")
    return filtered, n_trees


# ── Tree Count Estimation ─────────────────────────────────────────────────────

def estimate_tree_count_from_canopy(
    canopy_area_m2: float,
    biome: str = "tropical_dry",
) -> Dict[str, float]:
    """Estimate tree count from total canopy cover area using allometric scaling.

    When individual trees cannot be resolved (medium-resolution imagery),
    this provides a statistical estimate based on published crown-diameter
    allometric equations.

    Reference: Jucker, T. et al. (2017). Global Change Biology, 23(1), 177-190.
    Crown area-diameter relationships: Feldpausch et al. 2011, Global Change Biology.

    Mean crown area by biome (Jucker et al. 2017, Table 2):
      tropical_wet:   mean=40 m², SD=20
      tropical_dry:   mean=25 m², SD=12
      subtropical:    mean=20 m², SD=10
      temperate:      mean=18 m², SD=8
      boreal:         mean=12 m², SD=5
      urban:          mean=15 m², SD=8

    Args:
        canopy_area_m2: total vegetated area in m²
        biome:          one of the biome keys above

    Returns:
        dict with keys "estimate", "lower_95ci", "upper_95ci"
    """
    crown_stats = {
        "tropical_wet":  {"mean": 40.0, "sd": 20.0},
        "tropical_dry":  {"mean": 25.0, "sd": 12.0},
        "subtropical":   {"mean": 20.0, "sd": 10.0},
        "temperate":     {"mean": 18.0, "sd": 8.0},
        "boreal":        {"mean": 12.0, "sd": 5.0},
        "urban":         {"mean": 15.0, "sd": 8.0},
    }
    if biome not in crown_stats:
        raise ValueError(f"biome must be one of {list(crown_stats.keys())}")

    stats = crown_stats[biome]
    mean_ca = stats["mean"]
    sd_ca = stats["sd"]

    # Point estimate
    n_estimate = canopy_area_m2 / mean_ca
    # 95% CI from propagation of uncertainty (assuming normal distribution of crown area)
    n_lower = canopy_area_m2 / (mean_ca + 1.96 * sd_ca)
    n_upper = canopy_area_m2 / max(mean_ca - 1.96 * sd_ca, 1.0)

    return {
        "estimate":   round(n_estimate),
        "lower_95ci": round(n_lower),
        "upper_95ci": round(n_upper),
        "canopy_area_m2": canopy_area_m2,
        "mean_crown_area_m2": mean_ca,
        "biome": biome,
    }
