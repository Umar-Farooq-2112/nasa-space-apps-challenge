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
from scipy import ndimage
from scipy.spatial import cKDTree

PIX_ARCSEC = 6.15


@dataclass
class Frame:
    mjd: float
    date: str
    detector: str
    image: np.ndarray
    wcs: object  # astropy WCS (celestial, 2D)
    wave: object = None  # optional astropy WCS: pixel -> (wavelength um, bandwidth um)


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
    tol: match radius (arcsec); max_rate: fastest allowed speed (arcsec/day)."""
    n = len(dets)
    pts = [np.column_stack(d) if len(d[0]) else np.empty((0, 2)) for d in dets]
    trees = [cKDTree(p) if len(p) else None for p in pts]
    hyps = []
    for a in range(n):
        for b in range(a + 1, n):
            dt = t[b] - t[a]
            if dt < 1e-3 or not len(pts[a]) or not len(pts[b]):
                continue
            # every (i in a, j in b) pair at once: velocity grid, then nearest detection per frame via KD-tree
            v = (pts[b][None, :, :] - pts[a][:, None, :]) / dt          # (I, J, 2)
            ok = np.hypot(v[..., 0], v[..., 1]) <= max_rate
            ii, jj = np.nonzero(ok)
            if not len(ii):
                continue
            start, vel = pts[a][ii], v[ii, jj]
            idx = np.full((len(ii), n), -1)
            for f in range(n):
                if trees[f] is None:
                    continue
                d, k = trees[f].query(start + vel * (t[f] - t[a]), distance_upper_bound=tol)
                idx[np.isfinite(d), f] = k[np.isfinite(d)]
            for row in idx[(idx >= 0).sum(axis=1) >= min_frames]:
                hyps.append({f: int(k) for f, k in enumerate(row) if k >= 0})
    hyps.sort(key=len, reverse=True)
    used, tracks = set(), []
    for m in hyps:
        if any((f, k) in used for f, k in m.items()):
            continue
        tracks.append(m)
        used.update(m.items())
    return tracks


def spot_movers(frames, centre, min_frames=4, nsigma=5.0, tol=4.0, max_rate=300.0,
                min_disp=3.0, min_sig=4.0, half_size=None):
    """Main entry. Returns list of track dicts (movers only) with per-frame pixel positions + flux.
    half_size (arcsec): only use detections within this box around centre (cutout edges give fake tracks)."""
    frames = sorted(frames, key=lambda f: f.mjd)
    t = np.array([f.mjd for f in frames]) - frames[0].mjd
    raw = [detect_sources(f.image, nsigma) for f in frames]
    dets = [_to_arcsec(f, px, py, centre) for f, (px, py, _) in zip(frames, raw)]
    if half_size:
        dets = [(x[keep], y[keep]) for x, y in dets for keep in [(np.abs(x) <= half_size) & (np.abs(y) <= half_size)]]

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
        err = max(rms, 0.3) / denom if denom > 0 else np.inf  # floor: centroid noise ~0.3 arcsec
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
            ok = 3 <= ix < fr.image.shape[1] - 3 and 3 <= iy < fr.image.shape[0] - 3
            flux = lam = None
            if ok:   # aperture photometry: 3x3 sum minus the local sky from the surrounding 7x7 ring
                box = fr.image[iy - 3:iy + 4, ix - 3:ix + 4]
                ring = np.concatenate([box[[0, -1]].ravel(), box[1:-1, [0, -1]].ravel()])
                flux = float(np.nansum(box[2:5, 2:5]) - 9 * np.nanmedian(ring))
                if fr.wave is not None:   # SPHEREx: every pixel sees its own wavelength (linear variable filter)
                    lam = float(fr.wave.pixel_to_world_values(px, py)[0])
            pts.append({"frame": i, "px": float(px), "py": float(py), "ra": float(ra), "dec": float(dec),
                        "flux": flux, "wavelength_um": lam, "detected": i in fs})
        movers.append({"rate_arcsec_per_day": rate, "rate_arcsec_per_year": rate * 365.25,
                       "rate_err_arcsec_per_year": float(err * 365.25),
                       "pa_deg": float(np.degrees(np.arctan2(vx, vy)) % 360),   # east of north
                       "displacement_arcsec": float(disp), "span_days": float(span),
                       "fit_rms_arcsec": float(rms), "significance": float(rate / err),
                       "n_detections": len(fs), "points": pts})
    movers.sort(key=lambda m: m["n_detections"], reverse=True)
    for k, m in enumerate(movers):
        m["id"] = k
    return movers
