"""Download unWISE cutouts (one per release = one per time period) for a sky position.
Usage: fetch_unwise.py RA DEC [SIZE_PIX=100] [BAND=2]
Saves image FITS to data/raw/unwise/<ra>_<dec>/<version>_w<band>.fits (gitignored) and prints header info.
unWISE pixels are 2.75 arcsec. Releases: allwise (2010) then neo1..neo7, neo11 (one per NEOWISE year).
"""
import io
import sys
import tarfile
import time
from pathlib import Path

import requests
from astropy.io import fits

ra, dec = sys.argv[1], sys.argv[2]
size = sys.argv[3] if len(sys.argv) > 3 else "100"
band = sys.argv[4] if len(sys.argv) > 4 else "2"
VERSIONS = ["allwise", "neo1", "neo2", "neo3", "neo4", "neo5", "neo6", "neo7", "neo11"]

out = Path(f"data/raw/unwise/{ra}_{dec}")
out.mkdir(parents=True, exist_ok=True)

for v in VERSIONS:
    dest = out / f"{v}_w{band}.fits"
    if dest.exists():
        print(v, "cached")
        continue
    params = {"version": v, "ra": ra, "dec": dec, "size": size, "bands": band,
              "file_img_m": "on"}  # image only
    for attempt in range(4):
        try:
            r = requests.get("https://unwise.me/cutout_fits", params=params, timeout=120)
            if r.status_code == 200:
                break
        except requests.RequestException as e:
            print(v, "retry", type(e).__name__)
        time.sleep(3)
    else:
        print(v, "FAILED")
        continue
    try:
        with tarfile.open(fileobj=io.BytesIO(r.content)) as t:
            names = [n for n in t.getnames() if "-img-m" in n]
            if not names:
                print(v, "no image in tar:", t.getnames())
                continue
            dest.write_bytes(t.extractfile(names[0]).read())
    except tarfile.TarError:
        print(v, "not a tar:", r.content[:100])
        continue
    h = fits.getheader(dest)
    print(v, "OK", dest.stat().st_size, "bytes", fits.getdata(dest).shape,
          {k: h[k] for k in ("MJDMIN", "MJDMAX", "MJDMEAN", "CTYPE1") if k in h})
