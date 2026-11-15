"""Datasets of user-uploaded FITS images, stored in data/uploads/<dataset_id>/ (gitignored).

Nothing about targets is built in. Original files are kept exactly as uploaded. Everything else is worked out
when needed from the file headers (sky coordinates, date, band) and the dataset's settings:

  centre : RA/Dec the user wants to look at. Can be set, changed or cleared at any time.
  crop   : window size in pixels used for big images (e.g. a full 2048x2048 WISE tile).

Small images (up to MAX_SIDE pixels) are shown whole. Big images are cropped around the centre, so they need one.
Each file has a status: ok | needs_centre (big image, no centre set) | outside (does not cover the centre).
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
MAX_SIDE = 256       # images bigger than this (pixels) are cropped
DEFAULT_CROP = 200   # default crop window (pixels)
VIEW_PX = 600        # target on-screen size of a frame


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


def _check_centre(ra, dec):
    if not (-360 <= ra <= 360) or not (-90 <= dec <= 90):
        raise UploadError("RA must be between 0 and 360 and Dec between -90 and 90 (degrees)")
    return [float(ra % 360), float(dec)]


def create_dataset(name: str, ra=None, dec=None) -> dict:
    name = name.strip() or "dataset"
    ds_id = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:30] + "-" + uuid.uuid4().hex[:6]
    d = ROOT / ds_id
    d.mkdir(parents=True)
    has = ra is not None and dec is not None
    meta = {"id": ds_id, "name": name, "created": time.time(),
            "centre": _check_centre(ra, dec) if has else None, "crop": DEFAULT_CROP}
    (d / "meta.json").write_text(json.dumps(meta))
    return meta


def get_meta(ds_id: str) -> dict:
    meta = json.loads((_dir(ds_id) / "meta.json").read_text())
    meta.setdefault("crop", DEFAULT_CROP)
    return meta


def update_dataset(ds_id: str, name=None, ra=None, dec=None, clear_centre=False, crop=None) -> dict:
    """Change name / centre / crop. clear_centre=True removes the centre."""
    meta = get_meta(ds_id)
    if name is not None and name.strip():
        meta["name"] = name.strip()
    if clear_centre:
        meta["centre"] = None
    elif ra is not None or dec is not None:
        if ra is None or dec is None:
            raise UploadError("give both RA and Dec")
        meta["centre"] = _check_centre(ra, dec)
    if crop is not None:
        if not 20 <= crop <= 1000:
            raise UploadError("window size must be between 20 and 1000 pixels")
        meta["crop"] = int(crop)
    (_dir(ds_id) / "meta.json").write_text(json.dumps(meta))
    return meta


def delete_dataset(ds_id: str):
    d = _dir(ds_id)
    for f in d.iterdir():
        f.unlink()
    d.rmdir()


# ---------- reading headers ----------
def _image_hdu(hl):
    names = [h.name for h in hl]
    order = ([names.index("IMAGE")] if "IMAGE" in names else []) + list(range(len(hl)))
    for i in order:
        h = hl[i]
        if not isinstance(h, (fits.PrimaryHDU, fits.ImageHDU, fits.CompImageHDU)):
            continue
        if h.header.get("NAXIS") == 2 and min(h.header["NAXIS1"], h.header["NAXIS2"]) > 8:
            return i
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
    if "BANDNAME" in hdr:
        return str(hdr["BANDNAME"])
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


def _inspect(source, filename):
    """Read headers only. Returns dict(hdu, mjd, band, shape, wcs). Raises UploadError with a helpful reason."""
    try:
        hl = fits.open(source, memmap=True)
    except Exception:
        raise UploadError("not a readable FITS file")
    with hl:
        i = _image_hdu(hl)
        hdr = hl[i].header
        try:
            wcs = WCS(hdr)
        except Exception:
            raise UploadError("could not read sky coordinates (WCS) from the header")
        if not wcs.has_celestial:
            raise UploadError("no sky coordinates (WCS) in the header, so I cannot track positions")
        return {"hdu": i, "mjd": _mjd(hdr), "band": _band(hdr, filename), "wcs": wcs.celestial,
                "shape": (int(hdr["NAXIS2"]), int(hdr["NAXIS1"]))}


@lru_cache(maxsize=4096)
def _info(path: str, mtime: float):
    return _inspect(path, Path(path).name)


def _orig_name(fname: str):
    m = re.fullmatch(r"\d{4}_(.+)", fname)
    return m.group(1) if m else fname


def add_file(ds_id: str, data: bytes, filename: str) -> dict:
    """Validate and store one FITS file (kept exactly as uploaded). Raises UploadError."""
    d = _dir(ds_id)
    info = _inspect(io.BytesIO(data), filename)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(filename).name)
    if any(_orig_name(f.name) == safe for f in d.glob("*.fits")):
        raise UploadError("a file with this name is already in the dataset")
    k = len(list(d.glob("*.fits")))
    while (d / f"{k:04d}_{safe}").exists():
        k += 1
    (d / f"{k:04d}_{safe}").write_bytes(data)
    return {"file": f"{k:04d}_{safe}", "band": info["band"], "mjd": info["mjd"],
            "date": Time(info["mjd"], format="mjd").isot[:19], "size": list(info["shape"][::-1])}


def remove_file(ds_id: str, file: str):
    if Path(file).name != file or not file.endswith(".fits"):
        raise UploadError("bad file name")
    p = _dir(ds_id) / file
    if not p.exists():
        raise UploadError("file not found")
    p.unlink()


# ---------- what is usable, given the centre ----------
def _window(info, centre, crop):
    """Returns (status, window) where window = (x0, y0, w, h) in pixels or None for the whole image."""
    ny, nx = info["shape"]
    big = max(nx, ny) > MAX_SIDE
    if centre is None:
        return ("needs_centre", None) if big else ("ok", None)
    px, py = (float(v) for v in info["wcs"].world_to_pixel_values(*centre))
    if not (0 <= px < nx and 0 <= py < ny):
        return "outside", None
    if not big:
        return "ok", None
    w, h = min(crop, nx), min(crop, ny)
    x0 = int(np.clip(round(px) - w // 2, 0, nx - w))
    y0 = int(np.clip(round(py) - h // 2, 0, ny - h))
    return "ok", (x0, y0, w, h)


def _scan(ds_id: str):
    """All files with status. Returns (meta, effective_centre, auto_centre, files)."""
    d, meta = _dir(ds_id), get_meta(ds_id)
    files = []
    for f in sorted(d.glob("*.fits")):
        try:
            files.append((f, _info(str(f), f.stat().st_mtime)))
        except UploadError as e:
            files.append((f, {"error": str(e)}))
    good = sorted([x for x in files if "error" not in x[1]], key=lambda x: x[1]["mjd"])
    centre, auto = meta["centre"], False
    if centre is None:                      # no centre set: use the middle of the first small image
        for f, i in good:
            if max(i["shape"]) <= MAX_SIDE:
                ny, nx = i["shape"]
                c = i["wcs"].pixel_to_world_values((nx - 1) / 2, (ny - 1) / 2)
                centre, auto = [float(c[0]), float(c[1])], True
                break
    out = []
    for f, i in files:
        if "error" in i:
            out.append({"file": f.name, "orig": _orig_name(f.name), "status": "error", "error": i["error"]})
            continue
        status, win = _window(i, centre, meta["crop"])
        ny, nx = i["shape"]
        vh, vw = (win[3], win[2]) if win else (ny, nx)
        scale = max(1, round(VIEW_PX / max(vh, vw)))
        out.append({"file": f.name, "orig": _orig_name(f.name), "mjd": i["mjd"], "band": i["band"],
                    "date": Time(i["mjd"], format="mjd").isot[:19], "status": status, "window": win,
                    "scale": scale, "width": vw * scale, "height": vh * scale,
                    "shape": [nx, ny]})
    out.sort(key=lambda x: x.get("mjd", 0))
    return meta, centre, auto, out


def summary(ds_id: str) -> dict:
    meta, centre, auto, files = _scan(ds_id)
    bands = {}
    for f in files:
        if f["status"] == "ok":
            bands[f["band"]] = bands.get(f["band"], 0) + 1
    count = lambda s: sum(1 for f in files if f["status"] == s)
    return {**meta, "effective_centre": centre, "centre_is_auto": auto, "n_files": len(files),
            "n_ok": count("ok"), "n_needs_centre": count("needs_centre"), "n_outside": count("outside"),
            "n_error": count("error"), "bands": bands}


def list_datasets():
    out = [summary(p.parent.name) for p in ROOT.glob("*/meta.json")] if ROOT.exists() else []
    return sorted(out, key=lambda m: -m["created"])


def list_files(ds_id: str):
    """Every stored file with its status (for the file table)."""
    return [{k: v for k, v in f.items() if k != "window"} for f in _scan(ds_id)[3]]


def list_frames(ds_id: str, band=None):
    """Usable frames, oldest first."""
    return [{k: v for k, v in f.items() if k != "window"} for f in _scan(ds_id)[3]
            if f["status"] == "ok" and (not band or f["band"] == band)]


@lru_cache(maxsize=256)
def _image(path: str, mtime: float, window):
    """(image, wcs) for one file, cropped to window if given. Only the needed rows are read from disk."""
    info = _info(path, mtime)
    with fits.open(path, memmap=True) as hl:
        sec = hl[info["hdu"]].section
        if window:
            x0, y0, w, h = window
            img = np.array(sec[y0:y0 + h, x0:x0 + w], dtype="f4")
            wcs = info["wcs"].slice((slice(y0, y0 + h), slice(x0, x0 + w)))
        else:
            img = np.array(hl[info["hdu"]].data, dtype="f4")
            wcs = info["wcs"]
    return img, wcs


def _frames(ds_id: str, band=None):
    d = _dir(ds_id)
    out = []
    for f in _scan(ds_id)[3]:
        if f["status"] == "ok" and (not band or f["band"] == band):
            p = d / f["file"]
            out.append((f, *_image(str(p), p.stat().st_mtime, f["window"])))
    return out


def load_frames(ds_id: str, band=None):
    return [Frame(f["mjd"], f["date"], f["band"], img.astype(float), wcs) for f, img, wcs in _frames(ds_id, band)]


def effective_centre(ds_id: str):
    return _scan(ds_id)[1]


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


@lru_cache(maxsize=512)
def _render_cached(path: str, mtime: float, window, scale):
    img, _ = _image(path, mtime, window)
    return _png((_stretch(img) * 255).astype(np.uint8), scale)


def render_frame(ds_id: str, file: str) -> bytes:
    if Path(file).name != file:
        raise UploadError("bad file name")
    for f in _scan(ds_id)[3]:
        if f["file"] == file:
            if f["status"] != "ok":
                raise UploadError("this image is not usable with the current centre")
            p = _dir(ds_id) / file
            return _render_cached(str(p), p.stat().st_mtime, f["window"], f["scale"])
    raise UploadError("file not found")


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


def render_composite(frames) -> bytes:
    """One picture of the whole time span: each frame gets a colour by date (blue = oldest, red = newest).
    Stars that do not move add up to white; a mover leaves a trail of colours."""
    import colorsys
    stack = _aligned(frames)
    n = len(stack)
    rgb = np.zeros(stack.shape[1:] + (3,))
    for i, a in enumerate(stack):
        s = _stretch(a - np.median(a), 20, 99.7)
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
