"""Mover Spotter: find sources whose sky position changes between frames.

Steps (all positions in arcsec offsets from the field centre, so frames need no resampling):
1. detect_sources: threshold the background-subtracted image, centroid each peak.
2. find_tracks: find sets of detections (one per frame) that lie on a straight line in time.
   Static stars are tracks with ~zero speed; movers are tracks with real speed.
3. fix frame offsets: static stars should not move, so any common shift per frame is pointing error;
   subtract it and refit.
4. light curve: measure brightness at the track position in every frame.
"""
from dataclasses import dataclass

import numpy as np
from astropy.wcs.utils import proj_plane_pixel_scales
from scipy import ndimage
from scipy.stats import binom

PIX_ARCSEC = 6.15


@dataclass
class Frame:
    mjd: float
    date: str
    detector: str
    image: np.ndarray
    wcs: object  # astropy WCS (celestial, 2D)


def detect_sources(image, nsigma=5.0, max_sources=60):
    """Return (px, py, flux) arrays of detected peaks (pixel coords, 0-based)."""
    img = np.nan_to_num(image.astype(float), nan=np.nanmedian(image))
    bkg = np.median(img)
    sigma = 1.4826 * np.median(np.abs(img - bkg))
    if sigma <= 0:
        return np.empty(0), np.empty(0), np.empty(0)
    sm = ndimage.gaussian_filter(img - bkg, 0.8)
    s_sm = sigma / 2.0  # smoothing lowers noise by about this factor
    peaks = (sm == ndimage.maximum_filter(sm, size=3)) & (sm > nsigma * s_sm)
    ys, xs = np.nonzero(peaks)
    keep = (xs > 0) & (ys > 0) & (xs < img.shape[1] - 1) & (ys < img.shape[0] - 1)
    ys, xs = ys[keep], xs[keep]
    px, py, fl = [], [], []
    for x, y in zip(xs, ys):  # centroid in 3x3 box
        box = np.clip(img[y - 1:y + 2, x - 1:x + 2] - bkg, 0, None)
        tot = box.sum()
        if tot <= 0:
            continue
        gy, gx = np.mgrid[-1:2, -1:2]
        px.append(x + (box * gx).sum() / tot)
        py.append(y + (box * gy).sum() / tot)
        fl.append(tot)
    order = np.argsort(fl)[::-1][:max_sources]
    return np.array(px)[order], np.array(py)[order], np.array(fl)[order]


def _to_arcsec(frame, px, py, centre):
    sky = frame.wcs.pixel_to_world(px, py)
    ra0, dec0 = centre
    x = (sky.ra.deg - ra0) * np.cos(np.radians(dec0)) * 3600.0
    y = (sky.dec.deg - dec0) * 3600.0
    return x, y


def _fit(t, x, y):
    """Linear fit position vs time. Returns x0, y0, vx, vy, rms residual (arcsec, per day)."""
    A = np.vstack([np.ones_like(t), t]).T
    cx, *_ = np.linalg.lstsq(A, x, rcond=None)
    cy, *_ = np.linalg.lstsq(A, y, rcond=None)
    res = np.hypot(x - A @ cx, y - A @ cy)
    return cx[0], cy[0], cx[1], cy[1], float(np.sqrt(np.mean(res ** 2)))


