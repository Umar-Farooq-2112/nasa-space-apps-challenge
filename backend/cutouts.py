"""Read cached SPHEREx cutouts (data/raw/cutouts/<ra>_<dec>_<fov>/) and render them as PNG."""
import io
import logging
import os
import shutil
import warnings
from functools import lru_cache
from pathlib import Path

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from PIL import Image
from scipy import ndimage

from .movers import PIX_ARCSEC, Frame

ROOT = Path(__file__).resolve().parent.parent
ON_VERCEL = bool(os.environ.get("VERCEL"))   # serverless: the code folder is read-only, only /tmp is writable
CACHE = Path("/tmp/charon/cutouts") if ON_VERCEL else ROOT / "data" / "raw" / "cutouts_v2"   # v2: cutouts are 1.5x fov
SEED = ROOT / "seed" / "cutouts"   # the demo targets, shipped with the code so they open instantly
if ON_VERCEL and SEED.exists() and not CACHE.exists():
    shutil.copytree(SEED, CACHE, dirs_exist_ok=True)
SCALE = 12  # upscale tiny (~59x59 px for 0.1 deg) images, smoothly (bicubic), so they look sharp on screen
RENDER_VERSION = 8  # bump when render_png changes: browsers cache frame PNGs for a day


def folder_for(ra: float, dec: float, fov: float) -> Path:
    """Cache folder for one sky spot + field of view. 4 decimals = 0.36 arcsec, far below a 6" pixel."""
    return CACHE / f"{ra:.4f}_{dec:.4f}_{fov:g}"


@lru_cache(maxsize=4096)
def _meta(path: str):
    with fits.open(path) as h:
        hd = h["IMAGE"].header
        return {"date": hd["DATE-OBS"], "mjd": hd["MJD-OBS"], "detector": f"D{hd['DETECTOR']}"}


def list_frames(folder: Path, detector: str):
    out = []
    for f in folder.glob(f"*_{detector}_*.fits"):
        m = _meta(str(f))
        if m["detector"] == detector:
            out.append({**m, "file": f.name, "folder": folder.name})
    return sorted(out, key=lambda x: x["mjd"])


def display_wcs(folder: str) -> WCS:
    """Common grid for every frame of a folder: centred on its ra/dec, north up, east left, SPHEREx pixel size.
    Needed because SPHEREx images are rotated differently each pass (e.g. 21 vs -162 deg)."""
    ra, dec, fov = (float(x) for x in folder.split("_"))
    n = round(fov * 3600 / PIX_ARCSEC)
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = [ra, dec]
    w.wcs.crpix = [(n + 1) / 2, (n + 1) / 2]
    w.wcs.cdelt = [-PIX_ARCSEC / 3600, PIX_ARCSEC / 3600]
    w.pixel_shape = (n, n)
    return w


def to_display(folder: str, image, wcs) -> np.ndarray:
    """Resample one cutout onto the folder's common grid (bilinear, NaN outside the cutout)."""
    grid = display_wcs(folder)
    n = grid.pixel_shape[0]
    yy, xx = np.mgrid[0:n, 0:n]
    px, py = wcs.world_to_pixel_values(*grid.pixel_to_world_values(xx, yy))
    return ndimage.map_coordinates(image, [py, px], order=1, cval=np.nan)


# FLAGS bits 0-11 mark bad pixels (transients/cosmic rays, overflow, non-functional, hot...). Seen on real
# D6 cutouts: every >50-sigma junk pixel had one of them; bit 21 (on ~1/3 of pixels) marks sources, keep those.
# ponytail: chosen from data, not from the SPHEREx flag table; check the Explanatory Supplement if it misbehaves.
BAD_FLAGS = 0xFFF


def clean_image(hdul) -> np.ndarray:
    """IMAGE with flagged bad pixels and NaNs replaced from their neighbours."""
    img = hdul["IMAGE"].data.astype(float)
    if "FLAGS" in hdul:
        img[(hdul["FLAGS"].data.astype(np.int64) & BAD_FLAGS) != 0] = np.nan
    return fill_nan(img)


