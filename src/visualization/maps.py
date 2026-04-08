"""
Interactive map visualisation using Folium.

Generates Leaflet-based HTML maps showing:
  - NDVI / EVI raster overlays
  - Detected tree crown polygons
  - Change detection maps (gain / loss)
  - Before/after sliders
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np

try:
    import folium
    from folium.plugins import SideBySideLayers
    _FOLIUM_OK = True
except ImportError:
    _FOLIUM_OK = False

try:
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
    _MPL_OK = True
except ImportError:
    _MPL_OK = False


def _require_folium() -> None:
    if not _FOLIUM_OK:
        raise ImportError("folium is required. Run: pip install folium")


def create_base_map(
    center: Tuple[float, float],
    zoom: int = 13,
) -> "folium.Map":
    """Create a base Folium map centred on (lat, lon).

    Args:
        center: (latitude, longitude) tuple
        zoom:   initial zoom level (12–15 for tree-scale analysis)

    Returns:
        folium.Map object
    """
    _require_folium()
    m = folium.Map(
        location=center,
        zoom_start=zoom,
        tiles=None,
    )
    # Satellite basemap
    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        attr="Google Satellite",
        name="Satellite",
        max_zoom=21,
    ).add_to(m)
    # OpenStreetMap
    folium.TileLayer(
        tiles="OpenStreetMap",
        name="OpenStreetMap",
    ).add_to(m)
    folium.LayerControl().add_to(m)
    return m


def ndvi_to_rgb(
    ndvi_array: np.ndarray,
    colormap: str = "RdYlGn",
    vmin: float = 0.0,
    vmax: float = 0.9,
) -> np.ndarray:
    """Convert a 2D NDVI array to an RGBA uint8 array for overlay.

    Args:
        ndvi_array: 2D float array
        colormap:   matplotlib colormap name
        vmin, vmax: value range for colour mapping

    Returns:
        RGBA array shape (H, W, 4), dtype uint8
    """
    if not _MPL_OK:
        raise ImportError("matplotlib is required.")
    cmap = plt.get_cmap(colormap)
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax, clip=True)
    mapped = cmap(norm(ndvi_array))   # (H, W, 4) float [0, 1]
    # Set NaN pixels transparent
    nan_mask = np.isnan(ndvi_array)
    mapped[nan_mask, 3] = 0.0
    return (mapped * 255).astype(np.uint8)


def add_raster_overlay(
    m: "folium.Map",
    rgba_array: np.ndarray,
    bounds: List[List[float]],
    name: str = "NDVI",
    opacity: float = 0.7,
) -> "folium.Map":
    """Overlay an RGBA array as a semi-transparent image on the map.

    Args:
        m:          Folium map
        rgba_array: RGBA uint8 array (H, W, 4)
        bounds:     [[min_lat, min_lon], [max_lat, max_lon]]
        name:       layer name in the layer control
        opacity:    overlay opacity (0–1)

    Returns:
        Updated Folium map
    """
    _require_folium()
    import io
    import base64
    from PIL import Image

    img = Image.fromarray(rgba_array, mode="RGBA")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    img_b64 = base64.b64encode(buffer.getvalue()).decode()
    img_url = f"data:image/png;base64,{img_b64}"

    folium.raster_layers.ImageOverlay(
        image=img_url,
        bounds=bounds,
        opacity=opacity,
        name=name,
        cross_origin=False,
    ).add_to(m)
    return m


def add_tree_crowns(
    m: "folium.Map",
    gdf: "geopandas.GeoDataFrame",
    label: str = "Detected Trees",
    color: str = "lime",
    fill_opacity: float = 0.3,
) -> "folium.Map":
    """Add tree crown polygons / bounding boxes as a GeoJSON layer.

    Args:
        m:     Folium map
        gdf:   GeoDataFrame with crown geometries (in WGS-84 EPSG:4326)
        label: Layer label
        color: Stroke colour
        fill_opacity: Fill transparency

    Returns:
        Updated Folium map
    """
    _require_folium()
    try:
        import geopandas as gpd
    except ImportError:
        raise ImportError("geopandas is required.")

    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    folium.GeoJson(
        gdf.__geo_interface__,
        name=label,
        style_function=lambda _: {
            "color": color,
            "fillColor": color,
            "weight": 1,
            "fillOpacity": fill_opacity,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=[c for c in ["score", "area_m2", "label"] if c in gdf.columns],
            localize=True,
        ),
    ).add_to(m)
    folium.LayerControl().add_to(m)
    return m


def add_change_map(
    m: "folium.Map",
    gain_mask: np.ndarray,
    loss_mask: np.ndarray,
    bounds: List[List[float]],
    gain_color: Tuple[int, int, int] = (0, 200, 0),
    loss_color: Tuple[int, int, int] = (220, 0, 0),
    opacity: float = 0.65,
) -> "folium.Map":
    """Overlay vegetation gain (green) and loss (red) masks on the map.

    Args:
        gain_mask:  Boolean array for vegetation gain pixels
        loss_mask:  Boolean array for vegetation loss pixels
        bounds:     [[min_lat, min_lon], [max_lat, max_lon]]
    """
    H, W = gain_mask.shape
    rgba = np.zeros((H, W, 4), dtype=np.uint8)

    # Green for gain
    rgba[gain_mask, 0] = gain_color[0]
    rgba[gain_mask, 1] = gain_color[1]
    rgba[gain_mask, 2] = gain_color[2]
    rgba[gain_mask, 3] = int(opacity * 255)

    # Red for loss
    rgba[loss_mask, 0] = loss_color[0]
    rgba[loss_mask, 1] = loss_color[1]
    rgba[loss_mask, 2] = loss_color[2]
    rgba[loss_mask, 3] = int(opacity * 255)

    return add_raster_overlay(m, rgba, bounds, name="Vegetation Change", opacity=1.0)


def save_map(m: "folium.Map", output_path: Union[str, Path]) -> Path:
    """Save a Folium map to an HTML file."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(output_path))
    print(f"Map saved to: {output_path}")
    return output_path


