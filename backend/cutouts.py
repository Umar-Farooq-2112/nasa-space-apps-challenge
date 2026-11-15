"""Read cached SPHEREx cutouts (data/raw/cutouts/<ra>_<dec>/) and render them as PNG."""
import io
from functools import lru_cache
from pathlib import Path

import numpy as np
from astropy.io import fits
from PIL import Image

CACHE = Path(__file__).resolve().parent.parent / "data" / "raw" / "cutouts"
SCALE = 6  # upscale tiny 58x59 images so they are visible


def find_dir(ra: float, dec: float, tol: float = 0.05):
    """Cached folder closest to (ra, dec), or None."""
    best, best_d = None, tol
    for d in CACHE.glob("*_*") if CACHE.exists() else []:
        try:
            r, de = (float(x) for x in d.name.split("_"))
        except ValueError:
            continue
        dist = max(abs(r - ra) * np.cos(np.radians(dec)), abs(de - dec))
        if dist < best_d:
            best, best_d = d, dist
    return best


@lru_cache(maxsize=512)
def _meta(path: str):
    with fits.open(path) as h:
        hd = h["IMAGE"].header
        return {"date": hd["DATE-OBS"], "mjd": hd["MJD-OBS"], "detector": f"D{hd['DETECTOR']}"}


def list_frames(ra: float, dec: float, detector: str = "all"):
    folder = find_dir(ra, dec)
    if folder is None:
        return None
    out = []
    for f in folder.glob("*.fits"):
        m = _meta(str(f))
        if detector == "all" or m["detector"] == detector:
            out.append({**m, "file": f.name, "folder": folder.name})
    return sorted(out, key=lambda x: x["mjd"])


@lru_cache(maxsize=512)
def render_png(folder: str, file: str) -> bytes:
    with fits.open(CACHE / folder / file) as h:
        img = h["IMAGE"].data.astype(float)
    img = np.nan_to_num(img, nan=np.nanmedian(img))
    lo, hi = np.percentile(img, [1, 99.5])  # percentile stretch
    s = np.arcsinh(np.clip((img - lo) / (hi - lo), 0, 1) * 10) / np.arcsinh(10)
    pic = Image.fromarray((s * 255).astype(np.uint8))
    pic = pic.resize((s.shape[1] * SCALE, s.shape[0] * SCALE), Image.NEAREST)
    pic = pic.transpose(Image.FLIP_TOP_BOTTOM)  # FITS origin is bottom-left
    buf = io.BytesIO()
    pic.save(buf, "PNG")
    return buf.getvalue()
