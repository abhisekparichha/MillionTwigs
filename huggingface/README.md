---
title: MillionTwigs
emoji: 🌳
colorFrom: green
colorTo: blue
sdk: streamlit
sdk_version: "1.33.0"
app_file: app.py
pinned: false
license: mit
---

# MillionTwigs — Satellite Vegetation & Tree Analysis

Interactive demo for detecting and counting trees from satellite imagery,
with temporal change detection between two time periods.

## Deploy to Hugging Face Spaces

1. Create a new Space at [huggingface.co/spaces](https://huggingface.co/spaces)
2. Select **Streamlit** as the SDK
3. Push this repository to the Space

## Connect real satellite data

Edit `config.yaml` to set your AOI bounding box, then follow the
data sourcing guide in [README.md](../README.md).