def find_tracks(t, dets, tol=4.0, max_rate=300.0, min_frames=4):
    """t: days per frame. dets: per frame (x, y) arcsec arrays. Returns list of {frame_idx: det_idx}.
    tol: match radius (arcsec); max_rate: fastest allowed speed (arcsec/day).
    For each pair of detections in two frames we assume straight-line motion and count how many
    other frames have a detection near the predicted spot (vectorised with numpy)."""
    n = len(dets)
    D = max((len(d[0]) for d in dets), default=0)
    if D == 0:
        return []
    X = np.full((n, D), np.inf)
    Y = np.full((n, D), np.inf)
    for f, (x, y) in enumerate(dets):
        X[f, :len(x)], Y[f, :len(y)] = x, y
    hyps = []
    for a in range(n):
        for b in range(a + 1, n):
            dt = t[b] - t[a]
            xa, ya = dets[a]
            xb, yb = dets[b]
            if dt < 1e-3 or len(xa) == 0 or len(xb) == 0:
                continue
            dtf = (t - t[a])[None, :]
            for i in range(len(xa)):
                vx, vy = (xb - xa[i]) / dt, (yb - ya[i]) / dt
                ok = np.hypot(vx, vy) <= max_rate
                if not ok.any():
                    continue
                px = xa[i] + vx[ok, None] * dtf                      # predicted x per frame, (J, n)
                py = ya[i] + vy[ok, None] * dtf
                d = np.hypot(X[None] - px[:, :, None], Y[None] - py[:, :, None])   # (J, n, D)
                k, dmin = d.argmin(2), d.min(2)
                hit = dmin <= tol
                for q in np.nonzero(hit.sum(1) >= min_frames)[0]:
                    hyps.append({int(f): int(k[q, f]) for f in np.nonzero(hit[q])[0]})
    hyps.sort(key=len, reverse=True)
    used, tracks = set(), []
    for m in hyps:
        if any((f, k) in used for f, k in m.items()):
            continue
        tracks.append(m)
        used.update(m.items())
    return tracks


def pixel_scale(frame):
    """Mean pixel size in arcsec, from the frame's WCS."""
    return float(np.mean(proj_plane_pixel_scales(frame.wcs)) * 3600.0)


def significant_min_frames(dets, t, tol, field_arcsec, alpha=0.05):
    """Fewest frames a track must appear in so that a CHANCE alignment is unlikely (look-elsewhere effect).
    We try roughly (pairs of frames) x (detections)^2 candidate lines; with D random sources per frame inside a
    field of area A, a random source lands within tol of a line with probability p = D*pi*tol^2/A.
    Returns the smallest k with  expected_false_tracks = trials * P(k-2 or more extra hits) < alpha."""
    n = len(t)
    D = float(np.mean([len(d[0]) for d in dets])) if dets else 0.0
    if n < 3 or D < 1:
        return 3
    p = min(D * np.pi * tol ** 2 / field_arcsec ** 2, 0.5)
    trials = (n * (n - 1) / 2) * D * D
    for k in range(3, n + 1):
        if trials * binom.sf(k - 3, n - 2, p) < alpha:
            return k
    return n


