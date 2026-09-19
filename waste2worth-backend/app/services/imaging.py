"""Photo quality gates and lighting-corrected colour measurement.

Lighting problem: the same tile looks warmer under a tungsten bulb, bluer in shade and darker
indoors, so raw pixel colours from two sellers can't be compared.

Fix: the "colour_reference" shot has the item placed in the middle of a plain white A4 sheet.
The sheet (visible in the outer ring of the frame) is a known neutral white, so we compute
per-channel gains that turn the sheet into the same neutral white (240,240,240) in every photo.
That removes both the colour cast and the exposure difference, and the item's colour in the
centre of the frame becomes comparable across sellers (CIELAB delta-E).
Other shots are only quality-checked; their colour is stored raw and marked as not balanced.
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image, ImageOps

from app.config import settings

WHITE_TARGET = 240.0
LUMA = np.array([0.299, 0.587, 0.114], dtype=np.float32)

ISSUE_TEXT = {
    "too_small": "The photo is too small. Retake it closer, or at full camera resolution.",
    "blurry": "The photo is blurry. Hold steady, tap to focus and retake.",
    "too_dark": "The photo is too dark. Move to daylight or near a window.",
    "too_bright": "The photo is washed out. Avoid direct sun and turn the flash off.",
    "no_white_reference": "We couldn't find the white sheet. Put the item in the middle of a plain white A4 "
                          "sheet and fill the frame so the paper shows all around it.",
    "white_clipped": "The white sheet is overexposed, so we can't read the true colour. Step out of direct "
                     "light or tap the paper to lower the exposure, then retake.",
    "strong_color_cast": "The lighting is very coloured. Shoot in daylight so the colour can be corrected reliably.",
    "unreadable": "We couldn't read this file as an image. Upload a JPG or PNG.",
}


def open_image(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)
    return img.convert("RGB")


def _small(img: Image.Image, size: int = 512) -> np.ndarray:
    s = img.copy()
    s.thumbnail((size, size))
    return np.asarray(s, dtype=np.float32)


def blur_score(gray: np.ndarray) -> float:
    """Variance of the Laplacian: low = blurry."""
    lap = 4 * gray[1:-1, 1:-1] - gray[:-2, 1:-1] - gray[2:, 1:-1] - gray[1:-1, :-2] - gray[1:-1, 2:]
    return float(lap.var())


# ---------- colour maths ----------

def _srgb_to_linear(c: np.ndarray) -> np.ndarray:
    c = c / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def rgb_to_lab(rgb) -> list[float]:
    lin = _srgb_to_linear(np.asarray(rgb, dtype=np.float64))
    m = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = m @ lin / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > (6 / 29) ** 3, np.cbrt(xyz), xyz / (3 * (6 / 29) ** 2) + 4 / 29)
    L = 116 * f[1] - 16
    a = 500 * (f[0] - f[1])
    b = 200 * (f[1] - f[2])
    return [round(float(L), 2), round(float(a), 2), round(float(b), 2)]


def delta_e(lab1, lab2) -> float:
    """CIE76 colour difference. ~2 is barely visible, >6 is an obvious shade difference."""
    return round(float(np.linalg.norm(np.asarray(lab1) - np.asarray(lab2))), 2)


def to_hex(rgb) -> str:
    r, g, b = (int(round(max(0, min(255, v)))) for v in rgb)
    return f"#{r:02X}{g:02X}{b:02X}"


def dominant_color(pixels: np.ndarray, k: int = 3, iters: int = 10) -> np.ndarray:
    """Tiny deterministic k-means; returns the centre of the largest cluster."""
    px = pixels.reshape(-1, 3)
    if len(px) > 4000:
        px = px[:: len(px) // 4000]
    lum = px @ LUMA
    order = np.argsort(lum)
    centres = np.stack([px[order[int(q * (len(px) - 1))]] for q in np.linspace(0.2, 0.8, k)])
    for _ in range(iters):
        labels = np.argmin(((px[:, None, :] - centres[None]) ** 2).sum(-1), axis=1)
        for j in range(k):
            if np.any(labels == j):
                centres[j] = px[labels == j].mean(0)
    counts = np.bincount(labels, minlength=k)
    return centres[int(np.argmax(counts))]


def white_reference_gains(arr: np.ndarray) -> tuple[np.ndarray | None, str | None]:
    """Estimate per-channel gains from the white sheet in the outer ring of the frame."""
    h, w, _ = arr.shape
    bh, bw = max(1, int(h * 0.15)), max(1, int(w * 0.15))
    ring = np.concatenate([arr[:bh].reshape(-1, 3), arr[-bh:].reshape(-1, 3),
                           arr[bh:-bh, :bw].reshape(-1, 3), arr[bh:-bh, -bw:].reshape(-1, 3)])
    lum = ring @ LUMA
    bright = ring[lum >= np.percentile(lum, 50)]
    # A clipped channel has lost the information we need, so the correction would be wrong.
    if (bright.max(1) >= 254).mean() > 0.2:
        return None, "white_clipped"
    paper = bright[bright.max(1) < 254]
    if len(paper) < 0.1 * len(ring):
        return None, "no_white_reference"
    mean = paper.mean(0)
    if mean @ LUMA < 90:
        return None, "no_white_reference"
    chroma = (mean.max() - mean.min()) / mean.max()
    if chroma > 0.45:
        return None, "strong_color_cast"
    return WHITE_TARGET / mean, None


def analyze(img: Image.Image, shot_type: str) -> dict:
    w, h = img.size
    arr = _small(img)
    gray = arr @ LUMA
    issues: list[str] = []

    blur = blur_score(gray)
    brightness = float(gray.mean())
    if min(w, h) < settings.min_image_short_side:
        issues.append("too_small")
    if blur < settings.blur_threshold:
        issues.append("blurry")
    # Judge exposure by clipping, not mean brightness: a white tile on white paper is bright but fine.
    blown_out = float((arr.min(axis=2) >= 252).mean())
    if brightness < 55:
        issues.append("too_dark")
    elif blown_out > 0.30:
        issues.append("too_bright")

    white_balanced = False
    ah, aw, _ = arr.shape
    centre = arr[int(ah * 0.3): int(ah * 0.7), int(aw * 0.3): int(aw * 0.7)]
    if shot_type == "color_reference":
        gains, problem = white_reference_gains(arr)
        if problem:
            issues.append(problem)
            rgb = dominant_color(centre)
        else:
            rgb = dominant_color(np.clip(centre * gains, 0, 255))
            white_balanced = True
    else:
        rgb = dominant_color(centre)

    return {
        "width": w, "height": h,
        "blur_score": round(blur, 1), "brightness": round(brightness, 1),
        "issues": issues, "quality_ok": not issues,
        "color_hex": to_hex(rgb), "color_lab": rgb_to_lab(rgb),
        "white_balanced": white_balanced,
    }


def describe_issues(issues: list[str]) -> list[str]:
    return [ISSUE_TEXT.get(i, i) for i in issues]