def fill_nan(a: np.ndarray, rounds: int = 6) -> np.ndarray:
    """Fill masked (NaN) pixels with the mean of their valid neighbours, growing inwards.
    Saturated star cores (NaN ringed by bright pixels) come out bright; bad pixels blend into the sky."""
    a = a.copy()
    for _ in range(rounds):
        bad = np.isnan(a)
        if not bad.any():
            break
        ok = (~bad).astype(float)
        s = ndimage.uniform_filter(np.where(bad, 0.0, a), 3)
        c = ndimage.uniform_filter(ok, 3)
        fill = bad & (c > 0)
        a[fill] = s[fill] / c[fill]
    return np.nan_to_num(a, nan=np.nanmedian(a))


@lru_cache(maxsize=512)
def display_image(folder: str, file: str) -> np.ndarray:
    """Cleaned cutout resampled onto the folder's north-up grid (float, sky-subtracted)."""
    with fits.open(CACHE / folder / file) as h:
        img = to_display(folder, clean_image(h), WCS(h["IMAGE"].header, naxis=2))
    img = np.nan_to_num(img, nan=np.nanmedian(img))   # NaN now only = outside the cutout
    return img - np.median(img)   # remove sky level: frames at different wavelengths/zodi become comparable


@lru_cache(maxsize=32)
def median_image(folder: str, files: tuple) -> np.ndarray:
    """Median of all frames = the static sky. Keyed by the file list, so new downloads refresh it."""
    return np.median([display_image(folder, f) for f in files], axis=0)


@lru_cache(maxsize=1024)
def render_png(folder: str, file: str, ref_files: tuple = (), mode: str = "sky") -> bytes:
    """Frame as PNG.
    mode=diff: frame minus the median of ref_files (static stars vanish, movers show as a bright spot where
    they are now and a dark one where they usually are).
    mode=deep: median of all ref_files, ~3.5x less noise than one image for 20 frames, so faint things show."""
    img = median_image(folder, ref_files) if mode == "deep" else display_image(folder, file)
    sig = 1.4826 * np.median(np.abs(img)) or 1.0
    if mode == "diff":
        d = img - median_image(folder, ref_files)
        s = 0.5 + 0.5 * np.arcsinh(np.clip(d / (4 * sig), -30, 30)) / np.arcsinh(30)   # grey = no change
    else:
        # sky-based stretch: black just below the sky, white well above the noise (percentiles alone blew up
        # the noise in sparse fields like D6, where the top 0.5% of pixels is still just noise)
        lo, hi = -2 * sig, max(np.percentile(img, 99.7), 25 * sig)
        s = np.arcsinh(np.clip((img - lo) / (hi - lo), 0, 1) * 10) / np.arcsinh(10)
    # bicubic upscale of the float image (smooth stars instead of blocky pixels); grid_mode keeps pixel
    # centres where the mover overlay expects them ((px + 0.5) * SCALE)
    s = ndimage.zoom(s, SCALE, order=3, grid_mode=True, mode="nearest")
    pic = Image.fromarray((np.clip(s, 0, 1) * 255).astype(np.uint8))
    pic = pic.transpose(Image.FLIP_TOP_BOTTOM)  # FITS origin is bottom-left; now north is up
    buf = io.BytesIO()
    pic.save(buf, "PNG")
    return buf.getvalue()


def load_frames(folder: Path, detector: str):
    """Frame objects (image + WCS) for the movers code, oldest first."""
    out = []
    for it in list_frames(folder, detector):
        with fits.open(folder / it["file"]) as h:
            out.append(Frame(it["mjd"], it["date"], it["detector"],
                             # NaN fill only, no flag masking: bright star cores carry the same bad-pixel
                             # flags, and filling them shifts centroids so real movers (Barnard's Star) are lost.
                             # Hot pixels jump around between frames, so they never form a track anyway.
                             fill_nan(h["IMAGE"].data.astype(float)), WCS(h["IMAGE"].header, naxis=2),
                             _wave_wcs(h)))
    return out


def _wave_wcs(hdul):
    """Pixel -> wavelength lookup (the WCS-WAVE table), or None if the cutout has none."""
    if "WCS-WAVE" not in hdul:
        return None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        logging.getLogger("astropy").setLevel(logging.ERROR)   # harmless SIP notice on every file
        return WCS(hdul["IMAGE"].header, fobj=hdul, key="W")
