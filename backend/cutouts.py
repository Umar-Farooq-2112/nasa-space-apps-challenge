"""Read cached cutouts and render them as PNG. Two data sources, same folder naming <ra>_<dec>:
  spherex : data/raw/cutouts/        (SPHEREx, from IRSA; detectors D1-D6)
  unwise  : data/raw/unwise_epochs/  (WISE/NEOWISE time-resolved epochs; band W2)
"""
import io
import re
from functools import lru_cache
from pathlib import Path

import numpy as np
from astropy.io import fits
from astropy.time import Time
from astropy.wcs import WCS
from PIL import Image

from .movers import Frame

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
SOURCES = {"spherex": RAW / "cutouts", "unwise": RAW / "unwise_epochs"}
SCALE = 6  # upscale tiny images so they are visible


def find_dirs(ra: float, dec: float, tol: float = 0.05):
    """[(source, folder)] cached around (ra, dec)."""
    found = []
    for src, root in SOURCES.items():
        best, best_d = None, tol
        for d in root.glob("*_*") if root.exists() else []:
            try:
                r, de = (float(x) for x in d.name.split("_"))
            except ValueError:
                continue
            dist = max(abs(r - ra) * np.cos(np.radians(dec)), abs(de - dec))
            if dist < best_d:
                best, best_d = d, dist
        if best is not None:
            found.append((src, best))
    return found


def _read(path: Path, source: str):
    """(image, header) for one cutout file."""
    with fits.open(path) as h:
        if source == "spherex":
            return h["IMAGE"].data.astype(float), h["IMAGE"].header.copy()
        return h[0].data.astype(float), h[0].header.copy()


@lru_cache(maxsize=1024)
def _meta(path: str, source: str):
    p = Path(path)
    _, hd = _read(p, source)
    if source == "spherex":
        return {"date": hd["DATE-OBS"], "mjd": hd["MJD-OBS"], "detector": f"D{hd['DETECTOR']}"}
    mjd = (hd["MJDMIN"] + hd["MJDMAX"]) / 2
    band = re.search(r"_w(\d)", p.name).group(1)
    return {"date": Time(mjd, format="mjd").isot, "mjd": mjd, "detector": f"W{band}"}


def list_frames(ra: float, dec: float, detector: str = "all"):
    dirs = find_dirs(ra, dec)
    if not dirs:
        return None
    out = []
    for src, folder in dirs:
        for f in folder.glob("*.fits"):
            m = _meta(str(f), src)
            if detector == "all" or m["detector"] == detector:
                out.append({**m, "source": src, "file": f.name, "folder": folder.name})
    return sorted(out, key=lambda x: x["mjd"])


@lru_cache(maxsize=1024)
def render_png(source: str, folder: str, file: str) -> bytes:
    img, _ = _read(SOURCES[source] / folder / file, source)
    img = np.nan_to_num(img, nan=np.nanmedian(img))
    lo, hi = np.percentile(img, [5, 99.7] if source == "unwise" else [1, 99.5])  # percentile stretch
    s = np.arcsinh(np.clip((img - lo) / (hi - lo), 0, 1) * 10) / np.arcsinh(10)
    pic = Image.fromarray((s * 255).astype(np.uint8))
    pic = pic.resize((s.shape[1] * SCALE, s.shape[0] * SCALE), Image.NEAREST)
    pic = pic.transpose(Image.FLIP_TOP_BOTTOM)  # FITS origin is bottom-left
    buf = io.BytesIO()
    pic.save(buf, "PNG")
    return buf.getvalue()


def load_frames(ra: float, dec: float, detector: str = "all"):
    """Frame objects (image + WCS) for the movers code, oldest first."""
    out = []
    for it in list_frames(ra, dec, detector) or []:
        img, hd = _read(SOURCES[it["source"]] / it["folder"] / it["file"], it["source"])
        out.append(Frame(it["mjd"], it["date"], it["detector"], img, WCS(hd)))
    return out
