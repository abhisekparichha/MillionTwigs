"""
U-Net architecture for binary canopy segmentation.

Reference: Ronneberger, O., Fischer, P., Bröker, T. (2015).
  U-Net: Convolutional Networks for Biomedical Image Segmentation.
  MICCAI 2015, LNCS 9351, 234-241.

Two modes are provided:
  1. segmentation_models_pytorch wrapper (recommended) — uses ImageNet-
     pretrained encoders (ResNet50, EfficientNet-B4, etc.) for better
     generalisation with limited labelled satellite data.

  2. Minimal custom U-Net — built purely in PyTorch, useful for
     understanding the architecture and for very lightweight deployment.

Training data required:
  - Positive class: tree canopy pixels (from manual labels or
    pseudo-labels derived from LiDAR / high-confidence NDVI)
  - Negative class: non-canopy pixels

If no labelled data is available, use the DeepForest or watershed
approach from tree_detection.py instead.
"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    _TORCH_OK = True
except ImportError:
    _TORCH_OK = False


def _require_torch() -> None:
    if not _TORCH_OK:
        raise ImportError(
            "PyTorch is required. Install: pip install torch torchvision\n"
            "See: https://pytorch.org/get-started/locally/"
        )


# ── SMP-based U-Net (recommended) ─────────────────────────────────────────────

def build_smp_unet(
    encoder_name: str = "resnet50",
    encoder_weights: str = "imagenet",
    in_channels: int = 4,    # RGB + NIR
    classes: int = 1,
) -> "nn.Module":
    """Build a U-Net using segmentation-models-pytorch.

    Uses an ImageNet-pretrained encoder as the backbone, which provides
    significantly better performance than training from scratch when
    labelled satellite data is limited (< 1000 patches).

    Args:
        encoder_name:    ResNet or EfficientNet encoder:
                         "resnet50"         — balanced accuracy/speed
                         "efficientnet-b4"  — best accuracy for satellite imagery
                         "resnet34"         — fastest, for GPU-constrained setups
        encoder_weights: "imagenet" or None
        in_channels:     number of input bands (4 for RGB+NIR, 3 for RGB only)
        classes:         number of output classes (1 for binary canopy/non-canopy)

    Returns:
        torch.nn.Module ready for inference or fine-tuning
    """
    _require_torch()
    try:
        import segmentation_models_pytorch as smp
    except ImportError:
        raise ImportError(
            "segmentation-models-pytorch is required.\n"
            "Run: pip install segmentation-models-pytorch"
        )

    model = smp.Unet(
        encoder_name=encoder_name,
        encoder_weights=encoder_weights,
        in_channels=in_channels,
        classes=classes,
        activation=None,    # raw logits; use sigmoid in inference
    )
    return model


# ── Minimal custom U-Net (for reference / lightweight use) ────────────────────

class _DoubleConv(nn.Module):
    """Two consecutive 3×3 convolutions with BatchNorm and ReLU."""

    def __init__(self, in_ch: int, out_ch: int) -> None:
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_ch, out_ch, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: "torch.Tensor") -> "torch.Tensor":
        return self.block(x)


class MinimalUNet(nn.Module):
    """Lightweight U-Net for binary canopy segmentation.

    Architecture:
      Encoder: 4 downsampling blocks (3×3 conv, ReLU, MaxPool)
      Bottleneck: double conv at lowest resolution
      Decoder: 4 upsampling blocks (bilinear up + skip connection + conv)
      Output: 1×1 conv → logit map (apply sigmoid for probability)

    Reference: Ronneberger et al. (2015), MICCAI.
    """

    def __init__(
        self,
        in_channels: int = 4,
        features: Tuple[int, ...] = (64, 128, 256, 512),
    ) -> None:
        _require_torch()
        super().__init__()
        self.downs = nn.ModuleList()
        self.ups = nn.ModuleList()
        self.pool = nn.MaxPool2d(2, 2)

        # Encoder path
        ch = in_channels
        for feat in features:
            self.downs.append(_DoubleConv(ch, feat))
            ch = feat

        # Bottleneck
        self.bottleneck = _DoubleConv(features[-1], features[-1] * 2)

        # Decoder path
        for feat in reversed(features):
            self.ups.append(
                nn.ConvTranspose2d(feat * 2, feat, kernel_size=2, stride=2)
            )
            self.ups.append(_DoubleConv(feat * 2, feat))

        self.final = nn.Conv2d(features[0], 1, kernel_size=1)

    def forward(self, x: "torch.Tensor") -> "torch.Tensor":
        skip_connections = []

        for down in self.downs:
            x = down(x)
            skip_connections.append(x)
            x = self.pool(x)

        x = self.bottleneck(x)
        skip_connections.reverse()

        for i in range(0, len(self.ups), 2):
            x = self.ups[i](x)      # transpose conv (upsample)
            skip = skip_connections[i // 2]
            if x.shape != skip.shape:
                x = F.interpolate(x, size=skip.shape[2:])
            x = torch.cat([skip, x], dim=1)
            x = self.ups[i + 1](x)  # double conv

        return self.final(x)


# ── Inference on image tiles ───────────────────────────────────────────────────

def predict_canopy(
    model: "nn.Module",
    image_array: np.ndarray,
    patch_size: int = 256,
    overlap: int = 64,
    threshold: float = 0.5,
    device: Optional[str] = None,
) -> np.ndarray:
    """Run U-Net inference on a full satellite image using sliding window.

    Handles images larger than GPU memory by processing patch by patch
    and averaging overlapping predictions (reduces boundary artefacts).

    Args:
        model:       Trained U-Net (nn.Module), in eval mode
        image_array: Input array shape (bands, H, W), float32, [0, 1]
        patch_size:  Tile size for inference
        overlap:     Overlap in pixels between adjacent tiles
        threshold:   Sigmoid threshold for binary canopy mask
        device:      "cuda" or "cpu" (auto-detected if None)

    Returns:
        Binary canopy mask array shape (H, W), dtype uint8 (0 or 1)
    """
    _require_torch()
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    model = model.to(device).eval()
    _, H, W = image_array.shape
    stride = patch_size - overlap

    prob_map = np.zeros((H, W), dtype=np.float32)
    count_map = np.zeros((H, W), dtype=np.float32)

    with torch.no_grad():
        for row in range(0, H, stride):
            for col in range(0, W, stride):
                r_end = min(row + patch_size, H)
                c_end = min(col + patch_size, W)
                patch = image_array[:, row:r_end, col:c_end].copy()

                # Pad to patch_size if edge
                pad_h = patch_size - patch.shape[1]
                pad_w = patch_size - patch.shape[2]
                if pad_h > 0 or pad_w > 0:
                    patch = np.pad(patch, ((0, 0), (0, pad_h), (0, pad_w)))

                tensor = torch.from_numpy(patch[np.newaxis]).float().to(device)
                logit = model(tensor)
                prob = torch.sigmoid(logit).squeeze().cpu().numpy()

                # Accumulate (only the non-padded region)
                h = r_end - row
                w = c_end - col
                prob_map[row:r_end, col:c_end] += prob[:h, :w]
                count_map[row:r_end, col:c_end] += 1.0

    # Average overlapping regions
    prob_map /= np.maximum(count_map, 1)
    return (prob_map > threshold).astype(np.uint8)
