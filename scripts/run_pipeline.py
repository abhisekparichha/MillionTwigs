#!/usr/bin/env python3
"""
MillionTwigs — End-to-end CLI pipeline.

Usage:
  python scripts/run_pipeline.py --config config.yaml --source sentinel2

Runs the full pipeline:
  1. Download imagery from GEE (Sentinel-2 or Landsat)
  2. Compute vegetation indices (NDVI, EVI, NDRE)
  3. Detect tree canopy via selected method
  4. Run change detection between baseline and current periods
  5. Generate HTML map and summary report

Requires: earthengine authenticate (one-time setup)
"""

import argparse
import json
import sys
from pathlib import Path

import yaml
import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analysis.indices import compute_all_indices
from src.analysis.change_detection import (
    ndvi_difference,
    post_classification_comparison,
    classify_vegetation,
    vegetation_change_summary,
)
from src.visualization.maps import (
    create_base_map,
    ndvi_to_rgb,
    add_raster_overlay,
    add_change_map,
    save_map,
    create_change_summary_chart,
)


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def bbox_center(bbox: list) -> tuple:
    """Return (lat, lon) centre of a [min_lon, min_lat, max_lon, max_lat] bbox."""
    return ((bbox[1] + bbox[3]) / 2, (bbox[0] + bbox[2]) / 2)


def run_gee_pipeline(cfg: dict) -> dict:
    """Download and process imagery via Google Earth Engine."""
    from src.data.gee_downloader import (
        initialize_gee,
        get_sentinel2_median,
        get_landsat_median,
        get_hansen_forest_change,
    )
    import ee

    print("[1/5] Initialising Google Earth Engine...")
    initialize_gee(project=cfg["credentials"].get("gee_project"))

    bbox = cfg["aoi"]["bbox"]
    source = cfg["source"]["primary"]
    max_cloud = cfg["source"]["cloud_cover_max"]

    def fetch_image(period: str):
        d = cfg["dates"][period]
        start, end = d["start"], d["end"]
        print(f"  Fetching {source.upper()} composite: {d['label']} ({start} – {end})")
        if source == "sentinel2":
            return get_sentinel2_median(bbox, start, end, max_cloud)
        elif source in ("landsat8", "landsat9"):
            sat = "L8" if source == "landsat8" else "L9"
            return get_landsat_median(bbox, start, end, sat)
        else:
            raise ValueError(f"Unsupported source: {source}")

    print("[2/5] Fetching baseline and current imagery...")
    img_baseline = fetch_image("baseline")
    img_current  = fetch_image("current")

    print("[3/5] Computing vegetation indices on GEE...")
    if source == "sentinel2":
        s2_cfg = cfg["sentinel2"]
        def compute_ee_indices(img):
            nir  = img.select(s2_cfg["bands"]["nir"])
            red  = img.select(s2_cfg["bands"]["red"])
            blue = img.select(s2_cfg["bands"]["blue"])
            ndvi_img = nir.subtract(red).divide(nir.add(red)).rename("NDVI")
            evi_img  = (
                nir.subtract(red).multiply(2.5)
                .divide(nir.add(red.multiply(6)).subtract(blue.multiply(7.5)).add(1))
                .rename("EVI")
            )
            return img.addBands([ndvi_img, evi_img])
        img_baseline = compute_ee_indices(img_baseline)
        img_current  = compute_ee_indices(img_current)

    # Get Hansen GFC reference
    print("[4/5] Fetching Hansen Global Forest Change reference layer...")
    hansen = get_hansen_forest_change(bbox)

    print("[5/5] Exporting index images to Google Drive...")
    from src.data.gee_downloader import export_image_to_drive, wait_for_tasks
    aoi_name = cfg["aoi"]["name"].replace(" ", "_")
    scale = 10 if source == "sentinel2" else 30
    tasks = []
    for label, img in [
        (f"{aoi_name}_baseline_indices", img_baseline.select(["NDVI", "EVI"])),
        (f"{aoi_name}_current_indices",  img_current.select(["NDVI", "EVI"])),
    ]:
        t = export_image_to_drive(img, label, scale=scale, bbox=bbox)
        tasks.append(t)

    print("  Export tasks started. Monitor at: https://code.earthengine.google.com/tasks")
    print("  (Exports may take 5–30 minutes depending on AOI size)")

    return {
        "img_baseline": img_baseline,
        "img_current":  img_current,
        "hansen":       hansen,
        "tasks":        tasks,
    }


