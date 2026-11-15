"""Run Mover Spotter on cached real data and print what it finds. Usage (from repo root, with -m):
  .venv/Scripts/python -m scripts.check_movers RA DEC [DETECTOR=W2]
"""
import sys
import time

from backend import cutouts
from backend.app import MOVER_PARAMS
from backend.movers import detect_sources, spot_movers

ra, dec = float(sys.argv[1]), float(sys.argv[2])
det = sys.argv[3] if len(sys.argv) > 3 else "W2"
frames = cutouts.load_frames(ra, dec, det)
print(len(frames), "frames", frames[0].date[:10], "->", frames[-1].date[:10])
params = MOVER_PARAMS.get(det, {})
print("sources per frame:", [len(detect_sources(f.image, params.get("nsigma", 5.0))[0]) for f in frames])
t0 = time.time()
need = max(5, round(0.4 * len(frames)))
found = spot_movers(frames, (ra, dec), min_frames=need, **params)
print(f"{len(found)} movers in {time.time() - t0:.1f}s (min frames {need})")
for m in found:
    p = m["points"]
    print(f" #{m['id'] + 1}: {m['rate_arcsec_per_year']:.1f} arcsec/yr, seen in {m['n_detections']}/{len(frames)} frames,"
          f" pixel start ({p[0]['px']:.1f},{p[0]['py']:.1f}) end ({p[-1]['px']:.1f},{p[-1]['py']:.1f})")
