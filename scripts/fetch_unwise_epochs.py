"""Download time-resolved unWISE (WISE/NEOWISE) cutouts, one per epoch, using HTTP range requests.
Usage: fetch_unwise_epochs.py RA DEC TILE [SIZE_PIX=100] [BAND=2]
  TILE is the unWISE tile name covering the position, e.g. 1342m076 (WISE 0855).
Source: NERSC neo8 time-resolved coadds (Aaron Meisner, same data as WiseView). Pixels are 2.75 arcsec.
Saves data/raw/unwise_epochs/<ra>_<dec>/e###_w<band>.fits (small FITS with WCS + MJD range). Gitignored.
"""
import sys
import time
from pathlib import Path

import numpy as np
import requests
from astropy.io import fits
from astropy.wcs import WCS

ra, dec, tile = float(sys.argv[1]), float(sys.argv[2]), sys.argv[3]
size = int(sys.argv[4]) if len(sys.argv) > 4 else 100
band = sys.argv[5] if len(sys.argv) > 5 else "2"
BASE = "https://portal.nersc.gov/project/cosmo/temp/ameisner/neo8"
out = Path(f"data/raw/unwise_epochs/{sys.argv[1]}_{sys.argv[2]}")
out.mkdir(parents=True, exist_ok=True)
sess = requests.Session()


def get(url, rng=None, tries=4):
    for _ in range(tries):
        try:
            r = sess.get(url, headers={"Range": f"bytes={rng[0]}-{rng[1]}"} if rng else {}, timeout=120)
            if r.status_code in (200, 206, 404):
                return r
        except requests.RequestException:
            pass
        time.sleep(2)
    return None


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
    hlen = ((idx + 80 + 2879) // 2880) * 2880
    return fits.Header.fromstring(raw[:hlen].decode("ascii")), hlen


n_ok = 0
for e in range(0, 60):
    name = f"e{e:03d}"
    dest = out / f"{name}_w{band}.fits"
    if dest.exists():
        n_ok += 1
        continue
    url = f"{BASE}/{name}/{tile[:3]}/{tile}/unwise-{tile}-w{band}-img-m.fits"
    hdr, hlen = read_header(url)
    if hdr is None:
        continue                                     # this epoch has no coverage of the tile
    w = WCS(hdr)
    px, py = w.world_to_pixel_values(ra, dec)
    nx, ny = hdr["NAXIS1"], hdr["NAXIS2"]
    x0, y0 = int(round(float(px))) - size // 2, int(round(float(py))) - size // 2
    x0, y0 = max(0, min(nx - size, x0)), max(0, min(ny - size, y0))
    # float32 big-endian, rows are contiguous: fetch rows y0..y0+size-1 in one range request
    bpp = abs(hdr["BITPIX"]) // 8
    start = hlen + y0 * nx * bpp
    end = hlen + (y0 + size) * nx * bpp - 1
    r = get(url, (start, end))
    if r is None or r.status_code not in (200, 206):
        print(name, "data fetch failed")
        continue
    rows = np.frombuffer(r.content, dtype=">f4").reshape(size, nx)
    cut = rows[:, x0:x0 + size].astype("f4")
    h = fits.Header()
    h.update(w.slice((slice(y0, y0 + size), slice(x0, x0 + size))).to_header())
    for k in ("MJDMIN", "MJDMAX", "MJDMEAN", "BAND", "TILE"):
        if k in hdr:
            h[k] = hdr[k]
    h["EPOCH_ID"] = e
    fits.PrimaryHDU(cut, h).writeto(dest, overwrite=True)
    n_ok += 1
    print(name, "OK", f"MJD {hdr.get('MJDMIN')}..{hdr.get('MJDMAX')}", "window", (x0, y0), flush=True)
print("epochs saved:", n_ok)
