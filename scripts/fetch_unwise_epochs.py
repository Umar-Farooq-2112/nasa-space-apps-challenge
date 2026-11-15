"""Download time-resolved unWISE (WISE/NEOWISE) cutouts, one per epoch, using HTTP range requests.
Usage: fetch_unwise_epochs.py RA DEC [SIZE_PIX=100] [BANDS=12]
  Finds the unWISE tile for the position automatically. Pixels are 2.75 arcsec.
Source: NERSC neo8 time-resolved coadds (Aaron Meisner, same data as WiseView).
Saves data/raw/unwise_epochs/<ra>_<dec>/e###_w<band>.fits (small FITS with WCS + MJD range). Gitignored.
"""
import io
import re
import sys
import tarfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import requests
from astropy.io import fits
from astropy.wcs import WCS

ra, dec = float(sys.argv[1]), float(sys.argv[2])
size = int(sys.argv[3]) if len(sys.argv) > 3 else 100
bands = sys.argv[4] if len(sys.argv) > 4 else "12"
BASE = "https://portal.nersc.gov/project/cosmo/temp/ameisner/neo8"
out = Path(f"data/raw/unwise_epochs/{sys.argv[1]}_{sys.argv[2]}")
out.mkdir(parents=True, exist_ok=True)


def get(url, rng=None, tries=4):
    for _ in range(tries):
        try:
            r = requests.get(url, headers={"Range": f"bytes={rng[0]}-{rng[1]}"} if rng else {}, timeout=120)
            if r.status_code in (200, 206, 404):
                return r
        except requests.RequestException:
            pass
        time.sleep(2)
    return None


def resolve_tile():
    """Ask unwise.me for a tiny cutout; the file names in the answer contain the tile name."""
    r = requests.get("https://unwise.me/cutout_fits", timeout=120, params={
        "version": "neo7", "ra": ra, "dec": dec, "size": 5, "bands": "2", "file_img_m": "on"})
    with tarfile.open(fileobj=io.BytesIO(r.content)) as t:
        return re.search(r"unwise-(\d{4}[pm]\d{3})-", t.getnames()[0]).group(1)


def read_header(url):
    """Read FITS header blocks (2880 bytes each) until END."""
    raw = b""
    while True:
        r = get(url, (len(raw), len(raw) + 2880 * 4 - 1))
        if r is None or r.status_code == 404:
            return None, 0
        raw += r.content
        if b"END" + b" " * 77 in raw:
            break
    idx = raw.find(b"END" + b" " * 77)
    return fits.Header.fromstring(raw[:((idx + 80 + 2879) // 2880) * 2880].decode("ascii")), ((idx + 80 + 2879) // 2880) * 2880


def one(args):
    tile, band, e = args
    name = f"e{e:03d}"
    dest = out / f"{name}_w{band}.fits"
    if dest.exists():
        return name, band, "cached"
    url = f"{BASE}/{name}/{tile[:3]}/{tile}/unwise-{tile}-w{band}-img-m.fits"
    hdr, hlen = read_header(url)
    if hdr is None:
        return name, band, None                       # this epoch has no coverage of the tile
    w = WCS(hdr)
    px, py = w.world_to_pixel_values(ra, dec)
    nx, ny = hdr["NAXIS1"], hdr["NAXIS2"]
    x0, y0 = int(round(float(px))) - size // 2, int(round(float(py))) - size // 2
    x0, y0 = max(0, min(nx - size, x0)), max(0, min(ny - size, y0))
    bpp = abs(hdr["BITPIX"]) // 8                     # rows are contiguous: one range request for all rows
    r = get(url, (hlen + y0 * nx * bpp, hlen + (y0 + size) * nx * bpp - 1))
    if r is None or r.status_code not in (200, 206):
        return name, band, "FAILED"
    cut = np.frombuffer(r.content, dtype=">f4").reshape(size, nx)[:, x0:x0 + size].astype("f4")
    h = fits.Header()
    h.update(w.slice((slice(y0, y0 + size), slice(x0, x0 + size))).to_header())
    for k in ("MJDMIN", "MJDMAX", "MJDMEAN", "BAND", "TILE"):
        if k in hdr:
            h[k] = hdr[k]
    h["EPOCH_ID"] = e
    fits.PrimaryHDU(cut, h).writeto(dest, overwrite=True)
    return name, band, f"MJD {hdr.get('MJDMIN'):.0f}..{hdr.get('MJDMAX'):.0f}"


tile = resolve_tile()
print(f"RA {ra} Dec {dec}: tile {tile}", flush=True)
jobs = [(tile, b, e) for b in bands for e in range(0, 30)]
with ThreadPoolExecutor(8) as ex:
    res = [r for r in ex.map(one, jobs) if r[2]]
for b in bands:
    got = [r for r in res if r[1] == b and r[2] != "FAILED"]
    print(f"band W{b}: {len(got)} epochs", "FAILED: " + str([r[0] for r in res if r[1] == b and r[2] == "FAILED"])
          if any(r[2] == "FAILED" for r in res if r[1] == b) else "")
