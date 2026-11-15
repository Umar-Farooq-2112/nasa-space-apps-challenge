"""Find + download + convert cutouts for all demo targets. Usage: fetch_all.py [DETECTOR=D3] [N=20]
Run from the repo root. Slow because IRSA is often busy; safe to re-run (skips existing files).
"""
import subprocess
import sys

from astropy.coordinates import SkyCoord

det = sys.argv[1] if len(sys.argv) > 1 else "D3"
n = sys.argv[2] if len(sys.argv) > 2 else "20"

# name -> SIMBAD names to try (WISE 0855 uses fixed coordinates from the challenge page)
TARGETS = {
    "wise0855": (133.7951, -7.2451),
    "barnards_star": ["Barnard's star"],
    "eps_indi_b": ["eps Ind B", "eps Ind A"],
    "rw_aur": ["RW Aur"],
    "r_dra": ["R Dra"],
}

py = sys.executable
for name, spec in TARGETS.items():
    if isinstance(spec, tuple):
        ra, dec = spec
    else:
        for q in spec:
            try:
                c = SkyCoord.from_name(q)
                break
            except Exception as e:
                print("name lookup failed:", q, e, flush=True)
        else:
            continue
        ra, dec = round(c.ra.deg, 4), round(c.dec.deg, 4)
    print(f"=== {name}: RA {ra} Dec {dec}", flush=True)
    for script, extra in (("find_images.py", [det]), ("download_cutouts.py", ["0.1", n])):
        args = [py, "-I", f"scripts/{script}", str(ra), str(dec)] + extra
        subprocess.run(args, check=False)
    subprocess.run([py, "-I", "scripts/fits_to_png.py", str(ra), str(dec)], check=False)
