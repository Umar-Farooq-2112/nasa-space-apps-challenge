"""Convert downloaded FITS cutouts to PNG frames, sorted by date.
Usage: fits_to_png.py RA DEC   (reads data/raw/cutouts/<ra>_<dec>/, writes data/frames/<ra>_<dec>/)
"""
import sys
from pathlib import Path

import numpy as np
from astropy.io import fits
from PIL import Image

ra, dec = sys.argv[1], sys.argv[2]
det = sys.argv[3] if len(sys.argv) > 3 else ""   # e.g. D3: skip other detectors
src = Path(f"data/raw/cutouts/{ra}_{dec}")
dst = Path(f"data/frames/{ra}_{dec}")
dst.mkdir(parents=True, exist_ok=True)

for f in sorted(src.glob(f"*_{det}_*.fits" if det else "*.fits")):
    with fits.open(f) as h:
        img = h["IMAGE"].data.astype(float)
        flags = h["FLAGS"].data
        date = h["IMAGE"].header["DATE-OBS"][:10]
    img = np.nan_to_num(img, nan=np.nanmedian(img))
    lo, hi = np.percentile(img, [1, 99.5])           # percentile stretch
    s = np.arcsinh(np.clip((img - lo) / (hi - lo), 0, 1) * 10) / np.arcsinh(10)
    pic = Image.fromarray((s * 255).astype(np.uint8)).resize((s.shape[1] * 6, s.shape[0] * 6), Image.NEAREST)
    pic = pic.transpose(Image.FLIP_TOP_BOTTOM)           # FITS origin is bottom-left
    out = dst / (f.stem.split("_level2")[0] + f"_{date}.png")
    pic.save(out)
    print(out.name, "bad pixels:", int((flags != 0).sum()))
