"""Datasets of user-uploaded FITS images, stored in data/uploads/<dataset_id>/ (gitignored).

Nothing about targets is built in. For every uploaded file we read from the FITS header:
  - the sky coordinates (WCS)            - the observation date (MJD, or a date string)
  - the band / detector (for grouping)
Large images (e.g. a full 2048x2048 WISE tile) are cropped around the dataset centre, which the user gives
as RA/Dec; small cutouts are kept whole.
"""
import io
import json
import re
import time
import uuid
from functools import lru_cache
from pathlib import Path

import numpy as np
from astropy.io import fits
from astropy.time import Time
from astropy.wcs import WCS
from PIL import Image
from scipy import ndimage

from .movers import Frame

ROOT = Path(__file__).resolve().parent.parent / "data" / "uploads"
MAX_SIDE = 256   # images bigger than this (in pixels) are cropped
CROP = 200       # size of the crop
VIEW_PX = 600    # target on-screen size of a frame


class UploadError(ValueError):
    """Message is shown to the user, so keep it helpful."""


# ---------- datasets ----------
def _dir(ds_id: str) -> Path:
    if not re.fullmatch(r"[a-z0-9_-]+", ds_id):
        raise UploadError("bad dataset id")
    d = ROOT / ds_id
    if not d.is_dir():
        raise UploadError("dataset not found")
    return d


def create_dataset(name: str, ra=None, dec=None) -> dict:
    name = name.strip() or "dataset"
    ds_id = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:30] + "-" + uuid.uuid4().hex[:6]
    d = ROOT / ds_id
    d.mkdir(parents=True)
    meta = {"id": ds_id, "name": name, "created": time.time(),
            "centre": [float(ra), float(dec)] if ra not in (None, "") and dec not in (None, "") else None}
    (d / "meta.json").write_text(json.dumps(meta))
    return meta


def get_meta(ds_id: str) -> dict:
    return json.loads((_dir(ds_id) / "meta.json").read_text())


def _save_meta(ds_id: str, meta: dict):
    (_dir(ds_id) / "meta.json").write_text(json.dumps(meta))


def delete_dataset(ds_id: str):
    d = _dir(ds_id)
    for f in d.iterdir():
        f.unlink()
    d.rmdir()


def list_datasets():
    out = []
    for d in sorted(ROOT.glob("*/meta.json")) if ROOT.exists() else []:
        meta = json.loads(d.read_text())
        frames = list_frames(meta["id"])
        bands = {}
        for f in frames:
            bands[f["band"]] = bands.get(f["band"], 0) + 1
        out.append({**meta, "n_frames": len(frames), "bands": bands})
    return sorted(out, key=lambda m: -m["created"])


# ---------- reading headers ----------
def _image_hdu(hl):
    names = [h.name for h in hl]
    order = ([names.index("IMAGE")] if "IMAGE" in names else []) + list(range(len(hl)))
    for i in order:
        h = hl[i]
        if getattr(h, "data", None) is not None and h.data.ndim == 2 and min(h.data.shape) > 8:
            return h
    raise UploadError("no 2D image found in this FITS file")


def _mjd(hdr):
    for k in ("MJD-OBS", "MJD_OBS", "MJDMEAN"):
        if k in hdr:
            return float(hdr[k])
    if "MJDMIN" in hdr and "MJDMAX" in hdr:
        return (float(hdr["MJDMIN"]) + float(hdr["MJDMAX"])) / 2
    for k in ("DATE-OBS", "DATE_OBS", "DATE-AVG", "DATE"):
        if k in hdr:
            try:
                return float(Time(str(hdr[k]).strip(), format="isot").mjd)
            except ValueError:
                try:
                    return float(Time(str(hdr[k]).strip()).mjd)
                except ValueError:
                    pass
    raise UploadError("no observation date in the header (looked for MJD-OBS, MJDMEAN, MJDMIN/MJDMAX, DATE-OBS)")


