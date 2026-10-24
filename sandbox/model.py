"""TorchXRayVision DenseNet-121 (`densenet121-res224-all`) inference + Grad-CAM, CPU only.

Teaching and research only — not a clinical device.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import torch
import torch.nn.functional as F
import torchxrayvision as xrv
from PIL import Image

WEIGHTS = "densenet121-res224-all"
INPUT_SIZE = 224
MAX_SIDE = 4096  # reject absurdly large uploads before decoding further
torch.set_num_threads(max(1, torch.get_num_threads()))


@dataclass(frozen=True)
class Finding:
    label: str
    score: float


@dataclass(frozen=True)
class Result:
    findings: tuple[Finding, ...]
    cam_label: str
    overlay_png: bytes
    image_png: bytes


@lru_cache(maxsize=1)
def load_model() -> xrv.models.DenseNet:
    model = xrv.models.DenseNet(weights=WEIGHTS)
    return model.eval()


def read_grayscale(data: bytes) -> np.ndarray:
    """Decode image bytes to a 2-D uint8 array; raises ValueError on bad input."""
    try:
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()
        img = Image.open(io.BytesIO(data))
        if max(img.size) > MAX_SIDE:
            raise ValueError(f"Image is larger than {MAX_SIDE}px on a side.")
        return np.asarray(img.convert("L"), dtype=np.uint8)
    except ValueError:
        raise
    except Exception as exc:  # PIL raises many types for corrupt files
        raise ValueError("Could not read this file as an image.") from exc


def center_crop(gray: np.ndarray) -> np.ndarray:
    """Square centre crop, as in TorchXRayVision training (XRayCenterCrop).

    Very tall or wide images lose their edges (e.g. apices); that is how the model was trained.
    """
    h, w = gray.shape
    side = min(h, w)
    top, left = (h - side) // 2, (w - side) // 2
    return gray[top:top + side, left:left + side]


def to_tensor(square: np.ndarray) -> torch.Tensor:
    resized = np.asarray(Image.fromarray(square).resize((INPUT_SIZE, INPUT_SIZE), Image.BILINEAR), dtype=np.float32)
    scaled = xrv.datasets.normalize(resized, 255)  # -> [-1024, 1024], as the model expects
    return torch.from_numpy(scaled)[None, None]


def forward_with_features(model: xrv.models.DenseNet, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """Replicates DenseNet.forward but keeps the last conv feature map for Grad-CAM."""
    feats = F.relu(model.features(x))
    pooled = F.adaptive_avg_pool2d(feats, (1, 1)).flatten(1)
    logits = model.classifier(pooled)
    if getattr(model, "op_threshs", None) is not None:
        # Calibrated so that 0.5 sits at each label's operating threshold.
        scores = torch.sigmoid(logits)
        scores = xrv.models.op_norm(scores, model.op_threshs)
    else:
        scores = torch.sigmoid(logits)
    return feats, scores


def grad_cam(feats: torch.Tensor, score: torch.Tensor) -> np.ndarray:
    grads = torch.autograd.grad(score, feats, retain_graph=True)[0]
    weights = grads.mean(dim=(2, 3), keepdim=True)
    cam = F.relu((weights * feats).sum(dim=1))[0].detach().numpy()
    if cam.max() > 0:
        cam = cam / cam.max()
    return cam


def colorize(cam: np.ndarray, side: int) -> np.ndarray:
    """Upsample CAM and map to an RGBA 'inferno-like' heat colour."""
    up = np.asarray(Image.fromarray((cam * 255).astype(np.uint8)).resize((side, side), Image.BICUBIC),
                    dtype=np.float32) / 255.0
    r = np.clip(1.6 * up, 0, 1)
    g = np.clip(1.6 * up - 0.55, 0, 1)
    b = np.clip(0.7 - 1.4 * np.abs(up - 0.35), 0, 1) * 0.8
    alpha = np.clip((up - 0.15) / 0.85, 0, 1) * 0.65
    return np.dstack([r, g, b, alpha])


def blend(square: np.ndarray, heat: np.ndarray) -> Image.Image:
    base = np.dstack([square / 255.0] * 3)
    a = heat[..., 3:4]
    rgb = base * (1 - a) + heat[..., :3] * a
    return Image.fromarray((rgb * 255).astype(np.uint8))


def png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def analyse(data: bytes, cam_label: str | None = None, top_k: int = 6) -> Result:
    model = load_model()
    gray = read_grayscale(data)
    square = center_crop(gray)
    display_side = min(square.shape[0], 900)
    display = np.asarray(Image.fromarray(square).resize((display_side, display_side), Image.BILINEAR))

    x = to_tensor(square)
    feats, scores = forward_with_features(model, x)
    labels = [p for p in model.pathologies if p]
    idx = {p: i for i, p in enumerate(model.pathologies) if p}
    values = scores[0].detach().numpy()
    ranked = sorted(((p, float(values[idx[p]])) for p in labels), key=lambda t: -t[1])
    target = cam_label if cam_label in idx else ranked[0][0]

    cam = grad_cam(feats, scores[0, idx[target]])
    overlay = blend(display, colorize(cam, display_side))
    return Result(
        findings=tuple(Finding(label=p, score=round(s, 3)) for p, s in ranked[:top_k]),
        cam_label=target,
        overlay_png=png_bytes(overlay),
        image_png=png_bytes(Image.fromarray(display)),
    )


def all_labels() -> list[str]:
    return [p for p in load_model().pathologies if p]