def create_change_summary_chart(
    summary: Dict,
    output_path: Optional[Union[str, Path]] = None,
) -> None:
    """Create a bar chart comparing vegetation statistics between two dates.

    Args:
        summary: output dict from change_detection.vegetation_change_summary()
        output_path: if given, save as PNG; else display
    """
    if not _MPL_OK:
        raise ImportError("matplotlib is required.")

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("Vegetation Change Analysis — MillionTwigs", fontsize=14, fontweight="bold")

    # Left: vegetation area comparison
    ax = axes[0]
    labels = ["Past", "Present"]
    areas = [summary["veg_area_t1_ha"], summary["veg_area_t2_ha"]]
    colors = ["#4CAF50", "#2196F3"]
    bars = ax.bar(labels, areas, color=colors, width=0.5, edgecolor="black", linewidth=0.8)
    ax.set_ylabel("Vegetation Area (ha)", fontsize=11)
    ax.set_title("Vegetated Area", fontsize=12)
    for bar, val in zip(bars, areas):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                f"{val:,.1f} ha", ha="center", va="bottom", fontsize=10)
    change = summary["veg_change_ha"]
    color = "green" if change >= 0 else "red"
    ax.annotate(
        f"Change: {change:+,.1f} ha ({summary['veg_change_pct']:+.1f}%)",
        xy=(0.5, 0.05), xycoords="axes fraction",
        ha="center", color=color, fontsize=11, fontweight="bold",
    )

    # Right: estimated tree count
    ax2 = axes[1]
    trees = [summary["estimated_trees_t1"], summary["estimated_trees_t2"]]
    bars2 = ax2.bar(labels, trees, color=colors, width=0.5, edgecolor="black", linewidth=0.8)
    ax2.set_ylabel("Estimated Tree Count", fontsize=11)
    ax2.set_title("Estimated Number of Trees", fontsize=12)
    for bar, val in zip(bars2, trees):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 10,
                 f"{val:,}", ha="center", va="bottom", fontsize=10)
    delta = summary["estimated_trees_delta"]
    ax2.annotate(
        f"Change: {delta:+,} trees",
        xy=(0.5, 0.05), xycoords="axes fraction",
        ha="center", color="green" if delta >= 0 else "red",
        fontsize=11, fontweight="bold",
    )

    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        print(f"Chart saved to: {output_path}")
    else:
        plt.show()
    plt.close()
