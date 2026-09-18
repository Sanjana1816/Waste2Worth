"""Synthetic product photos for seed data and tests.

Draws an item (with grain so it isn't flagged as blurry) in the middle of a white sheet,
then applies a lighting tint and exposure, like a real phone photo under a warm bulb or in shade.
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image

PAPER = (246, 246, 243)
WARM_BULB = (1.0, 0.86, 0.66)
COOL_SHADE = (0.86, 0.93, 1.05)
DAYLIGHT = (1.0, 1.0, 1.0)


def photo(item_rgb, tint=DAYLIGHT, exposure=1.0, size=(1200, 900), paper=True, grain=7.0,
          blur=False, seed=0) -> bytes:
    rng = np.random.default_rng(seed)
    w, h = size
    img = np.empty((h, w, 3), dtype=np.float32)
    img[:] = PAPER if paper else (90, 80, 70)
    # item fills the centre ~50% of the frame, with tile grout lines
    y0, y1, x0, x1 = int(h * 0.25), int(h * 0.75), int(w * 0.25), int(w * 0.75)
    img[y0:y1, x0:x1] = item_rgb
    img[y0:y1:60, x0:x1] *= 0.8
    img[y0:y1, x0:x1:60] *= 0.8
    img += rng.normal(0, grain, img.shape)
    img *= np.array(tint, dtype=np.float32) * exposure
    arr = np.clip(img, 0, 255).astype(np.uint8)
    pil = Image.fromarray(arr)
    if blur:
        from PIL import ImageFilter
        pil = pil.filter(ImageFilter.GaussianBlur(6))
    buf = io.BytesIO()
    pil.save(buf, format="JPEG", quality=92)
    return buf.getvalue()