def _band(hdr, filename):
    if "DETECTOR" in hdr:
        return f"D{hdr['DETECTOR']}"
    if "BAND" in hdr:
        b = str(hdr["BAND"]).strip()
        return f"W{b}" if b.isdigit() else b
    if "FILTER" in hdr:
        return str(hdr["FILTER"]).strip()
    m = re.search(r"[_-]w(\d)[_.-]", filename.lower())
    if m:
        return f"W{m.group(1)}"
    m = re.search(r"\dd(\d)_spx", filename.lower())
    if m:
        return f"D{m.group(1)}"
    return "default"


def add_file(ds_id: str, data: bytes, filename: str) -> dict:
    """Validate + store one FITS file. Returns frame info or raises UploadError."""
    d = _dir(ds_id)
    meta = get_meta(ds_id)
    try:
        hl = fits.open(io.BytesIO(data))
    except Exception:
        raise UploadError("not a readable FITS file")
    with hl:
        hdu = _image_hdu(hl)
        hdr, img = hdu.header.copy(), hdu.data.astype("f4")
    try:
        wcs = WCS(hdr)
    except Exception:
        raise UploadError("could not read sky coordinates (WCS) from the header")
    if not wcs.has_celestial:
        raise UploadError("no sky coordinates (WCS) in the header, so I cannot track positions")
    wcs = wcs.celestial
    mjd, band = _mjd(hdr), _band(hdr, filename)
    ny, nx = img.shape
    big = max(nx, ny) > MAX_SIDE

    if meta["centre"] is None:
        if big:
            raise UploadError(f"this image is large ({nx}x{ny}). Enter the target RA/Dec when creating the dataset "
                              "so I can crop around it.")
        c = wcs.pixel_to_world_values((nx - 1) / 2, (ny - 1) / 2)
        meta["centre"] = [float(c[0]), float(c[1])]
        _save_meta(ds_id, meta)
    px, py = (float(v) for v in wcs.world_to_pixel_values(*meta["centre"]))
    if not (0 <= px < nx and 0 <= py < ny):
        raise UploadError("this image does not cover the dataset centre "
                          f"(RA {meta['centre'][0]:.4f}, Dec {meta['centre'][1]:.4f})")
    if big:
        x0 = int(np.clip(round(px) - CROP // 2, 0, nx - CROP))
        y0 = int(np.clip(round(py) - CROP // 2, 0, ny - CROP))
        img = img[y0:y0 + CROP, x0:x0 + CROP]
        wcs = wcs.slice((slice(y0, y0 + CROP), slice(x0, x0 + CROP)))

    for f in list_frames(ds_id):
        if f["orig"] == filename:
            raise UploadError("a file with this name is already in the dataset")
    k = len(list(d.glob("f*.fits")))
    h = wcs.to_header()
    h["MJD-OBS"], h["BANDNAME"], h["ORIGNAME"] = mjd, band, filename[:60]
    fname = f"f{k:04d}.fits"
    fits.PrimaryHDU(img, h).writeto(d / fname, overwrite=True)
    _meta_cached.cache_clear()
    return {"file": fname, "band": band, "mjd": mjd, "date": Time(mjd, format="mjd").isot[:19],
            "size": list(img.shape[::-1]), "cropped": big}


@lru_cache(maxsize=4096)
def _meta_cached(path: str, mtime: float):
    h = fits.getheader(path)
    return {"mjd": float(h["MJD-OBS"]), "band": h["BANDNAME"], "orig": h.get("ORIGNAME", ""),
            "shape": (int(h["NAXIS2"]), int(h["NAXIS1"]))}


def list_frames(ds_id: str, band=None):
    out = []
    for f in sorted(_dir(ds_id).glob("f*.fits")):
        m = _meta_cached(str(f), f.stat().st_mtime)
        if band and m["band"] != band:
            continue
        scale = max(1, round(VIEW_PX / max(m["shape"])))
        out.append({"file": f.name, "mjd": m["mjd"], "band": m["band"], "orig": m["orig"],
                    "date": Time(m["mjd"], format="mjd").isot[:19], "scale": scale,
                    "width": m["shape"][1] * scale, "height": m["shape"][0] * scale})
    return sorted(out, key=lambda x: x["mjd"])


def load_frames(ds_id: str, band=None):
    out = []
    for it in list_frames(ds_id, band):
        with fits.open(_dir(ds_id) / it["file"]) as hl:
            out.append(Frame(it["mjd"], it["date"], it["band"], hl[0].data.astype(float), WCS(hl[0].header)))
    return out


# ---------- pictures ----------
def _stretch(img, lo_pct=5, hi_pct=99.7):
    img = np.nan_to_num(img, nan=np.nanmedian(img))
    lo, hi = np.percentile(img, [lo_pct, hi_pct])
    return np.arcsinh(np.clip((img - lo) / max(hi - lo, 1e-9), 0, 1) * 10) / np.arcsinh(10)


def _png(arr, scale):
    pic = Image.fromarray(arr)
    pic = pic.resize((arr.shape[1] * scale, arr.shape[0] * scale), Image.NEAREST)
    pic = pic.transpose(Image.FLIP_TOP_BOTTOM)  # FITS origin is bottom-left
    buf = io.BytesIO()
    pic.save(buf, "PNG")
    return buf.getvalue()


def render_frame(ds_id: str, file: str) -> bytes:
    if Path(file).name != file:
        raise UploadError("bad file name")
    with fits.open(_dir(ds_id) / file) as hl:
        img = hl[0].data.astype(float)
    scale = max(1, round(VIEW_PX / max(img.shape)))
    return _png((_stretch(img) * 255).astype(np.uint8), scale)


def _aligned(frames):
    """Resample every frame onto the first frame's pixel grid using the WCS (bilinear)."""
    ref = frames[0]
    ny, nx = ref.image.shape
    yy, xx = np.mgrid[0:ny, 0:nx]
    ra, dec = ref.wcs.pixel_to_world_values(xx, yy)
    stack = []
    for f in frames:
        fx, fy = f.wcs.world_to_pixel_values(ra, dec)
        img = np.nan_to_num(f.image, nan=np.nanmedian(f.image))
        stack.append(ndimage.map_coordinates(img, [fy, fx], order=1, mode="nearest"))
    return np.array(stack)


def _subtract_sky(a):
    return a - np.median(a)


def render_composite(frames) -> bytes:
    """One picture of the whole time span: each frame gets a colour by date (blue = oldest, red = newest).
    Stars that do not move add up to white; a mover leaves a trail of colours."""
    import colorsys
    stack = _aligned(frames)
    n = len(stack)
    rgb = np.zeros(stack.shape[1:] + (3,))
    for i, a in enumerate(stack):
        s = _stretch(_subtract_sky(a), 20, 99.7)
        col = np.array(colorsys.hsv_to_rgb(0.66 * (1 - i / max(n - 1, 1)), 1.0, 1.0))
        rgb = np.maximum(rgb, s[..., None] * col)
    scale = max(1, round(VIEW_PX / max(rgb.shape[:2])))
    return _png((rgb * 255).astype(np.uint8), scale)


def render_difference(frames) -> bytes:
    """Average of the newest third minus average of the oldest third. Stars cancel out; a mover shows as
    a blue spot where it WAS and a red spot where it IS NOW."""
    stack = _aligned(frames)
    k = max(1, len(stack) // 3)
    diff = np.mean(stack[-k:], axis=0) - np.mean(stack[:k], axis=0)
    sig = 1.4826 * np.median(np.abs(diff - np.median(diff))) or 1.0
    z = np.clip((diff - np.median(diff)) / (5 * sig), -1, 1)
    rgb = np.zeros(z.shape + (3,))
    rgb[..., 0] = np.clip(z, 0, 1)                       # red = brighter now
    rgb[..., 2] = np.clip(-z, 0, 1)                      # blue = brighter before
    rgb[..., 1] = 0.25 * np.clip(np.abs(z), 0, 1)
    scale = max(1, round(VIEW_PX / max(rgb.shape[:2])))
    return _png((rgb * 255).astype(np.uint8), scale)
