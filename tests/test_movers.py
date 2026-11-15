"""Synthetic test: static stars + pointing jitter + injected movers. Run: .venv/Scripts/python -m pytest -q"""
import numpy as np
from astropy.wcs import WCS

from backend.movers import PIX_ARCSEC, Frame, spot_movers

RA0, DEC0, N = 133.8, -7.2, 60


def make_wcs(dx_arcsec, dy_arcsec):
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.cdelt = [-PIX_ARCSEC / 3600, PIX_ARCSEC / 3600]
    w.wcs.crpix = [N / 2, N / 2]
    w.wcs.crval = [RA0 + dx_arcsec / 3600 / np.cos(np.radians(DEC0)), DEC0 + dy_arcsec / 3600]
    return w


def star(img, x, y, amp, sig=1.1):
    yy, xx = np.mgrid[0:N, 0:N]
    img += amp * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * sig ** 2))


def build(movers, n_frames=15, seed=1):
    rng = np.random.default_rng(seed)
    stars = rng.uniform(6, N - 6, size=(25, 2))
    amps = rng.uniform(25, 80, 25)
    mjds = 60800 + np.sort(rng.uniform(0, 360, n_frames))
    frames = []
    for m in mjds:
        img = rng.normal(0, 1, (N, N))
        off = rng.normal(0, 1.0, 2)                  # pointing error (arcsec) shifts the whole frame
        w = make_wcs(*off)
        for (x, y), a in zip(stars, amps):
            star(img, x, y, a)
        for (x0, y0, vx_pix_day, vy_pix_day, a) in movers:
            star(img, x0 + vx_pix_day * (m - mjds[0]), y0 + vy_pix_day * (m - mjds[0]), a)
        frames.append(Frame(float(m), "2025-01-01", "D3", img, w))
    return frames


def run(frames):
    return spot_movers(frames, (RA0, DEC0))


def test_no_movers_when_all_static():
    assert run(build([])) == []


def test_slow_mover_found():
    # ~0.004 px/day = 1.4 px (8.6 arcsec) over the year, like a brown dwarf
    movers = run(build([(48.0, 48.0, 0.004, -0.002, 60.0)]))
    assert len(movers) == 1
    m = movers[0]
    expected = np.hypot(0.004, 0.002) * PIX_ARCSEC * 365.25
    assert abs(m["rate_arcsec_per_year"] - expected) < 0.3 * expected
    assert m["n_detections"] >= 10 and len(m["points"]) == 15


def test_fast_and_slow_movers():
    movers = run(build([(15.0, 40.0, 0.05, 0.0, 80.0), (45.0, 20.0, 0.0, -0.006, 70.0)]))
    assert len(movers) == 2
