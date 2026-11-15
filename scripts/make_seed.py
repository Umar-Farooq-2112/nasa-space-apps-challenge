"""Build seed/ for deployments: the compact sky index (seed/index/<det>.npz) and the demo targets' cutouts
without the PSF table (seed/cutouts/, ~200 KB per image instead of 4 MB).
Run after building the index and fetching the presets:  .venv/Scripts/python -m scripts.make_seed"""
from astropy.io import fits

from backend import cutouts, sky_index
from backend.targets import TARGETS

for det in ("D2", "D3", "D6"):
    sky_index.export(det)
for t in TARGETS:
    src = cutouts.folder_for(t["ra"], t["dec"], 0.1)
    dst = cutouts.SEED / src.name
    dst.mkdir(parents=True, exist_ok=True)
    for it in cutouts.list_frames(src, t["detector"]):
        with fits.open(src / it["file"]) as h:
            fits.HDUList([x for x in h if x.name != "EPSF"]).writeto(dst / it["file"], overwrite=True)
    print(t["name"], len(list(dst.glob("*.fits"))))