def run_local_pipeline(cfg: dict, baseline_path: str, current_path: str) -> dict:
    """Run analysis on locally downloaded rasters.

    Args:
        baseline_path: Path to baseline NDVI GeoTIFF
        current_path:  Path to current NDVI GeoTIFF

    Returns:
        Summary statistics dict
    """
    from src.preprocessing.image_utils import read_bands
    import rasterio

    print("[1/4] Loading rasters...")
    ndvi_t1, profile_t1 = read_bands(baseline_path, band_indices=[1])
    ndvi_t2, profile_t2 = read_bands(current_path, band_indices=[1])
    ndvi_t1 = ndvi_t1[0]
    ndvi_t2 = ndvi_t2[0]

    with rasterio.open(baseline_path) as src:
        transform = src.transform
        crs = src.crs
        bbox = [src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top]

    pixel_area_m2 = abs(transform.a * transform.e)
    print(f"  Pixel area: {pixel_area_m2:.1f} m²")
    print(f"  Array shape: {ndvi_t1.shape}")

    print("[2/4] Computing change detection...")
    diff = ndvi_difference(ndvi_t1, ndvi_t2, threshold_std=1.5)
    classes_t1 = classify_vegetation(ndvi_t1)
    classes_t2 = classify_vegetation(ndvi_t2)
    pcc = post_classification_comparison(classes_t1, classes_t2, pixel_area_m2)

    mean_crown = cfg["analysis"]["mean_crown_area_m2"]
    ndvi_thresh = cfg["analysis"]["vegetation_threshold"]
    summary = vegetation_change_summary(
        ndvi_t1, ndvi_t2, pixel_area_m2, ndvi_thresh, mean_crown
    )

    print("[3/4] Creating visualisations...")
    out_dir = Path(cfg["output"]["base_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    # NDVI overlay images
    ndvi_rgba_t1 = ndvi_to_rgb(ndvi_t1)
    ndvi_rgba_t2 = ndvi_to_rgb(ndvi_t2)

    # Compute map bounds [[S, W], [N, E]]
    map_bounds = [[bbox[1], bbox[0]], [bbox[3], bbox[2]]]
    center = bbox_center(bbox)

    # Interactive map
    m = create_base_map(center, zoom=13)
    add_raster_overlay(m, ndvi_rgba_t1, map_bounds,
                       name=f"NDVI {cfg['dates']['baseline']['label']}", opacity=0.7)
    add_raster_overlay(m, ndvi_rgba_t2, map_bounds,
                       name=f"NDVI {cfg['dates']['current']['label']}", opacity=0.7)
    add_change_map(m, diff["gain_mask"], diff["loss_mask"], map_bounds)

    map_path = out_dir / "vegetation_change_map.html"
    save_map(m, map_path)

    # Summary chart
    chart_path = out_dir / "change_summary.png"
    create_change_summary_chart(summary, chart_path)

    print("[4/4] Writing report...")
    report = {
        "aoi": cfg["aoi"]["name"],
        "baseline_label": cfg["dates"]["baseline"]["label"],
        "current_label":  cfg["dates"]["current"]["label"],
        "source": cfg["source"]["primary"],
        "summary": summary,
        "pcc": {
            k: v for k, v in pcc.items()
            if k not in ("from_to_matrix",)
        },
    }
    report_path = out_dir / "report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    print("\n" + "=" * 60)
    print("  VEGETATION CHANGE REPORT")
    print("=" * 60)
    print(f"  Area:           {cfg['aoi']['name']}")
    print(f"  Baseline:       {cfg['dates']['baseline']['label']}")
    print(f"  Current:        {cfg['dates']['current']['label']}")
    print(f"  Total AOI:      {summary['total_area_ha']:,.1f} ha")
    print(f"  Veg area (past):{summary['veg_area_t1_ha']:,.1f} ha")
    print(f"  Veg area (now): {summary['veg_area_t2_ha']:,.1f} ha")
    print(f"  Change:         {summary['veg_change_ha']:+,.1f} ha ({summary['veg_change_pct']:+.1f}%)")
    print(f"  Est. trees past:{summary['estimated_trees_t1']:,}")
    print(f"  Est. trees now: {summary['estimated_trees_t2']:,}")
    print(f"  Tree delta:     {summary['estimated_trees_delta']:+,}")
    print("=" * 60)
    print(f"\nOutputs saved to: {out_dir}/")
    print(f"  Map:    {map_path}")
    print(f"  Chart:  {chart_path}")
    print(f"  Report: {report_path}")

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="MillionTwigs — Satellite Vegetation Analysis Pipeline"
    )
    parser.add_argument("--config", default="config.yaml",
                        help="Path to config.yaml")
    parser.add_argument("--source", choices=["gee", "local"],
                        default="gee",
                        help="Data source: 'gee' (Google Earth Engine) or 'local' (downloaded rasters)")
    parser.add_argument("--baseline", default=None,
                        help="[local mode] Path to baseline NDVI GeoTIFF")
    parser.add_argument("--current",  default=None,
                        help="[local mode] Path to current NDVI GeoTIFF")
    args = parser.parse_args()

    cfg = load_config(args.config)

    if args.source == "gee":
        run_gee_pipeline(cfg)
    else:
        if not args.baseline or not args.current:
            parser.error("--baseline and --current are required in local mode.")
        run_local_pipeline(cfg, args.baseline, args.current)


if __name__ == "__main__":
    main()
