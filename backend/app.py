"""Mover Spotter API. Run from repo root: .venv/Scripts/python -m uvicorn backend.app:app --reload"""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from . import cutouts, movers
from .targets import TARGETS

app = FastAPI(title="Mover Spotter")


@app.get("/api/targets")
def targets():
    return TARGETS


@app.get("/api/frames")
def frames(ra: float, dec: float, fov: float = 0.1, detector: str = "all"):
    """Frames for a sky spot, oldest first. fov (deg) is reserved for live IRSA fetching (TODO)."""
    items = cutouts.list_frames(ra, dec, detector)
    if items is None:
        raise HTTPException(404, "No cached data for this position yet.")
    for it in items:
        it["png_url"] = f"/api/frame.png?folder={it['folder']}&file={it['file']}"
    return {"ra": ra, "dec": dec, "fov": fov, "frames": items}


@app.get("/api/movers")
def find_movers(ra: float, dec: float, detector: str = "D3"):
    """Detected movers. Use ONE detector: other detectors see other wavelengths, so stars vary."""
    frames = cutouts.load_frames(ra, dec, detector)
    if not frames:
        raise HTTPException(404, "No cached data for this position/detector.")
    if len(frames) < 5:
        return {"movers": [], "note": f"Need at least 5 frames to spot movers, have {len(frames)}."}
    need = max(5, round(0.4 * len(frames)))  # a real source shows up in most frames; blocks chance matches
    return {"movers": movers.spot_movers(frames, (ra, dec), min_frames=need), "scale": cutouts.SCALE,
            "frame_heights": [f.image.shape[0] for f in frames]}


@app.get("/api/frame.png")
def frame_png(folder: str, file: str):
    # block path tricks like ../
    if Path(folder).name != folder or Path(file).name != file or not file.endswith(".fits"):
        raise HTTPException(400, "bad name")
    if not (cutouts.CACHE / folder / file).exists():
        raise HTTPException(404, "not found")
    return Response(cutouts.render_png(folder, file), media_type="image/png")


app.mount("/", StaticFiles(directory=Path(__file__).resolve().parent.parent / "frontend", html=True))
