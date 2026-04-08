# Sensor Band Reference

## ISRO Resourcesat-2 / 2A

### LISS-IV Multispectral (5.8 m)
| Band | Wavelength (µm) | Name | Use |
|------|-----------------|------|-----|
| B2 | 0.52–0.59 | Green | Vegetation health, water penetration |
| B3 | 0.62–0.68 | Red | Chlorophyll absorption, NDVI denominator |
| B4 | 0.77–0.86 | NIR | NDVI numerator, biomass |

**Key formula**: `NDVI = (B4 - B3) / (B4 + B3)`

### LISS-III (23.5 m)
| Band | Wavelength (µm) | Name |
|------|-----------------|------|
| B2 | 0.52–0.59 | Green |
| B3 | 0.62–0.68 | Red |
| B4 | 0.77–0.86 | NIR |
| B5 | 1.55–1.70 | SWIR |

### AWiFS (56 m)
Same band layout as LISS-III (B2–B5).

### Cartosat-3 Multispectral (1.0 m)
| Band | Wavelength (µm) | Name |
|------|-----------------|------|
| B1 | 0.45–0.52 | Blue |
| B2 | 0.52–0.60 | Green |
| B3 | 0.63–0.69 | Red |
| B4 | 0.77–0.89 | NIR |

---

## ESA Sentinel-2 (10/20/60 m)

| Band | GSD | Wavelength (nm) | Name | Key Use |
|------|-----|-----------------|------|---------|
| B1  | 60 m | 443 | Coastal aerosol | Aerosol correction |
| B2  | 10 m | 490 | Blue | EVI blue correction |
| B3  | 10 m | 560 | Green | NDWI |
| B4  | 10 m | 665 | Red | NDVI denominator |
| B5  | 20 m | 705 | Red Edge 1 | NDRE, chlorophyll |
| B6  | 20 m | 740 | Red Edge 2 | Chlorophyll content |
| B7  | 20 m | 783 | Red Edge 3 | LAI, canopy structure |
| B8  | 10 m | 842 | NIR | NDVI numerator |
| B8A | 20 m | 865 | NIR narrow | Precise vegetation |
| B9  | 60 m | 945 | Water vapour | Atmospheric correction |
| B11 | 20 m | 1610 | SWIR 1 | Soil moisture, NBR |
| B12 | 20 m | 2190 | SWIR 2 | Fire detection, NBR |

### Key Sentinel-2 Formulas (GEE band names)
```python
NDVI  = (B8  - B4)  / (B8  + B4)
EVI   = 2.5 * (B8 - B4) / (B8 + 6*B4 - 7.5*B2 + 1)
NDRE  = (B8A - B5)  / (B8A + B5)    # Red-Edge NDVI
NDWI  = (B3  - B8)  / (B3  + B8)    # Water index
MNDWI = (B3  - B11) / (B3  + B11)   # Modified water
NBR   = (B8  - B12) / (B8  + B12)   # Burn ratio
```

---

## USGS Landsat 8 / 9 (30 m)

| Band | Wavelength (µm) | Name |
|------|-----------------|------|
| B2 | 0.452–0.512 | Blue |
| B3 | 0.533–0.590 | Green |
| B4 | 0.636–0.673 | Red |
| B5 | 0.851–0.879 | NIR |
| B6 | 1.566–1.651 | SWIR 1 |
| B7 | 2.107–2.294 | SWIR 2 |
| B8 | 0.503–0.676 | Pan (15m) |

**Collection 2 scaling**: `Reflectance = DN × 0.0000275 + (-0.2)`

```python
NDVI = (B5 - B4) / (B5 + B4)
EVI  = 2.5 * (B5 - B4) / (B5 + 6*B4 - 7.5*B2 + 1)
NBR  = (B5 - B7) / (B5 + B7)
```

---

## Landsat 5 TM (30 m) — Historical archive from 1984

| Band | Wavelength (µm) | Name |
|------|-----------------|------|
| B1 | 0.45–0.52 | Blue |
| B2 | 0.52–0.60 | Green |
| B3 | 0.63–0.69 | Red |
| B4 | 0.76–0.90 | NIR |
| B5 | 1.55–1.75 | SWIR 1 |
| B7 | 2.08–2.35 | SWIR 2 |

`NDVI = (B4 - B3) / (B4 + B3)` — consistent formula across all Landsat missions.

---

## NDVI Interpretation Thresholds (India-specific)

Based on: FSI (Forest Survey of India) vegetation mapping guidelines,
Jha et al. (2020) for Indian tropical forests.

| NDVI Range | Class | Approx. Canopy Cover |
|---|---|---|
| < 0.10 | Non-vegetation (water, rock, urban) | 0% |
| 0.10–0.20 | Scrubland, degraded land | < 10% |
| 0.20–0.35 | Open scrub, degraded forest | 10–25% |
| 0.35–0.50 | Moderately dense forest | 25–50% |
| 0.50–0.65 | Dense forest | 50–70% |
| 0.65–0.90 | Very dense forest, peak season | > 70% |

**Note**: Thresholds shift during monsoon season (June–September) — NDVI
is elevated for all vegetation classes due to increased moisture.
Use dry season imagery (Jan–May) for consistent inter-annual comparisons.