def spot_movers(frames, centre, min_frames=4, nsigma=5.0, tol=None, max_rate=None,
                min_disp=None, min_sig=4.0):
    """Main entry. Returns list of track dicts (movers only) with per-frame pixel positions + flux.
    Unless given, the limits come from the data itself (nothing is tuned to one target):
      tol      = 2 pixels (match radius)
      min_disp = half a pixel (a mover must travel at least this far over the whole time span)
      max_rate = fast enough to cross half the field during the time span
    """
    scale = pixel_scale(frames[0])
    span_days = max(max(f.mjd for f in frames) - min(f.mjd for f in frames), 1e-3)
    field = max(frames[0].image.shape) * scale
    tol = 2.0 * scale if tol is None else tol
    min_disp = 0.5 * scale if min_disp is None else min_disp
    max_rate = 0.5 * field / span_days if max_rate is None else max_rate
    frames = sorted(frames, key=lambda f: f.mjd)
    t = np.array([f.mjd for f in frames]) - frames[0].mjd
    raw = [detect_sources(f.image, nsigma) for f in frames]
    dets = [_to_arcsec(f, px, py, centre) for f, (px, py, _) in zip(frames, raw)]

    min_frames = max(min_frames, significant_min_frames(dets, t, tol, field))
    tracks = find_tracks(t, dets, tol, max_rate, min_frames)

    def fit_all(dets):
        out = []
        for m in tracks:
            fs = sorted(m)
            x = np.array([dets[f][0][m[f]] for f in fs])
            y = np.array([dets[f][1][m[f]] for f in fs])
            out.append((fs, x, y, _fit(t[fs], x, y)))
        return out

    # per-frame common shift from the (nearly) static stars = pointing error
    fits_ = fit_all(dets)
    span = max(t[-1], 1e-6)
    static = [(fs, x, y, p) for fs, x, y, p in fits_ if np.hypot(p[2], p[3]) * span < min_disp]
    shifts = np.zeros((len(frames), 2))
    for f in range(len(frames)):
        r = [(x[fs.index(f)] - (p[0] + p[2] * t[f]), y[fs.index(f)] - (p[1] + p[3] * t[f]))
             for fs, x, y, p in static if f in fs]
        if len(r) >= 3:
            shifts[f] = np.median(np.array(r), axis=0)
    dets = [(d[0] - shifts[i, 0], d[1] - shifts[i, 1]) for i, d in enumerate(dets)]

    movers = []
    for fs, x, y, _ in fit_all(dets):
        x0, y0, vx, vy, rms = _fit(t[fs], x, y)
        rate = float(np.hypot(vx, vy))
        disp = rate * span
        denom = np.sqrt(np.sum((t[fs] - np.mean(t[fs])) ** 2))
        err = max(rms, 0.05 * scale) / denom if denom > 0 else np.inf  # floor: centroid noise ~1/20 pixel
        if disp < min_disp or rate / err < min_sig:
            continue
        pts = []
        for i, fr in enumerate(frames):  # predicted position in every frame, then measure flux there
            ex = x0 + vx * t[i] + shifts[i, 0]
            ey = y0 + vy * t[i] + shifts[i, 1]
            ra0, dec0 = centre
            ra = ra0 + ex / 3600.0 / np.cos(np.radians(dec0))
            dec = dec0 + ey / 3600.0
            px, py = fr.wcs.world_to_pixel_values(ra, dec)
            ix, iy = int(round(float(px))), int(round(float(py)))
            ok = 1 <= ix < fr.image.shape[1] - 1 and 1 <= iy < fr.image.shape[0] - 1
            flux = float(np.nansum(fr.image[iy - 1:iy + 2, ix - 1:ix + 2])) if ok else None
            pts.append({"frame": i, "px": float(px), "py": float(py), "flux": flux,
                        "detected": i in fs})
        movers.append({"rate_arcsec_per_day": rate, "rate_arcsec_per_year": rate * 365.25,
                       "n_detections": len(fs), "points": pts})
    _flag_artifacts(movers)
    movers.sort(key=lambda m: (m["artifact"] is not None, -m["n_detections"]))
    for k, m in enumerate(movers):
        m["id"] = k
    return movers


def _flag_artifacts(movers, halo_px=10.0, ghost_std_px=1.5, ghost_flux_ratio=0.02):
    """Very bright stars create fake sources that travel with them. Flag (never delete) two kinds:
      halo     : stays within halo_px pixels of a brighter track in every frame (glare, spikes, saturation)
      comoving : keeps an almost constant offset from a much brighter track (optical ghost image, or a true companion)
    The brighter track is the real one. Flagged tracks carry artifact='halo'|'comoving' and of=<index of the star>."""
    for m in movers:
        f = [p["flux"] for p in m["points"] if p["detected"] and p["flux"] is not None]
        m["_flux"] = float(np.mean(f)) if f else 0.0
        m["artifact"], m["of"] = None, None
    xy = lambda m: np.array([[p["px"], p["py"]] for p in m["points"]])
    for b in movers:
        for a in sorted(movers, key=lambda m: -m["_flux"]):
            if a is b or a["_flux"] <= b["_flux"] or a["artifact"]:
                continue
            off = xy(b) - xy(a)
            dist = np.hypot(off[:, 0], off[:, 1])
            if dist.max() < halo_px:
                b["artifact"], b["of"] = "halo", a
            elif off.std(axis=0).max() < ghost_std_px and b["_flux"] < ghost_flux_ratio * a["_flux"]:
                b["artifact"], b["of"] = "comoving", a
            if b["artifact"]:
                break
    movers_sorted = sorted(movers, key=lambda m: (m["artifact"] is not None, -m["n_detections"]))
    index = {id(m): k for k, m in enumerate(movers_sorted)}
    for m in movers:
        m["of"] = index[id(m["of"])] if m["of"] is not None else None
    for m in movers:
        m.pop("_flux")
