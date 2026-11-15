"""Pre-download cutouts for all demo targets so the demo works even when IRSA is down.
Usage (from repo root): .venv/Scripts/python -m scripts.fetch_all [DETECTOR or "preset"] [N=20] [FOV=0.1]
"preset" (default) uses each target's own detector. Same code and cache as the app's live fetch; safe to re-run."""
import sys

from backend import irsa
from backend.cutouts import folder_for
from backend.targets import TARGETS

det = sys.argv[1] if len(sys.argv) > 1 else "preset"
n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
fov = float(sys.argv[3]) if len(sys.argv) > 3 else 0.1

for t in TARGETS:
    d = t["detector"] if det == "preset" else det
    folder = folder_for(t["ra"], t["dec"], fov)
    print(f"=== {t['name']} ({d}): RA {t['ra']} Dec {t['dec']} -> {folder.name}", flush=True)
    try:
        irsa.fetch(t["ra"], t["dec"], fov, d, folder, n)
        print("cutouts:", len(list(folder.glob(f"*_{d}_*.fits"))), flush=True)
    except RuntimeError as e:
        print("failed:", e, flush=True)
